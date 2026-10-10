"""Printed report renderer for relay execution finishes.

CAPABILITIES:
  CAP-OUTSOURCING-REPORT: Render concise finish report for relay execution. [tests: test_report.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Accepts RelayOutcome and context facts; formats and returns list of output report lines (at most 25 lines).
CONTRACTS: none.
INVARIANTS:
  - Report output is at most 25 lines.
  - Display name on first line.
NOT IN SCOPE:
  - Direct stdout printing or CLI execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 FIX 1 created.
"""
from __future__ import annotations

from typing import Any

from tools.outsourcing.records import RelayOutcome, Result

__all__ = ["render_report"]


def render_report(outcome: RelayOutcome, ctx_facts: dict[str, Any] | None = None) -> list[str]:
    facts = ctx_facts or {}
    lines: list[str] = [outcome.result.display_name]

    parts_done = facts.get("parts_done", len(outcome.accepted_parts))
    total_parts = facts.get("total_parts", len(outcome.accepted_parts))
    lines.append(f"Parts: {parts_done}/{total_parts}")

    reqs_per_model = facts.get("requests_per_model", {})
    model_str = ", ".join(f"{m}: {c}" for m, c in reqs_per_model.items()) if reqs_per_model else "none"
    retries = facts.get("retries_by_kind", {})
    retries_str = ", ".join(f"{k}: {c}" for k, c in retries.items()) if retries else "none"
    mins_waited = facts.get("minutes_waited", 0.0)
    lines.append(f"Requests: {model_str} | Retries: {retries_str} | Minutes waited: {mins_waited:.1f}")

    p_toks = facts.get("prompt_tokens", sum(a.prompt_tokens for a in outcome.accepted_parts))
    o_toks = facts.get("output_tokens", sum(a.output_tokens for a in outcome.accepted_parts))
    lines.append(f"Tokens: in {p_toks}, out {o_toks}")

    for pool_line in facts.get("pool_lines", ()):
        lines.append(pool_line)
    for access_line in facts.get("access_lines", ()):
        lines.append(access_line)

    checks_table = facts.get("checks_table", ())
    if checks_table:
        lines.append("Checks:")
        for chk in checks_table[:5]:
            lines.append(f"  {chk}")

    summary_path = facts.get("summary_path")
    if summary_path:
        lines.append(f"Summary: {summary_path}")

    if outcome.result == Result.PAUSED_DAILY:
        lines.append(f"Resume: .venv/bin/python -m tools.outsourcing.relay --wo {facts.get('wo_path', '')}")
        if "reset_time" in facts:
            lines.append(f"Reset: {facts['reset_time']}")
    elif outcome.result == Result.PAUSED_BUSY:
        lines.append(f"Resume: .venv/bin/python -m tools.outsourcing.relay --wo {facts.get('wo_path', '')}")
    elif outcome.result == Result.ACCEPTED:
        wo_id = facts.get("wo_id", "")
        lines.append(f"Merge: git merge --no-ff wo/{wo_id}")

    if len(lines) > 25:
        lines = lines[:25]

    return lines
