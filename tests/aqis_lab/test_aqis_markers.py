"""FR-0.0-04: lab tests are discovered from tests/aqis_lab/ with five registered markers,
without changing how the existing harness tests are discovered or run."""
import configparser
import os
import re
import subprocess
import sys

from aqis_testutil import LAB_MARKERS, ROOT

LAB_DIR = ROOT / "tests" / "aqis_lab"


def pytest_run(*args):
    # PYTHONDONTWRITEBYTECODE: collecting harness modules must not leave __pycache__ in guarded folders (F05).
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=600,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))


def harness_lines(output):
    """Collected node IDs and collection errors that concern harness tests, order-independent."""
    lines = set()
    for line in output.splitlines():
        line = line.strip()
        if re.fullmatch(r"tests/regression/\S+\.py::\S.*", line) or re.fullmatch(r"ERROR tests/regression/\S+\.py(?: - .*)?", line):
            lines.add(line)
    return lines


def test_FR_0_0_04_all_five_markers_registered():
    proc = pytest_run("--markers", "tests/aqis_lab")
    assert proc.returncode == 0, proc.stderr
    for name in LAB_MARKERS:
        assert f"@pytest.mark.{name}:" in proc.stdout, f"marker {name} not registered"


def test_FR_0_0_04_lab_tests_use_only_registered_markers():
    proc = pytest_run("--collect-only", "-q", "--strict-markers", "tests/aqis_lab")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert "tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_all_five_markers_registered" in proc.stdout


def test_FR_0_0_04_harness_collection_unchanged():
    """Harness discovery is the same with and without the lab tests in the same pytest session.

    What it can detect: lab files (conftest, root config, name clashes) changing which harness files are
    collected or how their collection ends. What it cannot detect here: in the lab .venv most harness modules
    fail to import (numpy and similar are not in the lab lock), so it mostly compares collection errors. The
    run-time proof is recorded in EVIDENCE.md: harness and lab tests run together in .venv-harness give the
    same harness outcomes as the harness alone (22 of 22), and CI job harness-regression runs the harness
    tests against the baseline on every push (audit finding WP-0.0-F05).
    """
    alone = pytest_run("--collect-only", "-q", "tests/regression")
    together = pytest_run("--collect-only", "-q", "tests/regression", "tests/aqis_lab")
    alone_lines = harness_lines(alone.stdout)
    assert alone_lines, "harness collection produced nothing to compare"
    assert harness_lines(together.stdout) == alone_lines
    # Every harness test file is still reached by discovery (collected or reported).
    files = {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests" / "regression").glob("test_*.py")}
    reached = {line.split("::")[0].replace("ERROR ", "").split(" ")[0] for line in alone_lines}
    assert files == reached


def test_FR_0_0_04_no_pytest_config_outside_lab():
    for directory in (ROOT, ROOT / "tests", ROOT / "tests" / "regression"):
        assert not (directory / "pytest.ini").exists(), directory
        assert not (directory / ".pytest.ini").exists(), directory
        assert not (directory / "conftest.py").exists(), directory
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            assert "[tool.pytest" not in pyproject.read_text(encoding="utf-8"), pyproject
        for name, section in (("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
            cfg = directory / name
            if cfg.exists():
                parser = configparser.ConfigParser()
                parser.read(cfg, encoding="utf-8")
                assert not parser.has_section(section), cfg
    assert not (LAB_DIR / "__init__.py").exists(), "an __init__.py here would shadow the aqis_lab package"


def test_FR_0_0_04_no_test_basename_collisions():
    lab = {p.name for p in LAB_DIR.rglob("*.py") if "fixtures" not in p.relative_to(LAB_DIR).parts}
    others = {p.name for p in (ROOT / "tests").rglob("*.py") if LAB_DIR not in p.parents}
    clashes = sorted((lab & others) - {"__init__.py"})
    assert not clashes, f"lab and harness test modules share basenames: {clashes}"
