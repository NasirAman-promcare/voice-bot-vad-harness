"""The `drive` command: `drive layout` creates the AQIS_LAB folder layout on Google Drive and reports crowded folders.

CAPABILITIES:
  CAP-DRIVE-004: `python -m aqis_lab drive layout --drive-mount DIR` creates the missing AQIS_LAB/{packs,models,results,logs} folders, prints one line per layout folder (created or exists) and a WARNING on stderr for every folder over 1,000 entries; exit 0 done, 2 when AQIS_LAB is missing, a layout name is not a folder, or a write is refused [tests: test_FR_0_5_03_creates_missing_layout_folders, test_FR_0_5_03_refuses_when_aqis_lab_missing, test_FR_0_5_03_layout_reports_crowded_folders]
INPUTS AND OUTPUTS: command-line arguments in; folders on Drive, a report on stdout, warnings and errors on stderr.
CONTRACTS: the Drive layout documented in the Colab runbook (docs/colab/).
INVARIANTS:
  - Never deletes or changes anything; never creates MyDrive/AQIS_LAB itself.
NOT IN SCOPE:
  - Mounting Drive (the launcher notebook).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-03 created.
"""
import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab drive",
                                     description="Google Drive folder layout for the lab (MyDrive/AQIS_LAB).")
    actions = parser.add_subparsers(dest="action", required=True, metavar="action")
    layout = actions.add_parser("layout", help="create the missing AQIS_LAB/{packs,models,results,logs} folders")
    layout.add_argument("--drive-mount", required=True, help="folder Google Drive is mounted at, such as /content/drive")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.drive import LAYOUT, DriveError, ensure_layout
    from aqis_lab.platform import PlatformError
    try:
        result = ensure_layout(ns.drive_mount)
    except (DriveError, PlatformError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for name in LAYOUT:
        state = "created" if name in result.created else "exists "
        print(f"{state} {name}  ({result.folder / name})")
    print(f"layout ready in {result.folder}; {len(result.crowded)} folder(s) over 1,000 entries")
    return 0
