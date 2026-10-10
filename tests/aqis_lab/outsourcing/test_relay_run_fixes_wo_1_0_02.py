"""Claude's fix after the first WO-1.0-04 relay run (FR-1.0-02, DEC-1.0-05), written before the fix.

On 2026-10-10, codestral-2508 wrapped its whole reply in a ```` ```text ```` fence three times. `parse_bundle` refused
it, correctly (WO-1.0-01 B5: no non-blank text outside the four blocks). But the fix turn said "Your answer was blocked
or empty (Bundle error: …)": that wording is for SAFETY, RECITATION or an empty answer (WO-1.0-02 B11), and it never
told the model what RETURN_FORMAT requires. Bundle errors and refused imports now get a fix reason that names the error
and restates RETURN_FORMAT's rules on text outside the blocks.
"""
from __future__ import annotations

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_02 import STEPS, load, mod, repo  # noqa: F401  (repo is a fixture)


@pytest.mark.parametrize("reason", ["Bundle error: Non-blank text outside block: '```text'",
                                    "Import refused: path outside outputs: tools/x.py"])
def test_FR_1_0_02_unreadable_answer_fix_order_names_the_error_and_the_format_rules(repo, reason):
    order, _ = load(repo)
    text = mod("fixorder").build_fix_order(order, mod("records").CheckResults(results=()), 1, STEPS[0], "1", reason)
    reason_section = text.split("## Reason for fix\n", 1)[1].split("\n## ", 1)[0]
    assert reason in reason_section
    assert "blocked or empty" not in reason_section
    assert "=== MANIFEST ===" in reason_section
    assert "code fence" in reason_section and "nothing before" in reason_section


@pytest.mark.parametrize("reason, phrase", [("MAX_TOKENS", "cut off"), ("SAFETY", "blocked or empty"),
                                            ("RECITATION", "blocked or empty"), ("STOP", "blocked or empty")])
def test_FR_1_0_02_model_stop_reasons_keep_their_b11_wording(repo, reason, phrase):
    order, _ = load(repo)
    text = mod("fixorder").build_fix_order(order, mod("records").CheckResults(results=()), 1, STEPS[0], "1", reason)
    assert phrase in text.split("## Reason for fix\n", 1)[1]
