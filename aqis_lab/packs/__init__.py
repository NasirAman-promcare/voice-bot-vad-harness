"""Pack builder and verifier: seeded selection, clip rendering, normalised tar shards, manifests and LICENCES.md.

CAPABILITIES: none of its own (package marker; see the modules of this package and docs/data/SMOKE_PACK.md).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: pack-manifest v1 (docs/contracts/PACK_MANIFEST.md); recipe v1 and the pack layout (docs/data/SMOKE_PACK.md).
INVARIANTS:
  - Importing the package imports none of its modules.
NOT IN SCOPE:
  - The source registry (aqis_lab/registry/).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-05 created.
"""
