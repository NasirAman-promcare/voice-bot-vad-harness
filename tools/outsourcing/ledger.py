"""Summary and ledger fragment writer for relay execution runs.

CAPABILITIES:
  CAP-OUTSOURCING-LEDGER: Write summary.md and ledger fragment for relay outcomes. [tests: test_ledger.py, test_acceptance_wo_1_0_11.py]
INPUTS AND OUTPUTS: Accepts summary path/ledger path and RelayOutcome/RunContext/GovernorReport; formats and writes Markdown.
CONTRACTS: FRAGMENTS.md B17 format for ledger fragments.
INVARIANTS:
  - Total tokens sum prompt and completion tokens from all successful HTTP 200 responses.
  - Models used in ledger fragment are formatted as '<model> (<provider>)'.
NOT IN SCOPE:
  - Network transport or process execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.outsourcing.records import RelayOutcome, Result, StepRecord

__all__ = ["write_summary", "write_ledger_fragment"]


def write_summary(
    path: str | Path,
    outcome: RelayOutcome,
    order_amended: bool = False,
    changed_files: tuple[str, ...] = (),
    unreadable_logs: tuple[str, ...] = (),
    governor_report: Any = None,
    unverified_providers: tuple[str, ...] = (),
    written_files: tuple[str, ...] = (),
    switches: tuple[Any, ...] = (),
    check_table_lines: tuple[str, ...] = (),
    questions: tuple[str, ...] = (),
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [f"# Summary: {outcome.result.display_name}", ""]

    if order_amended:
        lines.extend(["order amended since the last run", ""])

    if changed_files:
        lines.append("## Files changed since acceptance")
        for cf in changed_files:
            lines.append(f"- {cf}")
        lines.append("")

    if unreadable_logs:
        lines.append("## Unreadable step logs")
        for ul in unreadable_logs:
            lines.append(f"- {ul}")
        lines.append("")

    lines.append("## Accepted Parts")
    if outcome.accepted_parts:
        lines.append("| label | files | attempts | model | provider | tokens_in | tokens_out | seconds_waited |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for part in outcome.accepted_parts:
            files_str = ", ".join(f[0] for f in part.files)
            lines.append(
                f"| {part.label} | {files_str} | {part.attempts} | {part.model} | {part.provider} | "
                f"{part.prompt_tokens} | {part.output_tokens} | {part.seconds_waited:.1f} |"
            )
    else:
        lines.append("None")
    lines.append("")

    if switches:
        lines.append("## Model Switches")
        lines.append("| label | from_model | to_model | reason |")
        lines.append("| --- | --- | --- | --- |")
        for sw in switches:
            lines.append(f"| {sw.label} | {sw.from_model} | {sw.to_model} | {sw.reason} |")
        lines.append("")

    if questions:
        lines.append("## Questions")
        for q in questions:
            lines.append(q)
        lines.append("")
    elif outcome.result == Result.QUESTIONS and outcome.stop_reason:
        lines.append("## Questions")
        lines.append(outcome.stop_reason)
        lines.append("")

    if check_table_lines:
        lines.append("## Checks")
        lines.extend(check_table_lines)
        lines.append("")

    if governor_report:
        lines.append("## Governor Report")
        if hasattr(governor_report, "models"):
            lines.append("### Models")
            for m_name, m_rep in governor_report.models.items():
                lines.append(f"- {m_name}: requests={m_rep.requests}, count_today={m_rep.count_today}")
        lines.append("")

    if unverified_providers:
        lines.append("## Unverified Providers")
        for up in unverified_providers:
            lines.append(f"- {up}")
        lines.append("")

    if written_files:
        lines.append("## Files Written")
        for wf in written_files:
            lines.append(f"- {wf}")
        lines.append("")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ledger_fragment(
    path: str | Path,
    wo_id: str,
    outcome: RelayOutcome,
    total_requests: int,
    total_prompt_tokens: int,
    total_output_tokens: int,
    models_used: tuple[tuple[str, str], ...],
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    models_str_list = []
    seen = set()
    for m_name, p_name in models_used:
        item = f"{m_name} ({p_name})"
        if item not in seen:
            seen.add(item)
            models_str_list.append(item)
    models_str = ", ".join(models_str_list) if models_str_list else "none"

    lines = [
        f"---",
        f"id: {wo_id}",
        f"---",
        f"",
        f"# Ledger Fragment: {wo_id}",
        f"",
        f"Result: {outcome.result.name}",
        f"Requests: {total_requests}",
        f"Prompt tokens: {total_prompt_tokens}",
        f"Output tokens: {total_output_tokens}",
        f"Model: {models_str}",
        f"",
    ]

    p.write_text("\n".join(lines), encoding="utf-8")
