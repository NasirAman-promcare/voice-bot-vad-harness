"""Unit tests for tools.outsourcing.relay.

CAPABILITIES:
  CAP-OUTSOURCING-RELAY: Main entry point for running relay work orders, dry-runs, status checks, and model checks. [tests: test_relay.py]
INPUTS AND OUTPUTS: Test cases for relay main entry point.
CONTRACTS: none.
INVARIANTS:
  - Unit tests run fast.
NOT IN SCOPE:
  - External network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

import sys
from pathlib import Path

from tools.outsourcing.relay import main, run


def test_relay_main_help(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
