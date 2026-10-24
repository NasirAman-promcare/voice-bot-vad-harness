"""Sprint 2 result files: one atomically written parquet file per component, model, slice and condition, every row traced.

CAPABILITIES:
  CAP-S2-030: make_rows() puts the ten trace columns (component, model, revision, slice, condition, seed, git commit, machine,
    library versions, UTC time) after the utterance id of every payload; check_rows() refuses a row missing a trace column
    or holding an empty model, revision, slice, condition, commit or machine [tests:
    test_s2_rows_carry_every_trace_column_after_the_utterance_id, test_s2_a_row_missing_a_trace_column_fails,
    test_s2_a_row_with_an_empty_trace_field_fails, test_s2_make_rows_refuses_a_trace_missing_a_field,
    test_s2_make_rows_refuses_a_payload_without_an_utterance_id]
  CAP-S2-031: write_rows(), read_rows(), missing_ids() and merge_rows() keep each result file resumable: a rerun computes only
    the missing utterances, and a file never mixes revisions or repeats an utterance [tests:
    test_s2_result_file_roundtrip_and_missing_ids, test_s2_merging_keeps_old_rows_and_refuses_a_second_revision_or_a_repeat]
INPUTS AND OUTPUTS: trace dicts and payload dicts in; row dicts and parquet files (through aqis_lab.drive) out; RowError.
CONTRACTS: CLAUDE.md rule 3 (every result row records the model, model revision, slice, condition, seed, git commit and GPU or
  machine).
INVARIANTS:
  - Audio and per-utterance text stay on Drive; the repository gets aggregates only (aqis_lab/live/report.py).
  - A result file is replaced whole through aqis_lab.drive, never appended to in place.
NOT IN SCOPE:
  - What a payload holds (the stage modules) and summarising rows (aqis_lab/live/score.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import datetime
from pathlib import Path

from aqis_lab import drive

TRACE_COLUMNS = ("component", "model", "revision", "slice", "condition", "seed", "git_commit", "machine", "versions", "utc")
MUST_BE_FILLED = ("model", "revision", "slice", "condition", "git_commit", "machine")


class RowError(ValueError):
    """A result row breaks the trace format of CLAUDE.md rule 3."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_rows(trace, payloads):
    missing = [c for c in TRACE_COLUMNS if c not in trace]
    if missing:
        raise RowError(f"the run trace lacks {', '.join(missing)}")
    rows = []
    for payload in payloads:
        if "utt_id" not in payload:
            raise RowError(f"a result payload has no utt_id: {sorted(payload)}")
        rows.append({"utt_id": payload["utt_id"], **{c: trace[c] for c in TRACE_COLUMNS},
                     **{k: v for k, v in payload.items() if k != "utt_id"}})
    return rows


def check_rows(rows):
    for row in rows:
        missing = [c for c in TRACE_COLUMNS if c not in row]
        if missing:
            raise RowError(f"result row {row.get('utt_id', '?')} lacks {', '.join(missing)}")
        empty = [c for c in MUST_BE_FILLED if row[c] in ("", None)]
        if empty:
            raise RowError(f"result row {row.get('utt_id', '?')} has an empty trace field: {', '.join(empty)}")


def write_rows(path, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    check_rows(rows)
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist(rows), sink, compression="zstd")
    path = Path(path)
    drive.make_dirs(path.parent)
    drive.write_bytes(path, sink.getvalue().to_pybytes())


def read_rows(path):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def missing_ids(path, required):
    """The ids in `required` (in order) that the result file does not hold yet."""
    path = Path(path)
    have = {r["utt_id"] for r in read_rows(path)} if path.exists() else set()
    return [u for u in required if u not in have]


def merge_rows(path, new_rows):
    path = Path(path)
    old = read_rows(path) if path.exists() else []
    seen = {r["utt_id"] for r in old}
    for row in new_rows:
        if row["utt_id"] in seen:
            raise RowError(f"{path.name}: utterance {row['utt_id']} already has a result row")
        seen.add(row["utt_id"])
    combined = old + list(new_rows)
    for key in ("revision", "model"):
        values = {r[key] for r in combined}
        if len(values) > 1:
            raise RowError(f"{path.name}: rows would mix {key} values {sorted(values)}; a model keeps one {key} for the sprint")
    write_rows(path, combined)
