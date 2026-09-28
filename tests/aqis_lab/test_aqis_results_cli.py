"""FR-0.6-02: `python -m aqis_lab results add` and `results query --run-card <id>` on real runner and scorer output."""
import json
import subprocess
import sys

import pytest

from aqis_results_testutil import copy_tree, expected_row_id, run_rows, score_folder, smoke_run
from aqis_testutil import ROOT


def cli(*args):
    return subprocess.run([sys.executable, "-m", "aqis_lab", *map(str, args)], cwd=ROOT, capture_output=True,
                          text=True, timeout=300)


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    base = tmp_path_factory.mktemp("cli")
    return smoke_run(base / "run", base / "work")


def card_id(run_dir):
    return json.loads((run_dir / "run_card.json").read_text(encoding="utf-8"))["run_card_id"]


def test_FR_0_6_02_results_listed_by_dispatcher():
    proc = cli("--help")
    assert proc.returncode == 0 and "results" in proc.stdout and "query the append-only results store" in proc.stdout


def test_FR_0_6_02_query_returns_rows_for_run_card(tmp_path, run_dir):
    store_dir = tmp_path / "store"
    added = cli("results", "add", "--run", run_dir, "--store", store_dir)
    assert added.returncode == 0, added.stderr
    assert f"stored 60 row(s) for run card {card_id(run_dir)}" in added.stdout
    scores = score_folder(tmp_path / "scores", card_id(run_dir))
    added = cli("results", "add", "--scores", scores, "--store", store_dir)
    assert added.returncode == 0 and "stored 6 row(s)" in added.stdout, added.stderr
    proc = cli("results", "query", "--run-card", card_id(run_dir), "--store", store_dir)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    got = [json.loads(line) for line in lines]
    assert all(line == json.dumps(g, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
               for line, g in zip(lines, got))
    assert len(got) == 66
    assert [(g["kind"], g["clip_id"], g["result_row_id"]) for g in got] == \
        sorted((g["kind"], g["clip_id"], g["result_row_id"]) for g in got)
    runs = [g for g in got if g["kind"] == "run-result"]
    assert sorted((g["row"] for g in runs), key=lambda r: r["clip_id"]) == \
        sorted(run_rows(run_dir), key=lambda r: r["clip_id"])
    for g in runs:
        assert g["result_row_id"] == expected_row_id(g["identity"]) and g["run_card_id"] == card_id(run_dir)
    assert sum(g["kind"] == "score" for g in got) == 6
    assert set(got[0]) == {"result_row_id", "kind", "run_card_id", "clip_id", "identity", "row", "row_sha256",
                           "source_file", "source_sha256", "added_utc", "added_by"}


def test_FR_0_6_02_query_unknown_run_card_exit_1(tmp_path, run_dir):
    store_dir = tmp_path / "store"
    assert cli("results", "add", "--run", run_dir, "--store", store_dir).returncode == 0
    proc = cli("results", "query", "--run-card", "c" * 64, "--store", store_dir)
    assert proc.returncode == 1 and proc.stdout == ""
    assert proc.stderr.startswith("ERROR:") and "c" * 64 in proc.stderr and "no rows" in proc.stderr


@pytest.mark.parametrize("value", ["ABC", "a" * 63, "g" * 64, "a" * 65])
def test_FR_0_6_02_query_rejects_malformed_id(tmp_path, run_dir, value):
    store_dir = tmp_path / "store"
    assert cli("results", "add", "--run", run_dir, "--store", store_dir).returncode == 0
    proc = cli("results", "query", "--run-card", value, "--store", store_dir)
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:") and "64 lowercase" in proc.stderr


def test_FR_0_6_02_query_missing_store_exit_2(tmp_path):
    proc = cli("results", "query", "--run-card", "a" * 64, "--store", tmp_path / "nothing")
    assert proc.returncode == 2 and "no results store" in proc.stderr


def test_FR_0_6_02_add_exit_codes(tmp_path, run_dir):
    store_dir = tmp_path / "store"
    assert cli("results", "add", "--run", run_dir, "--store", store_dir).returncode == 0
    again = cli("results", "add", "--run", run_dir, "--store", store_dir)
    assert again.returncode == 0 and "stored 0 row(s)" in again.stdout and "60 already stored" in again.stdout
    changed = copy_tree(run_dir, tmp_path / "changed")
    rows = run_rows(changed)
    rows[0]["peak_abs"] += 1
    (changed / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    conflict = cli("results", "add", "--run", changed, "--store", store_dir)
    assert conflict.returncode == 1 and conflict.stderr.startswith("ERROR:") and "conflict" in conflict.stderr
    missing = cli("results", "add", "--run", tmp_path / "nothing", "--store", store_dir)
    assert missing.returncode == 2 and missing.stderr.startswith("ERROR:")
    both = cli("results", "add", "--run", run_dir, "--scores", run_dir, "--store", store_dir)
    assert both.returncode == 2


def test_FR_0_6_02_add_and_query_exit_promptly(tmp_path, run_dir):
    # With pyarrow 25.0.1, a process that read Parquet with threads hung at exit about 4 times in 10 on the cloud
    # VM (EVIDENCE.md, "pyarrow exit hang"). Ten conflicting adds and ten queries must each exit within 60 s.
    store_dir = tmp_path / "store"
    assert cli("results", "add", "--run", run_dir, "--store", store_dir).returncode == 0
    changed = copy_tree(run_dir, tmp_path / "changed")
    rows = run_rows(changed)
    rows[1]["peak_abs"] += 1
    (changed / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for _ in range(10):
        proc = subprocess.run([sys.executable, "-m", "aqis_lab", "results", "add", "--run", str(changed), "--store",
                               str(store_dir)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 1
        proc = subprocess.run([sys.executable, "-m", "aqis_lab", "results", "query", "--run-card", card_id(run_dir),
                               "--store", str(store_dir)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0
