"""
vad_adapters/adapter_contract.py

One Job:
    Define the immutable input/output contract for all VAD adapters, provide the
    shared 16kHz audio frame-chunking utility used identically across Tier 1 and
    Tier 2, and supply strict contract conformance validators.

What this module must NEVER do:
    - Never import or reference any concrete adapter implementation (TEN VAD,
      FireRedVAD, or WebRTC).
    - Never include adapter-specific inference logic, heuristics, or thresholds.
    - Never perform decision-stream-to-common-grid resampling (which belongs
      strictly in scoring/vad_scorer.py).
    - Never fabricate missing fields (e.g. confidence scores for binary adapters).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Union

import numpy as np

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class ContractValidationError(ValueError):
    """Raised when an adapter's input, output, or lifecycle violates the contract."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class DecisionRecord:
    """
    Standardized inference output produced for each audio frame by every VAD adapter.

    Attributes:
        adapter_id: Identifier of the adapter / operating point (e.g. 'ten_vad', 'webrtc_vad_mode2').
        sample_offset: Position in the continuous stream where this frame begins (in 16kHz samples).
        frame_index: Monotonically increasing sequential index of the frame within the clip (0-indexed).
        is_speech: Binary speech decision (True=speech, False=non-speech), or None if purely continuous.
        score: Continuous speech probability [0.0, 1.0] when genuinely produced; None for discrete VADs.
        confidence: Engine confidence metric [0.0, 1.0] when genuinely produced; None otherwise.
        produced_timestamp_ns: Monotonic nanosecond timestamp recorded when the decision was generated.
        extra: Bounded adapter-specific metadata (e.g. FireRedVAD's acoustic class labels); None if unused.
    """
    adapter_id: str
    sample_offset: int
    frame_index: int
    is_speech: Optional[bool]
    score: Optional[float]
    confidence: Optional[float] = None
    produced_timestamp_ns: int = 0
    extra: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.produced_timestamp_ns == 0:
            object.__setattr__(self, "produced_timestamp_ns", time.perf_counter_ns())


@dataclass(frozen=True)
class AudioChunk:
    """
    A single windowed frame sliced from a continuous 16kHz mono audio stream.

    Attributes:
        frame_index: 0-indexed sequential frame index.
        sample_offset: Sample index in the full stream where this frame starts.
        samples: 1D NumPy array of 16kHz mono audio samples (float32 or int16).
    """
    frame_index: int
    sample_offset: int
    samples: np.ndarray


# ==============================================================================
# Abstract Adapter Contract
# ==============================================================================

class VADAdapterContract(ABC):
    """
    Abstract contract that all concrete VAD adapters MUST implement.

    Ensures uniform streaming interface, native frame declarations, and state lifecycle.
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique identifier representing this adapter and operating point."""
        raise NotImplementedError

    @property
    @abstractmethod
    def frame_size_samples(self) -> int:
        """Native hop/frame size in samples required per step at 16kHz."""
        raise NotImplementedError

    @property
    def sample_rate_hz(self) -> int:
        """Audio sample rate requirement. Fixed at 16000 Hz across all adapters."""
        return 16000

    @abstractmethod
    def reset(self) -> None:
        """
        Reset all internal recurrent states, sliding history buffers, and hangover
        counters between audio clips or test runs.
        """
        raise NotImplementedError

    @abstractmethod
    def process_frame(
        self,
        frame: np.ndarray,
        sample_offset: int,
        frame_index: int,
    ) -> DecisionRecord:
        """
        Process a single 16kHz mono frame of exactly frame_size_samples.

        Args:
            frame: 1D NumPy array of length frame_size_samples.
            sample_offset: Absolute sample offset of the frame start in the stream.
            frame_index: Monotonic frame counter index.

        Returns:
            A conformant DecisionRecord instance.
        """
        raise NotImplementedError


# ==============================================================================
# Shared Frame Chunking Utility
# ==============================================================================

def chunk_audio_stream(
    audio: np.ndarray,
    frame_size_samples: int,
    sample_rate_hz: int = 16000,
) -> Iterator[AudioChunk]:
    """
    Slices a continuous 16kHz mono audio buffer into contiguous, non-overlapping frames.

    Used identically by Tier 1's local loop and Tier 2's Listener Bot subscription.

    Leftover Tail Policy:
        Any trailing audio segment shorter than frame_size_samples is DROPPED and logged.
        Rationale: Zero-padding or extrapolating partial tail frames synthesizes artificial
        step discontinuities and transient spectral spikes that trigger false onset/hangover
        detections in neural and spectral models. Dropping partial tail frames maintains
        strict ground-truth sample alignment without introducing synthetic acoustic artifacts.

    Args:
        audio: 1D NumPy array of audio samples (or 2D array of shape [1, N] / [N, 1]).
        frame_size_samples: Target frame size in samples (> 0).
        sample_rate_hz: Expected sample rate (must be 16000).

    Yields:
        AudioChunk objects containing frame_index, sample_offset, and the 1D sample frame.

    Raises:
        ValueError: If audio shape or sample rate violates mono 16kHz requirements.
    """
    if sample_rate_hz != 16000:
        raise ValueError(
            f"Unsupported sample rate: {sample_rate_hz} Hz. All adapters require 16000 Hz."
        )

    if frame_size_samples <= 0:
        raise ValueError(f"frame_size_samples must be positive, got {frame_size_samples}.")

    # Normalize audio buffer dimensions
    if not isinstance(audio, np.ndarray):
        audio = np.asarray(audio)

    if audio.ndim == 2:
        if audio.shape[0] == 1:
            audio = audio.squeeze(axis=0)
        elif audio.shape[1] == 1:
            audio = audio.squeeze(axis=1)
        else:
            raise ValueError(
                f"Multi-channel audio not supported. Expected mono (1D), got shape {audio.shape}."
            )
    elif audio.ndim > 2:
        raise ValueError(f"Invalid audio array dimensions: {audio.ndim}D. Expected 1D mono.")

    total_samples = len(audio)
    if total_samples == 0:
        return

    num_full_frames = total_samples // frame_size_samples
    leftover_samples = total_samples % frame_size_samples

    if leftover_samples > 0:
        logger.debug(
            "Dropping trailing %d leftover samples (< frame_size_samples=%d) from stream of %d samples.",
            leftover_samples,
            frame_size_samples,
            total_samples,
        )

    for frame_idx in range(num_full_frames):
        start_sample = frame_idx * frame_size_samples
        end_sample = start_sample + frame_size_samples
        frame_slice = audio[start_sample:end_sample]

        yield AudioChunk(
            frame_index=frame_idx,
            sample_offset=start_sample,
            samples=frame_slice,
        )


# ==============================================================================
# Conformance Verification
# ==============================================================================

def validate_decision_record(
    record: Any,
    expected_adapter_id: Optional[str] = None,
) -> None:
    """
    Validates that a record matches the immutable DecisionRecord schema and value constraints.

    Raises:
        ContractValidationError: If any field fails schema, type, or boundary constraints.
    """
    if not isinstance(record, DecisionRecord):
        raise ContractValidationError(
            f"Expected DecisionRecord instance, got {type(record).__name__}."
        )

    if not isinstance(record.adapter_id, str) or not record.adapter_id.strip():
        raise ContractValidationError(
            f"DecisionRecord.adapter_id must be a non-empty string, got {record.adapter_id!r}."
        )

    if expected_adapter_id is not None and record.adapter_id != expected_adapter_id:
        raise ContractValidationError(
            f"DecisionRecord.adapter_id mismatch: expected {expected_adapter_id!r}, "
            f"got {record.adapter_id!r}."
        )

    if not isinstance(record.sample_offset, int) or record.sample_offset < 0:
        raise ContractValidationError(
            f"DecisionRecord.sample_offset must be a non-negative int, got {record.sample_offset}."
        )

    if not isinstance(record.frame_index, int) or record.frame_index < 0:
        raise ContractValidationError(
            f"DecisionRecord.frame_index must be a non-negative int, got {record.frame_index}."
        )

    # Must provide at least one of score or is_speech
    if record.score is None and record.is_speech is None:
        raise ContractValidationError(
            "DecisionRecord must provide at least one of 'score' (continuous) or 'is_speech' (binary)."
        )

    if record.score is not None:
        if not isinstance(record.score, (int, float)) or isinstance(record.score, bool):
            raise ContractValidationError(
                f"DecisionRecord.score must be float/int, got {type(record.score).__name__}."
            )
        if not (0.0 <= float(record.score) <= 1.0):
            raise ContractValidationError(
                f"DecisionRecord.score out of range [0.0, 1.0]: {record.score}."
            )

    if record.is_speech is not None and not isinstance(record.is_speech, bool):
        raise ContractValidationError(
            f"DecisionRecord.is_speech must be boolean or None, got {type(record.is_speech).__name__}."
        )

    if record.confidence is not None:
        if not isinstance(record.confidence, (int, float)) or isinstance(record.confidence, bool):
            raise ContractValidationError(
                f"DecisionRecord.confidence must be float/int or None, got {type(record.confidence).__name__}."
            )
        if not (0.0 <= float(record.confidence) <= 1.0):
            raise ContractValidationError(
                f"DecisionRecord.confidence out of range [0.0, 1.0]: {record.confidence}."
            )

    if not isinstance(record.produced_timestamp_ns, int) or record.produced_timestamp_ns <= 0:
        raise ContractValidationError(
            f"DecisionRecord.produced_timestamp_ns must be a positive integer, got {record.produced_timestamp_ns}."
        )

    if record.extra is not None and not isinstance(record.extra, (dict, Mapping)):
        raise ContractValidationError(
            f"DecisionRecord.extra must be a Mapping or None, got {type(record.extra).__name__}."
        )


def check_adapter_conformance(
    adapter: VADAdapterContract,
    test_duration_frames: int = 5,
) -> None:
    """
    Executes a comprehensive contract conformance suite on a concrete VAD adapter.

    Validates:
        1. Class inheritance and property declarations (sample_rate_hz=16000, frame_size_samples > 0).
        2. Clean execution of reset().
        3. Correct processing of standard 16kHz frames yielding conformant DecisionRecords.
        4. Rejection of invalid frame shapes and lengths.
        5. Monotonic timestamping and frame offset progression.
        6. Clean post-run state reset.

    Args:
        adapter: The VAD adapter instance to test.
        test_duration_frames: Number of synthetic test frames to process.

    Raises:
        ContractValidationError: If the adapter violates any contract specification.
    """
    if not isinstance(adapter, VADAdapterContract):
        raise ContractValidationError(
            f"Adapter {type(adapter).__name__} does not implement VADAdapterContract."
        )

    if adapter.sample_rate_hz != 16000:
        raise ContractValidationError(
            f"Adapter {adapter.adapter_id} declared invalid sample rate: {adapter.sample_rate_hz} Hz (must be 16000)."
        )

    frame_size = adapter.frame_size_samples
    if not isinstance(frame_size, int) or frame_size <= 0:
        raise ContractValidationError(
            f"Adapter {adapter.adapter_id} declared invalid frame_size_samples: {frame_size}."
        )

    try:
        adapter.reset()
    except Exception as exc:
        raise ContractValidationError(
            f"Adapter {adapter.adapter_id} failed on initial reset(): {exc}"
        ) from exc

    # Generate synthetic frames: quiet speech-level float32 sinusoidal frame
    t = np.linspace(0, frame_size / 16000.0, frame_size, endpoint=False, dtype=np.float32)
    synthetic_frame = (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    last_timestamp_ns = 0
    for frame_idx in range(test_duration_frames):
        sample_offset = frame_idx * frame_size

        try:
            record = adapter.process_frame(
                frame=synthetic_frame,
                sample_offset=sample_offset,
                frame_index=frame_idx,
            )
        except Exception as exc:
            raise ContractValidationError(
                f"Adapter {adapter.adapter_id} raised exception on frame {frame_idx}: {exc}"
            ) from exc

        validate_decision_record(record, expected_adapter_id=adapter.adapter_id)

        if record.frame_index != frame_idx:
            raise ContractValidationError(
                f"Adapter {adapter.adapter_id} returned frame_index={record.frame_index}, expected {frame_idx}."
            )

        if record.sample_offset != sample_offset:
            raise ContractValidationError(
                f"Adapter {adapter.adapter_id} returned sample_offset={record.sample_offset}, expected {sample_offset}."
            )

        if record.produced_timestamp_ns < last_timestamp_ns:
            raise ContractValidationError(
                f"Adapter {adapter.adapter_id} produced non-monotonic timestamp: "
                f"{record.produced_timestamp_ns} < {last_timestamp_ns}."
            )
        last_timestamp_ns = record.produced_timestamp_ns

    # Test error handling: reject malformed frame size
    malformed_frame = np.zeros(frame_size + 17, dtype=np.float32)
    try:
        adapter.process_frame(malformed_frame, sample_offset=0, frame_index=0)
    except (ValueError, ContractValidationError):
        pass  # Expected rejection
    else:
        raise ContractValidationError(
            f"Adapter {adapter.adapter_id} accepted an invalid frame length ({len(malformed_frame)} != {frame_size}) "
            "without raising ValueError or ContractValidationError."
        )

    # Post-run cleanup reset
    try:
        adapter.reset()
    except Exception as exc:
        raise ContractValidationError(
            f"Adapter {adapter.adapter_id} failed on post-run reset(): {exc}"
        ) from exc

    logger.info("Adapter '%s' passed contract conformance checks.", adapter.adapter_id)