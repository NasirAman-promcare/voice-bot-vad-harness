"""The source registry (data/registry/sources.csv): one row per source clip, its CSV form and its validation.

CAPABILITIES:
  CAP-REG-001: check_registry_bytes() reports every problem of a registry file by line and column (header, field count, UTF-8, clip_id form and uniqueness, dataset and source, a missing or unknown licence, consent references for owner and campaign recordings that must name an existing non-empty file in the repository, transcript and speaker for speech only, split, tags, file facts); load_registry() turns a valid file into RegistryRow values or raises RegistryValidationError; registry_bytes() writes rows in the one canonical form (sorted by clip_id) [tests: test_FR_0_4_01_registry_has_spec_columns, test_FR_0_4_01_valid_rows_pass, test_FR_0_4_01_rejects_missing_licence, test_FR_0_4_01_rejects_unknown_licence, test_FR_0_4_01_rejects_owner_row_without_consent, test_FR_0_4_01_rejects_consent_ref_that_does_not_resolve, test_FR_0_4_01_rejects_consent_ref_on_other_sources, test_FR_0_4_01_rejects_speech_row_without_transcript_or_speaker, test_FR_0_4_01_rejects_non_speech_row_with_transcript, test_FR_0_4_01_rejects_invalid_or_duplicate_clip_id, test_FR_0_4_01_rejects_malformed_file_facts, test_FR_0_4_01_reports_every_problem_by_row_and_column, test_FR_0_4_01_rejects_wrong_header_and_field_count, test_FR_0_4_01_rows_round_trip_and_sort]
INPUTS AND OUTPUTS: registry CSV bytes, a Datasets value and the repository root in; a list of Problem values,
  RegistryRow values or canonical CSV bytes out.
CONTRACTS: registry format (docs/data/REGISTRY_FORMAT.md); datasets.yaml format 1.
INVARIANTS:
  - Every row is checked; one bad row never hides the problems of another.
  - A consent reference is accepted only if it resolves, inside the repository, to a non-empty regular file.
  - The same rows always give the same bytes (UTF-8, header, "\\n" line ends, minimal quoting, sorted by clip_id).
NOT IN SCOPE:
  - Producing rows from source files (aqis_lab/registry/importers.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-01 created.
"""
import csv
import io
import re
from dataclasses import dataclass, fields
from pathlib import Path, PurePosixPath

from aqis_lab.registry.datasets import CONSENT_SOURCES

# The first eight columns are the fields FR-0.4-01 names; the rest locate and describe the source file.
COLUMNS = ["clip_id", "source", "source_ref", "licence", "speaker_id", "consent_ref", "transcript", "split",
           "dataset", "tags", "sha256", "sample_rate_hz", "channels", "n_samples", "attribution"]
ID_RE = re.compile(r"[a-z0-9-]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
POSITIVE_INT_RE = re.compile(r"[1-9][0-9]*")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
OPTIONAL = ("speaker_id", "consent_ref", "transcript", "attribution")
INTEGERS = ("sample_rate_hz", "channels", "n_samples")
# Columns without a pattern of their own; the others are checked by their pattern or table lookup.
FREE_TEXT = ("source_ref", "speaker_id", "consent_ref", "transcript", "attribution")


@dataclass(frozen=True, order=True)
class Problem:
    line: int
    column: str
    message: str


class RegistryValidationError(ValueError):
    """A registry file breaks the format; .problems lists every problem found."""

    def __init__(self, where, problems):
        self.where = str(where)
        self.problems = tuple(sorted(problems))
        count = len(self.problems)
        lines = [f"{self.where}: registry is invalid ({count} problem{'' if count == 1 else 's'}):"]
        lines += [f"  line {p.line} column {p.column}: {p.message}" for p in self.problems]
        super().__init__("\n".join(lines))


@dataclass(frozen=True, order=True)
class RegistryRow:
    clip_id: str
    source: str
    source_ref: str
    licence: str
    speaker_id: str | None
    consent_ref: str | None
    transcript: str | None
    split: str
    dataset: str
    tags: tuple
    sha256: str
    sample_rate_hz: int
    channels: int
    n_samples: int
    attribution: str | None

    @property
    def duration_s(self):
        return self.n_samples / self.sample_rate_hz

    def record(self):
        """The row as the strings written to the CSV file."""
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "tags":
                out[f.name] = " ".join(value)
            elif value is None:
                out[f.name] = ""
            else:
                out[f.name] = str(value)
        return out


def _consent_problem(ref, repo_root):
    if PurePosixPath(ref).is_absolute() or "\\" in ref or any(p in ("", ".", "..") for p in ref.split("/")):
        return f"consent reference {ref!r} is not a relative path inside the repository"
    root = Path(repo_root).resolve()
    target = (root / ref).resolve()
    if root != target and root not in target.parents:
        return f"consent reference {ref!r} points outside the repository"
    if not target.is_file():
        return f"consent reference {ref!r} does not resolve to a file in the repository"
    if target.stat().st_size == 0:
        return f"consent reference {ref!r} names an empty file"
    return None


def check_records(records, datasets, repo_root):
    """Problems of [(line, {column: text})] records against the registry rules."""
    problems = []
    first_line = {}

    def bad(line, column, message):
        problems.append(Problem(line, column, message))

    for line, rec in records:
        for column in FREE_TEXT:
            if CONTROL_RE.search(rec[column]):
                bad(line, column, "contains a control character (line breaks and tabs are not allowed)")
        clip_id = rec["clip_id"]
        if not ID_RE.fullmatch(clip_id):
            bad(line, "clip_id", f"{clip_id!r} is not lowercase letters, digits and hyphens")
        elif clip_id in first_line:
            bad(line, "clip_id", f"{clip_id!r} repeats line {first_line[clip_id]}")
        else:
            first_line[clip_id] = line
        dataset = datasets.datasets.get(rec["dataset"])
        if dataset is None:
            bad(line, "dataset", f"dataset {rec['dataset']!r} is not defined in {datasets.path.name}")
        if not ID_RE.fullmatch(rec["source"]):
            bad(line, "source", f"{rec['source']!r} is not lowercase letters, digits and hyphens")
        elif dataset is not None and rec["source"] != dataset["source"]:
            bad(line, "source", f"{rec['source']!r} differs from dataset {dataset.dataset_id!r} source "
                                f"{dataset['source']!r}")
        if not rec["source_ref"].strip():
            bad(line, "source_ref", "missing source reference")
        if not rec["licence"]:
            bad(line, "licence", "missing licence")
        elif rec["licence"] not in datasets.licences:
            bad(line, "licence", f"licence {rec['licence']!r} is not defined in the licence table of "
                                 f"{datasets.path.name}")
        if rec["source"] in CONSENT_SOURCES:
            if not rec["consent_ref"]:
                bad(line, "consent_ref", f"missing consent reference (required for {rec['source']} recordings)")
            else:
                message = _consent_problem(rec["consent_ref"], repo_root)
                if message:
                    bad(line, "consent_ref", message)
        elif rec["consent_ref"]:
            bad(line, "consent_ref", f"only {' and '.join(CONSENT_SOURCES)} recordings carry a consent reference")
        if dataset is not None:
            speech = dataset["kind"] == "speech"
            for column in ("transcript", "speaker_id"):
                present = bool(rec[column].strip())
                if speech and not present:
                    bad(line, column, f"missing {column} (required for speech clips)")
                if not speech and rec[column]:
                    bad(line, column, f"must be empty for non-speech clips (dataset {dataset.dataset_id})")
            if ID_RE.fullmatch(rec["split"]) and rec["split"] not in dataset.splits:
                bad(line, "split", f"split {rec['split']!r} is not one of dataset {dataset.dataset_id!r} splits "
                                   f"{list(dataset.splits)}")
        if not ID_RE.fullmatch(rec["split"]):
            bad(line, "split", f"{rec['split']!r} is not lowercase letters, digits and hyphens")
        tags = rec["tags"].split(" ") if rec["tags"] else []
        if any(not ID_RE.fullmatch(t) for t in tags):
            bad(line, "tags", f"{rec['tags']!r}: tags are lowercase letters, digits and hyphens, one space apart")
        elif tags != sorted(set(tags)):
            bad(line, "tags", f"{rec['tags']!r}: tags must be unique and sorted")
        if not SHA256_RE.fullmatch(rec["sha256"]):
            bad(line, "sha256", f"{rec['sha256']!r} is not 64 lowercase hexadecimal characters")
        for column in INTEGERS:
            if not POSITIVE_INT_RE.fullmatch(rec[column]):
                bad(line, column, f"{rec[column]!r} is not a whole number of at least 1 without leading zeros")
    return problems


def _records(data):
    """(records, problems) of CSV bytes: structural problems only (encoding, header, field count)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], [Problem(0, "(file)", f"not UTF-8: {exc}")]
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        return [], [Problem(reader.line_num, "(file)", f"not valid CSV: {exc}")]
    if not rows or rows[0] != COLUMNS:
        found = rows[0] if rows else []
        return [], [Problem(1, "(header)", f"header must be exactly {','.join(COLUMNS)}; found {','.join(found)}")]
    records, problems = [], []
    for index, row in enumerate(rows[1:], start=2):
        if len(row) != len(COLUMNS):
            problems.append(Problem(index, "(row)", f"has {len(row)} fields, the header has {len(COLUMNS)}"))
            continue
        records.append((index, dict(zip(COLUMNS, row))))
    return records, problems


def check_registry_bytes(data, datasets, repo_root):
    """Every problem of registry CSV bytes, sorted by line and column."""
    records, problems = _records(data)
    return sorted(problems + check_records(records, datasets, repo_root))


def _row(rec):
    values = {}
    for column in COLUMNS:
        text = rec[column]
        if column == "tags":
            values[column] = tuple(text.split(" ")) if text else ()
        elif column in INTEGERS:
            values[column] = int(text)
        elif column in OPTIONAL:
            values[column] = text or None
        else:
            values[column] = text
    return RegistryRow(**values)


def load_registry_bytes(data, datasets, repo_root, where):
    records, problems = _records(data)
    problems += check_records(records, datasets, repo_root)
    if problems:
        raise RegistryValidationError(where, problems)
    return [_row(rec) for _, rec in records]


def load_registry(path, datasets, repo_root):
    """RegistryRow values of a registry file, in file order; RegistryValidationError lists every problem."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryValidationError(path, [Problem(0, "(file)", f"cannot read: {exc.strerror or exc}")]) from exc
    return load_registry_bytes(data, datasets, repo_root, path)


def check_rows(rows, datasets, repo_root, where):
    """Raise RegistryValidationError if RegistryRow values (as they would be written) break any rule."""
    ordered = sorted(rows, key=lambda r: r.clip_id)
    problems = check_records([(i, r.record()) for i, r in enumerate(ordered, start=2)], datasets, repo_root)
    if problems:
        raise RegistryValidationError(where, problems)


def registry_bytes(rows):
    """Canonical CSV bytes of RegistryRow values: header, rows sorted by clip_id, "\\n" line ends."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in sorted(rows, key=lambda r: r.clip_id):
        rec = row.record()
        writer.writerow([rec[c] for c in COLUMNS])
    return buf.getvalue().encode("utf-8")
