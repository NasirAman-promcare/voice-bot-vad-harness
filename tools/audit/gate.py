"""AQIS lab audit gate: checks a branch's changes for rule violations and exits 0 only when none are found.

Usage (from inside the repository):
  python -m tools.audit.gate --base <ref> [--wp <WP-ID>] [--json]

CAPABILITIES:
  CAP-AUDIT-001: check (a) protected paths per docs/process/PROTECTED_PATHS.txt with approvals read from origin/main [tests: test_FR_0_0_05_a_detects_never_path, test_FR_0_0_05_a_detects_guarded_path_without_approval, test_FR_0_0_05_a_passes_guarded_path_with_main_approval, test_FR_0_0_05_a_ignores_approval_committed_only_on_branch, test_FR_0_0_05_a_ignores_expired_or_withdrawn_approval]
  CAP-AUDIT-002: check (b) existing tests modified or deleted without ALLOW-EDIT [tests: test_FR_0_0_05_b_detects_modified_existing_test, test_FR_0_0_05_b_detects_deleted_existing_test, test_FR_0_0_05_b_passes_new_test_and_approved_edit]
  CAP-AUDIT-003: check (c) compromise patterns in added lab code lines and test-integrity patterns in added lab test lines [tests: test_FR_0_0_05_c_detects_each_code_pattern, test_FR_0_0_05_c_detects_each_test_pattern, test_FR_0_0_05_c_scans_only_added_lines, test_FR_0_0_05_c_includes_uncommitted_and_untracked_work]
  CAP-AUDIT-004: check (d) CAPABILITIES header in new aqis_lab/ modules [tests: test_FR_0_0_05_d_detects_new_module_without_header, test_FR_0_0_05_d_passes_module_with_header_or_short_file]
  CAP-AUDIT-005: check (e) capability registry consistency [tests: test_FR_0_0_08_detects_row_with_missing_test, test_FR_0_0_08_detects_row_with_missing_module, test_FR_0_0_08_detects_row_removed_since_base, test_FR_0_0_08_detects_malformed_row, test_FR_0_0_08_passes_consistent_registry]
  CAP-AUDIT-006: check (f) requirement traceability for --wp [tests: test_FR_0_0_09_detects_id_missing_from_plan, test_FR_0_0_09_detects_id_missing_from_test_names, test_FR_0_0_09_detects_id_missing_from_evidence, test_FR_0_0_09_passes_complete_traceability]
  CAP-AUDIT-007: lists every audit-allow line and every ALLOW-PATTERNS-IN exempted file [tests: test_FR_0_0_07_audit_allow_with_reason_exempts_and_is_listed, test_FR_0_0_07_allow_patterns_in_exempts_file_and_is_listed]
  CAP-AUDIT-009: command line, merge-base diffing, text and JSON reports, exit codes 0/1/2 [tests: test_FR_0_0_05_clean_branch_exits_zero, test_FR_0_0_05_uses_merge_base_not_ref_tip, test_FR_0_0_05_json_output_schema, test_FR_0_0_05_bad_base_ref_exits_2, test_NFR_0_0_02_every_message_names_file_line_and_rule]
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
"""
import argparse
import ast
import json
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
LAB_CODE_DIRS = ("aqis_lab/", "tools/")
LAB_TEST_DIR = "tests/aqis_lab/"
FIXTURE_DIR = "tests/aqis_lab/fixtures/"
REGISTRY = "docs/capabilities/REGISTRY.md"
REGISTRY_COLUMNS = ("Capability ID", "Module", "Functions", "What it does", "Tests", "Introduced by", "Status")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
WP_RE = re.compile(r"^WP-(\d+\.\d+)$")
ID_PREFIXES_WITH_TESTS = ("FR", "NFR")
ID_PREFIXES_DOCS_ONLY = ("AT", "OC")


class GateError(Exception):
    """The gate could not run (bad reference, not a repository, missing origin/main)."""


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
            proc = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=timeout)
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
                              timeout=60)
    except FileNotFoundError as exc:
        raise GateError("git is not installed or not on PATH") from exc
    if proc.returncode != 0:
        raise GateError(f"{cwd} is not inside a git repository: {proc.stderr.strip()}")
    return Path(proc.stdout.strip())


# ---------------------------------------------------------------------------------------------
# policy: protected paths and approvals (same semantics as .claude/hooks/_protected.py)
# ---------------------------------------------------------------------------------------------
def glob_to_regex(pattern):
    """Convert a repo-relative glob with **, * and ? into an anchored regular expression."""
    pattern = pattern.strip().lstrip("/")
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def load_protected(root):
    """{section: [regex]} from the working-tree PROTECTED_PATHS.txt plus the built-in NEVER list."""
    sections = {name: [] for name in SECTIONS}
    current = None
    try:
        text = (Path(root) / "docs" / "process" / "PROTECTED_PATHS.txt").read_text(encoding="utf-8")
    except OSError:
        text = ""
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
    """Commit of origin/main, fetching it once if it is missing (as the hooks do)."""
    commit = git.commit_of(APPROVALS_REF)
    if commit is None:
        git.run("fetch", "--quiet", "origin", "main:refs/remotes/origin/main", timeout=120)
        commit = git.commit_of(APPROVALS_REF)
    if commit is None:
        raise GateError(f"{APPROVALS_REF} not found and could not be fetched; approvals are read only from "
                        f"{APPROVALS_REF} (run: git fetch origin main)")
    return commit


def load_approvals(git, ref):
    """Rules from approval files with STATUS: APPROVED committed at ref (never the working tree)."""
    edit_rules, pattern_rules, files = [], [], []
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
        if "?" in code:
            state = "A"
        elif "D" in code:
            state = "D"
        elif "A" in code:
            state = "A"
        else:
            state = "M"
        previous = changes.get(path)
        if previous == "A":
            if state == "D":
                changes.pop(path)  # added on this branch, then removed again
            continue
        changes[path] = state
    return changes


def added_lines(git, base, path):
    """[(line_number, text)] for lines added relative to base (or all lines of a new file)."""
    full = git.root / path
    if not full.is_file():
        return []
    if not git.exists(base, path):
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return list(enumerate(text.splitlines(), start=1))
    _, out, _ = git.run("diff", "-U0", "--no-color", base, "--", path)
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
    _, out, _ = git.run("diff", "-U0", "--no-color", base, "--", path)
    for line in out.splitlines():
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


def check_patterns_and_headers(git, base, changes, approvals, report):
    for path, state in sorted(changes.items()):
        if state == "D" or not path.endswith(".py"):
            continue
        exemption = matching_rule(approvals.pattern_rules, path)
        if exemption:
            if path.startswith(LAB_CODE_DIRS) or path.startswith(LAB_TEST_DIR):
                report.exempted_files.append({"path": path, "approval": exemption[0], "glob": exemption[1]})
            continue
        if path.startswith(LAB_TEST_DIR):
            table, rule = patterns.TEST_PATTERNS, "C2"
        elif path.startswith(LAB_CODE_DIRS):
            table, rule = patterns.CODE_PATTERNS, "C1"
        else:
            continue
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
        if path.startswith("aqis_lab/") and state == "A" and not git.exists(base, path):
            try:
                content = (git.root / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            meaningful = [line for line in content.splitlines() if line.strip()]
            if len(meaningful) > 5 and not patterns.HEADER_RE.search("\n".join(content.splitlines()[:80])):
                report.findings.append(Finding(
                    "D1", "d", "MAJOR", path, 1,
                    "new lab module without a CAPABILITIES header in its first 80 lines "
                    "(docs/process/CHANGE_CONTROL.md)", state=state))


# ---------------------------------------------------------------------------------------------
# shared: test function index
# ---------------------------------------------------------------------------------------------
def test_functions(root, folder):
    """{path::name, path::Class::name, name} for every test function under folder, fixtures excluded.

    A test function is a module-level function whose name starts with 'test', or such a method of a
    class whose name starts with 'Test'. Files that do not parse are reported as a GateError, never skipped.
    """
    index = set()
    base = Path(root) / folder
    if not base.is_dir():
        return index
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(FIXTURE_DIR):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
        except SyntaxError as exc:
            raise GateError(f"{rel}:{exc.lineno}: cannot parse test file: {exc.msg}") from exc
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                index.update({node.name, f"{rel}::{node.name}"})
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                        index.update({item.name, f"{rel}::{node.name}::{item.name}"})
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
        text = path.read_text(encoding="utf-8")
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
    rc, base_text, _ = git.run("show", f"{base}:{REGISTRY}")
    if rc == 0:
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
        report.findings.append(Finding("F1", "f", "MAJOR", "docs/specs", 1,
                                       f"expected exactly one spec for {wp} under docs/specs/, found: {found}"))
        return
    spec_rel = specs[0].relative_to(root).as_posix()
    ids = requirement_ids(specs[0].read_text(encoding="utf-8"), number)
    docs = {}
    for rule, name in (("F2", "PLAN.md"), ("F4", "EVIDENCE.md")):
        rel = f"docs/progress/{wp}/{name}"
        try:
            docs[rule] = (rel, (root / rel).read_text(encoding="utf-8"))
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
    lines = [f"{TOOL}: base {report.base_ref} (merge-base {report.base_commit[:12]}), head {report.head_commit[:12]}, "
             f"approvals {APPROVALS_REF} {report.approvals_commit[:12]}, wp {report.wp or '-'}"]
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
