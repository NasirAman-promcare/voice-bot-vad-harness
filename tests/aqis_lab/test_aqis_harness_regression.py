"""FR-0.0-11 (amended): tools/harness/regression_check.py fails when a test that passed in the provisioned
harness baseline fails, errors or disappears; it reports newly passing tests without failing."""
import subprocess
import sys

from aqis_testutil import ROOT

SECTION = "Provisioned baseline (round 2)"


def baseline(tmp_path, rows):
    lines = ["# Harness regression baseline", "", f"## {SECTION}", "", "### Results",
             "| Test | Outcome | Seconds |", "| --- | --- | --- |"]
    lines += [f"| `{node}` | {outcome} | 0.001 |" for node, outcome in rows.items()]
    lines += ["", "## History (round 1)", "", "### Results", "| Test | Outcome | Seconds |", "| --- | --- | --- |",
              "| `tests/regression/test_old.py::test_only_in_history` | passed | 0.001 |", ""]
    path = tmp_path / "baseline.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def junit(tmp_path, outcomes):
    cases = []
    for node, outcome in outcomes.items():
        path, name = node.split("::")
        classname = path[:-3].replace("/", ".")
        inner = {"passed": "", "failed": "<failure message='x'>x</failure>", "error": "<error message='x'>x</error>",
                 "skipped": "<skipped message='x'/>"}[outcome]
        cases.append(f'<testcase classname="{classname}" name="{name}" time="0.01">{inner}</testcase>')
    xml = f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{"".join(cases)}</testsuite></testsuites>'
    path = tmp_path / "junit.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def check(junit_path, baseline_path):
    return subprocess.run([sys.executable, "-B", "-m", "tools.harness.regression_check", "--junit", str(junit_path),
                           "--baseline", str(baseline_path)], cwd=ROOT, capture_output=True, text=True, timeout=60)


A = "tests/regression/test_a.py::test_one"
B = "tests/regression/test_b.py::test_two"
C = "tests/regression/test_c.py::test_three"


def test_FR_0_0_11_regression_check_flags_newly_failing_baseline_pass(tmp_path):
    base = baseline(tmp_path, {A: "passed", B: "failed", C: "passed"})
    proc = check(junit(tmp_path, {A: "failed", B: "failed", C: "error"}), base)
    assert proc.returncode == 1
    regressions = sorted(line for line in proc.stdout.splitlines() if line.startswith("REGRESSION: "))
    assert regressions == [f"REGRESSION: {A} (baseline passed, now failed)",
                           f"REGRESSION: {C} (baseline passed, now error)"]


def test_FR_0_0_11_regression_check_flags_newly_skipped_baseline_pass(tmp_path):
    # A skip hides a test that used to pass, so it counts as a regression (audit F13); a test that was already
    # skipped in the baseline and is still skipped is not one.
    base = baseline(tmp_path, {A: "passed", B: "skipped"})
    proc = check(junit(tmp_path, {A: "skipped", B: "skipped"}), base)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    regressions = [line for line in proc.stdout.splitlines() if line.startswith("REGRESSION: ")]
    assert regressions == [f"REGRESSION: {A} (baseline passed, now skipped)"]
    assert proc.stdout.splitlines()[-1] == "RESULT: FAIL"


def test_FR_0_0_11_regression_check_flags_missing_baseline_pass(tmp_path):
    base = baseline(tmp_path, {A: "passed", B: "passed"})
    proc = check(junit(tmp_path, {A: "passed"}), base)
    assert proc.returncode == 1
    assert f"REGRESSION: {B} (baseline passed, now missing)" in proc.stdout.splitlines()


def test_FR_0_0_11_regression_check_passes_same_or_better(tmp_path):
    base = baseline(tmp_path, {A: "passed", B: "failed"})
    proc = check(junit(tmp_path, {A: "passed", B: "passed", C: "passed"}), base)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"newly passing: {B}" in proc.stdout
    assert "tests/regression/test_old.py" not in proc.stdout          # only the round 2 section is the baseline


def test_FR_0_0_11_regression_check_rejects_unreadable_inputs(tmp_path):
    base = baseline(tmp_path, {A: "passed"})
    missing = check(tmp_path / "absent.xml", base)
    assert missing.returncode == 2 and missing.stderr.startswith("ERROR:")
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<testsuites><testsuite>", encoding="utf-8")
    assert check(bad_xml, base).returncode == 2
    no_section = tmp_path / "no_section.md"
    no_section.write_text("# Harness regression baseline\n\n## History (round 1)\n", encoding="utf-8")
    proc = check(junit(tmp_path, {A: "passed"}), no_section)
    assert proc.returncode == 2 and SECTION in proc.stderr


def test_FR_0_0_11_regression_check_accepts_repository_baseline(tmp_path):
    base = ROOT / "docs" / "baselines" / "harness_tests_baseline.md"
    text = base.read_text(encoding="utf-8").split(f"## {SECTION}", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in text.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("tests/regression/"):
            rows[cells[0]] = cells[1]
    assert len(rows) >= 22
    proc = check(junit(tmp_path, rows), base)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_FR_0_0_11_regression_check_rejects_table_without_readable_rows(tmp_path):
    # Audit F42: a Results table whose rows cannot be read is an input error, never an empty baseline that passes.
    text = (f"# Harness regression baseline\n\n## {SECTION}\n\n### Results\n| Test | Outcome | Seconds |\n| --- | --- | --- |\n"
            f"| {A} | PASSED | 0.001 |\n")
    path = tmp_path / "baseline.md"
    path.write_text(text, encoding="utf-8")
    proc = check(junit(tmp_path, {A: "failed"}), path)
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:") and "has no rows" in proc.stderr, proc.stdout
    assert "RESULT: PASS" not in proc.stdout


def repository_baseline_rows():
    """{node: outcome} of the provisioned baseline's Results table, read independently of the tool."""
    text = (ROOT / "docs" / "baselines" / "harness_tests_baseline.md").read_text(encoding="utf-8")
    section = text.split(f"## {SECTION}", 1)[1].split("\n## ", 1)[0]
    results = section.split("### Results", 1)[1].split("\n### ", 1)[0]
    rows = {}
    for line in results.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`tests/"):
            rows[cells[0].strip("`")] = cells[1]
    return rows


def test_FR_0_0_11_regression_check_reads_every_repository_baseline_row(tmp_path):
    # Audit F42: the real baseline is parsed row by row, so one baseline pass that now fails is reported.
    rows = repository_baseline_rows()
    passes = sorted(node for node, outcome in rows.items() if outcome == "passed")
    assert len(rows) == 22 and len(passes) == 21
    current = dict(rows)
    current[passes[0]] = "failed"
    proc = check(junit(tmp_path, current), ROOT / "docs" / "baselines" / "harness_tests_baseline.md")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"baseline: 22 tests, 21 passed; this run: 22 tests, 20 passed" in proc.stdout
    assert [l for l in proc.stdout.splitlines() if l.startswith("REGRESSION: ")] == [
        f"REGRESSION: {passes[0]} (baseline passed, now failed)"]
