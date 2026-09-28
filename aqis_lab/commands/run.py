"""The `run` command: run a task over a pack in resumable shards (copy then compute, completion markers).

CAPABILITIES:
  CAP-RUN-009: `python -m aqis_lab run --task clip-stats --pack DIR --out DIR --seed N [--work-dir DIR] [--shard-minutes M] [--shard-clips N] [--max-shards N] [--from-scratch] [--drive-mount DIR] [--notes TEXT]` prints the runner log; exit 0 complete or stopped by --max-shards, 1 a clip failed, 2 usage or input error [tests: test_FR_0_5_05_clip_failure_stops_run_without_marker, test_FR_0_5_05_max_shards_stops_cleanly, test_FR_0_5_04_changed_extracted_clip_stops_the_run, test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing]
INPUTS AND OUTPUTS: command-line arguments in; the run folder, the log on stdout, errors on stderr, exit 0, 1 or 2.
CONTRACTS: run folder layout in docs/runner/RUNNER.md.
INVARIANTS:
  - --seed is required: the run card needs one and the lab never hides a missing input behind a default.
NOT IN SCOPE:
  - Running itself (aqis_lab/runner/run.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
"""
import argparse
import sys
from pathlib import Path

from aqis_lab.runner.plan import DEFAULT_SHARD_MINUTES


def build_parser():
    from aqis_lab.runner.run import DEFAULT_WORK_DIR
    from aqis_lab.runner.tasks import TASKS
    parser = argparse.ArgumentParser(prog="python -m aqis_lab run",
                                     description="Run a task over a pack in resumable shards (docs/runner/RUNNER.md).")
    parser.add_argument("--task", required=True, choices=sorted(TASKS), help="task to run on every clip")
    parser.add_argument("--pack", required=True, help="pack folder (in the repository or on Drive)")
    parser.add_argument("--out", required=True, help="run folder; the same folder resumes the run")
    parser.add_argument("--seed", required=True, type=int, help="seed recorded in the run card (integer >= 0)")
    parser.add_argument("--work-dir", default=None,
                        help=f"local folder the pack is copied to and extracted in (default {DEFAULT_WORK_DIR})")
    parser.add_argument("--shard-minutes", type=float, default=DEFAULT_SHARD_MINUTES,
                        help="most expected minutes of work per shard (default 30)")
    parser.add_argument("--shard-clips", type=int, default=None, help="most clips per shard (default no limit)")
    parser.add_argument("--max-shards", type=int, default=None,
                        help="stop cleanly after computing this many shards in this session")
    parser.add_argument("--from-scratch", action="store_true",
                        help="move an existing run folder aside (renamed, never deleted) and start again")
    parser.add_argument("--drive-mount", default=None,
                        help="Google Drive mount; on Colab it keeps the unit log's last-seen time current")
    parser.add_argument("--notes", default="", help="free text for the run card")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.runner.run import DEFAULT_WORK_DIR, RunFailure, RunInputError, RunOptions, run
    options = RunOptions(task=ns.task, pack=Path(ns.pack), out=Path(ns.out), seed=ns.seed,
                         work_dir=Path(ns.work_dir) if ns.work_dir else DEFAULT_WORK_DIR,
                         shard_minutes=ns.shard_minutes, shard_clips=ns.shard_clips, max_shards=ns.max_shards,
                         from_scratch=ns.from_scratch, drive_mount=Path(ns.drive_mount) if ns.drive_mount else None,
                         notes=ns.notes)
    try:
        outcome = run(options)
    except RunInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RunFailure as exc:
        print(f"ERROR: the run stopped: {exc}", file=sys.stderr)
        return 1
    print(f"{outcome.status}: {outcome.computed} shard(s) computed, {outcome.skipped} skipped, "
          f"{outcome.remaining} remaining")
    return 0
