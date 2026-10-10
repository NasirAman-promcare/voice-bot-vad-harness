"""Acceptance tests for WO-1.0-02 (FR-1.0-02): relay building blocks.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus positive controls. Modules are imported
inside the tests, so a missing module fails each test on its own instead of aborting collection.

Each test builds a scratch git repository holding the owner's real PROTECTED_PATHS.txt, FOUNDATION.md,
RETURN_FORMAT.md and FIX_ORDER.md and a three-step order WO-9.9-02. Checks run in that repository with this
interpreter; nothing reaches the network.
"""
from __future__ import annotations

import dataclasses
import importlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORDER_REL = "docs/outsourcing/orders/WO-9.9-02.md"
CONTEXT = "docs/notes/context.md"
INTERFACE = "tools/shared/iface.py"
READ_ONLY = "tests/aqis_lab/demo/test_acceptance_demo.py"
STEPS = (("tools/demo/alpha.py", "tests/aqis_lab/demo/test_alpha.py"),
         ("tools/demo/beta.py", "tests/aqis_lab/demo/test_beta.py"),
         ("tools/demo/gamma.py", "tests/aqis_lab/demo/test_gamma.py"))
OUTPUTS = tuple(p for step in STEPS for p in step)
OWNER_FILES = ("docs/process/PROTECTED_PATHS.txt", "docs/process/outsourcing/FOUNDATION.md",
               "docs/process/outsourcing/templates/RETURN_FORMAT.md",
               "docs/process/outsourcing/templates/FIX_ORDER.md")
KEY_HEADER = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"  # split so this file itself holds no key header
T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
RESULT_CODES = {"ACCEPTED": 0, "INVALID": 2, "QUESTIONS": 4, "CUT_OFF": 5, "SECRET": 6, "CREDENTIAL": 7,
                "EXHAUSTED": 8, "INTEGRITY": 9, "NETWORK": 10, "PAUSED_DAILY": 11, "PAUSED_BUSY": 12,
                "TOO_LARGE": 13, "GIT": 14}


def mod(name: str):
    return importlib.import_module(f"tools.outsourcing.{name}")


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "AQIS Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "AQIS Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return env


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True,
                          text=True, env=git_env(), timeout=60)
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout


def header(name: str) -> str:
    return (f'"""Scratch module {name} for the WO-1.0-02 acceptance tests.\n\nCAPABILITIES:\n'
            f"  CAP-DEMO-001: returns a constant [tests: test_{name}]\n"
            "INPUTS AND OUTPUTS: nothing in, one constant out.\nCONTRACTS: none.\nINVARIANTS:\n"
            "  - The constant never changes.\nNOT IN SCOPE:\n  - Anything else.\nCHANGE LOG:\n"
            '  2026-10-10 WP-9.9 FR-9.9-01 created.\n"""\n')


def module_text(name: str, value: int = 3, extra: str = "") -> str:
    return (header(name) + "from __future__ import annotations\n\n__all__ = [\"VALUE\", \"compute\"]\n\n"
            f"VALUE = {value}\n{extra}\n\ndef compute(x: int) -> int:\n    \"\"\"Add the constant.\"\"\"\n"
            f"    return x + VALUE + {value * 1000}\n")


def scratch_test_source(name: str, body: str = "") -> str:
    return (header(f"test_{name}") + f"from tools.demo.{name} import VALUE\n\n\n"
            f"def test_{name}():\n{body}    assert VALUE == 3\n")


VERIFY_ONE = (".venv/bin/python -c \"open('tests/aqis_lab/demo/test_acceptance_demo.py', 'a')"
              ".write(chr(10) + 'CHANGED = 1' + chr(10))\"")
VERIFY_TWO = ".venv/bin/python -c \"open('verify_two_ran.txt', 'w').write('ran')\""


def order_text(context=(CONTEXT,), verify=(".venv/bin/python -m pytest tests/aqis_lab/demo -q",)) -> str:
    lines = ["---", "id: WO-9.9-02", "wp: WP-9.9", "title: Scratch three-step order", "model: default",
             "channel: api", "attempt_budget: 2", "risk_tier: T2", "max_output_tokens: 12345", "context:"]
    lines += [f"  - {p}" for p in context]
    lines += ["interfaces:", f"  - {INTERFACE}", "outputs:"] + [f"  - {p}" for p in OUTPUTS]
    lines += ["steps:"] + [f"  - {', '.join(step)}" for step in STEPS]
    lines += ["read_only_tests:", f"  - {READ_ONLY}", "allowed_dependencies:", "  - stdlib", "verify:"]
    lines += [f"  - {v}" for v in verify]
    lines += ["---", "", "# WO-9.9-02 — scratch order", "", "ORDER-BODY-MARKER: build three constants.", ""]
    return "\n".join(lines)


IFACE_TEXT = (header("iface") + "from __future__ import annotations\n\n__all__ = [\"answer\"]\n\n\n"
              "def answer(question: str) -> int:\n    \"\"\"Return the answer to a question.\"\"\"\n"
              "    secret_body_marker = 41\n    return secret_body_marker + 1\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for rel in OWNER_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    files = {CONTEXT: "CONTEXT-MARKER: what the implementer reads.\n", "docs/other.md": "OTHER-MARKER: never sent.\n",
             INTERFACE: IFACE_TEXT, "tools/__init__.py": "", "tools/demo/__init__.py": "",
             READ_ONLY: "def test_demo():\n    assert 1 + 1 == 2\n", ORDER_REL: order_text()}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return root


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


def load(root: Path):
    order = mod("workorder").load_work_order(root / ORDER_REL, root)
    return order, mod("workorder").plan_steps(order)


def part(label: str, paths) -> object:
    return mod("records").StepPart(label=label, paths=tuple(paths))


def head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def quick(root: Path, tmp_path: Path, step_paths, base: str):
    order, _ = load(root)
    return mod("checks").quick_checks(order, part("1", step_paths), root, tmp_path / "logs", base, sys.executable, 120)


def names(results) -> list[str]:
    return [r.name for r in results.results]


# ---------------------------------------------------------------- must-catch 1

def build_step_two(repo: Path):
    write(repo, STEPS[0][0], module_text("alpha"))
    write(repo, STEPS[0][1], scratch_test_source("alpha"))
    order, plan = load(repo)
    return mod("prompt").step_request(order, plan, part("2", STEPS[1]), repo)


def test_FR_1_0_02_mc01_step_request_holds_allowed_files_in_order(repo):
    request = build_step_two(repo)
    chat = request.chat
    assert chat.system == (ROOT / OWNER_FILES[1]).read_text(encoding="utf-8")
    assert len(chat.turns) == 1 and chat.turns[0].role == "user"
    text = chat.turns[0].text
    marks = [text.index("ORDER-BODY-MARKER"), text.index(f"=== CONTEXT: {CONTEXT} ==="),
             text.index(f"=== CONTEXT: {READ_ONLY} ==="), text.index(f"=== INTERFACE: {INTERFACE} ==="),
             text.index(f"=== ACCEPTED INTERFACE: {STEPS[0][0]} ==="), text.index(f"=== ACCEPTED: {STEPS[0][1]} ==="),
             text.index("=== THIS STEP ==="), text.index("=== END THIS STEP ==="),
             text.rindex((ROOT / OWNER_FILES[2]).read_text(encoding="utf-8").strip()[:200])]
    assert marks == sorted(marks)
    for closing in ("=== END CONTEXT ===", "=== END INTERFACE ===", "=== END ACCEPTED INTERFACE ===",
                    "=== END ACCEPTED ==="):
        assert closing in text
    assert "OTHER-MARKER" not in text
    allowed = {ORDER_REL, CONTEXT, READ_ONLY, INTERFACE, *STEPS[0], *OWNER_FILES[1:3]}
    assert set(request.sent_paths) <= allowed and {CONTEXT, READ_ONLY, INTERFACE, *STEPS[0]} <= set(request.sent_paths)


def test_FR_1_0_02_mc01_earlier_code_outputs_are_interface_views(repo):
    text = build_step_two(repo).chat.turns[0].text
    alpha = text.split(f"=== ACCEPTED INTERFACE: {STEPS[0][0]} ===", 1)[1].split("=== END", 1)[0]
    assert "def compute(x: int) -> int" in alpha and "Add the constant." in alpha
    assert "3000" not in alpha  # the body's literal stays out of the view
    iface = text.split(f"=== INTERFACE: {INTERFACE} ===", 1)[1].split("=== END", 1)[0]
    assert "def answer(question: str) -> int" in iface and "secret_body_marker" not in iface
    full_test = text.split(f"=== ACCEPTED: {STEPS[0][1]} ===", 1)[1].split("=== END", 1)[0]
    assert "assert VALUE == 3" in full_test  # non-code outputs and tests are sent in full


def test_FR_1_0_02_mc01_step_block_names_exactly_the_part_files(repo):
    text = build_step_two(repo).chat.turns[0].text
    block = text.split("=== THIS STEP ===", 1)[1].split("=== END THIS STEP ===", 1)[0]
    assert "Step 2 of 3." in block
    now, later = block.split("each complete:", 1)[1].split("Later steps will add:", 1)
    path_re = re.compile(r"[\w./-]+\.py")
    assert set(path_re.findall(now.split("Files from earlier steps", 1)[0])) == set(STEPS[1])
    assert set(path_re.findall(later)) == set(STEPS[2])


def test_FR_1_0_02_mc01_missing_earlier_output_is_listed_not_sent(repo):
    write(repo, STEPS[0][0], module_text("alpha"))
    order, plan = load(repo)
    request = mod("prompt").step_request(order, plan, part("2", STEPS[1]), repo)
    assert STEPS[0][1] in request.missing_paths
    assert f"=== ACCEPTED: {STEPS[0][1]} ===" not in request.chat.turns[0].text


# ---------------------------------------------------------------- must-catch 2

@pytest.mark.parametrize("where", ["context", "earlier-output"])
def test_FR_1_0_02_mc02_secret_file_raises_naming_it(repo, where):
    if where == "context":
        write(repo, "docs/notes/key.md", f"notes\n{KEY_HEADER}\nb3BlbnNzaC1rZXktdjEAAAAA\n")
        write(repo, ORDER_REL, order_text(context=(CONTEXT, "docs/notes/key.md")))
        bad = "docs/notes/key.md"
    else:
        write(repo, STEPS[0][0], module_text("alpha", extra='TOKEN = "' + "ghp_" + "Z" * 36 + '"'))
        write(repo, STEPS[0][1], scratch_test_source("alpha"))
        bad = STEPS[0][0]
    order, plan = load(repo)
    prompt = mod("prompt")
    with pytest.raises(prompt.SecretInRequest, match=re.escape(bad)):
        prompt.step_request(order, plan, part("2", STEPS[1]), repo)


# ---------------------------------------------------------------- must-catch 3

def test_FR_1_0_02_mc03_request_carries_only_max_output_tokens_beyond_text(repo):
    request = build_step_two(repo)
    assert {f.name for f in dataclasses.fields(request.chat)} == {"system", "turns", "max_output_tokens"}
    assert request.chat.max_output_tokens == 12345
    assert request.characters == len(request.chat.system) + sum(len(t.text) for t in request.chat.turns)


# ---------------------------------------------------------------- must-catch 4

def failed_result(tmp_path: Path, name: str, lines: int):
    log = tmp_path / f"{name}.log"
    log.write_text("".join(f"LOGLINE-{name}-{i}\n" for i in range(lines)), encoding="utf-8")
    return mod("records").CheckResult(name=name, passed=False, summary=f"{name} failed", log_path=log,
                                      output_paths=(), integrity=False)


def test_FR_1_0_02_mc04_fix_order_trims_to_120_lines_and_lists_allowed_paths(repo, tmp_path):
    order, _ = load(repo)
    results = mod("records").CheckResults(results=tuple(failed_result(tmp_path, n, 500) for n in ("a", "b", "c")))
    allowed = (STEPS[1][0], STEPS[1][1], STEPS[0][0])
    text = mod("fixorder").build_fix_order(order, results, 1, allowed, "2", None)
    assert sum("LOGLINE" in line for line in text.splitlines()) <= 120
    assert "LOGLINE-a-0" in text and "LOGLINE-a-499" in text
    listed = text.split("## Files you may change", 1)[1].split("\n## ", 1)[0]
    assert set(re.findall(r"[\w./-]+\.py", listed)) == set(allowed)
    assert STEPS[2][0] not in text and STEPS[2][1] not in text


def test_FR_1_0_02_mc04_trim_log_keeps_first_20_and_last_40():
    trimmed = mod("fixorder").trim_log("".join(f"row {i}\n" for i in range(500))).splitlines()
    assert trimmed[:20] == [f"row {i}" for i in range(20)]
    assert trimmed[-40:] == [f"row {i}" for i in range(460, 500)]
    assert len(trimmed) == 61 and "440 lines" in trimmed[20]


@pytest.mark.parametrize("reason, phrase", [("MAX_TOKENS", "cut off"), ("SAFETY", "blocked or empty")])
def test_FR_1_0_02_mc04_stop_reason_fix_order(repo, reason, phrase):
    order, _ = load(repo)
    text = mod("fixorder").build_fix_order(order, mod("records").CheckResults(results=()), 1, STEPS[0], "1", reason)
    assert phrase in text and "LOGLINE" not in text


# ---------------------------------------------------------------- must-catch 5

ALLOWED_LINE = "LIMIT = 3  # TODO tidy the limit  # audit-allow: scratch reason for the acceptance test"


@pytest.mark.parametrize("line, passes", [(ALLOWED_LINE, True), (ALLOWED_LINE.split("  # audit-allow")[0], False)],
                         ids=["with-audit-allow", "without-audit-allow"])
def test_FR_1_0_02_mc05_compromise_check_honours_audit_allow(repo, tmp_path, line, passes):
    base = head(repo)
    write(repo, STEPS[0][0], module_text("alpha", extra=line))
    write(repo, STEPS[0][1], scratch_test_source("alpha"))
    results = quick(repo, tmp_path, STEPS[0], base)
    by_name = {r.name: r for r in results.results}
    assert by_name["patterns"].passed is passes
    assert results.passed is passes
    if passes:
        assert names(results) == ["scope", "headers", "patterns", "read-only-tests", "compile", "tests"]
    else:
        assert names(results)[-1] == "patterns"  # stops at the first failure


# ---------------------------------------------------------------- must-catch 6

def test_FR_1_0_02_mc06_read_only_test_changed_in_quick_checks_is_integrity_failure(repo, tmp_path):
    base = head(repo)
    write(repo, STEPS[0][0], module_text("alpha"))
    body = f"    open({READ_ONLY!r}, 'a').write(chr(10) + 'CHANGED = 1' + chr(10))\n"
    write(repo, STEPS[0][1], scratch_test_source("alpha", body))
    results = quick(repo, tmp_path, STEPS[0], base)
    last = results.results[-1]
    assert last.integrity is True and last.passed is False and results.passed is False
    assert sum(r.integrity for r in results.results) == 1


def test_FR_1_0_02_mc06_integrity_failure_in_verify_stops_later_commands(repo, tmp_path):
    write(repo, ORDER_REL, order_text(verify=(VERIFY_ONE, VERIFY_TWO)))
    git(repo, "commit", "-qam", "order with two verify commands")
    base = head(repo)
    for step in STEPS:
        name = Path(step[0]).stem
        write(repo, step[0], module_text(name))
        write(repo, step[1], scratch_test_source(name))
    order, _ = load(repo)
    results = mod("checks").full_checks(order, repo, tmp_path / "logs", base, sys.executable, 120)
    assert results.results[-1].integrity is True and results.passed is False
    assert not (repo / "verify_two_ran.txt").exists()


def test_FR_1_0_02_full_checks_pass_on_clean_outputs(repo, tmp_path):
    write(repo, ORDER_REL, order_text(verify=(VERIFY_TWO,)))
    git(repo, "commit", "-qam", "order with one verify command")
    base = head(repo)
    for step in STEPS:
        name = Path(step[0]).stem
        write(repo, step[0], module_text(name))
        write(repo, step[1], scratch_test_source(name))
    order, _ = load(repo)
    results = mod("checks").full_checks(order, repo, tmp_path / "logs", base, sys.executable, 120)
    assert results.passed is True, [(r.name, r.summary) for r in results.results]
    assert (repo / "verify_two_ran.txt").read_text(encoding="utf-8") == "ran"


# ---------------------------------------------------------------- must-catch 7

def sample_log():
    steplog, records = mod("steplog"), mod("records")
    log = steplog.parse("")
    log = log.record_run_start(T0, "a" * 64, "claude/wp-9-9-scratch", "default")
    log = log.record_accepted(records.StepRecord(
        label="1", files=((STEPS[0][0], "b" * 64), (STEPS[0][1], "c" * 64)), attempts=2, model="gemini-3.8-flash",
        provider="gemini", model_version="scratch-001", prompt_tokens=1234, output_tokens=567, seconds_waited=12.5))
    log = log.record_switch(T0 + timedelta(minutes=5), "2", "gemini-3.8-flash", "codestral-2508", "daily quota")
    log = log.record_stop(T0 + timedelta(minutes=9), "PAUSED-DAILY", T0 + timedelta(hours=19))
    return log


def test_FR_1_0_02_mc07_step_log_round_trips_byte_for_byte():
    steplog = mod("steplog")
    text = steplog.render(sample_log())
    assert steplog.render(steplog.parse(text)) == text
    reparsed = steplog.parse(text)
    assert reparsed.wp_branch == "claude/wp-9-9-scratch"
    assert len(reparsed.runs) == 1 and len(reparsed.accepted) == 1
    assert len(reparsed.switches) == 1 and len(reparsed.stops) == 1


def test_FR_1_0_02_mc07_malformed_step_log_raises():
    steplog = mod("steplog")
    text = steplog.render(sample_log()) + "this line belongs to no table\n"
    with pytest.raises(steplog.StepLogError):
        steplog.parse(text)


def test_FR_1_0_02_mc07_next_part_resumes_and_reduces_a_partial_step(repo):
    steplog, records = mod("steplog"), mod("records")
    _, plan = load(repo)
    log = sample_log()
    first = log.next_part(plan)
    assert (first.label, tuple(first.paths)) == ("2", STEPS[1])

    def accept(log, label, paths):
        return log.record_accepted(records.StepRecord(
            label=label, files=tuple((p, "d" * 64) for p in paths), attempts=1, model="codestral-2508",
            provider="mistral", model_version="2508", prompt_tokens=10, output_tokens=5, seconds_waited=0.0))

    log = steplog.parse(steplog.render(accept(log, "2.1", STEPS[1][:1])))
    second = log.next_part(plan)
    assert (second.label, tuple(second.paths)) == ("2.2", STEPS[1][1:])
    log = accept(accept(log, "2.2", STEPS[1][1:]), "3", STEPS[2])
    assert log.next_part(plan) is None


# ---------------------------------------------------------------- must-catch 8

def test_FR_1_0_02_mc08_every_result_maps_to_its_exit_code():
    result = mod("records").Result
    assert {member.name: member.exit_code for member in result} == RESULT_CODES
    assert result.PAUSED_DAILY.display_name == "PAUSED-DAILY"
    assert result.PAUSED_BUSY.display_name == "PAUSED-BUSY"
    assert result.TOO_LARGE.display_name == "TOO-LARGE" and result.ACCEPTED.display_name == "ACCEPTED"
