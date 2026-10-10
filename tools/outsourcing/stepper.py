"""Step runner and final verifier for relay execution.

CAPABILITIES:
  CAP-OUTSOURCING-STEPPER: Run step parts and final verifications with fix turns and model switching. [tests: test_stepper.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Accepts RunContext and StepPart; executes LLM requests, bundle imports, checks, and returns StepOutcome.
CONTRACTS: none.
INVARIANTS:
  - Fix turns stay on the model that answered the first attempt unless quota/error triggers a model switch.
  - Model switches re-start the part from attempt 1 in a fresh conversation.
NOT IN SCOPE:
  - CLI parsing (handled by relay.py).
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

import json
import sys
import time
import zoneinfo
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from tools.outsourcing import (
    bundle, checks, fixorder, importer, prompt, records, secrets, steplog, workorder,
)
from tools.outsourcing.chat import (
    ApiError, ChatRequest, CredentialError, DailyQuotaExhausted, ModelError,
    ServiceBusy, StepTooLarge, TransportError,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import _la_offset, _resolve_tz, next_reset
from tools.outsourcing.records import (
    CheckResult, CheckResults, RelayOptions, Request, Result, StepOutcome, StepPart, StepRecord,
)
from tools.outsourcing.router import NoEligibleModel, PoolExhausted, Router, client_for
from tools.outsourcing.steplog import StepLog
from tools.outsourcing.workorder import WorkOrder
from tools.outsourcing.worktree import Worktree

__all__ = ["RunContext", "run_part", "run_final"]


@dataclass
class RunContext:
    order: WorkOrder
    plan: tuple[workorder.Step, ...]
    worktree: Worktree
    router: Router
    governor: Governor
    step_log: StepLog
    options: RelayOptions
    clock: Callable[[], float]
    sleeper: Callable[[float], None]
    log_root: Path
    main_root: Path
    run_exclusions: set[str] = field(default_factory=set)


def _hash_file(path: Path) -> str:
    if not path.exists():
        return ""
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_current_files(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    files = {}
    for p in paths:
        fp = root / p
        if fp.exists():
            files[p] = fp.read_text(encoding="utf-8")
    return files


def _print_paused_daily(ctx: RunContext, reset_utc: datetime | None) -> None:
    now = ctx.clock()
    res_dt = reset_utc or next_reset(ctx.router.pool, "UTC", now).reset_utc

    prov_tz, _ = _resolve_tz("America/Los_Angeles")
    if prov_tz is None:
        reset_prov_dt = res_dt.astimezone(timezone(_la_offset(res_dt)))
    else:
        reset_prov_dt = res_dt.astimezone(prov_tz)

    try:
        karachi_tz: datetime.tzinfo = zoneinfo.ZoneInfo("Asia/Karachi")
    except zoneinfo.ZoneInfoNotFoundError:
        karachi_tz = timezone(timedelta(hours=5))
    reset_karachi_dt = res_dt.astimezone(karachi_tz)

    resume_cmd = f".venv/bin/python -m tools.outsourcing.relay --wo {ctx.options.wo}"
    print(f"PAUSED_DAILY: Pool exhausted until {res_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} / "
          f"{reset_prov_dt.strftime('%Y-%m-%d %H:%M:%S America/Los_Angeles')} / "
          f"{reset_karachi_dt.strftime('%Y-%m-%d %H:%M:%S Asia/Karachi')}")
    print(f"To resume: {resume_cmd}")


def _print_paused_busy(ctx: RunContext) -> None:
    resume_cmd = f".venv/bin/python -m tools.outsourcing.relay --wo {ctx.options.wo}"
    print(f"PAUSED_BUSY: Service busy after retries.")
    print(f"To resume: {resume_cmd}")


def _save_raw_records(
    attempt_dir: Path,
    req_obj: Request,
    model_name: str,
    raw_response: str,
    check_results: CheckResults | None = None,
) -> None:
    attempt_dir.mkdir(parents=True, exist_ok=True)

    (attempt_dir / "request.json").write_text(
        json.dumps(
            {
                "model": model_name,
                "sent_paths": list(req_obj.sent_paths),
                "missing_paths": list(req_obj.missing_paths),
                "characters": req_obj.characters,
                "system": req_obj.chat.system,
                "turns": [{"role": t.role, "text": t.text} for t in req_obj.chat.turns],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (attempt_dir / "response.raw").write_text(raw_response, encoding="utf-8")

    if check_results:
        checks_data = [
            {
                "name": cr.name,
                "passed": cr.passed,
                "summary": cr.summary,
                "log_path": str(cr.log_path),
                "output_paths": list(cr.output_paths),
                "integrity": cr.integrity,
            }
            for cr in check_results.results
        ]
        (attempt_dir / "checks.json").write_text(json.dumps(checks_data, indent=2), encoding="utf-8")


def run_part(ctx: RunContext, part: StepPart) -> StepOutcome:
    step_dir = ctx.log_root / f"step-{part.label}"

    while True:
        try:
            req_obj = prompt.step_request(ctx.order, ctx.plan, part, ctx.worktree.path)
        except prompt.SecretInRequest:
            return StepOutcome(result=Result.SECRET, stop_reason="Secret found in request")

        try:
            model_spec = ctx.router.choose(ctx.order, req_obj.characters, exclude=ctx.run_exclusions)
        except PoolExhausted as exc:
            now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
            ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_DAILY", exc.earliest_reset)
            _print_paused_daily(ctx, exc.earliest_reset)
            return StepOutcome(result=Result.PAUSED_DAILY, stop_reason="Pool exhausted")
        except NoEligibleModel as exc:
            if "Size alone" in exc.reason:
                return StepOutcome(result=Result.TOO_LARGE, stop_reason=exc.reason)
            return StepOutcome(result=Result.INVALID, stop_reason=exc.reason)

        outcome = _attempt_part_loop(ctx, part, req_obj, model_spec, step_dir)
        if outcome is not None:
            return outcome


def _attempt_part_loop(
    ctx: RunContext,
    part: StepPart,
    req_obj: Request,
    model_spec: Any,
    step_dir: Path,
) -> StepOutcome | None:
    client = client_for(model_spec, ctx.governor, ctx.options.timeout, ctx.options.api_base)
    current_req = req_obj
    attempts_used = 0
    max_attempts = ctx.options.attempts
    allowed_paths: tuple[str, ...] = part.paths
    py_path = sys.executable

    while attempts_used < max_attempts:
        attempts_used += 1
        attempt_dir = step_dir / f"attempt-{attempts_used}"

        try:
            reply = client.generate(current_req.chat)
        except DailyQuotaExhausted as exc:
            ctx.run_exclusions.add(model_spec.name)
            now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
            try:
                next_spec = ctx.router.choose(ctx.order, current_req.characters, exclude=ctx.run_exclusions)
                ctx.step_log = ctx.step_log.record_switch(
                    now_dt, part.label, model_spec.name, next_spec.name, "DAILY_QUOTA"
                )
                return None
            except PoolExhausted as p_exc:
                ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_DAILY", p_exc.earliest_reset)
                _print_paused_daily(ctx, p_exc.earliest_reset)
                return StepOutcome(result=Result.PAUSED_DAILY, stop_reason="Daily quota exhausted")
            except NoEligibleModel:
                ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_DAILY", exc.reset_utc)
                _print_paused_daily(ctx, exc.reset_utc)
                return StepOutcome(result=Result.PAUSED_DAILY, stop_reason="Daily quota exhausted")

        except ServiceBusy:
            alt_models = [
                m
                for m in ctx.router.pool.candidates(ctx.order.risk_tier)
                if m.provider.name != model_spec.provider.name and m.name not in ctx.run_exclusions
            ]
            if alt_models:
                ctx.run_exclusions.add(model_spec.name)
                next_spec = alt_models[0]
                now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
                ctx.step_log = ctx.step_log.record_switch(
                    now_dt, part.label, model_spec.name, next_spec.name, "SERVICE_BUSY"
                )
                return None

            success = False
            for delay in (300.0, 600.0):
                ctx.sleeper(delay)
                try:
                    reply = client.generate(current_req.chat)
                    success = True
                    break
                except ServiceBusy:
                    continue
            if not success:
                now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
                ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_BUSY")
                _print_paused_busy(ctx)
                return StepOutcome(result=Result.PAUSED_BUSY, stop_reason="Service busy after wait")

        except ModelError as exc:
            print(f"POOL: remove or rename {model_spec.name}")
            ctx.run_exclusions.add(model_spec.name)
            try:
                next_spec = ctx.router.choose(ctx.order, current_req.characters, exclude=ctx.run_exclusions)
                now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
                ctx.step_log = ctx.step_log.record_switch(
                    now_dt, part.label, model_spec.name, next_spec.name, "MODEL_ERROR"
                )
                return None
            except (PoolExhausted, NoEligibleModel):
                return StepOutcome(result=Result.INVALID, stop_reason=str(exc))

        except CredentialError as exc:
            print(f"ACCESS: add or fix the {model_spec.provider.name} credential on the aqis-lab environment")
            for m in ctx.router.pool.models().values():
                if m.provider.name == model_spec.provider.name:
                    ctx.run_exclusions.add(m.name)
            try:
                next_spec = ctx.router.choose(ctx.order, current_req.characters, exclude=ctx.run_exclusions)
                now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
                ctx.step_log = ctx.step_log.record_switch(
                    now_dt, part.label, model_spec.name, next_spec.name, "CREDENTIAL_ERROR"
                )
                return None
            except (PoolExhausted, NoEligibleModel):
                return StepOutcome(result=Result.CREDENTIAL, stop_reason=str(exc))

        except StepTooLarge as exc:
            ctx.run_exclusions.add(model_spec.name)
            try:
                next_spec = ctx.router.choose(ctx.order, current_req.characters, exclude=ctx.run_exclusions)
                now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
                ctx.step_log = ctx.step_log.record_switch(
                    now_dt, part.label, model_spec.name, next_spec.name, "STEP_TOO_LARGE"
                )
                return None
            except (PoolExhausted, NoEligibleModel):
                return StepOutcome(
                    result=Result.TOO_LARGE,
                    stop_reason=f"split this step, or move context files that are only called into interfaces: {exc}",
                )

        except (ApiError, TransportError) as exc:
            return StepOutcome(result=Result.NETWORK, stop_reason=str(exc))

        _save_raw_records(attempt_dir, current_req, model_spec.name, reply.raw_json or reply.text)

        if reply.finish in ("MAX_TOKENS", "SAFETY", "RECITATION") or not reply.text.strip():
            if len(part.paths) >= 2:
                sub_parts = [StepPart(label=f"{part.label}.{idx}", paths=(p,)) for idx, p in enumerate(part.paths, start=1)]
                for sp in sub_parts:
                    sub_out = run_part(ctx, sp)
                    if sub_out.result != Result.ACCEPTED:
                        return sub_out
                return StepOutcome(result=Result.ACCEPTED)
            elif attempts_used == max_attempts:
                return StepOutcome(result=Result.CUT_OFF, stop_reason="output cut off: split this file's work")
            else:
                fix_text = fixorder.build_fix_order(
                    ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=reply.finish
                )
                curr_files = _read_current_files(ctx.worktree.path, part.paths)
                current_req = prompt.with_fix_turn(current_req, reply.text, fix_text, curr_files)
                continue

        try:
            b_obj = bundle.parse_bundle(reply.text)
        except bundle.BundleError as exc:
            if attempts_used == max_attempts:
                return StepOutcome(result=Result.EXHAUSTED, stop_reason=f"Bundle error: {exc}")
            fix_text = fixorder.build_fix_order(
                ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=f"Bundle error: {exc}"
            )
            curr_files = _read_current_files(ctx.worktree.path, part.paths)
            current_req = prompt.with_fix_turn(current_req, reply.text, fix_text, curr_files)
            continue

        if b_obj.questions:
            now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
            ctx.step_log = ctx.step_log.record_stop(now_dt, "QUESTIONS")
            return StepOutcome(
                result=Result.QUESTIONS, stop_reason="\n".join(b_obj.questions)
            )

        mode = "first" if attempts_used == 1 else "fix"
        expected = set(part.paths) if mode == "first" else set(allowed_paths)

        try:
            imp_rep = importer.import_bundle(b_obj, ctx.order, ctx.worktree.path, mode=mode, expected=expected)
            written = tuple(f.path for f in imp_rep.files)
        except importer.ImportRefused as exc:
            if attempts_used == max_attempts:
                return StepOutcome(result=Result.EXHAUSTED, stop_reason=f"Import refused: {exc}")
            fix_text = fixorder.build_fix_order(
                ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=f"Import refused: {exc}"
            )
            curr_files = _read_current_files(ctx.worktree.path, part.paths)
            current_req = prompt.with_fix_turn(current_req, reply.text, fix_text, curr_files)
            continue

        chk_res = checks.quick_checks(
            ctx.order,
            part,
            ctx.worktree.path,
            attempt_dir,
            ctx.worktree.base_commit,
            py_path,
            ctx.options.verify_timeout,
        )

        _save_raw_records(
            attempt_dir,
            current_req,
            model_spec.name,
            reply.raw_json or reply.text,
            chk_res,
        )

        if chk_res.integrity_failed:
            return StepOutcome(result=Result.INTEGRITY, stop_reason="Quick checks integrity failed")

        if chk_res.passed:
            file_hashes = tuple(
                (p, _hash_file(ctx.worktree.path / p)) for p in part.paths
            )
            rec = StepRecord(
                label=part.label,
                files=file_hashes,
                attempts=attempts_used,
                model=model_spec.name,
                provider=model_spec.provider.name,
                model_version=reply.model_version,
                prompt_tokens=reply.prompt_tokens,
                output_tokens=reply.output_tokens,
                seconds_waited=reply.seconds_waited,
            )
            return StepOutcome(result=Result.ACCEPTED, step_record=rec)

        if attempts_used == max_attempts:
            return StepOutcome(
                result=Result.EXHAUSTED,
                stop_reason="Quick checks failed on final attempt",
            )

        failing_logs = [cr.output_paths for cr in chk_res.results if not cr.passed]
        extra_paths = set(p for paths in failing_logs for p in paths if p in ctx.order.outputs)
        allowed_paths = tuple(sorted(set(part.paths) | extra_paths))

        fix_text = fixorder.build_fix_order(ctx.order, chk_res, attempts_used, allowed_paths, part.label)
        curr_files = _read_current_files(ctx.worktree.path, allowed_paths)
        current_req = prompt.with_fix_turn(current_req, reply.text, fix_text, curr_files)

    return StepOutcome(result=Result.EXHAUSTED, stop_reason="Exhausted attempt budget")


def run_final(ctx: RunContext) -> StepOutcome:
    final_dir = ctx.log_root / "final"
    attempts_used = 0
    max_attempts = ctx.options.attempts
    py_path = sys.executable

    while attempts_used < max_attempts:
        attempts_used += 1
        attempt_dir = final_dir / f"attempt-{attempts_used}"

        chk_res = checks.full_checks(
            ctx.order,
            ctx.worktree.path,
            attempt_dir,
            ctx.worktree.base_commit,
            py_path,
            ctx.options.verify_timeout,
        )

        if chk_res.integrity_failed:
            return StepOutcome(
                result=Result.INTEGRITY, stop_reason="Full checks integrity failed"
            )

        if chk_res.passed:
            return StepOutcome(result=Result.ACCEPTED)

        if attempts_used == max_attempts:
            failing = [
                f"{r.name}: {r.summary}" for r in chk_res.results if not r.passed
            ]
            return StepOutcome(
                result=Result.EXHAUSTED, stop_reason="; ".join(failing)
            )

        failing_paths = tuple(sorted(set(p for cr in chk_res.results if not cr.passed for p in cr.output_paths if p in ctx.order.outputs)))
        focus_paths = failing_paths or ctx.order.outputs

        fix_text = fixorder.build_fix_order(
            ctx.order, chk_res, attempts_used, ctx.order.outputs, "final"
        )

        try:
            req_obj = prompt.final_fix_request(
                ctx.order, ctx.plan, ctx.worktree.path, fix_text, focus_paths=focus_paths
            )
            model_spec = ctx.router.choose(
                ctx.order, req_obj.characters, exclude=ctx.run_exclusions
            )
            client = client_for(
                model_spec,
                ctx.governor,
                ctx.options.timeout,
                ctx.options.api_base,
            )
            reply = client.generate(req_obj.chat)
        except (
            PoolExhausted,
            NoEligibleModel,
            DailyQuotaExhausted,
            ServiceBusy,
            ModelError,
            CredentialError,
            StepTooLarge,
            ApiError,
            TransportError,
        ) as exc:
            return StepOutcome(result=Result.EXHAUSTED, stop_reason=str(exc))

        _save_raw_records(
            attempt_dir,
            req_obj,
            model_spec.name,
            reply.raw_json or reply.text,
            chk_res,
        )

        try:
            b_obj = bundle.parse_bundle(reply.text)
            imp_rep = importer.import_bundle(
                b_obj,
                ctx.order,
                ctx.worktree.path,
                mode="fix",
                expected=set(ctx.order.outputs),
            )
            written = tuple(f.path for f in imp_rep.files)
        except (bundle.BundleError, importer.ImportRefused) as exc:
            continue

        if written:
            rel_written = tuple(set(written))
            from tools.outsourcing.worktree import commit, push
            commit(ctx.worktree, rel_written, f"{ctx.order.wp} {ctx.order.id} final fix {attempts_used} (relay, {model_spec.name})")
            if not ctx.options.no_push:
                push(ctx.worktree)

    return StepOutcome(
        result=Result.EXHAUSTED, stop_reason="Final fix attempts exhausted"
    )
