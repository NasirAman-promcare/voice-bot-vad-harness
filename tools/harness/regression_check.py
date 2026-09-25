"""Compare a harness pytest JUnit report with the recorded harness baseline and fail on regressions.

Usage:
  python -m tools.harness.regression_check --junit <report.xml> [--baseline docs/baselines/harness_tests_baseline.md]

CAPABILITIES:
  CAP-HARN-001: exits 1 when a test that passed in the provisioned baseline now fails, errors, is skipped or is missing; lists newly passing tests as information; exits 2 when an input cannot be read [tests: test_FR_0_0_11_regression_check_flags_newly_failing_baseline_pass, test_FR_0_0_11_regression_check_flags_missing_baseline_pass, test_FR_0_0_11_regression_check_passes_same_or_better, test_FR_0_0_11_regression_check_rejects_unreadable_inputs, test_FR_0_0_11_regression_check_accepts_repository_baseline]
INPUTS AND OUTPUTS: a pytest JUnit XML file and the baseline Markdown; a report on stdout; exit 0, 1 or 2.
CONTRACTS: baseline section "## Provisioned baseline (round 2)" with a "### Results" table of
  | `tests/...py::test_name` | passed/failed/error/skipped | seconds | rows (docs/baselines/harness_tests_baseline.md).
INVARIANTS:
  - Only the provisioned baseline section counts; the round 1 history is never used for comparison.
  - Standard library only.
NOT IN SCOPE:
  - Running the tests (the CI job harness-regression does), or updating the baseline.
CHANGE LOG:
  2026-09-25 WP-0.0 round 2 FR-0.0-11 (amended) created.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SECTION = "Provisioned baseline (round 2)"
ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(passed|failed|error|skipped)\s*\|\s*[\d.]+\s*\|\s*$")


class InputError(Exception):
    """An input file is missing, unreadable or not in the expected form."""


def read_baseline(path):
    """{node id: outcome} from the Results table of the provisioned baseline section."""
    try:
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise InputError(f"cannot read baseline {path}: {exc}") from exc
    match = re.search(rf"^## {re.escape(SECTION)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise InputError(f"{path} has no '## {SECTION}' section")
    results = re.search(r"^### Results\s*$(.*?)(?=^#{2,3} |\Z)", match.group(1), re.M | re.S)
    if not results:
        raise InputError(f"'## {SECTION}' in {path} has no '### Results' table")
    rows = {}
    for line in results.group(1).splitlines():
        m = ROW_RE.match(line.strip())
        if m:
            rows[m.group(1)] = m.group(2)
    if not rows:
        raise InputError(f"the '### Results' table of '## {SECTION}' in {path} has no rows")
    return rows


def read_junit(path):
    """{node id: outcome} from a pytest JUnit XML report."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise InputError(f"cannot read JUnit report {path}: {exc}") from exc
    outcomes = {}
    for case in root.iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        if not classname or not name:
            raise InputError(f"testcase without classname or name in {path}")
        node = classname.replace(".", "/") + ".py::" + name
        outcome = "passed"
        for tag, value in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            if case.find(tag) is not None:
                outcome = value
        outcomes[node] = outcome
    return outcomes


def compare(baseline, current):
    """(regressions, newly_passing): regressions are (node, now) for baseline passes that no longer pass."""
    regressions = [(node, current.get(node, "missing")) for node, outcome in sorted(baseline.items())
                   if outcome == "passed" and current.get(node) != "passed"]
    newly = sorted(node for node, outcome in current.items()
                   if outcome == "passed" and baseline.get(node) != "passed")
    return regressions, newly


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tools.harness.regression_check",
                                     description="Fail when a harness test that passed in the baseline no longer passes.")
    parser.add_argument("--junit", required=True, help="pytest --junitxml report of tests/regression")
    parser.add_argument("--baseline", default="docs/baselines/harness_tests_baseline.md")
    args = parser.parse_args(argv)
    try:
        baseline = read_baseline(args.baseline)
        current = read_junit(args.junit)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    regressions, newly = compare(baseline, current)
    passed = sum(1 for outcome in baseline.values() if outcome == "passed")
    print(f"baseline: {len(baseline)} tests, {passed} passed; this run: {len(current)} tests, "
          f"{sum(1 for o in current.values() if o == 'passed')} passed")
    for node, now in regressions:
        print(f"REGRESSION: {node} (baseline passed, now {now})")
    for node in newly:
        print(f"newly passing: {node}")
    print("RESULT: " + ("FAIL" if regressions else "PASS"))
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
