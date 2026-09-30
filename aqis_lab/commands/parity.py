"""The `parity` command: compare two smoke bundles (FR-0.7-08).

CAPABILITIES:
  CAP-PARITY-004: `python -m aqis_lab parity <results-A> <results-B>` (bundle folders or .tar archives) prints both bundles' facts, every difference (one DIFFERENT line each) and a summary; exit 0 identical, 1 differences, 2 an unusable bundle or a usage error (ERROR: on stderr) [tests: test_FR_0_7_08_identical_bundles_report_no_difference, test_FR_0_7_08_reports_every_per_clip_difference, test_FR_0_7_08_damaged_bundle_is_input_error]
INPUTS AND OUTPUTS: two paths in; the report on stdout, errors on stderr and an exit code out.
CONTRACTS: bundle format in docs/runs/PHASE0_SMOKE.md.
INVARIANTS:
  - A difference is never a warning: any difference is exit 1.
NOT IN SCOPE:
  - The comparison rules (aqis_lab/parity.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-08 created.
"""
import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab parity",
                                     description="Compare two smoke bundles: transcript hashes and WER per clip and in "
                                                 "total (docs/runs/PHASE0_SMOKE.md).")
    parser.add_argument("a", help="bundle A (folder or .tar)")
    parser.add_argument("b", help="bundle B (folder or .tar)")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.parity import ParityInputError, compare, load_bundle, report_lines
    try:
        report = compare(load_bundle(ns.a), load_bundle(ns.b))
    except ParityInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for line in report_lines(report):
        print(line)
    return 1 if report.differences else 0
