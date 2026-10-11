"""Claude's fix after the 2026-10-10 relay runs (FR-1.0-14, DEC-1.0-06), written before the fix.

The relay counted a request toward a model's day only after a success (WO-1.0-10 B5 as first written). Google counts
every request it receives: the owner's dashboard on 2026-10-11 showed gemini-3.6-flash at 22/20, 3.7 at 21/20 and
3.8 at 19/20 requests per day, while `.relay/governor.json` held no daily count for any of them. So `relay --status`
reported 0/20, and pacing let the relay spend requests the provider had already counted. Every sent request now counts
toward the model's and the provider's day when it is sent; tokens still count when the reply arrives.
"""
from __future__ import annotations

import json

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    TopRandom, chat_request, client, local_only, mod, model, ok, setup)

OVERLOADED = (503, {}, json.dumps({"error": {"code": 503, "status": "UNAVAILABLE", "message": "overloaded"}}))


@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_rejected_requests_count_toward_the_day(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1, rpd=20)}, script=[OVERLOADED, OVERLOADED, ok(api)],
                                    rng=TopRandom())
    with stand:
        client(api, pool, "x-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 3
    assert gov.remaining_today("x-a") == 17, "two rejected requests and one success: three requests sent"
    assert gov.report().models["x-a"].count_today == 3


@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_requests_that_end_in_service_busy_still_count(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1, rpd=20)}, script=[OVERLOADED] * 6,
                                    rng=TopRandom())
    with stand:
        with pytest.raises(mod("chat").ServiceBusy):
            client(api, pool, "x-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 6
    assert gov.remaining_today("x-a") == 14
