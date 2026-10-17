"""WP-1.1 ruler test 10 and the strict config: prediction and data rows carry every column; s1.yaml loads strictly."""
import copy
from pathlib import Path

import pytest
import yaml

from aqis_lab.bench import config as bench_config
from aqis_lab.bench import run, sources

REPO = Path(__file__).resolve().parents[2]
S1_YAML = REPO / "config" / "aqis_lab" / "s1.yaml"

FACTS = {"model": "parakeet-tdt-0.6b-v2", "hf_id": "nvidia/parakeet-tdt-0.6b-v2", "revision": "a" * 40,
         "stack": "nemo", "versions": '{"nemo": "3.0.0"}', "dtype": "bf16", "gpu": "NVIDIA L4",
         "git_commit": "b" * 40, "seed": 20261019, "utc": "2026-10-19T08:00:00Z"}


def pred_rows(n=3):
    return run.make_pred_rows(FACTS, [f"u{i}" for i in range(n)], [f"text {i}" for i in range(n)],
                              batch_ids=[0] * n, batch_audio_s=[12.5] * n, batch_wall_s=[0.4] * n)


# ---- 10. result rows -----------------------------------------------------------------------------------------
def test_s1_prediction_rows_have_every_column_of_the_spec():
    expected = ["utt_id", "model", "hf_id", "revision", "stack", "hyp", "batch_id", "batch_audio_s", "batch_wall_s",
                "versions", "dtype", "gpu", "git_commit", "seed", "utc"]
    assert list(run.PRED_COLUMNS) == expected
    rows = pred_rows()
    assert all(list(r) == expected for r in rows)
    run.check_pred_rows(rows)


@pytest.mark.parametrize("column", run.PRED_COLUMNS)
def test_s1_prediction_row_missing_a_column_fails(column):
    rows = pred_rows()
    del rows[1][column]
    with pytest.raises(run.RowError, match=column):
        run.check_pred_rows(rows)


def test_s1_prediction_row_with_an_empty_trace_field_fails():
    for column in ("revision", "git_commit", "gpu", "model"):
        rows = pred_rows()
        rows[0][column] = ""
        with pytest.raises(run.RowError, match=column):
            run.check_pred_rows(rows)


def test_s1_prediction_row_with_an_unlisted_column_fails():
    rows = pred_rows()
    rows[0]["extra"] = 1
    with pytest.raises(run.RowError, match="extra"):
        run.check_pred_rows(rows)


def test_s1_make_pred_rows_refuses_fields_missing_from_the_run_facts():
    facts = {k: v for k, v in FACTS.items() if k != "gpu"}
    with pytest.raises(run.RowError, match="gpu"):
        run.make_pred_rows(facts, ["u"], ["x"], [0], [1.0], [0.1])


def test_s1_data_rows_have_every_column_of_the_spec():
    expected = ["utt_id", "source", "licence", "audio", "n_samples", "duration_s", "ref_text", "ref_clean",
                "speaker", "cluster", "meta"]
    assert list(sources.DATA_COLUMNS) == expected
    row = {"utt_id": "x", "source": "edacc", "licence": "CC-BY-SA-4.0", "audio": b"\0\0" * 16000, "n_samples": 16000,
           "duration_s": 1.0, "ref_text": "Hi.", "ref_clean": "Hi.", "speaker": "s", "cluster": "s", "meta": "{}"}
    sources.check_data_rows([row])
    for column in expected:
        bad = dict(row)
        del bad[column]
        with pytest.raises(sources.DataError, match=column):
            sources.check_data_rows([bad])


def test_s1_data_row_audio_length_must_match_n_samples():
    row = {"utt_id": "x", "source": "edacc", "licence": "L", "audio": b"\0\0" * 100, "n_samples": 16000,
           "duration_s": 1.0, "ref_text": "Hi.", "ref_clean": "Hi.", "speaker": "s", "cluster": "s", "meta": "{}"}
    with pytest.raises(sources.DataError, match="n_samples"):
        sources.check_data_rows([row])


# ---- resumable prediction files ------------------------------------------------------------------------------
def test_s1_prediction_file_roundtrip_and_missing_ids(tmp_path):
    path = tmp_path / "preds" / "m" / "us_conv__clean.parquet"
    assert run.missing_ids(path, ["u0", "u1", "u2"]) == ["u0", "u1", "u2"]
    run.write_preds(path, pred_rows(2))
    assert run.missing_ids(path, ["u0", "u1", "u2"]) == ["u2"]
    assert [r["utt_id"] for r in run.read_preds(path)] == ["u0", "u1"]
    assert not list(path.parent.glob("*.partial"))


def test_s1_merging_new_rows_keeps_the_old_ones_and_refuses_another_revision(tmp_path):
    path = tmp_path / "us_conv__clean.parquet"
    run.write_preds(path, pred_rows(2))
    more = run.make_pred_rows(FACTS, ["u2"], ["text 2"], [1], [3.0], [0.1])
    run.merge_preds(path, more)
    assert [r["utt_id"] for r in run.read_preds(path)] == ["u0", "u1", "u2"]
    other = run.make_pred_rows(dict(FACTS, revision="c" * 40), ["u3"], ["x"], [2], [1.0], [0.1])
    with pytest.raises(run.RowError, match="revision"):
        run.merge_preds(path, other)


def test_s1_merging_a_duplicate_utterance_is_an_error(tmp_path):
    path = tmp_path / "x.parquet"
    run.write_preds(path, pred_rows(2))
    with pytest.raises(run.RowError, match="u1"):
        run.merge_preds(path, run.make_pred_rows(FACTS, ["u1"], ["again"], [3], [1.0], [0.1]))


# ---- strict configuration ------------------------------------------------------------------------------------
def load_raw():
    return yaml.safe_load(S1_YAML.read_text(encoding="utf-8"))


def write(tmp_path, data):
    path = tmp_path / "s1.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_s1_the_committed_config_loads_and_hashes_its_content():
    cfg = bench_config.load_config(S1_YAML)
    assert cfg.seed == 20261019 and cfg.normaliser == "main"
    assert cfg.caller_slices == ["us_conv", "sa_conv", "sa_india", "medical", "numbers", "us_phone"]
    assert set(cfg.models) >= {"whisper-large-v3", "canary-qwen-2.5b", "voxtral-realtime-4b"} and len(cfg.models) == 9
    assert cfg.bootstrap == {"resamples": 1000, "unit": "speaker", "ci": 0.95}
    assert cfg.conditions_for("us_phone") == ["native"] and cfg.conditions_for("anchor") == ["clean", "phone"]
    assert cfg.conditions_for("us_conv") == cfg.default_conditions
    assert len(cfg.hash) == 64 and cfg.hash == bench_config.load_config(S1_YAML).hash


def test_s1_config_hash_changes_when_a_value_changes(tmp_path):
    data = load_raw()
    data["seed"] = 1
    assert bench_config.load_config(write(tmp_path, data)).hash != bench_config.load_config(S1_YAML).hash


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.update(surprise=1), "surprise"),
    (lambda d: d.update(schema="s1-v2"), "schema"),
    (lambda d: d.pop("seed"), "seed"),
    (lambda d: d["slices"]["us_conv"].update(source="nowhere"), "nowhere"),
    (lambda d: d["slices"]["us_conv"].update(conditions=["studio"]), "studio"),
    (lambda d: d["models"]["whisper-large-v3"].update(stack="onnx"), "stack"),
    (lambda d: d["models"]["whisper-large-v3"].pop("hf"), "hf"),
    (lambda d: d["models"]["whisper-large-v3"].update(role="fast"), "role"),
    (lambda d: d["caller_slices"].append("ghost"), "ghost"),
    (lambda d: d["target_conditions"].append("studio"), "studio"),
    (lambda d: d["stages"]["anchor"]["models"].append("ghost-model"), "ghost-model"),
    (lambda d: d["bootstrap"].update(unit="word"), "unit"),
    (lambda d: d["anchor_published_test_other_wer"].pop("cohere-transcribe-2b"), "cohere-transcribe-2b"),
])
def test_s1_config_rejects_what_it_does_not_understand(tmp_path, mutate, message):
    data = copy.deepcopy(load_raw())
    mutate(data)
    with pytest.raises(bench_config.ConfigError, match=message):
        bench_config.load_config(write(tmp_path, data))


def test_s1_config_missing_file_is_an_error(tmp_path):
    with pytest.raises(bench_config.ConfigError, match="s1.yaml"):
        bench_config.load_config(tmp_path / "s1.yaml")


# ---- the GPU runner stays light --------------------------------------------------------------------------------
def test_s1_runner_modules_import_no_scorer_and_no_ml_library():
    import subprocess
    import sys
    code = ("import sys; import aqis_lab.bench.run, aqis_lab.bench.models, aqis_lab.bench.config, aqis_lab.bench.__main__; "
            "bad = [m for m in ('whisper_normalizer', 'jiwer', 'torch', 'transformers', 'nemo', 'soxr', 'matplotlib', "
            "'aqis_lab.scoring', 'aqis_lab.packs', 'aqis_lab.bench.score', 'aqis_lab.bench.select') if m in sys.modules]; "
            "print(bad); sys.exit(1 if bad else 0)")
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
