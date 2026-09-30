"""NVIDIA Parakeet Unified (nvidia/parakeet-unified-en-0.6b) in offline mode on a GPU through NeMo (FR-0.7-03), and
its per-clip GPU compute delay (FR-0.7-06).

CAPABILITIES:
  CAP-PARA-001: preflight() refuses to run without a GPU (aqis_lab.platform) or without NeMo installed (the GPU extras requirements/aqis_lab/phase0-gpu.txt), with an AdapterPlatformError that says what is missing; the adapter is never skipped or replaced; open() runs preflight, then refuses when torch sees no CUDA device, then fetches the pinned .nemo file (config/aqis_lab/models.yaml, size and SHA-256) and restores it on cuda; torch and NeMo are imported only here [tests: test_FR_0_7_03_refuses_without_gpu, test_FR_0_7_03_refuses_without_nemo, test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter, test_FR_0_7_03_parakeet_transcribes_on_gpu]
  CAP-PARA-002: model_block() gives family nemo, the Hugging Face model name, the pinned revision as version, the file's SHA-256 as checksum and the settings (offline mode, the model's default greedy RNN-T decoding, batch 1, float32, cuda, in-memory float32 input, the NeMo and torch versions pinned in phase0-gpu.txt) [tests: test_FR_0_7_03_parakeet_model_block_records_pinned_versions]
  CAP-PARA-003: process_clip() transcribes one clip from in-memory float32 samples (int16 / 32768) and emits one `final` event (component heavy_stt) at the clip's end; process_clip_timed() also measures the processing time on the monotonic clock around the transcription, with CUDA synchronised before the start and after the end, and returns processing_ms, rtf and the GPU type [tests: test_FR_0_7_06_compute_delay_rows_hold_gpu_and_per_clip_time, test_FR_0_7_06_audio_is_scaled_to_float_range, test_FR_0_7_06_gpu_compute_delay_on_colab_t4]
INPUTS AND OUTPUTS: 16 kHz mono int16 samples in; `final` events and result fields out; AdapterPlatformError
  (parakeet-no-gpu, parakeet-no-nemo, parakeet-no-cuda) or model-cache errors on failure.
CONTRACTS: event-log v1; run-card v1 `model` block; config/aqis_lab/models.yaml; requirements/aqis_lab/phase0-gpu.txt.
INVARIANTS:
  - Without a usable GPU the adapter raises; it never falls back to the CPU.
  - The model file is used only after its size and SHA-256 match the pin.
NOT IN SCOPE:
  - Streaming (buffered) inference; the warm-up choice of the compute-delay run (aqis_lab/runner/tasks.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-03 created.
"""
import hashlib
import importlib
import importlib.util
import time

import numpy as np

from aqis_lab import locks
from aqis_lab import platform as lp
from aqis_lab.adapters import model_cache
from aqis_lab.adapters.base import SAMPLE_RATE_HZ, Adapter, AdapterPlatformError

MODEL_KEY = "parakeet-unified-en-0.6b"
MODEL_NAME = "nvidia/parakeet-unified-en-0.6b"
GPU_EXTRAS = "requirements/aqis_lab/phase0-gpu.txt"


class ParakeetUnifiedAdapter(Adapter):
    name = "parakeet"
    component = "heavy_stt"
    uses_model_cache = True

    def __init__(self, pin=None, cache_dir=model_cache.DEFAULT_CACHE, system=None):
        self.pin = pin if pin is not None else model_cache.load_pins()[MODEL_KEY]
        self.cache_dir, self.system = cache_dir, system
        self.gpu = None
        self.load_s = None
        self.clock = time.monotonic_ns
        self._torch = self._model = None

    def model_block(self):
        return {"family": "nemo", "name": MODEL_NAME, "version": self.pin.revision, "checksum": self.pin.sha256,
                "settings": {"mode": "offline", "decoding": "the model's default (greedy RNN-T)", "batch_size": 1,
                             "dtype": "float32", "device": "cuda", "input": "in-memory float32 samples (int16 / 32768)",
                             "nemo": locks.pinned_version(GPU_EXTRAS, "nemo-toolkit"),
                             "torch": locks.pinned_version(GPU_EXTRAS, "torch")}}

    def describe(self):
        return f"NeMo {MODEL_NAME} ({self.pin.sha256[:12]}) on {self.gpu}, loaded in {self.load_s:.1f} s"

    def preflight(self):
        """AdapterPlatformError unless this machine has a GPU and the GPU extras are installed (nothing is loaded)."""
        gpu = lp.gpu_type(self.system or lp.SystemView.real())
        if gpu is None:
            raise AdapterPlatformError(
                "parakeet-no-gpu", "Parakeet Unified runs only on a CUDA GPU and this machine has no GPU "
                                   "(aqis_lab.platform found none). It is never skipped or replaced: run it on a GPU "
                                   "target (the Colab T4 runtime; runbook in docs/colab/)")
        if importlib.util.find_spec("nemo") is None or importlib.util.find_spec("torch") is None:
            raise AdapterPlatformError(
                "parakeet-no-nemo", f"NeMo and torch are not installed on this {gpu} machine: install the GPU extras "
                                    f"{GPU_EXTRAS} with `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`")
        self.gpu = gpu
        return gpu

    def open(self):
        self.preflight()
        start = self.clock()
        torch = importlib.import_module("torch")
        if not torch.cuda.is_available():
            raise AdapterPlatformError("parakeet-no-cuda", f"torch {torch.__version__} (CUDA {torch.version.cuda}) "
                                                           f"cannot use the {self.gpu}: torch.cuda.is_available() "
                                                           f"is false")
        nemo_asr = importlib.import_module("nemo.collections.asr")
        path = model_cache.fetch(self.pin, self.cache_dir, self.system)
        model = nemo_asr.models.ASRModel.restore_from(str(path), map_location="cuda")
        model.eval()
        self._torch, self._model = torch, model
        self.load_s = (self.clock() - start) / 1e9

    def close(self):
        self._model = None

    def _synchronize(self):
        self._torch.cuda.synchronize()

    def _run(self, audio):
        with self._torch.inference_mode():
            hypothesis = self._model.transcribe([audio], batch_size=1, verbose=False)[0]
        return hypothesis.text if hasattr(hypothesis, "text") else str(hypothesis)

    @staticmethod
    def _audio(samples):
        return np.asarray(samples, dtype=np.int16).astype(np.float32) / 32768.0

    def _result(self, clip_id, text, samples, sink):
        audio_s = len(samples) / SAMPLE_RATE_HZ
        sink.emit(self.component, "final", clip_id, audio_s, {"text": text})
        return {"text": text, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "audio_s": audio_s}

    def transcribe(self, samples):
        """The transcript of one clip (no event, no timing): used for the untimed warm-up."""
        return self._run(self._audio(samples))

    def process_clip(self, clip_id, samples, sink):
        return self._result(clip_id, self._run(self._audio(samples)), samples, sink)

    def process_clip_timed(self, clip_id, samples, sink):
        audio = self._audio(samples)
        self._synchronize()
        start = self.clock()
        text = self._run(audio)
        self._synchronize()
        elapsed = self.clock() - start
        fields = self._result(clip_id, text, samples, sink)
        return {**fields, "processing_ms": elapsed / 1e6, "rtf": (elapsed / 1e9) / fields["audio_s"],
                "gpu": self.gpu}
