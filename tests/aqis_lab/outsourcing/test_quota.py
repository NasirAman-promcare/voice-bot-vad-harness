"""Unit tests for quota module.

CAPABILITIES:
  CAP-OUTSOURCING-QUOTA: Rejection classification for Gemini and OpenAI responses. [tests: test_quota]
INPUTS AND OUTPUTS:
  Tests classification logic for status codes, headers, and body structures.
CONTRACTS: none.
INVARIANTS:
  - Tests classify both Gemini and OpenAI API shapes.
NOT IN SCOPE:
  - Persistent state or live HTTP calls.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import json
from tools.outsourcing.quota import classify


def test_classify_gemini_quota_failure():
    body = json.dumps({
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
                            "quotaValue": "5",
                        }
                    ],
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "37s",
                },
            ],
        }
    })
    v = classify("gemini", 429, {}, body)
    assert v.kind == "MINUTE_REQUESTS"
    assert v.retry_delay == 37.0
    assert v.server_limit_value == 5


def test_classify_gemini_zero_quota():
    body = json.dumps({
        "error": {
            "code": 429,
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaValue": "0"}],
                }
            ],
        }
    })
    v = classify("gemini", 429, {}, body)
    assert v.kind == "NO_QUOTA"


def test_classify_openai_daily_and_monthly():
    body_monthly = json.dumps({"error": {"message": "Monthly limit reached"}})
    v_m = classify("openai", 429, {}, body_monthly)
    assert v_m.kind == "MONTHLY"
    assert v_m.scope == "provider"

    body_daily = json.dumps({"error": {"message": "Daily free-request allowance for your account is used up"}})
    v_d = classify("openai", 429, {}, body_daily)
    assert v_d.kind == "DAILY"
    assert v_d.scope == "provider"


def test_classify_common_errors():
    v_401 = classify("gemini", 401, {}, "Unauthorized")
    assert v_401.kind == "CREDENTIAL"

    v_404 = classify("openai", 404, {}, "Model not found")
    assert v_404.kind == "MODEL"

    v_503 = classify("gemini", 503, {}, "Service Unavailable")
    assert v_503.kind == "OVERLOADED"


def test_non_json_429():
    v_g = classify("gemini", 429, {}, "Too Many Requests")
    assert v_g.kind == "OVERLOADED"

    v_o = classify("openai", 429, {"Retry-After": "10"}, "Rate limit exceeded")
    assert v_o.kind == "MINUTE_REQUESTS"
    assert v_o.retry_delay == 10.0
