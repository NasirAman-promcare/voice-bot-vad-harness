"""Throwaway git repositories for audit-gate tests (not a test module).

A FixtureRepo has a bare `origin` and a working clone. The clone's `main` holds the owner's
real docs/process/PROTECTED_PATHS.txt plus a small harness, lab module and registry; tests
then commit approvals to main, branch, and make the changes a scenario needs. The gate and
the real Stop hook (.claude/hooks/stop_gate.py) are both run against the clone.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from aqis_testutil import ROOT, git, hermetic_git_env

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gate"
STOP_HOOK = ROOT / ".claude" / "hooks" / "stop_gate.py"

REGISTRY_HEAD = (
    "# Capability registry\n\n"
    "| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)
LAB_MODULE_WITH_HEADER = (
    '"""Existing lab module.\n\nCAPABILITIES:\n  CAP-FIX-001: adds numbers [tests: test_adds]\n"""\n\n\n'
    "def add(a, b):\n    return a + b\n"
)
HARNESS_TEST = "def test_harness_example():\n    assert 2 + 2 == 4\n"
HARNESS_MODULE = "def harness_value():\n    return 42\n"
REGISTRY_BASE_ROW = ("| CAP-FIX-001 | `aqis_lab/existing.py` | `add` | adds numbers | `test_adds` | WP-0.0 FR-0.0-08 | ACTIVE |\n")
LAB_TEST_EXISTING = "from aqis_lab.existing import add\n\n\ndef test_adds():\n    assert add(2, 3) == 5\n"

APPROVAL_TEMPLATE = "STATUS: {status}\nWP: WP-9.9\nAPPROVED-BY: owner\nDATE: 2026-09-25\n{extra}"


class FixtureRepo:
    def __init__(self, tmp_path, with_lab_test=False):
        self.origin = tmp_path / "origin.git"
        self.path = tmp_path / "work"
        git(tmp_path, "init", "-q", "--bare", str(self.origin))
        git(tmp_path, "clone", "-q", str(self.origin), str(self.path))
        self.write("docs/process/PROTECTED_PATHS.txt",
                   (ROOT / "docs" / "process" / "PROTECTED_PATHS.txt").read_text(encoding="utf-8"))
        self.write("docs/approvals/README.md", "# Approvals\n")
        self.write("docs/capabilities/REGISTRY.md", REGISTRY_HEAD + REGISTRY_BASE_ROW)
        self.write("vad_adapters/example.py", HARNESS_MODULE)
        self.write("tests/regression/test_example.py", HARNESS_TEST)
        self.write("aqis_lab/__init__.py", '"""Fixture lab package."""\n')
        self.write("aqis_lab/existing.py", LAB_MODULE_WITH_HEADER)
        self.write("tools/existing_tool.py", "def tool():\n    return 'TODO list is a harmless string here'\n")
        self.write("README.md", "fixture\n")
        if with_lab_test:
            self.write("tests/aqis_lab/test_existing.py", LAB_TEST_EXISTING)
        else:
            self.write("tests/lab_support/test_adds.py", LAB_TEST_EXISTING)
        self.commit("base")
        git(self.path, "push", "-q", "origin", "main")

    # -- editing -------------------------------------------------------------------------
    def write(self, rel, text):
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def copy_fixture(self, name, rel):
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES / name, target)

    def append(self, rel, text):
        target = self.path / rel
        target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")

    def delete(self, rel):
        (self.path / rel).unlink()

    def commit(self, message):
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "--allow-empty", "-m", message)

    def approve_on_main(self, name, extra, status="APPROVED", merge_into_branch=True):
        """Commit an approval file to main and push it (the owner's route).

        With merge_into_branch=False the current branch does not merge main afterwards, so origin/main moves
        past the branch point and differs from the merge-base (audit finding WP-0.0-F02).
        """
        current = git(self.path, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if current != "main":
            git(self.path, "checkout", "-q", "main")
        self.write(f"docs/approvals/{name}", APPROVAL_TEMPLATE.format(status=status, extra=extra))
        self.commit(f"approval {name}")
        git(self.path, "push", "-q", "origin", "main")
        if current != "main":
            git(self.path, "checkout", "-q", current)
            git(self.path, "fetch", "-q", "origin")
            if merge_into_branch:
                git(self.path, "merge", "-q", "--no-edit", "origin/main")

    def commit_approval_text_on_main(self, name, text):
        """Commit an approval file with exactly this text to main, push it, and merge it into the current branch.

        Used for approvals whose lines are not in the standard form (audit finding WP-0.0-F33)."""
        current = git(self.path, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if current != "main":
            git(self.path, "checkout", "-q", "main")
        self.write(f"docs/approvals/{name}", text)
        self.commit(f"approval {name}")
        git(self.path, "push", "-q", "origin", "main")
        if current != "main":
            git(self.path, "checkout", "-q", current)
            git(self.path, "fetch", "-q", "origin")
            git(self.path, "merge", "-q", "--no-edit", "origin/main")

    def branch(self, name="feature"):
        git(self.path, "checkout", "-q", "-b", name)

    # -- running -------------------------------------------------------------------------
    def gate(self, *args, json_output=True):
        cmd = [sys.executable, "-B", "-m", "tools.audit.gate", *args]
        if json_output:
            cmd.append("--json")
        env = hermetic_git_env({"PYTHONPATH": str(ROOT)})
        proc = subprocess.run(cmd, cwd=self.path, capture_output=True, text=True, env=env, timeout=300)
        return proc

    def gate_json(self, *args):
        proc = self.gate("--base", "origin/main", *args)
        assert proc.returncode in (0, 1), f"gate exit {proc.returncode}: {proc.stderr}"
        report = json.loads(proc.stdout)
        assert report["ok"] == (proc.returncode == 0)
        return report

    def hook_lines(self):
        env = hermetic_git_env({"CLAUDE_PROJECT_DIR": str(self.path)})
        event = json.dumps({"cwd": str(self.path), "stop_hook_active": False})
        proc = subprocess.run([sys.executable, "-B", str(STOP_HOOK)], input=event, cwd=self.path,
                              capture_output=True, text=True, env=env, timeout=600)
        assert proc.returncode == 0, proc.stderr
        if not proc.stdout.strip():
            return []
        reason = json.loads(proc.stdout)["reason"]
        return [line[2:] for line in reason.splitlines() if line.startswith("- ")]


# -- normalisation for parity -------------------------------------------------------------
HOOK_RULES = [
    (re.compile(r"^CRITICAL: owner-only path changed \[(\w)\] (.+)$"), lambda m: ("A1", m.group(2), m.group(1))),
    (re.compile(r"^CRITICAL: guarded harness path changed without approval \[(\w)\] (.+)$"),
     lambda m: ("A2", m.group(2), m.group(1))),
    (re.compile(r"^CRITICAL: existing test modified without approval: (.+)$"), lambda m: ("B1", m.group(1))),
    (re.compile(r"^CRITICAL: existing test deleted without approval: (.+)$"), lambda m: ("B2", m.group(1))),
    (re.compile(r"^COMPROMISE PATTERN: (.+?):(\d+): (.+?): (.*)$"),
     lambda m: ("C", m.group(1), int(m.group(2)), m.group(3), m.group(4))),
    (re.compile(r"^MAJOR: new lab module without a CAPABILITIES header: (.+)$"), lambda m: ("D1", m.group(1))),
]


def normalise_hook(lines):
    out = []
    for line in lines:
        for rx, make in HOOK_RULES:
            m = rx.match(line)
            if m:
                out.append(make(m))
                break
    return sorted(out, key=repr)


def normalise_gate(report):
    out = []
    for f in report["findings"]:
        rule = f["rule"]
        if rule in ("A1", "A2"):
            out.append((rule, f["path"], f["state"]))
        elif rule in ("B1", "B2", "D1"):
            out.append((rule, f["path"]))
        elif rule in ("C1", "C2"):
            out.append(("C", f["path"], f["line"], f["label"], f["text"].strip()[:110]))
    return sorted(out, key=repr)
