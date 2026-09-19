"""
webrtc_bridge/listener_bridge.py

One Job:
    Implement `JitsiListenerBridge`, the concrete WebRTC listener driver that joins
    the Jitsi conference as a receive-only (`recvonly`) participant and drives the
    existing `bots.listener_bot.ListenerBot` purely through its public API:
    `prepare_for_clip()`, `ingest_packet()`, and `await_clip_completion()`.

Architecture & Boundary Discipline:
    - Receive-Only Participant: Joins the conference via XMPP/MUC signaling (File 26),
      translates Jicofo's Jingle offer into an SDP offer (File 27), and answers with a
      `recvonly` media session (File 28). Declares zero outgoing audio sources.
    - Raw Packet Ingestion: Bypasses aiortc's internal jitter buffer via `RawRtpTap` (File 30)
      and forwards undecoded Opus payload packets in true arrival order straight to
      `ListenerBot.ingest_packet()`.
    - Public API Only: Does not touch or inspect `ListenerBot`'s internal jitter buffer,
      sequence tracking state, or `OpusPCMDecoder`.

End-of-Clip Boundary Detection:
    Tracks incoming 20ms Opus packets against the clip's expected duration samples
    (plus a 400ms transport margin for guard gaps and packet jitter). Sets `is_clip_end=True`
    on the final packet or relies on `ListenerBot.await_clip_completion()`'s timeout as
    the backstop under severe packet loss.

What this module must NEVER do:
    - Never decode Opus packets or perform audio resampling.
    - Never touch `ListenerBot`'s internal state directly or edit `bots/listener_bot.py`.
    - Never import anything from `latency/`, `scoring/`, `storage/`, or `orchestrator.py`.
    - Never read `config/run_config.yaml` directly (reads `bridge_config.yaml` only).
    - Never reconnect between consecutive `run_clip` calls (connects once per run).
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Any, Optional, Union

from webrtc_bridge.injector import BridgeConfig, load_bridge_config
from webrtc_bridge.jingle_sdp_translator import (
    jingle_offer_to_sdp,
    sdp_answer_to_jingle_accept,
)
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession
from webrtc_bridge.media_session import BridgeMediaSession
from webrtc_bridge.raw_rtp_tap import RawRtpTap

logger = logging.getLogger("webrtc_bridge.listener_bridge")


# ==============================================================================
# Exceptions
# ==============================================================================

class ListenerBridgeError(Exception):
    """Base exception for JitsiListenerBridge failures."""
    pass


class ListenerBridgeStateError(ListenerBridgeError):
    """Raised when an operation is called in an invalid bridge connection state."""
    pass


class ListenerBridgeConnectionError(ListenerBridgeError):
    """Raised when connecting or joining the Jitsi conference fails."""
    pass


class ListenerBridgeExecutionError(ListenerBridgeError):
    """Raised when clip ingestion or stream capture fails."""
    pass


# ==============================================================================
# Jitsi Listener Bridge Implementation
# ==============================================================================

class JitsiListenerBridge:
    """
    Drives `bots.listener_bot.ListenerBot` across live Jitsi WebRTC audio streams.
    """

    def __init__(
        self,
        listener_bot: Any,
        config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml",
        config: Optional[BridgeConfig] = None,
    ) -> None:
        """
        Initializes the listener bridge.

        Args:
            listener_bot: An instantiated ListenerBot instance.
            config_path: Path to bridge_config.yaml.
            config: Optional pre-loaded BridgeConfig instance.
        """
        self.listener_bot = listener_bot
        self.config = config or load_bridge_config(config_path)

        self.is_connected = False
        self.current_room: Optional[str] = None
        self.bridge_url: Optional[str] = None

        self._signaling: Optional[JitsiSignalingSession] = None
        self._media_session: Optional[BridgeMediaSession] = None
        self._rtp_tap: Optional[RawRtpTap] = None

    # --------------------------------------------------------------------------
    # WebRTC & Signaling Connection (Connect Once per Run)
    # --------------------------------------------------------------------------
    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        """
        Connects to Jitsi as a receive-only participant, negotiates Jingle/SDP,
        and hooks RawRtpTap into the incoming audio receiver.

        Args:
            room_id: Jitsi room name (e.g. 'vad-benchmark-eval-room-01').
            bridge_url: WebSocket signaling endpoint (e.g. 'wss://vad-jitsi-nasir.duckdns.org/xmpp-websocket').

        Raises:
            ListenerBridgeConnectionError: If connection or negotiation fails.
        """
        if not room_id or not room_id.strip():
            raise ListenerBridgeConnectionError("Cannot connect: room_id is empty.")
        if not bridge_url or not bridge_url.strip():
            raise ListenerBridgeConnectionError("Cannot connect: bridge_url is empty.")

        if self.is_connected and self.current_room == room_id:
            logger.info("Listener bridge already connected to room '%s'", room_id)
            return

        if self.is_connected:
            self.disconnect()

        self.current_room = room_id.strip()
        self.bridge_url = bridge_url.strip()

        logger.info(
            "Connecting JitsiListenerBridge to room '%s' via bridge '%s'",
            self.current_room,
            self.bridge_url,
        )

        try:
            # 1. Initialize Recvonly Media Session
            self._media_session = BridgeMediaSession(
                role="recvonly",
                outgoing_track=None,
                ice_gather_timeout_s=self.config.ice_gather_timeout_s,
                dtls_handshake_timeout_s=self.config.dtls_handshake_timeout_s,
            )

            # 2. Initialize XMPP Signaling Session
            self._signaling = JitsiSignalingSession(
                xmpp_client_domain=self.config.xmpp_client_domain,
                muc_room_domain_prefix=self.config.muc_room_domain_prefix,
                jingle_debug_log_path=self.config.jingle_debug_log_path,
            )

            # 3. Connect Signaling & Join MUC
            connect_timeout = (
                self.config.ice_gather_timeout_s + self.config.dtls_handshake_timeout_s + 10.0
            )
            self._media_session._run_sync(
                self._signaling.connect(
                    bridge_url=self.bridge_url,
                    room_id=self.current_room,
                    display_name=self.config.listener_display_name,
                    timeout_s=connect_timeout,
                ),
                timeout=connect_timeout + 2.0,
            )

            # 4. Await Jicofo's Jingle Offer
            raw_offer_xml = self._media_session._run_sync(
                self._signaling.wait_for_offer(timeout_s=self.config.dtls_handshake_timeout_s),
                timeout=self.config.dtls_handshake_timeout_s + 2.0,
            )

            # 5. Translate Jingle XML Offer -> SDP Offer (File 27)
            sdp_offer = jingle_offer_to_sdp(raw_offer_xml)

            # 6. Apply Offer & Generate Recvonly Answer (Blocks until ICE & DTLS connect)
            sdp_answer = self._media_session.answer_offer(sdp_offer)

            # 7. Translate SDP Answer -> Jingle session-accept IQ (File 27)
            session_accept_xml = sdp_answer_to_jingle_accept(
                sdp_answer_str=sdp_answer,
                session_initiate_iq=raw_offer_xml,
            )

            # 8. Transmit session-accept Answer to Jicofo
            self._media_session._run_sync(
                self._signaling.send_answer(session_accept_xml),
                timeout=5.0,
            )

            self.is_connected = True
            logger.info("JitsiListenerBridge successfully joined room '%s' (recvonly)", self.current_room)

        except Exception as exc:
            logger.error("Failed to connect JitsiListenerBridge: %s", exc, exc_info=True)
            self.disconnect()
            raise ListenerBridgeConnectionError(
                f"Failed to join Jitsi room '{self.current_room}': {exc}"
            ) from exc

    # --------------------------------------------------------------------------
    # Single Clip Execution & Ingress Hook
    # --------------------------------------------------------------------------
    def run_clip(self, manifest_entry: Any, timeout_s: float = 30.0) -> Any:
        """
        Prepares ListenerBot for an incoming clip, captures raw RTP packets over the
        WebRTC bridge, and returns the resulting `CapturedStreamData`.

        Args:
            manifest_entry: Validated ManifestEntry object.
            timeout_s: Maximum timeout ceiling for stream completion.

        Returns:
            A `CapturedStreamData` instance from `listener_bot.await_clip_completion()`.

        Raises:
            ListenerBridgeStateError: If called before connecting.
            ListenerBridgeExecutionError: If stream capture or completion times out.
        """
        if not self.is_connected or self._media_session is None:
            raise ListenerBridgeStateError(
                "Cannot run clip: JitsiListenerBridge is not connected to a room. "
                "Call connect_and_join() first."
            )

        clip_id = str(manifest_entry.clip_id)
        logger.debug("[ListenerBridge] Preparing stream capture for clip '%s'", clip_id)

        # 1. Estimate Total Expected 16kHz Samples
        # Speech segments end sample + 300ms trailing silence (4800 samples)
        # 1 Opus packet = 20ms = 320 samples at 16kHz
        expected_samples_16k = 0
        if getattr(manifest_entry, "speech_segments", None):
            last_segment_end = max(seg[1] for seg in manifest_entry.speech_segments)
            expected_samples_16k = last_segment_end + 4800
        else:
            # Fallback for silence/unlabeled clips: 3 seconds baseline
            expected_samples_16k = 48000

        # Transport Margin: 400ms (6400 samples / 20 packets) for network jitter & guard gaps
        margin_samples_16k = 6400
        threshold_samples_16k = expected_samples_16k + margin_samples_16k

        # 2. Reset ListenerBot State for this Clip
        self.listener_bot.prepare_for_clip(clip_id)

        # 3. Setup RawRtpTap Packet Intake
        received_samples_16k = 0
        is_clip_end_signaled = False
        tap: Optional[RawRtpTap] = None

        def on_packet_arrived(sequence_id: int, payload_bytes: bytes, arrival_timestamp_ns: int) -> None:
            nonlocal received_samples_16k, is_clip_end_signaled

            # 20ms Opus packet = 320 samples at 16kHz
            received_samples_16k += 320

            is_end = False
            if received_samples_16k >= threshold_samples_16k and not is_clip_end_signaled:
                is_end = True
                is_clip_end_signaled = True

            # Ingest raw packet into ListenerBot in true arrival order
            self.listener_bot.ingest_packet(
                sequence_id=sequence_id,
                payload=payload_bytes,
                timestamp_ns=arrival_timestamp_ns,
                is_clip_end=is_end,
            )

            if is_end and tap is not None:
                tap.stop()

        try:
            # 4. Bind RawRtpTap to incoming aiortc RTCRtpReceiver
            receiver = self._media_session.get_incoming_receiver()
            tap = RawRtpTap(rtp_receiver=receiver, on_packet=on_packet_arrived)
            tap.start()

            # 5. Block Synchronously until ListenerBot signals completion
            captured_data = self.listener_bot.await_clip_completion(clip_id=clip_id, timeout_s=timeout_s)
            logger.debug(
                "[ListenerBridge] Successfully captured stream for clip '%s' (%d samples, %d packets)",
                clip_id,
                len(captured_data.decoded_audio_16k),
                tap.packet_count,
            )
            return captured_data

        except Exception as exc:
            logger.error("[ListenerBridge] Stream capture failed for clip '%s': %s", clip_id, exc)
            raise ListenerBridgeExecutionError(
                f"Failed to capture stream for clip '{clip_id}': {exc}"
            ) from exc
        finally:
            if tap is not None:
                tap.close()

    # --------------------------------------------------------------------------
    # Teardown
    # --------------------------------------------------------------------------
    def disconnect(self) -> None:
        """
        Leaves the Jitsi conference, terminates signaling, and closes the media session.
        """
        if not self.is_connected and self._signaling is None and self._media_session is None:
            return

        logger.info("Disconnecting JitsiListenerBridge from '%s'...", self.current_room)

        # 1. Teardown Signaling
        if self._signaling is not None:
            try:
                if self._media_session is not None:
                    self._media_session._run_sync(self._signaling.disconnect(), timeout=3.0)
            except Exception as exc:
                logger.debug("Notice disconnecting signaling: %s", exc)
            finally:
                self._signaling = None

        # 2. Teardown Media Session
        if self._media_session is not None:
            try:
                self._media_session.close()
            except Exception as exc:
                logger.debug("Notice closing media session: %s", exc)
            finally:
                self._media_session = None

        self.is_connected = False
        self.current_room = None
        self.bridge_url = None
        logger.info("JitsiListenerBridge disconnected cleanly.")

    def __enter__(self) -> JitsiListenerBridge:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()