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
  2026-10-10 WO-1.0-11 FIX 1: split functions, re-export run_final from stepper_final, and track reply token totals.
"""
from __future__ import annotations

import json
import sys
import zoneinfo
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from tools.outsourcing import bundle, checks, fixorder, importer, prompt, records, steplog, workorder
from tools.outsourcing.chat import (
    ApiError, CredentialError, DailyQuotaExhausted, ModelError, ServiceBusy, StepTooLarge, TransportError,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import _la_offset, _resolve_tz, next_reset
from tools.outsourcing.records import CheckResults, RelayOptions, Request, Result, StepOutcome, StepPart, StepRecord
from tools.outsourcing.router import NoEligibleModel, PoolExhausted, Router, client_for
from tools.outsourcing.steplog import StepLog
from tools.outsourcing.stepper_final import run_final
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
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    all_models_used: list[tuple[str, str]] = field(default_factory=list)

    def record_reply(self, reply: Any, model_name: str, provider_name: str) -> None:
        self.total_requests += 1
        self.total_prompt_tokens += getattr(reply, "prompt_tokens", 0) or 0
        self.total_output_tokens += getattr(reply, "output_tokens", 0) or 0
        pair = (model_name, provider_name)
        if pair not in self.all_models_used:
            self.all_models_used.append(pair)


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
    reset_prov_dt = res_dt.astimezone(timezone(_la_offset(res_dt))) if prov_tz is None else res_dt.astimezone(prov_tz)
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


def _save_raw_records(
    attempt_dir: Path, req_obj: Request, model_name: str, raw_response: str, check_results: CheckResults | None = None,
) -> None:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "request.json").write_text(
        json.dumps(
            {
                "model": model_name, "sent_paths": list(req_obj.sent_paths), "missing_paths": list(req_obj.missing_paths),
                "characters": req_obj.characters, "system": req_obj.chat.system,
                "turns": [{"role": t.role, "text": t.text} for t in req_obj.chat.turns],
            }, indent=2,
        ), encoding="utf-8",
    )
    (attempt_dir / "response.raw").write_text(raw_response, encoding="utf-8")
    if check_results:
        checks_data = [
            {"name": cr.name, "passed": cr.passed, "summary": cr.summary, "log_path": str(cr.log_path),
             "output_paths": list(cr.output_paths), "integrity": cr.integrity}
            for cr in check_results.results
        ]
        (attempt_dir / "checks.json").write_text(json.dumps(checks_data, indent=2), encoding="utf-8")


def _switch_model_or_stop(ctx: RunContext, part: StepPart, model_spec: Any, req_obj: Request, reason_code: str, fallback_res: Result, fallback_reason: str) -> StepOutcome | None:
    ctx.run_exclusions.add(model_spec.name)
    now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
    try:
        next_spec = ctx.router.choose(ctx.order, req_obj.characters, exclude=ctx.run_exclusions)
        ctx.step_log = ctx.step_log.record_switch(now_dt, part.label, model_spec.name, next_spec.name, reason_code)
        return None
    except (PoolExhausted, NoEligibleModel) as exc:
        if fallback_res == Result.PAUSED_DAILY:
            reset_dt = exc.earliest_reset if isinstance(exc, PoolExhausted) else None
            ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_DAILY", reset_dt)
            _print_paused_daily(ctx, reset_dt)
        return StepOutcome(result=fallback_res, stop_reason=fallback_reason)


def _handle_service_busy(ctx: RunContext, part: StepPart, model_spec: Any, client: Any, req_obj: Request) -> tuple[StepOutcome | None, Any]:
    alt = [m for m in ctx.router.pool.candidates(ctx.order.risk_tier) if m.provider.name != model_spec.provider.name and m.name not in ctx.run_exclusions]
    if alt:
        return _switch_model_or_stop(ctx, part, model_spec, req_obj, "SERVICE_BUSY", Result.PAUSED_BUSY, "Service busy"), None
    last_exc = None
    for delay in (300.0, 600.0):
        ctx.sleeper(delay)
        try:
            reply = client.generate(req_obj.chat)
            ctx.record_reply(reply, model_spec.name, model_spec.provider.name)
            return StepOutcome(result=Result.ACCEPTED), reply
        except ServiceBusy as exc:
            last_exc = exc
    now_dt = datetime.fromtimestamp(ctx.clock(), tz=timezone.utc)
    ctx.step_log = ctx.step_log.record_stop(now_dt, "PAUSED_BUSY")
    print(f"PAUSED_BUSY: Service busy after retries.\nTo resume: .venv/bin/python -m tools.outsourcing.relay --wo {ctx.options.wo}")
    return StepOutcome(result=Result.PAUSED_BUSY, stop_reason=f"Service busy: {last_exc}"), None


def _generate_or_switch(ctx: RunContext, part: StepPart, model_spec: Any, client: Any, req_obj: Request) -> tuple[StepOutcome | None, Any]:
    try:
        reply = client.generate(req_obj.chat)
        ctx.record_reply(reply, model_spec.name, model_spec.provider.name)
        return None, reply
    except DailyQuotaExhausted:
        return _switch_model_or_stop(ctx, part, model_spec, req_obj, "DAILY_QUOTA", Result.PAUSED_DAILY, "Daily quota exhausted"), None
    except ServiceBusy:
        return _handle_service_busy(ctx, part, model_spec, client, req_obj)
    except ModelError as exc:
        print(f"POOL: remove or rename {model_spec.name}")
        return _switch_model_or_stop(ctx, part, model_spec, req_obj, "MODEL_ERROR", Result.INVALID, str(exc)), None
    except CredentialError as exc:
        print(f"ACCESS: add or fix the {model_spec.provider.name} credential on the aqis-lab environment")
        for m in ctx.router.pool.models().values():
            if m.provider.name == model_spec.provider.name:
                ctx.run_exclusions.add(m.name)
        return _switch_model_or_stop(ctx, part, model_spec, req_obj, "CREDENTIAL_ERROR", Result.CREDENTIAL, str(exc)), None
    except StepTooLarge as exc:
        return _switch_model_or_stop(ctx, part, model_spec, req_obj, "STEP_TOO_LARGE", Result.TOO_LARGE, f"split step: {exc}"), None
    except (ApiError, TransportError) as exc:
        return StepOutcome(result=Result.NETWORK, stop_reason=str(exc)), None


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
            res = Result.TOO_LARGE if "Size alone" in exc.reason else Result.INVALID
            return StepOutcome(result=res, stop_reason=exc.reason)
        outcome = _attempt_part_loop(ctx, part, req_obj, model_spec, step_dir)
        if outcome is not None:
            return outcome


def _handle_import_and_checks(
    ctx: RunContext, part: StepPart, model_spec: Any, reply: Any, b_obj: Any,
    attempts_used: int, max_attempts: int, allowed_paths: tuple[str, ...], current_req: Request, attempt_dir: Path
) -> tuple[StepOutcome | None, Request, tuple[str, ...]]:
    mode = "first" if attempts_used == 1 else "fix"
    try:
        importer.import_bundle(b_obj, ctx.order, ctx.worktree.path, mode=mode, expected=set(part.paths if mode == "first" else allowed_paths))
    except importer.ImportRefused as exc:
        if attempts_used == max_attempts:
            return StepOutcome(result=Result.EXHAUSTED, stop_reason=f"Import refused: {exc}"), current_req, allowed_paths
        fix_text = fixorder.build_fix_order(ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=f"Import refused: {exc}")
        return None, prompt.with_fix_turn(current_req, reply.text, fix_text, _read_current_files(ctx.worktree.path, part.paths)), allowed_paths

    chk_res = checks.quick_checks(
        ctx.order, part, ctx.worktree.path, attempt_dir, ctx.worktree.base_commit, sys.executable, ctx.options.verify_timeout,
    )
    _save_raw_records(attempt_dir, current_req, model_spec.name, reply.raw_json or reply.text, chk_res)
    if chk_res.integrity_failed:
        return StepOutcome(result=Result.INTEGRITY, stop_reason="Quick checks integrity failed"), current_req, allowed_paths
    if chk_res.passed:
        hashes = tuple((p, _hash_file(ctx.worktree.path / p)) for p in part.paths)
        rec = StepRecord(
            label=part.label, files=hashes, attempts=attempts_used, model=model_spec.name,
            provider=model_spec.provider.name, model_version=reply.model_version,
            prompt_tokens=reply.prompt_tokens, output_tokens=reply.output_tokens, seconds_waited=reply.seconds_waited,
        )
        return StepOutcome(result=Result.ACCEPTED, step_record=rec), current_req, allowed_paths
    if attempts_used == max_attempts:
        return StepOutcome(result=Result.EXHAUSTED, stop_reason="Quick checks failed on final attempt"), current_req, allowed_paths

    extra = set(p for cr in chk_res.results if not cr.passed for p in cr.output_paths if p in ctx.order.outputs)
    new_allowed = tuple(sorted(set(part.paths) | extra))
    fix_text = fixorder.build_fix_order(ctx.order, chk_res, attempts_used, new_allowed, part.label)
    return None, prompt.with_fix_turn(current_req, reply.text, fix_text, _read_current_files(ctx.worktree.path, new_allowed)), new_allowed


def _handle_cutoff_reply(
    ctx: RunContext, part: StepPart, reply: Any, attempts_used: int, max_attempts: int, current_req: Request
) -> tuple[StepOutcome | None, Request]:
    if len(part.paths) >= 2:
        for sp in [StepPart(label=f"{part.label}.{idx}", paths=(p,)) for idx, p in enumerate(part.paths, start=1)]:
            sub_out = run_part(ctx, sp)
            if sub_out.result != Result.ACCEPTED:
                return sub_out, current_req
        return StepOutcome(result=Result.ACCEPTED), current_req
    elif attempts_used == max_attempts:
        return StepOutcome(result=Result.CUT_OFF, stop_reason="output cut off: split this file's work"), current_req
    else:
        fix_text = fixorder.build_fix_order(ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=reply.finish)
        return None, prompt.with_fix_turn(current_req, reply.text, fix_text, _read_current_files(ctx.worktree.path, part.paths))


def _attempt_part_loop(
    ctx: RunContext, part: StepPart, req_obj: Request, model_spec: Any, step_dir: Path,
) -> StepOutcome | None:
    client = client_for(model_spec, ctx.governor, ctx.options.timeout, ctx.options.api_base)
    curr_req, attempts_used, max_attempts, allowed_paths = req_obj, 0, ctx.options.attempts, part.paths
    while attempts_used < max_attempts:
        attempts_used += 1
        att_dir = step_dir / f"attempt-{attempts_used}"
        sw_out, reply = _generate_or_switch(ctx, part, model_spec, client, curr_req)
        if sw_out is not None and sw_out.result != Result.ACCEPTED:
            return sw_out
        if reply is None:
            return None
        _save_raw_records(att_dir, curr_req, model_spec.name, reply.raw_json or reply.text)
        if reply.finish in ("MAX_TOKENS", "SAFETY", "RECITATION") or not reply.text.strip():
            cutoff_res, curr_req = _handle_cutoff_reply(ctx, part, reply, attempts_used, max_attempts, curr_req)
            if cutoff_res is not None:
                return cutoff_res
            continue
        try:
            b_obj = bundle.parse_bundle(reply.text)
        except bundle.BundleError as exc:
            if attempts_used == max_attempts:
                return StepOutcome(result=Result.EXHAUSTED, stop_reason=f"Bundle error: {exc}")
            fix_text = fixorder.build_fix_order(ctx.order, CheckResults(()), attempts_used, part.paths, part.label, stop_reason=f"Bundle error: {exc}")
            curr_req = prompt.with_fix_turn(curr_req, reply.text, fix_text, _read_current_files(ctx.worktree.path, part.paths))
            continue
        if b_obj.questions:
            ctx.step_log = ctx.step_log.record_stop(datetime.fromtimestamp(ctx.clock(), tz=timezone.utc), "QUESTIONS")
            return StepOutcome(result=Result.QUESTIONS, stop_reason="\n".join(b_obj.questions))
        out_res, curr_req, allowed_paths = _handle_import_and_checks(
            ctx, part, model_spec, reply, b_obj, attempts_used, max_attempts, allowed_paths, curr_req, att_dir
        )
        if out_res is not None:
            return out_res
    return StepOutcome(result=Result.EXHAUSTED, stop_reason="Exhausted attempt budget")
