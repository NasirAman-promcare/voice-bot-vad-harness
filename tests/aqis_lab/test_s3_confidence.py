"""WP-1.3 fix: token confidences without running out of GPU memory, one decoding setup per method, finished cells skipped.

The first Colab run saved the 300 turns of us_conv/phone, then ran out of memory (22 GB L4, 17 GB held by PyTorch) in the next
file: NeMo kept alignments, which keep every logit, and the decoding was set up again for every batch.
"""
import contextlib
import copy
from pathlib import Path
from types import SimpleNamespace as Ns

import pytest
import yaml

from aqis_lab.cascade import config as cascade_config
from aqis_lab.cascade import confidence

REPO = Path(__file__).resolve().parents[2]


class FakeOmegaconf:
    @staticmethod
    @contextlib.contextmanager
    def open_dict(cfg):
        yield cfg


class FakeTorch:
    def __init__(self):
        self.cache_cleared = 0
        self.cuda = Ns(empty_cache=self._clear)

    def _clear(self):
        self.cache_cleared += 1

    @staticmethod
    @contextlib.contextmanager
    def inference_mode():
        yield


class FakeModel:
    def __init__(self, confs_by_method):
        self.cfg = Ns(decoding=Ns(preserve_alignments=True, confidence_cfg=Ns(
            preserve_frame_confidence=False, preserve_token_confidence=False, exclude_blank=False, aggregation="min",
            method_cfg=Ns(name="unset"))))
        self.confs_by_method = confs_by_method
        self.strategies, self.transcribed = [], []

    def change_decoding_strategy(self, decoding):
        c = decoding.confidence_cfg
        self.strategies.append({"alignments": decoding.preserve_alignments, "frame": c.preserve_frame_confidence,
                                "token": c.preserve_token_confidence, "blank": c.exclude_blank, "aggregation": c.aggregation,
                                "method": c.method_cfg.name})

    def transcribe(self, paths, batch_size, return_hypotheses):
        self.transcribed.append({"paths": list(paths), "batch_size": batch_size, "hyps": return_hypotheses})
        method = self.strategies[-1]["method"]
        return [Ns(token_confidence=self.confs_by_method[method].get(p)) for p in paths]


CONFS = {"max_prob": {"a.wav": [0.9, 0.7], "b.wav": [0.5]}, "entropy": {"a.wav": [0.8], "b.wav": None}}


def test_s3_decoding_keeps_confidences_but_not_alignments():
    model = FakeModel(CONFS)
    confidence.configure(model, "max_prob", omegaconf=FakeOmegaconf)
    assert model.strategies == [{"alignments": False, "frame": True, "token": True, "blank": True, "aggregation": "mean",
                                 "method": "max_prob"}]


def test_s3_token_confidences_pass_the_batch_size_and_free_the_gpu_cache():
    model, torch = FakeModel(CONFS), FakeTorch()
    confidence.configure(model, "max_prob", omegaconf=FakeOmegaconf)
    got = confidence.token_confidences(model, ["a.wav", "b.wav"], batch_size=16, torch=torch)
    assert got == [[0.9, 0.7], [0.5]] and model.transcribed == [{"paths": ["a.wav", "b.wav"], "batch_size": 16, "hyps": True}]
    assert torch.cache_cleared == 1


def test_s3_a_hypothesis_without_token_confidences_gives_an_empty_list_not_a_guess():
    model = FakeModel(CONFS)
    confidence.configure(model, "entropy", omegaconf=FakeOmegaconf)
    assert confidence.token_confidences(model, ["a.wav", "b.wav"], 4, torch=FakeTorch()) == [[0.8], []]


def test_s3_a_cell_sets_up_each_method_once_however_many_turns_it_has():
    model = FakeModel(CONFS)
    got = confidence.confidences_for_cell(model, ["a.wav", "b.wav"], {"confidence": "max_prob", "entropy": "entropy"}, 16,
                                          omegaconf=FakeOmegaconf, torch=FakeTorch())
    assert [s["method"] for s in model.strategies] == ["max_prob", "entropy"] and len(model.transcribed) == 2
    assert got == {"confidence": [[0.9, 0.7], [0.5]], "entropy": [[0.8], []]}


def test_s3_a_cell_is_finished_only_when_every_turn_has_both_scores():
    existing = {"k1": {"key": "k1", "confidence": 0.9, "entropy": 0.8}, "k2": {"key": "k2", "confidence": 0.7, "entropy": None}}
    assert confidence.cell_done(existing, ["k1"]) is True
    assert confidence.cell_done(existing, ["k1", "k2"]) is False          # k2 has no entropy
    assert confidence.cell_done(existing, ["k1", "k3"]) is False          # k3 was never scored
    assert confidence.cell_done({}, ["k1"]) is False


def test_s3_no_confidences_at_all_is_an_error_and_a_few_missing_is_not():
    all_empty = {"k1": {"confidence": None, "entropy": None}, "k2": {"confidence": None, "entropy": None}}
    with pytest.raises(confidence.ConfidenceError, match="us_conv:phone"):
        confidence.require_coverage(all_empty, "us_conv:phone")
    some = {"k1": {"confidence": 0.9, "entropy": 0.8}, "k2": {"confidence": None, "entropy": None}}
    assert confidence.require_coverage(some, "us_conv:phone") == pytest.approx(0.5)


def test_s3_the_config_names_a_positive_confidence_batch_size(tmp_path):
    raw = yaml.safe_load((REPO / "config" / "aqis_lab" / "s3.yaml").read_text(encoding="utf-8"))
    assert raw["cascade"]["confidence"]["batch_size"] == 16
    bad = copy.deepcopy(raw)
    bad["cascade"]["confidence"]["batch_size"] = 0
    target = tmp_path / "s3.yaml"
    target.write_text(yaml.safe_dump(bad, sort_keys=False), encoding="utf-8")
    with pytest.raises(cascade_config.ConfigError, match="batch_size"):
        cascade_config.load_config(target)
