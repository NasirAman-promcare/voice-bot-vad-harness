"""The `version` command: package version, short git commit (+dirty) and Python version.

CAPABILITIES:
  CAP-CLI-002: prints `aqis_lab <version> commit=<short>[+dirty] python=<x.y.z>` and exits 0; exits 1 with an ERROR line when the commit cannot be determined [tests: test_FR_0_0_01_version_prints_package_commit_python, test_FR_0_0_01_version_marks_dirty_tree, test_FR_0_0_01_version_fails_loudly_outside_git]
INPUTS AND OUTPUTS: reads git state of the repository that contains this package; one line to stdout.
CONTRACTS: none.
INVARIANTS:
  - The repository is the one holding this package (two levels above this file), never the caller's cwd.
  - "+dirty" means tracked changes or untracked files that are not ignored (owner decision, WP-0.0 plan).
  - A missing git, or a package not at the top of a git checkout, is an error, never an "unknown" commit.
NOT IN SCOPE:
  - Recording versions into run cards (WP-0.2).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-01 created.
"""
import argparse
import platform
import subprocess
import sys
from pathlib import Path

import aqis_lab


class VersionInfoError(RuntimeError):
    """The git commit of the lab checkout could not be determined."""


def repo_root():
    return Path(__file__).resolve().parents[2]


def _git(root, *args):
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise VersionInfoError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise VersionInfoError(f"git {' '.join(args)} timed out") from exc
    if proc.returncode != 0:
        raise VersionInfoError(f"git {' '.join(args)} failed in {root}: {proc.stderr.strip() or 'no message'}")
    return proc.stdout.strip()


def git_commit(root):
    """Return (short commit, dirty) for the checkout rooted at root."""
    toplevel = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    if toplevel != Path(root).resolve():
        raise VersionInfoError(f"{root} is inside the git checkout {toplevel} but is not its top level")
    short = _git(root, "rev-parse", "--short", "HEAD")
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=normal"))
    return short, dirty


def version_line():
    short, dirty = git_commit(repo_root())
    return f"aqis_lab {aqis_lab.__version__} commit={short}{'+dirty' if dirty else ''} python={platform.python_version()}"


def main(argv):
    parser = argparse.ArgumentParser(prog="python -m aqis_lab version",
                                     description="Print the package version, short git commit and Python version.")
    parser.parse_args(argv)
    try:
        line = version_line()
    except VersionInfoError as exc:
        print(f"ERROR: cannot determine the git commit: {exc}", file=sys.stderr)
        return 1
    print(line)
    return 0
