"""FR-0.0-02: aqis_lab/deploy/dev_bootstrap.sh builds .venv on the Colab Python from the hashed lock.

Every test copies the real script into a throwaway tree (script, lock, probe), so the
repository's own .venv is never touched and each failure mode is exercised for real.
"""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from aqis_testutil import BOOTSTRAP, LOCK, PROBE, parse_lock, probe_python_major_minor

PROBE_REL = "docs/environment/colab_probe.txt"


def make_tree(tmp_path, probe_text=None, probe_is_dir=False, lock_text=None):
    tree = tmp_path / "tree"
    (tree / "aqis_lab" / "deploy").mkdir(parents=True)
    shutil.copy2(BOOTSTRAP, tree / "aqis_lab" / "deploy" / "dev_bootstrap.sh")
    (tree / "requirements" / "aqis_lab").mkdir(parents=True)
    (tree / "requirements" / "aqis_lab" / "phase0.txt").write_text(
        LOCK.read_text(encoding="utf-8") if lock_text is None else lock_text, encoding="utf-8")
    probe = tree / PROBE_REL
    probe.parent.mkdir(parents=True)
    if probe_is_dir:
        probe.mkdir()
    elif probe_text is not None:
        probe.write_text(probe_text, encoding="utf-8")
    return tree


def run(tree, env=None, timeout=900):
    return subprocess.run(["bash", str(tree / "aqis_lab" / "deploy" / "dev_bootstrap.sh")],
                          cwd=tree, capture_output=True, text=True, env=env, timeout=timeout)


def path_without_uv(tmp_path):
    """A PATH offering every tool on the current PATH except uv and uvx."""
    bindir = tmp_path / "bin-without-uv"
    bindir.mkdir()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        d = Path(directory)
        if not d.is_dir():
            continue
        for entry in d.iterdir():
            if entry.name in ("uv", "uvx") or (bindir / entry.name).exists():
                continue
            if entry.is_file() and os.access(entry, os.X_OK):
                (bindir / entry.name).symlink_to(entry.resolve())
    return str(bindir)


def snapshot(tree):
    out = {}
    for path in sorted(tree.rglob("*")):
        st = path.lstat()
        out[str(path.relative_to(tree))] = (st.st_mode, st.st_size, st.st_mtime_ns)
    return out


def test_FR_0_0_02_fails_when_probe_missing(tmp_path):
    tree = make_tree(tmp_path)
    proc = run(tree)
    assert proc.returncode != 0
    assert "ERROR" in proc.stderr and PROBE_REL in proc.stderr and "missing" in proc.stderr.lower()
    assert not (tree / ".venv").exists()


@pytest.mark.parametrize("case", ["directory", "no_version_line", "conflicting_versions"])
def test_FR_0_0_02_fails_when_probe_unreadable(tmp_path, case):
    if case == "directory":
        tree = make_tree(tmp_path, probe_is_dir=True)
    elif case == "no_version_line":
        tree = make_tree(tmp_path, probe_text="--- COLAB ENVIRONMENT PROBE ---\nGPU Device Name: Tesla T4\n")
    else:
        tree = make_tree(tmp_path, probe_text="Python Version: 3.13.15\nPython 3.12.2\n")
    proc = run(tree)
    assert proc.returncode != 0
    assert "ERROR" in proc.stderr and PROBE_REL in proc.stderr
    assert not (tree / ".venv").exists()


def test_FR_0_0_02_fails_when_uv_missing(tmp_path):
    tree = make_tree(tmp_path, probe_text=PROBE.read_text(encoding="utf-8"))
    env = dict(os.environ, PATH=path_without_uv(tmp_path))
    proc = run(tree, env=env)
    assert proc.returncode != 0
    assert "ERROR" in proc.stderr and "uv" in proc.stderr and "not found" in proc.stderr
    assert not (tree / ".venv").exists()


def test_FR_0_0_02_uses_version_named_by_probe(tmp_path):
    # WP-0.0-F01: the version must come from the probe; a version that cannot exist proves it is used.
    tree = make_tree(tmp_path, probe_text="--- COLAB ENVIRONMENT PROBE ---\nPython Version: 3.99.1 (main)\n")
    proc = run(tree, timeout=120)
    assert proc.returncode != 0
    assert "Colab probe requires Python 3.99" in proc.stdout
    assert "ERROR:" in proc.stderr and "Python 3.99" in proc.stderr
    assert not (tree / ".venv").exists()


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_0_02_creates_venv_with_probe_python(tmp_path):
    tree = make_tree(tmp_path, probe_text=PROBE.read_text(encoding="utf-8"))
    proc = run(tree)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    python = tree / ".venv" / "bin" / "python"
    version = subprocess.run([str(python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                             capture_output=True, text=True, check=True).stdout.strip()
    assert version == probe_python_major_minor()
    pins = parse_lock()
    got = subprocess.run([str(python), "-c",
                          "import importlib.metadata as m; print(m.version('pytest'), m.version('jsonschema'))"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert got == [pins["pytest"]["version"], pins["jsonschema"]["version"]]


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_0_02_second_run_changes_nothing_within_30s(tmp_path):
    tree = make_tree(tmp_path, probe_text=PROBE.read_text(encoding="utf-8"))
    first = run(tree)
    assert first.returncode == 0, first.stdout + first.stderr
    before = snapshot(tree)
    start = time.monotonic()
    second = run(tree)
    elapsed = time.monotonic() - start
    assert second.returncode == 0, second.stdout + second.stderr
    assert elapsed < 30, f"second run took {elapsed:.1f} s"
    assert snapshot(tree) == before


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_0_02_rejects_lock_with_wrong_hash(tmp_path):
    text = LOCK.read_text(encoding="utf-8")
    block = re.search(r"^pytest==.*?(?=^\S)", text, re.M | re.S).group(0)
    broken = re.sub(r"sha256:[0-9a-f]{64}", "sha256:" + "0" * 64, block)
    tree = make_tree(tmp_path, probe_text=PROBE.read_text(encoding="utf-8"), lock_text=text.replace(block, broken))
    proc = run(tree)
    assert proc.returncode != 0
    assert "hash" in (proc.stdout + proc.stderr).lower()
