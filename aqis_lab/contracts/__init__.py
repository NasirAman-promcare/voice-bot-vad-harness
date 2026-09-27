"""AQIS lab contracts: the event log, run card and pack manifest every lab module speaks (WP-0.2).

CAPABILITIES: none of its own (package marker; validators in aqis_lab/contracts/validate.py, canonical JSON
  and IDs in aqis_lab/contracts/canonical.py, JSON Schema files in aqis_lab/contracts/schemas/).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: event-log v1, run-card v1, pack-manifest v1 (documents in docs/contracts/).
INVARIANTS:
  - Importing the package imports no submodule, so it never loads jsonschema by itself.
NOT IN SCOPE:
  - Producing records (runner, adapters and pack builder in later work packages).
CHANGE LOG:
  2026-09-27 WP-0.2 FR-0.2-01 created.
"""
