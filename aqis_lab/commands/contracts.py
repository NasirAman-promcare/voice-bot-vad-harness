"""The `contracts` command: validate event logs, run cards and pack manifests against the v1 contracts.

CAPABILITIES:
  CAP-CONTRACTS-006: `python -m aqis_lab contracts validate <file> --kind event|run_card|manifest [--workers N]` prints one report line per record (one per failing field, named by JSON Pointer) and a summary; exit 0 when every record is valid, 1 on any invalid record or no records, 2 on usage errors, an unreadable file or worker processes that cannot run [tests: test_FR_0_2_04_cli_valid_events_exit_0, test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields, test_FR_0_2_04_cli_one_invalid_line_anywhere_fails, test_FR_0_2_04_cli_unparsable_and_blank_lines_are_invalid_records, test_FR_0_2_04_cli_empty_file_fails, test_FR_0_2_04_cli_run_card_and_manifest_kinds, test_FR_0_2_04_cli_missing_file_exit_2, test_FR_0_2_04_cli_listed_by_dispatcher, test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files]
INPUTS AND OUTPUTS: a file path (events as JSON Lines; a run card or a manifest as one JSON document) in; the
  per-record report on stdout, errors on stderr, exit code 0, 1 or 2.
CONTRACTS: event-log v1, run-card v1, pack-manifest v1.
INVARIANTS:
  - Every record gets a report line; a record never passes because another one failed or could not be parsed.
  - Worker processes only change speed, never the report; a worker failure is exit 2, never a silent fallback.
NOT IN SCOPE:
  - The validation rules themselves (aqis_lab/contracts/validate.py).
CHANGE LOG:
  2026-09-27 WP-0.2 FR-0.2-04 created.
"""
import argparse
import os
import sys
from pathlib import Path

from aqis_lab.contracts.validate import (POOL_MIN_RECORDS, WorkerPoolError, display_pointer, split_json_lines,
                                         uses_worker_pool, validate_document, validate_event_lines)

KIND_CHOICES = ("event", "run_card", "manifest")


def _workers(text):
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be a whole number, got {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab contracts",
                                     description="Check records against the lab contracts (docs/contracts/).")
    actions = parser.add_subparsers(dest="action", required=True, metavar="action")
    check = actions.add_parser("validate", help="validate a file and print a per-record report",
                               description="Validate a file and print one line per record (one per failing field) "
                                           "and a summary. Exit 0: all valid; 1: any invalid record or no records; "
                                           "2: usage error or unreadable file.")
    check.add_argument("file", help="event log (JSON Lines) or run card or manifest (one JSON document)")
    check.add_argument("--kind", required=True, choices=KIND_CHOICES, help="contract to check against")
    check.add_argument("--workers", type=_workers, default=None,
                       help=f"worker processes for event files of at least {POOL_MIN_RECORDS} records "
                            f"(default: the CPUs this process may use; 1 validates in this process)")
    return parser


def _report_lines(reports, label):
    for report in reports:
        if report.valid:
            yield f"{label} {report.number}: OK"
            continue
        for err in report.errors:
            message = err.message.replace("\r", "\\r").replace("\n", "\\n")
            yield f"{label} {report.number}: INVALID {display_pointer(err.pointer)}: {message}"


def main(argv):
    ns = build_parser().parse_args(argv)
    try:
        data = Path(ns.file).read_bytes()
    except OSError as exc:
        print(f"ERROR: cannot read {ns.file}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    if ns.kind == "event":
        workers = ns.workers or os.process_cpu_count() or 1
        n_records = len(split_json_lines(data))
        if uses_worker_pool(n_records, workers):
            print(f"validating {n_records} records with {workers} worker processes", file=sys.stderr)
        try:
            reports = validate_event_lines(data, workers)
        except WorkerPoolError as exc:
            print(f"ERROR: {exc}; rerun with --workers 1", file=sys.stderr)
            return 2
        label = "line"
    else:
        reports = [validate_document(ns.kind, data)] if data.strip(b" \t\r\n") else []
        label = "record"
    invalid = sum(1 for report in reports if not report.valid)
    lines = list(_report_lines(reports, label))
    lines.append(f"{ns.kind}: {len(reports)} record{'' if len(reports) == 1 else 's'}, "
                 f"{len(reports) - invalid} valid, {invalid} invalid")
    sys.stdout.write("\n".join(lines) + "\n")
    if not reports:
        print(f"ERROR: {ns.file} contains no records", file=sys.stderr)
        return 1
    return 1 if invalid else 0
