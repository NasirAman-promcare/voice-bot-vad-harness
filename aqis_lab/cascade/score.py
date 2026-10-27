"""Sprint 3 cascade arithmetic: WER from error counts, escalation sets, operating curves, cost, latency and paired bootstrap.

CAPABILITIES:
  CAP-S3-010: wer() and mean_slice_wer() give the pooled WER (total errors over total reference words) and the mean over slices
    of each slice's pooled WER [tests: test_s3_wer_is_total_errors_over_total_words,
    test_s3_slice_mean_wer_averages_pooled_slice_wers_not_turns]
  CAP-S3-011: escalation_count() gives the largest whole number of turns a rate allows; escalation_mask() marks the turns with the
    highest gate scores up to that number (ties go to the lowest tiebreak value); chosen_errors() takes the heavy model's errors
    on escalated turns and stage 1's on the rest; oracle_scores() is the perfect gate (errors saved per turn);
    operating_curve() gives errors and WER at each rate; pareto() keeps the points that lower the WER [tests:
    test_s3_escalation_never_exceeds_the_rate, test_s3_a_rate_outside_zero_to_one_is_an_error,
    test_s3_the_gate_escalates_the_highest_scores_and_the_chosen_errors_follow,
    test_s3_ties_are_broken_by_the_tiebreak_not_by_input_order,
    test_s3_the_perfect_gate_picks_the_largest_error_reductions_first, test_s3_the_curve_reports_the_achieved_rate,
    test_s3_pareto_keeps_only_points_that_lower_the_wer]
  CAP-S3-012: gpu_cost() charges stage 1 for every turn and the heavy model for escalated ones, in GPU seconds from RTFx, and gives
    the saving against sending everything to the heavy model; added_latency_ms() is the mean post-turn delay [tests:
    test_s3_gpu_cost_charges_stage_1_for_every_turn_and_the_heavy_model_for_escalated_ones,
    test_s3_added_latency_is_the_heavy_latency_times_the_share_of_escalated_turns]
  CAP-S3-013: paired_cluster_diff() resamples speaker clusters for the WER difference of two systems and calls "A beats B", "B beats A"
    or "too close to call"; meets_gate(), non_regression() and recall_change() apply the brief's limits [tests:
    test_s3_paired_difference_with_a_constant_gap_collapses_to_the_gap,
    test_s3_paired_difference_that_changes_sign_across_clusters_is_too_close_to_call,
    test_s3_targets_are_met_only_when_both_limits_hold, test_s3_non_regression_allows_a_drop_of_at_most_the_limit,
    test_s3_recall_gain_counts_found_entities]
INPUTS AND OUTPUTS: arrays of per-turn error counts, reference word counts, scores and audio seconds in; numbers, arrays and dicts out;
  ScoreError.
CONTRACTS: brief sections 2 and 3; WER is the pooled WER of the 6,300 target turns used by Sprint 1's oracle (11.06% for the best pair).
INVARIANTS:
  - Rates are totals over totals, never means of per-turn rates.
  - A rate never escalates more turns than the rate allows.
  - The same seed and data give the same interval.
NOT IN SCOPE:
  - Reading Sprint 1 files and building gate scores (aqis_lab/cascade/simulate.py and gate.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import numpy as np

CHUNK = 100


class ScoreError(ValueError):
    """Scoring input is malformed."""


def wer(errors, words):
    total = float(np.sum(words))
    return float(np.sum(errors)) / total if total else None


def mean_slice_wer(errors, words, slices):
    errors, words, slices = np.asarray(errors), np.asarray(words), np.asarray(slices)
    values = [wer(errors[slices == s], words[slices == s]) for s in sorted(set(slices.tolist()))]
    if any(v is None for v in values):
        raise ScoreError("a slice has no reference words")
    return float(np.mean(values))


def escalation_count(n, rate):
    if not 0 <= rate <= 1:
        raise ScoreError(f"rate must be between 0 and 1, got {rate}")
    return int(np.floor(rate * n + 1e-9))


def escalation_mask(scores, rate, tiebreak=None):
    scores = np.asarray(scores, dtype=float)
    k = escalation_count(len(scores), rate)
    tie = np.arange(len(scores)) if tiebreak is None else np.asarray(tiebreak)
    order = np.lexsort((tie, -scores))
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:k]] = True
    return mask


def chosen_errors(e_stage1, e_heavy, mask):
    return np.where(mask, np.asarray(e_heavy), np.asarray(e_stage1))


def oracle_scores(e_stage1, e_heavy):
    return np.asarray(e_stage1) - np.asarray(e_heavy)


def operating_curve(scores, e_stage1, e_heavy, words, rates, tiebreak=None):
    n = len(scores)
    out = []
    for rate in rates:
        mask = escalation_mask(scores, rate, tiebreak)
        errors = int(chosen_errors(e_stage1, e_heavy, mask).sum())
        out.append({"rate": rate, "escalated": int(mask.sum()), "escalation_rate": mask.sum() / n if n else 0.0,
                    "errors": errors, "wer": wer(chosen_errors(e_stage1, e_heavy, mask), words)})
    return out


def pareto(points):
    kept, best = [], None
    for rate, value in sorted(points):
        if best is None or value < best:
            kept.append((rate, value))
            best = value
    return kept


def gpu_cost(audio_s, mask, rtfx_stage1, rtfx_heavy):
    audio_s = np.asarray(audio_s, dtype=float)
    cascade = audio_s.sum() / rtfx_stage1 + audio_s[np.asarray(mask)].sum() / rtfx_heavy
    everything = audio_s.sum() / rtfx_heavy
    return {"cascade_s": float(cascade), "all_heavy_s": float(everything), "savings": float(1 - cascade / everything)}


def added_latency_ms(mask, heavy_latency_ms):
    mask = np.asarray(mask)
    return float(mask.mean() * heavy_latency_ms) if len(mask) else 0.0


def paired_cluster_diff(errors_a, errors_b, words, clusters, resamples, seed, ci=0.95):
    """WER of system a minus WER of system b, with a percentile interval from resampling speaker clusters."""
    names = sorted(set(clusters))
    index = {c: i for i, c in enumerate(names)}
    cluster_ids = np.array([index[c] for c in clusters])
    sums = np.zeros((3, len(names)))
    for row, values in enumerate((errors_a, errors_b, words)):
        np.add.at(sums[row], cluster_ids, np.asarray(values, dtype=float))
    total_words = sums[2].sum()
    if not total_words:
        raise ScoreError("no reference words")
    point = (sums[0].sum() - sums[1].sum()) / total_words
    rng = np.random.default_rng(seed)
    diffs = []
    for start in range(0, resamples, CHUNK):
        idx = rng.integers(0, len(names), size=(min(CHUNK, resamples - start), len(names)))
        w = sums[2][idx].sum(axis=1)
        ok = w > 0
        diffs.append((sums[0][idx].sum(axis=1)[ok] - sums[1][idx].sum(axis=1)[ok]) / w[ok])
    lo, hi = np.percentile(np.concatenate(diffs), [100 * (1 - ci) / 2, 100 * (1 + ci) / 2])
    verdict = "A beats B" if hi < 0 else "B beats A" if lo > 0 else "too close to call"
    return {"diff": float(point), "ci": (float(lo), float(hi)), "verdict": verdict}


def meets_gate(wer_value, rate, wer_max, rate_max):
    return wer_value is not None and wer_value <= wer_max and rate <= rate_max


def non_regression(pre, post, max_increase):
    delta = post - pre
    return {"pre": pre, "post": post, "delta": delta, "ok": delta <= max_increase + 1e-12}


def recall_change(found_pre, found_post, total):
    if not total:
        raise ScoreError("no entities to recall")
    pre, post = found_pre / total, found_post / total
    return {"pre": pre, "post": post, "gain": post - pre}
