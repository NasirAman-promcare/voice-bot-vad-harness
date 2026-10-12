"""Unit tests for tools/progress/migrate.py.

CAPABILITIES:
  CAP-PROGRESS-008: convert legacy tables into fragments without losing a word or an ID
INPUTS AND OUTPUTS: scratch repositories built in tmp_path.
CONTRACTS: fragment formats v1; legacy table layout v1.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness.
NOT IN SCOPE:
  - Acceptance tests.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 5 created.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.progress.fragments import load_all
from tools.progress.migrate import MigrationError, migrate, plan
from tools.progress.render import render_all

STATUS = (
    "# Work package status\n"
    "\n"
    "Intro line.\n"
    "\n"
    "| WP | Title | Status | Branch / PR | Updated |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| WP-0.0 | Guardrails and audit tooling | MERGED | claude/hopeful-noether-yinc4e, "
    "PR https://github.com/x/y/pull/1 | 2026-09-27 |\n"
    "| WP-0.9 | Phase 0 review | MERGED | claude/great-heisenberg-h85gm9, "
    "PR https://github.com/x/y/pull/10 | 2026-10-08 |\n"
)

BLOCKERS = (
    "# Blockers\n"
    "\n"
    "Intro.\n"
    "\n"
    "<!-- entries start below -->\n"
    "\n"
    "## BLK-001 — first blocker\n"
    "STATUS: RESOLVED\n"
    "WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_x\n"
    "\n"
    "**What I need:** a thing.\n"
    "\n"
    "**Owner answer:** done.\n"
    "\n"
    "## BLK-010 — open blocker without an answer\n"
    "STATUS: OPEN\n"
    "WP: WP-0.7  ·  Raised: 2026-09-30  ·  Session: https://claude.ai/code/session_y\n"
    "\n"
    "**What I need:** a decision.\n"
    "\n"
    "**Owner answer:**\n"
)

DEBT = (
    "# Accepted debt\n"
    "\n"
    "Intro.\n"
    "\n"
    "| ID | From finding | What is limited or untested | Risk if it breaks | Accepted in | Target WP | Status |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
    "| DEBT-001 | WP-0.0-F48 | limited thing | some risk | `docs/approvals/WP-0.0.md` | WP-0.9 | "
    "CLOSED in WP-0.9 (details) |\n"
    "| DEBT-027 | WP-0.1 approval | latency estimates | wrong timing | `docs/approvals/WP-0.1.md` | "
    "Phase 2 VAD timing work | OPEN |\n"
)


def _repo(tmp_path: Path, status: str = STATUS, blockers: str = BLOCKERS, debt: str = DEBT) -> Path:
    for rel, text in (
        ("docs/progress/STATUS.md", status),
        ("docs/progress/BLOCKERS.md", blockers),
        ("docs/progress/DEBT.md", debt),
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_B8_status_rows_become_fragments(tmp_path: Path) -> None:
    _repo(tmp_path)
    report = migrate(tmp_path, dry_run=False)
    fragment = (tmp_path / "docs/progress/status.d/WP-0.0.md").read_text(encoding="utf-8")
    assert fragment == (
        "WP: WP-0.0\nTitle: Guardrails and audit tooling\nStatus: MERGED\n"
        "Branch: claude/hopeful-noether-yinc4e\nPR: https://github.com/x/y/pull/1\n"
        "Updated: 2026-09-27\nLegacy: yes\n"
    )
    assert Path("docs/progress/status.d/WP-0.9.md") in report.created


def test_B8_status_branch_pr_split(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    loaded = load_all(tmp_path)
    assert len(loaded.status) == 2
    record = next(r for r in loaded.status if r.fields["WP"] == "WP-0.9")
    assert record.fields["Branch"] == "claude/great-heisenberg-h85gm9"
    assert record.fields["PR"] == "https://github.com/x/y/pull/10"
    assert record.fields["Legacy"] == "yes"


def test_B8_blocker_entries_keep_text_verbatim(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    fragment = (tmp_path / "docs/progress/blockers.d/BLK-001.md").read_text(encoding="utf-8")
    entry = (
        "## BLK-001 — first blocker\n"
        "STATUS: RESOLVED\n"
        "WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_x\n"
        "\n"
        "**What I need:** a thing.\n"
        "\n"
        "**Owner answer:** done."
    )
    assert entry in fragment
    assert fragment.startswith("ID: BLK-001\nStatus: RESOLVED\nWP: WP-0.0\nOwner capability: legacy\nLegacy: yes\n\n")


def test_B8_blocker_status_from_entry(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    loaded = load_all(tmp_path)
    blockers = {record.fields["ID"]: record for record in loaded.blockers}
    assert blockers["BLK-001"].fields["Status"] == "RESOLVED"
    assert blockers["BLK-010"].fields["Status"] == "OPEN"
    assert blockers["BLK-010"].fields["Owner capability"] == "legacy"


def test_B8_blocker_open_with_empty_owner_answer_stays_open(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    fragment = (tmp_path / "docs/progress/blockers.d/BLK-010.md").read_text(encoding="utf-8")
    assert "Status: OPEN\n" in fragment
    assert fragment.rstrip("\n").endswith("**Owner answer:**")


def test_B8_debt_rows_become_legacy_fragments(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    fragment = (tmp_path / "docs/progress/debt.d/DEBT-001.md").read_text(encoding="utf-8")
    row = next(line for line in DEBT.splitlines() if line.startswith("| DEBT-001 |"))
    assert fragment.splitlines() == [
        "ID: DEBT-001",
        "Status: CLOSED",
        "Target WP: WP-0.9",
        "Legacy: yes",
        "",
        row,
    ]


def test_B8_debt_status_is_first_word_of_cell(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    loaded = load_all(tmp_path)
    rows = {record.fields["ID"]: record for record in loaded.debt}
    assert rows["DEBT-001"].fields["Status"] == "CLOSED"
    assert rows["DEBT-027"].fields["Status"] == "OPEN"
    assert rows["DEBT-027"].fields["Target WP"] == "Phase 2 VAD timing work"


def test_B8_dry_run_creates_nothing(tmp_path: Path) -> None:
    _repo(tmp_path)
    report = migrate(tmp_path, dry_run=True)
    assert report.dry_run
    assert not (tmp_path / "docs/progress/status.d").exists()
    assert not (tmp_path / "docs/progress/blockers.d").exists()
    assert not (tmp_path / "docs/progress/debt.d").exists()
    assert len(report.created) == 6
    summary = report.summary()
    for fragment_id in ("WP-0.0", "WP-0.9", "BLK-001", "BLK-010", "DEBT-001", "DEBT-027"):
        assert fragment_id in summary
    assert "would create" in summary


def test_B8_real_run_refuses_when_a_target_exists(tmp_path: Path) -> None:
    _repo(tmp_path)
    path = tmp_path / "docs/progress/debt.d/DEBT-001.md"
    path.parent.mkdir(parents=True)
    path.write_text("ID: DEBT-001\n", encoding="utf-8")
    with pytest.raises(MigrationError) as excinfo:
        migrate(tmp_path, dry_run=False)
    assert "debt.d/DEBT-001.md" in str(excinfo.value)
    assert path.read_text(encoding="utf-8") == "ID: DEBT-001\n"
    assert not (tmp_path / "docs/progress/debt.d/DEBT-027.md").exists()
    assert not (tmp_path / "docs/progress/blockers.d/BLK-001.md").exists()


def test_B8_dry_run_still_reports_when_a_target_exists(tmp_path: Path) -> None:
    _repo(tmp_path)
    path = tmp_path / "docs/progress/debt.d/DEBT-001.md"
    path.parent.mkdir(parents=True)
    path.write_text("ID: DEBT-001\n", encoding="utf-8")
    report = migrate(tmp_path, dry_run=True)
    assert Path("docs/progress/debt.d/DEBT-001.md") in report.created
    assert path.read_text(encoding="utf-8") == "ID: DEBT-001\n"


def test_B8_report_lists_every_id(tmp_path: Path) -> None:
    _repo(tmp_path)
    report = migrate(tmp_path, dry_run=False)
    names = [path.name for path in report.created]
    assert names == [
        "WP-0.0.md",
        "WP-0.9.md",
        "BLK-001.md",
        "BLK-010.md",
        "DEBT-001.md",
        "DEBT-027.md",
    ]


def test_B8_missing_legacy_file_is_an_error(tmp_path: Path) -> None:
    _repo(tmp_path, debt="")
    (tmp_path / "docs/progress/DEBT.md").unlink()
    with pytest.raises(MigrationError) as excinfo:
        plan(tmp_path)
    assert "DEBT.md" in str(excinfo.value)


def test_B8_debt_row_without_open_or_closed_is_an_error(tmp_path: Path) -> None:
    bad = DEBT.replace("| OPEN |", "| PENDING |")
    _repo(tmp_path, debt=bad)
    with pytest.raises(MigrationError) as excinfo:
        plan(tmp_path)
    assert "DEBT-027" in str(excinfo.value)


def test_B11_round_trip_renders_legacy_files_byte_for_byte(tmp_path: Path) -> None:
    _repo(tmp_path)
    migrate(tmp_path, dry_run=False)
    tables = render_all(load_all(tmp_path), on_main=True)
    status_legacy = STATUS.replace("| --- | --- | --- | --- | --- |\n", "")
    # The rendered table keeps the legacy header constant and re-emits the rows.
    assert tables[Path("docs/progress/STATUS.md")].endswith(
        "| WP-0.0 | Guardrails and audit tooling | MERGED | claude/hopeful-noether-yinc4e, "
        "PR https://github.com/x/y/pull/1 | 2026-09-27 |\n"
        "| WP-0.9 | Phase 0 review | MERGED | claude/great-heisenberg-h85gm9, "
        "PR https://github.com/x/y/pull/10 | 2026-10-08 |"
    )  # Claude, 2026-10-12: like the legacy STATUS.md, the table ends without a newline (B11 round trip)
    blockers_text = tables[Path("docs/progress/BLOCKERS.md")]
    assert "## BLK-001 — first blocker\nSTATUS: RESOLVED\n" in blockers_text
    assert "**Owner answer:**\n" in blockers_text or blockers_text.rstrip("\n").endswith("**Owner answer:**")
    debt_text = tables[Path("docs/progress/DEBT.md")]
    for legacy_id in ("DEBT-001", "DEBT-027"):
        row = next(line for line in DEBT.splitlines() if line.startswith(f"| {legacy_id} |"))
        assert row in debt_text.splitlines()
    assert status_legacy.count("| WP-") == tables[Path("docs/progress/STATUS.md")].count("| WP-")
