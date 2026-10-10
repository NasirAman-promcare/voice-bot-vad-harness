"""Unit tests for tools.outsourcing.prompt.

CAPABILITIES:
  CAP-OUTSOURCING-PROMPT: Build provider-neutral requests sent to model [tests: test_prompt.py]
INPUTS AND OUTPUTS: Request builder tests.
CONTRACTS: none.
INVARIANTS: Prompt building follows B3-B6 specifications.
NOT IN SCOPE: Network I/O.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from tools.outsourcing.prompt import SecretInRequest, step_pack, step_request, with_fix_turn
from tools.outsourcing.records import StepPart
from tools.outsourcing.workorder import load_work_order, plan_steps


def test_secret_in_request_raises(tmp_path: Path):
    # Set up scratch files
    (tmp_path / "docs" / "process").mkdir(parents=True)
    (tmp_path / "docs" / "process" / "PROTECTED_PATHS.txt").write_text("[LAB-OWNED]\nout.py\n", encoding="utf-8")
    (tmp_path / "docs" / "process" / "outsourcing").mkdir(parents=True)
    (tmp_path / "docs" / "process" / "outsourcing" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "process" / "outsourcing" / "FOUNDATION.md").write_text("Foundation", encoding="utf-8")
    (tmp_path / "docs" / "process" / "outsourcing" / "templates" / "RETURN_FORMAT.md").write_text("Format", encoding="utf-8")

    order_file = tmp_path / "order.md"
    order_file.write_text(
        "---\nid: WO-1.0-02\nwp: WP-1.0\ntitle: t\nmodel: default\nchannel: api\n"
        "attempt_budget: 3\nrisk_tier: T1\nmax_output_tokens: 100\n"
        "context:\n  - secret.md\noutputs:\n  - out.py\nread_only_tests:\n  - test_ro.py\n"
        "allowed_dependencies:\n  - stdlib\nverify:\n  - pytest\n---\nbody",
        encoding="utf-8",
    )
    (tmp_path / "secret.md").write_text("ghp_" + "A" * 36, encoding="utf-8")
    (tmp_path / "out.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "test_ro.py").write_text("def test_x(): pass", encoding="utf-8")

    order = load_work_order(order_file, tmp_path)
    plan = plan_steps(order)
    part = StepPart("1", ("out.py",))

    with pytest.raises(SecretInRequest) as exc_info:
        step_request(order, plan, part, tmp_path)
    assert exc_info.value.path == "secret.md"
