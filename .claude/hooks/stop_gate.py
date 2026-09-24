#!/usr/bin/env python3
"""Stop hook: a deterministic quality gate that runs every time Claude finishes a turn.

It inspects this branch's changes since it left origin/main, plus uncommitted work, for:
  1. changes to NEVER or GUARDED paths without an owner approval,
  2. existing test files that were modified or deleted without approval,
  3. compromise patterns in added lab code, and skips, xfails or trivial asserts in added lab tests,
  4. new lab modules without a CAPABILITIES header,
  5. failing fast lab tests (only when lab files changed),
  6. the project audit gate, tools/audit/gate.py, once WP-0.0 has built it.

First stop with problems: the stop is blocked and Claude is told what to fix.
Second consecutive stop with problems still open: the stop is allowed, and the owner sees a warning.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave cache files inside .claude/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protected import classify, load_approvals, load_patterns, project_root  # noqa: E402

LAB_CODE_DIRS = ("aqis_lab/", "tools/")
LAB_TEST_DIR = "tests/aqis_lab/"
LAB_TRIGGER_DIRS = ("aqis_lab/", "tools/", "tests/aqis_lab/", "requirements/aqis_lab/", "config/aqis_lab/")
FAST_MARKERS = "not slow and not gpu and not colab and not oracle and not network"
MAX_LINES = 60

CODE_PATTERNS = [
    ("TODO/FIXME/XXX marker", re.compile(r"\b(?:TODO|FIXME|XXX)\b")),
    ("placeholder wording", re.compile(r"\bplaceholders?\b", re.I)),
    ("simplification wording", re.compile(r"\bsimplif(?:y|ied|ies|ying|ication)\b", re.I)),
    ("'for now' wording", re.compile(r"\bfor now\b", re.I)),
    ("temporary wording", re.compile(r"\btemporar(?:y|ily)\b", re.I)),
    ("hack wording", re.compile(r"\bhack(?:s|y|ish)?\b", re.I)),
    ("dummy or fake wording", re.compile(r"\b(?:dummy|fake)\b", re.I)),
    ("NotImplementedError", re.compile(r"\bNotImplementedError\b")),
    ("swallowed exception", re.compile(r"\bexcept\b[^:]*:\s*(?:pass|\.\.\.)\s*(?:#.*)?$")),
    ("bare except", re.compile(r"^\s*except\s*:")),
    ("type-check suppression", re.compile(r"#\s*type:\s*ignore")),
    ("mocking in production code", re.compile(r"\b(?:unittest\.mock|MagicMock|mock\.patch)\b")),
]
TEST_PATTERNS = [
    ("test skip", re.compile(r"pytest\.skip\(|@pytest\.mark\.skip(?:if)?\b|unittest\.skip|pytest\.importorskip\(")),
    ("expected-failure marker", re.compile(r"\bxfail\b")),
    ("trivial assertion", re.compile(r"\bassert\s+(?:True|1)\s*(?:#.*)?$")),
]
ALLOW_RE = re.compile(r"#\s*audit-allow:\s*\S")
HEADER_RE = re.compile(r"^\s*CAPABILITIES:", re.M)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def git(root, *args, timeout=60):
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def find_base(root):
    """Merge-base of HEAD with the main branch (fetching origin/main if missing), or None."""
    for attempt in range(2):
        for ref in ("origin/main", "main", "origin/master", "master"):
            if git(root, "rev-parse", "--verify", "--quiet", ref)[0] == 0:
                rc, out = git(root, "merge-base", "HEAD", ref)
                if rc == 0 and out.strip():
                    return out.strip()
        if attempt == 0:
            git(root, "fetch", "--quiet", "origin", "main:refs/remotes/origin/main", timeout=120)
    return None


def changed_files(root, base):
    """{path: 'A'|'M'|'D'} for committed changes since base and uncommitted work."""
    changes = {}
    if base:
        rc, out = git(root, "diff", "--name-status", "--no-renames", "-z", base, "HEAD")
        if rc == 0:
            parts = out.split("\0")
            for status, path in zip(parts[0::2], parts[1::2]):
                if path:
                    changes[path] = status[:1]
    rc, out = git(root, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all")
    if rc == 0:
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


def existed_at(root, ref, path):
    return bool(ref) and git(root, "cat-file", "-e", f"{ref}:{path}")[0] == 0


def added_lines(root, base, path):
    """[(line_number, text)] for lines added relative to base (or all lines of a new file)."""
    full = Path(root) / path
    if not full.is_file():
        return []
    ref = base if base else "HEAD"
    if not existed_at(root, ref, path):
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return list(enumerate(text.splitlines(), start=1))
    rc, out = git(root, "diff", "-U0", "--no-color", ref, "--", path)
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


def scan(path, lines, patterns):
    findings, allowed = [], 0
    for number, text in lines:
        if ALLOW_RE.search(text):
            allowed += 1
            continue
        for label, rx in patterns:
            if rx.search(text):
                findings.append(f"{path}:{number}: {label}: {text.strip()[:110]}")
                break
    return findings, allowed


def project_python(root):
    venv = Path(root) / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def run_fast_tests(root):
    tests_dir = Path(root) / "tests" / "aqis_lab"
    if not tests_dir.is_dir() or not any(tests_dir.rglob("test_*.py")):
        return None
    timeout = int(os.environ.get("AQIS_GATE_TEST_TIMEOUT", "600"))
    cmd = [project_python(root), "-m", "pytest", "tests/aqis_lab", "-q", "-x",
           "-p", "no:cacheprovider", "-m", FAST_MARKERS]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"fast lab tests did not finish within {timeout} s"
    except OSError as exc:
        return f"could not start the fast lab tests: {exc}"
    if proc.returncode in (0, 5):  # 5 means no tests were collected after marker selection
        return None
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
    return f"fast lab tests failed (exit code {proc.returncode}):\n{tail}"


def run_project_gate(root, base):
    if not (Path(root) / "tools" / "audit" / "gate.py").is_file():
        return None
    cmd = [project_python(root), "-m", "tools.audit.gate", "--base", base or "HEAD"]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"project audit gate could not run: {exc}"
    if proc.returncode == 0:
        return None
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
    return f"project audit gate failed (exit code {proc.returncode}):\n{tail}"


def evaluate(root):
    base = find_base(root)
    changes = changed_files(root, base)
    if not changes:
        return [], 0
    sections = load_patterns(root)
    edit_rules, pattern_rules, _ = load_approvals(root, base)

    def approved(rules, path):
        return any(rx.match(path) for rx, _, _ in rules)

    issues, allowed_total = [], 0
    for path, state in sorted(changes.items()):
        kind = classify(path, sections)
        if kind == "NEVER":
            issues.append(f"CRITICAL: owner-only path changed [{state}] {path}")
        elif kind == "GUARDED" and not approved(edit_rules, path):
            issues.append(f"CRITICAL: guarded harness path changed without approval [{state}] {path}")
        if path.startswith("tests/") and path.endswith(".py") and state in ("M", "D"):
            if existed_at(root, base, path) and not approved(edit_rules, path):
                verb = "deleted" if state == "D" else "modified"
                issues.append(f"CRITICAL: existing test {verb} without approval: {path}")
    for path, state in sorted(changes.items()):
        if state == "D" or not path.endswith(".py") or approved(pattern_rules, path):
            continue
        if path.startswith(LAB_TEST_DIR):
            patterns = TEST_PATTERNS
        elif path.startswith(LAB_CODE_DIRS):
            patterns = CODE_PATTERNS
        else:
            continue
        found, allowed = scan(path, added_lines(root, base, path), patterns)
        allowed_total += allowed
        issues.extend(f"COMPROMISE PATTERN: {item}" for item in found)
        if (path.startswith("aqis_lab/") and state == "A"
                and not existed_at(root, base or "HEAD", path)):
            full = Path(root) / path
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            meaningful = [line for line in text.splitlines() if line.strip()]
            if len(meaningful) > 5 and not HEADER_RE.search("\n".join(text.splitlines()[:80])):
                issues.append(f"MAJOR: new lab module without a CAPABILITIES header: {path}")
    if any(path.startswith(LAB_TRIGGER_DIRS) for path in changes):
        failure = run_fast_tests(root)
        if failure:
            issues.append(f"FAILING TESTS: {failure}")
        gate = run_project_gate(root, base)
        if gate:
            issues.append(f"AUDIT GATE: {gate}")
    return issues, allowed_total


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        event = {}
    root = project_root(event)
    if git(root, "rev-parse", "--is-inside-work-tree")[0] != 0:
        return 0
    issues, allowed_total = evaluate(root)
    if not issues:
        return 0
    shown = issues[:MAX_LINES]
    if len(issues) > MAX_LINES:
        shown.append(f"... and {len(issues) - MAX_LINES} more")
    summary = "\n".join(f"- {line}" for line in shown)
    if allowed_total:
        summary += f"\n- note: {allowed_total} line(s) carry '# audit-allow:' and will be listed for the owner"
    if event.get("stop_hook_active"):
        print(json.dumps({"systemMessage": "⚠️ STOP GATE: unresolved problems remain on this branch. "
                                           "Do not merge until they are fixed or approved.\n" + summary}))
        return 0
    print(json.dumps({"decision": "block",
                      "reason": "STOP GATE (automatic check) found problems. Fix each one properly within "
                                "the rules, never by weakening tests, adding skips, deleting checks or "
                                "editing protected files. If a problem cannot be fixed honestly, use the "
                                "ask-owner skill (BLOCKERS.md entry and a message starting with "
                                "'🛑 OWNER ACTION NEEDED'), then stop again.\n" + summary}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
