"""Sprint 3 workstream A: simulate cascade gates over the Sprint 1 prediction files of the target set.

CAPABILITIES:
  CAP-S3-040: load_target_set() reads the Sprint 1 data and prediction files (through aqis_lab.bench.report.Loaded) and returns, for
    every target-condition turn that stage 1 and every heavy model answered, the word errors of each model (aqis_lab.bench.score
    alignment and normaliser), reference words, audio seconds, speaker cluster, channel and stage 1's hypothesis; turns a heavy
    model never answered are counted and left out [tests: test_s3_target_set_scores_every_turn_both_models_answered,
    test_s3_a_turn_one_model_never_answered_is_left_out_and_counted, test_s3_missing_predictions_of_a_model_stop_the_run]
  CAP-S3-041: run() builds the gate scores of every policy whose features exist (random, duration, words per second, digits, channel,
    non-speech ratio, confidence, entropy, and a hybrid trained out of fold by speaker), plus the perfect gate, and writes
    report/cascade.csv (WER, share escalated, GPU saving and added latency at each rate), headline.csv (the operating point within
    the escalation limit, with paired intervals against stage 1 and the heavy model), thresholds.json and policies.json (which
    policies ran, and why one could not) [tests: test_s3_the_perfect_gate_curve_matches_the_hand_worked_figures,
    test_s3_every_policy_starts_at_stage_1_and_ends_at_the_heavy_model_and_stays_within_its_rate,
    test_s3_a_policy_that_needs_a_missing_feature_is_reported_as_unavailable_and_not_guessed,
    test_s3_a_confidence_feature_file_makes_the_confidence_policy_available,
    test_s3_cost_and_latency_columns_use_the_config_figures, test_s3_the_gate_threshold_file_names_the_score_that_gives_the_rate]
  CAP-S3-042: compute_nonspeech() runs Silero v5 over the target turns' audio on the CPU and saves each turn's share of non-speech
    frames; merge_features() keeps the other feature columns [tests: test_s3_merging_features_keeps_other_columns]
  CAP-S3-043: impute_no_word_turns() scores a turn for which stage 1 produced no words as least confident (confidence and entropy 0.0), so
    that such turns do not disable the confidence, entropy and hybrid policies; a turn with words and no score is left alone and keeps the
    policy unavailable; nothing imputed is written to the feature file, and policies.json counts the turns [tests:
    test_s3_only_turns_with_no_stage_1_words_are_scored_as_least_confident,
    test_s3_a_silent_turn_no_longer_disables_the_confidence_policies, test_s3_the_silent_turn_is_escalated_first_and_the_numbers_follow,
    test_s3_nothing_imputed_is_written_to_the_feature_file,
    test_s3_a_turn_with_words_and_no_confidence_still_makes_the_policy_unavailable]
INPUTS AND OUTPUTS: s3 and s1 configs, the Sprint 1 output folder; CSV and JSON files under <out>/report; SimulateError.
CONTRACTS: brief section 2A; the target set is the one of docs/results/S1/oracle.csv (6,300 turns), pooled WER.
INVARIANTS:
  - The gate never sees the heavy model's output or the reference, except through training labels that are scored out of fold.
  - A policy with a feature missing for any turn is reported unavailable with the reason; it is not run on a guess.
  - Every figure is computed from the Sprint 1 files; nothing is estimated.
NOT IN SCOPE:
  - Running models (confidence.py, prompt_bias.py, train_lora.py) and plots (report.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from aqis_lab import drive
from aqis_lab.bench import report as s1_report
from aqis_lab.cascade import gate, score
from aqis_lab.cascade.features import FEATURE_FILE, OPTIONAL_FEATURES, merge_features, read_features  # noqa: F401  (tests use them here)

SIGNS = {"duration": ("duration_s", +1), "words_per_s": ("words_per_s", -1), "digits": ("digit_tokens", +1),
         "nonspeech": ("nonspeech_ratio", +1), "confidence": ("confidence", -1), "entropy": ("entropy", -1)}


class SimulateError(RuntimeError):
    """The cascade cannot be simulated from the files present."""


@dataclass
class TargetSet:
    keys: list
    slices: list
    conditions: list
    clusters: list
    words: np.ndarray
    audio_s: np.ndarray
    hyp: list
    channel: list
    errors: dict
    left_out: int = 0
    cells: dict = field(default_factory=dict)

    def audio_rows(self, s1_dir):
        """{(slice, condition): [{key, audio}]} read from the Sprint 1 data files, for the turns of this set."""
        import pyarrow.parquet as pq
        wanted = set(self.keys)
        out = {}
        for (slice_name, condition) in self.cells:
            path = Path(s1_dir) / "data" / slice_name / f"{condition}.parquet"
            rows = pq.read_table(path, columns=["utt_id", "audio"]).to_pylist()
            out[(slice_name, condition)] = [{"key": f"{slice_name}:{condition}:{r['utt_id']}", "audio": r["audio"]} for r in rows
                                            if f"{slice_name}:{condition}:{r['utt_id']}" in wanted]
        return out


def load_target_set(s1_cfg, s1_dir, stage1, heavy_models):
    loaded = s1_report.Loaded(s1_cfg, s1_dir)
    models = [stage1, *heavy_models]
    for name in models:
        if name not in loaded.models:
            raise SimulateError(f"no predictions of {name} under {Path(s1_dir) / 'preds'}; run it in Sprint 1 first")
    target = set(s1_cfg.target_conditions)
    keys, slices, conditions, clusters, words, audio, hyps, channels, left_out = [], [], [], [], [], [], [], [], 0
    errors = {m: [] for m in models}
    cells = {}
    for slice_name in s1_cfg.caller_slices:
        for condition in s1_cfg.conditions_for(slice_name):
            if condition not in target or (stage1, slice_name, condition) not in loaded.preds:
                continue
            scored = {m: {r.utt_id: r for r in loaded.scored(m, slice_name, condition)} if (m, slice_name, condition) in loaded.preds
                      else {} for m in models}
            hyp_of = {p["utt_id"]: p["hyp"] for p in loaded.preds[(stage1, slice_name, condition)]}
            refs = loaded.refs[(slice_name, condition)]
            for utt_id, rec in scored[stage1].items():
                if any(utt_id not in scored[m] for m in heavy_models):
                    left_out += 1
                    continue
                key = f"{slice_name}:{condition}:{utt_id}"
                keys.append(key)
                slices.append(slice_name)
                conditions.append(condition)
                clusters.append(rec.cluster)
                words.append(rec.ref_words)
                audio.append(float(refs[utt_id]["duration_s"]))
                hyps.append(hyp_of[utt_id])
                channels.append(gate.channel_of(condition))
                for m in models:
                    errors[m].append(scored[m][utt_id].errors)
                cells[(slice_name, condition)] = cells.get((slice_name, condition), 0) + 1
    if not keys:
        raise SimulateError(f"no turn of the target set is answered by {', '.join(models)} under {s1_dir}")
    return TargetSet(keys, slices, conditions, clusters, np.array(words), np.array(audio), hyps, channels,
                     {m: np.array(v) for m, v in errors.items()}, left_out, cells)


# ---- features ---------------------------------------------------------------------------------------------------
def compute_nonspeech(cfg, s2_cfg, s1_dir, out_dir, ts, log=print):
    """Share of 32 ms frames Silero v5 calls non-speech, for every turn of the target set (CPU)."""
    from aqis_lab.live import stages
    run = stages.Run(s2_cfg, out_dir, Path(__file__).resolve().parents[2], log)
    adapter, smoother, _ = stages.make_vad(run, cfg.cascade["nonspeech"]["vad"])
    found = {}
    for (slice_name, condition), rows in ts.audio_rows(s1_dir).items():
        for row in rows:
            decisions = stages.vad_decide(adapter, smoother, np.frombuffer(row["audio"], dtype=np.int16))
            found[row["key"]] = {"nonspeech_ratio": float(1.0 - decisions.speech.mean()) if len(decisions.speech) else None}
        log(f"nonspeech {slice_name}/{condition}: {len(rows)} turns")
    merge_features(Path(out_dir).joinpath(*FEATURE_FILE), found)
    return found


def feature_rows(ts, stored):
    rows = []
    for i, key in enumerate(ts.keys):
        base = gate.hyp_features(ts.hyp[i], float(ts.audio_s[i]))
        row = {"key": key, "duration_s": float(ts.audio_s[i]), "words": base["words"], "words_per_s": base["words_per_s"],
               "digit_tokens": base["digit_tokens"],
               "is_phone": float(ts.channel[i] == "phone"), "is_webrtc": float(ts.channel[i] == "webrtc"), "channel": ts.channel[i]}
        for name in OPTIONAL_FEATURES:
            row[name] = stored.get(key, {}).get(name)
        rows.append(row)
    return rows


def impute_no_word_turns(rows):
    """Score a turn for which stage 1 produced no words as least confident (0.0) where its confidence or entropy score is missing.

    Such a turn has no tokens to take a confidence of, and is the least trustworthy turn there is. The entropy feature is an
    entropy-based confidence (higher = more confident), so 0.0 is maximum entropy. A turn that has words but no score is not touched:
    that is a failure of the extraction and keeps the policy unavailable. Returns the number of turns changed; the feature file is
    never written with these values."""
    changed = 0
    for row in rows:
        if row.get("words", 1) != 0:
            continue
        filled = False
        for name in ("confidence", "entropy"):
            if row.get(name) is None:
                row[name] = 0.0
                filled = True
        if filled:
            row["imputed"] = True
            changed += 1
    return changed


def _missing(rows, name):
    return sum(1 for r in rows if r.get(name) is None)


# ---- policies ---------------------------------------------------------------------------------------------------
def _imputed_note(rows):
    n = sum(1 for r in rows if r.get("imputed"))
    return f"{n} turn{'s' if n != 1 else ''} with no stage 1 words scored as least confident" if n else ""


def policy_scores(cfg, ts, rows, heavy, status):
    """{policy: scores} for the policies that can run; fills `status` with the reason for the ones that cannot."""
    c = cfg.cascade
    e1, eh = ts.errors[c["stage1"]], ts.errors[heavy]
    out = {}
    for name in c["policies"]:
        if name == "random":
            out[name] = np.random.default_rng(cfg.seed).random(len(rows))
            status[name] = "ok"
        elif name == "channel":
            out[name] = gate.channel_scores(rows, c["channel_risk"])
            status[name] = "ok"
        elif name in SIGNS:
            feature, sign = SIGNS[name]
            gone = _missing(rows, feature)
            if gone:
                status[name] = (f"unavailable: {feature} is missing for {gone} of {len(rows)} turns; "
                                f"run `python -m aqis_lab.cascade confidence` or `cascade --nonspeech` to produce it")
                continue
            out[name] = gate.single_feature_scores(rows, feature, sign)
            note = _imputed_note(rows) if feature in ("confidence", "entropy") else ""
            status[name] = f"ok ({note})" if note else "ok"
        elif name == "hybrid":
            names = [f for f in c["hybrid_features"] if not _missing(rows, f)]
            if not names:
                status[name] = "unavailable: none of the hybrid features exists"
                continue
            try:
                X = gate.feature_matrix(rows, names)
                labels = gate.gain_labels(e1, eh, c["min_gain_errors"])
                out[name] = gate.out_of_fold_scores(X, labels, ts.clusters, c["folds"], cfg.seed,
                                                    lambda: gate.HybridGate(c["hybrid"]["l2"], c["hybrid"]["iterations"], cfg.seed))
            except gate.GateError as exc:
                status[name] = f"unavailable: {exc}"
                continue
            note = _imputed_note(rows) if any(f in ("confidence", "entropy") for f in names) else ""
            status[name] = f"ok ({', '.join(names)}{'; ' + note if note else ''})"
    out["oracle"] = score.oracle_scores(e1, eh).astype(float)
    return out


def _fmt(value, digits=6):
    return "" if value is None else f"{value:.{digits}g}" if isinstance(value, float) else value


def _write_csv(path, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, buf.getvalue().encode("utf-8"))


def _write_json(path, value):
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def run(cfg, s1_cfg, s1_dir, out_dir, log=print):
    c, boot = cfg.cascade, cfg.bootstrap
    rep = Path(out_dir) / "report"
    ts = load_target_set(s1_cfg, s1_dir, c["stage1"], c["heavy"])
    rows = feature_rows(ts, read_features(Path(out_dir).joinpath(*FEATURE_FILE)))
    n_imputed = impute_no_word_turns(rows)
    if n_imputed:
        log(f"{n_imputed} turns with no stage 1 words are scored as least confident (confidence and entropy 0.0)")
    tie = gate.tiebreak(ts.keys, cfg.seed)
    log(f"target set: {len(ts.keys)} turns, {int(ts.words.sum())} reference words, {ts.left_out} left out")
    table, headline, thresholds, status = [], [], {}, {}
    e1 = ts.errors[c["stage1"]]
    within = max(r for r in c["rates"] if r <= c["escalation_max"])
    summary = {"turns": len(ts.keys), "words": int(ts.words.sum()), "left_out": ts.left_out, "config_hash": cfg.hash,
               "stage1_wer": score.wer(e1, ts.words), "stage1_mean_slice_wer": score.mean_slice_wer(e1, ts.words, ts.slices),
               "heavy_wer": {h: score.wer(ts.errors[h], ts.words) for h in c["heavy"]}, "operating_rate": within}
    if len(c["heavy"]) >= 2:
        summary["best_two_heavy_oracle_wer"] = score.wer(np.minimum.reduce([ts.errors[h] for h in c["heavy"]]), ts.words)
    for heavy in c["heavy"]:
        eh = ts.errors[heavy]
        cost = c["cost"]["heavy"][heavy]
        scores = policy_scores(cfg, ts, rows, heavy, status)
        for name, s in scores.items():
            for point in score.operating_curve(s, e1, eh, ts.words, c["rates"], tie):
                mask = score.escalation_mask(s, point["rate"], tie)
                money = score.gpu_cost(ts.audio_s, mask, c["cost"]["live_rtfx"], cost["rtfx"])
                chosen = score.chosen_errors(e1, eh, mask)
                mean_wer = score.mean_slice_wer(chosen, ts.words, ts.slices)
                table.append([heavy, name, point["rate"], point["escalated"], _fmt(point["escalation_rate"]), point["errors"],
                              _fmt(point["wer"]), _fmt(mean_wer),
                              int(score.meets_gate(point["wer"], point["escalation_rate"], c["target_wer_max"], c["escalation_max"])),
                              _fmt(money["savings"]), _fmt(score.added_latency_ms(mask, cost["latency_p50_ms"]), 7)])
            mask = score.escalation_mask(s, within, tie)
            chosen = score.chosen_errors(e1, eh, mask)
            vs1 = score.paired_cluster_diff(chosen, e1, ts.words, ts.clusters, boot["resamples"], cfg.seed, boot["ci"])
            vsh = score.paired_cluster_diff(chosen, eh, ts.words, ts.clusters, boot["resamples"], cfg.seed, boot["ci"])
            wer_value = score.wer(chosen, ts.words)
            headline.append([heavy, name, within, int(mask.sum()), _fmt(wer_value), int(score.meets_gate(
                wer_value, mask.mean(), c["target_wer_max"], c["escalation_max"])), _fmt(vs1["diff"]), _fmt(vs1["ci"][0]),
                _fmt(vs1["ci"][1]), vs1["verdict"], _fmt(vsh["diff"]), _fmt(vsh["ci"][0]), _fmt(vsh["ci"][1]), vsh["verdict"]])
            if name not in ("random", "oracle"):
                feature, sign = SIGNS.get(name, (name, +1))
                thresholds.setdefault(name, {})[heavy] = {"rate": within, "threshold": gate.threshold_for_rate(s, within),
                                                          "feature": feature, "sign": sign}
        log(f"{heavy}: {len(scores)} policies at {len(c['rates'])} rates")
    _write_csv(rep / "cascade.csv", ["heavy", "policy", "rate", "escalated", "escalation_rate", "errors", "wer", "mean_slice_wer",
                                     "meets_gate", "gpu_savings", "added_latency_ms"], table)
    _write_csv(rep / "headline.csv", ["heavy", "policy", "rate", "escalated", "wer", "meets_gate", "diff_vs_stage1", "ci_lo", "ci_hi",
                                      "verdict_vs_stage1", "diff_vs_heavy", "ci_lo_heavy", "ci_hi_heavy", "verdict_vs_heavy"], headline)
    for key in ("random", "oracle"):
        status.setdefault(key, "ok")
    _write_json(rep / "thresholds.json", thresholds)
    _write_json(rep / "policies.json", status)
    _write_json(rep / "summary.json", summary)
    return {"cascade": table, "headline": headline, "policies": status, "summary": summary}
