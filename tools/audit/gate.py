"""AQIS lab audit gate: checks a branch's changes for rule violations and exits 0 only when none are found.

Usage (from inside the repository):
  python -m tools.audit.gate --base <ref> [--wp <WP-ID>] [--json]

CAPABILITIES:
  CAP-AUDIT-001: check (a) protected paths per docs/process/PROTECTED_PATHS.txt with approvals read from origin/main [tests: test_FR_0_0_05_a_detects_never_path, test_FR_0_0_05_a_detects_guarded_path_without_approval, test_FR_0_0_05_a_passes_guarded_path_with_main_approval, test_FR_0_0_05_a_ignores_approval_committed_only_on_branch, test_FR_0_0_05_a_ignores_expired_or_withdrawn_approval, test_FR_0_0_05_a_uses_approval_added_on_main_after_branch_point, test_FR_0_0_05_a_honours_withdrawal_on_main_after_branch_point, test_FR_0_0_06_approvals_none_when_origin_main_unverifiable, test_FR_0_0_06_fails_closed_when_protected_paths_unreadable, test_FR_0_0_05_a_builtin_never_list_applies_when_policy_section_removed, test_FR_0_0_05_a_approvals_readme_approves_nothing, test_FR_0_0_05_a_detects_renamed_guarded_harness_test, test_FR_0_0_05_a_approval_lines_must_start_the_line, test_FR_0_0_05_a_standard_approval_lines_still_approve, test_FR_0_0_05_a_fetches_missing_origin_main_once, test_FR_0_0_06_parity_lowercase_readme_approval_approves_nothing]
  CAP-AUDIT-002: check (b) existing tests modified or deleted without ALLOW-EDIT [tests: test_FR_0_0_05_b_detects_modified_existing_test, test_FR_0_0_05_b_detects_deleted_existing_test, test_FR_0_0_05_b_passes_new_test_and_approved_edit, test_FR_0_0_05_b_detects_renamed_existing_lab_test, test_FR_0_0_05_b_allow_patterns_in_does_not_approve_test_edits]
  CAP-AUDIT-003: check (c) compromise patterns in added lab code lines and test-integrity patterns in added lab test lines [tests: test_FR_0_0_05_c_detects_each_code_pattern, test_FR_0_0_05_c_detects_each_test_pattern, test_FR_0_0_05_c_scans_only_added_lines, test_FR_0_0_05_c_includes_uncommitted_and_untracked_work, test_FR_0_0_06_scans_v2_file_types_and_dirs, test_FR_0_0_06_flags_pytestmark_and_param_skips, test_FR_0_0_06_decodes_non_utf8_with_replacement, test_FR_0_0_06_fails_closed_on_unreadable_changed_file, test_FR_0_0_06_fails_closed_on_git_error, test_FR_0_0_05_c_indented_allow_patterns_in_exempts_nothing, test_FR_0_0_06_fails_closed_when_branch_diff_fails, test_FR_0_0_06_fails_closed_when_git_status_fails, test_FR_0_0_06_fails_closed_on_changed_file_it_cannot_read]
  CAP-AUDIT-004: check (d) CAPABILITIES header in new aqis_lab/ modules [tests: test_FR_0_0_05_d_detects_new_module_without_header, test_FR_0_0_05_d_passes_module_with_header_or_short_file]
  CAP-AUDIT-005: check (e) capability registry consistency [tests: test_FR_0_0_08_detects_row_with_missing_test, test_FR_0_0_08_detects_row_with_missing_module, test_FR_0_0_08_detects_row_removed_since_base, test_FR_0_0_08_detects_malformed_row, test_FR_0_0_08_detects_missing_registry, test_FR_0_0_08_passes_consistent_registry, test_FR_0_0_08_repository_registry_is_consistent, test_FR_0_0_08_detects_reordered_header_columns, test_FR_0_0_08_table_ends_at_first_non_table_line, test_FR_0_0_08_row_names_only_tests_pytest_collects, test_FR_0_0_08_row_naming_collected_tests_passes, test_FR_0_0_06_fails_closed_when_base_registry_unreadable, test_FR_0_0_08_registry_module_that_is_a_folder_is_a_finding, test_FR_0_0_08_registry_row_without_capability_id_is_malformed, test_FR_0_0_09_index_follows_pytest_collection_rules, test_FR_0_0_09_index_counts_every_collected_probe_test, test_FR_0_0_09_non_literal_collect_ignore_is_an_error, test_FR_0_0_09_index_applies_conftests_above_the_collected_folder, test_FR_0_0_06_fails_closed_on_unparsable_lab_test_file]
  CAP-AUDIT-006: check (f) requirement traceability for --wp [tests: test_FR_0_0_09_detects_id_missing_from_plan, test_FR_0_0_09_detects_id_missing_from_test_names, test_FR_0_0_09_detects_id_missing_from_evidence, test_FR_0_0_09_underscore_matching_respects_boundaries, test_FR_0_0_09_ignores_other_wp_ids_in_spec, test_FR_0_0_09_reports_unknown_wp, test_FR_0_0_09_passes_complete_traceability, test_FR_0_0_09_detects_nfr_id_missing_from_test_names, test_FR_0_0_09_detects_id_only_in_uncollected_test, test_FR_0_0_06_fails_closed_when_spec_unreadable, test_FR_0_0_09_two_specs_for_one_wp_is_a_finding, test_FR_0_0_09_only_lab_test_names_count, test_FR_0_0_09_traces_every_id_on_a_spec_line]
  CAP-AUDIT-007: lists every audit-allow line and every ALLOW-PATTERNS-IN exempted file [tests: test_FR_0_0_07_audit_allow_with_reason_exempts_and_is_listed, test_FR_0_0_07_audit_allow_without_reason_does_not_exempt, test_FR_0_0_07_audit_allow_exempts_only_its_line, test_FR_0_0_07_allow_patterns_in_exempts_file_and_is_listed, test_FR_0_0_07_exempted_files_list_only_scanned_files]
  CAP-AUDIT-009: command line, merge-base diffing, text and JSON reports, exit codes 0/1/2 [tests: test_FR_0_0_05_clean_branch_exits_zero, test_FR_0_0_05_uses_merge_base_not_ref_tip, test_FR_0_0_05_json_output_schema, test_FR_0_0_05_bad_base_ref_exits_2, test_NFR_0_0_01_gate_runtime_under_60s, test_NFR_0_0_02_every_message_names_file_line_and_rule, test_NFR_0_0_03_imports_are_stdlib_or_pinned]
INPUTS AND OUTPUTS: git state of the repository containing the cwd; a report on stdout; exit 0 (no findings),
  1 (findings) or 2 (the gate could not run, message on stderr).
CONTRACTS: checks (a) to (d) reproduce .claude/hooks/stop_gate.py exactly (FR-0.0-06); documented in docs/tools/AUDIT_GATE.md.
INVARIANTS:
  - Read-only: never writes to the repository; the only network action is fetching origin/main when it is missing.
  - Standard library plus tools.audit.patterns only (NFR-0.0-03); runs on Python 3.10 or newer.
  - Every finding names path:line and a rule ID (NFR-0.0-02).
NOT IN SCOPE:
  - Running tests (the Stop hook and CI do that).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-05 created.
  2026-09-25 WP-0.0 round 2 FR-0.0-06 (amended), F04, F09: Stop hook v2/v3 scan scope and status mapping;
             fail closed (read_changed_file, diff_against_base, load_protected, registry, spec, test files);
             UTF-8 decoding with replacement; no approvals when origin/main is unverifiable; F1 cites the glob.
  2026-09-25 WP-0.0 audit round 4 F28: header lists the new rename, built-in NEVER and README tests (header only).
  2026-09-26 WP-0.0 audit round 5 F33: header lists the approval-line tests (header only).
  2026-09-26 WP-0.0 audit round 6 F40: header lists the NFR traceability test (header only).
  2026-09-26 WP-0.0 audit round 6 F46: header lists the origin/main fetch and registry table-shape tests (header only).
  2026-09-26 WP-0.0 audit round 8 F47: test_functions mirrors pytest's default collection (file names, Test classes
             without constructors or __test__ = False, nested Test classes, no fixtures or properties);
             a Test class with a base class from another file does not count (fails closed).
  2026-09-26 WP-0.0 round 8 must-catch 7: header lists the branch-diff and git-status fail-closed tests (header only).
  2026-09-27 WP-0.0 audit round 9 F56/F57: header lists the ALLOW-PATTERNS-IN and read-error tests; F61: the
             test_functions docstring states the pytest rules it does not model (docstring only).
  2026-10-04 WP-0.9 DEBT-004: test_functions follows pytest 9.1's collection rules for skipped folders, conftest
             collect_ignore(_glob), false or unreadable __test__ values, abstract classes and rebound names;
             DEBT-001 to DEBT-003 and DEBT-005: header lists the new tests.
  2026-10-08 WP-0.9 round 2 F04: _ignores_for and _pytest_skips read conftests from the repository root down,
             also those above the collected folder; header lists the new test.
"""
import argparse
import ast
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from tools.audit import patterns

TOOL = "aqis-audit-gate"
APPROVALS_REF = "origin/main"
SECTIONS = ("NEVER", "GUARDED", "LAB-OWNED")
# Always enforced, even if the list file is missing or damaged (same as the hooks).
DEFAULT_NEVER = ("CLAUDE.md", ".claude/**", "docs/specs/**", "docs/process/**", "docs/approvals/**")
LAB_CODE_DIRS = patterns.LAB_CODE_DIRS
LAB_TEST_DIR = patterns.LAB_TEST_DIR
FIXTURE_DIR = "tests/aqis_lab/fixtures/"
REGISTRY = "docs/capabilities/REGISTRY.md"
REGISTRY_COLUMNS = ("Capability ID", "Module", "Functions", "What it does", "Tests", "Introduced by", "Status")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
WP_RE = re.compile(r"^WP-(\d+\.\d+)$")
ID_PREFIXES_WITH_TESTS = ("FR", "NFR")
ID_PREFIXES_DOCS_ONLY = ("AT", "OC")


class GateError(Exception):
    """The gate could not run or could not read something it must check (exit 2, never a pass)."""


@dataclass
class Finding:
    rule: str
    check: str
    severity: str
    path: str
    line: int
    message: str
    state: str = ""
    label: str = ""
    text: str = ""

    def render(self):
        return f"{self.path}:{self.line}: [{self.rule}] {self.severity}: {self.message}"


@dataclass
class Report:
    base_ref: str
    base_commit: str
    head_commit: str
    approvals_commit: str
    wp: str = None
    findings: list = field(default_factory=list)
    exempted_lines: list = field(default_factory=list)
    exempted_files: list = field(default_factory=list)


# ---------------------------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------------------------
class Git:
    def __init__(self, root):
        self.root = Path(root)

    def run(self, *args, timeout=60):
        """(returncode, stdout, stderr) of a git command in the repository."""
        try:
            proc = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout)
        except FileNotFoundError as exc:
            raise GateError("git is not installed or not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise GateError(f"git {' '.join(args)} did not finish within {timeout} s") from exc
        return proc.returncode, proc.stdout, proc.stderr

    def out(self, *args):
        rc, out, err = self.run(*args)
        if rc != 0:
            raise GateError(f"git {' '.join(args)} failed: {err.strip() or 'no message'}")
        return out

    def exists(self, ref, path):
        return bool(ref) and self.run("cat-file", "-e", f"{ref}:{path}")[0] == 0

    def commit_of(self, ref):
        rc, out, _ = self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        return out.strip() if rc == 0 and out.strip() else None


def repository_root(cwd):
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
    except FileNotFoundError as exc:
        raise GateError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GateError("git rev-parse --show-toplevel did not finish within 60 s") from exc
    if proc.returncode != 0:
        raise GateError(f"{cwd} is not inside a git repository: {proc.stderr.strip()}")
    return Path(proc.stdout.strip())


# ---------------------------------------------------------------------------------------------
# policy: protected paths and approvals (same semantics as .claude/hooks/_protected.py)
# ---------------------------------------------------------------------------------------------
glob_to_regex = patterns.glob_to_regex  # one implementation, shared with the scan scope


def load_protected(root):
    """{section: [regex]} from the working-tree PROTECTED_PATHS.txt plus the built-in NEVER list.

    Fails closed (GateError) when the list is missing or unreadable (difference G2 from the Stop hook,
    which falls back to the built-in NEVER list; owner decision R2-2).
    """
    sections = {name: [] for name in SECTIONS}
    current = None
    policy = Path(root) / "docs" / "process" / "PROTECTED_PATHS.txt"
    try:
        text = policy.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise GateError(f"docs/process/PROTECTED_PATHS.txt:1: cannot read the protected-path list: {exc}") from exc
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        header = re.fullmatch(r"\[([A-Z-]+)\]", line)
        if header:
            current = header.group(1) if header.group(1) in SECTIONS else None
            continue
        if current:
            sections[current].append(glob_to_regex(line))
    sections["NEVER"].extend(glob_to_regex(p) for p in DEFAULT_NEVER)
    return sections


def classify(rel, sections):
    """'NEVER', 'LAB', 'GUARDED' or None for a repo-relative POSIX path."""
    if any(rx.match(rel) for rx in sections["NEVER"]):
        return "NEVER"
    if any(rx.match(rel) for rx in sections["LAB-OWNED"]):
        return "LAB"
    if any(rx.match(rel) for rx in sections["GUARDED"]):
        return "GUARDED"
    return None


@dataclass
class Approvals:
    edit_rules: list
    pattern_rules: list
    files: list


def resolve_approvals_ref(git):
    """Commit of origin/main, fetching it once if it is missing (as the hooks do); None when unverifiable.

    Without a verified origin/main no approval counts (FR-0.0-06 amended): the caller then applies none,
    which can only add findings, never remove them.
    """
    commit = git.commit_of(APPROVALS_REF)
    if commit is None:
        git.run("fetch", "--quiet", "origin", "main:refs/remotes/origin/main", timeout=120)
        commit = git.commit_of(APPROVALS_REF)
    return commit


def load_approvals(git, ref):
    """Rules from approval files with STATUS: APPROVED committed at ref (never the working tree); none if ref is None."""
    edit_rules, pattern_rules, files = [], [], []
    if ref is None:
        return Approvals(edit_rules, pattern_rules, files)
    today = date.today().isoformat()
    rc, out, _ = git.run("ls-tree", "--name-only", f"{ref}:docs/approvals")
    names = [n for n in out.splitlines() if n.endswith(".md")] if rc == 0 else []
    for name in names:
        if name.lower() == "readme.md":
            continue
        rc2, text, _ = git.run("show", f"{ref}:docs/approvals/{name}")
        if rc2 != 0:
            continue
        if not re.search(r"^STATUS:\s*APPROVED\s*$", text, re.M):
            continue
        expires = re.search(r"^EXPIRES:\s*(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
        if expires and expires.group(1) < today:
            continue
        files.append(name)
        for m in re.finditer(r"^ALLOW-EDIT:\s*(\S+)\s*$", text, re.M):
            edit_rules.append((glob_to_regex(m.group(1)), name, m.group(1)))
        for m in re.finditer(r"^ALLOW-PATTERNS-IN:\s*(\S+)\s*$", text, re.M):
            pattern_rules.append((glob_to_regex(m.group(1)), name, m.group(1)))
    return Approvals(edit_rules, pattern_rules, files)


def matching_rule(rules, path):
    for rx, name, glob in rules:
        if rx.match(path):
            return name, glob
    return None


# ---------------------------------------------------------------------------------------------
# changes since the base (same semantics as .claude/hooks/stop_gate.py)
# ---------------------------------------------------------------------------------------------
def changed_files(git, base):
    """{path: 'A'|'M'|'D'} for committed changes since base plus uncommitted and untracked work."""
    changes = {}
    rc, out, _ = git.run("diff", "--name-status", "--no-renames", "-z", base, "HEAD")
    if rc != 0:
        raise GateError(f"git diff against {base} failed")
    parts = out.split("\0")
    for status, path in zip(parts[0::2], parts[1::2]):
        if path:
            changes[path] = status[:1]
    rc, out, _ = git.run("status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all")
    if rc != 0:
        raise GateError("git status failed")
    for entry in out.split("\0"):
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if "?" in code or "A" in code:
            state = "A"
        elif "D" in code:
            state = "D"
        else:
            state = "M"
        previous = changes.get(path)
        if previous == "A":
            if state == "D":
                changes.pop(path)  # added on this branch, then removed again
            continue
        changes[path] = state
    return changes


def read_changed_file(git, path):
    """Text of a changed file (UTF-8 with replacement); None when nothing exists at the path.

    Fails closed: a path that exists but is not a regular file (for example a dangling symlink) or cannot
    be read raises GateError (difference G2: the Stop hook skips such a file silently; owner decision R2-2).
    """
    full = git.root / path
    if not os.path.lexists(full):
        return None  # staged as added, then removed from the working tree: nothing left to scan
    if not full.is_file():
        raise GateError(f"{path}:1: changed file is not a regular file (for example a dangling symlink); cannot scan it")
    try:
        return full.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise GateError(f"{path}:1: cannot read changed file: {exc}") from exc


def diff_against_base(git, base, path):
    rc, out, err = git.run("diff", "-U0", "--no-color", "--text", base, "--", path)
    if rc != 0:
        raise GateError(f"{path}:1: git diff against {base[:12]} failed: {err.strip() or 'no message'}")
    return out


def added_lines(git, base, path):
    """[(line_number, text)] for lines added relative to base (or all lines of a new file)."""
    text = read_changed_file(git, path)
    if text is None:
        return []
    if not git.exists(base, path):
        return list(enumerate(text.splitlines(), start=1))
    out = diff_against_base(git, base, path)
    lines, new_no = [], 0
    for line in out.splitlines():
        hunk = HUNK_RE.match(line)
        if hunk:
            new_no = int(hunk.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines.append((new_no, line[1:]))
            new_no += 1
    return lines


def first_changed_line(git, base, path, state):
    """Line to cite for a whole-file finding: first changed line of a modified text file, else 1."""
    if state != "M":
        return 1
    for line in diff_against_base(git, base, path).splitlines():
        hunk = HUNK_RE.match(line)
        if hunk:
            return max(int(hunk.group(1)), 1)
    return 1


# ---------------------------------------------------------------------------------------------
# checks (a) to (d): identical rules to the Stop hook
# ---------------------------------------------------------------------------------------------
def check_protected_and_tests(git, base, changes, sections, approvals, report):
    for path, state in sorted(changes.items()):
        kind = classify(path, sections)
        if kind == "NEVER":
            report.findings.append(Finding(
                "A1", "a", "CRITICAL", path, first_changed_line(git, base, path, state),
                f"owner-only path changed [{state}] (NEVER list in docs/process/PROTECTED_PATHS.txt)", state=state))
        elif kind == "GUARDED" and not matching_rule(approvals.edit_rules, path):
            report.findings.append(Finding(
                "A2", "a", "CRITICAL", path, first_changed_line(git, base, path, state),
                f"guarded harness path changed [{state}] without an ALLOW-EDIT approval on {APPROVALS_REF}",
                state=state))
        if path.startswith("tests/") and path.endswith(".py") and state in ("M", "D"):
            if git.exists(base, path) and not matching_rule(approvals.edit_rules, path):
                deleted = state == "D"
                report.findings.append(Finding(
                    "B2" if deleted else "B1", "b", "CRITICAL", path, first_changed_line(git, base, path, state),
                    f"existing test {'deleted' if deleted else 'modified'} without an ALLOW-EDIT approval "
                    f"on {APPROVALS_REF}", state=state))


def scan_table(path):
    """(patterns, rule) for a path inside the lab scan scope of Stop hook v2/v3, else None."""
    if path.startswith(LAB_TEST_DIR) and path.endswith(".py"):
        return patterns.TEST_PATTERNS, "C2"
    if ((path.startswith(LAB_CODE_DIRS) or patterns.LAB_CI_FILES.match(path))
            and path.endswith(patterns.SCANNED_SUFFIXES)):
        return patterns.CODE_PATTERNS, "C1"
    return None


def check_patterns_and_headers(git, base, changes, approvals, report):
    for path, state in sorted(changes.items()):
        if state == "D":
            continue
        scope = scan_table(path)
        exemption = matching_rule(approvals.pattern_rules, path)
        if exemption:
            if scope:
                report.exempted_files.append({"path": path, "approval": exemption[0], "glob": exemption[1]})
            continue
        if scope is None:
            continue
        table, rule = scope
        for number, text in added_lines(git, base, path):
            if patterns.ALLOW_RE.search(text):
                reason = patterns.ALLOW_REASON_RE.search(text).group(1).strip()
                report.exempted_lines.append({"path": path, "line": number, "reason": reason})
                continue
            for label, rx in table:
                if rx.search(text):
                    report.findings.append(Finding(
                        rule, "c", "COMPROMISE", path, number, f"{label}: {text.strip()[:110]}",
                        state=state, label=label, text=text))
                    break
        if path.startswith("aqis_lab/") and path.endswith(".py") and state == "A":
            content = read_changed_file(git, path) or ""
            meaningful = [line for line in content.splitlines() if line.strip()]
            if len(meaningful) > 5 and not patterns.HEADER_RE.search("\n".join(content.splitlines()[:80])):
                report.findings.append(Finding(
                    "D1", "d", "MAJOR", path, 1,
                    "new lab module without a CAPABILITIES header in its first 80 lines "
                    "(docs/process/CHANGE_CONTROL.md)", state=state))


# ---------------------------------------------------------------------------------------------
# shared: test function index
# ---------------------------------------------------------------------------------------------
TEST_FILE_GLOBS = ("test_*.py", "*_test.py")  # pytest's default python_files
NOT_TEST_DECORATORS = ("fixture", "property")  # pytest never collects these as tests


def _decorator_name(node):
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else ""


def _is_test_def(node):
    return (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")
            and not any(_decorator_name(d) in NOT_TEST_DECORATORS for d in node.decorator_list))


def _sets_test_false(body):
    """True when the body leaves __test__ bound to a false value (pytest then collects nothing from it), or to
    a value the gate cannot read (not a literal), which does not count either (fails closed)."""
    statement = _final_bindings(body).get("__test__")
    if statement is None:
        return False
    value = _literal_test_value(statement)
    return value is _UNREADABLE or not value


_UNREADABLE = object()


def _literal_test_value(statement):
    """The value a plain `__test__ = <literal>` statement binds, else _UNREADABLE."""
    if isinstance(statement, ast.Assign) and all(isinstance(t, ast.Name) for t in statement.targets):
        value = statement.value
    elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value:
        value = statement.value
    else:
        return _UNREADABLE
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _UNREADABLE


COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _bound_names(statement):
    """Names a module- or class-level statement binds, including inside compound statements; function, class
    and lambda bodies and comprehension scopes are not entered. A star import binds '*'."""
    names = set()

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            for child in node.decorator_list:
                visit(child)
            return
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, COMPREHENSIONS):
            names.update(n.target.id for n in ast.walk(node) if isinstance(n, ast.NamedExpr))
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.alias):
            names.add("*" if node.name == "*" else (node.asname or node.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(statement)
    return names


def _final_bindings(body):
    """{name: the last statement of body that binds it}. A binding inside a compound statement (if, try, for,
    ...) maps to that compound statement, which is never a def, so a conditionally rebound name does not count."""
    last = {}
    for statement in body:
        for name in _bound_names(statement):
            last[name] = statement
    return last


def _defs_pytest_keeps(body):
    """The defs and class definitions of body whose name still refers to them after the whole body has run (pytest
    collects a module's or class's final namespace). A star import after a definition may rebind it, so such a
    definition does not count."""
    final = _final_bindings(body)
    star = max((i for i, s in enumerate(body) if "*" in _bound_names(s)), default=-1)
    return [node for i, node in enumerate(body)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and final.get(node.name) is node and i > star]


def _class_test_flag(cls, classes, seen=()):
    """True or False when the class or a base class in the same module binds __test__ (the class's own, last
    binding first, then its bases in order); None when none does; _UNREADABLE for a value that is not a literal."""
    statement = _final_bindings(cls.body).get("__test__")
    if statement is not None:
        value = _literal_test_value(statement)
        return value if value is _UNREADABLE else bool(value)
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in classes and base.id not in seen:
            inherited = _class_test_flag(classes[base.id], classes, (*seen, cls.name))
            if inherited is not None:
                return inherited
    return None


ABSTRACT_DECORATORS = ("abstractmethod", "abstractproperty", "abstractclassmethod", "abstractstaticmethod")


def _metaclass(cls, classes, seen=()):
    """The metaclass expression of the class or of its first base in the same module that names one, else None."""
    for keyword in cls.keywords:
        if keyword.arg == "metaclass":
            return keyword.value
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in classes and base.id not in seen:
            found = _metaclass(classes[base.id], classes, (*seen, cls.name))
            if found is not None:
                return found
    return None


def _is_abcmeta(node):
    return ((isinstance(node, ast.Name) and node.id == "ABCMeta")
            or (isinstance(node, ast.Attribute) and node.attr == "ABCMeta"
                and isinstance(node.value, ast.Name) and node.value.id == "abc"))


def _abstract_names(cls, classes, seen=()):
    """Names still abstract in the class: its own abstract methods plus those of its same-module bases that it does
    not bind again (the rule ABCMeta applies when it builds __abstractmethods__)."""
    final = _final_bindings(cls.body)
    own = {name for name, node in final.items()
           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
           and any(_decorator_name(d) in ABSTRACT_DECORATORS for d in node.decorator_list)}
    inherited = set()
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in classes and base.id not in seen:
            inherited |= _abstract_names(classes[base.id], classes, (*seen, cls.name))
    return own | {name for name in inherited if name not in final}


def _is_collected_class(cls, classes):
    """True when pytest collects tests from this Test class. A class whose metaclass is not ABCMeta is not
    counted: another metaclass can change what the class holds, and the gate cannot read it (fails closed)."""
    if not cls.name.startswith("Test") or _may_have_constructor(cls, classes):
        return False
    flag = _class_test_flag(cls, classes)
    if flag is _UNREADABLE or flag is False:
        return False
    metaclass = _metaclass(cls, classes)
    if metaclass is None:
        return True
    return _is_abcmeta(metaclass) and not _abstract_names(cls, classes)


def _may_have_constructor(cls, classes, seen=()):
    """True when the class, or a base class, defines __init__ or __new__, or when a base class is not defined
    in the same module (it cannot be read, so the gate assumes the worst and fails closed)."""
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ("__init__", "__new__")
           for n in cls.body):
        return True
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id == "object":
            continue
        if not (isinstance(base, ast.Name) and base.id in classes) or base.id in seen:
            return True
        if _may_have_constructor(classes[base.id], classes, (*seen, cls.name)):
            return True
    return False


def _collect_class(cls, prefix, classes, index):
    if not _is_collected_class(cls, classes):
        return
    path = f"{prefix}::{cls.name}"
    for item in _defs_pytest_keeps(cls.body):
        if _is_test_def(item):
            index.update({item.name, f"{path}::{item.name}"})
        elif isinstance(item, ast.ClassDef):
            _collect_class(item, path, classes, index)


# pytest 9.1's default norecursedirs (requirements/aqis_lab/phase0.txt pins pytest); the repository sets no
# pytest ini options.
PYTEST_NORECURSEDIRS = ("*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}")
CONFTEST_IGNORE_NAMES = ("collect_ignore", "collect_ignore_glob")


def _parse_python(path, rel, what):
    try:
        source = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise GateError(f"{rel}:1: cannot read {what}: {exc}") from exc
    try:
        return ast.parse(source, filename=rel)
    except SyntaxError as exc:
        raise GateError(f"{rel}:{exc.lineno}: cannot parse {what}: {exc.msg}") from exc


def _conftest_ignores(path, rel):
    """{name: [entries]} for collect_ignore and collect_ignore_glob in a conftest.py. Each name the file mentions
    must be bound once, at module level, to a literal list or tuple of strings and used nowhere else; anything
    else is a GateError, because the gate would have to guess which files pytest skips."""
    tree = _parse_python(path, rel, "conftest file")
    found = {}
    for name in CONFTEST_IGNORE_NAMES:
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name]
        if not uses:
            continue
        binds = [s for s in tree.body if isinstance(s, (ast.Assign, ast.AnnAssign)) and name in _bound_names(s)]
        value = _literal_test_value(binds[0]) if len(uses) == 1 and len(binds) == 1 else _UNREADABLE
        if not (isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value)):
            line = min(n.lineno for n in uses)
            raise GateError(f"{rel}:{line}: cannot tell which files pytest collects: {name} is not a single "
                            f"literal list of strings")
        found[name] = list(value)
    return found


def _ignores_for(directory, root, cache):
    """{name: [absolute paths or globs]} pytest applies to entries of `directory`: for each name, the entries of the
    nearest conftest.py between `directory` and the repository root `root` (pytest's rootdir when run from the
    repository root, as CI does) that defines it, including conftests above the folder being collected."""
    result = {}
    current = directory
    while True:
        conftest = current / "conftest.py"
        if conftest.is_file():
            if conftest not in cache:
                cache[conftest] = _conftest_ignores(conftest, conftest.relative_to(root).as_posix())
            for name, entries in cache[conftest].items():
                result.setdefault(name, [os.path.abspath(current / e.replace("/", os.sep)) for e in entries])
        if current == root:
            return {name: result.get(name, []) for name in CONFTEST_IGNORE_NAMES}
        current = current.parent


def _in_virtualenv(directory):
    return (directory / "pyvenv.cfg").is_file() or (directory / "conda-meta" / "history").is_file()


def _pytest_skips(path, base, root, cache):
    """True when pytest, collecting the folder `base`, never reaches the file `path`: a folder or file on the way
    is __pycache__, is listed in the nearest conftest's collect_ignore or matches its collect_ignore_glob (conftests
    from `root` down, also above `base`), or is a folder pytest does not enter (default norecursedirs, a virtual
    environment). `base` and the folders above it are never skipped: pytest does not ignore the path it is given."""
    current = base
    parts = path.relative_to(base).parts
    for i, part in enumerate(parts):
        parent, current = current, current / part
        if part == "__pycache__":
            return True
        ignores = _ignores_for(parent, root, cache)
        absolute = os.path.abspath(current)
        if absolute in ignores["collect_ignore"]:
            return True
        if any(fnmatch.fnmatch(absolute, pattern) for pattern in ignores["collect_ignore_glob"]):
            return True
        is_folder = i < len(parts) - 1
        if is_folder and (_in_virtualenv(current) or any(fnmatch.fnmatch(part, p) for p in PYTEST_NORECURSEDIRS)):
            return True
    return False


def test_functions(root, folder):
    """{path::name, path::Class::name, name} for test functions under folder, fixtures excluded.

    Applies pytest's default collection as if pytest were run on `folder` (pytest 9.1, no ini options):
    - files named test_*.py or *_test.py, outside tests/aqis_lab/fixtures/;
    - not under a folder pytest does not enter: __pycache__, the default norecursedirs (*.egg, hidden folders,
      _darcs, build, CVS, dist, node_modules, venv, {arch}) or a virtual environment (pyvenv.cfg or
      conda-meta/history);
    - not listed in the collect_ignore, or matched by the collect_ignore_glob, of the nearest conftest.py between
      the file and the repository root (pytest's rootdir in CI; conftests above `folder` apply too) that defines
      it; a conftest whose list is not a literal is a GateError;
    - module-level functions whose name starts with 'test', and such methods of classes whose name starts with
      'Test' (nested ones too) that have no __init__ or __new__ of their own or from a base class and whose base
      classes are all defined in the same module (others cannot be read, so they do not count);
    - a definition counts only if its name still refers to it after the whole module or class body has run, so a
      name rebound after its def (assigned, deleted, defined again, rebound conditionally or possibly by a later
      star import) counts only for the last plain def;
    - a module or class whose __test__ is a false value (its own last binding, or for a class the one inherited
      from a same-module base), or not a literal the gate can read, has no tests;
    - an abstract Test class (metaclass ABCMeta with an abstract method left) has no tests, and a class with any
      other metaclass is not counted (the gate cannot read the metaclass);
    - functions decorated as fixtures (either form) or properties are not tests.
    Files that do not parse are reported as a GateError, never skipped.
    """
    index = set()
    base = Path(root) / folder
    if not base.is_dir():
        return index
    conftests = {}
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(FIXTURE_DIR) or not any(fnmatch.fnmatchcase(path.name, g) for g in TEST_FILE_GLOBS):
            continue
        if _pytest_skips(path, base, Path(root), conftests):
            continue
        tree = _parse_python(path, rel, "test file")
        if _sets_test_false(tree.body):
            continue
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for node in _defs_pytest_keeps(tree.body):
            if _is_test_def(node):
                index.update({node.name, f"{rel}::{node.name}"})
            elif isinstance(node, ast.ClassDef):
                _collect_class(node, rel, classes, index)
    return index


# ---------------------------------------------------------------------------------------------
# check (e): capability registry consistency
# ---------------------------------------------------------------------------------------------
def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _unquote(cell):
    return cell.strip().strip("`").strip()


def parse_registry(text):
    """([(line_no, cells)], [(line_no, problem)]) for the rows of the registry table."""
    rows, problems, in_table = [], [], False
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("|") and _cells(stripped)[:1] == ["Capability ID"]:
                if tuple(_cells(stripped)) != REGISTRY_COLUMNS:
                    problems.append((number, f"header columns are {_cells(stripped)}, expected {list(REGISTRY_COLUMNS)}"))
                in_table = True
            continue
        if not stripped.startswith("|"):
            break
        cells = _cells(stripped)
        if all(set(c) <= set("-: ") for c in cells):
            continue  # separator row
        rows.append((number, cells))
    if not in_table:
        problems.append((1, "no table with a 'Capability ID' header"))
    return rows, problems


def module_exists(root, module):
    if not module:
        return False
    if "/" in module or module.endswith((".py", ".sh", ".md", ".txt", ".yml", ".yaml", ".json")):
        return (Path(root) / module).is_file()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", module):
        return False
    base = Path(root).joinpath(*module.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def check_registry(git, base, report):
    root = git.root
    path = root / REGISTRY
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        report.findings.append(Finding("E1", "e", "MAJOR", REGISTRY, 1, f"capability registry missing or unreadable: {exc}"))
        text = None
    current_ids = set()
    if text is not None:
        rows, problems = parse_registry(text)
        for number, problem in problems:
            report.findings.append(Finding("E2", "e", "MAJOR", REGISTRY, number, f"malformed registry: {problem}"))
        tests = test_functions(root, "tests")
        for number, cells in rows:
            if len(cells) != len(REGISTRY_COLUMNS) or not _unquote(cells[0]):
                report.findings.append(Finding(
                    "E2", "e", "MAJOR", REGISTRY, number,
                    f"malformed registry row: {len(cells)} cells, expected {len(REGISTRY_COLUMNS)} with a capability ID"))
                continue
            cap = _unquote(cells[0])
            if cap in current_ids:
                report.findings.append(Finding("E2", "e", "MAJOR", REGISTRY, number,
                                               f"malformed registry row: duplicate capability ID {cap}"))
                continue
            current_ids.add(cap)
            module = _unquote(cells[1])
            if not module_exists(root, module):
                report.findings.append(Finding("E4", "e", "MAJOR", REGISTRY, number,
                                               f"{cap}: module {module or '(empty)'} does not exist"))
            names = [_unquote(t) for t in cells[4].split(",") if _unquote(t)]
            if not names:
                report.findings.append(Finding("E3", "e", "MAJOR", REGISTRY, number, f"{cap}: row names no tests"))
            missing = [n for n in names if n not in tests]
            if missing:
                report.findings.append(Finding("E3", "e", "MAJOR", REGISTRY, number,
                                               f"{cap}: names tests that do not exist: {', '.join(missing)}"))
    if git.exists(base, REGISTRY):
        rc, base_text, err = git.run("show", f"{base}:{REGISTRY}")
        if rc != 0:
            raise GateError(f"{REGISTRY}:1: cannot read the registry at base {base[:12]}: {err.strip() or 'no message'}")
        base_rows, _ = parse_registry(base_text)
        for number, cells in base_rows:
            cap = _unquote(cells[0]) if cells else ""
            if cap and cap not in current_ids:
                report.findings.append(Finding(
                    "E5", "e", "MAJOR", REGISTRY, number,
                    f"row {cap} present at base {base[:12]} (line {number} there) is missing; rows are never deleted"))


# ---------------------------------------------------------------------------------------------
# check (f): requirement traceability for one work package
# ---------------------------------------------------------------------------------------------
def id_regex(text_id):
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(text_id) + r"(?![0-9])")


def find_spec(root, wp):
    specs = Path(root) / "docs" / "specs"
    matches = sorted(set(specs.rglob(f"{wp}-*.md")) | set(specs.rglob(f"{wp}.md"))) if specs.is_dir() else []
    return matches


def requirement_ids(spec_text, number):
    """[(id, first line)] for FR/NFR/AT/OC IDs that belong to WP number (for example '0.0')."""
    rx = re.compile(r"(?<![A-Za-z0-9])((?:FR|NFR|AT|OC)-" + re.escape(number) + r"-\d+)(?![0-9])")
    seen = {}
    for line_no, line in enumerate(spec_text.splitlines(), start=1):
        for m in rx.finditer(line):
            seen.setdefault(m.group(1), line_no)
    return sorted(seen.items(), key=lambda item: (item[1], item[0]))


def check_traceability(git, wp, report):
    root = git.root
    number = WP_RE.match(wp).group(1)
    specs = find_spec(root, wp)
    if len(specs) != 1:
        found = ", ".join(p.relative_to(root).as_posix() for p in specs) or "none"
        report.findings.append(Finding("F1", "f", "MAJOR", f"docs/specs/**/{wp}-*.md", 1,
                                       f"expected exactly one spec matching docs/specs/**/{wp}-*.md, found: {found}"))
        return
    spec_rel = specs[0].relative_to(root).as_posix()
    try:
        spec_text = specs[0].read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise GateError(f"{spec_rel}:1: cannot read the spec: {exc}") from exc
    ids = requirement_ids(spec_text, number)
    docs = {}
    for rule, name in (("F2", "PLAN.md"), ("F4", "EVIDENCE.md")):
        rel = f"docs/progress/{wp}/{name}"
        try:
            docs[rule] = (rel, (root / rel).read_bytes().decode("utf-8", errors="replace"))
        except OSError:
            report.findings.append(Finding(rule, "f", "MAJOR", rel, 1, f"{name} for {wp} is missing or unreadable"))
    names = [n for n in test_functions(root, LAB_TEST_DIR.rstrip("/")) if "::" not in n]
    for req, line_no in ids:
        for rule in ("F2", "F4"):
            if rule in docs and not id_regex(req).search(docs[rule][1]):
                report.findings.append(Finding(rule, "f", "MAJOR", spec_rel, line_no,
                                               f"{req} does not appear in {docs[rule][0]}"))
        if req.split("-", 1)[0] in ID_PREFIXES_WITH_TESTS:
            token = req.replace("-", "_").replace(".", "_")
            if not any(id_regex(token).search(n) for n in names):
                report.findings.append(Finding("F3", "f", "MAJOR", spec_rel, line_no,
                                               f"{req} is not in any test function name under {LAB_TEST_DIR} "
                                               f"(expected {token})"))


# ---------------------------------------------------------------------------------------------
# running and reporting
# ---------------------------------------------------------------------------------------------
def run_gate(cwd, base_ref, wp=None):
    root = repository_root(cwd)
    git = Git(root)
    ref_commit = git.commit_of(base_ref)
    if ref_commit is None:
        raise GateError(f"--base {base_ref!r} is not a commit in this repository")
    head = git.commit_of("HEAD")
    if head is None:
        raise GateError("HEAD has no commit")
    base = git.out("merge-base", ref_commit, head).strip()
    approvals_commit = resolve_approvals_ref(git)
    approvals = load_approvals(git, approvals_commit)
    report = Report(base_ref=base_ref, base_commit=base, head_commit=head, approvals_commit=approvals_commit, wp=wp)
    changes = changed_files(git, base)
    check_protected_and_tests(git, base, changes, load_protected(root), approvals, report)
    check_patterns_and_headers(git, base, changes, approvals, report)
    check_registry(git, base, report)
    if wp:
        check_traceability(git, wp, report)
    return report


def to_json(report, seconds):
    return {
        "tool": TOOL,
        "base_ref": report.base_ref,
        "base_commit": report.base_commit,
        "head_commit": report.head_commit,
        "approvals_ref": APPROVALS_REF,
        "approvals_commit": report.approvals_commit,
        "wp": report.wp,
        "findings": [asdict(f) for f in report.findings],
        "exempted_lines": report.exempted_lines,
        "exempted_files": report.exempted_files,
        "ok": not report.findings,
        "seconds": round(seconds, 3),
    }


def render_text(report, seconds):
    approvals = (f"approvals {APPROVALS_REF} {report.approvals_commit[:12]}" if report.approvals_commit
                 else f"approvals: none ({APPROVALS_REF} not verifiable)")
    lines = [f"{TOOL}: base {report.base_ref} (merge-base {report.base_commit[:12]}), head {report.head_commit[:12]}, "
             f"{approvals}, wp {report.wp or '-'}"]
    lines.append(f"Exempted lines (# audit-allow): {len(report.exempted_lines)}")
    lines.extend(f"  {e['path']}:{e['line']}: {e['reason']}" for e in report.exempted_lines)
    lines.append(f"Exempted files (ALLOW-PATTERNS-IN): {len(report.exempted_files)}")
    lines.extend(f"  {e['path']}: {e['glob']} ({e['approval']})" for e in report.exempted_files)
    lines.append(f"Findings: {len(report.findings)}")
    lines.extend(f.render() for f in report.findings)
    verdict = "OK" if not report.findings else "FAIL"
    lines.append(f"{len(report.findings)} findings: {verdict} ({seconds:.1f} s)")
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m tools.audit.gate",
                                     description="AQIS lab audit gate (docs/tools/AUDIT_GATE.md).")
    parser.add_argument("--base", required=True, help="reference to diff against (merge-base with HEAD is used)")
    parser.add_argument("--wp", help="work package ID for requirement traceability, e.g. WP-0.0")
    parser.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.wp is not None and not WP_RE.match(args.wp):
        print(f"ERROR: --wp {args.wp!r} is not a work package ID of the form WP-<phase>.<number>", file=sys.stderr)
        return 2
    start = time.monotonic()
    try:
        report = run_gate(Path.cwd(), args.base, args.wp)
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    seconds = time.monotonic() - start
    if args.json:
        print(json.dumps(to_json(report, seconds), indent=2))
    else:
        print(render_text(report, seconds))
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
