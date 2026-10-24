"""WP-1.2 ruler test 2: VAD alignment (onset and offset lag), false alarms and misses, the smoother, DET points, bootstrap.

Synthetic tone bursts sit at known millisecond boundaries in digital silence, so every expected lag is worked out by
hand from the definitions in aqis_lab/live/score.py (decision time = end of the frame that carries the decision).
"""
import numpy as np
import pytest

from aqis_lab.live import score, vad

SR = 16000


def ms(x):
    return int(round(x * SR / 1000))


def tone_bursts(total_ms, bursts_ms, amplitude=8000, freq=440.0):
    x = np.zeros(ms(total_ms), dtype=np.int16)
    for start, end in bursts_ms:
        t = np.arange(ms(end) - ms(start)) / SR
        x[ms(start):ms(end)] = np.round(amplitude * np.sin(2 * np.pi * freq * t + 0.3)).astype(np.int16)
    return x


class EnergyVAD(vad.VADAdapter):
    """Flags a frame when any sample is louder than the threshold: a frame that holds any tone sample is speech."""

    def __init__(self, frame_ms, threshold=1000):
        self.name, self.frame_samples, self.threshold = f"energy-{frame_ms}ms", ms(frame_ms), threshold

    def reset(self):
        pass

    def process(self, frame):
        loudest = int(np.max(np.abs(frame.astype(np.int32))))
        return loudest > self.threshold, float(min(loudest / 32768.0, 1.0))


def decisions(frame_ms, flags, scores=None):
    n = len(flags)
    return vad.Decisions(frame_samples=ms(frame_ms), speech=np.array(flags, dtype=bool),
                         score=np.full(n, np.nan) if scores is None else np.array(scores, dtype=float),
                         n_scored_samples=n * ms(frame_ms), compute_s=0.0)


# ---- running a VAD over a clip ---------------------------------------------------------------------------------
def test_s2_run_vad_scores_whole_frames_and_reports_the_dropped_tail():
    out = vad.run_vad(EnergyVAD(20), tone_bursts(1000, [(100, 200)])[:3300])      # 10 frames of 320 plus 100 samples
    assert len(out.speech) == 10 and out.n_scored_samples == 3200
    assert out.frame_samples == 320 and out.score.shape == (10,)


# ---- onset and offset lag, exact ----------------------------------------------------------------------------------
@pytest.mark.parametrize("frame_ms,burst,onset_lag,offset_lag", [
    (20, (1000, 1500), 20, 0),       # aligned: the frame [1000,1020) is flagged and reported at 1020; the run ends at 1500
    (20, (1005, 1495), 15, 5),       # frame [1000,1020) reported at 1020 (15 after 1005); last flagged [1480,1500) ends 5 after 1495
    (20, (1005, 1510), 15, 10),      # tone runs into [1500,1520): the run ends at 1520, 10 after the true end 1510
    (32, (1000, 1500), 24, 4),       # frame [992,1024) reported at 1024; the tone ends inside [1472,1504), run ends at 1504
])
def test_s2_onset_and_offset_lag_are_exact(frame_ms, burst, onset_lag, offset_lag):
    x = tone_bursts(3000, [burst])
    got = score.segment_timings([list(burst)], vad.run_vad(EnergyVAD(frame_ms), x))
    assert got == [score.SegmentTiming(onset_lag_ms=pytest.approx(onset_lag), offset_lag_ms=pytest.approx(offset_lag))]


def test_s2_two_bursts_are_timed_independently():
    x = tone_bursts(3000, [(500, 800), (1200, 1700)])
    got = score.segment_timings([[500, 800], [1200, 1700]], vad.run_vad(EnergyVAD(20), x))
    assert [t.onset_lag_ms for t in got] == [20, 20] and [t.offset_lag_ms for t in got] == [0, 0]


def test_s2_a_clipped_end_gives_a_negative_offset_lag():
    # flagged frames 50..72 of 20 ms cover 1000-1460 ms; the true end is 1500 ms: 40 ms of speech was cut off
    d = decisions(20, [False] * 50 + [True] * 23 + [False] * 77)
    assert score.segment_timings([[1000, 1500]], d) == [score.SegmentTiming(20.0, -40.0)]


def test_s2_a_segment_the_vad_never_flags_is_missed():
    x = tone_bursts(2000, [(500, 900)], amplitude=500)                                # quieter than the threshold
    got = score.segment_timings([[500, 900]], vad.run_vad(EnergyVAD(20), x))
    assert got == [score.SegmentTiming(None, None)]


def test_s2_a_flag_that_began_before_the_onset_is_counted_from_the_frame_that_holds_the_onset():
    d = decisions(20, [False] * 40 + [True] * 30 + [False] * 30)                       # flagged from 800 ms
    assert score.segment_timings([[1000, 1400]], d)[0].onset_lag_ms == pytest.approx(20.0)    # frame [1000,1020), end 1020


# ---- false alarms and misses -----------------------------------------------------------------------------------
def worked_example():
    # 1 s clip, reference speech 200-600 ms, the VAD flags frames 11..31 of 20 ms = 220-640 ms
    return [[200, 600]], decisions(20, [False] * 11 + [True] * 21 + [False] * 18)


def test_s2_far_and_mdr_by_hand():
    ref, d = worked_example()
    counts = score.vad_counts(ref, d)
    assert counts == {"speech_samples": 6400, "nonspeech_samples": 9600, "missed": 320, "false_alarm": 640}
    rates = score.vad_rates(counts)
    assert rates["mdr"] == pytest.approx(320 / 6400) and rates["far"] == pytest.approx(640 / 9600)


def test_s2_a_collar_leaves_out_the_samples_around_each_boundary():
    ref, d = worked_example()
    counts = score.vad_counts(ref, d, collar_ms=50)
    # excluded: 150-250 and 550-650 ms: 1600 speech samples (200-250, 550-600) and 1600 non-speech samples
    assert counts == {"speech_samples": 4800, "nonspeech_samples": 8000, "missed": 0, "false_alarm": 0}


def test_s2_rates_are_undefined_without_samples_of_that_kind():
    counts = score.vad_counts([], decisions(20, [True] * 10))                        # no reference speech at all
    assert counts["speech_samples"] == 0 and counts["false_alarm"] == 3200
    rates = score.vad_rates(counts)
    assert rates["mdr"] is None and rates["far"] == pytest.approx(1.0)


def test_s2_reference_beyond_the_scored_frames_is_not_counted():
    d = decisions(20, [True] * 10)                                                   # 200 ms scored
    counts = score.vad_counts([[100, 1000]], d)
    assert counts["speech_samples"] == 1600 and counts["missed"] == 0


def test_s2_segments_to_mask_uses_exact_sample_boundaries():
    mask = score.segments_to_mask([[0, 10], [20, 30]], 800)
    assert mask.sum() == 320 and mask[:160].all() and not mask[160:320].any() and mask[320:480].all() and not mask[480:].any()


# ---- the smoother ----------------------------------------------------------------------------------------------
def test_s2_smoother_hand_worked():
    sm = vad.HysteresisSmoother(frame_ms=20, min_speech_ms=40, min_silence_ms=60)   # 2 speech frames on, 3 silent frames off
    raw = [0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0]
    assert sm.apply(np.array(raw, dtype=bool)).astype(int).tolist() == [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0]


def test_s2_smoother_with_one_frame_minimums_changes_nothing():
    raw = np.array([0, 1, 0, 0, 1, 1, 0], dtype=bool)
    assert np.array_equal(vad.HysteresisSmoother(20, 20, 20).apply(raw), raw)


def test_s2_smoother_rounds_minimums_up_to_whole_frames():
    sm = vad.HysteresisSmoother(frame_ms=32, min_speech_ms=64, min_silence_ms=100)  # 2 frames on, ceil(100/32) = 4 frames off
    raw = np.array([1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0], dtype=bool)
    assert sm.apply(raw).astype(int).tolist() == [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]


# ---- DET points ------------------------------------------------------------------------------------------------
def test_s2_det_points_by_hand():
    # ten 100 ms frames, reference speech 300-700 ms (frames 3..6)
    d = decisions(100, [False] * 10, scores=[0.1, 0.2, 0.6, 0.9, 0.8, 0.4, 0.55, 0.3, 0.7, 0.1])
    pts = score.det_counts([[300, 700]], d, thresholds=[0.25, 0.5, 0.75])
    assert [(p["threshold"], p["missed"], p["false_alarm"]) for p in pts] == [(0.25, 0, 4800), (0.5, 1600, 3200), (0.75, 3200, 0)]
    assert all(p["speech_samples"] == 6400 and p["nonspeech_samples"] == 9600 for p in pts)
    # thresholds 0.25: frames 2,7,8 are false alarms of 1600 samples each = 4800; 0.5: frames 2 and 8 = 3200; 0.75: none


def test_s2_det_needs_scores():
    with pytest.raises(score.ScoreError, match="scores"):
        score.det_counts([[0, 100]], decisions(20, [True] * 10), thresholds=[0.5])


# ---- bootstrap and percentiles ---------------------------------------------------------------------------------
def test_s2_cluster_ratio_ci_with_two_clusters_is_their_two_ratios():
    # an interval of 1000 resamples of two clusters: AA, AB, BB; the 2.5% and 97.5% points are the single-cluster ratios
    lo, hi = score.cluster_ratio_ci({"A": 1.0, "B": 1.0}, {"A": 2.0, "B": 98.0}, resamples=1000, seed=1)
    assert lo == pytest.approx(1 / 98) and hi == pytest.approx(1 / 2)


def test_s2_cluster_ratio_ci_is_seeded_and_collapses_for_identical_clusters():
    num = {f"s{i}": float(i % 3) for i in range(30)}
    den = {f"s{i}": 10.0 for i in range(30)}
    assert score.cluster_ratio_ci(num, den, 500, seed=2) == score.cluster_ratio_ci(num, den, 500, seed=2)
    assert score.cluster_ratio_ci(num, den, 500, seed=2) != score.cluster_ratio_ci(num, den, 500, seed=3)
    same = score.cluster_ratio_ci({f"s{i}": 1.0 for i in range(8)}, {f"s{i}": 4.0 for i in range(8)}, 200, seed=1)
    assert same == (0.25, 0.25)


def test_s2_percentiles_use_linear_interpolation():
    got = score.percentiles(list(range(1, 101)))
    assert got["p50"] == pytest.approx(50.5) and got["p95"] == pytest.approx(95.05)
    assert score.percentiles([]) == {"p50": None, "p95": None}


# ---- pooled summaries ---------------------------------------------------------------------------------------------
def test_s2_vad_summary_by_hand():
    clips = [{"cluster": "A", "counts": {"speech_samples": 1000, "nonspeech_samples": 1000, "missed": 10, "false_alarm": 20},
              "onset_lags_ms": [20, 40, None], "offset_lags_ms": [0, -40, None]},
             {"cluster": "B", "counts": {"speech_samples": 3000, "nonspeech_samples": 1000, "missed": 20, "false_alarm": 0},
              "onset_lags_ms": [20, 60], "offset_lags_ms": [10, 30]}]
    got = score.vad_summary(clips, resamples=2000, seed=1)
    assert got["mdr"] == pytest.approx(30 / 4000) and got["far"] == pytest.approx(20 / 2000)     # totals over totals
    assert got["far_ci"] == pytest.approx((0.0, 0.02)) and got["mdr_ci"] == pytest.approx((0.20 / 30, 0.01), abs=1e-9)
    assert (got["segments"], got["missed_segments"], got["segment_miss_rate"]) == (5, 1, 0.2)
    assert got["onset_p50_ms"] == pytest.approx(30.0) and got["onset_p95_ms"] == pytest.approx(57.0)     # 20 20 40 60
    assert got["offset_p50_ms"] == pytest.approx(5.0) and got["offset_p95_ms"] == pytest.approx(27.0)    # -40 0 10 30


def test_s2_stream_summary_by_hand():
    clips = [{"cluster": "A", "audio_s": 10.0, "compute_s": 2.0, "step_compute_ms": [100.0, 200.0]},
             {"cluster": "B", "audio_s": 30.0, "compute_s": 3.0, "step_compute_ms": [100.0, 300.0]}]
    got = score.stream_summary(clips, resamples=2000, seed=1)
    assert got["rtf"] == pytest.approx(5.0 / 40.0)                                       # total compute over total audio
    assert got["rtf_ci"] == pytest.approx((0.1, 0.2))                                    # cluster B alone, cluster A alone
    assert got["chunk_p50_ms"] == pytest.approx(150.0) and got["chunk_p95_ms"] == pytest.approx(285.0)   # 100 100 200 300
