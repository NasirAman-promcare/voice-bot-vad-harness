"""WP-1.3 closeout: the four fixes the Colab run needed, so that main reproduces what ran.

1. NeMo's decoding config can lack confidence_cfg (or its method_cfg): it is assigned whole, not reached through missing keys.
2. Eka's 300 evaluated turns were drawn from every speaker, so excluding the evaluated speakers leaves nobody to train on: when that
   leaves fewer than MIN_SPEAKERS speakers, only the evaluated turns are excluded, and the split says speakers overlap.
3. Qwen3ASRForConditionalGeneration has no get/set_input_embeddings, which PEFT's k-bit preparation calls: they delegate to `thinker`.
4. Training wav files live beside train.jsonl on Drive, not in scratch that a dropped session loses (a path, checked in the source).
"""
import contextlib
import inspect
from types import SimpleNamespace as Ns

import pytest

from aqis_lab.cascade import confidence, train_data, train_lora


# ---- 1. confidence_cfg assigned whole ----------------------------------------------------------------------------
class OpenDict:
    @staticmethod
    @contextlib.contextmanager
    def open_dict(cfg):
        yield cfg


class RecordingModel:
    def __init__(self, decoding):
        self.cfg = Ns(decoding=decoding)
        self.seen = []

    def change_decoding_strategy(self, decoding):
        self.seen.append(decoding)


COMPLETE = {"preserve_frame_confidence": True, "preserve_token_confidence": True, "exclude_blank": True, "aggregation": "mean",
            "method_cfg": {"name": "entropy"}}


def test_s3_a_decoding_config_without_confidence_cfg_gets_the_whole_dictionary():
    decoding = Ns(preserve_alignments=True, confidence_cfg=None)
    model = RecordingModel(decoding)
    confidence.configure(model, "entropy", omegaconf=OpenDict)
    assert decoding.confidence_cfg == COMPLETE and decoding.preserve_alignments is False and model.seen == [decoding]


def test_s3_a_decoding_config_with_no_confidence_cfg_key_at_all_gets_it_too():
    decoding = Ns(preserve_alignments=True)
    confidence.configure(RecordingModel(decoding), "max_prob", omegaconf=OpenDict)
    assert decoding.confidence_cfg == dict(COMPLETE, method_cfg={"name": "max_prob"})


def test_s3_a_confidence_cfg_without_method_cfg_gets_one_and_the_other_keys_are_set():
    cfg = Ns(preserve_frame_confidence=False, preserve_token_confidence=False, exclude_blank=False, aggregation="min", method_cfg=None)
    decoding = Ns(preserve_alignments=True, confidence_cfg=cfg)
    confidence.configure(RecordingModel(decoding), "entropy", omegaconf=OpenDict)
    assert (cfg.preserve_frame_confidence, cfg.preserve_token_confidence, cfg.exclude_blank, cfg.aggregation) == (True, True, True, "mean")
    assert cfg.method_cfg == {"name": "entropy"}


# ---- 2. the split when every speaker was evaluated -------------------------------------------------------------------
def items(n_clusters=10, per=6):
    return [{"utt_id": f"u{c}-{k}", "cluster": f"spk{c}", "text": "t"} for c in range(n_clusters) for k in range(per)]


def test_s3_when_every_speaker_was_evaluated_only_the_evaluated_turns_are_left_out():
    everyone = {f"spk{c}" for c in range(10)}
    evaluated = {"u0-0", "u1-0", "u2-0", "u3-0"}
    split = train_data.split_train(items(), eval_clusters=everyone, eval_utt_ids=evaluated, val_fraction=0.2, seed=3)
    used = {x["utt_id"] for x in split.train + split.val}
    assert not used & evaluated and len(used) == 60 - 4
    assert not {x["cluster"] for x in split.train} & {x["cluster"] for x in split.val}               # validation still has its own speakers
    assert len({x["cluster"] for x in split.val}) == 2


def test_s3_the_fallback_says_that_training_speakers_overlap_the_evaluated_ones():
    everyone = {f"spk{c}" for c in range(10)}
    split = train_data.split_train(items(), everyone, {"u0-0"}, 0.2, seed=3)
    assert any("overlap" in note and "10" in note for note in split.notes), split.notes


def test_s3_with_enough_speakers_left_the_evaluated_speakers_are_still_excluded_whole():
    split = train_data.split_train(items(20), {"spk0", "spk1"}, set(), 0.2, seed=3)
    assert not {x["cluster"] for x in split.train + split.val} & {"spk0", "spk1"}
    assert not any("overlap" in note for note in split.notes)


def test_s3_the_fallback_still_needs_enough_speakers_overall():
    with pytest.raises(train_data.TrainDataError, match="speakers"):
        train_data.split_train(items(3), {"spk0", "spk1", "spk2"}, set(), 0.2, seed=3)


# ---- 3. the input embeddings shim -----------------------------------------------------------------------------------
class Thinker:
    def __init__(self):
        self.embeddings = "embeddings-of-thinker"

    def get_input_embeddings(self):
        return self.embeddings

    def set_input_embeddings(self, value):
        self.embeddings = value

    def forward(self, **kwargs):
        return kwargs


def make_outer():
    class Outer:
        def __init__(self):
            self.thinker = Thinker()
    return Outer


def test_s3_the_outer_model_delegates_input_embeddings_to_its_thinker():
    outer = make_outer()()
    train_lora.patch_input_embeddings(outer)
    assert outer.get_input_embeddings() == "embeddings-of-thinker"
    outer.set_input_embeddings("new")
    assert outer.thinker.embeddings == "new" and outer.get_input_embeddings() == "new"


def test_s3_patching_twice_is_harmless_and_a_model_without_a_thinker_is_refused():
    outer = make_outer()()
    train_lora.patch_input_embeddings(outer)
    train_lora.patch_input_embeddings(outer)
    assert outer.get_input_embeddings() == "embeddings-of-thinker"
    with pytest.raises(train_lora.TrainError, match="thinker"):
        train_lora.patch_input_embeddings(Ns())


def test_s3_training_calls_the_shim_before_the_k_bit_preparation():
    source = inspect.getsource(train_lora.train)
    assert source.index("patch_input_embeddings(model)") < source.index("prepare_model_for_kbit_training")


# ---- 4. where the training audio is written -----------------------------------------------------------------------
def test_s3_training_wav_files_are_written_under_the_output_folder_not_scratch():
    source = inspect.getsource(train_data.prepare)
    assert 'folder = Path(out_dir) / "train" / "audio"' in source and "s3_train" not in source
