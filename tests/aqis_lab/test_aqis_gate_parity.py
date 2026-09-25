"""FR-0.0-06: checks (a) to (d) of the gate match the Stop hook (.claude/hooks/stop_gate.py) exactly."""
import json
import subprocess
import sys

import pytest

from aqis_testutil import ROOT, git
from fixture_repo import FixtureRepo, normalise_gate, normalise_hook
from tools.audit import gate, patterns

SIX_LINES = "".join(f"V{i} = {i}\n" for i in range(6))


def s_never(r):
    r.branch(); r.write("CLAUDE.md", "x\n"); r.append("docs/process/PROTECTED_PATHS.txt", "\n"); r.commit("c")
    r.write(".claude/settings.json", "{}\n")


def s_guarded(r):
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n"); r.write("README.md", "changed\n")
    r.write(".github/workflows/other.yml", "on: push\n"); r.write(".github/workflows/aqis-lab-ci.yml", "on: push\n")


def s_guarded_approved(r):
    r.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/**\n")
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n"); r.write("vad_adapters/new.py", "Z = 3\n")


def s_branch_only_approval(r):
    r.branch(); r.write("docs/approvals/WP-9.9.md", "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/example.py\n")
    r.append("vad_adapters/example.py", "\nY = 2\n"); r.commit("c")


def s_modified_harness_test(r):
    r.branch(); r.append("tests/lab_support/test_adds.py", "\n# note\n"); r.commit("c")


def s_deleted_lab_test(r):
    r.branch(); r.delete("tests/aqis_lab/test_existing.py")


def s_approved_lab_test_edit(r):
    r.approve_on_main("WP-9.9.md", "ALLOW-EDIT: tests/aqis_lab/test_existing.py\n")
    r.branch(); r.append("tests/aqis_lab/test_existing.py", "\n\ndef test_zero():\n    assert add(0, 0) == 0\n")


def s_code_patterns(r):
    r.branch(); r.copy_fixture("code_patterns.py", "tools/bad.py"); r.copy_fixture("code_patterns.py", "aqis_lab/bad.py")


def s_test_patterns(r):
    r.branch(); r.copy_fixture("test_patterns.py", "tests/aqis_lab/test_bad.py"); r.commit("c")


def s_allow_lines(r):
    r.branch(); r.copy_fixture("allow_lines.py", "tools/allowed.py")


def s_allow_patterns_in(r):
    r.approve_on_main("WP-9.9.md", "ALLOW-PATTERNS-IN: aqis_lab/table.py\n")
    r.branch(); r.copy_fixture("code_patterns.py", "aqis_lab/table.py"); r.copy_fixture("code_patterns.py", "tools/t.py")


def s_headers(r):
    r.branch(); r.write("aqis_lab/no_header.py", SIX_LINES); r.write("aqis_lab/short.py", "A = 1\n")
    r.write("aqis_lab/pkg/__init__.py", SIX_LINES); r.write("tools/no_header.py", SIX_LINES); r.commit("c")
    r.append("aqis_lab/existing.py", SIX_LINES)


def s_added_then_removed(r):
    r.branch(); r.write("tools/gone.py", "X = 'dummy'\n"); r.commit("add"); r.delete("tools/gone.py")
    r.append("tools/existing_tool.py", "# XXX added line\n")


def s_main_moved(r):
    r.branch(); r.write("tools/branch.py", "B = 'fake'\n"); r.commit("branch")
    git(r.path, "checkout", "-q", "main"); r.write("tools/main_only.py", "M = 'dummy'\n"); r.commit("main")
    git(r.path, "push", "-q", "origin", "main"); git(r.path, "checkout", "-q", "feature")


def s_combined(r):
    s_never(r)
    r.append("vad_adapters/example.py", "\nY = 2\n")
    r.copy_fixture("code_patterns.py", "tools/bad.py")
    r.write("aqis_lab/no_header.py", SIX_LINES)
    r.delete("tests/lab_support/test_adds.py")


def s_clean(r):
    r.branch(); r.write("aqis_lab/ok.py", '"""Ok.\n\nCAPABILITIES:\n  CAP-X-1: y [tests: t]\n"""\nA = 1\nB = 2\nC = 3\nD = 4\n')
    r.write("docs/notes.md", "TODO in prose is fine\n")


SCENARIOS = {
    "never": (s_never, False), "guarded": (s_guarded, False), "guarded_approved": (s_guarded_approved, False),
    "branch_only_approval": (s_branch_only_approval, False), "modified_harness_test": (s_modified_harness_test, False),
    "deleted_lab_test": (s_deleted_lab_test, True), "approved_lab_test_edit": (s_approved_lab_test_edit, True),
    "code_patterns": (s_code_patterns, False), "test_patterns": (s_test_patterns, False),
    "allow_lines": (s_allow_lines, False), "allow_patterns_in": (s_allow_patterns_in, False),
    "headers": (s_headers, False), "added_then_removed": (s_added_then_removed, False),
    "main_moved": (s_main_moved, False), "combined": (s_combined, False), "clean": (s_clean, False),
}
EXPECT_NONE = {"guarded_approved", "approved_lab_test_edit", "clean"}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos(tmp_path, name):
    setup, with_lab_test = SCENARIOS[name]
    repo = FixtureRepo(tmp_path, with_lab_test=with_lab_test)
    setup(repo)
    hook = normalise_hook(repo.hook_lines())
    ours = normalise_gate(repo.gate_json())
    assert ours == hook
    if name in EXPECT_NONE:
        assert ours == []
    else:
        assert ours, f"scenario {name} must produce findings for the comparison to mean anything"


def _hook_eval(code):
    """Run code with the hook modules importable, without writing bytecode into .claude/."""
    proc = subprocess.run([sys.executable, "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1])\n" + code,
                           str(ROOT / ".claude" / "hooks")], capture_output=True, text=True, timeout=60, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_FR_0_0_06_pattern_tables_identical_to_stop_hook():
    hook = _hook_eval(
        "import json, stop_gate as s\n"
        "t = lambda tab: [[l, r.pattern, r.flags] for l, r in tab]\n"
        "print(json.dumps({'code': t(s.CODE_PATTERNS), 'test': t(s.TEST_PATTERNS),"
        " 'allow': [s.ALLOW_RE.pattern, s.ALLOW_RE.flags], 'header': [s.HEADER_RE.pattern, s.HEADER_RE.flags],"
        " 'lab_code': list(s.LAB_CODE_DIRS), 'lab_test': s.LAB_TEST_DIR, 'hunk': s.HUNK_RE.pattern}))")
    ours = {
        "code": [[l, r.pattern, r.flags] for l, r in patterns.CODE_PATTERNS],
        "test": [[l, r.pattern, r.flags] for l, r in patterns.TEST_PATTERNS],
        "allow": [patterns.ALLOW_RE.pattern, patterns.ALLOW_RE.flags],
        "header": [patterns.HEADER_RE.pattern, patterns.HEADER_RE.flags],
        "lab_code": list(gate.LAB_CODE_DIRS), "lab_test": gate.LAB_TEST_DIR, "hunk": gate.HUNK_RE.pattern,
    }
    assert ours == hook


PATHS = ["CLAUDE.md", ".claude/hooks/x.py", "docs/specs/phase-0/a.md", "docs/process/PROTECTED_PATHS.txt",
         "docs/approvals/WP-0.0.md", "bots/x.py", "config/run_config.yaml", "config/aqis_lab/a.yaml",
         "tests/regression/test_x.py", "tests/aqis_lab/test_y.py", "tests/aqis_lab/fixtures/gate/a.py",
         "requirements/base.txt", "requirements/aqis_lab/phase0.txt", ".github/workflows/aqis-lab-ci.yml",
         ".github/workflows/other.yml", ".github/dependabot.yml", "orchestrator.py", "sub/orchestrator.py",
         "README.md", ".gitignore", "aqis_lab/__init__.py", "tools/audit/gate.py", "docs/progress/STATUS.md",
         "notebooks/aqis_lab/n.ipynb", "notebooks/x.ipynb", "corpus-v1.tar.gz", "webrtc_bridge/a/b/c.py"]
GLOBS = ["**/x.py", "a/**", "a/**/b.py", "*.md", "docs/?.md", "tests/aqis_lab/fixtures/**", "x.y+z(1).py"]
PROBES = ["x.py", "a/x.py", "a/b/c/x.py", "a/b.py", "a/c/d/b.py", "b.py", "README.md", "docs/a.md", "docs/ab.md",
          "tests/aqis_lab/fixtures/gate/f.py", "tests/aqis_lab/fixtures", "x.y+z(1).py", "xay+z(1).py"]


def test_FR_0_0_06_path_classification_identical_to_hook():
    hook = _hook_eval(
        "import json\nfrom _protected import load_patterns, classify, glob_to_regex\n"
        f"s = load_patterns({str(ROOT)!r})\n"
        f"c = {{p: classify(p, s) for p in {PATHS!r}}}\n"
        f"g = {{gl: [bool(glob_to_regex(gl).match(p)) for p in {PROBES!r}] for gl in {GLOBS!r}}}\n"
        "print(json.dumps({'classify': c, 'globs': g}))")
    sections = gate.load_protected(ROOT)
    ours = {"classify": {p: gate.classify(p, sections) for p in PATHS},
            "globs": {gl: [bool(gate.glob_to_regex(gl).match(p)) for p in PROBES] for gl in GLOBS}}
    assert ours == hook
    assert ours["classify"]["tests/aqis_lab/test_y.py"] == "LAB" and ours["classify"]["bots/x.py"] == "GUARDED"
