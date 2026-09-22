"""
tests/regression/test_results_integrity.py
Regression test for A11 & A12: Verifies that all persisted evaluation records carry
an explicit tier field and that clip failures are persisted with diagnostic details.
"""

import pytest
from scoring.vad_scorer import MetricBundle, ResampledGridData, ClipScoreResult
from storage.results_store import ResultsStore
import numpy as np


def test_results_store_persists_tier_and_clip_failures(tmp_path):
    store_file = tmp_path / "integrity_evals.jsonl"
    store = ResultsStore(store_file)

    # 1. Store a Tier 1 scoring clip result
    metric_bundle = MetricBundle(
        tp=10, fp=1, tn=9, fn=0, total_frames=20,
        precision=0.909, recall=1.0, f1=0.952, accuracy=0.95,
        specificity=0.90, false_positive_rate=0.10, false_negative_rate=0.0
    )
    grid_data = ResampledGridData(
        grid_sample_offsets=np.arange(20),
        grid_decisions=np.ones(20, dtype=bool),
        grid_scores=None,
        grid_ground_truth=np.ones(20, dtype=bool),
        scoring_grid_ms=10,
        stream_length_discrepancy_ms=0.0,
        alignment_status="aligned",
    )
    clip_result = ClipScoreResult(
        clip_id="sample_01.wav",
        adapter_id="webrtc_vad_mode2",
        category="clean speech",
        target_snr_db=None,
        target_loudness_lufs=-20.0,
        metrics=metric_bundle,
        resampled_data=grid_data,
    )

    store.store_clip_score_result(
        run_id="run_001",
        manifest_version="hash_abc",
        clip_score_result=clip_result,
        tier="tier1",
    )

    # 2. Store a Tier 2 latency measurement
    store.store_latency_measurement(
        run_id="run_001",
        manifest_version="hash_abc",
        adapter_id="ten_vad",
        clip_id="sample_02.wav",
        latency_data={"mean_onset_latency_ms": 15.0, "mean_offset_hangover_latency_ms": 25.0},
        record_type="tier2_pipeline_latency",
        tier="tier2",
    )

    # 3. Store a clip failure record (A12)
    store.store_clip_failure(
        run_id="run_001",
        manifest_version="hash_abc",
        adapter_id="all",
        clip_id="sample_03_corrupt.wav",
        tier="tier2",
        stage="transport",
        error="Connection reset by peer",
        diagnostics={"lost_packets": 5},
    )

    records = list(store.read_raw_records())
    store.close()

    assert len(records) == 3

    # Check Tier 1 scoring record
    r1 = records[0]
    assert r1["record_type"] == "scoring_clip"
    assert r1["payload"]["tier"] == "tier1"

    # Check Tier 2 latency record
    r2 = records[1]
    assert r2["record_type"] == "tier2_pipeline_latency"
    assert r2["payload"]["tier"] == "tier2"

    # Check failure record
    r3 = records[2]
    assert r3["record_type"] == "clip_failure"
    assert r3["payload"]["tier"] == "tier2"
    assert r3["payload"]["stage"] == "transport"
    assert r3["payload"]["error"] == "Connection reset by peer"


if __name__ == "__main__":
    pytest.main([__file__])