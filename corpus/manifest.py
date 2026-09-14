"""
corpus/manifest.py

One Job:
    Define the immutable schema for audio corpus manifests, validate manifest data
    against rigorous structural and acoustic category constraints, and expose the
    sole loader function that all downstream modules must use to access corpus metadata.

What this module must NEVER do:
    - Never attempt to read, probe, or verify the existence of actual audio files on disk.
      The manifest is the ground truth ceiling; file decoding is deferred to audio loaders.
    - Never silently coerce invalid categories, missing fields, or out-of-bound values.
    - Never scatter category string literals; all valid categories are defined here.
    - Never modify manifest entries in place; all output structures are immutable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ==============================================================================
# Fixed Category Set Specification
# ==============================================================================

class CorpusCategory(str, Enum):
    """
    Fixed set of allowed audio categories across all benchmark tiers.

    Every manifest row must match one of these exact string values.
    """
    CLEAN_SPEECH = "clean speech"
    SPEECH_STATIONARY_NOISE = "speech + stationary noise"
    SPEECH_TRANSIENT_NOISE = "speech + transient noise"
    SPEECH_BABBLE_CROSSTALK = "speech + babble/cross-talk"
    QUIET_WHISPERED_SPEECH = "quiet/whispered speech"
    LOUD_CLIPPED_SPEECH = "loud/clipped speech"
    SILENCE_ONLY = "silence-only"
    MUSIC_SINGING = "music/singing"
    BAND_LIMITED_TELEPHONY = "band-limited/telephony"
    PACKET_LOSS_JITTER = "packet-loss/jitter"  # Operationally evaluated in Tier 2 live pipeline


VALID_CATEGORIES: frozenset[str] = frozenset(cat.value for cat in CorpusCategory)


# ==============================================================================
# Exceptions
# ==============================================================================

class ManifestValidationError(ValueError):
    """
    Raised when manifest parsing or schema validation fails.

    Carries a list of distinct, contextual error messages indicating the exact
    row, clip identifier, and failing field/value.
    """
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors: List[str] = list(errors)
        formatted_errors = "\n".join(f"  - {err}" for err in self.errors)
        super().__init__(
            f"Manifest validation failed with {len(self.errors)} error(s):\n{formatted_errors}"
        )


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class ManifestEntry:
    """
    Immutable representation of a single benchmark audio clip's metadata.

    Duplicate Clip Identifiers Policy:
        clip_id MUST be strictly unique across the entire manifest. If the same
        underlying audio source is evaluated under multiple conditions (e.g. clean
        vs SNR 10dB), distinct identifiers (e.g. 'spk01_clean' and 'spk01_snr10')
        must be assigned to preserve per-clip traceability across storage, timing,
        and scoring layers.
    """
    clip_id: str
    clip_path: str
    category: str
    target_snr_db: Optional[float]
    target_loudness_lufs: Optional[float]
    speech_segments: Tuple[Tuple[int, int], ...]
    calibration_marker_offset_samples: int
    is_held_out: bool = False

    @property
    def has_speech(self) -> bool:
        """Returns True if the clip contains any ground-truth speech frames."""
        return len(self.speech_segments) > 0


@dataclass(frozen=True)
class Manifest:
    """
    Immutable container representing a validated manifest dataset.

    Provides category filtering and held-out slice partitioning while preserving
    the deterministic version hash of the source content.
    """
    entries: Tuple[ManifestEntry, ...]
    version_hash: str
    source_path: Optional[str] = None

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self, index: int) -> ManifestEntry:
        return self.entries[index]

    def get_entry(self, clip_id: str) -> ManifestEntry:
        """Retrieve an entry by its unique clip_id."""
        for entry in self.entries:
            if entry.clip_id == clip_id:
                return entry
        raise KeyError(f"Clip identifier '{clip_id}' not found in manifest.")

    def filter_by_categories(self, categories: Sequence[str]) -> Manifest:
        """
        Return a new Manifest containing only entries matching the specified categories.
        """
        if not categories:
            return self

        filter_set = set(categories)
        invalid_filters = filter_set - VALID_CATEGORIES
        if invalid_filters:
            raise ValueError(
                f"Filter contains invalid categories: {sorted(invalid_filters)}. "
                f"Allowed categories: {sorted(VALID_CATEGORIES)}"
            )

        filtered = tuple(entry for entry in self.entries if entry.category in filter_set)
        return Manifest(
            entries=filtered,
            version_hash=self.version_hash,
            source_path=self.source_path,
        )

    def filter_held_out(self, include_held_out: bool) -> Manifest:
        """
        Return a new Manifest filtered by held-out split status.
        If include_held_out is False, excludes all entries marked is_held_out=True.
        """
        if include_held_out:
            return self
        filtered = tuple(entry for entry in self.entries if not entry.is_held_out)
        return Manifest(
            entries=filtered,
            version_hash=self.version_hash,
            source_path=self.source_path,
        )


# ==============================================================================
# Validation Logic
# ==============================================================================

def _compute_version_hash(raw_data: Union[str, bytes, Sequence[Dict[str, Any]]]) -> str:
    """Computes a deterministic SHA-256 hash representing the manifest contents."""
    hasher = hashlib.sha256()
    if isinstance(raw_data, bytes):
        hasher.update(raw_data)
    elif isinstance(raw_data, str):
        hasher.update(raw_data.encode("utf-8"))
    else:
        # Canonical JSON serialization for in-memory structures
        canonical_repr = json.dumps(raw_data, sort_keys=True, separators=(",", ":"))
        hasher.update(canonical_repr.encode("utf-8"))
    return hasher.hexdigest()[:16]


def parse_and_validate_manifest(
    raw_entries: Sequence[Dict[str, Any]],
    version_hash: str,
    source_path: Optional[str] = None,
) -> Manifest:
    """
    Validates an in-memory sequence of manifest dictionaries against the schema.

    Collects and reports all schema violations across all rows rather than failing
    on the first encountered error.

    Raises:
        ManifestValidationError: If any row fails structural or semantic validation.
    """
    errors: List[str] = []
    seen_clip_ids: Set[str] = set()
    validated_entries: List[ManifestEntry] = []

    # Manifest with zero rows is valid input
    if len(raw_entries) == 0:
        logger.warning("Loaded empty manifest (0 entries). Version hash: %s", version_hash)
        return Manifest(entries=(), version_hash=version_hash, source_path=source_path)

    for row_idx, row in enumerate(raw_entries):
        row_label = f"Row {row_idx}"
        if not isinstance(row, dict):
            errors.append(f"{row_label}: Expected dictionary object, received {type(row).__name__}")
            continue

        clip_id = row.get("clip_id") or row.get("clip_path")
        if clip_id:
            row_label = f"Row {row_idx} (clip_id='{clip_id}')"

        # 1. Required: clip path / identifier
        raw_clip_id = row.get("clip_id")
        raw_clip_path = row.get("clip_path")
        if not raw_clip_id and not raw_clip_path:
            errors.append(f"{row_label}: Missing required field 'clip_id' or 'clip_path'")
            final_clip_id = f"unknown_row_{row_idx}"
            final_clip_path = f"unknown_row_{row_idx}"
        else:
            final_clip_id = str(raw_clip_id if raw_clip_id is not None else raw_clip_path)
            final_clip_path = str(raw_clip_path if raw_clip_path is not None else raw_clip_id)

        # Duplicate ID check
        if final_clip_id in seen_clip_ids:
            errors.append(
                f"{row_label}: Duplicate clip_id '{final_clip_id}' detected. "
                "Clip identifiers must be unique across all manifest entries."
            )
        seen_clip_ids.add(final_clip_id)

        # 2. Required: category (must match fixed category set exactly)
        category = row.get("category")
        if category is None:
            errors.append(f"{row_label}: Missing required field 'category'")
        elif not isinstance(category, str) or category not in VALID_CATEGORIES:
            errors.append(
                f"{row_label}: Invalid category '{category}'. "
                f"Must be one of: {sorted(VALID_CATEGORIES)}"
            )

        # 3. Required: calibration_marker_offset
        cal_offset = row.get("calibration_marker_offset")
        if cal_offset is None:
            errors.append(f"{row_label}: Missing required field 'calibration_marker_offset'")
        elif not isinstance(cal_offset, int) or isinstance(cal_offset, bool) or cal_offset < 0:
            errors.append(
                f"{row_label}: 'calibration_marker_offset' must be a non-negative integer, received {cal_offset}"
            )

        # 4. Required: speech_segments (list of [start, end] sample pairs, empty list allowed)
        raw_segments = row.get("speech_segments")
        validated_segments: List[Tuple[int, int]] = []
        if raw_segments is None:
            errors.append(f"{row_label}: Missing required field 'speech_segments'")
        elif not isinstance(raw_segments, (list, tuple)):
            errors.append(
                f"{row_label}: 'speech_segments' must be a list of [start, end] sample pairs, "
                f"received {type(raw_segments).__name__}"
            )
        else:
            for seg_idx, seg in enumerate(raw_segments):
                if not isinstance(seg, (list, tuple)) or len(seg) != 2:
                    errors.append(
                        f"{row_label}: Speech segment at index {seg_idx} must be a pair of [start, end] samples, "
                        f"received {seg}"
                    )
                    continue

                start, end = seg
                if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
                    errors.append(
                        f"{row_label}: Speech segment at index {seg_idx} contains non-integer sample boundaries: {seg}"
                    )
                elif start < 0 or end < start:
                    errors.append(
                        f"{row_label}: Speech segment at index {seg_idx} has invalid bounds [start={start}, end={end}]. "
                        "Expected 0 <= start <= end."
                    )
                else:
                    validated_segments.append((start, end))

        # 5. Nullable: target_snr_db
        target_snr_db = row.get("target_snr_db")
        if target_snr_db is not None:
            if isinstance(target_snr_db, bool) or not isinstance(target_snr_db, (int, float)):
                errors.append(
                    f"{row_label}: 'target_snr_db' must be a float, integer, or null, received {target_snr_db}"
                )
            else:
                target_snr_db = float(target_snr_db)

        # 6. Nullable: target_loudness_lufs
        target_loudness_lufs = row.get("target_loudness_lufs")
        if target_loudness_lufs is not None:
            if isinstance(target_loudness_lufs, bool) or not isinstance(target_loudness_lufs, (int, float)):
                errors.append(
                    f"{row_label}: 'target_loudness_lufs' must be a float, integer, or null, received {target_loudness_lufs}"
                )
            else:
                target_loudness_lufs = float(target_loudness_lufs)

        # 7. Optional: is_held_out
        is_held_out = row.get("is_held_out", False)
        if not isinstance(is_held_out, bool):
            errors.append(f"{row_label}: 'is_held_out' must be a boolean, received {is_held_out}")
            is_held_out = False

        if not errors:
            validated_entries.append(
                ManifestEntry(
                    clip_id=final_clip_id,
                    clip_path=final_clip_path,
                    category=str(category),
                    target_snr_db=target_snr_db,
                    target_loudness_lufs=target_loudness_lufs,
                    speech_segments=tuple(validated_segments),
                    calibration_marker_offset_samples=int(cal_offset) if isinstance(cal_offset, int) else 0,
                    is_held_out=is_held_out,
                )
            )

    if errors:
        raise ManifestValidationError(errors)

    return Manifest(
        entries=tuple(validated_entries),
        version_hash=version_hash,
        source_path=source_path,
    )


# ==============================================================================
# Public Loader Function
# ==============================================================================

def load_manifest(
    manifest_path: Union[str, Path],
    category_filter: Optional[Sequence[str]] = None,
    include_held_out: bool = True,
) -> Manifest:
    """
    Loads and validates the corpus manifest from disk.

    This is the ONLY function downstream modules should use to access manifest data.
    Raw files on disk are parsed, schema-validated, and encapsulated in an immutable Manifest.

    Args:
        manifest_path: Path to the JSON manifest file.
        category_filter: Optional list of category names to restrict the manifest to.
        include_held_out: Whether to retain held-out evaluation clips.

    Returns:
        A validated, immutable Manifest object.

    Raises:
        FileNotFoundError: If manifest_path does not exist.
        ManifestValidationError: If the manifest contains schema or category violations.
        ValueError: If JSON deserialization fails.
    """
    path = Path(manifest_path)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {path.resolve()}")

    try:
        raw_bytes = path.read_bytes()
        raw_content = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in manifest file '{path}': {exc}") from exc

    version_hash = _compute_version_hash(raw_bytes)

    # Support either top-level list of entries or wrapper object {"entries": [...]}
    if isinstance(raw_content, list):
        entries_data = raw_content
    elif isinstance(raw_content, dict) and "entries" in raw_content:
        entries_data = raw_content["entries"]
        if not isinstance(entries_data, list):
            raise ManifestValidationError([
                f"Root 'entries' key must contain a list of rows, received {type(entries_data).__name__}"
            ])
    else:
        raise ManifestValidationError([
            f"Manifest root must be a JSON list or object with an 'entries' array, received {type(raw_content).__name__}"
        ])

    manifest = parse_and_validate_manifest(
        raw_entries=entries_data,
        version_hash=version_hash,
        source_path=str(path.resolve()),
    )

    if category_filter:
        manifest = manifest.filter_by_categories(category_filter)

    if not include_held_out:
        manifest = manifest.filter_held_out(include_held_out=False)

    logger.info(
        "Successfully loaded manifest from '%s' (%d clips, version_hash=%s)",
        path,
        len(manifest),
        version_hash,
    )
    return manifest