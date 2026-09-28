"""FR-0.5-05: the resumable runner. Shards, atomic results with completion markers, resume and --from-scratch."""
import hashlib
import io
import re
import json
import subprocess
import sys
import wave
from array import array

import pytest

from aqis_lab import platform as lp
from aqis_lab.contracts.canonical import compute_run_card_id, sha256_canonical
from aqis_lab.contracts.validate import validate_run_card
from aqis_lab.runner import plan as planmod
from aqis_lab.runner import store
from aqis_lab.runner.run import RunInputError, RunOptions, run
from aqis_lab.runner.tasks import TASKS
from aqis_runner_testutil import SMOKE_PACK
from aqis_testutil import ROOT

MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
CLIP_IDS = [c["clip_id"] for c in MANIFEST["clips"]]


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    """One staged copy of the smoke pack shared by this module's runs (staging is tested in test_aqis_stage.py)."""
    return tmp_path_factory.mktemp("work")


def opts(out, work, **extra):
    base = dict(task="clip-stats", pack=SMOKE_PACK, out=out, seed=0, work_dir=work)
    base.update(extra)
    return RunOptions(**base)


def markers(out):
    return sorted(p.name for p in (out / "shards").glob("*.done.json"))


def log_of(out):
    return (out / "runner.log").read_text(encoding="utf-8")


def last_session(out):
    text = log_of(out)
    return text[text.rindex(" session "):]


def expected_shards(durations, ratio, minutes, clips=None):
    """Greedy packing written independently from the spec: close a shard before it would pass the limit."""
    limit, shards, current, work = minutes * 60, [], [], 0.0
    for i, d in enumerate(durations):
        w = d * ratio
        if current and (work + w > limit or (clips is not None and len(current) >= clips)):
            shards.append(current)
            current, work = [], 0.0
        current.append(i)
        work += w
    if current:
        shards.append(current)
    return shards


def test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work():
    assert planmod.DEFAULT_SHARD_MINUTES == 30
    durations = [600.0] * 10 + [2000.0, 100.0]
    got = planmod.plan_shards(durations, seconds_per_audio_second=1.0, shard_minutes=30)
    assert got == expected_shards(durations, 1.0, 30) == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9], [10], [11]]
    for shard in got:
        assert sum(durations[i] for i in shard) <= 1800 or len(shard) == 1
    task = TASKS["clip-stats"]
    smoke = [c["duration_s"] for c in MANIFEST["clips"]]
    assert planmod.plan_shards(smoke, task.seconds_per_audio_second, 30) == \
        expected_shards(smoke, task.seconds_per_audio_second, 30)


def test_FR_0_5_05_shard_size_is_configurable(tmp_path, work):
    run(opts(tmp_path / "a", work, shard_clips=10))
    plan = json.loads((tmp_path / "a" / store.PLAN).read_text(encoding="utf-8"))
    assert [s["clip_ids"] for s in plan["shards"]] == [CLIP_IDS[i:i + 10] for i in range(0, 60, 10)]
    assert plan["shard_clips"] == 10 and plan["shard_minutes"] == 30
    ratio = TASKS["clip-stats"].seconds_per_audio_second
    minutes = 60 * ratio / 60                         # one minute of audio per shard
    run(opts(tmp_path / "b", work, shard_minutes=minutes))
    plan_b = json.loads((tmp_path / "b" / store.PLAN).read_text(encoding="utf-8"))
    want = expected_shards([c["duration_s"] for c in MANIFEST["clips"]], ratio, minutes)
    assert [s["clip_ids"] for s in plan_b["shards"]] == [[CLIP_IDS[i] for i in s] for s in want]
    assert len(plan_b["shards"]) > 1
    assert (tmp_path / "a" / "results.jsonl").read_bytes() == (tmp_path / "b" / "results.jsonl").read_bytes()


def test_FR_0_5_05_shard_results_written_atomically_with_marker(tmp_path, work):
    out = tmp_path / "run"
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.status == "complete" and outcome.computed == 6 and outcome.skipped == 0
    plan = json.loads((out / store.PLAN).read_text(encoding="utf-8"))
    joined = b""
    for i in range(6):
        data = (out / "shards" / f"shard-{i:05d}.jsonl").read_bytes()
        marker = json.loads((out / "shards" / f"shard-{i:05d}.done.json").read_text(encoding="utf-8"))
        assert marker["results_sha256"] == hashlib.sha256(data).hexdigest()
        assert marker["results_bytes"] == len(data) and marker["rows"] == 10 == data.count(b"\n")
        assert marker["plan_id"] == plan["plan_id"] and marker["shard"] == i
        assert marker["machine"] == lp.machine_block()
        joined += data
    assert (out / "results.jsonl").read_bytes() == joined
    assert list(out.rglob("*.partial")) == []


def test_FR_0_5_05_results_without_marker_not_finished(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    reference = (out / "results.jsonl").read_bytes()
    (out / "shards" / "shard-00002.done.json").unlink()
    (out / "shards" / "shard-00004.done.json").unlink()
    (out / "shards" / "shard-00004.jsonl").write_bytes(b'{"clip_id":"stale"}\n')
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.computed == 2 and outcome.skipped == 4
    session = last_session(out)
    assert "shard 00002 not finished: no completion marker" in session
    assert "shard 00004 not finished: no completion marker" in session
    assert "shard 00001 skipped" in session and "shard 00002 skipped" not in session
    assert (out / "results.jsonl").read_bytes() == reference


@pytest.mark.parametrize("damage, reason", [
    (lambda m: {**m, "results_sha256": "0" * 64}, "results sha256"),
    (lambda m: {**m, "plan_id": "f" * 64}, "another plan"),
    (lambda m: {**m, "shard": 5}, "another shard"),
    (None, "unreadable"),
])
def test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished(tmp_path, work, damage, reason):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    reference = (out / "results.jsonl").read_bytes()
    marker_path = out / "shards" / "shard-00003.done.json"
    if damage is None:
        marker_path.write_bytes(b'{"plan_id": ')
    else:
        marker_path.write_text(json.dumps(damage(json.loads(marker_path.read_text(encoding="utf-8")))),
                               encoding="utf-8")
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.computed == 1 and outcome.skipped == 5
    assert "shard 00003 not finished" in last_session(out) and reason in last_session(out)
    assert (out / "results.jsonl").read_bytes() == reference
    ok, _ = store.shard_finished(out, 3, json.loads((out / store.PLAN).read_text())["plan_id"])
    assert ok


def test_FR_0_5_05_restart_skips_finished_shards(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (out / "shards").iterdir()}
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.computed == 0 and outcome.skipped == 6
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (out / "shards").iterdir()} == before
    session = last_session(out)
    assert session.startswith(" session 2 start")
    assert all(f"shard {i:05d} skipped" in session for i in range(6)) and "started" not in session


def test_FR_0_5_05_starting_over_requires_from_scratch(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    with pytest.raises(RunInputError) as err:
        run(opts(out, work, shard_clips=20))
    assert "--from-scratch" in str(err.value) and "plan" in str(err.value)
    outcome = run(opts(out, work, shard_clips=20, from_scratch=True))
    assert outcome.status == "complete" and outcome.computed == 3 and outcome.skipped == 0
    assert len(markers(out)) == 3


def test_FR_0_5_05_from_scratch_keeps_old_run_folder(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    old = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    run(opts(out, work, shard_clips=10, from_scratch=True))
    kept = [p for p in tmp_path.iterdir() if p.name.startswith("run.superseded-")]
    assert len(kept) == 1
    assert {p.relative_to(kept[0]).as_posix(): p.read_bytes() for p in kept[0].rglob("*") if p.is_file()} == old
    assert "session 1 start" in log_of(out) and "session 2" not in log_of(out)


def test_FR_0_5_05_changed_card_or_plan_refused(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    with pytest.raises(RunInputError) as err:
        run(opts(out, work, shard_clips=10, seed=7))
    assert "/seed" in str(err.value) and "--from-scratch" in str(err.value)
    plan = out / store.PLAN
    data = json.loads(plan.read_text(encoding="utf-8"))
    data["shards"][0]["clip_ids"].reverse()
    plan.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RunInputError) as err:
        run(opts(out, work, shard_clips=10))
    assert "shard plan" in str(err.value)
    (tmp_path / "junk").mkdir()
    (tmp_path / "junk" / "x.txt").write_text("not a run", encoding="utf-8")
    with pytest.raises(RunInputError):
        run(opts(tmp_path / "junk", work, shard_clips=10))


def _edit_card(out, change):
    path = out / store.RUN_CARD
    card = json.loads(path.read_text(encoding="utf-8"))
    change(card)
    card["run_card_id"] = compute_run_card_id(card)
    path.write_text(json.dumps(card), encoding="utf-8")
    plan_path = out / store.PLAN
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["run_card_id"] = card["run_card_id"]
    plan["plan_id"] = sha256_canonical({k: v for k, v in plan.items() if k != "plan_id"})
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    for marker in (out / "shards").glob("*.done.json"):
        m = json.loads(marker.read_text(encoding="utf-8"))
        m["plan_id"] = plan["plan_id"]
        marker.write_text(json.dumps(m), encoding="utf-8")
    return card


def test_FR_0_5_05_resume_rule_for_other_cpu_model(tmp_path, work):
    # Owner decision (question 4 (b)): a resume may run on another CPU model, nothing else may differ.
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10, max_shards=2))
    card = _edit_card(out, lambda c: c["machine"].update(cpu_model="Intel(R) Xeon(R) CPU @ 2.20GHz (first session)"))
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.status == "complete" and outcome.skipped == 2 and outcome.computed == 4
    assert "CPU model differs" in last_session(out)
    stored = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    assert stored == card, "the stored card keeps the first session's machine block"
    later = json.loads((out / "shards" / "shard-00005.done.json").read_text(encoding="utf-8"))
    assert later["machine"] == lp.machine_block() and later["session"] == 2
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
    assert {r["run_card_id"] for r in rows[20:]} == {card["run_card_id"]}, "rows computed now use the stored card"
    out2 = tmp_path / "run-gpu"
    run(opts(out2, work, shard_clips=10, max_shards=2))
    _edit_card(out2, lambda c: c["machine"].update(gpu="Tesla T4"))
    with pytest.raises(RunInputError) as err:
        run(opts(out2, work, shard_clips=10))
    assert "/machine/gpu" in str(err.value)


def test_FR_0_5_05_run_card_valid_and_traceable(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, seed=42, notes="trace test"))
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    validate_run_card(card)
    assert card["pack"] == {"manifest_id": "smoke", "version": "1.0.0", "sha256": sha256_canonical(MANIFEST)}
    lock = ROOT / "requirements/aqis_lab/phase0.txt"
    assert card["lock"] == {"file": "requirements/aqis_lab/phase0.txt",
                            "sha256": hashlib.sha256(lock.read_bytes()).hexdigest()}
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=normal"],
                                capture_output=True, text=True).stdout.strip())
    assert card["git"] == {"commit": head, "dirty": dirty}
    assert card["machine"] == lp.machine_block()
    assert card["model"] == {"family": "aqis-lab-task", "name": "clip-stats", "version": "1.0", "checksum": None,
                             "settings": {}}
    assert card["mode"] == "batch" and card["seed"] == 42 and card["normaliser"] is None
    assert card["processing"] == {"vad": [], "stt": [], "emotion": []} and card["notes"] == "trace test"


def _stats(data):
    with wave.open(io.BytesIO(data)) as w:
        rate, channels, frames = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    samples = array("h")
    samples.frombytes(frames)
    return {"samples": len(samples), "sample_rate_hz": rate, "channels": channels,
            "peak_abs": max((abs(s) for s in samples), default=0), "sum_samples": sum(samples),
            "sum_squares": sum(s * s for s in samples)}


def test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids(tmp_path, work):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10))
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    lines = (out / "results.jsonl").read_bytes().splitlines()
    rows = [json.loads(l) for l in lines]
    assert [r["clip_id"] for r in rows] == CLIP_IDS
    assert {r["run_card_id"] for r in rows} == {card["run_card_id"]}
    for line, row in zip(lines, rows):
        assert line == json.dumps(row, sort_keys=True, separators=(",", ":")).encode(), "canonical JSON rows"
    staged = work / "packs" / "smoke" / "1.0.0" / "clips"
    for clip in (MANIFEST["clips"][0], MANIFEST["clips"][35], MANIFEST["clips"][45], MANIFEST["clips"][59]):
        row = rows[CLIP_IDS.index(clip["clip_id"])]
        expected = _stats((staged / clip["member_path"]).read_bytes())
        assert {k: row[k] for k in expected} == expected, clip["clip_id"]
        assert row["task"] == "clip-stats" and row["task_version"] == "1.0"


def test_FR_0_5_05_clip_failure_stops_run_without_marker(tmp_path):
    work = tmp_path / "work"
    run(opts(tmp_path / "prime", work, max_shards=0))       # stage only: stops before any shard
    clip = MANIFEST["clips"][47]
    (work / "packs" / "smoke" / "1.0.0" / "clips" / clip["member_path"]).write_bytes(b"RIFF broken")
    out = tmp_path / "run"
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(out), "--seed", "0", "--work-dir", str(work), "--shard-clips", "10"],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 1
    assert markers(out) == [f"shard-{i:05d}.done.json" for i in range(4)]
    assert not (out / "shards" / "shard-00004.jsonl").exists() and not (out / "results.jsonl").exists()
    assert f"ERROR shard 00004 clip {clip['clip_id']}" in log_of(out)


def test_FR_0_5_05_max_shards_stops_cleanly(tmp_path, work):
    out = tmp_path / "run"
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(out), "--seed", "0", "--work-dir", str(work), "--shard-clips", "10",
                           "--max-shards", "2"], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr
    assert markers(out) == ["shard-00000.done.json", "shard-00001.done.json"]
    assert "4 shard(s) remain" in log_of(out) and not (out / "results.jsonl").exists()
    outcome = run(opts(out, work, shard_clips=10))
    assert outcome.skipped == 2 and outcome.computed == 4 and outcome.status == "complete"


def test_FR_0_5_05_runner_doc_matches_code(tmp_path, work):
    doc = (ROOT / "docs" / "runner" / "RUNNER.md").read_text(encoding="utf-8")
    ratio = TASKS["clip-stats"].seconds_per_audio_second
    assert f"that ratio is **{ratio}**" in doc
    out = tmp_path / "run"
    run(opts(out, work))
    marker = json.loads((out / "shards" / "shard-00000.done.json").read_text(encoding="utf-8"))
    marker_line = next(l for l in doc.splitlines() if l.startswith("| `shards/shard-NNNNN.done.json`"))
    assert set(re.findall(r"`([a-z0-9_]+)`", marker_line)) == set(marker)
    row = json.loads((out / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert all(f"`{k}`" in doc for k in row)
    plan = json.loads((out / store.PLAN).read_text(encoding="utf-8"))
    plan_section = doc[doc.index("## Shard plan"):doc.index("## Run folder")]
    assert all(f"`{k}`" in plan_section for k in plan)


# WP-0.5-F05: owner decision (question 4 (b)): only machine.cpu_model may differ on resume; every other difference
# is refused, so shards from another Python, OS, architecture, commit, lock or pack never mix under one run card.
REFUSED_CHANGES = {
    "/machine/python_version": lambda c: c["machine"].update(python_version="3.12.9"),
    "/machine/os": lambda c: c["machine"].update(os="Ubuntu 22.04.4 LTS"),
    "/machine/architecture": lambda c: c["machine"].update(architecture="aarch64"),
    "/git/commit": lambda c: c["git"].update(commit="0" * 40),
    "/git/dirty": lambda c: c["git"].update(dirty=not c["git"]["dirty"]),
    "/lock/sha256": lambda c: c["lock"].update(sha256="1" * 64),
    "/pack/sha256": lambda c: c["pack"].update(sha256="2" * 64),
}


@pytest.mark.parametrize("pointer", sorted(REFUSED_CHANGES))
def test_FR_0_5_05_resume_refused_when_card_differs(tmp_path, work, pointer):
    out = tmp_path / "run"
    run(opts(out, work, shard_clips=10, max_shards=2))
    _edit_card(out, REFUSED_CHANGES[pointer])
    before = {p.name: p.read_bytes() for p in (out / "shards").iterdir()}
    with pytest.raises(RunInputError) as err:
        run(opts(out, work, shard_clips=10))
    assert pointer in str(err.value) and "--from-scratch" in str(err.value)
    assert {p.name: p.read_bytes() for p in (out / "shards").iterdir()} == before, "nothing was computed"


def _cli(out, work, *extra):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(out), "--seed", "0", "--work-dir", str(work), "--shard-clips", "10", *extra],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)


def test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log(tmp_path, work):
    # WP-0.5-F08: a failed write in the run folder names the run folder; only unit-log failures name the unit log
    out = tmp_path / "run"
    assert _cli(out, work, "--max-shards", "2").returncode == 0
    (out / "results.jsonl").mkdir()                           # the final results file cannot be written
    proc = _cli(out, work)
    assert proc.returncode == 2
    assert proc.stderr.startswith("ERROR: cannot write the run folder") and "results.jsonl" in proc.stderr
    assert "unit log" not in proc.stderr
    from aqis_runner_testutil import stand_in_drive
    mount = stand_in_drive(tmp_path / "drive")
    (mount / "MyDrive" / "AQIS_LAB" / "logs").mkdir()
    (mount / "MyDrive" / "AQIS_LAB" / "logs" / "units_open_session.json").write_text("{not json", encoding="utf-8")
    proc = _cli(tmp_path / "run-2", work, "--drive-mount", str(mount))
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR: unit log (last-seen time):")
    assert "units_open_session.json" in proc.stderr
