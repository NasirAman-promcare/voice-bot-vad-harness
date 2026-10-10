"""Unit tests for tools.outsourcing.fixorder.

CAPABILITIES:
  CAP-OUTSOURCING-FIXORDER: Format fix order text following FIX_ORDER.md [tests: test_fixorder.py]
INPUTS AND OUTPUTS: Fix order unit tests.
CONTRACTS: none.
INVARIANTS: Log trimming adheres to line budget limits.
NOT IN SCOPE: I/O.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from tools.outsourcing.fixorder import trim_log


def test_trim_log_short():
    text = "\n".join(f"line {i}" for i in range(10))
    assert trim_log(text) == text


def test_trim_log_long():
    text = "\n".join(f"line {i}" for i in range(100))
    trimmed = trim_log(text)
    lines = trimmed.splitlines()
    assert len(lines) == 61
    assert lines[0] == "line 0"
    assert lines[19] == "line 19"
    assert "[… 40 lines …]" in lines[20]
    assert lines[21] == "line 60"
    assert lines[-1] == "line 99"
