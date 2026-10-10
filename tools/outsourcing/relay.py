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
"""
from __future__ import annotations

import argparse
import fcntl
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.outsourcing import (
    checks, governor, ledger, limits, pack, prompt, records, steplog, stepper, workorder, worktree,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import load_pool, next_reset
from tools.outsourcing.records import RelayOptions, RelayOutcome, Result, StepOutcome
from tools.outsourcing.router import Router, client_for, model_stats
from tools.outsourcing.steplog import parse, render
from tools.outsourcing.stepper import RunContext, run_final, run_part
from tools.outsourcing.workorder import load_work_order, plan_steps
from tools.outsourcing.worktree import WorktreeError, commit, open_worktree, push, read_step_log, remove

__all__ = ["run", "main"]


def _get_repo_root() -> Path:
    import subprocess
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(proc.stdout.strip())


class _FileLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._fd = None

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
            except OSError:
                pass
            self._fd = None


def _parse_args(argv: list[str]) -> RelayOptions:
    parser = argparse.ArgumentParser(description="Relay Orchestration CLI")
    parser.add_argument("--wo", type=str, default="", help="Path to work order file")
    parser.add_argument("--attempts", type=int, default=0, help="Attempt budget (1-5)")
    parser.add_argument("--api-base", type=str, default="", help="API base URL override")
    parser.add_argument("--timeout", type=int, default=300, help="API call timeout in seconds")
    parser.add_argument("--verify-timeout", type=int, default=600, help="Verify timeout in seconds")
    parser.add_argument("--pool", type=str, default="config/aqis_lab/model_pool.json", help="Pool config path")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run")
    parser.add_argument("--status", action="store_true", help="Show pool/governor status")
    parser.add_argument("--models", action="store_true", help="Check model availability")
    parser.add_argument("--restart", action="store_true", help="Restart step log")
    parser.add_argument("--pack-step", type=str, default=None, help="Pack step K")
    parser.add_argument("--out", type=str, default=None, help="Output path for packed step")
    parser.add_argument("--no-push", action="store_true", help="Disable git push")

    args, unknown = parser.parse_known_args(argv)
    return RelayOptions(
        wo=args.wo,
        attempts=args.attempts,
        api_base=args.api_base,
        timeout=args.timeout,
        verify_timeout=args.verify_timeout,
        pool=args.pool,
        dry_run=args.dry_run,
        status=args.status,
        models=("models",) if args.models else (),
        restart=args.restart,
        pack_step=args.pack_step,
        out=args.out,
        no_push=args.no_push,
    )


def _handle_status_mode(pool_path: Path, main_root: Path) -> RelayOutcome:
    pool = load_pool(pool_path)
    gov = Governor(pool, main_root / ".relay" / "governor_state.json", time.time, lambda s: None)
    rep = gov.report()
    stats = model_stats(main_root)

    print("=== Model Pool & Governor Status ===")
    for m_name, m_spec in pool.models().items():
        m_rep = rep.models[m_name]
        p_spec = m_spec.provider
        st = stats.models.get(m_name)
        fp_rate = f"{st.first_pass_rate * 100:.1f}%" if st and st.parts > 0 else "N/A"
        ex_until = m_rep.exhausted_until.isoformat() if m_rep.exhausted_until else "None"
        print(f"Model: {m_name} ({p_spec.name}, rank {m_spec.rank}) | Tiers: {','.join(m_spec.risk_tiers)}")
        print(f"  Count today: {m_rep.count_today}/{m_rep.daily_limit or 'inf'} | First-pass: {fp_rate} | Exhausted until: {ex_until}")

    print("\n=== Provider Monthly Tokens ===")
    for p_name, p_rep in rep.providers.items():
        p_spec = pool.providers()[p_name]
        is_unv = " (UNVERIFIED)" if p_rep.unverified else ""
        print(f"Provider: {p_name}{is_unv} | Monthly tokens: {p_rep.monthly_tokens}/{p_spec.tokens_per_month or 'inf'}")

    res = next_reset(pool, "UTC", time.time())
    print(f"\nNext day reset (UTC): {res.reset_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Next day reset (America/Los_Angeles): {res.reset_provider.strftime('%Y-%m-%d %H:%M:%S America/Los_Angeles')}")
    print(f"Next day reset (Asia/Karachi): {res.reset_karachi.strftime('%Y-%m-%d %H:%M:%S Asia/Karachi')}")

    return RelayOutcome(result=Result.ACCEPTED)


def _handle_models_mode(pool_path: Path, main_root: Path, api_base: str) -> RelayOutcome:
    pool = load_pool(pool_path)
    gov = Governor(pool, main_root / ".relay" / "governor_state.json", time.time, lambda s: None)
    missing_found = False

    for p_name, p_spec in pool.providers().items():
        if not p_spec.enabled:
            continue
        dummy_spec = next((m for m in pool.models().values() if m.provider.name == p_name), None)
        if not dummy_spec:
            continue
        client = client_for(dummy_spec, gov, timeout=30.0, base_url_override=api_base)
        try:
            available = client.list_models()
        except Exception as exc:
            print(f"Error listing models for provider {p_name}: {exc}")
            available = []

        avail_set = set(available)
        for m_name, m_spec in pool.models().items():
            if m_spec.provider.name == p_name:
                short_name = m_spec.name.split("/")[-1]
                if m_spec.name in avail_set or short_name in avail_set or f"models/{m_spec.name}" in avail_set or f"models/{short_name}" in avail_set:
                    print(f"{m_spec.name}: present")
                else:
                    print(f"{m_spec.name}: missing")
                    missing_found = True

    return RelayOutcome(result=Result.INVALID if missing_found else Result.ACCEPTED)


def _handle_dry_run_mode(opts: RelayOptions, main_root: Path) -> RelayOutcome:
    wo_path = Path(opts.wo)
    if not wo_path.is_absolute():
        wo_path = main_root / wo_path
    order = load_work_order(wo_path, main_root)
    plan = plan_steps(order)
    pool = load_pool(opts.pool if Path(opts.pool).is_absolute() else main_root / opts.pool)
    gov = Governor(pool, main_root / ".relay" / "governor_state.json", time.time, lambda s: None)
    router = Router(pool, gov, model_stats(main_root))

    print(f"=== Dry Run: {order.id} ({order.risk_tier}) ===")
    for step_obj in plan:
        dummy_part = records.StepPart(label=str(step_obj.number), paths=step_obj.paths)
        req = prompt.step_request(order, plan, dummy_part, main_root)
        est_tokens = math.ceil(req.characters / 3.5)
        m_spec = router.choose(order, est_tokens)
        missing_count = len(req.missing_paths)
        print(f"Step {step_obj.number} ({','.join(step_obj.paths)}): ~{est_tokens} tokens, {missing_count} missing outputs -> {m_spec.name}")

    return RelayOutcome(result=Result.ACCEPTED)


def _handle_pack_mode(opts: RelayOptions, main_root: Path) -> RelayOutcome:
    wo_path = Path(opts.wo)
    if not wo_path.is_absolute():
        wo_path = main_root / wo_path
    order = load_work_order(wo_path, main_root)
    plan = plan_steps(order)
    step_num = int(opts.pack_step)
    target_step = next(s for s in plan if s.number == step_num)
    dummy_part = records.StepPart(label=str(step_num), paths=target_step.paths)
    text = prompt.step_pack(order, plan, dummy_part, main_root)

    out_p = Path(opts.out) if opts.out else main_root / f"pack_step_{opts.pack_step}.txt"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(text, encoding="utf-8")
    return RelayOutcome(result=Result.ACCEPTED)


def run(options: RelayOptions) -> RelayOutcome:
    main_root = _get_repo_root()

    if options.status:
        pool_p = Path(options.pool) if Path(options.pool).is_absolute() else main_root / options.pool
        return _handle_status_mode(pool_p, main_root)

    if options.models:
        pool_p = Path(options.pool) if Path(options.pool).is_absolute() else main_root / options.pool
        return _handle_models_mode(pool_p, main_root, options.api_base)

    if options.dry_run:
        return _handle_dry_run_mode(options, main_root)

    if options.pack_step is not None:
        return _handle_pack_mode(options, main_root)

    wo_path = Path(options.wo)
    if not wo_path.is_absolute():
        wo_path = main_root / wo_path

    order = load_work_order(wo_path, main_root)
    if order.channel != "api":
        return RelayOutcome(result=Result.INVALID, stop_reason=f"Channel {order.channel!r} not supported by relay (api only)")

    pool_p = Path(options.pool) if Path(options.pool).is_absolute() else main_root / options.pool
    pool = load_pool(pool_p)

    import subprocess
    curr_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=main_root, capture_output=True, text=True).stdout.strip()
    if not curr_branch.startswith("claude/wp-"):
        msg = f"Main checkout on invalid branch {curr_branch!r} (must start with claude/wp-)"
        print(msg)
        return RelayOutcome(result=Result.INVALID, stop_reason=msg)

    lock = _FileLock(main_root / ".relay" / "locks" / f"{order.id}.lock")
    if not lock.acquire():
        msg = f"another relay is running this order ({order.id})"
        print(msg)
        return RelayOutcome(result=Result.GIT, stop_reason=msg)

    try:
        existing_log_text = read_step_log(main_root, order.id)
        if existing_log_text:
            s_log = parse(existing_log_text)
            if s_log.wp_branch and s_log.wp_branch != curr_branch:
                msg = f"Step log records WP branch {s_log.wp_branch!r}, but main checkout is on {curr_branch!r}"
                print(msg)
                return RelayOutcome(result=Result.INVALID, stop_reason=msg)

        wt = open_worktree(main_root, order.id, curr_branch)

        attempts = options.attempts if options.attempts > 0 else order.attempt_budget
        eff_opts = RelayOptions(
            wo=options.wo, attempts=attempts, api_base=options.api_base, timeout=options.timeout,
            verify_timeout=options.verify_timeout, pool=options.pool, dry_run=options.dry_run,
            status=options.status, models=options.models, restart=options.restart,
            pack_step=options.pack_step, out=options.out, no_push=options.no_push
        )

        gov = Governor(pool, main_root / ".relay" / "governor_state.json", time.time, time.sleep)
        stats = model_stats(main_root)
        router = Router(pool, gov, stats)

        log_path = wt.path / "docs" / "outsourcing" / "returns" / order.id / "steps.md"
        if options.restart or not log_path.exists():
            s_log = steplog.StepLog()
        else:
            s_log = parse(log_path.read_text(encoding="utf-8"))

        now_dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
        s_log = s_log.record_run_start(now_dt, order.sha256 if hasattr(order, "sha256") else "sha", curr_branch, order.model)

        plan = plan_steps(order)
        log_root = main_root / ".relay" / "logs" / order.id

        run_ctx = RunContext(
            order=order, plan=plan, worktree=wt, router=router, governor=gov,
            step_log=s_log, options=eff_opts, clock=time.time, sleeper=time.sleep,
            log_root=log_root, main_root=main_root
        )

        accepted_records: list[records.StepRecord] = list(s_log.accepted)

        while True:
            next_p = run_ctx.step_log.next_part(plan)
            if next_p is None:
                break

            part_outcome = run_part(run_ctx, next_p)
            if part_outcome.result != Result.ACCEPTED:
                _finalize_records(run_ctx, part_outcome.result, accepted_records, part_outcome.stop_reason)
                return RelayOutcome(result=part_outcome.result, accepted_parts=tuple(accepted_records), stop_reason=part_outcome.stop_reason)

            if part_outcome.step_record:
                accepted_records.append(part_outcome.step_record)
                run_ctx.step_log = run_ctx.step_log.record_accepted(part_outcome.step_record)

            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(render(run_ctx.step_log), encoding="utf-8")

            rel_paths = [f[0] for f in part_outcome.step_record.files] if part_outcome.step_record else []
            step_rel_log = f"docs/outsourcing/returns/{order.id}/steps.md"
            commit(wt, tuple(set(rel_paths + [step_rel_log])), f"{order.wp} {order.id} step {next_p.label}: {', '.join(rel_paths)} (relay, {part_outcome.step_record.model if part_outcome.step_record else 'model'})")

            if not options.no_push:
                push(wt)

        final_outcome = run_final(run_ctx)
        if final_outcome.result != Result.ACCEPTED:
            _finalize_records(run_ctx, final_outcome.result, accepted_records, final_outcome.stop_reason)
            return RelayOutcome(result=final_outcome.result, accepted_parts=tuple(accepted_records), stop_reason=final_outcome.stop_reason)

        _finalize_records(run_ctx, Result.ACCEPTED, accepted_records)
        print(f"ACCEPTED: Order {order.id} finished successfully.")
        print(f"To merge run: git merge --no-ff wo/{order.id}")
        remove(wt)
        return RelayOutcome(result=Result.ACCEPTED, accepted_parts=tuple(accepted_records))

    finally:
        lock.release()


def _finalize_records(ctx: RunContext, result: Result, accepted: list[records.StepRecord], stop_reason: str | None = None) -> None:
    sum_path = ctx.worktree.path / "docs" / "outsourcing" / "returns" / ctx.order.id / "summary.md"
    led_path = ctx.worktree.path / "docs" / "outsourcing" / "ledger.d" / f"{ctx.order.id}.md"

    outcome = RelayOutcome(result=result, accepted_parts=tuple(accepted), stop_reason=stop_reason)
    ledger.write_summary(sum_path, outcome)

    models_used = tuple((a.model, a.provider) for a in accepted)
    p_toks = sum(a.prompt_tokens for a in accepted)
    o_toks = sum(a.output_tokens for a in accepted)

    ledger.write_ledger_fragment(
        led_path, ctx.order.id, outcome, len(accepted), p_toks, o_toks, models_used
    )

    if result != Result.INTEGRITY:
        log_path = ctx.worktree.path / "docs" / "outsourcing" / "returns" / ctx.order.id / "steps.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(render(ctx.step_log), encoding="utf-8")

        sum_rel = f"docs/outsourcing/returns/{ctx.order.id}/summary.md"
        led_rel = f"docs/outsourcing/ledger.d/{ctx.order.id}.md"
        step_rel = f"docs/outsourcing/returns/{ctx.order.id}/steps.md"

        commit(ctx.worktree, (sum_rel, led_rel, step_rel), f"{ctx.order.wp} {ctx.order.id} records ({result.name})")
        if not ctx.options.no_push:
            try:
                push(ctx.worktree)
            except WorktreeError:
                pass


def main(argv: list[str] | None = None) -> int:
    opts = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        outcome = run(opts)
        return outcome.result.exit_code
    except Exception as exc:
        print(f"Relay error: {exc}", file=sys.stderr)
        return Result.INVALID.exit_code


if __name__ == "__main__":
    sys.exit(main())
