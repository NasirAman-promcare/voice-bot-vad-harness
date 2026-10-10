"""Unit tests for limits module.

CAPABILITIES:
  CAP-OUTSOURCING-LIMITS: Model pool specification loading and limit calculations. [tests: test_limits]
INPUTS AND OUTPUTS:
  Tests Pool loading, validation, effective limits, reset times, and exceptions.
CONTRACTS: none.
INVARIANTS:
  - Unit tests run with simulated data.
NOT IN SCOPE:
  - Live API calls or persistent state testing.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from tools.outsourcing.limits import (
    LimitsError,
    load_pool,
    effective,
    next_reset,
)

ROOT = Path(__file__).resolve().parents[3]


def test_load_pool_valid(tmp_path):
    pool_file = ROOT / "config/aqis_lab/model_pool.json"
    pool = load_pool(pool_file)
    assert pool.share >= 1
    assert 0.5 <= pool.safety <= 1.0
    assert "gemini" in pool.providers()
    assert "gemini-3.8-flash" in pool.models()

    spec = pool.model("gemini-3.8-flash")
    assert spec.provider.name == "gemini"
    assert spec.rank == 1


def test_load_pool_disabled_provider():
    data = {
        "share": 1,
        "safety": 0.8,
        "providers": {
            "p1": {
                "api": "openai",
                "base_url": "https://example.com",
                "enabled": False,
                "tier": "free",
                "verified_on": "",
                "day_reset": "UTC",
                "data_use": "",
            }
        },
        "models": {
            "m1": {
                "provider": "p1",
                "rank": 1,
                "risk_tiers": ["T1"],
                "max_input_tokens": 1000,
                "max_output_tokens": 500,
            }
        },
    }
    pool = load_pool(data)
    with pytest.raises(LimitsError) as exc:
        pool.model("m1")
    assert "disabled provider" in str(exc.value)


def test_load_pool_invalid_keys():
    with pytest.raises(LimitsError):
        load_pool({"share": 0, "safety": 0.8, "providers": {}, "models": {}})

    with pytest.raises(LimitsError):
        load_pool({"share": 1, "safety": 1.5, "providers": {}, "models": {}})


def test_candidates():
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    c_t1 = pool.candidates("T1")
    assert len(c_t1) > 0
    ranks = [m.rank for m in c_t1]
    assert ranks == sorted(ranks)


def test_effective_limits():
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    model = pool.model("gemini-3.8-flash")
    eff = effective(pool, model, adaptive_factor=1.0)
    assert eff.rpm is not None
    assert eff.input_token_ceiling <= model.max_input_tokens


def test_next_reset():
    pool = load_pool(ROOT / "config/aqis_lab/model_pool.json")
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    p_spec = pool.providers()["gemini"]
    res = next_reset(pool, p_spec, now)
    assert res.reset_utc > now
    assert res.reset_utc.tzinfo == timezone.utc
