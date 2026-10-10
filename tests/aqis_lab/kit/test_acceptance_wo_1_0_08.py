"""Acceptance tests for WO-1.0-08 (FR-1.0-08): loop guard, bash guard and settings v4, staged in kit-staging/.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8. Each hook runs as a subprocess with the JSON
the hooks reference defines (`docs/outsourcing/refs/claude-code-hooks.md`): PreToolUse for Bash, PostToolUse for a
command that exits 0, and PostToolUseFailure (`error` starting `Exit code N`) for one that does not (DEC-1.0-03,
WO-1.0-08 B9). State lives in the scratch repository's `.git/`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "kit-staging" / ".claude" / "hooks"
PYTEST_CMD = ".venv/bin/python -m pytest tests/aqis_lab/demo -q --tb=short"
PYTEST_ERROR = ("Exit code 1\n.F\nFAILED tests/aqis_lab/demo/test_x.py::test_adds - assert 3 == 4\n"
                "1 failed, 1 passed in 0.05s")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/progress/blockers.d").mkdir(parents=True)
    (root / "docs/progress/decisions.d").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/process/PROTECTED_PATHS.txt", root / "notes.txt")  # any file; the list is copied next
    (root / "docs/process").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/process/PROTECTED_PATHS.txt", root / "docs/process/PROTECTED_PATHS.txt")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    return root


def run_hook(repo: Path, script: str, mode: str | None, event: dict) -> subprocess.CompletedProcess:
    assert (HOOKS / script).is_file(), f"{script} is not staged"
    args = [sys.executable, str(HOOKS / script)] + ([mode] if mode else [])
    event = {"session_id": "s", "transcript_path": str(repo / "t.jsonl"), "cwd": str(repo),
             "permission_mode": "default", **event}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    return subprocess.run(args, input=json.dumps(event), capture_output=True, text=True, env=env, timeout=60)


def failure(repo: Path, command: str, error: str) -> subprocess.CompletedProcess:
    return run_hook(repo, "loop_guard.py", "post", {
        "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_use_id": "toolu_1",
        "tool_input": {"command": command, "description": "scratch"}, "error": error, "is_interrupt": False})


def success(repo: Path, command: str, stdout: str = "ok") -> subprocess.CompletedProcess:
    return run_hook(repo, "loop_guard.py", "post", {
        "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": "toolu_2",
        "tool_input": {"command": command}, "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False}})


def pre(repo: Path, script: str, command: str, mode: str | None = None) -> subprocess.CompletedProcess:
    return run_hook(repo, script, mode, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_use_id": "toolu_3",
                                          "tool_input": {"command": command}})


def context_message(proc: subprocess.CompletedProcess) -> str:
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return ""
    data = json.loads(proc.stdout)
    return data.get("hookSpecificOutput", {}).get("additionalContext", "")


def blocked(proc: subprocess.CompletedProcess) -> str | None:
    """The block message, by exit code 2 with stderr or by permissionDecision deny; None when the call may run."""
    if proc.returncode == 2:
        return proc.stderr
    if proc.returncode == 0 and proc.stdout.strip():
        out = json.loads(proc.stdout).get("hookSpecificOutput", {})
        if out.get("permissionDecision") == "deny":
            return out.get("permissionDecisionReason", "")
    assert proc.returncode == 0, f"unexpected exit {proc.returncode}: {proc.stderr}"
    return None


# ---------------------------------------------------------------- must-catch 1: the 3rd failure warns

def test_FR_1_0_08_mc01_third_identical_failure_warns_second_does_not(repo):
    assert context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR)) == ""
    assert context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR)) == ""
    message = context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR))
    assert re.match(r"LOOP GUARD LOOP-[0-9a-f]{8}: this failure has repeated 3 times\. Stop retrying\.", message), message
    assert "climb the escalation ladder" in message


def test_FR_1_0_08_mc01_signature_ignores_scratch_paths_and_numbers(repo):
    for n in (1, 2):
        failure(repo, f"cat /tmp/run-{n}/out.log", f"Exit code 1\ncat: /tmp/run-{n}/out.log: No such file or directory")
    assert "LOOP GUARD" in context_message(
        failure(repo, "cat /tmp/run-3/out.log", "Exit code 1\ncat: /tmp/run-3/out.log: No such file or directory"))


# ---------------------------------------------------------------- must-catch 2: the 5th blocks until cited

def loop_id(repo: Path, command: str = PYTEST_CMD) -> str:
    message = ""
    for _ in range(5):
        message = context_message(failure(repo, command, PYTEST_ERROR)) or message
    return re.search(r"LOOP-[0-9a-f]{8}", message).group(0)


def test_FR_1_0_08_mc02_fifth_failure_blocks_until_a_fragment_cites_the_id(repo):
    lid = loop_id(repo)
    message = blocked(pre(repo, "loop_guard.py", PYTEST_CMD, "pre"))
    assert message and f"Blocked by the loop guard: {lid} failed 5 times." in message
    assert blocked(pre(repo, "loop_guard.py", "ls -la", "pre")) is None
    (repo / "docs/progress/blockers.d/BLK-9.9-01.md").write_text(f"# BLK-9.9-01\nLoop: {lid}\n", encoding="utf-8")
    assert blocked(pre(repo, "loop_guard.py", PYTEST_CMD, "pre")) is None


def test_FR_1_0_08_mc02_decision_record_also_unblocks(repo):
    lid = loop_id(repo)
    (repo / "docs/progress/decisions.d/DEC-9.9-01.md").write_text(f"# DEC-9.9-01\nCites {lid}.\n", encoding="utf-8")
    assert blocked(pre(repo, "loop_guard.py", PYTEST_CMD, "pre")) is None


# ---------------------------------------------------------------- must-catch 3: success resets

def test_FR_1_0_08_mc03_success_resets_the_count(repo):
    failure(repo, PYTEST_CMD, PYTEST_ERROR)
    failure(repo, PYTEST_CMD, PYTEST_ERROR)
    assert context_message(success(repo, PYTEST_CMD, "2 passed in 0.04s")) == ""
    assert context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR)) == ""
    assert context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR)) == ""
    assert "LOOP GUARD" in context_message(failure(repo, PYTEST_CMD, PYTEST_ERROR))


# ---------------------------------------------------------------- must-catch 4: environment at the 2nd

@pytest.mark.parametrize("error", [
    "Exit code 56\ncurl: (56) CONNECT tunnel failed, response 403\nx-deny-reason: host_not_allowed",
    "Exit code 1\nOSError: [Errno 28] No space left on device",
    "Exit code 128\nremote: Repository not found.\nfatal: repository 'https://github.com/x/y/' not found",
], ids=["host-not-allowed", "no-space", "repository-not-found"])
def test_FR_1_0_08_mc04_environment_failure_escalates_at_the_second(repo, error):
    command = "curl -sS https://example.invalid/data"
    assert context_message(failure(repo, command, error)) == ""
    message = context_message(failure(repo, command, error))
    assert re.match(r"LOOP GUARD LOOP-[0-9a-f]{8}: environment failure \(", message), message
    assert "ACCESS or COMPUTE" in message


# ---------------------------------------------------------------- must-catch 5 and 6: bash guard

@pytest.mark.parametrize("command", [
    "gh pr merge 12 --merge",
    "gh pr merge --squash 12",
    "git push origin HEAD:main",
    "git push origin main",
    "git push -u origin +main",
    "git push origin :main",
    "git push origin refs/heads/main",
    "git push origin feature:master",
    "git update-ref refs/heads/main 0123456789abcdef0123456789abcdef01234567",
    "gh api -X PUT repos/o/r/pulls/12/merge -f merge_method=merge",
    "gh api --method PUT repos/o/r/pulls/12/merge",
    "echo ok && gh pr merge 3",
    "git status; git push origin HEAD:main",
])
def test_FR_1_0_08_mc05_raw_merges_and_pushes_to_main_are_blocked(repo, command):
    message = blocked(pre(repo, "bash_guard.py", command))
    assert message and "merge gate" in message


@pytest.mark.parametrize("command", [
    ".venv/bin/python -m tools.autonomy.merge_gate --wp WP-1.3",
    "python3 -m tools.autonomy.merge_gate --wp WP-1.3 --dry-run",
    "git push -u origin claude/wp-1-3-x",
    "git push origin wo/WO-1.3-02",
    "git merge --no-ff wo/WO-1.3-02",
    "gh api repos/o/r/pulls/12",
    "ls -la && git status",
    "echo maintenance > notes.txt",
])
def test_FR_1_0_08_mc05_ordinary_commands_and_the_merge_gate_pass(repo, command):
    assert blocked(pre(repo, "bash_guard.py", command)) is None


@pytest.mark.parametrize("command", [
    "echo x > CLAUDE.md",
    "echo x >> .claude/settings.json",
    "printf 'x' | tee .claude/hooks/new_hook.py",
    "sed -i 's/a/b/' docs/process/WORKFLOW.md",
    "cp notes.txt .claude/rules/99-new.md",
    "mv notes.txt docs/specs/phase-1/x.md",
    "rm docs/approvals/WP-1.0.md",
    "cat notes.txt > config/aqis_lab/model_pool.json",
])
def test_FR_1_0_08_mc06_shell_writes_into_never_paths_are_blocked(repo, command):
    message = blocked(pre(repo, "bash_guard.py", command))
    target = next(word for word in command.split() if word.startswith(("CLAUDE.md", ".claude/", "docs/", "config/")))
    assert message and target in message


# ---------------------------------------------------------------- must-catch 7: fail open

@pytest.mark.parametrize("mode", ["post", "pre"])
def test_FR_1_0_08_mc07_loop_guard_exits_0_on_a_corrupt_state_file(repo, mode):
    (repo / ".git" / "aqis-loop.json").write_text("{not json", encoding="utf-8")
    proc = failure(repo, PYTEST_CMD, PYTEST_ERROR) if mode == "post" else pre(repo, "loop_guard.py", PYTEST_CMD, "pre")
    assert proc.returncode == 0 and blocked(proc) is None


def test_FR_1_0_08_mc07_loop_guard_exits_0_on_unparseable_input(repo):
    assert (HOOKS / "loop_guard.py").is_file()
    proc = subprocess.run([sys.executable, str(HOOKS / "loop_guard.py"), "post"], input="this is not json",
                          capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(repo)), timeout=60)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


# ---------------------------------------------------------------- must-catch 8: settings v4

def hook_commands(settings: dict, event: str, matcher: str | None) -> list[str]:
    found = []
    for entry in settings.get("hooks", {}).get(event, []):
        if matcher is None or entry.get("matcher") == matcher:
            found.extend(h["command"] for h in entry.get("hooks", []))
    return found


def test_FR_1_0_08_mc08_settings_v4_keep_every_entry_and_add_the_new_ones():
    current = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    staged = json.loads((ROOT / "kit-staging/.claude/settings.json").read_text(encoding="utf-8"))
    assert staged["advisorModel"] == current["advisorModel"]
    assert set(current["permissions"]["deny"]) <= set(staged["permissions"]["deny"])
    assert "Bash(gh pr merge *)" in staged["permissions"]["deny"]
    for event, entries in current["hooks"].items():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["command"] in hook_commands(staged, event, entry.get("matcher")), (event, hook)
    pre_bash = hook_commands(staged, "PreToolUse", "Bash")
    assert [c.rsplit("/", 1)[-1] for c in pre_bash] == ["bash_guard.py", "loop_guard.py pre"]
    for event in ("PostToolUse", "PostToolUseFailure"):
        assert [c.rsplit("/", 1)[-1] for c in hook_commands(staged, event, "Bash")] == ["loop_guard.py post"]
    for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        assert all(c.startswith('python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/') for c in hook_commands(staged, event, "Bash"))


# ---------------------------------------------------------------- must-catch 9: relay pauses

RELAY = ".venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/WO-1.3-02.md"


@pytest.mark.parametrize("code, text", [(11, "PAUSED-DAILY\nevery eligible model's daily quota is used up"),
                                        (12, "PAUSED-BUSY\nservice busy after long backoff")])
def test_FR_1_0_08_mc09_relay_pauses_are_never_counted(repo, code, text):
    for _ in range(6):
        assert context_message(failure(repo, RELAY, f"Exit code {code}\n{text}")) == ""
    assert blocked(pre(repo, "loop_guard.py", RELAY, "pre")) is None


def test_FR_1_0_08_mc09_relay_attempts_exhausted_is_counted(repo):
    for _ in range(2):
        assert context_message(failure(repo, RELAY, "Exit code 8\nEXHAUSTED\nquota of attempts used")) == ""
    assert "LOOP GUARD" in context_message(failure(repo, RELAY, "Exit code 8\nEXHAUSTED\nquota of attempts used"))


def test_FR_1_0_08_mc09_chained_relay_pause_is_not_counted(repo):
    command = f"cd /home/user/repo && {RELAY}"
    for _ in range(4):
        assert context_message(failure(repo, command, "Exit code 11\nPAUSED-DAILY\nrate limit: daily quota")) == ""
