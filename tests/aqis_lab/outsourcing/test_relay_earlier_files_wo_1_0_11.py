"""Claude's fix for WO-1.0-11 B12/B14 (FR-1.0-02), written first: FIX-B14-earlier-files.

On 2026-10-12, WO-1.0-03 step 4's second attempt changed `tools/index/registry.py`, an earlier output that the fix
order allowed because a failing log named it. The third attempt passed and the part was accepted. But the commit held
only the part's own files, so the next run's worktree reset discarded the registry change and step 5 could never pass.
B12 says an earlier file changed this way "is recorded again under the current part", and B14 says the commit holds
"exactly the part's files, any earlier file changed under B12, and the step log".
"""
from __future__ import annotations

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_11 import (  # noqa: F401  (fixtures)
    STEPS, WO, WO_BRANCH, git, good_content, scratch, stand)

ALPHA, TEST_ALPHA = STEPS[0]
BETA, TEST_BETA = STEPS[1]
NAMES_ALPHA = good_content(TEST_BETA).replace(
    "    assert VALUE", f"    assert False, 'needs a change in {ALPHA}'\n    assert VALUE")
ALPHA_FIXED = good_content(ALPHA).rstrip("\n") + "  # FIXED-MARKER\n"


def test_FR_1_0_02_fix_earlier_file_changed_by_a_fix_turn_is_committed_with_the_part(scratch, stand):
    stand.script["g-one"].extend([("auto",), ("override", {TEST_BETA: NAMES_ALPHA}), ("override", {ALPHA: ALPHA_FIXED})])
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FIXED-MARKER" in scratch.show(WO_BRANCH, ALPHA)
    step_two = git(scratch.root, "log", "--format=%H", "--grep", f"{WO} step 2:", WO_BRANCH).split()
    assert len(step_two) == 1
    assert ALPHA in git(scratch.root, "show", "--name-only", "--format=", step_two[0]).split()
    assert "FIXED-MARKER" in scratch.show(step_two[0], ALPHA)
    steps_log = scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/steps.md")
    part_two = next(line for line in steps_log.splitlines() if line.startswith("| 2 |"))
    assert ALPHA in part_two and BETA in part_two
