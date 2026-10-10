"""Acceptance tests for WO-1.0-11 (FR-1.0-02, FR-1.0-13, FR-1.0-14, NFR-1.0-03): relay orchestration.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus the dry-run, status and output-limit
checks the spec's acceptance commands need. Modules are imported inside the tests, so a missing module fails each
test on its own instead of aborting collection.

End-to-end tests run `python -m tools.outsourcing.relay` as a subprocess inside a scratch repository:
- the repository holds a work branch `claude/wp-9-9-scratch` and a local bare `origin`;
- a two-step `api` order is WO-9.9-03 (T1);
- a scratch pool has two Gemini-shaped models and OpenAI-shaped models;
- `--api-base` points every provider at a local HTTP stand-in.

The stand-in answers each generation request with a valid bundle for exactly the files the request's THIS STEP block
(or a fix order's file list) names, unless a test scripts something else for that model. The pool sets no
per-minute limits, so no run waits.
"""
from __future__ import annotations

import importlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WO = "WO-9.9-03"
WP_BRANCH = "claude/wp-9-9-scratch"
WO_BRANCH = f"wo/{WO}"
ORDER_REL = f"docs/outsourcing/orders/{WO}.md"
CONTEXT = "docs/notes/context.md"
READ_ONLY = "tests/aqis_lab/demo/test_acceptance_demo.py"
# The scratch package is lab_demo, not tools/demo: `python -m tools.outsourcing.relay` puts the scratch checkout first
# on sys.path, and a scratch `tools` package would shadow the repository's own `tools` package.
STEPS = (("lab_demo/alpha.py", "tests/aqis_lab/demo/test_alpha.py"),
         ("lab_demo/beta.py", "tests/aqis_lab/demo/test_beta.py"))
OUTPUTS = tuple(p for s in STEPS for p in s)
RECORDS = (f"docs/outsourcing/returns/{WO}/", f"docs/outsourcing/ledger.d/{WO}.md")
OWNER_FILES = ("docs/process/PROTECTED_PATHS.txt", "docs/process/outsourcing/FOUNDATION.md",
               "docs/process/outsourcing/templates/RETURN_FORMAT.md",
               "docs/process/outsourcing/templates/FIX_ORDER.md")
KEY_VALUES = {"GEMINI_API_KEY": "AIza" + "K" * 35, "GOOGLE_API_KEY": "AIza" + "L" * 35,
              "MISTRAL_API_KEY": "mistral-keyvalue-" + "M" * 20, "OPENAI_API_KEY": "sk-" + "N" * 30}
BLOCK_RE = re.compile(r"^=== (CONTEXT|INTERFACE|ACCEPTED INTERFACE|ACCEPTED|CURRENT): (\S+) ===$", re.M)
PATH_RE = re.compile(r"[\w./-]+\.py")


def mod(name: str):
    return importlib.import_module(f"tools.outsourcing.{name}")


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "AQIS Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "AQIS Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return env


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True,
                          text=True, env=git_env(), timeout=60)
    if check:
        assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout if proc.returncode == 0 else ""


# ---------------------------------------------------------------- scratch files

def header(name: str) -> str:
    return (f'"""Scratch module {name} for the WO-1.0-11 acceptance tests.\n\nCAPABILITIES:\n'
            f"  CAP-DEMO-011: returns a constant [tests: test_{name}]\n"
            "INPUTS AND OUTPUTS: nothing in, one constant out.\nCONTRACTS: none.\nINVARIANTS:\n"
            "  - The constant never changes.\nNOT IN SCOPE:\n  - Anything else.\nCHANGE LOG:\n"
            '  2026-10-10 WP-9.9 FR-9.9-01 created.\n"""\n')


def good_content(path: str) -> str:
    name = Path(path).stem
    if path.startswith("lab_demo/"):
        return header(name) + f'from __future__ import annotations\n\n__all__ = ["VALUE"]\n\nVALUE = {len(name)}\n'
    target = name.removeprefix("test_")
    return (header(name) + f"from lab_demo.{target} import VALUE\n\n\n"
            f"def test_{target}():\n    assert VALUE == {len(target)}\n")


def order_text(model: str = "default", tier: str = "T1") -> str:
    lines = ["---", f"id: {WO}", "wp: WP-9.9", "title: Scratch relay order", f"model: {model}", "channel: api",
             "attempt_budget: 2", f"risk_tier: {tier}", "max_output_tokens: 8000", "context:", f"  - {CONTEXT}",
             "outputs:"] + [f"  - {p}" for p in OUTPUTS]
    lines += ["steps:"] + [f"  - {', '.join(s)}" for s in STEPS]
    lines += ["read_only_tests:", f"  - {READ_ONLY}", "allowed_dependencies:", "  - stdlib", "verify:",
              "  - .venv/bin/python -m pytest tests/aqis_lab/demo -q", "---", "", f"# {WO} — scratch relay order",
              "", "Write two constants and their tests.", ""]
    return "\n".join(lines)


def model(prov: str, rank: int, tiers=("T1", "T2", "T3"), **extra) -> dict:
    base = {"provider": prov, "rank": rank, "risk_tiers": list(tiers), "max_input_tokens": 128000,
            "max_output_tokens": 8192}
    base.update(extra)
    return base


def default_models() -> dict:
    return {"g-one": model("gemini", 1), "g-two": model("gemini", 2), "m-one": model("mistral", 3)}


def write_pool(path: Path, models: dict, enabled=("gemini", "mistral")) -> Path:
    providers = {
        "gemini": {"api": "gemini", "base_url": "https://generativelanguage.googleapis.com", "enabled": "gemini" in enabled,
                   "tier": "free", "verified_on": "2026-10-10", "day_reset": "America/Los_Angeles", "data_use": "scratch"},
        "mistral": {"api": "openai", "base_url": "https://api.mistral.ai/v1", "enabled": "mistral" in enabled,
                    "tier": "free", "verified_on": "2026-10-10", "day_reset": "UTC", "data_use": "scratch"}}
    path.write_text(json.dumps({"notes": "scratch", "share": 1, "safety": 1.0, "providers": providers,
                                "models": models}, indent=2), encoding="utf-8")
    return path


class Scratch:
    def __init__(self, tmp_path: Path, order: str | None = None) -> None:
        self.tmp = tmp_path
        self.origin = tmp_path / "origin.git"
        self.root = tmp_path / "work"
        self.pool = write_pool(tmp_path / "pool.json", default_models())
        git(tmp_path, "init", "-q", "--bare", str(self.origin))
        self.root.mkdir()
        for rel in OWNER_FILES:
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, self.root / rel)
        files = {CONTEXT: "Context for the scratch order.\n", "docs/other.md": "OTHER-MARKER never sent.\n",
                 "lab_demo/__init__.py": "", ".gitignore": ".relay/\n__pycache__/\n",
                 READ_ONLY: "def test_demo():\n    assert 1 + 1 == 2\n", ORDER_REL: order or order_text()}
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "init", "-q")
        git(self.root, "checkout", "-qb", WP_BRANCH)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "remote", "add", "origin", str(self.origin))
        git(self.root, "push", "-q", "origin", WP_BRANCH)
        self.wp_head = self.sha(WP_BRANCH)

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text, encoding="utf-8")

    def sha(self, ref: str) -> str:
        return git(self.root, "rev-parse", "--verify", "--quiet", ref, check=False).strip()

    def show(self, ref: str, rel: str) -> str:
        return git(self.root, "show", f"{ref}:{rel}", check=False)

    def relay(self, url: str, *args: str, pool: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(git_env(), PYTHONPATH=str(ROOT), NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        env.update(KEY_VALUES)
        cmd = [sys.executable, "-m", "tools.outsourcing.relay", *args, "--pool", str(pool or self.pool),
               "--api-base", url, "--timeout", "20", "--verify-timeout", "180"]
        proc = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, env=env, timeout=900)
        assert len(proc.stdout.splitlines()) <= 25, proc.stdout  # NFR-1.0-03
        return proc

    def run(self, url: str, *args: str, pool: Path | None = None) -> subprocess.CompletedProcess:
        return self.relay(url, "--wo", ORDER_REL, *args, pool=pool)

    def branch_paths(self) -> set[str]:
        out = git(self.root, "log", "--name-only", "--format=", f"{self.wp_head}..{WO_BRANCH}", check=False)
        return {line for line in out.splitlines() if line}


# ---------------------------------------------------------------- local HTTP stand-in

def bundle(files: dict[str, str]) -> str:
    parts = ["=== MANIFEST ===", "| path | action | purpose |", "| --- | --- | --- |"]
    parts += [f"| {p} | create | scratch |" for p in files]
    parts.append("=== END MANIFEST ===")
    for path, text in files.items():
        parts += [f"=== FILE: {path} ===", text.rstrip("\n"), "=== END FILE ==="]
    parts += ["=== DOD ===", "| item | met at (file:line) | how |", "| --- | --- | --- |",
              f"| D1 | {next(iter(files), 'none')}:1 | scratch |", "=== END DOD ==="]
    return "\n".join(parts) + "\n"


def requested_paths(text: str) -> list[str]:
    if "=== THIS STEP ===" in text:
        block = text.rsplit("=== THIS STEP ===", 1)[1].split("=== END THIS STEP ===", 1)[0]
        return PATH_RE.findall(block.split("each complete:", 1)[1].split("Files from earlier steps", 1)[0])
    listed = text.rsplit("## Files you may change", 1)[1].split("\n## ", 1)[0]
    return PATH_RE.findall(listed)


class StandIn:
    """Answers both API shapes. `script[model]` holds actions used before the default action 'auto':
    ('auto',) a valid bundle; ('override', {path: text}) a bundle with some files replaced; ('questions',);
    ('cut',) an answer stopped by the output limit; ('status', code, body) an error response."""

    def __init__(self, listing=None, count: int = 3000) -> None:
        self.script: dict[str, deque] = defaultdict(deque)
        self.requests: list[dict] = []
        self.usage = {"prompt": 0, "output": 0}
        self.listing = listing or {"gemini": ["g-one", "g-two"], "openai": ["m-one", "m-two"]}
        self.count = count
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output quiet
                return

            def _send(self, status: int, payload) -> None:
                data = (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                outer.record(self, "")
                if self.path.startswith("/v1beta/models"):
                    self._send(200, {"models": [{"name": f"models/{m}"} for m in outer.listing["gemini"]]})
                else:
                    self._send(200, {"data": [{"id": m} for m in outer.listing["openai"]]})

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8")
                entry = outer.record(self, body)
                if self.path.endswith(":countTokens"):
                    self._send(200, {"totalTokens": outer.count})
                    return
                status, payload = outer.answer(entry)
                self._send(status, payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def record(self, handler, body: str) -> dict:
        data = json.loads(body) if body else {}
        if handler.path.endswith(":generateContent"):
            api, name = "gemini", handler.path.split("/models/", 1)[1].split(":", 1)[0]
            text = data["contents"][-1]["parts"][0]["text"]
        elif handler.path.endswith("/chat/completions"):
            api, name, text = "openai", data.get("model", ""), data["messages"][-1]["content"]
        else:
            api, name, text = "", "", ""
        entry = {"method": handler.command, "path": handler.path, "headers": dict(handler.headers), "body": body,
                 "api": api, "model": name, "text": text}
        with self.lock:
            self.requests.append(entry)
        return entry

    def generations(self, name: str | None = None) -> list[dict]:
        return [r for r in self.requests if r["api"] and (name is None or r["model"] == name)]

    def answer(self, entry: dict):
        with self.lock:
            action = self.script[entry["model"]].popleft() if self.script[entry["model"]] else ("auto",)
        if action[0] == "status":
            return action[1], action[2]
        if action[0] == "questions":
            text, finish = "=== QUESTIONS ===\n1. QUESTION-MARKER: which constant?\n=== END QUESTIONS ===\n", "stop"
        elif action[0] == "cut":
            text, finish = "=== MANIFEST ===\n| path | action | purpose |\n", "length"
        else:
            files = {p: good_content(p) for p in requested_paths(entry["text"])}
            if action[0] == "override":
                files.update({p: t for p, t in action[1].items() if p in files})
            text, finish = bundle(files), "stop"
        prompt, output = 1000 + len(self.requests), 200
        with self.lock:
            self.usage["prompt"] += prompt
            self.usage["output"] += output
        if entry["api"] == "gemini":
            reason = {"stop": "STOP", "length": "MAX_TOKENS"}[finish]
            return 200, {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": reason}],
                         "usageMetadata": {"promptTokenCount": prompt, "candidatesTokenCount": output},
                         "modelVersion": "scratch-001"}
        return 200, {"id": "x", "model": entry["model"], "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": text}}],
                     "usage": {"prompt_tokens": prompt, "completion_tokens": output}}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stand():
    server = StandIn()
    yield server
    server.close()


@pytest.fixture
def scratch(tmp_path):
    return Scratch(tmp_path)


def gemini_daily() -> tuple:
    return ("status", 429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "exhausted", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
            {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]}]}})


KEY_INVALID = ("status", 400, {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT",
                                         "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                                                      "reason": "API_KEY_INVALID"}]}})


def step_of(entry: dict) -> list[str]:
    return requested_paths(entry["text"]) if "=== THIS STEP ===" in entry["text"] else []


# ---------------------------------------------------------------- must-catch 1, 8, 11 (one accepted run)

def test_FR_1_0_02_mc01_mc08_mc11_accepted_run_end_to_end(scratch, stand):
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"git merge --no-ff {WO_BRANCH}" in proc.stdout
    # must-catch 1: only allowed files in any request, and no key anywhere.
    allowed = {CONTEXT, READ_ONLY, *OUTPUTS}
    assert stand.generations()
    for entry in stand.requests:
        assert {m.group(2) for m in BLOCK_RE.finditer(entry["text"])} <= allowed
        assert "OTHER-MARKER" not in entry["body"]
        assert not {k.lower() for k in entry["headers"]} & {"x-goog-api-key", "authorization", "x-api-key"}
        assert "key=" not in entry["path"].lower()
        for value in KEY_VALUES.values():
            assert value not in json.dumps(entry)
    for path in scratch.root.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(scratch.root).parts[:1]:
            data = path.read_bytes()
            assert not any(v.encode() in data for v in KEY_VALUES.values()), path
    # must-catch 8: only outputs and record files, only on wo/<WO>; the work branch and checkout untouched.
    assert scratch.branch_paths() <= set(OUTPUTS) | {p for p in scratch.branch_paths() if p.startswith(RECORDS)}
    assert set(OUTPUTS) <= scratch.branch_paths()
    assert scratch.sha(WP_BRANCH) == scratch.wp_head and scratch.sha(f"origin/{WP_BRANCH}") == scratch.wp_head
    assert git(scratch.root, "ls-remote", "origin", WO_BRANCH).split()[0] == scratch.sha(WO_BRANCH)
    assert git(scratch.root, "rev-parse", "--abbrev-ref", "HEAD").strip() == WP_BRANCH
    assert git(scratch.root, "status", "--porcelain", "--untracked-files=no") == ""
    assert not (scratch.root / ".relay/wt" / WO).exists()
    # must-catch 11: the ledger holds the usage totals and every part's model and provider.
    ledger = scratch.show(WO_BRANCH, f"docs/outsourcing/ledger.d/{WO}.md")
    fields = dict(re.findall(r"^([A-Za-z ]+):\s*(.*?)\s*$", ledger, re.M))
    assert int(fields["Prompt tokens"]) == stand.usage["prompt"]
    assert int(fields["Output tokens"]) == stand.usage["output"]
    assert fields["Result"] == "ACCEPTED" and "g-one (gemini)" in fields["Model"]
    assert scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/steps.md")
    summary = scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/summary.md")
    assert "ACCEPTED" in summary and "g-one" in summary and "gemini" in summary


# ---------------------------------------------------------------- must-catch 2

def test_FR_1_0_02_mc02_t1_order_never_goes_to_a_model_without_t1(scratch, stand):
    models = {"g-low": model("gemini", 1, tiers=("T2", "T3")), **default_models()}
    pool = write_pool(scratch.tmp / "pool-t1.json", models)
    assert scratch.run(stand.url, pool=pool).returncode == 0
    assert stand.generations("g-low") == [] and stand.generations("g-one")


def test_FR_1_0_02_mc02_pinned_model_without_the_tier_exits_2(tmp_path, stand):
    scratch = Scratch(tmp_path, order_text(model="g-low"))
    pool = write_pool(tmp_path / "pool-t1.json", {"g-low": model("gemini", 1, tiers=("T2", "T3")), **default_models()})
    assert scratch.run(stand.url, pool=pool).returncode == 2
    assert stand.generations() == []


def test_FR_1_0_02_mc02_router_skips_models_without_the_tier(scratch):
    pool = mod("limits").load_pool(write_pool(scratch.tmp / "p.json",
                                              {"g-low": model("gemini", 1, tiers=("T3",)), **default_models()}))
    gov = mod("governor").Governor(pool, scratch.tmp / "g.json", time.time, lambda s: None, random.Random(1))
    order = mod("workorder").load_work_order(scratch.root / ORDER_REL, scratch.root)
    router = mod("router").Router(pool, gov, mod("router").model_stats(scratch.root))
    assert router.choose(order, 5000, set()).name == "g-one"
    assert router.choose(order, 5000, {"g-one", "g-two"}).name == "m-one"


# ---------------------------------------------------------------- must-catch 3

def test_FR_1_0_02_mc03_daily_quota_switches_without_using_an_attempt(scratch, stand):
    stand.script["g-one"].append(gemini_daily())
    proc = scratch.run(stand.url, "--attempts", "1")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(stand.generations("g-one")) == 1 and stand.generations("g-two")


def test_FR_1_0_02_mc03_pool_exhausted_pauses_then_resumes_at_the_same_part(scratch, stand):
    pool = write_pool(scratch.tmp / "pool-g.json", {"g-one": model("gemini", 1), "g-two": model("gemini", 2)})
    stand.script["g-one"].extend([("auto",), gemini_daily()])
    stand.script["g-two"].append(gemini_daily())
    proc = scratch.run(stand.url, pool=pool)
    assert proc.returncode == 11, proc.stdout + proc.stderr
    assert "tools.outsourcing.relay" in proc.stdout and "UTC" in proc.stdout
    assert set(STEPS[0]) <= scratch.branch_paths() and not set(STEPS[1]) & scratch.branch_paths()
    first_run = len(stand.requests)
    pool2 = write_pool(scratch.tmp / "pool-gm.json", {"g-one": model("gemini", 1), "g-two": model("gemini", 2),
                                                      "m-one": model("mistral", 3)})
    proc = scratch.run(stand.url, pool=pool2)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    second = [r for r in stand.requests[first_run:] if r["api"]]
    assert second and {r["model"] for r in second} == {"m-one"}
    assert step_of(second[0]) and set(step_of(second[0])) == set(STEPS[1])
    assert not any(set(step_of(r)) & set(STEPS[0]) for r in second)


# ---------------------------------------------------------------- must-catch 4

def write_history(root: Path, wo: str, model_name: str, provider: str, attempts: int, parts: int = 8) -> None:
    steplog, records = mod("steplog"), mod("records")
    log = steplog.parse("").record_run_start(datetime(2026, 10, 1, tzinfo=timezone.utc), "e" * 64,
                                             "claude/wp-9-8-history", model_name)
    for k in range(1, parts + 1):
        log = log.record_accepted(records.StepRecord(
            label=str(k), files=((f"tools/h/{wo.lower()}_{k}.py", "f" * 64),), attempts=attempts, model=model_name,
            provider=provider, model_version="v", prompt_tokens=10, output_tokens=5, seconds_waited=0.0))
    path = root / "docs/outsourcing/returns" / wo / "steps.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(steplog.render(log), encoding="utf-8")


@pytest.mark.parametrize("weak_rate_attempts, demoted", [((2, 2, 2, 2, 2, 2, 2, 2), True),
                                                         ((1, 1, 1, 1, 1, 1, 2, 2), True),
                                                         ((1, 1, 1, 1, 1, 1, 1, 2), False)],
                         ids=["100-points-below", "exactly-25-points-below", "12.5-points-below"])
def test_FR_1_0_02_mc04_low_first_pass_model_is_chosen_after_all_others(scratch, weak_rate_attempts, demoted):
    # g-one: 8 parts with the given attempts; g-two: 8 parts all first time (100%); m-one: only 2 parts, never compared.
    for k, attempts in enumerate(weak_rate_attempts):
        write_history(scratch.root, f"WO-9.8-{k + 10}", "g-one", "gemini", attempts, parts=1)
    write_history(scratch.root, "WO-9.8-02", "g-two", "gemini", 1)
    write_history(scratch.root, "WO-9.8-03", "m-one", "mistral", 1, parts=2)
    pool = mod("limits").load_pool(scratch.pool)
    gov = mod("governor").Governor(pool, scratch.tmp / "g.json", time.time, lambda s: None, random.Random(1))
    order = mod("workorder").load_work_order(scratch.root / ORDER_REL, scratch.root)
    router = mod("router").Router(pool, gov, mod("router").model_stats(scratch.root))
    order_seen = []
    exclude: set[str] = set()
    for _ in range(3):
        name = router.choose(order, 5000, exclude).name
        order_seen.append(name)
        exclude.add(name)
    assert order_seen == (["g-two", "m-one", "g-one"] if demoted else ["g-one", "g-two", "m-one"])


# ---------------------------------------------------------------- must-catch 5

def test_FR_1_0_02_mc05_credential_error_moves_to_other_provider_with_access_line(scratch, stand):
    stand.script["g-one"].append(KEY_INVALID)
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    access = [line for line in proc.stdout.splitlines() if line.startswith("ACCESS:")]
    assert access and "gemini" in access[0]
    assert len(stand.generations("g-one")) == 1 and stand.generations("g-two") == [] and stand.generations("m-one")


def test_FR_1_0_02_mc05_no_provider_left_exits_7(scratch, stand):
    stand.script["g-one"].append(KEY_INVALID)
    stand.script["m-one"].append(("status", 401, {"error": {"message": "Unauthorized"}}))
    proc = scratch.run(stand.url)
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert scratch.branch_paths() & set(OUTPUTS) == set()


# ---------------------------------------------------------------- must-catch 6

def test_FR_1_0_02_mc06_questions_exit_4_keeps_earlier_parts(scratch, stand):
    stand.script["g-one"].extend([("auto",), ("questions",)])
    proc = scratch.run(stand.url)
    assert proc.returncode == 4, proc.stdout + proc.stderr
    paths = scratch.branch_paths()
    assert set(STEPS[0]) <= paths and not set(STEPS[1]) & paths
    assert "QUESTION-MARKER" in scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/summary.md")


# ---------------------------------------------------------------- must-catch 7

def test_FR_1_0_02_mc07_read_only_test_changed_exits_9_and_commits_nothing(scratch, stand):
    tampering = good_content(STEPS[0][1]).replace(
        "    assert VALUE", f"    open({READ_ONLY!r}, 'a').write(chr(10) + 'CHANGED = 1' + chr(10))\n    assert VALUE")
    stand.script["g-one"].append(("override", {STEPS[0][1]: tampering}))
    proc = scratch.run(stand.url)
    assert proc.returncode == 9, proc.stdout + proc.stderr
    assert scratch.sha(WO_BRANCH) in ("", scratch.wp_head)
    assert git(scratch.root, "ls-remote", "origin", WO_BRANCH).split()[:1] in ([], [scratch.wp_head])


# ---------------------------------------------------------------- must-catch 9

def test_FR_1_0_02_mc09_cut_off_two_file_part_is_split_per_file(scratch, stand):
    stand.script["g-one"].append(("cut",))
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    steps = [step_of(r) for r in stand.generations() if step_of(r)]
    assert steps[0] == list(STEPS[0])
    assert steps[1:3] == [[STEPS[0][0]], [STEPS[0][1]]]


def test_FR_1_0_02_mc09_cut_off_one_file_part_exits_5(scratch, stand):
    stand.script["g-one"].extend([("cut",)] * 6)
    proc = scratch.run(stand.url)
    assert proc.returncode == 5, proc.stdout + proc.stderr


# ---------------------------------------------------------------- must-catch 10

def test_FR_1_0_02_mc10_rerun_after_failed_attempt_discards_and_continues(scratch, stand):
    broken = good_content(STEPS[0][1]).replace("assert VALUE == 5", "assert VALUE == 6")
    stand.script["g-one"].append(("override", {STEPS[0][1]: broken}))
    first = scratch.run(stand.url, "--attempts", "1")
    assert first.returncode == 8, first.stdout + first.stderr
    second = scratch.run(stand.url)
    assert second.returncode == 0, second.stdout + second.stderr
    assert scratch.show(WO_BRANCH, STEPS[0][1]) == good_content(STEPS[0][1])


def test_FR_1_0_02_mc10_step_log_of_another_wp_branch_exits_2_before_any_merge(scratch, stand):
    steplog = mod("steplog")
    log = steplog.parse("").record_run_start(datetime(2026, 10, 9, tzinfo=timezone.utc), "a" * 64,
                                             "claude/wp-9-9-other", "default")
    git(scratch.root, "checkout", "-qb", WO_BRANCH)
    scratch.write(f"docs/outsourcing/returns/{WO}/steps.md", steplog.render(log))
    git(scratch.root, "add", "-A")
    git(scratch.root, "commit", "-qm", "step log of another branch")
    git(scratch.root, "push", "-q", "origin", WO_BRANCH)
    git(scratch.root, "checkout", "-q", WP_BRANCH)
    scratch.write("docs/notes/new.md", "A new commit on the work branch that a merge would bring in.\n")
    git(scratch.root, "add", "-A")
    git(scratch.root, "commit", "-qm", "work branch moves on")
    before = scratch.sha(WO_BRANCH)
    proc = scratch.run(stand.url)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "claude/wp-9-9-other" in proc.stdout and WP_BRANCH in proc.stdout
    assert scratch.sha(WO_BRANCH) == before and stand.generations() == []


# ---------------------------------------------------------------- must-catch 12

def test_FR_1_0_14_mc12_models_reports_a_missing_model_and_exits_2(scratch):
    server = StandIn(listing={"gemini": ["g-one"], "openai": ["m-one"]})
    try:
        proc = scratch.relay(server.url, "--models")
    finally:
        server.close()
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert [line for line in proc.stdout.splitlines() if "g-two" in line and "missing" in line.lower()]
    assert server.generations() == []


def test_FR_1_0_14_models_all_present_exits_0(scratch, stand):
    proc = scratch.relay(stand.url, "--models")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stand.generations() == []


# ---------------------------------------------------------------- must-catch 13

def test_FR_1_0_14_mc13_too_large_for_one_model_goes_to_one_that_fits(scratch, stand):
    pool = write_pool(scratch.tmp / "pool-size.json", {"g-one": model("gemini", 1, tpm_input=1000),
                                                       "g-two": model("gemini", 2, tpm_input=1000),
                                                       "m-one": model("mistral", 3)})
    proc = scratch.run(stand.url, "--attempts", "1", pool=pool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stand.generations("g-one") == [] and stand.generations("g-two") == [] and stand.generations("m-one")


def test_FR_1_0_14_mc13_no_model_fits_exits_13(scratch, stand):
    pool = write_pool(scratch.tmp / "pool-small.json", {"g-one": model("gemini", 1, tpm_input=1000),
                                                        "m-one": model("mistral", 2, max_input_tokens=1000)})
    proc = scratch.run(stand.url, pool=pool)
    assert proc.returncode == 13, proc.stdout + proc.stderr
    assert stand.generations() == []


# ---------------------------------------------------------------- dry run and status (AT-1.0-06, AT-1.0-08)

def test_FR_1_0_02_dry_run_measures_and_sends_nothing(scratch, stand):
    proc = scratch.run(stand.url, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stand.requests == [] and scratch.sha(WO_BRANCH) == ""
    assert not (scratch.root / ".relay/wt" / WO).exists()


def test_FR_1_0_14_status_reports_resets_and_sends_nothing(scratch, stand):
    proc = scratch.relay(stand.url, "--status")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stand.requests == []
    for needle in ("g-one", "m-one", "UTC", "Asia/Karachi"):
        assert needle in proc.stdout
