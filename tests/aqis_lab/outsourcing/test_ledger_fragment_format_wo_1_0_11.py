"""Claude's fix for WO-1.0-11 B17 (FR-1.0-02, FR-1.0-04), written first: FIX-B17-ledger-row.

B17: the relay writes `docs/outsourcing/ledger.d/<WO>.md` as "the ledger row of `FRAGMENTS.md` with total requests,
tokens and the models used". The first relay-written fragment (WO-1.0-04, 2026-10-12) had YAML front matter, a heading
and no `WO`, `Date`, `Model version`, `Attempts` or `Seconds` line, so `python -m tools.progress lint` refused it with
`Missing required field: WO`.
"""
from __future__ import annotations

from pathlib import Path

from tools.outsourcing.ledger import write_ledger_fragment
from tools.outsourcing.records import RelayOutcome, Result, StepRecord
from tools.progress.fragments import load_all
from tools.progress.lint import lint

FRAGMENTS_ORDER = ["WO", "Date", "Model", "Model version", "Attempts", "Requests", "Prompt tokens", "Output tokens",
                   "Result", "Seconds"]


def record(label: str, attempts: int, model: str, version: str) -> StepRecord:
    return StepRecord(label=label, files=((f"{label}.py", "h"),), attempts=attempts, model=model, provider="nvidia",
                      model_version=version, prompt_tokens=10, output_tokens=5, seconds_waited=0.0)


def write(root: Path) -> Path:
    path = root / "docs/outsourcing/ledger.d/WO-2.1-01.md"
    outcome = RelayOutcome(result=Result.ACCEPTED, accepted_parts=(record("1", 2, "m-one", "v7"), record("2", 1, "m-two", "")))
    write_ledger_fragment(path, "WO-2.1-01", outcome, 4, 1234, 567, (("m-one", "nvidia"), ("m-two", "nvidia")),
                          date="2026-10-12", model_versions=("v7",), attempts=3, seconds=812)
    return path


def test_FR_1_0_02_fix_ledger_fragment_is_the_fragments_md_row(tmp_path):
    lines = write(tmp_path).read_text(encoding="utf-8").splitlines()
    assert lines == [
        "WO: WO-2.1-01", "Date: 2026-10-12", "Model: m-one (nvidia), m-two (nvidia)", "Model version: v7",
        "Attempts: 3", "Requests: 4", "Prompt tokens: 1234", "Output tokens: 567", "Result: ACCEPTED", "Seconds: 812"]
    assert [line.partition(":")[0] for line in lines] == FRAGMENTS_ORDER


def test_FR_1_0_02_fix_ledger_fragment_passes_progress_lint(tmp_path):
    write(tmp_path)
    fragments = load_all(tmp_path)
    assert [f.fields["WO"] for f in fragments.ledger] == ["WO-2.1-01"]
    assert lint(fragments) == []


def test_FR_1_0_02_fix_ledger_without_a_model_version_says_so(tmp_path):
    path = tmp_path / "WO-2.1-02.md"
    write_ledger_fragment(path, "WO-2.1-02", RelayOutcome(result=Result.EXHAUSTED), 0, 0, 0, (),
                          date="2026-10-12", model_versions=(), attempts=0, seconds=3)
    text = path.read_text(encoding="utf-8")
    assert "Model: none\n" in text and "Model version: not reported\n" in text and "Result: EXHAUSTED\n" in text
