"""Timing support: keep timing runs on reserved CPU cores and batch runs off them.

CAPABILITIES: none of its own (package marker; see cores.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: run-card v1 `mode`; config/aqis_lab/oracle.yaml `cores`.
INVARIANTS:
  - Importing the package imports none of its modules.
NOT IN SCOPE:
  - The real-speed feeder and timing measurements (WP-0.7).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-04 created.
"""
