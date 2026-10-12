"""Autonomy tooling package: the deterministic merge gate and its helpers.

CAPABILITIES:
  CAP-AUTONOMY-001: package marker; the merge gate lives in merge_gate.py (later step)
    [tests: test_FR_1_0_05_dry_run_prints_all_seven_criteria_and_passes]
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: none.
INVARIANTS:
  - Importing this package starts no threads, runs no commands and writes nothing.
NOT IN SCOPE:
  - Merge gate logic (merge_gate.py), fact gathering (facts.py), criteria (criteria.py), GitHub access (github.py).
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 1 created.
"""

__all__: list[str] = []
