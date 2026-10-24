"""Voice activity detectors behind one frame-by-frame interface: Silero v5 and v4, and the harness's FireRed, TEN and WebRTC VADs.

CAPABILITIES:
  CAP-S2-004: VADAdapter is the one interface (name, frame_samples at 16 kHz, reset(), process(frame) -> (is_speech, score));
    run_vad() feeds a 16-bit clip to an adapter in whole frames (a shorter tail is dropped and counted by n_scored_samples) and
    returns Decisions with the per-frame flags, scores and the compute time [tests:
    test_s2_run_vad_scores_whole_frames_and_reports_the_dropped_tail]
  CAP-S2-005: HysteresisSmoother turns a raw frame stream into a causal one: speech is reported after min_speech_ms of speech
    frames and ends after min_silence_ms of non-speech frames, both rounded up to whole frames [tests:
    test_s2_smoother_hand_worked, test_s2_smoother_with_one_frame_minimums_changes_nothing,
    test_s2_smoother_rounds_minimums_up_to_whole_frames]
  CAP-S2-006: SileroVAD runs the Silero ONNX models through onnxruntime on one thread (v5: 512-sample frames with a 64-sample
    context and a 2 x 1 x 128 state; v4: 512-sample frames with h and c states of 2 x 1 x 64); HarnessVAD wraps the
    repository's existing FireRedVAD, TEN VAD and WebRTC VAD adapters (vad_adapters/, read only) behind the same interface.
    They need onnxruntime or the vendors' packages and weights, so the Oracle smoke run checks them; they have no unit tests.
INPUTS AND OUTPUTS: 16 kHz mono int16 samples in; Decisions out; VADError.
CONTRACTS: brief sections 3.1 and 4 (frame sizes; decisions are used as the model gives them, smoothing only where the config
  asks for it).
INVARIANTS:
  - A frame is always exactly frame_samples long; the clip's tail shorter than a frame is not scored by anyone, reference or VAD.
  - Smoothing never looks ahead: a decision depends on the frames up to and including the current one.
  - onnxruntime and the vendors' packages are imported when an adapter is built, never at module import.
NOT IN SCOPE:
  - Scoring decisions against references (aqis_lab/live/score.py) and fetching model files (aqis_lab/live/prep.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import importlib
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aqis_lab.bench import lib

REPO_ROOT = Path(__file__).resolve().parents[2]
SR = 16000


class VADError(RuntimeError):
    """A VAD cannot be built or run."""


@dataclass
class Decisions:
    frame_samples: int
    speech: np.ndarray            # bool per frame
    score: np.ndarray             # float per frame, nan where the VAD gives no probability
    n_scored_samples: int
    compute_s: float


class VADAdapter(ABC):
    name = ""
    frame_samples = 0

    @abstractmethod
    def reset(self):
        """Forget everything between clips."""

    @abstractmethod
    def process(self, frame):
        """(is_speech, score or None) for exactly frame_samples int16 samples."""


def run_vad(adapter, samples):
    x = np.asarray(samples)
    if x.dtype != np.int16 or x.ndim != 1:
        raise VADError(f"a clip must be one-dimensional int16, got {x.dtype} {x.shape}")
    h = adapter.frame_samples
    n = len(x) // h
    speech, scores = np.zeros(n, dtype=bool), np.full(n, np.nan)
    adapter.reset()
    compute = 0.0
    for k in range(n):
        frame = np.ascontiguousarray(x[k * h:(k + 1) * h])
        started = time.perf_counter()
        flag, prob = adapter.process(frame)
        compute += time.perf_counter() - started
        speech[k] = bool(flag)
        if prob is not None:
            scores[k] = float(prob)
    return Decisions(frame_samples=h, speech=speech, score=scores, n_scored_samples=n * h, compute_s=compute)


class HysteresisSmoother:
    def __init__(self, frame_ms, min_speech_ms, min_silence_ms):
        self.on_frames = max(1, -(-int(min_speech_ms) // int(frame_ms)))
        self.off_frames = max(1, -(-int(min_silence_ms) // int(frame_ms)))

    def apply(self, raw):
        out = np.zeros(len(raw), dtype=bool)
        state, speech_run, silence_run = False, 0, 0
        for k, flag in enumerate(raw):
            if flag:
                speech_run, silence_run = speech_run + 1, 0
                if not state and speech_run >= self.on_frames:
                    state = True
            else:
                silence_run, speech_run = silence_run + 1, 0
                if state and silence_run >= self.off_frames:
                    state = False
            out[k] = state
        return out


# ---- Silero ----------------------------------------------------------------------------------------------------
class SileroVAD(VADAdapter):
    frame_samples = 512

    def __init__(self, name, version, model_path, threshold):
        if version not in ("v4", "v5"):
            raise VADError(f"Silero version must be v4 or v5, got {version!r}")
        ort = lib("onnxruntime")
        options = ort.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
        self.name, self.version, self.threshold = name, version, threshold
        self.reset()

    def reset(self):
        if self.version == "v5":
            self.state = np.zeros((2, 1, 128), dtype=np.float32)
            self.context = np.zeros((1, 64), dtype=np.float32)
        else:
            self.h = np.zeros((2, 1, 64), dtype=np.float32)
            self.c = np.zeros((2, 1, 64), dtype=np.float32)

    def process(self, frame):
        x = (frame.astype(np.float32) / 32768.0)[None, :]
        if self.version == "v5":
            x = np.concatenate([self.context, x], axis=1)
            out, self.state = self.session.run(None, {"input": x, "state": self.state, "sr": np.array(SR, dtype=np.int64)})
            self.context = x[:, -64:]
        else:
            out, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c, "sr": np.array(SR, dtype=np.int64)})
        prob = float(out.reshape(-1)[0])
        return prob >= self.threshold, prob


# ---- the harness's own adapters ---------------------------------------------------------------------------------
def harness_registry():
    """The repository's vad_adapters registry; refuses a package of that name from anywhere else."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    registry = importlib.import_module("vad_adapters.adapter_registry")
    expected = REPO_ROOT / "vad_adapters" / "adapter_registry.py"
    if Path(registry.__file__).resolve() != expected:
        raise VADError(f"vad_adapters was imported from {registry.__file__}, not from this repository ({expected})")
    return registry


class HarnessVAD(VADAdapter):
    def __init__(self, name, registry_name, **kwargs):
        self.name = name
        self.adapter = harness_registry().get_adapter(registry_name, hardware_policy="cpu_only", **kwargs)
        self.frame_samples = int(self.adapter.frame_size_samples)
        self.count = 0

    def reset(self):
        self.adapter.reset()
        self.count = 0

    def process(self, frame):
        record = self.adapter.process_frame(frame, self.count * self.frame_samples, self.count)
        self.count += 1
        return bool(record.is_speech), None if record.score is None else float(record.score)
