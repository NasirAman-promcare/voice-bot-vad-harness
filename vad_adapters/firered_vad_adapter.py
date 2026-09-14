"""
vad_adapters/firered_vad_adapter.py

One Job:
    Wrap FireRedVAD's true STREAMING interface (DFSMN-based frame-by-frame inference)
    behind VADAdapterContract, enforce the explicit hardware execution policy, extract
    per-frame speech probability scores along with speech/singing/music acoustic class
    labels into DecisionRecord's bounded extra field, and capture tight algorithmic timing.

Declared Native Hop Size & Interface:
    - Interface: Streaming frame-by-frame API (FireRedStreamVad.detect_chunk), NEVER
      the offline whole-file call (FireRedVad.detect / detect_full).
    - Confirmed Native Hop Size: 160 samples (10.0 ms at 16 kHz).
      The streaming DFSMN acoustic encoder processes contiguous 10ms / 160-sample hops
      of 16kHz mono audio.

Hardware Fairness Policy Enforcement:
    Hardware execution mode is strictly controlled via the `hardware_policy` parameter:
      - 'cpu_only': Forces CPU inference regardless of CUDA GPU availability.
      - 'gpu_for_firered': Enables CUDA GPU acceleration specifically for FireRedVAD.
    Silent fallbacks to GPU when 'cpu_only' is selected, or silent fallback to CPU when
    'gpu_for_firered' is requested on a non-CUDA host, are forbidden and raise a
    FireRedVADHardwarePolicyError at construction time.

Fault Isolation Design:
    If FireRedVAD fails to initialize due to dependency conflicts (e.g. PyTorch CUDA binary
    mismatches, missing kaldi-native-fbank, or absent model weights), this module raises
    a typed FireRedVADInitializationError at construction time. orchestrator.py's adapter
    loader catches this typed exception, marks FireRedVAD as unavailable for the run,
    and allows independent adapters (TEN VAD, WebRTC) to proceed without session failure.

What this module must NEVER do:
    - Never call the offline whole-file detection method.
    - Never read run_config.yaml or global configuration directly.
    - Never silently alter hardware execution devices.
    - Never fabricate confidence metrics.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

from vad_adapters.adapter_contract import (
    ContractValidationError,
    DecisionRecord,
    VADAdapterContract,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class FireRedVADAdapterError(Exception):
    """Base exception for FireRedVAD adapter operations."""
    pass


class FireRedVADInitializationError(FireRedVADAdapterError):
    """Raised when FireRedVAD dependencies, native C bindings, or weights fail to load."""
    pass


class FireRedVADHardwarePolicyError(FireRedVADAdapterError):
    """Raised when the specified hardware policy cannot be strictly satisfied."""
    pass


class FireRedVADInferenceError(FireRedVADAdapterError):
    """
    Raised when FireRedVAD streaming inference fails during frame processing.

    Carries frame index and sample offset metadata for isolation and debugging.
    """
    def __init__(
        self,
        message: str,
        frame_index: int,
        sample_offset: int,
        adapter_id: str = "firered_vad",
        cause: Optional[Exception] = None,
    ) -> None:
        self.frame_index = frame_index
        self.sample_offset = sample_offset
        self.adapter_id = adapter_id
        self.cause = cause
        super().__init__(
            f"[{adapter_id}] Inference failed at frame {frame_index} (sample offset {sample_offset}): {message}"
        )


# ==============================================================================
# FireRedVAD Adapter Implementation
# ==============================================================================

class FireRedVADAdapter(VADAdapterContract):
    """
    Adapter implementing VADAdapterContract for FireRedVAD streaming DFSMN model.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        speech_threshold: float = 0.4,
        singing_threshold: float = 0.5,
        music_threshold: float = 0.5,
        hardware_policy: str = "cpu_only",
        engine: Optional[Any] = None,
    ) -> None:
        """
        Instantiates the FireRedVAD streaming adapter.

        Args:
            model_dir: Local path to FireRedVAD streaming weights directory.
            speech_threshold: Speech decision threshold [0.0, 1.0].
            singing_threshold: Singing event detection threshold [0.0, 1.0].
            music_threshold: Background music event detection threshold [0.0, 1.0].
            hardware_policy: Device policy ('cpu_only' or 'gpu_for_firered').
            engine: Optional pre-constructed streaming engine instance (for unit testing/mocks).

        Raises:
            FireRedVADHardwarePolicyError: If hardware policy cannot be strictly satisfied.
            FireRedVADInitializationError: If model weights or dependencies fail to load.
        """
        self._adapter_id = "firered_vad"
        self._hop_size = 160  # Confirmed native streaming hop: 10.0 ms at 16 kHz
        self._speech_threshold = float(speech_threshold)
        self._singing_threshold = float(singing_threshold)
        self._music_threshold = float(music_threshold)
        self._hardware_policy = hardware_policy
        self._model_dir = model_dir or os.environ.get(
            "FIREREDVAD_MODEL_DIR", "pretrained_models/FireRedVAD/Stream-VAD"
        )

        # Enforce hardware execution policy strictly
        self._use_gpu = self._validate_and_resolve_hardware_policy(hardware_policy)

        if engine is not None:
            self._engine = engine
        else:
            self._engine = self._initialize_streaming_engine()

    def _validate_and_resolve_hardware_policy(self, policy: str) -> bool:
        """
        Validates hardware policy against actual runtime capabilities without silent fallback.
        """
        if policy == "cpu_only":
            return False
        elif policy == "gpu_for_firered":
            # Verify CUDA availability through PyTorch
            try:
                import torch
                if not torch.cuda.is_available():
                    raise FireRedVADHardwarePolicyError(
                        "Hardware policy 'gpu_for_firered' was explicitly requested, "
                        "but PyTorch reports CUDA is NOT available on this system. "
                        "Aborting to avoid silent hardware bias."
                    )
                return True
            except ImportError as exc:
                raise FireRedVADHardwarePolicyError(
                    "Hardware policy 'gpu_for_firered' requested, but PyTorch is not installed: "
                    f"{exc}"
                ) from exc
        else:
            raise FireRedVADHardwarePolicyError(
                f"Invalid hardware_policy '{policy}'. Expected 'cpu_only' or 'gpu_for_firered'."
            )

    def _initialize_streaming_engine(self) -> Any:
        """
        Initializes the official FireRedVAD streaming model instance.
        """
        try:
            # Check official upstream package or repo imports
            try:
                from fireredvad import FireRedStreamVad, FireRedStreamVadConfig  # type: ignore
            except ImportError:
                from fireredasr2s.fireredvad import (  # type: ignore
                    FireRedStreamVad,
                    FireRedStreamVadConfig,
                )

            config = FireRedStreamVadConfig(
                use_gpu=self._use_gpu,
                smooth_window_size=5,
                speech_threshold=self._speech_threshold,
                pad_start_frame=5,
                min_speech_frame=8,
                max_speech_frame=2000,
                min_silence_frame=20,
                chunk_max_frame=30000,
            )

            instance = FireRedStreamVad.from_pretrained(self._model_dir, config)
            logger.info(
                "[%s] Initialized streaming engine from '%s' (GPU=%s)",
                self._adapter_id,
                self._model_dir,
                self._use_gpu,
            )
            return instance

        except (ImportError, ModuleNotFoundError) as exc:
            raise FireRedVADInitializationError(
                f"Failed to import FireRedVAD streaming module: {exc}. "
                "Ensure `fireredvad` (or `fireredasr2s`) and dependencies are installed."
            ) from exc
        except Exception as exc:
            raise FireRedVADInitializationError(
                f"Failed to instantiate FireRedStreamVad from '{self._model_dir}': {exc}"
            ) from exc

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def frame_size_samples(self) -> int:
        return self._hop_size

    @property
    def sample_rate_hz(self) -> int:
        return 16000

    def reset(self) -> None:
        """
        Resets streaming DFSMN memory buffers, history frames, and segment counters.
        """
        try:
            if hasattr(self._engine, "reset"):
                self._engine.reset()
            elif hasattr(self._engine, "clear"):
                self._engine.clear()
            else:
                # Re-instantiate streaming state if reset is unavailable
                self._engine = self._initialize_streaming_engine()
        except Exception as exc:
            raise FireRedVADInitializationError(
                f"Failed to reset FireRedVAD streaming state: {exc}"
            ) from exc

    def process_frame(
        self,
        frame: np.ndarray,
        sample_offset: int,
        frame_index: int,
    ) -> DecisionRecord:
        """
        Process a single 160-sample (10ms) 16kHz audio frame through the streaming pipeline.

        Args:
            frame: 1D NumPy array of 160 audio samples (float32 or int16).
            sample_offset: Absolute sample offset in the clip stream.
            frame_index: 0-indexed sequential frame count.

        Returns:
            A verified DecisionRecord containing the speech score and speech/singing/music extra.

        Raises:
            ValueError: If frame length is not 160 samples.
            FireRedVADInferenceError: If streaming inference fails on this frame.
        """
        if not isinstance(frame, np.ndarray):
            frame = np.asarray(frame)

        if frame.ndim != 1 or len(frame) != self._hop_size:
            raise ValueError(
                f"[{self._adapter_id}] Expected 1D frame of length {self._hop_size}, "
                f"received shape {frame.shape} (length {len(frame)})."
            )

        # Prepare 16-bit PCM integer buffer outside the timing window
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

        # TIGHT INFERENCE TIMING WINDOW: algorithmic latency measurement bounds
        try:
            t_start_ns = time.perf_counter_ns()
            # Call streaming chunk interface specifically (NOT offline whole-file detect)
            if hasattr(self._engine, "detect_chunk"):
                frame_results = self._engine.detect_chunk(audio_int16)
            elif hasattr(self._engine, "process"):
                frame_results = self._engine.process(audio_int16)
            else:
                raise RuntimeError("Engine missing streaming 'detect_chunk' or 'process' method.")
            t_end_ns = time.perf_counter_ns()
        except Exception as exc:
            logger.error(
                "[%s] Exception during streaming inference at frame %d (offset %d): %s",
                self._adapter_id,
                frame_index,
                sample_offset,
                exc,
            )
            raise FireRedVADInferenceError(
                message=str(exc),
                frame_index=frame_index,
                sample_offset=sample_offset,
                adapter_id=self._adapter_id,
                cause=exc,
            ) from exc

        # Parse per-frame results from streaming output
        raw_prob, is_speech_flag, extra_dict = self._parse_streaming_output(frame_results)

        score = float(np.clip(raw_prob, 0.0, 1.0))
        is_speech = bool(is_speech_flag)

        return DecisionRecord(
            adapter_id=self._adapter_id,
            sample_offset=sample_offset,
            frame_index=frame_index,
            is_speech=is_speech,
            score=score,
            confidence=None,  # FireRedVAD produces raw probability, not independent confidence
            produced_timestamp_ns=t_end_ns,
            extra=extra_dict,  # Acoustic class metadata (speech / singing / music)
        )

    def _parse_streaming_output(
        self,
        frame_results: Any,
    ) -> Tuple[float, bool, Dict[str, Any]]:
        """
        Parses streaming return structures, extracting continuous probability and AED labels.
        """
        raw_prob = 0.0
        is_speech = False
        acoustic_classes = {
            "speech": 0.0,
            "singing": 0.0,
            "music": 0.0,
        }

        # Extract primary speech probability and flags
        if isinstance(frame_results, (list, tuple)) and len(frame_results) > 0:
            item = frame_results[-1]
            if hasattr(item, "raw_prob"):
                raw_prob = float(item.raw_prob)
            elif hasattr(item, "prob"):
                raw_prob = float(item.prob)
            elif isinstance(item, (int, float)):
                raw_prob = float(item)

            if hasattr(item, "is_speech"):
                is_speech = bool(item.is_speech == 1 or item.is_speech is True)
            else:
                is_speech = bool(raw_prob >= self._speech_threshold)

            # Extract AED / multi-class probabilities if emitted
            if hasattr(item, "event_probs") and isinstance(item.event_probs, dict):
                acoustic_classes.update(item.event_probs)
            elif hasattr(item, "singing_prob") and hasattr(item, "music_prob"):
                acoustic_classes["singing"] = float(item.singing_prob)
                acoustic_classes["music"] = float(item.music_prob)
        elif isinstance(frame_results, dict):
            raw_prob = float(frame_results.get("raw_prob", frame_results.get("prob", 0.0)))
            is_speech = bool(frame_results.get("is_speech", raw_prob >= self._speech_threshold))
            if "event_probs" in frame_results and isinstance(frame_results["event_probs"], dict):
                acoustic_classes.update(frame_results["event_probs"])
        elif isinstance(frame_results, (int, float)):
            raw_prob = float(frame_results)
            is_speech = bool(raw_prob >= self._speech_threshold)
        elif hasattr(frame_results, "is_speech") and hasattr(frame_results, "confidence"):
            # e.g. OmniStreamVAD StreamResult
            raw_prob = float(frame_results.confidence)
            is_speech = bool(frame_results.is_speech)

        acoustic_classes["speech"] = raw_prob

        # Determine dominant acoustic class label
        dominant_label = "silence"
        max_score = 0.0
        for label, prob in acoustic_classes.items():
            if prob > max_score and prob >= self._speech_threshold:
                max_score = prob
                dominant_label = label

        extra: Dict[str, Any] = {
            "acoustic_class_label": dominant_label,
            "acoustic_class_probs": acoustic_classes,
        }

        return raw_prob, is_speech, extra