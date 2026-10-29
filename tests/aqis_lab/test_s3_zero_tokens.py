"""WP-1.3 rerun fix: turns for which stage 1 produced no words have no token confidence, and must not disable the confidence policies.

The first full run found 46 of 6,300 turns without confidence or entropy and marked confidence, entropy and the confidence part of
the hybrid gate unavailable for all 6,300. A turn with no stage 1 words is the least trustworthy turn there is, so it is scored as
least confident (0.0; the entropy feature is an entropy-based confidence, higher = more confident, so 0.0 is maximum entropy). Only
turns with no words get this: a turn with words and no confidence is a failure of the extraction and keeps the policy unavailable.
"""
import csv
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_s3_simulate import (CONDITION, EH, E1, HEAVY, SLICE, STAGE1, WORDS, build_s1, hyp, make_config, read_csv, s1_config, REPO)

from aqis_lab.cascade import simulate

LOG = lambda *_: None  # noqa: E731


def test_s3_only_turns_with_no_stage_1_words_are_scored_as_least_confident():
    rows = [{"key": "a", "words": 0, "confidence": None, "entropy": None},
            {"key": "b", "words": 5, "confidence": None, "entropy": 0.4},
            {"key": "c", "words": 0, "confidence": 0.7, "entropy": None}]
    assert simulate.impute_no_word_turns(rows) == 2
    assert (rows[0]["confidence"], rows[0]["entropy"], rows[0]["imputed"]) == (0.0, 0.0, True)
    assert rows[1]["confidence"] is None and rows[1]["entropy"] == 0.4 and not rows[1].get("imputed")      # words, no confidence: left alone
    assert (rows[2]["confidence"], rows[2]["entropy"], rows[2]["imputed"]) == (0.7, 0.0, True)               # only the missing score is filled


def silent_turn(root, features):
    """The 8-turn example where stage 1 says nothing on turn 3 (10 word errors) and `features` gives confidences (None = missing)."""
    ids = build_s1(root)
    path = root / "preds" / STAGE1 / f"{SLICE}__{CONDITION}.parquet"
    errors = list(E1)
    errors[3] = 10
    pq.write_table(pa.Table.from_pylist([{"utt_id": u, "hyp": "" if i == 3 else hyp(e)} for i, (u, e) in enumerate(zip(ids, errors))]), path)
    out = root.parent / "s3out"
    (out / "cascade").mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([{"key": f"{SLICE}:{CONDITION}:{u}", "confidence": c, "entropy": c, "nonspeech_ratio": None}
                                         for u, c in zip(ids, features)]), out / "cascade" / "features.parquet")
    return out, ids


CONFIDENCES = [0.9, 0.95, 0.99, None, 0.97, 0.8, 0.2, 0.98]        # turn 3 has no words and no confidence; turn 6 is the next least sure


def test_s3_a_silent_turn_no_longer_disables_the_confidence_policies(tmp_path):
    out, _ = silent_turn(tmp_path / "s1", CONFIDENCES)
    simulate.run(make_config(tmp_path), s1_config.load_config(REPO / "config" / "aqis_lab" / "s1.yaml"), tmp_path / "s1", out, log=LOG)
    status = json.loads((out / "report" / "policies.json").read_text(encoding="utf-8"))
    for name in ("confidence", "entropy"):
        assert status[name].startswith("ok") and "1 turn" in status[name] and "least confident" in status[name], status[name]
    assert "confidence" in status["hybrid"] and status["hybrid"].startswith("ok")


def test_s3_the_silent_turn_is_escalated_first_and_the_numbers_follow(tmp_path):
    out, _ = silent_turn(tmp_path / "s1", CONFIDENCES)
    simulate.run(make_config(tmp_path), s1_config.load_config(REPO / "config" / "aqis_lab" / "s1.yaml"), tmp_path / "s1", out, log=LOG)
    rows = {float(r["rate"]): r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] == "confidence"}
    # stage 1 makes 22 errors in 80 words; two escalations take turn 3 (10 -> 1) and turn 6 (5 -> 1): 22 - 9 - 4 = 9
    assert int(rows[0.25]["errors"]) == 9 and float(rows[0.25]["wer"]) == pytest.approx(9 / 80)
    assert int(rows[0.0]["errors"]) == 22


def test_s3_nothing_imputed_is_written_to_the_feature_file(tmp_path):
    out, ids = silent_turn(tmp_path / "s1", CONFIDENCES)
    simulate.run(make_config(tmp_path), s1_config.load_config(REPO / "config" / "aqis_lab" / "s1.yaml"), tmp_path / "s1", out, log=LOG)
    stored = simulate.read_features(out / "cascade" / "features.parquet")
    assert stored[f"{SLICE}:{CONDITION}:{ids[3]}"]["confidence"] is None


def test_s3_a_turn_with_words_and_no_confidence_still_makes_the_policy_unavailable(tmp_path):
    out, _ = silent_turn(tmp_path / "s1", [0.9, 0.95, 0.99, None, 0.97, 0.8, None, 0.98])        # turn 6 has words
    simulate.run(make_config(tmp_path), s1_config.load_config(REPO / "config" / "aqis_lab" / "s1.yaml"), tmp_path / "s1", out, log=LOG)
    status = json.loads((out / "report" / "policies.json").read_text(encoding="utf-8"))
    assert status["confidence"].startswith("unavailable") and "1 of 8" in status["confidence"]
    assert not [r for r in read_csv(out / "report" / "cascade.csv") if r["policy"] == "confidence"]
