"""Final verifier and fix runner for relay execution.

CAPABILITIES:
  CAP-OUTSOURCING-STEPPER-FINAL: Final verification and fix rounds for relay execution. [tests: test_stepper.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Accepts RunContext; runs full checks and fix turns; returns StepOutcome.
CONTRACTS: none.
INVARIANTS:
  - Final fix commits only after full checks pass.
  - Discards uncommitted files on EXHAUSTED after the final attempt.
NOT IN SCOPE:
  - CLI parsing.
CHANGE LOG:
  2026-10-10 WO-1.0-11 FIX 1 created.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): the router gets a token estimate; the full checks are kept
    in RunContext.last_checks for the report.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.outsourcing import bundle, checks, fixorder, importer, prompt
from tools.outsourcing.chat import (
    ApiError, CredentialError, DailyQuotaExhausted, ModelError,
    ServiceBusy, StepTooLarge, TransportError,
)
from tools.outsourcing.records import Result, StepOutcome
from tools.outsourcing.router import NoEligibleModel, PoolExhausted, client_for
from tools.outsourcing.worktree import commit, discard_attempt, push

if TYPE_CHECKING:
    from tools.outsourcing.stepper import RunContext

__all__ = ["run_final"]


def _get_status_uncommitted(wt_path: Path, outputs: tuple[str, ...]) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_path, capture_output=True, text=True
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return ()
    paths = []
    out_set = set(outputs)
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        p = line[3:].strip()
        if p in out_set or p.startswith("docs/outsourcing/"):
            paths.append(p)
    return tuple(paths)


def _attempt_final_fix_turn(
    ctx: RunContext, chk_res: Any, attempts_used: int, attempt_dir: Path
) -> tuple[bool, str, str]:
    from tools.outsourcing.stepper import _save_raw_records

    failing_paths = tuple(
        sorted(set(p for cr in chk_res.results if not cr.passed for p in cr.output_paths if p in ctx.order.outputs))
    )
    focus_paths = failing_paths or ctx.order.outputs
    fix_text = fixorder.build_fix_order(ctx.order, chk_res, attempts_used, ctx.order.outputs, "final")

    try:
        req_obj = prompt.final_fix_request(ctx.order, ctx.plan, ctx.worktree.path, fix_text, focus_paths=focus_paths)
        model_spec = ctx.router.choose(ctx.order, prompt.estimated_input_tokens(req_obj), exclude=ctx.run_exclusions)
        client = client_for(model_spec, ctx.governor, ctx.options.timeout, ctx.options.api_base)
        reply = client.generate(req_obj.chat)
        ctx.record_reply(reply, model_spec.name, model_spec.provider.name)
    except (
        PoolExhausted, NoEligibleModel, DailyQuotaExhausted, ServiceBusy,
        ModelError, CredentialError, StepTooLarge, ApiError, TransportError,
    ) as exc:
        return False, "", str(exc)

    _save_raw_records(attempt_dir, req_obj, model_spec.name, reply.raw_json or reply.text, chk_res)

    try:
        b_obj = bundle.parse_bundle(reply.text)
        imp_rep = importer.import_bundle(b_obj, ctx.order, ctx.worktree.path, mode="fix", expected=set(ctx.order.outputs))
        written = tuple(f.path for f in imp_rep.files)
        return True, model_spec.name, "" if written else "no files written"
    except (bundle.BundleError, importer.ImportRefused) as exc:
        return False, model_spec.name, str(exc)


def run_final(ctx: RunContext) -> StepOutcome:
    final_dir = ctx.log_root / "final"
    attempts_used, max_attempts, py_path, last_model = 0, ctx.options.attempts, sys.executable, "relay"

    while attempts_used < max_attempts:
        attempts_used += 1
        attempt_dir = final_dir / f"attempt-{attempts_used}"

        chk_res = checks.full_checks(
            ctx.order, ctx.worktree.path, attempt_dir, ctx.worktree.base_commit, py_path, ctx.options.verify_timeout
        )
        ctx.last_checks = chk_res

        if chk_res.integrity_failed:
            return StepOutcome(result=Result.INTEGRITY, stop_reason="Full checks integrity failed")

        if chk_res.passed:
            uncommitted = _get_status_uncommitted(ctx.worktree.path, ctx.order.outputs)
            if uncommitted:
                commit(
                    ctx.worktree, uncommitted,
                    f"{ctx.order.wp} {ctx.order.id} final fix {attempts_used - 1} (relay, {last_model})",
                )
                if not ctx.options.no_push:
                    push(ctx.worktree)
            return StepOutcome(result=Result.ACCEPTED)

        if attempts_used == max_attempts:
            uncommitted = _get_status_uncommitted(ctx.worktree.path, ctx.order.outputs)
            if uncommitted:
                discard_attempt(ctx.worktree, uncommitted)
            failing = [f"{r.name}: {r.summary}" for r in chk_res.results if not r.passed]
            return StepOutcome(result=Result.EXHAUSTED, stop_reason="; ".join(failing))

        ok, model_used, err_msg = _attempt_final_fix_turn(ctx, chk_res, attempts_used, attempt_dir)
        if model_used:
            last_model = model_used

    uncommitted = _get_status_uncommitted(ctx.worktree.path, ctx.order.outputs)
    if uncommitted:
        discard_attempt(ctx.worktree, uncommitted)
    return StepOutcome(result=Result.EXHAUSTED, stop_reason="Final fix attempts exhausted")
