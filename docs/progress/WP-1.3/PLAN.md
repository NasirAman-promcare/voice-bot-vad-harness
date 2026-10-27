# PLAN: WP-1.3 S3 Cascade and Fine-Tuning

Spec: `docs/specs/sprints/WP-1.3-S3-cascade-finetune.md` (section 4)  ·  Branch: `s3/cascade-finetune`  ·  Base: `origin/main` at `de85e84`

## What gets built
- `aqis_lab/cascade/`: `config`, `gate`, `simulate`, `prompt_bias`, `train_lora`, `score`, `report`, `__main__` as the brief lists them, plus `confidence` (token confidences, see departure 1), `features` (where extra gate features are stored), and `train_data` (the Eka training set, departure 3).
- `config/aqis_lab/s3.yaml`: the brief's numbers (12.00% WER, 35% escalation, r 16, alpha 32, drug recall 75%, us_conv +0.5%) and the keys the stages need. The loader refuses unknown and missing keys.
- Locks (uv 0.8.17, Python 3.13, x86_64, hashes, `-c phase0.txt`): `s3-cascade` (CPU: simulation, non-speech feature, report) and `s3-train` (GPU: QLoRA and evaluation, kept on the Sprint 1 Qwen pins by `-c s1-qwen.txt`). The prompt stage reuses the Sprint 1 locks `s1-hf` (Granite) and `s1-qwen` (Qwen3-ASR).
- `notebooks/aqis_lab/s3_cascade_finetune.ipynb`: `STAGE` = cascade, confidence, prompt, prepare, train, eval, report; `SMOKE = True` runs 3 turns (4 training steps) into `AQIS_LAB/s3/smoke`.
- CI: no workflow change is needed. The S3 tests run in the existing `lab` job; the two lock-resolution checks need PyPI and are `network` tests, which the existing `lab-network` job runs.

## Order
1. Ruler tests first (`tests/aqis_lab/test_s3_*.py`): cascade arithmetic by hand, gate features and leak-free speaker folds, strict config and locks, the simulation over Sprint 1 files with hand-set error counts, term lists, speaker-disjoint splits and LoRA settings. They failed on import before any `aqis_lab/cascade` code existed.
2. Code, config, locks, notebook.
3. Fast suite and gate green, PR `WP-1.3: S3 Cascade and Fine-Tuning`, merge, tag `s3-colab-1`.

## Definitions the ruler tests fix
- **Target WER** is the pooled WER (total errors over total reference words) of the 6,300 target turns, the figure behind the 11.06% of Sprint 1's oracle (`docs/results/S1/oracle.csv`, "target set"). Sprint 1's headline per model is the mean of the six slice WERs (qwen3-asr 16.55%) and is a different number; `cascade.csv` carries both (`wer`, `mean_slice_wer`), and the gate uses the pooled one.
- **Escalation rate** is turns sent to the heavy model over all turns, never above the rate asked: `floor(rate x turns)` turns, the highest gate scores first, ties by a seeded hash.
- **Cost saving** is GPU seconds from audio length over RTFx (Sprint 1 `speed.csv`): stage 1 for every turn plus the heavy model for escalated turns, against the heavy model alone. **Added latency** is the share of escalated turns times the heavy model's batch-1 p50 latency.
- **Hybrid gate** is a logistic regression on gate features, predicting that the heavy model saves at least one word error on the turn. Its scores are always out of fold by speaker (`test_s3_out_of_fold_scores_come_from_models_that_never_saw_the_row_or_its_cluster`).
- Each heavy model is simulated alone. "Qwen3 or Cohere" is not decided per turn by a realisable rule; the best-of-both figure is reported as an oracle bound (`best_two_heavy_oracle_wer` in `summary.json`).

## Where this build departs from the brief
1. **Confidence is not in the Sprint 1 files.** Their prediction files hold text, not token log-probabilities, so the gate's first feature cannot be simulated from them. The `confidence` action reruns parakeet-tdt-0.6b-v2 on the GPU with NeMo's token confidence switched on (a max-probability score and an entropy-based score) and saves them to `cascade/features.parquet`. NeMo's `confidence_cfg` calls are written from its documentation and **were not run**; the smoke run is their first test. Until it has run, the `confidence` and `entropy` policies are reported `unavailable` with the reason, and never filled in. The other features (duration, words per second, digit tokens, channel, Silero v5 non-speech ratio) come from the Sprint 1 files and audio.
2. **Words per second and digit tokens** come from stage 1's own hypothesis, which exists at gate time; nothing from the heavy model or the reference reaches the gate.
3. **Eka has no training split** (3,619 English turns, `test` only; checked on the Hugging Face card). The "Eka training split" is the part of Eka whose speakers are not in the 300-turn `medical` evaluation slice, with turns that have at least one scored entity. Up to 2,000 turns, spread over speakers, 10% of the speakers held out for early stopping; the training audio is rendered clean (40%), phone (40%) and noise_10 (20%) with the Sprint 1 conditions. The manifest counts how many evaluated drug names also appear in training, so a recall gain from names the model saw is visible as such.
4. **Prompt biasing terms** are the most frequent drug names in the Eka turns of the same non-evaluated speakers (at most 150 and 1,500 characters), never the evaluated slice's own entities. The `numbers` slice gets a one-sentence digit hint instead of a term list. Granite uses its card's keyword prompt; Qwen3-ASR uses `transcribe(context=...)`.
5. **LoRA recipe** (r 16, alpha 32, dropout 0.05, NF4 4-bit with bf16 compute, early stopping on validation loss with patience 3) follows Qwen's own `finetuning/qwen3_asr_sft.py` for the data format, forward patch and label masking. The target pattern covers `thinker.model.layers.*` attention and MLP projections only, not the audio tower. It stops with an error if the pattern matches no module. **Not run here**: module names, 4-bit loading through `Qwen3ASRModel.from_pretrained(quantization_config=...)`, `prepare_model_for_kbit_training` on this model and the merge for evaluation are untested; `train --smoke` is their first test. The base is Qwen3-ASR (the brief's other option, Parakeet, has no recipe here).
6. **Sprint 1's pinned revisions** (`s1/revisions.json`) are reused for stage 1, Granite and Qwen3-ASR, so the baselines and the new runs use the same weights.
7. **Smoke runs** (`--smoke`, CLAUDE.md rule 6) write to `<out>/smoke` and never touch the real files or checkpoints.
8. `report` writes `decision_inputs.md` (gate thresholds and gate results), not `DECISION.md`: the Go/No-Go decision and the end-to-end blueprint are the owner's and the reviewer's, as in Sprints 1 and 2.
9. As in the earlier sprints, libraries outside the phase 0 lock load through `aqis_lab.bench.lib()` so the two Phase 0 guard tests stay unchanged. GPU actions import no scorer (`test_s3_gpu_actions_import_no_scorer`).

## What this build does not check
The model wrappers (prompt biasing on Granite and Qwen3-ASR, NeMo token confidences, QLoRA training and the merged-adapter evaluation) and the Eka and MUSAN loaders in `train_data.prepare`: the cloud session downloads no corpora or models. Synthetic Sprint 1 files with hand-set error counts drive the cascade simulation end to end, and synthetic prediction files drive the prompt and fine-tuning scorecards.
