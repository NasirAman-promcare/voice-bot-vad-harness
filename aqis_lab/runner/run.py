"""Run a task over a staged pack in resumable shards: skip finished shards, compute the rest, join the results.

CAPABILITIES:
  CAP-RUN-007: run() stages the pack (copy then compute), builds and validates the run card and the shard plan, and in a new run folder writes both; in an existing run folder it resumes only when the stored card equals the rebuilt one except created_utc, notes and machine.cpu_model (owner decision, question 4 (b)) and the stored plan equals the rebuilt plan, else it refuses and names --from-scratch; --from-scratch renames the old folder to <out>.superseded-<UTC> (never deletes) and starts again [tests: test_FR_0_5_05_restart_skips_finished_shards, test_FR_0_5_05_starting_over_requires_from_scratch, test_FR_0_5_05_from_scratch_keeps_old_run_folder, test_FR_0_5_05_changed_card_or_plan_refused, test_FR_0_5_05_resume_rule_for_other_cpu_model, test_FR_0_5_05_run_card_valid_and_traceable]
  CAP-RUN-008: each shard is skipped when shard_finished() proves it finished, else computed clip by clip into canonical JSON rows carrying run_card_id and clip_id and written with its marker; a clip that fails stops the run (RunFailure, no marker for that shard, an ERROR line in runner.log); --max-shards N stops cleanly after N computed shards; when every shard is finished, results.jsonl is the shards' results joined in order [tests: test_FR_0_5_05_shard_results_written_atomically_with_marker, test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids, test_FR_0_5_05_clip_failure_stops_run_without_marker, test_FR_0_5_05_max_shards_stops_cleanly, test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing, test_FR_0_5_04_run_reads_only_local_extracted_clips]
INPUTS AND OUTPUTS: RunOptions in; the run folder (docs/runner/RUNNER.md), log lines on stdout and a RunOutcome
  out; RunInputError (usage or input problem) or RunFailure (a clip failed).
CONTRACTS: run-card v1; run folder layout, result rows and runner.log in docs/runner/RUNNER.md.
INVARIANTS:
  - A shard is never counted as finished without a valid completion marker; finished shards are never recomputed.
  - Results depend only on the pack, the task and the plan: an interrupted and an uninterrupted run give
    byte-identical results.jsonl.
  - Nothing is deleted: --from-scratch renames; stale shard files are replaced atomically.
NOT IN SCOPE:
  - The event log (WP-0.7 adapters; owner decision, question 14); the results store (WP-0.6).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
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
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.contracts.validate import ContractValidationError
from aqis_lab.packs.audio import AudioFormatError
from aqis_lab.runner import store
from aqis_lab.runner.card import build_run_card, card_differences
from aqis_lab.runner.plan import DEFAULT_SHARD_MINUTES, PlanError, build_plan, oversize_shards
from aqis_lab.runner.stage import ClipError, StageError, stage_pack
from aqis_lab.runner.tasks import TASKS

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = REPO_ROOT / "data" / "raw" / "aqis_lab" / "work"
IGNORED_ON_RESUME = ("/created_utc", "/notes", "/run_card_id")
RESUMABLE_MACHINE_CHANGES = ("/machine/cpu_model",)      # owner decision, WP-0.5 question 4 (b)
SESSION_RE = re.compile(r" session (\d+) start")


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
        plan = build_plan(stored["run_card_id"], task, manifest, options.shard_minutes, options.shard_clips)
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
    plan = build_plan(card["run_card_id"], task, manifest, options.shard_minutes, options.shard_clips)
    store.write_json(plan_path, plan, system, exclusive=True)
    drive.make_dirs(out / store.SHARDS, system)
    return card, plan, notes


def _compute_shard(shard, clips_by_id, staged, task, run_card_id, log):
    lines = []
    for clip_id in shard["clip_ids"]:
        clip = clips_by_id[clip_id]
        try:
            stats = task.run_clip(clip, staged.read_clip(clip))
        except (ClipError, AudioFormatError, OSError) as exc:
            log(f"ERROR shard {shard['index']:05d} clip {clip_id}: {exc}")
            raise RunFailure(f"shard {shard['index']:05d} clip {clip_id}: {exc}") from exc
        row = {"clip_id": clip_id, "run_card_id": run_card_id, "task": task.name, "task_version": task.version,
               **stats}
        lines.append(canonical_json(row) + b"\n")
    return b"".join(lines)


def run(options, system=None, echo=print, on_shard=None):
    """Run (or resume) a task over a pack; see the module header. `on_shard` is called after each written shard."""
    task = TASKS.get(options.task)
    if task is None:
        raise RunInputError(f"unknown task {options.task!r}; known tasks: {', '.join(sorted(TASKS))}")
    if options.max_shards is not None and options.max_shards < 0:
        raise RunInputError(f"--max-shards must be 0 or more, got {options.max_shards}")
    out = Path(options.out)
    try:
        drive.check_write_path(out, system)
        staged = stage_pack(options.pack, options.work_dir, system)
        machine = lp.machine_info(system).block()
        card = build_run_card(task, staged, options.seed, options.notes, machine)
        superseded = _supersede(out, system) if options.from_scratch and out.exists() else None
        card, plan, notes = _open_run_folder(out, card, task, staged.manifest, options, system)
    except (drive.DriveError, StageError, lp.PlatformError, PlanError, ContractValidationError) as exc:
        raise RunInputError(str(exc)) from exc
    log = _Log(out, system, echo)
    session = _next_session(out)
    log(f"session {session} start: task {task.name} {task.version}; pack {staged.manifest['manifest_id']} "
        f"{staged.manifest['version']}; run card {card['run_card_id']}; plan {plan['plan_id']} with "
        f"{len(plan['shards'])} shard(s); machine {json.dumps(machine, sort_keys=True)}")
    if superseded is not None:
        log(f"previous run folder moved to {superseded} (--from-scratch)")
    for note in notes:
        log(note)
    for index in oversize_shards(plan):
        log(f"shard {index:05d} holds one clip whose expected work passes the {plan['shard_minutes']}-minute limit")
    clips_by_id = {c["clip_id"]: c for c in staged.manifest["clips"]}
    computed = skipped = 0
    for shard in plan["shards"]:
        index = shard["index"]
        finished, info = store.shard_finished(out, index, plan["plan_id"])
        if finished:
            log(f"shard {index:05d} skipped: finished (marker verified, results sha256 {info['results_sha256']}, "
                f"{info['rows']} rows)")
            skipped += 1
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
        data = _compute_shard(shard, clips_by_id, staged, task, card["run_card_id"], log)
        marker = store.write_shard(out, index, data, len(shard["clip_ids"]), plan["plan_id"], session, machine,
                                   time.monotonic_ns() - start, system)
        log(f"shard {index:05d} finished ({marker['rows']} rows, results sha256 {marker['results_sha256']}, "
            f"{marker['duration_ns'] / 1e9:.3f} s)")
        computed += 1
        if on_shard is not None:
            on_shard(index)
    joined = []
    for shard in plan["shards"]:
        finished, info = store.shard_finished(out, shard["index"], plan["plan_id"])
        if not finished:
            raise RunFailure(f"shard {shard['index']:05d} is not finished after the run ({info})")
        joined.append(store.results_path(out, shard["index"]).read_bytes())
    data = b"".join(joined)
    results = drive.write_bytes(out / store.RESULTS, data, system)
    rows = data.count(b"\n")
    log(f"run complete: {len(plan['shards'])} shard(s), {skipped} skipped and {computed} computed in this session; "
        f"results.jsonl sha256 {hashlib.sha256(data).hexdigest()} ({rows} rows)")
    return RunOutcome("complete", computed, skipped, 0, card["run_card_id"], results)
