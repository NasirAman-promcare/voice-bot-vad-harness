"""Classify HTTP error responses for Gemini and OpenAI API shapes.

CAPABILITIES:
  CAP-OUTSOURCING-QUOTA: Rejection classification for Gemini and OpenAI responses.
    [tests: test_classify_gemini_quota_failure, test_classify_gemini_zero_quota,
    test_classify_openai_daily_and_monthly, test_classify_common_errors, test_non_json_429]
INPUTS AND OUTPUTS:
  Accepts API shape, HTTP status, headers, and body text; returns QuotaVerdict.
CONTRACTS: none.
INVARIANTS:
  - Classification order follows specification B7.
NOT IN SCOPE:
  - Network execution or retry sleeping.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

import email.utils
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class QuotaVerdict:
    kind: str
    retry_delay: float | None
    scope: str
    server_limit_value: int | None = None
    reset_time: datetime | None = None
    message: str = ""


def _parse_duration(val: str | None) -> float | None:
    if not val:
        return None
    s_val = val.strip()
    if not s_val:
        return None

    try:
        return float(s_val)
    except (ValueError, TypeError):
        err = None

    if s_val.endswith("s") and not s_val.endswith("ms"):
        try:
            return float(s_val[:-1])
        except (ValueError, TypeError):
            err = None

    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?$", s_val)
    if m and any(m.groups()):
        h = float(m.group(1) or 0)
        mins = float(m.group(2) or 0)
        secs = float(m.group(3) or 0)
        return h * 3600.0 + mins * 60.0 + secs

    try:
        dt = email.utils.parsedate_to_datetime(s_val)
        if dt is not None:
            now = datetime.now(timezone.utc)
            return max(0.0, (dt - now).total_seconds())
    except (ValueError, TypeError, OverflowError):
        err = None

    return None


def _extract_retry_delay(
    headers_lower: dict[str, str], details: list[dict]
) -> float | None:
    for d in details:
        if isinstance(d, dict) and str(d.get("@type", "")).endswith("RetryInfo"):
            delay_str = d.get("retryDelay")
            parsed = _parse_duration(str(delay_str) if delay_str is not None else None)
            if parsed is not None:
                return parsed

    if "retry-after" in headers_lower:
        parsed = _parse_duration(headers_lower["retry-after"])
        if parsed is not None:
            return parsed

    for h in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        if h in headers_lower:
            parsed = _parse_duration(headers_lower[h])
            if parsed is not None:
                return parsed

    return None


def _parse_body(body_text: str) -> tuple[dict | None, list[dict], str, str, str]:
    body_json = None
    if body_text:
        try:
            parsed = json.loads(body_text)
            if isinstance(parsed, dict):
                body_json = parsed
        except (json.JSONDecodeError, ValueError, TypeError):
            err = None

    details: list[dict] = []
    err_msg = body_text.lower() if body_text else ""
    err_code = ""
    err_status = ""

    if isinstance(body_json, dict):
        error_obj = body_json.get("error")
        if isinstance(error_obj, dict):
            err_msg = str(error_obj.get("message", "")).lower()
            err_code = str(error_obj.get("code", "")).lower()
            err_status = str(error_obj.get("status", "")).lower()
            raw_details = error_obj.get("details")
            if isinstance(raw_details, list):
                details = [d for d in raw_details if isinstance(d, dict)]
        elif isinstance(error_obj, str):
            err_msg = error_obj.lower()

    return body_json, details, err_msg, err_code, err_status


def _classify_gemini_violation(v: dict, err_msg: str, retry_delay: float | None) -> QuotaVerdict | None:
    q_val_raw = str(v.get("quotaValue", ""))
    q_val = None
    try:
        q_val = int(q_val_raw)
    except (ValueError, TypeError):
        q_val = None
    q_id = str(v.get("quotaId", ""))
    if q_val_raw == "0" or q_val == 0:
        return QuotaVerdict("NO_QUOTA", retry_delay, "model", server_limit_value=0, message=err_msg)
    if "PerDay" in q_id:
        return QuotaVerdict("DAILY", retry_delay, "model", server_limit_value=q_val, message=err_msg)
    if "PerMinute" in q_id and "Token" in q_id:
        return QuotaVerdict("MINUTE_TOKENS", retry_delay, "model", server_limit_value=q_val, message=err_msg)
    if "PerMinute" in q_id and "Request" in q_id:
        return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", server_limit_value=q_val, message=err_msg)
    return None


def _classify_gemini(
    status: int,
    details: list[dict],
    body_json: dict | None,
    err_msg: str,
    retry_delay: float | None,
    body_text: str,
) -> QuotaVerdict | None:
    if status == 400:
        for d in details:
            if isinstance(d, dict) and d.get("reason") == "API_KEY_INVALID":
                return QuotaVerdict("CREDENTIAL", retry_delay, "provider", message=err_msg)
        return None

    if status == 429:
        if body_json is None:
            return QuotaVerdict("OVERLOADED", retry_delay, "model", message=body_text)
        quota_failure = None
        for d in details:
            if isinstance(d, dict) and str(d.get("@type", "")).endswith("QuotaFailure"):
                quota_failure = d
                break
        if quota_failure:
            violations = quota_failure.get("violations", [])
            if isinstance(violations, list):
                for v in violations:
                    if isinstance(v, dict):
                        verdict = _classify_gemini_violation(v, err_msg, retry_delay)
                        if verdict is not None:
                            return verdict
        return QuotaVerdict("OVERLOADED", retry_delay, "model", message=err_msg)

    return None


def _classify_openai_429(
    err_msg: str,
    err_code: str,
    headers_lower: dict[str, str],
    retry_delay: float | None,
) -> QuotaVerdict:
    combined = f"{err_msg} {err_code}"
    s_limit_reqs = None
    if "x-ratelimit-limit-requests" in headers_lower:
        try:
            s_limit_reqs = int(headers_lower["x-ratelimit-limit-requests"])
        except (ValueError, TypeError):
            s_limit_reqs = None

    if "month" in combined or "monthly" in combined:
        return QuotaVerdict("MONTHLY", retry_delay, "provider", server_limit_value=s_limit_reqs, message=err_msg)

    if "day" in combined or "daily" in combined or "used up" in combined or (retry_delay is not None and retry_delay > 3600):
        scope = "provider" if any(w in combined for w in ("account", "allowance", "daily limit", "used up")) else "model"
        return QuotaVerdict("DAILY", retry_delay, scope, server_limit_value=s_limit_reqs, message=err_msg)

    if "token" in combined or "tokens" in combined:
        s_limit_tokens = None
        if "x-ratelimit-limit-tokens" in headers_lower:
            try:
                s_limit_tokens = int(headers_lower["x-ratelimit-limit-tokens"])
            except (ValueError, TypeError):
                s_limit_tokens = None
        return QuotaVerdict("MINUTE_TOKENS", retry_delay, "model", server_limit_value=s_limit_tokens, message=err_msg)

    return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", server_limit_value=s_limit_reqs, message=err_msg)


def _classify_openai(
    status: int,
    body_json: dict | None,
    err_msg: str,
    err_code: str,
    headers_lower: dict[str, str],
    retry_delay: float | None,
    body_text: str,
) -> QuotaVerdict | None:
    if status == 402:
        return QuotaVerdict("NO_QUOTA", retry_delay, "model", message=err_msg)

    if status == 429:
        if body_json is None:
            return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", message=body_text)
        return _classify_openai_429(err_msg, err_code, headers_lower, retry_delay)

    return None


def _classify_common(
    status: int,
    err_msg: str,
    err_status: str,
    retry_delay: float | None,
) -> QuotaVerdict:
    if status in (400, 413, 422):
        if any(w in err_msg for w in ("token", "tokens", "size", "length", "context")):
            return QuotaVerdict("TOO_LARGE", retry_delay, "model", message=err_msg)

    if status in (401, 403):
        return QuotaVerdict("CREDENTIAL", retry_delay, "provider", message=err_msg)

    if status == 404:
        return QuotaVerdict("MODEL", retry_delay, "model", message=err_msg)

    if status == 500:
        return QuotaVerdict("SERVER_ERROR", retry_delay, "model", message=err_msg)

    if status in (502, 503, 504, 529) or err_status == "unavailable" or "unavailable" in err_msg or "overloaded" in err_msg:
        return QuotaVerdict("OVERLOADED", retry_delay, "model", message=err_msg)

    return QuotaVerdict("OTHER", retry_delay, "model", message=err_msg or f"HTTP {status}")


def classify(
    api: str,
    status: int,
    headers: dict[str, str] | None,
    body_text: str,
) -> QuotaVerdict:
    headers_lower = {k.lower(): v for k, v in (headers or {}).items()}
    body_json, details, err_msg, err_code, err_status = _parse_body(body_text)
    retry_delay = _extract_retry_delay(headers_lower, details)

    if api == "gemini":
        v = _classify_gemini(status, details, body_json, err_msg, retry_delay, body_text)
        if v is not None:
            return v
    elif api == "openai":
        v = _classify_openai(status, body_json, err_msg, err_code, headers_lower, retry_delay, body_text)
        if v is not None:
            return v

    return _classify_common(status, err_msg, err_status, retry_delay)
