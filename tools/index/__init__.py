"""Lab Map index generator: scan, headers, registry, rendering and impact selection.

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: package marker; the command line is `python -P -m tools.index`.
CONTRACTS: module header standard in docs/process/CHANGE_CONTROL.md section 1.
INVARIANTS:
  - Importing this package has no side effects; submodules do the work.
NOT IN SCOPE:
  - Scanning (scan.py), registry (registry.py), rendering (render.py), impact (impact.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
"""
from __future__ import annotations

__all__ = ["headers", "scan", "registry", "render", "impact"]
