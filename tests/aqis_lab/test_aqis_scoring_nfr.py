"""NFR-0.3-01: scoring is deterministic and uses no network access."""
import ast
import csv
import json
import os
import random
import subprocess
import sys
import warnings
from pathlib import Path

from aqis_scoring_testutil import HYP_FIXTURE, REF_FIXTURE, run_score, write_csv
from aqis_testutil import ROOT

OUTPUTS = ("scores.parquet", "scores.csv", "summary.json")
NETWORK_MODULES = {"socket", "ssl", "urllib", "http", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
                   "xmlrpc", "requests", "httpx", "urllib3", "aiohttp", "websocket", "websockets"}


def _shuffled_copy(path, dest, seed):
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    body = rows[1:]
    random.Random(seed).shuffle(body)
    assert body != rows[1:]
    return write_csv(dest, rows[0], body)


def test_NFR_0_3_01_repeat_runs_give_identical_files(tmp_path):
    first = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", tmp_path / "a",
                      env={**os.environ, "PYTHONHASHSEED": "1"})
    ref = _shuffled_copy(REF_FIXTURE, tmp_path / "ref.csv", 7)
    hyp = _shuffled_copy(HYP_FIXTURE, tmp_path / "hyp.csv", 8)
    second = run_score("--ref", ref, "--hyp", hyp, "--out", tmp_path / "b",
                       env={**os.environ, "PYTHONHASHSEED": "4242", "LC_ALL": "C", "TZ": "Pacific/Kiritimati"})
    assert first.returncode == 0 and second.returncode == 0, first.stderr + second.stderr
    for name in OUTPUTS:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
    # The printed report is the same apart from the output folder named on its last line.
    assert first.stdout.splitlines()[:-1] == second.stdout.splitlines()[:-1]


NO_NETWORK_RUNNER = r"""
import json, socket, sys
events = []
def hook(event, args):
    if event.startswith(("socket.", "urllib.", "http.", "ssl.")):
        events.append(event)
sys.addaudithook(hook)
from aqis_lab.__main__ import main
code = main(["score", *sys.argv[1:]])
during = list(events)
socket.getaddrinfo("localhost", 80)  # control: proves the hook sees socket use in this process
print(json.dumps({"code": code, "during": during, "control": events[len(during):]}), file=sys.stderr)
"""


def test_NFR_0_3_01_no_network_during_scoring(tmp_path):
    proc = subprocess.run([sys.executable, "-c", NO_NETWORK_RUNNER, "--ref", str(REF_FIXTURE), "--hyp",
                           str(HYP_FIXTURE), "--out", str(tmp_path / "out")], cwd=ROOT, capture_output=True,
                          text=True, timeout=300)
    result = json.loads(proc.stderr.strip().splitlines()[-1])
    assert result["code"] == 0, proc.stderr
    assert result["during"] == []
    assert "socket.getaddrinfo" in result["control"]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(OUTPUTS)


def _imported_top_modules(path):
    with warnings.catch_warnings():
        # whisper-normalizer 0.1.1 basic.py has an invalid escape in a docstring (plan risk 3).
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_NFR_0_3_01_scoring_code_imports_no_network_modules():
    import whisper_normalizer
    ours = sorted((ROOT / "aqis_lab" / "scoring").glob("*.py")) + [ROOT / "aqis_lab" / "commands" / "score.py"]
    assert len(ours) == 5
    package = Path(whisper_normalizer.__file__).parent
    # The Whisper code the normaliser runs (english.py imports basic.py only).
    theirs = [package / "english.py", package / "basic.py"]
    for path in ours + theirs:
        found = _imported_top_modules(path) & NETWORK_MODULES
        assert not found, (str(path), found)
