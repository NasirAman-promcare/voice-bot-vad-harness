"""Validate progress fragments and report lint issues.

CAPABILITIES:
  CAP-PROGRESS-004: lint fragment records against IDs, statuses and required fields
    [tests: test_B2_status_values_are_validated, test_B2_blocker_required_fields_and_capability,
    test_B2_decision_required_fields_and_cannot_do, test_B2_debt_required_fields,
    test_B2_legacy_id_requires_legacy_marker, test_B2_new_id_pattern_is_enforced,
    test_B2_duplicate_ids_name_both_paths, test_B2_id_must_match_file_name,
    test_E4_unknown_wp_status_is_a_warning, test_B2_legacy_owner_capability_only_with_legacy_marker,
    test_B2_blocker_label_belongs_to_following_lines]
INPUTS AND OUTPUTS: fragment records from tools.progress.fragments; returns LintIssue records.
CONTRACTS: fragment formats v1 (docs/process/templates/FRAGMENTS.md, BLOCKER.md, DECISION.md).
INVARIANTS:
  - Lint never writes to the repository.
  - Lint output order is deterministic.
NOT IN SCOPE:
  - Rendering, migration and ID allocation (separate modules).
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 2 created.
  2026-10-12 WP-1.0 WO-1.0-04 (Claude, FIX-WO04-final): migrated legacy blockers skip the new template checks; `spec_wps` gives the E4 warning.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from tools.progress.fragments import BlockerFragment, DebtFragment, DecisionFragment, Fragments, StatusFragment

__all__ = ["LintIssue", "lint"]

_VALID_STATUS = {
    "NOT-STARTED",
    "PLANNED",
    "IN-BUILD",
    "READY-FOR-AUDIT",
    "AUDIT-FAIL",
    "AUDIT-PASS",
    "MERGE-READY",
    "MERGED",
    "OWNER-RUN",
    "BLOCKED",
}
_BLOCKER_STATUS = {"OPEN", "RESOLVED"}
_DECISION_STATUS = {"ACTIVE", "VETOED", "SUPERSEDED"}
_DEBT_STATUS = {"OPEN", "CLOSED"}
_LEDGER_RESULT = {"ACCEPTED", "EXHAUSTED", "QUESTIONS", "REJECTED"}
_OWNER_CAPABILITIES = {"ACCESS", "COMPUTE", "EXTERNAL-AI", "DECISION", "PHYSICAL", "KIT"}
_ID_KINDS = ("BLK", "DEC", "DEBT", "WO")
_ID_RE = re.compile(r"^(BLK|DEC|DEBT|WO)-\d+\.\d+-\d{2}$")
_LEGACY_ID_RE = re.compile(r"^(BLK|DEBT)-\d{3}$")


@dataclass(frozen=True)
class LintIssue:
    """One lint finding with severity and the fragment it names."""

    severity: str  # "error" or "warning"
    path: Path
    message: str


def lint(
    fragments: Fragments, changed_only_paths: set[Path] | None = None, spec_wps: set[str] | None = None
) -> list[LintIssue]:
    """Validate fragments and return lint issues in a deterministic order.

    With spec_wps (the WPs that have a spec), a status fragment for any other WP is a warning (E4)."""
    issues: list[LintIssue] = []
    for record in fragments.status if spec_wps is not None else ():
        wp = record.fields.get("WP", "")
        if wp and wp not in spec_wps and _include(record.path, changed_only_paths):
            issues.append(LintIssue("warning", record.path, f"{wp} has no spec under docs/specs/"))
    issues.extend(_lint_status(fragments.status, changed_only_paths))
    issues.extend(_lint_blockers(fragments.blockers, changed_only_paths))
    issues.extend(_lint_debt(fragments.debt, changed_only_paths))
    issues.extend(_lint_decisions(fragments.decisions, changed_only_paths))
    issues.extend(_lint_ledger(fragments.ledger, changed_only_paths))
    issues.extend(_lint_uniqueness(fragments))
    return sorted(issues, key=lambda issue: (issue.path.as_posix(), issue.severity, issue.message))


def _include(path: Path, changed_only_paths: set[Path] | None) -> bool:
    return changed_only_paths is None or path in changed_only_paths


def _fragment_id(kind: str, path: Path, fields: dict[str, str]) -> str | None:
    if kind in {"BLK", "DEBT", "DEC"}:
        return fields.get("ID") or path.stem
    return None


def _lint_status(records: tuple[StatusFragment, ...], changed_only: set[Path] | None) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for record in records:
        if not _include(record.path, changed_only):
            continue
        status = record.fields.get("Status", "")
        if status and status not in _VALID_STATUS:
            issues.append(LintIssue("error", record.path, f"Status must be one of {sorted(_VALID_STATUS)}"))
    return issues


def _lint_blockers(records: tuple[BlockerFragment, ...], changed_only: set[Path] | None) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for record in records:
        if not _include(record.path, changed_only):
            continue
        legacy = record.fields.get("Legacy") == "yes"
        capability = record.fields.get("Owner capability", "")
        if capability == "legacy":
            if not legacy:
                issues.append(
                    LintIssue("error", record.path, "Owner capability 'legacy' is allowed only on legacy fragments")
                )
        elif capability not in _OWNER_CAPABILITIES:
            issues.append(
                LintIssue("error", record.path, "Owner capability must be one of " + ", ".join(sorted(_OWNER_CAPABILITIES)))
            )
        status = record.fields.get("Status", "")
        if status and status not in _BLOCKER_STATUS:
            issues.append(LintIssue("error", record.path, "Status must be OPEN or RESOLVED"))
        for field in () if legacy else ("Time needed", "Meanwhile", "Unblocks"):
            if not record.fields.get(field):
                issues.append(LintIssue("error", record.path, f"Missing required field: {field}"))
        if not legacy and not 1 <= len(record.steps) <= 7:
            issues.append(LintIssue("error", record.path, "Exact steps must number 1 to at most 7"))
        issues.extend(_lint_id("BLK", record.path, record.fields, legacy))
    return issues


def _lint_debt(records: tuple[DebtFragment, ...], changed_only: set[Path] | None) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for record in records:
        if not _include(record.path, changed_only):
            continue
        legacy = record.fields.get("Legacy") == "yes"
        status = record.fields.get("Status", "")
        if status and status not in _DEBT_STATUS:
            issues.append(LintIssue("error", record.path, "Status must be OPEN or CLOSED"))
        if not legacy:
            for field in ("Severity", "Source", "Target WP", "Accepted by"):
                if not record.fields.get(field):
                    issues.append(LintIssue("error", record.path, f"Missing required field: {field}"))
        else:
            if status:
                row_status = _legacy_row_status(record.free_text, record.fields.get("ID", ""))
                if row_status and row_status != status:
                    issues.append(
                        LintIssue("error", record.path, "Status field and legacy row status must agree")
                    )
        issues.extend(_lint_id("DEBT", record.path, record.fields, legacy))
    return issues


def _legacy_row_status(free_text: str, legacy_id: str) -> str | None:
    for line in free_text.splitlines():
        if line.startswith(f"| {legacy_id} |"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 7 and cells[6]:
                return cells[6].split()[0]
    return None


def _lint_decisions(records: tuple[DecisionFragment, ...], changed_only: set[Path] | None) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for record in records:
        if not _include(record.path, changed_only):
            continue
        status = record.fields.get("Status", "")
        if status and status not in _DECISION_STATUS:
            issues.append(LintIssue("error", record.path, "Status must be ACTIVE, VETOED or SUPERSEDED"))
        for field in ("Choice", "Why", "Reversal"):
            if not record.fields.get(field):
                issues.append(LintIssue("error", record.path, f"Missing required field: {field}"))
        if not record.options:
            issues.append(LintIssue("error", record.path, "Options must list at least one option"))
        if len(record.cannot_do) != 6 or any(answer != "no" for _, answer in record.cannot_do):
            issues.append(LintIssue("error", record.path, 'All six cannot-do checks must answer "no"'))
        issues.extend(_lint_id("DEC", record.path, record.fields, legacy=False))
    return issues


def _lint_ledger(records, changed_only: set[Path] | None) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for record in records:
        if not _include(record.path, changed_only):
            continue
        result = record.fields.get("Result", "")
        if result and result not in _LEDGER_RESULT:
            issues.append(LintIssue("error", record.path, "Result must be one of ACCEPTED, EXHAUSTED, QUESTIONS, REJECTED"))
        issues.extend(_lint_id("WO", record.path, record.fields, legacy=False, id_key="WO"))
    return issues


def _lint_id(
    kind: str,
    path: Path,
    fields: dict[str, str],
    legacy: bool,
    id_key: str = "ID",
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    expected = path.stem
    actual = fields.get(id_key)
    if not actual:
        issues.append(LintIssue("error", path, f"Missing required field: {id_key}"))
        return issues
    if actual != expected:
        issues.append(LintIssue("error", path, f"ID must match file name ({expected})"))
    if _ID_RE.fullmatch(actual):
        return issues
    if _LEGACY_ID_RE.fullmatch(actual):
        if not legacy:
            issues.append(LintIssue("error", path, "Legacy IDs are allowed only on fragments marked Legacy: yes"))
        return issues
    issues.append(LintIssue("error", path, f"{actual} must match <KIND>-<n>.<n>-<nn>"))
    return issues


def _lint_uniqueness(fragments: Fragments) -> list[LintIssue]:
    issues: list[LintIssue] = []
    by_id: dict[tuple[str, str], list[Path]] = {}
    for kind, records, id_key in (
        ("BLK", fragments.blockers, "ID"),
        ("DEBT", fragments.debt, "ID"),
        ("DEC", fragments.decisions, "ID"),
        ("WO", fragments.ledger, "WO"),
    ):
        for record in records:
            fragment_id = record.fields.get(id_key) or record.path.stem
            by_id.setdefault((kind, fragment_id), []).append(record.path)
    for (kind, fragment_id), paths in by_id.items():
        if len(paths) > 1:
            names = ", ".join(path.as_posix() for path in sorted(paths))
            issues.append(LintIssue("error", paths[0], f"Duplicate {kind} ID {fragment_id}: {names}"))
    return issues
