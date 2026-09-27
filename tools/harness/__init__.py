"""AQIS lab tools for the existing VAD harness (run modules as `python -m tools.harness.<module>`).

CAPABILITIES: none of its own (package marker; see regression_check.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: none.
INVARIANTS:
  - Standard library only (NFR-0.0-03), so the tools run in .venv-harness or any Python 3.10+.
NOT IN SCOPE:
  - Changing harness code or tests (they are protected).
CHANGE LOG:
  2026-09-25 WP-0.0 round 2 FR-0.0-11 created.
"""
