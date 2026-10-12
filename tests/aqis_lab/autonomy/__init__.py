"""Autonomy test package for the merge gate.

CAPABILITIES:
  CAP-AUTONOMY-002: package marker; merge gate unit tests live in test_*.py (later steps)
    [tests: test_FR_1_0_05_dry_run_prints_all_seven_criteria_and_passes]
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: none.
INVARIANTS:
  - Importing this package starts no threads, runs no commands and writes nothing.
NOT IN SCOPE:
  - The stand-in gh program (stand_in_gh.py) and the test modules.
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 1 created.
"""

__all__: list[str] = []
