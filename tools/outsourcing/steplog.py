"""Step log parser and renderer for relay execution resuming.

CAPABILITIES:
  CAP-OUTSOURCING-STEPLOG: Parse and render relay step logs
    [tests: test_empty_log_roundtrip, test_malformed_log_raises,
    test_FR_1_0_02_mc07_step_log_round_trips_byte_for_byte, test_FR_1_0_02_mc07_malformed_step_log_raises,
    test_FR_1_0_02_mc07_next_part_resumes_and_reduces_a_partial_step]
INPUTS AND OUTPUTS: Markdown log string in, StepLog out; StepLog in, Markdown log string out.
CONTRACTS: none.
INVARIANTS:
  - render(parse(text)) == text for every log render produced.
  - Unknown or malformed lines raise StepLogError.
NOT IN SCOPE:
  - I/O or network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from tools.outsourcing.records import StepPart, StepRecord
from tools.outsourcing.workorder import Step

__all__ = [
    "StepLogError",
    "RunRecord",
    "SwitchRecord",
    "StopRecord",
    "StepLog",
    "parse",
    "render",
]


class StepLogError(Exception):
    """Raised when a step log file is malformed or contains unknown lines."""


@dataclass(frozen=True)
class RunRecord:
    time_utc: datetime
    order_sha256: str
    wp_branch: str
    model: str


@dataclass(frozen=True)
class SwitchRecord:
    time_utc: datetime
    label: str
    from_model: str
    to_model: str
    reason: str


@dataclass(frozen=True)
class StopRecord:
    time_utc: datetime
    reason: str
    reset_utc: datetime | None = None


@dataclass(frozen=True)
class StepLog:
    runs: tuple[RunRecord, ...] = ()
    accepted: tuple[StepRecord, ...] = ()
    switches: tuple[SwitchRecord, ...] = ()
    stops: tuple[StopRecord, ...] = ()

    @property
    def wp_branch(self) -> str | None:
        return self.runs[0].wp_branch if self.runs else None

    def next_part(self, plan: tuple[Step, ...]) -> StepPart | None:
        accepted_files: set[str] = set()
        for acc in self.accepted:
            for path, _ in acc.files:
                accepted_files.add(path)

        for step in plan:
            remaining = [p for p in step.paths if p not in accepted_files]
            if remaining:
                label = _calc_part_label(step, remaining, self.accepted)
                return StepPart(label=label, paths=tuple(remaining))

        return None

    def record_run_start(self, time_utc: datetime, order_sha256: str, wp_branch: str, model: str) -> StepLog:
        new_run = RunRecord(time_utc=time_utc, order_sha256=order_sha256, wp_branch=wp_branch, model=model)
        return StepLog(runs=(*self.runs, new_run), accepted=self.accepted, switches=self.switches, stops=self.stops)

    def record_accepted(self, step_record: StepRecord) -> StepLog:
        return StepLog(runs=self.runs, accepted=(*self.accepted, step_record), switches=self.switches, stops=self.stops)

    def record_switch(self, time_utc: datetime, label: str, from_model: str, to_model: str, reason: str) -> StepLog:
        new_switch = SwitchRecord(time_utc=time_utc, label=label, from_model=from_model, to_model=to_model, reason=reason)
        return StepLog(runs=self.runs, accepted=self.accepted, switches=(*self.switches, new_switch), stops=self.stops)

    def record_stop(self, time_utc: datetime, reason: str, reset_utc_or_None: datetime | None = None) -> StepLog:
        new_stop = StopRecord(time_utc=time_utc, reason=reason, reset_utc=reset_utc_or_None)
        return StepLog(runs=self.runs, accepted=self.accepted, switches=self.switches, stops=(*self.stops, new_stop))


def _calc_part_label(step: Step, remaining: list[str], accepted: tuple[StepRecord, ...]) -> str:
    if len(remaining) == len(step.paths):
        return str(step.number)

    existing_subs: list[int] = []
    for acc in accepted:
        if acc.label == str(step.number):
            existing_subs.append(1)
        elif acc.label.startswith(f"{step.number}."):
            try:
                existing_subs.append(int(acc.label.split(".", 1)[1]))
            except ValueError:
                pass
    next_sub = max(existing_subs, default=0) + 1
    return f"{step.number}.{next_sub}"


def _dt_to_str(dt: datetime | None) -> str:
    return dt.isoformat() if dt is not None else ""


def _str_to_dt(s: str) -> datetime | None:
    if not s or s == "-":
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception as exc:
        raise StepLogError(f"Invalid datetime format {s!r}: {exc}") from exc


def render(steplog: StepLog) -> str:
    """Render a StepLog object to Markdown format."""
    lines: list[str] = ["# Step Log", ""]

    _render_runs(steplog.runs, lines)
    _render_accepted(steplog.accepted, lines)
    _render_switches(steplog.switches, lines)
    _render_stops(steplog.stops, lines)

    return "\n".join(lines)


def _render_runs(runs: tuple[RunRecord, ...], lines: list[str]) -> None:
    lines.extend(["## Runs", "| time_utc | order_sha256 | wp_branch | model |", "| --- | --- | --- | --- |"])
    for r in runs:
        lines.append(f"| {_dt_to_str(r.time_utc)} | {r.order_sha256} | {r.wp_branch} | {r.model} |")
    lines.append("")


def _render_accepted(accepted: tuple[StepRecord, ...], lines: list[str]) -> None:
    lines.extend([
        "## Accepted Parts",
        "| label | files | attempts | model | provider | model_version | prompt_tokens | output_tokens | seconds_waited |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for a in accepted:
        files_str = ";".join(f"{p}={h}" for p, h in a.files)
        lines.append(
            f"| {a.label} | {files_str} | {a.attempts} | {a.model} | {a.provider} | {a.model_version} | {a.prompt_tokens} | {a.output_tokens} | {a.seconds_waited} |"
        )
    lines.append("")


def _render_switches(switches: tuple[SwitchRecord, ...], lines: list[str]) -> None:
    lines.extend(["## Switches", "| time_utc | label | from_model | to_model | reason |", "| --- | --- | --- | --- | --- |"])
    for sw in switches:
        lines.append(f"| {_dt_to_str(sw.time_utc)} | {sw.label} | {sw.from_model} | {sw.to_model} | {sw.reason} |")
    lines.append("")


def _render_stops(stops: tuple[StopRecord, ...], lines: list[str]) -> None:
    lines.extend(["## Stops", "| time_utc | reason | reset_utc |", "| --- | --- | --- |"])
    for st in stops:
        lines.append(f"| {_dt_to_str(st.time_utc)} | {st.reason} | {_dt_to_str(st.reset_utc)} |")
    lines.append("")


def parse(text: str) -> StepLog:
    """Parse a Markdown step log text into a StepLog object."""
    if not text or not text.strip():
        return StepLog()

    lines = text.splitlines()
    runs, accepted, switches, stops = [], [], [], []
    current_section = None

    for line in lines:
        sline = line.strip()
        if not sline:
            continue
        if sline.startswith("#"):
            current_section = _parse_header(sline)
            continue
        if sline.startswith("|"):
            _parse_table_line(sline, current_section, runs, accepted, switches, stops)
            continue
        raise StepLogError(f"Unknown line in step log: {line!r}")

    return StepLog(runs=tuple(runs), accepted=tuple(accepted), switches=tuple(switches), stops=tuple(stops))


def _parse_header(line: str) -> str:
    headers = {
        "# Step Log": "main",
        "## Runs": "runs",
        "## Accepted Parts": "accepted",
        "## Switches": "switches",
        "## Stops": "stops",
    }
    if line in headers:
        return headers[line]
    raise StepLogError(f"Unknown header line: {line!r}")


def _parse_table_line(line: str, current_section: str | None, runs: list, accepted: list, switches: list, stops: list) -> None:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if all(set(c) <= set("-: ") for c in cells if c) or cells[0].lower() in ("time_utc", "label"):
        return

    try:
        if current_section == "runs":
            runs.append(RunRecord(time_utc=_str_to_dt(cells[0]), order_sha256=cells[1], wp_branch=cells[2], model=cells[3]))
        elif current_section == "accepted":
            accepted.append(_parse_accepted_row(cells))
        elif current_section == "switches":
            switches.append(SwitchRecord(time_utc=_str_to_dt(cells[0]), label=cells[1], from_model=cells[2], to_model=cells[3], reason=cells[4]))
        elif current_section == "stops":
            reset_utc = _str_to_dt(cells[2]) if len(cells) > 2 else None
            stops.append(StopRecord(time_utc=_str_to_dt(cells[0]), reason=cells[1], reset_utc=reset_utc))
        else:
            raise StepLogError(f"Table row outside recognized section: {line!r}")
    except Exception as exc:
        raise StepLogError(f"Failed to parse table row {line!r}: {exc}") from exc


def _parse_accepted_row(cells: list[str]) -> StepRecord:
    files_list = []
    if cells[1]:
        for pair in cells[1].split(";"):
            if "=" in pair:
                p, h = pair.split("=", 1)
                files_list.append((p.strip(), h.strip()))
    return StepRecord(
        label=cells[0],
        files=tuple(files_list),
        attempts=int(cells[2]),
        model=cells[3],
        provider=cells[4],
        model_version=cells[5],
        prompt_tokens=int(cells[6]),
        output_tokens=int(cells[7]),
        seconds_waited=float(cells[8]),
    )
