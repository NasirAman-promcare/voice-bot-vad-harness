"""FR-0.0-11 (amended): docs/baselines/harness_tests_baseline.md records command, environment and per-test
results for the provisioned harness environment (round 2), and keeps the round 1 baseline as history."""
import ast
import re

from aqis_testutil import ROOT

BASELINE = ROOT / "docs" / "baselines" / "harness_tests_baseline.md"
OUTCOMES = {"passed", "failed", "error", "skipped"}
ROUND2 = "Provisioned baseline (round 2)"
ROUND1 = "History (round 1)"


def top_sections():
    text = BASELINE.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    return {p.splitlines()[0].strip(): p for p in parts[1:]}


def sub_sections(section_text):
    parts = re.split(r"^### ", section_text, flags=re.M)
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


def result_rows(section_text):
    rows = {}
    for line in sub_sections(section_text)["Results"].splitlines():
        m = re.fullmatch(r"\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|", line.strip())
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_FR_0_0_11_baseline_records_command_and_environment():
    tops = top_sections()
    assert ROUND2 in tops and ROUND1 in tops, sorted(tops)
    assert list(tops).index(ROUND2) < list(tops).index(ROUND1)
    for title in (ROUND2, ROUND1):
        subs = sub_sections(tops[title])
        for name in ("Command", "Environment", "Results"):
            assert name in subs, f"'### {name}' missing under '## {title}'"
        assert "-m pytest tests/regression" in subs["Command"]
        assert "git status --porcelain --ignored" in subs["Command"]
        env = subs["Environment"]
        assert re.search(r"Python: `3\.\d+\.\d+", env)
        assert "uv pip freeze" in env and re.search(r"^pytest==\S+$", env, re.M)
        assert re.search(r"Commit tested: `[0-9a-f]{40}`", tops[title])
    round2 = tops[ROUND2]
    assert "bash aqis_lab/deploy/harness_provision.sh" in sub_sections(round2)["Command"]
    assert re.search(r"^ten[-_]vad @ git\+https://github\.com/TEN-framework/ten-vad\.git@22a3bcd4509d0faaa8eef4881e8af5f39c178950$",
                     sub_sections(round2)["Environment"], re.M)


def test_FR_0_0_11_baseline_lists_every_harness_test():
    expected = harness_test_functions()
    assert expected, "no harness tests found"
    tops = top_sections()
    for title in (ROUND2, ROUND1):
        rows = result_rows(tops[title])
        listed = {re.sub(r"\[.*\]$", "", node) for node in rows}
        assert listed == expected, f"{title}: missing {sorted(expected - listed)}, unknown {sorted(listed - expected)}"
        assert set(rows.values()) <= OUTCOMES
        counts = {o: sum(1 for v in rows.values() if v == o) for o in OUTCOMES}
        assert (f"**{len(rows)} tests: {counts['passed']} passed, {counts['failed']} failed, "
                f"{counts['error']} errors, {counts['skipped']} skipped**") in tops[title]
        failures = sub_sections(tops[title]).get("Failures (recorded, not fixed)", "")
        for node, outcome in rows.items():
            if outcome in ("failed", "error"):
                assert f"#### `{node}`" in failures, f"{title}: failure detail missing for {node}"
