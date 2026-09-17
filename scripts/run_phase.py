#!/usr/bin/env python3
"""
Voice Bot VAD Test Harness — Repo Phase Runner
File: scripts/run_phase.py
Cross-cutting Infrastructure · All Tiers

One Job:
    Provides a thin, unified command-line entry point to manage requirements installation
    and execution across the harness lifecycle phases: `corpus`, `tier1`, `tier2`, and `report`.

What This Module Never Touches:
    - Never opens or reads `config/run_config.yaml` or `corpus/corpus_build_config.yaml`.
    - Never imports `orchestrator.py`, `manifest.py`, or any of the 20 architecture modules.
    - Never implements fetch-vs-build logic for data (delegated strictly to `dataset_builder.py`).
    - Never contains hardcoded API tokens or environment secrets.

Usage:
    python scripts/run_phase.py list
    python scripts/run_phase.py install <phase | all>
    python scripts/run_phase.py run <phase>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


# ==============================================================================
# Phase Definitions & Registry
# ==============================================================================
@dataclass(frozen=True)
class PhaseDefinition:
    name: str
    description: str
    entry_point_type: str  # 'module' or 'notebook'
    entry_target: str
    requirements_file: str
    extra_args: Optional[List[str]] = None
    notes: str = ""


# Root directory of the repository (scripts/ is one level down)
REPO_ROOT = Path(__file__).resolve().parent.parent

BASE_REQUIREMENTS = REPO_ROOT / "requirements" / "base.txt"

PHASES: Dict[str, PhaseDefinition] = {
    "corpus": PhaseDefinition(
        name="corpus",
        description="Fetch pre-built corpus or synthesize/mix 16kHz audio dataset from raw sources.",
        entry_point_type="module",
        entry_target="corpus.dataset_builder",
        requirements_file="requirements/corpus.txt",
        extra_args=["--config", "corpus/corpus_build_config.yaml"],
        notes="One-time build per corpus version; delegates fetch-vs-build to dataset_builder.py.",
    ),
    "tier1": PhaseDefinition(
        name="tier1",
        description="Offline benchmark: Run all active VAD adapters against local audio corpus.",
        entry_point_type="notebook",
        entry_target="notebooks/01_tier1_offline_bench.ipynb",
        requirements_file="requirements/tier1.txt",
        notes="Zero network, single process; evaluates algorithmic latency and detection accuracy.",
    ),
    "tier2": PhaseDefinition(
        name="tier2",
        description="Live pipeline: Stream corpus through Jitsi bridge with Speaker/Listener bots.",
        entry_point_type="notebook",
        entry_target="notebooks/02_tier2_live_pipeline.ipynb",
        requirements_file="requirements/tier2.txt",
        notes="Requires live bridge/tunnel; measures physical onset and hangover latency.",
    ),
    "report": PhaseDefinition(
        name="report",
        description="Generate comparison tables, weakness heatmaps, and sensitivity curves.",
        entry_point_type="notebook",
        entry_target="notebooks/03_report.ipynb",
        requirements_file="requirements/report.txt",
        notes="Reads results_store.py durable records; re-run freely after any benchmark pass.",
    ),
}

VALID_PHASE_NAMES = list(PHASES.keys())
VALID_INSTALL_TARGETS = VALID_PHASE_NAMES + ["all"]


# ==============================================================================
# Subcommand Implementations
# ==============================================================================
def cmd_list() -> int:
    """Prints formatted summary of all available phases, requirements, and targets."""
    print("=" * 80)
    print(" Voice Bot VAD Test Harness — Lifecycle Phases")
    print("=" * 80)
    for name, phase in PHASES.items():
        print(f"\nPhase: {name.upper()}")
        print(f"  Description:  {phase.description}")
        print(f"  Type:         {phase.entry_point_type}")
        print(f"  Entry Point:  {phase.entry_target}")
        print(f"  Requirements: {phase.requirements_file} (+ requirements/base.txt)")
        if phase.notes:
            print(f"  Notes:        {phase.notes}")
    print("\n" + "=" * 80)
    return 0


def _install_file(req_path: Path) -> int:
    """Invokes pip to install a specific requirements file with error validation."""
    if not req_path.is_file():
        print(
            f"ERROR: Requirements file not found at expected path: {req_path.resolve()}",
            file=sys.stderr,
        )
        return 1

    print(f"--> Installing dependencies from: {req_path.relative_to(REPO_ROOT)}")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_path)]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, check=True)
        return proc.returncode
    except subprocess.CalledProcessError as e:
        print(f"ERROR: pip install failed for {req_path.name} (exit code {e.returncode})", file=sys.stderr)
        return e.returncode


def cmd_install(target: str) -> int:
    """
    Installs base requirements plus targeted phase requirements.
    Supports 'install <phase>' for isolated environments and 'install all' for full sessions.
    """
    normalized_target = target.strip().lower()
    if normalized_target not in VALID_INSTALL_TARGETS:
        print(
            f"ERROR: Unrecognized install target '{target}'.\n"
            f"Valid options are: {', '.join(VALID_INSTALL_TARGETS)}",
            file=sys.stderr,
        )
        return 1

    # 1. Base requirements always installed
    ret = _install_file(BASE_REQUIREMENTS)
    if ret != 0:
        return ret

    # 2. Phase-specific or All requirements
    if normalized_target == "all":
        for phase in PHASES.values():
            req_file = REPO_ROOT / phase.requirements_file
            ret = _install_file(req_file)
            if ret != 0:
                return ret
        print("\nSUCCESS: All harness phase requirements successfully installed.")
        return 0

    phase = PHASES[normalized_target]
    phase_req = REPO_ROOT / phase.requirements_file
    ret = _install_file(phase_req)
    if ret == 0:
        print(f"\nSUCCESS: Phase '{normalized_target}' requirements successfully installed.")
    return ret


def cmd_run(phase_name: str) -> int:
    """
    Executes the designated entry point for the specified phase.
    Propagates non-zero exit codes with transparent stdout/stderr streaming.
    """
    normalized_name = phase_name.strip().lower()
    if normalized_name not in PHASES:
        print(
            f"ERROR: Unrecognized phase name '{phase_name}'.\n"
            f"Valid phases to run are: {', '.join(VALID_PHASE_NAMES)}",
            file=sys.stderr,
        )
        return 1

    phase = PHASES[normalized_name]
    print(f"================================================================================")
    print(f" Executing Phase: {phase.name.upper()} — {phase.description}")
    print(f"================================================================================")

    if phase.entry_point_type == "module":
        cmd = [sys.executable, "-m", phase.entry_target]
        if phase.extra_args:
            cmd.extend(phase.extra_args)

        print(f"--> Invoking CLI Command: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            return proc.returncode
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: Module execution failed for '{phase.entry_target}' (exit code {e.returncode})", file=sys.stderr)
            return e.returncode

    elif phase.entry_point_type == "notebook":
        nb_path = REPO_ROOT / phase.entry_target
        if not nb_path.is_file():
            print(f"ERROR: Target notebook not found at: {nb_path.resolve()}", file=sys.stderr)
            return 1

        cmd = [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
                                    str(nb_path),
        ]

        print(f"--> Executing Notebook in-place: {nb_path.relative_to(REPO_ROOT)}")
        try:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            print(f"\nSUCCESS: Notebook '{phase.entry_target}' completed successfully.")
            return proc.returncode
        except subprocess.CalledProcessError as e:
            print(
                f"\nERROR: Notebook execution failed for '{phase.entry_target}' (exit code {e.returncode}).\n"
                f"Review notebook cell trace above for specific assertion/runtime details.",
                file=sys.stderr,
            )
            return e.returncode

    return 0


# ==============================================================================
# CLI Parsing Interface
# ==============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_phase",
        description="Voice Bot VAD Test Harness — Lifecycle & Phase Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Subcommand to execute")

    # 'list' subcommand
    subparsers.add_parser("list", help="List all available harness phases, targets, and requirements")

    # 'install' subcommand
    parser_install = subparsers.add_parser(
        "install", help="Install requirements for a specific phase or all phases"
    )
    parser_install.add_argument(
        "phase",
        type=str,
        help=f"Target phase to install ({', '.join(VALID_INSTALL_TARGETS)})",
    )

    # 'run' subcommand
    parser_run = subparsers.add_parser("run", help="Execute the target phase entry point")
    parser_run.add_argument(
        "phase",
        type=str,
        help=f"Phase to execute ({', '.join(VALID_PHASE_NAMES)})",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "list":
        sys.exit(cmd_list())
    elif args.subcommand == "install":
        sys.exit(cmd_install(args.phase))
    elif args.subcommand == "run":
        sys.exit(cmd_run(args.phase))
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()