"""Command line for tools.progress: build, check, lint, migrate and new-id.

CAPABILITIES:
  CAP-PROGRESS-009: command line for the progress tooling
    [tests: test_FR_1_0_04_mc03_mc07_migration_round_trip_is_byte_identical,
    test_FR_1_0_04_mc03_dry_run_lists_every_legacy_id,
    test_FR_1_0_04_mc03_every_legacy_id_has_a_fragment_holding_its_text,
    test_FR_1_0_04_mc03_migration_refuses_when_a_target_exists, test_FR_1_0_04_mc07_memo_readers_see_the_same_rows,
    test_FR_1_0_04_mc01_blocker_without_valid_capability_fails_lint, test_FR_1_0_04_mc01_valid_blocker_passes_lint,
    test_FR_1_0_04_mc01_blocker_with_more_than_seven_steps_fails_lint,
    test_FR_1_0_04_mc02_id_differing_from_file_name_fails_lint,
    test_FR_1_0_04_mc02_duplicate_ids_fail_lint_naming_both_paths,
    test_FR_1_0_04_mc02_new_id_takes_the_next_free_number,
    test_FR_1_0_04_mc04_owner_queue_orders_blockers_by_unmerged_wps,
    test_FR_1_0_04_mc05_rendering_is_byte_identical_across_runs_and_file_order,
    test_FR_1_0_04_mc06_on_main_renders_merged, test_FR_1_0_04_check_fails_when_a_table_is_stale,
    test_FR_1_0_04_status_for_a_wp_without_spec_is_a_warning]
INPUTS AND OUTPUTS: argv and the repository root (from git rev-parse --show-toplevel);
  writes generated tables on build, prints reports on lint/migrate/new-id, sets the exit code.
CONTRACTS: fragment formats v1 (docs/process/templates/FRAGMENTS.md, BLOCKER.md, DECISION.md);
  generated-table layout v1 (legacy STATUS.md, BLOCKERS.md, DEBT.md).
INVARIANTS:
  - check writes only into a scratch folder.
  - build and check fail on any FragmentError.
  - lint exits 1 only on errors; warnings are printed.
  - migrate refuses (non-zero) when any target file exists and writes nothing then.
NOT IN SCOPE:
  - Parsing, linting, rendering, ID allocation and migration logic (separate modules).
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 6 created.
  2026-10-12 WP-1.0 WO-1.0-04 (Claude, FIX-WO04-final): lint passes the WPs with a spec under docs/specs/ (E4 warning).
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not a file (gate E3).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.progress import fragments as fragments_module
from tools.progress import ids as ids_module
from tools.progress import lint as lint_module
from tools.progress import migrate as migrate_module
from tools.progress import render as render_module

__all__ = ["main"]

GENERATED_RELATIVE_PATHS = (
    Path("docs/progress/STATUS.md"),
    Path("docs/progress/BLOCKERS.md"),
    Path("docs/progress/DEBT.md"),
    Path("docs/progress/DECISIONS.md"),
    Path("docs/progress/OWNER_QUEUE.md"),
    Path("docs/outsourcing/LEDGER.md"),
)

DIGEST_RE = re.compile(r"^Last digest: (\d{4}-\d{2}-\d{2})\s*$", re.M)


class CliError(Exception):
    """A command could not run; the message says what failed and what to do."""


def _repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CliError(
            "not inside a git repository (git rev-parse --show-toplevel failed); "
            "run tools.progress from within the repository"
        )
    return Path(proc.stdout.strip())


def _out_root(repo_root: Path, out: str | None) -> Path:
    if out is None:
        return repo_root
    target = Path(out)
    return target if target.is_absolute() else repo_root / target


def _last_digest(repo_root: Path) -> str | None:
    queue = repo_root / "docs/progress/OWNER_QUEUE.md"
    if not queue.is_file():
        return None
    match = DIGEST_RE.search(queue.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _load(repo_root: Path) -> fragments_module.Fragments:
    try:
        return fragments_module.load_all(repo_root)
    except fragments_module.FragmentError as exc:
        raise CliError(str(exc)) from exc


def _write_tables(tables: dict[Path, str], out_root: Path) -> None:
    for rel, text in tables.items():
        target = out_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="")


def _cmd_build(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    fragments = _load(repo_root)
    last_digest = _last_digest(repo_root) if not args.on_main else None
    tables = render_module.render_all(fragments, on_main=args.on_main, last_digest=last_digest)
    _write_tables(tables, _out_root(repo_root, args.out))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    fragments = _load(repo_root)
    scratch = Path(tempfile.mkdtemp(prefix="aqis-progress-check-"))
    try:
        tables = render_module.render_all(
            fragments, on_main=True, last_digest=_last_digest(repo_root)
        )
        _write_tables(tables, scratch)
        stale: list[str] = []
        for rel in GENERATED_RELATIVE_PATHS:
            committed = repo_root / rel
            generated = (scratch / rel).read_text(encoding="utf-8")
            if not committed.is_file() or committed.read_text(encoding="utf-8") != generated:
                stale.append(rel.as_posix())
    finally:
        shutil.rmtree(scratch)
    if stale:
        for rel in stale:
            print(f"STALE: {rel} (run: python -m tools.progress build --on-main)")
        return 1
    print("OK: generated tables are up to date")
    return 0


def _changed_paths(repo_root: Path, ref: str) -> set[Path]:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if base.returncode != 0:
        raise CliError(
            f"cannot find the merge base with {ref!r}; fetch the ref or name an existing one"
        )
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base.stdout.strip(), "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode != 0:
        raise CliError(f"git diff against {ref!r} failed: {diff.stderr.strip()}")
    return {repo_root / line for line in diff.stdout.splitlines() if line.strip()}


def _cmd_lint(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    fragments = _load(repo_root)
    changed = None
    if args.changed_from is not None:
        changed = _changed_paths(repo_root, args.changed_from)
    specs = repo_root / "docs" / "specs"
    spec_wps = {m.group(1) for p in specs.rglob("WP-*.md") if (m := re.match(r"(WP-\d+\.\d+)", p.name))}
    issues = lint_module.lint(fragments, changed_only_paths=changed, spec_wps=spec_wps)
    errors = 0
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")
        if issue.severity == "error":
            errors += 1
    return 1 if errors else 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    try:
        report = migrate_module.migrate(repo_root, dry_run=args.dry_run)
    except migrate_module.MigrationError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(report.summary())
    return 0


def _cmd_new_id(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    try:
        print(ids_module.next_id(args.kind, args.wp, repo_root))
    except ids_module.IdError as exc:
        raise CliError(str(exc)) from exc
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.progress",
        description="Progress fragments: build tables, check, lint, migrate, new-id.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="render the generated tables")
    build.add_argument("--on-main", action="store_true", help="render as on main (AUDIT-PASS and MERGE-READY become MERGED)")
    build.add_argument("--out", default=None, help="output root (absolute or relative to the repository root)")
    build.set_defaults(handler=_cmd_build)

    check = sub.add_parser("check", help="fail if the committed tables are stale")
    check.set_defaults(handler=_cmd_check)

    lint = sub.add_parser("lint", help="validate fragments")
    lint.add_argument("--changed-from", dest="changed_from", default=None,
                      help="lint only fragments changed since the merge base with REF (uniqueness still checks all)")
    lint.set_defaults(handler=_cmd_lint)

    migrate = sub.add_parser("migrate", help="one-time migration of the legacy tables")
    migrate.add_argument("--dry-run", action="store_true", help="print what would be created without writing")
    migrate.set_defaults(handler=_cmd_migrate)

    new_id = sub.add_parser("new-id", help="print the next free ID for a kind and WP")
    new_id.add_argument("--kind", required=True, help="BLK, DEC, DEBT or WO")
    new_id.add_argument("--wp", required=True, help="the work package ID, e.g. WP-1.3")
    new_id.set_defaults(handler=_cmd_new_id)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.handler(args)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
