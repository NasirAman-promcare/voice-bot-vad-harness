"""WP-1.3 ruler tests 1 and 2: cascade arithmetic (WER from errors, escalation sets, curves, cost, latency) by hand."""
import numpy as np
import pytest

from aqis_lab.cascade import score

E1 = np.array([4, 0, 2, 6, 0, 3])            # stage 1 errors per turn
EH = np.array([1, 0, 3, 1, 0, 3])            # heavy model errors per turn
WORDS = np.full(6, 10)                       # 60 reference words in all


def test_s3_wer_is_total_errors_over_total_words():
    assert score.wer(E1, WORDS) == pytest.approx(15 / 60) and score.wer(EH, WORDS) == pytest.approx(8 / 60)
    assert score.wer([1, 2], [0, 0]) is None


def test_s3_slice_mean_wer_averages_pooled_slice_wers_not_turns():
    errors, words = [1, 1, 9], [10, 10, 10]
    # slice a: 2 errors in 20 words = 0.1; slice b: 9 in 10 = 0.9; mean 0.5 (the pooled WER is 11/30)
    assert score.mean_slice_wer(errors, words, ["a", "a", "b"]) == pytest.approx(0.5)
    assert score.wer(errors, words) == pytest.approx(11 / 30)


@pytest.mark.parametrize("n,rate,expected", [(100, 0.29, 29), (10, 0.35, 3), (10, 0.0, 0), (7, 1.0, 7), (3, 0.333, 0), (20, 0.7, 14)])
def test_s3_escalation_never_exceeds_the_rate(n, rate, expected):
    assert score.escalation_count(n, rate) == expected


def test_s3_a_rate_outside_zero_to_one_is_an_error():
    for rate in (-0.1, 1.01):
        with pytest.raises(score.ScoreError, match="rate"):
            score.escalation_count(10, rate)


def test_s3_the_gate_escalates_the_highest_scores_and_the_chosen_errors_follow():
    scores = np.array([0.9, 0.1, 0.2, 0.8, 0.0, 0.5])
    mask = score.escalation_mask(scores, 0.5)
    assert mask.tolist() == [True, False, False, True, False, True]
    chosen = score.chosen_errors(E1, EH, mask)
    assert chosen.tolist() == [1, 0, 2, 1, 0, 3] and score.wer(chosen, WORDS) == pytest.approx(7 / 60)


def test_s3_ties_are_broken_by_the_tiebreak_not_by_input_order():
    scores = np.zeros(4)
    assert score.escalation_mask(scores, 0.5, tiebreak=np.array([3, 1, 0, 2])).tolist() == [False, False, True, True]
    assert score.escalation_mask(scores, 0.5).tolist() == [True, True, False, False]


def test_s3_the_perfect_gate_picks_the_largest_error_reductions_first():
    gain = score.oracle_scores(E1, EH)
    assert gain.tolist() == [3, 0, -1, 5, 0, 0]
    curve = score.operating_curve(gain, E1, EH, WORDS, [0.0, 1 / 6, 2 / 6, 1.0])
    assert [round(p["wer"] * 60) for p in curve] == [15, 10, 7, 8]            # 15 - 5, then - 3, and all heavy is 8
    assert [p["escalated"] for p in curve] == [0, 1, 2, 6]


def test_s3_the_curve_reports_the_achieved_rate():
    curve = score.operating_curve(np.arange(10.0), np.ones(10), np.zeros(10), np.full(10, 5), [0.35])
    assert curve[0]["escalated"] == 3 and curve[0]["escalation_rate"] == pytest.approx(0.3)


def test_s3_pareto_keeps_only_points_that_lower_the_wer():
    points = [(0.0, 0.20), (0.1, 0.18), (0.2, 0.185), (0.3, 0.15), (0.35, 0.15), (0.5, 0.16)]
    assert score.pareto(points) == [(0.0, 0.20), (0.1, 0.18), (0.3, 0.15)]


def test_s3_gpu_cost_charges_stage_1_for_every_turn_and_the_heavy_model_for_escalated_ones():
    audio = np.array([10.0, 20.0, 30.0, 40.0])
    got = score.gpu_cost(audio, np.array([False, True, False, True]), rtfx_stage1=500.0, rtfx_heavy=50.0)
    assert got["cascade_s"] == pytest.approx(100 / 500 + 60 / 50) and got["all_heavy_s"] == pytest.approx(100 / 50)
    assert got["savings"] == pytest.approx(1 - 1.4 / 2.0)


def test_s3_added_latency_is_the_heavy_latency_times_the_share_of_escalated_turns():
    assert score.added_latency_ms(np.array([True, False, True, False]), 800.0) == pytest.approx(400.0)


def test_s3_paired_difference_with_a_constant_gap_collapses_to_the_gap():
    # both clusters: system a makes one more error per 10 words than system b
    errors_a, errors_b = [2, 4], [1, 3]
    got = score.paired_cluster_diff(errors_a, errors_b, [10, 10], ["x", "y"], resamples=500, seed=1)
    assert got["diff"] == pytest.approx(0.1) and got["ci"] == pytest.approx((0.1, 0.1)) and got["verdict"] == "B beats A"


def test_s3_paired_difference_that_changes_sign_across_clusters_is_too_close_to_call():
    got = score.paired_cluster_diff([2, 0], [0, 2], [10, 10], ["x", "y"], resamples=500, seed=1)
    assert got["diff"] == pytest.approx(0.0) and got["verdict"] == "too close to call"
    assert score.paired_cluster_diff([2, 0], [0, 2], [10, 10], ["x", "y"], 500, 1) == got           # same seed, same answer


def test_s3_targets_are_met_only_when_both_limits_hold():
    assert score.meets_gate(0.1199, 0.35, wer_max=0.12, rate_max=0.35)
    assert not score.meets_gate(0.1201, 0.30, wer_max=0.12, rate_max=0.35)
    assert not score.meets_gate(0.10, 0.351, wer_max=0.12, rate_max=0.35)


def test_s3_non_regression_allows_a_drop_of_at_most_the_limit():
    assert score.non_regression(0.100, 0.1049, max_increase=0.005)["ok"]
    got = score.non_regression(0.100, 0.1051, max_increase=0.005)
    assert not got["ok"] and got["delta"] == pytest.approx(0.0051)


def test_s3_recall_gain_counts_found_entities():
    got = score.recall_change(found_pre=40, found_post=75, total=100)
    assert got == {"pre": 0.4, "post": 0.75, "gain": pytest.approx(0.35)}
