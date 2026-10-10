"""Claude's review fixes for WO-1.0-02 (FR-1.0-02), written before the fixes (WO review checklist items 4 and 5).

- B7 item 4 and B9: the `read-only-tests` check reported a pass without comparing any hash. It now compares every
  read-only test with its version at the base commit. A changed or deleted read-only test is an integrity failure
  (relay exit 9), whichever check sees it first (scope runs before it), and nothing after it runs.
- B7 item 3 and WO-1.0-07 B7: `kit-staging/` code is scanned by the relay's checks instead of the audit gate, but
  `gate.scan_table` returns no table for it, so staged hooks went unscanned. They get the gate's code patterns.
"""
from __future__ import annotations

import sys

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_02 import (  # noqa: F401  (repo is a fixture)
    ORDER_REL, READ_ONLY, STEPS, git, head, header, load, mod, module_text, part, repo, scratch_test_source, write)


def test_FR_1_0_02_read_only_test_changed_before_quick_checks_is_integrity_failure(repo, tmp_path):
    base = head(repo)
    write(repo, READ_ONLY, "def test_demo():\n    assert True or 1\n")
    write(repo, STEPS[0][0], module_text("alpha"))
    write(repo, STEPS[0][1], scratch_test_source("alpha"))
    order, _ = load(repo)
    results = mod("checks").quick_checks(order, part("1", STEPS[0]), repo, tmp_path / "logs", base, sys.executable, 120)
    names = [r.name for r in results.results]
    last = results.results[-1]
    assert "tests" not in names and READ_ONLY in last.summary
    assert last.passed is False and last.integrity is True and results.passed is False


def test_FR_1_0_02_read_only_test_changed_before_full_checks_is_integrity_failure(repo, tmp_path):
    base = head(repo)
    order, _ = load(repo)
    (repo / READ_ONLY).unlink()
    for step in STEPS:
        name = step[0].rsplit("/", 1)[1][:-3]
        write(repo, step[0], module_text(name))
        write(repo, step[1], scratch_test_source(name))
    results = mod("checks").full_checks(order, repo, tmp_path / "logs", base, sys.executable, 120)
    last = results.results[-1]
    assert last.integrity is True and last.passed is False and READ_ONLY in last.summary
    assert not any(r.name.startswith("verify-") for r in results.results)


def kit_order(tmp_root) -> None:
    lines = ["---", "id: WO-9.9-02", "wp: WP-9.9", "title: Scratch kit order", "model: default", "channel: api",
             "attempt_budget: 2", "risk_tier: T1", "max_output_tokens: 1000", "context:", "  - docs/notes/context.md",
             "outputs:", "  - kit-staging/.claude/hooks/demo_hook.py", "read_only_tests:", f"  - {READ_ONLY}",
             "allowed_dependencies:", "  - stdlib", "verify:", "  - python -m pytest -q", "---", "", "# body", ""]
    write(tmp_root, ORDER_REL, "\n".join(lines))
    git(tmp_root, "commit", "-qam", "kit order")


@pytest.mark.parametrize("suffix, passes", [("", False), ("  # audit-allow: scratch reason for the acceptance test", True)],
                         ids=["flagged", "flagged-with-audit-allow"])
def test_FR_1_0_02_kit_staging_code_is_pattern_scanned(repo, tmp_path, suffix, passes):
    kit_order(repo)
    base = head(repo)
    hook = "kit-staging/.claude/hooks/demo_hook.py"
    write(repo, hook, header("demo_hook") + f"LIMIT = 3  # TODO tidy{suffix}\n")
    order, _ = load(repo)
    results = mod("checks").quick_checks(order, part("1", (hook,)), repo, tmp_path / "logs", base, sys.executable, 120)
    by_name = {r.name: r for r in results.results}
    assert by_name["patterns"].passed is passes
