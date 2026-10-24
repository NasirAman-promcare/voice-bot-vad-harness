"""Sprint 2 report: the number tables and the scorecard with its gate checks, the DET and trade-off plots, and the archive.

CAPABILITIES:
  CAP-S2-060: score_all() reads the result files and writes report/vad.csv, vad_det.csv, turn.csv, stream.csv and emotion.csv
    (every figure from aqis_lab.live.score, with speaker or actor cluster intervals); build_report() writes scorecard.md with
    the brief's section 7 gates checked row by row, live_stack.csv (all tables in one long file), vad_det.png,
    turn_tradeoff.png and s2_report.zip (aggregates only). These read real result files, so the Oracle and Colab report runs
    check them; the maths they call is tested in test_s2_vad_score.py, test_s2_turn.py and test_s2_emotion.py.
INPUTS AND OUTPUTS: the config and the output folder (results/) in; files under <out>/report/ out.
CONTRACTS: brief sections 4, 7 and 8; thresholds come from scoring.gates in s2.yaml.
INVARIANTS:
  - Every number comes from result rows; a cell with no rows is absent, never zero.
  - A gate that cannot be checked (no row for it) says so in the scorecard instead of passing.
  - Audio and per-utterance texts are not written to the report or its archive.
NOT IN SCOPE:
  - The decision note (written at the review).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import csv
import io
import json
import zipfile
from pathlib import Path

from aqis_lab import drive
from aqis_lab.bench import lib
from aqis_lab.live import emotion, results, score


class ReportError(RuntimeError):
    """A report cannot be built from the files present."""


def _write_csv(path, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, buf.getvalue().encode("utf-8"))


def _fmt(x, digits=4):
    return "" if x is None else f"{x:.{digits}f}"


def _cells(out_dir, component):
    """{(model, condition): rows} for every result file of a component."""
    cells = {}
    for path in sorted((Path(out_dir) / "results" / component).glob("*__*.parquet")):
        rows = results.read_rows(path)
        if rows:
            cells[(rows[0]["model"], rows[0]["condition"])] = rows
    return cells


def _ci(pair):
    return _fmt(pair[0]), _fmt(pair[1])


# ---- tables ------------------------------------------------------------------------------------------------------
def vad_table(cfg, out_dir):
    boot = cfg.scoring["bootstrap"]
    table = []
    for (model, condition), rows in _cells(out_dir, "vad").items():
        for collar in cfg.scoring["collars_ms"]:
            clips = [{"cluster": r["cluster"], "counts": json.loads(r["counts"])[str(collar)],
                      "onset_lags_ms": json.loads(r["onset_lags_ms"]), "offset_lags_ms": json.loads(r["offset_lags_ms"])}
                     for r in rows]
            for subset, chosen in (("all clips", clips), ("non-speech clips", [c for c in clips if c["counts"]["speech_samples"] == 0])):
                if not chosen:
                    continue
                s = score.vad_summary(chosen, boot["resamples"], cfg.seed, boot["ci"])
                audio = sum(r["audio_s"] for r in rows)
                table.append({"model": model, "condition": condition, "collar_ms": collar, "subset": subset, **s,
                              "rtf": sum(r["compute_s"] for r in rows) / audio if audio else None})
    return table


def det_table(cfg, out_dir):
    thresholds = cfg.scoring["det_thresholds"]
    table = []
    for (model, condition), rows in _cells(out_dir, "vad").items():
        per_clip = [json.loads(r["det"]) for r in rows]
        if any(d is None for d in per_clip):
            continue
        for i, thr in enumerate(thresholds):
            agg = {k: sum(d[i][k] for d in per_clip) for k in ("speech_samples", "nonspeech_samples", "missed", "false_alarm")}
            table.append({"model": model, "condition": condition, "threshold": thr, **score.vad_rates(agg)})
    return table


def turn_table(cfg, out_dir):
    boot = cfg.scoring["bootstrap"]
    table = []
    for (model, condition), rows in _cells(out_dir, "turn").items():
        outcomes = [score.TurnOutcome(r["cluster"], r["pauses"], r["false_interruptions"], r["spurious"], r["latency_ms"], r["missed_end"])
                    for r in rows]
        table.append({"model": model, "condition": condition, **score.turn_summary(outcomes, boot["resamples"], cfg.seed, boot["ci"])})
    return table


def stream_table(cfg, out_dir):
    boot = cfg.scoring["bootstrap"]
    table = []
    for (model, condition), rows in _cells(out_dir, "stream").items():
        clips = [{"cluster": r["cluster"], "audio_s": r["audio_s"], "compute_s": r["compute_s"],
                  "step_compute_ms": json.loads(r["step_compute_ms"])} for r in rows]
        audio = sum(r["audio_s"] for r in rows)
        table.append({"model": model, "condition": condition, "chunk_ms": rows[0]["chunk_ms"],
                      **score.stream_summary(clips, boot["resamples"], cfg.seed, boot["ci"]),
                      "offline_rtf": sum(r["offline_compute_s"] for r in rows) / audio if audio else None})
    return table


def emotion_table(cfg, out_dir):
    boot = cfg.scoring["bootstrap"]
    table, by_model = [], {}
    for (model, condition), rows in _cells(out_dir, "emotion").items():
        y_true = [emotion.CLASSES.index(r["label"]) for r in rows]
        y_pred = [emotion.CLASSES.index(r["pred"]) for r in rows]
        m = score.confusion_matrix(y_true, y_pred)
        uar = score.uar(m)
        entry = {"model": model, "condition": condition, "n": len(rows), "uar": uar,
                 "uar_ci": score.uar_ci(y_true, y_pred, [r["cluster"] for r in rows], boot["resamples"], cfg.seed, boot["ci"])
                 if uar is not None else (None, None),
                 "accuracy": score.accuracy(m), "frustration_recall": score.frustration_recall(m),
                 "confusion": json.dumps(m.tolist())}
        anger = [i for i, t in enumerate(y_true) if t == emotion.CLASSES.index("anger")]
        entry["frustration_ci"] = (_bootstrap_recall([y_pred[i] == y_true[i] for i in anger], [rows[i]["cluster"] for i in anger],
                                                     boot["resamples"], cfg.seed, boot["ci"]) if anger else (None, None))
        table.append(entry)
        by_model.setdefault(model, {})[condition] = uar
    for entry in table:
        clean = by_model[entry["model"]].get("clean")
        entry["phone_cost"] = score.phone_cost(entry["uar"], clean) if entry["condition"] != "clean" else None
    return table


def _bootstrap_recall(correct, clusters, resamples, seed, ci):
    hit, total = {}, {}
    for ok, c in zip(correct, clusters):
        hit[c] = hit.get(c, 0) + int(ok)
        total[c] = total.get(c, 0) + 1
    return score.cluster_ratio_ci(hit, total, resamples, seed, ci)


def score_all(cfg, out_dir):
    out_dir = Path(out_dir)
    report = out_dir / "report"
    tables = {"vad": vad_table(cfg, out_dir), "vad_det": det_table(cfg, out_dir), "turn": turn_table(cfg, out_dir),
              "stream": stream_table(cfg, out_dir), "emotion": emotion_table(cfg, out_dir)}
    if not any(tables.values()):
        raise ReportError(f"{out_dir / 'results'} holds no result files; run the vad, turn, stream and emotion stages first")
    for name, rows in tables.items():
        if not rows:
            continue
        header = list(rows[0])
        _write_csv(report / f"{name}.csv", header, [[_cell(r[h]) for h in header] for r in rows])
    return tables


def _cell(value):
    if isinstance(value, tuple):
        return json.dumps(list(value))
    if isinstance(value, float):
        return f"{value:.6g}"
    return "" if value is None else value


# ---- scorecard ---------------------------------------------------------------------------------------------------
def _md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def _pct(x):
    return "" if x is None else f"{100 * x:.2f}%"


def _ms(x):
    return "" if x is None else f"{x:.0f}"


def _band(value, pair):
    return f"{_pct(value)} [{_pct(pair[0])}, {_pct(pair[1])}]" if value is not None else ""


def _gate(ok):
    return "n/a" if ok is None else ("PASS" if ok else "FAIL")


def scorecard(cfg, tables):
    g = cfg.scoring["gates"]
    primary = cfg.scoring["primary_collar_ms"]
    lines = ["# Sprint 2 scorecard (WP-1.2)", "",
             f"Config hash `{cfg.hash[:8]}`, seed {cfg.seed}. Intervals are {int(100 * cfg.scoring['bootstrap']['ci'])}% cluster "
             f"bootstrap intervals ({cfg.scoring['bootstrap']['resamples']} resamples). Rates are totals over totals. "
             f"VAD rows use a {primary} ms collar around each reference boundary; the 0 ms rows are in vad.csv.", ""]
    if tables["vad"]:
        lines += ["## VAD", "", f"Gates: FAR < {_pct(g['far_max'])}, MDR < {_pct(g['mdr_max'])}, onset p50 <= {g['onset_p50_ms_max']} ms.", ""]
        rows = []
        for r in tables["vad"]:
            if r["collar_ms"] != primary or r["subset"] != "all clips":
                continue
            ok = None if r["far"] is None or r["mdr"] is None or r["onset_p50_ms"] is None else (
                r["far"] < g["far_max"] and r["mdr"] < g["mdr_max"] and r["onset_p50_ms"] <= g["onset_p50_ms_max"])
            nonspeech = next((x for x in tables["vad"] if (x["model"], x["condition"], x["collar_ms"], x["subset"]) ==
                              (r["model"], r["condition"], primary, "non-speech clips")), None)
            rows.append([r["model"], r["condition"], _band(r["far"], r["far_ci"]), _band(r["mdr"], r["mdr_ci"]),
                         _pct(nonspeech["far"]) if nonspeech else "", _ms(r["onset_p50_ms"]), _ms(r["onset_p95_ms"]),
                         _ms(r["offset_p50_ms"]), _pct(r["segment_miss_rate"]), _fmt(r["rtf"], 4), _gate(ok)])
        lines += [_md(["model", "condition", "FAR [CI]", "MDR [CI]", "FAR on non-speech clips", "onset p50 ms", "onset p95 ms",
                       "offset p50 ms", "segments never flagged", "RTF", "gates"], rows), ""]
    if tables["turn"]:
        lines += ["## Turn end", "", f"Gates: FIR < {_pct(g['fir_max'])}, endpoint latency p50 <= {g['endpoint_p50_ms_max']} ms.", ""]
        rows = []
        for r in tables["turn"]:
            ok = None if r["fir"] is None or r["latency_p50_ms"] is None else (
                r["fir"] < g["fir_max"] and r["latency_p50_ms"] <= g["endpoint_p50_ms_max"])
            rows.append([r["model"], r["condition"], r["turns"], r["pauses"], _band(r["fir"], r["fir_ci"]), f"{r['spurious_per_turn']:.2f}",
                         _ms(r["latency_p50_ms"]), _ms(r["latency_p95_ms"]), _pct(r["missed_end_rate"]), _gate(ok)])
        lines += [_md(["policy", "condition", "turns", "pauses", "FIR [CI]", "spurious / turn", "latency p50 ms", "latency p95 ms",
                       "no endpoint", "gates"], rows), ""]
    if tables["stream"]:
        lines += ["## Streaming STT on CPU", "", f"Gates: RTF < {cfg.stt_streaming['target_rtf_max']}, chunk latency p95 <= "
                  f"{g['chunk_latency_ms_max']} ms. The decode is a rolling window re-read, not cache-aware streaming.", ""]
        rows = []
        for r in tables["stream"]:
            ok = None if r["rtf"] is None or r["chunk_p95_ms"] is None else (
                r["rtf"] < cfg.stt_streaming["target_rtf_max"] and r["chunk_p95_ms"] <= g["chunk_latency_ms_max"])
            rows.append([r["model"], r["condition"], r["clips"], f"{r['audio_s']:.0f}", f"{_fmt(r['rtf'], 3)} [{_fmt(r['rtf_ci'][0], 3)}, "
                         f"{_fmt(r['rtf_ci'][1], 3)}]", _fmt(r["offline_rtf"], 3), _ms(r["chunk_p50_ms"]), _ms(r["chunk_p95_ms"]), _gate(ok)])
        lines += [_md(["variant / chunk", "condition", "clips", "audio s", "RTF [CI]", "whole-clip RTF", "step p50 ms", "step p95 ms", "gates"], rows), ""]
    if tables["emotion"]:
        lines += ["## Emotion", "", f"Gate: frustration (anger) recall >= {_pct(g['frustration_recall_phone_min'])} on phone audio "
                  f"(target {_pct(g['frustration_recall_target'])}).", ""]
        rows = []
        for r in tables["emotion"]:
            ok = None if r["condition"] != "phone" or r["frustration_recall"] is None else (
                r["frustration_recall"] >= g["frustration_recall_phone_min"])
            rows.append([r["model"], r["condition"], r["n"], _band(r["uar"], r["uar_ci"]), _pct(r["accuracy"]),
                         _band(r["frustration_recall"], r["frustration_ci"]), _fmt(r["phone_cost"], 3), _gate(ok)])
        lines += [_md(["model", "condition", "n", "UAR [CI]", "accuracy", "anger recall [CI]", "UAR / UAR(clean)", "gate"], rows), ""]
    return "\n".join(lines) + "\n"


def _plots(rep, tables):
    matplotlib = lib("matplotlib")
    matplotlib.use("Agg")
    plt = lib("matplotlib.pyplot")
    made = []
    if tables["vad_det"]:
        fig, ax = plt.subplots(figsize=(6, 5))
        for (model, condition) in sorted({(r["model"], r["condition"]) for r in tables["vad_det"]}):
            pts = [(r["far"], r["mdr"]) for r in tables["vad_det"] if (r["model"], r["condition"]) == (model, condition)
                   and r["far"] is not None and r["mdr"] is not None]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=".", label=f"{model} {condition}")
        ax.set_xlabel("false alarm rate")
        ax.set_ylabel("missed detection rate")
        ax.legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(rep / "vad_det.png", dpi=150)
        plt.close(fig)
        made.append("vad_det.png")
    if tables["turn"]:
        fig, ax = plt.subplots(figsize=(6, 5))
        for r in tables["turn"]:
            if r["fir"] is not None and r["latency_p50_ms"] is not None:
                ax.scatter(r["latency_p50_ms"], 100 * r["fir"], label=f"{r['model']} {r['condition']}")
        ax.set_xlabel("endpoint latency p50 (ms)")
        ax.set_ylabel("false interruption rate (%)")
        ax.legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(rep / "turn_tradeoff.png", dpi=150)
        plt.close(fig)
        made.append("turn_tradeoff.png")
    return made


def build_report(cfg, out_dir):
    out_dir = Path(out_dir)
    rep = out_dir / "report"
    tables = score_all(cfg, out_dir)
    drive.make_dirs(rep)
    drive.write_bytes(rep / "scorecard.md", scorecard(cfg, tables).encode("utf-8"))
    long_rows = []
    for component, rows in tables.items():
        for r in rows:
            for metric, value in r.items():
                if metric not in ("model", "condition") and not isinstance(value, (tuple, str)) and value is not None:
                    long_rows.append([component, r.get("model", ""), r.get("condition", ""), metric, _cell(value)])
    _write_csv(rep / "live_stack.csv", ["component", "model", "condition", "metric", "value"], long_rows)
    made = _plots(rep, tables)
    names = ["scorecard.md", "live_stack.csv", *made, *[f"{n}.csv" for n, rows in tables.items() if rows]]
    archive = rep / "s2_report.zip"
    tmp = rep / "s2_report.zip.build"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(rep / name, name)
    drive.write_bytes(archive, tmp.read_bytes())
    tmp.unlink()
    return rep
