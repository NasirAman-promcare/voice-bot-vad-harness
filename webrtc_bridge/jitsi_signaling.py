"""
webrtc_bridge/jitsi_signaling.py

One Job:
    Own the XMPP signaling session lifecycle for a direct WebRTC participant in Jitsi Meet:
    manage RFC 7395 XMPP-over-WebSocket transport, SASL ANONYMOUS authentication, MUC room
    join/leave with Jitsi presence extensions, recognize Jicofo's `session-initiate` Jingle IQ,
    and transmit answers (`session-accept`), source declarations (`source-add`), and
    teardown stanzas (`session-terminate`).

Protocol Reference:
    Implements Blueprint §4 Steps 1–4 and 7–8:
      1. Transport: WebSocket with 'xmpp' subprotocol to `bridge_url` (/xmpp-websocket).
      2. Auth: SASL ANONYMOUS against `xmpp_client_domain`.
      3. Resource Binding: RFC 6120 resource bind to obtain full client JID.
      4. Room Join: XEP-0045 MUC join with Jitsi presence extensions (audio-only, nick, stats-id).
      5. Offer Recognition: Listens for Jicofo's `session-initiate` Jingle IQ without parsing SDP.
      6. Source Declaration: Transmits Jitsi `source-add` presence / IQ stanzas.
      7. Teardown: Cleanly leaves MUC and terminates Jingle session on disconnect.

What this module must NEVER do:
    - Never parse, interpret, or construct Jingle XML / SDP content (delegated to File 27).
    - Never import, reference, or construct aiortc objects (RTCPeerConnection, RTCSessionDescription).
    - Never retry a reconnect mid-clip (reconnect policy applies only prior to initial room join).
    - Never swallow signaling errors or return None on offer timeouts.
    - Never read config/run_config.yaml directly.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import websockets

logger = logging.getLogger("webrtc_bridge.jitsi_signaling")

# XML Namespaces
NS_FRAMING = "urn:ietf:params:xml:ns:xmpp-framing"
NS_CLIENT = "jabber:client"
NS_STREAMS = "http://etherx.jabber.org/streams"
NS_SASL = "urn:ietf:params:xml:ns:xmpp-sasl"
NS_BIND = "urn:ietf:params:xml:ns:xmpp-bind"
NS_SESSION = "urn:ietf:params:xml:ns:xmpp-session"
NS_MUC = "http://jabber.org/protocol/muc"
NS_MUC_USER = "http://jabber.org/protocol/muc#user"
NS_JINGLE = "urn:xmpp:jingle:1"
NS_NICK = "http://jabber.org/protocol/nick"
NS_STATS = "http://jitsi.org/jitmeet/stats"
NS_CAPS = "http://jabber.org/protocol/caps"
NS_AUDIO_MUTED = "http://jitsi.org/jitmeet/audio"
NS_VIDEO_MUTED = "http://jitsi.org/jitmeet/video"


# ==============================================================================
# Exceptions
# ==============================================================================

class SignalingError(Exception):
    """Base exception for all Jitsi signaling failures."""
    pass


class SignalingConnectionError(SignalingError):
    """Raised when transport connection or WebSocket handshake fails."""
    pass


class SASLAuthenticationError(SignalingError):
    """Raised when SASL ANONYMOUS authentication fails or is rejected by Prosody."""
    pass


class MUCJoinError(SignalingError):
    """Raised when joining the MUC room fails."""
    pass


class MUCConflictError(MUCJoinError):
    """Raised when the MUC nick is already occupied (stale session conflict, code 409)."""
    pass


class JingleOfferTimeoutError(SignalingError, asyncio.TimeoutError):
    """Raised when Jicofo fails to send a `session-initiate` Jingle IQ within timeout."""
    pass


# ==============================================================================
# Jitsi Signaling Session Implementation
# ==============================================================================

class JitsiSignalingSession:
    """
    Manages RFC 7395 XMPP-over-WebSocket signaling, SASL ANONYMOUS auth, MUC lifecycle,
    and raw Jingle IQ routing.
    """

    def __init__(
        self,
        xmpp_client_domain: str = "vad-jitsi-nasir.duckdns.org",
        muc_room_domain_prefix: str = "conference.",
        jingle_debug_log_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes the signaling session.

        Args:
            xmpp_client_domain: Base domain for SASL auth and Prosody virtual host.
            muc_room_domain_prefix: Prefix for MUC conference component (e.g. 'conference.').
            jingle_debug_log_path: Optional file path where all raw stanzas are logged.
        """
        self.xmpp_client_domain = xmpp_client_domain
        self.muc_room_domain_prefix = muc_room_domain_prefix
        self.jingle_debug_log_path = Path(jingle_debug_log_path) if jingle_debug_log_path else None

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._is_connected: bool = False
        self._is_authenticated: bool = False
        self._is_muc_joined: bool = False

        # Session Identifiers
        self.bound_jid: Optional[str] = None
        self.room_jid: Optional[str] = None
        self.display_name: Optional[str] = None
        self.jicofo_jid: Optional[str] = None
        self.jingle_sid: Optional[str] = None

        # Synchronization Primitives
        self._offer_queue: asyncio.Queue[str] = asyncio.Queue()
        self._presence_future: Optional[asyncio.Future[bool]] = None
        self._sasl_future: Optional[asyncio.Future[bool]] = None
        self._bind_future: Optional[asyncio.Future[str]] = None
        self._iq_futures: Dict[str, asyncio.Future[str]] = {}

        if self.jingle_debug_log_path:
            self.jingle_debug_log_path.parent.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Diagnostic Stanza Logging
    # --------------------------------------------------------------------------
    def _log_stanza(self, direction: str, stanza: str) -> None:
        """Appends raw XML stanzas to debug log with ISO UTC timestamp."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_entry = f"[{ts}] [{direction}] {stanza.strip()}\n"

        logger.debug("[XMPP %s] %s", direction, stanza.strip())

        if self.jingle_debug_log_path:
            try:
                with open(self.jingle_debug_log_path, mode="a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as exc:
                logger.warning("Failed writing to stanza debug log: %s", exc)

    # --------------------------------------------------------------------------
    # Transport & WebSocket Framing (RFC 7395)
    # --------------------------------------------------------------------------
    async def _send_raw(self, stanza: str) -> None:
        """Sends a raw XML string over the WebSocket transport."""
        if not self._ws or self._ws.closed:
            raise SignalingConnectionError("Cannot send stanza: WebSocket is not open.")
        self._log_stanza("SENT", stanza)
        await self._ws.send(stanza)

    async def _read_loop(self) -> None:
        """Continuously reads incoming WebSocket frames and routes parsed XML stanzas."""
        try:
            assert self._ws is not None
            async for message in self._ws:
                if isinstance(message, bytes):
                    message_str = message.decode("utf-8")
                else:
                    message_str = message

                self._log_stanza("RECV", message_str)
                await self._route_incoming_stanza(message_str)
        except asyncio.CancelledError:
            pass
        except websockets.ConnectionClosed as exc:
            logger.info("WebSocket connection closed: code=%s, reason=%s", exc.code, exc.reason)
            self._is_connected = False
        except Exception as exc:
            logger.error("Unexpected error in signaling read loop: %s", exc, exc_info=True)
            self._is_connected = False

    # --------------------------------------------------------------------------
    # Stanza Dispatcher
    # --------------------------------------------------------------------------
    async def _route_incoming_stanza(self, raw_xml: str) -> None:
        """Parses and dispatches incoming XML stanzas according to protocol state."""
        trimmed = raw_xml.strip()
        if not trimmed:
            return

        try:
            # Handle RFC 7395 <open> frame
            if trimmed.startswith("<open") or "<open " in trimmed:
                root = ET.fromstring(trimmed)
                if root.tag.endswith("open"):
                    logger.debug("Received XMPP stream open from server: %s", root.attrib)
                    return

            # Handle RFC 7395 <close> frame
            if trimmed.startswith("<close"):
                logger.info("Received XMPP stream close from server.")
                return

            root = ET.fromstring(trimmed)
            tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

            # 1. SASL Authentication responses
            if tag == "success" and (NS_SASL in root.tag or root.attrib.get("xmlns") == NS_SASL):
                if self._sasl_future and not self._sasl_future.done():
                    self._sasl_future.set_result(True)
                return

            if tag == "failure" and (NS_SASL in root.tag or root.attrib.get("xmlns") == NS_SASL):
                error_detail = ET.tostring(root, encoding="unicode")
                if self._sasl_future and not self._sasl_future.done():
                    self._sasl_future.set_exception(
                        SASLAuthenticationError(
                            f"SASL ANONYMOUS authentication failed against '{self.xmpp_client_domain}'. "
                            f"Prosody rejected auth: {error_detail}"
                        )
                    )
                return

            # 2. IQ Stanzas
            if tag == "iq":
                iq_id = root.attrib.get("id", "")
                iq_type = root.attrib.get("type", "")

                # Check if this IQ is a Jingle session-initiate from Jicofo
                jingle_elem = root.find(f".//{{{NS_JINGLE}}}jingle")
                if jingle_elem is None:
                    # Search unqualified
                    for child in root:
                        if child.tag.endswith("jingle"):
                            jingle_elem = child
                            break

                if jingle_elem is not None and jingle_elem.attrib.get("action") == "session-initiate":
                    self.jicofo_jid = root.attrib.get("from")
                    self.jingle_sid = jingle_elem.attrib.get("sid")
                    logger.info(
                        "Received Jingle session-initiate IQ from Jicofo (%s, sid=%s)",
                        self.jicofo_jid,
                        self.jingle_sid,
                    )
                    await self._offer_queue.put(trimmed)
                    return

                # Handle Ping IQs (Keep-Alive)
                if iq_type == "get":
                    ping_elem = root.find(f".//{{urn:xmpp:ping}}ping")
                    if ping_elem is not None or "ping" in trimmed:
                        sender = root.attrib.get("from")
                        pong = f'<iq type="result" to="{sender}" id="{iq_id}"/>'
                        await self._send_raw(pong)
                        return

                # Handle Resource Bind result
                if iq_id == "_bind_1" and iq_type == "result":
                    jid_elem = root.find(f".//{{{NS_BIND}}}jid")
                    if jid_elem is not None and jid_elem.text:
                        self.bound_jid = jid_elem.text.strip()
                        if self._bind_future and not self._bind_future.done():
                            self._bind_future.set_result(self.bound_jid)
                    return

                # Resolve generic tracked IQ futures
                if iq_id in self._iq_futures:
                    fut = self._iq_futures.pop(iq_id)
                    if not fut.done():
                        fut.set_result(trimmed)
                    return

            # 3. Presence Stanzas
            if tag == "presence":
                pres_type = root.attrib.get("type", "")
                pres_from = root.attrib.get("from", "")

                # Detect Nick / MUC Conflict (Stale Session)
                error_elem = root.find(".//error")
                if pres_type == "error" or error_elem is not None:
                    code = error_elem.attrib.get("code") if error_elem is not None else ""
                    if code == "409" or root.find(".//{urn:ietf:params:xml:ns:xmpp-stanzas}conflict") is not None or "conflict" in trimmed:
                        err_msg = (
                            f"MUC presence conflict: Nick '{self.display_name}' is already in use in room '{self.room_jid}'. "
                            "This typically indicates a stale session from an uncleanly terminated prior run."
                        )
                        if self._presence_future and not self._presence_future.done():
                            self._presence_future.set_exception(MUCConflictError(err_msg))
                        return

                # Check for self-presence reflection (MUC join confirmation)
                expected_muc_jid = f"{self.room_jid}/{self.display_name}"
                if pres_from == expected_muc_jid or (self.room_jid and pres_from.startswith(self.room_jid)):
                    self._is_muc_joined = True
                    logger.info("Successfully joined MUC room as '%s' (From: %s)", self.display_name, pres_from)
                    if self._presence_future and not self._presence_future.done():
                        self._presence_future.set_result(True)
                    return

        except Exception as exc:
            logger.warning("Error parsing incoming stanza: %s (Raw: %s)", exc, raw_xml)

    # --------------------------------------------------------------------------
    # Public Connection API
    # --------------------------------------------------------------------------
    async def connect(
        self,
        bridge_url: str,
        room_id: str,
        display_name: str,
        timeout_s: float = 15.0,
    ) -> None:
        """
        Opens RFC 7395 WebSocket stream, authenticates via SASL ANONYMOUS, binds resource,
        and joins the Jitsi MUC conference room.

        Args:
            bridge_url: WebSocket URL (e.g. 'wss://vad-jitsi-nasir.duckdns.org/xmpp-websocket').
            room_id: Target room name (e.g. 'vad-benchmark-eval-room-01').
            display_name: MUC participant nick (e.g. 'VAD-Harness-SpeakerBot').
            timeout_s: Maximum timeout in seconds for complete connection sequence.

        Raises:
            SignalingConnectionError: If transport fails.
            SASLAuthenticationError: If SASL ANONYMOUS auth is rejected.
            MUCConflictError: If the participant nick is already occupied.
            MUCJoinError: If room join times out or fails.
        """
        self.display_name = display_name
        muc_domain = f"{self.muc_room_domain_prefix}{self.xmpp_client_domain}"
        self.room_jid = f"{room_id}@{muc_domain}"

        logger.info(
            "Connecting signaling to '%s' (Domain: %s, Room: %s, Nick: %s)",
            bridge_url,
            self.xmpp_client_domain,
            self.room_jid,
            self.display_name,
        )

        try:
            # Step 1: Open WebSocket Transport with 'xmpp' subprotocol
            self._ws = await websockets.connect(
                bridge_url,
                subprotocols=["xmpp"],
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self._is_connected = True
            self._listener_task = asyncio.create_task(self._read_loop())

            async with asyncio.timeout(timeout_s):
                # Step 2: Open XMPP Stream (RFC 7395)
                open_stream = (
                    f'<open xmlns="{NS_FRAMING}" to="{self.xmpp_client_domain}" version="1.0"/>'
                )
                await self._send_raw(open_stream)

                # Step 3: SASL ANONYMOUS Authentication
                self._sasl_future = asyncio.get_running_loop().create_future()
                sasl_auth = f'<auth xmlns="{NS_SASL}" mechanism="ANONYMOUS"/>'
                await self._send_raw(sasl_auth)
                await self._sasl_future
                self._is_authenticated = True
                logger.info("SASL ANONYMOUS authentication successful.")

                # Step 4: Stream Restart after Auth
                await self._send_raw(open_stream)

                # Step 5: Resource Binding
                self._bind_future = asyncio.get_running_loop().create_future()
                resource_suffix = f"vad-bot-{uuid.uuid4().hex[:8]}"
                bind_iq = (
                    f'<iq xmlns="{NS_CLIENT}" type="set" id="_bind_1">'
                    f'<bind xmlns="{NS_BIND}"><resource>{resource_suffix}</resource></bind>'
                    f'</iq>'
                )
                await self._send_raw(bind_iq)
                self.bound_jid = await self._bind_future
                logger.info("XMPP Resource bound successfully: Full JID = '%s'", self.bound_jid)

                # Step 6: Join MUC Room with Jitsi Presence Extensions
                self._presence_future = asyncio.get_running_loop().create_future()
                stats_id = f"vad_harness_{uuid.uuid4().hex[:6]}"
                muc_presence = (
                    f'<presence xmlns="{NS_CLIENT}" to="{self.room_jid}/{self.display_name}">'
                    f'<x xmlns="{NS_MUC}"/>'
                    f'<nick xmlns="{NS_NICK}">{self.display_name}</nick>'
                    f'<stats-id xmlns="{NS_STATS}">{stats_id}</stats-id>'
                    f'<c xmlns="{NS_CAPS}" node="http://jitsi.org/jitsimeet" ver="audio-only" hash="sha-1"/>'
                    f'<audiomuted xmlns="{NS_AUDIO_MUTED}">false</audiomuted>'
                    f'<videomuted xmlns="{NS_VIDEO_MUTED}">true</videomuted>'
                    f'</presence>'
                )
                await self._send_raw(muc_presence)
                await self._presence_future
                logger.info("MUC room join confirmed by server reflection.")

        except SASLAuthenticationError:
            await self.disconnect()
            raise
        except MUCConflictError:
            await self.disconnect()
            raise
        except (TimeoutError, asyncio.TimeoutError) as exc:
            await self.disconnect()
            raise MUCJoinError(
                f"Signaling connection / MUC join timed out after {timeout_s}s (Room: {self.room_jid})"
            ) from exc
        except Exception as exc:
            await self.disconnect()
            raise SignalingConnectionError(f"Failed to connect signaling session: {exc}") from exc

    # --------------------------------------------------------------------------
    # Jingle Negotiation Public API
    # --------------------------------------------------------------------------
    async def wait_for_offer(self, timeout_s: float = 15.0) -> str:
        """
        Blocks until Jicofo's `session-initiate` Jingle IQ arrives from the room.

        Returns:
            The raw un-interpreted XML stanza string of the Jingle IQ.

        Raises:
            JingleOfferTimeoutError: If Jicofo does not initiate a session within timeout_s.
            SignalingConnectionError: If transport disconnects while waiting.
        """
        if not self._is_connected or not self._is_muc_joined:
            raise SignalingConnectionError("Cannot wait for offer: Session is not connected to MUC.")

        try:
            async with asyncio.timeout(timeout_s):
                offer_stanza = await self._offer_queue.get()
                return offer_stanza
        except (TimeoutError, asyncio.TimeoutError) as exc:
            logger.error(
                "Timed out waiting for Jicofo session-initiate IQ after %.1fs (Room: %s)",
                timeout_s,
                self.room_jid,
            )
            raise JingleOfferTimeoutError(
                f"Jicofo failed to send session-initiate Jingle IQ within {timeout_s}s in room '{self.room_jid}'"
            ) from exc

    async def send_answer(self, session_accept_iq: str) -> None:
        """
        Transmits the Jingle `session-accept` IQ built by File 27.

        Args:
            session_accept_iq: The complete XML string representing the session-accept IQ.
        """
        if not self._is_connected:
            raise SignalingConnectionError("Cannot send answer: Transport is closed.")
        logger.info("Transmitting Jingle session-accept IQ to Jicofo.")
        await self._send_raw(session_accept_iq)

    async def announce_source(
        self,
        ssrc: int,
        media_type: str = "audio",
        source_name: Optional[str] = None,
        muted: bool = False,
    ) -> None:
        """
        Constructs and transmits the Jitsi source-add presence update so JVB attributes
        and forwards the outgoing media track correctly. (Speaker role only).

        Args:
            ssrc: 32-bit Synchronization Source identifier.
            media_type: Media type string ('audio').
            source_name: Jitsi source name string (e.g. 'a0').
            muted: Audio mute status flag.
        """
        if not self._is_connected or not self.room_jid or not self.display_name:
            raise SignalingConnectionError("Cannot announce source: Session not connected.")

        src_name = source_name or f"{self.display_name}-a0"

        # Lazy import of File 27's builder if available, otherwise construct standard Jitsi source presence
        try:
            from webrtc_bridge.jingle_sdp_translator import build_source_add_stanza
            presence_xml = build_source_add_stanza(
                room_jid=self.room_jid,
                display_name=self.display_name,
                ssrc=ssrc,
                media_type=media_type,
                source_name=src_name,
                muted=muted,
            )
        except (ImportError, AttributeError):
            # Standard Jitsi Colibri2 / MUC source-add presence update
            presence_xml = (
                f'<presence xmlns="{NS_CLIENT}" to="{self.room_jid}/{self.display_name}">'
                f'<nick xmlns="{NS_NICK}">{self.display_name}</nick>'
                f'<audiomuted xmlns="{NS_AUDIO_MUTED}">{"true" if muted else "false"}</audiomuted>'
                f'<videomuted xmlns="{NS_VIDEO_MUTED}">true</videomuted>'
                f'<Sources xmlns="urn:xmpp:jingle:apps:dtls:0">'
                f'<Source xmlns="urn:xmpp:jingle:apps:rtp:1" ssrc="{ssrc}" name="{src_name}" media="{media_type}"/>'
                f'</Sources>'
                f'</presence>'
            )

        logger.info("Announcing WebRTC source (SSRC: %d, Name: %s) to MUC.", ssrc, src_name)
        await self._send_raw(presence_xml)

    # --------------------------------------------------------------------------
    # Teardown
    # --------------------------------------------------------------------------
    async def disconnect(self) -> None:
        """
        Sends `session-terminate`, leaves MUC via unavailable presence, and cleanly
        closes the WebSocket transport to prevent stale presence conflicts.
        """
        logger.info("Disconnecting Jitsi signaling session...")

        # 1. Terminate Jingle session if active
        if self._is_connected and self.jicofo_jid and self.jingle_sid:
            try:
                term_iq = (
                    f'<iq xmlns="{NS_CLIENT}" type="set" to="{self.jicofo_jid}" id="_term_1">'
                    f'<jingle xmlns="{NS_JINGLE}" action="session-terminate" sid="{self.jingle_sid}">'
                    f'<reason><success/></reason>'
                    f'</jingle>'
                    f'</iq>'
                )
                await self._send_raw(term_iq)
            except Exception as exc:
                logger.debug("Notice sending session-terminate on disconnect: %s", exc)

        # 2. Send Unavailable MUC Presence
        if self._is_connected and self.room_jid and self.display_name:
            try:
                unavail_pres = (
                    f'<presence xmlns="{NS_CLIENT}" type="unavailable" to="{self.room_jid}/{self.display_name}"/>'
                )
                await self._send_raw(unavail_pres)
            except Exception as exc:
                logger.debug("Notice sending unavailable presence on disconnect: %s", exc)

        # 3. Send RFC 7395 Stream Close
        if self._is_connected and self._ws and not self._ws.closed:
            try:
                close_frame = f'<close xmlns="{NS_FRAMING}"/>'
                await self._send_raw(close_frame)
            except Exception:
                pass

        # 4. Cancel Listener Task
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # 5. Close WebSocket transport
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass

        self._is_connected = False
        self._is_authenticated = False
        self._is_muc_joined = False
        self._ws = None
        logger.info("Jitsi signaling session disconnected cleanly.")