"""Git worktree and branch operations for relay execution.

CAPABILITIES:
  CAP-OUTSOURCING-WORKTREE: Git worktree management, branch creation, commit/push, and attempt cleanup. [tests: test_worktree.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Accepts root path, wo_id, wp_branch; manages .relay/wt/<WO> worktree and git commands.
CONTRACTS: none.
INVARIANTS:
  - Relay operations happen strictly in dedicated git worktrees.
  - Changes to uncommitted outputs belong to an attempt and are discarded on retry.
NOT IN SCOPE:
  - Direct file editing or generation.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
  2026-10-10 WO-1.0-11 FIX 1: split open_worktree to follow shape rules; no-op commit when clean.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from tools.outsourcing.steplog import StepLogError, parse

__all__ = [
    "WorktreeError",
    "Worktree",
    "read_step_log",
    "open_worktree",
    "discard_attempt",
    "commit",
    "push",
    "remove",
]


class WorktreeError(Exception):
    """Raised when a git operation fails."""

    def __init__(self, message: str, paths: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.paths = tuple(paths)


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str
    base_commit: str


def _git_cmd(repo_path: Path, *args: str, check: bool = True) -> str:
    env = dict(os.environ)
    for k in list(env.keys()):
        if k.startswith("GIT_") and k not in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            env.pop(k, None)
    env.setdefault("GIT_AUTHOR_NAME", "AQIS Relay")
    env.setdefault("GIT_AUTHOR_EMAIL", "relay@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "AQIS Relay")
    env.setdefault("GIT_COMMITTER_EMAIL", "relay@example.invalid")

    retries = 0
    last_err = ""
    while retries < 5:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode == 0:
            return proc.stdout

        last_err = proc.stderr or proc.stdout
        if "index.lock" in last_err or "lock" in last_err.lower():
            retries += 1
            time.sleep(2.0)
            continue
        break

    if check:
        raise WorktreeError(last_err.strip())
    return ""


def read_step_log(root: str | Path, wo_id: str) -> str | None:
    root_path = Path(root)
    branch = f"wo/{wo_id}"
    log_rel = f"docs/outsourcing/returns/{wo_id}/steps.md"

    text = _git_cmd(root_path, "show", f"{branch}:{log_rel}", check=False)
    if text:
        return text

    _git_cmd(root_path, "fetch", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}", check=False)

    text_origin = _git_cmd(root_path, "show", f"origin/{branch}:{log_rel}", check=False)
    if text_origin:
        return text_origin

    return None


def _check_diverged_or_ahead(root_path: Path, local_branch: str, remote_ref: str) -> tuple[bool, bool, bool]:
    has_local = bool(_git_cmd(root_path, "rev-parse", "--verify", "--quiet", local_branch, check=False).strip())
    has_remote = bool(_git_cmd(root_path, "rev-parse", "--verify", "--quiet", remote_ref, check=False).strip())

    if not has_local and not has_remote:
        return False, False, False

    if has_local and not has_remote:
        return True, False, False

    if not has_local and has_remote:
        return False, True, False

    local_sha = _git_cmd(root_path, "rev-parse", local_branch).strip()
    remote_sha = _git_cmd(root_path, "rev-parse", remote_ref).strip()

    if local_sha == remote_sha:
        return True, False, False

    mb = _git_cmd(root_path, "merge-base", local_branch, remote_ref).strip()
    if mb == local_sha:
        return False, True, False
    if mb == remote_sha:
        return True, False, False

    return True, True, True


def _prepare_branch(root_path: Path, wo_branch: str, wp_branch: str) -> None:
    _git_cmd(root_path, "fetch", "origin", check=False)
    remote_wo_ref = f"origin/{wo_branch}"
    has_local, has_remote, is_diverged = _check_diverged_or_ahead(root_path, wo_branch, remote_wo_ref)

    if is_diverged:
        raise WorktreeError(f"Branches {wo_branch} and {remote_wo_ref} have diverged")

    if not has_local and not has_remote:
        wp_head = _git_cmd(root_path, "rev-parse", wp_branch).strip()
        _git_cmd(root_path, "branch", wo_branch, wp_head)
    elif has_remote and not has_local:
        _git_cmd(root_path, "branch", wo_branch, remote_wo_ref)
    elif has_remote and has_local:
        remote_sha = _git_cmd(root_path, "rev-parse", remote_wo_ref).strip()
        _git_cmd(root_path, "update-ref", f"refs/heads/{wo_branch}", remote_sha)


def _ensure_worktree_dir(root_path: Path, wt_dir: Path, wo_branch: str) -> None:
    if wt_dir.exists():
        wt_branch = _git_cmd(wt_dir, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
        if wt_branch != wo_branch:
            _git_cmd(root_path, "worktree", "remove", "--force", str(wt_dir), check=False)

    if not wt_dir.exists():
        wt_dir.parent.mkdir(parents=True, exist_ok=True)
        _git_cmd(root_path, "worktree", "add", str(wt_dir), wo_branch)


def _merge_wp_branch_if_needed(wt_dir: Path, wo_branch: str, wp_branch: str) -> None:
    wp_head_sha = _git_cmd(wt_dir, "rev-parse", wp_branch).strip()
    wo_head_sha = _git_cmd(wt_dir, "rev-parse", "HEAD").strip()
    mb = _git_cmd(wt_dir, "merge-base", wo_head_sha, wp_head_sha).strip()

    if mb != wp_head_sha:
        proc = subprocess.run(
            ["git", "merge", "--no-ff", "--no-edit", wp_branch],
            cwd=wt_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            status_out = _git_cmd(wt_dir, "status", "--porcelain", check=False)
            conflicts = tuple(line[3:].strip() for line in status_out.splitlines() if line)
            _git_cmd(wt_dir, "merge", "--abort", check=False)
            raise WorktreeError(f"Merge conflict merging {wp_branch} into {wo_branch}", paths=conflicts)


def open_worktree(root: str | Path, wo_id: str, wp_branch: str) -> Worktree:
    root_path = Path(root)
    wo_branch = f"wo/{wo_id}"
    wt_dir = root_path / ".relay" / "wt" / wo_id

    _prepare_branch(root_path, wo_branch, wp_branch)
    base_commit = _git_cmd(root_path, "rev-parse", wp_branch).strip()

    _ensure_worktree_dir(root_path, wt_dir, wo_branch)
    _merge_wp_branch_if_needed(wt_dir, wo_branch, wp_branch)

    status_out = _git_cmd(wt_dir, "status", "--porcelain", check=False)
    if status_out.strip():
        modified_paths = tuple(line[3:].strip() for line in status_out.splitlines() if line)
        discard_attempt(Worktree(path=wt_dir, branch=wo_branch, base_commit=base_commit), modified_paths)

    return Worktree(path=wt_dir, branch=wo_branch, base_commit=base_commit)


def discard_attempt(worktree: Worktree, paths: tuple[str, ...]) -> None:
    if not paths:
        return
    for p in paths:
        _git_cmd(worktree.path, "checkout", "HEAD", "--", p, check=False)
        _git_cmd(worktree.path, "clean", "-fd", "--", p, check=False)


def commit(worktree: Worktree, paths: tuple[str, ...], message: str) -> None:
    if not paths:
        return
    for p in paths:
        _git_cmd(worktree.path, "add", "-f", p)

    diff_proc = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=worktree.path,
    )
    if diff_proc.returncode == 0:
        return

    _git_cmd(worktree.path, "commit", "-m", message)


def push(worktree: Worktree) -> None:
    proc = subprocess.run(
        ["git", "push", "origin", worktree.branch],
        cwd=worktree.path,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr or proc.stdout
        raise WorktreeError(f"Push to origin/{worktree.branch} failed: {err.strip()}")


def remove(worktree: Worktree) -> None:
    root = worktree.path.parents[2]
    _git_cmd(root, "worktree", "remove", "--force", str(worktree.path), check=False)
    if worktree.path.exists():
        shutil.rmtree(worktree.path, ignore_errors=True)
