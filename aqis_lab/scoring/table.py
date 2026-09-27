"""The score table: one row per clip and normaliser variant, written as Parquet and as CSV.

CAPABILITIES:
  CAP-SCORE-004: rows_from_scores() turns utterance scores into score rows (schema_version, run_card_id, clip_id, variant, normaliser name and version, SHA-256 of the raw reference and hypothesis, every word and character count, WER and CER) after checking run_card_id and clip_id; parquet_bytes() and csv_bytes() serialise them with the schema in docs/contracts/SCORE_TABLE.md, sorted by clip_id, then variant [tests: test_FR_0_3_06_every_row_carries_trace_fields, test_FR_0_3_06_hashes_are_sha256_of_raw_text, test_FR_0_3_06_parquet_schema_matches_score_table_doc, test_FR_0_3_06_csv_header_matches_score_table_doc, test_FR_0_3_06_csv_and_parquet_hold_the_same_rows, test_FR_0_3_06_rows_sorted_by_clip_and_variant, test_FR_0_3_06_rejects_invalid_run_card_id_and_clip_id]
INPUTS AND OUTPUTS: UtteranceScore values (aqis_lab/scoring/wer.py) in; lists of row dicts, Parquet bytes and CSV
  bytes out (the command writes the files); ValueError for an invalid ID.
CONTRACTS: docs/contracts/SCORE_TABLE.md (score table schema 1.0).
INVARIANTS:
  - Both files hold the same rows and columns in the same order; floats are written in Python's shortest
    round-trip form in CSV, so the two files hold the same numbers.
  - The same scores give byte-identical files (explicit schema, sorted rows, no timestamps).
  - Hashes are of the texts exactly as given, before normalisation.
NOT IN SCOPE:
  - Reading input files, refusing to overwrite and the printed report (aqis_lab/commands/score.py).
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-06 created.
"""
import csv
import hashlib
import io
import re

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = "1.0"
SCHEMA_METADATA_KEY = b"aqis_score_table_schema_version"

_STRING, _INT, _FLOAT = pa.string(), pa.int64(), pa.float64()
# (column, Arrow type, nullable) in file order; docs/contracts/SCORE_TABLE.md lists the same columns.
COLUMNS = (
    ("schema_version", _STRING, False),
    ("run_card_id", _STRING, False),
    ("clip_id", _STRING, False),
    ("variant", _STRING, False),
    ("normaliser_name", _STRING, False),
    ("normaliser_version", _STRING, False),
    ("ref_sha256", _STRING, False),
    ("hyp_sha256", _STRING, False),
    ("ref_words", _INT, False),
    ("hyp_words", _INT, False),
    ("hits", _INT, False),
    ("substitutions", _INT, False),
    ("deletions", _INT, False),
    ("insertions", _INT, False),
    ("errors", _INT, False),
    ("wer", _FLOAT, True),
    ("ref_chars", _INT, False),
    ("hyp_chars", _INT, False),
    ("char_hits", _INT, False),
    ("char_substitutions", _INT, False),
    ("char_deletions", _INT, False),
    ("char_insertions", _INT, False),
    ("char_errors", _INT, False),
    ("cer", _FLOAT, True),
)
COLUMN_NAMES = tuple(name for name, _, _ in COLUMNS)

CLIP_ID_RE = re.compile(r"[a-z0-9-]+")
RUN_CARD_ID_RE = re.compile(r"[0-9a-f]{64}")


def is_clip_id(value):
    """Phase 0 ID rule: lowercase ASCII letters, digits and hyphens, at least one character."""
    return isinstance(value, str) and CLIP_ID_RE.fullmatch(value) is not None


def is_run_card_id(value):
    """A run card ID: 64 lowercase hexadecimal characters (SHA-256)."""
    return isinstance(value, str) and RUN_CARD_ID_RE.fullmatch(value) is not None


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def arrow_schema():
    fields = [pa.field(name, kind, nullable=nullable) for name, kind, nullable in COLUMNS]
    return pa.schema(fields, metadata={SCHEMA_METADATA_KEY: SCHEMA_VERSION.encode("ascii")})


def rows_from_scores(scores):
    """Score rows, sorted by clip_id, then variant; ValueError for an invalid run_card_id or clip_id."""
    rows = []
    for s in scores:
        if not is_run_card_id(s.run_card_id):
            raise ValueError(f"invalid run_card_id {s.run_card_id!r}: expected 64 lowercase hexadecimal characters")
        if not is_clip_id(s.clip_id):
            raise ValueError(f"invalid clip_id {s.clip_id!r}: expected lowercase letters, digits and hyphens")
        w, c = s.words, s.chars
        rows.append({
            "schema_version": SCHEMA_VERSION, "run_card_id": s.run_card_id, "clip_id": s.clip_id,
            "variant": s.variant, "normaliser_name": s.normaliser_name, "normaliser_version": s.normaliser_version,
            "ref_sha256": sha256_text(s.ref_text), "hyp_sha256": sha256_text(s.hyp_text),
            "ref_words": w.ref_len, "hyp_words": w.hyp_len, "hits": w.hits, "substitutions": w.substitutions,
            "deletions": w.deletions, "insertions": w.insertions, "errors": w.errors, "wer": s.wer,
            "ref_chars": c.ref_len, "hyp_chars": c.hyp_len, "char_hits": c.hits,
            "char_substitutions": c.substitutions, "char_deletions": c.deletions, "char_insertions": c.insertions,
            "char_errors": c.errors, "cer": s.cer,
        })
    rows.sort(key=lambda r: (r["clip_id"], r["variant"]))
    return rows


def parquet_bytes(rows):
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=arrow_schema()), buffer)
    return buffer.getvalue()


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMN_NAMES)
    for row in rows:
        writer.writerow([_csv_cell(row[name]) for name in COLUMN_NAMES])
    return buffer.getvalue().encode("utf-8")
