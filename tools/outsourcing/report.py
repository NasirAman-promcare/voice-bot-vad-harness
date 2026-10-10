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
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): the stop reason, and for TOO_LARGE the B9 advice; checks_table
    and request_facts build the report from the checks and governor of the run.
"""
from __future__ import annotations

from typing import Any

from tools.outsourcing.governor import Governor
from tools.outsourcing.records import CheckResults, RelayOutcome, Result

__all__ = ["render_report", "checks_table", "request_facts"]


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

    reason = facts.get("stop_reason")
    if reason and outcome.result != Result.ACCEPTED:
        lines.append(f"Reason: {str(reason).splitlines()[0][:200]}")
    if outcome.result == Result.TOO_LARGE:
        lines.append("Advice: split this step, or move context files that are only called into `interfaces`.")
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


def checks_table(results: CheckResults | None) -> list[str]:
    """One line per check that really ran in the last check round (B18); none when no check ran."""
    if results is None or not results.results:
        return ["none run"]
    return [f"{r.name}: {'PASS' if r.passed else 'FAIL'}" + ("" if r.passed else f" ({r.summary[:70]})")
            for r in results.results]


def request_facts(governor: Governor) -> dict[str, Any]:
    """Requests, retries and minutes waited per model, from this run's governor (B18)."""
    models = governor.report().models
    used = {name: rep for name, rep in models.items() if rep.requests}
    retries: dict[str, int] = {}
    for rep in used.values():
        for kind, count in rep.retries.items():
            retries[kind] = retries.get(kind, 0) + count
    return {"requests_per_model": {name: rep.requests for name, rep in sorted(used.items())},
            "retries_by_kind": retries,
            "minutes_waited": sum(rep.seconds_waited for rep in used.values()) / 60.0}
