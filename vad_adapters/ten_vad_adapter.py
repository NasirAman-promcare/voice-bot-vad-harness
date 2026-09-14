"""
vad_adapters/ten_vad_adapter.py

One Job:
    Wrap the TEN VAD engine behind VADAdapterContract, streaming 16kHz audio frames
    at its native hop size (256 samples / 16ms), capturing tight per-inference execution
    timestamps, and producing standardized DecisionRecord instances.

Declared Native Hop Size:
    This adapter operates with a native hop size of 256 samples (16.0 ms at 16 kHz).
    Although TEN VAD's C binding offers an alternate 160-sample (10 ms) mode, 256 samples
    is the primary receptive field and native hop of TEN VAD's underlying neural acoustic
    model, avoiding initial-frame buffer initialization anomalies (-1 return values) present
    in non-power-of-two configurations. All downstream decision-stream alignment onto the
    benchmark's 10 ms scoring grid is performed uniformly in scoring/vad_scorer.py.

What this module must NEVER do:
    - Never reference or parse run configurations, audio manifests, or ground-truth segments.
    - Never perform decision-stream-to-common-grid resampling or threshold sweeping.
    - Never fabricate confidence scores or invent extra metadata.
    - Never swallow per-frame or initialization exceptions; surface distinct typed errors.
    - Never include setup/teardown glue code inside the algorithmic latency measurement window.
"""

from __future__ import annotations

import ctypes
import logging
import os
import time
from typing import Any, Optional

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

class TENVADAdapterError(Exception):
    """Base exception for TEN VAD adapter operations."""
    pass


class TENVADInitializationError(TENVADAdapterError):
    """Raised when TEN VAD native libraries, bindings, or model weights fail to load."""
    pass


class TENVADInferenceError(TENVADAdapterError):
    """
    Raised when TEN VAD fails to process a specific audio frame.

    Carries contextual frame metadata for isolation and debug logging.
    """
    def __init__(
        self,
        message: str,
        frame_index: int,
        sample_offset: int,
        adapter_id: str = "ten_vad",
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
# Ctypes / Native Binding Wrapper
# ==============================================================================

class _NativeTenVadWrapper:
    """
    Internal low-level binding wrapper for TEN VAD's C dynamic library.
    Handles memory buffers, ctypes function signatures, and instance lifecycles.
    """

    def __init__(self, hop_size: int = 256, threshold: float = 0.5) -> None:
        self.hop_size = hop_size
        self.threshold = threshold
        self._handle = None
        self._lib = None
        self._load_library()
        self._init_instance()

    def _load_library(self) -> None:
        # Search candidate locations: environment variable, local lib dirs, standard system paths
        candidate_paths = []
        if "TEN_VAD_LIB_PATH" in os.environ:
            candidate_paths.append(os.environ["TEN_VAD_LIB_PATH"])

        # Standard Linux x64 dynamic library names
        lib_names = ["libten_vad.so", "ten_vad.dll", "libten_vad.dylib"]
        search_dirs = [
            os.path.dirname(__file__),
            os.path.join(os.path.dirname(__file__), "lib"),
            os.path.join(os.path.dirname(__file__), "lib", "Linux", "x64"),
            "/usr/local/lib",
            "/usr/lib",
        ]

        for sdir in search_dirs:
            for name in lib_names:
                candidate_paths.append(os.path.join(sdir, name))

        loaded = False
        last_error = None
        for path in candidate_paths:
            if os.path.isfile(path):
                try:
                    self._lib = ctypes.CDLL(path)
                    loaded = True
                    logger.debug("Successfully loaded TEN VAD library from '%s'", path)
                    break
                except Exception as exc:
                    last_error = exc

        if not loaded:
            # Attempt direct system dlopen
            for name in lib_names:
                try:
                    self._lib = ctypes.CDLL(name)
                    loaded = True
                    break
                except Exception as exc:
                    last_error = exc

        if not loaded or self._lib is None:
            raise TENVADInitializationError(
                "Failed to locate or load TEN VAD dynamic library (libten_vad.so). "
                "Ensure TEN VAD is installed or set the TEN_VAD_LIB_PATH environment variable. "
                f"Underlying error: {last_error}"
            )

        # Declare C function signatures
        try:
            # void* ten_vad_create(int hop_size, float threshold)
            self._lib.ten_vad_create.argtypes = [ctypes.c_int, ctypes.c_float]
            self._lib.ten_vad_create.restype = ctypes.c_void_p

            # int ten_vad_process(void* handle, const int16_t* audio_data, float* out_prob, int* out_flag)
            self._lib.ten_vad_process.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int16),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_int),
            ]
            self._lib.ten_vad_process.restype = ctypes.c_int

            # void ten_vad_destroy(void* handle)
            self._lib.ten_vad_destroy.argtypes = [ctypes.c_void_p]
            self._lib.ten_vad_destroy.restype = None

            # Optional reset symbol if provided by newer builds
            if hasattr(self._lib, "ten_vad_reset"):
                self._lib.ten_vad_reset.argtypes = [ctypes.c_void_p]
                self._lib.ten_vad_reset.restype = ctypes.c_int
        except AttributeError as exc:
            raise TENVADInitializationError(
                f"TEN VAD library is missing required C symbols: {exc}"
            ) from exc

    def _init_instance(self) -> None:
        if self._handle is not None:
            self._destroy_instance()

        handle = self._lib.ten_vad_create(self.hop_size, ctypes.c_float(self.threshold))
        if not handle:
            raise TENVADInitializationError(
                f"ten_vad_create() returned NULL handle (hop_size={self.hop_size}, threshold={self.threshold})"
            )
        self._handle = handle

    def _destroy_instance(self) -> None:
        if self._handle is not None and self._lib is not None:
            try:
                self._lib.ten_vad_destroy(self._handle)
            except Exception:
                pass
            self._handle = None

    def reset(self) -> None:
        if hasattr(self._lib, "ten_vad_reset") and self._handle is not None:
            res = self._lib.ten_vad_reset(self._handle)
            if res != 0:
                self._init_instance()
        else:
            self._init_instance()

    def process(self, audio_int16: np.ndarray) -> tuple[float, int]:
        if self._handle is None:
            raise TENVADInitializationError("TEN VAD handle is uninitialized.")

        c_prob = ctypes.c_float(0.0)
        c_flag = ctypes.c_int(0)
        audio_ptr = audio_int16.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))

        ret = self._lib.ten_vad_process(
            self._handle,
            audio_ptr,
            ctypes.byref(c_prob),
            ctypes.byref(c_flag),
        )
        if ret != 0:
            raise RuntimeError(f"ten_vad_process returned non-zero error status code: {ret}")

        prob = float(c_prob.value)
        flag = int(c_flag.value)
        return prob, flag

    def __del__(self) -> None:
        self._destroy_instance()


# ==============================================================================
# TEN VAD Adapter Implementation
# ==============================================================================

class TENVADAdapter(VADAdapterContract):
    """
    Adapter implementing VADAdapterContract for the TEN VAD streaming neural model.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        hardware_policy: str = "cpu_only",
        engine: Optional[Any] = None,
    ) -> None:
        """
        Instantiates the TEN VAD adapter.

        Args:
            threshold: Internal decision threshold for binary speech flag generation.
            hardware_policy: Compute hardware configuration (TEN VAD is CPU-only).
            engine: Optional pre-constructed engine or mock instance for testing.

        Raises:
            TENVADInitializationError: If the model or dynamic library fails to load.
        """
        self._adapter_id = "ten_vad"
        self._hop_size = 256  # 16.0 ms native frame size at 16 kHz
        self._threshold = float(threshold)
        self._hardware_policy = hardware_policy

        if hardware_policy != "cpu_only" and hardware_policy != "gpu_for_firered":
            logger.warning(
                "[%s] Unrecognized hardware_policy '%s'; TEN VAD runs on CPU.",
                self._adapter_id,
                hardware_policy,
            )

        if engine is not None:
            self._engine = engine
        else:
            self._engine = self._initialize_engine()

    def _initialize_engine(self) -> Any:
        # First attempt: standard ten_vad python package
        try:
            from ten_vad import TenVad  # type: ignore
            instance = TenVad(hop_size=self._hop_size, threshold=self._threshold)
            logger.info("[%s] Initialized via official `ten_vad` Python package.", self._adapter_id)
            return instance
        except ImportError:
            pass
        except Exception as exc:
            raise TENVADInitializationError(
                f"Failed to instantiate TenVad from python package: {exc}"
            ) from exc

        # Second attempt: ctypes binding wrapper
        try:
            return _NativeTenVadWrapper(hop_size=self._hop_size, threshold=self._threshold)
        except Exception as exc:
            raise TENVADInitializationError(
                f"Failed to initialize TEN VAD engine via ctypes dynamic library: {exc}"
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
        """Resets TEN VAD internal hidden recurrent state and frame counters."""
        try:
            if hasattr(self._engine, "reset"):
                self._engine.reset()
            else:
                # Recreate if reset is unavailable
                self._engine = self._initialize_engine()
        except Exception as exc:
            raise TENVADInitializationError(
                f"Failed to reset TEN VAD internal state: {exc}"
            ) from exc

    def process_frame(
        self,
        frame: np.ndarray,
        sample_offset: int,
        frame_index: int,
    ) -> DecisionRecord:
        """
        Process a single 256-sample 16kHz audio frame through TEN VAD.

        Tightly captures inference execution timestamp to isolate pure algorithmic compute time.

        Args:
            frame: 1D NumPy array of 256 audio samples.
            sample_offset: Absolute sample offset in the clip stream.
            frame_index: 0-indexed sequential frame count.

        Returns:
            A verified DecisionRecord containing the continuous probability score.

        Raises:
            ValueError: If frame length does not equal declared frame_size_samples.
            TENVADInferenceError: If TEN VAD inference execution fails on this frame.
        """
        if not isinstance(frame, np.ndarray):
            frame = np.asarray(frame)

        if frame.ndim != 1 or len(frame) != self._hop_size:
            raise ValueError(
                f"[{self._adapter_id}] Expected 1D frame of length {self._hop_size}, "
                f"received shape {frame.shape} (length {len(frame)})."
            )

        # Convert audio buffer to contiguous int16 outside timing window
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
            out_probability, out_flag = self._engine.process(audio_int16)
            t_end_ns = time.perf_counter_ns()
        except Exception as exc:
            logger.error(
                "[%s] Exception during frame processing at frame %d (offset %d): %s",
                self._adapter_id,
                frame_index,
                sample_offset,
                exc,
            )
            raise TENVADInferenceError(
                message=str(exc),
                frame_index=frame_index,
                sample_offset=sample_offset,
                adapter_id=self._adapter_id,
                cause=exc,
            ) from exc

        # Handle uninitialized startup anomalies
        score = float(out_probability)
        if score < 0.0:
            score = 0.0
        elif score > 1.0:
            score = 1.0

        is_speech = bool(out_flag == 1) if out_flag in (0, 1) else bool(score >= self._threshold)

        return DecisionRecord(
            adapter_id=self._adapter_id,
            sample_offset=sample_offset,
            frame_index=frame_index,
            is_speech=is_speech,
            score=score,
            confidence=None,  # TEN VAD does not produce independent confidence; never fabricated
            produced_timestamp_ns=t_end_ns,
            extra=None,  # No extra metadata emitted by TEN VAD
        )