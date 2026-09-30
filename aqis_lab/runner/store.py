"""The run folder: run card, shard plan, shard results with completion markers, final results and the runner log.

CAPABILITIES:
  CAP-RUN-006: write_shard() writes a shard's results atomically, then its completion marker (plan ID, shard index, results SHA-256, bytes and rows, finished UTC, duration, session and machine); shard_finished() counts a shard as finished only when its marker parses, names this plan and shard, and matches the results file's SHA-256 and size, and otherwise says why not [tests: test_FR_0_5_05_shard_results_written_atomically_with_marker, test_FR_0_5_05_results_without_marker_not_finished, test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished, test_FR_0_5_06_kill_during_result_write_never_counts]
  CAP-RUN-011: for tasks that write events, write_shard() also writes the shard's events (shards/shard-NNNNN.events.jsonl) before the marker and records events_file, events_sha256, events_bytes, events and seq_first in it; shard_finished() then also requires the events file to match; markers of tasks without events are unchanged [tests: test_FR_0_7_01_events_validate_against_event_log_v1, test_FR_0_7_07_changed_shard_events_mean_the_shard_is_not_finished]
INPUTS AND OUTPUTS: a run folder and shard results in; files in the run folder out.
CONTRACTS: run folder layout in docs/runner/RUNNER.md.
INVARIANTS:
  - The results file (and the events file) are written before their marker; files without a valid marker never
    count.
  - Every write goes through aqis_lab.drive (atomic, and only under MyDrive/AQIS_LAB on Drive).
NOT IN SCOPE:
  - Deciding which shards to run (aqis_lab/runner/run.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
  2026-09-30 WP-0.7 FR-0.7-07: event files for tasks that write events (write_shard, shard_finished, events_path,
    RUN_ID, EVENTS_HEAD, EVENTS); markers of other tasks unchanged.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from aqis_lab import drive

RUN_CARD = "run_card.json"
PLAN = "shard_plan.json"
SHARDS = "shards"
RESULTS = "results.jsonl"
LOG = "runner.log"
RUN_ID = "run_id.txt"
EVENTS_HEAD = "events.head.jsonl"
EVENTS = "events.jsonl"
MARKER_VERSION = "1.0"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def shard_stem(index):
    return f"shard-{index:05d}"


def results_path(run_dir, index):
    return Path(run_dir) / SHARDS / f"{shard_stem(index)}.jsonl"


def marker_path(run_dir, index):
    return Path(run_dir) / SHARDS / f"{shard_stem(index)}.done.json"


def events_path(run_dir, index):
    return Path(run_dir) / SHARDS / f"{shard_stem(index)}.events.jsonl"


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path, value, system=None, exclusive=False):
    data = json_bytes(value)
    drive.write_bytes(path, data, system, exclusive=exclusive)
    if json.loads(Path(path).read_text(encoding="utf-8")) != value:
        raise OSError(f"{path} does not read back as written")


def write_shard(run_dir, index, data, rows, plan_id, session, machine, duration_ns, system=None, events=None,
                seq_first=None):
    """Write the shard's results (and events, for tasks that write events) atomically, then its marker."""
    target = drive.write_bytes(results_path(run_dir, index), data, system)
    if target.read_bytes() != data:
        raise OSError(f"{target} does not read back as written")
    marker = {"marker_version": MARKER_VERSION, "plan_id": plan_id, "shard": index,
              "results_file": target.name, "results_sha256": hashlib.sha256(data).hexdigest(),
              "results_bytes": len(data), "rows": rows, "finished_utc": utc_now(), "duration_ns": duration_ns,
              "session": session, "machine": machine}
    if events is not None:
        written = drive.write_bytes(events_path(run_dir, index), events, system)
        if written.read_bytes() != events:
            raise OSError(f"{written} does not read back as written")
        marker.update({"events_file": written.name, "events_sha256": hashlib.sha256(events).hexdigest(),
                       "events_bytes": len(events), "events": events.count(b"\n"), "seq_first": seq_first})
    write_json(marker_path(run_dir, index), marker, system)
    return marker


def shard_finished(run_dir, index, plan_id):
    """(True, marker) when the shard is provably finished, else (False, reason)."""
    path = marker_path(run_dir, index)
    if not path.exists():
        return False, "no completion marker"
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"completion marker unreadable ({exc})"
    if not isinstance(marker, dict):
        return False, "completion marker unreadable (not a JSON object)"
    if marker.get("plan_id") != plan_id:
        return False, "completion marker names another plan"
    if marker.get("shard") != index:
        return False, f"completion marker names another shard ({marker.get('shard')!r})"
    results = results_path(run_dir, index)
    try:
        data = results.read_bytes()
    except OSError:
        return False, "completion marker present but the results file is missing"
    if len(data) != marker.get("results_bytes") or hashlib.sha256(data).hexdigest() != marker.get("results_sha256"):
        return False, "results sha256 or size differs from the completion marker"
    if "events_file" in marker:
        try:
            events = events_path(run_dir, index).read_bytes()
        except OSError:
            return False, "completion marker present but the events file is missing"
        if len(events) != marker.get("events_bytes") or \
                hashlib.sha256(events).hexdigest() != marker.get("events_sha256"):
            return False, "events sha256 or size differs from the completion marker"
    return True, marker


def append_log(run_dir, message, system=None):
    """Append one UTC-stamped line to runner.log; returns the line."""
    line = f"{utc_now()} {message}"
    drive.append_bytes(Path(run_dir) / LOG, (line + "\n").encode("utf-8"), system)
    return line
