"""FR-0.6-02: `python -m aqis_lab results add` and `results query --run-card <id>` on real runner and scorer output."""
import json
import shutil
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


def tampered_store(tmp_path, run_dir, how):
    """A store holding run_dir's rows, then damaged `how`; returns (store, the first stored row ID)."""
    from aqis_results_testutil import part_file, rewrite_part
    store_dir = tmp_path / "store"
    assert cli("results", "add", "--run", run_dir, "--store", store_dir).returncode == 0
    part = part_file(store_dir)

    def bump(rows):
        row = json.loads(rows[0]["row"])
        row["peak_abs"] += 1
        rows[0]["row"] = json.dumps(row, sort_keys=True, separators=(",", ":"))

    if how == "row-text":
        _, rows = rewrite_part(part, bump, keep_name=False)
    elif how == "file-in-place":
        _, rows = rewrite_part(part, lambda rows: rows[0].update(added_by="someone else"), keep_name=True)
    elif how == "truncated":
        import pyarrow.parquet as pq
        rows = pq.read_table(part, use_threads=False).to_pylist()
        data = part.read_bytes()
        part.chmod(0o644)
        part.write_bytes(data[: len(data) // 2])
    else:                                            # a copy of the card in another run card's folder
        import pyarrow.parquet as pq
        rows = pq.read_table(part, use_threads=False).to_pylist()
        other = store_dir / ("run_card_id=" + "f" * 64)
        other.mkdir()
        shutil.copy2(part.parent / "run_card.json", other / "run_card.json")
    return store_dir, rows[0]["result_row_id"]


@pytest.mark.parametrize("how, words", [
    ("row-text", "row_sha256 does not match the row"),
    ("file-in-place", "no longer matches the SHA-256 in its name"),
    ("truncated", "no longer matches the SHA-256 in its name"),
    ("card-copy", "not the folder's"),
])
def test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store(tmp_path, run_dir, how, words):
    # Audit findings WP-0.6-F02 and F03: every reader checks the stored files and rows; a damaged or hand-edited
    # store gives `ERROR:` and exit 1 from `results query`, `trace` and `results add`, never rows with exit 0.
    store_dir, row_id = tampered_store(tmp_path, run_dir, how)
    readers = [("results", "query", "--run-card", card_id(run_dir)), ("trace", row_id)]
    if how != "card-copy":
        readers.append(("results", "add", "--run", run_dir))
    for args in readers:
        proc = cli(*args, "--store", store_dir)
        assert proc.returncode == 1, (args, proc.stdout, proc.stderr)
        assert proc.stdout == "" and proc.stderr.startswith("ERROR:") and words in proc.stderr, (args, proc.stderr)
        assert "Traceback" not in proc.stderr
    if how == "card-copy":
        # `add` reads only the partition it writes to; the stray card elsewhere does not change what it stores
        proc = cli("results", "add", "--run", run_dir, "--store", store_dir)
        assert proc.returncode == 0 and "stored 0 row(s)" in proc.stdout and "nothing written" in proc.stdout
