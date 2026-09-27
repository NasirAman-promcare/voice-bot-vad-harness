"""Shared helpers for the AQIS lab tests (not a test module).

The helpers compute expected values independently of the code under test: the probe
parser and the lock parser here are separate from aqis_lab/deploy/dev_bootstrap.sh and
from tools/audit.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "docs" / "environment" / "colab_probe.txt"
LOCK_DIR = ROOT / "requirements" / "aqis_lab"
LOCK = LOCK_DIR / "phase0.txt"
LOCK_IN = LOCK_DIR / "phase0.in"
BOOTSTRAP = ROOT / "aqis_lab" / "deploy" / "dev_bootstrap.sh"
FAST_MARKERS = "not slow and not gpu and not colab and not oracle and not network"
LAB_MARKERS = ("slow", "gpu", "colab", "oracle", "network")


def probe_python_major_minor(text=None):
    """Major.minor from the Colab probe, read the way a person would read it."""
    text = PROBE.read_text(encoding="utf-8") if text is None else text
    found = set()
    for line in text.splitlines():
        m = re.match(r"\s*(?:Python Version:\s*|Python\s+)(\d+)\.(\d+)", line)
        if m:
            found.add(f"{m.group(1)}.{m.group(2)}")
    assert len(found) == 1, f"expected exactly one Python version in the probe, found {sorted(found)}"
    return found.pop()


def parse_lock(text=None):
    """Return {normalised name: {"version", "marker", "hashes"}} from a pip-style hashed lock."""
    text = LOCK.read_text(encoding="utf-8") if text is None else text
    logical, current = [], ""
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            if current:
                logical.append(current)
                current = ""
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        current += line
        logical.append(current)
        current = ""
    if current:
        logical.append(current)
    entries = {}
    for item in logical:
        item = item.strip()
        if not item or item.startswith("-"):
            continue
        hashes = re.findall(r"--hash=(\w+):([0-9a-f]+)", item)
        spec = item.split("--hash=")[0].strip()
        req, _, marker = spec.partition(";")
        m = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s]+)", req.strip())
        assert m, f"lock line is not an exact pin: {item[:80]}"
        name = re.sub(r"[-_.]+", "-", m.group(1)).lower()
        entries[name] = {"version": m.group(2), "marker": marker.strip(), "hashes": hashes}
    return entries


def normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def hermetic_git_env(extra=None):
    """Environment for git in throwaway repositories: no user or system config, fixed identity.

    This keeps fixture repositories identical on the cloud VM (which signs commits globally)
    and on CI runners (which have no identity).
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "AQIS Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "AQIS Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    })
    if extra:
        env.update(extra)
    return env


def git(repo, *args, check=True):
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True,
                          text=True, env=hermetic_git_env(), timeout=120)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {repo}: {proc.stderr}")
    return proc.stdout


def pip_venv(path):
    """A throwaway virtual environment with pip, made with `uv venv --seed` like .venv-harness (owner decision BLK-006).

    `python -m venv` needs ensurepip, which Ubuntu's Python lacks unless the python3.X-venv package is installed
    (Colab). uv seeds pip from its cache or from the package index instead. Returns the environment's python.
    """
    uv = shutil.which("uv")
    assert uv, "uv is needed to create test environments (install uv 0.8.17, as dev_bootstrap.sh requires)"
    proc = subprocess.run([uv, "venv", "--seed", "--python", sys.executable, str(path)], capture_output=True,
                          text=True, timeout=600)
    assert proc.returncode == 0, f"uv venv --seed failed for {path}: {proc.stdout}{proc.stderr}"
    return Path(path) / "bin" / "python"
