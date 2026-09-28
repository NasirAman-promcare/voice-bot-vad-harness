"""Runner tasks: the work done for each clip. WP-0.5 has one built-in task, clip-stats (owner decision, question 2).

CAPABILITIES:
  CAP-RUN-003: TASKS maps a task name to a Task with its name, version, run card model block and measured expected processing seconds per audio second; clip-stats reads each clip as 16 kHz mono 16-bit PCM and returns integers only (samples, rate, channels, peak_abs, sum_samples, sum_squares), so its rows are byte-identical on every machine [tests: test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids, test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work]
INPUTS AND OUTPUTS: a manifest clip and its bytes in; a dict of result fields out; AudioFormatError on a bad clip.
CONTRACTS: run-card v1 `model` block; result row format in docs/runner/RUNNER.md.
INVARIANTS:
  - A task's output depends only on the clip bytes (no clock, randomness or machine facts).
NOT IN SCOPE:
  - Model adapters (WP-0.7 adds them to TASKS).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
"""
import numpy as np

from aqis_lab.packs.audio import read_wav


class ClipStats:
    """Integer statistics of each clip: a real, deterministic pass over every sample of the pack."""
    name = "clip-stats"
    version = "1.0"
    # Expected processing seconds per second of audio, measured on the cloud VM with the command recorded in
    # docs/runner/RUNNER.md ("Expected work") and docs/progress/WP-0.5/EVIDENCE.md; used only to size shards.
    seconds_per_audio_second = 0.000169

    def model_block(self):
        return {"family": "aqis-lab-task", "name": self.name, "version": self.version, "checksum": None,
                "settings": {}}

    def run_clip(self, clip, data):
        info, samples = read_wav(data, where=f"clip {clip['clip_id']}")
        wide = samples.astype(np.int64)
        return {"samples": int(wide.size), "sample_rate_hz": info.sample_rate_hz, "channels": info.channels,
                "peak_abs": int(np.abs(wide).max()) if wide.size else 0, "sum_samples": int(wide.sum()),
                "sum_squares": int(np.dot(wide, wide))}


TASKS = {ClipStats.name: ClipStats()}
