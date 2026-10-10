"""Unit tests for tools.outsourcing.steplog.

CAPABILITIES:
  CAP-OUTSOURCING-STEPLOG: Parse and render relay step logs [tests: test_steplog.py]
INPUTS AND OUTPUTS: Step log unit tests.
CONTRACTS: none.
INVARIANTS: StepLog round-trips byte for byte.
NOT IN SCOPE: I/O.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest
from tools.outsourcing.steplog import StepLog, StepLogError, parse, render


def test_empty_log_roundtrip():
    log = parse("")
    assert log.runs == ()
    assert log.accepted == ()
    assert log.switches == ()
    assert log.stops == ()


def test_malformed_log_raises():
    with pytest.raises(StepLogError):
        parse("This line is invalid\n")
