"""Unit tests for tools.index.impact (WO-1.0-03 step 5).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest tests over scratch git repositories built under pytest's scratch path.
CONTRACTS: WO-1.0-03 B11 and B12 pins 1, 2 and 14.
INVARIANTS:
  - No network, no sleeps, no randomness; git runs only inside the scratch path.
  - No test depends on the real repository's contents.
NOT IN SCOPE:
  - The command line and its exit codes (__main__.py, step 6); the read-only acceptance test.
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
  2026-10-12 WP-1.0 FR-1.0-03 fix 1: the untracked-and-modified test commits gamma before
             changing its content, so the change is tracked and its dependencies are visible.
  2026-10-12 WP-1.0 FR-1.0-03 fix 2 (superseded): expected seed-import propagation.
  2026-10-12 WP-1.0 FR-1.0-03 fix 3: expectations restored to B11: a changed or deleted
             module affects its importers, not its imports; the untracked half of the
             untracked-and-modified test keeps only the tracked-modification case.
  2026-10-12 WP-1.0 FR-1.0-03 fix 4: the deleted-module test documents that the deleted
             module itself is gone from the working tree, so the selection comes from the
             merge-base import graph."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tools.index.impact import ImpactError, ImpactResult, affected_tests, render_impact

DOC = ('"""Docstring for {name}.\n\nCAPABILITIES:\n{caps}\nINPUTS AND OUTPUTS: x in, y out.\n'
       'CONTRACTS: none.\nINVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\n'
       'CHANGE LOG:\n  {log}\n"""\n')

ALPHA = DOC.format(
    name='alpha',
    caps='  CAP-SCR-001: doubles a number [tests: test_FR_9_1_01_alpha_works,\n'
         '    test_FR_9_1_02_alpha_listed_capability]',
    log='2026-10-10 WP-9.1 FR-9.1-01 created.') + (
    'from __future__ import annotations\n\n\n'
    'def alpha_fn(value: int) -> int:\n    return value * 2\n')

BETA = DOC.format(
    name='beta', caps='  CAP-SCR-002: adds one [tests: test_FR_9_2_01_beta_works]',
    log='2026-10-10 WO-9.2-01 created.') + (
    'from .alpha import alpha_fn\n\n\n'
    'def beta_fn(value: int) -> int:\n    return alpha_fn(value) + 1\n')

PKG_INIT = DOC.format(name='pkg', caps='  none.', log='2026-10-10 WP-9.1 FR-9.1-01 created.') + (
    'from .alpha import alpha_fn\n\n__all__ = ["alpha_fn"]\n')

GAMMA_WITH_IMPORT = (DOC.format(name='gamma', caps='  none.',
                                log='2026-10-10 WP-9.1 FR-9.1-01 created.')
                     + 'from .alpha import alpha_fn\n')
GAMMA_PLAIN = DOC.format(name='gamma', caps='  none.', log='2026-10-10 WP-9.1 FR-9.1-01 created.')

FILES = {
    'aqis_lab/__init__.py': DOC.format(name='aqis_lab', caps='  none.',
                                       log='2026-10-10 WP-9.0 FR-9.0-01 created.'),
    'aqis_lab/pkg/__init__.py': PKG_INIT,
    'aqis_lab/pkg/alpha.py': ALPHA,
    'aqis_lab/pkg/beta.py': BETA,
    'tests/aqis_lab/conftest.py': '"""Scratch conftest."""\n',
    'tests/aqis_lab/test_scr_alpha.py': (
        '"""Alpha tests."""\nfrom aqis_lab.pkg.alpha import alpha_fn\n\n\n'
        'def test_FR_9_1_01_alpha_works():\n    assert alpha_fn(2) == 4\n'),
    'tests/aqis_lab/test_scr_beta.py': (
        '"""Beta tests."""\nimport aqis_lab.pkg.beta as beta\n\n\n'
        'def test_FR_9_2_01_beta_works():\n    assert beta.beta_fn(2) == 5\n'),
    'tests/aqis_lab/test_scr_other.py': (
        '"""Other tests."""\n\n\n'
        'def test_FR_9_1_02_alpha_listed_capability():\n    assert True\n\n\n'
        'def test_NFR_9_1_01_unrelated():\n    assert True\n'),
    'tests/aqis_lab/test_scr_pkg.py': (
        '"""Package tests."""\nfrom aqis_lab.pkg import alpha_fn\n\n\n'
        'def test_AT_9_1_01_package_reexport():\n    assert alpha_fn(1) == 2\n'),
    'tests/aqis_lab/test_scr_unrelated.py': (
        '"""Unrelated tests."""\n\n\ndef test_DEBT_901_unrelated():\n    assert True\n'),
}


def git(repo: Path, *args: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update({'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'})
    proc = subprocess.run(['git', '-c', 'init.defaultBranch=main', *args], cwd=repo, check=True,
                          capture_output=True, text=True, env=env, timeout=120)
    return proc.stdout


def write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding='utf-8')


def commit(repo: Path, message: str) -> None:
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / 'repo'
    root.mkdir()
    for rel, text in FILES.items():
        write(root, rel, text)
    git(root, 'init', '-q')
    commit(root, 'base')
    return root


def branch_change(repo: Path, rel: str, text: str | None) -> ImpactResult:
    git(repo, 'checkout', '-qb', 'work')
    if text is None:
        (repo / rel).unlink()
    else:
        write(repo, rel, text)
    commit(repo, 'change')
    return affected_tests(repo, 'main')


def test_FR_1_0_03_importer_tests_are_selected(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    assert not result.all
    assert 'tests/aqis_lab/test_scr_alpha.py' in result.lines
    assert 'tests/aqis_lab/test_scr_beta.py' in result.lines
    assert 'tests/aqis_lab/test_scr_pkg.py' in result.lines


def test_FR_1_0_03_capability_tests_outside_importing_files_are_selected(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    assert 'tests/aqis_lab/test_scr_other.py::test_FR_9_1_02_alpha_listed_capability' in result.lines
    assert 'tests/aqis_lab/test_scr_other.py' not in result.lines
    assert 'tests/aqis_lab/test_scr_unrelated.py' not in '\n'.join(result.lines)


def test_FR_1_0_03_transitive_importers_are_affected(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    assert 'tests/aqis_lab/test_scr_beta.py' in result.lines, 'beta imports alpha, so its test is affected'


def test_FR_1_0_03_deleted_module_affects_its_former_importers(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/beta.py', None)
    assert not result.all
    assert 'tests/aqis_lab/test_scr_beta.py' in result.lines, (
        'test_scr_beta imports the deleted beta, so it cannot even be collected (E5)')
    assert 'tests/aqis_lab/test_scr_alpha.py' not in result.lines


def test_FR_1_0_03_package_change_counts_only_reexported_modules(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/beta.py', BETA + '\nVALUE = 1\n')
    assert result.lines == ('tests/aqis_lab/test_scr_beta.py',)


def test_FR_1_0_03_untracked_and_modified_files_count_as_changed(repo: Path) -> None:
    git(repo, 'checkout', '-qb', 'work')
    write(repo, 'aqis_lab/pkg/gamma.py', GAMMA_WITH_IMPORT)
    commit(repo, 'add gamma')
    write(repo, 'aqis_lab/pkg/gamma.py', GAMMA_PLAIN)
    result = affected_tests(repo, 'main')
    assert not result.all
    assert result.lines == (), (
        'gamma changed, but B11 affects importers, not imports, and no test imports gamma')
    git(repo, 'checkout', '-q', '--', 'aqis_lab/pkg/gamma.py')
    result = affected_tests(repo, 'main')
    assert result.lines == (), 'no change against the merge base means no selection'


def test_FR_1_0_03_ignored_files_do_not_count(repo: Path) -> None:
    write(repo, '.gitignore', 'scratch_dir/\n')
    commit(repo, 'ignore')
    write(repo, 'scratch_dir/notes.py', 'VALUE = 1\n')
    result = affected_tests(repo, 'main')
    assert not result.all and result.lines == ()


@pytest.mark.parametrize('rel', ['tests/aqis_lab/conftest.py', 'pytest.ini', 'pyproject.toml',
                                 'requirements/pinned.txt'])
def test_FR_1_0_03_conftest_requirements_and_ini_answer_all(repo: Path, rel: str) -> None:
    result = branch_change(repo, rel, '"""Changed."""\n' if rel.endswith('.py') else '[pytest]\n')
    assert result.all
    assert result.reason and rel in result.reason
    assert render_impact(result).splitlines() == ['all', f'reason: {result.reason}']


def test_FR_1_0_03_test_helper_without_test_prefix_answers_all(repo: Path) -> None:
    result = branch_change(repo, 'tests/aqis_lab/helper_util.py', '"""Helper."""\n')
    assert result.all and 'tests/aqis_lab/helper_util.py' in (result.reason or '')


def test_FR_1_0_03_more_than_25_modules_answers_all(repo: Path) -> None:
    git(repo, 'checkout', '-qb', 'work')
    for number in range(26):
        write(repo, f'aqis_lab/pkg/extra_{number:02d}.py',
              DOC.format(name=f'extra {number}', caps='  none.',
                         log='2026-10-10 WP-9.1 FR-9.1-01 created.'))
    commit(repo, 'many')
    result = affected_tests(repo, 'main')
    assert result.all and '25' in (result.reason or '')


def test_FR_1_0_03_missing_base_ref_after_one_fetch_answers_all(repo: Path) -> None:
    result = affected_tests(repo, 'no-such-ref')
    assert result.all
    assert result.reason and 'no-such-ref' in result.reason
    assert render_impact(result).splitlines()[0] == 'all'


def test_FR_1_0_03_selection_lines_are_sorted_and_unique(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    assert list(result.lines) == sorted(set(result.lines))
    assert render_impact(result) == '\n'.join(result.lines) + '\n'


def test_FR_1_0_03_imported_files_print_as_paths_others_as_node_ids(repo: Path) -> None:
    result = branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    for line in result.lines:
        if '::' in line:
            assert line == 'tests/aqis_lab/test_scr_other.py::test_FR_9_1_02_alpha_listed_capability'
        else:
            assert '::' not in line and line.endswith('.py')


def test_FR_1_0_03_output_is_byte_identical_across_runs(repo: Path) -> None:
    branch_change(repo, 'aqis_lab/pkg/alpha.py', ALPHA + '\nVALUE = 1\n')
    first = affected_tests(repo, 'main')
    second = affected_tests(repo, 'main')
    assert first == second
    assert render_impact(first) == render_impact(second)


def test_FR_1_0_03_working_tree_edits_without_a_commit_count(repo: Path) -> None:
    git(repo, 'checkout', '-qb', 'work')
    write(repo, 'aqis_lab/pkg/beta.py', BETA + '\nVALUE = 1\n')
    result = affected_tests(repo, 'main')
    assert result.lines == ('tests/aqis_lab/test_scr_beta.py',)


def test_FR_1_0_03_an_empty_selection_prints_nothing(repo: Path) -> None:
    branch_change(repo, 'README.md', '# scratch\n')
    result = affected_tests(repo, 'main')
    assert not result.all and result.lines == ()
    assert render_impact(result) == ''


def test_FR_1_0_03_a_repository_without_commits_is_an_impact_error(tmp_path: Path) -> None:
    empty = tmp_path / 'empty'
    empty.mkdir()
    git(empty, 'init', '-q')
    with pytest.raises(ImpactError, match='HEAD'):
        affected_tests(empty, 'main')
