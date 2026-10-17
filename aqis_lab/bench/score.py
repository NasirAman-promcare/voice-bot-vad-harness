"""Sprint 1 scoring: WER and CER, number accuracy, medical entities, bootstrap, oracle, hallucination, speed.

CAPABILITIES:
  CAP-S1-006: score_rows() scores (utt_id, ref, hyp, cluster) rows with the aqis_lab.scoring MAIN normaliser and
    alignment; corpus() gives corpus WER and CER as total errors over total reference words or characters (None when
    the reference total is 0) [tests: test_s1_bench_scoring_uses_the_main_normaliser,
    test_s1_corpus_wer_is_total_errors_over_total_reference_words, test_s1_corpus_cer_counts_characters_including_spaces,
    test_s1_corpus_wer_is_undefined_without_reference_words, test_s1_score_rows_rejects_a_row_missing_a_field]
  CAP-S1-007: number_accuracy() is the share of reference tokens with digits that the alignment marks as hits;
    entity_found() and entity_recall() count a medical entity as found when its normalised words appear contiguous and in
    order in the normalised hypothesis, per category; parse_entities() reads the Eka entity string [tests:
    test_s1_number_accuracy_counts_reference_digit_tokens_marked_as_hits, test_s1_entity_found_needs_contiguous_ordered_normalised_words,
    test_s1_entity_recall_per_category_and_overall, test_s1_parse_entities_reads_the_eka_json_string]
  CAP-S1-008: bootstrap_ci() resamples speaker clusters (or utterances) with a fixed seed for a percentile interval of
    the corpus WER; paired_bootstrap() resamples the same clusters for two systems' WER difference and calls "A beats B",
    "B beats A" or "too close to call" [tests: test_s1_bootstrap_same_seed_same_interval_other_seed_other_interval,
    test_s1_bootstrap_with_two_speakers_gives_exactly_their_two_wers, test_s1_bootstrap_resamples_speakers_not_utterances,
    test_s1_bootstrap_of_identical_speakers_collapses_to_a_point, test_s1_paired_bootstrap_calls_a_clear_difference_and_a_tie]
  CAP-S1-018: mean_of_wers_ci() and paired_mean_of_wers() do the same for the target WER, the mean over slices of each
    slice's corpus WER, resampling the speaker clusters of every slice with one fixed seed (the paired form resamples
    the same clusters for both systems) [tests: test_s1_mean_of_wers_point_and_interval_by_hand,
    test_s1_paired_mean_of_wers_calls_a_constant_difference]
  CAP-S1-009: oracle() gives the best single model, the per-utterance oracle of all models and the best pair; hallucination()
    gives the share of clips with output words after normalisation and the mean words per clip; rtfx() and latency_stats()
    give speed [tests: test_s1_oracle_hand_example_with_three_models, test_s1_hallucination_counts_only_clips_with_words_after_normalisation,
    test_s1_rtfx_is_total_audio_over_total_wall_time, test_s1_latency_percentiles_use_linear_interpolation]
INPUTS AND OUTPUTS: row dicts and number lists in; dicts and tuples out; ScoreError on bad input.
CONTRACTS: brief section 5; the alignment and normaliser of aqis_lab.scoring (WP-0.3).
INVARIANTS:
  - Corpus rates are totals over totals, never means of per-utterance rates.
  - A bootstrap with the same seed and data gives the same interval.
NOT IN SCOPE:
  - Reading prediction files and writing tables (aqis_lab/bench/report.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import json
from dataclasses import dataclass

import numpy as np

from aqis_lab.scoring.normalise import MAIN
from aqis_lab.scoring.wer import HIT, score_utterance

NORMALISER = MAIN
CLUSTER_UNITS = ("cluster", "speaker")
CHUNK = 100                                   # resamples drawn per block, to bound memory


class ScoreError(ValueError):
    """Scoring input is malformed."""


@dataclass(frozen=True)
class Scored:
    utt_id: str
    cluster: str
    utt: object                               # aqis_lab.scoring.wer.UtteranceScore

    @property
    def errors(self):
        return self.utt.words.errors

    @property
    def ref_words(self):
        return self.utt.words.ref_len


def score_rows(rows):
    out = []
    for row in rows:
        missing = [k for k in ("utt_id", "ref", "hyp", "cluster") if k not in row]
        if missing:
            raise ScoreError(f"row {row.get('utt_id', '?')} lacks {', '.join(missing)}")
        out.append(Scored(row["utt_id"], row["cluster"], score_utterance(row["utt_id"], row["ref"], row["hyp"], NORMALISER)))
    return out


def corpus(recs):
    """Totals and corpus WER and CER of scored records."""
    recs = list(recs)
    errors = sum(r.errors for r in recs)
    ref_words = sum(r.ref_words for r in recs)
    char_errors = sum(r.utt.chars.errors for r in recs)
    ref_chars = sum(r.utt.chars.ref_len for r in recs)
    return {"utterances": len(recs), "errors": errors, "ref_words": ref_words, "char_errors": char_errors,
            "ref_chars": ref_chars, "wer": errors / ref_words if ref_words else None,
            "cer": char_errors / ref_chars if ref_chars else None}


# ---- numbers and entities ------------------------------------------------------------------------------------
def number_accuracy(recs):
    hits = total = 0
    for rec in recs:
        tokens = rec.utt.ref_normalised.split(" ") if rec.utt.ref_normalised else []
        hit_indexes = {op.ref_index for op in rec.utt.words.ops if op.kind == HIT}
        for i, token in enumerate(tokens):
            if any(ch.isdigit() for ch in token):
                total += 1
                hits += i in hit_indexes
    return {"hits": hits, "total": total, "rate": hits / total if total else None}


def parse_entities(value):
    """[(category, text)] from Eka's medical_entities string: a JSON list of [text, category, [[start, end], ...]]."""
    if value is None or value == "":
        return []
    try:
        data = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise ScoreError(f"medical_entities is not JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ScoreError(f"medical_entities must be a list, got {type(data).__name__}")
    out = []
    for entry in data:
        if not (isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[0], str)
                and isinstance(entry[1], str)):
            raise ScoreError(f"medical entity {entry!r} is not [text, category, ...]")
        out.append((entry[1], entry[0]))
    return out


def entity_found(entity, hyp):
    words = NORMALISER(entity).split()
    if not words:
        raise ScoreError(f"entity {entity!r} has no words after normalisation")
    heard = NORMALISER(hyp).split()
    return any(heard[i:i + len(words)] == words for i in range(len(heard) - len(words) + 1))


def entity_recall(items):
    """{category: {found, total, recall}, 'all': ...} for (category, entity, hypothesis) items."""
    tally = {}
    for category, entity, hyp in items:
        for key in (category, "all"):
            found, total = tally.get(key, (0, 0))
            tally[key] = (found + entity_found(entity, hyp), total + 1)
    return {k: {"found": f, "total": t, "recall": f / t} for k, (f, t) in tally.items()}


# ---- bootstrap -----------------------------------------------------------------------------------------------
def _groups(recs, unit):
    if unit not in CLUSTER_UNITS + ("utterance",):
        raise ScoreError(f"bootstrap unit must be 'speaker' (cluster) or 'utterance', got {unit!r}")
    keyed = {}
    for rec in recs:
        key = rec.utt_id if unit == "utterance" else rec.cluster
        errs, refs = keyed.get(key, (0, 0))
        keyed[key] = (errs + rec.errors, refs + rec.ref_words)
    names = sorted(keyed)
    return names, np.array([keyed[k][0] for k in names], dtype=np.int64), np.array([keyed[k][1] for k in names], dtype=np.int64)


def _percentiles(values, ci):
    lo, hi = np.percentile(values, [100 * (1 - ci) / 2, 100 * (1 + ci) / 2])
    return float(lo), float(hi)


def bootstrap_ci(recs, resamples, seed, ci=0.95, unit="cluster"):
    _, errs, refs = _groups(list(recs), unit)
    if len(errs) == 0:
        raise ScoreError("nothing to bootstrap")
    rng = np.random.default_rng(seed)
    rates = []
    for start in range(0, resamples, CHUNK):
        idx = rng.integers(0, len(errs), size=(min(CHUNK, resamples - start), len(errs)))
        e, w = errs[idx].sum(axis=1), refs[idx].sum(axis=1)
        rates.append(e[w > 0] / w[w > 0])
    return _percentiles(np.concatenate(rates), ci)


def paired_bootstrap(a_recs, b_recs, resamples, seed, ci=0.95, unit="cluster"):
    a_recs, b_recs = list(a_recs), list(b_recs)
    if {r.utt_id for r in a_recs} != {r.utt_id for r in b_recs} or len(a_recs) != len(b_recs):
        raise ScoreError("paired bootstrap needs both systems scored on the same utterances")
    b_by_id = {r.utt_id: r for r in b_recs}
    a_names, a_err, a_ref = _groups(a_recs, unit)
    b_names, b_err, b_ref = _groups([b_by_id[r.utt_id] for r in a_recs], unit)
    if a_names != b_names:
        raise ScoreError("the two systems disagree on the clusters of the same utterances")
    rng = np.random.default_rng(seed)
    diffs = []
    for start in range(0, resamples, CHUNK):
        idx = rng.integers(0, len(a_err), size=(min(CHUNK, resamples - start), len(a_err)))
        wa, wb = a_ref[idx].sum(axis=1), b_ref[idx].sum(axis=1)
        keep = (wa > 0) & (wb > 0)
        diffs.append(a_err[idx].sum(axis=1)[keep] / wa[keep] - b_err[idx].sum(axis=1)[keep] / wb[keep])
    lo, hi = _percentiles(np.concatenate(diffs), ci)
    point = a_err.sum() / a_ref.sum() - b_err.sum() / b_ref.sum()
    verdict = "A beats B" if hi < 0 else "B beats A" if lo > 0 else "too close to call"
    return {"diff": float(point), "ci": (lo, hi), "verdict": verdict}


def mean_of_wers(groups):
    """Mean over groups (slices) of each group's corpus WER; groups map a name to scored records."""
    wers = []
    for name in sorted(groups):
        total = corpus(groups[name])
        if total["wer"] is None:
            raise ScoreError(f"group {name} has no reference words")
        wers.append(total["wer"])
    return float(np.mean(wers))


def _group_samples(systems, resamples, seed):
    """Mean-over-groups WER for each resample and each system; all systems share the draws of each group."""
    arrays = [{g: _groups(recs, "cluster") for g, recs in sorted(groups.items())} for groups in systems]
    for other in arrays[1:]:
        if sorted(other) != sorted(arrays[0]) or any(other[g][0] != arrays[0][g][0] for g in arrays[0]):
            raise ScoreError("the systems differ in their groups or clusters; score the same utterances")
    rng = np.random.default_rng(seed)
    out = [[] for _ in arrays]
    for start in range(0, resamples, CHUNK):
        size = min(CHUNK, resamples - start)
        sums = [np.zeros(size) for _ in arrays]
        for g in sorted(arrays[0]):
            n = len(arrays[0][g][1])
            idx = rng.integers(0, n, size=(size, n))
            for k, system in enumerate(arrays):
                e, w = system[g][1][idx].sum(axis=1), system[g][2][idx].sum(axis=1)
                sums[k] += e / np.maximum(w, 1)
        for k in range(len(arrays)):
            out[k].append(sums[k] / len(arrays[0]))
    return [np.concatenate(chunks) for chunks in out]


def mean_of_wers_ci(groups, resamples, seed, ci=0.95):
    (samples,) = _group_samples([groups], resamples, seed)
    return _percentiles(samples, ci)


def paired_mean_of_wers(groups_a, groups_b, resamples, seed, ci=0.95):
    a, b = _group_samples([groups_a, groups_b], resamples, seed)
    lo, hi = _percentiles(a - b, ci)
    verdict = "A beats B" if hi < 0 else "B beats A" if lo > 0 else "too close to call"
    return {"diff": mean_of_wers(groups_a) - mean_of_wers(groups_b), "ci": (lo, hi), "verdict": verdict}


# ---- oracle, hallucination, speed ----------------------------------------------------------------------------
def oracle(errors, ref_words):
    """Best single model, per-utterance oracle of all models, and best pair, from per-utterance error counts."""
    names = sorted(errors)
    if len(names) < 2:
        raise ScoreError("an oracle needs at least two models")
    n = len(ref_words)
    if any(len(errors[m]) != n for m in names):
        raise ScoreError("every model needs one error count per utterance")
    total = sum(ref_words)
    arr = {m: np.asarray(errors[m], dtype=np.int64) for m in names}

    def entry(models, errs):
        return {"models": tuple(models), "errors": int(errs), "wer": errs / total}

    single = min(names, key=lambda m: arr[m].sum())
    best_pair = None
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            errs = int(np.minimum(arr[a], arr[b]).sum())
            if best_pair is None or errs < best_pair[1]:
                best_pair = ((a, b), errs)
    everything = np.min(np.stack([arr[m] for m in names]), axis=0).sum()
    return {"best_single": entry((single,), int(arr[single].sum())), "oracle": entry(names, everything),
            "best_pair": entry(*best_pair)}


def hallucination(hyps):
    hyps = list(hyps)
    if not hyps:
        raise ScoreError("no non-speech clips to count")
    counts = [len(NORMALISER(h).split()) for h in hyps]
    with_words = sum(1 for c in counts if c)
    return {"clips": len(hyps), "with_words": with_words, "rate": with_words / len(hyps),
            "mean_words": sum(counts) / len(hyps)}


def rtfx(batches):
    """Audio seconds per wall second over (audio_s, wall_s) batches."""
    batches = list(batches)
    wall = sum(w for _, w in batches)
    if not batches or wall <= 0:
        raise ScoreError("no timed batches")
    return sum(a for a, _ in batches) / wall


def latency_stats(values):
    values = list(values)
    if not values:
        raise ScoreError("no latencies")
    return {"p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95))}
