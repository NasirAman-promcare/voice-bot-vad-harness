"""Unit tests for tools.index (WO-1.0-03).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest collects tests from this package.
CONTRACTS: none.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness; scratch git repositories only.
NOT IN SCOPE:
  - Acceptance tests (tests/aqis_lab/index/test_acceptance_wo_1_0_03.py, read-only).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
"""
from __future__ import annotations
