"""Claude's fix for WO-1.0-11 B15/B16 (FR-1.0-02), written first: FIX-B15-final-questions.

On 2026-10-12, WO-1.0-03's final verification failed once and the final fix round's answer was a QUESTIONS block.
The relay crashed with `tools.outsourcing.importer.QuestionsReturned: Bundle contains questions; import stopped`
(exit 1), with no summary, ledger or step-log stop. B15: questions go into the summary, a stop with reason QUESTIONS
goes into the step log, nothing is imported, and the run finishes with QUESTIONS (exit 4).
"""
from __future__ import annotations

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_11 import (  # noqa: F401  (fixtures)
    STEPS, WO, WO_BRANCH, good_content, scratch, stand)

TEST_BETA = STEPS[1][1]
# Passes when its file runs alone (the part's quick checks) and fails in the order's verify command, which also
# collects test_alpha.py: so the final verification fails and a final fix round is requested.
ALONE_ONLY = good_content(TEST_BETA).replace(
    "    assert VALUE",
    "    import sys\n    assert not any(name.endswith('test_alpha') for name in sys.modules), 'run alone only'\n"
    "    assert VALUE")


def test_FR_1_0_02_fix_questions_in_a_final_fix_round_finish_with_exit_4(scratch, stand):
    stand.script["g-one"].extend([("auto",), ("override", {TEST_BETA: ALONE_ONLY}), ("questions",)])
    proc = scratch.run(stand.url)
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    summary = scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/summary.md")
    assert "QUESTIONS" in summary and "QUESTION-MARKER" in summary
    steps_log = scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/steps.md")
    assert "QUESTIONS" in steps_log
    assert scratch.show(WO_BRANCH, TEST_BETA) == ALONE_ONLY
