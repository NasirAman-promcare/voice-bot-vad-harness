"""WP-1.3: the fine-tuning and prompt scorecards apply the brief's gates to prediction files (synthetic, errors set by hand)."""
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aqis_lab.cascade import report
from aqis_lab.cascade.config import load_config

REPO = Path(__file__).resolve().parents[2]
CFG = load_config(REPO / "config" / "aqis_lab" / "s3.yaml")


def words(n, prefix="word"):
    return [f"{prefix}{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(n)]


def hyp(tokens, errors):
    return " ".join(["zebra"] * errors + tokens[errors:])


def write_data(root, slice_name, condition, refs):
    folder = root / "data" / slice_name
    folder.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([{"utt_id": f"{slice_name}:u{i}", "ref_clean": " ".join(t), "cluster": f"spk{i % 2}",
                                          "meta": json.dumps({"entities": e})} for i, (t, e) in enumerate(refs)]),
                   folder / f"{condition}.parquet")


def write_preds(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([{"utt_id": u, "hyp": h} for u, h in rows]), path)


def medical(root, out, base_found, lora_found):
    """Four turns of 'take metformin daily', each with one drug entity; `found` of them keep the drug word."""
    refs = [(["take", "metformin", "daily"], [{"category": "drugs", "text": "metformin"}]) for _ in range(4)]
    for condition in ("clean", "phone"):
        write_data(root, "medical", condition, refs)
        for variant, found in (("base", base_found), ("lora", lora_found)):
            write_preds(out / "eval" / variant / f"medical__{condition}.parquet",
                        [(f"medical:u{i}", "take metformin daily" if i < found else "take met forming daily") for i in range(4)])


def us_conv(root, out, base_errors, lora_errors):
    tokens = words(100)
    for condition in ("clean", "phone"):
        write_data(root, "us_conv", condition, [(tokens, []), (tokens, [])])
        for variant, errors in (("base", base_errors), ("lora", lora_errors)):
            write_preds(out / "eval" / variant / f"us_conv__{condition}.parquet",
                        [("us_conv:u0", hyp(tokens, errors[0])), ("us_conv:u1", hyp(tokens, errors[1]))])


def test_s3_drug_recall_gate_passes_at_exactly_the_minimum_and_fails_below(tmp_path):
    s1, out = tmp_path / "s1", tmp_path / "s3"
    medical(s1, out, base_found=1, lora_found=3)                    # 25% -> 75%
    _, gates = report.score_finetune(CFG, s1, out)
    assert gates["drug_recall"]["clean"] == {"pre": 0.25, "post": 0.75, "gain": pytest.approx(0.5), "ok": True}
    medical(s1, out, base_found=1, lora_found=2)                    # 25% -> 50%
    _, gates = report.score_finetune(CFG, s1, out)
    assert gates["drug_recall"]["phone"]["ok"] is False and gates["drug_recall"]["phone"]["post"] == 0.5


def test_s3_us_conv_gate_allows_half_a_point_and_no_more(tmp_path):
    s1, out = tmp_path / "s1", tmp_path / "s3"
    us_conv(s1, out, base_errors=(10, 10), lora_errors=(10, 11))       # 20 -> 21 errors in 200 words: +0.5%
    _, gates = report.score_finetune(CFG, s1, out)
    assert gates["us_conv"]["clean"]["ok"] is True and gates["us_conv"]["clean"]["delta"] == pytest.approx(0.005)
    us_conv(s1, out, base_errors=(10, 10), lora_errors=(11, 11))       # +1.0%
    _, gates = report.score_finetune(CFG, s1, out)
    assert gates["us_conv"]["phone"]["ok"] is False


def test_s3_finetune_rows_pair_the_lora_row_with_the_base_row(tmp_path):
    s1, out = tmp_path / "s1", tmp_path / "s3"
    medical(s1, out, base_found=1, lora_found=3)
    rows, _ = report.score_finetune(CFG, s1, out)
    clean = [r for r in rows if r[1] == "clean"]
    assert [r[2] for r in clean] == ["base", "lora"] and clean[0][8] == 4 and clean[0][7] == 1 and clean[1][7] == 3      # drug words found / total
    assert clean[1][13] != "" and clean[0][13] == ""                                                                   # the change sits on the lora row


def test_s3_a_slice_without_both_prediction_files_is_not_scored(tmp_path):
    s1, out = tmp_path / "s1", tmp_path / "s3"
    medical(s1, out, base_found=1, lora_found=3)
    (out / "eval" / "lora" / "medical__phone.parquet").unlink()
    rows, gates = report.score_finetune(CFG, s1, out)
    assert {r[1] for r in rows} == {"clean"} and set(gates["drug_recall"]) == {"clean"}


def test_s3_prompt_rows_compare_the_biased_run_with_the_sprint_1_prediction_of_the_same_model(tmp_path):
    s1, out = tmp_path / "s1", tmp_path / "s3"
    refs = [(["take", "metformin", "daily"], [{"category": "drugs", "text": "metformin"}]) for _ in range(4)]
    write_data(s1, "medical", "clean", refs)
    write_preds(s1 / "preds" / "qwen3-asr-1.7b" / "medical__clean.parquet", [(f"medical:u{i}", "take met forming daily") for i in range(4)])
    write_preds(out / "prompt" / "qwen3-asr-1.7b" / "medical__clean.parquet", [(f"medical:u{i}", "take metformin daily") for i in range(4)])
    rows = report.score_prompt(CFG, s1, out)
    assert [r[3] for r in rows] == ["none", "biased"] and rows[0][8] == 0 and rows[1][8] == 4          # drug words found: 0 then 4
    assert float(rows[0][5]) > float(rows[1][5]) == 0.0                                               # WER falls to 0
