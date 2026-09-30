"""The accepted debts WP-0.7 closes (docs/progress/DEBT.md).

DEBT-014 (NFR-0.5-02): `score`, `pack build`, `registry build` and `registry fetch` refuse to write on Google Drive
outside MyDrive/AQIS_LAB, like every WP-0.5 writer. Google Drive is the WP-0.5 test double: a local folder with a
generated fuse.drive mountinfo line, seen by the lab as the real system (aqis_lab.platform.SystemView.real). Each
command gets inputs it can really process, so without the guard it would write to Drive; with it, it prints
`ERROR:`, exits 2 and leaves Drive unchanged. The same command with a folder inside AQIS_LAB succeeds.

DEBT-015 items 2 to 4 (WP-0.6-F04): `sync` shows rclone's own message when listing the remote fails for another
reason than a missing folder; an rclone copy that runs past the time limit is `ERROR:` and exit 1; and STORE.json is
created only under the store lock, so simultaneous first adds to a new store all succeed. rclone is real, with the
WP-0.6 Drive test double (an rclone `alias` remote configured through environment variables).

DEBT-013 (NFR-0.5-01): the runner's overhead against a direct loop is under 5 % on a real workload, Vosk batch over
the smoke pack, measured as WP-0.5 measured it (same process, same staged pack, byte-identical results, medians of
alternating repetitions). It needs the real Vosk model (`network`) and takes several minutes (`slow`).
"""
import csv
import multiprocessing
import os
import shutil
import statistics
import subprocess
import time

import pytest

from aqis_lab import drive
from aqis_lab import platform as lp
from aqis_adapters_testutil import SESSION_MODEL_CACHE, drive_view, vosk_model
from aqis_packs_testutil import (librispeech_members, musan_members, serve, tar_gz, world_datasets, write_datasets,
                                 make_world, write_registry, write_spec)
from aqis_results_testutil import smoke_run, write_oracle_config
from aqis_runner_testutil import SMOKE_PACK, tree_snapshot


@pytest.fixture
def on_colab(tmp_path, monkeypatch):
    """(Drive mount, AQIS_LAB folder, a Drive folder outside AQIS_LAB) with the Drive double as the real system."""
    view, mount = drive_view(tmp_path)
    monkeypatch.setattr(lp.SystemView, "real", classmethod(lambda cls: view))
    drive.ensure_layout(mount, view)
    outside = mount / "MyDrive" / "Personal"
    outside.mkdir()
    (outside / "diary.txt").write_text("not the lab's\n", encoding="utf-8")
    return mount, drive.aqis_lab_folder(mount), outside


def _refused(capsys, code, mount, before):
    err = capsys.readouterr().err
    assert code == 2, err
    assert err.startswith("ERROR:") and "refusing to write" in err and "outside" in err and "AQIS_LAB" in err, err
    assert tree_snapshot(mount) == before, "the command wrote to Drive before refusing"


def _csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_NFR_0_5_02_score_refuses_drive_path_outside_aqis_lab(tmp_path, on_colab, capsys):
    from aqis_lab.commands import score
    mount, lab, outside = on_colab
    ref = _csv(tmp_path / "ref.csv", ["clip_id", "text"], [["c1", "the cat sat"], ["c2", "a dog ran"]])
    hyp = _csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [["a" * 64, "c1", "the cat sat"],
                                                                         ["a" * 64, "c2", "a dog"]])
    for out in (outside / "scores", mount / "MyDrive" / "scores", mount / "scores"):
        before = tree_snapshot(mount)
        _refused(capsys, score.main(["--ref", str(ref), "--hyp", str(hyp), "--out", str(out)]), mount, before)
    assert score.main(["--ref", str(ref), "--hyp", str(hyp), "--out", str(lab / "results" / "scores")]) == 0
    assert sorted(p.name for p in (lab / "results" / "scores").iterdir()) == ["scores.csv", "scores.parquet",
                                                                              "summary.json"]
    assert (outside / "diary.txt").read_text(encoding="utf-8") == "not the lab's\n"


def test_NFR_0_5_02_pack_build_refuses_drive_path_outside_aqis_lab(tmp_path, on_colab, capsys):
    from aqis_lab.commands import pack
    mount, lab, outside = on_colab
    world = make_world(tmp_path / "w")
    registry = write_registry(world)
    spec = write_spec(tmp_path / "spec.yaml")
    capsys.readouterr()                                # the set-up's own download log
    args = lambda out: ["build", str(spec), "--out", str(out), "--registry", str(registry), "--datasets",
                        str(world.datasets_path), "--cache", str(world.cache), "--repo-root", str(world.repo)]
    for out in (outside / "tpack", mount / "MyDrive" / "tpack"):
        before = tree_snapshot(mount)
        _refused(capsys, pack.main(args(out)), mount, before)
    assert pack.main(args(lab / "packs" / "tpack")) == 0
    assert (lab / "packs" / "tpack" / "manifest.json").is_file()


def test_NFR_0_5_02_registry_build_refuses_drive_path_outside_aqis_lab(tmp_path, on_colab, capsys):
    from aqis_lab.commands import registry
    mount, lab, outside = on_colab
    world = make_world(tmp_path / "w")
    capsys.readouterr()                                # the set-up's own download log
    args = lambda out: ["build", "--out", str(out), "--datasets", str(world.datasets_path), "--cache",
                        str(world.cache), "--repo-root", str(world.repo)]
    for out in (outside / "sources.csv", mount / "MyDrive" / "sources.csv"):
        before = tree_snapshot(mount)
        _refused(capsys, registry.main(args(out)), mount, before)
    assert registry.main(args(lab / "registry" / "sources.csv")) == 0
    assert (lab / "registry" / "sources.csv").is_file()


def test_NFR_0_5_02_registry_fetch_refuses_drive_cache_outside_aqis_lab(tmp_path, on_colab, capsys):
    from aqis_lab.commands import registry
    mount, lab, outside = on_colab
    repo = tmp_path / "repo"
    clean, _ = librispeech_members("test-clean", 4, 2, seed=1)
    other, _ = librispeech_members("test-other", 2, 2, seed=2)
    musan = musan_members()
    archives = {"ls/test-clean.tar.gz": tar_gz(clean), "ls/test-other.tar.gz": tar_gz(other),
                "musan.tar.gz": tar_gz(musan)}
    datasets = repo / "data" / "registry" / "datasets.yaml"
    with serve(archives) as server:
        write_datasets(datasets, world_datasets(server.base, archives, musan, tts=False))
        args = lambda cache: ["fetch", "librispeech-test-clean", "--cache", str(cache), "--datasets", str(datasets),
                              "--repo-root", str(repo)]
        for cache in (outside / "cache", mount / "MyDrive" / "cache"):
            before = tree_snapshot(mount)
            _refused(capsys, registry.main(args(cache)), mount, before)
        assert registry.main(args(lab / "cache")) == 0
    assert (lab / "cache" / "librispeech-test-clean").is_dir()


# --- DEBT-015 ---

REMOTE = "aqisdrive"


@pytest.fixture(scope="module")
def filled_store(tmp_path_factory):
    from aqis_lab.results import ingest, store
    base = tmp_path_factory.mktemp("debt015")
    store_dir = base / "store"
    store.add_batch(store_dir, ingest.from_run_folder(smoke_run(base / "run", base / "work")))
    return store_dir


def rclone_env(tmp_path, target):
    """Environment with only the alias remote REMOTE -> target (a folder, or another remote's path)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("RCLONE_")}
    env["RCLONE_CONFIG"] = str(tmp_path / "no-rclone.conf")
    env[f"RCLONE_CONFIG_{REMOTE.upper()}_TYPE"] = "alias"
    env[f"RCLONE_CONFIG_{REMOTE.upper()}_REMOTE"] = str(target)
    return env


def test_FR_0_6_05_failed_remote_listing_shows_rclone_message(tmp_path, filled_store):
    import sys
    from aqis_testutil import ROOT
    config = write_oracle_config(tmp_path / "oracle.yaml", [3], remote=REMOTE, results_store=str(filled_store))
    sync_cmd = lambda env: subprocess.run([sys.executable, "-m", "aqis_lab", "sync", "--config", str(config)],
                                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    # The remote exists but cannot be opened (as with an expired Drive sign-in): rclone's own message must be shown.
    env = rclone_env(tmp_path, "unconfigured-remote:somewhere")
    own = subprocess.run(["rclone", "lsf", f"{REMOTE}:AQIS_LAB", "--dirs-only"], env=env, capture_output=True,
                         text=True, timeout=120)
    assert own.returncode not in (0, 3)          # 3 is rclone's "directory not found"
    message = next(l for l in own.stderr.splitlines() if "NOTICE" not in l).split(" ", 2)[2]
    proc = sync_cmd(env)
    assert proc.returncode == 1 and proc.stderr.startswith("ERROR:"), proc.stderr
    assert message in proc.stderr and f"exit {own.returncode}" in proc.stderr
    assert "must already exist" not in proc.stderr and "never creates" not in proc.stderr
    # A really missing AQIS_LAB still gets the "create it first" guidance, now with rclone's message too.
    empty = tmp_path / "empty-drive"
    empty.mkdir()
    proc = sync_cmd(rclone_env(tmp_path, empty))
    assert proc.returncode == 2 and "never creates" in proc.stderr and "directory not found" in proc.stderr
    assert list(empty.iterdir()) == []


def test_FR_0_6_05_rclone_timeout_is_an_error(tmp_path, filled_store, monkeypatch, capsys):
    from aqis_lab import sync
    from aqis_lab.commands import sync as sync_command
    drive_dir = tmp_path / "drive"
    (drive_dir / "AQIS_LAB" / "results").mkdir(parents=True)
    # rclone itself, except that `copy` never finishes (the stand-in for a stalled Drive upload)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "rclone").write_text(f'#!/bin/sh\nif [ "$1" = copy ]; then exec sleep 60; fi\n'
                                   f'exec {shutil.which("rclone")} "$@"\n', encoding="utf-8")
    (bindir / "rclone").chmod(0o755)
    for key, value in rclone_env(tmp_path, drive_dir).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(sync, "TIMEOUT_S", 2)
    config = write_oracle_config(tmp_path / "oracle.yaml", [3], remote=REMOTE, results_store=str(filled_store))
    before = tree_snapshot(drive_dir)
    code = sync_command.main(["--config", str(config)])
    err = capsys.readouterr().err
    assert code == 1 and err.startswith("ERROR:") and "rclone copy did not finish within 2 s" in err, err
    assert tree_snapshot(drive_dir) == before


def _first_add(args):
    store_dir, run_dir, barrier = args
    from aqis_lab.results import ingest, store
    batch = ingest.from_run_folder(run_dir)
    barrier.wait()
    try:
        return "ok", store.add_batch(store_dir, batch).stored
    except Exception as exc:                  # the parent reports every failure with its type and message
        return "error", f"{type(exc).__name__}: {exc}"


def test_FR_0_6_02_simultaneous_first_adds_are_safe(tmp_path):
    from aqis_lab.results import ingest, store, views
    run_dir = smoke_run(tmp_path / "run", tmp_path / "work")
    rows = len(ingest.from_run_folder(run_dir).records)
    workers = 4
    ctx = multiprocessing.get_context("spawn")     # fork of this multi-threaded process could deadlock a child
    with ctx.Manager() as manager, ctx.Pool(workers) as pool:
        for round_no in range(12):
            store_dir = tmp_path / f"store-{round_no}"
            barrier = manager.Barrier(workers)
            outcomes = pool.map(_first_add, [(store_dir, run_dir, barrier)] * workers)
            assert [o for o in outcomes if o[0] != "ok"] == [], (round_no, outcomes)
            assert sum(stored for _, stored in outcomes) == rows, (round_no, outcomes)
            store.check_store(store_dir)
            assert len(views.query_run_card(store_dir, ingest.from_run_folder(run_dir).run_card_id)) == rows


# --- DEBT-013 ---

OVERHEAD_REPEATS = 3


@pytest.mark.slow
@pytest.mark.network
def test_NFR_0_5_01_runner_overhead_under_5_percent_on_vosk_batch(tmp_path):
    from aqis_lab.adapters.base import EventSink
    from aqis_lab.adapters.vosk_stt import VoskAdapter
    from aqis_lab.contracts.canonical import canonical_json
    from aqis_lab.packs.audio import read_wav
    from aqis_lab.runner.run import RunOptions, run
    from aqis_lab.runner.stage import stage_pack
    from aqis_lab.runner.tasks import TASKS
    vosk_model()                                     # the verified model in the session cache
    task = TASKS["vosk-batch"]
    work = tmp_path / "work"
    staged = stage_pack(SMOKE_PACK, work)
    options = lambda out: RunOptions(task=task.name, pack=SMOKE_PACK, out=out, seed=0, work_dir=work,
                                     model_cache=SESSION_MODEL_CACHE)
    reference = run(options(tmp_path / "reference"), echo=None)
    expected = (tmp_path / "reference" / "results.jsonl").read_bytes()

    def direct(i):
        # the same work without the runner: load the model, then every clip through the adapter, one results file
        adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
        adapter.open()
        sink = EventSink("run-direct", reference.run_card_id, "cloud-vm:direct")
        rows = []
        for clip in staged.manifest["clips"]:
            _, samples = read_wav(staged.read_clip(clip), where=f"clip {clip['clip_id']}")
            fields = adapter.process_clip(clip["clip_id"], samples, sink)
            rows.append(canonical_json({"clip_id": clip["clip_id"], "run_card_id": reference.run_card_id,
                                        "task": task.name, "task_version": task.version, **fields}) + b"\n")
        adapter.close()
        folder = tmp_path / f"direct-{i}"
        folder.mkdir()
        return drive.write_bytes(folder / "results.jsonl", b"".join(rows)).read_bytes()

    def runner(i):
        out = tmp_path / f"run-{i}"
        run(options(out), echo=None)
        return (out / "results.jsonl").read_bytes()

    times = {"direct": [], "runner": []}
    for i in range(OVERHEAD_REPEATS):
        for name, loop in (("direct", direct), ("runner", runner)):
            start = time.perf_counter_ns()
            assert loop(i) == expected, name          # like for like: the same result bytes
            times[name].append(time.perf_counter_ns() - start)
    direct_s = statistics.median(times["direct"]) / 1e9
    runner_s = statistics.median(times["runner"]) / 1e9
    overhead = (runner_s - direct_s) / direct_s
    print(f"NFR-0.5-01 on vosk-batch: direct median {direct_s:.2f} s, runner median {runner_s:.2f} s, overhead "
          f"{overhead * 100:.2f} % (limit 5 %); all times {times}")
    assert overhead < 0.05, (direct_s, runner_s, times)
