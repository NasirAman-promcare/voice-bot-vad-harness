"""Unit tests for tools/audit/breaks.py: recipe loading, running, reporting and exit codes.

CAPABILITIES:
  CAP-AUDIT-TEST-001: proves load_recipes() ordering and header parsing (B1), run_recipe()
  verdicts for caught/survived/broken including patch drift, missing nodes, crashes and
  unnamed failures (B3, MC1-MC4), worktree removal on success, crash and pytest timeout (B4),
  test-file recipes reported broken (E2), and main() exit codes, 30-line report cap, no-recipes
  exit 2 and --all WP grouping (B5, E1, E4) [tests: every test in this module is one of those
  proofs; the fixture builds a scratch git repository with its own recipes via `git diff`,
  and every recipe file is committed so the working tree is clean before and after each run]
INPUTS AND OUTPUTS: pytest collects this module; a scratch git repository and a private TMPDIR
  per test in; assertions on Recipe/RecipeResult and exit codes out. No network, no sleeps.
CONTRACTS: WO-1.0-06 B1 to B5, B8 pins 1-6, E1, E2, E4; docs/process/templates/BREAK_RECIPE.md.
INVARIANTS:
  - Every test leaves the scratch repository clean: no worktrees, no scratch folders, no
    changes to the real working tree (asserted by _assert_clean); recipes are committed
    before any run so `git status --porcelain` is empty.
  - No network and no unseeded randomness; git runs with a fixture identity.
NOT IN SCOPE:
  - The acceptance tests (test_acceptance_wo_1_0_06.py, read-only), mutate.py and
    mutation_report.py tests (later steps of WO-1.0-06).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-06 created.
  2026-10-12 WP-1.0 FR-1.0-06 fix 1: full module header standard added.
  2026-10-12 WP-1.0 FR-1.0-06 fix 2: recipe files committed in the fixture so _assert_clean's
    `git status --porcelain` check no longer fails on untracked recipe files."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from tools.audit.breaks import (
    BROKEN,
    CAUGHT,
    SURVIVED,
    load_recipes,
    main,
    run_recipe,
)

CALC = (
    '"""Scratch calculator."""\n'
    '\n'
    '\n'
    'def add(a: int, b: int) -> int:\n'
    '    return a + b\n'
    '\n'
    '\n'
    'def is_positive(value: int) -> bool:\n'
    '    if value > 0:\n'
    '        return True\n'
    '    return False\n'
)
TEST_CALC = (
    '"""Scratch tests for the calculator."""\n'
    'from aqis_lab.calc import add, is_positive\n'
    '\n'
    '\n'
    'def test_add():\n'
    '    assert add(2, 3) == 5\n'
    '\n'
    '\n'
    'def test_positive():\n'
    '    assert is_positive(4) is True\n'
    '\n'
    '\n'
    'def test_unrelated():\n'
    '    assert len("abc") == 3\n'
)
FILES = {
    'aqis_lab/__init__.py': '"""Scratch lab package."""\n',
    'aqis_lab/calc.py': CALC,
    'tests/aqis_lab/test_calc.py': TEST_CALC,
}
NODE = 'tests/aqis_lab/test_calc.py::'


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update({'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'AQIS Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                'GIT_COMMITTER_NAME': 'AQIS Fixture',
                'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'})
    return subprocess.run(['git', '-c', 'init.defaultBranch=main', *args], cwd=repo,
                          check=True, capture_output=True, text=True, env=env,
                          timeout=120).stdout


def _write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding='utf-8')


def _commit(repo: Path, message: str) -> None:
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-qm', message)


def _recipe(repo: Path, wp: str, name: str, rel: str, old: str, new: str,
            expect: list[str], mc: str = '1', behaviour: str = 'scratch behaviour',
            headers: list[str] | None = None) -> Path:
    """Write a recipe made with `git diff` against the committed file, then restore it."""
    original = (repo / rel).read_text(encoding='utf-8')
    assert original.count(old) == 1, (rel, old)
    (repo / rel).write_text(original.replace(old, new), encoding='utf-8')
    diff = _git(repo, 'diff', '--', rel)
    (repo / rel).write_text(original, encoding='utf-8')
    lines = headers if headers is not None else (
        [f'# MC: {mc}', f'# behaviour: {behaviour}']
        + [f'# expect-fail: {node}' for node in expect])
    path = repo / 'tests/aqis_lab/breaks' / wp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n' + diff, encoding='utf-8')
    return path


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = tmp_path / 'repo'
    for rel, text in FILES.items():
        _write(repo, rel, text)
    _git(repo, 'init', '-q')
    _commit(repo, 'base')
    tmp = tmp_path / 'tmp'
    tmp.mkdir()
    monkeypatch.setenv('TMPDIR', str(tmp))
    tempfile.tempdir = None
    yield {'repo': repo, 'tmp': tmp}
    tempfile.tempdir = None


def _commit_recipes(repo: Path) -> None:
    """Commit any uncommitted recipe files so the tree is clean before runs and checks."""
    if _git(repo, 'status', '--porcelain'):
        _commit(repo, 'recipes')


def _assert_clean(scratch: dict) -> None:
    repo = scratch['repo']
    assert _git(repo, 'status', '--porcelain') == '', 'the real working tree is never changed'
    worktrees = [line for line in _git(repo, 'worktree', 'list', '--porcelain').splitlines()
                 if line.startswith('worktree ')]
    assert worktrees == [f'worktree {repo}'], worktrees
    assert list(scratch['tmp'].iterdir()) == [], \
        f"left behind: {sorted(p.name for p in scratch['tmp'].iterdir())}"


def _status_by_name(scratch: dict, wp: str) -> dict[str, str]:
    recipes = load_recipes(scratch['repo'], wp)
    return {r.path.name: run_recipe(r, scratch['repo']).status for r in recipes}


# --------------------------------------------------------------------------- B1: loading

def test_B1_recipes_are_found_sorted_by_wp_then_name(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.2', 'MC-02-b.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _recipe(repo, 'WP-9.1', 'MC-02-z.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _recipe(repo, 'WP-9.1', 'MC-01-a.patch', 'aqis_lab/calc.py', 'return True',
            'return False', [NODE + 'test_positive'])
    names = [(r.wp, r.path.name) for r in load_recipes(repo, None)]
    assert names == [('WP-9.1', 'MC-01-a.patch'), ('WP-9.1', 'MC-02-z.patch'),
                     ('WP-9.2', 'MC-02-b.patch')]


def test_B1_headers_parse_mc_behaviour_and_expect_fail_nodes(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add', NODE + 'test_unrelated'],
            mc='WO-9.1-01 #3', behaviour='addition must add')
    (recipe,) = load_recipes(repo, 'WP-9.1')
    assert recipe.wp == 'WP-9.1'
    assert recipe.mc == 'WO-9.1-01 #3'
    assert recipe.behaviour == 'addition must add'
    assert recipe.expect_fail == (NODE + 'test_add', NODE + 'test_unrelated')


def test_B1_recipe_names_are_free_after_the_mc_prefix(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-WO-9.1-01-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _write(repo, 'tests/aqis_lab/breaks/WP-9.1/README.txt', 'not a recipe\n')
    names = [r.path.name for r in load_recipes(repo, 'WP-9.1')]
    assert names == ['MC-WO-9.1-01-01-add.patch']


def test_B1_missing_wp_loads_no_recipes(scratch: dict) -> None:
    assert load_recipes(scratch['repo'], 'WP-9.9') == []
    assert load_recipes(scratch['repo'], None) == []


# --------------------------------------------------------------------------- B3: verdicts

def test_B3_caught_when_every_named_test_fails(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _commit_recipes(repo)
    assert _status_by_name(scratch, 'WP-9.1') == {'MC-01-add.patch': CAUGHT}
    _assert_clean(scratch)


def test_B3_survived_when_a_named_test_passes(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-positive.patch', 'aqis_lab/calc.py', 'if value > 0:',
            'if value >= 0:', [NODE + 'test_positive'])
    _commit_recipes(repo)
    results = _status_by_name(scratch, 'WP-9.1')
    assert results == {'MC-01-positive.patch': SURVIVED}
    _assert_clean(scratch)


def test_B3_broken_when_the_patch_does_not_apply(scratch: dict) -> None:
    repo = scratch['repo']
    path = _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
                   'return a - b', [NODE + 'test_add'])
    _write(repo, 'aqis_lab/calc.py', CALC.replace('return a + b', 'return b + a'))
    _commit(repo, 'the code moved on')
    (recipe,) = load_recipes(repo, 'WP-9.1')
    result = run_recipe(recipe, repo)
    assert result.status == BROKEN
    assert 'apply' in result.details
    assert result.recipe.path == path
    _assert_clean(scratch)


def test_B3_broken_when_a_named_test_is_missing(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-x.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_does_not_exist'])
    _commit_recipes(repo)
    results = _status_by_name(scratch, 'WP-9.1')
    assert results == {'MC-01-x.patch': BROKEN}
    _assert_clean(scratch)


def test_B3_broken_when_the_test_process_crashes(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-crash.patch', 'aqis_lab/calc.py', '    return a + b\n',
            '    import os\n    os._exit(70)\n', [NODE + 'test_add'])
    _commit_recipes(repo)
    assert _status_by_name(scratch, 'WP-9.1') == {'MC-01-crash.patch': BROKEN}
    _assert_clean(scratch)


def test_B3_unnamed_test_failures_do_not_count(scratch: dict) -> None:
    repo = scratch['repo']
    # The break fails test_add, but the recipe names test_positive (still passing).
    _recipe(repo, 'WP-9.1', 'MC-01-other.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_positive'])
    # One of two named tests passes: survived, never caught.
    _recipe(repo, 'WP-9.1', 'MC-02-mixed.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add', NODE + 'test_unrelated'])
    _commit_recipes(repo)
    assert _status_by_name(scratch, 'WP-9.1') == {'MC-01-other.patch': SURVIVED,
                                                  'MC-02-mixed.patch': SURVIVED}
    _assert_clean(scratch)


def test_B3_missing_headers_make_the_recipe_broken(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-x.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [], headers=['# MC: 1', '# behaviour: scratch'])
    _commit_recipes(repo)
    results = _status_by_name(scratch, 'WP-9.1')
    assert results == {'MC-01-x.patch': BROKEN}
    # A recipe with broken headers must never leave a worktree behind.
    _assert_clean(scratch)


# --------------------------------------------------------------------------- B4: cleanup

def test_B4_worktree_is_removed_on_success_and_crash(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _recipe(repo, 'WP-9.1', 'MC-02-crash.patch', 'aqis_lab/calc.py', '    return a + b\n',
            '    import os\n    os._exit(70)\n', [NODE + 'test_add'])
    _commit_recipes(repo)
    statuses = _status_by_name(scratch, 'WP-9.1')
    assert statuses == {'MC-01-add.patch': CAUGHT, 'MC-02-crash.patch': BROKEN}
    _assert_clean(scratch)


def test_B4_worktree_is_removed_when_pytest_times_out(
        scratch: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _commit_recipes(repo)
    (recipe,) = load_recipes(repo, 'WP-9.1')

    def _timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=['pytest'], timeout=1)

    import tools.audit.breaks as breaks_mod
    monkeypatch.setattr(breaks_mod, '_run_pytest', _timeout)
    result = run_recipe(recipe, repo)
    assert result.status == BROKEN
    assert 'timed out' in result.details
    _assert_clean(scratch)


# --------------------------------------------------------------------------- E2: test files

def test_E2_a_recipe_that_changes_a_test_file_is_broken(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-tests.patch', 'tests/aqis_lab/test_calc.py',
            'assert add(2, 3) == 5', 'assert add(2, 3) == 6', [NODE + 'test_add'])
    _commit_recipes(repo)
    (recipe,) = load_recipes(repo, 'WP-9.1')
    result = run_recipe(recipe, repo)
    assert result.status == BROKEN
    assert 'test' in result.details.lower()
    _assert_clean(scratch)


def test_E2_a_recipe_that_changes_a_conftest_is_broken(scratch: dict) -> None:
    repo = scratch['repo']
    _write(repo, 'aqis_lab/conftest.py', '"""Scratch conftest."""\n')
    _commit(repo, 'conftest')
    _recipe(repo, 'WP-9.1', 'MC-01-conftest.patch', 'aqis_lab/conftest.py',
            '"""Scratch conftest."""', '"""Changed conftest."""', [NODE + 'test_add'])
    _commit_recipes(repo)
    (recipe,) = load_recipes(repo, 'WP-9.1')
    assert run_recipe(recipe, repo).status == BROKEN
    _assert_clean(scratch)


# --------------------------------------------------------------------- B5, E1, E4: main()

def _run_main(scratch: dict, argv: list[str]) -> tuple[int, str, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    cwd = os.getcwd()
    out, err = io.StringIO(), io.StringIO()
    os.chdir(scratch['repo'])
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
    finally:
        os.chdir(cwd)
    return code, out.getvalue(), err.getvalue()


def test_B5_exit_0_only_when_all_caught(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _commit_recipes(repo)
    code, out, _err = _run_main(scratch, ['--wp', 'WP-9.1'])
    assert code == 0
    assert 'MC-01-add.patch' in out and CAUGHT in out
    _assert_clean(scratch)


def test_B5_exit_1_when_any_recipe_survived(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-positive.patch', 'aqis_lab/calc.py', 'if value > 0:',
            'if value >= 0:', [NODE + 'test_positive'])
    _recipe(repo, 'WP-9.1', 'MC-02-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _commit_recipes(repo)
    code, _out, _err = _run_main(scratch, ['--wp', 'WP-9.1'])
    assert code == 1
    _assert_clean(scratch)


def test_B5_exit_2_when_broken_and_none_survived(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _write(repo, 'aqis_lab/calc.py', CALC.replace('return a + b', 'return b + a'))
    _commit(repo, 'the code moved on')
    code, _out, _err = _run_main(scratch, ['--wp', 'WP-9.1'])
    assert code == 2
    _assert_clean(scratch)


def test_B5_report_is_at_most_30_lines(scratch: dict) -> None:
    repo = scratch['repo']
    for index in range(40):
        _write(repo, f'aqis_lab/mod_{index:02d}.py',
               f'"""Module {index}."""\n\n\ndef value() -> int:\n    return {index}\n')
    _commit(repo, 'many modules')
    for index in range(40):
        _recipe(repo, 'WP-9.1', f'MC-{index:02d}-m.patch', f'aqis_lab/mod_{index:02d}.py',
                f'return {index}', f'return {index + 1}', [NODE + 'test_add'])
    _commit_recipes(repo)
    code, out, _err = _run_main(scratch, ['--wp', 'WP-9.1'])
    assert len(out.splitlines()) <= 30
    _assert_clean(scratch)


def test_E1_no_recipes_exits_2_with_no_recipes(scratch: dict) -> None:
    code, out, err = _run_main(scratch, ['--wp', 'WP-9.4'])
    assert code == 2
    assert 'no recipes' in (out + err).lower()


def test_E4_all_groups_the_table_by_wp_in_sorted_order(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.2', 'MC-01-b.patch', 'aqis_lab/calc.py', 'return True',
            'return False', [NODE + 'test_positive'])
    _recipe(repo, 'WP-9.1', 'MC-01-a.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'])
    _commit_recipes(repo)
    code, out, _err = _run_main(scratch, ['--all'])
    assert code == 0
    assert out.index('MC-01-a.patch') < out.index('MC-01-b.patch')
    lines = out.splitlines()
    for name, wp in (('MC-01-a.patch', 'WP-9.1'), ('MC-01-b.patch', 'WP-9.2')):
        at = next(n for n, line in enumerate(lines) if name in line)
        group = next(line for line in reversed(lines[:at + 1]) if 'WP-9.' in line)
        assert wp in group, (name, group)
    _assert_clean(scratch)


def test_B5_recipe_result_carries_recipe_status_and_details(scratch: dict) -> None:
    repo = scratch['repo']
    _recipe(repo, 'WP-9.1', 'MC-01-add.patch', 'aqis_lab/calc.py', 'return a + b',
            'return a - b', [NODE + 'test_add'], mc='7', behaviour='addition adds')
    _commit_recipes(repo)
    (recipe,) = load_recipes(repo, 'WP-9.1')
    result = run_recipe(recipe, repo)
    assert result.recipe is recipe
    assert result.status == CAUGHT
    assert 'test_add' in result.details
    _assert_clean(scratch)
