"""Read-only tests for FIX-1 of WO-1.0-10 (FR-1.0-14), written by Claude from the review of the delivered code.

Each test pins a defect the WO-1.0-10 acceptance tests did not catch:
- the governor's read-modify-write was not atomic across processes;
- a month's tokens were filed under the next month on its last day;
- per-day QuotaFailure values were not learned;
- a daily rejection ignored the reset the response gave;
- model listings and replies that cannot be parsed were swallowed or escaped as raw exceptions;
- the modules break the Foundation's shape rules: swallowed exceptions, functions over 40 lines, statements
  packed with semicolons.

The simulated clock, the pool helpers and the local HTTP stand-in come from the WO-1.0-10 acceptance test.
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import time
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    START, SimClock, chat_request, client, gemini_429, governor_for, local_only, mod, model, provider, setup,
    write_pool)

ROOT = Path(__file__).resolve().parents[3]
FIXED_MODULES = ("chat", "limits", "quota", "governor", "gemini_client", "openai_client")
DRIVER = """
import sys, time
from pathlib import Path
from tools.outsourcing.limits import load_pool
from tools.outsourcing.governor import Governor
import random


def refuse_to_wait(seconds):
    raise SystemExit(f"unexpected wait of {seconds} s")


pool_path, state_path, go_file, seed, rounds = sys.argv[1:6]
gov = Governor(load_pool(Path(pool_path)), Path(state_path), time.time, refuse_to_wait, random.Random(int(seed)))
while not Path(go_file).exists():
    pass
for _ in range(int(rounds)):
    gov.wait_for_slot("m-a", 1)
    gov.record_result("m-a", 1, 1)
"""


def chat_errors() -> tuple[type, ...]:
    chat = mod("chat")
    return (chat.ApiError, chat.ModelError, chat.CredentialError, chat.ServiceBusy, chat.TransportError)


# ---------------------------------------------------------------- atomic state across processes

def test_FR_1_0_14_fix01_parallel_processes_lose_no_update(tmp_path):
    pool_path = write_pool(tmp_path, {"m-a": model("mistral", 1, rpd=100000)})
    state, go_file, driver = tmp_path / ".relay/governor.json", tmp_path / "go", tmp_path / "driver.py"
    driver.write_text(DRIVER, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    procs = [subprocess.Popen([sys.executable, str(driver), str(pool_path), str(state), str(go_file), str(seed), "150"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for seed in range(4)]
    go_file.write_text("go", encoding="utf-8")
    results = [p.communicate(timeout=300) + (p.returncode,) for p in procs]
    assert [r[2] for r in results] == [0, 0, 0, 0], [r[1][-500:] for r in results]
    clock = SimClock()
    clock.now = time.time()
    _, gov = governor_for(pool_path, state, clock)
    assert gov.remaining_today("m-a") == 100000 - 4 * 150


# ---------------------------------------------------------------- month bucket

def test_FR_1_0_14_fix01_tokens_on_a_months_last_day_count_for_that_month(tmp_path):
    providers = {"gemini": provider("gemini"), "mistral": provider("openai", tokens_per_month=1000)}
    clock = SimClock()
    clock.now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc).timestamp()
    _, gov = governor_for(write_pool(tmp_path, {"m-a": model("mistral", 1)}, providers), tmp_path / "s.json", clock)
    gov.wait_for_slot("m-a", 10)
    gov.record_result("m-a", 600, 0)
    assert gov.exhausted_until("m-a") is None
    clock.now = datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc).timestamp()
    gov.wait_for_slot("m-a", 10)
    gov.record_result("m-a", 600, 0)
    assert gov.exhausted_until("m-a") is None  # October's 600 tokens no longer count in November
    gov.wait_for_slot("m-a", 10)
    gov.record_result("m-a", 500, 0)
    assert gov.exhausted_until("m-a") == datetime(2026, 12, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------- learned per-day limit (B12)

def test_FR_1_0_14_fix01_per_day_quota_value_is_learned(tmp_path):
    script = [gemini_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "10")]
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, rpd=20)}, script=script)
    with stand:
        with pytest.raises(mod("chat").DailyQuotaExhausted):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    clock.now = datetime(2026, 10, 11, 8, 0, tzinfo=timezone.utc).timestamp()  # 01:00 in Los Angeles, a new day
    _, restarted = governor_for(tmp_path / "pool.json", tmp_path / ".relay/governor.json", clock)
    assert restarted.remaining_today("g-a") == 10


# ---------------------------------------------------------------- reset from the response (B8)

def test_FR_1_0_14_fix01_daily_rejection_uses_the_reset_the_response_gives(tmp_path):
    body = json.dumps({"error": {"message": "Too many requests", "type": "rate_limit"}})
    clock, pool, gov, stand = setup(tmp_path, {"m-a": model("mistral", 1)}, script=[(429, {"Retry-After": "7200"}, body)])
    with stand:
        with pytest.raises(mod("chat").DailyQuotaExhausted) as info:
            client("openai", pool, "m-a", gov, stand.url).generate(chat_request())
    assert info.value.reset_utc == START + timedelta(hours=2)
    assert gov.exhausted_until("m-a") == START + timedelta(hours=2)


# ---------------------------------------------------------------- nothing swallowed in listings and replies

@pytest.mark.parametrize("api", ["gemini", "openai"])
@pytest.mark.parametrize("answer", [(500, {}, "server failure"), (403, {}, json.dumps({"error": {"message": "no"}})),
                                    (200, {}, "not json at all")], ids=["500", "403", "200-not-json"])
def test_FR_1_0_14_fix01_failed_model_listing_raises(tmp_path, api, answer):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=[answer] * 4)
    with stand:
        with pytest.raises(chat_errors()):
            client(api, pool, "x-a", gov, stand.url).list_models()


@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_fix01_unparseable_reply_raises_api_error(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=[(200, {}, "<html>not json</html>")])
    with stand:
        with pytest.raises(mod("chat").ApiError):
            client(api, pool, "x-a", gov, stand.url).generate(chat_request())


# ---------------------------------------------------------------- Foundation shape rules

def module_path(name: str) -> Path:
    return ROOT / "tools" / "outsourcing" / f"{name}.py"


def swallowing_handlers(tree: ast.AST) -> list[int]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
        reraises = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        silent = all(isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)) for stmt in node.body)
        if silent or (broad and not reraises):
            found.append(node.lineno)
    return found


@pytest.mark.parametrize("name", FIXED_MODULES)
def test_FR_1_0_14_fix01_no_swallowed_exceptions(name):
    assert swallowing_handlers(ast.parse(module_path(name).read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize("name", FIXED_MODULES)
def test_FR_1_0_14_fix01_functions_at_most_40_lines_and_no_semicolons(name):
    text = module_path(name).read_text(encoding="utf-8")
    long_functions = [f"{node.name}:{node.lineno} ({node.end_lineno - node.lineno + 1} lines)"
                      for node in ast.walk(ast.parse(text))
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and node.end_lineno - node.lineno + 1 > 40]
    semicolons = [tok.start[0] for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                  if tok.type == tokenize.OP and tok.string == ";"]
    assert (long_functions, semicolons) == ([], [])
