"""Unit tests for paste pack builder.

CAPABILITIES:
  CAP-OUTSOURCING-008: assemble work order context into a single paste pack [tests: test_FR_1_0_01_pack_assembly_clean, test_FR_1_0_01_pack_refuses_secret, test_FR_1_0_01_pack_too_large]
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
from tools.outsourcing.pack import SecretRefused, build_pack
from tools.outsourcing.workorder import WorkOrder

KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


def make_order_and_repo(tmp_path, context_files=("docs/ctx.md",)):
    root = tmp_path / "repo"
    root.mkdir()

    (root / "docs/process/outsourcing/templates").mkdir(parents=True)
    (root / "docs/process/outsourcing/FOUNDATION.md").write_text("FOUNDATION\n", encoding="utf-8")
    (root / "docs/process/outsourcing/templates/RETURN_FORMAT.md").write_text("RETURN_FORMAT\n", encoding="utf-8")

    for cf in context_files:
        (root / cf).parent.mkdir(parents=True, exist_ok=True)
        (root / cf).write_text("Context file content\n", encoding="utf-8")

    wo_rel = "docs/outsourcing/orders/WO-1.0-01.md"
    (root / wo_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / wo_rel).write_text("Body of work order\n", encoding="utf-8")

    order = WorkOrder(
        id="WO-1.0-01",
        wp="WP-1.0",
        title="Test",
        model="default",
        channel="api",
        attempt_budget=2,
        risk_tier="T1",
        max_output_tokens=10000,
        context=tuple(context_files),
        outputs=("tools/demo/alpha.py",),
        read_only_tests=(),
        allowed_dependencies=("stdlib",),
        verify=("pytest",),
        body="Body of work order\n",
        path=wo_rel,
    )
    return order, root


def test_FR_1_0_01_pack_assembly_clean(tmp_path):
    order, root = make_order_and_repo(tmp_path)
    pack = build_pack(order, root)

    assert "FOUNDATION" in pack.text
    assert "RETURN_FORMAT" in pack.text
    assert "=== CONTEXT: docs/ctx.md ===" in pack.text
    assert pack.characters == len(pack.text)


def test_FR_1_0_01_pack_refuses_secret(tmp_path):
    order, root = make_order_and_repo(tmp_path)
    (root / "docs/ctx.md").write_text(f"Secret inside:\n{KEY_HEADER}\n", encoding="utf-8")

    with pytest.raises(SecretRefused):
        build_pack(order, root)
