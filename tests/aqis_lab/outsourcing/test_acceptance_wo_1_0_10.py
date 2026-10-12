"""Acceptance tests for WO-1.0-10 (FR-1.0-14): model clients, rate governor and quota classification.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8. Modules are imported inside the tests,
so a missing package fails each test on its own instead of aborting collection.

Nothing here waits in real time or reaches the internet. A simulated clock moves only when the governor's
sleeper is called. A local HTTP stand-in (defined below, independent of the implementer's
`stub_model_server.py`) answers both API shapes from a script and records every request, together with the
simulated time at which it arrived.
"""
from __future__ import annotations

import importlib
import json
import math
import random
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
START = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)  # 05:00 in Los Angeles (PDT), 17:00 in Karachi
KEY_VALUES = {"GEMINI_API_KEY": "AIza" + "Q" * 35, "GOOGLE_API_KEY": "AIza" + "R" * 35,
              "MISTRAL_API_KEY": "mistral-value-" + "S" * 20, "OPENAI_API_KEY": "sk-" + "T" * 30}


def mod(name: str):
    return importlib.import_module(f"tools.outsourcing.{name}")


# ---------------------------------------------------------------- simulated time

class SimClock:
    """clock() gives POSIX seconds; sleep(s) advances the simulated time and records the call."""

    def __init__(self) -> None:
        self.now = START.timestamp()
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0, seconds
        self.sleeps.append(seconds)
        self.now += seconds


class TopRandom(random.Random):
    """Always draws the top of the range, so the longest permitted wait is the one observed."""

    def random(self) -> float:
        return 1.0 - 1e-12

    def uniform(self, a: float, b: float) -> float:
        return max(a, b)


# ---------------------------------------------------------------- pool files

def provider(api: str, **limits) -> dict:
    base = {"api": api, "enabled": True, "tier": "free", "verified_on": "2026-10-10", "data_use": "scratch",
            "base_url": "https://generativelanguage.googleapis.com" if api == "gemini" else "https://api.mistral.ai/v1",
            "day_reset": "America/Los_Angeles" if api == "gemini" else "UTC"}
    base.update(limits)
    return base


def model(prov: str, rank: int, **limits) -> dict:
    base = {"provider": prov, "rank": rank, "risk_tiers": ["T1", "T2", "T3"], "max_input_tokens": 100000,
            "max_output_tokens": 2048}
    base.update(limits)
    return base


def write_pool(tmp_path: Path, models: dict, providers: dict | None = None, share=1, safety=1.0) -> Path:
    data = {"notes": "scratch pool for acceptance tests", "share": share, "safety": safety,
            "providers": providers or {"gemini": provider("gemini"), "mistral": provider("openai")},
            "models": models}
    path = tmp_path / "pool.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def governor_for(pool_path: Path, state: Path, clock: SimClock, rng: random.Random | None = None):
    pool = mod("limits").load_pool(pool_path)
    gov = mod("governor").Governor(pool, state, clock, clock.sleep, rng or random.Random(7))
    return pool, gov


def window_max(starts: list[float]) -> int:
    return max(sum(1 for t in starts if s <= t < s + 60) for s in starts)


def run_slots(gov, clock: SimClock, name: str, n: int, tokens: int = 100) -> list[float]:
    starts = []
    for _ in range(n):
        gov.wait_for_slot(name, tokens)
        starts.append(clock())
        gov.record_result(name, tokens, 10)
    return starts


# ---------------------------------------------------------------- local HTTP stand-in

GEMINI_OK = {"candidates": [{"content": {"role": "model", "parts": [{"text": "hello"}]}, "finishReason": "STOP"}],
             "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3}, "modelVersion": "scratch-001"}
OPENAI_OK = {"id": "x", "model": "scratch", "choices": [{"index": 0, "finish_reason": "stop",
                                                       "message": {"role": "assistant", "content": "hello"}}],
             "usage": {"prompt_tokens": 12, "completion_tokens": 3}}


def gemini_429(quota_id: str, value: str, retry: str | None = None) -> tuple[int, dict, str]:
    details = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaMetric": "generativelanguage.googleapis.com/x", "quotaId": quota_id,
                                "quotaValue": value}]}]
    if retry:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry})
    body = {"error": {"code": 429, "message": "Resource has been exhausted", "status": "RESOURCE_EXHAUSTED",
                      "details": details}}
    return 429, {}, json.dumps(body)


class StandIn:
    """Replays `script` for generation requests; answers countTokens with `count`; records each request."""

    def __init__(self, clock: SimClock, script: list[tuple[int, dict, str]], count: int = 50) -> None:
        self.clock, self.script, self.count = clock, deque(script), count
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output quiet
                return

            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8") if length else ""
                outer.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                                       "body": body, "at": outer.clock()})
                if self.path.endswith(":countTokens"):
                    status, headers, text = 200, {}, json.dumps({"totalTokens": outer.count})
                else:
                    assert outer.script, f"unscripted request {self.command} {self.path}"
                    status, headers, text = outer.script.popleft()
                data = text.encode("utf-8")
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _answer

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "StandIn":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()

    def generations(self) -> list[dict]:
        return [r for r in self.requests if r["path"].endswith((":generateContent", "/chat/completions"))]


def ok(api: str, headers: dict | None = None) -> tuple[int, dict, str]:
    return 200, headers or {}, json.dumps(GEMINI_OK if api == "gemini" else OPENAI_OK)


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    for name, value in KEY_VALUES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def chat_request(system: str = "You are the implementer.", text: str = "Write the step.", max_out: int = 100000):
    chat = mod("chat")
    return chat.ChatRequest(system=system, turns=(chat.Turn(role="user", text=text),), max_output_tokens=max_out)


def client(api: str, pool, name: str, gov, url: str):
    if api == "gemini":
        return mod("gemini_client").GeminiClient(pool.model(name), gov, 5, base_url=url)
    return mod("openai_client").OpenAIClient(pool.model(name), gov, 5, base_url=url)


def setup(tmp_path, models, providers=None, script=(), count=50, rng=None):
    clock = SimClock()
    pool, gov = governor_for(write_pool(tmp_path, models, providers), tmp_path / ".relay/governor.json", clock, rng)
    return clock, pool, gov, StandIn(clock, list(script), count)


# ---------------------------------------------------------------- must-catch 1

def test_FR_1_0_14_mc01_model_rpm_never_exceeded_in_any_window(tmp_path):
    clock = SimClock()
    _, gov = governor_for(write_pool(tmp_path, {"g-a": model("gemini", 1, rpm=5)}), tmp_path / "s.json", clock)
    starts = run_slots(gov, clock, "g-a", 12)
    assert window_max(starts) <= 5
    assert starts[-1] - starts[0] < 180  # paced, not stalled


def test_FR_1_0_14_mc01_provider_rpm_holds_across_its_models(tmp_path):
    providers = {"gemini": provider("gemini", rpm=6), "mistral": provider("openai")}
    clock = SimClock()
    _, gov = governor_for(write_pool(tmp_path, {"g-a": model("gemini", 1, rpm=5), "g-b": model("gemini", 2, rpm=5)},
                                     providers), tmp_path / "s.json", clock)
    starts = []
    for i in range(14):
        name = "g-a" if i % 2 == 0 else "g-b"
        gov.wait_for_slot(name, 100)
        starts.append(clock())
        gov.record_result(name, 100, 10)
    assert window_max(starts) <= 6


def test_FR_1_0_14_mc01_provider_rps_spacing_always_holds(tmp_path):
    providers = {"gemini": provider("gemini"), "mistral": provider("openai", rps=0.5)}
    clock = SimClock()
    _, gov = governor_for(write_pool(tmp_path, {"m-a": model("mistral", 1), "m-b": model("mistral", 2)},
                                     providers), tmp_path / "s.json", clock)
    starts = []
    for i in range(6):
        name = "m-a" if i % 2 == 0 else "m-b"
        gov.wait_for_slot(name, 100)
        starts.append(clock())
        gov.record_result(name, 100, 10)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert min(gaps) >= 2.0 - 1e-6  # share / (rps x safety) = 1 / 0.5


def test_FR_1_0_14_mc01_effective_rpm_from_the_real_pool_file(tmp_path):
    # The real pool's best-ranked enabled model: its lower per-minute request limit (model or provider) x safety
    # / share, rounded down, is the most requests in any 60 seconds (B2).
    data = json.loads((ROOT / "config/aqis_lab/model_pool.json").read_text(encoding="utf-8"))
    enabled = [n for n, m in data["models"].items() if data["providers"][m["provider"]]["enabled"]]
    name = min(enabled, key=lambda n: data["models"][n]["rank"])
    rpms = [r for r in (data["models"][name].get("rpm"), data["providers"][data["models"][name]["provider"]].get("rpm")) if r]
    expected = max(1, math.floor(min(rpms) * data["safety"] / data["share"]))
    clock = SimClock()
    _, gov = governor_for(ROOT / "config/aqis_lab/model_pool.json", tmp_path / "s.json", clock)
    starts = run_slots(gov, clock, name, expected + 4)
    assert window_max(starts) == expected


# ---------------------------------------------------------------- must-catch 2

def test_FR_1_0_14_mc02_input_tokens_within_tpm_in_any_window(tmp_path):
    clock = SimClock()
    _, gov = governor_for(write_pool(tmp_path, {"g-a": model("gemini", 1, tpm_input=1000)}), tmp_path / "s.json", clock)
    starts = run_slots(gov, clock, "g-a", 8, tokens=400)
    assert window_max(starts) * 400 <= 1000


def test_FR_1_0_14_mc02_provider_tpm_holds_across_its_models(tmp_path):
    providers = {"gemini": provider("gemini"), "mistral": provider("openai", tpm_input=1000)}
    clock = SimClock()
    _, gov = governor_for(write_pool(tmp_path, {"m-a": model("mistral", 1), "m-b": model("mistral", 2)}, providers),
                          tmp_path / "s.json", clock)
    starts = []
    for i in range(8):
        name = "m-a" if i % 2 == 0 else "m-b"
        gov.wait_for_slot(name, 300)
        starts.append(clock())
        gov.record_result(name, 300, 10)
    assert window_max(starts) * 300 <= 1000


# ---------------------------------------------------------------- must-catch 3

def assert_reset_triplet(exc, utc: datetime, provider_zone_hour: int) -> None:
    assert exc.reset_utc == utc
    assert exc.reset_karachi == utc and exc.reset_karachi.utcoffset() == timedelta(hours=5)
    assert exc.reset_provider == utc and exc.reset_provider.hour == provider_zone_hour


def test_FR_1_0_14_mc03_gemini_daily_rejection_stops_at_once_with_resets(tmp_path):
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, rpd=20)},
                                    script=[gemini_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "20")])
    with stand:
        with pytest.raises(mod("chat").DailyQuotaExhausted) as info:
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1
    assert info.value.period == "day" and info.value.model == "g-a" and info.value.provider == "gemini"
    # Next midnight in Los Angeles after 05:00 PDT on 10 October: 07:00 UTC, 12:00 in Karachi.
    assert_reset_triplet(info.value, datetime(2026, 10, 11, 7, 0, tzinfo=timezone.utc), 0)
    assert gov.exhausted_until("g-a") is not None
    _, second = governor_for(tmp_path / "pool.json", tmp_path / ".relay/governor.json", clock)
    assert second.exhausted_until("g-a") is not None


def test_FR_1_0_14_mc03_provider_scope_daily_marks_every_model_of_the_provider(tmp_path):
    body = json.dumps({"error": {"message": "Daily free-request allowance for your account is used up",
                                 "type": "rate_limit", "code": "daily_limit"}})
    models = {"m-a": model("mistral", 1), "m-b": model("mistral", 2), "g-a": model("gemini", 3)}
    clock, pool, gov, stand = setup(tmp_path, models, script=[(429, {}, body)])
    with stand:
        with pytest.raises(mod("chat").DailyQuotaExhausted) as info:
            client("openai", pool, "m-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1 and info.value.period == "day"
    assert_reset_triplet(info.value, datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc), 0)
    assert gov.exhausted_until("m-a") is not None and gov.exhausted_until("m-b") is not None
    assert gov.exhausted_until("g-a") is None


def test_FR_1_0_14_mc03_monthly_rejection_marks_provider_until_next_month(tmp_path):
    body = json.dumps({"error": {"message": "Monthly token limit reached", "type": "rate_limit"}})
    models = {"m-a": model("mistral", 1), "m-b": model("mistral", 2)}
    clock, pool, gov, stand = setup(tmp_path, models, script=[(429, {}, body)])
    with stand:
        with pytest.raises(mod("chat").DailyQuotaExhausted) as info:
            client("openai", pool, "m-b", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1 and info.value.period == "month"
    assert_reset_triplet(info.value, datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc), 0)
    for name in models:
        until = gov.exhausted_until(name)
        assert until is not None and until >= datetime(2026, 11, 1, tzinfo=timezone.utc) - timedelta(seconds=1)


def test_FR_1_0_14_mc03_reaching_the_daily_count_exhausts_without_asking(tmp_path):
    clock = SimClock()
    pool_path = write_pool(tmp_path, {"g-a": model("gemini", 1, rpd=3)})
    _, gov = governor_for(pool_path, tmp_path / "s.json", clock)
    run_slots(gov, clock, "g-a", 3)
    assert gov.remaining_today("g-a") == 0 and gov.exhausted_until("g-a") is not None
    _, restarted = governor_for(pool_path, tmp_path / "s.json", clock)
    assert restarted.remaining_today("g-a") == 0 and restarted.exhausted_until("g-a") is not None


# ---------------------------------------------------------------- must-catch 4

def test_FR_1_0_14_mc04_minute_rejection_waits_retry_delay_and_slows_down(tmp_path):
    script = [gemini_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "5", "37s"), ok("gemini")]
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, rpm=5)}, script=script)
    with stand:
        reply = client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    first, second = stand.generations()
    assert reply.text == "hello" and second["at"] - first["at"] >= 37
    assert gov.report().models["g-a"].adaptive_factor == pytest.approx(0.75)


def test_FR_1_0_14_mc04_six_minute_rejections_raise_service_busy(tmp_path):
    script = [gemini_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "5", "5s")] * 7
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, rpm=5)}, script=script)
    with stand:
        with pytest.raises(mod("chat").ServiceBusy):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 7  # the first request and six retries


# ---------------------------------------------------------------- must-catch 5

@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_mc05_overload_backs_off_exponentially_then_service_busy(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    script = [(503, {}, json.dumps({"error": {"code": 503, "status": "UNAVAILABLE", "message": "overloaded"}}))] * 6
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=script, rng=TopRandom())
    with stand:
        with pytest.raises(mod("chat").ServiceBusy):
            client(api, pool, "x-a", gov, stand.url).generate(chat_request())
    times = [r["at"] for r in stand.generations()]
    assert len(times) == 6  # the first request and five retries
    gaps = [b - a for a, b in zip(times, times[1:])]
    # Full jitter drawn at the top of its range: min(120, 5 x 3^k) for k = 0..4.
    assert gaps == pytest.approx([5, 15, 45, 120, 120], abs=1e-6)


# ---------------------------------------------------------------- must-catch 6

def test_FR_1_0_14_mc06_over_max_input_tokens_is_not_sent_gemini(tmp_path):
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, max_input_tokens=1000)}, count=1500)
    with stand:
        with pytest.raises(mod("chat").StepTooLarge):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert stand.generations() == []


def test_FR_1_0_14_mc06_over_whole_minute_allowance_is_not_sent(tmp_path):
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1, tpm_input=800)}, count=900)
    with stand:
        with pytest.raises(mod("chat").StepTooLarge):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert stand.generations() == []


def test_FR_1_0_14_mc06_openai_estimate_over_limit_is_not_sent(tmp_path):
    clock, pool, gov, stand = setup(tmp_path, {"m-a": model("mistral", 1, max_input_tokens=1000)})
    with stand:
        with pytest.raises(mod("chat").StepTooLarge):
            client("openai", pool, "m-a", gov, stand.url).generate(chat_request(system="x" * 5000))
    assert stand.requests == []


def test_FR_1_0_14_mc06_minute_token_rejection_above_server_limit_is_not_retried(tmp_path):
    script = [gemini_429("GenerateContentInputTokensPerModelPerMinute-FreeTier", "500", "30s"), ok("gemini")]
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1)}, script=script, count=700)
    with stand:
        with pytest.raises(mod("chat").StepTooLarge):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1


# ---------------------------------------------------------------- must-catch 7

def test_FR_1_0_14_mc07_restart_keeps_window_and_counts(tmp_path):
    providers = {"gemini": provider("gemini"), "mistral": provider("openai", tokens_per_month=1000)}
    pool_path = write_pool(tmp_path, {"g-a": model("gemini", 1, rpm=3, rpd=10), "m-a": model("mistral", 2)}, providers)
    clock = SimClock()
    _, first = governor_for(pool_path, tmp_path / "s.json", clock)
    starts = run_slots(first, clock, "g-a", 3)
    first.wait_for_slot("m-a", 600)
    first.record_result("m-a", 600, 500)
    _, second = governor_for(pool_path, tmp_path / "s.json", clock)
    assert second.delay_for("g-a", 100) >= starts[0] + 60 - clock() - 1e-6 > 0
    assert second.remaining_today("g-a") == 7
    assert second.exhausted_until("m-a") is not None  # 1,100 tokens this month against 1,000
    second.wait_for_slot("g-a", 100)
    assert clock() >= starts[0] + 60 - 1e-6


# ---------------------------------------------------------------- must-catch 8

@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_mc08_no_key_in_any_request(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    script = [ok(api), (200, {}, json.dumps({"models": [{"name": "models/x-a"}]} if api == "gemini"
                                            else {"data": [{"id": "x-a"}]}))]
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=script)
    with stand:
        cl = client(api, pool, "x-a", gov, stand.url)
        cl.count_tokens(chat_request())
        cl.generate(chat_request())
        assert cl.list_models() == ["x-a"]
    assert stand.requests
    for req in stand.requests:
        names = {k.lower() for k in req["headers"]}
        assert not names & {"x-goog-api-key", "authorization", "api-key", "x-api-key"}, req["headers"]
        assert "key=" not in req["path"].lower()
        blob = json.dumps(req)
        for value in KEY_VALUES.values():
            assert value not in blob


# ---------------------------------------------------------------- must-catch 9

@pytest.mark.parametrize("header_value, expected_max", [("3", 3), ("100", 6)], ids=["lower", "higher"])
def test_FR_1_0_14_mc09_server_limit_lowers_but_never_raises(tmp_path, header_value, expected_max):
    script = [ok("openai", {"x-ratelimit-limit-requests": header_value})] * 9
    clock, pool, gov, stand = setup(tmp_path, {"m-a": model("mistral", 1, rpm=6)}, script=script)
    with stand:
        cl = client("openai", pool, "m-a", gov, stand.url)
        for _ in range(9):
            cl.generate(chat_request())
    assert window_max([r["at"] for r in stand.generations()]) == expected_max


def test_FR_1_0_14_mc09_quota_value_zero_raises_model_error_without_retry(tmp_path):
    script = [gemini_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "0")]
    clock, pool, gov, stand = setup(tmp_path, {"g-a": model("gemini", 1)}, script=script)
    with stand:
        with pytest.raises(mod("chat").ModelError):
            client("gemini", pool, "g-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1


def test_FR_1_0_14_mc09_http_402_raises_model_error_without_retry(tmp_path):
    script = [(402, {}, json.dumps({"error": {"message": "Payment required"}}))]
    clock, pool, gov, stand = setup(tmp_path, {"m-a": model("mistral", 1)}, script=script)
    with stand:
        with pytest.raises(mod("chat").ModelError):
            client("openai", pool, "m-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1


# ---------------------------------------------------------------- must-catch 10

KEY_INVALID = json.dumps({"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT",
                                    "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                                                 "reason": "API_KEY_INVALID", "domain": "googleapis.com"}]}})


@pytest.mark.parametrize("api, status, body, error", [
    ("gemini", 400, KEY_INVALID, "CredentialError"),
    ("openai", 401, json.dumps({"error": {"message": "Unauthorized"}}), "CredentialError"),
    ("gemini", 418, "short and stout", "ApiError"),
    ("openai", 418, "short and stout", "ApiError"),
], ids=["gemini-key-invalid", "openai-401", "gemini-unclassified", "openai-unclassified"])
def test_FR_1_0_14_mc10_credential_and_unclassified_errors_are_not_retried(tmp_path, api, status, body, error):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1)}, script=[(status, {}, body)])
    with stand:
        with pytest.raises(getattr(mod("chat"), error)):
            client(api, pool, "x-a", gov, stand.url).generate(chat_request())
    assert len(stand.generations()) == 1


# ---------------------------------------------------------------- must-catch 11

@pytest.mark.parametrize("api", ["gemini", "openai"])
def test_FR_1_0_14_mc11_no_temperature_and_output_capped_at_model_limit(tmp_path, api):
    prov = "gemini" if api == "gemini" else "mistral"
    clock, pool, gov, stand = setup(tmp_path, {"x-a": model(prov, 1, max_output_tokens=2048)}, script=[ok(api)])
    with stand:
        reply = client(api, pool, "x-a", gov, stand.url).generate(chat_request(max_out=100000))
    assert reply.text == "hello" and reply.finish == "STOP"
    assert (reply.prompt_tokens, reply.output_tokens) == (12, 3)
    (request,) = stand.generations()
    body = json.loads(request["body"])
    assert "temperature" not in json.dumps(body).lower()
    if api == "gemini":
        assert body["generationConfig"]["maxOutputTokens"] == 2048
        assert body["systemInstruction"]
    else:
        assert body["max_tokens"] == 2048 and body["model"] == "x-a"
        assert body["messages"][0]["role"] == "system"
