"""FR-0.0-09: with --wp, every FR/NFR ID of that WP's spec appears in PLAN.md, a test function name and
EVIDENCE.md; AT/OC IDs appear in PLAN.md and EVIDENCE.md (owner decision 1, WP-0.0 plan)."""
import pytest

from aqis_testutil import git
from fixture_repo import FixtureRepo

SPEC = "docs/specs/phase-9/WP-9.9-thing.md"
SPEC_TEXT = """# WP-9.9 — Thing

## Functional requirements
- **FR-9.9-01** does a.
- **FR-9.9-02** does b; see also FR-0.2-03 from another WP, which is only an example.

## Non-functional requirements
- **NFR-9.9-01** is fast.

## Acceptance commands
- **AT-9.9-01** run it.

## Owner-run checks
- **OC-9.9-01** the owner checks it.
"""
ALL_IDS = ["FR-9.9-01", "FR-9.9-02", "NFR-9.9-01", "AT-9.9-01", "OC-9.9-01"]
LINE_OF = {"FR-9.9-01": 4, "FR-9.9-02": 5, "NFR-9.9-01": 8, "AT-9.9-01": 11, "OC-9.9-01": 14}
TESTS = ("def test_FR_9_9_01_does_a():\n    assert 1 + 1 == 2\n\n\n"
         "def test_FR_9_9_02_does_b():\n    assert 2 + 2 == 4\n\n\n"
         "class TestSpeed:\n    def test_NFR_9_9_01_is_fast(self):\n        assert 3 + 3 == 6\n")


def doc(ids):
    return "# Record\n\n" + "\n".join(f"- {i}: covered" for i in ids) + "\n"


def f_findings(report):
    return sorted((f["rule"], f["path"], f["line"], f["message"]) for f in report["findings"] if f["check"] == "f")


@pytest.fixture
def repo(tmp_path):
    r = FixtureRepo(tmp_path)
    r.write(SPEC, SPEC_TEXT)
    r.commit("spec on main")
    git(r.path, "push", "-q", "origin", "main")
    r.branch()
    r.write("docs/progress/WP-9.9/PLAN.md", doc(ALL_IDS))
    r.write("docs/progress/WP-9.9/EVIDENCE.md", doc(ALL_IDS))
    r.write("tests/aqis_lab/test_thing.py", TESTS)
    return r


def test_FR_0_0_09_passes_complete_traceability(repo):
    report = repo.gate_json("--wp", "WP-9.9")
    assert report["findings"] == [] and report["wp"] == "WP-9.9"


def test_FR_0_0_09_detects_id_missing_from_plan(repo):
    repo.write("docs/progress/WP-9.9/PLAN.md", doc(["FR-9.9-01", "NFR-9.9-01", "AT-9.9-01"]))
    found = f_findings(repo.gate_json("--wp", "WP-9.9"))
    assert [(r, p, n) for r, p, n, _ in found] == [("F2", SPEC, LINE_OF["FR-9.9-02"]), ("F2", SPEC, LINE_OF["OC-9.9-01"])]
    assert "FR-9.9-02" in found[0][3] and "PLAN.md" in found[0][3]
    repo.delete("docs/progress/WP-9.9/PLAN.md")
    found = f_findings(repo.gate_json("--wp", "WP-9.9"))
    assert [(r, p) for r, p, _, _ in found] == [("F2", "docs/progress/WP-9.9/PLAN.md")]


def test_FR_0_0_09_detects_id_missing_from_test_names(repo):
    repo.write("tests/aqis_lab/test_thing.py", TESTS.replace("test_FR_9_9_02_does_b", "test_does_b"))
    found = f_findings(repo.gate_json("--wp", "WP-9.9"))
    assert [(r, n) for r, _, n, _ in found] == [("F3", LINE_OF["FR-9.9-02"])]
    assert "FR_9_9_02" in found[0][3]


def test_FR_0_0_09_detects_nfr_id_missing_from_test_names(repo):
    # Audit F40: NFR IDs, like FR IDs, must appear in a test function name.
    repo.write("tests/aqis_lab/test_thing.py", TESTS.replace("test_NFR_9_9_01_is_fast", "test_is_fast"))
    report = repo.gate_json("--wp", "WP-9.9")
    found = f_findings(report)
    assert report["ok"] is False
    assert [(r, p, n) for r, p, n, _ in found] == [("F3", SPEC, LINE_OF["NFR-9.9-01"])]
    assert "NFR-9.9-01" in found[0][3] and "NFR_9_9_01" in found[0][3]


def test_FR_0_0_09_detects_id_missing_from_evidence(repo):
    repo.write("docs/progress/WP-9.9/EVIDENCE.md", doc(["FR-9.9-01", "FR-9.9-02", "NFR-9.9-01", "OC-9.9-01"]))
    found = f_findings(repo.gate_json("--wp", "WP-9.9"))
    assert [(r, n) for r, _, n, _ in found] == [("F4", LINE_OF["AT-9.9-01"])]
    assert "EVIDENCE.md" in found[0][3]


def test_FR_0_0_09_underscore_matching_respects_boundaries(repo):
    # NFR_9_9_01 must not satisfy FR-9.9-01, FR_9_9_011 must not satisfy FR-9.9-01, and fixture
    # functions under tests/aqis_lab/fixtures/ never count.
    tests = ("def test_NFR_9_9_01_is_fast():\n    assert 3 + 3 == 6\n\n\n"
             "def test_FR_9_9_011_other():\n    assert 4 + 4 == 8\n\n\n"
             "def test_FR_9_9_02_does_b():\n    assert 2 + 2 == 4\n")
    repo.write("tests/aqis_lab/test_thing.py", tests)
    repo.write("tests/aqis_lab/fixtures/trace/test_fixture_only.py", "def test_FR_9_9_01_in_fixture():\n    pass\n")
    repo.write("docs/progress/WP-9.9/EVIDENCE.md", doc(["NFR-9.9-01", "FR-9.9-02", "AT-9.9-01", "OC-9.9-01"]) + "FR-9.9-011\n")
    found = f_findings(repo.gate_json("--wp", "WP-9.9"))
    assert [(r, n) for r, _, n, _ in found] == [("F3", LINE_OF["FR-9.9-01"]), ("F4", LINE_OF["FR-9.9-01"])]


def test_FR_0_0_09_ignores_other_wp_ids_in_spec(repo):
    report = repo.gate_json("--wp", "WP-9.9")
    assert not any("0.2-03" in f["message"] or "0_2_03" in f["message"] for f in report["findings"])
    assert report["findings"] == []


def test_FR_0_0_09_reports_unknown_wp(repo):
    found = f_findings(repo.gate_json("--wp", "WP-8.8"))
    assert [r for r, _, _, _ in found] == ["F1"]
    assert "WP-8.8" in found[0][3]
    # F1 cites the searched spec glob at line 1 (audit F09 fix, test added for audit F19)
    assert (found[0][1], found[0][2]) == ("docs/specs/**/WP-8.8-*.md", 1)
    bad = repo.gate("--base", "origin/main", "--wp", "banana", json_output=False)
    assert bad.returncode == 2 and bad.stderr.startswith("ERROR:")
