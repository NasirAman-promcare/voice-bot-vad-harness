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
  2026-10-10 WO-1.0-11 FIX 1: split write_summary and support B24 reply token counts.
  2026-10-12 WP-1.0 FR-1.0-02 fix (Claude, FIX-B17-ledger-row): the ledger fragment is the FRAGMENTS.md row (WO, Date,
    Model, Model version, Attempts, Requests, tokens, Result, Seconds) that tools.progress reads and lints.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.outsourcing.records import RelayOutcome, Result, StepRecord

__all__ = ["write_summary", "write_ledger_fragment", "run_facts"]


def _render_accepted_section(accepted_parts: tuple[StepRecord, ...]) -> list[str]:
    lines = ["## Accepted Parts"]
    if accepted_parts:
        lines.append("| label | files | attempts | model | provider | tokens_in | tokens_out | seconds_waited |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for part in accepted_parts:
            files_str = ", ".join(f[0] for f in part.files)
            lines.append(
                f"| {part.label} | {files_str} | {part.attempts} | {part.model} | {part.provider} | "
                f"{part.prompt_tokens} | {part.output_tokens} | {part.seconds_waited:.1f} |"
            )
    else:
        lines.append("None")
    lines.append("")
    return lines


def _render_switches_section(switches: tuple[Any, ...]) -> list[str]:
    if not switches:
        return []
    lines = ["## Model Switches", "| label | from_model | to_model | reason |", "| --- | --- | --- | --- |"]
    for sw in switches:
        lines.append(f"| {sw.label} | {sw.from_model} | {sw.to_model} | {sw.reason} |")
    lines.append("")
    return lines


def _render_questions_section(questions: tuple[str, ...], result: Result, stop_reason: str | None) -> list[str]:
    lines: list[str] = []
    if questions:
        lines.append("## Questions")
        lines.extend(questions)
        lines.append("")
    elif result == Result.QUESTIONS and stop_reason:
        lines.append("## Questions")
        lines.append(stop_reason)
        lines.append("")
    return lines


def _render_governor_section(governor_report: Any) -> list[str]:
    if not governor_report:
        return []
    lines = ["## Governor Report"]
    if hasattr(governor_report, "models"):
        lines.append("### Models")
        for m_name, m_rep in governor_report.models.items():
            lines.append(f"- {m_name}: requests={m_rep.requests}, count_today={m_rep.count_today}")
    lines.append("")
    return lines


def _render_list_section(title: str, items: tuple[str, ...]) -> list[str]:
    if not items:
        return []
    lines = [f"## {title}"]
    for item in items:
        lines.append(f"- {item}")
    lines.append("")
    return lines


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

    lines.extend(_render_list_section("Files changed since acceptance", changed_files))
    lines.extend(_render_list_section("Unreadable step logs", unreadable_logs))
    lines.extend(_render_accepted_section(outcome.accepted_parts))
    lines.extend(_render_switches_section(switches))
    lines.extend(_render_questions_section(questions, outcome.result, outcome.stop_reason))

    if check_table_lines:
        lines.append("## Checks")
        lines.extend(check_table_lines)
        lines.append("")

    lines.extend(_render_governor_section(governor_report))
    lines.extend(_render_list_section("Unverified Providers", unverified_providers))
    lines.extend(_render_list_section("Files Written", written_files))

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_facts(accepted: Any, step_log: Any, now: float) -> dict[str, Any]:
    """The ledger's date, model versions, attempts and seconds since the step log's latest run start (B17)."""
    started = step_log.runs[-1].time_utc.timestamp() if step_log.runs else now
    return {"date": datetime.fromtimestamp(now, tz=timezone.utc).date().isoformat(),
            "model_versions": tuple(a.model_version for a in accepted),
            "attempts": sum(a.attempts for a in accepted), "seconds": max(0, round(now - started))}


def write_ledger_fragment(
    path: str | Path,
    wo_id: str,
    outcome: RelayOutcome,
    total_requests: int,
    total_prompt_tokens: int,
    total_output_tokens: int,
    models_used: tuple[tuple[str, str], ...],
    *,
    date: str,
    model_versions: tuple[str, ...],
    attempts: int,
    seconds: int,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    models_str = ", ".join(dict.fromkeys(f"{m_name} ({p_name})" for m_name, p_name in models_used)) or "none"

    versions = ", ".join(dict.fromkeys(v for v in model_versions if v)) or "not reported"
    lines = [
        f"WO: {wo_id}",
        f"Date: {date}",
        f"Model: {models_str}",
        f"Model version: {versions}",
        f"Attempts: {attempts}",
        f"Requests: {total_requests}",
        f"Prompt tokens: {total_prompt_tokens}",
        f"Output tokens: {total_output_tokens}",
        f"Result: {outcome.result.name}",
        f"Seconds: {seconds}",
        "",
    ]

    p.write_text("\n".join(lines), encoding="utf-8")
