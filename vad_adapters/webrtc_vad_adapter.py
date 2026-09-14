"""
vad_adapters/webrtc_vad_adapter.py

One Job:
    Wrap the classical WebRTC Voice Activity Detector behind VADAdapterContract across
    its four distinct aggressiveness modes (0, 1, 2, 3), strictly enforcing valid WebRTC
    frame sizes (10/20/30ms), emitting purely binary decisions with genuinely absent
    confidence/score values, and measuring tight algorithmic inference latency.

Package Dependency Note:
    - Package: `webrtcvad-wheels` (NOT the unmaintained `webrtcvad` package which
      relies on deprecated C extension build chains that fail on modern Python runtimes).
    - Installation: `pip install webrtcvad-wheels`
    - Module Import: `import webrtcvad`

Aggressiveness Mode Mapping (0–3):
    - Mode 0 (Quality): Least aggressive; lowest speech rejection rate, highest false
      positive rate in noise.
    - Mode 1 (Low Bitrate): Balanced filtering for low bitrate speech codecs.
    - Mode 2 (Aggressive): Moderate noise suppression.
    - Mode 3 (Very Aggressive): Most aggressive non-speech filtering; lowest false alarm
      rate in background noise, higher false rejection rate of quiet speech.
    Each mode is evaluated as an independent, honest operating point — never blended or
    interpolated.

Binary Decision Integrity:
    WebRTC VAD produces strictly binary (speech / non-speech) output with zero internal
    confidence score or probability metric. This adapter sets `score=None` and
    `confidence=None` in every DecisionRecord. No synthetic scores, smoothing filters,
    or hysteresis-based probabilities are ever manufactured here.

What this module must NEVER do:
    - Never synthesize or fake continuous scores or confidence values.
    - Never silently truncate or pad invalid frame lengths.
    - Never read run_config.yaml or global configuration directly.
    - Never swap or transpose aggressiveness mode indices.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence, Tuple

import numpy as np

from vad_adapters.adapter_contract import (
    ContractValidationError,
    DecisionRecord,
    VADAdapterContract,
)

logger = logging.getLogger(__name__)

# Strict WebRTC frame size constraints at 16 kHz (10ms, 20ms, 30ms)
VALID_FRAME_SIZES_SAMPLES: Tuple[int, ...] = (160, 320, 480)
VALID_MODES: Tuple[int, ...] = (0, 1, 2, 3)


# ==============================================================================
# Exceptions
# ==============================================================================

class WebRTCVADAdapterError(Exception):
    """Base exception for WebRTC VAD adapter operations."""
    pass


class WebRTCVADInitializationError(WebRTCVADAdapterError):
    """Raised when `webrtcvad-wheels` is missing or fails to initialize."""
    pass


class WebRTCVADInvalidFrameSizeError(WebRTCVADAdapterError, ValueError):
    """Raised when an audio frame size does not match WebRTC's strict requirements."""
    pass


class WebRTCVADInferenceError(WebRTCVADAdapterError):
    """
    Raised when WebRTC fails to process an audio frame during inference.

    Carries frame index and sample offset metadata for isolation and debugging.
    """
    def __init__(
        self,
        message: str,
        frame_index: int,
        sample_offset: int,
        adapter_id: str,
        cause: Optional[Exception] = None,
    ) -> None:
        self.frame_index = frame_index
        self.sample_offset = sample_offset
        self.adapter_id = adapter_id
        self.cause = cause
        super().__init__(
            f"[{adapter_id}] WebRTC inference failed at frame {frame_index} "
            f"(sample offset {sample_offset}): {message}"
        )


# ==============================================================================
# WebRTC VAD Adapter Implementation
# ==============================================================================

class WebRTCVADAdapter(VADAdapterContract):
    """
    Adapter implementing VADAdapterContract for one specific WebRTC VAD mode.
    """

    def __init__(
        self,
        mode: int = 2,
        frame_size_samples: int = 160,
        vad_instance: Optional[Any] = None,
    ) -> None:
        """
        Instantiates the WebRTC VAD adapter for a given aggressiveness mode.

        Args:
            mode: WebRTC aggressiveness mode: 0 (quality), 1 (low bitrate), 2 (aggressive), 3 (very aggressive).
            frame_size_samples: Hop size in samples. Must be one of (160, 320, 480) at 16kHz (default: 160 = 10ms).
            vad_instance: Optional pre-constructed `webrtcvad.Vad` instance (for testing/mocks).

        Raises:
            ValueError: If mode or frame_size_samples is not valid.
            WebRTCVADInitializationError: If webrtcvad-wheels is not installed.
        """
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid WebRTC mode '{mode}'. Must be an integer in {list(VALID_MODES)} "
                "(0=Quality, 1=LowBitrate, 2=Aggressive, 3=VeryAggressive)."
            )

        if frame_size_samples not in VALID_FRAME_SIZES_SAMPLES:
            raise WebRTCVADInvalidFrameSizeError(
                f"Invalid frame size: {frame_size_samples} samples. At 16kHz, WebRTC VAD "
                f"strictly requires one of {list(VALID_FRAME_SIZES_SAMPLES)} samples (10ms, 20ms, or 30ms)."
            )

        self._mode = int(mode)
        self._frame_size_samples = int(frame_size_samples)
        self._adapter_id = f"webrtc_vad_mode{self._mode}"
        self._sample_rate_hz = 16000

        if vad_instance is not None:
            self._vad = vad_instance
        else:
            self._vad = self._initialize_vad()

    def _initialize_vad(self) -> Any:
        """
        Initializes the underlying webrtcvad C binding engine with the configured mode.
        """
        try:
            # Requires `webrtcvad-wheels` package
            import webrtcvad  # type: ignore
            instance = webrtcvad.Vad(self._mode)
            logger.debug("[%s] Initialized webrtcvad.Vad(mode=%d)", self._adapter_id, self._mode)
            return instance
        except ImportError as exc:
            raise WebRTCVADInitializationError(
                "Failed to import `webrtcvad`. Ensure `webrtcvad-wheels` is installed "
                "via `pip install webrtcvad-wheels`."
            ) from exc
        except Exception as exc:
            raise WebRTCVADInitializationError(
                f"Failed to instantiate webrtcvad.Vad(mode={self._mode}): {exc}"
            ) from exc

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def frame_size_samples(self) -> int:
        return self._frame_size_samples

    @property
    def sample_rate_hz(self) -> int:
        return self._sample_rate_hz

    def reset(self) -> None:
        """
        Resets WebRTC VAD internal adaptive noise floor tracking state between clips.
        """
        self._vad = self._initialize_vad()

    def process_frame(
        self,
        frame: np.ndarray,
        sample_offset: int,
        frame_index: int,
    ) -> DecisionRecord:
        """
        Process a single 16kHz audio frame through WebRTC VAD.

        Args:
            frame: 1D NumPy array of audio samples (must match declared frame_size_samples).
            sample_offset: Absolute sample offset in the clip stream.
            frame_index: 0-indexed sequential frame count.

        Returns:
            A verified DecisionRecord containing the honest binary decision.

        Raises:
            WebRTCVADInvalidFrameSizeError: If frame length does not match valid WebRTC lengths.
            WebRTCVADInferenceError: If WebRTC C engine fails during processing.
        """
        if not isinstance(frame, np.ndarray):
            frame = np.asarray(frame)

        # Enforce strict frame length validation
        frame_len = len(frame) if frame.ndim == 1 else frame.size
        if frame.ndim != 1 or frame_len != self._frame_size_samples:
            if frame_len not in VALID_FRAME_SIZES_SAMPLES:
                raise WebRTCVADInvalidFrameSizeError(
                    f"[{self._adapter_id}] Frame size {frame_len} samples is invalid. "
                    f"WebRTC at 16kHz strictly accepts only {list(VALID_FRAME_SIZES_SAMPLES)} samples."
                )
            raise WebRTCVADInvalidFrameSizeError(
                f"[{self._adapter_id}] Frame size {frame_len} does not match adapter's declared "
                f"frame_size_samples={self._frame_size_samples}."
            )

        # Convert audio samples to 16-bit signed PCM byte string outside timing window
        if np.issubdtype(frame.dtype, np.floating):
            audio_int16 = np.ascontiguousarray(
                np.clip(frame, -1.0, 1.0) * 32767.0, dtype=np.int16
            )
        elif frame.dtype == np.int16:
            audio_int16 = np.ascontiguousarray(frame)
        else:
            audio_int16 = np.ascontiguousarray(
                np.clip(frame.astype(np.float32), -1.0, 1.0) * 32767.0, dtype=np.int16
            )

        pcm_bytes = audio_int16.tobytes()

        # TIGHT INFERENCE TIMING WINDOW: algorithmic latency measurement bounds
        try:
            t_start_ns = time.perf_counter_ns()
            is_speech = bool(self._vad.is_speech(pcm_bytes, self._sample_rate_hz))
            t_end_ns = time.perf_counter_ns()
        except Exception as exc:
            logger.error(
                "[%s] Exception during WebRTC processing at frame %d (offset %d): %s",
                self._adapter_id,
                frame_index,
                sample_offset,
                exc,
            )
            raise WebRTCVADInferenceError(
                message=str(exc),
                frame_index=frame_index,
                sample_offset=sample_offset,
                adapter_id=self._adapter_id,
                cause=exc,
            ) from exc

        return DecisionRecord(
            adapter_id=self._adapter_id,
            sample_offset=sample_offset,
            frame_index=frame_index,
            is_speech=is_speech,
            score=None,  # WebRTC is strictly binary; continuous score is genuinely absent
            confidence=None,  # WebRTC has no confidence score; never fabricated
            produced_timestamp_ns=t_end_ns,
            extra=None,  # No extra metadata emitted by WebRTC
        )