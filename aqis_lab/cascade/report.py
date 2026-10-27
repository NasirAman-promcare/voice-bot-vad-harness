"""Sprint 3 report: prompt-biasing and fine-tuning scorecards, the cascade trade-off plot, the scorecard and the decision inputs.

CAPABILITIES:
  CAP-S3-080: score_prompt() scores the biased predictions against Sprint 1's own predictions of the same model (same data, same scorer):
    WER with a speaker-cluster interval, drug recall on medical, number accuracy on numbers, and the paired change; score_finetune()
    does the same for the base and the LoRA predictions and applies the brief's two gates (drug recall at least the minimum on medical
    clean and phone; us_conv WER up by at most the limit) [no unit test of the tables: they read prediction files from GPU runs; the
    arithmetic they call is tested in test_s3_score.py and in the Sprint 1 scoring tests]
  CAP-S3-081: build_report() writes prompt.csv, finetune.csv, tradeoff.png (heavy escalation rate against target WER, one panel per heavy
    model), scorecard.md with every gate checked and "not measured" where a stage has not run, decision_inputs.md (the figures the
    decision note needs; the decision itself is the owner's) and s3_report.zip (aggregates only) [no unit test: plots and files]
INPUTS AND OUTPUTS: the s3 config, the Sprint 1 output folder and the Sprint 3 output folder in; files under <out>/report out.
CONTRACTS: brief sections 3 and 6.
INVARIANTS:
  - A gate with no measurement says "not measured"; it never passes by default.
  - Audio and per-utterance texts are not written to the report or its archive.
NOT IN SCOPE:
  - The decision itself and the end-to-end architecture blueprint (docs/results/S3/DECISION.md, written at the review).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import csv
import io
import json
import zipfile
from pathlib import Path

from aqis_lab import drive
from aqis_lab.bench import lib
from aqis_lab.bench import score as s1_score
from aqis_lab.cascade import score


class ReportError(RuntimeError):
    """A report cannot be built from the files present."""


def _write_csv(path, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, buf.getvalue().encode("utf-8"))


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(value, digits=4):
    return "" if value is None else f"{value:.{digits}f}"


def _read_parquet(path, columns=None):
    import pyarrow.parquet as pq
    return pq.read_table(path, columns=columns).to_pylist()


def _refs(s1_dir, slice_name, condition):
    path = Path(s1_dir) / "data" / slice_name / f"{condition}.parquet"
    if not path.is_file():
        return None
    return {r["utt_id"]: r for r in _read_parquet(path, ["utt_id", "ref_clean", "cluster", "meta"])}


def _scored(refs, preds, slice_name):
    rows = [{"utt_id": p["utt_id"], "ref": refs[p["utt_id"]]["ref_clean"], "hyp": p["hyp"],
             "cluster": f"{slice_name}:{refs[p['utt_id']]['cluster']}"} for p in preds if p["utt_id"] in refs]
    return s1_score.score_rows(rows)


def _cell(refs, preds, slice_name, category, boot, seed):
    recs = _scored(refs, preds, slice_name)
    total = s1_score.corpus(recs)
    lo, hi = s1_score.bootstrap_ci(recs, boot["resamples"], seed, boot["ci"]) if total["wer"] is not None else (None, None)
    items = [(e["category"], e["text"], p["hyp"]) for p in preds if p["utt_id"] in refs
             for e in json.loads(refs[p["utt_id"]]["meta"]).get("entities", [])]
    recall = s1_score.entity_recall(items) if items else {}
    numbers = s1_score.number_accuracy(recs)
    return {"recs": recs, "n": total["utterances"], "wer": total["wer"], "ci": (lo, hi),
            "drug": recall.get(category), "all_entities": recall.get("all"), "numbers": numbers}


def _paired(a, b, boot, seed):
    by_id = {r.utt_id: r for r in b["recs"]}
    pairs = [(r, by_id[r.utt_id]) for r in a["recs"] if r.utt_id in by_id]
    if not pairs:
        return None
    return score.paired_cluster_diff([x.errors for x, _ in pairs], [y.errors for _, y in pairs], [x.ref_words for x, _ in pairs],
                                     [x.cluster for x, _ in pairs], boot["resamples"], seed, boot["ci"])


def _row(label, cell):
    drug, numbers = cell["drug"], cell["numbers"]
    return [label, cell["n"], _f(cell["wer"]), _f(cell["ci"][0]), _f(cell["ci"][1]),
            drug["found"] if drug else "", drug["total"] if drug else "", _f(drug["recall"]) if drug else "",
            numbers["hits"] if numbers["total"] else "", numbers["total"] if numbers["total"] else "", _f(numbers["rate"])]


COLUMNS = ["n", "wer", "wer_lo", "wer_hi", "drug_found", "drug_total", "drug_recall", "number_hits", "number_total", "number_accuracy"]


def score_prompt(cfg, s1_dir, out_dir):
    boot, rows = cfg.bootstrap, []
    for model in cfg.prompt["models"]:
        for slice_name in cfg.prompt["slices"]:
            for condition in cfg.prompt["conditions"]:
                refs = _refs(s1_dir, slice_name, condition)
                biased_path = Path(out_dir) / "prompt" / model / f"{slice_name}__{condition}.parquet"
                plain_path = Path(s1_dir) / "preds" / model / f"{slice_name}__{condition}.parquet"
                if refs is None or not biased_path.is_file() or not plain_path.is_file():
                    continue
                plain = _cell(refs, _read_parquet(plain_path), slice_name, cfg.eval["category"], boot, cfg.seed)
                biased = _cell(refs, _read_parquet(biased_path), slice_name, cfg.eval["category"], boot, cfg.seed)
                diff = _paired(biased, plain, boot, cfg.seed)
                for label, cell in (("none", plain), ("biased", biased)):
                    rows.append([model, slice_name, condition, *_row(label, cell),
                                 _f(diff["diff"]) if diff and label == "biased" else "", diff["verdict"] if diff and label == "biased" else ""])
    return rows


def score_finetune(cfg, s1_dir, out_dir):
    boot, rows, gates = cfg.bootstrap, [], {"drug_recall": {}, "us_conv": {}}
    for slice_name, conditions in cfg.eval["slices"].items():
        for condition in conditions:
            refs = _refs(s1_dir, slice_name, condition)
            paths = {v: Path(out_dir) / "eval" / v / f"{slice_name}__{condition}.parquet" for v in ("base", "lora")}
            if refs is None or not all(p.is_file() for p in paths.values()):
                continue
            cells = {v: _cell(refs, _read_parquet(p), slice_name, cfg.eval["category"], boot, cfg.seed) for v, p in paths.items()}
            diff = _paired(cells["lora"], cells["base"], boot, cfg.seed)
            for variant, cell in cells.items():
                rows.append([slice_name, condition, *_row(variant, cell), _f(diff["diff"]) if diff and variant == "lora" else "",
                             diff["verdict"] if diff and variant == "lora" else ""])
            if slice_name == "medical" and cells["lora"]["drug"]:
                got = score.recall_change(cells["base"]["drug"]["found"], cells["lora"]["drug"]["found"], cells["lora"]["drug"]["total"])
                got["ok"] = got["post"] >= cfg.eval["drug_recall_min"]
                gates["drug_recall"][condition] = got
            if slice_name == "us_conv":
                gates["us_conv"][condition] = score.non_regression(cells["base"]["wer"], cells["lora"]["wer"],
                                                                    cfg.eval["us_conv_wer_increase_max"])
    return rows, gates


def _plots(rep, cascade_rows, cfg):
    matplotlib = lib("matplotlib")
    matplotlib.use("Agg")
    plt = lib("matplotlib.pyplot")
    heavies = sorted({r["heavy"] for r in cascade_rows})
    fig, axes = plt.subplots(1, len(heavies), figsize=(6.5 * len(heavies), 5), squeeze=False)
    for ax, heavy in zip(axes[0], heavies):
        for policy in sorted({r["policy"] for r in cascade_rows if r["heavy"] == heavy}):
            pts = sorted((float(r["escalation_rate"]), float(r["wer"])) for r in cascade_rows if r["heavy"] == heavy and r["policy"] == policy)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=".", label=policy, linestyle="--" if policy == "oracle" else "-")
        ax.axhline(cfg.cascade["target_wer_max"], color="grey", linewidth=0.8)
        ax.axvline(cfg.cascade["escalation_max"], color="grey", linewidth=0.8)
        ax.set_title(f"stage 1 + {heavy}")
        ax.set_xlabel("heavy escalation rate")
        ax.set_ylabel("target-set WER (pooled)")
        ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(rep / "tradeoff.png", dpi=150)
    plt.close(fig)


def _gate_line(label, ok):
    return f"- {label}: " + ("not measured" if ok is None else "PASS" if ok else "FAIL")


def build_report(cfg, s1_dir, out_dir):
    rep = Path(out_dir) / "report"
    drive.make_dirs(rep)
    cascade_path = rep / "cascade.csv"
    cascade_rows = _read_csv(cascade_path) if cascade_path.is_file() else []
    prompt_rows = score_prompt(cfg, s1_dir, out_dir)
    tune_rows, gates = score_finetune(cfg, s1_dir, out_dir)
    if not (cascade_rows or prompt_rows or tune_rows):
        raise ReportError(f"nothing to report under {out_dir}: run the cascade, prompt, or train and eval stages first")
    names = []
    if prompt_rows:
        _write_csv(rep / "prompt.csv", ["model", "slice", "condition", "variant", *COLUMNS, "wer_change", "verdict"], prompt_rows)
        names.append("prompt.csv")
    if tune_rows:
        _write_csv(rep / "finetune.csv", ["slice", "condition", "variant", *COLUMNS, "wer_change", "verdict"], tune_rows)
        names.append("finetune.csv")
    if cascade_rows:
        _plots(rep, cascade_rows, cfg)
        names += ["cascade.csv", "tradeoff.png"] + [n for n in ("headline.csv", "thresholds.json", "policies.json", "summary.json")
                                                     if (rep / n).is_file()]
    lines = ["# Sprint 3 scorecard (WP-1.3)", "", f"Config hash `{cfg.hash[:8]}`, seed {cfg.seed}.", ""]
    cascade_ok = None
    if cascade_rows:
        passing = [r for r in cascade_rows if r["meets_gate"] == "1" and r["policy"] not in ("oracle",)]
        cascade_ok = bool(passing)
        lines += ["## Cascade", "", f"Gate: pooled target WER <= {cfg.cascade['target_wer_max']:.2%} with <= {cfg.cascade['escalation_max']:.0%} "
                  f"of turns sent to the heavy model. The perfect gate (`oracle`) is an upper bound, not a policy.", ""]
        lines += [_gate_line("a practical policy meets the gate", cascade_ok)]
        for r in sorted(passing, key=lambda r: float(r["wer"]))[:5]:
            lines.append(f"  - {r['heavy']} / {r['policy']} at rate {r['rate']}: WER {float(r['wer']):.2%}, {float(r['escalation_rate']):.1%} escalated, "
                         f"GPU saving {float(r['gpu_savings']):.1%}")
        lines.append("")
    drug_ok = None if not gates["drug_recall"] else all(g["ok"] for g in gates["drug_recall"].values())
    regress_ok = None if not gates["us_conv"] else all(g["ok"] for g in gates["us_conv"].values())
    if tune_rows:
        lines += ["## Fine-tuning pilot", "", f"Gates: drug recall >= {cfg.eval['drug_recall_min']:.0%} on medical clean and phone; "
                  f"us_conv WER up by at most {cfg.eval['us_conv_wer_increase_max']:.1%} absolute.", ""]
        lines += [_gate_line("drug recall on medical", drug_ok), _gate_line("us_conv non-regression", regress_ok), ""]
        for condition, g in sorted(gates["drug_recall"].items()):
            lines.append(f"  - medical/{condition}: drug recall {g['pre']:.1%} -> {g['post']:.1%}")
        for condition, g in sorted(gates["us_conv"].items()):
            lines.append(f"  - us_conv/{condition}: WER {g['pre']:.2%} -> {g['post']:.2%} (change {g['delta']:+.2%})")
        lines.append("")
    if prompt_rows:
        lines += ["## Prompt biasing", "", "See prompt.csv: each biased row is paired with Sprint 1's own prediction of the same model.", ""]
    drive.write_bytes(rep / "scorecard.md", ("\n".join(lines) + "\n").encode("utf-8"))
    names.append("scorecard.md")
    inputs = ["# Decision inputs (WP-1.3)", "", "Figures for docs/results/S3/DECISION.md. The decision and the architecture blueprint are the owner's.", ""]
    thresholds = rep / "thresholds.json"
    if thresholds.is_file():
        inputs += ["## Gate thresholds within the escalation limit", "", "```json", thresholds.read_text(encoding="utf-8").strip(), "```", ""]
    inputs += ["## Gates", "", _gate_line("cascade gate", cascade_ok), _gate_line("drug recall", drug_ok), _gate_line("us_conv non-regression", regress_ok), ""]
    drive.write_bytes(rep / "decision_inputs.md", ("\n".join(inputs) + "\n").encode("utf-8"))
    names.append("decision_inputs.md")
    tmp = rep / "s3_report.zip.build"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(rep / name, name)
    drive.write_bytes(rep / "s3_report.zip", tmp.read_bytes())
    tmp.unlink()
    return rep
