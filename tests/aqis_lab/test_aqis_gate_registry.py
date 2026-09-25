"""FR-0.0-08: registry consistency. Every row names tests and a module that exist; no row present at the
base is missing."""
import json
import subprocess
import sys

import pytest

from aqis_testutil import ROOT
from fixture_repo import REGISTRY_BASE_ROW, REGISTRY_HEAD, FixtureRepo

REG = "docs/capabilities/REGISTRY.md"


def row(cap, module, tests):
    return f"| {cap} | {module} | `f` | does things | {tests} | WP-9.9 FR-9.9-01 | ACTIVE |\n"


def e_findings(report):
    return sorted((f["rule"], f["line"], f["message"]) for f in report["findings"] if f["check"] == "e")


@pytest.fixture
def repo(tmp_path):
    r = FixtureRepo(tmp_path)
    r.branch()
    return r


def test_FR_0_0_08_detects_row_with_missing_test(repo):
    repo.append(REG, row("CAP-FIX-002", "`aqis_lab/existing.py`", "`test_adds`, `test_does_not_exist`"))
    repo.append(REG, row("CAP-FIX-003", "`aqis_lab/existing.py`", ""))
    found = e_findings(repo.gate_json())
    assert [(r, line) for r, line, _ in found] == [("E3", 6), ("E3", 7)]
    assert "test_does_not_exist" in found[0][2] and "CAP-FIX-002" in found[0][2]
    assert "names no tests" in found[1][2]


def test_FR_0_0_08_detects_row_with_missing_module(repo):
    repo.append(REG, row("CAP-FIX-002", "`aqis_lab/missing.py`", "`test_adds`"))
    repo.append(REG, row("CAP-FIX-003", "`aqis_lab.missing_too`", "`test_adds`"))
    repo.append(REG, row("CAP-FIX-004", "`aqis_lab.existing`", "`tests/lab_support/test_adds.py::test_adds`"))
    found = e_findings(repo.gate_json())
    assert [(r, line) for r, line, _ in found] == [("E4", 6), ("E4", 7)]
    assert "aqis_lab/missing.py" in found[0][2] and "aqis_lab.missing_too" in found[1][2]


def test_FR_0_0_08_detects_row_removed_since_base(repo):
    repo.write(REG, REGISTRY_HEAD)
    repo.commit("drop a row")
    found = e_findings(repo.gate_json())
    assert [(r, line) for r, line, _ in found] == [("E5", 5)]
    assert "CAP-FIX-001" in found[0][2]


def test_FR_0_0_08_detects_malformed_row(repo):
    repo.append(REG, "| CAP-FIX-002 | `aqis_lab/existing.py` | only three cells |\n")
    repo.append(REG, REGISTRY_BASE_ROW)  # duplicate ID
    found = e_findings(repo.gate_json())
    assert [(r, line) for r, line, _ in found] == [("E2", 6), ("E2", 7)]
    assert "duplicate" in found[1][2]


def test_FR_0_0_08_detects_missing_registry(repo):
    repo.delete(REG)
    found = e_findings(repo.gate_json())
    # The missing file is reported, and so is every row it held at the base (rows are never deleted).
    assert [r for r, _, _ in found] == ["E1", "E5"]
    assert "CAP-FIX-001" in found[1][2]


def test_FR_0_0_08_passes_consistent_registry(repo):
    repo.write("tests/aqis_lab/test_more.py", "class TestThings:\n    def test_method(self):\n        assert 1 + 1 == 2\n")
    repo.append(REG, row("CAP-FIX-002", "`aqis_lab/existing.py`",
                         "`test_adds`, `tests/aqis_lab/test_more.py::TestThings::test_method`"))
    repo.append(REG, row("CAP-FIX-003", "`aqis_lab`", "`test_method`"))
    report = repo.gate_json()
    assert e_findings(report) == [] and report["ok"] is True


def test_FR_0_0_08_repository_registry_is_consistent():
    proc = subprocess.run([sys.executable, "-B", "-m", "tools.audit.gate", "--base", "HEAD", "--json"], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode in (0, 1), proc.stderr
    report = json.loads(proc.stdout)
    assert [f for f in report["findings"] if f["check"] == "e"] == []
