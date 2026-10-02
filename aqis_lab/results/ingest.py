"""Read result rows for the store from a finished runner run folder or from a `score` output folder.

CAPABILITIES:
  CAP-RESULTS-003: from_run_folder() accepts only a finished run: a valid run_card.json, a shard_plan.json naming the same card, and a results.jsonl whose lines are strict JSON objects of this run card covering the plan's clips exactly once; each line becomes a run-result row with identity (kind, run_card_id, clip_id, task, task_version) [tests: test_FR_0_6_02_add_run_folder_writes_partition_by_run_card, test_FR_0_6_02_rejects_incomplete_run_folder, test_FR_0_6_02_rejects_rows_of_another_run_card]
  CAP-RESULTS-004: from_score_folder() accepts a score folder whose summary.json hashes match scores.parquet and scores.csv, with score table 1.0 columns, one run card and unique (clip, variant) rows; each row becomes a score row with identity (kind, run_card_id, clip_id, variant, normaliser_name, normaliser_version, ref_sha256); an optional run card file must be that run card; the Parquet bytes are read from a copy in Arrow-owned memory, so nothing Arrow releases at interpreter exit needs the Python interpreter (BLK-012) [tests: test_FR_0_6_02_add_score_folder_rows, test_FR_0_6_02_score_rows_need_their_run_card, test_FR_0_6_02_repeated_results_add_always_exits_cleanly]
INPUTS AND OUTPUTS: a folder (and an optional run card file) in; a store Batch out; StoreInputError naming the file
  and line on any problem.
CONTRACTS: run folder layout (docs/runner/RUNNER.md); score table (docs/contracts/SCORE_TABLE.md); run-card v1;
  row identities in docs/results/RESULTS_STORE.md.
INVARIANTS:
  - Reads only; never changes the source folder.
  - A source row is kept whole: the store holds it as canonical JSON.
NOT IN SCOPE:
  - Writing the store (aqis_lab/results/store.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-02 created.
  2026-10-02 WP-0.7 BLK-012: from_score_folder reads the Parquet bytes from a copy in Arrow-owned memory (pa.BufferOutputStream)
    (test_FR_0_6_02_repeated_results_add_always_exits_cleanly).
"""
import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from aqis_lab.contracts.validate import ContractValidationError, parse_json, split_json_lines
from aqis_lab.results.store import Batch, Record, StoreInputError, card_from_bytes
from aqis_lab.scoring.table import COLUMN_NAMES as SCORE_COLUMNS
from aqis_lab.scoring.table import SCHEMA_METADATA_KEY as SCORE_METADATA_KEY
from aqis_lab.scoring.table import SCHEMA_VERSION as SCORE_SCHEMA_VERSION

RUN_FILES = ("run_card.json", "shard_plan.json", "results.jsonl")
SCORE_FILES = ("scores.parquet", "scores.csv", "summary.json")
RUN_IDENTITY = ("run_card_id", "clip_id", "task", "task_version")
SCORE_IDENTITY = ("run_card_id", "clip_id", "variant", "normaliser_name", "normaliser_version", "ref_sha256")


def _read(path, what):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError as exc:
        raise StoreInputError(f"{path} is missing: {what}") from exc
    except OSError as exc:
        raise StoreInputError(f"{path} is unreadable: {exc.strerror or exc}") from exc


def _json(data, where):
    try:
        return parse_json(data, "JSON")
    except ContractValidationError as exc:
        raise StoreInputError(f"{where}: {exc}") from exc


def from_run_folder(run_dir):
    """The run-result Batch of a finished run folder."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise StoreInputError(f"{run_dir} is not a run folder")
    card_bytes = _read(run_dir / "run_card.json", "not a run folder")
    card = card_from_bytes(card_bytes, run_dir / "run_card.json")
    card_id = card["run_card_id"]
    plan = _json(_read(run_dir / "shard_plan.json", "not a run folder"), run_dir / "shard_plan.json")
    if not isinstance(plan, dict) or plan.get("run_card_id") != card_id:
        raise StoreInputError(f"{run_dir / 'shard_plan.json'} does not name run card {card_id}")
    try:
        planned = [c for shard in plan["shards"] for c in shard["clip_ids"]]
    except (KeyError, TypeError) as exc:
        raise StoreInputError(f"{run_dir / 'shard_plan.json'} has no readable shards: {exc}") from exc
    data = _read(run_dir / "results.jsonl", "the run is not finished (results.jsonl is written when every shard "
                                            "is finished)")
    where = run_dir / "results.jsonl"
    seen, records = {}, []
    for number, raw in enumerate(split_json_lines(data), start=1):
        row = _json(raw, f"{where} line {number}")
        if not isinstance(row, dict):
            raise StoreInputError(f"{where} line {number}: not a JSON object")
        missing = [k for k in RUN_IDENTITY if not isinstance(row.get(k), str)]
        if missing:
            raise StoreInputError(f"{where} line {number}: no text field {', '.join(missing)}")
        if row["run_card_id"] != card_id:
            raise StoreInputError(f"{where} line {number}: run_card_id {row['run_card_id']} is not this run card's "
                                  f"({card_id})")
        clip = row["clip_id"]
        if clip not in planned:
            raise StoreInputError(f"{where} line {number}: clip {clip} is not in the shard plan")
        if clip in seen:
            raise StoreInputError(f"{where}: clip {clip} appears more than once (lines {seen[clip]} and {number})")
        seen[clip] = number
        identity = {"kind": "run-result", **{k: row[k] for k in RUN_IDENTITY}}
        records.append(Record(kind="run-result", identity=identity, row=row))
    absent = [c for c in planned if c not in seen]
    if absent:
        raise StoreInputError(f"{where} is missing {len(absent)} clip(s) of the shard plan: {', '.join(absent)}")
    return Batch(run_card_id=card_id, card=card, card_bytes=card_bytes, records=records,
                 source_file="results.jsonl", source_sha256=hashlib.sha256(data).hexdigest())


def from_score_folder(score_dir, run_card=None):
    """The score Batch of a `score` output folder; `run_card` is the hypothesis run's card file, when given."""
    score_dir = Path(score_dir)
    if not score_dir.is_dir():
        raise StoreInputError(f"{score_dir} is not a score folder")
    contents = {name: _read(score_dir / name, "not a score folder") for name in SCORE_FILES}
    summary = _json(contents["summary.json"], score_dir / "summary.json")
    files = summary.get("files") if isinstance(summary, dict) else None
    if not isinstance(files, dict):
        raise StoreInputError(f"{score_dir / 'summary.json'} lists no file hashes")
    for name in ("scores.parquet", "scores.csv"):
        if files.get(name) != hashlib.sha256(contents[name]).hexdigest():
            raise StoreInputError(f"{score_dir / 'summary.json'}: the SHA-256 of {name} does not match the file")
    try:
        # Read from a copy in Arrow-owned memory: a Python-owned buffer released by Arrow at interpreter exit needs
        # the GIL and can abort or hang the exit (BLK-012; the WP-0.7 parity defect).
        owned = pa.BufferOutputStream()
        owned.write(contents["scores.parquet"])
        table = pq.read_table(pa.BufferReader(owned.getvalue()), use_threads=False)
    except (pa.ArrowException, OSError) as exc:
        raise StoreInputError(f"{score_dir / 'scores.parquet'} is unreadable: {exc}") from exc
    metadata = table.schema.metadata or {}
    if metadata.get(SCORE_METADATA_KEY) != SCORE_SCHEMA_VERSION.encode("ascii") or \
            tuple(table.column_names) != SCORE_COLUMNS:
        raise StoreInputError(f"{score_dir / 'scores.parquet'} is not a score table {SCORE_SCHEMA_VERSION}")
    rows = table.to_pylist()
    card_ids = sorted({r["run_card_id"] for r in rows})
    if len(card_ids) != 1 or card_ids[0] != summary.get("run_card_id"):
        raise StoreInputError(f"{score_dir}: the score rows must name one run card, the one in summary.json "
                              f"(found {', '.join(card_ids) or 'none'})")
    card_id = card_ids[0]
    card = card_bytes = None
    if run_card is not None:
        card_bytes = _read(run_card, "the run card file")
        card = card_from_bytes(card_bytes, run_card)
        if card["run_card_id"] != card_id:
            raise StoreInputError(f"{run_card} is run card {card['run_card_id']}, but the scores are for run card "
                                  f"{card_id}")
    records, seen = [], set()
    for row in rows:
        key = (row["clip_id"], row["variant"])
        if key in seen:
            raise StoreInputError(f"{score_dir / 'scores.parquet'}: clip {key[0]} variant {key[1]} appears twice")
        seen.add(key)
        identity = {"kind": "score", **{k: row[k] for k in SCORE_IDENTITY}}
        records.append(Record(kind="score", identity=identity, row=row))
    return Batch(run_card_id=card_id, card=card, card_bytes=card_bytes, records=records,
                 source_file="scores.parquet", source_sha256=hashlib.sha256(contents["scores.parquet"]).hexdigest())
