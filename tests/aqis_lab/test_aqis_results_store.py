"""FR-0.6-02: the results store: append-only Parquet files partitioned by run_card_id, never overwritten, with a
documented schema and a DuckDB view. Inputs are real runner and scorer output; expected row IDs are computed here
from the documented definition, independently of aqis_lab.results.
"""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from aqis_lab import platform as lp
from aqis_lab.results import ingest, store, views
from aqis_results_testutil import (SMOKE_MANIFEST, copy_tree, expected_row_id, run_rows, score_folder, smoke_run)
from aqis_runner_testutil import drive_mountinfo_line, make_system_tree, stand_in_drive, tree_snapshot
from aqis_testutil import ROOT

DOC = ROOT / "docs" / "results" / "RESULTS_STORE.md"


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("runs")
    work = base / "work"
    return {"seed0": smoke_run(base / "seed0", work, seed=0), "seed1": smoke_run(base / "seed1", work, seed=1),
            "base": base}


def card_of(run_dir):
    return json.loads((run_dir / "run_card.json").read_text(encoding="utf-8"))


def stored_rows(partition):
    rows = []
    for part in sorted(partition.glob("part-*.parquet")):
        rows += pq.read_table(part, use_threads=False).to_pylist()
    return rows


def add_run(store_dir, run_dir):
    return store.add_batch(store_dir, ingest.from_run_folder(run_dir))


def test_FR_0_6_02_add_run_folder_writes_partition_by_run_card(tmp_path, runs):
    run_dir = runs["seed0"]
    card = card_of(run_dir)
    result = add_run(tmp_path / "store", run_dir)
    partition = tmp_path / "store" / f"run_card_id={card['run_card_id']}"
    assert result.stored == 60 and result.already == 0
    assert json.loads((tmp_path / "store" / "STORE.json").read_text()) == {"store_schema_version": "1.0"}
    assert (partition / "run_card.json").read_bytes() == (run_dir / "run_card.json").read_bytes()
    parts = sorted(partition.glob("part-*.parquet"))
    assert len(parts) == 1 and parts[0] == result.part
    assert parts[0].name == f"part-{hashlib.sha256(parts[0].read_bytes()).hexdigest()}.parquet"
    assert pq.read_metadata(parts[0]).metadata[b"aqis_results_store_schema_version"] == b"1.0"
    rows = stored_rows(partition)
    source = (run_dir / "results.jsonl").read_bytes()
    assert sorted(json.loads(r["row"])["clip_id"] for r in rows) == sorted(c["clip_id"] for c in SMOKE_MANIFEST["clips"])
    by_clip = {json.loads(r["row"])["clip_id"]: r for r in rows}
    for line in run_rows(run_dir):
        r = by_clip[line["clip_id"]]
        assert json.loads(r["row"]) == line
        identity = {"kind": "run-result", "run_card_id": card["run_card_id"], "clip_id": line["clip_id"],
                    "task": line["task"], "task_version": line["task_version"]}
        assert json.loads(r["identity"]) == identity
        assert r["result_row_id"] == expected_row_id(identity)
        assert r["row_sha256"] == hashlib.sha256(r["row"].encode("utf-8")).hexdigest()
        assert (r["kind"], r["run_card_id"], r["clip_id"]) == ("run-result", card["run_card_id"], line["clip_id"])
        assert r["source_file"] == "results.jsonl" and r["source_sha256"] == hashlib.sha256(source).hexdigest()
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", r["added_utc"])
        assert r["added_by"].startswith("aqis_lab ")


def test_FR_0_6_02_add_score_folder_rows(tmp_path, runs):
    card = card_of(runs["seed0"])
    scores = score_folder(tmp_path / "scores", card["run_card_id"])
    result = store.add_batch(tmp_path / "store", ingest.from_score_folder(scores, run_card=runs["seed0"] / "run_card.json"))
    assert result.stored == 6 and result.already == 0
    table = pq.read_table(scores / "scores.parquet", use_threads=False).to_pylist()
    rows = stored_rows(tmp_path / "store" / f"run_card_id={card['run_card_id']}")
    assert sorted(json.loads(r["row"])["clip_id"] + json.loads(r["row"])["variant"] for r in rows) == \
        sorted(s["clip_id"] + s["variant"] for s in table)
    for r in rows:
        src = json.loads(r["row"])
        assert src in table
        identity = {k: src[k] for k in ("run_card_id", "clip_id", "variant", "normaliser_name", "normaliser_version",
                                         "ref_sha256")}
        identity["kind"] = "score"
        assert r["kind"] == "score" and r["result_row_id"] == expected_row_id(identity)
        assert r["source_file"] == "scores.parquet"


def test_FR_0_6_02_refuses_to_overwrite_existing_rows(tmp_path, runs):
    # Must-catch 1: a row whose identity is stored with other content is refused, and nothing is written.
    store_dir = tmp_path / "store"
    add_run(store_dir, runs["seed0"])
    changed = copy_tree(runs["seed0"], tmp_path / "changed")
    lines = run_rows(changed)
    lines[7]["sum_squares"] += 1
    (changed / "results.jsonl").write_text("".join(json.dumps(l, sort_keys=True, separators=(",", ":")) + "\n"
                                               for l in lines), encoding="utf-8")
    before = tree_snapshot(store_dir)
    with pytest.raises(store.StoreConflictError) as info:
        add_run(store_dir, changed)
    identity = {"kind": "run-result", "run_card_id": lines[7]["run_card_id"], "clip_id": lines[7]["clip_id"],
                "task": "clip-stats", "task_version": lines[7]["task_version"]}
    assert expected_row_id(identity) in str(info.value) and "nothing was written" in str(info.value)
    assert tree_snapshot(store_dir) == before


def test_FR_0_6_02_existing_files_never_replaced(tmp_path, runs):
    # Must-catch 1: a stored file is never replaced, even by a writer that asks to.
    target = tmp_path / "part-x.parquet"
    store.publish(target, b"first")
    with pytest.raises(store.StoreConflictError) as info:
        store.publish(target, b"second")
    assert "refusing to replace" in str(info.value)
    assert target.read_bytes() == b"first" and not list(tmp_path.glob("*.partial"))
    # a stored run card with other bytes but the same ID is kept as it is
    store_dir = tmp_path / "store"
    add_run(store_dir, runs["seed0"])
    card_file = store_dir / f"run_card_id={card_of(runs['seed0'])['run_card_id']}" / "run_card.json"
    card = json.loads(card_file.read_text())
    card["notes"] = "kept"            # notes are not part of run_card_id
    os.chmod(card_file, 0o644)
    card_file.write_text(json.dumps(card), encoding="utf-8")
    kept = card_file.read_bytes()
    assert add_run(store_dir, runs["seed0"]).already == 60
    assert card_file.read_bytes() == kept


def test_FR_0_6_02_identical_rows_not_stored_twice(tmp_path, runs):
    store_dir = tmp_path / "store"
    card = card_of(runs["seed0"])
    add_run(store_dir, runs["seed0"])
    before = tree_snapshot(store_dir)
    again = add_run(store_dir, runs["seed0"])
    assert (again.stored, again.already, again.part) == (0, 60, None)
    assert tree_snapshot(store_dir) == before
    # a score set that repeats three clips and adds a fourth: the six repeated rows are reported, two are stored
    first = score_folder(tmp_path / "s3", card["run_card_id"], clip_count=3)
    second = score_folder(tmp_path / "s4", card["run_card_id"], clip_count=4)
    assert store.add_batch(store_dir, ingest.from_score_folder(first)).stored == 6
    mixed = store.add_batch(store_dir, ingest.from_score_folder(second))
    assert (mixed.stored, mixed.already) == (2, 6)


def test_FR_0_6_02_row_id_computed_from_identity():
    identity = {"kind": "run-result", "run_card_id": "a" * 64, "clip_id": "c-1", "task": "clip-stats",
                "task_version": "1.0"}
    assert store.result_row_id(identity) == expected_row_id(identity)
    assert store.result_row_id(dict(reversed(list(identity.items())))) == expected_row_id(identity)
    assert store.result_row_id({**identity, "clip_id": "c-2"}) != expected_row_id(identity)


@pytest.mark.parametrize("damage, words", [
    ("no_results", "results.jsonl"),
    ("missing_clip", "missing"),
    ("extra_clip", "not in the shard plan"),
    ("repeated_clip", "more than once"),
    ("bad_json", "line 5"),
    ("no_card", "run_card.json"),
    ("plan_of_other_card", "shard_plan.json"),
])
def test_FR_0_6_02_rejects_incomplete_run_folder(tmp_path, runs, damage, words):
    run_dir = copy_tree(runs["seed0"], tmp_path / "run")
    lines = (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    results = run_dir / "results.jsonl"
    if damage == "no_results":
        results.unlink()
    elif damage == "missing_clip":
        results.write_text("".join(lines[:-1]), encoding="utf-8")
    elif damage == "extra_clip":
        row = json.loads(lines[0])
        row["clip_id"] = "not-a-smoke-clip"
        results.write_text("".join(lines) + json.dumps(row) + "\n", encoding="utf-8")
    elif damage == "repeated_clip":
        results.write_text("".join(lines[:-1] + [lines[0]]), encoding="utf-8")
    elif damage == "bad_json":
        lines[4] = "{not json\n"
        results.write_text("".join(lines), encoding="utf-8")
    elif damage == "no_card":
        (run_dir / "run_card.json").unlink()
    else:
        plan = json.loads((run_dir / "shard_plan.json").read_text())
        plan["run_card_id"] = "b" * 64
        (run_dir / "shard_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(store.StoreInputError) as info:
        ingest.from_run_folder(run_dir)
    assert words in str(info.value)


def test_FR_0_6_02_rejects_rows_of_another_run_card(tmp_path, runs):
    run_dir = copy_tree(runs["seed0"], tmp_path / "run")
    lines = run_rows(run_dir)
    lines[2]["run_card_id"] = card_of(runs["seed1"])["run_card_id"]
    (run_dir / "results.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")
    with pytest.raises(store.StoreInputError) as info:
        ingest.from_run_folder(run_dir)
    assert "line 3" in str(info.value) and "run_card_id" in str(info.value)


def test_FR_0_6_02_score_rows_need_their_run_card(tmp_path, runs):
    card = card_of(runs["seed0"])
    scores = score_folder(tmp_path / "scores", card["run_card_id"])
    store_dir = tmp_path / "store"
    with pytest.raises(store.StoreInputError) as info:
        store.add_batch(store_dir, ingest.from_score_folder(scores))
    assert "is not in the store" in str(info.value) and "--run-card" in str(info.value)
    with pytest.raises(store.StoreInputError) as info:
        ingest.from_score_folder(scores, run_card=runs["seed1"] / "run_card.json")
    assert card["run_card_id"] in str(info.value)
    assert not store_dir.exists()
    add_run(store_dir, runs["seed0"])                      # the card is stored with its run rows
    assert store.add_batch(store_dir, ingest.from_score_folder(scores)).stored == 6
    tampered = copy_tree(scores, tmp_path / "tampered")
    (tampered / "scores.csv").write_text("changed\n", encoding="utf-8")
    with pytest.raises(store.StoreInputError) as info:
        ingest.from_score_folder(tampered)
    assert "summary.json" in str(info.value)


def test_FR_0_6_02_interrupted_add_leaves_no_row(tmp_path, runs):
    # A kill during an add leaves at most a .partial file: readers ignore it and the next add replaces it.
    store_dir = tmp_path / "store"
    card = card_of(runs["seed0"])
    add_run(store_dir, runs["seed1"])
    partition = store_dir / f"run_card_id={card['run_card_id']}"
    partition.mkdir()
    (partition / "run_card.json.partial").write_bytes(b"{torn")
    (partition / "part-0000.parquet.partial").write_bytes(b"PAR1 torn")
    assert views.query_run_card(store_dir, card["run_card_id"]) == []
    assert add_run(store_dir, runs["seed0"]).stored == 60
    assert not list(partition.glob("*.partial"))
    assert len(views.query_run_card(store_dir, card["run_card_id"])) == 60


def test_FR_0_6_02_concurrent_adds_are_serialised(tmp_path, runs):
    store_dir = tmp_path / "store"
    add_run(store_dir, runs["seed1"])
    with open(store_dir / ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = subprocess.Popen([sys.executable, "-m", "aqis_lab", "results", "add", "--run", str(runs["seed0"]),
                                 "--store", str(store_dir)], cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        time.sleep(1.0)
        partition = store_dir / f"run_card_id={card_of(runs['seed0'])['run_card_id']}"
        assert proc.poll() is None and not partition.exists()
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 0, err
    assert len(list(partition.glob("part-*.parquet"))) == 1


def test_FR_0_6_02_duckdb_view_equals_stored_files(tmp_path, runs):
    store_dir = tmp_path / "store"
    for key in ("seed0", "seed1"):
        add_run(store_dir, runs[key])
    card0 = card_of(runs["seed0"])
    store.add_batch(store_dir, ingest.from_score_folder(score_folder(tmp_path / "scores", card0["run_card_id"])))
    files = sorted(store_dir.glob("run_card_id=*/part-*.parquet"))
    expected = sorted((r for f in files for r in pq.read_table(f, use_threads=False).to_pylist()), key=lambda r: r["result_row_id"])
    con = views.connect(store_dir)
    got = con.sql("SELECT * FROM result_rows ORDER BY result_row_id").fetchall()
    cols = [d[0] for d in con.sql("SELECT * FROM result_rows").description]
    assert cols == list(store.COLUMN_NAMES)
    assert [dict(zip(cols, row)) for row in got] == expected
    joined = con.sql("SELECT result_row_id, pack_manifest_id, pack_version, pack_sha256, git_commit, git_dirty, "
                     "lock_file, lock_sha256, mode FROM results").fetchall()
    assert len(joined) == len(expected) == 60 + 60 + 6
    cards = {card_of(runs[k])["run_card_id"]: card_of(runs[k]) for k in ("seed0", "seed1")}
    run_card_of = {r["result_row_id"]: r["run_card_id"] for r in expected}
    for row_id, manifest_id, version, sha, commit, dirty, lock_file, lock_sha, mode in joined:
        c = cards[run_card_of[row_id]]
        assert (manifest_id, version, sha) == (c["pack"]["manifest_id"], c["pack"]["version"], c["pack"]["sha256"])
        assert (commit, dirty, lock_file, lock_sha, mode) == (c["git"]["commit"], c["git"]["dirty"],
                                                              c["lock"]["file"], c["lock"]["sha256"], c["mode"])
    cards_view = dict(con.sql("SELECT run_card_id, card_json FROM run_cards").fetchall())
    assert {k: json.loads(v) for k, v in cards_view.items()} == cards


def test_FR_0_6_02_schema_documented_equals_code():
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## Columns", 1)[1].split("\n## ", 1)[0]
    documented = [m.group(1) for m in re.finditer(r"^\| `([a-z_0-9]+)` \|", section, re.M)]
    assert documented == list(store.COLUMN_NAMES)
    for name, kind in store.COLUMNS:
        assert re.search(rf"^\| `{name}` \| `{kind}` \|", section, re.M), name
    assert "`aqis_results_store_schema_version`" in text and '"1.0"' in text


def test_FR_0_6_02_duckdb_needs_no_network(tmp_path, runs):
    store_dir = tmp_path / "store"
    add_run(store_dir, runs["seed0"])
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", NO_PROXY="", no_proxy="")
    script = ("import sys\nfrom aqis_lab.results import views\ncon = views.connect(sys.argv[1])\n"
              "print(con.sql(\"SELECT count(*) FROM results\").fetchone()[0])\n"
              "print(sorted(con.sql(\"SELECT extension_name, install_mode FROM duckdb_extensions() WHERE "
              "extension_name IN ('parquet', 'json')\").fetchall()))\n")
    proc = subprocess.run([sys.executable, "-c", script, str(store_dir)], cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == ["60", "[('json', 'STATICALLY_LINKED'), ('parquet', 'STATICALLY_LINKED')]"]
    assert list(home.iterdir()) == []


def test_FR_0_6_02_store_on_drive_refused(tmp_path, runs):
    mount = stand_in_drive(tmp_path)
    root = make_system_tree(tmp_path / "sys", mountinfo=drive_mountinfo_line(mount))
    view = lp.SystemView(root=root, environ={"PATH": str(root / "bin"), "CLAUDE_CODE_REMOTE": "true"},
                         path=str(root / "bin"))
    target = mount / "MyDrive" / "AQIS_LAB" / "results"
    before = tree_snapshot(mount)
    with pytest.raises(store.StoreInputError) as info:
        store.add_batch(target, ingest.from_run_folder(runs["seed0"]), system=view)
    assert "local disk" in str(info.value) and str(mount) in str(info.value)
    assert tree_snapshot(mount) == before


def test_FR_0_6_02_add_rejects_tampered_stored_rows(tmp_path, runs):
    # Audit finding WP-0.6-F02: a stored row whose content no longer matches its row_sha256, or a part file changed
    # in place, is an integrity error for `add`, never counted as "already stored".
    from aqis_results_testutil import part_file, rewrite_part

    def bump(rows):
        row = json.loads(rows[0]["row"])
        row["peak_abs"] += 1
        rows[0]["row"] = json.dumps(row, sort_keys=True, separators=(",", ":"))

    store_dir = tmp_path / "a"
    add_run(store_dir, runs["seed0"])
    rewrite_part(part_file(store_dir), bump, keep_name=False)
    with pytest.raises(store.StoreIntegrityError) as info:
        add_run(store_dir, runs["seed0"])
    assert "row_sha256 does not match the row" in str(info.value)

    store_dir = tmp_path / "b"
    add_run(store_dir, runs["seed0"])
    rewrite_part(part_file(store_dir), lambda rows: rows[0].update(added_by="someone else"), keep_name=True)
    with pytest.raises(store.StoreIntegrityError) as info:
        add_run(store_dir, runs["seed0"])
    assert "no longer matches the SHA-256 in its name" in str(info.value)
