"""WP-1.3: the cascade simulation reads Sprint 1 files, builds the target set, and writes the operating curves.

Eight turns of ten words in two speakers; the errors of stage 1 and of the heavy model are set by substituting words, so every
figure is worked out by hand: stage 1 makes 18 errors in 80 words (0.225), the heavy model 6 (0.075).
"""
import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from aqis_lab.bench import config as s1_config
from aqis_lab.cascade import config as cascade_config
from aqis_lab.cascade import simulate

REPO = Path(__file__).resolve().parents[2]
WORDS = "apple banana cherry date elder fig grape honey iris jade".split()
E1 = [3, 0, 1, 6, 0, 2, 5, 1]
EH = [0, 0, 2, 1, 0, 0, 1, 1]
# gains (stage 1 errors minus heavy errors): 3 0 -1 5 0 2 4 0
STAGE1, HEAVY = "parakeet-tdt-0.6b-v2", "qwen3-asr-1.7b"
SLICE, CONDITION = "us_conv", "phone"


def hyp(errors):
    out = list(WORDS)
    for i in range(errors):
        out[i] = "zebra"
    return " ".join(out)


def build_s1(root, models=(STAGE1, HEAVY)):
    (root / "data" / SLICE).mkdir(parents=True)
    (root / "data" / "manifest.json").write_text("{}", encoding="utf-8")
    ids = [f"{SLICE}:u{i}" for i in range(8)]
    pq.write_table(pa.Table.from_pylist([
        {"utt_id": u, "ref_clean": " ".join(WORDS), "cluster": f"spk{i // 4}", "meta": json.dumps({}), "duration_s": 5.0}
        for i, u in enumerate(ids)]), root / "data" / SLICE / f"{CONDITION}.parquet")
    for model, errors in zip(models, (E1, EH)):
        folder = root / "preds" / model
        folder.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist([{"utt_id": u, "hyp": hyp(e)} for u, e in zip(ids, errors)]),
                       folder / f"{SLICE}__{CONDITION}.parquet")
    return ids


def make_config(tmp_path, **cascade_changes):
    raw = yaml.safe_load((REPO / "config" / "aqis_lab" / "s3.yaml").read_text(encoding="utf-8"))
    raw["cascade"].update(rates=[0.0, 0.25, 0.5, 1.0], folds=2, heavy=[HEAVY], **cascade_changes)
    path = tmp_path / "s3.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return cascade_config.load_config(path)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def s1(tmp_path):
    root = tmp_path / "s1"
    ids = build_s1(root)
    return root, ids, s1_config.load_config(REPO / "config" / "aqis_lab" / "s1.yaml")


def test_s3_target_set_scores_every_turn_both_models_answered(s1):
    root, ids, s1_cfg = s1
    ts = simulate.load_target_set(s1_cfg, root, STAGE1, [HEAVY])
    assert ts.keys == [f"{SLICE}:{CONDITION}:{u}" for u in ids]
    assert ts.errors[STAGE1].tolist() == E1 and ts.errors[HEAVY].tolist() == EH and ts.words.tolist() == [10] * 8
    assert ts.channel == ["phone"] * 8 and ts.clusters[0] == f"{SLICE}:spk0" and ts.audio_s.tolist() == [5.0] * 8


def test_s3_a_turn_one_model_never_answered_is_left_out_and_counted(s1, tmp_path):
    root, ids, s1_cfg = s1
    path = root / "preds" / HEAVY / f"{SLICE}__{CONDITION}.parquet"
    rows = pq.read_table(path).to_pylist()[:-1]
    pq.write_table(pa.Table.from_pylist(rows), path)
    ts = simulate.load_target_set(s1_cfg, root, STAGE1, [HEAVY])
    assert len(ts.keys) == 7 and ts.left_out == 1


def test_s3_missing_predictions_of_a_model_stop_the_run(s1):
    root, _, s1_cfg = s1
    with pytest.raises(simulate.SimulateError, match="cohere-transcribe-2b"):
        simulate.load_target_set(s1_cfg, root, STAGE1, ["cohere-transcribe-2b"])


def test_s3_the_perfect_gate_curve_matches_the_hand_worked_figures(s1, tmp_path):
    root, _, s1_cfg = s1
    out = tmp_path / "s3out"
    simulate.run(make_config(tmp_path), s1_cfg, root, out, log=lambda *_: None)
    rows = [r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] == "oracle"]
    got = {float(r["rate"]): (int(r["escalated"]), float(r["wer"])) for r in rows}
    assert got[0.0] == (0, pytest.approx(18 / 80)) and got[0.25] == (2, pytest.approx(9 / 80))
    assert got[0.5] == (4, pytest.approx(4 / 80)) and got[1.0] == (8, pytest.approx(6 / 80))        # all heavy: negative gain forced


def test_s3_every_policy_starts_at_stage_1_and_ends_at_the_heavy_model_and_stays_within_its_rate(s1, tmp_path):
    root, _, s1_cfg = s1
    out = tmp_path / "s3out"
    simulate.run(make_config(tmp_path), s1_cfg, root, out, log=lambda *_: None)
    rows = read_csv(out / "report" / "cascade.csv")
    policies = {r["policy"] for r in rows}
    assert {"random", "duration", "channel", "hybrid", "oracle"} <= policies
    for name in policies:
        mine = {float(r["rate"]): r for r in rows if r["policy"] == name}
        assert float(mine[0.0]["wer"]) == pytest.approx(18 / 80) and float(mine[1.0]["wer"]) == pytest.approx(6 / 80), name
        assert all(float(r["escalation_rate"]) <= float(r["rate"]) + 1e-9 for r in mine.values()), name


def test_s3_a_policy_that_needs_a_missing_feature_is_reported_as_unavailable_and_not_guessed(s1, tmp_path):
    root, _, s1_cfg = s1
    out = tmp_path / "s3out"
    simulate.run(make_config(tmp_path), s1_cfg, root, out, log=lambda *_: None)
    status = json.loads((out / "report" / "policies.json").read_text(encoding="utf-8"))
    assert status["confidence"].startswith("unavailable") and "confidence" in status["confidence"]
    assert status["nonspeech"].startswith("unavailable")
    assert not [r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] in ("confidence", "nonspeech")]
    assert status["hybrid"].startswith("ok") and "duration_s" in status["hybrid"] and "confidence" not in status["hybrid"].split("(")[1]


def test_s3_a_confidence_feature_file_makes_the_confidence_policy_available(s1, tmp_path):
    root, ids, s1_cfg = s1
    out = tmp_path / "s3out"
    gains = [e1 - eh for e1, eh in zip(E1, EH)]
    (out / "cascade").mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([{"key": f"{SLICE}:{CONDITION}:{u}", "confidence": 1 - g / 10, "entropy": g / 10,
                                          "nonspeech_ratio": None} for u, g in zip(ids, gains)]),
                   out / "cascade" / "features.parquet")
    simulate.run(make_config(tmp_path), s1_cfg, root, out, log=lambda *_: None)
    rows = [r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] == "confidence"]
    assert {float(r["rate"]): float(r["wer"]) for r in rows}[0.25] == pytest.approx(9 / 80)          # the two lowest confidences are the two largest gains
    status = json.loads((out / "report" / "policies.json").read_text(encoding="utf-8"))
    assert status["nonspeech"].startswith("unavailable")                                              # an empty column is not a feature


def test_s3_cost_and_latency_columns_use_the_config_figures(s1, tmp_path):
    root, _, s1_cfg = s1
    out = tmp_path / "s3out"
    cfg = make_config(tmp_path)
    simulate.run(cfg, s1_cfg, root, out, log=lambda *_: None)
    row = next(r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] == "oracle" and float(r["rate"]) == 0.5)
    heavy = cfg.cascade["cost"]["heavy"][HEAVY]
    live = cfg.cascade["cost"]["live_rtfx"]
    cascade_s = 40 / live + 20 / heavy["rtfx"]                  # 4 of 8 turns of 5 s go to the heavy model
    assert float(row["gpu_savings"]) == pytest.approx(1 - cascade_s / (40 / heavy["rtfx"]), abs=1e-4)
    assert float(row["added_latency_ms"]) == pytest.approx(0.5 * heavy["latency_p50_ms"], abs=1e-3)


def test_s3_the_gate_threshold_file_names_the_score_that_gives_the_rate(s1, tmp_path):
    root, _, s1_cfg = s1
    out = tmp_path / "s3out"
    simulate.run(make_config(tmp_path), s1_cfg, root, out, log=lambda *_: None)
    thresholds = json.loads((out / "report" / "thresholds.json").read_text(encoding="utf-8"))
    entry = thresholds["duration"][HEAVY]
    assert set(entry) >= {"rate", "threshold", "feature", "sign"} and entry["rate"] <= 0.35
