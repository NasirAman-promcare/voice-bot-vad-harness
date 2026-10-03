"""Accepted debt closed in WP-0.9 (docs/progress/DEBT.md; plan docs/progress/WP-0.9/PLAN.md, "Debt work").

Each test is named after the requirement whose behaviour it protects, and each must fail when that behaviour
is broken; the breaks are recorded in docs/progress/WP-0.9/EVIDENCE.md.
- DEBT-001 to DEBT-005: WP-0.0 gate, regression check, provisioning and bootstrap behaviours without a test,
  and the pytest collection rules the gate's test index did not model (DEBT-004).
"""
import json
import subprocess
import sys
import tarfile

import pytest

import test_aqis_harness_provision as provision_tests
from aqis_testutil import ROOT, git, probe_python_major_minor
from fixture_repo import FixtureRepo, normalise_gate, normalise_hook
from test_aqis_bootstrap import make_tree as bootstrap_tree, run as run_bootstrap

REG = "docs/capabilities/REGISTRY.md"


def registry_row(cap, module, tests):
    return f"| {cap} | {module} | `f` | does things | {tests} | WP-9.9 FR-9.9-01 | ACTIVE |\n"


def findings_of(report, check):
    return sorted((f["rule"], f["path"], f["line"], f["message"]) for f in report["findings"] if f["check"] == check)


# ---------------------------------------------------------------------------------------------
# DEBT-001 (WP-0.0-F48): an approvals README in any letter case approves nothing, in the hook and the gate
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["readme.md", "ReadMe.md"])
def test_FR_0_0_06_parity_lowercase_readme_approval_approves_nothing(tmp_path, name):
    repo = FixtureRepo(tmp_path)
    repo.approve_on_main(name, "ALLOW-EDIT: vad_adapters/**\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nY = 2\n")
    hook = normalise_hook(repo.hook_lines())
    ours = normalise_gate(repo.gate_json())
    assert ours == hook == [("A2", "vad_adapters/example.py", "M")]


# ---------------------------------------------------------------------------------------------
# DEBT-002 (WP-0.0-F51): G37, G40, G33, G63
# ---------------------------------------------------------------------------------------------
TRACE_SPEC = "# WP-9.9 — Thing\n\n## Functional requirements\n- **FR-9.9-01** does a.\n"
TRACE_TEST = "def test_FR_9_9_01_does_a():\n    assert 1 + 1 == 2\n"


def traced_repo(tmp_path, spec_files, test_rel="tests/aqis_lab/test_thing.py", plan_ids=("FR-9.9-01",)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = FixtureRepo(tmp_path)
    for rel, text in spec_files.items():
        repo.write(rel, text)
    repo.commit("specs on main")
    git(repo.path, "push", "-q", "origin", "main")
    repo.branch()
    record = "# Record\n\n" + "\n".join(f"- {i}: covered" for i in plan_ids) + "\n"
    repo.write("docs/progress/WP-9.9/PLAN.md", record)
    repo.write("docs/progress/WP-9.9/EVIDENCE.md", record)
    repo.write(test_rel, TRACE_TEST)
    return repo


def test_FR_0_0_09_two_specs_for_one_wp_is_a_finding(tmp_path):
    # G37: exactly one spec may match docs/specs/**/<WP>-*.md; a second one is a finding naming both.
    repo = traced_repo(tmp_path, {"docs/specs/phase-9/WP-9.9-thing.md": TRACE_SPEC,
                                  "docs/specs/phase-9/WP-9.9-other.md": TRACE_SPEC})
    found = findings_of(repo.gate_json("--wp", "WP-9.9"), "f")
    assert found == [("F1", "docs/specs/**/WP-9.9-*.md", 1,
                      "expected exactly one spec matching docs/specs/**/WP-9.9-*.md, found: "
                      "docs/specs/phase-9/WP-9.9-other.md, docs/specs/phase-9/WP-9.9-thing.md")]
    single = traced_repo(tmp_path / "single", {"docs/specs/phase-9/WP-9.9-thing.md": TRACE_SPEC})
    assert findings_of(single.gate_json("--wp", "WP-9.9"), "f") == []


def test_FR_0_0_09_only_lab_test_names_count(tmp_path):
    # G40: a matching test name outside tests/aqis_lab/ does not trace the ID.
    repo = traced_repo(tmp_path, {"docs/specs/phase-9/WP-9.9-thing.md": TRACE_SPEC},
                       test_rel="tests/lab_support/test_thing.py")
    found = findings_of(repo.gate_json("--wp", "WP-9.9"), "f")
    assert [(r, p, n) for r, p, n, _ in found] == [("F3", "docs/specs/phase-9/WP-9.9-thing.md", 4)]
    assert "FR-9.9-01 is not in any test function name under tests/aqis_lab/" in found[0][3]


def test_FR_0_0_08_registry_module_that_is_a_folder_is_a_finding(tmp_path):
    # G33: a path-style Module must be a file; a folder of that name does not count.
    repo = FixtureRepo(tmp_path)
    repo.branch()
    repo.write("aqis_lab/pkg/inner.py", "VALUE = 1\n")
    repo.append(REG, registry_row("CAP-FIX-002", "`aqis_lab/pkg`", "`test_adds`"))
    repo.append(REG, registry_row("CAP-FIX-003", "`aqis_lab/pkg/inner.py`", "`test_adds`"))
    found = findings_of(repo.gate_json(), "e")
    assert [(r, n) for r, _, n, _ in found] == [("E4", 6)]
    assert "CAP-FIX-002: module aqis_lab/pkg does not exist" in found[0][3]


def test_FR_0_0_08_registry_row_without_capability_id_is_malformed(tmp_path):
    # G63: every row needs a capability ID; a row without one is malformed even when its cells are valid.
    repo = FixtureRepo(tmp_path)
    repo.branch()
    repo.append(REG, registry_row("", "`aqis_lab/existing.py`", "`test_adds`"))
    repo.append(REG, registry_row("``", "`aqis_lab/existing.py`", "`test_adds`"))
    found = findings_of(repo.gate_json(), "e")
    assert [(r, n) for r, _, n, _ in found] == [("E2", 6), ("E2", 7)]
    assert all("with a capability ID" in message for _, _, _, message in found)


# ---------------------------------------------------------------------------------------------
# DEBT-003 (WP-0.0-F53): G44, P32, R15, B16
# ---------------------------------------------------------------------------------------------
def test_FR_0_0_07_exempted_files_list_only_scanned_files(tmp_path):
    # G44: ALLOW-PATTERNS-IN lists a changed file as exempted only when it is in the scan scope.
    repo = FixtureRepo(tmp_path)
    repo.approve_on_main("WP-9.9.md", "ALLOW-PATTERNS-IN: tools/pattern_table.py\nALLOW-PATTERNS-IN: docs/notes/**\n")
    repo.branch()
    repo.copy_fixture("code_patterns.py", "tools/pattern_table.py")
    repo.write("docs/notes/today.md", "A note that is never scanned.\n")
    report = repo.gate_json()
    assert report["exempted_files"] == [{"path": "tools/pattern_table.py", "approval": "WP-9.9.md",
                                         "glob": "tools/pattern_table.py"}]
    assert report["findings"] == []


def test_FR_0_0_12_fetches_pinned_corpus_commit_missing_from_shallow_clone(tmp_path):
    # P32: a shallow clone without the pinned corpus commit fetches it from origin (here a local repository).
    tree, cfg = provision_tests.make_tree(tmp_path)
    corpus_commit = json.loads(cfg.read_text(encoding="utf-8"))["corpus"]["commit"]
    (tree / "LATER.md").write_text("a later commit\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", "later commit")
    clone = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{tree}", str(clone))
    assert git(clone, "rev-parse", "--is-shallow-repository").strip() == "true"
    missing = subprocess.run(["git", "cat-file", "-e", f"{corpus_commit}^{{commit}}"], cwd=clone,
                             capture_output=True, text=True)
    assert missing.returncode != 0, "the shallow clone must not hold the pinned commit before provisioning"
    proc = provision_tests.run(clone, cfg, tmp_path / "cache", "--steps", "corpus")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert provision_tests.table(proc.stdout)["corpus"][0] == "PASS"
    assert subprocess.run(["git", "cat-file", "-e", f"{corpus_commit}^{{commit}}"], cwd=clone).returncode == 0
    assert (clone / "corpus" / "audio" / "a.wav").read_bytes() == provision_tests.WAV_A


@pytest.mark.parametrize("attributes", ['classname="tests.regression.test_example"', 'name="test_harness_example"',
                                        ''])
def test_FR_0_0_11_testcase_without_name_is_an_input_error(tmp_path, attributes):
    # R15: a JUnit testcase without classname or name cannot be matched to the baseline: exit 2, never a pass.
    junit = tmp_path / "junit.xml"
    junit.write_text('<?xml version="1.0"?>\n<testsuites><testsuite name="pytest" tests="1">'
                     f'<testcase {attributes} time="0.1"/></testsuite></testsuites>\n', encoding="utf-8")
    proc = subprocess.run([sys.executable, "-B", "-m", "tools.harness.regression_check", "--junit", str(junit)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr == f"ERROR: testcase without classname or name in {junit}\n"
    assert proc.stdout == ""


def test_FR_0_0_02_probe_repeating_one_version_is_accepted(tmp_path):
    # B16: a probe naming the same Python version in both line forms names one version, not a conflict.
    tree = bootstrap_tree(tmp_path, probe_text="--- COLAB ENVIRONMENT PROBE ---\nPython Version: 3.99.1 (main)\n"
                                               "Python 3.99.1\n")
    proc = run_bootstrap(tree, timeout=120)
    assert "Colab probe requires Python 3.99 (docs/environment/colab_probe.txt)" in proc.stdout
    assert "conflicting" not in proc.stderr
    assert proc.returncode != 0 and "Python 3.99" in proc.stderr  # 3.99 does not exist, so uv stops afterwards


# ---------------------------------------------------------------------------------------------
# DEBT-005 (WP-0.0-F60): K7.7, K10.6, K11.5a, K14.12, X4, X8 (K11.5b closed by the owner's ruling)
# ---------------------------------------------------------------------------------------------
def test_FR_0_0_06_fails_closed_on_unparsable_lab_test_file(tmp_path):
    # K7.7: a test file that does not parse stops the gate (exit 2) instead of being skipped.
    repo = FixtureRepo(tmp_path)
    repo.branch()
    repo.write("tests/lab_support/test_broken.py", "def test_ok():\n    assert True\n\n\ndef test_broken(:\n")
    proc = repo.gate("--base", "origin/main")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith("ERROR: tests/lab_support/test_broken.py:5: cannot parse test file: ")
    assert proc.stdout == ""


def test_FR_0_0_09_traces_every_id_on_a_spec_line(tmp_path):
    # K10.6: every ID on a spec line is traced, not only the first one.
    spec = "# WP-9.9 — Thing\n\n## Functional requirements\n- **FR-9.9-01** does a, and **FR-9.9-02** does b.\n"
    repo = traced_repo(tmp_path, {"docs/specs/phase-9/WP-9.9-thing.md": spec})
    found = findings_of(repo.gate_json("--wp", "WP-9.9"), "f")
    rel = "docs/specs/phase-9/WP-9.9-thing.md"
    assert [(r, p, n) for r, p, n, _ in found] == [("F2", rel, 4), ("F3", rel, 4), ("F4", rel, 4)]
    assert all("FR-9.9-02" in message for _, _, _, message in found)


def test_FR_0_0_02_recreates_venv_built_on_another_python(tmp_path):
    # K11.5a: an existing .venv on another Python major.minor is never reused; it is rebuilt on the probe's.
    probe_text = (ROOT / "docs" / "environment" / "colab_probe.txt").read_text(encoding="utf-8")
    tree = bootstrap_tree(tmp_path, probe_text=probe_text, lock_text="")
    wanted = probe_python_major_minor()
    other = "3.12" if wanted != "3.12" else "3.11"
    made = subprocess.run(["uv", "venv", "-q", "--python", other, str(tree / ".venv")], capture_output=True, text=True,
                          timeout=300)
    assert made.returncode == 0, made.stderr
    proc = run_bootstrap(tree, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"Recreating .venv (found Python {other}, need {wanted})" in proc.stdout
    got = subprocess.run([str(tree / ".venv" / "bin" / "python"), "-c",
                          "import sys; print('%d.%d' % sys.version_info[:2])"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert got == wanted


def test_FR_0_0_12_no_complete_marker_after_failed_extraction(tmp_path):
    # K14.12: the .complete marker is written only after every member is extracted. Here the archive's last
    # member cannot be written (its parent is a file), so extraction stops and no marker may exist.
    bad = tarfile.TarInfo("corpus/audio/a.wav/inside.wav")
    bad.size = 4
    tree, cfg = provision_tests.make_tree(tmp_path, extra_members=[(bad, b"RIFF")])
    cache = tmp_path / "cache"
    proc = provision_tests.run(tree, cfg, cache, "--steps", "corpus")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert provision_tests.table(proc.stdout)["corpus"][0] == "FAIL"
    markers = list(cache.glob("corpus/*/extracted/.complete"))
    assert markers == []
    assert list(cache.glob("corpus/*/extracted/corpus/audio/a.wav")), "extraction must have started"


def test_FR_0_0_12_blank_line_before_import_report(tmp_path):
    # X8: the import check prints a newline before its JSON report, so a module that writes to stdout without
    # a final newline while it is imported cannot merge its text into the report line.
    module, tree, provisioner = provision_tests.import_check_provisioner(tmp_path, ["json", "aqis_half_line", "csv"])
    (tree / "aqis_half_line.py").write_text('import sys\nsys.stdout.write("no newline here")\n', encoding="utf-8")
    provisioner.check_imports(sys.executable)
    assert provisioner.rows == [("imports", "PASS", "imported json, aqis_half_line, csv")]


# ---------------------------------------------------------------------------------------------
# DEBT-004 (WP-0.0-F55) and X4: the gate's test index follows pytest's collection rules
# ---------------------------------------------------------------------------------------------
PROBE_DIR = "tests/aqis_lab/probe9"
DEBT004_PROBE = {
    # folders pytest never enters (pytest 9.1 default norecursedirs, __pycache__ and virtual environments)
    f"{PROBE_DIR}/sub/test_in_sub.py": "def test_in_plain_subfolder():\n    assert 2 + 2 == 4\n",
    **{f"{PROBE_DIR}/{folder}/test_{i}_skipped_folder.py":
       f"def test_only_in_skipped_folder_{i}():\n    assert 2 + 2 == 4\n"
       for i, folder in enumerate(["build", "dist", "venv", "node_modules", ".hidden", "pkg.egg", "_darcs",
                                   "CVS", "{arch}", "__pycache__"])},
    f"{PROBE_DIR}/myenv/pyvenv.cfg": "home = /usr/bin\n",
    f"{PROBE_DIR}/myenv/test_in_venv_folder.py": "def test_only_in_virtualenv_folder():\n    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/condaenv/conda-meta/history": "==> 2026-01-01 <==\n",
    f"{PROBE_DIR}/condaenv/test_in_conda_folder.py": "def test_only_in_conda_folder():\n    assert 2 + 2 == 4\n",
    # conftest collect_ignore and collect_ignore_glob; the nearest conftest that defines a name wins
    f"{PROBE_DIR}/conftest.py": ('collect_ignore = ["ignored_dir", "test_ignored_file.py", "near/test_far_ignored.py"]\n'
                                 'collect_ignore_glob = ["*_globbed.py"]\n'),
    f"{PROBE_DIR}/ignored_dir/test_in_ignored_dir.py": "def test_only_in_ignored_dir():\n    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/test_ignored_file.py": "def test_only_in_ignored_file():\n    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/test_x_globbed.py": "def test_only_in_globbed_file():\n    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/near/conftest.py": "collect_ignore = []\n",
    f"{PROBE_DIR}/near/test_far_ignored.py": "def test_in_file_only_the_far_conftest_ignores():\n    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/near/test_y_globbed.py": "def test_only_in_file_globbed_by_far_conftest():\n    assert 2 + 2 == 4\n",
    # false __test__ values other than False, inherited and later rebound values
    f"{PROBE_DIR}/test_zero_switch.py": "__test__ = 0\n\n\ndef test_only_in_module_switched_off_by_zero():\n"
                                        "    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/test_none_switch.py": "__test__ = None\n\n\ndef test_only_in_module_switched_off_by_none():\n"
                                        "    assert 2 + 2 == 4\n",
    f"{PROBE_DIR}/test_switched_back_on.py": ("__test__ = False\n__test__ = True\n\n\n"
                                              "def test_in_module_switched_back_on():\n    assert 2 + 2 == 4\n"),
    f"{PROBE_DIR}/test_classes_switch.py": (
        "class TestEmptyListSwitch:\n    __test__ = []\n\n    def test_only_in_class_switched_off_by_empty_list(self):\n"
        "        assert 2 + 2 == 4\n\n\n"
        "class Off:\n    __test__ = False\n\n\n"
        "class TestInheritsSwitchOff(Off):\n    def test_only_in_class_inheriting_switch_off(self):\n"
        "        assert 2 + 2 == 4\n\n\n"
        "class TestSwitchesBackOn(Off):\n    __test__ = True\n\n    def test_in_class_switched_back_on(self):\n"
        "        assert 2 + 2 == 4\n\n\n"
        "class TestComputedSwitch:\n    __test__ = bool(0)\n\n    def test_only_in_class_with_computed_switch(self):\n"
        "        assert 2 + 2 == 4\n"),
    # abstract Test classes
    f"{PROBE_DIR}/test_abstract.py": (
        "import abc\nfrom abc import ABCMeta, abstractmethod\n\n\n"
        "class TestAbstract(metaclass=ABCMeta):\n    @abstractmethod\n    def helper(self):\n        return 0\n\n"
        "    def test_only_in_abstract_class(self):\n        assert 2 + 2 == 4\n\n\n"
        "class TestAbstractViaModule(metaclass=abc.ABCMeta):\n    @abc.abstractmethod\n    def helper(self):\n"
        "        return 0\n\n    def test_only_in_abc_module_abstract_class(self):\n        assert 2 + 2 == 4\n\n\n"
        "class AbstractBase(metaclass=ABCMeta):\n    @abstractmethod\n    def helper(self):\n        return 0\n\n\n"
        "class TestStillAbstract(AbstractBase):\n    def test_only_in_class_still_abstract(self):\n        assert 2 + 2 == 4\n\n\n"
        "class TestMadeConcrete(AbstractBase):\n    def helper(self):\n        return 1\n\n"
        "    def test_in_class_made_concrete(self):\n        assert 2 + 2 == 4\n\n\n"
        "class TestAbcMetaWithoutAbstractMethods(metaclass=ABCMeta):\n"
        "    def test_in_abcmeta_class_without_abstract_methods(self):\n        assert 2 + 2 == 4\n\n\n"
        "class OtherMeta(type):\n    pass\n\n\n"
        "class TestOtherMetaclass(metaclass=OtherMeta):\n    def test_in_class_with_unknown_metaclass(self):\n"
        "        assert 2 + 2 == 4\n"),
    # names rebound after their def, the call-form fixture rule and an explicit object base (X4)
    f"{PROBE_DIR}/test_rebound.py": (
        "import pytest\n\n\n"
        "def test_rebound_to_none():\n    assert 2 + 2 == 4\n\n\ntest_rebound_to_none = None\n\n\n"
        "def test_deleted_after_def():\n    assert 2 + 2 == 4\n\n\ndel test_deleted_after_def\n\n\n"
        "def test_made_fixture_after_def():\n    return 1\n\n\n"
        "test_made_fixture_after_def = pytest.fixture(test_made_fixture_after_def)\n\n\n"
        "def test_conditionally_rebound():\n    assert 2 + 2 == 4\n\n\nif True:\n    test_conditionally_rebound = 3\n\n\n"
        "def test_defined_twice():\n    assert 2 + 2 == 5\n\n\ndef test_defined_twice():\n    assert 2 + 2 == 4\n\n\n"
        "@pytest.fixture(scope='module')\ndef test_only_as_call_form_fixture():\n    return 1\n\n\n"
        "class TestRebinds:\n    def test_method_rebound_in_class(self):\n        assert 2 + 2 == 4\n\n"
        "    test_method_rebound_in_class = None\n\n    def test_in_class_with_rebinding(self):\n        assert 2 + 2 == 4\n\n\n"
        "class TestObjectBase(object):\n    def test_in_class_with_object_base(self):\n        assert 2 + 2 == 4\n\n\n"
        "class TestRebound:\n    def test_only_in_rebound_class(self):\n        assert 2 + 2 == 4\n\n\n"
        "TestRebound = None\n"),
}
DEBT004_COLLECTED = sorted([
    "test_in_plain_subfolder", "test_in_file_only_the_far_conftest_ignores", "test_in_module_switched_back_on",
    "test_in_class_switched_back_on", "test_in_class_made_concrete", "test_in_abcmeta_class_without_abstract_methods",
    "test_defined_twice", "test_in_class_with_rebinding", "test_in_class_with_object_base"])
DEBT004_NOT_COLLECTED = sorted([
    *[f"test_only_in_skipped_folder_{i}" for i in range(10)], "test_only_in_virtualenv_folder",
    "test_only_in_conda_folder", "test_only_in_ignored_dir", "test_only_in_ignored_file",
    "test_only_in_globbed_file", "test_only_in_file_globbed_by_far_conftest",
    "test_only_in_module_switched_off_by_zero", "test_only_in_module_switched_off_by_none",
    "test_only_in_class_switched_off_by_empty_list", "test_only_in_class_inheriting_switch_off",
    "test_only_in_class_with_computed_switch", "test_only_in_abstract_class",
    "test_only_in_abc_module_abstract_class", "test_only_in_class_still_abstract",
    "test_rebound_to_none", "test_deleted_after_def", "test_made_fixture_after_def", "test_conditionally_rebound",
    "test_only_as_call_form_fixture", "test_method_rebound_in_class", "test_only_in_rebound_class"])
# Collected by pytest but not counted by the gate: a metaclass other than ABCMeta can change what a class holds,
# and the gate cannot read it, so it does not count the class (stricter than pytest; docs/tools/AUDIT_GATE.md).
DEBT004_STRICTER = ["test_in_class_with_unknown_metaclass"]


def pytest_collected(path, target):
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", target],
                          cwd=path, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return sorted(line.rsplit("::", 1)[1] for line in proc.stdout.splitlines() if "::" in line)


@pytest.fixture
def probe_repo(tmp_path):
    repo = FixtureRepo(tmp_path)
    repo.branch()
    for rel, text in DEBT004_PROBE.items():
        repo.write(rel, text)
    return repo


def test_FR_0_0_09_index_follows_pytest_collection_rules(probe_repo):
    # Independent oracle: pytest itself (the pinned version) collects exactly these names from the probe.
    collected = pytest_collected(probe_repo.path, PROBE_DIR)
    assert collected == sorted(DEBT004_COLLECTED + DEBT004_STRICTER)
    assert not set(collected) & set(DEBT004_NOT_COLLECTED)
    names = ", ".join(f"`{n}`" for n in DEBT004_COLLECTED + DEBT004_NOT_COLLECTED + DEBT004_STRICTER)
    probe_repo.append(REG, registry_row("CAP-FIX-002", "`aqis_lab/existing.py`", names))
    found = findings_of(probe_repo.gate_json(), "e")
    assert [(r, n) for r, _, n, _ in found] == [("E3", 6)]
    reported = found[0][3].rsplit(": ", 1)[1].split(", ")
    assert sorted(reported) == sorted(DEBT004_NOT_COLLECTED + DEBT004_STRICTER)


def test_FR_0_0_09_index_counts_every_collected_probe_test(probe_repo):
    names = ", ".join(f"`{n}`" for n in DEBT004_COLLECTED)
    probe_repo.append(REG, registry_row("CAP-FIX-002", "`aqis_lab/existing.py`", names))
    report = probe_repo.gate_json()
    assert findings_of(report, "e") == [] and report["ok"] is True


@pytest.mark.parametrize("conftest, line", [
    ('collect_ignore = ["a"] + ["b"]\n', 1),
    ('collect_ignore = ["a"]\ncollect_ignore.append("b")\n', 1),
    ('import sys\ncollect_ignore_glob = [p for p in sys.argv]\n', 2),
    ('collect_ignore: list\n', 1),
])
def test_FR_0_0_09_non_literal_collect_ignore_is_an_error(tmp_path, conftest, line):
    # The gate cannot tell which files pytest skips when a conftest computes its ignore list: exit 2, never a guess.
    repo = FixtureRepo(tmp_path)
    repo.branch()
    repo.write("tests/lab_support/conftest.py", conftest)
    proc = repo.gate("--base", "origin/main")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith(f"ERROR: tests/lab_support/conftest.py:{line}: cannot tell which files pytest "
                                  "collects: "), proc.stderr
    assert "is not a single literal list of strings" in proc.stderr
