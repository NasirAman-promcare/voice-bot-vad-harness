"""Evaluate the seven merge-gate criteria from facts alone; pure functions only.

CAPABILITIES:
  CAP-AUTONOMY-301: evaluate C1 (audit), C2 (CI), C3 (fresh base), C4 (blockers and findings),
    C5 (paths), C6 (blocking owner-run checks) and C7 (status) from a Facts bundle
    [tests: test_FR_1_0_05_c1_head_audited_passes, test_FR_1_0_05_c1_missing_audit_fails,
    test_FR_1_0_05_c1_fail_verdict_fails, test_FR_1_0_05_c1_audited_not_ancestor_fails,
    test_FR_1_0_05_c1_later_code_commit_fails, test_FR_1_0_05_c1_later_record_only_passes,
    test_FR_1_0_05_c2_all_green_passes, test_FR_1_0_05_c2_check_run_pending_fails,
    test_FR_1_0_05_c2_check_run_failed_fails, test_FR_1_0_05_c2_check_run_skipped_optional_passes,
    test_FR_1_0_05_c2_combined_status_pending_fails, test_FR_1_0_05_c2_combined_status_failure_fails,
    test_FR_1_0_05_c2_no_statuses_passes, test_FR_1_0_05_c3_branch_contains_main_passes,
    test_FR_1_0_05_c3_branch_behind_main_fails, test_FR_1_0_05_c4_clean_passes,
    test_FR_1_0_05_c4_open_blocker_fails, test_FR_1_0_05_c4_open_critical_fails,
    test_FR_1_0_05_c4_major_open_fails, test_FR_1_0_05_c4_major_accepted_by_debt_passes,
    test_FR_1_0_05_c4_major_accepted_by_decision_passes, test_FR_1_0_05_c4_major_acceptance_for_other_finding_fails,
    test_FR_1_0_05_c5_no_protected_changes_passes, test_FR_1_0_05_c5_never_path_fails,
    test_FR_1_0_05_c5_guarded_allowed_by_spec_passes, test_FR_1_0_05_c5_guarded_allowed_by_glob_passes,
    test_FR_1_0_05_c5_guarded_allowed_by_approval_passes, test_FR_1_0_05_c5_guarded_unmatched_fails,
    test_FR_1_0_05_c5_none_means_no_allowance, test_FR_1_0_05_c5_star_glob_stays_within_one_folder,
    test_FR_1_0_05_c6_no_blocking_checks_passes,
    test_FR_1_0_05_c6_blocking_check_passing_passes, test_FR_1_0_05_c6_blocking_check_missing_fails,
    test_FR_1_0_05_c7_audit_pass_passes, test_FR_1_0_05_c7_other_status_fails,
    test_FR_1_0_05_c7_missing_status_fails, test_FR_1_0_05_evaluate_returns_all_seven_in_order]
INPUTS AND OUTPUTS: evaluate(facts: Facts) -> list[CriterionResult] for C1..C7 in order.
CONTRACTS: AUTONOMY.md "Merge gate criteria"; PROTECTED_PATHS.txt glob rules
  ("**" matches any depth, "*" matches within one folder).
INVARIANTS:
  - Pure: no I/O, no subprocess, no clock; the same facts always give the same results.
  - All seven criteria are evaluated every time, even after failures.
  - C3 carries exit_code 2 so the caller knows to update the branch; other failures carry 3.
NOT IN SCOPE:
  - Gathering facts (facts.py), GitHub access (github.py), the command line (merge_gate.py).
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 4 created.
  2026-10-10 WO-1.0-05 fix 1: fnmatch lets "*" cross "/" so "bots/*" wrongly matched
    "bots/deep/x.py"; guarded-edit patterns now follow the PROTECTED_PATHS.txt glob rules
    via a segment-wise matcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.autonomy.facts import Facts

__all__ = ["CriterionResult", "evaluate"]

_RECORD_PREFIXES = ("docs/progress/status.d/", "docs/progress/blockers.d/", "docs/progress/debt.d/",
                    "docs/progress/decisions.d/", "docs/outsourcing/ledger.d/")
_CRITERION_IDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7")


@dataclass(frozen=True)
class CriterionResult:
    """The outcome of one merge-gate criterion."""

    id: str
    passed: bool
    reason: str
    exit_code: int = 3


def _is_record_path(path: str) -> bool:
    """True when a path is a record-only location: a fragment folder (the WP folder is added by the caller)."""
    return any(path.startswith(prefix) for prefix in _RECORD_PREFIXES)


def _is_record_only_commit(facts: Facts, commit: object) -> bool:
    """True when every changed path of a commit is a record-only location for this WP."""
    wp_prefix = f"docs/progress/{facts.wp}/"
    paths = getattr(commit, "paths")
    return all(path.startswith(wp_prefix) or _is_record_path(path) for path in paths)


def _check_audit(facts: Facts) -> CriterionResult:
    """C1: the audit verdict is PASS for head or for an ancestor followed only by record commits."""
    if not facts.audit_exists:
        return CriterionResult("C1", False, f"no audit report at docs/progress/{facts.wp}/AUDIT.md")
    if facts.audit_verdict != "PASS":
        return CriterionResult("C1", False, f"audit verdict is {facts.audit_verdict or 'missing'}, not PASS")
    if facts.audited_sha is None:
        return CriterionResult("C1", False, "audit report names no commit")
    if not facts.audited_is_ancestor:
        return CriterionResult("C1", False,
                               f"audited commit {facts.audited_sha[:12]} is not an ancestor of head")
    if facts.audited_sha != facts.head_sha:
        wp_prefix = f"docs/progress/{facts.wp}/"
        for commit in facts.later_commits:
            if not _is_record_only_commit(facts, commit):
                non_record = [p for p in getattr(commit, "paths")
                              if not p.startswith(wp_prefix) and not _is_record_path(p)]
                return CriterionResult("C1", False,
                                       f"commit {getattr(commit, 'sha')[:12]} after the audit touches "
                                       f"non-record path {non_record[0]}")
        return CriterionResult("C1", True,
                               f"audit PASS on {facts.audited_sha[:12]}; later commits are record-only")
    return CriterionResult("C1", True, f"audit PASS on head {facts.head_sha[:12]}")


def _check_ci(facts: Facts) -> CriterionResult:
    """C2: every check run completed with success (skipped allowed) and the status is success or absent."""
    for run in facts.check_runs:
        name = run.get("name", "<unnamed>")
        status = run.get("status")
        if status != "completed":
            return CriterionResult("C2", False, f"check run {name} is {status}, not completed")
        conclusion = run.get("conclusion")
        if conclusion in ("success", "skipped"):
            continue
        return CriterionResult("C2", False, f"check run {name} concluded {conclusion or 'with nothing'}")
    state = facts.combined_status.get("state")
    statuses = facts.combined_status.get("statuses") or []
    if not statuses:
        return CriterionResult("C2", True, f"{len(facts.check_runs)} check runs green; no commit statuses")
    if state != "success":
        return CriterionResult("C2", False, f"combined status is {state}")
    return CriterionResult("C2", True, f"{len(facts.check_runs)} check runs and combined status green")


def _check_fresh_base(facts: Facts) -> CriterionResult:
    """C3: the branch contains the current origin/main; failure carries exit code 2."""
    if facts.branch_contains_origin_main:
        return CriterionResult("C3", True, f"branch contains origin/main {facts.origin_main_sha[:12]}")
    return CriterionResult("C3", False,
                           f"branch does not contain origin/main {facts.origin_main_sha[:12]}; "
                           "update the branch", exit_code=2)


def _finding_accepted(facts: Facts, finding_id: str) -> bool:
    """True when an open debt fragment or a decision record accepts the finding."""
    for fragment in facts.fragments.debt:
        if (fragment.fields.get("Status", "").upper() == "OPEN"
                and fragment.fields.get("Source", "").strip() == finding_id):
            return True
    for fragment in facts.fragments.decisions:
        if finding_id in fragment.free_text:
            return True
    return False


def _check_findings(facts: Facts) -> CriterionResult:
    """C4: no open blocker for the WP, no open CRITICAL, every MAJOR fixed or accepted."""
    if facts.open_blockers:
        return CriterionResult("C4", False,
                               f"open blocker for {facts.wp}: {', '.join(facts.open_blockers)}")
    for row in facts.critical_findings:
        if row.state == "open":
            return CriterionResult("C4", False, f"open CRITICAL finding {row.finding_id}")
    for row in facts.major_findings:
        if row.state in ("fixed", "accepted as debt"):
            continue
        if _finding_accepted(facts, row.finding_id):
            continue
        return CriterionResult("C4", False, f"MAJOR finding {row.finding_id} neither fixed nor accepted")
    return CriterionResult("C4", True, "no open blockers or unaccepted findings")


def _glob_match(pattern: str, path: str) -> bool:
    """Match a PROTECTED_PATHS.txt glob: "**" crosses folders, "*" stays within one folder."""
    pat_parts = [part for part in pattern.split("/") if part != ""]
    path_parts = [part for part in path.split("/") if part != ""]
    return _match_parts(pat_parts, path_parts)


def _match_parts(pat: list[str], path: list[str]) -> bool:
    if not pat:
        return not path
    head, rest = pat[0], pat[1:]
    if head == "**":
        return _match_parts(rest, path) or (bool(path) and _match_parts(pat, path[1:]))
    if not path:
        return False
    return _segment_match(head, path[0]) and _match_parts(rest, path[1:])


def _segment_match(pattern: str, name: str) -> bool:
    """Match one path segment where "*" and "?" never cross the folder boundary."""
    if not pattern:
        return not name
    head = pattern[0]
    if head == "*":
        return _segment_match(pattern[1:], name) or (bool(name) and _segment_match(pattern, name[1:]))
    if head == "?":
        return bool(name) and _segment_match(pattern[1:], name[1:])
    return bool(name) and name[0] == head and _segment_match(pattern[1:], name[1:])


def _check_paths(facts: Facts) -> CriterionResult:
    """C5: no NEVER path changed; guarded paths changed only where the spec or an approval allows."""
    for changed in facts.diff_paths:
        if changed.protected_class == "NEVER":
            return CriterionResult("C5", False, f"NEVER path changed: {changed.path}")
    patterns = facts.allowed_guarded_edits + facts.approvals_allow_edits
    for changed in facts.diff_paths:
        if changed.protected_class == "GUARDED" and not any(
                _glob_match(pattern, changed.path) for pattern in patterns):
            return CriterionResult("C5", False,
                                   f"guarded path {changed.path} not allowed by the spec or an approval")
    guarded = sum(1 for changed in facts.diff_paths if changed.protected_class == "GUARDED")
    return CriterionResult("C5", True, f"no NEVER paths changed; {guarded} guarded changes allowed")


def _check_owner_checks(facts: Facts) -> CriterionResult:
    """C6: every blocking owner-run check has a committed PASS report."""
    if not facts.spec_exists:
        return CriterionResult("C6", False, f"no spec on origin/main for {facts.wp}")
    for check in facts.blocking_checks:
        if not check.passed:
            return CriterionResult("C6", False,
                                   f"blocking check {check.check_id} has no committed PASS report")
    return CriterionResult("C6", True, f"{len(facts.blocking_checks)} blocking checks reported PASS")


def _check_status(facts: Facts) -> CriterionResult:
    """C7: the WP's status fragment says AUDIT-PASS."""
    if facts.status_state is None:
        return CriterionResult("C7", False, f"no status fragment for {facts.wp}")
    if facts.status_state != "AUDIT-PASS":
        return CriterionResult("C7", False, f"status is {facts.status_state}, not AUDIT-PASS")
    return CriterionResult("C7", True, "status fragment says AUDIT-PASS")


def evaluate(facts: Facts) -> list[CriterionResult]:
    """Evaluate criteria C1 to C7 from the facts; all seven results, in order, every time."""
    results = [_check_audit(facts), _check_ci(facts), _check_fresh_base(facts), _check_findings(facts),
               _check_paths(facts), _check_owner_checks(facts), _check_status(facts)]
    if tuple(result.id for result in results) != _CRITERION_IDS:
        raise AssertionError("criterion order drifted from C1..C7")
    return results
