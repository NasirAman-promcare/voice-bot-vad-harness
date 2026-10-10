"""Unit tests for tools.outsourcing.worktree.

CAPABILITIES:
  CAP-OUTSOURCING-WORKTREE: Git worktree management, branch creation, commit/push, and attempt cleanup. [tests: test_worktree.py]
INPUTS AND OUTPUTS: Test cases for worktree operations.
CONTRACTS: none.
INVARIANTS:
  - Unit tests use scratch repos with local bare origins.
NOT IN SCOPE:
  - External git service operations.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from tools.outsourcing.worktree import WorktreeError, commit, discard_attempt, open_worktree, push, read_step_log, remove


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "AQIS Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "AQIS Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    })
    return env


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    if check:
        assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout if proc.returncode == 0 else ""


@pytest.fixture
def scratch_repo(tmp_path: Path):
    origin = tmp_path / "origin.git"
    root = tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", str(origin))

    root.mkdir()
    git(root, "init", "-q")
    git(root, "checkout", "-qb", "claude/wp-1-0-test")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial commit")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "origin", "claude/wp-1-0-test")

    return root, origin


def test_open_and_commit_worktree(scratch_repo):
    root, _ = scratch_repo
    wt = open_worktree(root, "WO-1.0-01", "claude/wp-1-0-test")
    assert wt.path.exists()
    assert wt.branch == "wo/WO-1.0-01"

    new_file = wt.path / "file.py"
    new_file.write_text("print('test')\n", encoding="utf-8")

    commit(wt, ("file.py",), "add file.py")
    push(wt)

    assert git(root, "ls-remote", "origin", "wo/WO-1.0-01").strip() != ""

    remove(wt)
    assert not wt.path.exists()


def test_discard_attempt(scratch_repo):
    root, _ = scratch_repo
    wt = open_worktree(root, "WO-1.0-01", "claude/wp-1-0-test")

    dirty_file = wt.path / "dirty.txt"
    dirty_file.write_text("dirty content", encoding="utf-8")

    discard_attempt(wt, ("dirty.txt",))
    assert not dirty_file.exists()

    remove(wt)
