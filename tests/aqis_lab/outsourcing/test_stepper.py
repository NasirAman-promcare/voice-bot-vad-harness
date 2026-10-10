"""Unit tests for tools.outsourcing.stepper.

CAPABILITIES:
  CAP-OUTSOURCING-STEPPER: Run step parts and final verifications with fix turns and model switching. [tests: test_stepper.py]
INPUTS AND OUTPUTS: Test cases for stepper execution.
CONTRACTS: none.
INVARIANTS:
  - Tests use mock clients/stubs to avoid network access.
NOT IN SCOPE:
  - Network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import load_pool
from tools.outsourcing.records import RelayOptions, Result, StepPart
from tools.outsourcing.router import ModelStats, Router
from tools.outsourcing.steplog import StepLog
from tools.outsourcing.stepper import RunContext, run_final, run_part
from tools.outsourcing.workorder import WorkOrder, load_work_order, plan_steps
from tools.outsourcing.worktree import Worktree

ROOT = Path(__file__).resolve().parents[3]


def make_pool():
    providers = {
        "gemini": {
            "api": "gemini",
            "base_url": "https://generativelanguage.googleapis.com",
            "enabled": True,
            "tier": "free",
            "verified_on": "2026-10-10",
            "day_reset": "UTC",
            "data_use": "test",
        }
    }
    models = {
        "g1": {
            "provider": "gemini",
            "rank": 1,
            "risk_tiers": ["T1"],
            "max_input_tokens": 10000,
            "max_output_tokens": 1000,
        }
    }
    return load_pool({"share": 1, "safety": 1.0, "providers": providers, "models": models})


def test_stepper_context_setup(tmp_path: Path):
    prot = tmp_path / "docs/process/PROTECTED_PATHS.txt"
    prot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/process/PROTECTED_PATHS.txt", prot)

    ro_test = tmp_path / "test_ro.py"
    ro_test.write_text("def test_dummy(): pass\n", encoding="utf-8")

    order_file = tmp_path / "order.md"
    order_file.write_text(
        "---\nid: WO-1.0-01\nwp: WP-1.0\ntitle: T\nmodel: default\nchannel: api\nattempt_budget: 2\n"
        "risk_tier: T1\nmax_output_tokens: 1000\ncontext: []\noutputs:\n  - out.py\n"
        "read_only_tests:\n  - test_ro.py\nallowed_dependencies:\n  - stdlib\nverify:\n  - echo ok\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "out.py").write_text("print('hello')\n", encoding="utf-8")

    order = load_work_order(order_file, tmp_path)
    plan = plan_steps(order)
    pool = make_pool()
    gov = Governor(pool, tmp_path / "gov.json", time.time, lambda s: None)
    router = Router(pool, gov, ModelStats())
    wt = Worktree(path=tmp_path, branch="wo/WO-1.0-01", base_commit="abc")
    opts = RelayOptions(
        wo=str(order_file),
        attempts=2,
        api_base="http://127.0.0.1",
        timeout=10,
        verify_timeout=10,
        pool="pool.json",
        dry_run=False,
        status=False,
        models=(),
        restart=False,
    )

    ctx = RunContext(
        order=order,
        plan=plan,
        worktree=wt,
        router=router,
        governor=gov,
        step_log=StepLog(),
        options=opts,
        clock=time.time,
        sleeper=lambda s: None,
        log_root=tmp_path / "logs",
        main_root=tmp_path,
    )

    assert ctx.order.id == "WO-1.0-01"
