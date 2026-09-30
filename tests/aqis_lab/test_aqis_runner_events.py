"""WP-0.7: the runner with adapter tasks. Event logs (FR-0.7-01, must-catch 1 and 2), run-card mode, normaliser and
lock per task (FR-0.7-07), clip subsets in the shard plan, and resumable event runs.

The fast tests run the real harness VAD task over the real smoke pack; `network` tests run the real Vosk model.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from aqis_lab import platform as lp
from aqis_lab.adapters import base
from aqis_lab.contracts.validate import validate_event_lines, validate_run_card
from aqis_lab.runner import store
from aqis_lab.runner.run import RunFailure, RunInputError, RunOptions, run
from aqis_lab.runner.tasks import TASKS
from aqis_lab.scoring.normalise import normaliser_identity
from aqis_adapters_testutil import SESSION_MODEL_CACHE, vosk_model
from aqis_results_testutil import cpu_list_text, oracle_system, usable_cpus, write_oracle_config
from aqis_runner_testutil import SMOKE_PACK
from aqis_testutil import ROOT

MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
CLIP_IDS = [c["clip_id"] for c in MANIFEST["clips"]]


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    return tmp_path_factory.mktemp("work")


def opts(out, work, **extra):
    values = dict(task="harness-vad", pack=SMOKE_PACK, out=out, seed=0, work_dir=work, echo=None)
    values.update(extra)
    echo = values.pop("echo")
    return RunOptions(**values), echo


def do_run(out, work, **extra):
    options, echo = opts(out, work, **extra)
    return run(options, echo=echo)


def events(out):
    data = (out / "events.jsonl").read_bytes()
    return data, [json.loads(line) for line in data.splitlines()]


def check_event_log(out, clip_ids, component):
    data, records = events(out)
    reports = validate_event_lines(data)
    assert all(r.valid for r in reports), [r for r in reports if not r.valid][:3]
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    run_id = (out / "run_id.txt").read_text(encoding="utf-8").strip()
    assert [r["seq"] for r in records] == list(range(len(records)))
    assert {r["run_id"] for r in records} == {run_id} and {r["run_card_id"] for r in records} == {card["run_card_id"]}
    assert {r["host_id"] for r in records} == {base.host_id()}
    assert records[0]["event_type"] == "run_started" and records[0]["clip_id"] is None
    assert records[-1]["event_type"] == "run_finished" and records[-1]["payload"] == {"status": "completed"}
    started = [r["clip_id"] for r in records if r["event_type"] == "clip_started"]
    finished = [r["clip_id"] for r in records if r["event_type"] == "clip_finished"]
    assert started == finished == clip_ids
    for r in records[1:-1]:
        assert r["component"] in ("runner", component) and r["clip_id"] in clip_ids
    return records


def test_FR_0_7_01_events_validate_against_event_log_v1(tmp_path, work):
    # Must-catch 1: the whole run's event log validates against event log v1, seq included.
    out = tmp_path / "run"
    outcome = do_run(out, work, shard_clips=25)
    assert outcome.status == "complete"
    records = check_event_log(out, CLIP_IDS, "vad")
    assert {r["event_type"] for r in records} >= {"speech_start", "speech_end"}
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["clip_id"] for r in rows] == CLIP_IDS and all(r["task"] == "harness-vad" for r in rows)
    for row in rows:
        clip_events = [r for r in records if r["clip_id"] == row["clip_id"] and r["component"] == "vad"]
        assert len(clip_events) == 2 * len(row["segments"])
    markers = [json.loads(p.read_text()) for p in sorted((out / "shards").glob("*.done.json"))]
    assert len(markers) == 3 and markers[0]["seq_first"] == 1
    for a, b in zip(markers, markers[1:]):
        assert b["seq_first"] == a["seq_first"] + a["events"]


def test_FR_0_7_07_run_card_mode_normaliser_and_model_per_task(tmp_path, work):
    out = tmp_path / "vad"
    do_run(out, work, max_shards=0)
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    validate_run_card(card)
    assert card["mode"] == "batch" and card["normaliser"] is None and card["model"]["family"] == "harness-vad"
    assert card["lock"]["file"] == "requirements/aqis_lab/phase0.txt"
    out = tmp_path / "vosk"
    do_run(out, work, task="vosk-realspeed", clips=("smoke-mix-01",), max_shards=0)
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    validate_run_card(card)
    assert card["mode"] == "realspeed_cpu" and card["normaliser"] == normaliser_identity()
    assert card["model"]["family"] == "vosk" and card["model"]["settings"]["openblas_coretype"] == "Prescott"
    assert TASKS["vosk-batch"].mode == "batch" and TASKS["parakeet-compute-delay"].mode == "gpu_compute_delay"
    assert TASKS["parakeet-offline"].mode == "batch" and TASKS["clip-stats"].mode == "batch"


def test_FR_0_7_07_clip_subset_goes_into_the_plan_not_the_card(tmp_path, work):
    subset = ("tts-smoke-04", "smoke-mix-01")
    out = tmp_path / "subset"
    outcome = do_run(out, work, clips=subset)
    plan = json.loads((out / store.PLAN).read_text(encoding="utf-8"))
    ordered = [c for c in CLIP_IDS if c in subset]
    assert plan["clip_selection"] == {"clip_ids": ordered}
    assert [c for s in plan["shards"] for c in s["clip_ids"]] == ordered
    full = tmp_path / "full"
    do_run(full, work, max_shards=0)
    card = json.loads((out / store.RUN_CARD).read_text(encoding="utf-8"))
    assert card["run_card_id"] == json.loads((full / store.RUN_CARD).read_text(encoding="utf-8"))["run_card_id"]
    assert outcome.status == "complete"
    check_event_log(out, ordered, "vad")
    with pytest.raises(RunInputError, match="shard plan"):
        do_run(out, work, clips=("tts-smoke-04",))
    with pytest.raises(RunInputError, match="not in the pack"):
        do_run(tmp_path / "unknown", work, clips=("no-such-clip",))


def test_FR_0_7_07_interrupted_event_run_resumes_with_the_same_log(tmp_path, work):
    out = tmp_path / "resumed"
    first = do_run(out, work, shard_clips=10, max_shards=2)
    assert first.status == "stopped" and not (out / "events.jsonl").exists()
    run_id = (out / "run_id.txt").read_text(encoding="utf-8")
    head = (out / "events.head.jsonl").read_bytes()
    done = {p.name: p.read_bytes() for p in (out / "shards").iterdir()}
    second = do_run(out, work, shard_clips=10)
    assert second.status == "complete" and second.skipped == 2 and second.computed == 4
    assert (out / "run_id.txt").read_text(encoding="utf-8") == run_id and (out / "events.head.jsonl").read_bytes() == head
    for name, data in done.items():
        assert (out / "shards" / name).read_bytes() == data, f"{name} was rewritten"
    check_event_log(out, CLIP_IDS, "vad")
    whole = tmp_path / "whole"
    do_run(whole, work, shard_clips=10)
    assert (out / "results.jsonl").read_bytes() == (whole / "results.jsonl").read_bytes()
    strip = lambda recs: [{k: v for k, v in r.items() if k not in ("wall_time_ns", "wall_clock_utc", "run_id",
                                                                     "host_id")} for r in recs]
    assert strip(events(out)[1]) == strip(events(whole)[1])


def test_FR_0_7_07_changed_shard_events_mean_the_shard_is_not_finished(tmp_path, work):
    out = tmp_path / "tampered"
    do_run(out, work, shard_clips=20)
    events_file = out / "shards" / "shard-00001.events.jsonl"
    events_file.write_bytes(events_file.read_bytes() + b"\n")
    finished, info = store.shard_finished(out, 1, json.loads((out / store.PLAN).read_text())["plan_id"])
    assert not finished and "events" in info
    outcome = do_run(out, work, shard_clips=20)
    assert outcome.computed == 1 and outcome.skipped == 2
    check_event_log(out, CLIP_IDS, "vad")


def test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event(tmp_path, work):
    # Must-catch 2 through the runner: the Vosk model folder in the cache has no verification marker, so open()
    # fails; the first shard's events hold the error event, no marker is written and the run stops (exit 1).
    cache = tmp_path / "models"
    (cache / "vosk-model-small-en-us-0.15" / "30f26242c4eb449f").mkdir(parents=True)
    out = tmp_path / "failing"
    with pytest.raises(RunFailure, match="without its verification marker"):
        do_run(out, work, task="vosk-batch", model_cache=cache)
    fragment = out / "shards" / "shard-00000.events.jsonl"
    data = fragment.read_bytes()
    records = [json.loads(l) for l in data.splitlines()]
    errors = [r for r in records if r["event_type"] == "error"]
    assert len(errors) == 1 and errors[0]["payload"]["code"] == "model-download"
    assert errors[0]["payload"]["run_continues"] is False and errors[0]["component"] == "live_stt"
    assert records[0]["seq"] == 1 and all(r.valid for r in validate_event_lines(
        (out / "events.head.jsonl").read_bytes() + data))
    assert not (out / "shards" / "shard-00000.done.json").exists() and not (out / "events.jsonl").exists()
    assert "ERROR" in (out / "runner.log").read_text(encoding="utf-8")


def test_FR_0_7_03_runner_refuses_parakeet_without_gpu_before_writing(tmp_path, work):
    out = tmp_path / "parakeet"
    with pytest.raises(RunInputError, match="no GPU"):
        do_run(out, work, task="parakeet-offline")
    assert not out.exists()


def test_FR_0_7_05_realspeed_run_pins_timing_cores_on_oracle(tmp_path, work):
    # The runner pins itself for the task's run mode: a real-speed run goes to the reserved timing cores.
    cpus = usable_cpus()
    reserved = {cpus[-1]}
    config = write_oracle_config(tmp_path / "oracle.yaml", sorted(reserved))
    view = oracle_system(tmp_path)
    script = ("import json, sys\nfrom pathlib import Path\nfrom aqis_lab import platform as lp\n"
              "from aqis_lab.runner.run import RunOptions, run\n"
              "root, pack, out, work, config, env = sys.argv[1:7]\nenv = json.loads(env)\n"
              "view = lp.SystemView(root=Path(root), environ=env, path=env['PATH'])\n"
              "run(RunOptions(task='vosk-realspeed', pack=Path(pack), out=Path(out), seed=0, work_dir=Path(work),"
              " max_shards=0, clips=('smoke-mix-01',), cores_config=Path(config)), system=view, echo=None)\n")
    out = tmp_path / "rs"
    proc = subprocess.run([sys.executable, "-c", script, str(view.root), str(SMOKE_PACK), str(out), str(work),
                           str(config), json.dumps(view.environ)], cwd=ROOT, capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stderr
    assert f"cores: timing on {cpu_list_text(reserved)}" in (out / "runner.log").read_text(encoding="utf-8")


@pytest.mark.network
def test_FR_0_7_01_vosk_run_events_validate_against_event_log_v1(tmp_path, work):
    vosk_model()
    out = tmp_path / "vosk"
    subset = ("ls-test-clean-1188-133604-0029", "smoke-silence-01", "tts-smoke-04")
    do_run(out, work, task="vosk-batch", clips=subset, model_cache=SESSION_MODEL_CACHE)
    ordered = [c for c in CLIP_IDS if c in subset]
    records = check_event_log(out, ordered, "live_stt")
    assert {"partial", "final"} <= {r["event_type"] for r in records}
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["text_sha256"] and "text" in r for r in rows)
    assert "OpenBLAS kernel PRESCOTT" in (out / "runner.log").read_text(encoding="utf-8") or \
        "OpenBLAS kernel fixed-build" in (out / "runner.log").read_text(encoding="utf-8")
