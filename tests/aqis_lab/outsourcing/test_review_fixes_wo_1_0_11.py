"""Claude's review fixes for WO-1.0-11 (FR-1.0-02), written before the fixes.

- B8 and B1: the step runner and the final verification passed the request's character count to `Router.choose`,
  whose `input_estimate` is in tokens. On the first real run (WO-1.0-04, 297,915 characters, about 85,000 tokens)
  every model's input-token ceiling looked too small and the relay exited 13 without sending anything.
"""
from __future__ import annotations

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_11 import (  # noqa: F401  (scratch and stand are fixtures)
    ORDER_REL, model, scratch, stand, write_pool)


def test_FR_1_0_02_router_gets_a_token_estimate_not_characters(scratch, stand):
    request_chars = sum(len((scratch.root / rel).read_text(encoding="utf-8")) for rel in (
        "docs/process/outsourcing/FOUNDATION.md", "docs/process/outsourcing/templates/RETURN_FORMAT.md", ORDER_REL))
    ceiling = 6000  # between the request's tokens (characters / 3.5) and its characters
    assert request_chars / 3.5 + 1500 < ceiling < request_chars
    pool = write_pool(scratch.tmp / "pool-ceiling.json", {"g-one": model("gemini", 1, tpm_input=ceiling),
                                                          "m-one": model("mistral", 2, tpm_input=ceiling)})
    proc = scratch.run(stand.url, pool=pool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stand.generations()


def test_FR_1_0_02_report_shows_the_checks_that_really_ran(scratch, stand):
    # B18: the checks table comes from the checks the relay ran. A module without its header fails the headers check,
    # so the part's tests never run; the report must not show a tests result at all.
    from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_11 import STEPS
    stand.script["g-one"].append(("override", {STEPS[0][0]: "VALUE = 5\n"}))
    proc = scratch.run(stand.url, "--attempts", "1")
    assert proc.returncode == 8, proc.stdout + proc.stderr
    assert "headers: FAIL" in proc.stdout
    assert "tests: PASS" not in proc.stdout and "tests: FAIL" not in proc.stdout


def test_FR_1_0_02_too_large_report_gives_reason_and_advice(scratch, stand):
    pool = write_pool(scratch.tmp / "pool-small.json", {"g-one": model("gemini", 1, tpm_input=1000),
                                                        "m-one": model("mistral", 2, max_input_tokens=1000)})
    proc = scratch.run(stand.url, pool=pool)
    assert proc.returncode == 13, proc.stdout + proc.stderr
    assert "split this step" in proc.stdout and "1000" in proc.stdout


def test_FR_1_0_02_report_counts_requests_per_model(scratch, stand):
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    requests_line = next(line for line in proc.stdout.splitlines() if line.startswith("Requests:"))
    assert f"g-one: {len(stand.generations('g-one'))}" in requests_line
