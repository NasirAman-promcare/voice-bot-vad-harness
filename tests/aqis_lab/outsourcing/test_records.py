"""Unit tests for tools.outsourcing.records.

CAPABILITIES:
  CAP-OUTSOURCING-RECORDS: Shared records and exit codes for relay runs [tests: test_records.py]
INPUTS AND OUTPUTS: Records and result codes tests.
CONTRACTS: none.
INVARIANTS: Records and exit codes match specification.
NOT IN SCOPE: I/O.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from pathlib import Path
from tools.outsourcing.chat import ChatRequest, Turn
from tools.outsourcing.records import (
    CheckResult,
    CheckResults,
    RelayOptions,
    Request,
    Result,
    StepPart,
)


def test_result_codes_and_display_names():
    assert Result.ACCEPTED.exit_code == 0
    assert Result.ACCEPTED.display_name == "ACCEPTED"
    assert Result.INVALID.exit_code == 2
    assert Result.QUESTIONS.exit_code == 4
    assert Result.CUT_OFF.exit_code == 5
    assert Result.SECRET.exit_code == 6
    assert Result.CREDENTIAL.exit_code == 7
    assert Result.EXHAUSTED.exit_code == 8
    assert Result.INTEGRITY.exit_code == 9
    assert Result.NETWORK.exit_code == 10
    assert Result.PAUSED_DAILY.exit_code == 11
    assert Result.PAUSED_DAILY.display_name == "PAUSED-DAILY"
    assert Result.PAUSED_BUSY.exit_code == 12
    assert Result.PAUSED_BUSY.display_name == "PAUSED-BUSY"
    assert Result.TOO_LARGE.exit_code == 13
    assert Result.TOO_LARGE.display_name == "TOO-LARGE"
    assert Result.GIT.exit_code == 14


def test_check_results_properties():
    r1 = CheckResult("scope", True, "ok", Path("log1"), (), False)
    r2 = CheckResult("headers", True, "ok", Path("log2"), (), False)
    res = CheckResults((r1, r2))
    assert res.passed is True
    assert res.integrity_failed is False

    r3 = CheckResult("integrity", False, "failed", Path("log3"), (), True)
    res_failed = CheckResults((r1, r3))
    assert res_failed.passed is False
    assert res_failed.integrity_failed is True


def test_records_instantiation():
    part = StepPart("1", ("file1.py",))
    assert part.label == "1"
    assert part.paths == ("file1.py",)

    chat_req = ChatRequest("sys", (Turn("user", "hello"),), 100)
    req = Request(chat_req, ("file1.py",), (), 8)
    assert req.characters == 8

    opt = RelayOptions(
        wo="WO-1.0-02",
        attempts=3,
        api_base="base",
        timeout=60,
        verify_timeout=120,
        pool="default",
        dry_run=False,
        status=False,
        models=("m1",),
        restart=False,
    )
    assert opt.wo == "WO-1.0-02"
