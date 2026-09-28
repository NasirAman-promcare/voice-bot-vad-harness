"""The `unitlog` command: start and end a Colab session's entry in AQIS_LAB/logs/units.csv.

CAPABILITIES:
  CAP-UNIT-003: `python -m aqis_lab unitlog start|end --drive-mount DIR [--rates FILE]` records the session start, or appends the session's row with its estimated compute units; outside Colab it refuses (exit 2) and writes nothing; exit 0 done, 2 on any error [tests: test_FR_0_5_07_refuses_outside_colab, test_FR_0_5_07_colab_session_recorded]
INPUTS AND OUTPUTS: command-line arguments in; the unit log on Drive, one line on stdout, errors on stderr.
CONTRACTS: the unit log format documented in the Colab runbook (docs/colab/).
INVARIANTS:
  - Platform and GPU type come from aqis_lab.platform.
NOT IN SCOPE:
  - The estimate itself (aqis_lab/unitlog.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-07 created.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RATES = REPO_ROOT / "config" / "aqis_lab" / "colab_rates.yaml"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab unitlog",
                                     description="Colab compute-unit log in MyDrive/AQIS_LAB/logs/units.csv.")
    actions = parser.add_subparsers(dest="action", required=True, metavar="action")
    for name, text in (("start", "record the start of this Colab session"),
                       ("end", "append this session's row with its estimated units")):
        sub = actions.add_parser(name, help=text)
        sub.add_argument("--drive-mount", required=True, help="folder Google Drive is mounted at")
        sub.add_argument("--rates", default=str(DEFAULT_RATES), help=f"rate table (default {DEFAULT_RATES})")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab import platform as lp
    from aqis_lab import unitlog
    from aqis_lab.drive import DriveError
    try:
        machine = lp.machine_block()
        if machine["platform"] != "colab":
            print(f"ERROR: the unit log records Colab sessions; this machine is {machine['platform']}",
                  file=sys.stderr)
            return 2
        rates = unitlog.load_rates(ns.rates)
        if ns.action == "start":
            closed, session = unitlog.start_session(ns.drive_mount, machine, rates)
            if closed is not None:
                print(f"closed unfinished session {closed['session_id']} at its last-seen time {closed['end_utc']}: "
                      f"{closed['estimated_units']} units")
            print(f"session {session['session_id']} started {session['start_utc']} "
                  f"(runtime {unitlog.runtime_of(session['gpu_type'])})")
        else:
            row = unitlog.end_session(ns.drive_mount, rates)
            print(f"session {row['session_id']}: {row['hours']} h x {row['units_per_hour']} units/h = "
                  f"{row['estimated_units']} units (appended to {unitlog.logs_dir(ns.drive_mount) / unitlog.UNITS_CSV})")
    except (unitlog.UnitLogError, DriveError, lp.PlatformError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0
