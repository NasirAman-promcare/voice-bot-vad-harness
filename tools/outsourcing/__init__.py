"""AQIS lab outsourcing tools package.

CAPABILITIES:
  CAP-OUTSOURCING-001: package entry point and version string [tests: test_paths.py]
INPUTS AND OUTPUTS: __version__ string export.
CONTRACTS: none.
INVARIANTS:
  - __version__ is a valid semver string.
NOT IN SCOPE:
  - Command line execution (see tools.outsourcing.__main__).
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
