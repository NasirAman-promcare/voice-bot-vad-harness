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
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from tools.outsourcing.chat import (
    ApiError, ChatRequest, CredentialError, DailyQuotaExhausted, ModelError,
    Reply, ServiceBusy, StepTooLarge, TokenCount, TransportError,
)
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import ModelSpec, effective, monthly_reset, next_reset
from tools.outsourcing.quota import classify

FINISH_MAP = {"STOP": "STOP", "MAX_TOKENS": "MAX_TOKENS", "SAFETY": "SAFETY", "RECITATION": "RECITATION"}


def _calc_char_tokens(request: ChatRequest) -> int:
    chars = len(request.system)
    for turn in request.turns:
        chars += len(turn.text)
    return math.ceil(chars / 3.5)


class GeminiClient:

    def __init__(self, spec: ModelSpec, governor: Governor, timeout: float, base_url: str | None = None) -> None:
        self.spec, self.governor, self.timeout = spec, governor, timeout
        self.base_url = (base_url or spec.provider.base_url).rstrip("/")

    def _build_gen_body(self, request: ChatRequest) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if request.system:
            body["systemInstruction"] = {"parts": [{"text": request.system}]}
        contents = []
        for turn in request.turns:
            role = "user" if turn.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn.text}]})
        body["contents"] = contents
        body["generationConfig"] = {"maxOutputTokens": min(request.max_output_tokens, self.spec.max_output_tokens)}
        return body

    def count_tokens(self, request: ChatRequest) -> TokenCount:
        url = f"{self.base_url}/v1beta/models/{self.spec.name}:countTokens"
        gen_body = self._build_gen_body(request)
        payload = {"generateContentRequest": {"model": f"models/{self.spec.name}", **gen_body}}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    parsed = json.loads(resp.read().decode("utf-8"))
                    return TokenCount(value=parsed.get("totalTokens", 0), estimated=False)
        except Exception:
            pass
        return TokenCount(value=_calc_char_tokens(request), estimated=True)

    def generate(self, request: ChatRequest) -> Reply:
        tc = self.count_tokens(request)
        input_tokens = tc.value
        ms = self.governor.model_stats[self.spec.name]
        eff = effective(self.governor.pool, self.spec, ms.adaptive_factor, ms.learned_limits)

        if input_tokens > self.spec.max_input_tokens or input_tokens > eff.input_token_ceiling:
            raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds max input limit ({self.spec.max_input_tokens}) or TPM limit ({eff.input_token_ceiling})")

        url = f"{self.base_url}/v1beta/models/{self.spec.name}:generateContent"
        data = json.dumps(self._build_gen_body(request)).encode("utf-8")

        minute_retries, overload_retries, server_retries, transport_retries = 0, 0, 0, 0
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
                transport_retries += 1
                if transport_retries > 3:
                    raise TransportError(f"Transport error after retries: {e}")
                self.governor.sleeper(self.governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (transport_retries - 1)))))
                continue

            if status == 200:
                parsed = json.loads(body_text) if body_text else {}
                candidates = parsed.get("candidates", [])
                block_reason = parsed.get("promptFeedback", {}).get("blockReason")

                if not candidates or block_reason:
                    finish = "SAFETY" if block_reason else "OTHER"
                    usage = parsed.get("usageMetadata", {})
                    p_tok, c_tok = usage.get("promptTokenCount", input_tokens), usage.get("candidatesTokenCount", 0)
                    self.governor.record_result(self.spec.name, p_tok, c_tok)
                    return Reply(text="", finish=finish, prompt_tokens=p_tok, output_tokens=c_tok, block_reason=block_reason, seconds_waited=total_waited, model=self.spec.name, model_version=parsed.get("modelVersion", ""), raw_json=body_text)

                cand = candidates[0]
                content = cand.get("content") or {}
                parts = content.get("parts") or []
                text = "".join([pt["text"] for pt in parts if isinstance(pt, dict) and "text" in pt and not pt.get("thought")])
                finish = FINISH_MAP.get(cand.get("finishReason", "STOP"), "OTHER")
                usage = parsed.get("usageMetadata", {})
                p_tok, c_tok = usage.get("promptTokenCount", input_tokens), usage.get("candidatesTokenCount", 0)

                self.governor.record_result(self.spec.name, p_tok, c_tok)
                return Reply(text=text, finish=finish, prompt_tokens=p_tok, output_tokens=c_tok, seconds_waited=total_waited, model=self.spec.name, model_version=parsed.get("modelVersion", ""), raw_json=body_text)

            verdict = classify("gemini", status, headers, body_text)
            self.governor.record_rejection(self.spec.name, verdict)

            if verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
                learned_tpm = self.governor.model_stats[self.spec.name].learned_limits.get("tpm_input")
                m_tpm = learned_tpm or self.spec.tpm_input or self.spec.provider.tpm_input
                if verdict.kind == "MINUTE_TOKENS" and m_tpm and input_tokens > math.floor(m_tpm * self.governor.pool.safety):
                    raise StepTooLarge(f"Input tokens ({input_tokens}) exceeds per-minute token limit ({m_tpm})")
                minute_retries += 1
                if minute_retries > 6:
                    raise ServiceBusy("Per-minute rate limits exhausted after 6 retries")
                continue
            elif verdict.kind == "OVERLOADED":
                overload_retries += 1
                if overload_retries > 5:
                    raise ServiceBusy("Service overloaded after 5 retries")
                self.governor.sleeper(self.governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (overload_retries - 1)))))
                continue
            elif verdict.kind == "SERVER_ERROR":
                server_retries += 1
                if server_retries > 2:
                    raise ServiceBusy("Server error after 2 retries")
                self.governor.sleeper(self.governor.rng.uniform(0.0, min(120.0, 5.0 * (3.0 ** (server_retries - 1)))))
                continue
            elif verdict.kind in ("DAILY", "MONTHLY"):
                now = self.governor.clock()
                res = monthly_reset(self.governor.pool, self.spec.provider, now) if verdict.kind == "MONTHLY" else next_reset(self.governor.pool, self.spec.provider, now)
                raise DailyQuotaExhausted(model=self.spec.name, provider=self.spec.provider.name, period="day" if verdict.kind == "DAILY" else "month", quota_value=verdict.server_limit_value, reset_utc=res.reset_utc, reset_provider=res.reset_provider, reset_karachi=res.reset_karachi, message=verdict.message)
            elif verdict.kind == "NO_QUOTA":
                raise ModelError(f"the {self.spec.provider.tier} tier gives {self.spec.name} no quota; remove it from the pool or enable billing")
            elif verdict.kind == "TOO_LARGE":
                raise StepTooLarge(f"Request too large: {verdict.message}")
            elif verdict.kind == "CREDENTIAL":
                raise CredentialError(f"Credential error for provider {self.spec.provider.name} at {self.base_url}")
            elif verdict.kind == "MODEL":
                raise ModelError(f"Model error for {self.spec.name}: {verdict.message}")
            else:
                raise ApiError(f"API error HTTP {status}: {verdict.message}")

    def list_models(self) -> list[str]:
        self.governor.wait_for_provider(self.spec.provider.name)
        models, page_token = [], None
        while True:
            query = f"?pageToken={page_token}" if page_token else ""
            url = f"{self.base_url}/v1beta/models{query}"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        parsed = json.loads(resp.read().decode("utf-8"))
                        for m in parsed.get("models", []):
                            name = m.get("name", "")
                            models.append(name[len("models/"):] if name.startswith("models/") else name)
                        page_token = parsed.get("nextPageToken")
                        if not page_token:
                            break
                    else:
                        break
            except Exception:
                break
        return models
