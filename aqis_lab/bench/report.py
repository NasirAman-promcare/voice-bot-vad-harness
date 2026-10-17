"""Sprint 1 report: the number tables (`score`) and the scorecard, weakness map and archive (`report`).

CAPABILITIES:
  CAP-S1-019: score_all() reads the prediction files and prepared references and writes report/cells.csv (WER with a
    speaker-cluster bootstrap CI, CER, utterances and words per model x slice x condition), channel_cost.csv, accent_gap.csv,
    numbers.csv, medical.csv, hallucination.csv, oracle.csv (best single, all-model oracle and best pair per slice x
    condition and on the target set), speed.csv, paired.csv (top 4 models on the target set), models.csv (target WER
    [CI], clean WER and the other scorecard columns) and anchor.json (the anchor check of brief section 8); every figure
    is computed from the files by aqis_lab.bench.score
  CAP-S1-020: build_report() turns those tables into scorecard.md and scorecard.csv, weakness.csv with each model's 3
    worst cells, weakness_map.png (WER relative to the best model in each cell) and s1_report.zip (aggregates only).
    These read real prediction files, so the Colab score and report run checks them; the maths they call is tested in
    tests/aqis_lab/test_s1_scoring.py.
INPUTS AND OUTPUTS: the config and the output folder (data/, preds/, speed/) in; files under <out>/report/ out.
CONTRACTS: brief section 5; docs/results/S1/ takes the aggregates the owner uploads from report/.
INVARIANTS:
  - Every number comes from a prediction row and a reference; a cell with no predictions is absent, never zero.
  - Audio and per-utterance texts are not written to the report or its archive.
NOT IN SCOPE:
  - The decision note (written at the review).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import csv
import dataclasses
import itertools
import json
import zipfile
from pathlib import Path

import numpy as np

from aqis_lab import drive
from aqis_lab.bench import lib, score

ANCHOR_TOLERANCE = 0.7
PARAKEET_PHONE_RATIO = (1.0, 1.4)
NUMBER_SLICES = ("numbers", "us_phone", "sa_india", "medical")


class ReportError(RuntimeError):
    """A report cannot be built from the files present."""


def _write_csv(path, header, rows):
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, buf.getvalue().encode("utf-8"))


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(value, digits=4):
    return "" if value is None else f"{value:.{digits}f}"


class Loaded:
    """Prepared references (no audio) and predictions of one output folder."""

    def __init__(self, cfg, out_dir):
        import pyarrow.parquet as pq
        self.cfg, self.out = cfg, Path(out_dir)
        manifest_path = self.out / "data" / "manifest.json"
        if not manifest_path.is_file():
            raise ReportError(f"{manifest_path} is missing; run prep first")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.dropped = set(self.manifest.get("dropped_slices", {}))
        self.refs = {}
        for slice_name in cfg.slices:
            if slice_name in self.dropped:
                continue
            for condition in cfg.conditions_for(slice_name):
                path = self.out / "data" / slice_name / f"{condition}.parquet"
                if path.is_file():
                    cols = ["utt_id", "ref_clean", "cluster", "meta", "duration_s"]
                    self.refs[(slice_name, condition)] = {r["utt_id"]: r for r in pq.read_table(path, columns=cols).to_pylist()}
        self.preds = {}
        for model in cfg.models:
            for path in sorted((self.out / "preds" / model).glob("*__*.parquet")):
                slice_name, condition = path.stem.split("__")
                self.preds[(model, slice_name, condition)] = pq.read_table(path).to_pylist()
        self.models = [m for m in cfg.models if any(k[0] == m for k in self.preds)]

    def scored(self, model, slice_name, condition):
        """Scored records for the predicted utterances of a cell (references from the prepared data)."""
        refs = self.refs[(slice_name, condition)]
        rows = [{"utt_id": p["utt_id"], "ref": refs[p["utt_id"]]["ref_clean"], "hyp": p["hyp"],
                 "cluster": f"{slice_name}:{refs[p['utt_id']]['cluster']}"} for p in self.preds[(model, slice_name, condition)]]
        return score.score_rows(rows)


def _target_conditions(cfg, slice_name):
    return [c for c in cfg.conditions_for(slice_name) if c in cfg.target_conditions]


def _tagged(recs, condition):
    return [dataclasses.replace(r, utt_id=f"{r.utt_id}@{condition}") for r in recs]


def score_all(cfg, out_dir, gaps=None, log=print):
    data = Loaded(cfg, out_dir)
    if not data.models:
        raise ReportError(f"no prediction files under {Path(out_dir) / 'preds'}")
    rep = Path(out_dir) / "report"
    boot = cfg.bootstrap
    scored, cells = {}, []
    for (model, slice_name, condition) in sorted(data.preds):
        if slice_name == "nonspeech" or (slice_name, condition) not in data.refs:
            continue
        recs = data.scored(model, slice_name, condition)
        scored[(model, slice_name, condition)] = recs
        total = score.corpus(recs)
        lo, hi = score.bootstrap_ci(recs, boot["resamples"], cfg.seed, boot["ci"]) if total["wer"] is not None else (None, None)
        complete = total["utterances"] == len(data.refs[(slice_name, condition)])
        cells.append([model, slice_name, condition, total["utterances"], total["ref_words"], _num(total["wer"]),
                      _num(lo), _num(hi), _num(total["cer"]), total["errors"], int(complete)])
        log(f"scored {model} {slice_name}/{condition}: {total['utterances']} utterances")
    _write_csv(rep / "cells.csv", ["model", "slice", "condition", "utterances", "words", "wer", "wer_lo", "wer_hi", "cer",
                                   "errors", "complete"], cells)
    wer = {(r[0], r[1], r[2]): float(r[5]) for r in cells if r[5] != ""}

    # channel and noise cost, accent gap
    cost_rows, gap_rows = [], []
    for model in data.models:
        for slice_name in cfg.caller_slices:
            clean = wer.get((model, slice_name, "clean"))
            for condition in cfg.conditions_for(slice_name):
                value = wer.get((model, slice_name, condition))
                if clean and value is not None and condition not in ("clean", "native"):
                    cost_rows.append([model, slice_name, condition, _num(value / clean)])
        for condition in cfg.default_conditions:
            us, sa = wer.get((model, "us_conv", condition)), wer.get((model, "sa_conv", condition))
            if us and sa is not None:
                gap_rows.append([model, condition, _num(sa / us)])
    _write_csv(rep / "channel_cost.csv", ["model", "slice", "condition", "wer_over_clean"], cost_rows)
    _write_csv(rep / "accent_gap.csv", ["model", "condition", "sa_conv_over_us_conv"], gap_rows)

    # numbers, medical entities, hallucination
    number_rows, medical_rows, halluc_rows = [], [], []
    for (model, slice_name, condition), recs in sorted(scored.items()):
        if slice_name in NUMBER_SLICES:
            n = score.number_accuracy(recs)
            number_rows.append([model, slice_name, condition, n["hits"], n["total"], _num(n["rate"])])
    for (model, slice_name, condition), preds in sorted(data.preds.items()):
        if slice_name == "medical":
            refs = data.refs[(slice_name, condition)]
            items = []
            for p in preds:
                for entity in json.loads(refs[p["utt_id"]]["meta"]).get("entities", []):
                    items.append((entity["category"], entity["text"], p["hyp"]))
            for category, r in sorted(score.entity_recall(items).items()):
                medical_rows.append([model, condition, category, r["found"], r["total"], _num(r["recall"])])
        if slice_name == "nonspeech":
            h = score.hallucination([p["hyp"] for p in preds])
            halluc_rows.append([model, condition, h["clips"], h["with_words"], _num(h["rate"]), _num(h["mean_words"])])
    _write_csv(rep / "numbers.csv", ["model", "slice", "condition", "hits", "total", "accuracy"], number_rows)
    _write_csv(rep / "medical.csv", ["model", "condition", "category", "found", "total", "recall"], medical_rows)
    _write_csv(rep / "hallucination.csv", ["model", "condition", "clips", "with_words", "rate", "mean_words"], halluc_rows)

    # target set: per model, slice -> pooled records over the target conditions
    groups = {}
    for model in data.models:
        g = {}
        for slice_name in cfg.caller_slices:
            recs = []
            for condition in _target_conditions(cfg, slice_name):
                if (model, slice_name, condition) in scored:
                    recs += _tagged(scored[(model, slice_name, condition)], condition)
            if recs:
                g[slice_name] = recs
        groups[model] = g
    headline = {}
    for model, g in groups.items():
        if len(g) == len(cfg.caller_slices) - len([s for s in cfg.caller_slices if s in data.dropped]):
            headline[model] = (score.mean_of_wers(g), *score.mean_of_wers_ci(g, boot["resamples"], cfg.seed, boot["ci"]))
    ranking = sorted(headline, key=lambda m: headline[m][0])
    paired_rows = []
    top = ranking[:4]
    if len(top) >= 2:
        common = {}
        for slice_name in cfg.caller_slices:
            keys = [{r.utt_id for r in groups[m].get(slice_name, [])} for m in top]
            common[slice_name] = set.intersection(*keys) if all(keys) else set()
        restricted = {m: {s: [r for r in groups[m].get(s, []) if r.utt_id in common[s]] for s in cfg.caller_slices
                          if common[s]} for m in top}
        for a, b in itertools.combinations(top, 2):
            got = score.paired_mean_of_wers(restricted[a], restricted[b], boot["resamples"], cfg.seed, boot["ci"])
            paired_rows.append([a, b, _num(got["diff"]), _num(got["ci"][0]), _num(got["ci"][1]), got["verdict"]])
    _write_csv(rep / "paired.csv", ["model_a", "model_b", "wer_a_minus_wer_b", "ci_lo", "ci_hi", "verdict"], paired_rows)

    # oracle per cell and on the target set
    oracle_rows = []
    cell_keys = sorted({(s, c) for (_, s, c) in scored})
    for slice_name, condition in cell_keys:
        have = [m for m in data.models if (m, slice_name, condition) in scored]
        _oracle_row(oracle_rows, f"{slice_name}/{condition}", {m: scored[(m, slice_name, condition)] for m in have})
    pooled = {m: [r for s in cfg.caller_slices for r in groups[m].get(s, [])] for m in data.models}
    _oracle_row(oracle_rows, "target set", {m: pooled[m] for m in data.models if pooled[m]})
    _write_csv(rep / "oracle.csv", ["scope", "models", "utterances", "ref_words", "best_single", "best_single_wer",
                                    "oracle_wer", "best_pair", "best_pair_wer", "pair_over_single"], oracle_rows)

    # speed
    info = {m: _read_info(Path(out_dir), m) for m in data.models}
    speed_rows = []
    for model in data.models:
        batches = {(k[1], k[2], p["batch_id"], p["batch_audio_s"], p["batch_wall_s"])
                   for k, rows in data.preds.items() if k[0] == model for p in rows}
        rtfx = score.rtfx([(b[3], b[4]) for b in batches]) if batches else None
        speed_path = Path(out_dir) / "speed" / f"{model}.parquet"
        lat = None
        if speed_path.is_file():
            import pyarrow.parquet as pq
            lat = score.latency_stats([r["latency_s"] * 1000 for r in pq.read_table(speed_path).to_pylist()])
        speed_rows.append([model, info[model].get("params") or "", _num(info[model].get("peak_gpu_mem_mib"), 0),
                           _num(rtfx, 1), _num(lat["p50"], 0) if lat else "", _num(lat["p95"], 0) if lat else "",
                           info[model].get("dtype", ""), info[model].get("gpu", "")])
    _write_csv(rep / "speed.csv", ["model", "params", "peak_gpu_mem_mib", "rtfx_batched", "latency_p50_ms",
                                   "latency_p95_ms", "dtype", "gpu"], speed_rows)

    # anchor check
    anchor = {}
    for model, published in cfg.anchor_published_test_other_wer.items():
        clean = wer.get((model, "anchor", "clean"))
        phone = wer.get((model, "anchor", "phone"))
        if clean is None:
            continue
        entry = {"published": published, "measured": round(100 * clean, 2),
                 "delta_points": round(100 * clean - published, 2),
                 "within_tolerance": abs(100 * clean - published) <= ANCHOR_TOLERANCE}
        if phone is not None and model == "parakeet-tdt-0.6b-v2":
            ratio = phone / clean
            entry["phone_over_clean"] = round(ratio, 3)
            entry["phone_ratio_in_range"] = PARAKEET_PHONE_RATIO[0] <= ratio <= PARAKEET_PHONE_RATIO[1]
        anchor[model] = entry
    drive.write_bytes(rep / "anchor.json", (json.dumps(anchor, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    # per-model summary
    model_rows = []
    for model in data.models:
        h = headline.get(model)
        cleans = [wer[(model, s, "clean")] for s in cfg.caller_slices if (model, s, "clean") in wer]
        cost = {}
        for tag, conds in (("phone", ("phone",)), ("webrtc", ("webrtc",))):
            ratios = [float(r[3]) for r in cost_rows if r[0] == model and r[2] in conds]
            cost[tag] = float(np.mean(ratios)) if ratios else None
        gaps_for = [float(r[2]) for r in gap_rows if r[0] == model and r[1] in cfg.target_conditions]
        n_rows = [r for r in number_rows if r[0] == model and r[2] in cfg.target_conditions and r[4] > 0]
        n_hits, n_total = sum(r[3] for r in n_rows), sum(r[4] for r in n_rows)
        med = [r for r in medical_rows if r[0] == model and r[1] in cfg.target_conditions and r[2] == "all"]
        m_found, m_total = sum(r[3] for r in med), sum(r[4] for r in med)
        hal = [r for r in halluc_rows if r[0] == model]
        h_clips, h_with = sum(r[2] for r in hal), sum(r[3] for r in hal)
        speed = next(r for r in speed_rows if r[0] == model)
        cells_here = [r for r in cells if r[0] == model]
        expected = sum(len(cfg.conditions_for(s)) for s in cfg.slices if s not in data.dropped and s != "nonspeech")
        model_rows.append([model, cfg.models[model]["role"], _num(h[0]) if h else "", _num(h[1]) if h else "",
                           _num(h[2]) if h else "", _num(float(np.mean(cleans))) if cleans else "",
                           _num(float(np.mean(gaps_for)), 3) if gaps_for else "", _num(cost["phone"], 3),
                           _num(cost["webrtc"], 3), _num(n_hits / n_total) if n_total else "",
                           _num(m_found / m_total) if m_total else "", _num(h_with / h_clips) if h_clips else "",
                           speed[3], speed[4], cfg.models[model].get("licence", ""),
                           "complete" if len(cells_here) >= expected and all(r[10] for r in cells_here)
                           else f"partial: {len(cells_here)} of {expected} cells"])
    _write_csv(rep / "models.csv", MODEL_HEADER, model_rows)
    drive.write_bytes(rep / "gaps_input.json", (json.dumps(gaps or {}, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    log(f"wrote the number tables to {rep}")
    return rep


MODEL_HEADER = ["model", "role", "target_wer", "target_lo", "target_hi", "clean_wer", "accent_gap", "phone_cost",
                "webrtc_cost", "number_accuracy", "medical_recall", "hallucination_rate", "rtfx", "p50_ms", "licence",
                "status"]


def _read_info(out_dir, model):
    path = out_dir / "preds" / model / "model_info.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _oracle_row(rows, scope, by_model):
    """Append one oracle.csv row; the utterance set is what every listed model predicted."""
    if len(by_model) < 2:
        return
    ids = set.intersection(*[{r.utt_id for r in recs} for recs in by_model.values()])
    if not ids:
        return
    order = sorted(ids)
    errors, ref_words = {}, None
    for model, recs in by_model.items():
        by_id = {r.utt_id: r for r in recs}
        errors[model] = [by_id[i].errors for i in order]
        ref_words = [by_id[i].ref_words for i in order]
    if not sum(ref_words):
        return
    got = score.oracle(errors, ref_words)
    ratio = got["best_pair"]["wer"] / got["best_single"]["wer"] if got["best_single"]["wer"] else None
    rows.append([scope, len(by_model), len(order), sum(ref_words), got["best_single"]["models"][0],
                 _num(got["best_single"]["wer"]), _num(got["oracle"]["wer"]), "+".join(got["best_pair"]["models"]),
                 _num(got["best_pair"]["wer"]), _num(ratio, 3)])


# ---- scorecard and heatmap -----------------------------------------------------------------------------------
def build_report(cfg, out_dir, log=print):
    rep = Path(out_dir) / "report"
    models = _read_csv(rep / "models.csv")
    cells = _read_csv(rep / "cells.csv")
    anchor = json.loads((rep / "anchor.json").read_text(encoding="utf-8"))
    gaps = json.loads((rep / "gaps_input.json").read_text(encoding="utf-8")) if (rep / "gaps_input.json").is_file() else {}
    manifest = json.loads((Path(out_dir) / "data" / "manifest.json").read_text(encoding="utf-8"))

    # weakness: WER relative to the best model in each cell
    best = {}
    for r in cells:
        if r["wer"] != "":
            key = (r["slice"], r["condition"])
            best[key] = min(best.get(key, 1e9), float(r["wer"]))
    relative = {}
    for r in cells:
        key = (r["slice"], r["condition"])
        if r["wer"] != "" and best.get(key):
            relative[(r["model"], key)] = float(r["wer"]) / best[key]
    weak_rows, worst = [], {}
    for model in [m["model"] for m in models]:
        mine = sorted(((v, k) for (m, k), v in relative.items() if m == model), reverse=True)[:3]
        worst[model] = mine
        for v, (s, c) in mine:
            weak_rows.append([model, s, c, _num(v, 2)])
    _write_csv(rep / "weakness.csv", ["model", "slice", "condition", "wer_over_best"], weak_rows)

    ordered = sorted(models, key=lambda m: float(m["target_wer"]) if m["target_wer"] else 9.9)
    header = ["model", "role", "target WER [95% CI]", "clean WER", "accent gap", "phone cost", "WebRTC cost",
              "number acc.", "medical recall", "halluc. rate", "RTFx", "p50 ms", "licence", "status"]
    table = []
    for m in ordered:
        ci = f"{float(m['target_wer']) * 100:.2f}% [{float(m['target_lo']) * 100:.2f}, {float(m['target_hi']) * 100:.2f}]" \
            if m["target_wer"] else "n/a"
        table.append([m["model"], m["role"], ci, f"{float(m['clean_wer']) * 100:.2f}%" if m["clean_wer"] else "n/a",
                      m["accent_gap"] or "n/a", m["phone_cost"] or "n/a", m["webrtc_cost"] or "n/a",
                      f"{float(m['number_accuracy']) * 100:.1f}%" if m["number_accuracy"] else "n/a",
                      f"{float(m['medical_recall']) * 100:.1f}%" if m["medical_recall"] else "n/a",
                      f"{float(m['hallucination_rate']) * 100:.1f}%" if m["hallucination_rate"] else "n/a",
                      m["rtfx"] or "n/a", m["p50_ms"] or "n/a", m["licence"], m["status"]])
    _write_csv(rep / "scorecard.csv", header, table)
    lines = ["# Sprint 1 scorecard", "",
             f"Config hash `{manifest['config_hash'][:12]}`, data commit `{manifest['git_commit'][:10]}`, seed {manifest['seed']}. "
             "Target WER is the mean over the caller slices of each slice's WER on its target conditions; the interval is a "
             "speaker-cluster bootstrap.", "", "## Anchor check (brief section 8, item 2)", ""]
    if anchor:
        for model, a in sorted(anchor.items()):
            extra = f", phone/clean {a['phone_over_clean']}" if "phone_over_clean" in a else ""
            lines.append(f"- {model}: measured {a['measured']} vs published {a['published']} "
                         f"({a['delta_points']:+} points): {'within' if a['within_tolerance'] else 'OUTSIDE'} ±{ANCHOR_TOLERANCE}{extra}")
    else:
        lines.append("- no anchor predictions yet")
    lines += ["", "## Models", "", "| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in table]
    lines += ["", "## Three worst cells per model (WER relative to the best model in the cell)", ""]
    for model, mine in worst.items():
        lines.append(f"- **{model}**: " + "; ".join(f"{s}/{c} ×{v:.2f}" for v, (s, c) in mine))
    gap_lines = [f"- {m['model']}: {gaps.get(m['model'], 'reason not recorded')}" for m in ordered
                 if m["status"] != "complete"]
    gap_lines += [f"- slice {s}: dropped, {why}" for s, why in manifest.get("dropped_slices", {}).items()]
    if gap_lines:
        lines += ["", "## Gaps", ""] + gap_lines
    drive.write_bytes(rep / "scorecard.md", ("\n".join(lines) + "\n").encode("utf-8"))
    _heatmap(rep / "weakness_map.png", relative, [m["model"] for m in ordered])
    members = ["cells.csv", "channel_cost.csv", "accent_gap.csv", "numbers.csv", "medical.csv", "hallucination.csv",
               "oracle.csv", "speed.csv", "paired.csv", "models.csv", "weakness.csv", "scorecard.csv", "scorecard.md",
               "anchor.json", "weakness_map.png"]
    archive = rep / "s1_report.zip"
    tmp = rep / "s1_report.zip.build"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in members:
            z.write(rep / name, name)
        z.write(Path(out_dir) / "data" / "manifest.json", "manifest.json")
        z.write(Path(out_dir) / "data" / "LICENCES.md", "LICENCES.md")
    drive.write_bytes(archive, tmp.read_bytes())
    tmp.unlink()
    log(f"wrote {rep / 'scorecard.md'} and {archive}")


def _heatmap(path, relative, models):
    import io
    matplotlib = lib("matplotlib")
    matplotlib.use("Agg")
    plt = lib("matplotlib.pyplot")
    columns = sorted({k for (_, k) in relative})
    grid = np.full((len(models), len(columns)), np.nan)
    for i, model in enumerate(models):
        for j, key in enumerate(columns):
            if (model, key) in relative:
                grid[i, j] = relative[(model, key)]
    fig, ax = plt.subplots(figsize=(max(8, 0.32 * len(columns)), 0.55 * len(models) + 3))
    image = ax.imshow(np.log2(grid), aspect="auto", cmap="viridis_r", vmin=0, vmax=3)
    ax.set_xticks(range(len(columns)), [f"{s}/{c}" for s, c in columns], rotation=90, fontsize=7)
    ax.set_yticks(range(len(models)), models, fontsize=8)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_ticks([0, 1, 2, 3], labels=["1x", "2x", "4x", "8x"])
    cbar.set_label("WER relative to the best model in the cell (1x = best)")
    ax.set_title("Sprint 1 weakness map")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    drive.write_bytes(path, buf.getvalue())
