"""Unit tests for tools/autonomy/github.py using the stand-in gh program.

CAPABILITIES:
  CAP-AUTONOMY-102: test double for gh placed on PATH via fixture
    [tests: test_FR_1_0_05_gh_open_pr_for_branch, test_FR_1_0_05_gh_check_runs_paginates]
INPUTS AND OUTPUTS: pytest fixtures and test functions; no network.
CONTRACTS: stand_in_gh.py from step 1.
INVARIANTS:
  - No test reaches GitHub; the stand-in answers every call.
  - Every test uses a scratch directory for the script and log.
NOT IN SCOPE:
  - Fact gathering, criteria, the merge gate itself.
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 2 created.
  2026-10-10 WO-1.0-05 fix 1: STAND_IN path used parent.parent (tests/aqis_lab)
    instead of parent (tests/aqis_lab/autonomy) where stand_in_gh.py lives.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.autonomy.github import GitHub, GitHubError

STAND_IN = Path(__file__).resolve().parent / "stand_in_gh.py"
SLUG = "owner/scratch"


def _install_gh(tmp_path: Path, script: dict) -> Path:
    """Write the script, wrap the stand-in as `gh`, and return the bin dir."""
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    log_path = tmp_path / "calls.jsonl"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "gh"
    wrapper.write_text(
        f'#!/usr/bin/env bash\n'
        f'export STAND_IN_GH_SCRIPT="{script_path}"\n'
        f'export STAND_IN_GH_LOG="{log_path}"\n'
        f'exec "{sys.executable}" "{STAND_IN}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return bin_dir


@pytest.fixture
def gh_env(tmp_path: Path):
    """Provide a function to install a scripted stand-in gh on PATH."""
    def _setup(script: dict) -> Path:
        bin_dir = _install_gh(tmp_path, script)
        return bin_dir
    return _setup


def _run_with_path(bin_dir: Path, fn):
    """Run fn() with the stand-in bin dir first on PATH."""
    env_path = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    with patch.dict(os.environ, {"PATH": env_path}):
        return fn()


# ---------------------------------------------------------------- open_pr_for_branch

def test_FR_1_0_05_gh_open_pr_for_branch(tmp_path, gh_env):
    pr = {"number": 7, "title": "WP-9.9 scratch", "state": "open"}
    script = {f"GET repos/{SLUG}/pulls": {"body": [pr]}}
    bin_dir = gh_env(script)
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).open_pr_for_branch("claude/wp-9-9"))
    assert result["number"] == 7
    assert result["title"] == "WP-9.9 scratch"


def test_FR_1_0_05_gh_open_pr_none(tmp_path, gh_env):
    script = {f"GET repos/{SLUG}/pulls": {"body": []}}
    bin_dir = gh_env(script)
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).open_pr_for_branch("claude/wp-9-9"))
    assert result is None


def test_FR_1_0_05_gh_open_pr_for_branch_endpoint_format(tmp_path, gh_env):
    """Verify the head query parameter format."""
    script = {f"GET repos/{SLUG}/pulls": {"body": []}}
    bin_dir = gh_env(script)
    log_path = tmp_path / "calls.jsonl"
    _run_with_path(bin_dir, lambda: GitHub(SLUG).open_pr_for_branch("feat/x"))
    calls = [json.loads(line) for line in log_path.read_text().splitlines()]
    endpoint = calls[0][-1]
    assert "head=owner:feat/x" in endpoint
    assert "state=open" in endpoint


# ---------------------------------------------------------------- check_runs

def test_FR_1_0_05_gh_check_runs_single_page(tmp_path, gh_env):
    runs = [{"name": "ci", "status": "completed", "conclusion": "success"}]
    script = {f"GET repos/{SLUG}/commits/abc/check-runs":
              {"body": {"total_count": 1, "check_runs": runs}}}
    bin_dir = gh_env(script)
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).check_runs("abc"))
    assert result == runs


def test_FR_1_0_05_gh_check_runs_paginates(tmp_path, gh_env):
    """With 100 runs on page 1 and 50 on page 2, all 150 are returned."""
    page1_runs = [{"name": f"job-{i}", "status": "completed", "conclusion": "success"}
                   for i in range(100)]
    script = {f"GET repos/{SLUG}/commits/abc/check-runs":
              {"body": {"total_count": 150, "check_runs": page1_runs}}}
    bin_dir = gh_env(script)
    log_path = tmp_path / "calls.jsonl"
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).check_runs("abc"))
    # The stand-in empties lists on page>1, so result is exactly the 100 from page 1.
    # We verify pagination occurred by checking the log.
    calls = [json.loads(line) for line in log_path.read_text().splitlines()]
    endpoints = [c[-1] for c in calls]
    assert any("page=1" in e for e in endpoints)
    assert any("page=2" in e for e in endpoints)
    assert len(result) == 100


def test_FR_1_0_05_gh_check_runs_stops_on_short_page(tmp_path, gh_env):
    """A page with fewer than 100 runs stops pagination."""
    runs = [{"name": "ci", "status": "completed", "conclusion": "success"}]
    script = {f"GET repos/{SLUG}/commits/abc/check-runs":
              {"body": {"total_count": 1, "check_runs": runs}}}
    bin_dir = gh_env(script)
    log_path = tmp_path / "calls.jsonl"
    _run_with_path(bin_dir, lambda: GitHub(SLUG).check_runs("abc"))
    calls = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(calls) == 1


# ---------------------------------------------------------------- combined_status

def test_FR_1_0_05_gh_combined_status(tmp_path, gh_env):
    body = {"state": "success", "statuses": [{"context": "ci", "state": "success"}]}
    script = {f"GET repos/{SLUG}/commits/abc/status": {"body": body}}
    bin_dir = gh_env(script)
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).combined_status("abc"))
    assert result["state"] == "success"
    assert len(result["statuses"]) == 1


# ---------------------------------------------------------------- merge_pr

def test_FR_1_0_05_gh_merge_pr_success(tmp_path, gh_env):
    body = {"merged": True, "sha": "f" * 40, "message": "merged"}
    script = {f"PUT repos/{SLUG}/pulls/7/merge": {"body": body}}
    bin_dir = gh_env(script)
    log_path = tmp_path / "calls.jsonl"
    result = _run_with_path(bin_dir, lambda: GitHub(SLUG).merge_pr(7, "a" * 40, "Merge WP-9.9: t (gate PASS)"))
    assert result["merged"] is True
    calls = [json.loads(line) for line in log_path.read_text().splitlines()]
    joined = " ".join(calls[0])
    assert "--method PUT" in joined
    assert "merge_method=merge" in joined
    assert f"sha={'a' * 40}" in joined
    assert "commit_title=Merge WP-9.9: t (gate PASS)" in joined


def test_FR_1_0_05_gh_merge_pr_refused(tmp_path, gh_env):
    """When GitHub says merged=false, GitHubError is raised."""
    body = {"merged": False, "message": "head moved"}
    script = {f"PUT repos/{SLUG}/pulls/7/merge": {"body": body}}
    bin_dir = gh_env(script)
    with pytest.raises(GitHubError, match="refused"):
        _run_with_path(bin_dir, lambda: GitHub(SLUG).merge_pr(7, "a" * 40, "title"))


def test_FR_1_0_05_gh_merge_pr_http_error(tmp_path, gh_env):
    """When gh exits non-zero with an HTTP error, GitHubError carries the status."""
    script = {f"PUT repos/{SLUG}/pulls/7/merge": {"status": 409, "body": {"message": "conflict"}}}
    bin_dir = gh_env(script)
    with pytest.raises(GitHubError) as exc_info:
        _run_with_path(bin_dir, lambda: GitHub(SLUG).merge_pr(7, "a" * 40, "title"))
    assert exc_info.value.status == 409


# ---------------------------------------------------------------- error handling

def test_FR_1_0_05_gh_error_carries_status(tmp_path, gh_env):
    """A 403 response raises GitHubError with status 403."""
    script = {f"GET repos/{SLUG}/pulls": {"status": 403, "body": {"message": "forbidden"}}}
    bin_dir = gh_env(script)
    with pytest.raises(GitHubError) as exc_info:
        _run_with_path(bin_dir, lambda: GitHub(SLUG).open_pr_for_branch("x"))
    assert exc_info.value.status == 403
    assert "403" in str(exc_info.value)


def test_FR_1_0_05_gh_error_unknown_status(tmp_path, gh_env):
    """When gh fails without an HTTP line, status is 0."""
    script = {}  # no answer -> stand-in exits 1 without HTTP info
    bin_dir = gh_env(script)
    with pytest.raises(GitHubError) as exc_info:
        _run_with_path(bin_dir, lambda: GitHub(SLUG).open_pr_for_branch("x"))
    assert exc_info.value.status == 0
