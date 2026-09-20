"""
webrtc_bridge/jitsi_signaling.py

One Job:
    Own the XMPP signaling session lifecycle for a direct WebRTC participant in Jitsi Meet:
    manage RFC 7395 XMPP-over-WebSocket transport, SSL context verification, SASL ANONYMOUS
    authentication, request Jicofo conference focus creation, join MUC room with matching
    participant ID resource, respond to Jicofo's `disco#info` query, recognize Jicofo's
    `session-initiate` Jingle IQ, and transmit answers (`session-accept`), source declarations
    (`source-add`), and teardown stanzas (`session-terminate`).
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import ssl
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


def _is_ws_open(ws: Any) -> bool:
    """Universally checks if WebSocket is open across websockets v10–v15+."""
    if ws is None:
        return False
    if hasattr(ws, "state"):
        try:
            from websockets.protocol import State
            return ws.state == State.OPEN
        except ImportError:
            return str(ws.state).upper().endswith("OPEN")
    if hasattr(ws, "open"):
        return bool(ws.open)
    if hasattr(ws, "closed"):
        return not bool(ws.closed)
    return True


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


class JitsiSignalingSession:
    """
    Manages RFC 7395 XMPP-over-WebSocket signaling, SSL context, SASL ANONYMOUS auth,
    Jicofo conference creation, MUC lifecycle, and raw Jingle IQ routing.
    """

    def __init__(
        self,
        xmpp_client_domain: str = "meet.jitsi",
        muc_room_domain_prefix: str = "muc.",
        ssl_verify: bool = False,
        jingle_debug_log_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.xmpp_client_domain = xmpp_client_domain
        self.muc_room_domain_prefix = muc_room_domain_prefix
        self.ssl_verify = bool(ssl_verify)
        self.jingle_debug_log_path = Path(jingle_debug_log_path) if jingle_debug_log_path else None

        self._ws: Optional[Any] = None
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._is_connected: bool = False
        self._is_authenticated: bool = False
        self._is_muc_joined: bool = False

        self.bound_jid: Optional[str] = None
        self.room_jid: Optional[str] = None
        self.display_name: Optional[str] = None
        self.participant_id: Optional[str] = None
        self.jicofo_jid: Optional[str] = None
        self.jingle_sid: Optional[str] = None

        self._offer_queue: asyncio.Queue[str] = asyncio.Queue()
        self._presence_future: Optional[asyncio.Future[bool]] = None
        self._sasl_future: Optional[asyncio.Future[bool]] = None
        self._bind_future: Optional[asyncio.Future[str]] = None
        self._iq_futures: Dict[str, asyncio.Future[str]] = {}

        if self.jingle_debug_log_path:
            self.jingle_debug_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log_stanza(self, direction: str, stanza: str) -> None:
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_entry = f"[{ts}] [{direction}] {stanza.strip()}\n"
        logger.debug("[XMPP %s] %s", direction, stanza.strip())

        if self.jingle_debug_log_path:
            try:
                with open(self.jingle_debug_log_path, mode="a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as exc:
                logger.warning("Failed writing to stanza debug log: %s", exc)

    async def _send_raw(self, stanza: str) -> None:
        if not _is_ws_open(self._ws):
            raise SignalingConnectionError("Cannot send stanza: WebSocket is not open.")
        self._log_stanza("SENT", stanza)
        await self._ws.send(stanza)

    async def _read_loop(self) -> None:
        try:
            assert self._ws is not None
            async for message in self._ws:
                message_str = message.decode("utf-8") if isinstance(message, bytes) else message
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

    async def _route_incoming_stanza(self, raw_xml: str) -> None:
        trimmed = raw_xml.strip()
        if not trimmed:
            return

        try:
            if trimmed.startswith("<open") or "<open " in trimmed:
                root = ET.fromstring(trimmed)
                if root.tag.endswith("open"):
                    logger.debug("Received XMPP stream open: %s", root.attrib)
                    return

            if trimmed.startswith("<close"):
                logger.info("Received XMPP stream close from server.")
                return

            root = ET.fromstring(trimmed)
            tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

            if tag == "success" and (NS_SASL in root.tag or root.attrib.get("xmlns") == NS_SASL):
                if self._sasl_future and not self._sasl_future.done():
                    self._sasl_future.set_result(True)
                return

            if tag == "failure" and (NS_SASL in root.tag or root.attrib.get("xmlns") == NS_SASL):
                error_detail = ET.tostring(root, encoding="unicode")
                if self._sasl_future and not self._sasl_future.done():
                    self._sasl_future.set_exception(
                        SASLAuthenticationError(
                            f"SASL ANONYMOUS authentication failed against '{self.xmpp_client_domain}': {error_detail}"
                        )
                    )
                return

            if tag == "iq":
                iq_id = root.attrib.get("id", "")
                iq_type = root.attrib.get("type", "")

                # 1. Jingle session-initiate from Jicofo
                jingle_elem = root.find(f".//{{{NS_JINGLE}}}jingle")
                if jingle_elem is None:
                    for child in root:
                        if child.tag.endswith("jingle"):
                            jingle_elem = child
                            break

                if jingle_elem is not None and jingle_elem.attrib.get("action") == "session-initiate":
                    self.jicofo_jid = root.attrib.get("from")
                    self.jingle_sid = jingle_elem.attrib.get("sid")
                    logger.info("Received Jingle session-initiate from Jicofo (%s, sid=%s)", self.jicofo_jid, self.jingle_sid)
                    await self._offer_queue.put(trimmed)
                    return

                # 2. Handle GET IQs (Ping and Jicofo Feature Discovery - XEP-0030 disco#info)
                if iq_type == "get":
                    sender = root.attrib.get("from")

                    # Reply to Ping (with explicit jabber:client namespace)
                    ping_elem = root.find(".//{urn:xmpp:ping}ping")
                    if ping_elem is not None or "ping" in trimmed:
                        pong = f'<iq xmlns="{NS_CLIENT}" type="result" to="{sender}" id="{iq_id}"/>'
                        await self._send_raw(pong)
                        return

                    # Reply to Jicofo Service Discovery (disco#info with explicit jabber:client namespace)
                    disco_elem = root.find(".//{http://jabber.org/protocol/disco#info}query")
                    if disco_elem is not None or "disco#info" in trimmed:
                        node_attr = ""
                        if disco_elem is not None and "node" in disco_elem.attrib:
                            node_attr = f' node="{disco_elem.attrib["node"]}"'

                        disco_reply = (
                            f'<iq xmlns="{NS_CLIENT}" type="result" to="{sender}" id="{iq_id}">'
                            f'<query xmlns="http://jabber.org/protocol/disco#info"{node_attr}>'
                            f'<identity category="client" type="bot" name="{self.display_name or "vad-bot"}"/>'
                            f'<feature var="urn:xmpp:jingle:1"/>'
                            f'<feature var="urn:xmpp:jingle:apps:rtp:1"/>'
                            f'<feature var="urn:xmpp:jingle:apps:rtp:audio"/>'
                            f'<feature var="urn:xmpp:jingle:transports:ice-udp:1"/>'
                            f'<feature var="urn:xmpp:jingle:apps:dtls:0"/>'
                            f'<feature var="http://jabber.org/protocol/disco#info"/>'
                            f'</query>'
                            f'</iq>'
                        )
                        await self._send_raw(disco_reply)
                        return

                # 3. Resource Bind Result
                if iq_id == "_bind_1" and iq_type == "result":
                    jid_elem = root.find(f".//{{{NS_BIND}}}jid")
                    if jid_elem is not None and jid_elem.text:
                        self.bound_jid = jid_elem.text.strip()
                        if self._bind_future and not self._bind_future.done():
                            self._bind_future.set_result(self.bound_jid)
                    return

                # 4. Resolve generic tracked IQ futures (including Jicofo Conference ready result)
                if iq_id in self._iq_futures:
                    fut = self._iq_futures.pop(iq_id)
                    if not fut.done():
                        fut.set_result(trimmed)
                    return

            if tag == "presence":
                pres_type = root.attrib.get("type", "")
                pres_from = root.attrib.get("from", "")

                error_elem = root.find(".//error")
                if pres_type == "error" or error_elem is not None:
                    code = error_elem.attrib.get("code") if error_elem is not None else ""
                    if code == "409" or root.find(".//{urn:ietf:params:xml:ns:xmpp-stanzas}conflict") is not None or "conflict" in trimmed:
                        err_msg = (
                            f"MUC presence conflict: Nick '{self.display_name}' is already in use in room '{self.room_jid}'."
                        )
                        if self._presence_future and not self._presence_future.done():
                            self._presence_future.set_exception(MUCConflictError(err_msg))
                        return
                    else:
                        err_detail = ET.tostring(error_elem, encoding="unicode") if error_elem is not None else "Unknown presence error"
                        if self._presence_future and not self._presence_future.done():
                            self._presence_future.set_exception(MUCJoinError(f"MUC presence rejected: {err_detail}"))
                        return

                # Confirm join when presence reflects from our room JID with matching participant ID
                expected_muc_jid = f"{self.room_jid}/{self.participant_id}"
                if pres_from == expected_muc_jid or (self.room_jid and pres_from.startswith(self.room_jid)):
                    self._is_muc_joined = True
                    logger.info("Successfully joined MUC room as '%s' (From: %s)", self.display_name, pres_from)
                    if self._presence_future and not self._presence_future.done():
                        self._presence_future.set_result(True)
                    return

        except Exception as exc:
            logger.warning("Error parsing incoming stanza: %s (Raw: %s)", exc, raw_xml)

    async def connect(
        self,
        bridge_url: str,
        room_id: str,
        display_name: str,
        timeout_s: float = 15.0,
    ) -> None:
        self.display_name = display_name
        self.participant_id = uuid.uuid4().hex[:8]
        muc_domain = f"{self.muc_room_domain_prefix}{self.xmpp_client_domain}"
        self.room_jid = f"{room_id}@{muc_domain}"

        logger.info(
            "Connecting signaling to '%s' (Domain: %s, Room: %s, Participant ID: %s, Nick: %s)",
            bridge_url,
            self.xmpp_client_domain,
            self.room_jid,
            self.participant_id,
            self.display_name,
        )

        ssl_context = None
        if bridge_url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            if not self.ssl_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        try:
            self._ws = await websockets.connect(
                bridge_url,
                subprotocols=["xmpp"],
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self._is_connected = True
            self._listener_task = asyncio.create_task(self._read_loop())

            async with asyncio.timeout(timeout_s):
                # 1. Open XMPP Stream (RFC 7395)
                open_stream = f'<open xmlns="{NS_FRAMING}" to="{self.xmpp_client_domain}" version="1.0"/>'
                await self._send_raw(open_stream)

                # 2. SASL ANONYMOUS Auth
                self._sasl_future = asyncio.get_running_loop().create_future()
                sasl_auth = f'<auth xmlns="{NS_SASL}" mechanism="ANONYMOUS"/>'
                await self._send_raw(sasl_auth)
                await self._sasl_future
                self._is_authenticated = True
                logger.info("SASL ANONYMOUS authentication successful.")

                # 3. Stream Restart after Auth
                await self._send_raw(open_stream)

                # 4. Resource Binding using participant ID
                self._bind_future = asyncio.get_running_loop().create_future()
                bind_iq = (
                    f'<iq xmlns="{NS_CLIENT}" type="set" id="_bind_1">'
                    f'<bind xmlns="{NS_BIND}"><resource>{self.participant_id}</resource></bind>'
                    f'</iq>'
                )
                await self._send_raw(bind_iq)
                self.bound_jid = await self._bind_future
                logger.info("XMPP Resource bound: Full JID = '%s'", self.bound_jid)

                # 5. Request Jicofo to create/open conference room FIRST
                stats_id = f"vad_harness_{self.participant_id}"
                conf_req_id = f"_conf_{uuid.uuid4().hex[:8]}"
                focus_target = f"focus.{self.xmpp_client_domain}"
                
                self._iq_futures[conf_req_id] = asyncio.get_running_loop().create_future()
                conf_req_iq = (
                    f'<iq xmlns="{NS_CLIENT}" type="set" to="{focus_target}" id="{conf_req_id}">'
                    f'<conference xmlns="http://jitsi.org/protocol/focus" '
                    f'room="{self.room_jid}" machine-uid="{stats_id}">'
                    f'<property name="bridge" value="true"/>'
                    f'</conference>'
                    f'</iq>'
                )
                logger.info("Requesting conference focus from Jicofo (%s for room %s)...", focus_target, self.room_jid)
                await self._send_raw(conf_req_iq)
                await self._iq_futures[conf_req_id]
                logger.info("Jicofo confirmed room is ready.")

                # 6. Now join MUC Room using participant_id as MUC occupant resource
                self._presence_future = asyncio.get_running_loop().create_future()
                muc_presence = (
                    f'<presence xmlns="{NS_CLIENT}" to="{self.room_jid}/{self.participant_id}">'
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

    async def wait_for_offer(self, timeout_s: float = 15.0) -> str:
        if not self._is_connected or not self._is_muc_joined:
            raise SignalingConnectionError("Cannot wait for offer: Session is not connected to MUC.")

        try:
            async with asyncio.timeout(timeout_s):
                offer_stanza = await self._offer_queue.get()
                return offer_stanza
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise JingleOfferTimeoutError(
                f"Jicofo failed to send session-initiate Jingle IQ within {timeout_s}s in room '{self.room_jid}'"
            ) from exc

    async def send_answer(self, session_accept_iq: str) -> None:
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
        if not self._is_connected or not self.room_jid or not self.participant_id:
            raise SignalingConnectionError("Cannot announce source: Session not connected.")

        src_name = source_name or f"{self.participant_id}-a0"
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
            presence_xml = (
                f'<presence xmlns="{NS_CLIENT}" to="{self.room_jid}/{self.participant_id}">'
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

    async def disconnect(self) -> None:
        logger.info("Disconnecting Jitsi signaling session...")
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

        if self._is_connected and self.room_jid and self.participant_id:
            try:
                unavail_pres = (
                    f'<presence xmlns="{NS_CLIENT}" type="unavailable" to="{self.room_jid}/{self.participant_id}"/>'
                )
                await self._send_raw(unavail_pres)
            except Exception as exc:
                logger.debug("Notice sending unavailable presence on disconnect: %s", exc)

        if _is_ws_open(self._ws):
            try:
                close_frame = f'<close xmlns="{NS_FRAMING}"/>'
                await self._send_raw(close_frame)
            except Exception:
                pass

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listener_task = None

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.debug("Notice closing websocket: %s", exc)
            self._ws = None

        self._is_connected = False
        self._is_authenticated = False
        self._is_muc_joined = False
        logger.info("Jitsi signaling session disconnected cleanly.")
