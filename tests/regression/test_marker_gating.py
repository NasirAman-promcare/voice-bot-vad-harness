"""
tests/regression/test_marker_gating.py
Regression test for A03: Verifies that clips with low marker confidence or failed alignment
are gated out and persisted as failure records without polluting benchmark accuracy rows.
"""

import pytest
import numpy as np
from latency.marker_alignment import align_marker, MarkerAlignmentResult
from storage.results_store import ResultsStore


def test_low_confidence_marker_is_gated(tmp_path):
    # Pure noise buffer with no chirp marker
    rng = np.random.RandomState(42)
    noise_audio = rng.normal(0, 0.05, 32000).astype(np.float32)

    result = align_marker(
        received_audio=noise_audio,
        reference_marker_offset=320,
        sample_rate_hz=16000,
        min_confidence_threshold=0.50,
    )

    # Must not report detected
    assert result.marker_detected is False
    assert result.status in ("low_confidence", "correlation_failed")

    # Verify ResultsStore failure persistence behavior
    store_file = tmp_path / "test_evals.jsonl"
    store = ResultsStore(store_file)

    if not result.marker_detected or result.status != "detected":
        store.store_clip_failure(
            run_id="test_run",
            manifest_version="hash123",
            adapter_id="all",
            clip_id="noisy_clip_001.wav",
            tier="tier2",
            stage="marker_gating",
            error=f"Marker status: {result.status}",
        )

    records = list(store.read_raw_records())
    store.close()

    assert len(records) == 1
    assert records[0]["record_type"] == "clip_failure"
    assert records[0]["payload"]["stage"] == "marker_gating"


if __name__ == "__main__":
    pytest.main([__file__])