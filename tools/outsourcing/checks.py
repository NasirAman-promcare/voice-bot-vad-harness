"""Check runner for relay step verification.

CAPABILITIES:
  CAP-OUTSOURCING-CHECKS: Run checks and collect results for relay runs [tests: test_checks.py, test_acceptance_wo_1_0_02.py]
INPUTS AND OUTPUTS: WorkOrder, step part / outputs, worktree path, log dir, base commit, python, timeout in; CheckResults or hash dict out.
CONTRACTS: none.
INVARIANTS:
  - Hashes read-only tests before and after verification runs to detect integrity violations.
NOT IN SCOPE:
  - Network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): the read-only-tests check compares each read-only test with
    its base-commit version (it reported a pass without comparing); a changed read-only test is an integrity
    failure in scope or that check; kit-staging/ code is scanned with the gate's code patterns; check commands run
    with PYTHONDONTWRITEBYTECODE=1 so a stale bytecode cache can never stand in for a changed file.
"""
from __future__ import annotations

import hashlib
import os
import py_compile
import shlex
import signal
import subprocess
import tempfile
from pathlib import Path
from tools.audit import gate, patterns
from tools.outsourcing import scope
from tools.outsourcing.records import CheckResult, CheckResults, StepPart
from tools.outsourcing.workorder import WorkOrder

__all__ = ["quick_checks", "full_checks", "hash_read_only_tests"]


def hash_read_only_tests(order: WorkOrder, worktree_path: str | Path) -> dict[str, str]:
    """Compute SHA-256 hashes for all read-only test files in order."""
    wt = Path(worktree_path)
    res: dict[str, str] = {}
    for ro_path in order.read_only_tests:
        full = wt / ro_path
        if full.is_file():
            res[ro_path] = hashlib.sha256(full.read_bytes()).hexdigest()
        else:
            res[ro_path] = ""
    return res


def _check_module_headers(paths: tuple[str, ...], wt: Path) -> tuple[bool, str]:
    """Check module header compliance on python files in paths."""
    required_sections = [
        "CAPABILITIES:",
        "INPUTS AND OUTPUTS:",
        "CONTRACTS:",
        "INVARIANTS:",
        "NOT IN SCOPE:",
        "CHANGE LOG:",
    ]
    missing_files: list[str] = []

    for rel_p in paths:
        if not rel_p.endswith(".py"):
            continue
        full_p = wt / rel_p
        if not full_p.is_file():
            continue

        text = full_p.read_bytes().decode("utf-8", errors="replace")
        meaningful = [line for line in text.splitlines() if line.strip()]
        if not meaningful:
            continue

        header_chunk = "\n".join(text.splitlines()[:80])
        for sec in required_sections:
            if sec not in header_chunk:
                missing_files.append(f"{rel_p} (missing {sec})")
                break

    if missing_files:
        return False, f"Module header check failed for: {', '.join(missing_files)}"
    return True, "Module headers ok"


def _scan_table(rel_p: str) -> tuple[list, str] | None:
    """The audit gate's table for a path; kit-staging/ code, which the gate does not scan, gets its code patterns."""
    found = gate.scan_table(rel_p)
    if found is None and rel_p.startswith("kit-staging/") and rel_p.endswith(patterns.SCANNED_SUFFIXES):
        return patterns.CODE_PATTERNS, "C1"
    return found


def _compare_read_only_with_base(order: WorkOrder, wt: Path, base_commit: str) -> tuple[bool, str]:
    """Compare each read-only test's SHA-256 in the worktree with its version at base_commit."""
    changed: list[str] = []
    for ro_path in order.read_only_tests:
        proc = subprocess.run(["git", "show", f"{base_commit}:{ro_path}"], cwd=wt, capture_output=True, timeout=60)
        if proc.returncode != 0:
            changed.append(f"{ro_path} (not in base {base_commit}: {proc.stderr.decode('utf-8', 'replace').strip()})")
            continue
        current = wt / ro_path
        if not current.is_file():
            changed.append(f"{ro_path} (deleted)")
        elif hashlib.sha256(current.read_bytes()).hexdigest() != hashlib.sha256(proc.stdout).hexdigest():
            changed.append(f"{ro_path} (changed)")
    if changed:
        return False, f"Integrity violation: read-only tests differ from base: {', '.join(changed)}"
    return True, f"{len(order.read_only_tests)} read-only test(s) match base {base_commit[:12]}"


def _check_compromise_patterns(paths: tuple[str, ...], wt: Path) -> tuple[bool, str]:
    """Scan every line of python files in paths for compromise/test-integrity patterns."""
    flagged: list[str] = []

    for rel_p in paths:
        scan_info = _scan_table(rel_p)
        if scan_info is None:
            continue
        table, rule_id = scan_info

        full_p = wt / rel_p
        if not full_p.is_file():
            continue

        text = full_p.read_bytes().decode("utf-8", errors="replace")
        for idx, line in enumerate(text.splitlines(), start=1):
            if patterns.ALLOW_RE.search(line):
                continue
            for label, rx in table:
                if rx.search(line):
                    flagged.append(f"{rel_p}:{idx} [{label}]")
                    break

    if flagged:
        return False, f"Compromise pattern violations: {', '.join(flagged)}"
    return True, "Compromise patterns ok"


def _check_compile(paths: tuple[str, ...], wt: Path) -> tuple[bool, str]:
    """Check that all python files compile."""
    failed: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for rel_p in paths:
            if not rel_p.endswith(".py"):
                continue
            full_p = wt / rel_p
            if not full_p.is_file():
                continue
            try:
                py_compile.compile(str(full_p), cfile=os.path.join(tmp_dir, "temp.pyc"), doraise=True)
            except Exception as exc:
                failed.append(f"{rel_p}: {exc}")

    if failed:
        return False, f"Compilation failed: {'; '.join(failed)}"
    return True, "Compilation ok"


def _run_command(
    cmd_args: list[str],
    cwd: Path,
    log_file: Path,
    timeout: int,
    env_override: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a command with process group timeout and write output to log_file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # No bytecode caches: a fix that keeps a file's size within the same second would otherwise run the cached old code,
    # and cache files would show up as changes in the next scope check.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_override:
        env.update(env_override)

    return _exec_proc(cmd_args, cwd, log_file, timeout, env)


def _exec_proc(
    cmd_args: list[str],
    cwd: Path,
    log_file: Path,
    timeout: int,
    env: dict[str, str],
) -> tuple[bool, str]:
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd_args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        try:
            out_bytes, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            out_bytes, _ = proc.communicate()
    except Exception as exc:
        msg = f"Failed to execute command {' '.join(cmd_args)}: {exc}"
        log_file.write_text(msg, encoding="utf-8", errors="replace")
        return False, msg

    return _write_command_log(out_bytes, timed_out, timeout, proc.returncode, log_file)


def _write_command_log(
    out_bytes: bytes,
    timed_out: bool,
    timeout: int,
    returncode: int,
    log_file: Path,
) -> tuple[bool, str]:
    text = out_bytes.decode("utf-8", errors="replace")
    if timed_out:
        text += f"\ntimed out after {timeout} s\n"

    log_file.write_text(text, encoding="utf-8", errors="replace")

    if timed_out:
        return False, f"timed out after {timeout} s"
    if returncode != 0:
        return False, f"command failed with returncode {returncode}"
    return True, "command passed"


def _find_mentioned_outputs(log_file: Path, allowed_outputs: tuple[str, ...]) -> tuple[str, ...]:
    """Find outputs named in log file by exact path match."""
    if not log_file.is_file():
        return ()
    try:
        log_text = log_file.read_bytes().decode("utf-8", errors="replace")
    except Exception:
        return ()

    found: set[str] = set()
    for out_p in allowed_outputs:
        if out_p in log_text:
            found.add(out_p)
    return tuple(sorted(found))


def _check_scope_and_headers(order: WorkOrder, paths: tuple[str, ...], wt: Path, ld: Path, base_commit: str, results: list[CheckResult]) -> bool:
    scope_passed, scope_sum = True, "Scope check passed"
    scope_log = ld / "scope.log"
    try:
        s_rep = scope.check_scope(order, wt, base_commit)
        if s_rep.violations:
            scope_passed, scope_sum = False, f"Scope violations: {', '.join(s_rep.violations)}"
            scope_log.write_text(scope_sum, encoding="utf-8")
        else:
            scope_log.write_text("Scope check passed\n", encoding="utf-8")
    except Exception as exc:
        scope_passed, scope_sum = False, f"Scope check error: {exc}"
        scope_log.write_text(scope_sum, encoding="utf-8")

    touched_read_only = not scope_passed and any(p in scope_sum for p in order.read_only_tests)
    results.append(CheckResult("scope", scope_passed, scope_sum, scope_log, _find_mentioned_outputs(scope_log, order.outputs),
                               touched_read_only))
    if not scope_passed:
        return False

    hdr_passed, hdr_sum = _check_module_headers(paths, wt)
    hdr_log = ld / "headers.log"
    hdr_log.write_text(hdr_sum + "\n", encoding="utf-8")
    results.append(CheckResult("headers", hdr_passed, hdr_sum, hdr_log, _find_mentioned_outputs(hdr_log, order.outputs), False))
    return hdr_passed


def _check_patterns_readonly_and_compile(order: WorkOrder, paths: tuple[str, ...], wt: Path, ld: Path, base_commit: str,
                                         results: list[CheckResult]) -> bool:
    pat_passed, pat_sum = _check_compromise_patterns(paths, wt)
    pat_log = ld / "patterns.log"
    pat_log.write_text(pat_sum + "\n", encoding="utf-8")
    results.append(CheckResult("patterns", pat_passed, pat_sum, pat_log, _find_mentioned_outputs(pat_log, order.outputs), False))
    if not pat_passed:
        return False

    ro_passed, ro_sum = _compare_read_only_with_base(order, wt, base_commit)
    ro_log = ld / "read_only_tests.log"
    ro_log.write_text(ro_sum + "\n", encoding="utf-8")
    results.append(CheckResult("read-only-tests", ro_passed, ro_sum, ro_log, _find_mentioned_outputs(ro_log, order.outputs),
                               not ro_passed))
    if not ro_passed:
        return False

    cmp_passed, cmp_sum = _check_compile(paths, wt)
    cmp_log = ld / "compile.log"
    cmp_log.write_text(cmp_sum + "\n", encoding="utf-8")
    results.append(CheckResult("compile", cmp_passed, cmp_sum, cmp_log, _find_mentioned_outputs(cmp_log, order.outputs), False))
    return cmp_passed


def _run_static_checks(
    order: WorkOrder,
    paths: tuple[str, ...],
    wt: Path,
    ld: Path,
    base_commit: str,
) -> tuple[list[CheckResult], bool]:
    results: list[CheckResult] = []
    if not _check_scope_and_headers(order, paths, wt, ld, base_commit, results):
        return results, False

    if not _check_patterns_readonly_and_compile(order, paths, wt, ld, base_commit, results):
        return results, False

    return results, True


def quick_checks(
    order: WorkOrder,
    part: StepPart,
    worktree_path: str | Path,
    log_dir: str | Path,
    base_commit: str,
    python: str,
    timeout: int,
) -> CheckResults:
    """Run quick checks after a step part is imported."""
    wt = Path(worktree_path).resolve()
    ld = Path(log_dir).resolve()
    ld.mkdir(parents=True, exist_ok=True)

    initial_ro_hashes = hash_read_only_tests(order, wt)
    results, ok = _run_static_checks(order, part.paths, wt, ld, base_commit)
    if not ok:
        return CheckResults(tuple(results))

    test_files = [p for p in part.paths if p.startswith("tests/") and p.endswith(".py")]
    if test_files:
        test_log = ld / "tests.log"
        cmd = [python, "-m", "pytest", *test_files, "-q", "--tb=short"]
        t_passed, t_sum = _run_command(cmd, wt, test_log, timeout)

        post_ro_hashes = hash_read_only_tests(order, wt)
        if initial_ro_hashes != post_ro_hashes:
            results.append(CheckResult("tests", False, "Integrity violation: read-only test files modified during test run", test_log, _find_mentioned_outputs(test_log, order.outputs), True))
            return CheckResults(tuple(results))

        results.append(CheckResult("tests", t_passed, t_sum, test_log, _find_mentioned_outputs(test_log, order.outputs), False))

    return CheckResults(tuple(results))


def full_checks(
    order: WorkOrder,
    worktree_path: str | Path,
    log_dir: str | Path,
    base_commit: str,
    python: str,
    timeout: int,
) -> CheckResults:
    """Run full checks over all outputs and execute all verify commands."""
    wt = Path(worktree_path).resolve()
    ld = Path(log_dir).resolve()
    ld.mkdir(parents=True, exist_ok=True)

    initial_ro_hashes = hash_read_only_tests(order, wt)
    results, ok = _run_static_checks(order, order.outputs, wt, ld, base_commit)
    if not ok:
        return CheckResults(tuple(results))

    for idx, v_cmd in enumerate(order.verify, start=1):
        v_name = f"verify-{idx}"
        v_log = ld / f"{v_name}.log"

        parts = shlex.split(v_cmd)
        if parts and parts[0] == ".venv/bin/python":
            parts[0] = python

        v_passed, v_sum = _run_command(parts, wt, v_log, timeout)

        post_ro_hashes = hash_read_only_tests(order, wt)
        if initial_ro_hashes != post_ro_hashes:
            results.append(CheckResult(v_name, False, "Integrity violation: read-only test files modified during verify command", v_log, _find_mentioned_outputs(v_log, order.outputs), True))
            return CheckResults(tuple(results))

        results.append(CheckResult(v_name, v_passed, v_sum, v_log, _find_mentioned_outputs(v_log, order.outputs), False))
        if not v_passed:
            return CheckResults(tuple(results))

    return CheckResults(tuple(results))
