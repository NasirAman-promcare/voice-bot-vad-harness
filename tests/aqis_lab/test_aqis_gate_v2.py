"""FR-0.0-06 (amended, Amendment 1): the gate follows Stop hook version 2/3 detection rules, fails closed,
decodes non-UTF-8 content with replacement, scans the wider lab scope, and uses no approvals when
origin/main cannot be verified. Also covers audit findings WP-0.0-F04 and WP-0.0-F09."""
import json
import os

import pytest

from aqis_testutil import git
from fixture_repo import FIXTURES, FixtureRepo

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
