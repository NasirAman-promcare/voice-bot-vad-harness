"""The existing harness VAD the owner named (WebRTC VAD, mode 2, 20 ms frames) behind the lab's adapter contract
(FR-0.7-04).

CAPABILITIES:
  CAP-HVAD-001: HarnessVADAdapter.model_block() gives family harness-vad, the harness registry name webrtc_vad_mode2, the webrtcvad-wheels version, no checksum (the harness code is identified by the run card's git commit) and the settings (mode 2, 320-sample frames, harness module, raw frame transitions, the harness's dropped-tail rule) [tests: test_FR_0_7_04_model_block_names_the_harness_vad]
  CAP-HVAD-002: open() imports the harness registry from this repository's vad_adapters/ (refusing a same-named package from anywhere else) and takes the adapter with get_adapter("webrtc_vad_mode2", frame_size_samples=320), which runs the harness's own conformance check; no harness file is copied or changed [tests: test_FR_0_7_04_wraps_named_harness_vad_without_modifying_harness, test_FR_0_7_04_process_before_open_is_an_error]
  CAP-HVAD-003: process_clip() and the streaming steps frame the clip as the harness does (whole 20 ms frames, a shorter tail dropped and counted) and turn the frame decisions into segments without smoothing: speech_start at the first speech frame's start, speech_end at the end of the run's last speech frame (a run reaching the last whole frame ends there); returns segments, speech_s, frames, speech_frames and dropped_tail_samples [tests: test_FR_0_7_04_segments_follow_frame_decisions, test_FR_0_7_04_emits_speech_start_and_speech_end, test_FR_0_7_04_silence_gives_no_segment, test_FR_0_7_04_streaming_equals_whole_clip]
INPUTS AND OUTPUTS: 16 kHz mono int16 samples in; `speech_start`/`speech_end` events (component vad) and result
  fields out; AdapterError or the harness's own exceptions on failure.
CONTRACTS: event-log v1; run-card v1 `model` block; the harness contract vad_adapters/adapter_contract.py (read only).
INVARIANTS:
  - The harness is imported, never modified; its decisions are used as they are (no smoothing, no hangover).
NOT IN SCOPE:
  - Scoring VAD decisions (a later phase); the other harness VADs (TEN VAD, FireRedVAD).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-04 created.
"""
import importlib
import importlib.metadata as md
import sys
from pathlib import Path

import numpy as np

from aqis_lab.adapters.base import SAMPLE_RATE_HZ, AdapterError, StreamingAdapter

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_NAME = "webrtc_vad_mode2"          # owner decision, docs/approvals/WP-0.7.md, question 1
MODE = 2
FRAME_SAMPLES = 320                         # 20 ms


def _harness_registry():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    registry = importlib.import_module("vad_adapters.adapter_registry")
    expected = REPO_ROOT / "vad_adapters" / "adapter_registry.py"
    if Path(registry.__file__).resolve() != expected:
        raise AdapterError("harness-vad-not-found", f"vad_adapters was imported from {registry.__file__}, not from "
                                                    f"this repository ({expected})")
    return registry


class HarnessVADAdapter(StreamingAdapter):
    name = "harness-vad"
    component = "vad"

    def __init__(self):
        self.harness_adapter = None

    def model_block(self):
        return {"family": "harness-vad", "name": REGISTRY_NAME, "version": f"webrtcvad-wheels {md.version('webrtcvad-wheels')}",
                "checksum": None,
                "settings": {"mode": MODE, "frame_size_samples": FRAME_SAMPLES, "registry_name": REGISTRY_NAME,
                             "harness_module": "vad_adapters.webrtc_vad_adapter",
                             "segmentation": "raw frame transitions (no smoothing)",
                             "tail": "dropped (harness chunk_audio_stream)"}}

    def describe(self):
        return f"harness {REGISTRY_NAME} from vad_adapters/ (webrtcvad-wheels {md.version('webrtcvad-wheels')})"

    def open(self):
        vad = _harness_registry().get_adapter(REGISTRY_NAME, frame_size_samples=FRAME_SAMPLES)
        if vad.adapter_id != REGISTRY_NAME or vad.frame_size_samples != FRAME_SAMPLES:
            raise AdapterError("harness-vad-mismatch", f"the harness returned {vad.adapter_id} with "
                                                       f"{vad.frame_size_samples}-sample frames")
        self.harness_adapter = vad

    def close(self):
        self.harness_adapter = None

    def start_clip(self, clip_id, sink):
        if self.harness_adapter is None:
            raise AdapterError("harness-vad-not-open", "the harness VAD adapter was used before open()")
        self.harness_adapter.reset()
        self._clip, self._frames, self._speech_frames, self._tail = clip_id, 0, 0, 0
        self._start, self._segments = None, []

    def _decide(self, frame, sink):
        offset = self._frames * FRAME_SAMPLES
        record = self.harness_adapter.process_frame(frame, sample_offset=offset, frame_index=self._frames)
        speech = bool(record.is_speech)
        if speech and self._start is None:
            self._start = offset
            sink.emit(self.component, "speech_start", self._clip, offset / SAMPLE_RATE_HZ, {})
        elif not speech and self._start is not None:
            self._close_segment(offset, sink)
        self._frames += 1
        self._speech_frames += speech

    def _close_segment(self, end, sink):
        sink.emit(self.component, "speech_end", self._clip, end / SAMPLE_RATE_HZ, {})
        self._segments.append([self._start / SAMPLE_RATE_HZ, end / SAMPLE_RATE_HZ])
        self._start = None

    def feed(self, frame, audio_end_s, sink):
        frame = np.asarray(frame, dtype=np.int16)
        if len(frame) == FRAME_SAMPLES:
            self._decide(frame, sink)
        else:
            self._tail += len(frame)        # the harness's rule: a part-frame is dropped (chunk_audio_stream)

    def finish_clip(self, audio_end_s, sink):
        if self._start is not None:
            self._close_segment(self._frames * FRAME_SAMPLES, sink)
        fields = {"segments": self._segments, "speech_s": sum(e - b for b, e in self._segments),
                  "frames": self._frames, "speech_frames": self._speech_frames, "dropped_tail_samples": self._tail}
        return fields

    def process_clip(self, clip_id, samples, sink):
        self.start_clip(clip_id, sink)
        chunk = importlib.import_module("vad_adapters.adapter_contract").chunk_audio_stream
        samples = np.asarray(samples, dtype=np.int16)
        for piece in chunk(samples, FRAME_SAMPLES, SAMPLE_RATE_HZ):
            self._decide(piece.samples, sink)
        self._tail = len(samples) - self._frames * FRAME_SAMPLES
        return self.finish_clip(len(samples) / SAMPLE_RATE_HZ, sink)
