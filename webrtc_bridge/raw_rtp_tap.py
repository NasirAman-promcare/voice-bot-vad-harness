"""
webrtc_bridge/raw_rtp_tap.py

One Job:
    Intercept raw, undecoded Opus audio payloads directly from aiortc's RTCRtpReceiver
    in physical arrival order and pass them to ListenerBot's `ingest_packet(...)`
    callback, bypassing aiortc's internal jitter buffer and decoding pipeline.

Why this bypass exists:
    `bots.listener_bot.ListenerBot` already implements its own sequence-gap detection
    (`PacketDiagnostic`), out-of-order packet reordering (`_flush_jitter_buffer`), and
    single-point 48kHz -> 16kHz polyphase resampling (`OpusPCMDecoder`). Feeding it
    aiortc's default high-level `MediaStreamTrack.recv()` output would supply already-smoothed,
    already-reordered, already-decoded PCM frames, rendering ListenerBot's network diagnostic
    measurements completely blind to real-world packet loss and jitter.

Interception Point:
    Replaces `RTCRtpReceiver._handle_rtp_packet` at the SRTP boundary where decrypted,
    undecoded Opus packets exist in true arrival order immediately before being queued
    into aiortc's internal `_jitter_buffer`. Since nothing in the test harness calls
    `recv()` on the receiver track, this tap replaces the jitter buffer intake entirely,
    saving CPU cycles and preserving exact wire-level transport physics.

What this module must NEVER do:
    - Never decode Opus payload bytes to PCM (decoding belongs to `ListenerBot`).
    - Never resample audio (resampling belongs to `ListenerBot.resample_48k_to_16k`).
    - Never reorder packets or synthesize missing frames for sequence gaps.
    - Never drop or filter packets with non-monotonic or decreasing sequence IDs.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from aiortc.rtcrtpreceiver import RTCRtpReceiver

logger = logging.getLogger("webrtc_bridge.raw_rtp_tap")

# Packet Callback Signature: (sequence_id: int, payload_bytes: bytes, arrival_timestamp_ns: int) -> None
PacketCallback = Callable[[int, bytes, int], None]


# ==============================================================================
# Exceptions
# ==============================================================================

class RawRtpTapError(Exception):
    """Base exception for RawRtpTap interception failures."""
    pass


class InvalidReceiverError(RawRtpTapError, TypeError):
    """Raised when the provided object is not an aiortc RTCRtpReceiver instance."""
    pass


# ==============================================================================
# Raw RTP Tap Implementation
# ==============================================================================

class RawRtpTap:
    """
    Hooks into an aiortc RTCRtpReceiver to stream raw Opus payload packets
    in true physical arrival order to ListenerBot.
    """

    def __init__(
        self,
        rtp_receiver: RTCRtpReceiver,
        on_packet: PacketCallback,
    ) -> None:
        """
        Initializes the raw RTP tap.

        Args:
            rtp_receiver: The incoming RTCRtpReceiver from `BridgeMediaSession.get_incoming_receiver()`.
            on_packet: Callback invoked as `on_packet(sequence_id, payload_bytes, timestamp_ns)`
                       for every packet in arrival order.

        Raises:
            InvalidReceiverError: If rtp_receiver is not a valid RTCRtpReceiver.
        """
        if not isinstance(rtp_receiver, RTCRtpReceiver):
            raise InvalidReceiverError(
                f"Expected RTCRtpReceiver instance, received {type(rtp_receiver).__name__}."
            )

        if not hasattr(rtp_receiver, "_handle_rtp_packet"):
            raise RawRtpTapError(
                "Provided RTCRtpReceiver is missing required private method '_handle_rtp_packet'."
            )

        self._receiver = rtp_receiver
        self._on_packet = on_packet
        self._original_handle_rtp_packet = rtp_receiver._handle_rtp_packet
        self._is_active: bool = False

        # Diagnostic Counters
        self._intercepted_packets_count: int = 0
        self._intercepted_bytes_count: int = 0
        self._last_sequence_id: Optional[int] = None

    @property
    def is_active(self) -> bool:
        """True if the tap is actively intercepting and forwarding RTP packets."""
        return self._is_active

    @property
    def packet_count(self) -> int:
        """Total number of RTP packets intercepted since creation or last reset."""
        return self._intercepted_packets_count

    @property
    def total_bytes(self) -> int:
        """Total payload bytes intercepted."""
        return self._intercepted_bytes_count

    # --------------------------------------------------------------------------
    # Interception Lifecycle
    # --------------------------------------------------------------------------
    def start(self) -> None:
        """
        Begins packet interception by binding the tap handler to the RTCRtpReceiver.

        Safe to call at the start of each clip evaluation.
        """
        if self._is_active:
            return

        self._is_active = True
        # Monkeypatch the private packet handler on this specific receiver instance
        self._receiver._handle_rtp_packet = self._tap_handle_rtp_packet  # type: ignore[assignment]
        logger.debug("RawRtpTap started packet interception.")

    def stop(self) -> None:
        """
        Stops packet interception cleanly without tearing down the underlying WebRTC session.

        Safe to call between consecutive clip evaluations.
        """
        if not self._is_active:
            return

        self._is_active = False
        logger.debug(
            "RawRtpTap stopped. Intercepted %d total packets (%d bytes).",
            self._intercepted_packets_count,
            self._intercepted_bytes_count,
        )

    # --------------------------------------------------------------------------
    # Private Interception Handler
    # --------------------------------------------------------------------------
    def _tap_handle_rtp_packet(self, packet: Any, arrival_time_ms: Optional[float] = None) -> None:
        """
        Custom packet handler replacing `RTCRtpReceiver._handle_rtp_packet`.

        Captures nanosecond arrival timestamp, extracts sequence ID and raw Opus payload,
        and dispatches immediately to ListenerBot in true arrival order.
        """
        arrival_ns = time.perf_counter_ns()

        if not self._is_active:
            return

        try:
            # Extract standard RTP packet header attributes
            sequence_id = int(packet.sequence_number)
            payload_bytes = bytes(packet.payload)
            payload_len = len(payload_bytes)

            self._intercepted_packets_count += 1
            self._intercepted_bytes_count += payload_len
            self._last_sequence_id = sequence_id

            # Forward immediately in true arrival order (preserving out-of-order & gaps for ListenerBot)
            self._on_packet(sequence_id, payload_bytes, arrival_ns)

        except Exception as exc:
            logger.error("Error in RawRtpTap packet callback: %s", exc, exc_info=True)

    def close(self) -> None:
        """Restores the original receiver handler and releases references."""
        self.stop()
        if hasattr(self._receiver, "_handle_rtp_packet"):
            self._receiver._handle_rtp_packet = self._original_handle_rtp_packet  # type: ignore[assignment]
        logger.debug("RawRtpTap closed and original receiver method restored.")

    def __enter__(self) -> RawRtpTap:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()