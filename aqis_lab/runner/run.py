"""Run a task over a staged pack in resumable shards: skip finished shards, compute the rest, join the results.

CAPABILITIES:
  CAP-RUN-007: run() stages the pack (copy then compute), builds and validates the run card and the shard plan, and in a new run folder writes both; in an existing run folder it resumes only when the stored card equals the rebuilt one except created_utc, notes and machine.cpu_model (owner decision, question 4 (b)) and the stored plan equals the rebuilt plan, else it refuses and names --from-scratch; --from-scratch renames the old folder to <out>.superseded-<UTC> (never deletes) and starts again; before staging, on the oracle platform it pins every thread to the cores of the task's run mode in config/aqis_lab/oracle.yaml (batch cores for batch tasks, the reserved timing cores for timing tasks; WP-0.6 FR-0.6-04, WP-0.7) (a core error is exit 2 before anything is written) and logs `cores: ...`; a task that cannot run on this machine (preflight, WP-0.7) and a clip subset naming a clip that is not in the pack are exit 2 before anything is written [tests: test_FR_0_7_05_realspeed_run_pins_timing_cores_on_oracle, test_FR_0_7_03_runner_refuses_parakeet_without_gpu_before_writing, test_FR_0_7_07_clip_subset_goes_into_the_plan_not_the_card, test_FR_0_6_04_batch_run_kept_off_reserved_cores, test_FR_0_6_04_real_runner_logs_no_reservation_on_this_vm, test_FR_0_6_04_run_stops_with_exit_2_on_core_error, test_FR_0_5_05_restart_skips_finished_shards, test_FR_0_5_05_starting_over_requires_from_scratch, test_FR_0_5_05_from_scratch_keeps_old_run_folder, test_FR_0_5_05_changed_card_or_plan_refused, test_FR_0_5_05_resume_rule_for_other_cpu_model, test_FR_0_5_05_run_card_valid_and_traceable, test_FR_0_5_05_resume_refused_when_card_differs]
  CAP-RUN-008: each shard is skipped when shard_finished() proves it finished, else computed clip by clip into canonical JSON rows carrying run_card_id and clip_id and written with its marker; a clip that fails stops the run (RunFailure, no marker for that shard, an ERROR line in runner.log); --max-shards N stops cleanly after N computed shards; when every shard is finished, results.jsonl is the shards' results joined in order [tests: test_FR_0_5_05_shard_results_written_atomically_with_marker, test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids, test_FR_0_5_05_clip_failure_stops_run_without_marker, test_FR_0_5_05_max_shards_stops_cleanly, test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing, test_FR_0_5_04_run_reads_only_local_extracted_clips]
  CAP-RUN-012: for tasks that write events (WP-0.7) run() keeps one run ID (run_id.txt) and a run_started event (events.head.jsonl, seq 0) per run folder, opens the task inside its failure guard before the first computed shard and logs its description, numbers each shard's events on from the events of the finished shards before it, writes a failed shard's events (with its error event) without a marker and stops, and when every shard is finished joins the head, every shard's events and a run_finished event into events.jsonl, validated against event log v1 before it is written [tests: test_FR_0_7_01_events_validate_against_event_log_v1, test_FR_0_7_07_interrupted_event_run_resumes_with_the_same_log, test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event, test_FR_0_7_07_changed_shard_events_mean_the_shard_is_not_finished, test_FR_0_7_01_vosk_run_events_validate_against_event_log_v1]
INPUTS AND OUTPUTS: RunOptions in; the run folder (docs/runner/RUNNER.md), log lines on stdout and a RunOutcome
  out; RunInputError (usage or input problem) or RunFailure (a clip failed).
CONTRACTS: run-card v1; run folder layout, result rows and runner.log in docs/runner/RUNNER.md.
INVARIANTS:
  - A shard is never counted as finished without a valid completion marker; finished shards are never recomputed.
  - Results depend only on the pack, the task and the plan: an interrupted and an uninterrupted run give
    byte-identical results.jsonl.
  - Nothing is deleted: --from-scratch renames; stale shard files are replaced atomically.
NOT IN SCOPE:
  - The results store (WP-0.6); the adapters themselves (aqis_lab/adapters/).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
  2026-09-28 WP-0.5 round 2 F05: header lists the resume-refusal test (header only).
  2026-09-28 WP-0.6 FR-0.6-04: RunOptions.cores_config; run() pins to the batch cores before staging and logs
    the core line.
  2026-09-30 WP-0.7 FR-0.7-07: RunOptions.clips and .model_cache; run() pins for the task's mode, runs the task's
    preflight, writes event logs for adapter tasks (_open_run_folder, _compute_shard, run); clip-stats unchanged.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from aqis_lab import drive
from aqis_lab import platform as lp
from aqis_lab.oracle_config import OracleConfigError
from aqis_lab.adapters import base as adapters_base
from aqis_lab.adapters import model_cache as models
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.contracts.validate import ContractValidationError, validate_event_lines
from aqis_lab.locks import LockError
from aqis_lab.packs.audio import AudioFormatError
from aqis_lab.runner import store
from aqis_lab.runner.card import build_run_card, card_differences
from aqis_lab.runner.plan import DEFAULT_SHARD_MINUTES, PlanError, build_plan, oversize_shards
from aqis_lab.runner.stage import ClipError, StageError, stage_pack
from aqis_lab.runner.tasks import TASKS
from aqis_lab.timing import cores

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = REPO_ROOT / "data" / "raw" / "aqis_lab" / "work"
IGNORED_ON_RESUME = ("/created_utc", "/notes", "/run_card_id")
RESUMABLE_MACHINE_CHANGES = ("/machine/cpu_model",)      # owner decision, WP-0.5 question 4 (b)
SESSION_RE = re.compile(r" session (\d+) start")
RUN_LEVEL_REASON = "run-level event"


class RunInputError(RuntimeError):
    """The run cannot start: a usage or input problem, or a run folder that holds another run (exit 2)."""


class RunFailure(RuntimeError):
    """A clip failed; the run stopped without marking its shard finished (exit 1)."""


@dataclass
class RunOptions:
    task: str
    pack: Path
    out: Path
    seed: int
    work_dir: Path = DEFAULT_WORK_DIR
    shard_minutes: float = DEFAULT_SHARD_MINUTES
    shard_clips: int | None = None
    max_shards: int | None = None
    from_scratch: bool = False
    drive_mount: Path | None = None
    notes: str = ""
    cores_config: Path | None = None        # oracle.yaml; None: config/aqis_lab/oracle.yaml
    clips: tuple | None = None              # a clip subset (WP-0.7); None: every clip of the pack
    model_cache: Path | None = None         # model files (WP-0.7); None: data/raw/aqis_lab/models


@dataclass
class RunOutcome:
    status: str            # "complete" or "stopped"
    computed: int
    skipped: int
    remaining: int
    run_card_id: str
    results: Path | None


class _Log:
    def __init__(self, run_dir, system, echo):
        self.run_dir, self.system, self.echo = run_dir, system, echo

    def __call__(self, message):
        line = store.append_log(self.run_dir, message, self.system)
        if self.echo:
            self.echo(line)
        return line


def _supersede(out, system):
    stamp = re.sub(r"[-:]|\.\d+", "", store.utc_now())
    target = out.with_name(f"{out.name}.superseded-{stamp}")
    n = 1
    while target.exists():
        n += 1
        target = out.with_name(f"{out.name}.superseded-{stamp}-{n}")
    drive.check_write_path(target, system)
    os.rename(out, target)
    return target


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RunInputError(f"{path} is unreadable ({exc}); use another --out, or --from-scratch to move the "
                            f"folder aside and start again") from exc


def _next_session(run_dir):
    try:
        text = (Path(run_dir) / store.LOG).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 1
    return max((int(m.group(1)) for m in SESSION_RE.finditer(text)), default=0) + 1


def _new_run_id(card):
    stamp = re.sub(r"[-:]|\.\d+", "", store.utc_now())
    return f"run-{stamp}-{card['run_card_id'][:12]}"


def _start_event_log(out, card, system):
    """Write run_id.txt and the run_started event (seq 0) of a new run folder of a task that writes events."""
    run_id = _new_run_id(card)
    drive.write_bytes(out / store.RUN_ID, (run_id + "\n").encode("utf-8"), system, exclusive=True)
    sink = adapters_base.EventSink(run_id, card["run_card_id"], adapters_base.host_id(system))
    sink.emit("runner", "run_started", None, None, {}, audio_time_reason=RUN_LEVEL_REASON)
    drive.write_bytes(out / store.EVENTS_HEAD, sink.data(), system, exclusive=True)


def _read_run_id(out):
    try:
        run_id = (out / store.RUN_ID).read_text(encoding="utf-8").strip()
        head = (out / store.EVENTS_HEAD).read_bytes()
    except OSError as exc:
        raise RunInputError(f"{out} holds a run of a task that writes events but lacks {store.RUN_ID} or "
                            f"{store.EVENTS_HEAD} ({exc}); use another --out, or --from-scratch") from exc
    if not run_id or not all(r.valid for r in validate_event_lines(head)) or head.count(b"\n") != 1:
        raise RunInputError(f"{out / store.EVENTS_HEAD} is not one valid run_started event; use --from-scratch")
    return run_id


def _open_run_folder(out, card, task, manifest, options, system):
    """(card in force, plan, notes for the log) for a new or resumable run folder; RunInputError otherwise."""
    notes = []
    card_path, plan_path = out / store.RUN_CARD, out / store.PLAN
    if card_path.exists():
        stored = _read_json(card_path)
        diffs = [d for d in card_differences(stored, card) if d not in IGNORED_ON_RESUME]
        blocking = [d for d in diffs if d not in RESUMABLE_MACHINE_CHANGES]
        if blocking:
            raise RunInputError(f"the run folder {out} holds another run: its run card differs at "
                                f"{', '.join(blocking)}; use another --out, or --from-scratch to move it aside and "
                                f"start again")
        if diffs:
            notes.append(f"CPU model differs from the run card's ({stored['machine']['cpu_model']!r} there, "
                         f"{card['machine']['cpu_model']!r} here); allowed on resume (owner decision, question 4 (b)); "
                         f"each shard's marker records the machine that computed it")
        plan = build_plan(stored["run_card_id"], task, manifest, options.shard_minutes, options.shard_clips,
                          options.clips)
        if plan_path.exists():
            if _read_json(plan_path) != plan:
                raise RunInputError(f"the shard plan in {plan_path} differs from the plan for these options "
                                    f"(--shard-minutes {options.shard_minutes}, --shard-clips {options.shard_clips}); "
                                    f"repeat the first command's shard options, or use --from-scratch to move the "
                                    f"run folder aside and start again")
        else:
            store.write_json(plan_path, plan, system)
        drive.make_dirs(out / store.SHARDS, system)
        return stored, plan, notes
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise RunInputError(f"{out} exists and is not a run folder (no {store.RUN_CARD}); use another --out, or "
                            f"--from-scratch to move it aside")
    drive.make_dirs(out, system)
    store.write_json(card_path, card, system, exclusive=True)
    plan = build_plan(card["run_card_id"], task, manifest, options.shard_minutes, options.shard_clips, options.clips)
    store.write_json(plan_path, plan, system, exclusive=True)
    if task.emits_events:
        _start_event_log(out, card, system)
    drive.make_dirs(out / store.SHARDS, system)
    return card, plan, notes


def _compute_shard(shard, clips_by_id, staged, task, run_card_id, log, sink=None):
    lines = []
    for clip_id in shard["clip_ids"]:
        clip = clips_by_id[clip_id]
        try:
            if sink is None:
                stats = task.run_clip(clip, staged.read_clip(clip))
            else:
                stats = task.run_clip(clip, staged.read_clip(clip), sink)
        except (ClipError, AudioFormatError, OSError, adapters_base.AdapterError, ContractValidationError) as exc:
            log(f"ERROR shard {shard['index']:05d} clip {clip_id}: {exc}")
            raise RunFailure(f"shard {shard['index']:05d} clip {clip_id}: {exc}") from exc
        row = {"clip_id": clip_id, "run_card_id": run_card_id, "task": task.name, "task_version": task.version,
               **stats}
        lines.append(canonical_json(row) + b"\n")
    return b"".join(lines)


def _check_clips(clips, manifest):
    if clips is None:
        return
    known = {c["clip_id"] for c in manifest["clips"]}
    unknown = sorted(set(clips) - known)
    if unknown or not clips or len(set(clips)) != len(clips):
        raise RunInputError(f"the clip subset must name distinct clips of the pack: {', '.join(unknown)} "
                            f"{'is' if len(unknown) == 1 else 'are'} not in the pack" if unknown else
                            "the clip subset must name one or more distinct clips of the pack")


def _join_events(out, plan, run_id, card, system):
    """The whole run's event log: head, every shard's events and run_finished, validated before it is written."""
    parts = [(out / store.EVENTS_HEAD).read_bytes()]
    for shard in plan["shards"]:
        parts.append(store.events_path(out, shard["index"]).read_bytes())
    data = b"".join(parts)
    sink = adapters_base.EventSink(run_id, card["run_card_id"], adapters_base.host_id(system),
                                   seq_start=data.count(b"\n"))
    sink.emit("runner", "run_finished", None, None, {"status": "completed"}, audio_time_reason=RUN_LEVEL_REASON)
    data += sink.data()
    bad = [r for r in validate_event_lines(data) if not r.valid]
    if bad:
        raise RunFailure(f"the joined event log is not valid event log v1 (line {bad[0].number}: {bad[0].errors[0]})")
    return data


def run(options, system=None, echo=print, on_shard=None):
    """Run (or resume) a task over a pack; see the module header. `on_shard` is called after each written shard."""
    task = TASKS.get(options.task)
    if task is None:
        raise RunInputError(f"unknown task {options.task!r}; known tasks: {', '.join(sorted(TASKS))}")
    if options.max_shards is not None and options.max_shards < 0:
        raise RunInputError(f"--max-shards must be 0 or more, got {options.max_shards}")
    out = Path(options.out)
    try:
        if task.emits_events:
            task.configure(options.model_cache or models.DEFAULT_CACHE, system, options.cores_config)
            task.preflight()
        pinning = cores.pin_for_mode(task.mode, system, options.cores_config)
        drive.check_write_path(out, system)
        staged = stage_pack(options.pack, options.work_dir, system)
        _check_clips(options.clips, staged.manifest)
        machine = lp.machine_info(system).block()
        card = build_run_card(task, staged, options.seed, options.notes, machine)
        if card["mode"] != pinning.mode:
            raise RunInputError(f"the run card mode is {card['mode']!r}, but the runner pinned itself for "
                                f"{pinning.mode!r}")
        superseded = _supersede(out, system) if options.from_scratch and out.exists() else None
        card, plan, notes = _open_run_folder(out, card, task, staged.manifest, options, system)
        run_id = _read_run_id(out) if task.emits_events else None
    except (drive.DriveError, StageError, lp.PlatformError, PlanError, ContractValidationError, cores.CoreError,
            OracleConfigError, adapters_base.AdapterError, LockError) as exc:
        raise RunInputError(str(exc)) from exc
    log = _Log(out, system, echo)
    session = _next_session(out)
    log(f"session {session} start: task {task.name} {task.version}; pack {staged.manifest['manifest_id']} "
        f"{staged.manifest['version']}; run card {card['run_card_id']}; plan {plan['plan_id']} with "
        f"{len(plan['shards'])} shard(s); machine {json.dumps(machine, sort_keys=True)}")
    log(f"cores: {pinning.describe()}")
    if superseded is not None:
        log(f"previous run folder moved to {superseded} (--from-scratch)")
    for note in notes:
        log(note)
    for index in oversize_shards(plan):
        log(f"shard {index:05d} holds one clip whose expected work passes the {plan['shard_minutes']}-minute limit")
    clips_by_id = {c["clip_id"]: c for c in staged.manifest["clips"]}
    computed = skipped = 0
    next_seq = 1                      # seq 0 is the run_started event in events.head.jsonl
    opened = False
    try:
        for shard in plan["shards"]:
            index = shard["index"]
            finished, info = store.shard_finished(out, index, plan["plan_id"])
            if finished:
                log(f"shard {index:05d} skipped: finished (marker verified, results sha256 {info['results_sha256']}, "
                    f"{info['rows']} rows)")
                skipped += 1
                if task.emits_events:
                    next_seq = info["seq_first"] + info["events"]
                continue
            if options.max_shards is not None and computed >= options.max_shards:
                remaining = sum(1 for s in plan["shards"][index:]
                                if not store.shard_finished(out, s["index"], plan["plan_id"])[0])
                log(f"stopped after {computed} computed shard(s) (--max-shards {options.max_shards}); {remaining} "
                    f"shard(s) remain; run the same command again to continue")
                return RunOutcome("stopped", computed, skipped, remaining, card["run_card_id"], None)
            if store.results_path(out, index).exists() or store.marker_path(out, index).exists():
                log(f"shard {index:05d} not finished: {info}; computing it again")
            log(f"shard {index:05d} started ({len(shard['clip_ids'])} clips)")
            start = time.monotonic_ns()
            sink = None
            if task.emits_events:
                sink = adapters_base.EventSink(run_id, card["run_card_id"], adapters_base.host_id(system), next_seq)
                try:
                    if not opened:
                        log(f"task {task.name}: {task.open(sink)}")
                        opened = True
                    data = _compute_shard(shard, clips_by_id, staged, task, card["run_card_id"], log, sink)
                except (RunFailure, adapters_base.AdapterError) as exc:
                    drive.write_bytes(store.events_path(out, index), sink.data(), system)
                    if isinstance(exc, RunFailure):
                        raise
                    log(f"ERROR shard {index:05d} task {task.name}: {exc}")
                    raise RunFailure(f"shard {index:05d} task {task.name}: {exc}") from exc
            else:
                data = _compute_shard(shard, clips_by_id, staged, task, card["run_card_id"], log)
            marker = store.write_shard(out, index, data, len(shard["clip_ids"]), plan["plan_id"], session, machine,
                                       time.monotonic_ns() - start, system,
                                       events=sink.data() if sink is not None else None,
                                       seq_first=next_seq if sink is not None else None)
            if sink is not None:
                next_seq += sink.count
            log(f"shard {index:05d} finished ({marker['rows']} rows, results sha256 {marker['results_sha256']}, "
                f"{marker['duration_ns'] / 1e9:.3f} s)")
            computed += 1
            if on_shard is not None:
                on_shard(index)
    finally:
        if opened:
            task.close()
    joined = []
    for shard in plan["shards"]:
        finished, info = store.shard_finished(out, shard["index"], plan["plan_id"])
        if not finished:
            raise RunFailure(f"shard {shard['index']:05d} is not finished after the run ({info})")
        joined.append(store.results_path(out, shard["index"]).read_bytes())
    data = b"".join(joined)
    if task.emits_events:
        events = drive.write_bytes(out / store.EVENTS, _join_events(out, plan, run_id, card, system), system)
        log(f"events.jsonl sha256 {hashlib.sha256(events.read_bytes()).hexdigest()} "
            f"({events.read_bytes().count(b'\n')} events, run {run_id})")
    results = drive.write_bytes(out / store.RESULTS, data, system)
    rows = data.count(b"\n")
    log(f"run complete: {len(plan['shards'])} shard(s), {skipped} skipped and {computed} computed in this session; "
        f"results.jsonl sha256 {hashlib.sha256(data).hexdigest()} ({rows} rows)")
    return RunOutcome("complete", computed, skipped, 0, card["run_card_id"], results)
