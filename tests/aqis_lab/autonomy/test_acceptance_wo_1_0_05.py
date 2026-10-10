"""Acceptance tests for WO-1.0-05 (FR-1.0-05): the merge gate.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus the all-pass controls (a real merge
and a dry run) that AT-1.0-05 needs.

Each test builds a scratch repository whose `origin` URL reads `https://github.com/owner/scratch` while fetches and
pushes go to a local bare repository (`url.<bare>.insteadOf`). The gate runs as
`python -m tools.autonomy.merge_gate` with a stand-in `gh` (defined below, independent of the implementer's
`stand_in_gh.py`) first on `PATH`. The stand-in answers `gh api` calls from a JSON script and records each call.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WP = "WP-9.9"
BRANCH = "claude/wp-9-9-scratch"
SLUG = "owner/scratch"
URL = f"https://github.com/{SLUG}"
SPEC = f"docs/specs/phase-9/{WP}-scratch.md"
CRITERIA = ("C1", "C2", "C3", "C4", "C5", "C6", "C7")
STAND_IN_GH = r'''#!/usr/bin/env python3
"""Stand-in for the gh command: answers `gh api` from SCRIPT and logs every call to LOG (one JSON line each)."""
import json, os, sys
from urllib.parse import parse_qs, urlsplit

args = sys.argv[1:]
with open(os.environ["STAND_IN_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if not args or args[0] != "api":
    sys.stderr.write("stand-in gh only answers `gh api`\n")
    sys.exit(2)
method, endpoint, i = "GET", None, 1
while i < len(args):
    a = args[i]
    if a in ("-X", "--method"):
        method, i = args[i + 1].upper(), i + 2
        continue
    if a in ("-f", "-F", "--field", "--raw-field", "-H", "--header", "--jq", "-q", "--input", "--template", "-t"):
        i += 2
        continue
    if a.startswith("-"):
        i += 1
        continue
    if endpoint is None:
        endpoint = a.lstrip("/")
    i += 1
if method == "GET" and any(a in ("-f", "-F", "--field", "--raw-field") for a in args) and not any(a in ("-X", "--method") for a in args):
    method = "POST"
parts = urlsplit(endpoint)
page = int(parse_qs(parts.query).get("page", ["1"])[0])
with open(os.environ["STAND_IN_GH_SCRIPT"], encoding="utf-8") as handle:
    script = json.load(handle)
key = f"{method} {parts.path}"
if key not in script:
    sys.stderr.write(f"stand-in gh: no answer for {key}\n")
    sys.exit(1)
answer = script[key]
status, body = answer.get("status", 200), answer.get("body")
if page > 1:
    body = [] if isinstance(body, list) else {k: ([] if isinstance(v, list) else v) for k, v in body.items()}
if status >= 400:
    sys.stderr.write(f"gh: HTTP {status}: {json.dumps(body)}\n")
    sys.exit(1)
sys.stdout.write(json.dumps(body))
'''


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "AQIS Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "AQIS Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True, text=True,
                          env=env, timeout=60)
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


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
            f"PR: {URL}/pull/7\nThread model: Sonnet high\nUpdated: 2026-10-10\n")


class Scratch:
    """main holds the protected-path list and the spec; the WP branch holds code, the audit and the status fragment."""

    def __init__(self, tmp: Path, spec: str | None = None) -> None:
        self.tmp, self.root, self.bare = tmp, tmp / "work", tmp / "origin.git"
        tmp.mkdir(parents=True, exist_ok=True)
        git(tmp, "init", "-q", "--bare", str(self.bare))
        self.root.mkdir()
        self.write("docs/process/PROTECTED_PATHS.txt", (ROOT / "docs/process/PROTECTED_PATHS.txt").read_text("utf-8"))
        self.write(SPEC, spec or spec_text())
        self.write("tools/demo/__init__.py", "")
        git(self.root, "init", "-q")
        git(self.root, "remote", "add", "origin", URL)
        git(self.root, "config", f"url.{self.bare.as_uri()}.insteadOf", URL)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "main base")
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "checkout", "-qb", BRANCH)
        self.commit({"tools/demo/alpha.py": "VALUE = 1\n"}, "code")
        self.audited = self.head()
        self.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(self.audited),
                     f"docs/progress/status.d/{WP}.md": status_text()}, "audit and status")
        git(self.root, "push", "-q", "origin", BRANCH)
        self.bin = tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(STAND_IN_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.log = tmp / "gh-calls.jsonl"
        self.script_path = tmp / "gh-script.json"
        self.custom_script = False  # True once a test sets its own answers; otherwise answers follow the head

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

    def script(self, runs=None, status_state: str = "success", merge_status: int = 200, custom: bool = True) -> None:
        self.custom_script = custom
        sha = self.head()
        runs = [{"name": "ci", "status": "completed", "conclusion": "success"}] if runs is None else runs
        pr = {"number": 7, "title": "WP-9.9 scratch", "state": "open", "html_url": f"{URL}/pull/7",
              "head": {"ref": BRANCH, "sha": sha}, "base": {"ref": "main"}}
        merge = {"merged": True, "sha": "f" * 40, "message": "merged"} if merge_status == 200 else {"message": "no"}
        self.script_path.write_text(json.dumps({
            f"GET repos/{SLUG}/pulls": {"body": [pr]},
            f"GET repos/{SLUG}/commits/{sha}/pulls": {"body": [pr]},
            f"GET repos/{SLUG}/pulls/7": {"body": pr},
            f"GET repos/{SLUG}/commits/{sha}/check-runs": {"body": {"total_count": len(runs), "check_runs": runs}},
            f"GET repos/{SLUG}/commits/{sha}/status": {"body": {"state": status_state, "statuses": []}},
            f"PUT repos/{SLUG}/pulls/7/merge": {"status": merge_status, "body": merge},
        }), encoding="utf-8")

    def gate(self, *args: str) -> subprocess.CompletedProcess:
        if not self.custom_script:
            self.script(custom=False)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "PYTHONPATH": str(ROOT),
                    "STAND_IN_GH_LOG": str(self.log), "STAND_IN_GH_SCRIPT": str(self.script_path),
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        return subprocess.run([sys.executable, "-m", "tools.autonomy.merge_gate", "--wp", WP, *args], cwd=self.root,
                              capture_output=True, text=True, env=env, timeout=300)

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def merge_calls(self) -> list[list[str]]:
        return [c for c in self.calls() if any("/merge" in a for a in c)]


@pytest.fixture
def scratch(tmp_path: Path) -> Scratch:
    return Scratch(tmp_path)


def criteria(proc: subprocess.CompletedProcess) -> dict[str, dict]:
    data = json.loads(proc.stdout)
    rows = data["criteria"] if isinstance(data, dict) else data
    return {row["id"]: row for row in rows}


def failed(proc) -> set[str]:
    return {cid for cid, row in criteria(proc).items() if not row["passed"]}


# ---------------------------------------------------------------- all-pass controls (AT-1.0-05)

def test_FR_1_0_05_dry_run_prints_all_seven_criteria_and_passes(scratch):
    proc = scratch.gate("--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert all(cid in proc.stdout for cid in CRITERIA)
    assert len(proc.stdout.splitlines()) <= 20
    proc = scratch.gate("--dry-run", "--json")
    assert set(criteria(proc)) == set(CRITERIA) and failed(proc) == set()
    assert all(row["reason"] for row in criteria(proc).values())


# ---------------------------------------------------------------- must-catch 7: a dry run never merges

def test_FR_1_0_05_mc07_dry_run_never_calls_the_merge_endpoint(scratch):
    assert scratch.gate("--dry-run").returncode == 0
    assert scratch.calls() and scratch.merge_calls() == []


# ---------------------------------------------------------------- must-catch 6: merge pinned to head

def test_FR_1_0_05_mc06_merge_is_pinned_to_the_head_sha(scratch):
    head = scratch.head()
    proc = scratch.gate()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (call,) = scratch.merge_calls()
    joined = " ".join(call)
    assert f"repos/{SLUG}/pulls/7/merge" in joined
    assert any(a in ("PUT",) for a in call) or "--method PUT" in joined or "-X PUT" in joined
    assert f"sha={head}" in call and "merge_method=merge" in call
    assert any(a.startswith("commit_title=Merge WP-9.9: WP-9.9 scratch (gate PASS)") for a in call)
    assert not any("graphql" in a for c in scratch.calls() for a in c)


def test_FR_1_0_05_mc06_github_refusing_the_merge_exits_4(scratch):
    scratch.script(merge_status=409)
    assert scratch.gate().returncode == 4


# ---------------------------------------------------------------- must-catch 1: audit must cover head

def test_FR_1_0_05_mc01_later_code_commit_after_audit_fails_c1(scratch):
    scratch.commit({"tools/demo/beta.py": "VALUE = 2\n"}, "code after the audit")
    git(scratch.root, "push", "-q", "origin", BRANCH)
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and failed(proc) == {"C1"}


def test_FR_1_0_05_mc01_later_record_only_commit_keeps_c1(scratch):
    scratch.commit({f"docs/progress/{WP}/EVIDENCE.md": "evidence\n", "docs/progress/decisions.d/DEC-9.9-01.md": "x\n"},
                   "records after the audit")
    git(scratch.root, "push", "-q", "origin", BRANCH)
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 0 and failed(proc) == set()


def test_FR_1_0_05_mc01_failed_verdict_fails_c1(scratch):
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.audited, "FAIL")}, "audit failed")
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and "C1" in failed(proc)


# ---------------------------------------------------------------- must-catch 2: CI

@pytest.mark.parametrize("runs, state", [
    ([{"name": "ci", "status": "in_progress", "conclusion": None}], "success"),
    ([{"name": "ci", "status": "completed", "conclusion": "failure"}], "success"),
    ([{"name": "ci", "status": "completed", "conclusion": "success"}], "pending"),
    ([{"name": "ci", "status": "completed", "conclusion": "success"}], "failure"),
], ids=["check-run-pending", "check-run-failed", "status-pending", "status-failed"])
def test_FR_1_0_05_mc02_pending_or_failed_ci_fails_c2(scratch, runs, state):
    scratch.script(runs=runs, status_state=state)
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and failed(proc) == {"C2"}


def test_FR_1_0_05_mc02_more_than_100_check_runs_are_all_read(scratch):
    runs = [{"name": f"job-{i}", "status": "completed", "conclusion": "success"} for i in range(150)]
    runs[149]["conclusion"] = "failure"
    scratch.script(runs=runs)
    proc = scratch.gate("--dry-run", "--json")
    assert "C2" in failed(proc)


# ---------------------------------------------------------------- must-catch 3: fresh base

def test_FR_1_0_05_mc03_branch_behind_main_exits_2(scratch):
    git(scratch.root, "checkout", "-q", "main")
    scratch.commit({"docs/notes.md": "main moved on\n"}, "main moves")
    git(scratch.root, "push", "-q", "origin", "main")
    git(scratch.root, "checkout", "-q", BRANCH)
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 2 and "C3" in failed(proc)


# ---------------------------------------------------------------- must-catch 4: open blocker

def test_FR_1_0_05_mc04_open_blocker_for_the_wp_fails_c4(scratch):
    blocker = (f"# BLK-9.9-01 — scratch\nStatus: OPEN\nWP: {WP}\nOwner capability: ACCESS\nRaised: 2026-10-10\n"
               "Unblocks: WP-9.9\nTime needed: 1 minute\n\nExact steps:\n1. Do it.\n\nMeanwhile: wait.\n\nOwner answer:\n")
    scratch.commit({"docs/progress/blockers.d/BLK-9.9-01.md": blocker}, "open blocker")
    git(scratch.root, "push", "-q", "origin", BRANCH)
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and failed(proc) == {"C4"}
    scratch.commit({"docs/progress/blockers.d/BLK-9.9-01.md": blocker.replace("Status: OPEN", "Status: RESOLVED")},
                   "resolved")
    assert failed(scratch.gate("--dry-run", "--json")) == set()


# ---------------------------------------------------------------- must-catch 5: protected paths

@pytest.mark.parametrize("path", ["CLAUDE.md", ".claude/hooks/x.py", "docs/process/WORKFLOW.md",
                                  "config/aqis_lab/model_pool.json"])
def test_FR_1_0_05_mc05_never_path_fails_c5(scratch, path):
    scratch.commit({path: "changed\n"}, "touch a NEVER path")
    audited = scratch.head()
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(audited)}, "audit covers it")
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and failed(proc) == {"C5"}


def test_FR_1_0_05_mc05_guarded_path_needs_the_specs_allowance_on_main(tmp_path):
    scratch = Scratch(tmp_path / "denied")
    scratch.commit({"bots/x.py": "x = 1\n"}, "guarded edit")
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.head())}, "audit")
    assert failed(scratch.gate("--dry-run", "--json")) == {"C5"}
    allowed = Scratch(tmp_path / "allowed", spec=spec_text(allowed=("bots/x.py",)))
    allowed.commit({"bots/x.py": "x = 1\n"}, "guarded edit")
    allowed.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(allowed.head())}, "audit")
    assert failed(allowed.gate("--dry-run", "--json")) == set()


def test_FR_1_0_05_mc05_allowance_added_only_on_the_branch_does_not_count(scratch):
    scratch.commit({SPEC: spec_text(allowed=("bots/x.py",)), "bots/x.py": "x = 1\n"}, "allowance on the branch only")
    scratch.commit({f"docs/progress/{WP}/AUDIT.md": audit_text(scratch.head())}, "audit")
    assert "C5" in failed(scratch.gate("--dry-run", "--json"))


# ---------------------------------------------------------------- must-catch 8: blocking owner-run check

def test_FR_1_0_05_mc08_blocking_check_without_pass_report_fails_c6(tmp_path):
    scratch = Scratch(tmp_path, spec=spec_text(blocking_check=True))
    proc = scratch.gate("--dry-run", "--json")
    assert proc.returncode == 3 and failed(proc) == {"C6"}
    scratch.commit({f"docs/progress/{WP}/OC-9.9-02_report.txt": "Result: FAIL\n"}, "failing report")
    assert failed(scratch.gate("--dry-run", "--json")) == {"C6"}
    scratch.commit({f"docs/progress/{WP}/OC-9.9-02_report.txt": "Result: PASS\n"}, "passing report")
    assert failed(scratch.gate("--dry-run", "--json")) == set()


# ---------------------------------------------------------------- C7 and the missing pull request

def test_FR_1_0_05_status_not_audit_pass_fails_c7(scratch):
    scratch.commit({f"docs/progress/status.d/{WP}.md": status_text("READY-FOR-AUDIT")}, "status")
    assert failed(scratch.gate("--dry-run", "--json")) == {"C7"}


def test_FR_1_0_05_no_open_pull_request_exits_5(scratch):
    scratch.script()
    script = json.loads(scratch.script_path.read_text(encoding="utf-8"))
    for key in list(script):
        if key.endswith("/pulls"):
            script[key] = {"body": []}
    scratch.script_path.write_text(json.dumps(script), encoding="utf-8")
    assert scratch.custom_script
    assert scratch.gate("--dry-run").returncode == 5


def test_FR_1_0_05_gate_writes_nothing(scratch):
    before = git(scratch.root, "status", "--porcelain", "--untracked-files=all")
    head = scratch.head()
    assert scratch.gate().returncode == 0
    assert git(scratch.root, "status", "--porcelain", "--untracked-files=all") == before
    assert scratch.head() == head
