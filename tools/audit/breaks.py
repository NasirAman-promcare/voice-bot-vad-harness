"""Find, validate and run break recipes in throwaway worktrees; report caught/survived/broken.

CAPABILITIES:
  CAP-AUDIT-001: load_recipes() finds every tests/aqis_lab/breaks/<WP>/MC-*.patch (sorted by WP
  then file name), parses the `# MC:`, `# behaviour:` and `# expect-fail:` header lines, and
  returns Recipe records with path, wp, mc, behaviour and expect_fail
  [tests: test_B1_recipes_are_found_sorted_by_wp_then_name,
  test_B1_headers_parse_mc_behaviour_and_expect_fail_nodes,
  test_B1_recipe_names_are_free_after_the_mc_prefix,
  test_B1_missing_wp_loads_no_recipes]
  CAP-AUDIT-002: run_recipe() applies one recipe in a detached worktree of HEAD inside a
  tempfile.mkdtemp() scratch folder, refuses patches that touch tests/ or conftest.py /
  test_*.py files, runs only the expect-fail node IDs with sys.executable -m pytest -rA
  -p no:cacheprovider (PYTHONDONTWRITEBYTECODE=1 added), and reports caught only when every
  named node failed or errored, survived when any named node passed, broken when the patch
  does not apply, a node has no reported outcome, or pytest could not run; the worktree is
  removed (worktree remove --force, folder deleted, worktree prune) in every case, including
  crashes and timeouts [tests: test_B3_caught_when_every_named_test_fails,
  test_B3_survived_when_a_named_test_passes,
  test_B3_broken_when_the_patch_does_not_apply,
  test_B3_broken_when_a_named_test_is_missing,
  test_B3_broken_when_the_test_process_crashes,
  test_B3_unnamed_test_failures_do_not_count,
  test_B4_worktree_is_removed_on_success_and_crash,
  test_B4_worktree_is_removed_when_pytest_times_out,
  test_E2_a_recipe_that_changes_a_test_file_is_broken]
  CAP-AUDIT-003: main() runs one WP or all WPs, prints a grouped report of at most 30 lines,
  exits 0 when every recipe is caught, 1 when any survived, 2 when any is broken and none
  survived or the WP has no recipes [tests: test_B5_exit_0_only_when_all_caught,
  test_B5_exit_1_when_any_recipe_survived, test_B5_exit_2_when_broken_and_none_survived,
  test_B5_report_is_at_most_30_lines, test_E1_no_recipes_exits_2_with_no_recipes,
  test_E4_all_groups_the_table_by_wp_in_sorted_order]
INPUTS AND OUTPUTS: a repository root path and a WP name (or None for all) in; Recipe and
  RecipeResult records, a printed table, and a process exit code out. Runs git and pytest as
  subprocesses inside scratch worktrees; never touches the real working tree.
CONTRACTS: docs/process/templates/BREAK_RECIPE.md (recipe format); WO-1.0-06 B1 to B5, B8
  pins 1 to 6, E1, E2, E4.
INVARIANTS:
  - The real working tree is never modified; recipes apply only inside scratch worktrees.
  - A named node with no reported outcome is broken, never caught.
  - Only the named expect-fail nodes count; other failures are ignored.
  - Deterministic: recipe order is sorted; no clock, locale or filesystem order.
NOT IN SCOPE:
  - Mutation generation (mutate.py) and the mutation report (mutation_report.py).
  - Writing or updating recipes (BREAK_RECIPE.md rules are for WP owners).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-06 created."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

__all__ = ['Recipe', 'RecipeResult', 'load_recipes', 'run_recipe', 'main']

RECIPE_GLOB = 'MC-*.patch'
BREAKS_DIR = Path('tests') / 'aqis_lab' / 'breaks'
DEFAULT_TIMEOUT_SECONDS = 600
REPORT_LINE_BUDGET = 30

MC_PREFIX = 'MC-'
HEADER_MC = 'MC:'
HEADER_BEHAVIOUR = 'behaviour:'
HEADER_EXPECT_FAIL = 'expect-fail:'

CAUGHT = 'caught'
SURVIVED = 'survived'
BROKEN = 'broken'

# pytest -rA short-summary tokens for outcomes that count as the test failing.
_FAIL_SUMMARY_TOKENS = ('FAILED', 'ERROR')
# Outcomes that mean the test definitely did not fail.
_PASS_SUMMARY_TOKENS = ('PASSED', 'XFAIL', 'SKIPPED', 'XPASS')
_SUMMARY_RE = re.compile(r'^(FAILED|ERROR|PASSED|XFAIL|SKIPPED|XPASS)\s+(\S+)')
# Lines git apply prints when a patch does not apply cleanly; only used for detail text.
_DIFF_HEADER_RE = re.compile(r'^diff --git a/(\S+) b/(\S+)$')


class BreaksError(Exception):
    """The break suite itself could not run: no repository or git failed."""


@dataclass(frozen=True)
class Recipe:
    """One break recipe: its file, WP, free-text MC id, behaviour and expect-fail node IDs."""

    path: Path
    wp: str
    mc: str
    behaviour: str
    expect_fail: tuple[str, ...]


@dataclass(frozen=True)
class RecipeResult:
    """The outcome of one recipe run: caught, survived or broken, with human details."""

    recipe: Recipe
    status: str
    details: str


def _recipe_files(repo_root: Path, wp: str | None) -> list[Path]:
    base = repo_root / BREAKS_DIR
    if wp is not None:
        candidates = [base / wp] if (base / wp).is_dir() else []
    else:
        candidates = sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.name) \
            if base.is_dir() else []
    files: list[Path] = []
    for folder in candidates:
        files.extend(sorted(folder.glob(RECIPE_GLOB), key=lambda p: p.name))
    return files


def _parse_recipe(path: Path) -> tuple[Recipe, str | None]:
    """Parse one recipe file; the error string is None when the headers are complete."""
    wp = path.parent.name
    mc = ''
    behaviour = ''
    expect: list[str] = []
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        return Recipe(path, wp, mc, behaviour, ()), f'cannot read {path.name}: {exc}'
    for line in text.splitlines():
        if line.startswith('diff --git'):
            break
        if not line.startswith('# '):
            continue
        body = line[2:]
        if body.startswith(HEADER_MC):
            mc = body[len(HEADER_MC):].strip()
        elif body.startswith(HEADER_BEHAVIOUR):
            behaviour = body[len(HEADER_BEHAVIOUR):].strip()
        elif body.startswith(HEADER_EXPECT_FAIL):
            node = body[len(HEADER_EXPECT_FAIL):].strip()
            if node:
                expect.append(node)
    recipe = Recipe(path, wp, mc, behaviour, tuple(expect))
    if not mc:
        return recipe, f'{path.name}: missing `# MC:` header'
    if not behaviour:
        return recipe, f'{path.name}: missing `# behaviour:` header'
    if not expect:
        return recipe, f'{path.name}: no `# expect-fail:` node IDs'
    return recipe, ''


def load_recipes(repo_root: Path | str, wp: str | None = None) -> list[Recipe]:
    """Every recipe under tests/aqis_lab/breaks/<WP>/ (or all WPs), sorted by WP then name.

A recipe whose headers are incomplete still loads; run_recipe reports it broken (B1)."""
    root = Path(repo_root)
    recipes: list[Recipe] = []
    for path in _recipe_files(root, wp):
        recipe, _error = _parse_recipe(path)
        recipes.append(recipe)
    return recipes


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    proc = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True,
                          env=env, timeout=300)
    if check and proc.returncode != 0:
        raise BreaksError(f'git {" ".join(args)} failed in {repo}: {proc.stderr.strip()}')
    return proc


def _patch_paths(recipe: Recipe) -> list[str]:
    """The repository-relative paths a recipe's diff touches, from its diff headers."""
    paths: list[str] = []
    for line in recipe.path.read_text(encoding='utf-8').splitlines():
        match = _DIFF_HEADER_RE.match(line)
        if match:
            paths.append(match.group(2))
    return paths


def _touches_test_files(recipe: Recipe) -> str | None:
    """The offending path when the recipe changes tests/ or a test file (E2), else None."""
    for rel in _patch_paths(recipe):
        parts = Path(rel).parts
        name = parts[-1] if parts else rel
        if parts[0] == 'tests' or name == 'conftest.py' or name.startswith('test_') and \
                name.endswith('.py'):
            return rel
    return None


def _parse_outcomes(pytest_stdout: str, nodes: tuple[str, ...]) -> dict[str, str]:
    """Map each named node to failed/passed from the pytest -rA summary; absent when missing."""
    outcomes: dict[str, str] = {}
    for line in pytest_stdout.splitlines():
        match = _SUMMARY_RE.match(line.strip())
        if not match:
            continue
        token, node = match.group(1), match.group(2)
        if token in _FAIL_SUMMARY_TOKENS:
            outcomes[node] = 'failed'
        elif token in _PASS_SUMMARY_TOKENS:
            outcomes.setdefault(node, 'passed')
    return {node: outcomes[node] for node in nodes if node in outcomes}


def _run_pytest(worktree: Path, nodes: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run(
        [sys.executable, '-m', 'pytest', *nodes, '-rA', '-p', 'no:cacheprovider'],
        cwd=worktree, capture_output=True, text=True, env=env,
        timeout=DEFAULT_TIMEOUT_SECONDS)


def _classify(recipe: Recipe, proc: subprocess.CompletedProcess[str]) -> RecipeResult:
    """The recipe result from pytest's output; only the named nodes count (B3, MC4)."""
    outcomes = _parse_outcomes(proc.stdout, recipe.expect_fail)
    missing = [node for node in recipe.expect_fail if node not in outcomes]
    if missing:
        joined = ', '.join(missing)
        return RecipeResult(recipe, BROKEN,
                            f'no outcome reported for {joined} (exit {proc.returncode})')
    failed = [node for node in recipe.expect_fail if outcomes[node] == 'failed']
    passed = [node for node in recipe.expect_fail if outcomes[node] != 'failed']
    if passed:
        return RecipeResult(recipe, SURVIVED, f'passed: {", ".join(passed)}')
    return RecipeResult(recipe, CAUGHT, f'failed as expected: {", ".join(failed)}')


def _cleanup_worktree(repo_root: Path, worktree: Path) -> None:
    """Remove the worktree, delete the scratch folder, prune; never raises (B4, B8 pin 5)."""
    try:
        _git(repo_root, 'worktree', 'remove', '--force', str(worktree), check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass
    shutil.rmtree(worktree.parent, ignore_errors=True)
    try:
        _git(repo_root, 'worktree', 'prune', check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_recipe(recipe: Recipe, repo_root: Path | str) -> RecipeResult:
    """Apply one recipe in a scratch worktree of HEAD and run only its expect-fail nodes."""
    root = Path(repo_root)
    _recipe, header_error = _parse_recipe(recipe.path)
    if header_error:
        return RecipeResult(recipe, BROKEN, header_error)
    bad_path = _touches_test_files(recipe)
    if bad_path:
        return RecipeResult(recipe, BROKEN, f'recipe changes test file {bad_path} (E2)')

    scratch = Path(tempfile.mkdtemp(prefix='aqis-break-'))
    worktree = scratch / 'worktree'
    try:
        add = _git(root, 'worktree', 'add', '--detach', str(worktree), 'HEAD', check=False)
        if add.returncode != 0:
            return RecipeResult(recipe, BROKEN,
                                f'worktree add failed: {add.stderr.strip()}')
        check = _git(worktree, 'apply', '--check', str(recipe.path), check=False)
        if check.returncode != 0:
            return RecipeResult(recipe, BROKEN,
                                f'patch does not apply: {check.stderr.strip()}')
        applied = _git(worktree, 'apply', str(recipe.path), check=False)
        if applied.returncode != 0:
            return RecipeResult(recipe, BROKEN,
                                f'patch apply failed: {applied.stderr.strip()}')
        try:
            proc = _run_pytest(worktree, recipe.expect_fail)
        except subprocess.TimeoutExpired:
            return RecipeResult(recipe, BROKEN,
                                f'pytest timed out after {DEFAULT_TIMEOUT_SECONDS}s')
        except OSError as exc:
            return RecipeResult(recipe, BROKEN, f'pytest could not start: {exc}')
        return _classify(recipe, proc)
    finally:
        _cleanup_worktree(root, worktree)


def _format_row(recipe: Recipe, result: RecipeResult) -> str:
    details = result.details
    if len(details) > 120:
        details = details[:117] + '...'
    return f'{result.status:9} {recipe.path.name}  {recipe.behaviour}  {details}'


def _report(grouped: list[tuple[str, list[RecipeResult]]]) -> list[str]:
    """The report lines, grouped by WP, capped at REPORT_LINE_BUDGET lines (B5, E4)."""
    lines: list[str] = []
    overflow = 0
    for wp, results in grouped:
        group = [f'{wp}: {len(results)} recipe(s)']
        group.extend(_format_row(r.recipe, r) for r in results)
        if len(lines) + len(group) > REPORT_LINE_BUDGET:
            overflow += len(group)
            continue
        lines.extend(group)
    if overflow:
        lines = lines[:REPORT_LINE_BUDGET - 1]
        lines.append(f'... {overflow} more line(s) omitted')
    return lines


def _exit_code(results: list[RecipeResult]) -> int:
    statuses = {r.status for r in results}
    if statuses == {CAUGHT}:
        return 0
    if SURVIVED in statuses:
        return 1
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='python -P -m tools.audit.breaks',
        description='Run break recipes in scratch worktrees and check the named tests fail.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--wp', help='run only this WP\'s recipes')
    group.add_argument('--all', action='store_true', help='run every WP\'s recipes, grouped')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True,
                             text=True, check=True, timeout=60).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f'no recipes: not inside a git repository ({exc})', file=sys.stderr)
        return 2
    repo_root = Path(top)

    wps: list[str | None] = [args.wp] if args.wp else [None]
    if args.all:
        base = repo_root / BREAKS_DIR
        wps = sorted(d.name for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    if not wps:
        print('no recipes found', file=sys.stderr)
        return 2

    grouped: list[tuple[str, list[RecipeResult]]] = []
    for wp in wps:
        recipes = load_recipes(repo_root, wp)
        if not recipes:
            label = wp if wp else 'any WP'
            print(f'no recipes found for {label}', file=sys.stderr)
            return 2
        results = [run_recipe(recipe, repo_root) for recipe in recipes]
        grouped.append((recipes[0].wp, results))

    for line in _report(grouped):
        print(line)
    return _exit_code([r for _wp, results in grouped for r in results])


if __name__ == '__main__':
    sys.exit(main())
