"""FR-0.6-03: `python -m aqis_lab trace <result-row-id>` prints the run card, pack manifest ID and version, clip, git
commit and lock hash for a stored row. Expected values are read here from the source run_card.json and result rows,
independently of aqis_lab.trace.
"""
import hashlib
import io
import json
import os
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aqis_lab.commands import trace as trace_cmd
from aqis_lab.contracts.canonical import compute_run_card_id
from aqis_lab.contracts.validate import validate_run_card
from aqis_lab.results import ingest, store
from aqis_results_testutil import canonical, expected_row_id, score_folder, smoke_run
from aqis_testutil import ROOT


@pytest.fixture(scope="module")
def filled(tmp_path_factory):
    base = tmp_path_factory.mktemp("trace")
    runs = {seed: smoke_run(base / f"seed{seed}", base / "work", seed=seed) for seed in (0, 1)}
    store_dir = base / "store"
    for run_dir in runs.values():
        store.add_batch(store_dir, ingest.from_run_folder(run_dir))
    card0 = json.loads((runs[0] / "run_card.json").read_text(encoding="utf-8"))
    store.add_batch(store_dir, ingest.from_score_folder(score_folder(base / "scores", card0["run_card_id"])))
    return {"runs": runs, "store": store_dir}


def all_rows(store_dir):
    return [r for f in sorted(store_dir.glob("run_card_id=*/part-*.parquet")) for r in pq.read_table(f, use_threads=False).to_pylist()]


def parse_trace(text):
    head, _, card_text = text.partition("run_card:\n")
    fields = dict(line.split(": ", 1) for line in head.splitlines())
    return fields, json.loads(card_text)


def run_trace(capsys, *args):
    code = trace_cmd.main([str(a) for a in args])
    out = capsys.readouterr()
    return code, out.out, out.err


def expected_fields(row, card):
    return {"result_row_id": row["result_row_id"], "kind": row["kind"], "clip_id": row["clip_id"],
            "run_card_id": card["run_card_id"], "pack_manifest_id": card["pack"]["manifest_id"],
            "pack_version": card["pack"]["version"], "pack_sha256": card["pack"]["sha256"],
            "git_commit": f"{card['git']['commit']} (dirty: {str(card['git']['dirty']).lower()})",
            "lock_file": card["lock"]["file"], "lock_sha256": card["lock"]["sha256"]}


def test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock(capsys, filled):
    # Must-catch 2: every stored row traces to exactly its run card, manifest version, clip, commit and lock hash.
    cards = {}
    for run_dir in filled["runs"].values():
        card = json.loads((run_dir / "run_card.json").read_text(encoding="utf-8"))
        cards[card["run_card_id"]] = card
    rows = all_rows(filled["store"])
    assert len(rows) == 126
    for row in rows:
        card = cards[json.loads(row["identity"])["run_card_id"]]
        code, out, err = run_trace(capsys, row["result_row_id"], "--store", filled["store"])
        assert code == 0, err
        fields, printed_card = parse_trace(out)
        assert fields == expected_fields(row, card)
        assert printed_card == card
        assert row["clip_id"] == json.loads(row["row"])["clip_id"]
    # the command line gives the same output
    row = rows[0]
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "trace", row["result_row_id"], "--store",
                           str(filled["store"])], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0 and parse_trace(proc.stdout)[0] == \
        expected_fields(row, cards[row["run_card_id"]])


def test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card(capsys, filled):
    # Must-catch 2: the same clip under two run cards (seeds 0 and 1) traces to each row's own card.
    cards = [json.loads((filled["runs"][s] / "run_card.json").read_text(encoding="utf-8")) for s in (0, 1)]
    assert cards[0]["run_card_id"] != cards[1]["run_card_id"]
    clip = json.loads((filled["runs"][0] / "results.jsonl").read_text().splitlines()[0])["clip_id"]
    for card in cards:
        identity = {"kind": "run-result", "run_card_id": card["run_card_id"], "clip_id": clip, "task": "clip-stats",
                    "task_version": card["model"]["version"]}
        code, out, err = run_trace(capsys, expected_row_id(identity), "--store", filled["store"])
        assert code == 0, err
        fields, printed = parse_trace(out)
        assert fields["run_card_id"] == card["run_card_id"] and printed["seed"] == card["seed"]
        assert printed == card


def test_FR_0_6_03_unknown_row_id_exit_1(capsys, filled):
    code, out, err = run_trace(capsys, "d" * 64, "--store", filled["store"])
    assert code == 1 and out == "" and err.startswith("ERROR:") and "d" * 64 in err and "not in" in err


@pytest.mark.parametrize("value", ["xyz", "D" * 64, "d" * 63])
def test_FR_0_6_03_malformed_row_id_exit_2(capsys, filled, value):
    code, out, err = run_trace(capsys, value, "--store", filled["store"])
    assert code == 2 and out == "" and "64 lowercase" in err


def test_FR_0_6_03_missing_store_exit_2(capsys, tmp_path):
    code, out, err = run_trace(capsys, "d" * 64, "--store", tmp_path / "nothing")
    assert code == 2 and "no results store" in err


def copy_store(filled, tmp_path):
    subprocess.run(["cp", "-a", str(filled["store"]), str(tmp_path / "store")], check=True)
    return tmp_path / "store"


def test_FR_0_6_03_changed_run_card_is_reported(capsys, filled, tmp_path):
    store_dir = copy_store(filled, tmp_path)
    row = all_rows(store_dir)[0]
    card_file = store_dir / f"run_card_id={row['run_card_id']}" / "run_card.json"
    card = json.loads(card_file.read_text(encoding="utf-8"))
    card["seed"] = card["seed"] + 7                  # run_card_id no longer matches the content
    os.chmod(card_file, 0o644)
    card_file.write_text(json.dumps(card), encoding="utf-8")
    code, out, err = run_trace(capsys, row["result_row_id"], "--store", store_dir)
    assert code == 1 and out == "" and "stored run card" in err and "damaged" in err
    card_file.unlink()
    code, out, err = run_trace(capsys, row["result_row_id"], "--store", store_dir)
    assert code == 1 and out == "" and "no stored run card" in err


def write_part(partition, rows):
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=store.arrow_schema()), buffer)
    data = buffer.getvalue()
    path = partition / f"part-{hashlib.sha256(data).hexdigest()}.parquet"
    path.write_bytes(data)
    return path


def test_FR_0_6_03_row_not_matching_its_id_is_reported(capsys, filled, tmp_path):
    store_dir = copy_store(filled, tmp_path)
    row = all_rows(store_dir)[0]
    partition = store_dir / f"run_card_id={row['run_card_id']}"
    bad = dict(row, identity=canonical({**json.loads(row["identity"]), "clip_id": "another-clip"}).decode())
    write_part(partition, [dict(bad, result_row_id="e" * 64)])
    code, out, err = run_trace(capsys, "e" * 64, "--store", store_dir)
    assert code == 1 and out == "" and "is not the SHA-256 of its identity" in err
    # the same row ID stored twice is reported, never resolved by picking one
    write_part(partition, [dict(row, added_utc="2026-09-28T00:00:00.000000Z")])
    code, out, err = run_trace(capsys, row["result_row_id"], "--store", store_dir)
    assert code == 1 and out == "" and "2 rows" in err


def git_out(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def historical_run(tmp_path, run_dir):
    """A copy of a real run whose card records an earlier commit of this repository and the lock as it was at that
    commit: the parent of the last commit that changed requirements/aqis_lab/phase0.txt (audit finding WP-0.6-F01)."""
    changed = git_out("log", "-1", "--format=%H", "--", "requirements/aqis_lab/phase0.txt").decode().strip()
    old = git_out("rev-parse", f"{changed}^").decode().strip()
    old_lock_sha = hashlib.sha256(git_out("show", f"{old}:requirements/aqis_lab/phase0.txt")).hexdigest()
    copy = tmp_path / "historical-run"
    subprocess.run(["cp", "-a", str(run_dir), str(copy)], check=True)
    card = json.loads((copy / "run_card.json").read_text(encoding="utf-8"))
    card["git"] = {"commit": old, "dirty": False}
    card["lock"]["sha256"] = old_lock_sha
    card["run_card_id"] = compute_run_card_id(card)
    validate_run_card(card)
    (copy / "run_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    plan = json.loads((copy / "shard_plan.json").read_text(encoding="utf-8"))
    plan["run_card_id"] = card["run_card_id"]
    (copy / "shard_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    rows = [dict(json.loads(line), run_card_id=card["run_card_id"])
            for line in (copy / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    (copy / "results.jsonl").write_text("".join(canonical(r).decode() + "\n" for r in rows), encoding="utf-8")
    return copy, card


def test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash(capsys, filled, tmp_path):
    # Must-catch 2 (audit finding WP-0.6-F01): the commit and lock hash come from the row's run card, never from the
    # checkout. The stored card names an earlier commit and that commit's lock, both unlike the checkout's.
    run_dir, card = historical_run(tmp_path, filled["runs"][0])
    head = git_out("rev-parse", "HEAD").decode().strip()
    current_lock = hashlib.sha256((ROOT / card["lock"]["file"]).read_bytes()).hexdigest()
    assert card["git"]["commit"] != head and card["lock"]["sha256"] != current_lock
    store_dir = tmp_path / "store"
    assert store.add_batch(store_dir, ingest.from_run_folder(run_dir)).stored == 60
    rows = all_rows(store_dir)
    assert len(rows) == 60
    for row in rows:
        code, out, err = run_trace(capsys, row["result_row_id"], "--store", store_dir)
        assert code == 0, err
        fields, printed = parse_trace(out)
        assert fields["git_commit"] == f"{card['git']['commit']} (dirty: false)"
        assert fields["lock_sha256"] == card["lock"]["sha256"]
        assert fields == expected_fields(row, card) and printed == card
