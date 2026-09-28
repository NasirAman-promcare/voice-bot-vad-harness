"""DuckDB views over the results store: result_rows, run_cards, and results (every row joined to its run card).

CAPABILITIES:
  CAP-RESULTS-005: connect() opens an in-memory DuckDB connection (extension installs and autoloading switched off; parquet and json are built in) with the views result_rows (every stored part file), run_cards (every stored run card, key fields extracted) and results (result_rows joined to run_cards: pack manifest ID, version and SHA-256, git commit and dirty flag, lock file and SHA-256, mode); query_run_card() returns a run card's rows through the view, each row checked [tests: test_FR_0_6_02_duckdb_view_equals_stored_files, test_FR_0_6_02_duckdb_needs_no_network, test_FR_0_6_02_query_returns_rows_for_run_card, test_FR_0_6_02_interrupted_add_leaves_no_row]
INPUTS AND OUTPUTS: a store folder in; a DuckDB connection or a list of row dicts out; StoreInputError when there is
  no store, StoreIntegrityError when a stored row does not check.
CONTRACTS: store layout and view definitions in docs/results/RESULTS_STORE.md.
INVARIANTS:
  - Read-only: nothing in the store is written; `.partial` files are never read.
  - No network: DuckDB never installs or downloads an extension.
NOT IN SCOPE:
  - Writing the store (aqis_lab/results/store.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-02 created.
"""
from pathlib import Path

import duckdb

from aqis_lab.results import store

DUCKDB_CONFIG = {"autoinstall_known_extensions": False, "autoload_known_extensions": False}
CARD_FIELDS = (
    ("run_card_id", "json_extract_string(content, '$.run_card_id')"),
    ("pack_manifest_id", "json_extract_string(content, '$.pack.manifest_id')"),
    ("pack_version", "json_extract_string(content, '$.pack.version')"),
    ("pack_sha256", "json_extract_string(content, '$.pack.sha256')"),
    ("git_commit", "json_extract_string(content, '$.git.commit')"),
    ("git_dirty", "CAST(json_extract(content, '$.git.dirty') AS BOOLEAN)"),
    ("lock_file", "json_extract_string(content, '$.lock.file')"),
    ("lock_sha256", "json_extract_string(content, '$.lock.sha256')"),
    ("mode", "json_extract_string(content, '$.mode')"),
    ("card_json", "content"),
    ("card_file", "filename"),
)


def _sql_text(value):
    return "'" + str(value).replace("'", "''") + "'"


def _sql_list(paths):
    return "[" + ", ".join(_sql_text(p) for p in paths) + "]"


def stored_files(root):
    """(part files, run card files) of every partition, sorted; `.partial` files are never listed."""
    root = Path(root)
    partitions = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith(store.PARTITION_PREFIX))
    parts = [f for p in partitions for f in store.part_files(p)]
    cards = [p / store.RUN_CARD for p in partitions if (p / store.RUN_CARD).is_file()]
    return parts, cards


def connect(store_dir):
    """An in-memory DuckDB connection with the views result_rows, run_cards and results over the store."""
    root = store.check_store(store_dir)
    parts, cards = stored_files(root)
    con = duckdb.connect(":memory:", config=DUCKDB_CONFIG)
    if parts:
        con.execute(f"CREATE VIEW result_rows AS SELECT {', '.join(store.COLUMN_NAMES)} "
                    f"FROM read_parquet({_sql_list(parts)})")
    else:
        con.execute("CREATE VIEW result_rows AS SELECT "
                    + ", ".join(f"CAST(NULL AS VARCHAR) AS {name}" for name in store.COLUMN_NAMES) + " WHERE false")
    if cards:
        con.execute("CREATE VIEW run_cards AS SELECT " + ", ".join(f"{expr} AS {name}" for name, expr in CARD_FIELDS)
                    + f" FROM read_text({_sql_list(cards)})")
    else:
        con.execute("CREATE VIEW run_cards AS SELECT "
                    + ", ".join(f"CAST(NULL AS {'BOOLEAN' if name == 'git_dirty' else 'VARCHAR'}) AS {name}"
                                for name, _ in CARD_FIELDS) + " WHERE false")
    joined = ", ".join(f"c.{name}" for name, _ in CARD_FIELDS if name not in ("run_card_id", "card_json", "card_file"))
    con.execute(f"CREATE VIEW results AS SELECT r.*, {joined} FROM result_rows r "
                f"LEFT JOIN run_cards c ON c.run_card_id = r.run_card_id")
    return con


def _records(con, sql, params):
    cursor = con.execute(sql, params)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def query_run_card(store_dir, run_card_id):
    """Every stored row of a run card (stored columns), sorted by kind, clip_id and row ID; each row checked."""
    con = connect(store_dir)
    try:
        records = _records(con, f"SELECT {', '.join(store.COLUMN_NAMES)} FROM results WHERE run_card_id = ? "
                                f"ORDER BY kind, clip_id, result_row_id", [run_card_id])
    finally:
        con.close()
    for rec in records:
        store.verify_record(rec, run_card_id)
    return records


def rows_by_id(store_dir, row_id):
    """Every row of the `results` view with this result_row_id (all columns), for trace."""
    con = connect(store_dir)
    try:
        return _records(con, "SELECT * FROM results WHERE result_row_id = ?", [row_id])
    finally:
        con.close()
