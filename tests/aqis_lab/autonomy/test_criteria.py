"""Unit tests for tools/autonomy/criteria.py over stand-in Facts bundles.

CAPABILITIES:
  CAP-AUTONOMY-302: exercise evaluate() against constructed Facts with a stand-in Fragments
    [tests: test_FR_1_0_05_c1_head_audited_passes, test_FR_1_0_05_c2_all_green_passes,
    test_FR_1_0_05_c3_branch_contains_main_passes, test_FR_1_0_05_c4_clean_passes,
    test_FR_1_0_05_c5_no_protected_changes_passes, test_FR_1_0_05_c6_no_blocking_checks_passes,
    test_FR_1_0_05_c7_audit_pass_passes, test_FR_1_0_05_evaluate_returns_all_seven_in_order]
INPUTS AND OUTPUTS: pytest fixtures and test functions; no I/O at all.
CONTRACTS: Facts as defined in tools/autonomy/facts.py; CriterionResult in tools/autonomy/criteria.py.
INVARIANTS:
  - Criteria are pure, so tests never touch git, files or the network.
  - The stand-in Facts mirrors the real dataclass fields without importing facts.py
    (a later step may still change its constructor).
NOT IN SCOPE:
  - Fact gathering (test_facts.py) and the command line (test_merge_gate.py).
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 4 created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.autonomy.criteria import evaluate

WP = "WP-9.9"
HEAD = "a" * 40
AUDITED = "b" * 40
MAIN = "c" * 40


@dataclass(frozen=True)
class StandInChangedPath:
    path: str
    protected_class: str


@dataclass(frozen=True)
class StandInLaterCommit:
    sha: str
    subject: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class StandInFindingRow:
    finding_id: str
    severity: str
    state: str
    raw: str


@dataclass(frozen=True)
class StandInBlockingCheck:
    check_id: str
    passed: bool
    report_path: str | None


@dataclass(frozen=True)
class StandInFragment:
    fields: dict[str, str]
    free_text: str = ""


@dataclass(frozen=True)
class StandInFragments:
    status: tuple = ()
    blockers: tuple = ()
    debt: tuple = ()
    decisions: tuple = ()
    ledger: tuple = ()


@dataclass(frozen=True)
class StandInFacts:
    """Mirror of facts.Facts with all-pass defaults; tests override what they exercise."""

    wp: str = WP
    repo_slug: str = "owner/scratch"
    branch: str = "claude/wp-9-9-scratch"
    head_sha: str = HEAD
    origin_main_sha: str = MAIN
    merge_base: str = MAIN
    branch_contains_origin_main: bool = True
    pull_request: dict[str, Any] | None = field(
        default_factory=lambda: {"number": 7, "title": "WP-9.9 scratch"})
    check_runs: tuple[dict[str, Any], ...] = field(
        default_factory=lambda: ({"name": "ci", "status": "completed", "conclusion": "success"},))
    combined_status: dict[str, Any] = field(
        default_factory=lambda: {"state": "success", "statuses": []})
    audit_exists: bool = True
    audit_verdict: str | None = "PASS"
    audited_sha: str | None = HEAD
    audited_is_ancestor: bool = True
    later_commits: tuple[StandInLaterCommit, ...] = ()
    open_blockers: tuple[str, ...] = ()
    critical_findings: tuple[StandInFindingRow, ...] = ()
    major_findings: tuple[StandInFindingRow, ...] = ()
    major_acceptances: tuple[str, ...] = ()
    diff_paths: tuple[StandInChangedPath, ...] = field(
        default_factory=lambda: (StandInChangedPath("tools/demo/alpha.py", "FREE"),))
    spec_exists: bool = True
    allowed_guarded_edits: tuple[str, ...] = ()
    approvals_allow_edits: tuple[str, ...] = ()
    blocking_checks: tuple[StandInBlockingCheck, ...] = ()
    status_state: str | None = "AUDIT-PASS"
    fragments: StandInFragments = field(default_factory=StandInFragments)


def by_id(facts: StandInFacts) -> dict[str, Any]:
    return {result.id: result for result in evaluate(facts)}


# ---------------------------------------------------------------- shape

def test_FR_1_0_05_evaluate_returns_all_seven_in_order():
    results = evaluate(StandInFacts(major_findings=(StandInFindingRow("WP-9.9-F01", "MAJOR", "open", "x"),)))
    assert [r.id for r in results] == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    assert all(r.reason for r in results)
    assert results[3].passed is False  # the one failing criterion does not stop the rest
    assert all(results[i].passed for i in (0, 1, 2, 4, 5, 6))


# ---------------------------------------------------------------- C1: audit

def test_FR_1_0_05_c1_head_audited_passes():
    assert by_id(StandInFacts())["C1"].passed is True


def test_FR_1_0_05_c1_missing_audit_fails():
    result = by_id(StandInFacts(audit_exists=False, audit_verdict=None, audited_sha=None))["C1"]
    assert result.passed is False
    assert "AUDIT.md" in result.reason


def test_FR_1_0_05_c1_fail_verdict_fails():
    result = by_id(StandInFacts(audit_verdict="FAIL"))["C1"]
    assert result.passed is False
    assert "FAIL" in result.reason


def test_FR_1_0_05_c1_audited_not_ancestor_fails():
    facts = StandInFacts(audited_sha=AUDITED, audited_is_ancestor=False)
    result = by_id(facts)["C1"]
    assert result.passed is False
    assert "ancestor" in result.reason


def test_FR_1_0_05_c1_later_code_commit_fails():
    later = (StandInLaterCommit(HEAD, "code", ("tools/demo/beta.py",)),)
    facts = StandInFacts(audited_sha=AUDITED, later_commits=later)
    result = by_id(facts)["C1"]
    assert result.passed is False
    assert "tools/demo/beta.py" in result.reason


def test_FR_1_0_05_c1_later_record_only_passes():
    later = (StandInLaterCommit(HEAD, "records", (f"docs/progress/{WP}/EVIDENCE.md",
                                                  "docs/progress/decisions.d/DEC-9.9-01.md",
                                                  "docs/outsourcing/ledger.d/WO-9.9-01.md")),)
    facts = StandInFacts(audited_sha=AUDITED, later_commits=later)
    assert by_id(facts)["C1"].passed is True


def test_FR_1_0_05_c1_later_mixed_commit_fails():
    later = (StandInLaterCommit(HEAD, "mixed", (f"docs/progress/{WP}/EVIDENCE.md", "bots/x.py")),)
    facts = StandInFacts(audited_sha=AUDITED, later_commits=later)
    assert by_id(facts)["C1"].passed is False


# ---------------------------------------------------------------- C2: CI

def test_FR_1_0_05_c2_all_green_passes():
    assert by_id(StandInFacts())["C2"].passed is True


def test_FR_1_0_05_c2_check_run_pending_fails():
    runs = ({"name": "ci", "status": "in_progress", "conclusion": None},)
    result = by_id(StandInFacts(check_runs=runs))["C2"]
    assert result.passed is False
    assert "in_progress" in result.reason


def test_FR_1_0_05_c2_check_run_failed_fails():
    runs = ({"name": "ci", "status": "completed", "conclusion": "failure"},)
    assert by_id(StandInFacts(check_runs=runs))["C2"].passed is False


def test_FR_1_0_05_c2_check_run_skipped_optional_passes():
    runs = ({"name": "ci", "status": "completed", "conclusion": "skipped"},)
    assert by_id(StandInFacts(check_runs=runs))["C2"].passed is True


def test_FR_1_0_05_c2_combined_status_pending_fails():
    status = {"state": "pending", "statuses": [{"context": "ci", "state": "pending"}]}
    assert by_id(StandInFacts(combined_status=status))["C2"].passed is False


def test_FR_1_0_05_c2_combined_status_failure_fails():
    status = {"state": "failure", "statuses": [{"context": "ci", "state": "failure"}]}
    assert by_id(StandInFacts(combined_status=status))["C2"].passed is False


def test_FR_1_0_05_c2_no_statuses_passes():
    assert by_id(StandInFacts(combined_status={"state": "success", "statuses": []}))["C2"].passed is True


# ---------------------------------------------------------------- C3: fresh base

def test_FR_1_0_05_c3_branch_contains_main_passes():
    result = by_id(StandInFacts())["C3"]
    assert result.passed is True
    assert result.exit_code == 3  # passing criteria never override the exit code


def test_FR_1_0_05_c3_branch_behind_main_fails():
    result = by_id(StandInFacts(branch_contains_origin_main=False))["C3"]
    assert result.passed is False
    assert result.exit_code == 2


# ---------------------------------------------------------------- C4: blockers and findings

def test_FR_1_0_05_c4_clean_passes():
    assert by_id(StandInFacts())["C4"].passed is True


def test_FR_1_0_05_c4_open_blocker_fails():
    result = by_id(StandInFacts(open_blockers=("BLK-9.9-01",)))["C4"]
    assert result.passed is False
    assert "BLK-9.9-01" in result.reason


def test_FR_1_0_05_c4_open_critical_fails():
    rows = (StandInFindingRow("WP-9.9-F01", "CRITICAL", "open", "x"),)
    assert by_id(StandInFacts(critical_findings=rows))["C4"].passed is False


def test_FR_1_0_05_c4_major_open_fails():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "open", "x"),)
    assert by_id(StandInFacts(major_findings=rows))["C4"].passed is False


def test_FR_1_0_05_c4_major_fixed_or_accepted_in_table_passes():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "fixed", "x"),
            StandInFindingRow("WP-9.9-F03", "MAJOR", "accepted as debt", "x"))
    assert by_id(StandInFacts(major_findings=rows))["C4"].passed is True


def test_FR_1_0_05_c4_major_accepted_by_debt_passes():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "open", "x"),)
    debt = StandInFragment({"ID": "DEBT-9.9-01", "Status": "OPEN", "Severity": "MAJOR",
                            "Source": "WP-9.9-F02", "Target WP": "WP-9.10"})
    facts = StandInFacts(major_findings=rows, fragments=StandInFragments(debt=(debt,)))
    assert by_id(facts)["C4"].passed is True


def test_FR_1_0_05_c4_major_accepted_by_decision_passes():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "open", "x"),)
    decision = StandInFragment({"ID": "DEC-9.9-02"}, "Accepts finding WP-9.9-F02 as debt.")
    facts = StandInFacts(major_findings=rows, fragments=StandInFragments(decisions=(decision,)))
    assert by_id(facts)["C4"].passed is True


def test_FR_1_0_05_c4_major_acceptance_for_other_finding_fails():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "open", "x"),)
    debt = StandInFragment({"ID": "DEBT-9.9-01", "Status": "OPEN", "Severity": "MAJOR",
                            "Source": "WP-9.9-F99", "Target WP": "WP-9.10"})
    facts = StandInFacts(major_findings=rows, fragments=StandInFragments(debt=(debt,)))
    assert by_id(facts)["C4"].passed is False


def test_FR_1_0_05_c4_closed_debt_does_not_accept():
    rows = (StandInFindingRow("WP-9.9-F02", "MAJOR", "open", "x"),)
    debt = StandInFragment({"ID": "DEBT-9.9-01", "Status": "CLOSED", "Severity": "MAJOR",
                            "Source": "WP-9.9-F02", "Target WP": "WP-9.10"})
    facts = StandInFacts(major_findings=rows, fragments=StandInFragments(debt=(debt,)))
    assert by_id(facts)["C4"].passed is False


# ---------------------------------------------------------------- C5: protected paths

def test_FR_1_0_05_c5_no_protected_changes_passes():
    assert by_id(StandInFacts())["C5"].passed is True


def test_FR_1_0_05_c5_never_path_fails():
    paths = (StandInChangedPath("CLAUDE.md", "NEVER"),)
    result = by_id(StandInFacts(diff_paths=paths))["C5"]
    assert result.passed is False
    assert "CLAUDE.md" in result.reason


def test_FR_1_0_05_c5_guarded_allowed_by_spec_passes():
    paths = (StandInChangedPath("bots/x.py", "GUARDED"),)
    facts = StandInFacts(diff_paths=paths, allowed_guarded_edits=("bots/x.py",))
    assert by_id(facts)["C5"].passed is True


def test_FR_1_0_05_c5_guarded_allowed_by_glob_passes():
    paths = (StandInChangedPath("bots/deep/x.py", "GUARDED"),)
    facts = StandInFacts(diff_paths=paths, allowed_guarded_edits=("bots/**",))
    assert by_id(facts)["C5"].passed is True


def test_FR_1_0_05_c5_guarded_allowed_by_approval_passes():
    paths = (StandInChangedPath("bots/x.py", "GUARDED"),)
    facts = StandInFacts(diff_paths=paths, approvals_allow_edits=("bots/x.py",))
    assert by_id(facts)["C5"].passed is True


def test_FR_1_0_05_c5_guarded_unmatched_fails():
    paths = (StandInChangedPath("bots/x.py", "GUARDED"),)
    result = by_id(StandInFacts(diff_paths=paths))["C5"]
    assert result.passed is False
    assert "bots/x.py" in result.reason


def test_FR_1_0_05_c5_none_means_no_allowance():
    paths = (StandInChangedPath("bots/x.py", "GUARDED"),)
    assert by_id(StandInFacts(diff_paths=paths, allowed_guarded_edits=()))["C5"].passed is False


def test_FR_1_0_05_c5_star_glob_stays_within_one_folder():
    paths = (StandInChangedPath("bots/deep/x.py", "GUARDED"),)
    assert by_id(StandInFacts(diff_paths=paths, allowed_guarded_edits=("bots/*",)))["C5"].passed is False


# ---------------------------------------------------------------- C6: blocking owner-run checks

def test_FR_1_0_05_c6_no_blocking_checks_passes():
    assert by_id(StandInFacts())["C6"].passed is True


def test_FR_1_0_05_c6_blocking_check_passing_passes():
    checks = (StandInBlockingCheck("OC-9.9-02", True, f"docs/progress/{WP}/OC-9.9-02_report.txt"),)
    assert by_id(StandInFacts(blocking_checks=checks))["C6"].passed is True


def test_FR_1_0_05_c6_blocking_check_missing_fails():
    checks = (StandInBlockingCheck("OC-9.9-02", False, None),)
    result = by_id(StandInFacts(blocking_checks=checks))["C6"]
    assert result.passed is False
    assert "OC-9.9-02" in result.reason


def test_FR_1_0_05_c6_spec_missing_fails():
    assert by_id(StandInFacts(spec_exists=False))["C6"].passed is False


# ---------------------------------------------------------------- C7: status fragment

def test_FR_1_0_05_c7_audit_pass_passes():
    assert by_id(StandInFacts())["C7"].passed is True


def test_FR_1_0_05_c7_other_status_fails():
    result = by_id(StandInFacts(status_state="READY-FOR-AUDIT"))["C7"]
    assert result.passed is False
    assert "READY-FOR-AUDIT" in result.reason


def test_FR_1_0_05_c7_missing_status_fails():
    result = by_id(StandInFacts(status_state=None))["C7"]
    assert result.passed is False
    assert "no status fragment" in result.reason
