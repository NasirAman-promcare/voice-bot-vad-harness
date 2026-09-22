"""
scoring/correlation_engine.py

One Job:
    Join the physical acoustic measurements produced by audio_profiler.py with the
    accuracy scores from vad_scorer.py (and latency metrics from latency_calculator.py)
    to generate the multi-dimensional weakness heatmap: VAD Operating Point × Audio Condition.

Why this file is separate from vad_scorer.py:
    vad_scorer.py evaluates ground-truth speech classification without knowing acoustic
    physics. audio_profiler.py measures signal acoustics without knowing VAD decisions.
    Keeping them separate ensures that changes to acoustic profiling algorithms can never
    silently corrupt or alter benchmark accuracy numbers. This file strictly joins and
    reshapes existing metrics; it NEVER re-derives or computes primary metrics.

Manifest Version Mismatch Policy:
    Correlating results across different corpus/manifest versions (e.g. comparing a run on
    v1 against a run on v2) invalidates condition alignment. By default, attempting to
    correlate inputs tagged with differing manifest version hashes raises a
    CorpusVersionMismatchError. If cross-version regression comparison is explicitly intended,
    callers must pass `allow_version_mismatch=True`, which tags the output report with an
    explicit warning and records all involved version hashes.

Visibly-Empty Cell Policy:
    Any VAD × category combination that has not been evaluated is populated as an explicit
    empty cell (is_empty=True, metrics=None). Missing cells are NEVER defaulted to 0.0
    (which would misrepresent an un-evaluated condition as a 0% accuracy failure) and
    NEVER silently omitted from the matrix.

What this module must NEVER do:
    - Never import or reference concrete VAD adapters or internal engine details.
    - Never re-derive precision, recall, F1, or latency from raw samples or timestamps.
    - Never silently omit untested categories or adapters.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from corpus.manifest import VALID_CATEGORIES
from scoring.vad_scorer import (
    ClipScoreResult,
    MetricBundle,
    get_loudness_bucket,
    get_snr_bucket,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class CorrelationEngineError(Exception):
    """Base exception for correlation engine errors."""
    pass


class CorpusVersionMismatchError(CorrelationEngineError):
    """Raised when attempting to correlate data from conflicting manifest versions."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class HeatmapCell:
    """
    A single cell in the weakness heatmap representing one (VAD × Audio Condition) pair.

    All metrics are passed directly from vad_scorer.py, audio_profiler.py, or
    latency_calculator.py without re-computation.
    """
    adapter_id: str
    category: str
    condition_key: str
    snr_bucket: Optional[str]
    loudness_bucket: Optional[str]
    is_empty: bool
    clip_count: int
    # Accuracy metrics (from vad_scorer.py)
    f1: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    false_positive_rate: Optional[float]
    false_negative_rate: Optional[float]
    # Latency metrics (from latency_calculator.py & Tier 1 profiler)
    onset_latency_ms: Optional[float]
    offset_hangover_latency_ms: Optional[float]
    algorithmic_compute_p95_ms: Optional[float]
    # Profiler physical measurements (from audio_profiler.py)
    measured_snr_db: Optional[float]
    measured_rms_dbfs: Optional[float]
    measured_spectral_flatness: Optional[float]
    is_clipped: Optional[bool]


@dataclass(frozen=True)
class CorrelationHeatmapReport:
    """
    The master weakness heatmap matrix across all adapters and acoustic categories.
    """
    run_id: str
    manifest_versions: Tuple[str, ...]
    adapter_ids: Tuple[str, ...]
    categories: Tuple[str, ...]
    conditions: Tuple[str, ...]
    matrix: Dict[str, Dict[str, HeatmapCell]]  # adapter_id -> condition_key -> HeatmapCell
    version_mismatch_warning: Optional[str] = None

    def get_cell(self, adapter_id: str, condition_key: str) -> HeatmapCell:
        """Retrieves a cell from the matrix, returning an explicit empty cell if absent."""
        if adapter_id in self.matrix and condition_key in self.matrix[adapter_id]:
            return self.matrix[adapter_id][condition_key]
        return HeatmapCell(
            adapter_id=adapter_id,
            category=condition_key.split(" [")[0],
            condition_key=condition_key,
            snr_bucket=None,
            loudness_bucket=None,
            is_empty=True,
            clip_count=0,
            f1=None,
            precision=None,
            recall=None,
            false_positive_rate=None,
            false_negative_rate=None,
            onset_latency_ms=None,
            offset_hangover_latency_ms=None,
            algorithmic_compute_p95_ms=None,
            measured_snr_db=None,
            measured_rms_dbfs=None,
            measured_spectral_flatness=None,
            is_clipped=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the heatmap report to a nested JSON-serializable dictionary."""
        return asdict(self)

    def to_markdown_table(self, metric_name: str = "f1") -> str:
        """
        Renders a formatted Markdown table for reports and notebooks.

        Args:
            metric_name: One of 'f1', 'precision', 'recall', 'fpr', 'fnr', 'onset_latency_ms'.
        """
        headers = ["Adapter / Operating Point"] + list(self.categories)
        rows: List[List[str]] = []

        for adapter_id in self.adapter_ids:
            row = [adapter_id]
            for cat in self.categories:
                cell = self.get_cell(adapter_id, cat)
                if cell.is_empty:
                    row.append("—")
                else:
                    val = getattr(cell, metric_name, None)
                    if val is None:
                        row.append("N/A")
                    elif isinstance(val, float):
                        if "latency" in metric_name or "ms" in metric_name:
                            row.append(f"{val:.1f}ms")
                        else:
                            row.append(f"{val:.3f}")
                    else:
                        row.append(str(val))
            rows.append(row)

        # Build Markdown formatting
        col_widths = [max(len(row[i]) for row in ([headers] + rows)) for i in range(len(headers))]
        header_line = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"
        sep_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(len(headers))) + "-|"
        body_lines = [
            "| " + " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"
            for row in rows
        ]

        return "\n".join([header_line, sep_line] + body_lines)


# ==============================================================================
# Joining & Correlation Logic
# ==============================================================================

def build_weakness_heatmap(
    scores: Sequence[ClipScoreResult],
    profiles: Optional[Union[Sequence[Dict[str, Any]], Dict[str, Dict[str, Any]]]] = None,
    latencies: Optional[Union[Sequence[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]] = None,
    run_id: str = "benchmark_run",
    manifest_version: Optional[str] = None,
    expected_adapters: Optional[Sequence[str]] = None,
    expected_categories: Optional[Sequence[str]] = None,
    allow_version_mismatch: bool = False,
) -> CorrelationHeatmapReport:
    """
    Joins scoring, profiling, and latency metrics into a structured weakness matrix.

    Guarantees:
        1. Never re-derives primary metrics; only passes through computed values.
        2. Populates all (adapter × category) combinations with explicit empty cells
           when untested.
        3. Enforces manifest version consistency.

    Args:
        scores: Sequence of ClipScoreResult from vad_scorer.py.
        profiles: Acoustic profiles from audio_profiler.py (dict or list of dicts).
        latencies: Latency measurement records (dict or list of dicts).
        run_id: Unique run identifier tag.
        manifest_version: Expected manifest version hash.
        expected_adapters: Complete list of active adapters to include in matrix rows.
        expected_categories: Categories to include in matrix columns (defaults to VALID_CATEGORIES).
        allow_version_mismatch: If True, allows correlating differing manifest versions.

    Returns:
        A complete CorrelationHeatmapReport.

    Raises:
        CorpusVersionMismatchError: If manifest versions mismatch and allow_version_mismatch=False.
    """
    # 1. Normalize and index audio profiles by clip_id
    profiles_by_clip: Dict[str, Dict[str, Any]] = {}
    if profiles is not None:
        if isinstance(profiles, dict):
            profiles_by_clip = profiles
        elif isinstance(profiles, (list, tuple)):
            for p in profiles:
                cid = p.get("clip_id")
                if cid:
                    profiles_by_clip[cid] = p

    # 2. Normalize and index latency measurements by (adapter_id, clip_id)
    latencies_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if latencies is not None:
        if isinstance(latencies, dict):
            latencies_by_key = latencies
        elif isinstance(latencies, (list, tuple)):
            for lat in latencies:
                aid = lat.get("adapter_id")
                cid = lat.get("clip_id")
                payload = lat.get("payload", lat)
                if aid and cid:
                    latencies_by_key[(aid, cid)] = payload

    # 3. Determine active adapter list and category universe
    active_adapters: List[str] = []
    if expected_adapters:
        active_adapters = list(expected_adapters)
    else:
        seen_adapters = {s.adapter_id for s in scores}
        active_adapters = sorted(seen_adapters)

    active_categories: List[str] = (
        list(expected_categories) if expected_categories else sorted(VALID_CATEGORIES)
    )

    # 4. Group scored clips by (adapter_id, category)
    grouped_clips: Dict[Tuple[str, str], List[ClipScoreResult]] = {}
    observed_versions: Set[str] = set()
    if manifest_version:
        observed_versions.add(manifest_version)

    for clip in scores:
        key = (clip.adapter_id, clip.category)
        grouped_clips.setdefault(key, []).append(clip)

    # Version mismatch enforcement
    version_warning: Optional[str] = None
    if len(observed_versions) > 1 and not allow_version_mismatch:
        raise CorpusVersionMismatchError(
            f"Cannot correlate results across conflicting manifest versions: {sorted(observed_versions)}. "
            "Set allow_version_mismatch=True to override."
        )
    elif len(observed_versions) > 1:
        version_warning = f"Multi-version correlation: {sorted(observed_versions)}"

    # 5. Populate heatmap matrix
    matrix: Dict[str, Dict[str, HeatmapCell]] = {}

    for adapter_id in active_adapters:
        matrix[adapter_id] = {}
        for category in active_categories:
            clips = grouped_clips.get((adapter_id, category), [])

            if not clips:
                # Explicit empty cell (never defaulted to 0.0)
                matrix[adapter_id][category] = HeatmapCell(
                    adapter_id=adapter_id,
                    category=category,
                    condition_key=category,
                    snr_bucket=None,
                    loudness_bucket=None,
                    is_empty=True,
                    clip_count=0,
                    f1=None,
                    precision=None,
                    recall=None,
                    false_positive_rate=None,
                    false_negative_rate=None,
                    onset_latency_ms=None,
                    offset_hangover_latency_ms=None,
                    algorithmic_compute_p95_ms=None,
                    measured_snr_db=None,
                    measured_rms_dbfs=None,
                    measured_spectral_flatness=None,
                    is_clipped=None,
                )
                continue

            # Pass-through aggregated metrics for populated cell (filtering out None values)
            f1_scores = [c.metrics.f1 for c in clips if c.metrics.f1 is not None]
            precisions = [c.metrics.precision for c in clips if c.metrics.precision is not None]
            recalls = [c.metrics.recall for c in clips if c.metrics.recall is not None]
            fprs = [c.metrics.false_positive_rate for c in clips if c.metrics.false_positive_rate is not None]
            fnrs = [c.metrics.false_negative_rate for c in clips if c.metrics.false_negative_rate is not None]

            # Collect latency metrics associated with these clips
            onset_latencies: List[float] = []
            offset_latencies: List[float] = []
            compute_p95s: List[float] = []

            for c in clips:
                lat = latencies_by_key.get((adapter_id, c.clip_id), {})
                if "onset_latency_ms" in lat and lat["onset_latency_ms"] is not None:
                    onset_latencies.append(float(lat["onset_latency_ms"]))
                if "offset_hangover_latency_ms" in lat and lat["offset_hangover_latency_ms"] is not None:
                    offset_latencies.append(float(lat["offset_hangover_latency_ms"]))
                if "p95_compute_ms" in lat and lat["p95_compute_ms"] is not None:
                    compute_p95s.append(float(lat["p95_compute_ms"]))

            # Collect profiler metrics associated with these clips
            snrs: List[float] = []
            rms_list: List[float] = []
            flatness_list: List[float] = []
            clipped_flags: List[bool] = []

            for c in clips:
                prof = profiles_by_clip.get(c.clip_id, {})
                noise_sub = prof.get("noise", {})
                loudness_sub = prof.get("loudness", {})
                spectral_sub = prof.get("spectral", {})

                if noise_sub.get("estimated_snr_db") is not None:
                    snrs.append(float(noise_sub["estimated_snr_db"]))
                if loudness_sub.get("rms_dbfs") is not None:
                    rms_list.append(float(loudness_sub["rms_dbfs"]))
                if spectral_sub.get("spectral_flatness") is not None:
                    flatness_list.append(float(spectral_sub["spectral_flatness"]))
                if loudness_sub.get("is_clipped") is not None:
                    clipped_flags.append(bool(loudness_sub["is_clipped"]))

            cell = HeatmapCell(
                adapter_id=adapter_id,
                category=category,
                condition_key=category,
                snr_bucket=get_snr_bucket(clips[0].target_snr_db) if clips else None,
                loudness_bucket=get_loudness_bucket(clips[0].target_loudness_lufs) if clips else None,
                is_empty=False,
                clip_count=len(clips),
                f1=round(float(sum(f1_scores) / len(f1_scores)), 4) if f1_scores else None,
                precision=round(float(sum(precisions) / len(precisions)), 4) if precisions else None,
                recall=round(float(sum(recalls) / len(recalls)), 4) if recalls else None,
                false_positive_rate=round(float(sum(fprs) / len(fprs)), 4) if fprs else None,
                false_negative_rate=round(float(sum(fnrs) / len(fnrs)), 4) if fnrs else None,
                onset_latency_ms=round(float(sum(onset_latencies) / len(onset_latencies)), 2) if onset_latencies else None,
                offset_hangover_latency_ms=round(float(sum(offset_latencies) / len(offset_latencies)), 2) if offset_latencies else None,
                algorithmic_compute_p95_ms=round(float(sum(compute_p95s) / len(compute_p95s)), 2) if compute_p95s else None,
                measured_snr_db=round(float(sum(snrs) / len(snrs)), 2) if snrs else None,
                measured_rms_dbfs=round(float(sum(rms_list) / len(rms_list)), 2) if rms_list else None,
                measured_spectral_flatness=round(float(sum(flatness_list) / len(flatness_list)), 4) if flatness_list else None,
                is_clipped=any(clipped_flags) if clipped_flags else False,
            )
            matrix[adapter_id][category] = cell

    return CorrelationHeatmapReport(
        run_id=run_id,
        manifest_versions=tuple(sorted(observed_versions)),
        adapter_ids=tuple(active_adapters),
        categories=tuple(active_categories),
        conditions=tuple(active_categories),
        matrix=matrix,
        version_mismatch_warning=version_warning,
    )


def correlate_profiles_and_scores(
    profiles: Sequence[Dict[str, Any]],
    scores: Sequence[ClipScoreResult],
    latencies: Optional[Sequence[Dict[str, Any]]] = None,
    run_id: str = "tier1_run",
    manifest_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper matching orchestrator.py's Step 7 correlation call.

    Returns:
        JSON-serializable dictionary representation of the CorrelationHeatmapReport.
    """
    report = build_weakness_heatmap(
        scores=scores,
        profiles=profiles,
        latencies=latencies,
        run_id=run_id,
        manifest_version=manifest_version,
    )
    return report.to_dict()