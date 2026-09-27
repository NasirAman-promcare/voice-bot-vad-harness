"""FR-0.0-06 (amended, Amendment 1): the gate follows Stop hook version 2/3 detection rules, fails closed,
decodes non-UTF-8 content with replacement, scans the wider lab scope, and uses no approvals when
origin/main cannot be verified. Also covers audit findings WP-0.0-F04 and WP-0.0-F09."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import pytest

from aqis_testutil import ROOT, git, hermetic_git_env
from fixture_repo import FIXTURES, REGISTRY_HEAD, FixtureRepo

REG = "docs/capabilities/REGISTRY.md"

EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

V2_TARGETS = {
    "shell_patterns.sh": "aqis_lab/deploy/fixture.sh",
    "lab_ci.yml": ".github/workflows/aqis-lab-fixture.yml",
    "requirements.in": "requirements/aqis_lab/fixture.in",
    "config.toml": "config/aqis_lab/fixture.toml",
}


@pytest.fixture
def repo(tmp_path):
    return FixtureRepo(tmp_path)


def labels_by_line(report, path):
    return {str(f["line"]): f["label"] for f in report["findings"] if f["path"] == path}


def test_FR_0_0_06_scans_v2_file_types_and_dirs(repo):
    repo.branch()
    for fixture, target in V2_TARGETS.items():
        repo.copy_fixture(fixture, target)
    repo.copy_fixture("shell_patterns.sh", "tests/aqis_lab/helper.sh")      # not scanned: tests take .py only
    repo.copy_fixture("config.toml", "config/other.toml")                     # guarded, outside the lab scope
    report = repo.gate_json()
    for fixture, target in V2_TARGETS.items():
        assert labels_by_line(report, target) == EXPECTED[fixture], target
        assert all(f["rule"] == "C1" for f in report["findings"] if f["path"] == target)
    assert labels_by_line(report, "tests/aqis_lab/helper.sh") == {}
    assert [f["rule"] for f in report["findings"] if f["path"] == "config/other.toml"] == ["A2"]


def test_FR_0_0_06_flags_pytestmark_and_param_skips(repo):
    repo.branch()
    repo.copy_fixture("test_pytestmark.py", "tests/aqis_lab/test_marked.py")
    report = repo.gate_json()
    assert labels_by_line(report, "tests/aqis_lab/test_marked.py") == EXPECTED["test_pytestmark.py"]
    assert {f["rule"] for f in report["findings"]} == {"C2"}


def test_FR_0_0_06_decodes_non_utf8_with_replacement(repo):
    repo.branch()
    repo.copy_fixture("non_utf8.py", "tools/non_utf8.py")
    proc = repo.gate("--base", "origin/main")
    assert proc.returncode == 1, proc.stderr
    assert "Traceback" not in proc.stderr
    report = json.loads(proc.stdout)
    assert labels_by_line(report, "tools/non_utf8.py") == EXPECTED["non_utf8.py"]
    assert "�" in report["findings"][0]["text"]
    # a modified tracked file with a non-UTF-8 byte goes through the git-diff path
    with open(repo.path / "tools/existing_tool.py", "ab") as handle:
        handle.write(b"# XXX caf\xe9\n")
    report = repo.gate_json()
    assert labels_by_line(report, "tools/existing_tool.py") == {"3": "TODO/FIXME/XXX marker"}


def test_FR_0_0_06_fails_closed_on_unreadable_changed_file(repo):
    repo.branch()
    os.symlink("does-not-exist.py", repo.path / "aqis_lab" / "dangling.py")
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2
    assert proc.stderr.startswith("ERROR:") and "aqis_lab/dangling.py" in proc.stderr
    assert "0 findings" not in proc.stdout


@pytest.mark.parametrize("how", ["missing", "directory"])
def test_FR_0_0_06_fails_closed_when_protected_paths_unreadable(repo, how):
    repo.branch()
    policy = repo.path / "docs" / "process" / "PROTECTED_PATHS.txt"
    policy.unlink()
    if how == "directory":
        policy.mkdir()
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2
    assert proc.stderr.startswith("ERROR:") and "PROTECTED_PATHS.txt" in proc.stderr


def test_FR_0_0_06_fails_closed_on_git_error(repo):
    repo.branch()
    git(repo.path, "config", "diff.external", str(repo.path / "no-such-diff-tool"))
    repo.append("tools/existing_tool.py", "\nEXTRA = 1\n")
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2
    assert proc.stderr.startswith("ERROR:") and "tools/existing_tool.py" in proc.stderr
    # the Stop hook fails closed on the same repository too
    assert any(line.startswith("GATE ERROR:") and "tools/existing_tool.py" in line for line in repo.hook_lines())


def test_FR_0_0_06_approvals_none_when_origin_main_unverifiable(repo):
    repo.approve_on_main("WP-9.9.md", "ALLOW-EDIT: vad_adapters/example.py\n")
    repo.branch()
    repo.append("vad_adapters/example.py", "\nY = 2\n")
    assert repo.gate_json()["findings"] == []                      # approval honoured while verifiable
    git(repo.path, "remote", "set-url", "origin", str(repo.path.parent / "gone.git"))
    git(repo.path, "update-ref", "-d", "refs/remotes/origin/main")
    proc = repo.gate("--base", "main")
    assert proc.returncode == 1, proc.stderr
    report = json.loads(proc.stdout)
    assert report["approvals_commit"] is None
    assert [(f["rule"], f["path"]) for f in report["findings"]] == [("A2", "vad_adapters/example.py")]
    text = repo.gate("--base", "main", json_output=False).stdout
    assert "approvals: none (origin/main not verifiable)" in text


def test_FR_0_0_06_fails_closed_when_branch_diff_fails(repo):
    # Must-catch 7 (round 8 proof, break MC7.19): if `git diff --name-status <base> HEAD` fails, the gate exits 2
    # and never reports a clean or partial result. The base commit's root tree object is removed, so git cannot
    # read the base side of the diff; HEAD and its index stay readable.
    repo.branch()
    repo.append("tools/existing_tool.py", "\nEXTRA = 1\n")
    repo.commit("branch change")
    tree = git(repo.path, "rev-parse", "origin/main^{tree}").strip()
    (repo.path / ".git" / "objects" / tree[:2] / tree[2:]).unlink()
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith("ERROR:") and "git diff against" in proc.stderr
    assert "0 findings" not in proc.stdout


def test_FR_0_0_06_fails_closed_when_git_status_fails(repo):
    # Must-catch 7, sibling case: a corrupt index makes `git status` fail; the gate exits 2, never a clean pass.
    repo.branch()
    repo.append("tools/existing_tool.py", "\nEXTRA = 1\n")
    repo.commit("branch change")
    (repo.path / ".git" / "index").write_bytes(b"DIRC not a valid index")
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith("ERROR:") and "git status failed" in proc.stderr
    assert "0 findings" not in proc.stdout


def test_FR_0_0_06_fails_closed_on_changed_file_it_cannot_read(tmp_path):
    # Audit F57 (K7.4, must-catch 7): a changed regular file that the gate's user cannot read gives exit 2,
    # never a clean pass. Root reads any file, so as root the gate runs as an unprivileged user (setpriv), the
    # same way the non-root provisioning test does; when the test is not root it runs the gate directly. The
    # control run, made the same way while the file is readable, proves that this user can run the gate here.
    as_root = os.geteuid() == 0
    setpriv = shutil.which("setpriv")
    if as_root:
        assert setpriv, "setpriv (util-linux) is needed to run the gate as an unprivileged user"
    base = Path(tempfile.mkdtemp(prefix="aqis-unreadable-")) if as_root else tmp_path
    try:
        repo = FixtureRepo(base)
        repo.branch()
        repo.write("tools/unreadable_tool.py", "# TODO: the gate must not pass this file unread\n")
        target = repo.path / "tools" / "unreadable_tool.py"
        prefix = []
        if as_root:
            nobody = 65534
            for path in [base, *base.rglob("*")]:
                os.lchown(path, nobody, nobody)
            prefix = [setpriv, f"--reuid={nobody}", f"--regid={nobody}", "--clear-groups"]
        env = hermetic_git_env({"PYTHONPATH": str(ROOT), "HOME": str(base)})

        def run_gate(*extra):
            return subprocess.run([*prefix, sys.executable, "-B", "-m", "tools.audit.gate", "--base", "origin/main",
                                   *extra], cwd=repo.path, capture_output=True, text=True, env=env, timeout=300)

        control = run_gate("--json")
        assert control.returncode == 1, control.stdout + control.stderr
        found = [(f["rule"], f["path"]) for f in json.loads(control.stdout)["findings"]]
        assert found == [("C1", "tools/unreadable_tool.py")]
        target.chmod(0)
        proc = run_gate()
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert proc.stderr.startswith("ERROR: tools/unreadable_tool.py:1: cannot read changed file:"), proc.stderr
        assert "0 findings" not in proc.stdout
    finally:
        if as_root:
            shutil.rmtree(base)


def test_FR_0_0_06_fails_closed_when_base_registry_unreadable(repo):
    # Audit F57 (K7.9, must-catch 7): the registry at the base exists (`git cat-file -e` succeeds) but cannot be
    # read. The gate exits 2 instead of skipping the removed-row check (E5). The base registry's loose object keeps
    # its header and loses half its content, and its compressed stream is never finished.
    repo.branch()
    repo.write(REG, REGISTRY_HEAD)
    repo.commit("drop registry row CAP-FIX-001")
    control = repo.gate_json()
    assert [f["rule"] for f in control["findings"]] == ["E5"]
    blob = git(repo.path, "rev-parse", f"origin/main:{REG}").strip()
    obj = repo.path / ".git" / "objects" / blob[:2] / blob[2:]
    raw = zlib.decompress(obj.read_bytes())
    header, content = raw.split(b"\0", 1)
    obj.chmod(0o644)
    stream = zlib.compressobj()
    obj.write_bytes(stream.compress(header + b"\0") + stream.flush(zlib.Z_SYNC_FLUSH)
                    + stream.compress(content[:len(content) // 2]) + stream.flush(zlib.Z_SYNC_FLUSH))  # never finished
    exists = subprocess.run(["git", "cat-file", "-e", f"origin/main:{REG}"], cwd=repo.path, env=hermetic_git_env(),
                            capture_output=True, text=True, timeout=60)
    shown = subprocess.run(["git", "show", f"origin/main:{REG}"], cwd=repo.path, env=hermetic_git_env(),
                           capture_output=True, text=True, timeout=60)
    assert exists.returncode == 0 and shown.returncode != 0, (exists.stderr, shown.stderr)
    proc = repo.gate("--base", "origin/main", json_output=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith(f"ERROR: {REG}:1: cannot read the registry at base"), proc.stderr
    assert "0 findings" not in proc.stdout


def test_FR_0_0_06_fails_closed_when_spec_unreadable(repo):
    # Audit F57 (K7.11, must-catch 7): the one path matching docs/specs/**/<WP>-*.md cannot be read (here it is a
    # folder). Traceability exits 2 instead of ending with no findings.
    repo.branch()
    (repo.path / "docs" / "specs" / "phase-9" / "WP-9.9-thing.md").mkdir(parents=True)
    proc = repo.gate("--base", "origin/main", "--wp", "WP-9.9", json_output=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith("ERROR: docs/specs/phase-9/WP-9.9-thing.md:1: cannot read the spec"), proc.stderr
    assert "0 findings" not in proc.stdout
