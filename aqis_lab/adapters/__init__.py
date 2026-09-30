"""Model adapters: the components the lab tests, each behind one contract (aqis_lab/adapters/base.py).

CAPABILITIES:
  CAP-ADAPT-000: package marker; the adapters are imported from their own modules so that one adapter's
    dependencies (NeMo and torch for Parakeet) never load for another [tests: test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter]
INPUTS AND OUTPUTS: none.
CONTRACTS: event-log v1, run-card v1 `model` block.
INVARIANTS:
  - Importing this package imports no adapter module.
NOT IN SCOPE:
  - Running adapters over a pack (aqis_lab/runner/tasks.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-01 created.
"""
