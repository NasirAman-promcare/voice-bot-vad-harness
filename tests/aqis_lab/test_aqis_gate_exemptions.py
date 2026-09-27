"""FR-0.0-07: an audit-allow comment with a reason exempts one line only; an audit-allow comment
without a reason exempts nothing; ALLOW-PATTERNS-IN exempts whole files; the gate lists both."""
import json

import pytest

from fixture_repo import FIXTURES, FixtureRepo

EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


@pytest.fixture
def repo(tmp_path):
    return FixtureRepo(tmp_path)


def test_FR_0_0_07_audit_allow_with_reason_exempts_and_is_listed(repo):
    repo.branch()
    repo.copy_fixture("allow_lines.py", "tools/allowed.py")
    report = repo.gate_json()
    assert report["exempted_lines"] == [
        {"path": "tools/allowed.py", "line": int(n), "reason": reason}
        for n, reason in EXPECTED["allow_lines.py exempted"].items()
    ]
    assert 2 not in {f["line"] for f in report["findings"]}
    text = repo.gate("--base", "origin/main", json_output=False).stdout
    assert "Exempted lines (# audit-allow): 1" in text
    assert "  tools/allowed.py:2: fixture shows an exempted line with a reason" in text


def test_FR_0_0_07_audit_allow_without_reason_does_not_exempt(repo):
    repo.branch()
    repo.copy_fixture("allow_lines.py", "tools/allowed.py")
    report = repo.gate_json()
    assert {str(f["line"]): f["label"] for f in report["findings"]} == EXPECTED["allow_lines.py"]
    assert "3" in EXPECTED["allow_lines.py"]  # line 3 carries an audit-allow comment with no reason and is still flagged


def test_FR_0_0_07_audit_allow_exempts_only_its_line(repo):
    repo.branch()
    repo.copy_fixture("allow_lines.py", "tools/allowed.py")
    report = repo.gate_json()
    # line 2 is exempted; the identical content on line 4 is still reported
    assert [f["line"] for f in report["findings"] if f["line"] == 4] == [4]
    assert [e["line"] for e in report["exempted_lines"]] == [2]


def test_FR_0_0_07_allow_patterns_in_exempts_file_and_is_listed(repo):
    repo.approve_on_main("WP-9.9.md", "ALLOW-PATTERNS-IN: tools/pattern_table.py\n")
    repo.branch()
    repo.copy_fixture("code_patterns.py", "tools/pattern_table.py")
    repo.copy_fixture("code_patterns.py", "tools/not_exempt.py")
    report = repo.gate_json()
    assert report["exempted_files"] == [{"path": "tools/pattern_table.py", "approval": "WP-9.9.md",
                                         "glob": "tools/pattern_table.py"}]
    assert {f["path"] for f in report["findings"]} == {"tools/not_exempt.py"}
    text = repo.gate("--base", "origin/main", json_output=False).stdout
    assert "  tools/pattern_table.py: tools/pattern_table.py (WP-9.9.md)" in text
