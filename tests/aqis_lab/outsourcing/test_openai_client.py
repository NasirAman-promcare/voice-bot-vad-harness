"""Unit tests for openai_client module.

CAPABILITIES:
  CAP-OUTSOURCING-OPENAI-CLIENT: OpenAI-compatible model client with token counting, content generation, and model listing. [tests: test_openai_client]
INPUTS AND OUTPUTS:
  Tests OpenAIClient methods with stub model server and simulated clock.
CONTRACTS: none.
INVARIANTS:
  - Uses local stub model server with no external network calls.
NOT IN SCOPE:
  - Live OpenAI API calls.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.outsourcing.chat import ApiError, ChatRequest, Turn
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import load_pool
from tools.outsourcing.openai_client import OpenAIClient
from tests.aqis_lab.outsourcing.stub_model_server import StubModelServer

ROOT = Path(__file__).resolve().parents[3]


class SimClock:

    def __init__(self, start: float = 1775822400.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


def test_openai_client_generate(tmp_path):
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    spec = pool.model("codestral-2508")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    ok_body = json.dumps({
        "id": "cmpl-123",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello OpenAI"},
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6},
    })

    server = StubModelServer([(200, {}, ok_body)], count=20, clock=clock)
    with server as (url, reqs):
        client = OpenAIClient(spec, gov, timeout=5.0, base_url=url)
        req = ChatRequest(
            system="System prompt",
            turns=(Turn(role="user", text="Hello"),),
            max_output_tokens=100,
        )
        reply = client.generate(req)
        assert reply.text == "Hello OpenAI"
        assert reply.finish == "STOP"
        assert reply.prompt_tokens == 12
        assert reply.output_tokens == 6


def test_openai_client_list_models(tmp_path):
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    spec = pool.model("codestral-2508")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    models_body = json.dumps({
        "data": [{"id": "codestral-2508"}, {"id": "mistral-small"}]
    })

    server = StubModelServer([(200, {}, models_body)], count=20, clock=clock)
    with server as (url, reqs):
        client = OpenAIClient(spec, gov, timeout=5.0, base_url=url)
        models = client.list_models()
        assert "codestral-2508" in models
        assert "mistral-small" in models


def test_openai_client_non_json_reply(tmp_path):
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    spec = pool.model("codestral-2508")
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    server = StubModelServer([(200, {}, "<html>html response</html>")], count=20, clock=clock)
    with server as (url, reqs):
        client = OpenAIClient(spec, gov, timeout=5.0, base_url=url)
        req = ChatRequest(
            system="System prompt",
            turns=(Turn(role="user", text="Hello"),),
            max_output_tokens=100,
        )
        with pytest.raises(ApiError):
            client.generate(req)
