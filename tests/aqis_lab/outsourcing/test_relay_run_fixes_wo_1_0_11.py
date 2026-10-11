"""Claude's fix after the 2026-10-11 WO-1.0-03 relay run (FR-1.0-02, WO-1.0-11 B18), written before the fix.

The run ended `EXHAUSTED` with `Reason: Quick checks failed on final attempt`. The printed checks table showed five
checks, all PASS, because `render_report` printed only the first five lines of the table. The sixth, `tests: FAIL`, was
the one that failed. B18 asks for the checks table; only the whole report is capped at 25 lines.
"""
from __future__ import annotations

from pathlib import Path

from tools.outsourcing.records import CheckResult, CheckResults, RelayOutcome, Result
from tools.outsourcing.report import checks_table, render_report

NAMES = ("scope", "headers", "patterns", "read-only-tests", "compile", "tests", "full-tests")


def results(failing: str) -> CheckResults:
    return CheckResults(results=tuple(
        CheckResult(name=name, passed=name != failing, summary="command failed with returncode 1" if name == failing
                    else "ok", log_path=Path(f"/tmp/{name}.log"), output_paths=(), integrity=False)
        for name in NAMES))


def test_FR_1_0_02_report_shows_every_check_including_a_failure_after_the_fifth():
    facts = {"checks_table": checks_table(results("tests")), "stop_reason": "Quick checks failed on final attempt",
             "summary_path": "docs/outsourcing/returns/WO-9.9-03/summary.md", "wo_id": "WO-9.9-03"}
    lines = render_report(RelayOutcome(result=Result.EXHAUSTED), facts)
    assert len(lines) <= 25
    shown = [line.strip() for line in lines if line.startswith("  ")]
    assert [s.split(":")[0] for s in shown] == list(NAMES)
    assert any(s.startswith("tests: FAIL") for s in shown)
    assert lines[-1].startswith("Summary:")
