"""Relay orchestration command line interface and execution loop.

CAPABILITIES:
  CAP-OUTSOURCING-RELAY: Main entry point for running relay work orders, dry-runs, status checks, and model checks. [tests: test_relay.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Command line flags/options in; executes relay run, outputs status/reports and returns exit code.
CONTRACTS: none.
INVARIANTS:
  - Concise stdout report (<= 25 lines).
  - Main checkout must be on branch 'claude/wp-...'.
NOT IN SCOPE:
  - Low-level network transport.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
  2026-10-10 WO-1.0-11 FIX 1: reports on every finish, sha256 order hashing, correct governor state file and model listing error codes.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): the report's checks table, requests and retries come from the
    checks and governor of this run (they were derived from the result, which reported checks that never ran).
  2026-10-12 WP-1.0 FR-1.0-02 fix (Claude, FIX-B17-ledger-row): the ledger fragment gets the run's facts.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.outsourcing import (
    chat, checks, governor, ledger, limits, pack, prompt, records, report, router, steplog, stepper, workorder, worktree,
)
from tools.outsourcing.chat import CredentialError
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import load_pool, next_reset
from tools.outsourcing.records import RelayOptions, RelayOutcome, Result, StepOutcome
from tools.outsourcing.report import checks_table, render_report, request_facts
from tools.outsourcing.router import Router, client_for, model_stats
from tools.outsourcing.steplog import parse, render
from tools.outsourcing.stepper import RunContext, run_final, run_part
from tools.outsourcing.workorder import load_work_order, plan_steps
from tools.outsourcing.worktree import WorktreeError, commit, open_worktree, push, read_step_log, remove

__all__ = ["run", "main"]


def _get_repo_root() -> Path:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(proc.stdout.strip())


class _FileLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._fd: Any = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = open(self.lock_path, "a+")
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def release(self) -> None:
        if self._fd:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                self._fd.close()
            except (OSError, IOError):
                self._fd = None
            self._fd = None


def _parse_args(argv: list[str]) -> RelayOptions:
    p = argparse.ArgumentParser(description="Relay CLI")
    p.add_argument("--wo", type=str, default="")
    p.add_argument("--attempts", type=int, default=0)
    p.add_argument("--api-base", type=str, default="")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--verify-timeout", type=int, default=600)
    p.add_argument("--pool", type=str, default="config/aqis_lab/model_pool.json")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--models", action="store_true")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--pack-step", type=str, default=None)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--no-push", action="store_true")
    args, _ = p.parse_known_args(argv)
    return RelayOptions(
        wo=args.wo, attempts=args.attempts, api_base=args.api_base, timeout=args.timeout,
        verify_timeout=args.verify_timeout, pool=args.pool, dry_run=args.dry_run, status=args.status,
        models=("models",) if args.models else (), restart=args.restart, pack_step=args.pack_step,
        out=args.out, no_push=args.no_push,
    )


def _handle_status_mode(pool_path: Path, main_root: Path) -> RelayOutcome:
    pool = load_pool(pool_path)
    gov = Governor(pool, main_root / ".relay" / "governor.json", time.time, lambda s: None)
    rep = gov.report()
    stats = model_stats(main_root)
    print("=== Model Pool & Governor Status ===")
    for m_name, m_spec in pool.models().items():
        m_rep = rep.models[m_name]
        st = stats.models.get(m_name)
        fp_rate = f"{st.first_pass_rate * 100:.1f}%" if st and st.parts > 0 else "N/A"
        ex_until = m_rep.exhausted_until.isoformat() if m_rep.exhausted_until else "None"
        print(f"Model: {m_name} ({m_spec.provider.name}, rank {m_spec.rank}) | Tiers: {','.join(m_spec.risk_tiers)}")
        print(f"  Count today: {m_rep.count_today}/{m_rep.daily_limit or 'inf'} | First-pass: {fp_rate} | Exhausted until: {ex_until}")
    res = next_reset(pool, "UTC", time.time())
    print(f"\nNext day reset (UTC): {res.reset_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Next day reset (America/Los_Angeles): {res.reset_provider.strftime('%Y-%m-%d %H:%M:%S America/Los_Angeles')}")
    print(f"Next day reset (Asia/Karachi): {res.reset_karachi.strftime('%Y-%m-%d %H:%M:%S Asia/Karachi')}")
    return RelayOutcome(result=Result.ACCEPTED)


def _check_provider_models(pool: Any, gov: Governor, p_name: str, p_spec: Any, api_base: str) -> tuple[RelayOutcome | None, list[str]]:
    listing_spec = next((m for m in pool.models().values() if m.provider.name == p_name), None)
    if not listing_spec:
        return None, []
    client = client_for(listing_spec, gov, timeout=30.0, base_url_override=api_base)
    try:
        available = client.list_models()
    except CredentialError as exc:
        print(f"ACCESS: add or fix the {p_name} credential on the aqis-lab environment")
        return RelayOutcome(result=Result.CREDENTIAL, stop_reason=str(exc)), []
    except (chat.ApiError, chat.TransportError, chat.ServiceBusy) as exc:
        return RelayOutcome(result=Result.NETWORK, stop_reason=str(exc)), []
    avail_set = set(available)
    missing = [m_name for m_name, m_spec in pool.models().items() if m_spec.provider.name == p_name and not (
        m_spec.name in avail_set or m_spec.name.split("/")[-1] in avail_set or f"models/{m_spec.name}" in avail_set or f"models/{m_spec.name.split('/')[-1]}" in avail_set
    )]
    for m_name, m_spec in pool.models().items():
        if m_spec.provider.name == p_name and m_name not in missing:
            print(f"{m_name}: present")
    return None, missing


def _handle_models_mode(pool_path: Path, main_root: Path, api_base: str) -> RelayOutcome:
    pool = load_pool(pool_path)
    gov = Governor(pool, main_root / ".relay" / "governor.json", time.time, lambda s: None)
    all_missing = []
    for p_name, p_spec in pool.providers().items():
        if not p_spec.enabled:
            continue
        err_outcome, missing = _check_provider_models(pool, gov, p_name, p_spec, api_base)
        if err_outcome is not None:
            return err_outcome
        for m_name in missing:
            print(f"{m_name}: missing")
            all_missing.append(m_name)
    return RelayOutcome(result=Result.INVALID if all_missing else Result.ACCEPTED)


def _handle_dry_run_mode(opts: RelayOptions, main_root: Path) -> RelayOutcome:
    wo_path = Path(opts.wo) if Path(opts.wo).is_absolute() else main_root / opts.wo
    order = load_work_order(wo_path, main_root)
    plan = plan_steps(order)
    pool = load_pool(Path(opts.pool) if Path(opts.pool).is_absolute() else main_root / opts.pool)
    gov = Governor(pool, main_root / ".relay" / "governor.json", time.time, lambda s: None)
    router = Router(pool, gov, model_stats(main_root))

    print(f"=== Dry Run: {order.id} ({order.risk_tier}) ===")
    for step_obj in plan:
        step_part = records.StepPart(label=str(step_obj.number), paths=step_obj.paths)
        req = prompt.step_request(order, plan, step_part, main_root)
        est_tokens = math.ceil(req.characters / 3.5)
        m_spec = router.choose(order, est_tokens)
        print(f"Step {step_obj.number} ({','.join(step_obj.paths)}): ~{est_tokens} tokens -> {m_spec.name}")

    return RelayOutcome(result=Result.ACCEPTED)


def _handle_pack_mode(opts: RelayOptions, main_root: Path) -> RelayOutcome:
    wo_path = Path(opts.wo) if Path(opts.wo).is_absolute() else main_root / opts.wo
    order = load_work_order(wo_path, main_root)
    plan = plan_steps(order)
    step_num = int(opts.pack_step)
    target_step = next(s for s in plan if s.number == step_num)
    step_part = records.StepPart(label=str(step_num), paths=target_step.paths)
    text = prompt.step_pack(order, plan, step_part, main_root)

    out_p = Path(opts.out) if opts.out else main_root / f"pack_step_{opts.pack_step}.txt"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(text, encoding="utf-8")
    return RelayOutcome(result=Result.ACCEPTED)


def _write_records(
    run_ctx: RunContext, outcome: RelayOutcome, accepted_records: list[records.StepRecord]
) -> tuple[str, bool]:
    sum_rel = f"docs/outsourcing/returns/{run_ctx.order.id}/summary.md"
    sum_path = run_ctx.worktree.path / sum_rel
    led_rel = f"docs/outsourcing/ledger.d/{run_ctx.order.id}.md"
    step_rel = f"docs/outsourcing/returns/{run_ctx.order.id}/steps.md"

    ledger.write_summary(sum_path, outcome)
    models_used = tuple(run_ctx.all_models_used) or tuple((a.model, a.provider) for a in accepted_records)
    ledger.write_ledger_fragment(
        run_ctx.worktree.path / led_rel, run_ctx.order.id, outcome, run_ctx.total_requests, run_ctx.total_prompt_tokens,
        run_ctx.total_output_tokens, models_used, **ledger.run_facts(accepted_records, run_ctx.step_log, run_ctx.clock()),
    )

    push_ok = True
    if outcome.result != Result.INTEGRITY:
        log_path = run_ctx.worktree.path / step_rel
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(render(run_ctx.step_log), encoding="utf-8")
        commit(run_ctx.worktree, (sum_rel, led_rel, step_rel), f"{run_ctx.order.wp} {run_ctx.order.id} records ({outcome.result.name})")
        if not run_ctx.options.no_push:
            try:
                push(run_ctx.worktree)
            except WorktreeError:
                push_ok = False

    return sum_rel, push_ok


def _finalize_and_report(
    run_ctx: RunContext, outcome: StepOutcome | RelayOutcome, accepted_records: list[records.StepRecord]
) -> RelayOutcome:
    res = outcome.result if hasattr(outcome, "result") else outcome
    stop_r = getattr(outcome, "stop_reason", None)
    relay_outcome = RelayOutcome(result=res, accepted_parts=tuple(accepted_records), stop_reason=stop_r)

    sum_rel, push_ok = _write_records(run_ctx, relay_outcome, accepted_records)
    eff_res = Result.GIT if not push_ok else relay_outcome.result
    eff_outcome = RelayOutcome(result=eff_res, accepted_parts=relay_outcome.accepted_parts, stop_reason=relay_outcome.stop_reason)

    facts = {
        "summary_path": sum_rel, "wo_id": run_ctx.order.id, "wo_path": run_ctx.options.wo,
        "total_parts": len(run_ctx.plan), "parts_done": len(accepted_records),
        "prompt_tokens": run_ctx.total_prompt_tokens, "output_tokens": run_ctx.total_output_tokens,
        "checks_table": checks_table(run_ctx.last_checks),
        "stop_reason": eff_outcome.stop_reason,
        **request_facts(run_ctx.governor),
    }
    if not push_ok:
        facts["pool_lines"] = ("Push failed: commit is local only",)

    rep_lines = render_report(eff_outcome, facts)
    for line in rep_lines:
        print(line)
    return eff_outcome


def _execute_run_loop(run_ctx: RunContext, accepted_records: list[records.StepRecord]) -> RelayOutcome:
    log_path = run_ctx.worktree.path / "docs" / "outsourcing" / "returns" / run_ctx.order.id / "steps.md"

    while True:
        next_p = run_ctx.step_log.next_part(run_ctx.plan)
        if next_p is None:
            break

        part_outcome = run_part(run_ctx, next_p)
        if part_outcome.result != Result.ACCEPTED:
            return _finalize_and_report(run_ctx, part_outcome, accepted_records)

        if part_outcome.step_record:
            accepted_records.append(part_outcome.step_record)
            run_ctx.step_log = run_ctx.step_log.record_accepted(part_outcome.step_record)

        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(render(run_ctx.step_log), encoding="utf-8")

        rel_paths = [f[0] for f in part_outcome.step_record.files] if part_outcome.step_record else []
        step_rel_log = f"docs/outsourcing/returns/{run_ctx.order.id}/steps.md"
        commit(
            run_ctx.worktree, tuple(set(rel_paths + [step_rel_log])),
            f"{run_ctx.order.wp} {run_ctx.order.id} step {next_p.label}: {', '.join(rel_paths)} (relay, {part_outcome.step_record.model if part_outcome.step_record else 'model'})"
        )
        if not run_ctx.options.no_push:
            push(run_ctx.worktree)

    final_outcome = run_final(run_ctx)
    ret_outcome = _finalize_and_report(run_ctx, final_outcome, accepted_records)
    if ret_outcome.result == Result.ACCEPTED:
        remove(run_ctx.worktree)
    return ret_outcome


def _check_branch_and_lock(order: Any, main_root: Path) -> tuple[str, _FileLock]:
    proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=main_root, capture_output=True, text=True)
    curr_branch = proc.stdout.strip()
    if not curr_branch.startswith("claude/wp-"):
        msg = f"Main checkout on invalid branch {curr_branch!r}"
        print(msg)
        raise workorder.WorkOrderError(msg)

    lock = _FileLock(main_root / ".relay" / "locks" / f"{order.id}.lock")
    if not lock.acquire():
        msg = f"another relay is running this order ({order.id})"
        print(msg)
        raise WorktreeError(msg)
    return curr_branch, lock


def _setup_run_context(
    order: Any, options: RelayOptions, main_root: Path, wo_path: Path, curr_branch: str, pool: Any
) -> RunContext:
    wt = open_worktree(main_root, order.id, curr_branch)
    wo_wt = wt.path / options.wo
    wo_sha256 = hashlib.sha256(wo_wt.read_bytes()).hexdigest() if wo_wt.exists() else hashlib.sha256(wo_path.read_bytes()).hexdigest()

    gov = Governor(pool, main_root / ".relay" / "governor.json", time.time, time.sleep)
    router_obj = Router(pool, gov, model_stats(main_root))

    log_path = wt.path / "docs" / "outsourcing" / "returns" / order.id / "steps.md"
    s_log = steplog.StepLog() if (options.restart or not log_path.exists()) else parse(log_path.read_text(encoding="utf-8"))
    s_log = s_log.record_run_start(datetime.fromtimestamp(time.time(), tz=timezone.utc), wo_sha256, curr_branch, order.model)

    eff_opts = RelayOptions(
        wo=options.wo, attempts=options.attempts if options.attempts > 0 else order.attempt_budget,
        api_base=options.api_base, timeout=options.timeout, verify_timeout=options.verify_timeout,
        pool=options.pool, dry_run=options.dry_run, status=options.status, models=options.models,
        restart=options.restart, pack_step=options.pack_step, out=options.out, no_push=options.no_push,
    )
    return RunContext(
        order=order, plan=plan_steps(order), worktree=wt, router=router_obj, governor=gov,
        step_log=s_log, options=eff_opts, clock=time.time, sleeper=time.sleep,
        log_root=main_root / ".relay" / "logs" / order.id, main_root=main_root,
    )


def _init_run_context(options: RelayOptions, main_root: Path, wo_path: Path) -> tuple[RunContext | None, RelayOutcome | None, _FileLock]:
    order = load_work_order(wo_path, main_root)
    if order.channel != "api":
        msg = f"Channel {order.channel!r} not supported"
        print(msg)
        return None, RelayOutcome(result=Result.INVALID, stop_reason=msg), _FileLock(main_root / ".relay" / "locks" / f"{order.id}.lock")

    pool = load_pool(Path(options.pool) if Path(options.pool).is_absolute() else main_root / options.pool)
    curr_branch, lock = _check_branch_and_lock(order, main_root)

    try:
        existing_log = read_step_log(main_root, order.id)
        if existing_log and parse(existing_log).wp_branch and parse(existing_log).wp_branch != curr_branch:
            msg = f"Step log records WP branch {parse(existing_log).wp_branch!r}, but main checkout is on {curr_branch!r}"
            print(msg)
            lock.release()
            return None, RelayOutcome(result=Result.INVALID, stop_reason=msg), lock

        run_ctx = _setup_run_context(order, options, main_root, wo_path, curr_branch, pool)
        return run_ctx, None, lock
    except (workorder.WorkOrderError, limits.LimitsError, WorktreeError):
        lock.release()
        raise


def run(options: RelayOptions) -> RelayOutcome:
    main_root = _get_repo_root()
    pool_p = Path(options.pool) if Path(options.pool).is_absolute() else main_root / options.pool

    if options.status:
        return _handle_status_mode(pool_p, main_root)
    if options.models:
        return _handle_models_mode(pool_p, main_root, options.api_base)
    if options.dry_run:
        return _handle_dry_run_mode(options, main_root)
    if options.pack_step is not None:
        return _handle_pack_mode(options, main_root)

    wo_path = Path(options.wo) if Path(options.wo).is_absolute() else main_root / options.wo
    run_ctx, early_outcome, lock = _init_run_context(options, main_root, wo_path)
    if early_outcome is not None:
        return early_outcome
    try:
        assert run_ctx is not None
        return _execute_run_loop(run_ctx, list(run_ctx.step_log.accepted))
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    opts = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        outcome = run(opts)
        return outcome.result.exit_code
    except (workorder.WorkOrderError, limits.LimitsError, router.NoEligibleModel) as exc:
        print(f"Relay error: {exc}", file=sys.stderr)
        return Result.INVALID.exit_code
    except WorktreeError as exc:
        print(f"Relay error: {exc}", file=sys.stderr)
        return Result.GIT.exit_code
    except (chat.ApiError, chat.TransportError, chat.ServiceBusy) as exc:
        print(f"Relay error: {exc}", file=sys.stderr)
        return Result.NETWORK.exit_code


if __name__ == "__main__":
    sys.exit(main())
