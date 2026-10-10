"""Provider-neutral request and reply records and exceptions.

CAPABILITIES:
  CAP-OUTSOURCING-CHAT: Provider-neutral records and exceptions for model clients. [tests: test_limits, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Turns, requests, token counts, replies, and client exceptions.
CONTRACTS: none.
INVARIANTS:
  - Chat records are immutable frozen dataclasses.
NOT IN SCOPE:
  - Transport or protocol specific details.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Turn:
    role: str
    text: str


@dataclass(frozen=True)
class ChatRequest:
    system: str
    turns: tuple[Turn, ...]
    max_output_tokens: int


@dataclass(frozen=True)
class TokenCount:
    value: int
    estimated: bool = False


@dataclass(frozen=True)
class Reply:
    text: str
    finish: str
    prompt_tokens: int
    output_tokens: int
    block_reason: str | None = None
    prompt_estimated: bool = False
    output_estimated: bool = False
    seconds_waited: float = 0.0
    model: str = ""
    model_version: str = ""
    raw_json: str = ""


class DailyQuotaExhausted(Exception):
    """Raised when a daily or monthly quota is exhausted."""

    def __init__(
        self,
        model: str,
        provider: str,
        period: str,
        quota_value: int | None,
        reset_utc: datetime,
        reset_provider: datetime,
        reset_karachi: datetime,
        message: str = "",
    ) -> None:
        msg = message or f"Quota exhausted for {model} ({provider}) for period {period}"
        super().__init__(msg)
        self.model = model
        self.provider = provider
        self.period = period
        self.quota_value = quota_value
        self.reset_utc = reset_utc
        self.reset_provider = reset_provider
        self.reset_karachi = reset_karachi


class ServiceBusy(Exception):
    """Raised when retries on rate limits or service busy are exhausted."""


class StepTooLarge(Exception):
    """Raised when a request exceeds max input tokens or TPM limits."""


class CredentialError(Exception):
    """Raised on authentication or credential failures (e.g. invalid API key)."""


class ModelError(Exception):
    """Raised on model configuration errors or missing quota tier."""


class ApiError(Exception):
    """Raised on unclassified API error response."""


class TransportError(Exception):
    """Raised on network transport failures after retries."""
