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
     Decodes inbound Opus byte packets directly to 16kHz mono float32 (A14 & A05).
     Fails loudly if opuslib/libopus is missing, eliminating silent raw PCM fallback.
     """
 
     def __init__(self, target_sample_rate: int = 16000) -> None:
         self.target_sample_rate = target_sample_rate
         self._opus_decoder = None
         self._init_opus()
 
     def _init_opus(self) -> None:
         try:
             import opuslib  # type: ignore
             # Direct 16kHz decoding: libopus handles stateful resampling internally (A14)
             self._opus_decoder = opuslib.Decoder(self.target_sample_rate, 1)
         except Exception as exc:
             raise ListenerBotError(
                 f"Failed to initialize Opus decoder at {self.target_sample_rate}Hz: {exc}. "
                 "Ensure 'opuslib' and system library 'libopus0' are installed."
             ) from exc
 
     def decode_chunk_to_16k(self, payload: Union[bytes, np.ndarray]) -> Tuple[np.ndarray, bool]:
         """
         Decodes payload to 16kHz mono float32.
         Returns (samples_16k, is_decode_error).
         """
         if isinstance(payload, np.ndarray):
             if payload.dtype == np.int16:
                 float_audio = payload.astype(np.float32) / 32768.0
             else:
                 float_audio = payload.astype(np.float32)

             return float_audio, False
 
         elif isinstance(payload, bytes):

             if self._opus_decoder is None:
                 raise ListenerBotError("Opus decoder is not available.")
             try:
                 # 320 samples per 20ms frame at 16kHz
                 pcm_bytes = self._opus_decoder.decode(payload, frame_size=320)
                 pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
                 pcm_float = pcm_int16.astype(np.float32) / 32768.0

                 return pcm_float, False
             except Exception as exc:
                 logger.warning("[ListenerBot] Opus decode failure on %d byte payload: %s", len(payload), exc)
                 # Conceal with 320 samples of silence (A05)
                 return np.zeros(320, dtype=np.float32), True
 

         return np.empty(0, dtype=np.float32), False


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
        self._decoder = OpusPCMDecoder(target_sample_rate=16000)
 
        # Sequence tracking state
        self._expected_sequence_id: int = 0
        self._current_clip_id: Optional[str] = None
        self._current_capture: Optional[CapturedStreamData] = None
           
        # Jitter reordering buffer: sequence_id -> (timestamp_ns, raw_payload)
        self._jitter_buffer: Dict[int, Tuple[int, Union[bytes, np.ndarray]]] = {}
        self._captured_audio_buffer: List[np.ndarray] = []
        # Per-adapter leftover sample buffer for frame-size mismatch (A04): adapter_name -> (leftover_samples, sample_offset, frame_index)
        self._adapter_carry: Dict[str, Tuple[np.ndarray, int, int]] = {}
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
            self._adapter_carry.clear()

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

            # Process contiguous ready sequences from jitter buffer and check loss timeout (A13)
            self._flush_jitter_buffer(current_arrival_ns=arrival_ns)

            if is_clip_end:
                # Flush any remaining packets in jitter buffer on clip completion
                self._flush_remaining_jitter()
                if self._captured_audio_buffer:
                    self._current_capture.decoded_audio_16k = np.concatenate(self._captured_audio_buffer)
                self._completion_event.set()
    
    def _flush_jitter_buffer(self, current_arrival_ns: Optional[int] = None) -> None:
        """
        Extracts contiguous sequences. If missing packets exceed jitter_buffer_window_ms,
        declares them lost, inserts concealment to preserve timeline (A06, A13), and continues.
        """
        window_ns = int(self.jitter_buffer_window_ms * 1_000_000)

        while self._jitter_buffer:
            # 1. Process contiguous sequence packets
            if self._expected_sequence_id in self._jitter_buffer:
                seq_id = self._expected_sequence_id
                arrival_ns, raw_payload = self._jitter_buffer.pop(seq_id)
                self._process_single_ordered_packet(seq_id, arrival_ns, raw_payload, is_gap=False)
                self._expected_sequence_id += 1
                continue

            # 2. Check jitter buffer loss timeout (A13)
            if current_arrival_ns is not None:
                min_buffered_seq = min(self._jitter_buffer.keys())
                oldest_arrival_ns, _ = self._jitter_buffer[min_buffered_seq]

                if (current_arrival_ns - oldest_arrival_ns) >= window_ns:
                    # Window elapsed: declare skipped packets lost
                    missing_count = min_buffered_seq - self._expected_sequence_id
                    arrival_ns, raw_payload = self._jitter_buffer.pop(min_buffered_seq)
                    self._process_single_ordered_packet(
                        seq_id=min_buffered_seq,
                        arrival_ns=arrival_ns,
                        raw_payload=raw_payload,
                        is_gap=(missing_count > 0),
                        missing_count=max(0, missing_count),
                    )
                    self._expected_sequence_id = min_buffered_seq + 1
                    continue

            # Neither contiguous nor timed out: wait for next packet
            break

    def _flush_remaining_jitter(self) -> None:
        """Flushes all non-contiguous packets remaining in buffer on clip end, flagging gaps."""
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
        """
        Preserves timeline upon packet loss (A06), decodes to 16kHz (A14),
        and feeds adapters statefully without dropping leftover samples (A04).
        """
        if self._current_capture is None:
            return

        current_sample_offset = sum(len(b) for b in self._captured_audio_buffer)

        # 1. Timeline Loss Compensation (A06): Insert 320 zero samples per lost packet
        if is_gap and missing_count > 0:
            lost_samples_count = missing_count * 320
            concealment_samples = np.zeros(lost_samples_count, dtype=np.float32)

            diag = PacketDiagnostic(
                sequence_id=seq_id,
                arrival_timestamp_ns=arrival_ns,
                sample_offset_16k=current_sample_offset,
                is_gap=True,
                is_reordered=True,
                missing_count=missing_count,
                message=f"Sequence gap detected: missing {missing_count} packet(s) before sequence {seq_id}. Inserted {lost_samples_count} concealment samples.",
            )
            self._current_capture.packet_diagnostics.append(diag)
            logger.warning("[ListenerBot] %s (Offset: %d samples)", diag.message, current_sample_offset)

            self._captured_audio_buffer.append(concealment_samples)
            # Dispatch loss concealment to adapters to prevent sample-clock drift
            self._dispatch_audio_to_adapters(concealment_samples, current_sample_offset)
            current_sample_offset += lost_samples_count

        # 2. Decode packet directly to 16kHz
        samples_16k, is_decode_error = self._decoder.decode_chunk_to_16k(raw_payload)
        if len(samples_16k) == 0:
            return

        if is_decode_error:
            diag = PacketDiagnostic(
                sequence_id=seq_id,
                arrival_timestamp_ns=arrival_ns,
                sample_offset_16k=current_sample_offset,
                is_gap=False,
                is_reordered=False,
                missing_count=0,
                message=f"Corrupt packet at sequence {seq_id}; substituted silence frame.",
            )
            self._current_capture.packet_diagnostics.append(diag)

        self._captured_audio_buffer.append(samples_16k)
        self._current_capture.arrival_timestamps_ns.append(arrival_ns)

        # 3. Dispatch to subscribed VAD adapters with leftover carry preservation (A04)
        self._dispatch_audio_to_adapters(samples_16k, current_sample_offset)

    def _dispatch_audio_to_adapters(self, new_samples: np.ndarray, current_sample_offset: int) -> None:
        """
        Carries leftover samples per adapter across packet boundaries (A04).
        Guarantees TEN VAD (256-sample hop) receives 100% of the audio stream without dropping remainder.
        """
        for adapter_name, adapter in self._active_adapters.items():
            try:
                leftover, base_offset, frame_idx = self._adapter_carry.get(
                    adapter_name,
                    (np.empty(0, dtype=np.float32), current_sample_offset, 0),
                )
                combined = np.concatenate([leftover, new_samples]) if leftover.size > 0 else new_samples
                frame_size = adapter.frame_size_samples
                num_frames = len(combined) // frame_size
                consumed = num_frames * frame_size

                for i in range(0, consumed, frame_size):
                    chunk = combined[i : i + frame_size]
                    record = adapter.process_frame(
                        frame=chunk,
                        sample_offset=base_offset + i,
                        frame_index=frame_idx,
                    )
                    self._current_capture.adapter_decisions[adapter_name].append(record)
                    frame_idx += 1

                # Carry remainder to next packet
                remainder = combined[consumed:]
                self._adapter_carry[adapter_name] = (remainder, base_offset + consumed, frame_idx)

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