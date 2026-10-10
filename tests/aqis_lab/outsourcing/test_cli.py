"""Unit tests for CLI entry point.

CAPABILITIES:
  CAP-OUTSOURCING-009: command-line interface for validate, import, scope and pack [tests: test_FR_1_0_01_cli_validate, test_FR_1_0_01_cli_import, test_FR_1_0_01_cli_scope, test_FR_1_0_01_cli_pack]
INPUTS AND OUTPUTS: pytest tests.
CONTRACTS: none.
INVARIANTS:
  - All tests pass cleanly.
NOT IN SCOPE:
  - Acceptance tests (see test_acceptance_wo_1_0_01.py).
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import os
import subprocess
from tools.outsourcing.__main__ import main


def make_repo_and_order(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    # Git init
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
    subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q"], cwd=root, check=True, env=env)

    (root / "docs/process/outsourcing/templates").mkdir(parents=True)
    (root / "docs/process/outsourcing/FOUNDATION.md").write_text("FOUNDATION\n", encoding="utf-8")
    (root / "docs/process/outsourcing/templates/RETURN_FORMAT.md").write_text("RETURN_FORMAT\n", encoding="utf-8")

    (root / "docs/process/PROTECTED_PATHS.txt").write_text("[NEVER]\nCLAUDE.md\n[GUARDED]\nbots/**\n[LAB-OWNED]\ntests/aqis_lab/**\n", encoding="utf-8")

    (root / "docs/ctx.md").write_text("Context\n", encoding="utf-8")

    wo_text = """---
id: WO-1.0-01
wp: WP-1.0
title: Test
model: default
channel: api
attempt_budget: 2
risk_tier: T1
max_output_tokens: 10000
context:
  - docs/ctx.md
outputs:
  - tools/demo/alpha.py
read_only_tests: []
allowed_dependencies:
  - stdlib
verify:
  - pytest
---
Body
"""
    wo_path = root / "docs/outsourcing/orders/WO-1.0-01.md"
    wo_path.parent.mkdir(parents=True, exist_ok=True)
    wo_path.write_text(wo_text, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True, env=env)

    return root, wo_path


def test_FR_1_0_01_cli_validate(tmp_path, monkeypatch):
    root, wo_path = make_repo_and_order(tmp_path)
    monkeypatch.chdir(root)

    code = main(["validate", "--wo", str(wo_path)])
    assert code == 0


def test_FR_1_0_01_cli_import(tmp_path, monkeypatch):
    root, wo_path = make_repo_and_order(tmp_path)
    monkeypatch.chdir(root)

    bundle_text = """=== MANIFEST ===
| path | action | purpose |
| --- | --- | --- |
| tools/demo/alpha.py | create | test |
=== END MANIFEST ===
=== FILE: tools/demo/alpha.py ===
A = 1
=== END FILE ===
=== DOD ===
| item | met at | how |
| --- | --- | --- |
| D1 | tools/demo/alpha.py:1 | ok |
=== END DOD ===
"""
    bundle_path = root / "answer.md"
    bundle_path.write_text(bundle_text, encoding="utf-8")

    code = main(["import", "--wo", str(wo_path), "--bundle", str(bundle_path)])
    assert code == 0
    assert (root / "tools/demo/alpha.py").read_text(encoding="utf-8") == "A = 1\n"


def test_FR_1_0_01_cli_scope(tmp_path, monkeypatch):
    root, wo_path = make_repo_and_order(tmp_path)
    monkeypatch.chdir(root)

    code = main(["scope", "--wo", str(wo_path), "--base", "HEAD"])
    assert code == 0


def test_FR_1_0_01_cli_pack(tmp_path, monkeypatch):
    root, wo_path = make_repo_and_order(tmp_path)
    monkeypatch.chdir(root)

    out_path = root / "pack.txt"
    code = main(["pack", "--wo", str(wo_path), "--out", str(out_path)])
    assert code == 0
    assert out_path.exists()
