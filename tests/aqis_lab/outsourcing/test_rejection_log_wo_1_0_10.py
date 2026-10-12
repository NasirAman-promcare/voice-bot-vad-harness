"""Claude's fix for the relay's rejection records (FR-1.0-14, DEC-1.0-07), written before the fix.

On 2026-10-11 every NVIDIA model answered six times with a rejection the classifier called OVERLOADED, and the relay
kept only the counts (`Retries: OVERLOADED: 30`). The provider's own message, which says whether it was overload, a rate
limit or an oversized request, was dropped, so the cause could not be established. Every classified rejection is now
appended to `rejections.jsonl` next to the governor's state file: UTC time, model, provider, kind, scope and the
provider's message.
"""
from __future__ import annotations

import json

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    TopRandom, chat_request, client, local_only, mod, model, ok, setup)


@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_every_rejection_is_recorded_with_the_providers_message(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    busy = (503, {}, json.dumps({"error": {"code": 503, "status": "UNAVAILABLE",
                                           "message": "The model is overloaded. Please try again later."}}))
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=[busy, busy, ok(api)], rng=TopRandom())
    with stand:
        client(api, pool, "x-a", gov, stand.url).generate(chat_request())
    log = tmp_path / ".relay" / "rejections.jsonl"
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    for record in records:
        assert record["model"] == "x-a" and record["provider"] == prov and record["kind"] == "OVERLOADED"
        assert "the model is overloaded" in record["message"].lower()  # the classifier keeps the message lower-cased
        assert record["utc"].endswith("+00:00")


def test_FR_1_0_14_no_rejection_writes_no_record(tmp_path):
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model("gemini", 1)}, script=[ok("gemini")])
    with stand:
        client("gemini", pool, "x-a", gov, stand.url).generate(chat_request())
    assert not (tmp_path / ".relay" / "rejections.jsonl").exists()
