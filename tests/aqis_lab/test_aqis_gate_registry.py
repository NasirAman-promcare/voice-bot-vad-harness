"""FR-0.0-08: registry consistency. Every row names tests and a module that exist; no row present at the
base is missing."""
import json
import re
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


def _registry_rows():
    rows = {}
    for line in (ROOT / REG).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[0].startswith("CAP-"):
            tests = {t.strip().strip("`").split("::")[-1] for t in cells[4].split(",") if t.strip().strip("`")}
            rows[cells[0]] = (cells[1].strip("`"), tests)
    return rows


def _header_entries(path):
    """{CAP-ID: set(test names)} from a module header (Python docstring or shell comment block)."""
    text = "\n".join(line.lstrip("#").rstrip() for line in path.read_text(encoding="utf-8").splitlines()[:80])
    entries = {}
    for m in re.finditer(r"^\s*(CAP-[A-Z0-9-]+):.*?\[tests:\s*(.*?)\]", text, re.M | re.S):
        entries[m.group(1)] = {t.strip() for t in re.split(r"[,\s]+", m.group(2)) if t.strip()}
    return entries


def test_FR_0_0_08_module_headers_match_registry():
    # WP-0.0-F06: every lab module named in the registry states the same tests in its header as its row.
    rows = _registry_rows()
    checked = 0
    for cap, (module, tests) in sorted(rows.items()):
        path = ROOT / module
        if not (module.startswith(("aqis_lab/", "tools/")) and path.suffix in (".py", ".sh")):
            continue
        entries = _header_entries(path)
        assert cap in entries, f"{module} header does not list {cap}"
        assert entries[cap] == tests, f"{cap}: header {sorted(entries[cap])} != registry {sorted(tests)}"
        checked += 1
    assert checked >= 10
    for package in ("aqis_lab/commands/__init__.py", "tools/__init__.py", "tools/audit/__init__.py"):
        doc = (ROOT / package).read_text(encoding="utf-8")
        for field in ("CAPABILITIES:", "INPUTS AND OUTPUTS:", "CONTRACTS:", "INVARIANTS:", "NOT IN SCOPE:", "CHANGE LOG:"):
            assert field in doc, f"{package} header lacks {field}"
