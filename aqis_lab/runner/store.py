"""The run folder: run card, shard plan, shard results with completion markers, final results and the runner log.

CAPABILITIES:
  CAP-RUN-006: write_shard() writes a shard's results atomically, then its completion marker (plan ID, shard index, results SHA-256, bytes and rows, finished UTC, duration, session and machine); shard_finished() counts a shard as finished only when its marker parses, names this plan and shard, and matches the results file's SHA-256 and size, and otherwise says why not [tests: test_FR_0_5_05_shard_results_written_atomically_with_marker, test_FR_0_5_05_results_without_marker_not_finished, test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished, test_FR_0_5_06_kill_during_result_write_never_counts]
INPUTS AND OUTPUTS: a run folder and shard results in; files in the run folder out.
CONTRACTS: run folder layout in docs/runner/RUNNER.md.
INVARIANTS:
  - The results file is written before its marker; a results file without a valid marker never counts.
  - Every write goes through aqis_lab.drive (atomic, and only under MyDrive/AQIS_LAB on Drive).
NOT IN SCOPE:
  - Deciding which shards to run (aqis_lab/runner/run.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
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
MARKER_VERSION = "1.0"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def shard_stem(index):
    return f"shard-{index:05d}"


def results_path(run_dir, index):
    return Path(run_dir) / SHARDS / f"{shard_stem(index)}.jsonl"


def marker_path(run_dir, index):
    return Path(run_dir) / SHARDS / f"{shard_stem(index)}.done.json"


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path, value, system=None, exclusive=False):
    data = json_bytes(value)
    drive.write_bytes(path, data, system, exclusive=exclusive)
    if json.loads(Path(path).read_text(encoding="utf-8")) != value:
        raise OSError(f"{path} does not read back as written")


def write_shard(run_dir, index, data, rows, plan_id, session, machine, duration_ns, system=None):
    """Write the shard's results atomically, then its marker; returns the marker."""
    target = drive.write_bytes(results_path(run_dir, index), data, system)
    if target.read_bytes() != data:
        raise OSError(f"{target} does not read back as written")
    marker = {"marker_version": MARKER_VERSION, "plan_id": plan_id, "shard": index,
              "results_file": target.name, "results_sha256": hashlib.sha256(data).hexdigest(),
              "results_bytes": len(data), "rows": rows, "finished_utc": utc_now(), "duration_ns": duration_ns,
              "session": session, "machine": machine}
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
    return True, marker


def append_log(run_dir, message, system=None):
    """Append one UTC-stamped line to runner.log; returns the line."""
    line = f"{utc_now()} {message}"
    drive.append_bytes(Path(run_dir) / LOG, (line + "\n").encode("utf-8"), system)
    return line
