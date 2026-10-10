"""Scope checker verifying branch changes against work order allowed paths.

CAPABILITIES:
  CAP-OUTSOURCING-007: check branch changes against allowed outputs and logs [tests: test_FR_1_0_01_mc05_scope_reports_extra_file_and_deletion, test_FR_1_0_01_mc05_scope_counts_uncommitted_and_untracked_changes, test_FR_1_0_01_scope_passes_outputs_and_record_files, test_FR_1_0_01_mc08_missing_base_ref_is_never_no_changes, test_scope.py]
INPUTS AND OUTPUTS: ScopeError, ScopeReport, check_scope.
CONTRACTS: CHANGE_CONTROL.md change budget rules.
INVARIANTS:
  - Deletions and changes outside outputs, return logs or ledger are violations.
  - Missing base ref raises ScopeError after single fetch attempt.
NOT IN SCOPE:
  - Reverting unallowed changes.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tools.outsourcing.paths import normalise
from tools.outsourcing.workorder import WorkOrder

__all__ = ["ScopeError", "ScopeReport", "check_scope"]


class ScopeError(Exception):
    """Raised when base ref cannot be found or git execution fails."""


@dataclass(frozen=True)
class ScopeReport:
    violations: tuple[str, ...]
    changed_paths: tuple[str, ...]


def _run_git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise ScopeError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScopeError(f"git {' '.join(args)} timed out") from exc

    if proc.returncode != 0:
        raise ScopeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _is_allowed(path: str, order: WorkOrder) -> bool:
    if path in order.outputs:
        return True
    if path == f"docs/outsourcing/ledger.d/{order.id}.md":
        return True
    if fnmatch.fnmatch(path, f"docs/outsourcing/returns/{order.id}/*") or fnmatch.fnmatch(path, f"docs/outsourcing/returns/{order.id}/**/*"):
        return True
    if path.startswith(f"docs/outsourcing/returns/{order.id}/"):
        return True
    return False


def check_scope(
    order: WorkOrder,
    repo_root: str | Path,
    base_ref: str,
    head_ref: str = "HEAD",
) -> ScopeReport:
    root = Path(repo_root).resolve()

    # Step 1: find merge-base
    try:
        merge_base = _run_git(root, "merge-base", base_ref, head_ref).strip()
    except ScopeError:
        # Fetch once and retry B8 / E4
        try:
            _run_git(root, "fetch", "--quiet", "origin")
        except ScopeError:
            pass
        try:
            merge_base = _run_git(root, "merge-base", base_ref, head_ref).strip()
        except ScopeError as exc:
            raise ScopeError(f"Base ref {base_ref!r} cannot be found: {exc}") from exc

    if not merge_base:
        raise ScopeError(f"Base ref {base_ref!r} has no merge-base with {head_ref!r}")

    changed_set: set[str] = set()
    violations_set: set[str] = set()

    # Step 2: diff merge_base vs head_ref
    diff_out = _run_git(root, "diff", "--name-status", "--no-renames", "-z", merge_base, head_ref)
    parts = diff_out.split("\0")
    for status, raw_path in zip(parts[0::2], parts[1::2]):
        if not raw_path:
            continue
        try:
            norm_p = normalise(raw_path)
        except ValueError:
            norm_p = raw_path.strip()

        st_code = status[:1]
        if st_code == "D":
            violations_set.add(norm_p)
        else:
            changed_set.add(norm_p)
            if not _is_allowed(norm_p, order):
                violations_set.add(norm_p)

    # Step 3: if head_ref == "HEAD", check uncommitted/untracked
    if head_ref == "HEAD":
        status_out = _run_git(root, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all")
        for entry in status_out.split("\0"):
            if len(entry) < 4:
                continue
            code, raw_path = entry[:2], entry[3:]
            try:
                norm_p = normalise(raw_path)
            except ValueError:
                norm_p = raw_path.strip()

            if "D" in code:
                violations_set.add(norm_p)
            elif "?" in code or "A" in code or "M" in code or "R" in code or "C" in code:
                changed_set.add(norm_p)
                if not _is_allowed(norm_p, order):
                    violations_set.add(norm_p)

    return ScopeReport(
        violations=tuple(sorted(violations_set)),
        changed_paths=tuple(sorted(changed_set)),
    )
