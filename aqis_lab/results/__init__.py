"""Results store: append-only Parquet files partitioned by run_card_id, with DuckDB views (WP-0.6).

CAPABILITIES: none of its own (package marker; see store.py, ingest.py and views.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: store layout and schema in docs/results/RESULTS_STORE.md.
INVARIANTS:
  - Importing the package imports none of its modules.
NOT IN SCOPE:
  - Copying the store to Google Drive (aqis_lab/sync.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-02 created.
"""
