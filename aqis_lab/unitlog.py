"""Colab unit log: each session appends platform, GPU type, start and end UTC and estimated compute units.

CAPABILITIES:
  CAP-UNIT-001: start_session() records an open session in AQIS_LAB/logs/units_open_session.json (after closing a session that never ran `end` with end = its last-seen time, end_basis last-seen); touch() keeps last_seen_utc current; end_session() appends the session's row to AQIS_LAB/logs/units.csv: hours x the rate for its runtime from config/aqis_lab/colab_rates.yaml, computed exactly with fractions and rounded half-even to 4 places; the CSV is only appended to, never to a file with another header; an unknown runtime type is an error, never a default rate [tests: test_FR_0_5_07_appends_row_with_estimate_from_rate_table, test_FR_0_5_07_append_never_rewrites_existing_rows, test_FR_0_5_07_unknown_runtime_type_is_an_error, test_FR_0_5_07_unclosed_session_is_closed_at_next_start, test_FR_0_5_07_writes_only_under_aqis_lab_logs, test_FR_0_5_07_run_and_doctor_keep_last_seen_current]
  CAP-UNIT-002: load_rates() reads the rate table strictly: schema_version 1.0, each runtime once, a positive decimal string and a non-empty source for every rate [tests: test_FR_0_5_07_every_rate_names_its_source, test_FR_0_5_07_committed_rates_equal_owner_figures]
INPUTS AND OUTPUTS: the Drive mount, a machine block (from aqis_lab.platform) and the rate table in; rows in
  units.csv and the open-session file out; UnitLogError on failure.
CONTRACTS: the unit log format documented in the Colab runbook (docs/colab/).
INVARIANTS:
  - Writes only AQIS_LAB/logs/units.csv and AQIS_LAB/logs/units_open_session.json; nothing is deleted.
  - The estimate uses the exact duration; only the written numbers are rounded.
NOT IN SCOPE:
  - Deciding that this is a Colab session (aqis_lab/commands/unitlog.py asks aqis_lab.platform).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-07 created.
  2026-09-28 WP-0.5 FR-0.5-07: exact arithmetic with fractions (28-digit decimal division rounded a tie wrongly).
"""
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

import yaml

from aqis_lab import drive

UNITS_CSV = "units.csv"
OPEN_SESSION = "units_open_session.json"
RATES_REL = "config/aqis_lab/colab_rates.yaml"
HEADER = ["session_id", "platform", "gpu_type", "start_utc", "end_utc", "end_basis", "hours", "runtime",
          "units_per_hour", "estimated_units", "rate_source"]
PLACES = 4
UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class UnitLogError(RuntimeError):
    """The unit log cannot be written correctly."""


@dataclass(frozen=True)
class Rate:
    runtime: str
    units_per_hour: Decimal
    text: str
    source: str


def utc_now():
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


def load_rates(path):
    """{runtime: Rate} from the rate table; UnitLogError on any problem."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UnitLogError(f"{path} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or not isinstance(data.get("rates"), list):
        raise UnitLogError(f"{path} must hold schema_version: \"1.0\" and a list of rates")
    rates = {}
    for i, entry in enumerate(data["rates"]):
        where = f"{path} rate {i + 1}"
        if not isinstance(entry, dict) or set(entry) != {"runtime", "units_per_hour", "source"}:
            raise UnitLogError(f"{where}: needs exactly runtime, units_per_hour and source")
        runtime, value, source = entry["runtime"], entry["units_per_hour"], entry["source"]
        if not isinstance(runtime, str) or not runtime.strip():
            raise UnitLogError(f"{where}: runtime must be a non-empty string")
        if not isinstance(source, str) or not source.strip():
            raise UnitLogError(f"{where} ({runtime}): source must be a non-empty string")
        if not isinstance(value, str):
            raise UnitLogError(f"{where} ({runtime}): units_per_hour must be a decimal written as a string, "
                               f"got {value!r}")
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise UnitLogError(f"{where} ({runtime}): units_per_hour {value!r} is not a decimal") from exc
        if not number.is_finite() or number <= 0:
            raise UnitLogError(f"{where} ({runtime}): units_per_hour must be positive, got {value!r}")
        if runtime in rates:
            raise UnitLogError(f"{where}: runtime {runtime!r} is listed twice")
        rates[runtime] = Rate(runtime, number, value, source)
    if not rates:
        raise UnitLogError(f"{path} lists no rates")
    return rates


def runtime_of(gpu):
    return "cpu" if gpu is None else gpu


def rate_for(rates, gpu):
    runtime = runtime_of(gpu)
    if runtime not in rates:
        raise UnitLogError(f"no rate for runtime {runtime!r} in {RATES_REL} (known: {', '.join(sorted(rates))}); add "
                           f"its compute units per hour and their source")
    return rates[runtime]


def _parse(text):
    try:
        return datetime.strptime(text, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise UnitLogError(f"unreadable UTC time {text!r}") from exc


def round_half_even(value, places=PLACES):
    """A Fraction rounded half-even to `places` decimals, as a string with exactly that many decimals."""
    scaled = Fraction(value) * 10 ** places
    whole, rest = divmod(scaled.numerator, scaled.denominator)
    doubled = 2 * rest
    if doubled > scaled.denominator or (doubled == scaled.denominator and whole % 2 == 1):
        whole += 1
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole)).rjust(places + 1, "0")
    return f"{sign}{digits[:-places]}.{digits[-places:]}"


def estimate(start_utc, end_utc, rate):
    """(hours, units) as 4-place strings: the exact duration in hours x the rate, rounded half-even."""
    delta = _parse(end_utc) - _parse(start_utc)
    if delta.total_seconds() < 0:
        raise UnitLogError(f"session end {end_utc} is before its start {start_utc}")
    hours = Fraction(delta.days * 86400 * 10 ** 6 + delta.seconds * 10 ** 6 + delta.microseconds, 3600 * 10 ** 6)
    return round_half_even(hours), round_half_even(hours * Fraction(rate.text))


def logs_dir(mount):
    return drive.aqis_lab_folder(mount) / "logs"


def _read_session(mount):
    path = logs_dir(mount) / OPEN_SESSION
    if not path.exists():
        return None
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UnitLogError(f"{path} is unreadable: {exc}") from exc
    if not isinstance(session, dict) or session.get("state") not in ("open", "closed"):
        raise UnitLogError(f"{path} is not a unit-log session record")
    return session


def _write_session(mount, session, system):
    drive.write_bytes(logs_dir(mount) / OPEN_SESSION,
                      (json.dumps(session, indent=2, sort_keys=True) + "\n").encode("utf-8"), system)


def _append_row(mount, row, system):
    path = logs_dir(mount) / UNITS_CSV
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if path.exists():
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        if first != ",".join(HEADER):
            raise UnitLogError(f"{path} does not start with the unit-log header ({','.join(HEADER)}); nothing was "
                               f"appended")
    else:
        writer.writerow(HEADER)
    writer.writerow([row[k] for k in HEADER])
    drive.append_bytes(path, buffer.getvalue().encode("utf-8"), system)


def _close(mount, session, end_utc, end_basis, rates, system):
    rate = rate_for(rates, session["gpu_type"])
    hours, units = estimate(session["start_utc"], end_utc, rate)
    row = {"session_id": session["session_id"], "platform": session["platform"],
           "gpu_type": session["gpu_type"] or "", "start_utc": session["start_utc"], "end_utc": end_utc,
           "end_basis": end_basis, "hours": hours, "runtime": rate.runtime, "units_per_hour": rate.text,
           "estimated_units": units, "rate_source": rate.source}
    _append_row(mount, row, system)
    _write_session(mount, {**session, "state": "closed", "end_utc": end_utc, "end_basis": end_basis}, system)
    return row


def start_session(mount, machine, rates, now=None, system=None):
    """(row of a closed leftover session or None, the new open session)."""
    now = now or utc_now()
    rate_for(rates, machine["gpu"])                    # fail before writing anything
    if not logs_dir(mount).is_dir():
        raise UnitLogError(f"{logs_dir(mount)} does not exist; run `python -m aqis_lab drive layout` first")
    closed = None
    previous = _read_session(mount)
    if previous is not None and previous["state"] == "open":
        closed = _close(mount, previous, previous["last_seen_utc"], "last-seen", rates, system)
    seed = json.dumps({"start": now, "machine": machine}, sort_keys=True).encode()
    session = {"state": "open", "session_id": f"colab-{now[:10]}-{hashlib.sha256(seed).hexdigest()[:12]}",
               "platform": machine["platform"], "gpu_type": machine["gpu"], "start_utc": now, "last_seen_utc": now}
    _write_session(mount, session, system)
    return closed, session


def touch(mount, now=None, system=None):
    """Record that the open session is still alive; returns the session, or None when none is open."""
    session = _read_session(mount)
    if session is None or session["state"] != "open":
        return None
    session = {**session, "last_seen_utc": now or utc_now()}
    _write_session(mount, session, system)
    return session


def end_session(mount, rates, now=None, system=None):
    """Append the open session's row (end_basis end-command) and mark it closed; returns the row."""
    session = _read_session(mount)
    if session is None or session["state"] != "open":
        raise UnitLogError(f"no open session in {logs_dir(mount) / OPEN_SESSION}; run `unitlog start` first")
    return _close(mount, session, now or utc_now(), "end-command", rates, system)
