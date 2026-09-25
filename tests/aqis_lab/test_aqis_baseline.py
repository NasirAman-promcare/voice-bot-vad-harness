"""FR-0.0-11: docs/baselines/harness_tests_baseline.md records command, environment and per-test results."""
import ast
import re

from aqis_testutil import ROOT

BASELINE = ROOT / "docs" / "baselines" / "harness_tests_baseline.md"
OUTCOMES = {"passed", "failed", "error", "skipped"}


def sections():
    text = BASELINE.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    return {p.splitlines()[0].strip(): p for p in parts[1:]}


def harness_test_functions():
    """tests/regression/<file>.py::<function> for every test function, computed from source."""
    found = set()
    for path in sorted((ROOT / "tests" / "regression").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                found.add(f"{path.relative_to(ROOT).as_posix()}::{node.name}")
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                        found.add(f"{path.relative_to(ROOT).as_posix()}::{node.name}::{item.name}")
    return found


def result_rows():
    rows = {}
    for line in sections()["Results"].splitlines():
        m = re.fullmatch(r"\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|", line.strip())
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_FR_0_0_11_baseline_records_command_and_environment():
    s = sections()
    for name in ("Command", "Environment", "Results"):
        assert name in s, f"section '## {name}' missing"
    assert "python\" -m pytest tests/regression" in s["Command"] or "python -m pytest tests/regression" in s["Command"]
    assert "git status --porcelain --ignored" in s["Command"]
    env = s["Environment"]
    assert re.search(r"Python: `3\.\d+\.\d+", env)
    assert "uv pip freeze" in env and re.search(r"^pytest==\S+$", env, re.M)
    assert re.search(r"Commit tested: `[0-9a-f]{40}`", BASELINE.read_text(encoding="utf-8"))


def test_FR_0_0_11_baseline_lists_every_harness_test():
    rows = result_rows()
    expected = harness_test_functions()
    assert expected, "no harness tests found"
    listed = {re.sub(r"\[.*\]$", "", node) for node in rows}
    assert listed == expected, f"missing {sorted(expected - listed)}, unknown {sorted(listed - expected)}"
    assert set(rows.values()) <= OUTCOMES
    failed = [node for node, outcome in rows.items() if outcome in ("failed", "error")]
    text = BASELINE.read_text(encoding="utf-8")
    counts = {o: sum(1 for v in rows.values() if v == o) for o in OUTCOMES}
    assert f"**{len(rows)} tests: {counts['passed']} passed, {counts['failed']} failed, " \
           f"{counts['error']} errors, {counts['skipped']} skipped**" in text
    for node in failed:
        assert f"### `{node}`" in sections()["Failures (recorded, not fixed)"], f"failure detail missing for {node}"
