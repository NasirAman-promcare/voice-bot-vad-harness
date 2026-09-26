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


def s_v2_file_types(r):
    r.branch(); r.copy_fixture("shell_patterns.sh", "aqis_lab/deploy/x.sh"); r.copy_fixture("lab_ci.yml", ".github/workflows/aqis-lab-x.yml")
    r.copy_fixture("requirements.in", "requirements/aqis_lab/x.in"); r.copy_fixture("config.toml", "config/aqis_lab/x.toml")
    r.copy_fixture("shell_patterns.sh", "tests/aqis_lab/x.sh"); r.copy_fixture("config.toml", "config/other.toml")


def s_pytestmark(r):
    r.branch(); r.copy_fixture("test_pytestmark.py", "tests/aqis_lab/test_marked.py")


def s_added_then_deleted_in_worktree(r):
    r.branch(); r.write("vad_adapters/staged.py", "S = 1\n"); git(r.path, "add", "vad_adapters/staged.py")
    r.delete("vad_adapters/staged.py"); r.write("tools/z.py", "Z = 'fake'\n")


def s_non_utf8(r):
    r.branch(); r.copy_fixture("non_utf8.py", "tools/non_utf8.py"); r.copy_fixture("non_utf8.py", "aqis_lab/non_utf8.py")
    with open(r.path / "tools/existing_tool.py", "ab") as handle:
        handle.write(b"# XXX caf\xe9\n")


def s_clean(r):
    r.branch(); r.write("aqis_lab/ok.py", '"""Ok.\n\nCAPABILITIES:\n  CAP-X-1: y [tests: t]\n"""\nA = 1\nB = 2\nC = 3\nD = 4\n')
    r.write("docs/notes.md", "TODO in prose is fine\n")


def strip_never_section(text):
    """PROTECTED_PATHS.txt without its [NEVER] section (the lines from [NEVER] up to the next section)."""
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        if line.strip().startswith("["):
            skipping = line.strip() == "[NEVER]"
        if not skipping:
            out.append(line)
    assert "[NEVER]" not in "".join(out) and "[GUARDED]" in "".join(out)
    return "".join(out)


def s_never_section_stripped(r):
    # Audit F28 (M26): the built-in NEVER list still applies when the branch deletes the [NEVER] section.
    r.branch()
    policy = r.path / "docs/process/PROTECTED_PATHS.txt"
    r.write("docs/process/PROTECTED_PATHS.txt", strip_never_section(policy.read_text(encoding="utf-8")))
    r.write("CLAUDE.md", "rewritten\n"); r.commit("c")


def s_renamed_lab_test(r):
    # Audit F28 (M23): --no-renames; a renamed existing lab test counts as deleted.
    r.branch(); git(r.path, "mv", "tests/aqis_lab/test_existing.py", "tests/aqis_lab/test_renamed.py"); r.commit("c")


def s_renamed_harness_test(r):
    r.branch(); git(r.path, "mv", "tests/regression/test_example.py", "tests/regression/test_moved.py"); r.commit("c")


def s_readme_approval(r):
    # Audit F28 (M24): docs/approvals/README.md is never an approval, whatever it contains.
    r.approve_on_main("README.md", "ALLOW-EDIT: vad_adapters/**\n")
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n")


def s_expired_approval(r):
    r.approve_on_main("WP-9.9.md", "EXPIRES: 2000-01-01\nALLOW-EDIT: vad_adapters/**\n")
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n")


def s_unapproved_status(r):
    r.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/**\n", status="DRAFT")
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n")


def s_multi_pattern_line(r):
    # Audit F29 (M16): one added line matching three code patterns gives one finding (the first pattern wins).
    r.branch(); r.write("tools/multi.py", 'NOTE = "TODO: placeholder hack"\n')


def s_late_header(r):
    # Audit F29 (M17): the header must be within the first 80 lines of a new lab module.
    lines = [f"V{i} = {i}\n" for i in range(91)] + ["CAPABILITIES: int = 1\n", "W = 2\n", "X = 3\n"]
    assert len(lines) == 94 and lines[91].startswith("CAPABILITIES:")
    r.branch(); r.write("aqis_lab/late_header.py", "".join(lines))


def s_modified_headerless_module(r):
    # Audit F29 (M18): only new lab modules need a header; an existing header-less one may be modified.
    r.write("aqis_lab/legacy.py", "".join(f"L{i} = {i}\n" for i in range(10))); r.commit("legacy module on main")
    git(r.path, "push", "-q", "origin", "main")
    r.branch(); r.append("aqis_lab/legacy.py", "L10 = 10\n")


# ---- audit round 5 (F33): approval keywords count only at the start of a line, with the value ending it ----
APPROVAL_TEXTS = {
    "bulleted_allow_edit": "STATUS: APPROVED\nCONDITIONS:\n- ALLOW-EDIT: vad_adapters/**\n",
    "indented_allow_edit": "STATUS: APPROVED\n  ALLOW-EDIT: vad_adapters/**\n",
    "bulleted_status": "- STATUS: APPROVED\nALLOW-EDIT: vad_adapters/**\n",
    "allow_edit_trailing_text": "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/** (WP-0.1 only)\n",
}


def approval_text_scenario(key):
    def scenario(r):
        r.commit_approval_text_on_main("WP-9.9.md", APPROVAL_TEXTS[key])
        r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n")
    return scenario


def s_indented_allow_patterns_in(r):
    r.commit_approval_text_on_main("WP-9.9.md", "STATUS: APPROVED\n  ALLOW-PATTERNS-IN: tools/t.py\n")
    r.branch(); r.copy_fixture("code_patterns.py", "tools/t.py")


def s_bulleted_expires(r):
    # "- EXPIRES:" is not an expiry line, so the approval still counts: no finding.
    r.commit_approval_text_on_main("WP-9.9.md", "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/**\n- EXPIRES: 2000-01-01\n")
    r.branch(); r.append("vad_adapters/example.py", "\nY = 2\n")


# ---- audit round 5 (F34) ----------------------------------------------------------------------------
def s_modified_non_py_test_file(r):
    # Check (b) applies to .py files under tests/ only.
    r.write("tests/aqis_lab/data/expected.json", '{"a": 1}\n'); r.commit("data on main")
    git(r.path, "push", "-q", "origin", "main")
    r.branch(); r.write("tests/aqis_lab/data/expected.json", '{"a": 2}\n')


def s_non_py_lab_test_file(r):
    # Test patterns apply to .py files under tests/aqis_lab/ only.
    # The text names an expected-failure marker, so it lives in the fixtures folder (PLAN.md test-data rule).
    r.branch(); r.copy_fixture("lab_test_readme.md", "tests/aqis_lab/README.md")


def s_guarded_added_then_deleted(r):
    # A GUARDED file committed on the branch, then deleted in the working tree, is ignored.
    r.branch(); r.write("vad_adapters/tmp_adapter.py", "T = 1\n"); r.commit("add")
    r.delete("vad_adapters/tmp_adapter.py"); r.write("tools/z.py", "Z = 'fake'\n")


def s_flagged_word_in_path(r):
    # Diff header lines (+++ b/tools/fake.py) are not added lines. The path must hold the word with a word
    # boundary after it ("fake_clock" would not match the pattern, so it could not show the difference).
    r.write("tools/fake.py", "CLOCK = 0\n"); r.commit("clock on main")
    git(r.path, "push", "-q", "origin", "main")
    r.branch(); r.append("tools/fake.py", "TICK = 1\n")


def s_unscanned_suffix_in_lab_dirs(r):
    # Only files with a scanned suffix under the lab code folders are scanned for code patterns.
    r.branch(); r.write("aqis_lab/NOTES.md", "TODO: write the placeholder notes\n"); r.write("tools/data.json", '{"fake": 1}\n')


def s_staged_rename_of_harness_test(r):
    # --no-renames also applies to staged, uncommitted work.
    r.branch(); git(r.path, "mv", "tests/regression/test_example.py", "tests/regression/test_staged.py")


SCENARIOS = {
    "never": (s_never, False), "guarded": (s_guarded, False), "guarded_approved": (s_guarded_approved, False),
    "branch_only_approval": (s_branch_only_approval, False), "modified_harness_test": (s_modified_harness_test, False),
    "deleted_lab_test": (s_deleted_lab_test, True), "approved_lab_test_edit": (s_approved_lab_test_edit, True),
    "code_patterns": (s_code_patterns, False), "test_patterns": (s_test_patterns, False),
    "allow_lines": (s_allow_lines, False), "allow_patterns_in": (s_allow_patterns_in, False),
    "headers": (s_headers, False), "added_then_removed": (s_added_then_removed, False),
    "main_moved": (s_main_moved, False), "combined": (s_combined, False), "clean": (s_clean, False),
    "v2_file_types": (s_v2_file_types, False), "pytestmark": (s_pytestmark, False),
    "added_then_deleted_in_worktree": (s_added_then_deleted_in_worktree, False), "non_utf8": (s_non_utf8, False),
    # audit round 4 (F28, F29): every parity rule in PLAN.md "Parity with the Stop hook" has a scenario
    "never_section_stripped": (s_never_section_stripped, False), "renamed_lab_test": (s_renamed_lab_test, True),
    "renamed_harness_test": (s_renamed_harness_test, False), "readme_approval": (s_readme_approval, False),
    "expired_approval": (s_expired_approval, False), "unapproved_status": (s_unapproved_status, False),
    "multi_pattern_line": (s_multi_pattern_line, False), "late_header": (s_late_header, False),
    "modified_headerless_module": (s_modified_headerless_module, False),
    # audit round 5 (F33, F34)
    **{key: (approval_text_scenario(key), False) for key in APPROVAL_TEXTS},
    "indented_allow_patterns_in": (s_indented_allow_patterns_in, False), "bulleted_expires": (s_bulleted_expires, False),
    "modified_non_py_test_file": (s_modified_non_py_test_file, False),
    "non_py_lab_test_file": (s_non_py_lab_test_file, False),
    "guarded_added_then_deleted": (s_guarded_added_then_deleted, False),
    "flagged_word_in_path": (s_flagged_word_in_path, False),
    "staged_rename_of_harness_test": (s_staged_rename_of_harness_test, False),
    "unscanned_suffix_in_lab_dirs": (s_unscanned_suffix_in_lab_dirs, False),
}
EXPECT_NONE = {"guarded_approved", "approved_lab_test_edit", "clean", "modified_headerless_module", "bulleted_expires",
               "modified_non_py_test_file", "non_py_lab_test_file", "flagged_word_in_path", "unscanned_suffix_in_lab_dirs"}
# Scenarios whose exact findings are fixed here, so a change the hook shares cannot pass unnoticed either.
EXPECT_EXACT = {
    **{key: [("A2", "vad_adapters/example.py", "M")] for key in APPROVAL_TEXTS},
    "guarded_added_then_deleted": [("C", "tools/z.py", 1, "dummy or fake wording", "Z = 'fake'")],
    "staged_rename_of_harness_test": [("A2", "tests/regression/test_example.py", "D"),
                                      ("A2", "tests/regression/test_staged.py", "A"),
                                      ("B2", "tests/regression/test_example.py")],
}


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
    elif name in EXPECT_EXACT:
        assert ours == sorted(EXPECT_EXACT[name], key=repr)
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
        " 'lab_code': list(s.LAB_CODE_DIRS), 'lab_test': s.LAB_TEST_DIR, 'hunk': s.HUNK_RE.pattern,"
        " 'suffixes': list(s.SCANNED_SUFFIXES), 'ci_files': s.LAB_CI_FILES.pattern}))")
    ours = {
        "code": [[l, r.pattern, r.flags] for l, r in patterns.CODE_PATTERNS],
        "test": [[l, r.pattern, r.flags] for l, r in patterns.TEST_PATTERNS],
        "allow": [patterns.ALLOW_RE.pattern, patterns.ALLOW_RE.flags],
        "header": [patterns.HEADER_RE.pattern, patterns.HEADER_RE.flags],
        "lab_code": list(patterns.LAB_CODE_DIRS), "lab_test": patterns.LAB_TEST_DIR, "hunk": gate.HUNK_RE.pattern,
        "suffixes": list(patterns.SCANNED_SUFFIXES), "ci_files": patterns.LAB_CI_FILES.pattern,
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
