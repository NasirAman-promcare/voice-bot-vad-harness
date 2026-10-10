"""Unit tests for tools.outsourcing.router.

CAPABILITIES:
  CAP-OUTSOURCING-ROUTER: Choose model based on risk tier, token limits, governor delays, and first-pass performance stats. [tests: test_router.py]
INPUTS AND OUTPUTS: Test cases for router selection and stats.
CONTRACTS: none.
INVARIANTS:
  - Unit tests run fast without real network calls.
NOT IN SCOPE:
  - Integration with actual LLM endpoints.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import ModelSpec, Pool, ProviderSpec, load_pool
from tools.outsourcing.router import ModelStats, NoEligibleModel, PoolExhausted, Router, client_for, model_stats
from tools.outsourcing.workorder import WorkOrder


def make_pool(models_data: dict, enabled_providers=("gemini", "openai")) -> Pool:
    providers = {
        "gemini": {
            "api": "gemini",
            "base_url": "https://generativelanguage.googleapis.com",
            "enabled": "gemini" in enabled_providers,
            "tier": "free",
            "verified_on": "2026-10-10",
            "day_reset": "UTC",
            "data_use": "test",
        },
        "openai": {
            "api": "openai",
            "base_url": "https://api.openai.com/v1",
            "enabled": "openai" in enabled_providers,
            "tier": "free",
            "verified_on": "2026-10-10",
            "day_reset": "UTC",
            "data_use": "test",
        },
    }
    return load_pool({"share": 1, "safety": 1.0, "providers": providers, "models": models_data})


def dummy_wo(model: str = "default", risk_tier: str = "T1") -> WorkOrder:
    return WorkOrder(
        id="WO-1.0-01",
        wp="WP-1.0",
        title="Test Order",
        model=model,
        channel="api",
        attempt_budget=3,
        risk_tier=risk_tier,
        max_output_tokens=4000,
        context=(),
        outputs=("out.py",),
        read_only_tests=(),
        allowed_dependencies=(),
        verify=("pytest",),
        path="docs/outsourcing/orders/WO-1.0-01.md",
    )


def test_model_stats_empty_and_unreadable(tmp_path: Path):
    stats = model_stats(tmp_path)
    assert stats.models == {}
    assert stats.unreadable == ()

    returns_dir = tmp_path / "docs/outsourcing/returns/WO-1/steps.md"
    returns_dir.parent.mkdir(parents=True, exist_ok=True)
    returns_dir.write_text("invalid log content", encoding="utf-8")

    stats2 = model_stats(tmp_path)
    assert "docs/outsourcing/returns/WO-1/steps.md" in stats2.unreadable


def test_router_pinned_model_valid(tmp_path: Path):
    m_data = {
        "m1": {
            "provider": "gemini",
            "rank": 1,
            "risk_tiers": ["T1"],
            "max_input_tokens": 10000,
            "max_output_tokens": 1000,
        }
    }
    pool = make_pool(m_data)
    gov = Governor(pool, tmp_path / "gov.json", time.time, lambda s: None)
    router = Router(pool, gov, ModelStats())

    chosen = router.choose(dummy_wo(model="m1"), 5000)
    assert chosen.name == "m1"


def test_router_pinned_model_not_eligible(tmp_path: Path):
    m_data = {
        "m1": {
            "provider": "gemini",
            "rank": 1,
            "risk_tiers": ["T2"],
            "max_input_tokens": 10000,
            "max_output_tokens": 1000,
        }
    }
    pool = make_pool(m_data)
    gov = Governor(pool, tmp_path / "gov.json", time.time, lambda s: None)
    router = Router(pool, gov, ModelStats())

    with pytest.raises(NoEligibleModel):
        router.choose(dummy_wo(model="m1", risk_tier="T1"), 5000)


def test_router_default_size_ruled_out(tmp_path: Path):
    m_data = {
        "m1": {
            "provider": "gemini",
            "rank": 1,
            "risk_tiers": ["T1"],
            "max_input_tokens": 1000,
            "max_output_tokens": 1000,
        }
    }
    pool = make_pool(m_data)
    gov = Governor(pool, tmp_path / "gov.json", time.time, lambda s: None)
    router = Router(pool, gov, ModelStats())

    with pytest.raises(NoEligibleModel) as exc:
        router.choose(dummy_wo(model="default", risk_tier="T1"), 5000)
    assert "Size alone" in exc.value.reason


def test_client_for_factory(tmp_path: Path):
    m_data = {
        "g1": {
            "provider": "gemini",
            "rank": 1,
            "risk_tiers": ["T1"],
            "max_input_tokens": 10000,
            "max_output_tokens": 1000,
        },
        "o1": {
            "provider": "openai",
            "rank": 2,
            "risk_tiers": ["T1"],
            "max_input_tokens": 10000,
            "max_output_tokens": 1000,
        },
    }
    pool = make_pool(m_data)
    gov = Governor(pool, tmp_path / "gov.json", time.time, lambda s: None)

    c_g = client_for(pool.model("g1"), gov, 10.0)
    assert c_g.__class__.__name__ == "GeminiClient"

    c_o = client_for(pool.model("o1"), gov, 10.0)
    assert c_o.__class__.__name__ == "OpenAIClient"
