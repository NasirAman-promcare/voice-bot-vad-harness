"""
tests/regression/test_hangover_cutoff.py
Regression test for A07: Verifies that cutting speech off early produces a signed negative
hangover and sets cut_off_early=True without clamping to 0 or reporting fake positive hangover.
"""

import pytest
from latency.latency_calculator import calculate_pipeline_latency
from vad_adapters.adapter_contract import DecisionRecord


def test_early_speech_cutoff_reports_negative_hangover():
    # Ground truth speech: 100ms (1600 samples) to 600ms (9600 samples) -> 500ms duration
    gt_start = 1600
    gt_end = 9600
    gt_segments = ((gt_start, gt_end),)

    # VAD triggers on time at 1600, but terminates early at 400ms (6400 samples) -> 200ms early cutoff
    cutoff_sample = 6400
    records = []
    hop = 160  # 10ms

    for offset in range(0, 16000, hop):
        is_speech = (gt_start <= offset < cutoff_sample)
        records.append(
            DecisionRecord(
                adapter_id="aggressive_vad",
                sample_offset=offset,
                frame_index=offset // hop,
                is_speech=is_speech,
                score=1.0 if is_speech else 0.0,
            )
        )

    res = calculate_pipeline_latency(
        decision_records=records,
        speech_segments=gt_segments,
        time_zero_ns=0,
        sample_rate_hz=16000,
    )

    seg = res.segment_latencies[0]
    assert seg.cut_off_early is True, "Expected cut_off_early to be True"
    assert seg.hangover_resolved is True
    # Non-speech transition occurred at 6400. Delta = 6400 - 9600 = -3200 samples = -200.0 ms
    assert seg.offset_hangover_latency_ms == pytest.approx(-200.0, abs=10.0)


def test_early_trigger_reports_negative_onset_latency():
    # Ground truth speech starts at 500ms (8000 samples)
    gt_start = 8000
    gt_end = 12000
    gt_segments = ((gt_start, gt_end),)

    # VAD triggers 100ms early at 400ms (6400 samples)
    early_trigger_sample = 6400
    records = []
    hop = 160

    for offset in range(0, 16000, hop):
        is_speech = (early_trigger_sample <= offset < gt_end)
        records.append(
            DecisionRecord(
                adapter_id="sensitive_vad",
                sample_offset=offset,
                frame_index=offset // hop,
                is_speech=is_speech,
                score=1.0 if is_speech else 0.0,
            )
        )

    res = calculate_pipeline_latency(
        decision_records=records,
        speech_segments=gt_segments,
        time_zero_ns=0,
        sample_rate_hz=16000,
    )

    seg = res.segment_latencies[0]
    assert seg.triggered_early is True, "Expected triggered_early to be True"
    # Delta = 6400 - 8000 = -1600 samples = -100.0 ms
    assert seg.onset_latency_ms == pytest.approx(-100.0, abs=10.0)


if __name__ == "__main__":
    pytest.main([__file__])