"""Claude's fix for the pool loader (FR-1.0-14, WO-1.0-10 B1), written before the fix.

B1: "A model, keyed by its API name, has `provider`, `rank` (unique positive integer), …". On 2026-10-11 the pool on
`main` (`00c8f91`) gave rank 7 to both `gemini-3-flash-preview` and `deepseek-ai/deepseek-v4.1-flash`, and rank 8 to
both `gemini-2.5-flash` and `z-ai/glm-5-3-flash`. `load_pool` accepted it, so the routing order between those models
was left to the file's key order. A repeated rank is now a `LimitsError` naming both models and the rank.
"""
from __future__ import annotations

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import mod, model, provider


def pool(models: dict) -> dict:
    return {"share": 1, "safety": 1.0, "providers": {"gemini": provider("gemini"), "nvidia": provider("openai")},
            "models": models}


def test_FR_1_0_14_repeated_rank_is_refused_naming_both_models():
    with pytest.raises(mod("limits").LimitsError) as info:
        mod("limits").load_pool(pool({"g-a": model("gemini", 1), "g-b": model("gemini", 7),
                                      "n-a": model("nvidia", 7)}))
    message = str(info.value)
    assert "g-b" in message and "n-a" in message and "7" in message


def test_FR_1_0_14_distinct_ranks_load():
    loaded = mod("limits").load_pool(pool({"g-a": model("gemini", 1), "g-b": model("gemini", 7),
                                           "n-a": model("nvidia", 8)}))
    assert sorted(m.rank for m in loaded.models().values()) == [1, 7, 8]
