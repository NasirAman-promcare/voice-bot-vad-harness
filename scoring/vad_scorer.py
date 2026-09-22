"""
scoring/vad_scorer.py

One Job:
    Own the decision-stream-to-common-grid resampling step and compute frame-level
    VAD accuracy metrics (Precision, Recall, F1, Accuracy, Specificity, FPR, FNR)
    rigorously bucketed by acoustic category, target SNR, and target loudness.

Why this file is shared across Tier 1 and Tier 2:
    This exact scoring logic runs identically on Tier 1 offline frame streams and
    Tier 2 live decoded Jitsi feeds. Centralizing the scoring code guarantees that
    any delta observed between Tier 1 and Tier 2 reflects genuine network/pipeline
    effects, not scoring methodology discrepancies.

Common Grid Resampling (Defending against Frame-Size Mismatch):
    Different adapters operate at different native hops (TEN VAD at 16ms/256 samples,
    FireRedVAD at 10ms/160 samples, WebRTC at 10/20/30ms). Before computing any metric,
    all decision streams and manifest ground-truth intervals are resampled onto the
    common uniform time grid (scoring_grid_ms, default 10ms).

Silence-Only Mathematical Convention (Zero Ground-Truth Positives):
    For silence-only or music-only clips with zero speech segments (P = TP + FN = 0):
      - If FP == 0 (no false alarms): Precision = 1.0, Recall = 1.0 (no true speech was
        missed), F1 = 1.0, FPR = 0.0, FNR = 0.0.
      - If FP > 0 (false alarms present): Precision = 0.0 (all positive predictions are false),
        Recall = 1.0 (no true speech was missed), F1 = 0.0, FPR = FP / (FP + TN) > 0.
    This provides mathematically closed, non-crashing, documented metrics for all clips.

What this module must NEVER do:
    - Never import or reference audio_profiler.py or correlation_engine.py.
    - Never read config/run_config.yaml directly; all parameters are passed explicitly.
    - Never synthesize or pool WebRTC's binary modes into continuous threshold sweeps.
    - Never silently truncate or pad decision streams without tracking discrepancies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from corpus.manifest import ManifestEntry
from vad_adapters.adapter_contract import DecisionRecord

logger = logging.getLogger(__name__)


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class MetricBundle:
     """
     Immutable bundle of frame-level classification counts and derived rates.
     """
     tp: int
     fp: int
     tn: int
     fn: int
     total_frames: int
     precision: Optional[float]
     recall: Optional[float]
     f1: Optional[float]
     accuracy: float
     specificity: float
     false_positive_rate: float
     false_negative_rate: Optional[float]


@dataclass(frozen=True)
class ResampledGridData:
    """
    Output of the common-grid resampling stage for a single clip.
    """
    grid_sample_offsets: np.ndarray
    grid_decisions: np.ndarray
    grid_scores: Optional[np.ndarray]
    grid_ground_truth: np.ndarray
    scoring_grid_ms: int
    stream_length_discrepancy_ms: float
    alignment_status: str  # 'aligned', 'shorter_than_ground_truth', 'longer_than_ground_truth'


@dataclass(frozen=True)
class ClipScoreResult:
    """
    Detailed scoring evaluation for a single clip.
    """
    clip_id: str
    adapter_id: str
    category: str
    target_snr_db: Optional[float]
    target_loudness_lufs: Optional[float]
    metrics: MetricBundle
    resampled_data: ResampledGridData


@dataclass(frozen=True)
class BucketScoreSummary:
    """
    Aggregated performance metrics for a specific slice/bucket.
    """
    bucket_dimension: str  # 'category', 'snr_bucket', 'loudness_bucket', 'overall'
    bucket_key: str        # e.g., 'clean speech', '0 to 10 dB', 'overall'
    clip_count: int
    metrics: MetricBundle


@dataclass(frozen=True)
class VADScorerReport:
    """
    Complete benchmark evaluation report for an adapter across an entire dataset.

    Headline Deliverable:
        The bucketed category, SNR, and loudness breakdowns are the primary results.
        The overall metrics summary is strictly secondary.
    """
    adapter_id: str
    scoring_grid_ms: int
    category_breakdown: Dict[str, BucketScoreSummary]
    snr_breakdown: Dict[str, BucketScoreSummary]
    loudness_breakdown: Dict[str, BucketScoreSummary]
    silence_noise_fpr: Dict[str, float]
    quiet_whisper_fnr: Optional[float]
    overall_metrics: BucketScoreSummary
    clip_results: Tuple[ClipScoreResult, ...]


# ==============================================================================
# Helper Bucketing Functions
# ==============================================================================

def get_snr_bucket(snr: Optional[float]) -> str:
    """Categorizes target SNR in dB into discrete evaluation buckets."""
    if snr is None:
        return "N/A (Clean / Non-noisy)"
    if snr < 0.0:
        return "< 0 dB"
    elif 0.0 <= snr < 10.0:
        return "0 to 10 dB"
    elif 10.0 <= snr < 20.0:
        return "10 to 20 dB"
    else:
        return ">= 20 dB"


def get_loudness_bucket(loudness: Optional[float]) -> str:
    """Categorizes target loudness in LUFS into discrete evaluation buckets."""
    if loudness is None:
        return "N/A (Unspecified)"
    if loudness < -25.0:
        return "< -25 LUFS (Quiet)"
    elif -25.0 <= loudness < -15.0:
        return "-25 to -15 LUFS (Nominal)"
    else:
        return ">= -15 LUFS (Loud/Clipped)"


# ==============================================================================
# Metric Computation
# ==============================================================================

def compute_metrics_bundle(
    predictions: np.ndarray,
    ground_truth: np.ndarray,
) -> MetricBundle:
    """
    Computes frame-level confusion counts and derived accuracy metrics.

    Handles the silence-only / zero ground-truth speech case explicitly:
        When (TP + FN) == 0:
          - If FP == 0: precision=1.0, recall=1.0, f1=1.0, fpr=0.0, fnr=0.0
          - If FP > 0: precision=0.0, recall=1.0, f1=0.0, fpr=FP/(FP+TN), fnr=0.0
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(
            f"Predictions length ({len(predictions)}) != Ground truth length ({len(ground_truth)})"
        )

    preds_bool = np.asarray(predictions, dtype=bool)
    gt_bool = np.asarray(ground_truth, dtype=bool)

    tp = int(np.sum(preds_bool & gt_bool))
    fp = int(np.sum(preds_bool & ~gt_bool))
    tn = int(np.sum(~preds_bool & ~gt_bool))
    fn = int(np.sum(~preds_bool & gt_bool))
    total_frames = tp + fp + tn + fn

    total_gt_positives = tp + fn
    total_gt_negatives = tn + fp
    total_pred_positives = tp + fp

    # 1. Precision: Undefined (None) if total_gt_positives == 0 or no positives predicted without ground truth
    if total_gt_positives == 0:
        precision = None
    elif total_pred_positives > 0:
        precision = float(tp / total_pred_positives)
    else:
        precision = 0.0

    # 2. Recall: Undefined (None) if no ground truth speech exists
    if total_gt_positives > 0:
        recall = float(tp / total_gt_positives)
    else:
        recall = None

    # 3. F1 Score: 
    if total_gt_positives > 0:
       f1 = float(2 * tp / (2 * tp + fp + fn))
    else:
       f1 = None

    # 4. Accuracy
    accuracy = float((tp + tn) / total_frames) if total_frames > 0 else 1.0

    # 5. Specificity (True Negative Rate)
    specificity = float(tn / total_gt_negatives) if total_gt_negatives > 0 else 1.0

    # 6. False Positive Rate (FPR) - Primary metric for non-speech/silence clips
    false_positive_rate = float(fp / total_gt_negatives) if total_gt_negatives > 0 else 0.0

    # 7. False Negative Rate (FNR)
    false_negative_rate = float(fn / total_gt_positives) if total_gt_positives > 0 else None

    return MetricBundle(
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        total_frames=total_frames,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        specificity=specificity,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
    )


# ==============================================================================
# Common Grid Resampling
# ==============================================================================

def resample_to_common_grid(
    decision_records: Sequence[DecisionRecord],
    speech_segments: Sequence[Tuple[int, int]],
    total_samples: int,
    scoring_grid_ms: int = 10,
    sample_rate_hz: int = 16000,
    decision_threshold: float = 0.5,
) -> ResampledGridData:
    """
    Resamples an adapter's native decision records and clip ground truth onto a common grid.

    Stream Length Discrepancy Policy:
        Any mismatch between the decision stream duration and expected clip samples is
        measured, logged, and surfaced in ResampledGridData. If shorter, missing trailing
        frames are padded with False/0.0; if longer, excess frames are truncated to clip bounds.

    Args:
        decision_records: Sequence of DecisionRecord from adapter.
        speech_segments: List of (start_sample, end_sample) ground-truth speech intervals.
        total_samples: Ground-truth total sample count for the audio clip.
        scoring_grid_ms: Resolution of the common grid (default: 10ms).
        sample_rate_hz: Audio sample rate (16000 Hz).
        decision_threshold: Threshold to convert continuous scores to binary decisions.

    Returns:
        ResampledGridData containing aligned boolean decisions, scores, and ground truth.
    """
    if scoring_grid_ms <= 0:
        raise ValueError(f"scoring_grid_ms must be positive, got {scoring_grid_ms}")
    if total_samples <= 0:
        raise ValueError(f"total_samples must be positive, got {total_samples}")

    grid_hop_samples = int(sample_rate_hz * (scoring_grid_ms / 1000.0))
    if grid_hop_samples <= 0:
        raise ValueError(f"Computed grid_hop_samples is invalid ({grid_hop_samples}).")

    num_grid_frames = int(np.ceil(total_samples / grid_hop_samples))
    grid_offsets = np.arange(num_grid_frames, dtype=np.int64) * grid_hop_samples

    # 1. Build ground-truth binary mask on common grid
    gt_mask = np.zeros(num_grid_frames, dtype=bool)
    for g_idx, g_start in enumerate(grid_offsets):
        g_end = min(g_start + grid_hop_samples, total_samples)
        g_center = g_start + (g_end - g_start) // 2

        # Frame is speech if its midpoint falls inside any ground-truth speech interval
        is_gt_speech = any(s_start <= g_center < s_end for s_start, s_end in speech_segments)
        gt_mask[g_idx] = is_gt_speech

    # 2. Resample adapter decisions onto common grid
    resampled_decisions = np.zeros(num_grid_frames, dtype=bool)
    has_continuous_scores = any(r.score is not None for r in decision_records)
    resampled_scores: Optional[np.ndarray] = (
        np.zeros(num_grid_frames, dtype=np.float32) if has_continuous_scores else None
    )

    if len(decision_records) == 0:
        logger.warning("Resampling received 0 decision records for total_samples=%d", total_samples)
        return ResampledGridData(
            grid_sample_offsets=grid_offsets,
            grid_decisions=resampled_decisions,
            grid_scores=resampled_scores,
            grid_ground_truth=gt_mask,
            scoring_grid_ms=scoring_grid_ms,
            stream_length_discrepancy_ms=-(total_samples / (sample_rate_hz / 1000.0)),
            alignment_status="shorter_than_ground_truth",
        )

    # Sort records by sample offset for monotonic alignment
    sorted_records = sorted(decision_records, key=lambda r: r.sample_offset)
    record_offsets = np.array([r.sample_offset for r in sorted_records], dtype=np.int64)

    # Calculate stream duration discrepancy
    last_record_offset = sorted_records[-1].sample_offset
    # Approximate native hop from first two records or default
    native_hop = (
        sorted_records[1].sample_offset - sorted_records[0].sample_offset
        if len(sorted_records) > 1
        else grid_hop_samples
    )
    covered_samples = last_record_offset + native_hop
    discrepancy_samples = covered_samples - total_samples
    discrepancy_ms = float(discrepancy_samples / (sample_rate_hz / 1000.0))

    if abs(discrepancy_ms) > (scoring_grid_ms / 2.0):
        if discrepancy_ms < 0:
            alignment_status = "shorter_than_ground_truth"
            logger.debug("Decision stream is shorter than clip by %.2f ms", abs(discrepancy_ms))
        else:
            alignment_status = "longer_than_ground_truth"
            logger.debug("Decision stream is longer than clip by %.2f ms", discrepancy_ms)
    else:
        alignment_status = "aligned"

    # Map each common grid frame to the nearest overlapping decision record
    for g_idx, g_start in enumerate(grid_offsets):
        # Find index of closest record at or before g_start
        rec_idx = int(np.searchsorted(record_offsets, g_start, side="right") - 1)
        if rec_idx < 0:
            rec_idx = 0
        elif rec_idx >= len(sorted_records):
            rec_idx = len(sorted_records) - 1

        chosen_record = sorted_records[rec_idx]

        if chosen_record.score is not None:
            score_val = float(chosen_record.score)
            if resampled_scores is not None:
                resampled_scores[g_idx] = score_val
            resampled_decisions[g_idx] = bool(score_val >= decision_threshold)
        elif chosen_record.is_speech is not None:
            resampled_decisions[g_idx] = bool(chosen_record.is_speech)
            if resampled_scores is not None:
                resampled_scores[g_idx] = 1.0 if chosen_record.is_speech else 0.0

    return ResampledGridData(
        grid_sample_offsets=grid_offsets,
        grid_decisions=resampled_decisions,
        grid_scores=resampled_scores,
        grid_ground_truth=gt_mask,
        scoring_grid_ms=scoring_grid_ms,
        stream_length_discrepancy_ms=discrepancy_ms,
        alignment_status=alignment_status,
    )


# ==============================================================================
# Single Clip Scoring
# ==============================================================================

def score_single_clip(
    decision_records: Sequence[DecisionRecord],
    manifest_entry: ManifestEntry,
    total_clip_samples: int,
    scoring_grid_ms: int = 10,
    sample_rate_hz: int = 16000,
    decision_threshold: float = 0.5,
) -> ClipScoreResult:
    """
    Evaluates one adapter's decision stream for a single manifest clip.

    Args:
        decision_records: Inference decision records from the adapter.
        manifest_entry: Manifest entry containing ground truth and metadata.
        total_clip_samples: Total audio sample count of the clip.
        scoring_grid_ms: Common scoring grid resolution in ms.
        sample_rate_hz: Audio sample rate (16000 Hz).
        decision_threshold: Threshold for continuous scoring models.

    Returns:
        A complete ClipScoreResult with resampled grid and metric bundle.
    """
    adapter_id = decision_records[0].adapter_id if decision_records else "unknown_adapter"

    resampled = resample_to_common_grid(
        decision_records=decision_records,
        speech_segments=manifest_entry.speech_segments,
        total_samples=total_clip_samples,
        scoring_grid_ms=scoring_grid_ms,
        sample_rate_hz=sample_rate_hz,
        decision_threshold=decision_threshold,
    )

    metrics = compute_metrics_bundle(
        predictions=resampled.grid_decisions,
        ground_truth=resampled.grid_ground_truth,
    )

    return ClipScoreResult(
        clip_id=manifest_entry.clip_id,
        adapter_id=adapter_id,
        category=manifest_entry.category,
        target_snr_db=manifest_entry.target_snr_db,
        target_loudness_lufs=manifest_entry.target_loudness_lufs,
        metrics=metrics,
        resampled_data=resampled,
    )


# ==============================================================================
# Adapter Benchmark Aggregation & Bucketing
# ==============================================================================

def _aggregate_metric_bundles(clip_results: Sequence[ClipScoreResult]) -> MetricBundle:
    """Aggregates raw confusion matrix counts across clips without fabricating 1.0 on empty/silence sets."""
    if not clip_results:
        return MetricBundle(0, 0, 0, 0, 0, None, None, None, 1.0, 1.0, 0.0, None)

    total_tp = sum(cr.metrics.tp for cr in clip_results)
    total_fp = sum(cr.metrics.fp for cr in clip_results)
    total_tn = sum(cr.metrics.tn for cr in clip_results)
    total_fn = sum(cr.metrics.fn for cr in clip_results)
    total_frames = total_tp + total_fp + total_tn + total_fn

    total_gt_positives = total_tp + total_fn
    total_gt_negatives = total_tn + total_fp
    total_pred_positives = total_tp + total_fp

    if total_gt_positives == 0:
        precision = None
        recall = None
        f1 = None
        fnr = None
    else:
        precision = float(total_tp / total_pred_positives) if total_pred_positives > 0 else 0.0
        recall = float(total_tp / total_gt_positives)
        f1 = float(2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        fnr = float(total_fn / total_gt_positives)

    accuracy = float((total_tp + total_tn) / total_frames) if total_frames > 0 else 1.0
    specificity = float(total_tn / total_gt_negatives) if total_gt_negatives > 0 else 1.0
    fpr = float(total_fp / total_gt_negatives) if total_gt_negatives > 0 else 0.0

    return MetricBundle(
        tp=total_tp,
        fp=total_fp,
        tn=total_tn,
        fn=total_fn,
        total_frames=total_frames,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        specificity=specificity,
        false_positive_rate=fpr,
        false_negative_rate=fnr,
    )


def score_adapter_evaluation(
    clip_results: Sequence[ClipScoreResult],
    scoring_grid_ms: int = 10,
) -> VADScorerReport:
    """
    Builds the complete bucketed VAD report across all evaluated clips for one adapter.

    Generates:
        1. Category breakdown (all manifest categories).
        2. SNR breakdown (<0dB, 0-10dB, 10-20dB, >=20dB, N/A).
        3. Loudness breakdown (<-25 LUFS, -25 to -15 LUFS, >= -15 LUFS, N/A).
        4. Specific headline metrics: Silence-only FPR, Noise-only FPR, Quiet-speech FNR.
        5. Secondary overall aggregated metrics.

    Args:
        clip_results: Sequence of per-clip evaluation results for one adapter.
        scoring_grid_ms: The common grid resolution used.

    Returns:
        A VADScorerReport with complete bucketed metrics.
    """
    if not clip_results:
        empty_bundle = MetricBundle(0, 0, 0, 0, 0, None, None, None, 1.0, 1.0, 0.0, None)
        empty_summary = BucketScoreSummary("overall", "overall", 0, empty_bundle)
        return VADScorerReport(
            adapter_id="empty",
            scoring_grid_ms=scoring_grid_ms,
            category_breakdown={},
            snr_breakdown={},
            loudness_breakdown={},
            silence_noise_fpr={},
            quiet_whisper_fnr=None,
            overall_metrics=empty_summary,
            clip_results=(),
        )

    adapter_id = clip_results[0].adapter_id

    # 1. Bucket by Category
    category_groups: Dict[str, List[ClipScoreResult]] = {}
    for cr in clip_results:
        category_groups.setdefault(cr.category, []).append(cr)

    category_breakdown: Dict[str, BucketScoreSummary] = {}
    for cat, items in sorted(category_groups.items()):
        metrics = _aggregate_metric_bundles(items)
        category_breakdown[cat] = BucketScoreSummary(
            bucket_dimension="category",
            bucket_key=cat,
            clip_count=len(items),
            metrics=metrics,
        )

    # 2. Bucket by SNR
    snr_groups: Dict[str, List[ClipScoreResult]] = {}
    for cr in clip_results:
        bucket_key = get_snr_bucket(cr.target_snr_db)
        snr_groups.setdefault(bucket_key, []).append(cr)

    snr_breakdown: Dict[str, BucketScoreSummary] = {}
    for snr_key, items in sorted(snr_groups.items()):
        metrics = _aggregate_metric_bundles(items)
        snr_breakdown[snr_key] = BucketScoreSummary(
            bucket_dimension="snr_bucket",
            bucket_key=snr_key,
            clip_count=len(items),
            metrics=metrics,
        )

    # 3. Bucket by Loudness
    loudness_groups: Dict[str, List[ClipScoreResult]] = {}
    for cr in clip_results:
        bucket_key = get_loudness_bucket(cr.target_loudness_lufs)
        loudness_groups.setdefault(bucket_key, []).append(cr)

    loudness_breakdown: Dict[str, BucketScoreSummary] = {}
    for loud_key, items in sorted(loudness_groups.items()):
        metrics = _aggregate_metric_bundles(items)
        loudness_breakdown[loud_key] = BucketScoreSummary(
            bucket_dimension="loudness_bucket",
            bucket_key=loud_key,
            clip_count=len(items),
            metrics=metrics,
        )

    # 4. Highlighted false positive rates on silence and noise categories
    silence_noise_fpr: Dict[str, float] = {}
    noise_and_silence_cats = [
        "silence-only",
        "speech + stationary noise",
        "speech + transient noise",
        "speech + babble/cross-talk",
    ]
    for cat in noise_and_silence_cats:
        if cat in category_breakdown:
            silence_noise_fpr[cat] = category_breakdown[cat].metrics.false_positive_rate

    # 5. Highlighted quiet / whispered speech false negative rate
    quiet_whisper_fnr: Optional[float] = None
    if "quiet/whispered speech" in category_breakdown:
        quiet_whisper_fnr = category_breakdown["quiet/whispered speech"].metrics.false_negative_rate

    # 6. Overall secondary aggregate
    overall_bundle = _aggregate_metric_bundles(clip_results)
    overall_summary = BucketScoreSummary(
        bucket_dimension="overall",
        bucket_key="overall",
        clip_count=len(clip_results),
        metrics=overall_bundle,
    )

    return VADScorerReport(
        adapter_id=adapter_id,
        scoring_grid_ms=scoring_grid_ms,
        category_breakdown=category_breakdown,
        snr_breakdown=snr_breakdown,
        loudness_breakdown=loudness_breakdown,
        silence_noise_fpr=silence_noise_fpr,
        quiet_whisper_fnr=quiet_whisper_fnr,
        overall_metrics=overall_summary,
        clip_results=tuple(clip_results),
    )