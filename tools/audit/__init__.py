"""AQIS lab audit tooling: the audit gate (gate.py) and its pattern tables (patterns.py).

CAPABILITIES: none of its own (package marker; see gate.py and patterns.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: docs/tools/AUDIT_GATE.md describes the gate's command line and reports.
INVARIANTS:
  - Checks (a) to (d) match .claude/hooks/stop_gate.py (FR-0.0-06).
NOT IN SCOPE:
  - Running tests (the Stop hook and CI do that).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-05 created.
  2026-09-25 WP-0.0 round 2 F06: full header form.
"""
