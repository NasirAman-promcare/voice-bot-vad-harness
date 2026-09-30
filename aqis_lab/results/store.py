"""The append-only results store: one folder per run card, one immutable Parquet file per add, never replaced.

CAPABILITIES:
  CAP-RESULTS-001: add_batch() appends a batch of result rows under <store>/run_card_id=<id>/: the run card is written once, new rows go into one new part-<SHA-256>.parquet file published by hard link (an existing file can never be replaced), rows already stored with identical content are reported and not stored again, and a row whose identity is stored with other content stops the whole add with nothing written; adds hold an exclusive lock on <store>/.lock; a store on a Google Drive mount is refused; a new store's STORE.json is published only while holding the store lock (a folder that holds anything else is refused before any file is made in it), so adds that start at the same moment on a new store all succeed (DEBT-015) [tests: test_FR_0_6_02_add_run_folder_writes_partition_by_run_card, test_FR_0_6_02_add_score_folder_rows, test_FR_0_6_02_refuses_to_overwrite_existing_rows, test_FR_0_6_02_existing_files_never_replaced, test_FR_0_6_02_identical_rows_not_stored_twice, test_FR_0_6_02_score_rows_need_their_run_card, test_FR_0_6_02_interrupted_add_leaves_no_row, test_FR_0_6_02_concurrent_adds_are_serialised, test_FR_0_6_02_store_on_drive_refused, test_FR_0_6_02_simultaneous_first_adds_are_safe]
  CAP-RESULTS-002: result_row_id() is the SHA-256 of the canonical JSON of a row's identity fields; check_part_file(), read_partition() and verify_record() check every stored file and row (schema version, columns, content-addressed name, row ID, row SHA-256, partition) and raise StoreIntegrityError on any difference [tests: test_FR_0_6_02_row_id_computed_from_identity, test_FR_0_6_02_schema_documented_equals_code, test_FR_0_6_03_row_not_matching_its_id_is_reported, test_FR_0_6_02_add_rejects_tampered_stored_rows, test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store]
INPUTS AND OUTPUTS: a store folder and a Batch (from aqis_lab/results/ingest.py) in; files in the store and an
  AddResult out; StoreInputError (usage or input, exit 2), StoreConflictError and StoreIntegrityError (exit 1).
CONTRACTS: store layout and schema in docs/results/RESULTS_STORE.md; run-card v1.
INVARIANTS:
  - Nothing in the store is ever replaced or deleted; the only files removed are this module's own <name>.partial
    files: after their content has been published, when publishing failed, or (under the store lock) when an
    interrupted add left them behind.
  - Every published file is complete when it appears (write, fsync, hard link, fsync of the folder).
  - Parquet is read with use_threads=False: with pyarrow 25.0.1 a threaded read made about 4 in 10 processes hang
    at exit on the cloud VM (docs/progress/WP-0.6/EVIDENCE.md, "pyarrow exit hang").
NOT IN SCOPE:
  - Reading runner or scorer output (aqis_lab/results/ingest.py); queries (aqis_lab/results/views.py).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-02 created.
  2026-09-29 WP-0.6 round 2 F03: the file checks of read_partition moved unchanged into check_part_file, which
    aqis_lab/results/views.py also calls.
  2026-09-30 WP-0.7 DEBT-015 (4): _ensure_store creates the folder race-safely and publishes STORE.json only while
    holding the store lock (test_FR_0_6_02_simultaneous_first_adds_are_safe).
"""
import fcntl
import hashlib
import io
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from aqis_lab import drive
from aqis_lab import platform as lp
from aqis_lab.commands.version import VersionInfoError, version_line
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.contracts.validate import ContractValidationError, parse_json, validate_run_card

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = REPO_ROOT / "data" / "raw" / "aqis_lab" / "results"
SCHEMA_VERSION = "1.0"
STORE_FILE = "STORE.json"
LOCK_FILE = ".lock"
RUN_CARD = "run_card.json"
PARTIAL = ".partial"
PARTITION_PREFIX = "run_card_id="
METADATA_KEY = b"aqis_results_store_schema_version"
KINDS = ("run-result", "score")
# (column, Arrow type name) in file order; docs/results/RESULTS_STORE.md lists the same columns.
COLUMNS = (
    ("result_row_id", "string"),
    ("kind", "string"),
    ("run_card_id", "string"),
    ("clip_id", "string"),
    ("identity", "string"),
    ("row", "string"),
    ("row_sha256", "string"),
    ("source_file", "string"),
    ("source_sha256", "string"),
    ("added_utc", "string"),
    ("added_by", "string"),
)
COLUMN_NAMES = tuple(name for name, _ in COLUMNS)
RUN_CARD_ID_RE = re.compile(r"[0-9a-f]{64}")
PART_RE = re.compile(r"part-([0-9a-f]{64})\.parquet")


class StoreInputError(RuntimeError):
    """A usage or input problem: nothing was written (exit 2)."""


class StoreConflictError(RuntimeError):
    """The add would change a stored row or replace a stored file: nothing was written (exit 1)."""


class StoreIntegrityError(RuntimeError):
    """A stored file or row does not match what the store recorded (exit 1)."""


@dataclass(frozen=True)
class Record:
    kind: str
    identity: dict
    row: dict

    @property
    def row_id(self):
        return result_row_id(self.identity)


@dataclass
class Batch:
    run_card_id: str
    card: dict | None           # the validated run card, or None when it must already be in the store
    card_bytes: bytes | None
    records: list
    source_file: str
    source_sha256: str


@dataclass
class AddResult:
    run_card_id: str
    stored: int
    already: int
    part: Path | None
    card_written: bool
    partition: Path
    already_ids: list = field(default_factory=list)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def result_row_id(identity):
    """SHA-256 (lowercase hex) of the canonical JSON of a row's identity fields."""
    return hashlib.sha256(canonical_json(identity)).hexdigest()


def arrow_schema():
    return pa.schema([pa.field(name, pa.string(), nullable=False) for name, _ in COLUMNS],
                     metadata={METADATA_KEY: SCHEMA_VERSION.encode("ascii")})


def partition_dir(root, run_card_id):
    return Path(root) / f"{PARTITION_PREFIX}{run_card_id}"


def _fsync_folder(folder):
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _unlink_partial(partial):
    if os.path.lexists(partial):
        os.unlink(partial)


def publish(path, data):
    """Publish `data` at `path` atomically; StoreConflictError when `path` exists (it is never replaced)."""
    target = Path(path)
    partial = target.with_name(target.name + PARTIAL)
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        view = memoryview(bytes(data))
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.link(partial, target)
    except FileExistsError as exc:
        _unlink_partial(partial)
        raise StoreConflictError(f"refusing to replace {target}: it already exists; stored files are never "
                                 f"replaced") from exc
    except OSError as exc:
        _unlink_partial(partial)
        raise StoreInputError(f"cannot publish {target}: {exc.strerror or exc}; the results store needs a local "
                              f"file system with hard links") from exc
    os.chmod(target, 0o444)
    _fsync_folder(target.parent)
    os.unlink(partial)
    _fsync_folder(target.parent)
    return target


def _refuse_drive(root, system):
    try:
        mount = drive.drive_mount_of(root, system)
    except (lp.PlatformError, OSError) as exc:
        raise StoreInputError(f"cannot tell whether {root} is on Google Drive: {exc}") from exc
    if mount is not None:
        raise StoreInputError(f"refusing a results store on Google Drive ({mount}): the store must be on local disk "
                              f"(it publishes files by hard link); `python -m aqis_lab sync` copies it to Drive")


def check_store(root):
    """The store folder, or StoreInputError when there is no results store there."""
    root = Path(root)
    marker = root / STORE_FILE
    if not root.is_dir() or not marker.is_file():
        raise StoreInputError(f"no results store at {root} (no {STORE_FILE}); add rows with "
                              f"`python -m aqis_lab results add` first")
    try:
        data = parse_json(marker.read_bytes(), "results store")
    except (OSError, ContractValidationError) as exc:
        raise StoreIntegrityError(f"{marker} is unreadable: {exc}") from exc
    if data != {"store_schema_version": SCHEMA_VERSION}:
        raise StoreIntegrityError(f"{marker} says {data!r}; this aqis_lab reads results store version "
                                  f"{SCHEMA_VERSION}")
    return root


@contextmanager
def _locked(root):
    with open(root / LOCK_FILE, "a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _ensure_store(root):
    """Check the store at `root`, creating it first if needed. STORE.json is published only while holding the store
    lock, so adds that start at the same moment on a new store all succeed (DEBT-015)."""
    if root.exists() and not root.is_dir():
        raise StoreInputError(f"{root} exists and is not a folder")
    own = {LOCK_FILE, STORE_FILE, STORE_FILE + PARTIAL}     # what a store that another add is creating may hold

    def foreign():
        return (root.exists() and not (root / STORE_FILE).exists()
                and any(entry.name not in own for entry in root.iterdir()))

    if foreign():                                # checked before the lock file is made in someone else's folder
        raise StoreInputError(f"{root} is not a results store (no {STORE_FILE}) and is not empty")
    if not (root / STORE_FILE).exists():
        created = not root.exists()
        root.mkdir(parents=True, exist_ok=True)
        if created:
            _fsync_folder(root.parent)
        with _locked(root):
            if not (root / STORE_FILE).exists():
                if foreign():
                    raise StoreInputError(f"{root} is not a results store (no {STORE_FILE}) and is not empty")
                publish(root / STORE_FILE, canonical_json({"store_schema_version": SCHEMA_VERSION}) + b"\n")
    return check_store(root)


def load_stored_card(partition):
    """The validated run card stored in a partition; StoreIntegrityError when it is damaged or misplaced."""
    path = Path(partition) / RUN_CARD
    try:
        card = parse_json(path.read_bytes(), "run card")
        validate_run_card(card)
    except (OSError, ContractValidationError) as exc:
        raise StoreIntegrityError(f"stored run card {path} is damaged: {exc}") from exc
    expected = Path(partition).name[len(PARTITION_PREFIX):]
    if card["run_card_id"] != expected:
        raise StoreIntegrityError(f"stored run card {path} has run_card_id {card['run_card_id']}, not the "
                                  f"folder's {expected}")
    return card


def part_files(partition):
    partition = Path(partition)
    if not partition.is_dir():
        return []
    return sorted(p for p in partition.iterdir() if PART_RE.fullmatch(p.name))


def verify_record(rec, run_card_id=None):
    """Check one stored row: identity, row ID, row SHA-256 and IDs agree; StoreIntegrityError otherwise."""
    where = f"row {rec.get('result_row_id')}"
    try:
        identity = parse_json(rec["identity"].encode("utf-8"), "identity")
        row = parse_json(rec["row"].encode("utf-8"), "row")
    except (ContractValidationError, KeyError, AttributeError) as exc:
        raise StoreIntegrityError(f"{where}: unreadable identity or row: {exc}") from exc
    problems = []
    if result_row_id(identity) != rec["result_row_id"]:
        problems.append(f"its ID is not the SHA-256 of its identity ({result_row_id(identity)})")
    if hashlib.sha256(rec["row"].encode("utf-8")).hexdigest() != rec["row_sha256"]:
        problems.append("row_sha256 does not match the row")
    for key in ("kind", "run_card_id", "clip_id"):
        if identity.get(key) != rec[key]:
            problems.append(f"{key} {rec[key]!r} differs from its identity's {identity.get(key)!r}")
    if run_card_id is not None and rec["run_card_id"] != run_card_id:
        problems.append(f"it is stored under run card {run_card_id}")
    if problems:
        raise StoreIntegrityError(f"{where}: " + "; ".join(problems))
    return identity, row


def check_part_file(part):
    """The table of a stored part file after its file checks: content equal to the SHA-256 in its name, readable
    Parquet, schema version and columns; StoreIntegrityError otherwise. Rows are checked by verify_record."""
    part = Path(part)
    data = part.read_bytes()
    if hashlib.sha256(data).hexdigest() != PART_RE.fullmatch(part.name).group(1):
        raise StoreIntegrityError(f"{part}: its content no longer matches the SHA-256 in its name")
    try:
        table = pq.read_table(io.BytesIO(data), use_threads=False)
    except (pa.ArrowException, OSError) as exc:
        raise StoreIntegrityError(f"{part} is not a readable Parquet file: {exc}") from exc
    metadata = table.schema.metadata or {}
    if metadata.get(METADATA_KEY) != SCHEMA_VERSION.encode("ascii") or tuple(table.column_names) != COLUMN_NAMES:
        raise StoreIntegrityError(f"{part} is not a results store {SCHEMA_VERSION} file (metadata or columns)")
    return table


def read_partition(partition):
    """Every stored row of a partition, each checked; StoreIntegrityError on any damaged file or row."""
    partition = Path(partition)
    run_card_id = partition.name[len(PARTITION_PREFIX):]
    records = []
    for part in part_files(partition):
        table = check_part_file(part)
        for rec in table.to_pylist():
            verify_record(rec, run_card_id)
            records.append(rec)
    return records


def _remove_stale_partials(root, partition):
    """Remove `.partial` files an interrupted add left behind; called only while holding the store lock, so no
    live add owns them."""
    for folder in (root, partition):
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path.name.endswith(PARTIAL) and path.is_file():
                    os.unlink(path)


def _record_row(rec, batch, added_utc, added_by):
    row_text = canonical_json(rec.row).decode("utf-8")
    return {"result_row_id": rec.row_id, "kind": rec.kind, "run_card_id": batch.run_card_id,
            "clip_id": rec.identity["clip_id"], "identity": canonical_json(rec.identity).decode("utf-8"),
            "row": row_text, "row_sha256": hashlib.sha256(row_text.encode("utf-8")).hexdigest(),
            "source_file": batch.source_file, "source_sha256": batch.source_sha256, "added_utc": added_utc,
            "added_by": added_by}


def add_batch(store_dir, batch, system=None):
    """Append a batch to the store (see the module header); returns an AddResult."""
    root = Path(store_dir).absolute()
    _refuse_drive(root, system)
    if not RUN_CARD_ID_RE.fullmatch(batch.run_card_id or ""):
        raise StoreInputError(f"invalid run_card_id {batch.run_card_id!r}")
    ids = {}
    for rec in batch.records:
        if rec.kind not in KINDS:
            raise StoreInputError(f"unknown row kind {rec.kind!r}")
        if rec.identity.get("kind") != rec.kind or rec.identity.get("run_card_id") != batch.run_card_id:
            raise StoreInputError(f"row {rec.row_id}: its identity does not name kind {rec.kind} and run card "
                                  f"{batch.run_card_id}")
        if rec.row_id in ids:
            raise StoreInputError(f"the input holds two rows with the same identity {rec.identity} "
                                  f"(row ID {rec.row_id})")
        ids[rec.row_id] = rec
    partition = partition_dir(root, batch.run_card_id)
    if batch.card_bytes is None and not (partition / RUN_CARD).is_file():
        raise StoreInputError(f"run card {batch.run_card_id} is not in the store {root}; add its run folder first, "
                              f"or pass its run card with --run-card FILE")
    try:
        added_by = version_line()
    except VersionInfoError as exc:
        raise StoreInputError(f"cannot record which code adds the rows: {exc}") from exc
    root = _ensure_store(root)
    with _locked(root):
        _remove_stale_partials(root, partition)
        card_file = partition / RUN_CARD
        if card_file.is_file():
            load_stored_card(partition)
        elif batch.card_bytes is None:
            raise StoreInputError(f"run card {batch.run_card_id} is not in the store {root}; add its run folder "
                                  f"first, or pass its run card with --run-card FILE")
        existing = {rec["result_row_id"]: rec["row_sha256"] for rec in read_partition(partition)}
        added_utc = utc_now()
        rows = [_record_row(rec, batch, added_utc, added_by) for rec in batch.records]
        new, already, conflicts = [], [], []
        for row in rows:
            stored = existing.get(row["result_row_id"])
            if stored is None:
                new.append(row)
            elif stored == row["row_sha256"]:
                already.append(row["result_row_id"])
            else:
                conflicts.append(row["result_row_id"])
        if conflicts:
            raise StoreConflictError(
                f"{len(conflicts)} row(s) are already stored with other content (conflict), so nothing was written: "
                f"{', '.join(sorted(conflicts))}; stored rows are never changed")
        card_written = False
        if not partition.is_dir():
            partition.mkdir()
            _fsync_folder(root)
        if not card_file.is_file():
            publish(card_file, batch.card_bytes)
            card_written = True
        part = None
        if new:
            new.sort(key=lambda r: (r["kind"], r["clip_id"], r["result_row_id"]))
            buffer = io.BytesIO()
            pq.write_table(pa.Table.from_pylist(new, schema=arrow_schema()), buffer)
            data = buffer.getvalue()
            part = publish(partition / f"part-{hashlib.sha256(data).hexdigest()}.parquet", data)
    return AddResult(run_card_id=batch.run_card_id, stored=len(new), already=len(already), part=part,
                     card_written=card_written, partition=partition, already_ids=already)


def card_from_bytes(data, where):
    """A validated run card parsed strictly from bytes; StoreInputError naming `where` otherwise."""
    try:
        card = parse_json(data, "run card")
        validate_run_card(card)
    except ContractValidationError as exc:
        raise StoreInputError(f"{where} is not a valid run card: {exc}") from exc
    return card


def json_lines(records):
    """Canonical JSON text lines for query output, with identity and row expanded."""
    out = []
    for rec in records:
        item = {name: rec[name] for name in COLUMN_NAMES}
        item["identity"] = json.loads(rec["identity"])
        item["row"] = json.loads(rec["row"])
        out.append(canonical_json(item).decode("utf-8"))
    return out
