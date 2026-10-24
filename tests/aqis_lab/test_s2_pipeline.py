"""WP-1.2: synthetic clips flow through the VAD and turn stages into the scorecard, and a rerun computes nothing twice.

The expected figures are the hand-worked ones of test_s2_turn.py: a 300 ms timer interrupts the 400 ms and 700 ms pauses but not
the 250 ms one (2 of 3), a 500 ms timer only the 700 ms one (1 of 3), and each fires exactly its threshold after the last word.
"""
import json
from pathlib import Path

import numpy as np
import pytest
from test_s2_vad_score import EnergyVAD, tone_bursts

from aqis_lab.live import prep, report, results, stages
from aqis_lab.live.config import load_config

REPO = Path(__file__).resolve().parents[2]
SR = 16000
BURSTS = [(0, 1000), (1400, 2000), (2700, 3500), (3750, 4500)]
TURN_REF = {"words_ms": BURSTS, "pauses_ms": [[1000, 1400], [2000, 2700], [3500, 3750]], "end_ms": 4500}


def data_rows(set_name, items):
    return [{"utt_id": f"{set_name}:{i['id']}", "source": "synthetic", "licence": "none", "audio": i["audio"].astype("<i2").tobytes(),
             "n_samples": len(i["audio"]), "duration_s": len(i["audio"]) / SR, "speaker": i["cluster"], "cluster": i["cluster"],
             "label": "", "ref": json.dumps(i["ref"]), "meta": "{}"} for i in items]


@pytest.fixture
def run(tmp_path, monkeypatch):
    cfg = load_config(REPO / "config" / "aqis_lab" / "s2.yaml")
    audio = tone_bursts(6000, BURSTS)
    turns = [{"id": f"t{i}", "audio": audio, "cluster": f"spk{i % 2}", "ref": TURN_REF} for i in range(4)]
    vads = [{"id": f"v{i}", "audio": audio, "cluster": f"spk{i % 2}", "ref": {"segments_ms": BURSTS, "kind": "speech"}} for i in range(4)]
    vads.append({"id": "quiet", "audio": np.zeros(3 * SR, dtype=np.int16), "cluster": "silence1", "ref": {"segments_ms": [], "kind": "silence"}})
    for condition in cfg.conditions["turn"]:
        prep._write_rows(tmp_path / "data" / "turn" / f"{condition}.parquet", data_rows("turn", turns))
    for condition in cfg.conditions["vad"]:
        prep._write_rows(tmp_path / "data" / "vad" / f"{condition}.parquet", data_rows("vad", vads))
    monkeypatch.setattr(stages, "make_vad", lambda run, name: (EnergyVAD(20), None, "energy-vad@test"))
    return stages.Run(cfg, tmp_path, REPO, machine="synthetic test machine")


def test_s2_turn_stage_scores_the_hand_worked_turn(run):
    stages.run_turn(run, policies=["fixed_300", "fixed_500", "fixed_1000"], conditions=["native"])
    table = {r["model"]: r for r in report.turn_table(run.cfg, run.out)}
    assert (table["fixed_300"]["pauses"], table["fixed_300"]["fir"], table["fixed_300"]["latency_p50_ms"]) == (12, 8 / 12, 300.0)
    assert (table["fixed_500"]["fir"], table["fixed_500"]["latency_p50_ms"]) == (4 / 12, 500.0)
    assert (table["fixed_1000"]["fir"], table["fixed_1000"]["latency_p50_ms"]) == (0.0, 1000.0)


def test_s2_vad_stage_scores_exact_lags_and_no_false_alarms(run):
    stages.run_vad(run, names=["silero_v5"], conditions=["phone"])
    row = next(r for r in report.vad_table(run.cfg, run.out) if r["collar_ms"] == 50 and r["subset"] == "all clips")
    assert (row["far"], row["mdr"], row["onset_p50_ms"], row["offset_p50_ms"]) == (0.0, 0.0, 20.0, 0.0)
    assert row["segments"] == 16 and row["segment_miss_rate"] == 0.0
    quiet = next(r for r in report.vad_table(run.cfg, run.out) if r["collar_ms"] == 50 and r["subset"] == "non-speech clips")
    assert quiet["far"] == 0.0 and quiet["clips"] == 1


def test_s2_every_result_row_carries_the_trace_and_a_rerun_adds_nothing(run):
    stages.run_turn(run, policies=["fixed_500"], conditions=["native"])
    path = run.result_path("turn", "fixed_500", "native")
    rows = results.read_rows(path)
    assert {r["machine"] for r in rows} == {"synthetic test machine"} and {r["revision"] for r in rows} == {"energy-vad@test"}
    assert {r["git_commit"] for r in rows} == {run.commit} and {r["seed"] for r in rows} == {run.cfg.seed}
    stages.run_turn(run, policies=["fixed_500"], conditions=["native"])
    assert len(results.read_rows(path)) == len(rows)


def test_s2_scorecard_checks_every_gate_and_marks_unmeasured_ones(run):
    stages.run_turn(run, policies=["fixed_300"], conditions=["native"])
    stages.run_vad(run, names=["silero_v5"], conditions=["phone"])
    tables = {name: [] for name in ("vad", "vad_det", "turn", "stream", "emotion")}
    tables["vad"], tables["turn"] = report.vad_table(run.cfg, run.out), report.turn_table(run.cfg, run.out)
    text = report.scorecard(run.cfg, tables)
    assert "| fixed_300 | native | 4 | 12 | 66.67% [66.67%, 66.67%] |" in text and "FAIL" in text      # FIR 8/12 against the 3% gate
    assert "| silero_v5 | phone |" in text and "PASS" in text
    assert "Streaming STT" not in text and "## Emotion" not in text                                    # nothing measured: no section
