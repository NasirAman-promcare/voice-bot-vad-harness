"""Claude's DEC-1.0-10 (FR-1.0-03, WO-1.0-03 B11 clarification), written first.

`impact --base REF` selected the test files that import an affected module, but not a changed or new test file itself
(probe on 2026-10-12: a branch that only edits `tests/aqis_lab/test_gamma.py` selected nothing). The stop gate runs
the tests impact selects, so a change to a test alone would run no test.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tools.index.impact import affected_tests

TEST_GAMMA = '"""T."""\nfrom aqis_lab.gamma import g\n\n\ndef test_FR_9_3_01():\n    assert g() == 3\n'


def git(root: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="f", GIT_AUTHOR_EMAIL="f@x.invalid",
               GIT_COMMITTER_NAME="f", GIT_COMMITTER_EMAIL="f@x.invalid")
    subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=root, check=True, capture_output=True, env=env)


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    write(root, "aqis_lab/__init__.py", '"""Lab."""\n')
    write(root, "aqis_lab/gamma.py", '"""Gamma."""\n\n\ndef g() -> int:\n    return 3\n')
    write(root, "tests/aqis_lab/test_gamma.py", TEST_GAMMA)
    write(root, "tests/aqis_lab/test_other.py", '"""O."""\n\n\ndef test_FR_9_9_01():\n    assert True\n')
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    git(root, "checkout", "-qb", "work")
    return root


def test_FR_1_0_03_a_changed_test_file_selects_itself(tmp_path):
    root = repo(tmp_path)
    write(root, "tests/aqis_lab/test_gamma.py", TEST_GAMMA + "\n\ndef test_FR_9_3_02():\n    assert g() > 0\n")
    git(root, "commit", "-qam", "change a test only")
    result = affected_tests(root, "main")
    assert not result.all and result.lines == ("tests/aqis_lab/test_gamma.py",)


def test_FR_1_0_03_a_new_untracked_test_file_selects_itself(tmp_path):
    root = repo(tmp_path)
    write(root, "tests/aqis_lab/test_new.py", '"""N."""\n\n\ndef test_FR_9_4_01():\n    assert True\n')
    result = affected_tests(root, "main")
    assert not result.all and result.lines == ("tests/aqis_lab/test_new.py",)
