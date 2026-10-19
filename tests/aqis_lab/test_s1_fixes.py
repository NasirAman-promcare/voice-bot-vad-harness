"""WP-1.1 fixes found by the first Colab runs: unique Earnings-22 IDs, the committed HarperValleyBank rules, the
GPU-name lookup, and the two model-load compatibility helpers."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from aqis_lab.bench import config as bench_config
from aqis_lab.bench import models, sources

S1_YAML = Path(__file__).resolve().parents[2] / "config" / "aqis_lab" / "s1.yaml"


def data_row(utt_id):
    return {"utt_id": utt_id, "source": "s", "licence": "L", "audio": b"\0\0" * 16000, "n_samples": 16000,
            "duration_s": 1.0, "ref_text": "Hi.", "ref_clean": "Hi.", "speaker": "a", "cluster": "a", "meta": "{}"}


def earnings_source():
    source = sources.Earnings22Source.__new__(sources.Earnings22Source)
    source.name, source.licence = "earnings22", "CC-BY-SA-4.0"
    return source


# ---- unique utterance IDs --------------------------------------------------------------------------------------
def test_s1_earnings22_chunks_of_one_call_get_distinct_ids():
    source = earnings_source()
    rows = [{"file_id": "4320209", "segment_id": "71", "transcription": "we grew 5 percent", "start_ts": 0.0, "end_ts": 6.0},
            {"file_id": "4320211", "segment_id": "71", "transcription": "costs fell 3 percent", "start_ts": 0.0, "end_ts": 6.0},
            {"file_id": "4320209", "segment_id": "72", "transcription": "next slide please", "start_ts": 6.0, "end_ts": 9.0}]
    ids = [source.row_to_utt("test", i, row)["utt_id"] for i, row in enumerate(rows)]
    assert len(set(ids)) == 3
    assert source.row_to_utt("test", 0, rows[0])["meta"]["segment_id"] == "71"    # the published chunk number is kept


def test_s1_repeated_utterance_ids_are_an_error():
    sources.check_unique_ids(["a", "b", "c"], "x")
    with pytest.raises(sources.DataError, match=r"x: utterance IDs repeat \(1\), for example numbers:earnings22-71"):
        sources.check_unique_ids(["numbers:earnings22-71", "b", "numbers:earnings22-71"], "x")
    with pytest.raises(sources.DataError, match="repeat"):
        sources.check_data_rows([data_row("u1"), data_row("u2"), data_row("u1")])
    sources.check_data_rows([data_row("u1"), data_row("u2")])


# ---- the committed HarperValleyBank cleaning rules -------------------------------------------------------------
def hvb_rules():
    return bench_config.load_config(S1_YAML).sources["harper_valley_bank"]["clean"]


@pytest.mark.parametrize("tag", ["baby", "cough", "dogs", "kids", "laughter", "music", "noise", "ringing"])
def test_s1_hvb_rules_strip_each_bracketed_sound(tag):
    result = sources.clean_reference(f"yes [{tag}] my number is five", hvb_rules())
    assert result.text == "yes my number is five" and result.dropped is None and result.unknown_tags == ()


@pytest.mark.parametrize("raw,reason", [("so [unintelligible] thanks", "unintelligible"), ("a <unk> b", "unk")])
def test_s1_hvb_rules_drop_unintelligible_turns(raw, reason):
    assert sources.clean_reference(raw, hvb_rules()).dropped == reason


# ---- model-load compatibility helpers ----------------------------------------------------------------------------
def test_s1_torchao_names_are_added_only_when_missing():
    functional = SimpleNamespace()
    assert models.add_torchao_symbols(functional) == ["ScalingType", "scaled_grouped_mm"]
    assert functional.scaled_grouped_mm is None and isinstance(functional.ScalingType, type)
    assert models.add_torchao_symbols(functional) == []
    kept = SimpleNamespace(ScalingType="real", scaled_grouped_mm="real")
    assert models.add_torchao_symbols(kept) == [] and kept.ScalingType == "real"


def test_s1_validation_ds_is_filled_only_when_none():
    # omegaconf comes with NeMo and is absent here, so the helper is given a minimal object with the two calls it makes
    omegaconf = SimpleNamespace(open_dict=lambda cfg: nullcontext(), OmegaConf=SimpleNamespace(create=dict))
    missing = SimpleNamespace(cfg=SimpleNamespace(validation_ds=None))
    models.ensure_validation_ds(missing, omegaconf)
    assert missing.cfg.validation_ds == {}
    kept = SimpleNamespace(cfg=SimpleNamespace(validation_ds={"batch_size": 4}))
    models.ensure_validation_ds(kept, omegaconf)
    assert kept.cfg.validation_ds == {"batch_size": 4}
    no_cfg = SimpleNamespace(cfg=None)
    models.ensure_validation_ds(no_cfg, omegaconf)
    assert no_cfg.cfg is None


# ---- the GPU name ------------------------------------------------------------------------------------------------
def test_s1_machine_block_names_the_gpu_under_the_key_the_runner_reads():
    from aqis_lab import platform as lp
    info = lp.MachineInfo("colab", "NVIDIA L4", "cpu", "x86_64", "os", "3.13.0", ())
    assert info.block()["gpu"] == "NVIDIA L4" and "gpu_type" not in info.block()
