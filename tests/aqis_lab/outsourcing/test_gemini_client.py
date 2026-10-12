"""Unit tests for gemini_client module.

CAPABILITIES:
  CAP-OUTSOURCING-GEMINI-CLIENT: Gemini model client with token counting, content generation, and model listing. [tests: test_gemini_client]
INPUTS AND OUTPUTS:
  Tests GeminiClient methods with stub model server and simulated clock.
CONTRACTS: none.
INVARIANTS:
  - Uses local stub model server with no external network calls.
NOT IN SCOPE:
  - Live Gemini API calls.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.outsourcing.chat import ApiError, ChatRequest, Turn
from tools.outsourcing.gemini_client import GeminiClient
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import load_pool
from tests.aqis_lab.outsourcing.stub_model_server import StubModelServer

ROOT = Path(__file__).resolve().parents[3]

# The pool these tests were written against (config/aqis_lab/model_pool.json at 5aafe78), reduced to the two models
# they use. The real pool is owner-maintained and changes; the code's behaviour is what these tests check.
SCRATCH_POOL = json.loads('{"share": 2, "safety": 0.8, "providers": {"gemini": {"api": "gemini", "base_url": "https://generativelanguage.googleapis.com", "enabled": true, "tier": "free", "verified_on": "2026-10-09", "day_reset": "America/Los_Angeles", "data_use": "Free tier: Google may use prompts and responses to improve its products, and human reviewers may read them."}, "mistral": {"api": "openai", "base_url": "https://api.mistral.ai/v1", "enabled": true, "tier": "free", "verified_on": "2026-10-10", "day_reset": "UTC", "data_use": "Free (Experiment) plan: may be used for training unless \'Anonymous improvement data\' is switched off in Admin > Privacy."}}, "models": {"gemini-3.8-flash": {"provider": "gemini", "rank": 1, "risk_tiers": ["T1", "T2", "T3"], "rpm": 5, "tpm_input": 250000, "rpd": 20, "max_input_tokens": 1048576, "max_output_tokens": 65536}, "codestral-2508": {"provider": "mistral", "rank": 5, "risk_tiers": ["T1", "T2", "T3"], "rpm": 124, "tpm_input": 625000, "max_input_tokens": 128000, "max_output_tokens": 32768}}}')


class SimClock:

    def __init__(self, start: float = 1775822400.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


def test_gemini_client_generate(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    spec = pool.model("gemini-3.8-flash")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    ok_body = json.dumps({
        "candidates": [
            {
                "content": {"parts": [{"text": "Hello world"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    })

    server = StubModelServer([(200, {}, ok_body)], count=20, clock=clock)
    with server as (url, reqs):
        client = GeminiClient(spec, gov, timeout=5.0, base_url=url)
        req = ChatRequest(
            system="System prompt",
            turns=(Turn(role="user", text="Hello"),),
            max_output_tokens=100,
        )
        reply = client.generate(req)
        assert reply.text == "Hello world"
        assert reply.finish == "STOP"
        assert reply.prompt_tokens == 10
        assert reply.output_tokens == 5


def test_gemini_client_list_models(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    spec = pool.model("gemini-3.8-flash")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    models_body = json.dumps({
        "models": [{"name": "models/gemini-3.8-flash"}, {"name": "models/gemini-3.8-pro"}]
    })

    server = StubModelServer([(200, {}, models_body)], count=20, clock=clock)
    with server as (url, reqs):
        client = GeminiClient(spec, gov, timeout=5.0, base_url=url)
        models = client.list_models()
        assert "gemini-3.8-flash" in models
        assert "gemini-3.8-pro" in models


def test_gemini_client_non_json_reply(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    spec = pool.model("gemini-3.8-flash")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    server = StubModelServer([(200, {}, "<html>html response</html>")], count=20, clock=clock)
    with server as (url, reqs):
        client = GeminiClient(spec, gov, timeout=5.0, base_url=url)
        req = ChatRequest(
            system="System prompt",
            turns=(Turn(role="user", text="Hello"),),
            max_output_tokens=100,
        )
        with pytest.raises(ApiError):
            client.generate(req)
