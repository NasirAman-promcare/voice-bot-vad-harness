"""
webrtc_bridge/listener_bridge.py

One Job:
    Implement `JitsiListenerBridge`, the concrete WebRTC listener driver that joins
    the Jitsi conference as a receive-only (`recvonly`) participant and drives the
    existing `bots.listener_bot.ListenerBot` purely through its public API:
    `prepare_for_clip()`, `ingest_packet()`, and `await_clip_completion()`.
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


class JitsiListenerBridge:
    """Drives `bots.listener_bot.ListenerBot` across live Jitsi WebRTC audio streams."""

    def __init__(
        self,
        listener_bot: Any,
        config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml",
        config: Optional[BridgeConfig] = None,
    ) -> None:
        self.listener_bot = listener_bot
        self.config = config or load_bridge_config(config_path)

        self.is_connected = False
        self.current_room: Optional[str] = None
        self.bridge_url: Optional[str] = None

        self._signaling: Optional[JitsiSignalingSession] = None
        self._media_session: Optional[BridgeMediaSession] = None

    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        if not room_id or not room_id.strip():
            raise ListenerBridgeConnectionError("Cannot connect: room_id is empty.")
        if not bridge_url or not bridge_url.strip():
            raise ListenerBridgeConnectionError("Cannot connect: bridge_url is empty.")

        if self.is_connected and self.current_room == room_id:
            logger.info("Listener bridge already connected to room '%s'", room_id)
            return

        if self.is_connected:
            self.disconnect()

        target_room = room_id.strip()
        self.current_room = target_room
        self.bridge_url = bridge_url.strip()

        logger.info(
            "Connecting JitsiListenerBridge to room '%s' via bridge '%s'",
            self.current_room,
            self.bridge_url,
        )

        try:
            self._media_session = BridgeMediaSession(
                role="recvonly",
                outgoing_track=None,
                ice_gather_timeout_s=self.config.ice_gather_timeout_s,
                dtls_handshake_timeout_s=self.config.dtls_handshake_timeout_s,
            )

            self._signaling = JitsiSignalingSession(
                xmpp_client_domain=self.config.xmpp_client_domain,
                muc_room_domain_prefix=self.config.muc_room_domain_prefix,
                ssl_verify=self.config.ssl_verify,
                jingle_debug_log_path=self.config.jingle_debug_log_path,
            )

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

            raw_offer_xml = self._media_session._run_sync(
                self._signaling.wait_for_offer(timeout_s=self.config.dtls_handshake_timeout_s),
                timeout=self.config.dtls_handshake_timeout_s + 2.0,
            )

            sdp_offer = jingle_offer_to_sdp(raw_offer_xml)
            sdp_answer = self._media_session.answer_offer(sdp_offer)

            session_accept_xml = sdp_answer_to_jingle_accept(
                sdp_answer_str=sdp_answer,
                session_initiate_iq=raw_offer_xml,
            )

            self._media_session._run_sync(
                self._signaling.send_answer(session_accept_xml),
                timeout=5.0,
            )

            self.is_connected = True
            logger.info("JitsiListenerBridge joined room '%s' (recvonly)", self.current_room)

        except Exception as exc:
            logger.error("Failed to connect JitsiListenerBridge: %s", exc, exc_info=True)
            self.disconnect()
            raise ListenerBridgeConnectionError(
                f"Failed to join Jitsi room '{target_room}': {exc}"
            ) from exc

    def run_clip(self, manifest_entry: Any, timeout_s: float = 30.0) -> Any:
        if not self.is_connected or self._media_session is None:
            raise ListenerBridgeStateError(
                "Cannot run clip: JitsiListenerBridge is not connected to a room. "
                "Call connect_and_join() first."
            )

        clip_id = str(manifest_entry.clip_id)
        logger.debug("[ListenerBridge] Preparing stream capture for clip '%s'", clip_id)

        expected_samples_16k = 0
        if getattr(manifest_entry, "speech_segments", None):
            last_segment_end = max(seg[1] for seg in manifest_entry.speech_segments)
            expected_samples_16k = last_segment_end + 4800
        else:
            expected_samples_16k = 48000

        margin_samples_16k = 6400
        threshold_samples_16k = expected_samples_16k + margin_samples_16k

        self.listener_bot.prepare_for_clip(clip_id)

        received_samples_16k = 0
        is_clip_end_signaled = False
        tap: Optional[RawRtpTap] = None

        def on_packet_arrived(sequence_id: int, payload_bytes: bytes, arrival_timestamp_ns: int) -> None:
            nonlocal received_samples_16k, is_clip_end_signaled
            received_samples_16k += 320
            is_end = False
            if received_samples_16k >= threshold_samples_16k and not is_clip_end_signaled:
                is_end = True
                is_clip_end_signaled = True

            self.listener_bot.ingest_packet(
                sequence_id=sequence_id,
                payload=payload_bytes,
                timestamp_ns=arrival_timestamp_ns,
                is_clip_end=is_end,
            )
            if is_end and tap is not None:
                tap.stop()

        try:
            receiver = self._media_session.get_incoming_receiver()
            tap = RawRtpTap(rtp_receiver=receiver, on_packet=on_packet_arrived)
            tap.start()

            captured_data = self.listener_bot.await_clip_completion(clip_id=clip_id, timeout_s=timeout_s)
            logger.debug(
                "[ListenerBridge] Successfully captured stream for '%s' (%d samples, %d packets)",
                clip_id,
                len(captured_data.decoded_audio_16k),
                tap.packet_count,
            )
            return captured_data

        except Exception as exc:
            logger.error("[ListenerBridge] Stream capture failed for '%s': %s", clip_id, exc)
            raise ListenerBridgeExecutionError(f"Failed to capture stream for clip '{clip_id}': {exc}") from exc
        finally:
            if tap is not None:
                tap.close()

    def disconnect(self) -> None:
        if not self.is_connected and self._signaling is None and self._media_session is None:
            return

        logger.info("Disconnecting JitsiListenerBridge...")

        if self._signaling is not None:
            try:
                if self._media_session is not None:
                    self._media_session._run_sync(self._signaling.disconnect(), timeout=3.0)
            except Exception as exc:
                logger.debug("Notice disconnecting signaling: %s", exc)
            finally:
                self._signaling = None

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
