"""The `phase0` command: `phase0 smoke --target cloud|colab|oracle` runs the phase 0 smoke run (FR-0.7-07).

CAPABILITIES:
  CAP-SMOKE-005: `python -m aqis_lab phase0 smoke --target {cloud,colab,oracle} [--out DIR] [--store DIR] [--model-cache DIR] [--work-dir DIR] [--bundle-dir DIR] [--drive-mount DIR] [--from-scratch]` runs aqis_lab.smoke.run_smoke and prints the runner logs and a summary; exit 0 complete, 1 a run, score or check failed, 2 usage, configuration or machine problem (ERROR: on stderr) [tests: test_FR_0_7_07_target_must_match_platform, test_FR_0_7_07_cli_parses_every_option, test_FR_0_7_07_failed_run_exits_1_with_error, test_FR_0_7_07_from_scratch_supersedes_the_old_runs]
INPUTS AND OUTPUTS: command-line arguments in; the smoke's outputs, a summary on stdout, errors on stderr and an exit
  code out.
CONTRACTS: docs/runs/PHASE0_SMOKE.md.
INVARIANTS:
  - The target is required; the lab never guesses which machine it runs on.
NOT IN SCOPE:
  - The smoke itself (aqis_lab/smoke.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-07 created.
  2026-10-02 WP-0.7 round 2 F04: --from-scratch, passed to run_smoke; F03: header lists the exit-1 test
    (test_FR_0_7_07_failed_run_exits_1_with_error).
"""
import argparse
import sys
from pathlib import Path


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab phase0", description="Phase 0 runs (docs/runs/PHASE0_SMOKE.md).")
    sub = parser.add_subparsers(dest="action", required=True)
    smoke = sub.add_parser("smoke", help="run the first adapters over the smoke pack and write a result bundle")
    smoke.add_argument("--target", required=True, choices=["cloud", "colab", "oracle"],
                       help="the machine this is: cloud VM, Colab (T4) or Oracle")
    smoke.add_argument("--out", default=None, help="run folders and the bundle archive (default data/raw/aqis_lab/smoke/<target>; "
                                                   "on Colab a folder under MyDrive/AQIS_LAB)")
    smoke.add_argument("--store", default=None, help="results store on local disk (default data/raw/aqis_lab/results, the lab's results store)")
    smoke.add_argument("--model-cache", default=None, help="local model cache (default data/raw/aqis_lab/models)")
    smoke.add_argument("--work-dir", default=None, help="local folder the pack is staged in (the runner's default)")
    smoke.add_argument("--bundle-dir", default=None, help="local folder for the bundle (default data/raw/aqis_lab/smoke-bundles)")
    smoke.add_argument("--drive-mount", default=None, help="Google Drive mount on Colab (keeps the unit log current)")
    smoke.add_argument("--from-scratch", action="store_true",
                       help="start every run again: a run folder under --out that holds another run (for example "
                            "from an earlier commit) is renamed <folder>.superseded-<UTC>, never deleted")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.smoke import SmokeError, run_smoke
    path = lambda value: Path(value) if value is not None else None
    try:
        run_smoke(ns.target, out=path(ns.out), store=path(ns.store), model_cache=path(ns.model_cache),
                  work_dir=path(ns.work_dir), bundle_dir=path(ns.bundle_dir), drive_mount=path(ns.drive_mount),
                  from_scratch=ns.from_scratch)
    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    return 0
