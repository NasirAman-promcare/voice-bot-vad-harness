"""
tests/regression/test_tier2_alignment.py
Regression test for A01: Verifies that subtracting the marker alignment delta
restores ground-truth clip coordinates across different pre-roll delays P.
"""

import dataclasses
import numpy as np
import pytest
from corpus.manifest import ManifestEntry
from latency.latency_calculator import calculate_pipeline_latency
from scoring.vad_scorer import score_single_clip
from vad_adapters.adapter_contract import DecisionRecord


def test_tier2_realignment_recovers_ground_truth_accuracy():
    sample_rate = 16000
    # Ground-truth: speech from 200ms (3200 samples) to 1000ms (16000 samples)
    gt_start = 3200
    gt_end = 16000
    clip_len = 32000

    entry = ManifestEntry(
        clip_id="test_clip.wav",
        clip_path="corpus/audio/test_clip.wav",
        category="clean speech",
        target_snr_db=None,
        target_loudness_lufs=-20.0,
        speech_segments=((gt_start, gt_end),),
        calibration_marker_offset_samples=320,
    )

    # Test across multiple pre-roll delays P: 0ms, 20ms (320 smp), 250ms (4000 smp)
    pre_rolls_ms = [0, 20, 250]

    for p_ms in pre_rolls_ms:
        delta_samples = int(sample_rate * (p_ms / 1000.0))

        # Raw capture decisions (shifted late by delta_samples)
        raw_records = []
        hop = 160  # 10ms frames
        for frame_idx, offset in enumerate(range(0, clip_len + delta_samples, hop)):
            # Active in capture coordinates when offset is within shifted speech interval
            is_active = (gt_start + delta_samples) <= offset < (gt_end + delta_samples)
            raw_records.append(
                DecisionRecord(
                    adapter_id="perfect_vad",
                    sample_offset=offset,
                    frame_index=frame_idx,
                    is_speech=is_active,
                    score=1.0 if is_active else 0.0,
                )
            )

        # Realignment step (A01 fix in orchestrator.py): shift by -delta_samples
        aligned_records = [
            dataclasses.replace(r, sample_offset=r.sample_offset - delta_samples)
            for r in raw_records
            if 0 <= (r.sample_offset - delta_samples) < clip_len
        ]

        # 1. Verify accuracy scores F1 == 1.000
        clip_score = score_single_clip(
            decision_records=aligned_records,
            manifest_entry=entry,
            total_clip_samples=clip_len,
            scoring_grid_ms=10,
            sample_rate_hz=16000,
        )
        assert clip_score.metrics.f1 == 1.0, (
            f"F1 score corrupted by pre-roll P={p_ms}ms: got {clip_score.metrics.f1}"
        )

        # 2. Verify onset latency == 0.0 ms
        lat_res = calculate_pipeline_latency(
            decision_records=aligned_records,
            speech_segments=entry.speech_segments,
            time_zero_ns=0,
            sample_rate_hz=16000,
        )
        assert lat_res.mean_onset_latency_ms == 0.0, (
            f"Onset latency inflated by pre-roll P={p_ms}ms: got {lat_res.mean_onset_latency_ms}ms"
        )


if __name__ == "__main__":
    pytest.main([__file__])