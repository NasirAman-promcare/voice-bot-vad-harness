"""The `sync` command: copy the results store one way to AQIS_LAB/results on Google Drive with rclone.

CAPABILITIES:
  CAP-SYNC-003: `python -m aqis_lab sync [--dry-run] [--config FILE]` prints rclone's messages and a summary; exit 0 done, 1 rclone failed or refused to replace a remote file, 2 missing rclone, remote, destination folder, store or a bad config [tests: test_FR_0_6_05_copies_store_to_aqis_lab_results, test_FR_0_6_05_dry_run_changes_nothing, test_FR_0_6_05_never_replaces_a_remote_file, test_FR_0_6_05_missing_remote_points_to_runbook, test_FR_0_6_05_missing_rclone_points_to_runbook]
INPUTS AND OUTPUTS: command-line arguments in; messages on stdout, `ERROR: ...` on stderr, exit 0, 1 or 2.
CONTRACTS: docs/oracle/ORACLE_RUNBOOK.md (setup, nightly schedule).
INVARIANTS:
  - The settings come from config/aqis_lab/oracle.yaml unless --config names another file.
NOT IN SCOPE:
  - The copy itself (aqis_lab/sync.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-05 created.
"""
import argparse
import sys


def build_parser():
    from aqis_lab.oracle_config import DEFAULT_CONFIG
    parser = argparse.ArgumentParser(prog="python -m aqis_lab sync",
                                     description="Copy the results store one way to AQIS_LAB/results on Google Drive "
                                                 "with rclone; remote files are never deleted or replaced "
                                                 "(docs/oracle/ORACLE_RUNBOOK.md).")
    parser.add_argument("--dry-run", action="store_true", help="list what would be copied; change nothing")
    parser.add_argument("--config", default=None, help=f"Oracle settings (default {DEFAULT_CONFIG})")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.oracle_config import OracleConfigError
    from aqis_lab.results.store import StoreInputError, StoreIntegrityError
    from aqis_lab.sync import SyncFailed, SyncUsageError, run_sync
    try:
        return run_sync(ns.config, dry_run=ns.dry_run, echo=lambda line: print(line, flush=True))
    except (SyncUsageError, OracleConfigError, StoreInputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (SyncFailed, StoreIntegrityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
