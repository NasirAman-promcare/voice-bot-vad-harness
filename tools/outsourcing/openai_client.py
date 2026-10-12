"""OpenAI-compatible chat completions API client with rate governor integration.

CAPABILITIES:
  CAP-OUTSOURCING-OPENAI-CLIENT: OpenAI-compatible model client with token counting, content generation, and model listing. [tests: test_openai_client, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Accepts ChatRequest; returns TokenCount or Reply; raises chat exceptions.
CONTRACTS: none.
INVARIANTS:
  - No API key sent in request headers or body (handled by proxy).
NOT IN SCOPE:
  - Local state persistence (handled by governor).
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-11 WP-1.0 FR-1.0-14 (Claude, owner's BLK-1.0-12 answer): the request carries the model's reasoning_effort,
    temperature and top_p when the pool sets them (DEC-1.0-08); the socket timeout is at least its timeout_seconds.
  2026-10-12 WP-1.0 FR-1.0-14 (Claude, BLK-1.0-14): the request asks for a stream with usage, because the session's
    egress path answers 502 to any reply slower than 30 seconds; an event-stream reply is assembled by `sse`, and a
    stream cut before its end is retried as a network error. A JSON reply is parsed as before.
"""
from __future__ import annotations

import http.client
import json
import math
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any

from tools.outsourcing import sse
from tools.outsourcing.chat import (
    ApiError, ChatRequest, CredentialError, DailyQuotaExhausted, ModelError,
    Reply, ServiceBusy, StepTooLarge, TokenCount, TransportError, Turn,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import ModelSpec, _la_offset, _resolve_tz, effective, monthly_reset, next_reset
from tools.outsourcing.quota import QuotaVerdict, classify

FINISH_MAP = {"stop": "STOP", "length": "MAX_TOKENS", "content_filter": "SAFETY"}


def _calc_char_tokens(request: ChatRequest) -> int:
    chars = len(request.system)
    for turn in request.turns:
        chars += len(turn.text)
    return math.ceil(chars / 3.5)


def _build_payload(spec: ModelSpec, request: ChatRequest) -> dict[str, Any]:
    messages = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    for turn in request.turns:
        messages.append({"role": turn.role, "content": turn.text})
    payload: dict[str, Any] = {"model": spec.name, "messages": messages,
                               "max_tokens": min(request.max_output_tokens, spec.max_output_tokens),
                               "stream": True, "stream_options": {"include_usage": True}}
    for key in ("reasoning_effort", "temperature", "top_p"):
        if getattr(spec, key) is not None:
            payload[key] = getattr(spec, key)
    return payload


def _check_learned_headers(spec: ModelSpec, governor: Governor, headers: dict[str, str]) -> None:
    headers_lower = {k.lower(): v for k, v in headers.items()}
    if "x-ratelimit-limit-requests" in headers_lower:
        try:
            val = int(headers_lower["x-ratelimit-limit-requests"])
            scope = "model" if spec.rpm is not None else ("provider" if spec.provider.rpm is not None else "model")
            governor.record_learned_limit(spec.name, "rpm", val, scope)
        except (ValueError, TypeError):
            err = None
    if "x-ratelimit-limit-tokens" in headers_lower:
        try:
            val = int(headers_lower["x-ratelimit-limit-tokens"])
            scope = "model" if spec.tpm_input is not None else ("provider" if spec.provider.tpm_input is not None else "model")
            governor.record_learned_limit(spec.name, "tpm_input", val, scope)
        except (ValueError, TypeError):
            err = None


def _raise_daily_exhausted(spec: ModelSpec, governor: Governor, verdict: QuotaVerdict) -> None:
    now = governor.clock()
    if verdict.reset_time is not None:
        reset_utc_dt = verdict.reset_time
    elif verdict.retry_delay is not None:
        reset_utc_dt = datetime.fromtimestamp(now + verdict.retry_delay, tz=timezone.utc)
    else:
        is_monthly = verdict.kind == "MONTHLY"
        res = monthly_reset(governor.pool, spec.provider, now) if is_monthly else next_reset(governor.pool, spec.provider, now)
        reset_utc_dt = res.reset_utc

    prov_tz, _ = _resolve_tz(spec.provider.day_reset)
    if prov_tz is None and spec.provider.day_reset == "America/Los_Angeles":
        reset_prov_dt = reset_utc_dt.astimezone(timezone(_la_offset(reset_utc_dt)))
    else:
        reset_prov_dt = reset_utc_dt.astimezone(prov_tz)

    try:
        karachi_tz: datetime.tzinfo = zoneinfo.ZoneInfo("Asia/Karachi")
    except zoneinfo.ZoneInfoNotFoundError:
        karachi_tz = timezone(timedelta(hours=5))
    reset_karachi_dt = reset_utc_dt.astimezone(karachi_tz)

    raise DailyQuotaExhausted(
        model=spec.name,
        provider=spec.provider.name,
        period="day" if verdict.kind == "DAILY" else "month",
        quota_value=verdict.server_limit_value,
        reset_utc=reset_utc_dt,
        reset_provider=reset_prov_dt,
        reset_karachi=reset_karachi_dt,
        message=verdict.message,
    )


def _raise_verdict_exception(
    spec: ModelSpec, governor: Governor, base_url: str, verdict: QuotaVerdict, input_tokens: int
) -> None:
    if verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
        learned_tpm = governor.model_stats[spec.name].learned_limits.get("tpm_input")
        m_tpm = learned_tpm or spec.tpm_input or spec.provider.tpm_input
        if verdict.kind == "MINUTE_TOKENS" and m_tpm and input_tokens > math.floor(m_tpm * governor.pool.safety):
            raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds per-minute token limit ({m_tpm})")
        raise ServiceBusy("Per-minute rate limits exhausted after retries")
    if verdict.kind == "OVERLOADED":
        raise ServiceBusy("Service overloaded after retries")
    if verdict.kind == "SERVER_ERROR":
        raise ServiceBusy("Server error after retries")
    if verdict.kind in ("DAILY", "MONTHLY"):
        _raise_daily_exhausted(spec, governor, verdict)
    if verdict.kind == "NO_QUOTA":
        raise ModelError(f"the {spec.provider.tier} tier gives {spec.name} no quota; remove it from the pool or enable billing")
    if verdict.kind == "TOO_LARGE":
        raise StepTooLarge(f"Request too large: {verdict.message}")
    if verdict.kind == "CREDENTIAL":
        raise CredentialError(f"Credential error for provider {spec.provider.name} at {base_url}")
    if verdict.kind == "MODEL":
        raise ModelError(f"Model error for {spec.name}: {verdict.message}")
    raise ApiError(f"API error: {verdict.message}")


def _handle_openai_retry(
    spec: ModelSpec, governor: Governor, verdict: QuotaVerdict, input_tokens: int, retries: dict[str, int]
) -> None:
    if verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
        learned_tpm = governor.model_stats[spec.name].learned_limits.get("tpm_input")
        m_tpm = learned_tpm or spec.tpm_input or spec.provider.tpm_input
        if verdict.kind == "MINUTE_TOKENS" and m_tpm and input_tokens > math.floor(m_tpm * governor.pool.safety):
            raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds per-minute token limit ({m_tpm})")
        retries["minute"] += 1
        if retries["minute"] > 6:
            raise ServiceBusy("Per-minute rate limits exhausted after 6 retries")
    elif verdict.kind == "OVERLOADED":
        retries["overload"] += 1
        if retries["overload"] > 5:
            raise ServiceBusy("Service overloaded after retries")
        governor.sleeper(governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (retries["overload"] - 1)))))
    elif verdict.kind == "SERVER_ERROR":
        retries["server"] += 1
        if retries["server"] > 2:
            raise ServiceBusy("Server error after retries")
        governor.sleeper(governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (retries["server"] - 1)))))
    else:
        _raise_verdict_exception(spec, governor, spec.provider.base_url, verdict, input_tokens)


def _parse_openai_empty_choices(
    parsed: dict, body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    usage = parsed.get("usage")
    p_tok = usage.get("prompt_tokens", input_tokens) if isinstance(usage, dict) else input_tokens
    c_tok = usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
    p_est = not isinstance(usage, dict) or "prompt_tokens" not in usage
    c_est = not isinstance(usage, dict) or "completion_tokens" not in usage
    governor.record_result(spec.name, p_tok, c_tok)
    return Reply(
        text="",
        finish="OTHER",
        prompt_tokens=p_tok,
        output_tokens=c_tok,
        prompt_estimated=p_est,
        output_estimated=c_est,
        seconds_waited=total_waited,
        model=spec.name,
        model_version=str(parsed.get("model", "")),
        raw_json=body_text,
    )


def _parse_openai_choice_reply(
    parsed: dict, c0: dict, body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    text = str(c0.get("message", {}).get("content", "") or "") if isinstance(c0.get("message"), dict) else ""
    finish = FINISH_MAP.get(str(c0.get("finish_reason", "stop")), "OTHER")
    usage = parsed.get("usage")

    if isinstance(usage, dict) and "prompt_tokens" in usage and "completion_tokens" in usage:
        p_tok = int(usage["prompt_tokens"])
        c_tok = int(usage["completion_tokens"])
        p_est, c_est = False, False
    else:
        p_tok = input_tokens
        c_tok = math.ceil(len(text) / 3.5)
        p_est, c_est = True, True

    governor.record_result(spec.name, p_tok, c_tok)
    return Reply(
        text=text,
        finish=finish,
        prompt_tokens=p_tok,
        output_tokens=c_tok,
        prompt_estimated=p_est,
        output_estimated=c_est,
        seconds_waited=total_waited,
        model=spec.name,
        model_version=str(parsed.get("model", "")),
        raw_json=body_text,
    )


def _parse_openai_reply(
    body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    try:
        parsed = json.loads(body_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ApiError(f"unexpected API response: {e}") from None

    if not isinstance(parsed, dict):
        raise ApiError("unexpected API response: body must be object")

    choices = parsed.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return _parse_openai_empty_choices(parsed, body_text, input_tokens, spec, governor, total_waited)

    c0 = choices[0]
    if not isinstance(c0, dict):
        raise ApiError("unexpected API response: choice must be object")

    return _parse_openai_choice_reply(parsed, c0, body_text, input_tokens, spec, governor, total_waited)


def _parse_openai_ok(
    done: sse.Completion | None, body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor,
    total_waited: float,
) -> Reply:
    if done is None:
        return _parse_openai_reply(body_text, input_tokens, spec, governor, total_waited)
    parsed = {"model": done.model, "choices": [{"message": {"content": done.text}, "finish_reason": done.finish_reason}]}
    if done.usage is not None:
        parsed["usage"] = done.usage
    return _parse_openai_choice_reply(parsed, parsed["choices"][0], body_text, input_tokens, spec, governor, total_waited)


class OpenAIClient:

    def __init__(self, spec: ModelSpec, governor: Governor, timeout: float, base_url: str | None = None) -> None:
        self.spec = spec
        self.governor = governor
        self.timeout = max(timeout, spec.timeout_seconds or 0)
        self.base_url = (base_url or spec.provider.base_url).rstrip("/")

    def count_tokens(self, request: ChatRequest) -> TokenCount:
        return TokenCount(value=_calc_char_tokens(request), estimated=True)

    def generate(self, request: ChatRequest) -> Reply:
        tc = self.count_tokens(request)
        input_tokens = tc.value
        ms = self.governor.model_stats[self.spec.name]
        eff = effective(self.governor.pool, self.spec, ms.adaptive_factor, ms.learned_limits)

        if input_tokens > self.spec.max_input_tokens or input_tokens > eff.input_token_ceiling:
            raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds max input limit ({self.spec.max_input_tokens}) or TPM limit ({eff.input_token_ceiling})")

        url = f"{self.base_url}/chat/completions"
        data = json.dumps(_build_payload(self.spec, request)).encode("utf-8")

        retries = {"minute": 0, "overload": 0, "server": 0, "transport": 0}
        total_waited = 0.0

        while True:
            total_waited += self.governor.wait_for_slot(self.spec.name, input_tokens)
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status, headers, body_text = resp.status, dict(resp.headers), resp.read().decode("utf-8")
                streamed = sse.assemble(body_text, self.spec.provider.name) if status == 200 and sse.is_event_stream(headers) else None
            except urllib.error.HTTPError as e:
                status, headers, body_text, streamed = e.code, dict(e.headers), e.read().decode("utf-8"), None
            except (urllib.error.URLError, OSError, http.client.HTTPException, sse.StreamCut) as e:
                retries["transport"] += 1
                if retries["transport"] > 3:
                    raise TransportError(f"Transport error after retries: {e}") from e
                self.governor.sleeper(self.governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (retries["transport"] - 1)))))
                continue

            _check_learned_headers(self.spec, self.governor, headers)

            if status == 200:
                return _parse_openai_ok(streamed, body_text, input_tokens, self.spec, self.governor, total_waited)

            verdict = classify("openai", status, headers, body_text)
            self.governor.record_rejection(self.spec.name, verdict)
            _handle_openai_retry(self.spec, self.governor, verdict, input_tokens, retries)

    def list_models(self) -> list[str]:
        self.governor.wait_for_provider(self.spec.provider.name)
        url = f"{self.base_url}/models"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status, headers, body_text = resp.status, dict(resp.headers), resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status, headers, body_text = e.code, dict(e.headers), e.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as e:
            raise TransportError(f"Transport error listing models: {e}") from e

        if status != 200:
            verdict = classify("openai", status, headers, body_text)
            self.governor.record_rejection(self.spec.name, verdict)
            _raise_verdict_exception(self.spec, self.governor, self.base_url, verdict, 0)

        try:
            parsed = json.loads(body_text)
        except (json.JSONDecodeError, ValueError) as e:
            raise ApiError(f"unexpected API response: {e}") from None

        if not isinstance(parsed, dict) or "data" not in parsed:
            raise ApiError("unexpected API response: missing data field")

        return [str(item["id"]) for item in parsed.get("data", []) if isinstance(item, dict) and "id" in item]
