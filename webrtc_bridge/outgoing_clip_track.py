"""
webrtc_bridge/outgoing_clip_track.py

One Job:
    Subclass aiortc's MediaStreamTrack to turn one 16kHz mono WAV audio file into
    paced, 48kHz Opus-ready AudioFrame instances for the WebRTC Speaker role.

Audio Upsampling & Single Resampling Authority:
    This module owns the outbound 16kHz -> 48kHz audio upsampling using high-quality
    polyphase filtering (scipy.signal.resample_poly at 3:1 ratio). Inbound 48kHz -> 16kHz
    downsampling remains strictly and exclusively owned by `bots.listener_bot.ListenerBot`.

Real-Time Monotonic Frame Pacing:
    Frames are emitted at Opus's native 20ms ptime (960 samples per frame at 48kHz).
    Pacing is computed against `time.perf_counter_ns()` with cumulative drift correction,
    guaranteeing that frames are never handed to the encoder faster than real time.

Continuous Stream & Lifecycle Stability:
    When the source clip's real audio samples are exhausted, `done_event` is set exactly
    once to notify `injector.py` that audio transmission has completed. Thereafter, `recv()`
    continues yielding correctly-paced 20ms silence frames indefinitely to maintain the
    RTP stream without triggering sender teardowns before the next clip is queued.

What this module must NEVER do:
    - Never add artificial silence padding beyond what the manifest clip already contains.
    - Never let `recv()` block on anything other than its monotonic pacing clock.
    - Never reference Jingle, XMPP, or any signaling concepts.
    - Never swallow missing file or sample rate mismatch errors at construction time.
"""

from __future__ import annotations

import asyncio
import fractions
import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional, Union

import av
import numpy as np
import soundfile as sf
from aiortc import MediaStreamTrack
from scipy.signal import resample_poly

logger = logging.getLogger("webrtc_bridge.outgoing_clip_track")


# ==============================================================================
# Exceptions
# ==============================================================================

class OutgoingClipTrackError(Exception):
    """Base exception for outgoing clip track failures."""
    pass


class ClipTrackFileNotFoundError(OutgoingClipTrackError, FileNotFoundError):
    """Raised when the specified audio clip file does not exist on disk."""
    pass


class SampleRateMismatchError(OutgoingClipTrackError, ValueError):
    """Raised when the audio file's native sample rate does not match the required rate."""
    pass


class AudioFileDecodeError(OutgoingClipTrackError, RuntimeError):
    """Raised when decoding the WAV audio file fails."""
    pass


# ==============================================================================
# Manifest Clip Track Implementation
# ==============================================================================

class ManifestClipTrack(MediaStreamTrack):
    """
    Custom aiortc MediaStreamTrack delivering paced 48kHz Opus-ready audio frames.
    """

    kind = "audio"

    def __init__(
        self,
        audio_path: Union[str, Path],
        sample_rate_hz: int = 16000,
    ) -> None:
        """
        Initializes the clip track, validates the source WAV, and pre-computes the 48kHz buffer.

        Args:
            audio_path: Path to the 16kHz mono WAV file.
            sample_rate_hz: Expected input sample rate (must be 16000).

        Raises:
            ClipTrackFileNotFoundError: If the file does not exist on disk.
            SampleRateMismatchError: If the file's native sample rate != sample_rate_hz.
            AudioFileDecodeError: If reading or resampling the audio fails.
        """
        super().__init__()

        self.expected_sample_rate = int(sample_rate_hz)
        self.output_sample_rate = 48000
        self.frame_samples_48k = 960  # 20ms ptime at 48kHz (48000 * 0.020)
        self.frame_duration_ns = 20_000_000  # 20ms in nanoseconds

        # 1. Resolve and Validate File Existence (Fail Fast at Construction)
        target_path = Path(audio_path)
        if not target_path.is_file():
            # Check standard corpus/audio directory fallback
            candidate = Path("corpus/audio") / target_path.name
            if candidate.is_file():
                target_path = candidate
            else:
                raise ClipTrackFileNotFoundError(
                    f"Audio clip file not found: {target_path.resolve()} (also checked {candidate.resolve()})"
                )

        self.audio_path = target_path.resolve()

        # 2. Inspect Sample Rate Defensively
        try:
            info = sf.info(str(self.audio_path))
            if info.samplerate != self.expected_sample_rate:
                raise SampleRateMismatchError(
                    f"Audio file '{self.audio_path.name}' has sample rate {info.samplerate} Hz, "
                    f"expected {self.expected_sample_rate} Hz."
                )
        except SampleRateMismatchError:
            raise
        except Exception as exc:
            raise AudioFileDecodeError(
                f"Failed to inspect audio file '{self.audio_path}': {exc}"
            ) from exc

        # 3. Load Audio and Resample 16kHz -> 48kHz (3:1 Polyphase Upsample)
        try:
            data, sr = sf.read(str(self.audio_path), dtype="float32")
            if data.ndim > 1:
                data = np.mean(data, axis=1, dtype=np.float32)

            # 3:1 integer upsampling (16kHz -> 48kHz)
            resampled_float = resample_poly(data, up=3, down=1).astype(np.float32)
            # Convert to contiguous int16 for PyAV AudioFrame packing
            self._audio_48k_int16 = np.ascontiguousarray(
                np.clip(resampled_float, -1.0, 1.0) * 32767.0, dtype=np.int16
            )
        except Exception as exc:
            raise AudioFileDecodeError(
                f"Failed to decode and resample audio file '{self.audio_path}': {exc}"
            ) from exc

        self.total_samples_48k = len(self._audio_48k_int16)
        self.total_frames_count = int(math.ceil(self.total_samples_48k / self.frame_samples_48k))
        self.duration_seconds = float(self.total_samples_48k / self.output_sample_rate)

        # 4. Transmission Synchronization
        self.done_event = threading.Event()
        self._is_done_fired = False

        # 5. Pacing & PTS State
        self._current_frame_index = 0
        self._start_time_ns: Optional[int] = None
        self._pts = 0
        self._time_base = fractions.Fraction(1, self.output_sample_rate)

        # Pre-allocated 20ms silence frame buffer
        self._silence_frame_int16 = np.zeros(self.frame_samples_48k, dtype=np.int16)

        logger.info(
            "ManifestClipTrack initialized for '%s' (Duration: %.2fs, %d frames @ 48kHz)",
            self.audio_path.name,
            self.duration_seconds,
            self.total_frames_count,
        )

    # --------------------------------------------------------------------------
    # aiortc MediaStreamTrack Protocol
    # --------------------------------------------------------------------------
    async def recv(self) -> av.AudioFrame:
        """
        Emits the next paced 48kHz 20ms AudioFrame to the WebRTC audio encoder.

        Enforces strictly monotonic pacing against real-world clock time and yields
        continuous silence frames indefinitely after the clip payload finishes.

        Returns:
            An `av.AudioFrame` containing 960 samples of 48kHz mono 16-bit PCM.
        """
        now_ns = time.perf_counter_ns()
        if self._start_time_ns is None:
            self._start_time_ns = now_ns

        # 1. Pacing Calculation with Cumulative Drift Correction
        target_send_time_ns = self._start_time_ns + (self._current_frame_index * self.frame_duration_ns)
        sleep_duration_s = (target_send_time_ns - now_ns) / 1_000_000_000.0

        if sleep_duration_s > 0.001:
            await asyncio.sleep(sleep_duration_s)

        # 2. Extract Frame Payload
        start_sample = self._current_frame_index * self.frame_samples_48k
        end_sample = start_sample + self.frame_samples_48k

        if start_sample < self.total_samples_48k:
            # Active clip audio payload
            chunk = self._audio_48k_int16[start_sample:end_sample]
            if len(chunk) < self.frame_samples_48k:
                # Pad final partial frame with zeros to maintain 960-sample ptime
                padded_chunk = np.zeros(self.frame_samples_48k, dtype=np.int16)
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk
        else:
            # Clip payload exhausted: signal completion once and emit silence
            if not self._is_done_fired:
                self._is_done_fired = True
                self.done_event.set()
                logger.debug(
                    "Clip transmission completed for '%s' at frame %d. Transitioning to silence feed.",
                    self.audio_path.name,
                    self._current_frame_index,
                )
            chunk = self._silence_frame_int16

        # 3. Construct PyAV AudioFrame
        # PyAV expects 2D array of shape [channels, samples] -> [1, 960]
        chunk_2d = np.ascontiguousarray(chunk.reshape(1, -1), dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(chunk_2d, format="s16", layout="mono")
        frame.sample_rate = self.output_sample_rate
        frame.pts = self._pts
        frame.time_base = self._time_base

        self._pts += self.frame_samples_48k
        self._current_frame_index += 1

        return frame