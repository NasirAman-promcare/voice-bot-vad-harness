"""Run cards for runner runs: pack, task, machine, seed, lock and code, validated against run-card v1.

CAPABILITIES:
  CAP-RUN-004: build_run_card() fills every run-card v1 field (pack manifest ID, version and canonical SHA-256; the task's model block; empty processing steps; the task's mode (batch for clip-stats); the machine block from aqis_lab.platform; seed; the task's normaliser (null for clip-stats and the VAD); the lock the environment was installed from (aqis_lab.locks: phase0.txt, or phase0-gpu.txt with the GPU extras) and its SHA-256; the full git commit and dirty flag of this checkout), computes run_card_id and validates the card; card_differences() lists the JSON Pointers where two cards differ [tests: test_FR_0_5_05_run_card_valid_and_traceable, test_FR_0_5_05_changed_card_or_plan_refused]
INPUTS AND OUTPUTS: a task, a staged pack, a seed, notes and a machine block in; a run card dict out.
CONTRACTS: run-card v1 (docs/contracts/RUN_CARD.md).
INVARIANTS:
  - The card is validated before it is returned; an invalid card is never written.
  - "dirty" follows the rule of the version command (tracked changes or untracked files that are not ignored).
NOT IN SCOPE:
  - Deciding whether a stored card may be resumed (aqis_lab/runner/run.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
  2026-09-28 WP-0.5 NFR-0.5-01: git_state asks git twice instead of four times (same rules).
  2026-09-30 WP-0.7 FR-0.7-07: build_run_card takes mode and normaliser from the task and the lock from
    aqis_lab.locks (a clip-stats card in a CPU environment is unchanged).
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from aqis_lab import locks
from aqis_lab.commands.version import VersionInfoError, _git
from aqis_lab.contracts.canonical import compute_run_card_id
from aqis_lab.contracts.validate import validate_run_card

LOCK_REL = "requirements/aqis_lab/phase0.txt"
REPO_ROOT = Path(__file__).resolve().parents[2]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def git_state(root=REPO_ROOT):
    """{"commit": full hash, "dirty": bool} of the checkout holding this package (the version command's rules)."""
    toplevel, commit = _git(root, "rev-parse", "--show-toplevel", "HEAD").splitlines()
    if Path(toplevel).resolve() != Path(root).resolve():
        raise VersionInfoError(f"{root} is inside the git checkout {toplevel} but is not its top level")
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=normal"))
    return {"commit": commit, "dirty": dirty}


def build_run_card(task, staged, seed, notes, machine, root=REPO_ROOT):
    lock_rel = locks.installed_lock(root)
    card = {
        "schema_version": "1.0",
        "pack": {"manifest_id": staged.manifest["manifest_id"], "version": staged.manifest["version"],
                 "sha256": staged.manifest_sha256},
        "model": task.model_block(),
        "processing": {"vad": [], "stt": [], "emotion": []},
        "mode": task.mode,
        "machine": machine,
        "seed": seed,
        "normaliser": task.normaliser_block(),
        "lock": {"file": lock_rel, "sha256": hashlib.sha256((Path(root) / lock_rel).read_bytes()).hexdigest()},
        "git": git_state(root),
        "created_utc": utc_now(),
        "notes": notes,
    }
    card["run_card_id"] = compute_run_card_id(card)
    validate_run_card(card)
    return card


def card_differences(a, b, prefix=""):
    """Sorted JSON Pointers where the two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            pointer = f"{prefix}/{key}"
            if key not in a or key not in b:
                out.append(pointer)
            else:
                out += card_differences(a[key], b[key], pointer)
        return out
    return [] if a == b and type(a) is type(b) else [prefix or "/"]
