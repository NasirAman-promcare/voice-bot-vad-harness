"""Acceptance tests for WO-1.0-09 (FR-1.0-09): lab CI workflows, branch refs, main guard and kit parity.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus positive controls and the edge cases.

The workflows are read with PyYAML (pinned in `requirements/aqis_lab/phase0.txt`); YAML reads the key `on` as
`True`, so both spellings are accepted. The main guard runs end to end in a scratch repository whose history holds
one commit of each kind, with a stand-in `gh` on `PATH` that answers `gh api` from a JSON script and logs each call.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
NAMES = ("generate", "breaks", "scope", "main-guard", "mutation", "kit-parity")
HEAVY = "${{ vars.AQIS_HEAVY_RUNNER || 'ubuntu-latest' }}"
SHA_USES = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")
GENERATED = ("docs/index/", "docs/capabilities/REGISTRY.md", "docs/progress/STATUS.md", "docs/progress/BLOCKERS.md",
             "docs/progress/DEBT.md", "docs/progress/DECISIONS.md", "docs/progress/OWNER_QUEUE.md",
             "docs/outsourcing/LEDGER.md")
SLUG = "owner/scratch"
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")
WEB = ("GitHub", "noreply@github.com")


# ============================================================================== workflow structure
def workflow(name: str) -> dict:
    path = WORKFLOWS / f"aqis-lab-{name}.yml"
    assert path.is_file(), f"{path.name} missing"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), path.name
    return data


def triggers(data: dict) -> dict:
    on = data.get("on", data.get(True))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return {k: None for k in on}
    return on or {}


def steps_text(job: dict) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


def norm(expr: object) -> str:
    return re.sub(r"\s+", " ", str(expr or "")).strip()


def job_permissions(data: dict, job: dict) -> dict:
    perms = job.get("permissions", data.get("permissions"))
    assert isinstance(perms, dict), "permissions must be explicit (B1)"
    return perms


@pytest.mark.parametrize("name", NAMES)
def test_FR_1_0_09_mc6_every_third_party_action_is_pinned_to_a_commit_sha(name: str) -> None:
    text = (WORKFLOWS / f"aqis-lab-{name}.yml").read_text(encoding="utf-8")
    uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$", text, re.M)
    assert uses, f"{name}: no actions"
    for action, rest in uses:
        assert SHA_USES.match(action), f"{name}: {action} is not pinned to a full commit SHA"
        assert re.search(r"#\s*v\d", rest), f"{name}: {action} has no version comment"
    assert "|| true" not in text and "2>/dev/null" not in text, f"{name}: hides failures"


@pytest.mark.parametrize("name", NAMES)
def test_FR_1_0_09_every_job_installs_the_lab_environment_like_the_lab_ci(name: str) -> None:
    for job_id, job in workflow(name)["jobs"].items():
        uses = [str(step.get("uses", "")) for step in job.get("steps", [])]
        assert any(u.startswith("actions/checkout@") for u in uses), (name, job_id)
        checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))
        assert str((checkout.get("with") or {}).get("fetch-depth")) == "0", (name, job_id, "full history")
        setup_uv = [s for s in job["steps"] if str(s.get("uses", "")).startswith("astral-sh/setup-uv@")]
        assert setup_uv and str((setup_uv[0].get("with") or {}).get("version")) == "0.8.17", (name, job_id)
        assert "bash aqis_lab/deploy/dev_bootstrap.sh" in steps_text(job), (name, job_id)


@pytest.mark.parametrize("name", NAMES)
def test_FR_1_0_09_mc2_pull_request_jobs_have_read_only_permissions(name: str) -> None:
    data = workflow(name)
    top = data.get("permissions")
    assert isinstance(top, dict) and set(top.values()) <= {"read", "none"}, (name, "workflow-level read only")
    on_pr = "pull_request" in triggers(data)
    for job_id, job in data["jobs"].items():
        perms = job_permissions(data, job)
        writes = {k for k, v in perms.items() if v == "write"}
        if writes:
            condition = norm(job.get("if"))
            assert not on_pr or "github.event_name == 'push'" in condition, (name, job_id, writes, condition)


def test_FR_1_0_09_permissions_are_least_privilege() -> None:
    generate = workflow("generate")
    regen = [job for job in generate["jobs"].values() if "push" in norm(job.get("if"))]
    assert len(regen) == 1
    assert job_permissions(generate, regen[0]) == {"contents": "write"}
    guard = workflow("main-guard")
    assert set(triggers(guard)) == {"push"}
    for job in guard["jobs"].values():
        assert job_permissions(guard, job) == {"contents": "read", "issues": "write", "pull-requests": "read"}
    for name in ("breaks", "scope", "mutation", "kit-parity"):
        data = workflow(name)
        for job in data["jobs"].values():
            assert job_permissions(data, job) == {"contents": "read"}, name


def test_FR_1_0_09_mc1_regeneration_job_skips_bot_commits_and_commits_only_generated_paths() -> None:
    data = workflow("generate")
    assert set(triggers(data)) == {"pull_request", "push"}
    push = triggers(data)["push"] or {}
    assert push.get("branches") == ["main"]
    regen = next(job for job in data["jobs"].values() if "push" in norm(job.get("if")))
    condition = norm(regen.get("if"))
    assert "github.event_name == 'push'" in condition
    assert "!startsWith(github.event.head_commit.message, 'chore(bot):')" in condition
    script = steps_text(regen)
    assert "-m tools.index build" in script and "-m tools.progress build --on-main" in script
    assert "chore(bot): regenerate index and progress" in script
    assert "git status --porcelain" in script, "commits only when files changed (B2)"
    adds = re.findall(r"git add\s+([^\n;&|]+)", script)
    assert adds, "the commit names its paths"
    for add in adds:
        for path in add.split():
            ok = path == "--" or any(path == g.rstrip("/") or path.startswith(g) for g in GENERATED)
            assert ok, f"git add outside the generated paths: {path}"
    assert "github-actions[bot]" in script and "41898282+github-actions[bot]@users.noreply.github.com" in script
    pr_jobs = [job for job in data["jobs"].values() if "pull_request" in norm(job.get("if"))]
    assert len(pr_jobs) == 1
    pr_script = steps_text(pr_jobs[0])
    assert re.search(r"-m tools\.index build --out \S+", pr_script)
    assert re.search(r"-m tools\.progress build --on-main --out \S+", pr_script)
    assert "-m tools.progress lint" in pr_script
    assert "git commit" not in pr_script and "git push" not in pr_script


def test_FR_1_0_09_mc4_breaks_job_fails_when_a_recipe_survives_and_runs_nightly() -> None:
    data = workflow("breaks")
    on = triggers(data)
    assert "pull_request" in on
    assert on["schedule"] == [{"cron": "17 2 * * *"}]
    (job,) = data["jobs"].values()
    assert job["runs-on"] == HEAVY
    assert "continue-on-error" not in job and not any("continue-on-error" in s for s in job["steps"])
    script = steps_text(job)
    assert "-m tools.ci.refs wp" in script, "the WP comes from the branch name"
    assert re.search(r'-m tools\.audit\.breaks --wp "?\$', script), script
    assert "-m tools.audit.breaks --all" in script
    assert "::notice::" in script, "E1: no derivable WP prints a notice and succeeds"


def test_FR_1_0_09_mutation_job_is_advisory_and_uses_the_heavy_runner() -> None:
    text = (WORKFLOWS / "aqis-lab-mutation.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s*continue-on-error:\s*true\s*#\s*audit-allow:\s*advisory report\s*$", text, re.M)
    data = workflow("mutation")
    assert set(triggers(data)) == {"pull_request"}
    (job,) = data["jobs"].values()
    assert job["runs-on"] == HEAVY and job.get("continue-on-error") is True
    script = steps_text(job)
    assert "-m tools.audit.mutation_report --base" in script and "GITHUB_STEP_SUMMARY" in script
    assert any(str(s.get("uses", "")).startswith("actions/upload-artifact@") for s in job["steps"])


def test_FR_1_0_09_scope_main_guard_and_parity_triggers_and_runners() -> None:
    scope = workflow("scope")
    assert set(triggers(scope)) == {"pull_request"}
    (job,) = scope["jobs"].values()
    assert "startsWith(github.head_ref, 'wo/')" in norm(job.get("if")) and job["runs-on"] == "ubuntu-latest"
    assert "-m tools.ci.refs wo" in steps_text(job) and "-m tools.outsourcing scope --wo" in steps_text(job)
    guard = workflow("main-guard")
    assert (triggers(guard)["push"] or {}).get("branches") == ["main"]
    (job,) = guard["jobs"].values()
    assert job["runs-on"] == "ubuntu-latest"
    assert "-m tools.ci.main_guard" in steps_text(job) and "github.event.before" in json.dumps(job)
    parity = workflow("kit-parity")
    assert set(triggers(parity)) == {"pull_request", "push"}
    assert (triggers(parity)["push"] or {}).get("branches") == ["main"]
    for job in parity["jobs"].values():
        assert job["runs-on"] == "ubuntu-latest" and "-m tools.ci.kit_parity" in steps_text(job)


# ============================================================================== refs
def run(module: str, *args: str, cwd: Path = ROOT, env: dict | None = None) -> subprocess.CompletedProcess:
    full = dict(os.environ, PYTHONPATH=str(ROOT))
    full.update(env or {})
    return subprocess.run([sys.executable, "-P", "-m", module, *args], cwd=cwd, capture_output=True, text=True,
                          env=full, timeout=300)


@pytest.mark.parametrize("branch, wp, wo", [
    ("claude/wp-1-3-calibration", "WP-1.3", None),
    ("claude/wp-1-10-x", "WP-1.10", None),
    ("claude/wp-1-0-operating-model-v2", "WP-1.0", None),
    ("wo/WO-1.3-02", None, "WO-1.3-02"),
    ("wo/WO-1.10-11", None, "WO-1.10-11"),
    ("feature/x", None, None),
    ("main", None, None),
    ("claude/wp-x-y-z", None, None),
])
def test_FR_1_0_09_refs_derive_wp_and_work_order(branch: str, wp: str | None, wo: str | None) -> None:
    refs = importlib.import_module("tools.ci.refs")
    assert refs.wp_from_branch(branch) == wp
    assert refs.wo_from_branch(branch) == wo
    for kind, expected in (("wp", wp), ("wo", wo)):
        proc = run("tools.ci.refs", kind, branch)
        assert proc.returncode == 0 and proc.stdout.strip() == (expected or ""), (kind, branch, proc.stdout)


# ============================================================================== main guard (B5, E2)
STAND_IN_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["STAND_IN_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if not args or args[0] != "api":
    sys.stderr.write("stand-in gh only answers `gh api`\n")
    sys.exit(2)
method, endpoint, i, fields = "GET", None, 1, False
while i < len(args):
    a = args[i]
    if a in ("-X", "--method"):
        method, i = args[i + 1].upper(), i + 2
        continue
    if a in ("-f", "-F", "--field", "--raw-field"):
        fields, i = True, i + 2
        continue
    if a in ("-H", "--header", "--jq", "-q", "--input", "--template", "-t"):
        i += 2
        continue
    if a.startswith("-"):
        i += 1
        continue
    if endpoint is None:
        endpoint = a.lstrip("/").split("?")[0]
    i += 1
if fields and not any(a in ("-X", "--method") for a in args):
    method = "POST"
with open(os.environ["STAND_IN_GH_SCRIPT"], encoding="utf-8") as handle:
    script = json.load(handle)
key = f"{method} {endpoint}"
if key not in script:
    sys.stderr.write(f"stand-in gh: no answer for {key}\n")
    sys.exit(1)
answer = script[key]
if answer.get("status", 200) >= 400:
    sys.stderr.write(f"gh: HTTP {answer['status']}\n")
    sys.exit(1)
sys.stdout.write(json.dumps(answer.get("body")))
'''


def git(repo: Path, *args: str, who: tuple[str, str] = ("AQIS Fixture", "fixture@example.invalid"),
        committer: tuple[str, str] | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    committer = committer or who
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": who[0],
                "GIT_AUTHOR_EMAIL": who[1], "GIT_COMMITTER_NAME": committer[0], "GIT_COMMITTER_EMAIL": committer[1]})
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True, text=True,
                          env=env, timeout=60)
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")


def commit(repo: Path, files: dict[str, str], message: str, **who) -> str:
    for rel, text in files.items():
        write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message, **who)
    return git(repo, "rev-parse", "HEAD")


def gated_merge(repo: Path, wp: str, verdict: str, title_suffix: str = " (gate PASS)") -> tuple[str, dict]:
    branch = f"claude/wp-{wp[3]}-{wp[5]}-scratch"
    git(repo, "checkout", "-qb", branch)
    commit(repo, {f"aqis_lab/{wp[3]}_{wp[5]}.py": "VALUE = 1\n"}, f"{wp} code")
    head = commit(repo, {f"docs/progress/{wp}/AUDIT.md": f"# AUDIT — {wp}\n\n## Verdict: {verdict}\n"}, "audit")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--no-ff", "-q", "-m", f"Merge {wp}: {wp} scratch{title_suffix}", branch)
    merge = git(repo, "rev-parse", "HEAD")
    pr = {"number": int(wp[5]) + 10, "title": f"{wp} scratch", "head": {"ref": branch, "sha": head},
          "base": {"ref": "main"}, "merged_at": "2026-10-10T00:00:00Z"}
    return merge, {f"GET repos/{SLUG}/commits/{merge}/pulls": {"body": [pr]}}


@pytest.fixture
def history(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo, "docs/process/PROTECTED_PATHS.txt", (ROOT / "docs/process/PROTECTED_PATHS.txt").read_text("utf-8"))
    before = commit(repo, {"README.md": "# scratch\n"}, "base")
    script: dict = {}
    kinds: dict[str, str] = {}
    sha, answers = gated_merge(repo, "WP-9.1", "PASS")
    script.update(answers)
    kinds[sha] = "gated-merge"
    sha = commit(repo, {"docs/index/MAP.md": "map\n", "docs/progress/STATUS.md": "status\n"},
                 "chore(bot): regenerate index and progress", who=BOT)
    kinds[sha] = "bot-regeneration"
    sha = commit(repo, {"CLAUDE.md": "owner text\n", "docs/specs/phase-9/WP-9.9-x.md": "spec\n"}, "Update CLAUDE.md",
                 who=("Owner", "owner@example.invalid"), committer=WEB)
    kinds[sha] = "owner-never-edit"
    sha = commit(repo, {"aqis_lab/direct.py": "VALUE = 2\n"}, "direct push")
    kinds[sha] = "unexpected"
    sha = commit(repo, {"docs/index/MAP.md": "map 2\n", "aqis_lab/sneaky.py": "VALUE = 3\n"},
                 "chore(bot): regenerate index and progress", who=BOT)
    kinds[sha] = "unexpected"
    sha = commit(repo, {"bots/web.py": "VALUE = 4\n"}, "Update bots/web.py",
                 who=("Owner", "owner@example.invalid"), committer=WEB)
    kinds[sha] = "unexpected"
    sha, answers = gated_merge(repo, "WP-9.2", "FAIL")
    script.update(answers)
    kinds[sha] = "unexpected"
    sha, answers = gated_merge(repo, "WP-9.3", "PASS", title_suffix="")
    script.update(answers)
    kinds[sha] = "unexpected"
    for sha in kinds:
        script.setdefault(f"GET repos/{SLUG}/commits/{sha}/pulls", {"body": []})
    script[f"POST repos/{SLUG}/issues"] = {"status": 201, "body": {"number": 99}}
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(STAND_IN_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "script.json").write_text(json.dumps(script), encoding="utf-8")
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "STAND_IN_GH_LOG": str(tmp_path / "calls.jsonl"),
           "STAND_IN_GH_SCRIPT": str(tmp_path / "script.json"), "GIT_CONFIG_GLOBAL": os.devnull}
    return {"repo": repo, "before": before, "after": git(repo, "rev-parse", "HEAD"), "kinds": kinds, "env": env,
            "log": tmp_path / "calls.jsonl"}


def calls(history: dict) -> list[list[str]]:
    log = history["log"]
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def test_FR_1_0_09_mc3_main_guard_classifies_every_pushed_commit_and_flags_direct_pushes(history: dict) -> None:
    proc = run("tools.ci.main_guard", "--repo", SLUG, "--before", history["before"], "--after", history["after"],
               cwd=history["repo"], env=history["env"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    seen = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{7,40}", parts[0]):
            seen[parts[0][:7]] = parts[1]
    assert seen == {sha[:7]: kind for sha, kind in history["kinds"].items()}, proc.stdout
    issues = [c for c in calls(history) if f"repos/{SLUG}/issues" in c]
    titles = sorted(next(a.split("=", 1)[1] for a in c if a.startswith("title=")) for c in issues)
    unexpected = sorted(f"main-guard: unexpected commit {sha[:7]}" for sha, kind in history["kinds"].items()
                        if kind == "unexpected")
    assert titles == unexpected


def test_FR_1_0_09_main_guard_passes_a_clean_push(history: dict) -> None:
    repo = history["repo"]
    clean_before = git(repo, "rev-parse", "HEAD")
    commit(repo, {"docs/index/MAP.md": "map 3\n"}, "chore(bot): regenerate index and progress", who=BOT)
    script = json.loads(Path(history["env"]["STAND_IN_GH_SCRIPT"]).read_text(encoding="utf-8"))
    script[f"GET repos/{SLUG}/commits/{git(repo, 'rev-parse', 'HEAD')}/pulls"] = {"body": []}
    Path(history["env"]["STAND_IN_GH_SCRIPT"]).write_text(json.dumps(script), encoding="utf-8")
    proc = run("tools.ci.main_guard", "--repo", SLUG, "--before", clean_before, "--after", git(repo, "rev-parse", "HEAD"),
               cwd=repo, env=history["env"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not [c for c in calls(history) if f"repos/{SLUG}/issues" in c]


# ============================================================================== kit parity (E4)
def parity_repo(tmp_path: Path, staged: dict[str, str] | None, installed: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, text in (staged or {}).items():
        write(repo, f"kit-staging/.claude/{rel}", text)
    for rel, text in installed.items():
        write(repo, f".claude/{rel}", text)
    git(repo, "init", "-q")
    commit(repo, {"README.md": "# scratch\n"}, "base")
    return repo


def kit_blocker(text: str = "Install staged kit from kit-staging/.claude/ into .claude/.", status: str = "OPEN",
                capability: str = "KIT") -> str:
    return (f"# BLK-9.1-01 — kit\nStatus: {status}\nWP: WP-9.1\nOwner capability: {capability}\n"
            f"Raised: 2026-10-10\n\nWhat I need: {text}\n")


def test_FR_1_0_09_mc5_kit_parity_fails_on_a_difference_without_a_kit_blocker(tmp_path: Path) -> None:
    repo = parity_repo(tmp_path, {"hooks/stop_gate.py": "v4\n", "hooks/_protected.py": "same\n"},
                       {"hooks/stop_gate.py": "v3\n", "hooks/_protected.py": "same\n", "hooks/extra.py": "x\n"})
    proc = run("tools.ci.kit_parity", cwd=repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    out = proc.stdout + proc.stderr
    assert "hooks/stop_gate.py" in out and "hooks/_protected.py" not in out and "hooks/extra.py" not in out


@pytest.mark.parametrize("case, expected", [
    ("identical", 0), ("missing-installed", 1), ("open-kit-blocker", 0), ("resolved-kit-blocker", 1),
    ("open-blocker-other-class", 1), ("no-staging", 0)])
def test_FR_1_0_09_kit_parity_cases(tmp_path: Path, case: str, expected: int) -> None:
    staged = {"hooks/stop_gate.py": "v4\n"}
    installed = {"hooks/stop_gate.py": "v4\n" if case == "identical" else "v3\n"}
    if case == "missing-installed":
        installed = {}
    if case == "no-staging":
        staged = None
    repo = parity_repo(tmp_path, staged, installed)
    if case == "open-kit-blocker":
        write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", kit_blocker())
    elif case == "resolved-kit-blocker":
        write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", kit_blocker(status="RESOLVED"))
    elif case == "open-blocker-other-class":
        write(repo, "docs/progress/blockers.d/BLK-9.1-01.md", kit_blocker(capability="ACCESS"))
    proc = run("tools.ci.kit_parity", cwd=repo)
    assert proc.returncode == expected, (case, proc.stdout + proc.stderr)
    if case in ("open-kit-blocker", "no-staging"):
        assert "::notice::" in proc.stdout, case
    if expected == 1:
        assert "hooks/stop_gate.py" in proc.stdout + proc.stderr, (case, "the difference is named")
        assert "Traceback" not in proc.stderr, (case, proc.stderr)
