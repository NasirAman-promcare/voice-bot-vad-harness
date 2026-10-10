"""Unit tests for tools.outsourcing.checks.

CAPABILITIES:
  CAP-OUTSOURCING-CHECKS: Run checks and collect results for relay runs [tests: test_checks.py]
INPUTS AND OUTPUTS: Check runner unit tests.
CONTRACTS: none.
INVARIANTS: Check execution matches specifications.
NOT IN SCOPE: I/O outside temp directories.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tools.outsourcing.checks import hash_read_only_tests, quick_checks
from tools.outsourcing.records import StepPart
from tools.outsourcing.workorder import load_work_order


def test_hash_read_only_tests(tmp_path: Path):
    (tmp_path / "docs" / "process").mkdir(parents=True)
    (tmp_path / "docs" / "process" / "PROTECTED_PATHS.txt").write_text("[LAB-OWNED]\nout.py\n", encoding="utf-8")
    order_file = tmp_path / "order.md"
    order_file.write_text(
        "---\nid: WO-1.0-02\nwp: WP-1.0\ntitle: t\nmodel: default\nchannel: api\n"
        "attempt_budget: 3\nrisk_tier: T1\nmax_output_tokens: 100\n"
        "context: []\noutputs:\n  - out.py\nread_only_tests:\n  - test_ro.py\n"
        "allowed_dependencies:\n  - stdlib\nverify:\n  - pytest\n---\nbody",
        encoding="utf-8",
    )
    (tmp_path / "out.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "test_ro.py").write_text("def test_x(): pass\n", encoding="utf-8")

    order = load_work_order(order_file, tmp_path)
    hashes = hash_read_only_tests(order, tmp_path)
    assert "test_ro.py" in hashes
    assert len(hashes["test_ro.py"]) == 64
