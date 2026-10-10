"""Unit tests for branch scope checker.

CAPABILITIES:
  CAP-OUTSOURCING-007: check branch changes against allowed outputs and logs [tests: test_FR_1_0_01_scope_clean_branch, test_FR_1_0_01_scope_detects_violations, test_FR_1_0_01_scope_missing_base_raises_error]
INPUTS AND OUTPUTS: pytest tests.
CONTRACTS: none.
INVARIANTS:
  - All tests pass cleanly.
NOT IN SCOPE:
  - Acceptance tests (see test_acceptance_wo_1_0_01.py).
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import os
import subprocess
import pytest
from tools.outsourcing.scope import ScopeError, check_scope
from tools.outsourcing.workorder import WorkOrder


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    return env


def run_git(repo, *args):
    subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, check=True, env=git_env())


def make_order(order_id="WO-1.0-01", outputs=("tools/demo/alpha.py",)):
    return WorkOrder(
        id=order_id,
        wp="WP-1.0",
        title="Test",
        model="default",
        channel="api",
        attempt_budget=2,
        risk_tier="T1",
        max_output_tokens=10000,
        context=(),
        outputs=outputs,
        read_only_tests=(),
        allowed_dependencies=("stdlib",),
        verify=("pytest",),
    )


def test_FR_1_0_01_scope_clean_branch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "base")

    order = make_order()
    (repo / "tools/demo").mkdir(parents=True)
    (repo / "tools/demo/alpha.py").write_text("VALUE = 1\n", encoding="utf-8")

    report = check_scope(order, repo, "HEAD")
    assert report.violations == ()
    assert report.changed_paths == ("tools/demo/alpha.py",)


def test_FR_1_0_01_scope_detects_violations(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "base")

    order = make_order()
    (repo / "extra.py").write_text("extra\n", encoding="utf-8")

    report = check_scope(order, repo, "HEAD")
    assert "extra.py" in report.violations


def test_FR_1_0_01_scope_missing_base_raises_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "base")

    order = make_order()
    with pytest.raises(ScopeError):
        check_scope(order, repo, "nonexistent-ref")
