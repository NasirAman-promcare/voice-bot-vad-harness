"""
storage/results_store.py

One Job:
    The SOLE module in the entire project permitted to write permanent results to disk.
    Persists granular, raw per-clip evaluation records (scoring, latency, and profiling)
    incrementally to durable append-only storage, tagging every row with run_id,
    manifest_version, and runtime-queried library versions.

Why writes are strictly incremental:
    In long-running evaluation sessions (e.g. Google Colab, Kaggle, remote GPU instances),
    sessions can be preempted or disconnected unexpectedly. Holding evaluation results in
    memory to write once at the end risks losing all progress. Every single completed clip
    is written, flushed, and fsynced to disk immediately as produced.

Tagging & Traceability:
    Every persisted row carries:
      1. run_id: Unique execution tag.
      2. manifest_version: Content hash from corpus/manifest.py.
      3. vad_library_version: Exact runtime-queried package version (e.g. 'ten-vad 0.1.2').
         If querying fails, it is explicitly tagged 'version_unknown' and logged.
    Appending never overwrites existing rows; records from multiple runs coexist
    transparently and are filtered or aggregated downstream by reporting.py.

What this module must NEVER do:
    - Never compute, average, or transform metrics (no aggregation logic).
    - Never overwrite, truncate, or merge existing run data.
    - Never hold rows in memory for end-of-run batch writes.
    - Never guess or fake library versions.
"""

from __future__ import annotations

import datetime
import importlib.metadata
import json
import logging
import os
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class ResultsStoreError(Exception):
    """Base exception for storage and persistence failures."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class RawEvaluationRecord:
    """
    Standard envelope wrapping every raw evaluation event persisted to disk.

    Attributes:
        run_id: Unique run identifier from run_config.yaml.
        manifest_version: Hash tag of the manifest dataset used during the run.
        vad_library_version: Exact installed version of the evaluated VAD package.
        adapter_id: Canonical identifier of the adapter / operating point.
        clip_id: Identifier of the audio clip.
        record_type: Category of record ('scoring_clip', 'latency_algorithmic', 'latency_pipeline', 'audio_profile').
        timestamp_utc: ISO-8601 UTC timestamp when the record was persisted.
        payload: Granular raw metric values and measurements (no aggregated summaries).
    """
    run_id: str
    manifest_version: str
    vad_library_version: str
    adapter_id: str
    clip_id: str
    record_type: str
    timestamp_utc: str
    payload: Dict[str, Any]


# ==============================================================================
# Dynamic Runtime Library Version Querying
# ==============================================================================

# Mapping from canonical adapter names to their underlying PyPI package distribution names
_ADAPTER_PACKAGE_MAP: Dict[str, Tuple[str, ...]] = {
    "ten_vad": ("ten-vad", "ten_vad"),
    "firered_vad": ("fireredvad", "fireredasr2s"),
    "webrtc_vad": ("webrtcvad-wheels", "webrtcvad"),
    "webrtc_vad_mode0": ("webrtcvad-wheels", "webrtcvad"),
    "webrtc_vad_mode1": ("webrtcvad-wheels", "webrtcvad"),
    "webrtc_vad_mode2": ("webrtcvad-wheels", "webrtcvad"),
    "webrtc_vad_mode3": ("webrtcvad-wheels", "webrtcvad"),
}


def get_installed_library_version(package_candidates: Sequence[str]) -> str:
    """
    Queries the installed version of a package from the runtime environment.

    Args:
        package_candidates: Candidate distribution or module names to check.

    Returns:
        Exact installed version string, or 'version_unknown' if querying fails.
    """
    for pkg in package_candidates:
        # 1. Attempt importlib.metadata lookup
        try:
            version = importlib.metadata.version(pkg)
            if version:
                return f"{pkg}=={version}"
        except importlib.metadata.PackageNotFoundError:
            pass
        except Exception as exc:
            logger.debug("importlib.metadata failed for '%s': %s", pkg, exc)

        # 2. Attempt module attribute inspection
        try:
            mod = __import__(pkg.replace("-", "_"))
            if hasattr(mod, "__version__"):
                return f"{pkg}=={mod.__version__}"
            elif hasattr(mod, "VERSION"):
                return f"{pkg}=={mod.VERSION}"
        except Exception:
            pass

    logger.warning(
        "Could not determine installed package version for candidates: %s. Tagging as 'version_unknown'.",
        list(package_candidates),
    )
    return "version_unknown"


def get_vad_library_version(adapter_id: str) -> str:
    """
    Resolves the exact installed library version for a given VAD adapter ID.

    Guarantees:
        Never returns None or empty string; returns 'version_unknown' if unresolved.
    """
    clean_id = adapter_id.strip()
    candidates = _ADAPTER_PACKAGE_MAP.get(clean_id)

    if candidates is None:
        # Check prefix matches for mode variations (e.g. webrtc_vad_modeX)
        for prefix, candidate_pkgs in _ADAPTER_PACKAGE_MAP.items():
            if clean_id.startswith(prefix):
                candidates = candidate_pkgs
                break

    if candidates is None:
        candidates = (clean_id,)

    return get_installed_library_version(candidates)


# ==============================================================================
# JSON Serialization Helper
# ==============================================================================

def _json_serializer(obj: Any) -> Any:
    """Custom serializer for NumPy scalar/array types and dataclasses."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    elif hasattr(obj, "tolist"):  # NumPy arrays
        return obj.tolist()
    elif hasattr(obj, "item"):  # NumPy scalars
        return obj.item()
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ==============================================================================
# Permanent Results Store
# ==============================================================================

class ResultsStore:
    """
    Incremental, append-only persistence store for all VAD benchmark records.
    """

    def __init__(self, destination: Union[str, Path]) -> None:
        """
        Initializes the results store at the specified file or directory path.

        Args:
            destination: Path to a .jsonl file or directory where raw_evaluations.jsonl is kept.
        """
        dest_path = Path(destination)
        if dest_path.suffix == ".jsonl":
            self._file_path = dest_path.resolve()
            self._dir_path = self._file_path.parent
        else:
            self._dir_path = dest_path.resolve()
            self._file_path = self._dir_path / "raw_evaluations.jsonl"

        self._dir_path.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(self._file_path, mode="a", encoding="utf-8")
        logger.info("ResultsStore opened append-only store at '%s'", self._file_path)

    @property
    def file_path(self) -> Path:
        """The absolute path to the append-only JSON Lines storage file."""
        return self._file_path

    def append_raw_record(self, record: RawEvaluationRecord) -> None:
        """
        Appends a fully constructed RawEvaluationRecord to the persistent store.

        Immediately flushes and syncs to disk to defend against mid-run process crashes.

        Raises:
            ResultsStoreError: If required envelope tags are missing or disk write fails.
        """
        if not record.run_id or not record.run_id.strip():
            raise ResultsStoreError("Cannot persist record: 'run_id' is missing or empty.")

        if not record.manifest_version or not record.manifest_version.strip():
            raise ResultsStoreError("Cannot persist record: 'manifest_version' is missing or empty.")

        if not record.vad_library_version or not record.vad_library_version.strip():
            raise ResultsStoreError("Cannot persist record: 'vad_library_version' is missing or empty.")

        record_dict = {
            "run_id": record.run_id,
            "manifest_version": record.manifest_version,
            "vad_library_version": record.vad_library_version,
            "adapter_id": record.adapter_id,
            "clip_id": record.clip_id,
            "record_type": record.record_type,
            "timestamp_utc": record.timestamp_utc,
            "payload": record.payload,
        }

        try:
            line = json.dumps(record_dict, default=_json_serializer)
            self._file_handle.write(line + "\n")
            self._file_handle.flush()
            os.fsync(self._file_handle.fileno())
        except Exception as exc:
            logger.error("Failed to persist raw record to '%s': %s", self._file_path, exc)
            raise ResultsStoreError(f"Disk persistence failure: {exc}") from exc

    def store_clip_score_result(
        self,
        run_id: str,
        manifest_version: str,
        clip_score_result: Any,
        vad_library_version: Optional[str] = None,
        tier: str = "tier1",
    ) -> None:
        """
        Persists a single clip's raw scoring metrics without any aggregation.
        """
        adapter_id = getattr(clip_score_result, "adapter_id", "unknown_adapter")
        clip_id = getattr(clip_score_result, "clip_id", "unknown_clip")
        lib_ver = vad_library_version or get_vad_library_version(adapter_id)

        metrics_obj = getattr(clip_score_result, "metrics", None)
        metrics_dict = asdict(metrics_obj) if metrics_obj is not None else {}

        resampled_obj = getattr(clip_score_result, "resampled_data", None)
        alignment_status = getattr(resampled_obj, "alignment_status", "unknown")
        discrepancy_ms = getattr(resampled_obj, "stream_length_discrepancy_ms", 0.0)

        payload = {
            "tier": tier,
            "category": getattr(clip_score_result, "category", None),
            "target_snr_db": getattr(clip_score_result, "target_snr_db", None),
            "target_loudness_lufs": getattr(clip_score_result, "target_loudness_lufs", None),
            "metrics": metrics_dict,
            "alignment_status": alignment_status,
            "stream_length_discrepancy_ms": discrepancy_ms,
        }

        record = RawEvaluationRecord(
            run_id=run_id,
            manifest_version=manifest_version,
            vad_library_version=lib_ver,
            adapter_id=adapter_id,
            clip_id=clip_id,
            record_type="scoring_clip",
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload=payload,
        )
        self.append_raw_record(record)

    def store_latency_measurement(
        self,
        run_id: str,
        manifest_version: str,
        adapter_id: str,
        clip_id: str,
        latency_data: Any,
        record_type: str = "latency_measurement",
        vad_library_version: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> None:
        """
        Persists a single raw latency measurement (algorithmic, onset, or hangover).
        """
        lib_ver = vad_library_version or get_vad_library_version(adapter_id)
        payload_data = asdict(latency_data) if is_dataclass(latency_data) and not isinstance(latency_data, type) else (latency_data if isinstance(latency_data, dict) else {"data": latency_data})
        if tier is not None and "tier" not in payload_data:
            payload_data["tier"] = tier
        record = RawEvaluationRecord(
            run_id=run_id,
            manifest_version=manifest_version,
            vad_library_version=lib_ver,
            adapter_id=adapter_id,
            clip_id=clip_id,
            record_type=record_type,
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload=payload_data,
        )
        self.append_raw_record(record)

    def store_audio_profile(
        self,
        run_id: str,
        manifest_version: str,
        clip_id: str,
        profile_data: Dict[str, Any],
    ) -> None:
        """
        Persists a single clip's raw acoustic profile metrics from audio_profiler.py.
        """
        record = RawEvaluationRecord(
            run_id=run_id,
            manifest_version=manifest_version,
            vad_library_version="audio_profiler==1.0.0",
            adapter_id="audio_profiler",
            clip_id=clip_id,
            record_type="audio_profile",
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload=profile_data,
        )
        self.append_raw_record(record)

    def store_clip_failure(
        self,
        run_id: str,
        manifest_version: str,
        adapter_id: str,
        clip_id: str,
        tier: str,
        stage: str,
        error: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Persists a clip-level failure record whenever processing or transport fails (A12).
        """
        lib_ver = get_vad_library_version(adapter_id)
        payload = {
            "tier": tier,
            "stage": stage,
            "error": str(error),
            "diagnostics": diagnostics or {},
        }
        record = RawEvaluationRecord(
            run_id=run_id,
            manifest_version=manifest_version,
            vad_library_version=lib_ver,
            adapter_id=adapter_id,
            clip_id=clip_id,
            record_type="clip_failure",
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload=payload,
        )
        self.append_raw_record(record)

    def store_run_context(
        self,
        run_id: str,
        manifest_version: str,
        context_data: Dict[str, Any],
    ) -> None:
        """
        Persists environmental, codec, hardware, and runtime context for the run (A23).
        """
        record = RawEvaluationRecord(
            run_id=run_id,
            manifest_version=manifest_version,
            vad_library_version="harness==1.0.0",
            adapter_id="orchestrator",
            clip_id="run_context",
            record_type="run_context",
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload=context_data,
        )
        self.append_raw_record(record)

    def read_raw_records(
        self,
        run_id: Optional[str] = None,
        record_type: Optional[str] = None,
        adapter_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Streams persisted raw records from disk with optional filtering.

        Used by reporting.py or analysis notebooks to aggregate stored results.

        Args:
            run_id: Optional run ID filter.
            record_type: Optional record type filter.
            adapter_id: Optional adapter identifier filter.

        Yields:
            Parsed dictionary objects for matching rows.
        """
        self._file_handle.flush()
        if not self._file_path.is_file():
            return

        with open(self._file_path, mode="r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    record_dict = json.loads(line_str)
                except json.JSONDecodeError as exc:
                    logger.error("Corrupted JSON record at line %d in '%s': %s", line_idx, self._file_path, exc)
                    continue

                if run_id is not None and record_dict.get("run_id") != run_id:
                    continue
                if record_type is not None and record_dict.get("record_type") != record_type:
                    continue
                if adapter_id is not None and record_dict.get("adapter_id") != adapter_id:
                    continue

                yield record_dict

    def close(self) -> None:
        """Flushes and closes the persistent file handle."""
        if not self._file_handle.closed:
            self._file_handle.flush()
            os.fsync(self._file_handle.fileno())
            self._file_handle.close()
            logger.debug("Closed ResultsStore file handle for '%s'", self._file_path)

    def __enter__(self) -> ResultsStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass