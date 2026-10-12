"""Unit tests for governor module.

CAPABILITIES:
  CAP-OUTSOURCING-GOVERNOR: Pacing, adaptive factor, state persistence, and report generation. [tests: test_governor]
INPUTS AND OUTPUTS:
  Tests Governor pacing, state serialization, adaptive adjustments, and reports.
CONTRACTS: none.
INVARIANTS:
  - Tests use simulated clock and sleeper.
NOT IN SCOPE:
  - Real clock waiting.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tools.outsourcing.limits import load_pool
from tools.outsourcing.governor import Governor
from tools.outsourcing.quota import QuotaVerdict

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


def test_governor_pacing(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    # gemini-3.8-flash has rpm 5, safety 0.8, share 2 -> floor(5*0.8/2) = 2 rpm
    delay1 = gov.wait_for_slot("gemini-3.8-flash", 100)
    assert delay1 == 0.0

    delay2 = gov.wait_for_slot("gemini-3.8-flash", 100)
    assert delay2 >= 0.0

    delay3 = gov.delay_for("gemini-3.8-flash", 100)
    assert delay3 > 0.0


def test_governor_record_result_and_report(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    gov.wait_for_slot("gemini-3.8-flash", 100)
    gov.record_result("gemini-3.8-flash", 100, 20)

    rep = gov.report()
    assert "gemini-3.8-flash" in rep.models
    m_rep = rep.models["gemini-3.8-flash"]
    assert m_rep.requests == 1
    assert m_rep.prompt_tokens == 100
    assert m_rep.output_tokens == 20


def test_governor_rejection_and_adaptive(tmp_path):
    pool = load_pool(SCRATCH_POOL)
    clock = SimClock()
    gov = Governor(pool, tmp_path / "state.json", clock, clock.sleep)

    verdict = QuotaVerdict("MINUTE_REQUESTS", 30.0, "model")
    gov.record_rejection("gemini-3.8-flash", verdict)

    rep = gov.report()
    m_rep = rep.models["gemini-3.8-flash"]
    assert m_rep.adaptive_factor == 0.75
    assert m_rep.retries["MINUTE_REQUESTS"] == 1


def test_governor_corrupt_state(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("corrupt json...", encoding="utf-8")

    pool = load_pool(SCRATCH_POOL)
    clock = SimClock()
    gov = Governor(pool, state_file, clock, clock.sleep)

    rep = gov.report()
    assert rep.corrupt_state is True
    assert rep.models["gemini-3.8-flash"].adaptive_factor == 0.75
