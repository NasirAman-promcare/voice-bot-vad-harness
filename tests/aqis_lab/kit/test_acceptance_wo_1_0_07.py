"""Acceptance tests for WO-1.0-07 (FR-1.0-07): staged guard, protected-path helpers, stop gate v4, session context v2.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus positive controls and the edge cases.

Every hook runs as a subprocess from `kit-staging/.claude/hooks/` with real JSON on stdin, as Claude Code runs it,
inside a scratch repository that has an `origin` remote. The scratch repository carries copies of the real
`tools/index` and `tools/progress` packages, because the stop gate calls them with `python -m` from the project root.
Scratch tests append their name to the file named by `AQIS_SCRATCH_RAN`, which shows exactly which tests the stop
gate ran.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "kit-staging" / ".claude" / "hooks"
WP1 = "claude/wp-9-1-scratch"
WP2 = "claude/wp-9-2-other"

SPEC_91 = ("# WP-9.1 scratch spec\n\n## Requirements\n- **FR-9.1-01** Scratch.\n\n"
           "## Allowed guarded edits\n- `bots/allowed.py`\n- bots/pattern/**\n- `CLAUDE.md`\n\n## Owner needs\nNone.\n")
SPEC_92 = "# WP-9.2 scratch spec\n\n## Allowed guarded edits\n- None\n\n## Owner needs\nNone.\n"
RECORD = ("import os\n\n\n"
          "def record(name):\n"
          "    target = os.environ.get('AQIS_SCRATCH_RAN')\n"
          "    if target:\n"
          "        with open(target, 'a', encoding='utf-8') as handle:\n"
          "            handle.write(name + '\\n')\n")
TEST_A = ('"""Scratch tests for module a."""\n' + RECORD +
          "\n\nfrom aqis_lab.a import a_fn\n\n\n"
          "def test_a():\n    record('test_a')\n    assert a_fn(1) == 2\n")
TEST_B = ('"""Scratch tests for module b."""\n' + RECORD +
          "\n\nfrom aqis_lab.b import b_fn\n\n\n"
          "def test_b():\n    record('test_b')\n    assert b_fn(1) == 3\n    assert b_fn(2) == 4\n\n\n"
          "def test_b_other():\n    record('test_b_other')\n    assert b_fn(0) == 2\n")


def module(name: str, body: str) -> str:
    return (f'"""Scratch module {name}.\n\nCAPABILITIES:\n  none.\nINPUTS AND OUTPUTS: numbers.\nCONTRACTS: none.\n'
            f'INVARIANTS:\n  - Scratch.\nNOT IN SCOPE:\n  - Anything real.\nCHANGE LOG:\n  2026-10-10 WP-9.1 created.\n"""\n'
            f"{body}")


BASE_FILES = {
    "docs/specs/phase-9/WP-9.1-scratch.md": SPEC_91,
    "docs/specs/phase-9/WP-9.2-other.md": SPEC_92,
    "bots/allowed.py": "VALUE = 1\n",
    "bots/other.py": "VALUE = 1\n",
    "aqis_lab/__init__.py": '"""Scratch lab package."""\n',
    "aqis_lab/a.py": module("a", "\n\ndef a_fn(value):\n    return value + 1\n"),
    "aqis_lab/b.py": module("b", "\n\ndef b_fn(value):\n    return value + 2\n"),
    "tests/aqis_lab/conftest.py": '"""Scratch conftest."""\n',
    "tests/aqis_lab/test_a.py": TEST_A,
    "tests/aqis_lab/test_b.py": TEST_B,
    "docs/progress/status.d/WP-9.1.md": ("WP: WP-9.1\nTitle: Scratch\nStatus: IN-BUILD\nTier: T2\nSize: S\n"
                                         f"Branch: {WP1}\nPR: none\nThread model: Sonnet high\nUpdated: 2026-10-10\n"),
}


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "AQIS Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "AQIS Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, check=True,
                          capture_output=True, text=True, env=env, timeout=120).stdout


def write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")


def commit(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)


def copy_tools(repo: Path) -> None:
    shutil.copy2(ROOT / "tools/__init__.py", repo / "tools/__init__.py")
    for package in ("index", "progress"):
        shutil.copytree(ROOT / "tools" / package, repo / "tools" / package,
                        ignore=shutil.ignore_patterns("__pycache__"))


def make_repo(tmp_path: Path, branch: str | None = WP1, extra: dict | None = None, remote: bool = True) -> Path:
    repo = tmp_path / "repo"
    files = dict(BASE_FILES, **(extra or {}))
    for rel, text in files.items():
        write(repo, rel, text)
    write(repo, "docs/process/PROTECTED_PATHS.txt", (ROOT / "docs/process/PROTECTED_PATHS.txt").read_text("utf-8"))
    (repo / "tools").mkdir()
    copy_tools(repo)
    git(repo, "init", "-q")
    commit(repo, "main")
    if remote:
        bare = tmp_path / "origin.git"
        git(tmp_path, "init", "-q", "--bare", str(bare))
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "push", "-q", "origin", "main")
        git(repo, "fetch", "-q", "origin")
    if branch:
        git(repo, "checkout", "-qb", branch)
    return repo


def hook_env(repo: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"CLAUDE_PROJECT_DIR": str(repo), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "AQIS_SCRATCH_RAN": str(repo.parent / "ran.txt"), "GIT_AUTHOR_NAME": "AQIS Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "AQIS Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return env


def run_hook(repo: Path, script: str, payload: str) -> subprocess.CompletedProcess:
    assert (HOOKS / script).is_file(), f"{script} is not staged"
    return subprocess.run([sys.executable, str(HOOKS / script)], input=payload, cwd=repo, capture_output=True,
                          text=True, env=hook_env(repo), timeout=900)


def guard(repo: Path, rel: str, tool: str = "Write") -> subprocess.CompletedProcess:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    event = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(repo),
             "tool_input": {key: str(repo / rel), "content": "VALUE = 2\n"}}
    return run_hook(repo, "guard_protected.py", json.dumps(event))


def stop(repo: Path, active: bool = False) -> tuple[subprocess.CompletedProcess, str]:
    (repo.parent / "ran.txt").unlink(missing_ok=True)
    event = {"session_id": "s", "hook_event_name": "Stop", "stop_hook_active": active, "cwd": str(repo)}
    proc = run_hook(repo, "stop_gate.py", json.dumps(event))
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return proc, ""
    answer = json.loads(proc.stdout)
    return proc, answer.get("reason") or answer.get("systemMessage") or ""


def blocks(proc: subprocess.CompletedProcess) -> bool:
    return bool(proc.stdout.strip()) and json.loads(proc.stdout).get("decision") == "block"


def ran(repo: Path) -> list[str]:
    path = repo.parent / "ran.txt"
    return sorted(path.read_text(encoding="utf-8").split()) if path.exists() else []


def protected():
    spec = importlib.util.spec_from_file_location("staged_protected", HOOKS / "_protected.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def blocker(bid: str, wp: str, capability: str | None = "ACCESS", status: str = "OPEN") -> str:
    lines = [f"# {bid} — scratch blocker", f"Status: {status}", f"WP: {wp}"]
    if capability is not None:
        lines.append(f"Owner capability: {capability}")
    lines += ["Raised: 2026-10-10", "Session: https://claude.ai/code/session_scratch", f"Unblocks: {wp}",
              "Time needed: 5 minutes", "Loop: none", "", "What I need: a scratch thing.", "", "Why: a test.", "",
              "What I tried:", "- nothing", "", "Options:", "1. do it (recommended)", "", "Exact steps:",
              "1. Step 1.", "2. Step 2.", "", "Meanwhile: other work.", "", "Owner answer:", ""]
    return "\n".join(lines)


# ============================================================================== guard and spec allowances (B1-B3)
def test_FR_1_0_07_mc1_spec_allowance_on_origin_main_allows_a_guarded_edit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert guard(repo, "bots/allowed.py").returncode == 0
    assert guard(repo, "bots/pattern/deep/new.py").returncode == 0
    assert guard(repo, "bots/allowed.py", tool="Edit").returncode == 0
    refused = guard(repo, "bots/other.py")
    assert refused.returncode == 2 and "bots/other.py" in refused.stderr


def test_FR_1_0_07_mc2_allowance_does_not_apply_on_another_wps_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, branch=WP2)
    assert guard(repo, "bots/allowed.py").returncode == 2
    assert protected().spec_allowances(repo, "origin/main", "WP-9.2") == []


def test_FR_1_0_07_mc3_allowance_added_only_on_the_work_branch_has_no_effect(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "docs/specs/phase-9/WP-9.1-scratch.md", SPEC_91.replace("- bots/pattern/**\n",
                                                                         "- bots/pattern/**\n- bots/other.py\n"))
    commit(repo, "allowance on the branch only")
    assert guard(repo, "bots/other.py").returncode == 2
    assert "bots/other.py" not in protected().spec_allowances(repo, "origin/main", "WP-9.1")


def test_FR_1_0_07_never_paths_stay_blocked_even_when_a_spec_lists_them(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert guard(repo, "CLAUDE.md").returncode == 2
    assert guard(repo, ".claude/settings.json").returncode == 2


def test_FR_1_0_07_spec_allowances_and_current_wp_values(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    mod = protected()
    assert mod.spec_allowances(repo, "origin/main", "WP-9.1") == ["bots/allowed.py", "bots/pattern/**", "CLAUDE.md"]
    assert mod.current_wp(repo) == "WP-9.1"
    git(repo, "checkout", "-qb", "feature/scratch")
    assert mod.current_wp(repo) is None
    write(repo, "docs/progress/status.d/WP-9.2.md", BASE_FILES["docs/progress/status.d/WP-9.1.md"]
          .replace("WP-9.1", "WP-9.2").replace(WP1, "feature/scratch"))
    assert mod.current_wp(repo) == "WP-9.2", "B1: the status fragment whose Branch: is the current branch"


def test_FR_1_0_07_without_origin_main_spec_allowances_are_empty(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, remote=False)
    assert protected().spec_allowances(repo, "origin/main", "WP-9.1") == []
    assert guard(repo, "bots/allowed.py").returncode == 2, "E1: fail closed; the local main never counts"


def test_FR_1_0_07_two_matching_spec_files_give_no_allowance_and_are_named(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, extra={"docs/specs/phase-9b/WP-9.1-copy.md": SPEC_91})
    proc = guard(repo, "bots/allowed.py")
    assert proc.returncode == 2
    assert "docs/specs/phase-9/WP-9.1-scratch.md" in proc.stderr and "docs/specs/phase-9b/WP-9.1-copy.md" in proc.stderr


def test_FR_1_0_07_approval_files_still_unlock_and_bad_input_still_blocks(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, branch=WP2, extra={
        "docs/approvals/APP-901.md": "# APP-901\nSTATUS: APPROVED\nALLOW-EDIT: bots/other.py\n"})
    assert guard(repo, "bots/other.py").returncode == 0
    assert run_hook(repo, "guard_protected.py", "{not json").returncode == 2


# ============================================================================== stop gate v4
def test_FR_1_0_07_stop_gate_is_version_4_and_honours_spec_allowances(tmp_path: Path) -> None:
    assert 'HOOK_VERSION = "4"' in (HOOKS / "stop_gate.py").read_text(encoding="utf-8")
    repo = make_repo(tmp_path)
    write(repo, "bots/allowed.py", "VALUE = 2\n")
    commit(repo, "allowed guarded edit")
    proc, text = stop(repo)
    assert not blocks(proc), text
    other = make_repo(tmp_path / "second", branch=WP2)
    write(other, "bots/allowed.py", "VALUE = 2\n")
    commit(other, "guarded edit on another WP")
    proc, text = stop(other)
    assert blocks(proc) and "bots/allowed.py" in text


def change_test_b(repo: Path, new_text: str, row: bool, rel: str = "tests/aqis_lab/test_b.py") -> None:
    write(repo, rel, new_text)
    if row:
        write(repo, "docs/progress/WP-9.1/TEST_CHANGES.md",
              "# TEST_CHANGES — WP-9.1\n\n"
              "| File | Test functions | Kind (add-cases, helper-refactor, rename) | Why | Assertions before, after |\n"
              "| --- | --- | --- | --- | --- |\n"
              f"| `{rel}` | `test_b` | add-cases | scratch | 2 → 3 |\n")
    commit(repo, "test change")


def test_FR_1_0_07_added_case_with_a_record_passes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    change_test_b(repo, TEST_B.replace("    assert b_fn(2) == 4\n", "    assert b_fn(2) == 4\n    assert b_fn(3) == 5\n"),
                  row=True)
    proc, text = stop(repo)
    assert not blocks(proc), text


def test_FR_1_0_07_modified_test_without_a_record_is_blocked_as_in_version_3(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    change_test_b(repo, TEST_B.replace("    assert b_fn(2) == 4\n", "    assert b_fn(2) == 4\n    assert b_fn(3) == 5\n"),
                  row=False)
    proc, text = stop(repo)
    assert blocks(proc) and "tests/aqis_lab/test_b.py" in text


@pytest.mark.parametrize("case", ["assertion-fell", "skip-decorator", "pytest-skip-call", "pytestmark-skip",
                                  "deleted-function", "renamed-file-assertion-fell"])
def test_FR_1_0_07_mc4_mc5_weakened_test_is_blocked_even_with_a_record(tmp_path: Path, case: str) -> None:
    repo = make_repo(tmp_path)
    rel = "tests/aqis_lab/test_b.py"
    if case == "assertion-fell":
        text = TEST_B.replace("    assert b_fn(2) == 4\n", "")
    elif case == "skip-decorator":
        text = TEST_B.replace("def test_b_other():", "@pytest.mark.skip(reason='later')\ndef test_b_other():") \
            .replace("import os\n", "import os\n\nimport pytest\n", 1)
    elif case == "pytest-skip-call":
        text = TEST_B.replace("    record('test_b_other')\n", "    record('test_b_other')\n    pytest.skip('later')\n") \
            .replace("import os\n", "import os\n\nimport pytest\n", 1)
    elif case == "pytestmark-skip":
        text = TEST_B.replace("import os\n", "import os\n\nimport pytest\n\npytestmark = pytest.mark.xfail\n", 1)
    elif case == "deleted-function":
        text = TEST_B.split("\n\n\ndef test_b_other")[0] + "\n"
    else:
        git(repo, "mv", rel, "tests/aqis_lab/test_b_renamed.py")
        rel = "tests/aqis_lab/test_b_renamed.py"
        text = TEST_B.replace("    assert b_fn(2) == 4\n", "")
    change_test_b(repo, text, row=True, rel=rel)
    proc, text_seen = stop(repo)
    assert blocks(proc), (case, text_seen)
    assert rel in text_seen, (case, text_seen)


def test_FR_1_0_07_mc6_impact_selected_tests_run(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "aqis_lab/a.py", BASE_FILES["aqis_lab/a.py"] + "\n\nLIMIT = 2\n")
    commit(repo, "change a")
    proc, text = stop(repo)
    assert not blocks(proc), text
    assert ran(repo) == ["test_a"]


@pytest.mark.parametrize("case", ["impact-prints-all", "impact-fails", "ready-for-audit"])
def test_FR_1_0_07_mc6_full_suite_runs_when_impact_cannot_narrow(tmp_path: Path, case: str) -> None:
    repo = make_repo(tmp_path)
    write(repo, "aqis_lab/a.py", BASE_FILES["aqis_lab/a.py"] + "\n\nLIMIT = 2\n")
    if case == "impact-prints-all":
        write(repo, "tests/aqis_lab/conftest.py", '"""Scratch conftest, changed."""\n')
        write(repo, "docs/progress/WP-9.1/TEST_CHANGES.md",
              "| File | Test functions | Kind (add-cases, helper-refactor, rename) | Why | Assertions before, after |\n"
              "| --- | --- | --- | --- | --- |\n"
              "| `tests/aqis_lab/conftest.py` | none | helper-refactor | scratch | 0 → 0 |\n")
    elif case == "impact-fails":
        (repo / "tools/index/impact.py").unlink()
    else:
        write(repo, "docs/progress/status.d/WP-9.1.md",
              BASE_FILES["docs/progress/status.d/WP-9.1.md"].replace("IN-BUILD", "READY-FOR-AUDIT"))
    commit(repo, case)
    proc, text = stop(repo)
    assert not blocks(proc), text
    assert ran(repo) == ["test_a", "test_b", "test_b_other"], case


def test_FR_1_0_07_mc7_what_claude_sees_never_exceeds_40_lines(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    for n in range(60):
        write(repo, f"docs/process/extra_{n:02d}.md", f"note {n}\n")
    commit(repo, "sixty never-path changes")
    proc, text = stop(repo)
    assert blocks(proc)
    assert len(text.splitlines()) <= 40, len(text.splitlines())
    log = (repo / ".git" / "aqis-stop-gate.log").read_text(encoding="utf-8")
    assert all(f"docs/process/extra_{n:02d}.md" in log for n in range(60)), "the full report goes to the log"
    _, text = stop(repo, active=True)
    assert len(text.splitlines()) <= 40


def test_FR_1_0_07_mc8_blocker_fragment_without_a_capability_class_blocks(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", blocker("BLK-9.1-01", "WP-9.1", capability=None))
    commit(repo, "bad blocker")
    proc, text = stop(repo)
    assert blocks(proc) and "BLK-9.1-01" in text
    good = make_repo(tmp_path / "second")
    write(good, "docs/progress/blockers.d/BLK-9.1-01.md", blocker("BLK-9.1-01", "WP-9.1", capability="ACCESS"))
    commit(good, "good blocker")
    proc, text = stop(good)
    assert not blocks(proc), text


def test_FR_1_0_07_mc9_never_path_blocked_and_known_problem_memory_works(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "docs/process/extra.md", "owner only\n")
    commit(repo, "never path")
    proc, text = stop(repo)
    assert blocks(proc) and "docs/process/extra.md" in text
    proc, text = stop(repo)
    assert not blocks(proc) and "docs/process/extra.md" in text, "known set, no blocker: warn, do not block"
    write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", blocker("BLK-9.1-01", "WP-9.1"))
    commit(repo, "open blocker fragment")
    proc, text = stop(repo)
    assert proc.stdout.strip() == "", "known set while an open blocker fragment exists: silent"


# ============================================================================== session context v2 (B10)
def session(repo: Path, payload: str | None = None) -> subprocess.CompletedProcess:
    event = payload if payload is not None else json.dumps(
        {"session_id": "s", "hook_event_name": "SessionStart", "source": "startup", "cwd": str(repo)})
    proc = run_hook(repo, "session_context.py", event)
    assert proc.returncode == 0, proc.stderr
    return proc


def test_FR_1_0_07_session_context_reports_wp_blockers_and_navigation(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", blocker("BLK-9.1-01", "WP-9.1"))
    write(repo, "docs/progress/blockers.d/BLK-9.1-02.md", blocker("BLK-9.1-02", "WP-9.1", status="RESOLVED"))
    write(repo, "docs/progress/blockers.d/BLK-9.2-01.md", blocker("BLK-9.2-01", "WP-9.2"))
    write(repo, "docs/progress/BLOCKERS.md", "# Blockers\n\n## BLK-001 — legacy\nSTATUS: OPEN\n\n"
                                             "## BLK-002 — legacy\nSTATUS: RESOLVED\n")
    write(repo, "docs/environment/colab_probe.txt", "Python 3.12\n")
    lines = session(repo).stdout.splitlines()
    assert 0 < len(lines) <= 15, lines
    text = "\n".join(lines)
    assert WP1 in text
    assert "- WP: WP-9.1 (IN-BUILD)" in lines, lines
    assert "- Open blockers: 1 for WP-9.1 (BLK-9.1-01), 3 in total" in lines, lines
    assert "Navigate: docs/index/MAP.md first." in text
    assert any("colab_probe.txt" in line and "present" in line for line in lines)
    assert any("oracle_probe.txt" in line and "MISSING" in line for line in lines)
    assert not any("Owner queue" in line for line in lines), "no OWNER_QUEUE.md, no owner-queue line"


def test_FR_1_0_07_session_context_counts_the_generated_owner_queue(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", blocker("BLK-9.1-01", "WP-9.1"))
    write(repo, "docs/progress/blockers.d/BLK-9.2-01.md", blocker("BLK-9.2-01", "WP-9.2", capability="COMPUTE"))
    built = subprocess.run([sys.executable, "-P", "-m", "tools.progress", "build", "--on-main"], cwd=repo,
                           capture_output=True, text=True, env=dict(hook_env(repo), PYTHONPATH=str(repo)), timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    assert (repo / "docs/progress/OWNER_QUEUE.md").is_file()
    lines = session(repo).stdout.splitlines()
    assert "- Owner queue: 2 items" in lines, lines


@pytest.mark.parametrize("case", ["bad-json", "unreadable-status"])
def test_FR_1_0_07_session_context_never_fails_the_session(tmp_path: Path, case: str) -> None:
    repo = make_repo(tmp_path)
    if case == "bad-json":
        proc = session(repo, "{not json")
        assert 0 < len(proc.stdout.splitlines()) <= 15
        return
    (repo / "docs/progress/status.d/WP-9.1.md").unlink()
    (repo / "docs/progress/status.d/WP-9.1.md").mkdir()
    proc = session(repo)
    assert len(proc.stdout.splitlines()) == 1, proc.stdout
