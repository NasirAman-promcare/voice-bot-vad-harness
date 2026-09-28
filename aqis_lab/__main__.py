"""Command dispatcher for `python -m aqis_lab <command> [arguments]`.

CAPABILITIES:
  CAP-CLI-001: dispatches a named command to its module, importing only that module; unknown or missing commands exit 2 with usage [tests: test_FR_0_0_01_dispatcher_rejects_unknown_command, test_FR_0_0_01_version_prints_package_commit_python]
INPUTS AND OUTPUTS: command-line arguments in; the chosen command's exit code out.
CONTRACTS: every command module exposes main(argv: list[str]) -> int.
INVARIANTS:
  - Command modules are imported lazily, so one command's dependencies never slow down or break another.
NOT IN SCOPE:
  - Argument parsing for individual commands (each command parses its own arguments).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-01 created.
  2026-09-27 WP-0.2 FR-0.2-04: `contracts` command registered in COMMANDS.
  2026-09-27 WP-0.3 FR-0.3-06: `score` command registered in COMMANDS.
  2026-09-27 WP-0.4 FR-0.4-01: `registry` command registered in COMMANDS.
  2026-09-27 WP-0.4 FR-0.4-05: `pack` command registered in COMMANDS.
  2026-09-28 WP-0.5 FR-0.5-02: `doctor` command registered in COMMANDS.
  2026-09-28 WP-0.5 FR-0.5-03: `drive` command registered in COMMANDS.
  2026-09-28 WP-0.5 FR-0.5-05: `run` command registered in COMMANDS.
  2026-09-28 WP-0.5 FR-0.5-07: `unitlog` command registered in COMMANDS.
"""
import argparse
import importlib
import sys

# name -> (module exposing main(argv), one-line help)
COMMANDS = {
    "version": ("aqis_lab.commands.version", "print the package version, git commit and Python version"),
    "contracts": ("aqis_lab.commands.contracts", "validate event logs, run cards and pack manifests (docs/contracts/)"),
    "score": ("aqis_lab.commands.score", "score transcripts: corpus WER and CER, Parquet and CSV score table"),
    "registry": ("aqis_lab.commands.registry", "fetch source datasets, build and validate the source registry"),
    "pack": ("aqis_lab.commands.pack", "build a test pack from a pack spec, or verify a built pack"),
    "doctor": ("aqis_lab.commands.doctor", "check Python, lock, disk, RAM, GPU and Drive; PASS/FAIL report"),
    "drive": ("aqis_lab.commands.drive", "create the Google Drive AQIS_LAB folder layout; report crowded folders"),
    "run": ("aqis_lab.commands.run", "run a task over a pack in resumable shards (copy then compute)"),
    "unitlog": ("aqis_lab.commands.unitlog", "Colab session compute-unit log (start, end)"),
}


def build_parser():
    epilog = "commands:\n" + "\n".join(f"  {name:<12} {text}" for name, (_, text) in sorted(COMMANDS.items()))
    parser = argparse.ArgumentParser(prog="python -m aqis_lab", description="AQIS Test Lab command line.",
                                     epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=sorted(COMMANDS), help="command to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments for the command")
    return parser


def main(argv=None):
    ns = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    module = importlib.import_module(COMMANDS[ns.command][0])
    return module.main(ns.args)


if __name__ == "__main__":
    sys.exit(main())
