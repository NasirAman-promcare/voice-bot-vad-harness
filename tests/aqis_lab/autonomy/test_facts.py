"""Unit tests for tools/autonomy/facts.py over scratch git repositories.

CAPABILITIES:
  CAP-AUTONOMY-202: exercise gather() against scratch repositories with a scripted GitHub double
    [tests: test_FR_1_0_05_facts_git_fields, test_FR_1_0_05_facts_audit_fields,
    test_FR_1_0_05_facts_spec_from_origin_main]
INPUTS AND OUTPUTS: pytest fixtures and test functions; no network, no GitHub.
CONTRACTS: Facts dataclass fields as defined in tools/autonomy/facts.py.
INVARIANTS:
  - GitHub is replaced by a local stand-in class; no subprocess named gh runs here.
  - Each test builds its own scratch repository; iteration order is deterministic.
NOT IN SCOPE:
  - Criteria evaluation (test_criteria.py) and the command line (test_merge_gate.py).
CHANGE LOG:
  2026-10-10 WO-1_0-05 step 3 created.
  2026-10-10 WO-1_0-05 fix 1: StandInGitHub used `pr if pr is not None else default`, which made
    an explicit pr=None (no open pull request) indistinguishable from "argument omitted";
    a sentinel now separates the two cases."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tools.autonomy.facts import FactsError, gather, slug_from_remote_url

ROOT = Path(__file__).resolve().parents[3]
WP = "WP-9.9"
BRANCH = "claude/wp-9-9-scratch"
SPEC = f"docs/specs/phase-9/{WP}-scratch.md"
_UNSET = object()


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "AQIS Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "AQIS Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo,
                          capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


class StandInGitHub:
    """Local stand-in for the GitHub client; records calls and answers from attributes.

    pr=None means "no open pull request"; omitting the argument uses the default PR.
    """

    def __init__(self, pr=_UNSET, runs=None, status=None) -> None:
        self.pr = {"number": 7, "title": "WP-9.9 scratch"} if pr is _UNSET else pr
        self.runs = runs if runs is not None else [
            {"name": "ci", "status": "completed", "conclusion": "success"}]
        self.status = status if status is not None else {"state": "success", "statuses": []}
        self.calls: list[tuple[str, str]] = []

    def open_pr_for_branch(self, branch: str):
        self.calls.append(("open_pr_for_branch", branch))
        return self.pr

    def check_runs(self, sha: str):
        self.calls.append(("check_runs", sha))
        return list(self.runs)

    def combined_status(self, sha: str):
        self.calls.append(("combined_status", sha))
        return dict(self.status)


def spec_text(allowed=("None",), blocking_check: bool = False) -> str:
    checks = "| Check | Blocking or post-merge | Where | Command | Expected output |\n| --- | --- | --- | --- | --- |\n"
    checks += "| OC-9.9-01 Scratch check | post-merge | Colab | `x` | ok |\n"
    if blocking_check:
        checks += "| OC-9.9-02 Scratch blocking check | blocking | Colab | `y` | ok |\n"
    return (f"# {WP} — scratch\n\n- **Touches**: `tools/demo/**`\n\n## Functional requirements\n- **FR-9.9-01** x\n\n"
            "## Allowed guarded edits\n" + "".join(f"- {a}\n" for a in allowed) + "\n## Owner-run checks\n" + checks)


def audit_text(sha: str, verdict: str = "PASS") -> str:
    return (f"# AUDIT — {WP}, round 1\n\nAuditor: wp-auditor · Tier: T2 · Date: 2026-10-10 · Commit audited: `{sha}` · "
            f"Previous audited commit: first audit · Protocol: version 3\n\n## Verdict: {verdict}\n"
            "CRITICAL: 0 · MAJOR: 0 (fixed 0, accepted as debt 0, open 0) · MINOR: 0\n\n## Findings\n"
            "| ID | Severity | Item | Finding | Evidence | Recommendation |\n| --- | --- | --- | --- | --- | --- |\n")


def status_text(state: str = "AUDIT-PASS") -> str:
    return (f"WP: {WP}\nTitle: Scratch\nStatus: {state}\nTier: T2\nSize: S\nBranch: {BRANCH}\n"
            f"PR: https://github.com/owner/scratch/pull/7\nThread model: Sonnet high\nUpdated: 2026-10-10\n")


class Scratch:
    def __init__(self, tmp: Path, spec: str | None = None) -> None:
        self.root, self.bare = tmp / "work", tmp / "origin.git"
        tmp.mkdir(parents=True, exist_ok=True)
        git(tmp, "init", "-q", "--bare", str(self.bare))
        self.root.mkdir()
        self.write("docs/process/PROTECTED_PATHS.txt",
                   (ROOT / "docs/process/PROTECTED_PATHS.txt").read_text("utf-8"))
        self.write(SPEC, spec or spec_text())
        self.write("tools/demo/__init__.py", "")
        git(self.root, "init", "-q")
        git(self.root, "remote", "add", "origin", self.bare.as_uri())
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "main base")
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "checkout", "-qb", BRANCH)
        self.commit({"tools/demo/alpha.py": "VALUE = 1\n"}, "code")
        self.audited = self.head()
        self.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(self.audited),
                     f"docs/progress/status.d/{WP}.md": status_text()}, "audit and status")
        git(self.root, "push", "-q", "origin", BRANCH)

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text, encoding="utf-8")

    def commit(self, files: dict[str, str], message: str) -> None:
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", message)

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD")


@pytest.fixture
def scratch(tmp_path: Path) -> Scratch:
    return Scratch(tmp_path)


# ---------------------------------------------------------------- slug parsing

def test_FR_1_0_05_facts_slug_https():
    assert slug_from_remote_url("https://github.com/owner/scratch") == "owner/scratch"
    assert slug_from_remote_url("https://github.com/owner/scratch.git") == "owner/scratch"


def test_FR_1_0_05_facts_slug_ssh():
    assert slug_from_remote_url("git@github.com:owner/scratch.git") == "owner/scratch"
    assert slug_from_remote_url("ssh://git@github.com/owner/scratch.git") == "owner/scratch"


def test_FR_1_0_05_facts_slug_proxy_form():
    assert slug_from_remote_url("http://proxy.local:8080/owner/scratch") == "owner/scratch"
    with pytest.raises(FactsError):
        slug_from_remote_url("single-component")


# ---------------------------------------------------------------- git facts

def test_FR_1_0_05_facts_git_fields(scratch):
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.branch == BRANCH
    assert facts.head_sha == scratch.head()
    assert facts.origin_main_sha == git(scratch.root, "rev-parse", "origin/main")
    assert facts.merge_base == git(scratch.root, "merge-base", "origin/main", "HEAD")
    assert facts.branch_contains_origin_main is True


def test_FR_1_0_05_facts_fetches_origin_once(scratch, monkeypatch):
    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(cmd, *args, **kwargs):
        if cmd[:2] == ["git", "fetch"]:
            calls.append(list(cmd))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("tools.autonomy.facts.subprocess.run", recording_run)
    gather(WP, scratch.root, StandInGitHub())
    assert calls == [["git", "fetch", "origin", "main"]]


def test_FR_1_0_05_facts_missing_origin_main_raises(tmp_path):
    repo = tmp_path / "work"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "remote", "add", "origin", "https://github.com/owner/scratch")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    # No origin/main exists because the remote URL is unreachable in tests; fetch fails.
    with pytest.raises(FactsError):
        gather(WP, repo, StandInGitHub())


# ---------------------------------------------------------------- audit facts

def test_FR_1_0_05_facts_audit_fields(scratch):
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.audit_exists is True
    assert facts.audit_verdict == "PASS"
    assert facts.audited_sha == scratch.audited
    assert facts.audited_is_ancestor is True
    assert len(facts.later_commits) == 1  # the audit-and-status commit itself


def test_FR_1_0_05_facts_audit_missing_file(scratch):
    git(scratch.root, "rm", "-q", f"docs/progress/{WP}/AUDIT.md")
    git(scratch.root, "commit", "-qm", "remove audit")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.audit_exists is False
    assert facts.audit_verdict is None
    assert facts.audited_sha is None


def test_FR_1_0_05_facts_audit_bad_verdict(scratch):
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.audited, "FAIL")}, "fail")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.audit_verdict == "FAIL"


def test_FR_1_0_05_facts_audit_abbreviated_sha(scratch):
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.audited[:8])}, "abbrev")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.audited_sha == scratch.audited


def test_FR_1_0_05_facts_later_commits_paths(scratch):
    scratch.commit({"tools/demo/beta.py": "VALUE = 2\n", f"docs/progress/{WP}/EVIDENCE.md": "e\n"}, "later")
    facts = gather(WP, scratch.root, StandInGitHub())
    later = facts.later_commits
    assert len(later) == 2  # audit-and-status commit plus the later commit
    assert later[-1].paths == (f"docs/progress/{WP}/EVIDENCE.md", "tools/demo/beta.py")


# ---------------------------------------------------------------- GitHub facts

def test_FR_1_0_05_facts_github_fields(scratch):
    github = StandInGitHub()
    facts = gather(WP, scratch.root, github)
    assert facts.pull_request == {"number": 7, "title": "WP-9.9 scratch"}
    assert facts.check_runs == ({"name": "ci", "status": "completed", "conclusion": "success"},)
    assert facts.combined_status == {"state": "success", "statuses": []}
    assert github.calls[0] == ("open_pr_for_branch", BRANCH)
    assert github.calls[1] == ("check_runs", facts.head_sha)
    assert github.calls[2] == ("combined_status", facts.head_sha)


def test_FR_1_0_05_facts_no_open_pr(scratch):
    facts = gather(WP, scratch.root, StandInGitHub(pr=None))
    assert facts.pull_request is None


# ---------------------------------------------------------------- blockers, findings, status

def test_FR_1_0_05_facts_open_blockers_for_wp(scratch):
    blocker = (f"# BLK-9.9-01 — scratch\nStatus: OPEN\nWP: {WP}\nOwner capability: ACCESS\nRaised: 2026-10-10\n"
               "Unblocks: WP-9.9\nTime needed: 1 minute\n\nExact steps:\n1. Do it.\n\nMeanwhile: wait.\n\nOwner answer:\n")
    other = blocker.replace("WP: WP-9.9", "WP: WP-8.8").replace("BLK-9.9-01", "BLK-8.8-01")
    scratch.commit({"docs/progress/blockers.d/BLK-9.9-01.md": blocker,
                    "docs/progress/blockers.d/BLK-8.8-01.md": other}, "blockers")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.open_blockers == ("BLK-9.9-01",)


def test_FR_1_0_05_facts_findings_rows(scratch):
    text = audit_text(scratch.audited).replace(
        "| --- | --- | --- | --- | --- | --- |\n",
        "| --- | --- | --- | --- | --- | --- |\n"
        "| WP-9.9-F01 | CRITICAL | A1 | broken | evidence | fix now |\n"
        "| WP-9.9-F02 | MAJOR | A2 | gap | evidence | debt (target WP-9.10; Claude may accept) |\n")
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": text}, "findings")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert [row.finding_id for row in facts.critical_findings] == ["WP-9.9-F01"]
    assert [row.finding_id for row in facts.major_findings] == ["WP-9.9-F02"]
    assert facts.major_findings[0].state in ("open", "accepted as debt", "fixed")


def test_FR_1_0_05_facts_status_fragment(scratch):
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.status_state == "AUDIT-PASS"
    scratch.commit({f"docs/progress/status.d/{WP}.md": status_text("READY-FOR-AUDIT")}, "status")
    assert gather(WP, scratch.root, StandInGitHub()).status_state == "READY-FOR-AUDIT"


# ---------------------------------------------------------------- spec and approvals

def test_FR_1_0_05_facts_spec_from_origin_main(scratch):
    # Change the spec on the branch only; facts must still read the origin/main version.
    scratch.commit({SPEC: spec_text(allowed=("bots/x.py",))}, "branch-only allowance")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.spec_exists is True
    assert facts.allowed_guarded_edits == ()


def test_FR_1_0_05_facts_allowed_guarded_edits(tmp_path):
    scratch = Scratch(tmp_path, spec=spec_text(allowed=("bots/x.py", "config/**")))
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.allowed_guarded_edits == ("bots/x.py", "config/**")


def test_FR_1_0_05_facts_spec_missing(tmp_path):
    scratch = Scratch(tmp_path)
    git(scratch.root, "checkout", "-q", "main")
    git(scratch.root, "rm", "-q", SPEC)
    git(scratch.root, "commit", "-qm", "drop spec")
    git(scratch.root, "push", "-q", "origin", "main")
    git(scratch.root, "checkout", "-q", BRANCH)
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.spec_exists is False
    assert facts.blocking_checks == ()


def test_FR_1_0_05_facts_approval_allow_edit(tmp_path):
    scratch = Scratch(tmp_path)
    git(scratch.root, "checkout", "-q", "main")
    scratch.write("docs/approvals/APPROVAL-1.md", "# Approval\nALLOW-EDIT: bots/x.py\n")
    git(scratch.root, "add", "-A")
    git(scratch.root, "commit", "-qm", "approval")
    git(scratch.root, "push", "-q", "origin", "main")
    git(scratch.root, "checkout", "-q", BRANCH)
    git(scratch.root, "merge", "-qm", "main", "main")
    facts = gather(WP, scratch.root, StandInGitHub())
    assert facts.approvals_allow_edits == ("bots/x.py",)


# ---------------------------------------------------------------- blocking checks

def test_FR_1_0_05_facts_blocking_checks_and_reports(tmp_path):
    scratch = Scratch(tmp_path, spec=spec_text(blocking_check=True))
    facts = gather(WP, scratch.root, StandInGitHub())
    assert len(facts.blocking_checks) == 1
    check = facts.blocking_checks[0]
    assert check.check_id == "OC-9.9-02" and check.passed is False and check.report_path is None
    scratch.commit({f"docs/progress/{WP}/OC-9.9-02_report.txt": "Result: FAIL\n"}, "fail report")
    assert gather(WP, scratch.root, StandInGitHub()).blocking_checks[0].passed is False
    scratch.commit({f"docs/progress/{WP}/OC-9.9-02_report.txt": "Result: PASS\n"}, "pass report")
    done = gather(WP, scratch.root, StandInGitHub()).blocking_checks[0]
    assert done.passed is True and done.report_path == f"docs/progress/{WP}/OC-9.9-02_report.txt"


# ---------------------------------------------------------------- diff paths

def test_FR_1_0_05_facts_diff_paths_classified(scratch):
    scratch.commit({"CLAUDE.md": "changed\n"}, "never path")
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.head())}, "re-audit")
    facts = gather(WP, scratch.root, StandInGitHub())
    classes = {changed.path: changed.protected_class for changed in facts.diff_paths}
    assert classes["CLAUDE.md"] == "NEVER"
    assert classes["tools/demo/alpha.py"] == "FREE"
    assert classes[f"docs/progress/{WP}/AUDIT.md"] == "FREE"


def test_FR_1_0_05_facts_gather_writes_nothing(scratch):
    before = git(scratch.root, "status", "--porcelain", "--untracked-files=all")
    head = scratch.head()
    gather(WP, scratch.root, StandInGitHub())
    assert git(scratch.root, "status", "--porcelain", "--untracked-files=all") == before
    assert scratch.head() == head
