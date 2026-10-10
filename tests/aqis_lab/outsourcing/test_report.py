"""Unit tests for tools.outsourcing.report.

CAPABILITIES:
  CAP-OUTSOURCING-REPORT: Render concise finish report for relay execution. [tests: test_report.py]
INPUTS AND OUTPUTS: Tests report output generation.
CONTRACTS: none.
INVARIANTS:
  - Report output is <= 25 lines.
  - Display name on first line.
NOT IN SCOPE:
  - Network calls or git execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 FIX 1 created.
"""
from __future__ import annotations

from tools.outsourcing.records import RelayOutcome, Result
from tools.outsourcing.report import render_report


def test_render_report_basic():
    outcome = RelayOutcome(result=Result.ACCEPTED)
    lines = render_report(outcome, {"wo_id": "WO-9.9-03", "summary_path": "docs/outsourcing/returns/WO-9.9-03/summary.md"})
    assert lines[0] == "ACCEPTED"
    assert any("Merge: git merge --no-ff wo/WO-9.9-03" in line for line in lines)
    assert any("Summary: docs/outsourcing/returns/WO-9.9-03/summary.md" in line for line in lines)
    assert len(lines) <= 25


def test_render_report_exhausted():
    outcome = RelayOutcome(result=Result.EXHAUSTED)
    facts = {
        "summary_path": "docs/outsourcing/returns/WO-9.9-03/summary.md",
        "checks_table": ["test_demo: FAIL"],
    }
    lines = render_report(outcome, facts)
    assert lines[0] == "EXHAUSTED"
    assert any("Summary: docs/outsourcing/returns/WO-9.9-03/summary.md" in line for line in lines)
    assert any("test_demo: FAIL" in line for line in lines)
    assert len(lines) <= 25
