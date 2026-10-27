"""Sprint 3 gate policies: features of a stage 1 turn, rank scores, speaker-fold training without leakage, and thresholds.

CAPABILITIES:
  CAP-S3-020: channel_of() names a condition's channel (phone, webrtc, wideband); hyp_features() gives word count, words per second
    and digit tokens of stage 1's hypothesis; feature_matrix() orders feature columns and names a missing one;
    single_feature_scores(), channel_scores() and tiebreak() give the rank scores and the deterministic tie order of the simple
    policies [tests: test_s3_channel_of_a_condition, test_s3_unknown_condition_has_no_channel,
    test_s3_hypothesis_features_by_hand, test_s3_feature_matrix_orders_columns_and_names_a_missing_feature,
    test_s3_single_feature_scores_follow_the_sign, test_s3_channel_risk_scores_come_from_the_config_map,
    test_s3_tiebreak_is_deterministic_and_depends_on_the_seed]
  CAP-S3-021: folds_by_cluster() assigns whole speaker clusters to folds; out_of_fold_scores() scores every turn with a model fitted
    on the other folds only; HybridGate is the small logistic classifier of "the heavy model saves errors here";
    gain_labels() makes its labels [tests: test_s3_cluster_folds_are_balanced_and_never_split_a_cluster,
    test_s3_more_folds_than_clusters_is_an_error,
    test_s3_out_of_fold_scores_come_from_models_that_never_saw_the_row_or_its_cluster,
    test_s3_hybrid_gate_ranks_the_rows_it_should_escalate_above_the_rest,
    test_s3_gain_labels_mark_turns_where_the_heavy_model_saves_enough_errors]
  CAP-S3-022: threshold_for_rate() gives the lowest score threshold whose escalation share stays within a rate without splitting a tie
    [tests: test_s3_threshold_for_a_rate_never_splits_a_tie_and_never_exceeds_the_rate]
INPUTS AND OUTPUTS: feature rows (dicts), arrays and cluster names in; arrays and numbers out; GateError.
CONTRACTS: brief section 2A: the gate sees confidence, turn duration, channel and non-speech ratio from stage 1 and the audio only,
  never the heavy model's output or the reference.
INVARIANTS:
  - A trained gate's score for a turn never comes from a model that saw that turn's speaker.
  - A missing or empty feature is an error naming the feature; no value is invented.
NOT IN SCOPE:
  - Choosing policies and reading Sprint 1 files (aqis_lab/cascade/simulate.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import hashlib

import numpy as np

from aqis_lab.cascade import score
from aqis_lab.live import emotion


class GateError(ValueError):
    """A gate cannot be built from the features given."""


def channel_of(condition):
    if condition == "native" or condition.startswith("phone"):
        return "phone"
    if condition.startswith("webrtc"):
        return "webrtc"
    if condition == "clean" or condition.startswith("noise_"):
        return "wideband"
    raise GateError(f"condition {condition!r} has no channel (phone, webrtc, clean or noise_*)")


def hyp_features(hyp, duration_s):
    tokens = hyp.split()
    return {"words": len(tokens), "words_per_s": len(tokens) / duration_s if duration_s > 0 else 0.0,
            "digit_tokens": sum(1 for t in tokens if any(ch.isdigit() for ch in t))}


def feature_matrix(rows, names):
    for name in names:
        for row in rows:
            if row.get(name) is None:
                raise GateError(f"feature {name} is missing for turn {row.get('key', '?')}")
    return np.array([[float(row[name]) for name in names] for row in rows])


def single_feature_scores(rows, name, sign):
    return sign * feature_matrix(rows, [name])[:, 0]


def channel_scores(rows, risk):
    out = []
    for row in rows:
        if row["channel"] not in risk:
            raise GateError(f"channel_risk has no entry for {row['channel']}")
        out.append(risk[row["channel"]])
    return np.array(out, dtype=float)


def _hash(seed, text):
    return int.from_bytes(hashlib.sha256(f"aqis-s3|{seed}|{text}".encode("utf-8")).digest()[:8], "big")


def tiebreak(ids, seed):
    order = np.argsort([_hash(seed, i) for i in ids], kind="stable")
    ranks = np.empty(len(ids), dtype=int)
    ranks[order] = np.arange(len(ids))
    return ranks


def folds_by_cluster(clusters, n_folds, seed):
    names = sorted(set(clusters), key=lambda c: (_hash(seed, c), c))
    if n_folds > len(names):
        raise GateError(f"{n_folds} folds need at least {n_folds} speaker clusters, there are {len(names)}")
    return {c: i % n_folds for i, c in enumerate(names)}


class HybridGate:
    """Logistic regression on standardised features that scores how likely the heavy model is to save errors on a turn."""

    def __init__(self, l2=1e-2, iterations=500, seed=0):
        self.model = emotion.LogisticRegression(l2=l2, iterations=iterations, seed=seed)

    def fit(self, X, y):
        y = np.asarray(y, dtype=int)
        if len(set(y.tolist())) < 2:
            raise GateError("the gate needs turns of both kinds (heavy helps and heavy does not) to learn from")
        self.model.fit(X, y, 2)
        return self

    def score(self, X):
        return self.model.predict_proba(X)[:, 1]


def out_of_fold_scores(X, y, clusters, n_folds, seed, make_model):
    X, y = np.asarray(X), np.asarray(y)
    fold_of = folds_by_cluster(clusters, n_folds, seed)
    fold = np.array([fold_of[c] for c in clusters])
    scores = np.zeros(len(X))
    for k in range(n_folds):
        test = fold == k
        model = make_model().fit(X[~test], y[~test])
        scores[test] = model.score(X[test])
    return scores


def gain_labels(e_stage1, e_heavy, min_gain):
    return (score.oracle_scores(e_stage1, e_heavy) >= min_gain).astype(int)


def threshold_for_rate(scores, rate):
    scores = np.asarray(scores, dtype=float)
    k = score.escalation_count(len(scores), rate)
    if k == 0:
        return float("inf")
    for value in np.unique(scores):
        if (scores >= value).sum() <= k:
            return float(value)
    return float("inf")
