"""Unit tests for work order parsing and step planning.

CAPABILITIES:
  CAP-OUTSOURCING-004: parse and validate work order front matter and step plan [tests: test_FR_1_0_01_load_valid_work_order, test_FR_1_0_01_invalid_front_matter_errors, test_FR_1_0_01_step_plan_valid_and_invalid]
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

import pytest
from tools.outsourcing.workorder import WorkOrderError, load_work_order, plan_steps


def make_repo(tmp_path, context_file="docs/context.md", read_only="tests/test_ro.py"):
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    policy_dir = root / "docs" / "process"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "PROTECTED_PATHS.txt").write_text(
        "[NEVER]\nCLAUDE.md\n\n[GUARDED]\nbots/**\n\n[LAB-OWNED]\ntests/aqis_lab/**\n",
        encoding="utf-8"
    )
    (root / context_file).parent.mkdir(parents=True, exist_ok=True)
    (root / context_file).write_text("context content\n", encoding="utf-8")
    (root / read_only).parent.mkdir(parents=True, exist_ok=True)
    (root / read_only).write_text("def test_ro(): pass\n", encoding="utf-8")
    return root


def create_wo_file(root, text):
    wo_path = root / "docs" / "outsourcing" / "orders" / "WO-1.0-01.md"
    wo_path.parent.mkdir(parents=True, exist_ok=True)
    wo_path.write_text(text, encoding="utf-8")
    return wo_path


def valid_wo_text(outputs=("tools/demo/alpha.py",), steps=None):
    lines = [
        "---",
        "id: WO-1.0-01",
        "wp: WP-1.0",
        "title: Test Order",
        "model: default",
        "channel: api",
        "attempt_budget: 3",
        "risk_tier: T1",
        "max_output_tokens: 40000",
        "context:",
        "  - docs/context.md",
        "outputs:",
    ]
    lines += [f"  - {p}" for p in outputs]
    if steps:
        lines += ["steps:"] + [f"  - {s}" for s in steps]
    lines += [
        "read_only_tests:",
        "  - tests/test_ro.py",
        "allowed_dependencies:",
        "  - stdlib",
        "verify:",
        "  - pytest",
        "---",
        "",
        "Body content here."
    ]
    return "\n".join(lines)


def test_FR_1_0_01_load_valid_work_order(tmp_path):
    root = make_repo(tmp_path)
    wo_path = create_wo_file(root, valid_wo_text())
    order = load_work_order(wo_path, root)

    assert order.id == "WO-1.0-01"
    assert order.wp == "WP-1.0"
    assert order.attempt_budget == 3
    assert order.risk_tier == "T1"
    assert order.max_output_tokens == 40000
    assert order.outputs == ("tools/demo/alpha.py",)
    assert order.body.strip() == "Body content here."


def test_FR_1_0_01_invalid_front_matter_errors(tmp_path):
    root = make_repo(tmp_path)

    # Missing required key
    text_no_id = valid_wo_text().replace("id: WO-1.0-01\n", "")
    wo_path = create_wo_file(root, text_no_id)
    with pytest.raises(WorkOrderError, match="Missing required"):
        load_work_order(wo_path, root)

    # Protected output
    text_protected = valid_wo_text(outputs=("CLAUDE.md",))
    wo_path = create_wo_file(root, text_protected)
    with pytest.raises(WorkOrderError, match="protected"):
        load_work_order(wo_path, root)

    # Missing context file
    text_missing_ctx = valid_wo_text().replace("docs/context.md", "docs/missing.md")
    wo_path = create_wo_file(root, text_missing_ctx)
    with pytest.raises(WorkOrderError, match="does not exist"):
        load_work_order(wo_path, root)


def test_FR_1_0_01_step_plan_valid_and_invalid(tmp_path):
    root = make_repo(tmp_path)
    outputs = ("tools/demo/a.py", "tools/demo/b.py", "tools/demo/c.py", "tools/demo/d.py")
    steps = ("tools/demo/a.py, tools/demo/b.py", "tools/demo/c.py, tools/demo/d.py")

    wo_path = create_wo_file(root, valid_wo_text(outputs=outputs, steps=steps))
    order = load_work_order(wo_path, root)
    planned = plan_steps(order)
    assert len(planned) == 2
    assert planned[0].number == 1
    assert planned[0].paths == ("tools/demo/a.py", "tools/demo/b.py")
    assert planned[1].number == 2
    assert planned[1].paths == ("tools/demo/c.py", "tools/demo/d.py")

    # Missing step list with > 3 non-init outputs
    wo_path_no_steps = create_wo_file(root, valid_wo_text(outputs=outputs))
    order_no_steps = load_work_order(wo_path_no_steps, root)
    with pytest.raises(WorkOrderError, match="add a steps list"):
        plan_steps(order_no_steps)
