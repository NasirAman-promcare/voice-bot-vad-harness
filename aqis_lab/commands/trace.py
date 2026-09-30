"""The `trace` command: print the run card, pack manifest ID and version, clip, git commit and lock hash of a row.

CAPABILITIES:
  CAP-TRACE-002: `python -m aqis_lab trace <result-row-id> [--store DIR]` prints the checked trace of one stored row; exit 0 printed, 1 not in the store or a check failed, 2 a malformed ID or no store [tests: test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock, test_FR_0_6_03_unknown_row_id_exit_1, test_FR_0_6_03_malformed_row_id_exit_2, test_FR_0_6_03_missing_store_exit_2]
INPUTS AND OUTPUTS: command-line arguments in; the trace on stdout, `ERROR: ...` on stderr, exit 0, 1 or 2.
CONTRACTS: output format in docs/results/RESULTS_STORE.md ("Trace").
INVARIANTS:
  - The default store is data/raw/aqis_lab/results, as for `results`.
NOT IN SCOPE:
  - The checks themselves (aqis_lab/trace.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-03 created.
"""
import argparse
import sys

from aqis_lab.results.store import DEFAULT_STORE


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab trace",
                                     description="Print the run card, pack manifest ID and version, clip, git commit "
                                                 "and lock hash of a stored result row (docs/results/RESULTS_STORE.md).")
    parser.add_argument("row_id", help="result_row_id: 64 lowercase hexadecimal characters")
    parser.add_argument("--store", default=str(DEFAULT_STORE), help=f"results store folder (default {DEFAULT_STORE})")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.results.store import StoreInputError, StoreIntegrityError
    from aqis_lab.trace import TraceError, format_trace, trace_row
    try:
        text = format_trace(trace_row(ns.store, ns.row_id))
    except StoreInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (TraceError, StoreIntegrityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0
