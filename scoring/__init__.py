"""
scoring package initialization.

Exposes the canonical VAD scoring engine, grid resampling utilities,
metric calculation bundles, correlation engine, and weakness heatmap builders.
"""

from scoring.correlation_engine import (
    CorrelationEngineError,
    CorrelationHeatmapReport,
    CorpusVersionMismatchError,
    HeatmapCell,
    build_weakness_heatmap,
    correlate_profiles_and_scores,
)
from scoring.vad_scorer import (
    BucketScoreSummary,
    ClipScoreResult,
    MetricBundle,
    ResampledGridData,
    VADScorerReport,
    compute_metrics_bundle,
    get_loudness_bucket,
    get_snr_bucket,
    resample_to_common_grid,
    score_adapter_evaluation,
    score_single_clip,
)

__all__ = [
    # Scorer
    "BucketScoreSummary",
    "ClipScoreResult",
    "MetricBundle",
    "ResampledGridData",
    "VADScorerReport",
    "compute_metrics_bundle",
    "get_loudness_bucket",
    "get_snr_bucket",
    "resample_to_common_grid",
    "score_adapter_evaluation",
    "score_single_clip",
    # Correlation Engine
    "CorrelationEngineError",
    "CorrelationHeatmapReport",
    "CorpusVersionMismatchError",
    "HeatmapCell",
    "build_weakness_heatmap",
    "correlate_profiles_and_scores",
]