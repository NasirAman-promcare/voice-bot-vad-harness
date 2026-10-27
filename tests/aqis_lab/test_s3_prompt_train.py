"""WP-1.3 workstreams B and C: the pure parts of prompt biasing and the LoRA pilot (term lists, splits, formats, settings)."""
import collections

import pytest

from aqis_lab.cascade import confidence, prompt_bias, train_data, train_lora

ENTITIES = [
    {"cluster": "s1", "category": "drugs", "text": "Metformin"},
    {"cluster": "s1", "category": "drugs", "text": "metformin"},
    {"cluster": "s2", "category": "drugs", "text": "Atorvastatin"},
    {"cluster": "s2", "category": "clinical_findings", "text": "chest pain"},
    {"cluster": "s3", "category": "drugs", "text": "Lisinopril"},
    {"cluster": "s3", "category": "drugs", "text": "metformin"},
    {"cluster": "evalspk", "category": "drugs", "text": "Warfarin"},
    {"cluster": "evalspk", "category": "drugs", "text": "Warfarin"},
]


# ---- workstream B -------------------------------------------------------------------------------------------------
def test_s3_bias_terms_count_the_chosen_category_case_insensitively_most_frequent_first():
    terms = prompt_bias.bias_terms(ENTITIES, exclude_clusters=set(), max_terms=10, category="drugs")
    assert terms == ["metformin", "warfarin", "atorvastatin", "lisinopril"]           # 3, 2, then 1 and 1 alphabetically


def test_s3_bias_terms_never_come_from_the_evaluated_speakers():
    terms = prompt_bias.bias_terms(ENTITIES, exclude_clusters={"evalspk"}, max_terms=10, category="drugs")
    assert "warfarin" not in terms and terms[0] == "metformin"


def test_s3_bias_terms_stop_at_max_terms():
    assert prompt_bias.bias_terms(ENTITIES, set(), 2, "drugs") == ["metformin", "warfarin"]


def test_s3_term_text_drops_whole_terms_from_the_end_to_fit_the_limit():
    assert prompt_bias.terms_text(["metformin", "warfarin", "lisinopril"], max_chars=100) == "metformin, warfarin, lisinopril"
    assert prompt_bias.terms_text(["metformin", "warfarin", "lisinopril"], max_chars=20) == "metformin, warfarin"
    assert prompt_bias.terms_text(["metformin"], max_chars=3) == ""


def test_s3_granite_and_qwen_prompts_follow_their_cards():
    text = "metformin, warfarin"
    assert prompt_bias.granite_prompt(text) == "<|audio|>transcribe the speech to text. Keywords: metformin, warfarin"
    assert prompt_bias.qwen_context(text) == "Medication and clinical terms: metformin, warfarin"
    assert prompt_bias.granite_prompt("") == "<|audio|>transcribe the speech with proper punctuation and capitalization."
    assert prompt_bias.qwen_context("") == ""


# ---- workstream C: data ---------------------------------------------------------------------------------------------
def items(n_clusters=20, per=5):
    return [{"utt_id": f"u{c}-{k}", "cluster": f"spk{c}", "text": f"text {c} {k}"} for c in range(n_clusters) for k in range(per)]


def test_s3_train_and_validation_share_no_speaker_and_neither_touches_the_evaluated_ones():
    split = train_data.split_train(items(), eval_clusters={"spk0", "spk1"}, eval_utt_ids={"u2-0"}, val_fraction=0.2, seed=5)
    train_c, val_c = {x["cluster"] for x in split.train}, {x["cluster"] for x in split.val}
    assert not train_c & val_c and not (train_c | val_c) & {"spk0", "spk1"}
    assert "u2-0" not in {x["utt_id"] for x in split.train + split.val}
    assert len(val_c) == round(0.2 * 18) and len(split.train) + len(split.val) == 18 * 5 - 1


def test_s3_split_is_deterministic_and_independent_of_input_order():
    a = train_data.split_train(items(), set(), set(), 0.25, seed=1)
    b = train_data.split_train(list(reversed(items())), set(), set(), 0.25, seed=1)
    assert sorted(x["utt_id"] for x in a.val) == sorted(x["utt_id"] for x in b.val)


def test_s3_split_with_too_few_speakers_for_a_validation_set_is_an_error():
    with pytest.raises(train_data.TrainDataError, match="speakers"):
        train_data.split_train(items(n_clusters=2), set(), set(), 0.2, seed=1)


def test_s3_augmentation_choice_is_stable_and_follows_the_mix():
    mix = {"clean": 0.5, "phone": 0.3, "noise_10": 0.2}
    assert train_data.augmentation_condition("u1", mix, seed=3) == train_data.augmentation_condition("u1", mix, seed=3)
    counts = collections.Counter(train_data.augmentation_condition(f"u{i}", mix, seed=3) for i in range(4000))
    assert {k: counts[k] / 4000 for k in mix} == pytest.approx(mix, abs=0.03)


def test_s3_training_target_has_the_language_prefix_qwen_was_trained_with():
    assert train_data.training_target("Take two tablets") == "language English<asr_text>Take two tablets"


# ---- workstream C: LoRA settings -----------------------------------------------------------------------------------
LORA = {"r": 16, "alpha": 32, "dropout": 0.05, "target_modules": r".*thinker\.model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)"}


def test_s3_lora_settings_are_r16_alpha32_on_the_language_model_layers():
    got = train_lora.lora_settings(LORA)
    assert (got["r"], got["lora_alpha"], got["lora_dropout"], got["bias"], got["task_type"]) == (16, 32, 0.05, "none", "CAUSAL_LM")
    assert got["target_modules"] == LORA["target_modules"]


def test_s3_target_pattern_matches_text_layers_and_not_the_audio_tower():
    names = ["thinker.model.layers.0.self_attn.q_proj", "thinker.model.layers.27.mlp.down_proj",
             "thinker.audio_tower.layers.0.self_attn.q_proj", "thinker.lm_head", "thinker.model.layers.3.input_layernorm"]
    assert train_lora.matching_modules(names, LORA["target_modules"]) == names[:2]


def test_s3_a_pattern_that_matches_nothing_stops_the_run():
    with pytest.raises(train_lora.TrainError, match="matches no module"):
        train_lora.require_targets(["a.b", "c.d"], r".*nothing.*")
    assert train_lora.require_targets(["x.q_proj"], r".*q_proj") == ["x.q_proj"]


def test_s3_qlora_loads_the_base_in_4_bit_nf4_with_bf16_compute():
    assert train_lora.quantization_settings() == {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4",
                                                   "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": True}


def test_s3_early_stopping_watches_the_validation_loss_and_restores_the_best_checkpoint():
    got = train_lora.early_stopping_settings({"patience": 3, "eval_steps": 25, "min_delta": 0.001})
    assert got["training_args"] == {"eval_strategy": "steps", "eval_steps": 25, "save_strategy": "steps", "save_steps": 25,
                                    "load_best_model_at_end": True, "metric_for_best_model": "eval_loss", "greater_is_better": False}
    assert got["callback"] == {"early_stopping_patience": 3, "early_stopping_threshold": 0.001}


# ---- confidence features ---------------------------------------------------------------------------------------------
def test_s3_confidence_summary_is_the_mean_and_minimum_of_token_confidences():
    assert confidence.summarise([0.9, 0.5, 0.7]) == {"confidence": pytest.approx(0.7), "min_confidence": 0.5, "tokens": 3}


def test_s3_a_turn_without_tokens_has_no_confidence_and_is_not_invented():
    assert confidence.summarise([]) == {"confidence": None, "min_confidence": None, "tokens": 0}


def test_s3_numbers_hint_prompts_keep_the_card_prompt_and_add_the_hint():
    hint = "Spoken numbers are written as digits."
    assert prompt_bias.granite_hint_prompt(hint) == (
        "<|audio|>transcribe the speech with proper punctuation and capitalization. Spoken numbers are written as digits.")
    assert prompt_bias.qwen_hint_context(hint) == hint
