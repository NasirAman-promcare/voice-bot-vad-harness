"""Vosk speech recognition on CPU (vosk-model-small-en-us-0.15): the lab's first live-STT adapter (FR-0.7-02).

CAPABILITIES:
  CAP-VOSK-001: VoskAdapter.model_block() gives family vosk, the pinned model name, its version, the model archive's SHA-256 as checksum and the settings the run uses (16 kHz, 20 ms feed, word times, library version, OpenBLAS kernel Prescott and 1 thread, owner decision question 6; the C library rand() seed set before every clip) [tests: test_FR_0_7_02_model_block_records_checksum_and_settings]
  CAP-VOSK-002: open() loads libvosk with OPENBLAS_CORETYPE and OPENBLAS_NUM_THREADS set only for the load (the process environment is restored), reads the library's active kernel and thread count back (x86_64: it must equal the pin; aarch64: a fixed build without dispatch), refuses a Vosk library already loaded with another kernel, then fetches and verifies the model (config/aqis_lab/models.yaml) and loads it; a library or model failure raises [tests: test_FR_0_7_02_openblas_kernel_pinned_and_verified, test_FR_0_7_02_refuses_when_vosk_already_loaded_with_other_kernel, test_FR_0_7_01_vosk_unusable_model_emits_error_event_and_raises, test_FR_0_7_02_changed_model_file_stops_vosk_open, test_FR_0_7_02_process_before_open_is_an_error]
  CAP-VOSK-003: process_clip() and the streaming steps (start_clip, feed, finish_clip) feed 20 ms frames (the last part-frame as it is), emit a `partial` event whenever the partial text changes and a `final` event (with word times) for every Vosk result and for the closing result, and return text, text_sha256, finals, partials, words, events and audio_s; the clip text is the final texts joined by single spaces, empty ones left out; every clip starts with the C library's rand() reseeded (Kaldi draws its feature dither from it), so a clip's result does not depend on the clips computed before it in the process [tests: test_FR_0_7_02_emits_partial_and_final_events_with_word_times, test_FR_0_7_02_same_input_gives_identical_transcript, test_FR_0_7_02_clip_result_independent_of_earlier_clips]
INPUTS AND OUTPUTS: 16 kHz mono int16 samples in; event-log v1 events (component live_stt) and result fields out;
  AdapterError (vosk-library-loaded, vosk-not-open, model-checksum, model-download) on failure.
CONTRACTS: event-log v1; run-card v1 `model` block; config/aqis_lab/models.yaml.
INVARIANTS:
  - The same samples, model, kernel and feed size give the same events and text (measured, PLAN.md finding 5), in any
    process and after any earlier clips (the dither generator is reseeded per clip).
  - The model is used only after its files match their pins.
NOT IN SCOPE:
  - Pacing frames in real time (aqis_lab/realspeed.py); running over a pack (aqis_lab/runner/).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-02 created.
  2026-09-30 WP-0.7 FR-0.7-02: start_clip reseeds the C library's rand() (C_RAND_SEED), and the model block records it;
    found by the DEBT-013 measurement (test_FR_0_7_02_clip_result_independent_of_earlier_clips).
"""
import ctypes
import hashlib
import importlib
import importlib.metadata as md
import json
import os
import sys
from pathlib import Path

import numpy as np

from aqis_lab.adapters import model_cache
from aqis_lab.adapters.base import SAMPLE_RATE_HZ, AdapterError, StreamingAdapter

MODEL_NAME = "vosk-model-small-en-us-0.15"
FEED_SAMPLES = 320                         # 20 ms at 16 kHz, in batch and in real-speed mode
OPENBLAS_CORETYPE = "Prescott"             # owner decision, docs/approvals/WP-0.7.md, question 6 (a)
OPENBLAS_NUM_THREADS = 1
LOG_LEVEL = -1
# Kaldi dithers the features (the model's mfcc.conf keeps the default dither 1.0) with noise drawn from the C library's
# rand(), one generator for the whole process. It is reseeded with this value at the start of every clip, so a clip's
# result does not depend on what the process computed before it. glibc's rand() starts from seed 1, so every clip is
# computed as the first clip of a fresh process would be.
C_RAND_SEED = 1
# OpenBLAS kernels that libvosk's x86_64 build may dispatch to (its gotoblas_<NAME> tables).
X86_KERNELS = ("PRESCOTT", "CORE2", "PENRYN", "DUNNINGTON", "NEHALEM", "SANDYBRIDGE", "HASWELL", "SKYLAKEX",
               "COOPERLAKE", "SAPPHIRERAPIDS", "ATOM", "ATHLON", "OPTERON", "OPTERON_SSE3", "BARCELONA", "BOBCAT",
               "BULLDOZER", "PILEDRIVER", "STEAMROLLER", "EXCAVATOR", "ZEN", "KATMAI", "COPPERMINE", "NORTHWOOD",
               "BANIAS", "NANO")
FIXED_BUILD = "fixed-build"


def active_kernel():
    """The OpenBLAS kernel libvosk runs with: a gotoblas table name, or 'fixed-build' when it has no dispatch."""
    import vosk
    lib = ctypes.CDLL(os.path.join(os.path.dirname(vosk.__file__), "libvosk.so"))
    try:
        current = ctypes.c_void_p.in_dll(lib, "gotoblas").value
    except ValueError:
        return FIXED_BUILD
    for name in X86_KERNELS:
        try:
            if ctypes.addressof(ctypes.c_byte.in_dll(lib, f"gotoblas_{name}")) == current:
                return name
        except ValueError:
            continue
    raise AdapterError("vosk-kernel-unknown", "libvosk's active OpenBLAS kernel is none of its known tables")


def active_threads():
    """The number of threads libvosk's OpenBLAS uses."""
    import vosk
    lib = ctypes.CDLL(os.path.join(os.path.dirname(vosk.__file__), "libvosk.so"))
    return int(lib.openblas_get_num_threads())


def _seed_c_rand():
    """Reseed the C library's rand() (process-wide), from which Kaldi's feature dither draws."""
    ctypes.CDLL(None).srand(ctypes.c_uint(C_RAND_SEED))


def _load_library():
    """Import vosk with the pinned OpenBLAS settings and return (module, active kernel).

    libvosk reads OPENBLAS_CORETYPE and OPENBLAS_NUM_THREADS once, when it loads; they are set only around the import
    and the previous values are restored, so child processes of this process are not affected."""
    if "vosk" not in sys.modules:
        saved = {k: os.environ.get(k) for k in ("OPENBLAS_CORETYPE", "OPENBLAS_NUM_THREADS")}
        os.environ["OPENBLAS_CORETYPE"] = OPENBLAS_CORETYPE
        os.environ["OPENBLAS_NUM_THREADS"] = str(OPENBLAS_NUM_THREADS)
        try:
            importlib.import_module("vosk")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    vosk = importlib.import_module("vosk")
    kernel = active_kernel()
    if kernel != FIXED_BUILD and kernel != OPENBLAS_CORETYPE.upper():
        raise AdapterError("vosk-library-loaded",
                           f"the Vosk library in this process runs OpenBLAS kernel {kernel}, not the pinned "
                           f"{OPENBLAS_CORETYPE} (it was loaded before the adapter set OPENBLAS_CORETYPE); start a new "
                           f"process")
    threads = active_threads()
    if threads != OPENBLAS_NUM_THREADS:
        raise AdapterError("vosk-library-loaded", f"the Vosk library in this process uses {threads} OpenBLAS threads, "
                                                  f"not the pinned {OPENBLAS_NUM_THREADS}; start a new process")
    vosk.SetLogLevel(LOG_LEVEL)
    return vosk, kernel


class VoskAdapter(StreamingAdapter):
    name = "vosk"
    component = "live_stt"
    uses_model_cache = True

    def __init__(self, pin=None, cache_dir=model_cache.DEFAULT_CACHE, system=None):
        self.pin = pin if pin is not None else model_cache.load_pins()[MODEL_NAME]
        self.cache_dir = Path(cache_dir)
        self.system = system
        self.kernel = None
        self._vosk = self._model = self._rec = None

    def model_block(self):
        return {"family": "vosk", "name": self.pin.name, "version": self.pin.name.rsplit("-", 1)[-1],
                "checksum": self.pin.sha256,
                "settings": {"sample_rate_hz": SAMPLE_RATE_HZ, "feed_samples": FEED_SAMPLES, "words": True,
                             "partial_events": "when the partial text changes",
                             "library": f"vosk {md.version('vosk')}", "openblas_coretype": OPENBLAS_CORETYPE,
                             "openblas_num_threads": OPENBLAS_NUM_THREADS, "log_level": LOG_LEVEL,
                             "c_rand_seed_per_clip": C_RAND_SEED}}

    def describe(self):
        return f"vosk {md.version('vosk')}, model {self.pin.name} ({self.pin.sha256[:12]}), OpenBLAS kernel {self.kernel}"

    def open(self):
        self._vosk, self.kernel = _load_library()
        path = model_cache.fetch(self.pin, self.cache_dir, self.system)
        self._model = self._vosk.Model(str(path))

    def close(self):
        self._rec = self._model = None

    # streaming steps
    def start_clip(self, clip_id, sink):
        if self._model is None:
            raise AdapterError("vosk-not-open", "the Vosk adapter was used before open()")
        _seed_c_rand()
        rec = self._vosk.KaldiRecognizer(self._model, SAMPLE_RATE_HZ)
        rec.SetWords(True)
        self._rec, self._clip = rec, clip_id
        self._partial, self._texts, self._counts = "", [], {"finals": 0, "partials": 0, "words": 0, "events": 0}

    def _final(self, result, audio_s, sink):
        text = result.get("text", "")
        payload = {"text": text}
        words = [{"word": w["word"], "start_s": w["start"], "end_s": w["end"]} for w in result.get("result", [])]
        if words:
            payload["words"] = words
        sink.emit(self.component, "final", self._clip, audio_s, payload)
        if text:
            self._texts.append(text)
        self._partial = ""
        self._counts["finals"] += 1
        self._counts["words"] += len(words)
        self._counts["events"] += 1

    def feed(self, frame, audio_end_s, sink):
        data = np.ascontiguousarray(frame, dtype="<i2").tobytes()
        if self._rec.AcceptWaveform(data):
            self._final(json.loads(self._rec.Result()), audio_end_s, sink)
            return
        partial = json.loads(self._rec.PartialResult()).get("partial", "")
        if partial and partial != self._partial:
            sink.emit(self.component, "partial", self._clip, audio_end_s, {"text": partial})
            self._partial = partial
            self._counts["partials"] += 1
            self._counts["events"] += 1

    def finish_clip(self, audio_end_s, sink):
        self._final(json.loads(self._rec.FinalResult()), audio_end_s, sink)
        text = " ".join(self._texts)
        fields = {"text": text, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), **self._counts,
                  "audio_s": audio_end_s}
        self._rec = None
        return fields

    def process_clip(self, clip_id, samples, sink):
        self.start_clip(clip_id, sink)
        n = len(samples)
        for start in range(0, n, FEED_SAMPLES):
            end = min(start + FEED_SAMPLES, n)
            self.feed(samples[start:end], end / SAMPLE_RATE_HZ, sink)
        return self.finish_clip(n / SAMPLE_RATE_HZ, sink)
