"""FR-0.0-05: the audit gate's checks (a) to (d), each proven to detect its violation and pass clean input."""
import json

import pytest

from fixture_repo import FIXTURES, FixtureRepo
from aqis_testutil import git
from tools.audit import patterns

EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
HEADER_MODULE = '"""New lab module.\n\nCAPABILITIES:\n  CAP-FIX-002: doubles [tests: test_adds]\n"""\n\n\ndef double(x):\n    return 2 * x\n'
SIX_LINE_MODULE = "".join(f"VALUE_{i} = {i}\n" for i in range(6))
FIVE_LINE_MODULE = "".join(f"VALUE_{i} = {i}\n" for i in range(5))


def rules(report):
    return sorted((f["rule"], f["path"]) for f in report["findings"])


@pytest.fixture
def repo(tmp_path):
    return FixtureRepo(tmp_path)


# ---- (a) protected paths -----------------------------------------------------------------
def test_FR_0_0_05_a_builtin_never_list_applies_when_policy_section_removed(repo):
    # Audit F28 (M26): a branch that deletes the [NEVER] section of PROTECTED_PATHS.txt and rewrites CLAUDE.md
    # is still caught, by the built-in NEVER list.
    repo.branch()
    policy = (repo.path / "docs/process/PROTECTED_PATHS.txt").read_text(encoding="utf-8")
    start, end = policy.index("[NEVER]"), policy.index("[GUARDED]")
    repo.write("docs/process/PROTECTED_PATHS.txt", policy[:start] + policy[end:])
    repo.write("CLAUDE.md", "rewritten\n")
    repo.commit("drop the NEVER section")
    report = repo.gate_json()
    assert report["ok"] is False
    assert sorted((f["rule"], f["path"], f["state"]) for f in report["findings"]) == [
        ("A1", "CLAUDE.md", "A"), ("A1", "docs/process/PROTECTED_PATHS.txt", "M")]


@pytest.mark.parametrize("text", [
    "STATUS: APPROVED\nCONDITIONS:\n- ALLOW-EDIT: vad_adapters/**\n",
    "STATUS: APPROVED\n  ALLOW-EDIT: vad_adapters/**\n",
    "- STATUS: APPROVED\nALLOW-EDIT: vad_adapters/**\n",
    "  STATUS: APPROVED\nALLOW-EDIT: vad_adapters/**\n",
    "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/** (WP-0.1 only)\n",
], ids=["bulleted_allow_edit", "indented_allow_edit", "bulleted_status", "indented_status", "trailing_text"])
def test_FR_0_0_05_a_approval_lines_must_start_the_line(repo, text):
    # Audit F33: STATUS: APPROVED and ALLOW-EDIT count only at the start of a line, with the value ending it
    # (as in the Stop hook); a bullet, an indent or trailing text approves nothing.
    repo.commit_approval_text_on_main("WP-9.9.md", text)
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    report = repo.gate_json()
    assert report["ok"] is False and rules(report) == [("A2", "vad_adapters/example.py")]


def test_FR_0_0_05_a_standard_approval_lines_still_approve(repo):
    # The positive control for the test above: the same approval written in the standard form approves.
    repo.commit_approval_text_on_main("WP-9.9.md", "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/**\n- EXPIRES: 2000-01-01\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    report = repo.gate_json()
    assert report["ok"] is True and report["findings"] == []     # a bulleted EXPIRES line is not an expiry


def test_FR_0_0_05_c_indented_allow_patterns_in_exempts_nothing(repo):
    # Audit F33: an indented ALLOW-PATTERNS-IN line exempts no file.
    repo.commit_approval_text_on_main("WP-9.9.md", "STATUS: APPROVED\n  ALLOW-PATTERNS-IN: tools/t.py\n")
    repo.branch()
    repo.copy_fixture("code_patterns.py", "tools/t.py")
    report = repo.gate_json()
    assert report["exempted_files"] == []
    assert {f["rule"] for f in report["findings"]} == {"C1"} and all(f["path"] == "tools/t.py" for f in report["findings"])


def test_FR_0_0_05_a_approvals_readme_approves_nothing(repo):
    # Audit F28 (M24): docs/approvals/README.md on main is ignored even when it holds approval lines.
    repo.approve_on_main("README.md", "ALLOW-EDIT: vad_adapters/**\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    report = repo.gate_json()
    assert rules(report) == [("A2", "vad_adapters/example.py")]


def test_FR_0_0_05_a_detects_renamed_guarded_harness_test(repo):
    # Audit F28 (M23): with --no-renames a rename is a delete plus an add of guarded paths, and a deleted test.
    repo.branch()
    git(repo.path, "mv", "tests/regression/test_example.py", "tests/regression/test_moved.py")
    repo.commit("rename a harness test")
    report = repo.gate_json()
    found = sorted((f["rule"], f["path"], f.get("state")) for f in report["findings"])
    assert found == [("A2", "tests/regression/test_example.py", "D"), ("A2", "tests/regression/test_moved.py", "A"),
                     ("B2", "tests/regression/test_example.py", "D")]


def test_FR_0_0_05_a_detects_never_path(repo):
    repo.branch()
    repo.append("docs/process/PROTECTED_PATHS.txt", "\n# edited\n")
    repo.commit("edit policy")
    repo.write("CLAUDE.md", "new\n")
    report = repo.gate_json()
    assert rules(report) == [("A1", "CLAUDE.md"), ("A1", "docs/process/PROTECTED_PATHS.txt")]
    states = {f["path"]: f["state"] for f in report["findings"]}
    assert states == {"CLAUDE.md": "A", "docs/process/PROTECTED_PATHS.txt": "M"}
    assert all(f["severity"] == "CRITICAL" for f in report["findings"])


def test_FR_0_0_05_a_detects_guarded_path_without_approval(repo):
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    report = repo.gate_json()
    assert rules(report) == [("A2", "vad_adapters/example.py")]
    assert report["findings"][0]["line"] == 3


def test_FR_0_0_05_a_passes_guarded_path_with_main_approval(repo):
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    report = repo.gate_json()
    assert report["findings"] == [] and report["ok"] is True
    assert report["approvals_ref"] == "origin/main"


def test_FR_0_0_05_a_fetches_missing_origin_main_once(repo):
    # Audit F46 (G22): a clone whose origin/main ref is gone fetches it once, then uses its approvals.
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    main_commit = git(repo.path, "rev-parse", "origin/main").strip()
    git(repo.path, "update-ref", "-d", "refs/remotes/origin/main")
    proc = repo.gate("--base", "main")                    # the base is the local main; only origin/main is gone
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert git(repo.path, "rev-parse", "origin/main").strip() == main_commit      # fetched back
    assert report["approvals_ref"] == "origin/main" and report["approvals_commit"] == main_commit
    assert report["findings"] == [] and report["ok"] is True


def test_FR_0_0_05_a_ignores_approval_committed_only_on_branch(repo):
    repo.branch()
    repo.write("docs/approvals/WP-9.9.md", "STATUS: APPROVED\nALLOW-EDIT: vad_adapters/example.py\n")
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    repo.commit("self-approval on the branch")
    assert rules(repo.gate_json()) == [("A1", "docs/approvals/WP-9.9.md"), ("A2", "vad_adapters/example.py")]


@pytest.mark.parametrize("status,extra", [("WITHDRAWN", ""), ("APPROVED", "EXPIRES: 2020-01-01\n")])
def test_FR_0_0_05_a_ignores_expired_or_withdrawn_approval(repo, status, extra):
    repo.approve_on_main("WP-9.9.md", extra + "ALLOW-EDIT: vad_adapters/example.py\n", status=status)
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    assert rules(repo.gate_json()) == [("A2", "vad_adapters/example.py")]


def test_FR_0_0_05_a_uses_approval_added_on_main_after_branch_point(repo):
    # WP-0.0-F02: the approval exists only on origin/main, after the branch point; the branch never merges it.
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    repo.commit("branch edits a guarded file")
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n", merge_into_branch=False)
    merge_base = git(repo.path, "merge-base", "origin/main", "HEAD").strip()
    assert merge_base != git(repo.path, "rev-parse", "origin/main").strip()
    report = repo.gate_json()
    assert report["findings"] == []
    assert report["approvals_commit"] == git(repo.path, "rev-parse", "origin/main").strip()


def test_FR_0_0_05_a_honours_withdrawal_on_main_after_branch_point(repo):
    # WP-0.0-F02: approved at the branch point, withdrawn on origin/main later; the branch never merges it.
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nEXTRA = 1\n")
    repo.commit("branch edits a guarded file")
    assert repo.gate_json()["findings"] == []
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n", status="WITHDRAWN",
                         merge_into_branch=False)
    assert rules(repo.gate_json()) == [("A2", "vad_adapters/example.py")]


# ---- (b) existing tests ------------------------------------------------------------------
def test_FR_0_0_05_b_detects_modified_existing_test(repo):
    repo.branch()
    repo.append("tests/lab_support/test_adds.py", "\n\ndef test_more():\n    assert add(1, 1) == 2\n")
    assert rules(repo.gate_json()) == [("A2", "tests/lab_support/test_adds.py"), ("B1", "tests/lab_support/test_adds.py")]


def test_FR_0_0_05_b_detects_deleted_existing_test(tmp_path):
    repo = FixtureRepo(tmp_path, with_lab_test=True)
    repo.branch()
    repo.delete("tests/aqis_lab/test_existing.py")
    repo.commit("drop test")
    report = repo.gate_json()
    # The deleted file held the only test named by registry row CAP-FIX-001, so check (e) reports it too.
    assert rules(report) == [("B2", "tests/aqis_lab/test_existing.py"), ("E3", "docs/capabilities/REGISTRY.md")]
    assert report["findings"][0]["severity"] == "CRITICAL"


def test_FR_0_0_05_b_detects_renamed_existing_lab_test(tmp_path):
    # Audit F28 (M23): renaming an existing lab test away deletes the original test.
    repo = FixtureRepo(tmp_path, with_lab_test=True)
    repo.branch()
    git(repo.path, "mv", "tests/aqis_lab/test_existing.py", "tests/aqis_lab/test_renamed.py")
    repo.commit("rename a lab test")
    report = repo.gate_json()
    assert report["ok"] is False
    assert rules(report) == [("B2", "tests/aqis_lab/test_existing.py")]


def test_FR_0_0_05_b_passes_new_test_and_approved_edit(tmp_path):
    repo = FixtureRepo(tmp_path, with_lab_test=True)
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: tests/aqis_lab/test_existing.py\n")
    repo.branch()
    repo.append("tests/aqis_lab/test_existing.py", "\n\ndef test_zero():\n    assert add(0, 0) == 0\n")
    repo.write("tests/aqis_lab/test_new.py", "def test_new():\n    assert 3 * 3 == 9\n")
    assert repo.gate_json()["findings"] == []


# ---- (c) compromise patterns -------------------------------------------------------------
def test_FR_0_0_05_c_detects_each_code_pattern(repo):
    repo.branch()
    repo.copy_fixture("code_patterns.py", "tools/bad_code.py")
    report = repo.gate_json()
    got = {str(f["line"]): f["label"] for f in report["findings"] if f["rule"] == "C1"}
    assert got == EXPECTED["code_patterns.py"]
    assert {label for label, _ in patterns.CODE_PATTERNS} == set(EXPECTED["code_patterns.py"].values())
    assert all(f["path"] == "tools/bad_code.py" and f["severity"] == "COMPROMISE" for f in report["findings"])


def test_FR_0_0_05_c_detects_each_test_pattern(repo):
    repo.branch()
    repo.copy_fixture("test_patterns.py", "tests/aqis_lab/test_bad.py")
    report = repo.gate_json()
    got = {str(f["line"]): f["label"] for f in report["findings"] if f["rule"] == "C2"}
    assert got == EXPECTED["test_patterns.py"]
    assert {label for label, _ in patterns.TEST_PATTERNS} == set(EXPECTED["test_patterns.py"].values())
    assert len(report["findings"]) == len(got)


def test_FR_0_0_05_c_scans_only_added_lines(repo):
    repo.branch()
    # tools/existing_tool.py already contains the word TODO at the base; only new lines count.
    repo.append("tools/existing_tool.py", "\n\ndef other():\n    return 'fine'\n")
    repo.commit("extend tool")
    assert repo.gate_json()["findings"] == []
    repo.append("tools/existing_tool.py", "# FIXME later\n")
    report = repo.gate_json()
    assert [(f["rule"], f["line"], f["label"]) for f in report["findings"]] == [("C1", 7, "TODO/FIXME/XXX marker")]


def test_FR_0_0_05_c_includes_uncommitted_and_untracked_work(repo):
    repo.branch()
    repo.write("tools/committed.py", "A = 1\n")
    repo.commit("clean commit")
    repo.append("tools/committed.py", "B = 'dummy'\n")          # uncommitted change to a tracked file
    repo.write("tools/untracked.py", "C = 'fake'\n")             # untracked file
    report = repo.gate_json()
    assert sorted((f["path"], f["line"]) for f in report["findings"]) == [("tools/committed.py", 2), ("tools/untracked.py", 1)]


# ---- (d) CAPABILITIES headers ------------------------------------------------------------
def test_FR_0_0_05_d_detects_new_module_without_header(repo):
    repo.branch()
    repo.write("aqis_lab/no_header.py", SIX_LINE_MODULE)
    report = repo.gate_json()
    assert rules(report) == [("D1", "aqis_lab/no_header.py")]
    assert report["findings"][0]["severity"] == "MAJOR" and report["findings"][0]["line"] == 1


def test_FR_0_0_05_d_passes_module_with_header_or_short_file(repo):
    repo.branch()
    repo.write("aqis_lab/with_header.py", HEADER_MODULE)
    repo.write("aqis_lab/short.py", FIVE_LINE_MODULE)
    repo.write("tools/no_header_tool.py", SIX_LINE_MODULE)        # check (d) covers aqis_lab/ only
    repo.append("aqis_lab/existing.py", SIX_LINE_MODULE)         # not a new module
    assert repo.gate_json()["findings"] == []


# ---- whole-gate behaviour ----------------------------------------------------------------
def test_FR_0_0_05_clean_branch_exits_zero(repo):
    repo.branch()
    repo.write("aqis_lab/with_header.py", HEADER_MODULE)
    repo.write("docs/notes.md", "free text with TODO is fine outside code\n")
    repo.commit("clean work")
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().splitlines()[-1].startswith("0 findings")


def test_FR_0_0_05_uses_merge_base_not_ref_tip(repo):
    repo.branch()
    repo.write("aqis_lab/with_header.py", HEADER_MODULE)
    repo.commit("branch work")
    # main moves on after the branch point; those changes are not the branch's.
    git(repo.path, "checkout", "-q", "main")
    repo.write("vad_adapters/example.py", "def harness_value():\n    return 43\n")
    repo.write("tools/main_only.py", "X = 'dummy'\n")
    repo.commit("main moves")
    git(repo.path, "push", "-q", "origin", "main")
    git(repo.path, "checkout", "-q", "feature")
    report = repo.gate_json()
    assert report["findings"] == []
    assert report["base_commit"] == git(repo.path, "merge-base", "origin/main", "HEAD").strip()
    assert report["base_commit"] != git(repo.path, "rev-parse", "origin/main").strip()


def test_FR_0_0_05_json_output_schema(repo):
    repo.branch()
    repo.write("vad_adapters/new.py", "X = 1\n")
    report = repo.gate_json()
    for key in ("tool", "base_ref", "base_commit", "head_commit", "approvals_ref", "approvals_commit", "wp",
                "findings", "exempted_lines", "exempted_files", "ok"):
        assert key in report, key
    assert report["base_ref"] == "origin/main" and report["wp"] is None and report["ok"] is False
    finding = report["findings"][0]
    for key in ("rule", "check", "severity", "path", "line", "message"):
        assert key in finding, key
    assert (finding["rule"], finding["check"], finding["path"], finding["line"]) == ("A2", "a", "vad_adapters/new.py", 1)


def test_FR_0_0_05_bad_base_ref_exits_2(repo):
    proc = repo.gate("--base", "no-such-ref", json_output=False)
    assert proc.returncode == 2
    assert proc.stderr.startswith("ERROR:") and "no-such-ref" in proc.stderr
