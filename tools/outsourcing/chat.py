"""Provider-neutral request and reply records and exceptions.

CAPABILITIES:
  CAP-OUTSOURCING-CHAT: Provider-neutral records and exceptions for model clients.
    [tests: test_load_pool_valid, test_load_pool_disabled_provider, test_load_pool_invalid_keys, test_candidates,
    test_effective_limits, test_next_reset, test_FR_1_0_14_mc03_gemini_daily_rejection_stops_at_once_with_resets,
    test_FR_1_0_14_mc03_provider_scope_daily_marks_every_model_of_the_provider,
    test_FR_1_0_14_mc03_monthly_rejection_marks_provider_until_next_month,
    test_FR_1_0_14_mc04_six_minute_rejections_raise_service_busy,
    test_FR_1_0_14_mc05_overload_backs_off_exponentially_then_service_busy,
    test_FR_1_0_14_mc06_over_max_input_tokens_is_not_sent_gemini,
    test_FR_1_0_14_mc06_over_whole_minute_allowance_is_not_sent,
    test_FR_1_0_14_mc06_openai_estimate_over_limit_is_not_sent,
    test_FR_1_0_14_mc06_minute_token_rejection_above_server_limit_is_not_retried,
    test_FR_1_0_14_mc09_quota_value_zero_raises_model_error_without_retry,
    test_FR_1_0_14_mc09_http_402_raises_model_error_without_retry,
    test_FR_1_0_14_mc10_credential_and_unclassified_errors_are_not_retried]
INPUTS AND OUTPUTS:
  Turns, requests, token counts, replies, and client exceptions.
CONTRACTS: none.
INVARIANTS:
  - Chat records are immutable frozen dataclasses.
NOT IN SCOPE:
  - Transport or protocol specific details.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
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
