"""Unit tests for tools/progress/fragments.py.

CAPABILITIES:
  CAP-PROGRESS-002: fragment loading per kind
  CAP-PROGRESS-003: parse errors carry path and line
INPUTS AND OUTPUTS: scratch repositories built in tmp_path.
CONTRACTS: fragment formats v1.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness.
NOT IN SCOPE:
  - Acceptance tests.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 1 created.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.progress import fragments
from tools.progress.fragments import FragmentError, load_all


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


STATUS = (
    "WP: WP-2.1\n"
    "Title: Scratch status\n"
    "Status: IN-BUILD\n"
    "Tier: T2\n"
    "Size: S\n"
    "Branch: claude/wp-2-1-x\n"
    "PR: none\n"
    "Thread model: Sonnet high\n"
    "Updated: 2026-10-10\n"
    "\n"
    "Free text line.\n"
)

BLOCKER = (
    "# BLK-2.1-01 — scratch blocker\n"
    "Status: OPEN\n"
    "WP: WP-2.1\n"
    "Owner capability: ACCESS\n"
    "Raised: 2026-10-10\n"
    "Session: https://claude.ai/code/session_scratch\n"
    "Unblocks: WP-2.1\n"
    "Time needed: 5 minutes\n"
    "Loop: none\n"
    "\n"
    "What I need: a scratch thing.\n"
    "\n"
    "Exact steps:\n"
    "1. Step one.\n"
    "2. Step two.\n"
    "\n"
    "Meanwhile: other work.\n"
)

DECISION = (
    "# DEC-2.1-01 — scratch decision\n"
    "Status: ACTIVE\n"
    "WP: WP-2.1\n"
    "Date: 2026-10-10\n"
    "Spec basis: FR-x\n"
    "\n"
    "Question: which way?\n"
    "\n"
    "Options:\n"
    "1. A — cheap\n"
    "2. B — safe\n"
    "\n"
    "Choice: 1. A\n"
    "\n"
    "Why: measured.\n"
    "\n"
    'Cannot-do check (all must be "no"):\n'
    "- Weakens, skips or deletes a test: no\n"
    "- Changes a requirement, threshold or exit criterion: no\n"
    "- Touches a NEVER path: no\n"
    "- Adds synthetic or substitute data where real data is required: no\n"
    "- Widens network, credentials or security permissions: no\n"
    "- Spends money or starts a paid service or trial: no\n"
    "\n"
    "Reversal: revert the commit.\n"
)

DEBT = (
    "ID: DEBT-2.1-01\n"
    "Status: OPEN\n"
    "Severity: MINOR\n"
    "Source: WP-2.1-F01\n"
    "Target WP: WP-2.2\n"
    "Accepted by: owner\n"
    "What: scratch debt\n"
)

LEDGER = (
    "WO: WO-2.1-01\n"
    "Date: 2026-10-10\n"
    "Model: scratch-model\n"
    "Attempts: 1\n"
    "Result: ACCEPTED\n"
)


def test_B1_status_fragment_fields(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/status.d/WP-2.1.md", STATUS)
    loaded = load_all(tmp_path)
    assert len(loaded.status) == 1
    record = loaded.status[0]
    assert record.fields["WP"] == "WP-2.1"
    assert record.fields["Status"] == "IN-BUILD"
    assert record.fields["Updated"] == "2026-10-10"
    assert record.free_text == "Free text line."
    assert record.path.name == "WP-2.1.md"


def test_B1_blocker_labelled_lines_and_free_text(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-01.md", BLOCKER)
    (record,) = load_all(tmp_path).blockers
    assert record.fields["Status"] == "OPEN"
    assert record.fields["Owner capability"] == "ACCESS"
    assert record.fields["Unblocks"] == "WP-2.1"
    assert record.steps == ("Step one.", "Step two.")
    assert "What I need: a scratch thing." in record.free_text
    assert "Meanwhile: other work." in record.free_text


def test_B1_decision_cannot_do_answers(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/decisions.d/DEC-2.1-01.md", DECISION)
    (record,) = load_all(tmp_path).decisions
    assert record.fields["Status"] == "ACTIVE"
    assert record.options == ("A — cheap", "B — safe")
    assert len(record.cannot_do) == 6
    assert all(answer == "no" for _, answer in record.cannot_do)
    assert record.cannot_do[0][0] == "Weakens, skips or deletes a test"


def test_B1_debt_fragment_fields(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/debt.d/DEBT-2.1-01.md", DEBT)
    (record,) = load_all(tmp_path).debt
    assert record.fields["ID"] == "DEBT-2.1-01"
    assert record.fields["Severity"] == "MINOR"
    assert record.fields["Target WP"] == "WP-2.2"


def test_B1_ledger_fragment_fields(tmp_path: Path) -> None:
    _write(tmp_path, "docs/outsourcing/ledger.d/WO-2.1-01.md", LEDGER)
    (record,) = load_all(tmp_path).ledger
    assert record.fields["WO"] == "WO-2.1-01"
    assert record.fields["Result"] == "ACCEPTED"


def test_B1_missing_folders_are_empty(tmp_path: Path) -> None:
    loaded = load_all(tmp_path)
    assert loaded.status == ()
    assert loaded.blockers == ()
    assert loaded.debt == ()
    assert loaded.decisions == ()
    assert loaded.ledger == ()


def test_B1_unknown_fragment_file_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/notes.txt", "not a fragment\n")
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-01.md", BLOCKER)
    loaded = load_all(tmp_path)
    assert len(loaded.blockers) == 1


def test_B1_iteration_over_directories_is_sorted(tmp_path: Path) -> None:
    for name in ("BLK-2.1-03", "BLK-2.1-01", "BLK-2.1-02"):
        _write(tmp_path, f"docs/progress/blockers.d/{name}.md", BLOCKER.replace("BLK-2.1-01", name))
    loaded = load_all(tmp_path)
    assert [record.path.name for record in loaded.blockers] == [
        "BLK-2.1-01.md",
        "BLK-2.1-02.md",
        "BLK-2.1-03.md",
    ]


def test_E2_windows_line_endings_and_trailing_space_after_key(tmp_path: Path) -> None:
    text = "WP: WP-2.1 \r\nTitle :  Scratch \r\nStatus: IN-BUILD\r\nUpdated: 2026-10-10\r\n"
    _write(tmp_path, "docs/progress/status.d/WP-2.1.md", text)
    (record,) = load_all(tmp_path).status
    assert record.fields["WP"] == "WP-2.1"
    assert record.fields["Title"] == "Scratch"
    assert record.fields["Status"] == "IN-BUILD"


def test_E6_parse_error_names_path_and_line(tmp_path: Path) -> None:
    path = _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-01.md", "WP: WP-2.1\n")
    with pytest.raises(FragmentError) as excinfo:
        load_all(tmp_path)
    message = str(excinfo.value)
    assert str(path) in message
    assert ":1:" in message


def test_E6_key_without_value_is_a_parse_error(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/status.d/WP-2.1.md", "WP\n")
    # "WP" has no colon, so the fields stop at once and the WP key is absent.
    (record,) = load_all(tmp_path).status
    assert "WP" not in record.fields


def test_E6_labelled_line_before_marker_is_a_parse_error(tmp_path: Path) -> None:
    bad = "# DEC-2.1-01 — x\nWP: WP-2.1\n\n- not-a-check-line\n"
    _write(tmp_path, "docs/progress/decisions.d/DEC-2.1-01.md", bad)
    with pytest.raises(FragmentError):
        load_all(tmp_path)


def test_fragment_error_attributes(tmp_path: Path) -> None:
    path = _write(tmp_path, "docs/progress/decisions.d/DEC-2.1-01.md", "WP: WP-2.1\n")
    with pytest.raises(FragmentError) as excinfo:
        load_all(tmp_path)
    assert excinfo.value.path == path
    assert excinfo.value.line == 1
    assert "Status" in excinfo.value.reason


def test_module_public_api_is_exported() -> None:
    assert set(fragments.__all__) >= {"FragmentError", "Fragments", "load_all"}
