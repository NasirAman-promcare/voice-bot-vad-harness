"""Sprint 1 GPU runner: copy a prepared cell to local disk, transcribe it, write predictions, resume after a drop.

CAPABILITIES:
  CAP-S1-013: make_pred_rows() and check_pred_rows() build and check prediction rows with every column of brief section
    6.3 (model, Hugging Face ID, revision, stack, hypothesis, batch timing, library versions, dtype, GPU, git commit,
    seed, UTC time); a missing, unlisted or empty trace column is an error [tests:
    test_s1_prediction_rows_have_every_column_of_the_spec, test_s1_prediction_row_missing_a_column_fails,
    test_s1_prediction_row_with_an_empty_trace_field_fails, test_s1_prediction_row_with_an_unlisted_column_fails,
    test_s1_make_pred_rows_refuses_fields_missing_from_the_run_facts]
  CAP-S1-014: write_preds(), read_preds(), missing_ids() and merge_preds() keep one atomically written parquet file per
    model x slice x condition, so a rerun computes only the utterances a file lacks, adds them to what is there, and
    refuses to mix model revisions or repeat an utterance [tests: test_s1_prediction_file_roundtrip_and_missing_ids,
    test_s1_merging_new_rows_keeps_the_old_ones_and_refuses_another_revision, test_s1_merging_a_duplicate_utterance_is_an_error]
  CAP-S1-015: run_model() and run_speed() load a model once, warm it up on 2 clips, batch each cell by length, time
    every batch between CUDA synchronisations, and write predictions (stages smoke, anchor, pilot, full) or batch-1
    latencies (speed); the smoke stage prints hypotheses beside references and fails on empty or identical text for
    speech clips. They need a GPU and a model, so the Colab smoke run checks them; they have no unit tests.
INPUTS AND OUTPUTS: the config, prepared parquet files under <out>/data and a model name in; parquet files under
  <out>/preds/<model>/, <out>/speed/ and <out>/revisions.json out; RowError, RunError.
CONTRACTS: brief sections 4 and 6.3.
INVARIANTS:
  - Imports only numpy, pyarrow, the standard library and the model stack (never the scorer), so each GPU virtual
    environment stays small.
  - A model revision is resolved once and kept in revisions.json, so a model never changes revision during the sprint.
  - Load time and warm-up are never timed; every timed batch is bracketed by CUDA synchronisation.
  - Files on Drive are written only through aqis_lab.drive (atomic, under AQIS_LAB).
NOT IN SCOPE:
  - Scoring (score.py, report.py) and the model wrappers (models.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import datetime
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from aqis_lab import drive
from aqis_lab.bench import lib

PRED_COLUMNS = ("utt_id", "model", "hf_id", "revision", "stack", "hyp", "batch_id", "batch_audio_s", "batch_wall_s",
                "versions", "dtype", "gpu", "git_commit", "seed", "utc")
FACT_KEYS = ("model", "hf_id", "revision", "stack", "versions", "dtype", "gpu", "git_commit", "seed", "utc")
TRACE_KEYS = ("model", "hf_id", "revision", "stack", "versions", "dtype", "gpu", "git_commit", "utc")
SPEED_COLUMNS = ("utt_id", "model", "hf_id", "revision", "duration_s", "latency_s", "dtype", "gpu", "git_commit",
                 "seed", "utc")
SR = 16000


class RowError(ValueError):
    """A result row breaks the format of brief section 6.3."""


class RunError(RuntimeError):
    """A run cannot continue."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- rows ----------------------------------------------------------------------------------------------------
def make_pred_rows(facts, utt_ids, hyps, batch_ids, batch_audio_s, batch_wall_s):
    missing = [k for k in FACT_KEYS if k not in facts]
    if missing:
        raise RowError(f"run facts lack {', '.join(missing)}")
    rows = []
    for u, h, b, a, w in zip(utt_ids, hyps, batch_ids, batch_audio_s, batch_wall_s):
        values = {"utt_id": u, "hyp": h, "batch_id": b, "batch_audio_s": a, "batch_wall_s": w}
        rows.append({c: values[c] if c in values else facts[c] for c in PRED_COLUMNS})
    return rows


def check_pred_rows(rows):
    for row in rows:
        missing = [c for c in PRED_COLUMNS if c not in row]
        if missing:
            raise RowError(f"prediction row {row.get('utt_id', '?')} lacks {', '.join(missing)}")
        extra = sorted(set(row) - set(PRED_COLUMNS))
        if extra:
            raise RowError(f"prediction row {row['utt_id']} has unlisted column {', '.join(extra)}")
        empty = [c for c in TRACE_KEYS if row[c] in ("", None)]
        if empty:
            raise RowError(f"prediction row {row['utt_id']} has an empty trace field: {', '.join(empty)}")


def _table(rows, columns):
    import pyarrow as pa
    return pa.Table.from_pylist([{c: r[c] for c in columns} for r in rows])


def _write_parquet(path, table):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd")
    path = Path(path)
    drive.make_dirs(path.parent)
    drive.write_bytes(path, sink.getvalue().to_pybytes())


def write_preds(path, rows):
    check_pred_rows(rows)
    _write_parquet(path, _table(rows, PRED_COLUMNS))


def read_preds(path):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def missing_ids(path, required):
    """The ids in `required` (in order) that the prediction file does not hold yet."""
    path = Path(path)
    have = {r["utt_id"] for r in read_preds(path)} if path.exists() else set()
    return [u for u in required if u not in have]


def merge_preds(path, new_rows):
    path = Path(path)
    old = read_preds(path) if path.exists() else []
    seen = {r["utt_id"] for r in old}
    for row in new_rows:
        if row["utt_id"] in seen:
            raise RowError(f"{path.name}: utterance {row['utt_id']} is already predicted")
        seen.add(row["utt_id"])
    combined = old + list(new_rows)
    for key in ("revision", "model"):
        values = {r[key] for r in combined}
        if len(values) > 1:
            raise RowError(f"{path.name}: rows would mix {key} values {sorted(values)}; a model keeps one {key} for the "
                           f"sprint")
    write_preds(path, combined)


# ---- stages and cells ----------------------------------------------------------------------------------------
def git_commit(repo_root):
    proc = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RunError(f"cannot read the git commit of {repo_root}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def read_manifest(out_dir):
    path = Path(out_dir) / "data" / "manifest.json"
    if not path.is_file():
        raise RunError(f"{path} is missing; run `prep` first")
    return json.loads(path.read_text(encoding="utf-8"))


def stage_cells(cfg, stage, manifest):
    """[(slice, condition, row_limit or None)] a stage covers; slices prep dropped are left out."""
    spec = cfg.stages[stage]
    dropped = set(manifest.get("dropped_slices", {}))
    names = spec.get("slices", list(cfg.slices))
    cells = []
    for name in names:
        if name in dropped:
            continue
        limit = spec.get("per_slice")
        for condition in cfg.stage_conditions(stage, name):
            cells.append((name, condition, limit))
    return cells


def revision_for(model_name, hf_id, out_dir):
    path = Path(out_dir) / "revisions.json"
    known = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if model_name not in known:
        known[model_name] = lib("huggingface_hub").HfApi().model_info(hf_id).sha
        drive.write_bytes(path, (json.dumps(known, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return known[model_name]


def _local_copy(src, work_dir):
    dst = Path(work_dir) / "s1_data" / Path(src).parent.name / Path(src).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size:
        shutil.copyfile(src, dst)
    return dst


def read_cell(path, columns):
    import pyarrow.parquet as pq
    return pq.read_table(path, columns=list(columns)).to_pylist()


def _audio(row):
    return np.frombuffer(row["audio"], dtype=np.int16).astype(np.float32) / 32768.0


def batches_by_length(rows, size):
    ordered = sorted(rows, key=lambda r: -r["n_samples"])
    return [ordered[i:i + size] for i in range(0, len(ordered), size)]


def _facts(model, cfg, name, revision, gpu, commit):
    return {"model": name, "hf_id": cfg.models[name]["hf"], "revision": revision, "stack": cfg.models[name]["stack"],
            "versions": json.dumps(model.versions(), sort_keys=True), "dtype": model.dtype, "gpu": gpu,
            "git_commit": commit, "seed": cfg.seed, "utc": utc_now()}


def _update_model_info(out_dir, name, info):
    path = Path(out_dir) / "preds" / name / "model_info.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    info["peak_gpu_mem_mib"] = max(info.get("peak_gpu_mem_mib") or 0, old.get("peak_gpu_mem_mib") or 0)
    old.update(info)
    drive.make_dirs(path.parent)
    drive.write_bytes(path, (json.dumps(old, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _load(cfg, name, out_dir, dtype, log):
    from aqis_lab.bench import models
    revision = revision_for(name, cfg.models[name]["hf"], out_dir)
    started = time.perf_counter()
    model = models.load(name, cfg.models[name], revision, dtype)
    log(f"{name}: loaded revision {revision[:10]} in {time.perf_counter() - started:.0f} s (dtype {model.dtype})")
    return model, revision


def run_model(cfg, name, stage, out_dir, work_dir, repo_root, gpu, dtype=None, slices=None, log=print):
    """Predict every cell of `stage` for model `name`; returns the smoke failures (empty list when none)."""
    if name not in cfg.models:
        raise RunError(f"unknown model {name!r}; the config has {', '.join(cfg.models)}")
    if stage == "anchor" and name not in cfg.stages["anchor"]["models"]:
        raise RunError(f"{name} is not an anchor model ({', '.join(cfg.stages['anchor']['models'])})")
    out_dir = Path(out_dir)
    manifest = read_manifest(out_dir)
    commit = git_commit(repo_root)
    model = revision = None
    failures, shown = [], []
    for slice_name, condition, limit in stage_cells(cfg, stage, manifest):
        if slices and slice_name not in slices:
            continue
        src = out_dir / "data" / slice_name / f"{condition}.parquet"
        if not src.is_file():
            raise RunError(f"{src} is missing; run `prep` for {slice_name} first")
        path = out_dir / "preds" / name / f"{slice_name}__{condition}.parquet"
        ids = [r["utt_id"] for r in read_cell(src, ["utt_id"])]
        required = ids[:limit] if limit else ids
        todo = missing_ids(path, required)
        if not todo:
            log(f"{slice_name}/{condition}: complete ({len(required)} utterances), skipped")
            continue
        if model is None:
            model, revision = _load(cfg, name, out_dir, dtype, log)
        rows = read_cell(_local_copy(src, work_dir), ["utt_id", "audio", "n_samples", "duration_s", "ref_clean"])
        wanted = set(todo)
        rows = [r for r in rows if r["utt_id"] in wanted]
        if not getattr(model, "warmed", False):
            model.transcribe([_audio(r) for r in rows[:2]])
            model.sync()
            model.warmed = True
        size = cfg.models[name]["batch"]
        utt_ids, hyps, batch_ids, batch_audio, batch_wall = [], [], [], [], []
        for batch_id, batch in enumerate(batches_by_length(rows, size)):
            prepared = model.prepare([_audio(r) for r in batch])
            model.sync()
            started = time.perf_counter()
            out = model.run(prepared)
            model.sync()
            wall = time.perf_counter() - started
            model.release(prepared)
            if len(out) != len(batch):
                raise RunError(f"{name} returned {len(out)} texts for {len(batch)} clips")
            for r, text in zip(batch, out):
                utt_ids.append(r["utt_id"])
                hyps.append(text)
                batch_ids.append(batch_id)
                batch_audio.append(sum(b["duration_s"] for b in batch))
                batch_wall.append(wall)
        new_rows = make_pred_rows(_facts(model, cfg, name, revision, gpu, commit), utt_ids, hyps, batch_ids,
                                  batch_audio, batch_wall)
        merge_preds(path, new_rows)
        log(f"{slice_name}/{condition}: {len(new_rows)} utterances, {sum(batch_wall) / max(len(set(batch_ids)), 1):.2f} s "
            f"per batch (written {path.name})")
        refs = {r["utt_id"]: r["ref_clean"] for r in rows}
        shown.append((slice_name, condition, [(refs[u], h) for u, h in zip(utt_ids, hyps)]))
    if model is not None:
        _update_model_info(out_dir, name, {"hf_id": cfg.models[name]["hf"], "revision": revision,
                                           "stack": cfg.models[name]["stack"], "batch": cfg.models[name]["batch"],
                                           "gpu": gpu, **model.info()})
        model.close()
    if stage == "smoke":
        failures = smoke_check(name, shown, log)
    return failures


def smoke_check(name, shown, log=print):
    """Print hypotheses beside references; return the failures: empty clean-speech output or identical output."""
    failures = []
    for slice_name, condition, pairs in shown:
        speech = [(ref, hyp) for ref, hyp in pairs if ref]
        for ref, hyp in pairs:
            log(f"  [{slice_name}/{condition}] REF: {ref[:90]!r}\n  {'':{len(slice_name) + len(condition) + 4}}HYP: {hyp[:90]!r}")
        if condition == "clean" and any(not hyp.strip() for _, hyp in speech):
            failures.append(f"{name}: empty output for a speech clip in {slice_name}/clean")
        if len(speech) >= 2 and len({ref for ref, _ in speech}) >= 2 and len({hyp for _, hyp in speech}) == 1:
            failures.append(f"{name}: identical output for different speech clips in {slice_name}/{condition}")
    return failures


def run_speed(cfg, name, out_dir, work_dir, repo_root, gpu, dtype=None, log=print):
    """Batch-1 latency on `speed.clips` clips of 3 to 8 s from the speed slices, after `speed.warmup` untimed clips."""
    spec = cfg.speed
    out_dir = Path(out_dir)
    path = out_dir / "speed" / f"{name}.parquet"
    if path.exists():
        log(f"{name}: speed file exists, skipped")
        return
    manifest = read_manifest(out_dir)
    pools = []
    for slice_name in spec["from_slices"]:
        if slice_name in manifest.get("dropped_slices", {}):
            continue
        src = out_dir / "data" / slice_name / f"{spec['condition']}.parquet"
        rows = read_cell(_local_copy(src, work_dir), ["utt_id", "audio", "n_samples", "duration_s"])
        lo, hi = spec["length_s"]
        pools.append([r for r in rows if lo <= r["duration_s"] <= hi])
    chosen = []
    for k in range(max((len(p) for p in pools), default=0)):
        for pool in pools:
            if k < len(pool) and len(chosen) < spec["clips"] + spec["warmup"]:
                chosen.append(pool[k])
    if len(chosen) < spec["clips"] + spec["warmup"]:
        raise RunError(f"only {len(chosen)} clips of {spec['length_s']} s, {spec['clips'] + spec['warmup']} needed")
    model, revision = _load(cfg, name, out_dir, dtype, log)
    for r in chosen[:spec["warmup"]]:
        model.transcribe([_audio(r)])
    model.sync()
    latencies = []
    for r in chosen[spec["warmup"]:]:
        prepared = model.prepare([_audio(r)])
        model.sync()
        started = time.perf_counter()
        model.run(prepared)
        model.sync()
        latencies.append(time.perf_counter() - started)
        model.release(prepared)
    commit = git_commit(repo_root)
    facts = _facts(model, cfg, name, revision, gpu, commit)
    rows = [{"utt_id": r["utt_id"], "model": name, "hf_id": facts["hf_id"], "revision": revision,
             "duration_s": r["duration_s"], "latency_s": lat, "dtype": facts["dtype"], "gpu": gpu,
             "git_commit": commit, "seed": cfg.seed, "utc": facts["utc"]}
            for r, lat in zip(chosen[spec["warmup"]:], latencies)]
    _write_parquet(path, _table(rows, SPEED_COLUMNS))
    _update_model_info(out_dir, name, {"hf_id": facts["hf_id"], "revision": revision, "stack": facts["stack"],
                                       "gpu": gpu, **model.info()})
    model.close()
    log(f"{name}: batch-1 latency over {len(latencies)} clips: median {1000 * float(np.median(latencies)):.0f} ms")
