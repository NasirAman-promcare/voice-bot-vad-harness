"""Source registry: datasets and licences, acquisition, import into data/registry/sources.csv, and validation.

CAPABILITIES: none of its own (package marker; see the modules of this package and docs/data/REGISTRY_FORMAT.md).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: registry format and datasets.yaml format 1 (docs/data/REGISTRY_FORMAT.md).
INVARIANTS:
  - Importing the package imports none of its modules.
NOT IN SCOPE:
  - Building packs (aqis_lab/packs/).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-01 created.
"""
