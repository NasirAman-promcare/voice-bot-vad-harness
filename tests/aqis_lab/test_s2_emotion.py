"""WP-1.2 ruler test 5: UAR, recalls and confusion matrices, label mapping, and the acoustic baseline's features.

All expected values are worked out by hand from the 4-class definitions of the brief (section 4, item 4).
"""
import numpy as np
import pytest

from aqis_lab.live import emotion, score

N, A, S, H = emotion.CLASSES.index("neutral"), emotion.CLASSES.index("anger"), emotion.CLASSES.index("sadness"), \
    emotion.CLASSES.index("happiness")


def labels_from(confusion):
    """(y_true, y_pred) that give a confusion matrix (rows true, columns predicted)."""
    y_true, y_pred = [], []
    for t, row in enumerate(confusion):
        for p, n in enumerate(row):
            y_true += [t] * n
            y_pred += [p] * n
    return y_true, y_pred


CONFUSION = [[16, 2, 1, 1],        # neutral 20: recall 0.8
             [0, 9, 0, 1],         # anger 10: recall 0.9
             [2, 0, 7, 1],         # sadness 10: recall 0.7
             [1, 1, 0, 8]]         # happiness 10: recall 0.8


def test_s2_class_order_is_neutral_anger_sadness_happiness():
    assert emotion.CLASSES == ("neutral", "anger", "sadness", "happiness")


def test_s2_confusion_matrix_by_hand():
    y_true, y_pred = labels_from(CONFUSION)
    assert score.confusion_matrix(y_true, y_pred).tolist() == CONFUSION


def test_s2_uar_is_the_mean_of_class_recalls_not_accuracy():
    y_true, y_pred = labels_from(CONFUSION)
    m = score.confusion_matrix(y_true, y_pred)
    assert score.class_recalls(m).tolist() == pytest.approx([0.8, 0.9, 0.7, 0.8])
    assert score.uar(m) == pytest.approx(0.8)                              # (0.8 + 0.9 + 0.7 + 0.8) / 4
    assert score.accuracy(m) == pytest.approx(40 / 50)                     # diagonal 16 + 9 + 7 + 8 = 40 of 50


def test_s2_uar_and_accuracy_differ_when_classes_are_unbalanced():
    m = score.confusion_matrix(*labels_from([[18, 2, 0, 0], [3, 7, 0, 0], [0, 0, 5, 5], [0, 0, 0, 10]]))
    # recalls 0.9, 0.7, 0.5, 1.0 -> UAR 0.775; accuracy (18 + 7 + 5 + 10) / 50 = 0.8
    assert score.uar(m) == pytest.approx(0.775) and score.accuracy(m) == pytest.approx(0.8)


def test_s2_frustration_recall_is_the_anger_recall():
    m = score.confusion_matrix(*labels_from(CONFUSION))
    assert score.frustration_recall(m) == pytest.approx(0.9)


def test_s2_a_class_without_samples_has_undefined_recall_and_uar():
    m = score.confusion_matrix([0, 0, 1, 1], [0, 1, 1, 1])                 # no sadness, no happiness samples
    assert np.isnan(score.class_recalls(m)[S]) and score.uar(m) is None


def test_s2_phone_cost_is_uar_phone_over_uar_clean():
    assert score.phone_cost(0.6, 0.8) == pytest.approx(0.75)
    assert score.phone_cost(0.6, None) is None


def test_s2_uar_ci_resamples_actors():
    # two actors with opposite behaviour: resampling two clusters gives only AA, AB or BB
    y_true = [0, 1, 2, 3] * 2
    pred_good, pred_bad = [0, 1, 2, 3], [1, 2, 3, 0]
    lo, hi = score.uar_ci(y_true, pred_good + pred_bad, ["good"] * 4 + ["bad"] * 4, resamples=1000, seed=1)
    assert lo == pytest.approx(0.0) and hi == pytest.approx(1.0)
    assert score.uar_ci(y_true, pred_good + pred_bad, ["good"] * 4 + ["bad"] * 4, 1000, 1) == (lo, hi)


# ---- label mapping ---------------------------------------------------------------------------------------------
def test_s2_nine_class_scores_are_restricted_to_the_four_classes_and_renormalised():
    labels = ["angry", "disgusted", "fearful", "happy", "neutral", "other", "sad", "surprised", "unknown"]
    scores = [0.30, 0.10, 0.05, 0.10, 0.20, 0.05, 0.10, 0.05, 0.05]
    got = emotion.map_scores(labels, scores)
    # kept: neutral 0.20, angry 0.30, sad 0.10, happy 0.10 (sum 0.70)
    assert got.tolist() == pytest.approx([0.20 / 0.70, 0.30 / 0.70, 0.10 / 0.70, 0.10 / 0.70])


def test_s2_labels_are_read_after_the_slash_and_in_any_case():
    got = emotion.map_scores(["生气/angry", "开心/happy", "中立/neutral", "难过/sad"], [0.4, 0.3, 0.2, 0.1])
    assert got.tolist() == pytest.approx([0.2, 0.4, 0.1, 0.3])


def test_s2_short_superb_labels_map_too():
    assert emotion.map_scores(["neu", "hap", "ang", "sad"], [0.1, 0.2, 0.3, 0.4]).tolist() == pytest.approx([0.1, 0.3, 0.4, 0.2])


def test_s2_labels_missing_a_target_class_are_an_error():
    with pytest.raises(emotion.EmotionError, match="happiness"):
        emotion.map_scores(["angry", "neutral", "sad"], [0.3, 0.3, 0.4])


def test_s2_crema_d_labels_map_to_the_four_classes_and_other_emotions_are_left_out():
    assert emotion.crema_label("ANG") == "anger" and emotion.crema_label("HAP") == "happiness"
    assert emotion.crema_label("NEU") == "neutral" and emotion.crema_label("SAD") == "sadness"
    assert emotion.crema_label("DIS") is None and emotion.crema_label("FEA") is None


# ---- the classical acoustic baseline ----------------------------------------------------------------------------
SR = 16000


def sine(freq, seconds=1.0, amplitude=8000):
    t = np.arange(int(seconds * SR)) / SR
    return np.round(amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def test_s2_pitch_of_a_steady_tone_is_its_frequency():
    for f0 in (120.0, 200.0, 310.0):
        f = emotion.acoustic_features(sine(f0))
        assert f["f0_mean_hz"] == pytest.approx(f0, rel=0.01) and f["f0_std_semitones"] < 0.2


def test_s2_pitch_variation_in_semitones_of_two_alternating_tones():
    x = np.concatenate([sine(200.0, 0.5), sine(400.0, 0.5)])                # an octave apart
    f = emotion.acoustic_features(x)
    assert f["f0_range_semitones"] == pytest.approx(12.0, abs=0.5)


def test_s2_rms_features_of_a_known_amplitude():
    f = emotion.acoustic_features(sine(200.0, amplitude=8000))
    assert f["rms_mean"] == pytest.approx(8000 / np.sqrt(2) / 32768, rel=0.02)
    assert f["rms_std"] < 0.01


def test_s2_speaking_rate_counts_energy_bursts_per_second():
    # four 150 ms tone bursts, 100 ms apart, in 1.5 s of audio: 4 syllable nuclei in 1.5 s
    x = np.zeros(int(1.5 * SR), dtype=np.int16)
    for k in range(4):
        start = int(k * 0.25 * SR)
        x[start:start + int(0.15 * SR)] = sine(220.0, 0.15)
    f = emotion.acoustic_features(x)
    assert f["syllable_rate_hz"] == pytest.approx(4 / 1.5, rel=0.1)


def test_s2_silence_has_no_pitch_and_zero_voiced_ratio():
    f = emotion.acoustic_features(np.zeros(SR, dtype=np.int16))
    assert f["voiced_ratio"] == 0.0 and f["f0_mean_hz"] == 0.0


def test_s2_logistic_regression_separates_four_clusters_and_is_deterministic():
    rng = np.random.default_rng(0)
    centres = np.array([[0, 0], [4, 0], [0, 4], [4, 4]], dtype=float)
    X = np.concatenate([c + rng.normal(0, 0.3, (40, 2)) for c in centres])
    y = np.repeat(np.arange(4), 40)
    a = emotion.LogisticRegression(l2=1e-3, iterations=300, seed=1).fit(X, y)
    b = emotion.LogisticRegression(l2=1e-3, iterations=300, seed=1).fit(X, y)
    pa = a.predict_proba(X)
    assert (pa.argmax(axis=1) == y).mean() == 1.0
    assert np.allclose(pa, b.predict_proba(X)) and np.allclose(pa.sum(axis=1), 1.0)
