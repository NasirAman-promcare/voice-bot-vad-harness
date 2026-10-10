"""Acceptance tests for WO-1.0-06 (FR-1.0-06): break suite runner and mutation report.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus positive controls. Modules are imported
inside the tests and the command lines run as subprocesses, so a missing module fails each test on its own.

Each test builds a scratch git repository with a tiny `aqis_lab` package, its tests and recipes made with `git diff`
against the committed code. The commands run with `python -P` and `PYTHONPATH` set to this repository, and with
`TMPDIR` set to a folder of the test's own, so leftover worktrees or scratch folders are visible.
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

CALC = (
    '"""Scratch calculator."""\n'
    "\n"
    "\n"
    "def add(a: int, b: int) -> int:\n"
    "    return a + b\n"
    "\n"
    "\n"
    "def is_positive(value: int) -> bool:\n"
    "    if value > 0:\n"
    "        return True\n"
    "    return False\n"
)
LONELY = '"""Scratch module with no tests."""\n\n\ndef lonely(value: int) -> int:\n    return value - 1\n'
TEST_CALC = (
    '"""Scratch tests for the calculator."""\n'
    "from aqis_lab.calc import add, is_positive\n"
    "\n"
    "\n"
    "def test_add():\n"
    "    assert add(2, 3) == 5\n"
    "\n"
    "\n"
    "def test_positive():\n"
    "    assert is_positive(4) is True\n"
    "\n"
    "\n"
    "def test_unrelated():\n"
    "    assert len('abc') == 3\n"
)
FILES = {
    "aqis_lab/__init__.py": '"""Scratch lab package."""\n',
    "aqis_lab/calc.py": CALC,
    "aqis_lab/lonely.py": LONELY,
    "tests/aqis_lab/test_calc.py": TEST_CALC,
}
NODE = "tests/aqis_lab/test_calc.py::"


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "AQIS Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "AQIS Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, check=True,
                          capture_output=True, text=True, env=env, timeout=120).stdout


def write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")


def commit(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)


def recipe(repo: Path, wp: str, name: str, rel: str, old: str, new: str, expect: list[str],
           mc: str = "1", behaviour: str = "scratch behaviour", headers: list[str] | None = None) -> Path:
    """Write a recipe made with `git diff` against the committed file, then restore the file."""
    original = (repo / rel).read_text(encoding="utf-8")
    assert original.count(old) == 1, (rel, old)
    (repo / rel).write_text(original.replace(old, new), encoding="utf-8")
    diff = git(repo, "diff", "--", rel)
    (repo / rel).write_text(original, encoding="utf-8")
    lines = headers if headers is not None else (
        [f"# MC: {mc}", f"# behaviour: {behaviour}"] + [f"# expect-fail: {node}" for node in expect])
    path = repo / "tests/aqis_lab/breaks" / wp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" + diff, encoding="utf-8")
    return path


@pytest.fixture
def scratch(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    for rel, text in FILES.items():
        write(repo, rel, text)
    git(repo, "init", "-q")
    commit(repo, "base")
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    return {"repo": repo, "tmp": tmp}


def run_module(scratch: dict, module: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT), TMPDIR=str(scratch["tmp"]))
    return subprocess.run([sys.executable, "-P", "-m", module, *args], cwd=scratch["repo"], capture_output=True,
                          text=True, env=env, timeout=900)


def breaks(scratch: dict, *args: str) -> subprocess.CompletedProcess:
    return run_module(scratch, "tools.audit.breaks", *args)


def assert_clean(scratch: dict) -> None:
    repo = scratch["repo"]
    assert git(repo, "status", "--porcelain") == "", "the real working tree is never changed"
    worktrees = [line for line in git(repo, "worktree", "list", "--porcelain").splitlines()
                 if line.startswith("worktree ")]
    assert worktrees == [f"worktree {repo}"], worktrees
    assert list(scratch["tmp"].iterdir()) == [], f"left behind: {sorted(p.name for p in scratch['tmp'].iterdir())}"


def results_by_name(scratch: dict, wp: str) -> dict[str, str]:
    breaks_mod = importlib.import_module("tools.audit.breaks")
    old_tmp = os.environ.get("TMPDIR")
    os.environ["TMPDIR"] = str(scratch["tmp"])
    import tempfile
    tempfile.tempdir = None
    try:
        recipes = breaks_mod.load_recipes(scratch["repo"], wp)
        return {Path(str(r.path)).name: breaks_mod.run_recipe(r, scratch["repo"]).status for r in recipes}
    finally:
        if old_tmp is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = old_tmp
        tempfile.tempdir = None


# --------------------------------------------------------------------------------------------- positive control
def test_FR_1_0_06_recipe_is_caught_when_every_named_test_fails(scratch: dict) -> None:
    recipe(scratch["repo"], "WP-9.1", "MC-01-add.patch", "aqis_lab/calc.py", "return a + b", "return a - b",
           [NODE + "test_add"])
    commit(scratch["repo"], "recipe")
    proc = breaks(scratch, "--wp", "WP-9.1")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "MC-01-add.patch" in out and "caught" in out
    assert len(proc.stdout.splitlines()) <= 30
    assert_clean(scratch)
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-add.patch": "caught"}
    assert_clean(scratch)


# --------------------------------------------------------------------------------------------- must-catch 1
def test_FR_1_0_06_mc1_recipe_that_no_longer_applies_is_broken(scratch: dict) -> None:
    repo = scratch["repo"]
    recipe(repo, "WP-9.1", "MC-01-add.patch", "aqis_lab/calc.py", "return a + b", "return a - b",
           [NODE + "test_add"])
    write(repo, "aqis_lab/calc.py", CALC.replace("return a + b", "return b + a"))
    commit(repo, "recipe, then the code moved on")
    proc = breaks(scratch, "--wp", "WP-9.1")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert "broken" in out and "caught" not in out
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-add.patch": "broken"}
    assert_clean(scratch)


# --------------------------------------------------------------------------------------------- must-catch 2, 4
def test_FR_1_0_06_mc2_surviving_recipe_exits_1(scratch: dict) -> None:
    recipe(scratch["repo"], "WP-9.1", "MC-01-positive.patch", "aqis_lab/calc.py", "if value > 0:",
           "if value >= 0:", [NODE + "test_positive"])
    recipe(scratch["repo"], "WP-9.1", "MC-02-add.patch", "aqis_lab/calc.py", "return a + b", "return a - b",
           [NODE + "test_add"])
    commit(scratch["repo"], "recipes")
    proc = breaks(scratch, "--wp", "WP-9.1")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-positive.patch": "survived", "MC-02-add.patch": "caught"}
    assert_clean(scratch)


def test_FR_1_0_06_mc4_only_the_named_tests_count(scratch: dict) -> None:
    # The break makes test_add fail, but the recipe names test_positive (which still passes) and test_add.
    recipe(scratch["repo"], "WP-9.1", "MC-01-other-test-fails.patch", "aqis_lab/calc.py", "return a + b",
           "return a - b", [NODE + "test_positive"])
    recipe(scratch["repo"], "WP-9.1", "MC-02-one-of-two.patch", "aqis_lab/calc.py", "return a + b",
           "return a - b", [NODE + "test_add", NODE + "test_unrelated"])
    commit(scratch["repo"], "recipes")
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-other-test-fails.patch": "survived",
                                                  "MC-02-one-of-two.patch": "survived"}
    assert breaks(scratch, "--wp", "WP-9.1").returncode == 1
    assert_clean(scratch)


# --------------------------------------------------------------------------------------------- must-catch 3, B4
def test_FR_1_0_06_mc3_worktrees_are_removed_when_the_test_run_crashes(scratch: dict) -> None:
    recipe(scratch["repo"], "WP-9.1", "MC-01-crash.patch", "aqis_lab/calc.py", "    return a + b\n",
           "    import os\n    os._exit(70)\n", [NODE + "test_add"])
    commit(scratch["repo"], "recipe")
    proc = breaks(scratch, "--wp", "WP-9.1")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-crash.patch": "broken"}, \
        "a named test with no reported outcome is broken, never caught (B8)"
    assert_clean(scratch)


# --------------------------------------------------------------------------------------------- B1, E1, E2, E4
@pytest.mark.parametrize("case", ["no-expect-fail", "missing-node", "test-file-change"])
def test_FR_1_0_06_invalid_recipes_are_broken(scratch: dict, case: str) -> None:
    repo = scratch["repo"]
    if case == "no-expect-fail":
        recipe(repo, "WP-9.1", "MC-01-x.patch", "aqis_lab/calc.py", "return a + b", "return a - b", [],
               headers=["# MC: 1", "# behaviour: scratch"])
    elif case == "missing-node":
        recipe(repo, "WP-9.1", "MC-01-x.patch", "aqis_lab/calc.py", "return a + b", "return a - b",
               [NODE + "test_does_not_exist"])
    else:
        recipe(repo, "WP-9.1", "MC-01-x.patch", "tests/aqis_lab/test_calc.py", "assert add(2, 3) == 5",
               "assert add(2, 3) == 6", [NODE + "test_add"])
    commit(repo, "recipe")
    proc = breaks(scratch, "--wp", "WP-9.1")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert results_by_name(scratch, "WP-9.1") == {"MC-01-x.patch": "broken"}
    assert_clean(scratch)


def test_FR_1_0_06_no_recipes_for_the_wp_exits_2(scratch: dict) -> None:
    proc = breaks(scratch, "--wp", "WP-9.4")
    assert proc.returncode == 2 and "no recipes" in (proc.stdout + proc.stderr).lower()


def test_FR_1_0_06_all_groups_by_wp_and_recipe_names_are_free_after_mc(scratch: dict) -> None:
    recipe(scratch["repo"], "WP-9.1", "MC-01-add.patch", "aqis_lab/calc.py", "return a + b", "return a - b",
           [NODE + "test_add"])
    recipe(scratch["repo"], "WP-9.2", "MC-WO-9.2-01-03-positive.patch", "aqis_lab/calc.py", "return True",
           "return False", [NODE + "test_positive"], mc="WO-9.2-01 #3")
    commit(scratch["repo"], "recipes")
    proc = breaks(scratch, "--all")
    out = proc.stdout
    assert proc.returncode == 0, out + proc.stderr
    lines = out.splitlines()
    for name, wp in (("MC-01-add.patch", "WP-9.1"), ("MC-WO-9.2-01-03-positive.patch", "WP-9.2")):
        at = next(n for n, line in enumerate(lines) if name in line)
        group = next(line for line in reversed(lines[:at + 1]) if "WP-9." in line)
        assert wp in group, (name, group)
    assert out.index("MC-01-add.patch") < out.index("MC-WO-9.2-01-03-positive.patch"), "grouped by WP, in order"
    assert_clean(scratch)


# --------------------------------------------------------------------------------------------- must-catch 5, B6
MUTABLE = (
    "def f(a, b, items):\n"
    "    if a < b and b > 0:\n"
    "        return a == b\n"
    "    while a != 3 or not items:\n"
    "        a = a + 2\n"
    "    if a <= 1:\n"
    "        raise ValueError('small')\n"
    "    return a >= b\n"
)
OPERATORS = {"comparison", "boolean", "negate-condition", "constant", "return-none", "raise-pass"}


def test_FR_1_0_06_mc5_mutant_set_is_identical_for_the_same_seed_and_limit() -> None:
    script = ("import json, sys; from tools.audit.mutate import mutants; "
              "src = sys.stdin.read(); "
              "print(json.dumps([[m.operator, m.line, m.description, m.source] for m in mutants(src, 7, 6)]))")
    runs = [subprocess.run([sys.executable, "-P", "-c", script], input=MUTABLE, capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONHASHSEED=seed), timeout=120)
            for seed in ("1", "2", "3")]
    assert all(r.returncode == 0 for r in runs), [r.stderr for r in runs]
    assert runs[0].stdout == runs[1].stdout == runs[2].stdout
    mutate = importlib.import_module("tools.audit.mutate")
    assert len(mutate.mutants(MUTABLE, 7, 6)) == 6


def test_FR_1_0_06_mutants_are_single_compiling_changes_of_every_operator() -> None:
    mutate = importlib.import_module("tools.audit.mutate")
    every = mutate.mutants(MUTABLE, 1, 1000)
    assert {m.operator for m in every} == OPERATORS
    original = MUTABLE.splitlines()
    for m in every:
        compile(m.source, "<mutant>", "exec")
        changed = [n for n, (a, b) in enumerate(zip(original, m.source.splitlines()), start=1) if a != b]
        assert changed == [m.line], (m.operator, m.line, changed)
    lines = {(m.operator, m.source.splitlines()[m.line - 1].strip()) for m in every}
    assert ("comparison", "if a >= b and b > 0:") in lines
    assert ("boolean", "if a < b or b > 0:") in lines
    assert ("return-none", "return None") in lines
    assert ("raise-pass", "pass") in lines
    assert ("constant", "a = a + 3") in lines and ("constant", "a = a + 1") in lines
    assert any(op == "negate-condition" and text.startswith("while not") for op, text in lines)
    assert len({m.source for m in every}) == len(every), "no duplicate mutants"


# --------------------------------------------------------------------------------------------- must-catch 6, B7, E3
def test_FR_1_0_06_mc6_mutation_report_leaves_the_working_tree_unchanged(scratch: dict) -> None:
    repo = scratch["repo"]
    git(repo, "checkout", "-qb", "work")
    write(repo, "aqis_lab/calc.py", CALC + "\n\ndef double(value: int) -> int:\n    return value * 2\n")
    write(repo, "aqis_lab/lonely.py", LONELY + "\n\nLIMIT = 3\n")
    commit(repo, "change")
    head = git(repo, "rev-parse", "HEAD")
    before = {rel: (repo / rel).read_bytes() for rel in FILES}
    out = scratch["tmp"].parent / "report.md"
    proc = run_module(scratch, "tools.audit.mutation_report", "--base", "main", "--max-mutants", "20", "--seed", "1",
                      "--out", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert git(repo, "rev-parse", "HEAD") == head
    assert {rel: (repo / rel).read_bytes() for rel in FILES} == before
    assert_clean(scratch)

    report = out.read_text(encoding="utf-8")
    calc = report[report.index("aqis_lab/calc.py"):]
    assert re.search(r"killed\D*[1-9]", calc, re.I), report
    assert re.search(r"surviv\w*\D*[1-9]", calc, re.I), report
    assert re.search(r"aqis_lab/calc\.py:(9|11|15)\b", report), "survivors are listed with path:line"
    lonely = report[report.index("aqis_lab/lonely.py"):]
    assert "no tests selected" in "\n".join(lonely.splitlines()[:3]), report
