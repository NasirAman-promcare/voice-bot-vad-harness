"""Step log parser and renderer for relay execution resuming.

CAPABILITIES:
  CAP-OUTSOURCING-STEPLOG: Parse and render relay step logs [tests: test_steplog.py, test_acceptance_wo_1_0_02.py]
INPUTS AND OUTPUTS: Markdown log string in, StepLog out; StepLog in, Markdown log string out.
CONTRACTS: none.
INVARIANTS:
  - render(parse(text)) == text for every log render produced.
  - Unknown or malformed lines raise StepLogError.
NOT IN SCOPE:
  - I/O or network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
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
                if len(remaining) == len(step.paths):
                    label = str(step.number)
                else:
                    existing_subs: list[int] = []
                    for acc in self.accepted:
                        if acc.label == str(step.number):
                            existing_subs.append(1)
                        elif acc.label.startswith(f"{step.number}."):
                            try:
                                existing_subs.append(int(acc.label.split(".", 1)[1]))
                            except ValueError:
                                pass
                    next_sub = max(existing_subs, default=0) + 1
                    label = f"{step.number}.{next_sub}"
                return StepPart(label=label, paths=tuple(remaining))

        return None

    def record_run_start(self, time_utc: datetime, order_sha256: str, wp_branch: str, model: str) -> StepLog:
        new_run = RunRecord(time_utc=time_utc, order_sha256=order_sha256, wp_branch=wp_branch, model=model)
        return StepLog(
            runs=(*self.runs, new_run),
            accepted=self.accepted,
            switches=self.switches,
            stops=self.stops,
        )

    def record_accepted(self, step_record: StepRecord) -> StepLog:
        return StepLog(
            runs=self.runs,
            accepted=(*self.accepted, step_record),
            switches=self.switches,
            stops=self.stops,
        )

    def record_switch(self, time_utc: datetime, label: str, from_model: str, to_model: str, reason: str) -> StepLog:
        new_switch = SwitchRecord(time_utc=time_utc, label=label, from_model=from_model, to_model=to_model, reason=reason)
        return StepLog(
            runs=self.runs,
            accepted=self.accepted,
            switches=(*self.switches, new_switch),
            stops=self.stops,
        )

    def record_stop(self, time_utc: datetime, reason: str, reset_utc_or_None: datetime | None = None) -> StepLog:
        new_stop = StopRecord(time_utc=time_utc, reason=reason, reset_utc=reset_utc_or_None)
        return StepLog(
            runs=self.runs,
            accepted=self.accepted,
            switches=self.switches,
            stops=(*self.stops, new_stop),
        )


def _dt_to_str(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


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

    # 1. Runs
    lines.append("## Runs")
    lines.append("| time_utc | order_sha256 | wp_branch | model |")
    lines.append("| --- | --- | --- | --- |")
    for r in steplog.runs:
        lines.append(f"| {_dt_to_str(r.time_utc)} | {r.order_sha256} | {r.wp_branch} | {r.model} |")
    lines.append("")

    # 2. Accepted Parts
    lines.append("## Accepted Parts")
    lines.append("| label | files | attempts | model | provider | model_version | prompt_tokens | output_tokens | seconds_waited |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for a in steplog.accepted:
        files_str = ";".join(f"{p}={h}" for p, h in a.files)
        lines.append(
            f"| {a.label} | {files_str} | {a.attempts} | {a.model} | {a.provider} | {a.model_version} | {a.prompt_tokens} | {a.output_tokens} | {a.seconds_waited} |"
        )
    lines.append("")

    # 3. Switches
    lines.append("## Switches")
    lines.append("| time_utc | label | from_model | to_model | reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for sw in steplog.switches:
        lines.append(f"| {_dt_to_str(sw.time_utc)} | {sw.label} | {sw.from_model} | {sw.to_model} | {sw.reason} |")
    lines.append("")

    # 4. Stops
    lines.append("## Stops")
    lines.append("| time_utc | reason | reset_utc |")
    lines.append("| --- | --- | --- |")
    for st in steplog.stops:
        lines.append(f"| {_dt_to_str(st.time_utc)} | {st.reason} | {_dt_to_str(st.reset_utc)} |")
    lines.append("")

    return "\n".join(lines)


def _split_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(text: str) -> StepLog:
    """Parse a Markdown step log text into a StepLog object."""
    if not text or not text.strip():
        return StepLog()

    lines = text.splitlines()
    i = 0
    runs: list[RunRecord] = []
    accepted: list[StepRecord] = []
    switches: list[SwitchRecord] = []
    stops: list[StopRecord] = []

    current_section: str | None = None

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.startswith("#"):
            if line == "# Step Log":
                current_section = "main"
            elif line == "## Runs":
                current_section = "runs"
            elif line == "## Accepted Parts":
                current_section = "accepted"
            elif line == "## Switches":
                current_section = "switches"
            elif line == "## Stops":
                current_section = "stops"
            else:
                raise StepLogError(f"Unknown header line: {line!r}")
            i += 1
            continue

        if line.startswith("|"):
            cells = _split_table_row(line)
            # Check if separator row
            if all(set(c) <= set("-: ") for c in cells if c):
                i += 1
                continue

            # Check if header row
            first_c = cells[0].lower()
            if first_c in ("time_utc", "label"):
                i += 1
                continue

            # Data row parsing based on section
            try:
                if current_section == "runs":
                    t_utc = _str_to_dt(cells[0])
                    assert t_utc is not None
                    runs.append(RunRecord(time_utc=t_utc, order_sha256=cells[1], wp_branch=cells[2], model=cells[3]))
                elif current_section == "accepted":
                    lbl = cells[0]
                    files_raw = cells[1]
                    files_list: list[tuple[str, str]] = []
                    if files_raw:
                        for pair in files_raw.split(";"):
                            if "=" in pair:
                                p, h = pair.split("=", 1)
                                files_list.append((p.strip(), h.strip()))
                    attempts = int(cells[2])
                    model = cells[3]
                    provider = cells[4]
                    m_ver = cells[5]
                    p_tok = int(cells[6])
                    o_tok = int(cells[7])
                    sec_w = float(cells[8])
                    accepted.append(
                        StepRecord(
                            label=lbl,
                            files=tuple(files_list),
                            attempts=attempts,
                            model=model,
                            provider=provider,
                            model_version=m_ver,
                            prompt_tokens=p_tok,
                            output_tokens=o_tok,
                            seconds_waited=sec_w,
                        )
                    )
                elif current_section == "switches":
                    t_utc = _str_to_dt(cells[0])
                    assert t_utc is not None
                    switches.append(
                        SwitchRecord(
                            time_utc=t_utc,
                            label=cells[1],
                            from_model=cells[2],
                            to_model=cells[3],
                            reason=cells[4],
                        )
                    )
                elif current_section == "stops":
                    t_utc = _str_to_dt(cells[0])
                    assert t_utc is not None
                    reset_utc = _str_to_dt(cells[2]) if len(cells) > 2 else None
                    stops.append(StopRecord(time_utc=t_utc, reason=cells[1], reset_utc=reset_utc))
                else:
                    raise StepLogError(f"Table row outside recognized section: {line!r}")
            except Exception as exc:
                raise StepLogError(f"Failed to parse table row {line!r}: {exc}") from exc

            i += 1
            continue

        raise StepLogError(f"Unknown line in step log: {line!r}")

    return StepLog(
        runs=tuple(runs),
        accepted=tuple(accepted),
        switches=tuple(switches),
        stops=tuple(stops),
    )
