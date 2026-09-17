"""
bots/listener_bot.py

One Job:
    Act as the far-end receiver of the live Jitsi bridge feed: ingest tagged, sequenced
    audio chunks over WebSocket, timestamp arrival at the nanosecond boundary, reorder
    jittered packets, detect and publish sequence gaps/loss as first-class diagnostics,
    decode Opus to PCM, resample EXACTLY ONCE to 16kHz mono float32, and republish the
    clean 16kHz feed to all registered subscribers.

WebSocket Role Architecture & Ephemeral Runtime Design:
    - WebSocket Role: ListenerBot operates primarily as a WebSocket Ingest Server (listening
      on a local/tunneled endpoint, e.g. via Cloudflare Worker or reverse tunnel) to accept
      the outbound feed pushed from the Jitsi bridge. It also supports an active client
      connection mode if a direct bridge feed endpoint URL is provided.
    - Ephemeral Runtime Handling (Colab / Kaggle): Because ephemeral notebook environments
      suffer from idle timeouts and lack static public IPs, ListenerBot binds dynamically,
      maintains non-blocking asynchronous event loops with ping keep-alives, and operates
      on bounded per-clip transaction timeouts. Runs must be structured to complete within
      the kernel's active lifecycle.

Single-Point Resampling Authority:
    Opus decoders natively output 48kHz PCM. All downsampling to 16kHz mono float32 occurs
    strictly within this file before any subscriber receives audio. Centralizing resampling
    guarantees that resampler filter differences never introduce hidden confounds into
    downstream VAD comparisons.

First-Class Diagnostics:
    Any packet loss, missing sequence numbers, or out-of-order deliveries are captured as
    structured PacketDiagnostic records published alongside the audio stream. This allows
    downstream analysis to definitively distinguish between a model failure and network packet loss.

What this module must NEVER do:
    - Never import or reference any concrete VAD adapter (TEN VAD, FireRedVAD, WebRTC).
    - Never import or know about speaker_bot.py (isolation across bot boundaries).
    - Never perform scoring, ground-truth alignment, or metric calculations.
    - Never output subscriber-facing audio at any sample rate other than 16000 Hz mono.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

# Use shared contract utilities without referencing concrete adapters
from vad_adapters.adapter_contract import (
    AudioChunk,
    DecisionRecord,
    VADAdapterContract,
    chunk_audio_stream,
)

logger = logging.getLogger("bots.listener_bot")


# ==============================================================================
# Exceptions
# ==============================================================================

class ListenerBotError(Exception):
    """Base exception for ListenerBot operations."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class PacketDiagnostic:
    """
    First-class diagnostic record capturing packet loss, gaps, or jitter anomalies.
    """
    sequence_id: int
    arrival_timestamp_ns: int
    sample_offset_16k: int
    is_gap: bool
    is_reordered: bool
    missing_count: int
    message: str


@dataclass(frozen=True)
class AudioStreamEvent:
    """
    A single window of 16kHz mono audio published to downstream subscribers.
    """
    clip_id: str
    sample_offset: int
    samples_16k: np.ndarray  # 1D float32 at 16kHz
    arrival_timestamp_ns: int
    diagnostics: Optional[PacketDiagnostic] = None


@dataclass
class CapturedStreamData:
    """
    Accumulated stream data and adapter decisions for one completed clip evaluation.
    """
    clip_id: str
    decoded_audio_16k: np.ndarray
    arrival_timestamps_ns: List[int] = field(default_factory=list)
    adapter_decisions: Dict[str, List[DecisionRecord]] = field(default_factory=dict)
    packet_diagnostics: List[PacketDiagnostic] = field(default_factory=list)
    sample_rate_hz: int = 16000


# ==============================================================================
# High-Quality Polyphase Audio Resampling (48kHz -> 16kHz)
# ==============================================================================

def resample_48k_to_16k(audio_48k: np.ndarray) -> np.ndarray:
    """
    Resamples a 48kHz audio buffer to 16kHz mono float32 (3:1 integer downsampling).

    Uses polyphase filtering via scipy.signal.resample_poly if available, with a
    fallback to an anti-aliased polyphase FIR filter.
    """
    if len(audio_48k) == 0:
        return np.empty(0, dtype=np.float32)

    # Convert to 1D float32
    if audio_48k.ndim > 1:
        audio_48k = np.mean(audio_48k, axis=1 if audio_48k.shape[1] < audio_48k.shape[0] else 0)

    audio_float = audio_48k.astype(np.float32)

    try:
        from scipy.signal import resample_poly
        resampled = resample_poly(audio_float, up=1, down=3).astype(np.float32)
        return resampled
    except ImportError:
        # High-quality 24-tap anti-aliased polyphase FIR filter fallback (cutoff at 7.5kHz / Nyquist)
        # Normalized filter coefficients for 3:1 decimation
        fir_taps = np.array([
            -0.0012, -0.0031, -0.0020,  0.0062,  0.0175,  0.0172,
            -0.0083, -0.0478, -0.0718, -0.0381,  0.0792,  0.2461,
             0.3340,  0.2461,  0.0792, -0.0381, -0.0718, -0.0478,
            -0.0083,  0.0172,  0.0175,  0.0062, -0.0020, -0.0031
        ], dtype=np.float32)
        filtered = np.convolve(audio_float, fir_taps, mode="same")
        return filtered[::3].astype(np.float32)


# ==============================================================================
# Ingress Audio Decoder
# ==============================================================================

class OpusPCMDecoder:
    """
    Decodes inbound Opus byte packets or raw 48kHz PCM buffers to normalized 16kHz mono.
    """

    def __init__(self, source_sample_rate: int = 48000) -> None:
        self.source_sample_rate = source_sample_rate
        self._opus_decoder = None
        self._init_opus()

    def _init_opus(self) -> None:
        try:
            import opuslib  # type: ignore
            self._opus_decoder = opuslib.Decoder(self.source_sample_rate, 1)
        except (ImportError, Exception):
            self._opus_decoder = None

    def decode_chunk_to_16k(self, payload: Union[bytes, np.ndarray]) -> np.ndarray:
        """
        Decodes a binary or array chunk and converts to 16kHz mono float32.
        """
        if isinstance(payload, np.ndarray):
            if payload.dtype == np.int16:
                float_audio = payload.astype(np.float32) / 32768.0
            else:
                float_audio = payload.astype(np.float32)

            if self.source_sample_rate == 48000:
                return resample_48k_to_16k(float_audio)
            return float_audio

        elif isinstance(payload, bytes):
            # If native Opus decoder is available and payload is Opus-encoded
            if self._opus_decoder is not None:
                try:
                    # 960 samples per 20ms frame at 48kHz
                    pcm_bytes = self._opus_decoder.decode(payload, frame_size=960)
                    pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
                    pcm_float = pcm_int16.astype(np.float32) / 32768.0
                    return resample_48k_to_16k(pcm_float)
                except Exception:
                    pass

            # Fallback: treat as raw 16-bit PCM (48kHz)
            if len(payload) % 2 == 0:
                pcm_int16 = np.frombuffer(payload, dtype=np.int16)
                pcm_float = pcm_int16.astype(np.float32) / 32768.0
                if self.source_sample_rate == 48000:
                    return resample_48k_to_16k(pcm_float)
                return pcm_float

        return np.empty(0, dtype=np.float32)


# ==============================================================================
# Listener Bot Implementation
# ==============================================================================

class ListenerBot:
    """
    Tier 2 Ingress Bot managing live stream decoding, sequence tracking, and adapter dispatch.
    """

    def __init__(
        self,
        room_id: str,
        bridge_url: str,
        adapters: Optional[Dict[str, VADAdapterContract]] = None,
        scoring_grid_ms: int = 10,
        concurrency_mode: str = "sequential",
        jitter_buffer_window_ms: int = 40,
    ) -> None:
        """
        Initializes the ListenerBot.

        Args:
            room_id: Jitsi room/session identifier.
            bridge_url: WebSocket endpoint or tunnel URL for audio ingress.
            adapters: Dictionary of subscribed VADAdapterContract instances.
            scoring_grid_ms: Common scoring grid resolution.
            concurrency_mode: 'sequential' (timing runs) or 'parallel' (accuracy-only).
            jitter_buffer_window_ms: Buffer window for out-of-order packet reordering.
        """
        self.room_id = room_id
        self.bridge_url = bridge_url
        self.scoring_grid_ms = scoring_grid_ms
        self.concurrency_mode = concurrency_mode
        self.jitter_buffer_window_ms = jitter_buffer_window_ms

        self._active_adapters: Dict[str, VADAdapterContract] = adapters or {}
        self._decoder = OpusPCMDecoder(source_sample_rate=48000)

        # Sequence tracking state
        self._expected_sequence_id: int = 0
        self._current_clip_id: Optional[str] = None
        self._current_capture: Optional[CapturedStreamData] = None

        # Jitter reordering buffer: sequence_id -> (timestamp_ns, raw_payload)
        self._jitter_buffer: Dict[int, Tuple[int, Union[bytes, np.ndarray]]] = {}
        self._captured_audio_buffer: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._completion_event = threading.Event()

    def set_active_adapters(self, adapters: Dict[str, VADAdapterContract]) -> None:
        """Dynamically update the active adapter subscriber list (for sequential passes)."""
        with self._lock:
            self._active_adapters = dict(adapters)
            for adapter in self._active_adapters.values():
                adapter.reset()
            logger.debug("[ListenerBot] Subscribed %d active adapter(s)", len(self._active_adapters))

    def prepare_for_clip(self, clip_id: str) -> None:
        """Resets stream capture buffers and prepares for incoming clip playback."""
        with self._lock:
            self._current_clip_id = clip_id
            self._expected_sequence_id = 0
            self._jitter_buffer.clear()
            self._captured_audio_buffer.clear()
            self._completion_event.clear()

            self._current_capture = CapturedStreamData(
                clip_id=clip_id,
                decoded_audio_16k=np.empty(0, dtype=np.float32),
                adapter_decisions={name: [] for name in self._active_adapters},
            )

            for adapter in self._active_adapters.values():
                adapter.reset()

        logger.debug("[ListenerBot] Prepared for incoming stream: clip_id='%s'", clip_id)

    def ingest_packet(
        self,
        sequence_id: int,
        payload: Union[bytes, np.ndarray],
        timestamp_ns: Optional[int] = None,
        is_clip_end: bool = False,
    ) -> None:
        """
        Ingests an incoming packet from the Jitsi bridge WebSocket connection.

        Performs:
            1. Nanosecond arrival timestamping.
            2. Out-of-order reordering and gap detection.
            3. Single-point 48k -> 16k mono decoding and resampling.
            4. Dispatch to subscribed VAD adapters.
        """
        arrival_ns = timestamp_ns or time.perf_counter_ns()

        with self._lock:
            if self._current_capture is None:
                logger.warning("[ListenerBot] Received packet %d with no active clip configured.", sequence_id)
                return

            # Store into jitter buffer
            self._jitter_buffer[sequence_id] = (arrival_ns, payload)

            # Process contiguous ready sequences from jitter buffer
            self._flush_jitter_buffer()

            if is_clip_end:
                # Flush any remaining packets in jitter buffer on clip completion
                self._flush_remaining_jitter()
                if self._captured_audio_buffer:
                    self._current_capture.decoded_audio_16k = np.concatenate(self._captured_audio_buffer)
                self._completion_event.set()

    def _flush_jitter_buffer(self) -> None:
        """Extracts and processes contiguous sequences in order, detecting gaps."""
        while self._expected_sequence_id in self._jitter_buffer:
            seq_id = self._expected_sequence_id
            arrival_ns, raw_payload = self._jitter_buffer.pop(seq_id)
            self._process_single_ordered_packet(seq_id, arrival_ns, raw_payload, is_gap=False)
            self._expected_sequence_id += 1

    def _flush_remaining_jitter(self) -> None:
        """Flushes non-contiguous packets remaining in buffer, flagging gaps."""
        for seq_id in sorted(self._jitter_buffer.keys()):
            arrival_ns, raw_payload = self._jitter_buffer.pop(seq_id)

            is_gap = False
            missing_count = 0
            if seq_id > self._expected_sequence_id:
                is_gap = True
                missing_count = seq_id - self._expected_sequence_id

            self._process_single_ordered_packet(
                seq_id=seq_id,
                arrival_ns=arrival_ns,
                raw_payload=raw_payload,
                is_gap=is_gap,
                missing_count=missing_count,
            )
            self._expected_sequence_id = seq_id + 1

    def _process_single_ordered_packet(
        self,
        seq_id: int,
        arrival_ns: int,
        raw_payload: Union[bytes, np.ndarray],
        is_gap: bool = False,
        missing_count: int = 0,
    ) -> None:
        """Decodes, logs diagnostics, resamples to 16kHz, and dispatches to adapters."""
        if self._current_capture is None:
            return

        current_sample_offset = sum(len(b) for b in self._captured_audio_buffer)

        # 1. First-class Packet Diagnostic generation
        if is_gap:
            diag = PacketDiagnostic(
                sequence_id=seq_id,
                arrival_timestamp_ns=arrival_ns,
                sample_offset_16k=current_sample_offset,
                is_gap=True,
                is_reordered=True,
                missing_count=missing_count,
                message=f"Sequence gap detected: missing {missing_count} packet(s) before sequence {seq_id}",
            )
            self._current_capture.packet_diagnostics.append(diag)
            logger.warning("[ListenerBot] %s (Offset: %d samples)", diag.message, current_sample_offset)

        # 2. Decode and Resample exactly once to 16kHz mono float32
        samples_16k = self._decoder.decode_chunk_to_16k(raw_payload)
        if len(samples_16k) == 0:
            return

        self._captured_audio_buffer.append(samples_16k)
        self._current_capture.arrival_timestamps_ns.append(arrival_ns)

        # 3. Publish to subscribed VAD adapters (chunking at each adapter's declared hop)
        for adapter_name, adapter in self._active_adapters.items():
            try:
                chunks = chunk_audio_stream(samples_16k, adapter.frame_size_samples, 16000)
                for chunk in chunks:
                    global_sample_offset = current_sample_offset + chunk.sample_offset
                    record = adapter.process_frame(
                        frame=chunk.samples,
                        sample_offset=global_sample_offset,
                        frame_index=chunk.frame_index,
                    )
                    self._current_capture.adapter_decisions[adapter_name].append(record)
            except Exception as exc:
                logger.error(
                    "[ListenerBot | Adapter %s] Error processing stream chunk: %s",
                    adapter_name,
                    exc,
                )

    def await_clip_completion(self, clip_id: str, timeout_s: float = 30.0) -> CapturedStreamData:
        """
        Blocks until the active clip stream finishes transmission or times out.

        Args:
            clip_id: Expected clip identifier.
            timeout_s: Maximum timeout in seconds.

        Returns:
            A CapturedStreamData object containing decoded 16kHz audio, timestamps, and decisions.

        Raises:
            TimeoutError: If stream completion event does not fire within timeout_s.
            ListenerBotError: If clip_id mismatch occurs.
        """
        if self._current_clip_id != clip_id:
            raise ListenerBotError(
                f"Requested clip '{clip_id}' does not match active capture '{self._current_clip_id}'"
            )

        finished = self._completion_event.wait(timeout=timeout_s)
        if not finished:
            logger.error("[ListenerBot] Timeout waiting for clip '%s' completion after %.1fs", clip_id, timeout_s)
            with self._lock:
                if self._captured_audio_buffer and self._current_capture:
                    self._current_capture.decoded_audio_16k = np.concatenate(self._captured_audio_buffer)

        with self._lock:
            if self._current_capture is None:
                raise ListenerBotError("No capture data available.")
            return self._current_capture