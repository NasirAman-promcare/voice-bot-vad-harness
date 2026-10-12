"""Git worktree and branch operations for relay execution.

CAPABILITIES:
  CAP-OUTSOURCING-WORKTREE: Git worktree management, branch creation, commit/push, attempt cleanup, and the
    per-order run lock.
    [tests: test_open_and_commit_worktree, test_discard_attempt,
    test_FR_1_0_02_mc01_mc08_mc11_accepted_run_end_to_end,
    test_FR_1_0_02_mc02_t1_order_never_goes_to_a_model_without_t1,
    test_FR_1_0_02_mc02_pinned_model_without_the_tier_exits_2,
    test_FR_1_0_02_mc03_daily_quota_switches_without_using_an_attempt,
    test_FR_1_0_02_mc03_pool_exhausted_pauses_then_resumes_at_the_same_part,
    test_FR_1_0_02_mc05_credential_error_moves_to_other_provider_with_access_line,
    test_FR_1_0_02_mc05_no_provider_left_exits_7, test_FR_1_0_02_mc06_questions_exit_4_keeps_earlier_parts,
    test_FR_1_0_02_mc07_read_only_test_changed_exits_9_and_commits_nothing,
    test_FR_1_0_02_mc09_cut_off_two_file_part_is_split_per_file, test_FR_1_0_02_mc09_cut_off_one_file_part_exits_5,
    test_FR_1_0_02_mc10_rerun_after_failed_attempt_discards_and_continues,
    test_FR_1_0_02_mc10_step_log_of_another_wp_branch_exits_2_before_any_merge,
    test_FR_1_0_14_mc12_models_reports_a_missing_model_and_exits_2, test_FR_1_0_14_models_all_present_exits_0,
    test_FR_1_0_14_mc13_too_large_for_one_model_goes_to_one_that_fits, test_FR_1_0_14_mc13_no_model_fits_exits_13,
    test_FR_1_0_02_dry_run_measures_and_sends_nothing, test_FR_1_0_14_status_reports_resets_and_sends_nothing]
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
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
  2026-10-12 WP-1.0 FR-1.0-02 (Claude): OrderLock moved here unchanged from relay.py (was _FileLock), so relay.py
    stays within 400 lines with its header's test names.
"""
from __future__ import annotations

import fcntl
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
    "OrderLock",
]


class OrderLock:
    """Exclusive, non-blocking lock so only one relay runs an order at a time (moved from relay.py)."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._fd: Any = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = open(self.lock_path, "a+")
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def release(self) -> None:
        if self._fd:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                self._fd.close()
            except (OSError, IOError):
                self._fd = None
            self._fd = None


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
