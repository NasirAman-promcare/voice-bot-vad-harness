"""Classify HTTP error responses for Gemini and OpenAI API shapes.

CAPABILITIES:
  CAP-OUTSOURCING-QUOTA: Rejection classification for Gemini and OpenAI responses. [tests: test_quota, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Accepts API shape, HTTP status, headers, and body text; returns QuotaVerdict.
CONTRACTS: none.
INVARIANTS:
  - Classification order follows specification B7.
NOT IN SCOPE:
  - Network execution or retry sleeping.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import email.utils
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class QuotaVerdict:
    kind: str  # NO_QUOTA, DAILY, MONTHLY, MINUTE_TOKENS, MINUTE_REQUESTS, OVERLOADED, CREDENTIAL, TOO_LARGE, MODEL, SERVER_ERROR, OTHER
    retry_delay: float | None
    scope: str  # model, provider
    server_limit_value: int | None = None
    reset_time: datetime | None = None
    message: str = ""


def _parse_duration(val: str | None) -> float | None:
    if not val:
        return None
    val = val.strip()
    if not val:
        return None

    # Try numeric seconds
    try:
        return float(val)
    except ValueError:
        pass

    # Try "37s" or "1.5s"
    if val.endswith("s") and not val.endswith("ms"):
        try:
            return float(val[:-1])
        except ValueError:
            pass

    # Try "1m30s" or "2m" or "1h"
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?$", val)
    if m and any(m.groups()):
        h = float(m.group(1) or 0)
        mins = float(m.group(2) or 0)
        s = float(m.group(3) or 0)
        return h * 3600 + mins * 60 + s

    # Try HTTP date
    try:
        dt = email.utils.parsedate_to_datetime(val)
        if dt:
            now = datetime.now(timezone.utc)
            delta = (dt - now).total_seconds()
            return max(0.0, delta)
    except Exception:
        pass

    return None


def _extract_retry_delay(
    headers_lower: dict[str, str], details: list[dict]
) -> float | None:
    # 1. From RetryInfo in Gemini details
    for d in details:
        if isinstance(d, dict) and d.get("@type", "").endswith("RetryInfo"):
            delay_str = d.get("retryDelay")
            parsed = _parse_duration(str(delay_str) if delay_str else None)
            if parsed is not None:
                return parsed

    # 2. From Retry-After header
    if "retry-after" in headers_lower:
        parsed = _parse_duration(headers_lower["retry-after"])
        if parsed is not None:
            return parsed

    # 3. From x-ratelimit-reset-requests or x-ratelimit-reset-tokens
    for h in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        if h in headers_lower:
            parsed = _parse_duration(headers_lower[h])
            if parsed is not None:
                return parsed

    return None


def classify(
    api: str,
    status: int,
    headers: dict[str, str] | None,
    body_text: str,
) -> QuotaVerdict:
    headers_lower = {k.lower(): v for k, v in (headers or {}).items()}

    # Try JSON parse
    body_json = None
    if body_text:
        try:
            body_json = json.loads(body_text)
        except Exception:
            pass

    details: list[dict] = []
    error_obj = {}
    err_msg = ""
    err_code = ""
    err_status = ""

    if isinstance(body_json, dict):
        error_obj = body_json.get("error", {})
        if isinstance(error_obj, dict):
            err_msg = str(error_obj.get("message", "")).lower()
            err_code = str(error_obj.get("code", "")).lower()
            err_status = str(error_obj.get("status", "")).lower()
            details = error_obj.get("details", [])
            if not isinstance(details, list):
                details = []
        elif isinstance(error_obj, str):
            err_msg = error_obj.lower()
    elif body_text:
        err_msg = body_text.lower()

    retry_delay = _extract_retry_delay(headers_lower, details)

    # E5: Non-JSON 429
    if status == 429 and body_json is None:
        if api == "gemini":
            return QuotaVerdict("OVERLOADED", retry_delay, "model", message=body_text)
        else:
            return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", message=body_text)

    # Gemini 400 API_KEY_INVALID
    if api == "gemini" and status == 400:
        for d in details:
            if isinstance(d, dict) and d.get("reason") == "API_KEY_INVALID":
                return QuotaVerdict("CREDENTIAL", retry_delay, "provider", message=err_msg)

    # Gemini 429
    if api == "gemini" and status == 429:
        quota_failure = None
        for d in details:
            if isinstance(d, dict) and d.get("@type", "").endswith("QuotaFailure"):
                quota_failure = d
                break

        if quota_failure:
            violations = quota_failure.get("violations", [])
            for v in violations:
                if isinstance(v, dict):
                    q_val_raw = v.get("quotaValue", "")
                    q_val = None
                    try:
                        q_val = int(q_val_raw)
                    except ValueError:
                        pass

                    q_id = str(v.get("quotaId", ""))

                    if q_val_raw == "0" or q_val == 0:
                        return QuotaVerdict("NO_QUOTA", retry_delay, "model", server_limit_value=0, message=err_msg)
                    if "PerDay" in q_id:
                        return QuotaVerdict("DAILY", retry_delay, "model", server_limit_value=q_val, message=err_msg)
                    if "PerMinute" in q_id and "Token" in q_id:
                        return QuotaVerdict("MINUTE_TOKENS", retry_delay, "model", server_limit_value=q_val, message=err_msg)
                    if "PerMinute" in q_id and "Request" in q_id:
                        return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", server_limit_value=q_val, message=err_msg)

        return QuotaVerdict("OVERLOADED", retry_delay, "model", message=err_msg)

    # OpenAI 429 & 402
    if api == "openai":
        if status == 402:
            return QuotaVerdict("NO_QUOTA", retry_delay, "model", message=err_msg)

        if status == 429:
            combined = f"{err_msg} {err_code}"

            # Server limit headers
            s_limit = None
            if "x-ratelimit-limit-requests" in headers_lower:
                try:
                    s_limit = int(headers_lower["x-ratelimit-limit-requests"])
                except ValueError:
                    pass

            if "month" in combined or "monthly" in combined:
                return QuotaVerdict("MONTHLY", retry_delay, "provider", server_limit_value=s_limit, message=err_msg)

            if (
                "day" in combined
                or "daily" in combined
                or "used up" in combined
                or (retry_delay is not None and retry_delay > 3600)
            ):
                scope = "provider" if any(w in combined for w in ("account", "allowance", "daily limit", "used up")) else "model"
                return QuotaVerdict("DAILY", retry_delay, scope, server_limit_value=s_limit, message=err_msg)

            if "token" in combined or "tokens" in combined:
                if "x-ratelimit-limit-tokens" in headers_lower:
                    try:
                        s_limit = int(headers_lower["x-ratelimit-limit-tokens"])
                    except ValueError:
                        pass
                return QuotaVerdict("MINUTE_TOKENS", retry_delay, "model", server_limit_value=s_limit, message=err_msg)

            return QuotaVerdict("MINUTE_REQUESTS", retry_delay, "model", server_limit_value=s_limit, message=err_msg)

    # Common statuses
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
