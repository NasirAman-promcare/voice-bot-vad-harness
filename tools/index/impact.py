"""Pick the tests affected by a change since a base ref (WO-1.0-03 B11, B12 pins 1 and 14).

CAPABILITIES:
  CAP-INDEX-005: affected_tests() finds the merge base of REF and HEAD (fetching REF once when
  missing), diffs to the working tree (tracked and untracked, never ignored), expands changed
  modules to their transitive importers (working tree and merge-base tree, so a deleted module
  still carries its former importers, E5), and selects the test files that import an affected
  module, the test files that import a deleted module under any name (an unimportable module
  breaks the file's collection) and the capability tests the affected non-test modules'
  headers list; answers `all` with a reason when shared infrastructure changes, more than 25
  modules are affected or the base ref is unverifiable
  [tests: test_FR_1_0_03_importer_tests_are_selected,
  test_FR_1_0_03_capability_tests_outside_importing_files_are_selected,
  test_FR_1_0_03_transitive_importers_are_affected,
  test_FR_1_0_03_deleted_module_affects_its_former_importers,
  test_FR_1_0_03_package_change_counts_only_reexported_modules,
  test_FR_1_0_03_untracked_and_modified_files_count_as_changed,
  test_FR_1_0_03_ignored_files_do_not_count,
  test_FR_1_0_03_conftest_requirements_and_ini_answer_all,
  test_FR_1_0_03_test_helper_without_test_prefix_answers_all,
  test_FR_1_0_03_more_than_25_modules_answers_all,
  test_FR_1_0_03_missing_base_ref_after_one_fetch_answers_all,
  test_FR_1_0_03_selection_lines_are_sorted_and_unique,
  test_FR_1_0_03_imported_files_print_as_paths_others_as_node_ids,
  test_FR_1_0_03_output_is_byte_identical_across_runs]
INPUTS AND OUTPUTS: a repository root and a base ref in; an ImpactResult out (lines or `all`
  with a reason). Runs git read-only commands and `git fetch` at most once for a missing ref.
CONTRACTS: WO-1.0-03 B11 and B12 pins 1, 2, 3 and 14; scan() shapes imports and capability tests.
INVARIANTS:
  - Never imports scanned code; analysis comes from scan() and git diff output only.
  - Deterministic: output lines are sorted and unique; no clock, locale or filesystem order.
  - A deleted module's former importers come from the merge-base tree (E5); a test module's
    CAPABILITIES section never names capability tests (B12 pin 3).
NOT IN SCOPE:
  - Scanning (scan.py), rendering (render.py), the command line and exit codes (__main__.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
  2026-10-12 WP-1.0 FR-1.0-03 fix 1: reverse closure over the working-tree and base graphs.
  2026-10-12 WP-1.0 FR-1.0-03 fix 2 (superseded): added seed-import propagation.
  2026-10-12 WP-1.0 FR-1.0-03 fix 3: seed-import propagation removed; B11 affects a changed
             module's importers, not its imports; capability tests come from non-test modules.
  2026-10-12 WP-1.0 FR-1.0-03 fix 4: a test file that imported a deleted module is selected
             from the merge-base graph directly: the import cannot resolve, so the file cannot
             be collected, whatever its new content says.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude, DEC-1.0-10): a changed or new test file is selected itself.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from tools.index.headers import parse_header
from tools.index.scan import ModuleFacts, scan

__all__ = ['ImpactError', 'ImpactResult', 'affected_tests', 'render_impact']

_MAX_AFFECTED_MODULES = 25


class ImpactError(Exception):
    """impact could not run at all: no repository, no HEAD commit or git itself failed."""


@dataclass(frozen=True)
class ImpactResult:
    """The impact answer: either `all` with a reason, or sorted unique pytest argument lines."""
    all: bool
    reason: str | None
    lines: tuple[str, ...]


def render_impact(result: ImpactResult) -> str:
    """Text of the impact answer: `all` plus `reason: <why>`, or one pytest argument per line."""
    if result.all:
        return f'all\nreason: {result.reason}\n'
    if not result.lines:
        return ''
    return '\n'.join(result.lines) + '\n'


def _git(root: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update({'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'})
    proc = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, env=env, timeout=120)
    if check and proc.returncode != 0:
        raise ImpactError(f'git {" ".join(args)} failed in {root}: {proc.stderr.strip() or proc.stdout.strip()}')
    return proc


def _resolve_ref(root: str, base_ref: str) -> str | None:
    """The commit of base_ref, fetching it once when missing; None when still unverifiable."""
    proc = _git(root, 'rev-parse', '--verify', '--quiet', f'{base_ref}^{{commit}}', check=False)
    commit = proc.stdout.strip()
    if commit:
        return commit
    _git(root, 'fetch', 'origin', base_ref, check=False)
    proc = _git(root, 'rev-parse', '--verify', '--quiet', f'{base_ref}^{{commit}}', check=False)
    return proc.stdout.strip() or None


def _changed_paths(root: str, merge_base: str) -> tuple[str, ...]:
    """Changed files between the merge base and the working tree: tracked, untracked, not ignored."""
    out = _git(root, 'diff', '--name-only', '-z', merge_base).stdout
    tracked = [part for part in out.split('\0') if part]
    out = _git(root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    untracked = [part for part in out.split('\0') if part]
    return tuple(sorted(set(tracked) | set(untracked)))


def _deleted_paths(root: str, merge_base: str) -> frozenset[str]:
    """The .py files that existed at the merge base and are gone from the working tree."""
    out = _git(root, 'diff', '--name-only', '--diff-filter=D', '-z', merge_base).stdout
    return frozenset(part for part in out.split('\0') if part)


def _base_tree(root: str, merge_base: str):
    """Extract the merge-base tree into a scratch folder and scan it (E5: deleted modules)."""
    import tempfile  # audit-allow: stdlib name
    scratch = tempfile.TemporaryDirectory(prefix='aqis-impact-base-')  # audit-allow: stdlib name
    archive = subprocess.run(['git', 'archive', '--format=tar', merge_base], cwd=root,
                             capture_output=True, timeout=300)
    if archive.returncode != 0:
        scratch.cleanup()
        raise ImpactError(f'git archive {merge_base} failed: '
                          f'{archive.stderr.decode("utf-8", "replace").strip()}')
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(scratch.name, filter='data')
    return scratch, scan(scratch.name)


def _reverse_graph(facts: tuple[ModuleFacts, ...]) -> dict[str, frozenset[str]]:
    """{imported module: direct importers} across the scanned modules."""
    graph: dict[str, set[str]] = {}
    for fact in facts:
        for imported in fact.imports:
            graph.setdefault(imported, set()).add(fact.path)
    return {key: frozenset(values) for key, values in graph.items()}


def _closure(seeds: set[str], graphs: list[dict[str, frozenset[str]]]) -> set[str]:
    """Seeds plus every module that imports them, transitively, in any of the graphs."""
    affected = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop()
        for graph in graphs:
            for importer in graph.get(current, ()):
                if importer not in affected:
                    affected.add(importer)
                    queue.append(importer)
    return affected


def _broken_importers(deleted: frozenset[str], base_graph: dict[str, frozenset[str]],
                      facts: tuple[ModuleFacts, ...]) -> set[str]:
    """Test files that imported a deleted module at the merge base and still exist.

The import cannot resolve, so the file cannot be collected: it is selected no matter what
its current content says."""
    broken: set[str] = set()
    for module in deleted:
        for importer in base_graph.get(module, ()):
            if _is_test_file(importer):
                broken.add(importer)
    present = {fact.path for fact in facts}
    return broken & present


def _all_reason(changed: tuple[str, ...], affected_count: int) -> str | None:
    """The `all` reason for the change, or None when a normal selection applies (B11)."""
    for rel in changed:
        name = rel.rsplit('/', 1)[-1]
        if name == 'conftest.py':
            return f'{rel}: conftest.py is shared by every test collected below it'
        if rel == 'pyproject.toml' or rel == 'pytest.ini':
            return f'{rel}: test configuration applies to every test run'
        if rel.startswith('requirements/'):
            return f'{rel}: a dependency change can change any test outcome'
        if (rel.startswith('tests/aqis_lab/') and rel.endswith('.py')
                and not name.startswith('test_') and not name.endswith('_test.py')):
            return f'{rel}: a test helper without a test prefix may be imported by any test'
    if affected_count > _MAX_AFFECTED_MODULES:
        return (f'{affected_count} modules are affected, more than {_MAX_AFFECTED_MODULES}: '
                'a selection would miss real dependents')
    return None


def _is_test_file(path: str) -> bool:
    name = path.rsplit('/', 1)[-1]
    return path.startswith('tests/aqis_lab/') and (name.startswith('test_') or name.endswith('_test.py'))


def _capability_tests(facts: tuple[ModuleFacts, ...], affected: set[str]) -> set[str]:
    """The capability test names the affected non-test modules' headers list (B12 pin 3)."""
    named: set[str] = set()
    for fact in facts:
        if fact.path not in affected or _is_test_file(fact.path):
            continue
        if fact.docstring is None or fact.parse_error is not None:
            continue
        for capability in parse_header(fact.docstring).capabilities:
            named.update(capability.tests)
    return named


def affected_tests(repo_root, base_ref: str) -> ImpactResult:
    """The tests affected by the change since base_ref (B11); `all` when selection is unsafe."""
    root = _git(str(repo_root), 'rev-parse', '--show-toplevel').stdout.strip()
    if not _git(root, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}', check=False).stdout.strip():
        raise ImpactError(f'{root} has no HEAD commit; impact needs at least one commit')
    base_commit = _resolve_ref(root, base_ref)
    if base_commit is None:
        return ImpactResult(True, f'base ref {base_ref} is missing after one fetch from origin', ())
    merge_base = _git(root, 'merge-base', base_commit, 'HEAD').stdout.strip()
    if not merge_base:
        return ImpactResult(True, f'no merge base between {base_ref} and HEAD', ())
    changed = _changed_paths(root, merge_base)
    deleted = frozenset(rel for rel in _deleted_paths(root, merge_base) if rel.endswith('.py'))
    facts = scan(root)
    scratch, base_facts = _base_tree(root, merge_base)
    try:
        graphs = [_reverse_graph(facts), _reverse_graph(base_facts)]
        seeds = {rel for rel in changed if rel.endswith('.py')}
        affected = _closure(seeds, graphs)
        reason = _all_reason(changed, len(affected))
        if reason is not None:
            return ImpactResult(True, reason, ())
        selected_files: set[str] = set()
        for fact in facts:
            if _is_test_file(fact.path) and any(module in affected for module in fact.imports):
                selected_files.add(fact.path)
        selected_files |= _broken_importers(deleted, graphs[1], facts)
        selected_files |= {fact.path for fact in facts if _is_test_file(fact.path) and fact.path in affected}  # DEC-1.0-10
        wanted = _capability_tests(facts, affected)
        node_ids: set[str] = set()
        for fact in facts:
            if not _is_test_file(fact.path) or fact.path in selected_files:
                continue
            for test_name in fact.tests:
                if test_name in wanted:
                    node_ids.add(f'{fact.path}::{test_name}')
        lines = sorted(selected_files | node_ids)
        return ImpactResult(False, None, tuple(lines))
    finally:
        scratch.cleanup()
