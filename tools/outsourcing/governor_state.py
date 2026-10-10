"""The governor's records, its state file and the lock that makes every read-modify-write atomic across processes.

CAPABILITIES:
  CAP-OUTSOURCING-GOVSTATE: persisted per-model and per-provider pacing state under an exclusive file lock
    [tests: test_FR_1_0_14_fix01_parallel_processes_lose_no_update, test_FR_1_0_14_mc07_restart_keeps_window_and_counts,
     test_FR_1_0_14_fix02_wait_for_provider_never_sleeps_holding_the_lock]
INPUTS AND OUTPUTS: the governor's in-memory stats in, `.relay/governor.json` out (and back); report records.
CONTRACTS: none.
INVARIANTS:
  - The state file is replaced atomically (scratch file, then rename) while the caller holds `FileLock`.
  - Starts older than 60 seconds are dropped on load; learned limits are always kept (WO-1.0-10 B6, E2).
  - A corrupt or unreadable state file is reported to the caller, never treated as empty data (E3).
NOT IN SCOPE:
  - Pacing decisions, counting and classification (governor.py, quota.py).
CHANGE LOG:
  2026-10-10 WO-1.0-10 created (records and persistence inside governor.py).
  2026-10-10 WP-1.0 FR-1.0-14 FIX-2 (Claude): moved here from governor.py, unchanged in behaviour, so that
    governor.py stays within the Foundation's 400-line limit.
"""
from __future__ import annotations

import fcntl
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TextIO

__all__ = ["FileLock", "ModelStats", "ProviderStats", "ModelReport", "ProviderReport", "GovernorReport",
           "load_stats", "save_stats"]

WINDOW_SECONDS = 60.0


class FileLock:
    """Exclusive `flock` on a lock file next to the state file, held for one read-modify-write."""

    def __init__(self, lock_file: Path) -> None:
        self.lock_file = lock_file
        self._fd: TextIO | None = None

    def __enter__(self) -> FileLock:
        self._fd = open(self.lock_file, "a+")
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None


@dataclass
class ModelStats:
    adaptive_factor: float = 1.0
    consecutive_successes: int = 0
    requests: int = 0
    retries: dict[str, int] = field(default_factory=dict)
    seconds_waited: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    cooldown_until: float = 0.0
    exhausted_until: float | None = None
    learned_limits: dict[str, int] = field(default_factory=dict)
    starts: list[tuple[float, int]] = field(default_factory=list)
    daily_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ProviderStats:
    requests: int = 0
    retries: dict[str, int] = field(default_factory=dict)
    seconds_waited: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    cooldown_until: float = 0.0
    exhausted_until: float | None = None
    learned_limits: dict[str, int] = field(default_factory=dict)
    starts: list[tuple[float, int]] = field(default_factory=list)
    daily_counts: dict[str, int] = field(default_factory=dict)
    monthly_tokens: dict[str, int] = field(default_factory=dict)


@dataclass
class ModelReport:
    adaptive_factor: float
    requests: int
    retries: dict[str, int]
    seconds_waited: float
    prompt_tokens: int
    output_tokens: int
    effective_limits: dict
    learned_limits: dict
    count_today: int
    daily_limit: int | None
    cooldown_end: float | None
    exhausted_until: datetime | None


@dataclass
class ProviderReport:
    requests: int
    retries: dict[str, int]
    seconds_waited: float
    prompt_tokens: int
    output_tokens: int
    monthly_tokens: int
    unverified: bool


@dataclass
class GovernorReport:
    models: dict[str, ModelReport]
    providers: dict[str, ProviderReport]
    unverified_providers: list[str]
    corrupt_state: bool = False


def _recent(starts: list, now: float) -> list[tuple[float, int]]:
    return [(t, tok) for t, tok in starts if now - t < WINDOW_SECONDS]


def _apply_models(models_data: dict, model_stats: dict[str, ModelStats], now: float) -> None:
    for name, md in models_data.items():
        if name not in model_stats:
            continue
        ms = model_stats[name]
        ms.adaptive_factor = md.get("adaptive_factor", 1.0)
        ms.consecutive_successes = md.get("consecutive_successes", 0)
        ms.cooldown_until = md.get("cooldown_until", 0.0)
        ms.exhausted_until = md.get("exhausted_until")
        ms.learned_limits = md.get("learned_limits", {})
        ms.starts = _recent(md.get("starts", []), now)
        ms.daily_counts = md.get("daily_counts", {})


def _apply_providers(providers_data: dict, provider_stats: dict[str, ProviderStats], now: float) -> None:
    for name, pd in providers_data.items():
        if name not in provider_stats:
            continue
        ps = provider_stats[name]
        ps.cooldown_until = pd.get("cooldown_until", 0.0)
        ps.exhausted_until = pd.get("exhausted_until")
        ps.learned_limits = pd.get("learned_limits", {})
        ps.starts = _recent(pd.get("starts", []), now)
        ps.daily_counts = pd.get("daily_counts", {})
        ps.monthly_tokens = pd.get("monthly_tokens", {})


def load_stats(state_path: Path, model_stats: dict[str, ModelStats], provider_stats: dict[str, ProviderStats],
               now: float) -> bool:
    """Load the state file into the stats; return False when it exists but cannot be read or parsed (E3)."""
    if not state_path.exists():
        return True
    try:
        text = state_path.read_text(encoding="utf-8")
        data = json.loads(text) if text.strip() else {}
    except (OSError, ValueError):
        return False
    _apply_models(data.get("models", {}), model_stats, now)
    _apply_providers(data.get("providers", {}), provider_stats, now)
    return True


def save_stats(state_path: Path, model_stats: dict[str, ModelStats], provider_stats: dict[str, ProviderStats]) -> None:
    """Write the persisted fields of B6 atomically; the caller holds the lock."""
    data = {
        "models": {name: {"adaptive_factor": ms.adaptive_factor, "consecutive_successes": ms.consecutive_successes,
                          "cooldown_until": ms.cooldown_until, "exhausted_until": ms.exhausted_until,
                          "learned_limits": ms.learned_limits, "starts": ms.starts, "daily_counts": ms.daily_counts}
                   for name, ms in model_stats.items()},
        "providers": {name: {"cooldown_until": ps.cooldown_until, "exhausted_until": ps.exhausted_until,
                             "learned_limits": ps.learned_limits, "starts": ps.starts,
                             "daily_counts": ps.daily_counts, "monthly_tokens": ps.monthly_tokens}
                      for name, ps in provider_stats.items()},
    }
    scratch = state_path.parent / f"{state_path.name}.tmp"
    scratch.write_text(json.dumps(data, indent=2), encoding="utf-8")
    scratch.replace(state_path)
