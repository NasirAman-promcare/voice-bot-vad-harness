"""Gemini API client with rate governor integration.

CAPABILITIES:
  CAP-OUTSOURCING-GEMINI-CLIENT: Gemini model client with token counting, content generation, and model listing. [tests: test_gemini_client, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Accepts ChatRequest; returns TokenCount or Reply; raises chat exceptions.
CONTRACTS: none.
INVARIANTS:
  - No API key sent in request headers or body (handled by proxy).
NOT IN SCOPE:
  - Local state persistence (handled by governor).
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-11 WP-1.0 FR-1.0-14 (Claude): the socket timeout is at least the model's timeout_seconds.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any

from tools.outsourcing.chat import (
    ApiError, ChatRequest, CredentialError, DailyQuotaExhausted, ModelError,
    Reply, ServiceBusy, StepTooLarge, TokenCount, TransportError, Turn,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import ModelSpec, _la_offset, _resolve_tz, effective, monthly_reset, next_reset
from tools.outsourcing.quota import QuotaVerdict, classify

FINISH_MAP = {"STOP": "STOP", "MAX_TOKENS": "MAX_TOKENS", "SAFETY": "SAFETY", "RECITATION": "RECITATION"}


def _calc_char_tokens(request: ChatRequest) -> int:
    chars = len(request.system)
    for turn in request.turns:
        chars += len(turn.text)
    return math.ceil(chars / 3.5)


def _build_gen_body(spec: ModelSpec, request: ChatRequest) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if request.system:
        body["systemInstruction"] = {"parts": [{"text": request.system}]}
    contents = []
    for turn in request.turns:
        role = "user" if turn.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": turn.text}]})
    body["contents"] = contents
    body["generationConfig"] = {"maxOutputTokens": min(request.max_output_tokens, spec.max_output_tokens)}
    return body


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


def _handle_gemini_retry(
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


def _parse_gemini_blocked_reply(
    parsed: dict, body_text: str, block_reason: str | None, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    finish = "SAFETY" if block_reason else "OTHER"
    usage = parsed.get("usageMetadata", {})
    p_tok = usage.get("promptTokenCount", input_tokens) if isinstance(usage, dict) else input_tokens
    c_tok = usage.get("candidatesTokenCount", 0) if isinstance(usage, dict) else 0
    governor.record_result(spec.name, p_tok, c_tok)
    return Reply(
        text="",
        finish=finish,
        prompt_tokens=p_tok,
        output_tokens=c_tok,
        block_reason=block_reason,
        seconds_waited=total_waited,
        model=spec.name,
        model_version=str(parsed.get("modelVersion", "")),
        raw_json=body_text,
    )


def _parse_gemini_candidate_reply(
    parsed: dict, cand: dict, body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    content = cand.get("content") or {}
    parts = content.get("parts") or [] if isinstance(content, dict) else []
    text_parts = [pt["text"] for pt in parts if isinstance(pt, dict) and "text" in pt and not pt.get("thought")]
    text = "".join(text_parts)
    finish = FINISH_MAP.get(str(cand.get("finishReason", "STOP")), "OTHER")
    usage = parsed.get("usageMetadata", {})
    p_tok = usage.get("promptTokenCount", input_tokens) if isinstance(usage, dict) else input_tokens
    c_tok = usage.get("candidatesTokenCount", 0) if isinstance(usage, dict) else 0

    governor.record_result(spec.name, p_tok, c_tok)
    return Reply(
        text=text,
        finish=finish,
        prompt_tokens=p_tok,
        output_tokens=c_tok,
        seconds_waited=total_waited,
        model=spec.name,
        model_version=str(parsed.get("modelVersion", "")),
        raw_json=body_text,
    )


def _parse_gemini_reply(
    body_text: str, input_tokens: int, spec: ModelSpec, governor: Governor, total_waited: float
) -> Reply:
    try:
        parsed = json.loads(body_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ApiError(f"unexpected API response: {e}") from None

    if not isinstance(parsed, dict):
        raise ApiError("unexpected API response: body must be object")

    candidates = parsed.get("candidates", [])
    block_reason = parsed.get("promptFeedback", {}).get("blockReason")

    if not candidates or block_reason:
        return _parse_gemini_blocked_reply(parsed, body_text, block_reason, input_tokens, spec, governor, total_waited)

    cand = candidates[0]
    if not isinstance(cand, dict):
        raise ApiError("unexpected API response: candidate must be object")

    return _parse_gemini_candidate_reply(parsed, cand, body_text, input_tokens, spec, governor, total_waited)


class GeminiClient:

    def __init__(self, spec: ModelSpec, governor: Governor, timeout: float, base_url: str | None = None) -> None:
        self.spec = spec
        self.governor = governor
        self.timeout = max(timeout, spec.timeout_seconds or 0)
        self.base_url = (base_url or spec.provider.base_url).rstrip("/")

    def count_tokens(self, request: ChatRequest) -> TokenCount:
        url = f"{self.base_url}/v1beta/models/{self.spec.name}:countTokens"
        gen_body = _build_gen_body(self.spec, request)
        payload = {"generateContentRequest": {"model": f"models/{self.spec.name}", **gen_body}}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    parsed = json.loads(resp.read().decode("utf-8"))
                    if isinstance(parsed, dict) and "totalTokens" in parsed:
                        return TokenCount(value=int(parsed["totalTokens"]), estimated=False)
        except (urllib.error.URLError, OSError, ValueError, ApiError):
            err = None
        return TokenCount(value=_calc_char_tokens(request), estimated=True)

    def generate(self, request: ChatRequest) -> Reply:
        tc = self.count_tokens(request)
        input_tokens = tc.value
        ms = self.governor.model_stats[self.spec.name]
        eff = effective(self.governor.pool, self.spec, ms.adaptive_factor, ms.learned_limits)

        if input_tokens > self.spec.max_input_tokens or input_tokens > eff.input_token_ceiling:
            raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds max input limit ({self.spec.max_input_tokens}) or TPM limit ({eff.input_token_ceiling})")

        url = f"{self.base_url}/v1beta/models/{self.spec.name}:generateContent"
        data = json.dumps(_build_gen_body(self.spec, request)).encode("utf-8")

        retries = {"minute": 0, "overload": 0, "server": 0, "transport": 0}
        total_waited = 0.0

        while True:
            total_waited += self.governor.wait_for_slot(self.spec.name, input_tokens)
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status, headers, body_text = resp.status, dict(resp.headers), resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                status, headers, body_text = e.code, dict(e.headers), e.read().decode("utf-8")
            except (urllib.error.URLError, OSError) as e:
                retries["transport"] += 1
                if retries["transport"] > 3:
                    raise TransportError(f"Transport error after retries: {e}") from e
                self.governor.sleeper(self.governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (retries["transport"] - 1)))))
                continue

            if status == 200:
                return _parse_gemini_reply(body_text, input_tokens, self.spec, self.governor, total_waited)

            verdict = classify("gemini", status, headers, body_text)
            self.governor.record_rejection(self.spec.name, verdict)
            _handle_gemini_retry(self.spec, self.governor, verdict, input_tokens, retries)

    def list_models(self) -> list[str]:
        self.governor.wait_for_provider(self.spec.provider.name)
        models, page_token = [], None
        while True:
            query = f"?pageToken={page_token}" if page_token else ""
            url = f"{self.base_url}/v1beta/models{query}"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status, headers, body_text = resp.status, dict(resp.headers), resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                status, headers, body_text = e.code, dict(e.headers), e.read().decode("utf-8")
            except (urllib.error.URLError, OSError) as e:
                raise TransportError(f"Transport error listing models: {e}") from e

            if status != 200:
                verdict = classify("gemini", status, headers, body_text)
                self.governor.record_rejection(self.spec.name, verdict)
                _raise_verdict_exception(self.spec, self.governor, self.base_url, verdict, 0)

            try:
                parsed = json.loads(body_text)
            except (json.JSONDecodeError, ValueError) as e:
                raise ApiError(f"unexpected API response: {e}") from None

            if not isinstance(parsed, dict) or "models" not in parsed:
                raise ApiError("unexpected API response: missing models field")

            for m in parsed.get("models", []):
                if isinstance(m, dict):
                    name = str(m.get("name", ""))
                    models.append(name[len("models/"):] if name.startswith("models/") else name)
            page_token = parsed.get("nextPageToken")
            if not page_token:
                break
        return models
