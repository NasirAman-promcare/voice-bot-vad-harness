"""WP-1.3: gate features, rank scores, cluster folds without leakage, and thresholds for a rate."""
import numpy as np
import pytest

from aqis_lab.cascade import gate


@pytest.mark.parametrize("condition,channel", [("phone", "phone"), ("phone_noise_10", "phone"), ("native", "phone"),
                                               ("webrtc", "webrtc"), ("webrtc_noise_10", "webrtc"), ("clean", "wideband"),
                                               ("noise_10", "wideband")])
def test_s3_channel_of_a_condition(condition, channel):
    assert gate.channel_of(condition) == channel


def test_s3_unknown_condition_has_no_channel():
    with pytest.raises(gate.GateError, match="studio"):
        gate.channel_of("studio")


def test_s3_hypothesis_features_by_hand():
    got = gate.hyp_features("call 555 0199 now", duration_s=4.0)
    assert got == {"words": 4, "words_per_s": 1.0, "digit_tokens": 2}
    assert gate.hyp_features("", 2.0) == {"words": 0, "words_per_s": 0.0, "digit_tokens": 0}


def test_s3_feature_matrix_orders_columns_and_names_a_missing_feature():
    rows = [{"a": 1.0, "b": 2.0}, {"a": 3.0, "b": 4.0}]
    assert gate.feature_matrix(rows, ["b", "a"]).tolist() == [[2.0, 1.0], [4.0, 3.0]]
    with pytest.raises(gate.GateError, match="confidence"):
        gate.feature_matrix(rows, ["a", "confidence"])
    with pytest.raises(gate.GateError, match="confidence"):
        gate.feature_matrix([{"a": 1.0, "confidence": None}], ["confidence"])


def test_s3_single_feature_scores_follow_the_sign():
    rows = [{"duration_s": 1.0}, {"duration_s": 5.0}]
    assert gate.single_feature_scores(rows, "duration_s", +1).tolist() == [1.0, 5.0]
    assert gate.single_feature_scores(rows, "duration_s", -1).tolist() == [-1.0, -5.0]


def test_s3_channel_risk_scores_come_from_the_config_map():
    rows = [{"channel": "phone"}, {"channel": "webrtc"}, {"channel": "wideband"}]
    assert gate.channel_scores(rows, {"phone": 1.0, "webrtc": 0.5, "wideband": 0.0}).tolist() == [1.0, 0.5, 0.0]
    with pytest.raises(gate.GateError, match="wideband"):
        gate.channel_scores(rows, {"phone": 1.0, "webrtc": 0.5})


def test_s3_tiebreak_is_deterministic_and_depends_on_the_seed():
    ids = [f"u{i}" for i in range(20)]
    a = gate.tiebreak(ids, seed=1)
    assert a.tolist() == gate.tiebreak(ids, seed=1).tolist() and a.tolist() != gate.tiebreak(ids, seed=2).tolist()
    assert sorted(a.tolist()) == list(range(20))


def test_s3_cluster_folds_are_balanced_and_never_split_a_cluster():
    clusters = ["a", "b", "c", "d", "e"]
    folds = gate.folds_by_cluster(clusters, 2, seed=3)
    assert set(folds) == set(clusters) and sorted(list(folds.values()).count(f) for f in (0, 1)) == [2, 3]
    assert folds == gate.folds_by_cluster(list(reversed(clusters)), 2, seed=3)         # independent of input order


def test_s3_more_folds_than_clusters_is_an_error():
    with pytest.raises(gate.GateError, match="folds"):
        gate.folds_by_cluster(["a", "b"], 3, seed=1)


class LeakProbe:
    """Remembers the row ids it was fitted on; scores 1 for any row it has seen."""

    def fit(self, X, y):
        self.seen = set(X[:, 0].tolist())
        return self

    def score(self, X):
        return np.array([1.0 if row in self.seen else 0.0 for row in X[:, 0].tolist()])


def test_s3_out_of_fold_scores_come_from_models_that_never_saw_the_row_or_its_cluster():
    X = np.arange(12.0).reshape(12, 1)
    y = np.zeros(12)
    clusters = [f"c{i // 3}" for i in range(12)]
    got = gate.out_of_fold_scores(X, y, clusters, n_folds=2, seed=1, make_model=LeakProbe)
    assert got.tolist() == [0.0] * 12


def test_s3_hybrid_gate_ranks_the_rows_it_should_escalate_above_the_rest():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (200, 3))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    scores = gate.HybridGate(l2=1e-3, iterations=300, seed=1).fit(X, y).score(X)
    assert scores[y == 1].mean() > scores[y == 0].mean() + 0.5 and np.corrcoef(scores, X[:, 0])[0, 1] > 0.7
    assert scores.tolist() == gate.HybridGate(l2=1e-3, iterations=300, seed=1).fit(X, y).score(X).tolist()


def test_s3_gain_labels_mark_turns_where_the_heavy_model_saves_enough_errors():
    assert gate.gain_labels([4, 0, 2], [1, 0, 3], min_gain=1).tolist() == [1, 0, 0]
    assert gate.gain_labels([4, 0, 2], [1, 0, 3], min_gain=3).tolist() == [1, 0, 0]
    assert gate.gain_labels([4, 2, 2], [1, 0, 3], min_gain=2).tolist() == [1, 1, 0]


def test_s3_threshold_for_a_rate_never_splits_a_tie_and_never_exceeds_the_rate():
    scores = np.array([5.0, 4.0, 4.0, 3.0, 1.0])
    assert gate.threshold_for_rate(scores, 0.4) == 5.0           # two rows allowed; 5 and 4 would also pull in the second 4
    assert gate.threshold_for_rate(scores, 0.6) == 4.0
    assert gate.threshold_for_rate(scores, 0.0) == float("inf")
    assert gate.threshold_for_rate(scores, 1.0) == 1.0
