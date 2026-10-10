"""Fix order builder and log trimmer.

CAPABILITIES:
  CAP-OUTSOURCING-FIXORDER: Format fix order text following FIX_ORDER.md [tests: test_fixorder.py, test_acceptance_wo_1_0_02.py]
INPUTS AND OUTPUTS: WorkOrder, CheckResults/stop_reason, fix_number, allowed_paths in; string fix order out.
CONTRACTS: none.
INVARIANTS:
  - Trimmed logs keep first 20 and last 40 lines.
  - Across all checks, at most 120 lines of log are included.
NOT IN SCOPE:
  - Interacting with network or models.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from pathlib import Path
from tools.outsourcing.records import CheckResults
from tools.outsourcing.workorder import WorkOrder

__all__ = ["build_fix_order", "trim_log"]


def trim_log(text: str) -> str:
    """Trim a log text to keep the first 20 and last 40 lines, adding cut marks if needed."""
    lines = text.splitlines()
    if len(lines) <= 60:
        return "\n".join(lines)

    first_20 = lines[:20]
    last_40 = lines[-40:]
    cut_count = len(lines) - 60

    return "\n".join(first_20) + f"\n[… {cut_count} lines …]\n" + "\n".join(last_40)


def build_fix_order(
    order: WorkOrder,
    results: CheckResults,
    fix_number: int,
    allowed_paths: tuple[str, ...] | list[str],
    step_label: str,
    stop_reason: str | None = None,
) -> str:
    """Build fix order text per FIX_ORDER.md format."""
    lines: list[str] = [f"# FIX {fix_number} for {order.id}\n"]

    if stop_reason is not None:
        _format_stop_reason(stop_reason, lines)
    else:
        _format_failed_checks(results, lines)

    lines.append("## Files you may change")
    for path in allowed_paths:
        lines.append(f"- {path}")

    lines.append("\n## Rules")
    lines.append("- Return only the files you change, each complete, in RETURN_FORMAT.md form, followed by the DOD table for the items affected.")
    lines.append("- Do not touch any other file, and never the read-only tests.")
    lines.append("- If the failure shows the work order itself is wrong, return a QUESTIONS block instead.")

    return "\n".join(lines).rstrip() + "\n"


def _format_stop_reason(stop_reason: str, lines: list[str]) -> None:
    if stop_reason == "MAX_TOKENS":
        msg = "Your answer was cut off before the end. Return the same files again, complete; keep comments and docstrings short."
    else:
        msg = f"Your answer was blocked or empty ({stop_reason}). Return the files again, complete, in RETURN_FORMAT form."
    lines.append(f"## Reason for fix\n{msg}\n")


def _format_failed_checks(results: CheckResults, lines: list[str]) -> None:
    lines.append("Your previous answer did not pass these checks. Fix the root cause; do not special-case test inputs.\n")
    lines.append("## Failed checks")

    failed_results = [r for r in results.results if not r.passed]
    total_budget = 120
    used_budget = 0

    for idx, r in enumerate(failed_results, start=1):
        if used_budget >= total_budget:
            lines.append(f"{idx}. {r.name}: {r.summary}\n   [… log omitted due to line budget …]")
            continue
        used_budget += _format_single_check(r, idx, lines, total_budget - used_budget)

    lines.append("")


def _format_single_check(r: object, idx: int, lines: list[str], remaining_budget: int) -> int:
    log_text = ""
    if getattr(r, "log_path", None) and getattr(r, "log_path").is_file():
        try:
            log_text = getattr(r, "log_path").read_bytes().decode("utf-8", errors="replace")
        except Exception:
            log_text = ""

    trimmed = trim_log(log_text) if log_text else ""
    t_lines = trimmed.splitlines()

    if len(t_lines) <= remaining_budget:
        chunk = trimmed
        used = len(t_lines)
    else:
        chunk = "\n".join(t_lines[:remaining_budget])
        used = remaining_budget

    indented_log = "\n".join(f"   {l}" for l in chunk.splitlines())
    lines.append(f"{idx}. {getattr(r, 'name')}: {getattr(r, 'summary')}\n{indented_log}")
    return used
