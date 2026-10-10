"""Shared records and exit codes for relay runs.

CAPABILITIES:
  CAP-OUTSOURCING-RECORDS: Shared records and exit codes for relay runs [tests: test_records.py, test_acceptance_wo_1_0_02.py]
INPUTS AND OUTPUTS: Relay options, step parts, requests, check results, step records, outcomes, and exit codes.
CONTRACTS: none.
INVARIANTS:
  - Relay records are immutable frozen dataclasses.
NOT IN SCOPE:
  - Network transport or process execution.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tools.outsourcing.chat import ChatRequest

__all__ = [
    "Result",
    "RelayOptions",
    "StepPart",
    "Request",
    "CheckResult",
    "CheckResults",
    "StepRecord",
    "StepOutcome",
    "RelayOutcome",
]


class Result(Enum):
    ACCEPTED = 0
    INVALID = 2
    QUESTIONS = 4
    CUT_OFF = 5
    SECRET = 6
    CREDENTIAL = 7
    EXHAUSTED = 8
    INTEGRITY = 9
    NETWORK = 10
    PAUSED_DAILY = 11
    PAUSED_BUSY = 12
    TOO_LARGE = 13
    GIT = 14

    @property
    def exit_code(self) -> int:
        return self.value

    @property
    def display_name(self) -> str:
        return self.name.replace("_", "-")


@dataclass(frozen=True)
class RelayOptions:
    wo: str
    attempts: int
    api_base: str
    timeout: int
    verify_timeout: int
    pool: str
    dry_run: bool
    status: bool
    models: tuple[str, ...]
    restart: bool
    pack_step: str | None = None
    out: str | None = None
    no_push: bool = False


@dataclass(frozen=True)
class StepPart:
    label: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Request:
    chat: ChatRequest
    sent_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]
    characters: int


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    summary: str
    log_path: Path
    output_paths: tuple[str, ...]
    integrity: bool


@dataclass(frozen=True)
class CheckResults:
    results: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def integrity_failed(self) -> bool:
        return any(r.integrity and not r.passed for r in self.results)


@dataclass(frozen=True)
class StepRecord:
    label: str
    files: tuple[tuple[str, str], ...]
    attempts: int
    model: str
    provider: str
    model_version: str
    prompt_tokens: int
    output_tokens: int
    seconds_waited: float


@dataclass(frozen=True)
class StepOutcome:
    result: Result
    step_record: StepRecord | None = None
    stop_reason: str | None = None


@dataclass(frozen=True)
class RelayOutcome:
    result: Result
    accepted_parts: tuple[StepRecord, ...] = ()
    stop_reason: str | None = None
