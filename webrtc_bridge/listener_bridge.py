"""
webrtc_bridge/listener_bridge.py

One Job:
    Implement `JitsiListenerBridge`, the concrete WebRTC listener driver that joins
    the Jitsi conference as a receive-only (`recvonly`) participant and drives the
    existing `bots.listener_bot.ListenerBot` purely through its public API:
    `prepare_for_clip()`, `ingest_packet()`, and `await_clip_completion()`.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import math
import time
from pathlib import Path
from typing import Any, Optional, Union

from webrtc_bridge.injector import BridgeConfig, load_bridge_config
from webrtc_bridge.jingle_sdp_translator import (
    jingle_offer_to_sdp,
    parse_transport_info_candidates,
    sdp_answer_to_jingle_accept,
)
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession
from webrtc_bridge.media_session import BridgeMediaSession
from webrtc_bridge.raw_rtp_tap import RawRtpTap
from webrtc_bridge.rtp_sequence import RtpSequenceUnwrapper

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
        self._ready_future: Optional[concurrent.futures.Future[None]] = None
        self._current_tap: Optional[RawRtpTap] = None
        self._active_clip_id: Optional[str] = None
        # One continuous RTP stream spans all clips, so unwrap state persists across clips.
        self._seq_unwrapper = RtpSequenceUnwrapper()

    async def _negotiate_media(self) -> None:
        """Asynchronous background worker executing Jingle offer/answer for recvonly session."""
        assert self._signaling is not None
        assert self._media_session is not None

        logger.info("[ListenerBridge] Awaiting Jingle offer from Jicofo...")
        raw_offer_xml = await self._signaling.wait_for_offer(timeout_s=self.config.dtls_handshake_timeout_s)

        logger.info("[ListenerBridge] Translating Jingle offer to SDP and generating answer...")
        sdp_offer = jingle_offer_to_sdp(raw_offer_xml)
        
        # 1. Generate answer without blocking on ICE/DTLS yet
        sdp_answer = await self._media_session.async_answer_offer(sdp_offer)

        # 2. Transmit session-accept so JVB receives our ICE/DTLS credentials
        session_accept_xml = sdp_answer_to_jingle_accept(
            sdp_answer_str=sdp_answer,
            session_initiate_iq=raw_offer_xml,
        )
        logger.info("[ListenerBridge] Transmitting session-accept IQ to Jicofo...")
        await self._signaling.send_answer(session_accept_xml)

        # 3. Await ICE connectivity & DTLS handshake
        logger.info("[ListenerBridge] Awaiting ICE & DTLS handshake completion...")
        await self._media_session.async_wait_for_connection()

        self.is_connected = True
        logger.info("JitsiListenerBridge media negotiation complete (recvonly)")

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

            # Separate listener debug log to avoid overwriting speaker
            base_log_path = Path(self.config.jingle_debug_log_path)
            listener_log = base_log_path.with_name(f"{base_log_path.stem}_listener{base_log_path.suffix}")

            self._signaling = JitsiSignalingSession(
                xmpp_client_domain=self.config.xmpp_client_domain,
                muc_room_domain_prefix=self.config.muc_room_domain_prefix,
                ssl_verify=self.config.ssl_verify,
                jingle_debug_log_path=listener_log,
            )

            # Hook trickle ICE candidate delivery
            def _handle_transport_info(raw_xml: str) -> None:
                if self._media_session is not None:
                    candidates = parse_transport_info_candidates(raw_xml)
                    for mid, cand in candidates:
                        self._media_session.add_remote_candidate(mid, cand)

            self._signaling.set_transport_info_callback(_handle_transport_info)

            connect_timeout = (
                self.config.ice_gather_timeout_s + self.config.dtls_handshake_timeout_s + 10.0
            )
            # 1. Join MUC synchronously
            self._media_session._run_sync(
                self._signaling.connect(
                    bridge_url=self.bridge_url,
                    room_id=self.current_room,
                    display_name=self.config.listener_display_name,
                    timeout_s=connect_timeout,
                ),
                timeout=connect_timeout + 2.0,
            )

            # 2. Dispatch offer/answer negotiation to background event loop
            self._ready_future = asyncio.run_coroutine_threadsafe(
                self._negotiate_media(),
                self._media_session._loop,
            )
            logger.info("JitsiListenerBridge joined MUC; background media negotiation dispatched.")

        except Exception as exc:
            logger.error("Failed to connect JitsiListenerBridge: %s", exc, exc_info=True)
            self.disconnect()
            raise ListenerBridgeConnectionError(
                f"Failed to join Jitsi room '{target_room}': {exc}"
            ) from exc

    def wait_until_ready(self, timeout_s: float = 30.0) -> None:
        """Blocks until the background WebRTC negotiation completes."""
        if self._ready_future is None:
            raise ListenerBridgeStateError("ListenerBridge is not connecting or connected.")

        try:
            self._ready_future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError as exc:
            raise ListenerBridgeConnectionError(
                f"WebRTC media negotiation timed out after {timeout_s}s in room '{self.current_room}'"
            ) from exc
        except Exception as exc:
            raise ListenerBridgeConnectionError(
                f"WebRTC media negotiation failed in room '{self.current_room}': {exc}"
            ) from exc

    def arm_clip(self, manifest_entry: Any) -> None:
        """
        Arms the listener tap BEFORE audio playback begins.

        Guarantees that no leading packets or calibration chirps are missed.
        """
        self.wait_until_ready()

        if self._media_session is None:
            raise ListenerBridgeStateError("Media session is not initialized.")

        clip_id = str(manifest_entry.clip_id)
        self._active_clip_id = clip_id
        logger.debug("[ListenerBridge] Arming stream capture tap for clip '%s'", clip_id)

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
        clip_base_seq = None

        def on_packet_arrived(sequence_id: int, payload_bytes: bytes, arrival_timestamp_ns: int) -> None:
            nonlocal received_samples_16k, is_clip_end_signaled, clip_base_seq
            # RTP sequence numbers start at a random value and wrap at 65535, but
            # ListenerBot expects each clip to start at 0: unwrap, then rebase per clip.
            ext_seq = self._seq_unwrapper.unwrap(sequence_id)
            if clip_base_seq is None:
                clip_base_seq = ext_seq
            sequence_id = ext_seq - clip_base_seq
            if sequence_id < 0:
                return  # late packet from before this clip's capture window
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
            if is_end and self._current_tap is not None:
                self._current_tap.stop()

        if self._current_tap is not None:
            self._current_tap.close()
            self._current_tap = None

        try:
            receiver = self._media_session.get_incoming_receiver()
            self._current_tap = RawRtpTap(rtp_receiver=receiver, on_packet=on_packet_arrived)
            self._current_tap.start()
            logger.debug("[ListenerBridge] Tap armed and listening for clip '%s'", clip_id)
        except Exception as exc:
            logger.error("[ListenerBridge] Failed to arm tap for '%s': %s", clip_id, exc)
            raise ListenerBridgeExecutionError(f"Failed to arm tap for clip '{clip_id}': {exc}") from exc

    def await_clip(self, manifest_entry: Any, timeout_s: float = 30.0) -> Any:
        """Awaits clip stream completion and tears down the active tap."""
        clip_id = str(manifest_entry.clip_id)
        if self._active_clip_id != clip_id:
            raise ListenerBridgeStateError(
                f"Active armed clip '{self._active_clip_id}' does not match await request '{clip_id}'"
            )

        try:
            captured_data = self.listener_bot.await_clip_completion(clip_id=clip_id, timeout_s=timeout_s)
            logger.debug(
                "[ListenerBridge] Successfully captured stream for '%s' (%d samples, %d packets)",
                clip_id,
                len(captured_data.decoded_audio_16k),
                self._current_tap.packet_count if self._current_tap else 0,
            )
            return captured_data
        except Exception as exc:
            logger.error("[ListenerBridge] Stream capture failed for '%s': %s", clip_id, exc)
            raise ListenerBridgeExecutionError(f"Failed to capture stream for clip '{clip_id}': {exc}") from exc
        finally:
            if self._current_tap is not None:
                self._current_tap.close()
                self._current_tap = None
            self._active_clip_id = None

    def run_clip(self, manifest_entry: Any, timeout_s: float = 30.0) -> Any:
        """Convenience method combining arming and awaiting."""
        self.arm_clip(manifest_entry)
        return self.await_clip(manifest_entry, timeout_s=timeout_s)

    def disconnect(self) -> None:
        if not self.is_connected and self._signaling is None and self._media_session is None:
            return

        logger.info("Disconnecting JitsiListenerBridge...")

        if self._current_tap is not None:
            try:
                self._current_tap.close()
            except Exception:
                pass
            self._current_tap = None

        if self._ready_future and not self._ready_future.done():
            self._ready_future.cancel()
        self._ready_future = None

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
        self._active_clip_id = None
        logger.info("JitsiListenerBridge disconnected cleanly.")

    def __enter__(self) -> JitsiListenerBridge:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()