"""Trace a stored result row back to what produced it: run card, pack manifest ID and version, clip, commit, lock.

CAPABILITIES:
  CAP-TRACE-001: trace_row() finds a result_row_id through the DuckDB `results` view and, only after checking that exactly one row has the ID, that the row checks (ID from identity, row SHA-256, IDs agree) and that the stored run card validates and belongs to the row's folder, returns the row with its run card; format_trace() prints result_row_id, kind, clip_id, run_card_id, pack_manifest_id, pack_version, pack_sha256, git_commit (dirty flag), lock_file, lock_sha256 and the full run card [tests: test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock, test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card, test_FR_0_6_03_unknown_row_id_exit_1, test_FR_0_6_03_changed_run_card_is_reported, test_FR_0_6_03_row_not_matching_its_id_is_reported]
INPUTS AND OUTPUTS: a store folder and a result_row_id in; a Trace and its text out; StoreInputError (malformed ID,
  no store), TraceError (not found) or StoreIntegrityError (a check failed).
CONTRACTS: store layout in docs/results/RESULTS_STORE.md; run-card v1.
INVARIANTS:
  - Never prints a partial or best-guess answer: any failed check is an error.
  - Read-only.
NOT IN SCOPE:
  - Resolving the pack manifest file itself (the run card names its manifest ID, version and SHA-256).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-03 created.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from aqis_lab.results import store, views

ROW_ID_RE = re.compile(r"[0-9a-f]{64}")


class TraceError(RuntimeError):
    """The row is not in the store (exit 1)."""


@dataclass
class Trace:
    row: dict
    card: dict


def trace_row(store_dir, row_id):
    """The checked Trace of one stored row."""
    if not ROW_ID_RE.fullmatch(row_id or ""):
        raise store.StoreInputError(f"a result_row_id is 64 lowercase hexadecimal characters, got {row_id!r}")
    root = store.check_store(store_dir)
    rows = views.rows_by_id(root, row_id)
    if not rows:
        raise TraceError(f"result row {row_id} is not in the results store {root}")
    if len(rows) > 1:
        raise store.StoreIntegrityError(f"result row {row_id} is stored {len(rows)} times ({len(rows)} rows); the "
                                        f"store is damaged")
    row = rows[0]
    store.verify_record(row)
    partition = store.partition_dir(root, row["run_card_id"])
    if not (partition / store.RUN_CARD).is_file():
        raise store.StoreIntegrityError(f"result row {row_id}: no stored run card {partition / store.RUN_CARD}")
    card = store.load_stored_card(partition)
    if card["run_card_id"] != row["run_card_id"]:
        raise store.StoreIntegrityError(f"result row {row_id} names run card {row['run_card_id']}, but its folder "
                                        f"holds {card['run_card_id']}")
    return Trace(row=row, card=card)


def format_trace(trace):
    card, row = trace.card, trace.row
    pack = card["pack"] or {"manifest_id": None, "version": None, "sha256": None}
    lines = [
        f"result_row_id: {row['result_row_id']}",
        f"kind: {row['kind']}",
        f"clip_id: {row['clip_id']}",
        f"run_card_id: {card['run_card_id']}",
        f"pack_manifest_id: {pack['manifest_id']}",
        f"pack_version: {pack['version']}",
        f"pack_sha256: {pack['sha256']}",
        f"git_commit: {card['git']['commit']} (dirty: {str(card['git']['dirty']).lower()})",
        f"lock_file: {card['lock']['file']}",
        f"lock_sha256: {card['lock']['sha256']}",
        "run_card:",
        json.dumps(card, indent=2, sort_keys=True, ensure_ascii=False),
    ]
    return "\n".join(lines) + "\n"
