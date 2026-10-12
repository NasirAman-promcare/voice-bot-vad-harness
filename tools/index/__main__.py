"""Command line for the Lab Map index generator: build, check and impact.

CAPABILITIES:
  CAP-INDEX-006: `python -P -m tools.index build [--adopt-registry] [--out DIR]` scans the lab
  trees, adopts a hand-written registry into fragments when asked, builds the registry and
  writes MAP.md, SYMBOLS.md, CALLERS.md, TESTMAP.md and REGISTRY.md; `check` compares a scratch
  build with the working tree and names every differing or missing file, NO HEADER module and
  parse error; `impact --base REF` prints the affected pytest arguments, or `all` with a
  reason; failures (CapabilityRemoved, duplicate capabilities, bad fragments, adoption errors)
  exit 1 writing nothing, while parse errors still write and exit 1
  [tests: test_FR_1_0_03_build_writes_the_five_files_with_the_generated_line,
  test_FR_1_0_03_mc1_check_fails_when_a_header_changed_without_regeneration,
  test_FR_1_0_03_mc2_capability_removed_without_retirement_raises,
  test_FR_1_0_03_a_record_removed_without_retirement_raises,
  test_FR_1_0_03_a_capability_in_two_modules_is_an_error_naming_both,
  test_FR_1_0_03_test_file_headers_are_not_registry_sources,
  test_FR_1_0_03_mc3_impact_selects_the_tests_of_importers,
  test_FR_1_0_03_impact_through_a_package_counts_only_reexported_modules,
  test_FR_1_0_03_impact_of_a_deleted_module_selects_its_former_importers,
  test_FR_1_0_03_impact_answers_all_for_shared_test_infrastructure,
  test_FR_1_0_03_impact_answers_all_when_the_base_ref_is_missing,
  test_FR_1_0_03_mc4_output_is_byte_identical_regardless_of_file_order,
  test_FR_1_0_03_mc5_syntax_error_is_reported_with_path_line_and_others_still_indexed,
  test_FR_1_0_03_module_without_docstring_is_listed_and_fails_check,
  test_FR_1_0_03_pipes_in_a_description_keep_the_gate_columns,
  test_FR_1_0_03_adopt_registry_creates_records_and_retirements,
  test_FR_1_0_03_adopt_registry_refuses_a_retired_row_without_a_wp,
  test_FR_1_0_03_adopting_the_real_registry_accounts_for_every_legacy_row]
INPUTS AND OUTPUTS: argv in; files under docs/index/ and docs/capabilities/ (or --out), report
  lines on stdout, errors on stderr; exit 0 (clean), 1 (differences or failures), 2 (usage).
CONTRACTS: WO-1.0-03 B1, B7, B9, B10, B11 and B12 pins 1, 9, 10, 11, 13, 14 and 15; the git
  top-level of the current directory is the repository; PYTHONPATH supplies the package.
INVARIANTS:
  - Every path printed or written is repository-relative with `/` separators.
  - Registry failures write none of the five files (B12 pin 11); adoption checks run before
    any write and a refused adoption writes nothing at all (B12 pin 10).
  - Writes land only under docs/index/, docs/capabilities/ or the --out directory.
NOT IN SCOPE:
  - Scanning (scan.py), header parsing (headers.py), registry logic (registry.py), rendering
    (render.py) and impact selection (impact.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from tools.index.impact import ImpactError, affected_tests, render_impact
from tools.index.registry import (
    CapabilityRemoved,
    RegistryError,
    adopt_registry,
    build_registry,
)
from tools.index.render import ALL_PATHS, REGISTRY_PATH, render_all
from tools.index.scan import scan

__all__ = ['CliError', 'main', 'run_build', 'run_check', 'run_impact']


class CliError(Exception):
    """The command could not run: no repository root, or git refused a required read."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, timeout=120)


def _git_out(repo: Path, *args: str) -> str:
    proc = _git(repo, *args)
    if proc.returncode != 0:
        raise CliError(f"git {' '.join(args)} failed in {repo}: {proc.stderr.strip()}")
    return proc.stdout


def repo_root() -> Path:
    """The git top-level of the current directory (B12 pin 1); never the import location."""
    proc = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                          timeout=60)
    if proc.returncode != 0:
        raise CliError(f'not inside a git repository: {proc.stderr.strip()}')
    return Path(proc.stdout.strip())


def previous_registry_text(repo: Path) -> str | None:
    """The committed REGISTRY.md at HEAD (B12 pin 9); None when HEAD has none."""
    proc = _git(repo, 'show', f'HEAD:{REGISTRY_PATH}')
    if proc.returncode != 0:
        missing = (repo / REGISTRY_PATH)
        if _git(repo, 'rev-parse', '--verify', 'HEAD').returncode != 0:
            return None
        if not missing.exists() and _git(repo, 'cat-file', '-e',
                                         f'HEAD:{REGISTRY_PATH}').returncode != 0:
            return None
        return None
    return proc.stdout


def _write_outputs(base: Path, outputs: dict[str, str]) -> None:
    for rel in ALL_PATHS:
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(outputs[rel], encoding='utf-8', newline='')


def _write_fragments(repo: Path, fragments: dict[str, str]) -> None:
    for rel in sorted(fragments):
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fragments[rel], encoding='utf-8', newline='')


def _report_problems(facts) -> list[str]:
    """Parse errors (B9) and NO HEADER modules (E1), as report lines, sorted by path."""
    lines = []
    for fact in sorted(facts, key=lambda item: item.path):
        if fact.parse_error is not None:
            lines.append(fact.parse_error.render())
        elif fact.docstring is None:
            lines.append(f'NO HEADER: {fact.path}')
    return lines


def run_build(repo: Path, out_dir: Path | None, adopt: bool) -> int:
    """Build the five generated files; exit 1 on failures or parse errors (B9, B12 pin 11)."""
    facts = scan(repo)
    retired_dir = repo / 'docs/capabilities/retired.d'
    records_dir = repo / 'docs/capabilities/records.d'
    if adopt:
        registry_path = repo / REGISTRY_PATH
        if not registry_path.is_file():
            print(f'--adopt-registry needs a working-tree {REGISTRY_PATH}', file=sys.stderr)
            return 1
        try:
            fragments = adopt_registry(facts, registry_path.read_text(encoding='utf-8'),
                                       records_dir, retired_dir)
        except RegistryError as error:
            print(f'adoption refused: {error}', file=sys.stderr)
            return 1
        _write_fragments(repo, fragments)
        for rel in sorted(fragments):
            print(rel)
    try:
        registry = build_registry(facts, retired_dir, records_dir, previous_registry_text(repo))
    except CapabilityRemoved as error:
        print(str(error), file=sys.stderr)
        return 1
    except RegistryError as error:
        print(str(error), file=sys.stderr)
        return 1
    outputs = render_all(facts, registry)
    _write_outputs(out_dir if out_dir is not None else repo, outputs)
    problems = _report_problems(facts)
    for line in problems:
        print(line, file=sys.stderr)
    return 1 if any(fact.parse_error is not None for fact in facts) else 0


def run_check(repo: Path) -> int:
    """Compare a scratch build with the committed files (B10, B12 pin 13); never writes docs/."""
    import tempfile as scratch_space  # audit-allow: stdlib name

    facts = scan(repo)
    problems = _report_problems(facts)
    try:
        registry = build_registry(facts, repo / 'docs/capabilities/retired.d',
                                  repo / 'docs/capabilities/records.d', previous_registry_text(repo))
    except RegistryError as error:
        print(str(error), file=sys.stderr)
        return 1
    outputs = render_all(facts, registry)
    with scratch_space.TemporaryDirectory() as folder:
        scratch = Path(folder)
        _write_outputs(scratch, outputs)
        differing = []
        for rel in ALL_PATHS:
            committed = repo / rel
            if not committed.is_file():
                differing.append(rel)
                continue
            if committed.read_bytes() != (scratch / rel).read_bytes():
                differing.append(rel)
    for rel in differing:
        print(f'differs: {rel}')
    for line in problems:
        print(line)
    return 1 if differing or problems else 0


def run_impact(repo: Path, base_ref: str) -> int:
    """Print the affected pytest arguments, or `all` with a reason (B11, B12 pin 14)."""
    try:
        result = affected_tests(repo, base_ref)
    except ImpactError as error:
        print(f'all\nreason: impact could not run: {error}')
        return 0
    sys.stdout.write(render_impact(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tools.index',
                                     description='Lab Map index generator, registry and impact.')
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build', help='write the five generated files')
    build.add_argument('--adopt-registry', action='store_true',
                       help='migrate the hand-written registry into fragments first')
    build.add_argument('--out', type=Path, default=None,
                       help='write into DIR with the same relative layout instead of the repo')
    check = sub.add_parser('check', help='fail when the committed files differ from a fresh build')
    check.set_defaults(check=True)
    impact = sub.add_parser('impact', help='print the tests affected since a base ref')
    impact.add_argument('--base', required=True, help='base ref, for example main')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = repo_root()
    except CliError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.command == 'build':
        out_dir = args.out
        if out_dir is not None and not out_dir.is_absolute():
            out_dir = Path(os.getcwd()) / out_dir
        return run_build(repo, out_dir, args.adopt_registry)
    if args.command == 'check':
        return run_check(repo)
    return run_impact(repo, args.base)


if __name__ == '__main__':
    sys.exit(main())
