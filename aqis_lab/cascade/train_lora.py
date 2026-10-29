"""Sprint 3 workstream C: a self-contained QLoRA fine-tuning of Qwen3-ASR 1.7B with early stopping, and its evaluation.

CAPABILITIES:
  CAP-S3-070: lora_settings() gives the peft LoraConfig arguments (r 16, alpha 32 from the config, on the language-model layers only);
    matching_modules() and require_targets() count the modules a pattern matches and stop the run when it matches none;
    quantization_settings() is the 4-bit NF4 setup with bfloat16 compute and double quantisation; early_stopping_settings() gives the
    evaluation, saving and early-stopping arguments that watch the validation loss and restore the best checkpoint [tests:
    test_s3_lora_settings_are_r16_alpha32_on_the_language_model_layers,
    test_s3_target_pattern_matches_text_layers_and_not_the_audio_tower, test_s3_a_pattern_that_matches_nothing_stops_the_run,
    test_s3_qlora_loads_the_base_in_4_bit_nf4_with_bf16_compute,
    test_s3_early_stopping_watches_the_validation_loss_and_restores_the_best_checkpoint]
  CAP-S3-071: train() loads the base model in 4 bit, wraps its language-model layers in LoRA, trains on train.jsonl with the Hugging Face
    Trainer (the collator, label masking and forward patch of Qwen's own finetuning/qwen3_asr_sft.py), stops early on the
    validation loss and saves the adapter (patch_input_embeddings gives the outer model the embedding accessors PEFT's k-bit preparation
    needs) [tests: test_s3_the_outer_model_delegates_input_embeddings_to_its_thinker,
    test_s3_patching_twice_is_harmless_and_a_model_without_a_thinker_is_refused, test_s3_training_calls_the_shim_before_the_k_bit_preparation]; evaluate() transcribes the evaluation slices with the base model and with the merged
    adapter into prediction files [no unit test: they need the model, bitsandbytes and a GPU; the Colab smoke run checks them]
INPUTS AND OUTPUTS: s3 and s1 configs, train.jsonl and val.jsonl from train_data.prepare(); an adapter folder and prediction parquet
  files out; TrainError.
CONTRACTS: brief section 2C (r=16, alpha=32, QLoRA, early stopping); Qwen3-ASR finetuning recipe (system prompt, audio, then
  "language English<asr_text>" + text + eos; labels masked over the prefix).
INVARIANTS:
  - The audio tower is not adapted; a pattern that matches no module stops the run before any training.
  - Training and validation speakers are disjoint from the evaluated slice (train_data.split_train).
  - Evaluation reads the same Sprint 1 data files as the base model's Sprint 1 run.
NOT IN SCOPE:
  - Preparing the data (train_data.py) and scoring (report.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import re
from pathlib import Path

from aqis_lab.bench import lib


class TrainError(RuntimeError):
    """Training or evaluation cannot run as asked."""


def lora_settings(lora):
    return {"r": lora["r"], "lora_alpha": lora["alpha"], "lora_dropout": lora["dropout"], "bias": "none",
            "task_type": "CAUSAL_LM", "target_modules": lora["target_modules"]}


def matching_modules(names, pattern):
    rx = re.compile(pattern)
    return [n for n in names if rx.fullmatch(n)]


def require_targets(names, pattern):
    found = matching_modules(names, pattern)
    if not found:
        raise TrainError(f"the LoRA pattern {pattern!r} matches no module of the model ({len(names)} modules); "
                         f"fix train.lora.target_modules in s3.yaml")
    return found


def quantization_settings():
    return {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": True}


def early_stopping_settings(es):
    return {"training_args": {"eval_strategy": "steps", "eval_steps": es["eval_steps"], "save_strategy": "steps",
                              "save_steps": es["eval_steps"], "load_best_model_at_end": True, "metric_for_best_model": "eval_loss",
                              "greater_is_better": False},
            "callback": {"early_stopping_patience": es["patience"], "early_stopping_threshold": es["min_delta"]}}


# ---- training (GPU) ---------------------------------------------------------------------------------------------
def _patch_outer_forward(model):
    """Qwen's own patch: the outer model forwards to its `thinker`, which takes the labels and returns the loss."""
    cls = model.__class__
    if getattr(cls, "_forward_patched", False):
        return
    if not hasattr(model, "thinker") or not hasattr(model.thinker, "forward"):
        raise TrainError("the Qwen3-ASR model has no `.thinker.forward`; its code differs from the one this script was written for")

    def forward(self, input_ids=None, attention_mask=None, input_features=None, feature_attention_mask=None, labels=None, **kwargs):
        return self.thinker.forward(input_ids=input_ids, attention_mask=attention_mask, input_features=input_features,
                                    feature_attention_mask=feature_attention_mask, labels=labels, **kwargs)
    cls.forward = forward
    cls._forward_patched = True


def patch_input_embeddings(model):
    """PEFT's k-bit preparation calls get/set_input_embeddings on the outer model, which has none: they go to its `thinker`."""
    cls = model.__class__
    if getattr(cls, "_embeddings_patched", False):
        return
    thinker = getattr(model, "thinker", None)
    if thinker is None or not hasattr(thinker, "get_input_embeddings"):
        raise TrainError("the Qwen3-ASR model has no `.thinker.get_input_embeddings`; its code differs from the one this script was written for")

    def get_input_embeddings(self):
        return self.thinker.get_input_embeddings()

    def set_input_embeddings(self, value):
        self.thinker.set_input_embeddings(value)
    cls.get_input_embeddings = get_input_embeddings
    cls.set_input_embeddings = set_input_embeddings
    cls._embeddings_patched = True


def _collator(processor, sample_rate=16000):
    soundfile = lib("soundfile")

    def load(path):
        wav, rate = soundfile.read(path, dtype="float32", always_2d=False)
        if rate != sample_rate:
            raise TrainError(f"{path} is {rate} Hz, training audio is {sample_rate} Hz")
        return wav

    def collate(features):
        prefixes = [f["prefix_text"] for f in features]
        eos = processor.tokenizer.eos_token or ""
        full = [p + f["target"] + eos for p, f in zip(prefixes, features)]
        audios = [load(f["audio"]) for f in features]
        full_inputs = processor(text=full, audio=audios, return_tensors="pt", padding=True, truncation=False)
        prefix_inputs = processor(text=prefixes, audio=audios, return_tensors="pt", padding=True, truncation=False)
        labels = full_inputs["input_ids"].clone()
        for i, length in enumerate(prefix_inputs["attention_mask"].sum(dim=1).tolist()):
            labels[i, :length] = -100
        pad = processor.tokenizer.pad_token_id
        if pad is not None:
            labels[labels == pad] = -100
        full_inputs["labels"] = labels
        return full_inputs
    return collate


def _read_jsonl(path, processor):
    import json
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    prefix = processor.apply_chat_template([[{"role": "system", "content": ""},
                                             {"role": "user", "content": [{"type": "audio", "audio": None}]}]],
                                           add_generation_prompt=True, tokenize=False)[0]
    return [{"audio": r["audio"], "target": r["text"], "prefix_text": prefix} for r in rows]


def train(cfg, s1_cfg, s1_dir, out_dir, repo_root, log=print, smoke=False):
    from aqis_lab.bench import run as s1_run
    torch, transformers, peft = lib("torch"), lib("transformers"), lib("peft")
    qwen_asr, hub = lib("qwen_asr"), lib("huggingface_hub")
    t = cfg.train
    base = t["base"]
    revision = s1_run.revision_for(base, s1_cfg.models[base]["hf"], s1_dir)
    folder = hub.snapshot_download(s1_cfg.models[base]["hf"], revision=revision)
    q = quantization_settings()
    bnb = transformers.BitsAndBytesConfig(load_in_4bit=q["load_in_4bit"], bnb_4bit_quant_type=q["bnb_4bit_quant_type"],
                                          bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=q["bnb_4bit_use_double_quant"])
    wrapper = qwen_asr.Qwen3ASRModel.from_pretrained(folder, dtype=torch.bfloat16, device_map={"": 0}, quantization_config=bnb)
    model, processor = wrapper.model, wrapper.processor
    _patch_outer_forward(model)
    patch_input_embeddings(model)
    model.generation_config = transformers.GenerationConfig.from_model_config(model.config)
    model = peft.prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    targets = require_targets([name for name, _ in model.named_modules()], t["lora"]["target_modules"])
    log(f"LoRA on {len(targets)} modules, for example {targets[0]}")
    model = peft.get_peft_model(model, peft.LoraConfig(**lora_settings(t["lora"])))
    model.print_trainable_parameters()

    data_dir = Path(out_dir) / "train"
    run_dir = Path(out_dir) / ("smoke" if smoke else ".") / "train"          # a smoke run never touches the real checkpoints
    train_rows = _read_jsonl(data_dir / "train.jsonl", processor)[:16 if smoke else None]
    val_rows = _read_jsonl(data_dir / "val.jsonl", processor)[:8 if smoke else None]
    es = early_stopping_settings(dict(t["early_stopping"], eval_steps=2) if smoke else t["early_stopping"])
    o = t["optim"]
    adapter_dir = run_dir / "adapter"
    args = transformers.TrainingArguments(
        output_dir=str(run_dir / "checkpoints"), per_device_train_batch_size=o["batch_size"],
        per_device_eval_batch_size=o["batch_size"], gradient_accumulation_steps=o["grad_acc"], learning_rate=o["lr"],
        num_train_epochs=o["epochs"], max_steps=4 if smoke else -1, warmup_ratio=o["warmup_ratio"], lr_scheduler_type="cosine", logging_steps=5,
        bf16=True, gradient_checkpointing=True, remove_unused_columns=False, report_to="none", save_total_limit=2,
        seed=cfg.seed, dataloader_num_workers=2, **es["training_args"])

    class CastFloatInputsTrainer(transformers.Trainer):
        def _prepare_inputs(self, inputs):
            inputs = super()._prepare_inputs(inputs)
            dtype = getattr(self.model, "dtype", None)
            if dtype is not None:
                for key, value in list(inputs.items()):
                    if torch.is_tensor(value) and value.is_floating_point():
                        inputs[key] = value.to(dtype=dtype)
            return inputs

    trainer = CastFloatInputsTrainer(model=model, args=args, train_dataset=train_rows, eval_dataset=val_rows,
                                     data_collator=_collator(processor), processing_class=processor.tokenizer,
                                     callbacks=[transformers.EarlyStoppingCallback(**es["callback"])])
    latest = None
    if Path(args.output_dir).is_dir():
        latest = transformers.trainer_utils.get_last_checkpoint(args.output_dir)
    trainer.train(resume_from_checkpoint=latest)
    model.save_pretrained(str(adapter_dir))
    history = [h for h in trainer.state.log_history if "eval_loss" in h]
    result = {"base": base, "revision": revision, "config_hash": cfg.hash, "global_step": trainer.state.global_step,
              "best_eval_loss": trainer.state.best_metric, "evaluations": len(history), "trainable_modules": len(targets),
              "stopped_early": trainer.state.global_step < trainer.state.max_steps}
    log(f"training done: {result}")
    return result


# ---- evaluation (GPU) -------------------------------------------------------------------------------------------
def evaluate(cfg, s1_cfg, s1_dir, out_dir, repo_root, gpu, log=print, smoke=False):
    """Transcribe the evaluation slices with the base model and with the base plus the merged adapter."""
    import gc

    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from aqis_lab import drive
    from aqis_lab.bench import run as s1_run
    torch, peft, qwen_asr, hub = lib("torch"), lib("peft"), lib("qwen_asr"), lib("huggingface_hub")
    base = cfg.train["base"]
    revision = s1_run.revision_for(base, s1_cfg.models[base]["hf"], s1_dir)
    folder = hub.snapshot_download(s1_cfg.models[base]["hf"], revision=revision)
    run_root = Path(out_dir) / "smoke" if smoke else Path(out_dir)               # a smoke run reads and writes its own folder
    adapter = run_root / "train" / "adapter"
    if not adapter.is_dir():
        raise TrainError(f"{adapter} is missing; run the train stage{' with --smoke' if smoke else ''} first")
    commit = s1_run.git_commit(repo_root)
    for variant in ("base", "lora"):
        wrapper = qwen_asr.Qwen3ASRModel.from_pretrained(folder, dtype=torch.bfloat16, device_map="cuda:0",
                                                        max_inference_batch_size=s1_cfg.models[base]["batch"], max_new_tokens=256)
        if variant == "lora":
            wrapper.model = peft.PeftModel.from_pretrained(wrapper.model, str(adapter)).merge_and_unload()
        for slice_name, conditions in cfg.eval["slices"].items():
            for condition in conditions:
                dst = run_root / "eval" / variant / f"{slice_name}__{condition}.parquet"
                if dst.exists():
                    log(f"eval {variant} {slice_name}/{condition}: done, skipped")
                    continue
                src = Path(s1_dir) / "data" / slice_name / f"{condition}.parquet"
                rows = pq.read_table(src, columns=["utt_id", "audio"]).to_pylist()[:3 if smoke else None]
                out = []
                size = s1_cfg.models[base]["batch"]
                for start in range(0, len(rows), size):
                    chunk = rows[start:start + size]
                    audios = [(np.frombuffer(r["audio"], dtype=np.int16).astype(np.float32) / 32768.0, 16000) for r in chunk]
                    results = wrapper.transcribe(audio=audios, language=[s1_cfg.models[base]["language"]] * len(chunk))
                    out += [{"utt_id": r["utt_id"], "model": base, "variant": variant, "revision": revision, "hyp": res.text.strip(),
                             "dtype": "bf16", "gpu": gpu, "git_commit": commit, "seed": cfg.seed} for r, res in zip(chunk, results)]
                sink = pa.BufferOutputStream()
                pq.write_table(pa.Table.from_pylist(out), sink, compression="zstd")
                drive.make_dirs(dst.parent)
                drive.write_bytes(dst, sink.getvalue().to_pybytes())
                log(f"eval {variant} {slice_name}/{condition}: {len(out)} turns")
        del wrapper
        gc.collect()
        torch.cuda.empty_cache()
