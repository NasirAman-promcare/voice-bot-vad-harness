"""Pack specs (packs/specs/*.yaml): strict loading and checking into a PackSpec value.

CAPABILITIES:
  CAP-PACK-001: load_spec() reads a pack spec with duplicate keys rejected, checks it against pack_spec.v1.json (each part against the schema of its kind) and then checks what a schema cannot: created_utc is a real UTC time, category names are unique, each category's count equals what its parts give, every duration is a whole number of 16 kHz samples, min_seconds is at most max_seconds, and the limits are at most the hard caps of 1,000 files per folder and 200,000,000 bytes per archive [tests: test_FR_0_4_03_smoke_spec_declares_exact_composition, test_FR_0_4_03_spec_is_checked_strictly, test_FR_0_4_03_spec_rejects_duplicate_keys, test_FR_0_4_06_rejects_limits_above_hard_caps, test_FR_0_4_05_created_utc_comes_from_spec]
INPUTS AND OUTPUTS: a spec file path in; a PackSpec value (with the file's SHA-256) out; SpecError naming the file
  and every problem.
CONTRACTS: pack spec version 1 (aqis_lab/packs/schemas/pack_spec.v1.json, docs/data/SMOKE_PACK.md).
INVARIANTS:
  - Nothing is defaulted: every value the builder uses is written in the spec.
  - Durations are exact: a duration that is not a whole number of samples is an error, never rounded.
NOT IN SCOPE:
  - Choosing clips (aqis_lab/packs/select.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-03 created.
"""
import datetime
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from aqis_lab.packs.archive import MAX_ARCHIVE_BYTES, MAX_FILES_PER_FOLDER
from aqis_lab.packs.audio import WORKING_RATE
from aqis_lab.registry.datasets import DatasetsError, load_yaml_strict, schema_problems

SCHEMA = json.loads((Path(__file__).resolve().parent / "schemas" / "pack_spec.v1.json").read_text(encoding="utf-8"))


class SpecError(ValueError):
    """A pack spec is unreadable or invalid."""


@dataclass(frozen=True)
class Filter:
    source: str
    split: str
    tags_all: tuple
    tags_none: tuple
    min_seconds: Fraction | None
    max_seconds: Fraction | None
    distinct_speakers: bool

    def admits(self, row):
        """Whether a registry row passes this filter (source, split, tags and duration)."""
        if row.source != self.source or row.split != self.split:
            return False
        if not set(self.tags_all) <= set(row.tags) or set(self.tags_none) & set(row.tags):
            return False
        duration = Fraction(row.n_samples, row.sample_rate_hz)
        if self.min_seconds is not None and duration < self.min_seconds:
            return False
        return self.max_seconds is None or duration <= self.max_seconds


@dataclass(frozen=True)
class Part:
    index: int
    kind: str
    count: int
    label: str | None
    tags: tuple
    source_filter: Filter | None = None
    speech: Filter | None = None
    noise: Filter | None = None
    snr_db: tuple = ()
    length_samples: int | None = None
    silence_lengths: tuple = ()


@dataclass(frozen=True)
class Category:
    name: str
    count: int
    tags: tuple
    parts: tuple


@dataclass(frozen=True)
class PackSpec:
    path: Path
    sha256: str
    manifest_id: str
    version: str
    purpose: str
    created_utc: str
    seed: int
    max_files_per_folder: int
    max_archive_bytes: int
    allow_share_alike: bool
    allow_non_commercial: bool
    categories: tuple

    @property
    def created_epoch(self):
        when = datetime.datetime.strptime(self.created_utc, "%Y-%m-%dT%H:%M:%SZ")
        return int(when.replace(tzinfo=datetime.timezone.utc).timestamp())


def _samples(seconds, where, problems):
    exact = Fraction(repr(seconds)) if isinstance(seconds, float) else Fraction(seconds)
    samples = exact * WORKING_RATE
    if samples.denominator != 1:
        problems.append(f"{where}: {seconds} s is not a whole number of samples at {WORKING_RATE} Hz")
        return None
    return int(samples)


def _seconds(value):
    if value is None:
        return None
    return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)


def _filter(raw, where, problems):
    low, high = _seconds(raw.get("min_seconds")), _seconds(raw.get("max_seconds"))
    if low is not None and high is not None and low > high:
        problems.append(f"{where}: min_seconds {raw['min_seconds']} is more than max_seconds {raw['max_seconds']}")
    return Filter(raw["source"], raw["split"], tuple(raw.get("tags_all", ())), tuple(raw.get("tags_none", ())), low,
                  high, bool(raw.get("distinct_speakers", False)))


def _part(raw, index, where, problems):
    kind = raw["kind"]
    tags = tuple(raw.get("tags", ()))
    if kind == "take":
        return Part(index, kind, raw["count"], None, tags, source_filter=_filter(raw["from"], f"{where}/from", problems))
    if kind == "mix":
        return Part(index, kind, len(raw["snr_db"]), raw["label"], tags, speech=_filter(raw["speech"], f"{where}/speech", problems),
                    noise=_filter(raw["noise"], f"{where}/noise", problems), snr_db=tuple(raw["snr_db"]))
    if kind == "excerpt":
        return Part(index, kind, raw["count"], raw["label"], tags, source_filter=_filter(raw["from"], f"{where}/from", problems),
                    length_samples=_samples(raw["seconds"], f"{where}/seconds", problems))
    lengths = tuple(_samples(s, f"{where}/seconds/{i}", problems) for i, s in enumerate(raw["seconds"]))
    return Part(index, kind, len(lengths), raw["label"], tags, silence_lengths=lengths)


def load_spec(path):
    """Load and check a pack spec; returns PackSpec or raises SpecError listing every problem."""
    path = Path(path)
    try:
        doc = load_yaml_strict(path)
    except DatasetsError as exc:
        raise SpecError(str(exc)) from exc
    problems = schema_problems(SCHEMA, doc)
    if not problems:
        for c, category in enumerate(doc["categories"]):
            for p, part in enumerate(category["parts"]):
                problems += schema_problems(SCHEMA, part, f"part_{part['kind']}", f"/categories/{c}/parts/{p}")
    if problems:
        raise SpecError(f"{path} is invalid:\n  " + "\n  ".join(problems))
    try:
        datetime.datetime.strptime(doc["created_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        problems.append(f"/created_utc: {doc['created_utc']!r} is not a real UTC date and time")
    limits = doc["limits"]
    if limits["max_files_per_folder"] > MAX_FILES_PER_FOLDER:
        problems.append(f"/limits/max_files_per_folder: {limits['max_files_per_folder']} is above the hard cap of "
                        f"{MAX_FILES_PER_FOLDER} files per folder (FR-0.4-06)")
    if limits["max_archive_bytes"] > MAX_ARCHIVE_BYTES:
        problems.append(f"/limits/max_archive_bytes: {limits['max_archive_bytes']} is above the hard cap of "
                        f"{MAX_ARCHIVE_BYTES} bytes per archive (FR-0.4-06)")
    categories, seen = [], set()
    for c, raw in enumerate(doc["categories"]):
        where = f"/categories/{c}"
        if raw["name"] in seen:
            problems.append(f"{where}/name: category {raw['name']} appears twice")
        seen.add(raw["name"])
        parts = tuple(_part(part, p, f"{where}/parts/{p}", problems) for p, part in enumerate(raw["parts"]))
        given = sum(part.count for part in parts)
        if given != raw["count"]:
            problems.append(f"{where}: category {raw['name']} declares count {raw['count']} but its parts give {given}")
        categories.append(Category(raw["name"], raw["count"], tuple(raw["tags"]), parts))
    if problems:
        raise SpecError(f"{path} is invalid:\n  " + "\n  ".join(problems))
    return PackSpec(path, hashlib.sha256(path.read_bytes()).hexdigest(), doc["manifest_id"], doc["version"],
                    doc["purpose"], doc["created_utc"], doc["seed"], limits["max_files_per_folder"],
                    limits["max_archive_bytes"], doc["licence_policy"]["allow_share_alike"],
                    doc["licence_policy"]["allow_non_commercial"], tuple(categories))
