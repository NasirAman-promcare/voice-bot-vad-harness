"""
latency/latency_calculator.py

One Job:
    Compute Tier-2-only pipeline latency metrics — Onset Latency and Offset / Hangover
    Latency — from marker-aligned decision timestamps, maintaining them as two strictly
    independent numbers that are NEVER collapsed or averaged together into one generic value.

Why Algorithmic Latency is NOT computed here:
    Algorithmic latency (pure compute time per frame) is measured in Tier 1 inline
    around the adapter's direct inference call. This module measures acoustic and pipeline
    reaction times in the live stream:
      1. Onset Latency: Real speech starts (ground truth) -> VAD's first "speech" decision.
      2. Offset / Hangover Latency: Real speech ends (ground truth) -> VAD's first "non-speech" decision.

Single-Clock Authority (Defending against Cross-Process Clock Skew):
    Subtractive latency math must NEVER compare timestamps from different physical machines
    or separate processes (e.g. subtracting Speaker Bot's local wall clock from Listener Bot's).
    All measurements in this file are referenced to the Listener Bot's own monotonic timeline,
    anchored to the physical acoustic Time Zero ($T_0$) established upstream via
    marker_alignment.py's cross-correlation chirp alignment.

Explicit Undefined Markers (Zero and Duration Corruption Defense):
    - False Negative (VAD never detects speech in a segment): `onset_latency_ms` is explicitly
      None (`onset_detected=False`). It is NEVER set to 0.0 or the clip's full duration.
    - Unresolved Hangover (VAD never returns to non-speech before clip ends):
      `offset_hangover_latency_ms` is explicitly None (`hangover_resolved=False`). It is NEVER
      defaulted to clip length.

What this module must NEVER do:
    - Never collapse onset and offset latency into a single "average latency" metric.
    - Never subtract timestamps originating from different process clocks.
    - Never fabricate latency values for missed speech or unresolved hangovers.
    - Never perform scoring, confusion matrix math, or spectral profiling.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from vad_adapters.adapter_contract import DecisionRecord

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class LatencyCalculationError(Exception):
    """Raised when latency calculation fails due to corrupted inputs or mismatched bounds."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class SegmentLatency:
    """
    Latency measurements for a single ground-truth speech segment.
    """
    segment_index: int
    gt_start_sample: int
    gt_end_sample: int
    onset_detected: bool
    onset_latency_ms: Optional[float]
    hangover_resolved: bool
    offset_hangover_latency_ms: Optional[float]
    first_speech_sample_offset: Optional[int]
    first_non_speech_sample_offset: Optional[int]
    triggered_early: bool = False
    cut_off_early: bool = False
    wallclock_pipeline_latency_ms: Optional[float] = None


@dataclass(frozen=True)
class PipelineLatencyResult:
    """
    Complete Tier 2 latency results for an adapter on a single audio clip.

    Guarantees:
        Onset and offset/hangover latencies remain strictly separated.
    """
    clip_id: str
    adapter_id: str
    has_speech: bool
    total_speech_segments: int
    detected_onsets_count: int
    resolved_hangovers_count: int
    segment_latencies: Tuple[SegmentLatency, ...]
    # Separate headline latency numbers (NEVER averaged together)
    mean_onset_latency_ms: Optional[float]
    median_onset_latency_ms: Optional[float]
    mean_offset_hangover_latency_ms: Optional[float]
    median_offset_hangover_latency_ms: Optional[float]
    mean_wallclock_pipeline_latency_ms: Optional[float] = None
    median_wallclock_pipeline_latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the result into a JSON-compatible dictionary."""
        return asdict(self)


# ==============================================================================
# Latency Calculation Logic
# ==============================================================================

def calculate_pipeline_latency(
    decision_records: Sequence[DecisionRecord],
    speech_segments: Sequence[Tuple[int, int]],
    time_zero_ns: int,
    marker_alignment: Optional[Any] = None,
    sample_rate_hz: int = 16000,
    decision_threshold: float = 0.5,
    clip_id: str = "unknown_clip",
) -> PipelineLatencyResult:
    """
    Computes onset and offset/hangover latencies on the single Listener Bot clock.

    Args:
        decision_records: Monotonically ordered decision stream from one adapter.
        speech_segments: List of (start_sample, end_sample) ground-truth speech intervals.
        time_zero_ns: Monotonic nanosecond timestamp of sample 0 established by marker_alignment.
        marker_alignment: MarkerAlignmentResult object for diagnostic cross-referencing.
        sample_rate_hz: Expected sample rate (16000 Hz).
        decision_threshold: Threshold to evaluate continuous probability scores.
        clip_id: Unique clip identifier for traceability.

    Returns:
        A PipelineLatencyResult with independent onset and offset latency statistics.

    Raises:
        ValueError: If sample_rate_hz is not 16000.
    """
    if sample_rate_hz != 16000:
        raise ValueError(f"Latency calculation requires 16000 Hz sample rate, got {sample_rate_hz}.")

    adapter_id = decision_records[0].adapter_id if decision_records else "unknown_adapter"

    # Edge Case: Silence-only clip (no ground-truth speech)
    if not speech_segments:
        return PipelineLatencyResult(
            clip_id=clip_id,
            adapter_id=adapter_id,
            has_speech=False,
            total_speech_segments=0,
            detected_onsets_count=0,
            resolved_hangovers_count=0,
            segment_latencies=(),
            mean_onset_latency_ms=None,
            median_onset_latency_ms=None,
            mean_offset_hangover_latency_ms=None,
            median_offset_hangover_latency_ms=None,
        )

    if not decision_records:
        # 100% False Negative (no decisions emitted)
        seg_results = [
            SegmentLatency(
                segment_index=idx,
                gt_start_sample=start,
                gt_end_sample=end,
                onset_detected=False,
                onset_latency_ms=None,
                hangover_resolved=False,
                offset_hangover_latency_ms=None,
                first_speech_sample_offset=None,
                first_non_speech_sample_offset=None,
            )
            for idx, (start, end) in enumerate(speech_segments)
        ]
        return PipelineLatencyResult(
            clip_id=clip_id,
            adapter_id=adapter_id,
            has_speech=True,
            total_speech_segments=len(speech_segments),
            detected_onsets_count=0,
            resolved_hangovers_count=0,
            segment_latencies=tuple(seg_results),
            mean_onset_latency_ms=None,
            median_onset_latency_ms=None,
            mean_offset_hangover_latency_ms=None,
            median_offset_hangover_latency_ms=None,
        )

    # Sort records by sample offset to guarantee monotonic progression
    records = sorted(decision_records, key=lambda r: r.sample_offset)

    # Extract boolean decisions
    def is_speech_active(record: DecisionRecord) -> bool:
        if record.is_speech is not None:
            return bool(record.is_speech)
        if record.score is not None:
            return bool(record.score >= decision_threshold)
        return False

    segment_latencies: List[SegmentLatency] = []
    valid_onset_latencies: List[float] = []
    valid_offset_latencies: List[float] = []
    valid_wallclock_latencies: List[float] = []

    for seg_idx, (gt_start, gt_end) in enumerate(speech_segments):
        prev_seg_end = speech_segments[seg_idx - 1][1] if seg_idx > 0 else 0
        next_seg_start = (
            speech_segments[seg_idx + 1][0]
            if seg_idx + 1 < len(speech_segments)
            else float("inf")
        )

        # ----------------------------------------------------------------------
        # 1. Onset Latency (Decision Delay & True Wall-Clock Transit)
        # ----------------------------------------------------------------------
        first_speech_record: Optional[DecisionRecord] = None

        search_onset_start = (prev_seg_end + gt_start) // 2
        for rec in records:
            if search_onset_start <= rec.sample_offset <= gt_end:
                if is_speech_active(rec):
                    first_speech_record = rec
                    break

        triggered_early = False
        wallclock_latency_ms: Optional[float] = None

        if first_speech_record is not None:
            # Sample-domain decision delay (A01: signed, unclamped)
            delta_samples = first_speech_record.sample_offset - gt_start
            onset_latency_ms = round((delta_samples / 16000.0) * 1000.0, 2)
            if delta_samples < 0:
                triggered_early = True

            # Wall-clock pipeline latency (A02): production timestamp minus physical arrival time of speech start
            if time_zero_ns > 0 and first_speech_record.produced_timestamp_ns > 0:
                expected_speech_arrival_ns = time_zero_ns + int((gt_start / 16000.0) * 1_000_000_000)
                wc_delta = (first_speech_record.produced_timestamp_ns - expected_speech_arrival_ns) / 1_000_000.0
                wallclock_latency_ms = round(wc_delta, 2)
                valid_wallclock_latencies.append(wallclock_latency_ms)

            onset_detected = True
            first_speech_offset = first_speech_record.sample_offset
            valid_onset_latencies.append(onset_latency_ms)
        else:
            onset_detected = False
            onset_latency_ms = None
            first_speech_offset = None

        # ----------------------------------------------------------------------
        # 2. Offset / Hangover Latency: Speech End -> First "Non-Speech" Transition
        # ----------------------------------------------------------------------
        last_speech_record: Optional[DecisionRecord] = None
        for rec in records:
            if rec.sample_offset < next_seg_start and is_speech_active(rec):
                if rec.sample_offset >= (gt_start - 320):
                    last_speech_record = rec

        hangover_resolved = False
        hangover_latency_ms = None
        first_non_speech_offset = None
        cut_off_early = False

        if last_speech_record is not None:
            following_non_speech = [
                r for r in records
                if r.sample_offset > last_speech_record.sample_offset and r.sample_offset < next_seg_start and not is_speech_active(r)
            ]

            if following_non_speech:
                first_non_speech_record = following_non_speech[0]
                delta_samples = first_non_speech_record.sample_offset - gt_end
                hangover_latency_ms = round((delta_samples / 16000.0) * 1000.0, 2)
                if last_speech_record.sample_offset < gt_end - 160:
                    cut_off_early = True

                hangover_resolved = True
                first_non_speech_offset = first_non_speech_record.sample_offset
                valid_offset_latencies.append(hangover_latency_ms)
            else:
                hangover_resolved = False
        else:
            hangover_resolved = False

        segment_latencies.append(
            SegmentLatency(
                segment_index=seg_idx,
                gt_start_sample=gt_start,
                gt_end_sample=gt_end,
                onset_detected=onset_detected,
                onset_latency_ms=onset_latency_ms,
                hangover_resolved=hangover_resolved,
                offset_hangover_latency_ms=hangover_latency_ms,
                first_speech_sample_offset=first_speech_offset,
                first_non_speech_sample_offset=first_non_speech_offset,
                triggered_early=triggered_early,
                cut_off_early=cut_off_early,
                wallclock_pipeline_latency_ms=wallclock_latency_ms,
            )
        )

    # Compute aggregate statistics independently
    mean_onset = round(float(np.mean(valid_onset_latencies)), 2) if valid_onset_latencies else None
    median_onset = round(float(np.median(valid_onset_latencies)), 2) if valid_onset_latencies else None
    mean_offset = round(float(np.mean(valid_offset_latencies)), 2) if valid_offset_latencies else None
    median_offset = round(float(np.median(valid_offset_latencies)), 2) if valid_offset_latencies else None
    mean_wallclock = round(float(np.mean(valid_wallclock_latencies)), 2) if valid_wallclock_latencies else None
    median_wallclock = round(float(np.median(valid_wallclock_latencies)), 2) if valid_wallclock_latencies else None

    return PipelineLatencyResult(
        clip_id=clip_id,
        adapter_id=adapter_id,
        has_speech=True,
        total_speech_segments=len(speech_segments),
        detected_onsets_count=len(valid_onset_latencies),
        resolved_hangovers_count=len(valid_offset_latencies),
        segment_latencies=tuple(segment_latencies),
        mean_onset_latency_ms=mean_onset,
        median_onset_latency_ms=median_onset,
        mean_offset_hangover_latency_ms=mean_offset,
        median_offset_hangover_latency_ms=median_offset,
        mean_wallclock_pipeline_latency_ms=mean_wallclock,
        median_wallclock_pipeline_latency_ms=median_wallclock,
    )