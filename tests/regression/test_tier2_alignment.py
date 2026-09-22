"""
tests/regression/test_tier2_alignment.py
Regression test for A01 & A02: Verifies that marker alignment accurately computes
sample_delta and time_zero_timestamp_ns without any 20ms marker offset bias.
"""

import dataclasses
import numpy as np
import pytest
from corpus.manifest import ManifestEntry
from latency.latency_calculator import calculate_pipeline_latency
from latency.marker_alignment import align_marker, generate_reference_marker
from scoring.vad_scorer import score_single_clip
from vad_adapters.adapter_contract import DecisionRecord


def test_tier2_realignment_recovers_ground_truth_accuracy():
    sample_rate = 16000
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

    chirp = generate_reference_marker(sample_rate)

    pre_rolls_ms = [0, 20, 250]

    for p_ms in pre_rolls_ms:
        p_samples = int(sample_rate * (p_ms / 1000.0))

        # Synthetic received audio: [pre-roll silence][lead-in 320 smp][chirp 960 smp][silence]
        lead_in = np.zeros(320, dtype=np.float32)
        tail = np.zeros(clip_len, dtype=np.float32)
        rec_audio = np.concatenate([np.zeros(p_samples, dtype=np.float32), lead_in, chirp, tail])

        # Run real align_marker with physical arrival timestamp at 1.0s
        stream_t0_ns = 1_000_000_000
        alignment_result = align_marker(
            received_audio=rec_audio,
            reference_marker_offset=320,
            stream_start_timestamp_ns=stream_t0_ns,
            sample_rate_hz=sample_rate,
        )

        assert alignment_result.marker_detected is True
        assert alignment_result.status == "detected"
        assert alignment_result.sample_offset_delta == p_samples

        # Verify time_zero_timestamp_ns is EXACTLY when clip sample 0 arrived (no 20ms bias)
        expected_clip_s0_ns = stream_t0_ns + int((p_samples / sample_rate) * 1e9)
        assert alignment_result.time_zero_timestamp_ns == expected_clip_s0_ns

        # Generate capture decision records shifted by p_samples
        hop = 160
        raw_records = []
        for frame_idx, offset in enumerate(range(0, clip_len + p_samples, hop)):
            is_active = (gt_start + p_samples) <= offset < (gt_end + p_samples)
            # Simulate produced timestamp with 10ms processing latency
            frame_arr_ns = stream_t0_ns + int((offset / sample_rate) * 1e9)
            produced_ns = frame_arr_ns + 10_000_000
            raw_records.append(
                DecisionRecord(
                    adapter_id="perfect_vad",
                    sample_offset=offset,
                    frame_index=frame_idx,
                    is_speech=is_active,
                    score=1.0 if is_active else 0.0,
                    produced_timestamp_ns=produced_ns,
                )
            )

        # Realignment step: shift by -delta
        delta = alignment_result.sample_offset_delta
        aligned_records = [
            dataclasses.replace(r, sample_offset=r.sample_offset - delta)
            for r in raw_records
            if 0 <= (r.sample_offset - delta) < clip_len
        ]

        # 1. Verify accuracy score F1 == 1.000
        clip_score = score_single_clip(
            decision_records=aligned_records,
            manifest_entry=entry,
            total_clip_samples=clip_len,
            scoring_grid_ms=10,
            sample_rate_hz=sample_rate,
        )
        assert clip_score.metrics.f1 == 1.0

        # 2. Verify onset decision delay == 0.0 ms
        lat_res = calculate_pipeline_latency(
            decision_records=aligned_records,
            speech_segments=entry.speech_segments,
            time_zero_ns=alignment_result.time_zero_timestamp_ns,
            sample_rate_hz=sample_rate,
        )
        assert lat_res.mean_onset_latency_ms == 0.0

        # 3. Verify true wall-clock pipeline latency == +10.0 ms (no -20ms error)
        assert lat_res.mean_wallclock_pipeline_latency_ms == pytest.approx(10.0, abs=1.0)


if __name__ == "__main__":
    pytest.main([__file__])