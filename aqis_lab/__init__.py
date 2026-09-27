"""AQIS Test Lab package: run every lab command as `python -m aqis_lab <command>`.

CAPABILITIES:
  CAP-CLI-003: exposes the lab package version as aqis_lab.__version__ [tests: test_FR_0_0_01_version_prints_package_commit_python]
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: none.
INVARIANTS:
  - Importing aqis_lab never imports heavy or optional dependencies.
NOT IN SCOPE:
  - Command implementations (aqis_lab/commands/) and the dispatcher (aqis_lab/__main__.py).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-01 created.
"""

__version__ = "0.0.1"
