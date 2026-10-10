"""Unit tests for bundle importer.

CAPABILITIES:
  CAP-OUTSOURCING-006: write bundle files atomically with mode and expected checks [tests: test_FR_1_0_01_import_first_mode, test_FR_1_0_01_import_fix_mode, test_FR_1_0_01_questions_refused, test_FR_1_0_01_existing_directory_refused]
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
from tools.outsourcing.bundle import Bundle
from tools.outsourcing.importer import ImportRefused, QuestionsReturned, import_bundle
from tools.outsourcing.workorder import WorkOrder


def make_order(outputs=("tools/demo/alpha.py", "tools/demo/beta.py")):
    return WorkOrder(
        id="WO-1.0-01",
        wp="WP-1.0",
        title="Test",
        model="default",
        channel="api",
        attempt_budget=2,
        risk_tier="T1",
        max_output_tokens=10000,
        context=(),
        outputs=outputs,
        read_only_tests=(),
        allowed_dependencies=("stdlib",),
        verify=("pytest",),
    )


def test_FR_1_0_01_import_first_mode(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    order = make_order()
    bundle = Bundle(
        manifest=(("tools/demo/alpha.py", "c", "p"), ("tools/demo/beta.py", "c", "p")),
        files=(("tools/demo/alpha.py", "A = 1\n"), ("tools/demo/beta.py", "B = 2\n")),
        dod=(),
        questions=(),
    )

    report = import_bundle(bundle, order, root, mode="first")
    assert len(report.files) == 2
    assert (root / "tools/demo/alpha.py").read_text(encoding="utf-8") == "A = 1\n"
    assert (root / "tools/demo/beta.py").read_text(encoding="utf-8") == "B = 2\n"


def test_FR_1_0_01_import_fix_mode(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    order = make_order()
    bundle = Bundle(
        manifest=(("tools/demo/alpha.py", "c", "p"),),
        files=(("tools/demo/alpha.py", "A = 2\n"),),
        dod=(),
        questions=(),
    )

    report = import_bundle(bundle, order, root, mode="fix", expected={"tools/demo/alpha.py"})
    assert len(report.files) == 1
    assert (root / "tools/demo/alpha.py").read_text(encoding="utf-8") == "A = 2\n"


def test_FR_1_0_01_questions_refused(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    order = make_order()
    bundle = Bundle(
        manifest=(),
        files=(),
        dod=(),
        questions=("Question 1?",),
    )

    with pytest.raises(QuestionsReturned):
        import_bundle(bundle, order, root, mode="first")


def test_FR_1_0_01_existing_directory_refused(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "tools/demo/alpha.py").mkdir(parents=True)
    order = make_order()
    bundle = Bundle(
        manifest=(("tools/demo/alpha.py", "c", "p"), ("tools/demo/beta.py", "c", "p")),
        files=(("tools/demo/alpha.py", "A = 1\n"), ("tools/demo/beta.py", "B = 2\n")),
        dod=(),
        questions=(),
    )

    with pytest.raises(ImportRefused, match="exists as a directory"):
        import_bundle(bundle, order, root, mode="first")
