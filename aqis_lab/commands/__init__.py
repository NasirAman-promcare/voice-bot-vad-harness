"""Command modules for `python -m aqis_lab`; each exposes main(argv) -> int.

CAPABILITIES: none of its own (package marker; the commands are listed in aqis_lab/__main__.py COMMANDS).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: every module in this package exposes main(argv: list[str]) -> int.
INVARIANTS:
  - Importing the package imports no command module.
NOT IN SCOPE:
  - Command logic (each command module), dispatch (aqis_lab/__main__.py).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-01 created.
  2026-09-25 WP-0.0 round 2 F06: full header form.
"""
