"""Unit tests for path normalisation and classification.

CAPABILITIES:
  CAP-OUTSOURCING-002: normalise and classify repository-relative paths [tests: test_FR_1_0_01_normalise_valid_paths, test_FR_1_0_01_normalise_invalid_paths, test_FR_1_0_01_classify_sections]
INPUTS AND OUTPUTS: pytest tests.
CONTRACTS: none.
INVARIANTS:
  - All tests pass cleanly.
NOT IN SCOPE:
  - Acceptance tests (see test_acceptance_wo_1_0_01.py).
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import pytest
from tools.outsourcing.paths import classify, normalise


def test_FR_1_0_01_normalise_valid_paths():
    assert normalise("tools/demo/alpha.py") == "tools/demo/alpha.py"
    assert normalise("./tools/demo/alpha.py") == "tools/demo/alpha.py"
    assert normalise("tools/demo/alpha.py/") == "tools/demo/alpha.py"
    assert normalise("   tools/demo/alpha.py   ") == "tools/demo/alpha.py"


@pytest.mark.parametrize("bad_path", [
    "",
    "   ",
    "/absolute/path.py",
    "C:\\windows\\path.py",
    "tools\\demo\\alpha.py",
    "../outside.py",
    "tools/../outside.py",
    "./",
])
def test_FR_1_0_01_normalise_invalid_paths(bad_path: str):
    with pytest.raises(ValueError):
        normalise(bad_path)


def test_FR_1_0_01_classify_sections(tmp_path):
    root = tmp_path / "repo"
    policy_dir = root / "docs" / "process"
    policy_dir.mkdir(parents=True)
    policy_file = policy_dir / "PROTECTED_PATHS.txt"
    policy_file.write_text(
        "[NEVER]\nCLAUDE.md\n.claude/**\n\n"
        "[GUARDED]\nbots/**\nREADME.md\n\n"
        "[LAB-OWNED]\ntests/aqis_lab/**\n",
        encoding="utf-8"
    )

    assert classify("CLAUDE.md", root) == "NEVER"
    assert classify(".claude/settings.json", root) == "NEVER"
    assert classify("bots/bot.py", root) == "GUARDED"
    assert classify("README.md", root) == "GUARDED"
    assert classify("tests/aqis_lab/test_foo.py", root) == "LAB-OWNED"
    assert classify("tools/outsourcing/paths.py", root) == "FREE"
