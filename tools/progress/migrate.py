"""One-time migration of the legacy progress tables into fragment files.

CAPABILITIES:
  CAP-PROGRESS-008: convert STATUS.md rows, BLOCKERS.md entries and DEBT.md rows into fragments
    [tests: test_B8_status_rows_become_fragments, test_B8_status_branch_pr_split,
    test_B8_blocker_entries_keep_text_verbatim, test_B8_blocker_status_from_entry,
    test_B8_blocker_open_with_empty_owner_answer_stays_open, test_B8_debt_rows_become_legacy_fragments,
    test_B8_debt_status_is_first_word_of_cell, test_B8_dry_run_creates_nothing,
    test_B8_real_run_refuses_when_a_target_exists, test_B8_report_lists_every_id,
    test_B11_round_trip_renders_legacy_files_byte_for_byte]
INPUTS AND OUTPUTS: reads docs/progress/STATUS.md, BLOCKERS.md, DEBT.md; writes docs/progress/status.d,
  blockers.d and debt.d fragments (unless dry_run); returns a MigrationReport.
CONTRACTS: fragment formats v1 (docs/process/templates/FRAGMENTS.md, BLOCKER.md); legacy table layout v1.
INVARIANTS:
  - Legacy text is carried over verbatim; migration never alters it.
  - A real run refuses when any target file exists and writes nothing then.
  - A dry run writes nothing.
  - Every legacy ID is kept.
NOT IN SCOPE:
  - Parsing fragments, linting, rendering and ID allocation (separate modules).
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 5 created.
  2026-10-12 WP-1.0 WO-1.0-04 fix 1: restructured the entry-heading match so no type-check suppression is needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["MigrationError", "MigrationReport", "migrate"]

STATUS_PATH = Path("docs/progress/STATUS.md")
BLOCKERS_PATH = Path("docs/progress/BLOCKERS.md")
DEBT_PATH = Path("docs/progress/DEBT.md")

_STATUS_ROW = re.compile(r"^\| (WP-\d+\.\d+) \| (.*?) \| ([A-Z-]+) \| (.*?) \| (\d{4}-\d{2}-\d{2}) \|\s*$")
_BRANCH_PR = re.compile(r"^(.*?), PR (https://\S+)$")
_BLOCKER_HEADING = re.compile(r"^## (BLK-\d+) ")
_BLOCKER_STATUS = re.compile(r"^STATUS: ([A-Z-]+)\s*$", re.M)
_BLOCKER_WP = re.compile(r"^WP: (WP-\d+\.\d+)", re.M)
_DEBT_ROW = re.compile(r"^\| (DEBT-\d+) \|")


class MigrationError(Exception):
    """The migration cannot run; the message says what failed and what to do."""


@dataclass(frozen=True)
class MigrationReport:
    """What a migration run created or would create."""

    created: tuple[Path, ...]
    dry_run: bool

    def summary(self) -> str:
        verb = "would create" if self.dry_run else "created"
        lines = [f"{verb} {path.as_posix()}" for path in self.created]
        return "\n".join(lines)


def _read(repo_root: Path, rel: Path) -> str:
    path = repo_root / rel
    if not path.is_file():
        raise MigrationError(f"{rel.as_posix()} is missing; nothing to migrate. Restore the legacy file first.")
    return path.read_text(encoding="utf-8")


def _status_fragments(text: str) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = _STATUS_ROW.match(line.rstrip())
        if not match:
            continue
        wp, title, status, branch_pr, updated = match.groups()
        branch, pull = branch_pr, "none"
        split = _BRANCH_PR.match(branch_pr)
        if split:
            branch, pull = split.group(1), split.group(2)
        body = (
            f"WP: {wp}\nTitle: {title}\nStatus: {status}\nBranch: {branch}\nPR: {pull}\n"
            f"Updated: {updated}\nLegacy: yes\n"
        )
        fragments.append((f"docs/progress/status.d/{wp}.md", body))
    return fragments


def _entry_ranges(lines: list[str]) -> list[tuple[str, int, int]]:
    """Return (block ID, start line index, end line index) for each blocker entry."""
    heads: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = _BLOCKER_HEADING.match(line)
        if match:
            heads.append((match.group(1), index))
    ranges: list[tuple[str, int, int]] = []
    for position, (block_id, start) in enumerate(heads):
        end = heads[position + 1][1] if position + 1 < len(heads) else len(lines)
        ranges.append((block_id, start, end))
    return ranges


def _blocker_fragments(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines(keepends=True)
    fragments: list[tuple[str, str]] = []
    for block_id, start, end in _entry_ranges(lines):
        entry = "".join(lines[start:end]).rstrip("\n")
        status_match = _BLOCKER_STATUS.search(entry)
        wp_match = _BLOCKER_WP.search(entry)
        if status_match is None or wp_match is None:
            raise MigrationError(
                f"{BLOCKERS_PATH.as_posix()}: entry {block_id} lacks a STATUS: or WP: line; "
                "fix the legacy entry before migrating."
            )
        body = (
            f"ID: {block_id}\nStatus: {status_match.group(1)}\nWP: {wp_match.group(1)}\n"
            f"Owner capability: legacy\nLegacy: yes\n\n{entry}\n"
        )
        fragments.append((f"docs/progress/blockers.d/{block_id}.md", body))
    return fragments


def _debt_fragments(text: str) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not _DEBT_ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        debt_id, status_cell, target_wp = cells[0], cells[6], cells[5]
        status = status_cell.split()[0] if status_cell else ""
        if status not in ("OPEN", "CLOSED"):
            raise MigrationError(
                f"{DEBT_PATH.as_posix()}: row {debt_id} has a Status cell that starts with neither OPEN nor "
                f"CLOSED ({status_cell!r}); fix the legacy row before migrating."
            )
        body = f"ID: {debt_id}\nStatus: {status}\nTarget WP: {target_wp}\nLegacy: yes\n\n{line}\n"
        fragments.append((f"docs/progress/debt.d/{debt_id}.md", body))
    return fragments


def plan(repo_root: Path) -> list[tuple[str, str]]:
    """Compute every fragment (relative path, content) the legacy files produce."""
    fragments: list[tuple[str, str]] = []
    fragments += _status_fragments(_read(repo_root, STATUS_PATH))
    fragments += _blocker_fragments(_read(repo_root, BLOCKERS_PATH))
    fragments += _debt_fragments(_read(repo_root, DEBT_PATH))
    return fragments


def migrate(repo_root: Path, dry_run: bool) -> MigrationReport:
    """Migrate the legacy tables into fragments; a dry run reports without writing."""
    planned = plan(repo_root)
    existing = sorted(rel for rel, _ in planned if (repo_root / rel).exists())
    if existing and not dry_run:
        names = "\n".join(f"  {rel}" for rel in existing)
        raise MigrationError(
            f"refusing to migrate; these target files already exist:\n{names}\n"
            "Remove them (or move them aside) and run migrate again."
        )
    if not dry_run:
        for rel, body in planned:
            path = repo_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
    return MigrationReport(created=tuple(Path(rel) for rel, _ in planned), dry_run=dry_run)
