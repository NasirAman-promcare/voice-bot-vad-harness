"""Unit test package for the break suite runner and mutation report (WO-1.0-06).

CAPABILITIES:
  CAP-AUDIT-TEST-000: marks tests/aqis_lab/audit_breaks/ as a Python test package so the
  break-runner, mutation-engine and mutation-report unit tests are collected together
  [tests: tests/aqis_lab/audit_breaks/test_breaks.py,
  tests/aqis_lab/audit_breaks/test_mutate.py,
  tests/aqis_lab/audit_breaks/test_mutation_report.py]
INPUTS AND OUTPUTS: nothing in; package membership out.
CONTRACTS: docs/process/CHANGE_CONTROL.md module header standard; WO-1.0-06 section 3.
INVARIANTS:
  - Importing this package has no side effects.
  - This file holds no test logic; tests live in test_*.py modules beside it.
NOT IN SCOPE:
  - Scratch repository construction (each test module builds its own).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-06 created.
  2026-10-12 WP-1.0 FR-1.0-06 fix 1: full module header standard added."""
