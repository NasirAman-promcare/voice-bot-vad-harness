"""The `doctor` command: check that this machine is ready for the lab and write a PASS/FAIL report.

CAPABILITIES:
  CAP-DOCTOR-003: `python -m aqis_lab doctor --target cloud|colab|oracle [--expect-gpu] [--drive-mount DIR] [--out DIR] [--work-dir DIR]` prints the check table and the report path; exit 0 when nothing FAILs, 1 on any FAIL, 2 on a usage error or when the report cannot be written [tests: test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json, test_FR_0_5_02_any_fail_exits_non_zero, test_FR_0_5_02_fails_when_target_is_not_this_platform, test_FR_0_5_02_colab_fails_when_aqis_lab_read_only]
INPUTS AND OUTPUTS: command-line arguments in; the table on stdout, doctor_<platform>_<UTC>.json in --out
  (default data/raw/aqis_lab/doctor, git-ignored), errors on stderr, exit code 0, 1 or 2.
CONTRACTS: report format in docs/doctor/DOCTOR.md.
INVARIANTS:
  - --out on Google Drive must be inside MyDrive/AQIS_LAB (aqis_lab.drive).
NOT IN SCOPE:
  - The checks themselves (aqis_lab/doctor.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-02 created.
  2026-09-28 WP-0.5 FR-0.5-07: with --drive-mount, the unit log's last-seen time is updated.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "raw" / "aqis_lab" / "doctor"
DEFAULT_WORK = REPO_ROOT / "data" / "raw" / "aqis_lab" / "work"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab doctor",
                                     description="Check Python, the lock, disk, RAM, GPU and (on Colab) Google Drive; "
                                                 "print a PASS/FAIL table and write a JSON report "
                                                 "(docs/doctor/DOCTOR.md).")
    parser.add_argument("--target", required=True, choices=["cloud", "colab", "oracle"],
                        help="the platform this machine must be")
    parser.add_argument("--expect-gpu", action="store_true", help="fail unless a GPU is detected")
    parser.add_argument("--drive-mount", default=None,
                        help="folder Google Drive is mounted at (required with --target colab)")
    parser.add_argument("--out", default=None, help=f"folder for the JSON report (default {DEFAULT_OUT})")
    parser.add_argument("--work-dir", default=None,
                        help=f"local work folder whose free disk is checked (default {DEFAULT_WORK})")
    return parser


def main(argv):
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.target == "colab" and ns.drive_mount is None:
        parser.error("--target colab needs --drive-mount (the folder Google Drive is mounted at, "
                     "such as /content/drive)")
    from aqis_lab.doctor import DoctorInputError, run_doctor, write_report
    from aqis_lab.drive import DriveError
    from aqis_lab.platform import PlatformError
    from aqis_lab.unitlog import UnitLogError, touch
    try:
        report = run_doctor(ns.target, expect_gpu=ns.expect_gpu, work_dir=ns.work_dir or DEFAULT_WORK,
                            drive_mount=ns.drive_mount)
        print(report.table())
        path = write_report(report, ns.out or DEFAULT_OUT)
        if ns.drive_mount is not None:
            touch(ns.drive_mount)
    except (DoctorInputError, DriveError, PlatformError, UnitLogError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"report: {path}")
    return 1 if report.result == "FAIL" else 0
