"""Read-only tests for FIX-2 of WO-1.0-10 (FR-1.0-14), written by Claude from the review of FIX-1.

- B7: every classification row and every retry-delay form the order names. FIX-1 asked for unit tests covering
  them, but few were added, so these tests pin them directly; each expected value is the order's own row.
- Foundation standard 10: every module of the order stays within the 400-line hard limit (governor.py had 531).
- B6 and B23: `wait_for_provider` never sleeps while holding the state lock, so other processes are not blocked.
"""
from __future__ import annotations

import fcntl
import json
import random
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    ROOT, SimClock, governor_for, local_only, mod, model, provider, write_pool)

FIXED_MODULES = ("chat", "limits", "quota", "governor", "gemini_client", "openai_client")


def gemini_body(code: int, status: str, details: list) -> str:
    return json.dumps({"error": {"code": code, "status": status, "message": "scratch", "details": details}})


def quota_failure(quota_id: str, value: str) -> dict:
    return {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": quota_id, "quotaValue": value}]}


def openai_body(message: str, code: str = "") -> str:
    return json.dumps({"error": {"message": message, "type": "rate_limit", "code": code}})


CLASSIFY_ROWS = [
    ("gemini", 429, {}, gemini_body(429, "RESOURCE_EXHAUSTED", [quota_failure("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "0")]), "NO_QUOTA", None),
    ("gemini", 429, {}, gemini_body(429, "RESOURCE_EXHAUSTED", [quota_failure("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "20")]), "DAILY", None),
    ("gemini", 429, {}, gemini_body(429, "RESOURCE_EXHAUSTED", [quota_failure("GenerateContentInputTokensPerModelPerMinute-FreeTier", "250000")]), "MINUTE_TOKENS", None),
    ("gemini", 429, {}, gemini_body(429, "RESOURCE_EXHAUSTED", [quota_failure("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "5")]), "MINUTE_REQUESTS", None),
    ("gemini", 429, {}, gemini_body(429, "RESOURCE_EXHAUSTED", []), "OVERLOADED", None),
    ("gemini", 429, {}, "<html>busy</html>", "OVERLOADED", None),
    ("gemini", 400, {}, gemini_body(400, "INVALID_ARGUMENT", [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]), "CREDENTIAL", None),
    ("openai", 429, {}, openai_body("Monthly token limit reached"), "MONTHLY", "provider"),
    ("openai", 429, {}, openai_body("Daily request limit reached for this model"), "DAILY", "model"),
    ("openai", 429, {}, openai_body("Daily free-request allowance for your account is used up"), "DAILY", "provider"),
    ("openai", 429, {"Retry-After": "7200"}, openai_body("Too many requests"), "DAILY", None),
    ("openai", 429, {}, openai_body("Rate limit exceeded: tokens per minute"), "MINUTE_TOKENS", None),
    ("openai", 429, {}, openai_body("Rate limit exceeded"), "MINUTE_REQUESTS", None),
    ("openai", 429, {"Retry-After": "12"}, "not json", "MINUTE_REQUESTS", None),
    ("openai", 402, {}, openai_body("Payment required"), "NO_QUOTA", None),
]
BOTH_ROWS = [
    (400, openai_body("This model's maximum context length is 128000 tokens"), "TOO_LARGE"),
    (413, openai_body("Request entity too large: size limit"), "TOO_LARGE"),
    (422, openai_body("Input length exceeds the limit"), "TOO_LARGE"),
    (401, openai_body("Unauthorized"), "CREDENTIAL"),
    (403, openai_body("Forbidden"), "CREDENTIAL"),
    (404, openai_body("Model not found"), "MODEL"),
    (500, openai_body("Internal error"), "SERVER_ERROR"),
    (502, "bad gateway", "OVERLOADED"),
    (503, gemini_body(503, "UNAVAILABLE", []), "OVERLOADED"),
    (504, "gateway timeout", "OVERLOADED"),
    (529, "overloaded", "OVERLOADED"),
    (418, "short and stout", "OTHER"),
]


@pytest.mark.parametrize("api, status, headers, body, kind, scope", CLASSIFY_ROWS,
                         ids=[f"{r[0]}-{r[1]}-{r[4]}-{i}" for i, r in enumerate(CLASSIFY_ROWS)])
def test_FR_1_0_14_fix02_classification_rows(api, status, headers, body, kind, scope):
    verdict = mod("quota").classify(api, status, headers, body)
    assert verdict.kind == kind
    if scope is not None:
        assert verdict.scope == scope


@pytest.mark.parametrize("api", ["gemini", "openai"])
@pytest.mark.parametrize("status, body, kind", BOTH_ROWS, ids=[f"{r[0]}-{r[2]}" for r in BOTH_ROWS])
def test_FR_1_0_14_fix02_classification_rows_for_both_shapes(api, status, body, kind):
    assert mod("quota").classify(api, status, {}, body).kind == kind


@pytest.mark.parametrize("api, headers, details, seconds", [
    ("gemini", {}, [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}], 37.0),
    ("gemini", {}, [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1.5s"}], 1.5),
    ("openai", {"Retry-After": "120"}, None, 120.0),
    ("openai", {"Retry-After": "HTTP-DATE+90"}, None, 90.0),  # built inside the test, relative to the wall clock
    ("openai", {"x-ratelimit-reset-requests": "1m30s"}, None, 90.0),
    ("openai", {"x-ratelimit-reset-tokens": "45s"}, None, 45.0),
], ids=["retryinfo-37s", "retryinfo-1.5s", "retry-after-seconds", "retry-after-http-date", "reset-requests-1m30s",
        "reset-tokens-45s"])
def test_FR_1_0_14_fix02_retry_delay_forms(api, headers, details, seconds, monkeypatch):
    if headers.get("Retry-After") == "HTTP-DATE+90":
        headers = {"Retry-After": format_datetime(datetime.now(timezone.utc) + timedelta(seconds=90), usegmt=True)}
    body = (gemini_body(429, "RESOURCE_EXHAUSTED", [quota_failure("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "5")] + details)
            if api == "gemini" else openai_body("Rate limit exceeded"))
    verdict = mod("quota").classify(api, 429, headers, body)
    assert verdict.kind == "MINUTE_REQUESTS"
    if "Retry-After" in headers and not headers["Retry-After"].isdigit():
        # An HTTP date is relative to the wall clock; allow the seconds between building the header and classifying.
        assert verdict.retry_delay is not None and seconds - 5 <= verdict.retry_delay <= seconds
    else:
        assert verdict.retry_delay == pytest.approx(seconds)


@pytest.mark.parametrize("name", FIXED_MODULES)
def test_FR_1_0_14_fix02_modules_within_400_lines(name):
    lines = (ROOT / "tools" / "outsourcing" / f"{name}.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 400


def test_FR_1_0_14_fix02_wait_for_provider_never_sleeps_holding_the_lock(tmp_path):
    providers = {"gemini": provider("gemini"), "mistral": provider("openai", rps=0.5)}
    state = tmp_path / ".relay/governor.json"
    clock = SimClock()
    held_while_sleeping: list[bool] = []

    def probing_sleeper(seconds: float) -> None:
        with open(state.parent / f"{state.name}.lock", "a+") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(probe, fcntl.LOCK_UN)
                held_while_sleeping.append(False)
            except BlockingIOError:
                held_while_sleeping.append(True)
        clock.sleep(seconds)

    pool = mod("limits").load_pool(write_pool(tmp_path, {"m-a": model("mistral", 1)}, providers))
    gov = mod("governor").Governor(pool, state, clock, probing_sleeper, random.Random(3))
    gov.wait_for_provider("mistral")
    gov.wait_for_provider("mistral")
    assert held_while_sleeping == [False]
