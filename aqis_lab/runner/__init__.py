"""Resumable runner: copy a pack to local disk, split a run into shards, write each shard atomically, resume.

CAPABILITIES: none of its own (package marker; see stage.py, tasks.py, card.py, plan.py, store.py and run.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: run-card v1, pack-manifest v1; run folder layout in docs/runner/RUNNER.md.
INVARIANTS:
  - Importing the package imports none of its modules.
NOT IN SCOPE:
  - Model adapters (WP-0.7), the results store (WP-0.6).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-04 created.
"""
