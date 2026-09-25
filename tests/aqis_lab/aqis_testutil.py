"""Shared helpers for the AQIS lab tests (not a test module).

The helpers compute expected values independently of the code under test: the probe
parser and the lock parser here are separate from aqis_lab/deploy/dev_bootstrap.sh and
from tools/audit.
"""
import re
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
