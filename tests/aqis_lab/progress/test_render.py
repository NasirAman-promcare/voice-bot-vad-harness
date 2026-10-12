"""Unit tests for tools/progress/render.py.

CAPABILITIES:
  CAP-PROGRESS-005: render the generated tables and the owner queue
  CAP-PROGRESS-006: keep the legacy table layout byte for byte
INPUTS AND OUTPUTS: fragment records built in memory; rendered text.
CONTRACTS: fragment formats v1; generated-table layout v1.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness.
NOT IN SCOPE:
  - Acceptance tests.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 3 created.
"""
from __future__ import annotations

from pathlib import Path

from tools.progress.fragments import (
    BlockerFragment,
    DebtFragment,
    DecisionFragment,
    Fragments,
    LedgerFragment,
    StatusFragment,
)
from tools.progress.render import (
    DEBT_HEADER,
    GENERATED_LINE,
    STATUS_HEADER,
    render_all,
    render_blockers,
    render_debt,
    render_owner_queue,
    render_status,
    wp_sort_key,
)


def _status(wp: str, state: str, updated: str = "2026-10-10", branch: str = "claude/wp-x", pr: str = "none") -> StatusFragment:
    return StatusFragment(
        Path(f"docs/progress/status.d/{wp}.md"),
        {"WP": wp, "Title": f"Title {wp}", "Status": state, "Branch": branch, "PR": pr, "Updated": updated},
        "",
    )


def _blocker(
    bid: str,
    status: str = "OPEN",
    raised: str = "2026-10-10",
    unblocks: str = "WP-2.1",
    capability: str = "ACCESS",
    steps: tuple[str, ...] = ("Step one.", "Step two."),
    legacy: bool = False,
    free_text: str = "",
) -> BlockerFragment:
    fields = {
        "ID": bid,
        "Status": status,
        "WP": "WP-2.1",
        "Owner capability": capability,
        "Raised": raised,
        "Unblocks": unblocks,
        "Time needed": "5 minutes",
        "Meanwhile": "other work",
    }
    if legacy:
        fields["Legacy"] = "yes"
    return BlockerFragment(Path(f"docs/progress/blockers.d/{bid}.md"), fields, steps, free_text)


def _legacy_debt(row: str, status: str = "OPEN") -> DebtFragment:
    debt_id = row.split("|")[1].strip()
    return DebtFragment(
        Path(f"docs/progress/debt.d/{debt_id}.md"),
        {"ID": debt_id, "Status": status, "Target WP": "WP-9.9", "Legacy": "yes"},
        row,
    )


def _new_debt(debt_id: str = "DEBT-2.1-01") -> DebtFragment:
    return DebtFragment(
        Path(f"docs/progress/debt.d/{debt_id}.md"),
        {
            "ID": debt_id,
            "Status": "OPEN",
            "Severity": "MINOR",
            "Source": "WP-2.1-F01",
            "Target WP": "WP-2.2",
            "Accepted by": "DEC-2.1-01",
            "What": "a thing is limited",
            "Risk": "it breaks quietly",
        },
        "",
    )


def _fragments(
    status=(),
    blockers=(),
    debt=(),
    decisions=(),
    ledger=(),
) -> Fragments:
    return Fragments(status=status, blockers=blockers, debt=debt, decisions=decisions, ledger=ledger)


def test_B4_render_all_produces_every_table_with_generated_line() -> None:
    fragments = _fragments(
        status=(_status("WP-2.1", "IN-BUILD"),),
        blockers=(_blocker("BLK-2.1-01"),),
        debt=(_new_debt(),),
    )
    tables = render_all(fragments, on_main=False)
    expected = {
        Path("docs/progress/STATUS.md"),
        Path("docs/progress/BLOCKERS.md"),
        Path("docs/progress/DEBT.md"),
        Path("docs/progress/DECISIONS.md"),
        Path("docs/progress/OWNER_QUEUE.md"),
        Path("docs/outsourcing/LEDGER.md"),
    }
    assert set(tables) == expected
    for text in tables.values():
        assert text.startswith(GENERATED_LINE)


def test_B4_tables_sort_by_wp_number_then_id() -> None:
    records = (
        _status("WP-1.10", "IN-BUILD"),
        _status("WP-1.9", "IN-BUILD"),
        _status("WP-1.1", "IN-BUILD"),
    )
    text = render_status(records, on_main=False)
    order = [line.split("|")[1].strip() for line in text.splitlines() if line.startswith("| WP-")]
    assert order == ["WP-1.1", "WP-1.9", "WP-1.10"]


def test_B5_on_main_renders_audit_pass_and_merge_ready_as_merged() -> None:
    records = (_status("WP-2.1", "AUDIT-PASS"), _status("WP-2.2", "MERGE-READY"))
    text = render_status(records, on_main=True)
    assert "| WP-2.1 | Title WP-2.1 | MERGED |" in text
    assert "| WP-2.2 | Title WP-2.2 | MERGED |" in text


def test_B5_off_main_keeps_audit_pass() -> None:
    text = render_status((_status("WP-2.1", "AUDIT-PASS"),), on_main=False)
    assert "| WP-2.1 | Title WP-2.1 | AUDIT-PASS |" in text


def test_B11_status_table_keeps_legacy_layout() -> None:
    records = (
        _status("WP-0.0", "MERGED", updated="2026-09-27", branch="claude/hopeful-noether-yinc4e",
                pr="https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/1"),
    )
    text = render_status(records, on_main=True)
    assert text == GENERATED_LINE + STATUS_HEADER + (
        "| WP-0.0 | Title WP-0.0 | MERGED | claude/hopeful-noether-yinc4e, "
        "PR https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/1 | 2026-09-27 |\n"
    )


def test_B11_blocker_entry_keeps_verbatim_text() -> None:
    entry = (
        "## BLK-001 — WP-0.0 approval file is not recognised by the hooks\n"
        "STATUS: RESOLVED\n"
        "WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_x\n"
        "\n"
        "**What I need:** the file.\n"
    )
    record = _blocker("BLK-001", status="RESOLVED", legacy=True, free_text=entry)
    text = render_blockers((record,), on_main=True)
    assert text == GENERATED_LINE + "# Blockers\n\nClaude appends an entry here (template: `docs/process/templates/BLOCKER.md`) whenever it needs you. Answer in the session chat or under \"Owner answer\", then set `STATUS: RESOLVED`.\n\n<!-- entries start below -->\n\n" + entry.rstrip("\n") + "\n"


def test_B11_debt_row_renders_verbatim_legacy_line() -> None:
    row = "| DEBT-027 | WP-0.1 approval | latency estimates | wrong timing | `docs/approvals/WP-0.1.md` | Phase 2 VAD timing work | OPEN |"
    text = render_debt((_legacy_debt(row),), on_main=True)
    assert text == GENERATED_LINE + DEBT_HEADER + row + "\n"


def test_B12_new_debt_renders_into_legacy_columns() -> None:
    text = render_debt((_new_debt(),), on_main=False)
    row = "| DEBT-2.1-01 | WP-2.1-F01 | a thing is limited | it breaks quietly | DEC-2.1-01 | WP-2.2 | OPEN |"
    assert row in text


def test_B12_new_debt_closed_by_renders_in_status_cell() -> None:
    debt = _new_debt()
    debt.fields["Status"] = "CLOSED"
    debt.fields["Closed by"] = "WP-2.2"
    text = render_debt((debt,), on_main=False)
    assert "| DEBT-2.1-01 | WP-2.1-F01 | a thing is limited | it breaks quietly | DEC-2.1-01 | WP-2.2 | CLOSED (WP-2.2) |" in text


def test_B6_owner_queue_lists_open_blockers_with_class_time_and_steps() -> None:
    fragments = _fragments(blockers=(_blocker("BLK-2.1-01"),))
    text = render_owner_queue(fragments, on_main=True, last_digest=None)
    assert "BLK-2.1-01" in text
    assert "ACCESS" in text
    assert "5 minutes" in text
    assert "Step one." in text
    assert "Step two." in text


def test_B6_owner_queue_orders_by_unmerged_wp_count_then_age() -> None:
    statuses = (
        _status("WP-2.1", "IN-BUILD"),
        _status("WP-2.2", "NOT-STARTED"),
        _status("WP-2.3", "MERGED"),
    )
    blockers = (
        _blocker("BLK-2.1-01", raised="2026-10-01", unblocks="WP-2.1"),
        _blocker("BLK-2.1-02", raised="2026-10-05", unblocks="WP-2.1, WP-2.2, WP-2.3"),
        _blocker("BLK-2.3-01", raised="2026-09-01", unblocks="WP-2.3"),
        _blocker("BLK-2.2-01", raised="2026-09-20", unblocks="WP-2.1"),
        _blocker("BLK-2.2-02", status="RESOLVED", raised="2026-09-25", unblocks="WP-2.2"),
    )
    fragments = _fragments(status=statuses, blockers=blockers)
    text = render_owner_queue(fragments, on_main=True, last_digest=None)
    order = [line for line in text.splitlines() if line.startswith("### BLK-")]
    assert order == ["### BLK-2.1-02", "### BLK-2.2-01", "### BLK-2.1-01", "### BLK-2.3-01"]
    assert "BLK-2.2-02" not in text


def _decision(did: str, date: str, status: str = "ACTIVE") -> DecisionFragment:
    return DecisionFragment(
        Path(f"docs/progress/decisions.d/{did}.md"),
        {"ID": did, "Status": status, "Date": date, "Question": f"Question of {did}"},
        ("A",),
        (("Weakens, skips or deletes a test", "no"),),
        "",
    )


def test_B6_owner_queue_includes_decisions_after_digest() -> None:
    decisions = (_decision("DEC-2.1-01", "2026-10-09"), _decision("DEC-2.1-02", "2026-10-11"))
    fragments = _fragments(decisions=decisions)
    text = render_owner_queue(fragments, on_main=True, last_digest="2026-10-10")
    assert "DEC-2.1-02" in text
    assert "DEC-2.1-01" not in text


def test_B6_owner_queue_all_active_decisions_without_digest() -> None:
    decisions = (_decision("DEC-2.1-01", "2026-01-01"), _decision("DEC-2.1-02", "2026-10-11", status="VETOED"))
    fragments = _fragments(decisions=decisions)
    text = render_owner_queue(fragments, on_main=True, last_digest=None)
    assert "DEC-2.1-01" in text
    assert "DEC-2.1-02" not in text


def test_B6_pending_checks_come_last() -> None:
    record = _status("WP-2.1", "MERGED")
    record = StatusFragment(record.path, record.fields, "Notes.\nPending check: run the Oracle smoke test\n")
    fragments = _fragments(status=(record,), blockers=(_blocker("BLK-2.1-01"),), decisions=(_decision("DEC-2.1-01", "2026-10-11"),))
    text = render_owner_queue(fragments, on_main=True, last_digest=None)
    blocker_pos = text.index("BLK-2.1-01")
    decision_pos = text.index("DEC-2.1-01")
    check_pos = text.index("run the Oracle smoke test")
    assert blocker_pos < decision_pos < check_pos


def test_B12_ledger_renders_fragment_fields() -> None:
    ledger = (
        LedgerFragment(
            Path("docs/outsourcing/ledger.d/WO-2.1-01.md"),
            {
                "WO": "WO-2.1-01",
                "Date": "2026-10-10",
                "Model": "gemini-3.7-flash",
                "Attempts": "2",
                "Prompt tokens": "not reported by the Jules channel",
                "Output tokens": "not reported by the Jules channel",
                "Result": "ACCEPTED",
                "Seconds": "42",
            },
            "",
        ),
    )
    tables = render_all(_fragments(ledger=ledger), on_main=False)
    text = tables[Path("docs/outsourcing/LEDGER.md")]
    assert "| WO-2.1-01 | 2026-10-10 | gemini-3.7-flash |" in text
    assert "not reported by the Jules channel" in text
    assert "| ACCEPTED | 42 |" in text


def test_B10_rendering_is_deterministic() -> None:
    fragments = _fragments(
        status=(_status("WP-2.1", "IN-BUILD"), _status("WP-1.9", "MERGED")),
        blockers=(_blocker("BLK-2.1-02"), _blocker("BLK-2.1-01", raised="2026-10-01")),
        debt=(_new_debt(), _legacy_debt("| DEBT-001 | f | w | r | a | WP-0.9 | OPEN |")),
        decisions=(_decision("DEC-2.1-01", "2026-10-10"),),
    )
    first = render_all(fragments, on_main=True)
    second = render_all(fragments, on_main=True)
    assert first == second
    debt_lines = [line for line in first[Path("docs/progress/DEBT.md")].splitlines() if line.startswith("| DEBT")]
    assert [line.split("|")[1].strip() for line in debt_lines] == ["DEBT-001", "DEBT-2.1-01"]


def test_B4_empty_fragments_render_headers_only() -> None:
    tables = render_all(_fragments(), on_main=True)
    assert tables[Path("docs/progress/STATUS.md")] == GENERATED_LINE + STATUS_HEADER
    assert tables[Path("docs/progress/DEBT.md")] == GENERATED_LINE + DEBT_HEADER


def test_B4_wp_sort_key_handles_non_wp_names_last() -> None:
    assert wp_sort_key("WP-1.9") < wp_sort_key("WP-1.10")
    assert wp_sort_key("WP-1.10") < wp_sort_key("other")
