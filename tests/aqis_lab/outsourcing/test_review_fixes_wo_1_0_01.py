"""Claude's review fixes for WO-1.0-01 (FR-1.0-01), written before the fixes (WO review checklist items 4 and 6).

Each test pins a gap found in the delivered code:
- an invalid path leaked as `ValueError` instead of the order's named errors;
- manifest paths were not normalised;
- QUESTIONS were not split per question;
- the CLI swallowed a git failure, let read errors and `PackTooLarge` escape as tracebacks with exit 1 (the code
  for a scope violation), and reported an unreadable file as a secret;
- the scope check dropped the reason a fetch failed.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORDER_REL = "docs/outsourcing/orders/WO-9.9-01.md"
OWNER_FILES = ("docs/process/PROTECTED_PATHS.txt", "docs/process/outsourcing/FOUNDATION.md",
               "docs/process/outsourcing/templates/RETURN_FORMAT.md")


def mod(name: str):
    return importlib.import_module(f"tools.outsourcing.{name}")


def git(repo: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "AQIS Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "AQIS Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, check=True, capture_output=True,
                   env=env, timeout=60)


def order_text(outputs=("tools/demo/alpha.py",), steps=None) -> str:
    lines = ["---", "id: WO-9.9-01", "wp: WP-9.9", "title: Scratch", "model: default", "channel: api",
             "attempt_budget: 2", "risk_tier: T2", "max_output_tokens: 1000", "context:", "  - docs/notes/c.md",
             "outputs:"] + [f"  - {p}" for p in outputs]
    if steps:
        lines += ["steps:"] + [f"  - {s}" for s in steps]
    lines += ["read_only_tests:", "allowed_dependencies:", "  - stdlib", "verify:", "  - python -m pytest -q",
              "---", "", "# body", ""]
    return "\n".join(lines)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in OWNER_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    (root / "docs/notes").mkdir(parents=True)
    (root / "docs/notes/c.md").write_text("context\n", encoding="utf-8")
    (root / ORDER_REL).parent.mkdir(parents=True)
    (root / ORDER_REL).write_text(order_text(), encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return root


def cli(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "tools.outsourcing", *args], cwd=cwd, capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=120)


@pytest.mark.parametrize("output", ["tools\\demo\\alpha.py", "/etc/alpha.py", "tools/../alpha.py"])
def test_FR_1_0_01_invalid_output_path_is_a_work_order_error(repo, output):
    (repo / ORDER_REL).write_text(order_text(outputs=(output,)), encoding="utf-8")
    with pytest.raises(mod("workorder").WorkOrderError):
        mod("workorder").load_work_order(repo / ORDER_REL, repo)
    proc = cli(repo, "validate", "--wo", ORDER_REL)
    assert proc.returncode == 2 and "Traceback" not in proc.stderr


def test_FR_1_0_01_invalid_step_path_is_a_work_order_error(repo):
    (repo / ORDER_REL).write_text(order_text(outputs=("tools/demo/alpha.py",), steps=("../alpha.py",)),
                                  encoding="utf-8")
    order = mod("workorder").load_work_order(repo / ORDER_REL, repo)
    with pytest.raises(mod("workorder").WorkOrderError):
        mod("workorder").plan_steps(order)


def bundle(path_in_marker: str, path_in_manifest: str) -> str:
    return (f"=== MANIFEST ===\n| path | action | purpose |\n| --- | --- | --- |\n| {path_in_manifest} | create | x |\n"
            f"=== END MANIFEST ===\n=== FILE: {path_in_marker} ===\nVALUE = 1\n=== END FILE ===\n")


def test_FR_1_0_01_absolute_file_marker_is_a_bundle_error():
    with pytest.raises(mod("bundle").BundleError):
        mod("bundle").parse_bundle(bundle("/etc/alpha.py", "/etc/alpha.py"))


def test_FR_1_0_01_manifest_paths_are_normalised_like_file_markers():
    parsed = mod("bundle").parse_bundle(bundle("./tools/demo/alpha.py", "./tools/demo/alpha.py "))
    assert [path for path, _ in parsed.files] == ["tools/demo/alpha.py"]


def test_FR_1_0_01_questions_are_split_per_numbered_question():
    text = "=== QUESTIONS ===\n1. First question,\n   continued here?\n2. Second question?\n=== END QUESTIONS ===\n"
    assert mod("bundle").parse_bundle(text).questions == ("First question,\ncontinued here?", "Second question?")


def test_FR_1_0_01_cli_outside_a_git_repository_fails_clearly(tmp_path):
    proc = cli(tmp_path, "validate", "--wo", "missing.md")
    assert proc.returncode == 2 and "git" in proc.stderr.lower() and "Traceback" not in proc.stderr


def test_FR_1_0_01_cli_unreadable_bundle_exits_3(repo):
    proc = cli(repo, "import", "--wo", ORDER_REL, "--bundle", "no-such-answer.md")
    assert proc.returncode == 3 and "no-such-answer.md" in proc.stderr and "Traceback" not in proc.stderr


def test_FR_1_0_01_pack_missing_foundation_is_not_reported_as_a_secret(repo):
    (repo / OWNER_FILES[1]).unlink()
    proc = cli(repo, "pack", "--wo", ORDER_REL)
    assert proc.returncode == 2 and "FOUNDATION.md" in proc.stderr and "Traceback" not in proc.stderr


def test_FR_1_0_01_pack_too_large_exits_2_without_traceback(repo):
    (repo / "docs/notes/c.md").write_text("x" * 600_001, encoding="utf-8")
    git(repo, "commit", "-qam", "large context")
    with pytest.raises(mod("pack").PackTooLarge):
        mod("pack").build_pack(mod("workorder").load_work_order(repo / ORDER_REL, repo), repo)
    proc = cli(repo, "pack", "--wo", ORDER_REL)
    assert proc.returncode == 2 and "Traceback" not in proc.stderr


def test_FR_1_0_01_scope_error_keeps_the_fetch_failure(repo):
    order = mod("workorder").load_work_order(repo / ORDER_REL, repo)
    with pytest.raises(mod("scope").ScopeError, match="fetch"):
        mod("scope").check_scope(order, repo, "origin/main", "HEAD")
