"""Runner tasks: the work done for each clip: clip-stats (WP-0.5) and the model adapters' tasks (WP-0.7).

CAPABILITIES:
  CAP-RUN-003: TASKS maps a task name to a Task with its name, version, run card model block and measured expected processing seconds per audio second; clip-stats reads each clip as 16 kHz mono 16-bit PCM and returns integers only (samples, rate, channels, peak_abs, sum_samples, sum_squares), so its rows are byte-identical on every machine [tests: test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids, test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work]
  CAP-RUN-010: AdapterTask runs one adapter per clip with events: vosk-batch (batch), vosk-realspeed (realspeed_cpu, through the real-speed feeder), harness-vad (batch), parakeet-offline (batch) and parakeet-compute-delay (gpu_compute_delay, one untimed warm-up transcription before the first timed clip, owner decision question 7); each declares its run-card mode, normaliser (text tasks: the main normaliser; the VAD: none), model block and whether its rows repeat byte for byte; preflight refuses a machine the adapter cannot use before anything is written; each clip is framed by runner clip_started and clip_finished events and read as 16 kHz mono int16 inside the adapter's failure guard, so any failure leaves one error event and raises [tests: test_FR_0_7_07_run_card_mode_normaliser_and_model_per_task, test_FR_0_7_01_events_validate_against_event_log_v1, test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event, test_FR_0_7_03_runner_refuses_parakeet_without_gpu_before_writing, test_FR_0_7_06_warm_up_not_timed, test_FR_0_7_01_vosk_run_events_validate_against_event_log_v1]
INPUTS AND OUTPUTS: a manifest clip and its bytes in; a dict of result fields out; AudioFormatError on a bad clip.
CONTRACTS: run-card v1 `model` block; result row format in docs/runner/RUNNER.md.
INVARIANTS:
  - A deterministic task's output depends only on the clip bytes (no clock, randomness or machine facts); a timing
    task (vosk-realspeed, parakeet-compute-delay) also records the times it measured, and says so
    (deterministic = False).
  - Adapter modules are imported only when their task is used (importing this module loads no model library).
NOT IN SCOPE:
  - The adapters themselves (aqis_lab/adapters/); the real-speed pacing (aqis_lab/realspeed.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
  2026-09-30 WP-0.7 FR-0.7-07: ClipStats declares mode batch, deterministic, no events (behaviour unchanged);
    AdapterTask and the five adapter tasks added to TASKS.
"""
import importlib

import numpy as np

from aqis_lab.adapters.base import SAMPLE_RATE_HZ, guarded
from aqis_lab.packs.audio import read_wav
from aqis_lab.scoring.normalise import normaliser_identity


class ClipStats:
    """Integer statistics of each clip: a real, deterministic pass over every sample of the pack."""
    name = "clip-stats"
    version = "1.0"
    # Expected processing seconds per second of audio, measured on the cloud VM with the command recorded in
    # docs/runner/RUNNER.md ("Expected work") and docs/progress/WP-0.5/EVIDENCE.md; used only to size shards.
    seconds_per_audio_second = 0.000169
    mode = "batch"
    deterministic = True
    emits_events = False

    def normaliser_block(self):
        return None

    def model_block(self):
        return {"family": "aqis-lab-task", "name": self.name, "version": self.version, "checksum": None,
                "settings": {}}

    def run_clip(self, clip, data):
        info, samples = read_wav(data, where=f"clip {clip['clip_id']}")
        wide = samples.astype(np.int64)
        return {"samples": int(wide.size), "sample_rate_hz": info.sample_rate_hz, "channels": info.channels,
                "peak_abs": int(np.abs(wide).max()) if wide.size else 0, "sum_samples": int(wide.sum()),
                "sum_squares": int(np.dot(wide, wide))}


class AdapterTask:
    """One adapter run over each clip, writing events. `kind` is batch, realspeed or timed (GPU compute delay)."""
    emits_events = True

    def __init__(self, name, version, mode, kind, adapter, deterministic, text, seconds_per_audio_second):
        self.name, self.version, self.mode, self.kind = name, version, mode, kind
        self.adapter_ref, self.deterministic, self.text = adapter, deterministic, text
        # Expected processing seconds per second of audio; used only to size shards (docs/runner/RUNNER.md).
        self.seconds_per_audio_second = seconds_per_audio_second
        self.adapter = self.feeder = None
        self.warmed = False

    def configure(self, model_cache, system=None, cores_config=None):
        """Build the adapter for this run (nothing is loaded yet)."""
        module_name, class_name = self.adapter_ref.split(":")
        cls = getattr(importlib.import_module(module_name), class_name)
        self.adapter = cls(cache_dir=model_cache, system=system) if cls.uses_model_cache else cls()
        self.system, self.cores_config = system, cores_config
        self.feeder = None
        self.warmed = False
        return self

    def model_block(self):
        return self.adapter.model_block()

    def normaliser_block(self):
        return normaliser_identity() if self.text else None

    def preflight(self):
        return self.adapter.preflight()

    def open(self, sink):
        """Load the adapter (inside the failure guard); returns a one-line description for the runner log."""
        guarded(self.adapter, sink, None, "open", self.adapter.open)
        if self.kind == "realspeed":
            from aqis_lab.realspeed import RealSpeedFeeder
            self.feeder = RealSpeedFeeder(self.adapter, self.system, self.cores_config)
        return self.adapter.describe()

    def close(self):
        if self.adapter is not None:
            self.adapter.close()

    def _clip(self, clip, data, sink):
        _, samples = read_wav(data, where=f"clip {clip['clip_id']}")
        if self.kind == "realspeed":
            return self.feeder.run_clip(clip["clip_id"], samples, sink), len(samples)
        if self.kind == "timed":
            if not self.warmed:
                self.adapter.transcribe(samples)          # untimed warm-up on the first clip (question 7)
                self.warmed = True
            return self.adapter.process_clip_timed(clip["clip_id"], samples, sink), len(samples)
        return self.adapter.process_clip(clip["clip_id"], samples, sink), len(samples)

    def run_clip(self, clip, data, sink):
        clip_id = clip["clip_id"]
        sink.emit("runner", "clip_started", clip_id, 0.0, {})
        fields, n = guarded(self.adapter, sink, clip_id, "clip", self._clip, clip, data, sink)
        sink.emit("runner", "clip_finished", clip_id, n / SAMPLE_RATE_HZ, {})
        return fields


# Measured on the cloud VM with the method in docs/runner/RUNNER.md ("Expected work"): Vosk batch 67.9 to 74.6 s and
# the harness VAD 0.212 s for the 390.9 s smoke pack. Real-speed runs take real time by construction. Parakeet's T4
# figure is measured by the compute-delay run itself (OC-0.7-01); 1.0 is an upper bound used only for shard sizes.
TASKS = {
    ClipStats.name: ClipStats(),
    "vosk-batch": AdapterTask("vosk-batch", "1.0", "batch", "batch", "aqis_lab.adapters.vosk_stt:VoskAdapter",
                              deterministic=True, text=True, seconds_per_audio_second=0.19),
    "vosk-realspeed": AdapterTask("vosk-realspeed", "1.0", "realspeed_cpu", "realspeed",
                                  "aqis_lab.adapters.vosk_stt:VoskAdapter", deterministic=False, text=True,
                                  seconds_per_audio_second=1.0),
    "harness-vad": AdapterTask("harness-vad", "1.0", "batch", "batch", "aqis_lab.adapters.harness_vad:HarnessVADAdapter",
                               deterministic=True, text=False, seconds_per_audio_second=0.000542),
    "parakeet-offline": AdapterTask("parakeet-offline", "1.0", "batch", "batch",
                                    "aqis_lab.adapters.parakeet_unified:ParakeetUnifiedAdapter", deterministic=False,
                                    text=True, seconds_per_audio_second=1.0),
    "parakeet-compute-delay": AdapterTask("parakeet-compute-delay", "1.0", "gpu_compute_delay", "timed",
                                          "aqis_lab.adapters.parakeet_unified:ParakeetUnifiedAdapter",
                                          deterministic=False, text=True, seconds_per_audio_second=1.0),
}
