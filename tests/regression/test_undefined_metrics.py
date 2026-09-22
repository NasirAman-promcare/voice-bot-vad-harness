"""
tests/regression/test_undefined_metrics.py
Regression test for A08: Verifies that mathematically undefined metrics on silence clips
and empty adapter sets return None instead of fabricated 1.000 or 0.000 values.
"""

import numpy as np
import pytest
from scoring.vad_scorer import (
    compute_metrics_bundle,
    score_adapter_evaluation,
    _aggregate_metric_bundles,
)


def test_silence_only_clip_returns_none_for_precision_recall_f1():
    # 200 frames of non-speech ground truth (silence-only clip)
    gt = np.zeros(200, dtype=bool)

    # Case A: VAD remains silent (FP = 0)
    preds_silent = np.zeros(200, dtype=bool)
    bundle_silent = compute_metrics_bundle(preds_silent, gt)
    assert bundle_silent.precision is None
    assert bundle_silent.recall is None
    assert bundle_silent.f1 is None
    assert bundle_silent.false_positive_rate == 0.0
    assert bundle_silent.accuracy == 1.0

    # Case B: VAD triggers 2 false alarms (FP = 2)
    preds_noisy = np.zeros(200, dtype=bool)
    preds_noisy[10] = True
    preds_noisy[20] = True
    bundle_noisy = compute_metrics_bundle(preds_noisy, gt)
    assert bundle_noisy.precision is None
    assert bundle_noisy.recall is None
    assert bundle_noisy.f1 is None
    assert bundle_noisy.false_positive_rate == pytest.approx(2 / 200, rel=1e-3)


def test_empty_adapter_evaluation_returns_none():
    report = score_adapter_evaluation([], scoring_grid_ms=10)
    assert report.adapter_id == "empty"
    assert report.overall_metrics.clip_count == 0
    assert report.overall_metrics.metrics.precision is None
    assert report.overall_metrics.metrics.recall is None
    assert report.overall_metrics.metrics.f1 is None

def test_correlation_engine_handles_silence_clips_without_type_error():
    from scoring.vad_scorer import score_single_clip
    from scoring.correlation_engine import build_weakness_heatmap
    from corpus.manifest import ManifestEntry
    from vad_adapters.adapter_contract import DecisionRecord

    # Create a silence clip score result with None precision/recall/f1
    entry = ManifestEntry(
        clip_id="silence_test_01.wav",
        clip_path="corpus/audio/silence_test_01.wav",
        category="silence-only",
        target_snr_db=None,
        target_loudness_lufs=-60.0,
        speech_segments=(),
        calibration_marker_offset_samples=320,
    )
    records = [
        DecisionRecord(adapter_id="vad_a", sample_offset=0, frame_index=0, is_speech=False, score=0.0)
    ]
    clip_res = score_single_clip(
        decision_records=records,
        manifest_entry=entry,
        total_clip_samples=16000,
        scoring_grid_ms=10,
        sample_rate_hz=16000,
    )

    assert clip_res.metrics.f1 is None
    assert clip_res.metrics.precision is None

    # Must build weakness heatmap without TypeError
    report = build_weakness_heatmap(
        scores=[clip_res],
        run_id="silence_run",
        manifest_version="v1_hash",
    )
    cell = report.get_cell("vad_a", "silence-only")
    assert cell.is_empty is False
    assert cell.f1 is None
    assert cell.false_positive_rate == 0.0


if __name__ == "__main__":
    pytest.main([__file__])