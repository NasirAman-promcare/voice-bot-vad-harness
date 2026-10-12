"""Claude's change for the owner's BLK-1.0-12 answer (FR-1.0-14; WO-1.0-10 B1 and B11 amended), written first.

The owner found why every NVIDIA request failed: the NIM gateway rejects unsupported sampling values (Kimi-K3 needs
top_p 0.95), and GLM-5.3-Flash defaults to maximum reasoning, which outlasts the gateway's 15-minute limit. The pool on
`main` (`dbfba0e`) gives each model `reasoning_effort`, `temperature`, `top_p` and `timeout_seconds`. The owner's
instructions: the OpenAI-compatible client forwards them. A model without a value gets none of them, as WO-1.0-10
must-catch 11 requires (DEC-1.0-08). The socket timeout is at least the model's `timeout_seconds`.
"""
from __future__ import annotations

import json

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    chat_request, local_only, mod, model, ok, provider, setup)

KIMI = {"reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "timeout_seconds": 360}


def pool_dict(**fields) -> dict:
    return {"share": 1, "safety": 1.0, "providers": {"nvidia": provider("openai")}, "models": {"n-a": model("nvidia", 1, **fields)}}


def test_FR_1_0_14_pool_reads_the_model_request_parameters():
    spec = mod("limits").load_pool(pool_dict(**KIMI)).model("n-a")
    assert (spec.reasoning_effort, spec.temperature, spec.top_p, spec.timeout_seconds) == ("high", 1.0, 0.95, 360)
    bare = mod("limits").load_pool(pool_dict()).model("n-a")
    assert (bare.reasoning_effort, bare.temperature, bare.top_p, bare.timeout_seconds) == (None, None, None, None)


@pytest.mark.parametrize("field, value", [
    ("reasoning_effort", ""), ("reasoning_effort", 3), ("temperature", -0.1), ("temperature", 2.5),
    ("temperature", "0.5"), ("top_p", 0), ("top_p", 1.5), ("top_p", True), ("timeout_seconds", 0),
    ("timeout_seconds", 12.5)])
def test_FR_1_0_14_invalid_request_parameters_are_refused(field, value):
    with pytest.raises(mod("limits").LimitsError, match=field):
        mod("limits").load_pool(pool_dict(**{field: value}))


def sent_body(tmp_path, fields: dict) -> dict:
    clock, pool, gov, stand = setup(tmp_path, {"n-a": model("mistral", 1, **fields)}, script=[ok("openai")])
    with stand:
        mod("openai_client").OpenAIClient(pool.model("n-a"), gov, 5, base_url=stand.url).generate(chat_request())
    return json.loads(stand.generations()[0]["body"])


def test_FR_1_0_14_openai_request_carries_the_models_parameters(tmp_path):
    body = sent_body(tmp_path, KIMI)
    assert (body["reasoning_effort"], body["temperature"], body["top_p"]) == ("high", 1.0, 0.95)


def test_FR_1_0_14_openai_request_without_parameters_sends_none(tmp_path):
    # WO-1.0-10 must-catch 11 (no temperature unless the pool sets one) stays; see DEC-1.0-08.
    body = sent_body(tmp_path, {})
    assert not {"reasoning_effort", "temperature", "top_p"} & set(body)


@pytest.mark.parametrize("api", ["gemini", "openai"])
@pytest.mark.parametrize("given, model_timeout, expected", [(300, 360, 360), (1200, 360, 1200), (300, None, 300)])
def test_FR_1_0_14_socket_timeout_is_at_least_the_models(tmp_path, api, given, model_timeout, expected):
    prov = "gemini" if api == "gemini" else "mistral"
    fields = {} if model_timeout is None else {"timeout_seconds": model_timeout}
    clock, pool, gov, stand = setup(tmp_path, {"n-a": model(prov, 1, **fields)})
    cls = mod("gemini_client").GeminiClient if api == "gemini" else mod("openai_client").OpenAIClient
    assert cls(pool.model("n-a"), gov, given).timeout == expected
