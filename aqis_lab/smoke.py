"""The phase 0 smoke run: run the first adapters over the smoke pack on one target and write a traceable result
bundle (FR-0.7-07, NFR-0.7-01).

CAPABILITIES:
  CAP-SMOKE-001: load_config() reads config/aqis_lab/phase0_smoke.yaml strictly: pack, seed, the 5-clip subset (its clip IDs must equal what its rule computes on the pack), targets with their platform and GPU need, the runs per target (task, all clips or the subset), the scored tasks and the score subsets; any problem is a SmokeInputError [tests: test_FR_0_7_07_config_subset_equals_rule, test_FR_0_7_07_config_is_checked]
  CAP-SMOKE-002: run_smoke() refuses a target that is not this machine's platform, refuses a --bundle-dir on Google Drive outside MyDrive/AQIS_LAB (NFR-0.5-02, WP-0.8 DEBT-018) and runs every task's preflight before anything is written (on a GPU target without a GPU it stops: Parakeet is never skipped), then runs each task of the target as a resumable runner run with its own run card: vosk-batch and harness-vad on all 60 clips, vosk-realspeed on the subset, and on colab parakeet-offline (60) and parakeet-compute-delay (subset); with from_scratch every run folder under --out that holds another run is moved aside by the runner (<folder>.superseded-<UTC>) and the run starts again [tests: test_FR_0_7_07_target_must_match_platform, test_FR_0_7_03_colab_smoke_without_gpu_fails_never_skips, test_FR_0_7_07_smoke_creates_valid_run_card_for_every_run, test_FR_0_7_07_vosk_batch_on_all_60_clips, test_FR_0_7_07_harness_vad_on_all_clips, test_FR_0_7_07_realspeed_vosk_on_5_clips, test_FR_0_7_07_second_run_resumes_and_stores_nothing_new, test_NFR_0_7_01_cloud_smoke_within_15_minutes, test_FR_0_7_07_from_scratch_supersedes_the_old_runs, test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab, test_NFR_0_5_02_smoke_accepts_bundle_dir_inside_aqis_lab]
  CAP-SMOKE-003: the transcripts of the scored tasks are scored with the WP-0.3 `score` command per score subset (natural speech, and synthetic TTS apart); every run and score folder is added to a results store, every run card and event log is validated and every stored row is traced [tests: test_FR_0_7_07_speech_clips_scored_with_wp03_scorer, test_FR_0_7_07_trace_works_on_every_row, test_FR_0_7_07_smoke_traced_rows_equal_the_stored_rows, test_FR_0_7_07_failed_trace_of_any_row_stops_the_smoke, test_FR_0_7_07_smoke_revalidates_each_event_log_before_storing]
  CAP-SMOKE-004: the bundle phase0-smoke-<target>-<UTC> holds BUNDLE.json (target, platform, machine, git, locks, elapsed time, run cards, score summaries and the SHA-256 and size of every file), PHASE0_SMOKE.md, runs/<task>/ (run card, plan, results, events, log) and scores/<task>-<subset>/, and is written as one deterministic .tar; every number of the report is printed from a bundle file and each table row names its result row [tests: test_FR_0_7_07_bundle_files_match_bundle_json, test_FR_0_7_07_every_report_number_traces_to_a_row, test_FR_0_7_07_parakeet_only_on_gpu_target_and_report_says_so, test_FR_0_7_07_committed_bundles_and_their_reports_in_docs, test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows]
INPUTS AND OUTPUTS: a target and folders in; run folders under --out, the bundle folder and .tar, a results store
  and a summary on stdout out; SmokeInputError (exit 2) or SmokeFailure (exit 1) on failure.
CONTRACTS: run-card v1, event-log v1, score table 1.0, results store 1.0, docs/runs/PHASE0_SMOKE.md (bundle format).
INVARIANTS:
  - Nothing is written for a target that is not this machine or a task this machine cannot run.
  - A failed run, score, store add or trace stops the smoke; no bundle claims a run that did not finish.
  - Run folders resume: running the smoke again computes only what is not finished.
NOT IN SCOPE:
  - Comparing bundles across machines (aqis_lab/parity.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-07 created.
  2026-10-02 WP-0.7 round 2 F04: run_smoke takes from_scratch and passes it to every run; F02: header lists the
    trace tests (test_FR_0_7_07_from_scratch_supersedes_the_old_runs, test_FR_0_7_07_failed_trace_of_any_row_stops_the_smoke).
  2026-10-02 WP-0.8 DEBT-018: run_smoke checks --bundle-dir with aqis_lab.drive.check_write_path right after
    the platform check, before any preflight or write (SmokeInputError, exit 2).
  2026-10-02 WP-0.8 DEBT-020: header lists the event-log re-validation and report summary tests (header only).
"""
import contextlib
import csv
import hashlib
import io
import json
import re
import statistics
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from aqis_lab import drive
from aqis_lab import platform as lp
from aqis_lab.adapters import base as adapters_base
from aqis_lab.adapters import model_cache as models
from aqis_lab.commands import score as score_command
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.contracts.validate import ContractValidationError, validate_event_lines, validate_run_card
from aqis_lab.locks import CPU_LOCK, GPU_LOCK, LockError, installed_lock
from aqis_lab.results import ingest, views
from aqis_lab.results import store as rstore
from aqis_lab.runner import store as run_store
from aqis_lab.runner.card import git_state
from aqis_lab.runner.run import DEFAULT_WORK_DIR, RunFailure, RunInputError, RunOptions, run
from aqis_lab.runner.tasks import TASKS
from aqis_lab.trace import TraceError, trace_row

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "phase0_smoke.yaml"
DEFAULT_OUT = REPO_ROOT / "data" / "raw" / "aqis_lab" / "smoke"
DEFAULT_BUNDLES = REPO_ROOT / "data" / "raw" / "aqis_lab" / "smoke-bundles"
SCHEMA_VERSION = "1.0"
BUNDLE_VERSION = "1.0"
RUN_FILES = (run_store.RUN_CARD, run_store.PLAN, run_store.RESULTS, run_store.EVENTS, run_store.LOG)
CONFIG_KEYS = {"schema_version", "pack", "seed", "subset", "targets", "runs", "scored_tasks", "score_subsets"}
# Report columns that print a result row's field as it is (see format_value).
REPORT_FIELDS = {k: k for k in ("clip_id", "text_sha256", "words", "finals", "wer", "errors", "ref_words",
                                "speech_s", "speech_frames", "first_partial_latency_ms", "finalisation_latency_ms",
                                "max_frame_lag_ms", "processing_ms", "rtf", "gpu", "audio_s")}


class SmokeError(RuntimeError):
    exit_code = 1


class SmokeInputError(SmokeError):
    """Usage, configuration or machine problem found before anything is written (exit 2)."""
    exit_code = 2


class SmokeFailure(SmokeError):
    """A run, score, store add or check failed (exit 1)."""
    exit_code = 1


@dataclass(frozen=True)
class SmokeConfig:
    path: Path
    pack: Path
    seed: int
    subset: tuple
    targets: dict
    runs: tuple
    scored_tasks: tuple
    score_subsets: dict

    def tasks_for(self, target):
        return [(task, clips) for task, clips, targets in self.runs if target in targets]


@dataclass
class SmokeResult:
    bundle: Path
    tar: Path
    elapsed_s: float
    store: Path
    runs: dict


def subset_rule(manifest, per_split, key_prefix):
    """The subset: per category, the clips with the lowest sha256(key_prefix + clip_id), categories in order."""
    chosen = []
    for split, n in per_split.items():
        clips = sorted((c["clip_id"] for c in manifest["clips"] if c["split"] == split),
                       key=lambda cid: hashlib.sha256((key_prefix + cid).encode("utf-8")).hexdigest())
        if len(clips) < n:
            raise SmokeInputError(f"subset: category {split} has {len(clips)} clip(s), {n} needed")
        chosen += clips[:n]
    return chosen


def load_config(path=DEFAULT_CONFIG):
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise SmokeInputError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != CONFIG_KEYS or data["schema_version"] != SCHEMA_VERSION:
        raise SmokeInputError(f"{path}: needs exactly the keys {sorted(CONFIG_KEYS)} and schema_version "
                              f"{SCHEMA_VERSION!r}")
    pack = REPO_ROOT / data["pack"]
    try:
        manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SmokeInputError(f"{path}: cannot read the pack manifest in {pack}: {exc}") from exc
    sub = data["subset"]
    if not isinstance(sub, dict) or set(sub) != {"key_prefix", "per_split", "clip_ids"}:
        raise SmokeInputError(f"{path}: subset needs exactly key_prefix, per_split and clip_ids")
    computed = subset_rule(manifest, sub["per_split"], sub["key_prefix"])
    if list(sub["clip_ids"]) != computed:
        raise SmokeInputError(f"{path}: subset.clip_ids {sub['clip_ids']} differ from the rule's {computed}")
    targets = data["targets"]
    if not isinstance(targets, dict) or any(set(v) != {"platform", "gpu"} or v["platform"] not in lp.PLATFORMS
                                            for v in targets.values()):
        raise SmokeInputError(f"{path}: each target needs a lab platform and gpu true or false")
    runs = []
    for entry in data["runs"]:
        if set(entry) != {"task", "clips", "targets"} or entry["task"] not in TASKS or entry["task"] == "clip-stats" \
                or entry["clips"] not in ("all", "subset") or not set(entry["targets"]) <= set(targets):
            raise SmokeInputError(f"{path}: run {entry} needs an adapter task, clips all or subset, and known targets")
        runs.append((entry["task"], entry["clips"], tuple(entry["targets"])))
    splits = {c["split"] for c in manifest["clips"]}
    if not set(data["scored_tasks"]) <= {t for t, _, _ in runs} or \
            any(not set(v) <= splits for v in data["score_subsets"].values()):
        raise SmokeInputError(f"{path}: scored_tasks must be runs and score_subsets must name pack categories")
    if type(data["seed"]) is not int or data["seed"] < 0:
        raise SmokeInputError(f"{path}: seed must be an integer >= 0")
    return SmokeConfig(path=path, pack=pack, seed=data["seed"], subset=tuple(computed), targets=targets,
                       runs=tuple(runs), scored_tasks=tuple(data["scored_tasks"]),
                       score_subsets={k: list(v) for k, v in data["score_subsets"].items()})


def format_value(value):
    """How the report prints a value: null, true/false, integers as they are, other numbers with 4 decimals."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _utc_stamp():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y%m%dT%H%M%SZ")


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _run_row_id(row):
    return rstore.result_row_id({"kind": "run-result", **{k: row[k] for k in ingest.RUN_IDENTITY}})


def _score_row_id(row):
    return rstore.result_row_id({"kind": "score", **{k: row[k] for k in ingest.SCORE_IDENTITY}})


def _csv_bytes(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _score(bundle, inputs, cfg, manifest, task, echo):
    rows = {r["clip_id"]: r for r in _rows(bundle / "runs" / task / run_store.RESULTS)}
    card_id = next(iter(rows.values()))["run_card_id"]
    tables = []
    for subset, splits in cfg.score_subsets.items():
        clips = [c for c in manifest["clips"] if c["split"] in splits and c["transcript"] is not None
                 and c["clip_id"] in rows]
        if not clips:
            continue
        folder = inputs / f"{task}-{subset}"
        folder.mkdir(parents=True)
        (folder / "ref.csv").write_bytes(_csv_bytes(["clip_id", "text"], [[c["clip_id"], c["transcript"]]
                                                                         for c in clips]))
        (folder / "hyp.csv").write_bytes(_csv_bytes(["run_card_id", "clip_id", "text"],
                                                    [[card_id, c["clip_id"], rows[c["clip_id"]]["text"]]
                                                     for c in clips]))
        out = bundle / "scores" / f"{task}-{subset}"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = score_command.main(["--ref", str(folder / "ref.csv"), "--hyp", str(folder / "hyp.csv"),
                                       "--out", str(out)])
        if code != 0:
            raise SmokeFailure(f"scoring {task} ({subset}) failed: {stderr.getvalue().strip()}")
        if echo:
            echo(f"scored {task} {subset}: " + stdout.getvalue().splitlines()[1].strip())
        tables.append(f"{task}-{subset}")
    return tables


def _check_and_store(bundle, store_dir, run_cards, tables):
    try:
        for task, card_id in run_cards.items():
            folder = bundle / "runs" / task
            card = json.loads((folder / run_store.RUN_CARD).read_text(encoding="utf-8"))
            validate_run_card(card)
            bad = [r for r in validate_event_lines((folder / run_store.EVENTS).read_bytes()) if not r.valid]
            if bad:
                raise SmokeFailure(f"{folder / run_store.EVENTS} line {bad[0].number} is not valid event log v1: "
                                   f"{bad[0].errors[0]}")
            rstore.add_batch(store_dir, ingest.from_run_folder(folder))
        for table in tables:
            rstore.add_batch(store_dir, ingest.from_score_folder(bundle / "scores" / table))
        traced = 0
        for card_id in run_cards.values():
            for row in views.query_run_card(store_dir, card_id):
                trace_row(store_dir, row["result_row_id"])
                traced += 1
    except (ContractValidationError, rstore.StoreInputError, rstore.StoreConflictError, rstore.StoreIntegrityError,
            TraceError, OSError, ValueError) as exc:
        raise SmokeFailure(f"checking the bundle failed: {exc}") from exc
    return traced


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return lines


def _stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return "no value"
    return f"median {format_value(float(statistics.median(values)))}, maximum {format_value(float(max(values)))}"


def _report(meta, bundle, manifest, cfg):
    split_of = {c["clip_id"]: c["split"] for c in manifest["clips"]}
    m = meta["machine"]
    lines = [f"# Phase 0 smoke run: target {meta['target']}", "",
             f"Bundle `{meta['name']}` (bundle format {BUNDLE_VERSION}, docs/runs/PHASE0_SMOKE.md), written "
             f"{meta['created_utc']} on {meta['host_id']}.", "",
             f"- Machine: platform {m['platform']}, {m['cpu_model']}, {m['architecture']}, {m['os']}, Python "
             f"{m['python_version']}, GPU {m['gpu'] or 'none'}.",
             f"- Code: git commit `{meta['git']['commit']}` (dirty: {str(meta['git']['dirty']).lower()}).",
             "- Locks: " + ", ".join(f"`{l['file']}` sha256 `{l['sha256']}`" for l in meta["locks"]) + ".",
             f"- Elapsed: {format_value(meta['elapsed_s'])} s (NFR-0.7-01: at most 900 s on the cloud VM).", "",
             "Every number below is printed from a file of this bundle. A table row names its result row: add the "
             "bundle's run and score folders to a results store (`python -m aqis_lab results add --run "
             "runs/<task>`, then `--scores scores/<table>`) and run `python -m aqis_lab trace <row>`.", "",
             "## Runs", ""]
    run_rows = []
    for task, info in meta["runs"].items():
        run_rows.append([task, f"`{info['run_card_id']}`", info["mode"], str(info["clips"]),
                         f"`{meta['files'][f'runs/{task}/results.jsonl']['sha256']}`", str(info["events"])])
    lines += _table(["task", "run card", "mode", "clips", "results.jsonl sha256", "events"], run_rows)
    lines += ["", "## Word error rate (WP-0.3 scorer)", "",
              "Tables `*-synthetic-tts` are synthetic TTS speech: plumbing only, never a model judgement "
              "(docs/data/SMOKE_PACK.md).", ""]
    summary_rows, per_clip = [], []
    for table, info in meta["scores"].items():
        summary = json.loads((bundle / "scores" / table / "summary.json").read_text(encoding="utf-8"))
        for variant, s in summary["variants"].items():
            summary_rows.append([table, variant, format_value(s["corpus_wer"]), str(s["errors"]),
                                 str(s["ref_words"]), format_value(s["corpus_cer"]), f"`{info['summary_sha256']}`"])
        import pyarrow.parquet as pq
        for row in pq.read_table(bundle / "scores" / table / "scores.parquet").to_pylist():
            if row["variant"] == "main":
                per_clip.append([table, row["clip_id"], format_value(row["wer"]), str(row["errors"]),
                                 str(row["ref_words"]), f"`{_score_row_id(row)}`"])
    lines += _table(["table", "variant", "corpus WER", "errors", "reference words", "corpus CER",
                     "summary.json sha256"], summary_rows)
    lines += ["", "### WER per clip (variant main)", ""]
    lines += _table(["table", "clip_id", "wer", "errors", "ref_words", "row"], per_clip)
    for task, title in (("vosk-batch", "Vosk batch transcripts (60 clips)"),
                        ("parakeet-offline", "Parakeet offline transcripts (60 clips)")):
        if task not in meta["runs"]:
            continue
        rows = _rows(bundle / "runs" / task / run_store.RESULTS)
        cols = ["clip_id", "words", "text_sha256", "row"] if task == "vosk-batch" else ["clip_id", "text_sha256", "row"]
        lines += ["", f"## {title}", ""]
        lines += _table(["category"] + cols, [[split_of[r["clip_id"]]] + [
            f"`{_run_row_id(r)}`" if c == "row" else format_value(r[c]) for c in cols] for r in rows])
    if "vosk-realspeed" in meta["runs"]:
        rows = _rows(bundle / "runs" / "vosk-realspeed" / run_store.RESULTS)
        batch = {r["clip_id"]: r for r in _rows(bundle / "runs" / "vosk-batch" / run_store.RESULTS)}
        same = sum(r["text_sha256"] == batch[r["clip_id"]]["text_sha256"] for r in rows)
        cols = ["clip_id", "audio_s", "first_partial_latency_ms", "finalisation_latency_ms", "max_frame_lag_ms"]
        lines += ["", "## Real-speed Vosk (20 ms frames, never faster than real time)", "",
                  "First-partial latency: first partial event minus the delivery of the frame holding the first "
                  "recognised word's start. Finalisation latency: last final event minus the audio-end mark. Both "
                  "in milliseconds (owner decision, question 7).", ""]
        lines += _table(cols + ["row"], [[format_value(r[c]) for c in cols] + [f"`{_run_row_id(r)}`"] for r in rows])
        lines += ["", f"- First-partial latency: {_stats([r['first_partial_latency_ms'] for r in rows])} ms.",
                  f"- Finalisation latency: {_stats([r['finalisation_latency_ms'] for r in rows])} ms.",
                  f"- Real-speed transcript equal to the batch transcript: {same} of {len(rows)} clips."]
    if "harness-vad" in meta["runs"]:
        rows = _rows(bundle / "runs" / "harness-vad" / run_store.RESULTS)
        lines += ["", "## Harness VAD (webrtc_vad_mode2, 20 ms frames)", ""]
        lines += _table(["category", "clip_id", "speech_frames", "speech_s", "row"],
                        [[split_of[r["clip_id"]], r["clip_id"], format_value(r["speech_frames"]),
                          format_value(r["speech_s"]), f"`{_run_row_id(r)}`"] for r in rows])
    if "parakeet-compute-delay" in meta["runs"]:
        rows = _rows(bundle / "runs" / "parakeet-compute-delay" / run_store.RESULTS)
        cols = ["clip_id", "audio_s", "processing_ms", "rtf", "gpu"]
        lines += ["", "## Parakeet GPU compute delay (one untimed warm-up first)", ""]
        lines += _table(cols + ["row"], [[format_value(r[c]) for c in cols] + [f"`{_run_row_id(r)}`"] for r in rows])
        lines += ["", f"- Processing time: {_stats([r['processing_ms'] for r in rows])} ms per clip on "
                      f"{rows[0]['gpu']}."]
    if "parakeet-offline" not in meta["runs"]:
        lines += ["", f"Parakeet: not run on target {meta['target']} (a CPU target; FR-0.7-07 runs Parakeet on the "
                      f"GPU target only)."]
    return "\n".join(lines) + "\n"


def _tar_bytes(bundle, created):
    buf = io.BytesIO()
    mtime = int(datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            data = path.read_bytes()
            info = tarfile.TarInfo(f"{bundle.name}/{path.relative_to(bundle).as_posix()}")
            info.size, info.mtime, info.mode, info.uid, info.gid = len(data), mtime, 0o644, 0, 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def run_smoke(target, out=None, store=None, model_cache=None, work_dir=None, bundle_dir=None, drive_mount=None,
              config=DEFAULT_CONFIG, system=None, echo=print, from_scratch=False):
    """Run the smoke for `target`; returns a SmokeResult. See the module header."""
    cache = Path(model_cache) if model_cache is not None else models.DEFAULT_CACHE
    cfg = load_config(config)
    if target not in cfg.targets:
        raise SmokeInputError(f"unknown target {target!r}; targets: {', '.join(cfg.targets)}")
    view = system or lp.SystemView.real()
    try:
        platform = lp.detect_platform(view).platform
    except lp.PlatformError as exc:
        raise SmokeInputError(str(exc)) from exc
    want = cfg.targets[target]["platform"]
    if platform != want:
        raise SmokeInputError(f"--target {target} runs on platform {want}, but this machine is {platform}")
    bundle_dir = Path(bundle_dir) if bundle_dir is not None else DEFAULT_BUNDLES
    try:
        drive.check_write_path(bundle_dir, system)   # NFR-0.5-02: on Google Drive, only under MyDrive/AQIS_LAB
    except drive.DriveError as exc:
        raise SmokeInputError(f"--bundle-dir: {exc}") from exc
    tasks = cfg.tasks_for(target)
    try:
        for task, _ in tasks:
            TASKS[task].configure(cache, system)
            TASKS[task].preflight()
    except adapters_base.AdapterError as exc:
        raise SmokeInputError(f"task {task} cannot run on this machine: {exc.message}") from exc
    out = Path(out) if out is not None else DEFAULT_OUT / target
    start = time.monotonic_ns()
    created, stamp = _utc_stamp()
    name = f"phase0-smoke-{target}-{stamp}"
    manifest = json.loads((cfg.pack / "manifest.json").read_text(encoding="utf-8"))
    on_shard = None
    if drive_mount is not None:
        from aqis_lab.unitlog import touch

        def on_shard(index):
            touch(drive_mount, system=system)
    runs = {}
    for task, clips in tasks:
        options = RunOptions(task=task, pack=cfg.pack, out=out / "runs" / task, seed=cfg.seed,
                             work_dir=Path(work_dir) if work_dir is not None else DEFAULT_WORK_DIR,
                             clips=cfg.subset if clips == "subset" else None, model_cache=cache,
                             drive_mount=drive_mount, notes=f"phase0 smoke, target {target}",
                             from_scratch=from_scratch)
        try:
            outcome = run(options, system=system, echo=echo, on_shard=on_shard)
        except RunInputError as exc:
            raise SmokeInputError(f"task {task}: {exc}") from exc
        except RunFailure as exc:
            raise SmokeFailure(f"task {task}: {exc}") from exc
        if outcome.status != "complete":
            raise SmokeFailure(f"task {task} stopped before it finished ({outcome.remaining} shard(s) remain)")
        runs[task] = outcome.run_card_id
    bundle = bundle_dir / name
    if bundle.exists():
        raise SmokeFailure(f"{bundle} already exists")
    for task in runs:
        (bundle / "runs" / task).mkdir(parents=True)
        for file in RUN_FILES:
            (bundle / "runs" / task / file).write_bytes((out / "runs" / task / file).read_bytes())
    tables = []
    inputs = bundle_dir / f"{name}.inputs"
    for task in cfg.scored_tasks:
        if task in runs:
            tables += _score(bundle, inputs, cfg, manifest, task, echo)
    store_dir = Path(store) if store is not None else rstore.DEFAULT_STORE
    traced = _check_and_store(bundle, store_dir, runs, tables)
    elapsed = (time.monotonic_ns() - start) / 1e9
    try:
        lock = installed_lock()
    except LockError as exc:
        raise SmokeFailure(str(exc)) from exc
    lock_files = [CPU_LOCK] + ([GPU_LOCK] if lock == GPU_LOCK else [])
    meta = {"bundle_version": BUNDLE_VERSION, "name": name, "target": target, "platform": platform,
            "created_utc": created, "elapsed_s": elapsed, "host_id": adapters_base.host_id(system),
            "machine": lp.machine_info(system).block(), "git": git_state(),
            "locks": [{"file": f, "sha256": hashlib.sha256((REPO_ROOT / f).read_bytes()).hexdigest()}
                      for f in lock_files],
            "runs": {}, "scores": {}, "traced_rows": traced}
    for task, card_id in runs.items():
        card = json.loads((bundle / "runs" / task / run_store.RUN_CARD).read_text(encoding="utf-8"))
        meta["runs"][task] = {"run_card_id": card_id, "mode": card["mode"],
                              "clips": len(_rows(bundle / "runs" / task / run_store.RESULTS)),
                              "events": (bundle / "runs" / task / run_store.EVENTS).read_bytes().count(b"\n")}
    for table in tables:
        task = next(t for t in runs if table.startswith(t + "-"))
        meta["scores"][table] = {"task": task, "subset": table[len(task) + 1:], "run_card_id": runs[task],
                                 "summary_sha256": hashlib.sha256(
                                     (bundle / "scores" / table / "summary.json").read_bytes()).hexdigest()}
    files = {p.relative_to(bundle).as_posix(): p for p in bundle.rglob("*") if p.is_file()}
    meta["files"] = {rel: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                     for rel, p in sorted(files.items())}
    report = _report(meta, bundle, manifest, cfg).encode("utf-8")
    (bundle / "PHASE0_SMOKE.md").write_bytes(report)
    meta["files"]["PHASE0_SMOKE.md"] = {"sha256": hashlib.sha256(report).hexdigest(), "bytes": len(report)}
    meta["files"] = dict(sorted(meta["files"].items()))
    (bundle / "BUNDLE.json").write_bytes((json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    tar_data = _tar_bytes(bundle, created)
    (bundle_dir / f"{name}.tar").write_bytes(tar_data)
    try:
        drive.make_dirs(out, system)
        tar_path = drive.write_bytes(out / f"{name}.tar", tar_data, system, exclusive=True)
    except (drive.DriveError, OSError) as exc:
        raise SmokeFailure(f"cannot write the bundle archive to {out}: {exc}") from exc
    if echo:
        echo(f"smoke complete: bundle {bundle} ({len(meta['files']) + 1} files, {traced} rows traced), archive "
             f"{tar_path}, {elapsed:.1f} s")
    return SmokeResult(bundle=bundle, tar=tar_path, elapsed_s=elapsed, store=store_dir, runs=runs)
