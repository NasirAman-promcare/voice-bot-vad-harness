"""Unit tests for tools/progress/lint.py.

CAPABILITIES:
  CAP-PROGRESS-004: lint fragment records against IDs, statuses and required fields
INPUTS AND OUTPUTS: scratch fragments built in memory.
CONTRACTS: fragment formats v1.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness.
NOT IN SCOPE:
  - Acceptance tests.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 2 created.
"""
from __future__ import annotations

from pathlib import Path

from tools.progress.fragments import BlockerFragment, DebtFragment, DecisionFragment, Fragments, LedgerFragment, StatusFragment
from tools.progress.lint import lint


def _status(status: str = "IN-BUILD", path: str = "docs/progress/status.d/WP-2.1.md") -> StatusFragment:
    return StatusFragment(Path(path), {"WP": "WP-2.1", "Status": status}, "")


def _blocker(
    bid: str = "BLK-2.1-01",
    capability: str = "ACCESS",
    status: str = "OPEN",
    steps: tuple[str, ...] = ("Step one.",),
    path: str | None = None,
    legacy: bool = False,
) -> BlockerFragment:
    fields = {
        "ID": bid,
        "Status": status,
        "Owner capability": capability,
        "Time needed": "5 minutes",
        "Meanwhile": "other work",
        "Unblocks": "WP-2.1",
    }
    if legacy:
        fields["Legacy"] = "yes"
    return BlockerFragment(Path(path or f"docs/progress/blockers.d/{bid}.md"), fields, steps, "")


def _decision(
    did: str = "DEC-2.1-01",
    status: str = "ACTIVE",
    options: tuple[str, ...] = ("A",),
    cannot_do: tuple[tuple[str, str], ...] = (
        ("Weakens, skips or deletes a test", "no"),
        ("Changes a requirement, threshold or exit criterion", "no"),
        ("Touches a NEVER path", "no"),
        ("Adds synthetic or substitute data where real data is required", "no"),
        ("Widens network, credentials or security permissions", "no"),
        ("Spends money or starts a paid service or trial", "no"),
    ),
) -> DecisionFragment:
    fields = {"ID": did, "Status": status, "Choice": "1. A", "Why": "Measured.", "Reversal": "Revert."}
    return DecisionFragment(Path(f"docs/progress/decisions.d/{did}.md"), fields, options, cannot_do, "")


def _debt(
    debt_id: str = "DEBT-2.1-01",
    status: str = "OPEN",
    path: str | None = None,
    legacy: bool = False,
    free_text: str = "",
) -> DebtFragment:
    fields = {
        "ID": debt_id,
        "Status": status,
        "Severity": "MINOR",
        "Source": "WP-2.1-F01",
        "Target WP": "WP-2.2",
        "Accepted by": "owner",
    }
    if legacy:
        fields["Legacy"] = "yes"
    return DebtFragment(Path(path or f"docs/progress/debt.d/{debt_id}.md"), fields, free_text)


def _ledger(wo_id: str = "WO-2.1-01", result: str = "ACCEPTED") -> LedgerFragment:
    return LedgerFragment(Path(f"docs/outsourcing/ledger.d/{wo_id}.md"), {"WO": wo_id, "Result": result}, "")


def _fragments(
    status=(),
    blockers=(),
    debt=(),
    decisions=(),
    ledger=(),
) -> Fragments:
    return Fragments(status=status, blockers=blockers, debt=debt, decisions=decisions, ledger=ledger)


def test_B2_status_values_are_validated() -> None:
    issues = lint(_fragments(status=(_status("WRONG"),)))
    assert any("Status" in issue.message for issue in issues)


def test_B2_blocker_required_fields_and_capability() -> None:
    blocker = BlockerFragment(
        Path("docs/progress/blockers.d/BLK-2.1-01.md"),
        {"ID": "BLK-2.1-01", "Status": "OPEN", "Owner capability": "ACCESS"},
        (),
        "",
    )
    issues = lint(_fragments(blockers=(blocker,)))
    messages = "\n".join(issue.message for issue in issues)
    assert "Time needed" in messages
    assert "Meanwhile" in messages
    assert "Unblocks" in messages
    assert "Exact steps" in messages


def test_B2_legacy_owner_capability_only_with_legacy_marker() -> None:
    blocker = _blocker(capability="legacy", legacy=False)
    issues = lint(_fragments(blockers=(blocker,)))
    assert any("legacy" in issue.message for issue in issues)


def test_B2_blocker_label_belongs_to_following_lines() -> None:
    blocker = _blocker(steps=("Step one.", "Step two."))
    issues = lint(_fragments(blockers=(blocker,)))
    assert not any("Exact steps" in issue.message for issue in issues)


def test_B2_decision_required_fields_and_cannot_do() -> None:
    decision = DecisionFragment(
        Path("docs/progress/decisions.d/DEC-2.1-01.md"),
        {"ID": "DEC-2.1-01", "Status": "ACTIVE"},
        (),
        (("Weakens, skips or deletes a test", "yes"),),
        "",
    )
    issues = lint(_fragments(decisions=(decision,)))
    messages = "\n".join(issue.message for issue in issues)
    assert "Choice" in messages
    assert "Why" in messages
    assert "Reversal" in messages
    assert "Options" in messages
    assert "cannot-do" in messages


def test_B2_debt_required_fields() -> None:
    debt = DebtFragment(
        Path("docs/progress/debt.d/DEBT-2.1-01.md"),
        {"ID": "DEBT-2.1-01", "Status": "OPEN"},
        "",
    )
    issues = lint(_fragments(debt=(debt,)))
    messages = "\n".join(issue.message for issue in issues)
    for field in ("Severity", "Source", "Target WP", "Accepted by"):
        assert field in messages


def test_B2_new_id_pattern_is_enforced() -> None:
    blocker = _blocker(bid="BLK-2.1-1", path="docs/progress/blockers.d/BLK-2.1-1.md")
    issues = lint(_fragments(blockers=(blocker,)))
    assert any("must match <KIND>-<n>.<n>-<nn>" in issue.message for issue in issues)


def test_B2_legacy_id_requires_legacy_marker() -> None:
    debt = _debt(debt_id="DEBT-001", path="docs/progress/debt.d/DEBT-001.md", legacy=False)
    issues = lint(_fragments(debt=(debt,)))
    assert any("Legacy: yes" in issue.message for issue in issues)


def test_B2_duplicate_ids_name_both_paths() -> None:
    one = _debt(debt_id="DEBT-2.1-01", path="docs/progress/debt.d/DEBT-2.1-01.md")
    two = _debt(debt_id="DEBT-2.1-01", path="docs/progress/debt.d/sub/DEBT-2.1-01.md")
    issues = lint(_fragments(debt=(one, two)))
    messages = "\n".join(issue.message for issue in issues)
    assert "debt.d/DEBT-2.1-01.md" in messages
    assert "debt.d/sub/DEBT-2.1-01.md" in messages


def test_B2_id_must_match_file_name() -> None:
    blocker = _blocker(bid="BLK-2.1-02", path="docs/progress/blockers.d/BLK-2.1-01.md")
    issues = lint(_fragments(blockers=(blocker,)))
    assert any("file name" in issue.message for issue in issues)


def test_B2_legacy_debt_status_agrees_with_row() -> None:
    row = "| DEBT-001 | finding | what | risk | accepted | WP-2.1 | CLOSED in WP-2.2 |"
    debt = _debt(debt_id="DEBT-001", path="docs/progress/debt.d/DEBT-001.md", legacy=True, free_text=row)
    debt.fields["Status"] = "OPEN"
    issues = lint(_fragments(debt=(debt,)))
    assert any("agree" in issue.message for issue in issues)


def test_E4_unknown_wp_status_is_a_warning() -> None:
    record = _status(path="docs/progress/status.d/WP-7.7.md")
    fragments = _fragments(status=(record,))
    issues = lint(fragments)
    assert issues == []
