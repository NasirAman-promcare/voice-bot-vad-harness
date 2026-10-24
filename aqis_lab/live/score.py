"""Sprint 2 scoring: VAD alignment, false alarms and misses, DET points, turn outcomes, emotion metrics, cluster bootstrap.

CAPABILITIES:
  CAP-S2-010: segment_timings() gives, for each reference speech segment, the onset lag (end of the first flagged frame that
    holds or follows the onset, minus the onset) and the offset lag (end of the last flagged frame of the run that holds the
    last speech sample, minus the true end; negative when the end was clipped); None when the VAD never flags the segment
    [tests: test_s2_onset_and_offset_lag_are_exact, test_s2_two_bursts_are_timed_independently,
    test_s2_a_clipped_end_gives_a_negative_offset_lag, test_s2_a_segment_the_vad_never_flags_is_missed,
    test_s2_a_flag_that_began_before_the_onset_is_counted_from_the_frame_that_holds_the_onset]
  CAP-S2-011: vad_counts() and vad_rates() count missed speech and false-alarm samples over the scored region, optionally leaving
    out a collar around every reference boundary, and give MDR and FAR as totals over totals; det_counts() does the same for a
    list of score thresholds [tests: test_s2_far_and_mdr_by_hand, test_s2_a_collar_leaves_out_the_samples_around_each_boundary,
    test_s2_rates_are_undefined_without_samples_of_that_kind, test_s2_reference_beyond_the_scored_frames_is_not_counted,
    test_s2_segments_to_mask_uses_exact_sample_boundaries, test_s2_det_points_by_hand, test_s2_det_needs_scores]
  CAP-S2-012: turn_outcome() scores one turn's triggers against its reference pauses and end (a pause with a trigger in it is
    one false interruption; a trigger in speech is spurious; the endpoint latency is the first trigger after the true end);
    turn_summary() gives the false interruption rate as total over total with a speaker-cluster bootstrap interval, the latency
    percentiles and the missed-endpoint rate [tests: test_s2_false_interruption_rate_of_a_multi_pause_turn_matches_the_definition,
    test_s2_outcome_counts_pauses_with_a_trigger_once_and_separates_spurious_triggers,
    test_s2_outcome_without_a_trigger_after_the_end_is_a_missed_endpoint, test_s2_outcome_uses_the_first_trigger_after_the_true_end,
    test_s2_turn_summary_by_hand]
  CAP-S2-013: confusion_matrix(), class_recalls(), uar(), accuracy(), frustration_recall(), phone_cost() and uar_ci() give the
    4-class emotion metrics, the interval resampling actors [tests: test_s2_confusion_matrix_by_hand,
    test_s2_uar_is_the_mean_of_class_recalls_not_accuracy, test_s2_uar_and_accuracy_differ_when_classes_are_unbalanced,
    test_s2_frustration_recall_is_the_anger_recall, test_s2_a_class_without_samples_has_undefined_recall_and_uar,
    test_s2_phone_cost_is_uar_phone_over_uar_clean, test_s2_uar_ci_resamples_actors]
  CAP-S2-015: vad_summary() and stream_summary() pool per-clip results into the sprint's totals: FAR and MDR as totals over totals
    with speaker-cluster intervals, onset and offset lag percentiles over reference segments, the share of segments never flagged;
    the real-time factor as total compute over total audio and the step-time percentiles [tests:
    test_s2_vad_summary_by_hand, test_s2_stream_summary_by_hand]
  CAP-S2-014: cluster_ratio_ci() is a seeded percentile interval of a ratio of sums, resampling clusters (speakers); percentiles()
    gives p50 and p95 by linear interpolation [tests: test_s2_cluster_ratio_ci_with_two_clusters_is_their_two_ratios,
    test_s2_cluster_ratio_ci_is_seeded_and_collapses_for_identical_clusters, test_s2_percentiles_use_linear_interpolation]
INPUTS AND OUTPUTS: reference segments in ms, vad.Decisions, trigger times, label lists in; dicts, tuples and dataclasses out;
  ScoreError.
CONTRACTS: brief section 4; definitions in this header are the ones the tests work out by hand.
INVARIANTS:
  - Rates are totals over totals, never means of per-clip rates.
  - Reference and VAD are compared over the same samples: the whole frames the VAD scored.
  - The same seed and data give the same interval.
NOT IN SCOPE:
  - Running models (the stage modules) and writing tables (aqis_lab/live/report.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
from dataclasses import dataclass

import numpy as np

from aqis_lab.live import emotion

CHUNK = 100


class ScoreError(ValueError):
    """Scoring input is malformed."""


def percentiles(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"p50": None, "p95": None}
    return {"p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95))}


# ---- VAD -------------------------------------------------------------------------------------------------------
def _samples(ms, rate):
    return int(round(ms * rate / 1000.0))


def segments_to_mask(segments_ms, n_samples, rate=16000):
    mask = np.zeros(n_samples, dtype=bool)
    for start, end in segments_ms:
        a, b = _samples(start, rate), _samples(end, rate)
        mask[max(a, 0):min(b, n_samples)] = True
    return mask


def _collar_mask(segments_ms, n_samples, collar_ms, rate):
    mask = np.zeros(n_samples, dtype=bool)
    c = _samples(collar_ms, rate)
    if c <= 0:
        return mask
    for start, end in segments_ms:
        for edge in (_samples(start, rate), _samples(end, rate)):
            mask[max(edge - c, 0):max(min(edge + c, n_samples), 0)] = True
    return mask


def _counts(ref_mask, dec_mask, excluded):
    keep = ~excluded
    speech = ref_mask & keep
    quiet = ~ref_mask & keep
    return {"speech_samples": int(speech.sum()), "nonspeech_samples": int(quiet.sum()),
            "missed": int((speech & ~dec_mask).sum()), "false_alarm": int((quiet & dec_mask).sum())}


def vad_counts(ref_segments_ms, decisions, collar_ms=0, rate=16000):
    n = decisions.n_scored_samples
    dec = np.repeat(decisions.speech, decisions.frame_samples)
    return _counts(segments_to_mask(ref_segments_ms, n, rate), dec, _collar_mask(ref_segments_ms, n, collar_ms, rate))


def vad_rates(counts):
    return {"far": counts["false_alarm"] / counts["nonspeech_samples"] if counts["nonspeech_samples"] else None,
            "mdr": counts["missed"] / counts["speech_samples"] if counts["speech_samples"] else None}


def det_counts(ref_segments_ms, decisions, thresholds, collar_ms=0, rate=16000):
    if np.isnan(decisions.score).any():
        raise ScoreError("this VAD gives no scores, so it has no DET points")
    n = decisions.n_scored_samples
    ref, excluded = segments_to_mask(ref_segments_ms, n, rate), _collar_mask(ref_segments_ms, n, collar_ms, rate)
    out = []
    for thr in thresholds:
        dec = np.repeat(decisions.score >= thr, decisions.frame_samples)
        out.append({"threshold": thr, **_counts(ref, dec, excluded)})
    return out


@dataclass(frozen=True)
class SegmentTiming:
    onset_lag_ms: float | None
    offset_lag_ms: float | None


def segment_timings(ref_segments_ms, decisions, rate=16000):
    h, flags = decisions.frame_samples, decisions.speech
    n = len(flags)
    out = []
    for start, end in ref_segments_ms:
        s, e = _samples(start, rate), _samples(end, rate)
        first, last = s // h, (e - 1) // h
        if e <= s or first >= n:
            out.append(SegmentTiming(None, None))
            continue
        hit = next((k for k in range(first, min(last, n - 1) + 1) if flags[k]), None)
        if hit is None:
            out.append(SegmentTiming(None, None))
            continue
        onset = ((hit + 1) * h - s) * 1000.0 / rate
        if last > n - 1:                                   # the end lies beyond the scored frames: not observable
            out.append(SegmentTiming(onset, None))
            continue
        if flags[last]:
            r = last
            while r + 1 < n and flags[r + 1]:
                r += 1
        else:
            r = next(k for k in range(last - 1, hit - 1, -1) if flags[k])
        out.append(SegmentTiming(onset, ((r + 1) * h - e) * 1000.0 / rate))
    return out


# ---- bootstrap ---------------------------------------------------------------------------------------------------
def cluster_ratio_ci(num, den, resamples, seed, ci=0.95):
    names = sorted(num)
    n = np.array([num[k] for k in names], dtype=float)
    d = np.array([den[k] for k in names], dtype=float)
    if len(names) == 0:
        raise ScoreError("nothing to bootstrap")
    rng = np.random.default_rng(seed)
    ratios = []
    for start in range(0, resamples, CHUNK):
        idx = rng.integers(0, len(names), size=(min(CHUNK, resamples - start), len(names)))
        top, bottom = n[idx].sum(axis=1), d[idx].sum(axis=1)
        ratios.append(top[bottom > 0] / bottom[bottom > 0])
    lo, hi = np.percentile(np.concatenate(ratios), [100 * (1 - ci) / 2, 100 * (1 + ci) / 2])
    return float(lo), float(hi)


def vad_summary(clips, resamples, seed, ci=0.95):
    """Pooled VAD results. Each clip: cluster, counts (vad_counts), onset_lags_ms and offset_lags_ms (None when never flagged)."""
    totals = {k: sum(c["counts"][k] for c in clips) for k in ("speech_samples", "nonspeech_samples", "missed", "false_alarm")}
    rates = vad_rates(totals)
    by_cluster = {}
    for c in clips:
        agg = by_cluster.setdefault(c["cluster"], dict.fromkeys(totals, 0))
        for k in totals:
            agg[k] += c["counts"][k]

    def interval(num, den):
        if not totals[den]:
            return (None, None)
        return cluster_ratio_ci({k: v[num] for k, v in by_cluster.items()}, {k: v[den] for k, v in by_cluster.items()},
                                resamples, seed, ci)
    onsets = [x for c in clips for x in c["onset_lags_ms"]]
    offsets = [x for c in clips for x in c["offset_lags_ms"] if x is not None]
    seen = [x for x in onsets if x is not None]
    on, off = percentiles(seen), percentiles(offsets)
    return {"clips": len(clips), "far": rates["far"], "far_ci": interval("false_alarm", "nonspeech_samples"),
            "mdr": rates["mdr"], "mdr_ci": interval("missed", "speech_samples"),
            "segments": len(onsets), "missed_segments": len(onsets) - len(seen),
            "segment_miss_rate": (len(onsets) - len(seen)) / len(onsets) if onsets else None,
            "onset_p50_ms": on["p50"], "onset_p95_ms": on["p95"], "offset_p50_ms": off["p50"], "offset_p95_ms": off["p95"]}


def stream_summary(clips, resamples, seed, ci=0.95):
    """Pooled streaming results. Each clip: cluster, audio_s, compute_s, step_compute_ms (list)."""
    audio = sum(c["audio_s"] for c in clips)
    compute = sum(c["compute_s"] for c in clips)
    by_audio, by_compute = {}, {}
    for c in clips:
        by_audio[c["cluster"]] = by_audio.get(c["cluster"], 0.0) + c["audio_s"]
        by_compute[c["cluster"]] = by_compute.get(c["cluster"], 0.0) + c["compute_s"]
    steps = percentiles([x for c in clips for x in c["step_compute_ms"]])
    return {"clips": len(clips), "audio_s": audio, "rtf": compute / audio if audio else None,
            "rtf_ci": cluster_ratio_ci(by_compute, by_audio, resamples, seed, ci) if audio else (None, None),
            "chunk_p50_ms": steps["p50"], "chunk_p95_ms": steps["p95"]}


# ---- turn end ----------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TurnOutcome:
    cluster: str
    pauses: int
    false_interruptions: int
    spurious: int
    latency_ms: float | None
    missed_end: bool


def turn_outcome(triggers_ms, pauses_ms, end_ms, cluster=""):
    hit, spurious, end_trigger = set(), 0, None
    for t in sorted(triggers_ms):
        if t > end_ms:
            if end_trigger is None:
                end_trigger = t
            continue
        inside = [i for i, (a, b) in enumerate(pauses_ms) if a < t <= b]
        if inside:
            hit.add(inside[0])
        else:
            spurious += 1
    return TurnOutcome(cluster=cluster, pauses=len(pauses_ms), false_interruptions=len(hit), spurious=spurious,
                       latency_ms=None if end_trigger is None else end_trigger - end_ms, missed_end=end_trigger is None)


def turn_summary(outcomes, resamples, seed, ci=0.95):
    outcomes = list(outcomes)
    pauses = sum(o.pauses for o in outcomes)
    fi = sum(o.false_interruptions for o in outcomes)
    latencies = [o.latency_ms for o in outcomes if o.latency_ms is not None]
    by_cluster_fi, by_cluster_pauses = {}, {}
    for o in outcomes:
        by_cluster_fi[o.cluster] = by_cluster_fi.get(o.cluster, 0) + o.false_interruptions
        by_cluster_pauses[o.cluster] = by_cluster_pauses.get(o.cluster, 0) + o.pauses
    p = percentiles(latencies)
    return {"turns": len(outcomes), "pauses": pauses, "false_interruptions": fi,
            "fir": fi / pauses if pauses else None,
            "fir_ci": cluster_ratio_ci(by_cluster_fi, by_cluster_pauses, resamples, seed, ci) if pauses else (None, None),
            "spurious_per_turn": sum(o.spurious for o in outcomes) / len(outcomes) if outcomes else None,
            "latency_p50_ms": p["p50"], "latency_p95_ms": p["p95"],
            "missed_end_rate": sum(o.missed_end for o in outcomes) / len(outcomes) if outcomes else None}


# ---- emotion ----------------------------------------------------------------------------------------------------
def confusion_matrix(y_true, y_pred, n=len(emotion.CLASSES)):
    m = np.zeros((n, n), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[int(t), int(p)] += 1
    return m


def class_recalls(m):
    totals = m.sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(totals > 0, np.diag(m) / np.where(totals > 0, totals, 1), np.nan)


def uar(m):
    r = class_recalls(m)
    return None if np.isnan(r).any() else float(r.mean())


def accuracy(m):
    return float(np.diag(m).sum() / m.sum()) if m.sum() else None


def frustration_recall(m):
    value = class_recalls(m)[emotion.CLASSES.index("anger")]
    return None if np.isnan(value) else float(value)


def phone_cost(uar_phone, uar_clean):
    if uar_phone is None or not uar_clean:
        return None
    return uar_phone / uar_clean


def uar_ci(y_true, y_pred, clusters, resamples, seed, ci=0.95):
    names = sorted(set(clusters))
    per = {c: np.zeros((len(emotion.CLASSES),) * 2, dtype=int) for c in names}
    for t, p, c in zip(y_true, y_pred, clusters):
        per[c][int(t), int(p)] += 1
    stack = np.stack([per[c] for c in names])
    rng = np.random.default_rng(seed)
    values = []
    for start in range(0, resamples, CHUNK):
        idx = rng.integers(0, len(names), size=(min(CHUNK, resamples - start), len(names)))
        for row in idx:
            value = uar(stack[row].sum(axis=0))
            if value is not None:
                values.append(value)
    if not values:
        raise ScoreError("no resample had every class")
    lo, hi = np.percentile(values, [100 * (1 - ci) / 2, 100 * (1 + ci) / 2])
    return float(lo), float(hi)
