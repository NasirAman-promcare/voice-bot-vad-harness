"""Unit tests for tools.outsourcing.ledger.

CAPABILITIES:
  CAP-OUTSOURCING-LEDGER: Write summary.md and ledger fragment for relay outcomes. [tests: test_ledger.py]
INPUTS AND OUTPUTS: Test cases for writing ledger fragments and summary files.
CONTRACTS: none.
INVARIANTS:
  - Ledger formatting conforms to FRAGMENTS.md format.
NOT IN SCOPE:
  - Network execution.
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
"""
from __future__ import annotations

from pathlib import Path

from tools.outsourcing.ledger import write_ledger_fragment, write_summary
from tools.outsourcing.records import RelayOutcome, Result, StepRecord


def test_write_summary_and_ledger(tmp_path: Path):
    sum_path = tmp_path / "summary.md"
    led_path = tmp_path / "ledger.md"

    step_rec = StepRecord(
        label="1",
        files=(("a.py", "hasha"),),
        attempts=1,
        model="g-one",
        provider="gemini",
        model_version="v1",
        prompt_tokens=100,
        output_tokens=50,
        seconds_waited=0.5,
    )

    outcome = RelayOutcome(result=Result.ACCEPTED, accepted_parts=(step_rec,))

    write_summary(sum_path, outcome, written_files=("a.py",))
    assert sum_path.exists()
    sum_text = sum_path.read_text(encoding="utf-8")
    assert "# Summary: ACCEPTED" in sum_text
    assert "g-one" in sum_text

    write_ledger_fragment(
        led_path,
        wo_id="WO-1.0-11",
        outcome=outcome,
        total_requests=1,
        total_prompt_tokens=100,
        total_output_tokens=50,
        models_used=(("g-one", "gemini"),),
    )
    assert led_path.exists()
    led_text = led_path.read_text(encoding="utf-8")
    assert "Result: ACCEPTED" in led_text
    assert "Prompt tokens: 100" in led_text
    assert "Output tokens: 50" in led_text
    assert "Model: g-one (gemini)" in led_text
