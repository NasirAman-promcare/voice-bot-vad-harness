"""CLI entry point for AQIS lab outsourcing subcommands.

CAPABILITIES:
  CAP-OUTSOURCING-009: command-line interface for validate, import, scope and pack
    [tests: test_FR_1_0_01_cli_import_succeeds_with_exit_0, test_FR_1_0_01_cli_validate, test_FR_1_0_01_cli_import,
    test_FR_1_0_01_cli_scope, test_FR_1_0_01_cli_pack]
INPUTS AND OUTPUTS: main(argv) -> int.
CONTRACTS: CLI interface with exit codes 0 to 6.
INVARIANTS:
  - Prints at most 25 lines.
  - Returns exit code 0 to 6 per exception type.
NOT IN SCOPE:
  - Interactive prompts.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
  2026-10-10 WP-1.0 FR-1.0-01 review fix (Claude): a git failure is reported (RepositoryError, exit 2) instead of
    falling back to the current directory; an unreadable bundle exits 3; PackTooLarge and read errors exit 2.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tools.outsourcing.bundle import BundleError, TruncatedBundle, parse_bundle
from tools.outsourcing.importer import ImportRefused, QuestionsReturned, import_bundle
from tools.outsourcing.pack import PackTooLarge, SecretRefused, build_pack
from tools.outsourcing.scope import ScopeError, check_scope
from tools.outsourcing.workorder import WorkOrderError, load_work_order, plan_steps

__all__ = ["main"]


class RepositoryError(Exception):
    """Raised when the current directory is not inside a git checkout (exit code 2)."""


def _get_repo_root() -> Path:
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError(f"git rev-parse --show-toplevel could not run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RepositoryError(f"not inside a git repository ({proc.stderr.strip()}); run from the repository checkout")
    return Path(proc.stdout.strip()).resolve()


def _read_bundle(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise BundleError(f"cannot read bundle {path}: {exc}") from exc


def _truncate_output(text: str, max_lines: int = 25) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:max_lines]) if len(lines) > max_lines else text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.outsourcing")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    val = sub.add_parser("validate")
    val.add_argument("--wo", required=True)

    imp = sub.add_parser("import")
    imp.add_argument("--wo", required=True)
    imp.add_argument("--bundle", required=True)
    imp.add_argument("--mode", choices=["first", "fix"], default="first")
    imp.add_argument("--step", type=int)
    imp.add_argument("--dry-run", action="store_true")

    sc = sub.add_parser("scope")
    sc.add_argument("--wo", required=True)
    sc.add_argument("--base", default="origin/main")
    sc.add_argument("--head", default="HEAD")

    pk = sub.add_parser("pack")
    pk.add_argument("--wo", required=True)
    pk.add_argument("--out")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out: list[str] = []

    try:
        root = _get_repo_root()
        if args.subcommand == "validate":
            order = load_work_order(args.wo, root)
            steps = plan_steps(order)
            out.append(f"Work order {order.id} is valid ({len(steps)} steps):")
            out.extend(f"Step {s.number}: {', '.join(s.paths)}" for s in steps)

        elif args.subcommand == "import":
            order = load_work_order(args.wo, root)
            exp: set[str] | None = None
            if args.step is not None:
                steps = plan_steps(order)
                if not (1 <= args.step <= len(steps)):
                    raise WorkOrderError(f"Step {args.step} out of bounds")
                exp = set(steps[args.step - 1].paths)

            b_text = _read_bundle(args.bundle)
            bundle = parse_bundle(b_text)
            report = import_bundle(bundle, order, root, mode=args.mode, dry_run=args.dry_run, expected=exp)
            out.append(f"Imported {len(report.files)} file(s) successfully.")
            out.extend(f"  {f.path} ({f.bytes} bytes, {f.lines} lines, sha256: {f.sha256[:8]})" for f in report.files)

        elif args.subcommand == "scope":
            order = load_work_order(args.wo, root)
            report = check_scope(order, root, base_ref=args.base, head_ref=args.head)
            if report.violations:
                print(_truncate_output("\n".join(report.violations)))
                return 1
            out.append("Scope check passed: no violations.")

        elif args.subcommand == "pack":
            order = load_work_order(args.wo, root)
            pack = build_pack(order, root)
            if args.out:
                p = Path(args.out)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(pack.text, encoding="utf-8")
            out.append(f"Pack built: {pack.characters} characters, est. {pack.estimated_tokens} tokens.")

    except (WorkOrderError, RepositoryError, PackTooLarge, OSError) as exc:
        print(f"Error [2]: {exc}", file=sys.stderr)
        return 2
    except QuestionsReturned as exc:
        print(f"Error [4]: {exc}", file=sys.stderr)
        return 4
    except TruncatedBundle as exc:
        print(f"Error [5]: {exc}", file=sys.stderr)
        return 5
    except (BundleError, ImportRefused) as exc:
        print(f"Error [3]: {exc}", file=sys.stderr)
        return 3
    except SecretRefused as exc:
        print(f"Error [6]: {exc}", file=sys.stderr)
        return 6
    except ScopeError as exc:
        print(f"Error [1]: {exc}", file=sys.stderr)
        return 1

    if out:
        print(_truncate_output("\n".join(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
