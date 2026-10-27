# Sprint 3 (WP-1.3): Model Routing Cascade & Targeted Fine-Tuning

**Approved:** by the owner on 27 Oct 2026.  
**When:** the week of 2 Nov 2026.  
**GPU budget:** ~20–30 Colab compute units (out of ~94 units available).  
**People:** Claude Code (Sonnet) builds it, the owner runs it on Colab, and Opus reviews the results with the owner.  
**This file:** owner-owned; Claude reads it and never edits it.  

---

## 1. The Question
How do we combine our component champions into an optimal conversational system?

Sprint 3 settles two core architectural decisions:
1. **The Mixture of Models (AQIS Gate v0):** In Sprint 1, our oracle check proved that pairing `cohere-transcribe-2b` and `qwen3-asr-1.7b` yields **11.06% target WER** (a 17% relative error reduction over the best single model). Can a lightweight gating policy (confidence score, speech length, audio channel, and VAD features) achieve this gain while calling the heavy model on <= 35% of turns?
2. **Targeted LoRA Fine-Tuning Pilot:** Sprint 1 showed that every model struggled with clinical drug names (< 58% recall) and native 8 kHz phone distortion. Can targeted LoRA fine-tuning recover drug recall to >= 75% without degrading conversational WER?

---

## 2. Workstreams

### Workstream A: AQIS Routing & Cascade v0 (Simulated on S1 Data)
* **Input:** Prediction parquet files from Sprint 1 (`AQIS_LAB/s1/preds/`), evaluated on the 6 caller slices across target conditions (6,300 evaluated turns).
* **Cascade Architecture:**
  1. *Stage 1 (Live Transcriber):* `parakeet-tdt-0.6b-v2` produces the real-time transcript during caller speech.
  2. *Stage 2 (AQIS Gate v0):* Evaluates confidence (mean token log-probabilities / entropy), turn duration, channel (phone vs WebRTC), and non-speech ratio from Silero v5.
  3. *Stage 3 (Heavy Escalation):* If the gate triggers, the audio turn is dispatched to `qwen3-asr-1.7b` or `cohere-transcribe-2b` for post-turn re-transcription.
* **Evaluation:** Measure the trade-off curve of **Heavy Escalation Rate vs. Target WER**.
* **Gate Target:** Target WER <= 12.00% with escalation rate <= 35.0%.

### Workstream B: Keyword & Context Prompt Biasing
* Evaluate whether prompt biasing on `granite-speech-4.1-2b` and `qwen3-asr-1.7b` recovers medical drug terms and numbers without fine-tuning:
  * Prompt: Provide clinical entity lists in the prompt context.
  * Slices: `medical` and `numbers` (clean, phone, noise_10).

### Workstream C: Targeted LoRA Fine-Tuning Pilot
* **Base Model:** `qwen3-asr-1.7b` (Heavy accuracy champion) or `parakeet-tdt-0.6b-v2`.
* **Training Target:** Medical Drug & Clinical Entities (Eka medical training split).
* **Method:** PEFT / LoRA (r=16, alpha=32) using 4-bit / 8-bit QLoRA on Colab A100/L4 GPU (~2–3 hours).
* **Validation:** 
  1. Primary: Clinical drug recall on `s1/data/medical` under clean and phone distortion (target >= 75%).
  2. Non-regression: Verify that WER on `us_conv` degrades by <= 0.5% absolute.

---

## 3. Metrics & Deliverables
1. **Cascade Scorecard (`cascade.csv` & `tradeoff.png`):**
   * Target WER, Heavy Escalation Rate (%), Latency impact, and Cost savings vs. All-Heavy.
2. **Fine-Tuning Scorecard (`finetune.csv`):**
   * Pre vs. Post WER, Drug Recall, Number Accuracy, and non-regression check on `us_conv`.
3. **Official Decision Note (`docs/results/S3/DECISION.md`):**
   * Production AQIS Gate threshold parameters.
   * Fine-tuning Go / No-Go decision for production deployment.
   * Full Voice Bot End-to-End Architecture Blueprint.

---

## 4. Build Specifications (Claude Code)
All code implemented in `aqis_lab/cascade/`:
* `config.py`: Strict loader for `config/aqis_lab/s3.yaml`.
* `gate.py`: Gating policies (confidence thresholding, entropy, channel rules, and hybrid classifiers).
* `simulate.py`: Simulates cascade policies directly over Sprint 1 prediction parquet caches.
* `prompt_bias.py`: Evaluation runner for context/keyword prompt biasing.
* `train_lora.py`: Self-contained QLoRA fine-tuning script with early stopping.
* `score.py`: Computes cascade Pareto frontiers, entity recall, and paired bootstrap tests.
* `report.py`: Generates scorecards and trade-off plots.
* `__main__.py`: CLI entry point (`cascade`, `prompt`, `train`, `eval`, `report`).
* Unit tests in `tests/aqis_lab/test_s3_*.py`.
* Pinned lock file: `requirements/aqis_lab/s3-cascade.txt`.
* Branch: `s3/cascade-finetune`. PR: `WP-1.3: S3 Cascade and Fine-Tuning`.
* Tag on merge: `s3-colab-1`.

---

## 5. Execution Plan
| Stage | Machine | Runtime | Focus |
|---|---|---|---|
| `cascade` | CPU (Colab/local) | ~10 min | Simulate gating policies on S1 prediction caches. |
| `prompt` | Colab L4 GPU | ~30 min | Benchmark keyword prompt biasing on medical/numbers. |
| `train` | Colab A100 / L4 GPU | ~2–3 hours | LoRA fine-tuning pilot on medical clinical terms. |
| `eval` | Colab L4 GPU | ~20 min | Benchmark fine-tuned checkpoint against pre-trained base. |
| `report` | CPU | ~5 min | Generate final scorecard, Pareto curves, and DECISION.md. |

---

## 6. Sprint 3 Is Done When
1. **Tests:** All unit tests pass in fast suite, CI is green, and PR is merged.
2. **Cascade Verified:** Practical routing gate achieves Target WER <= 12.0% with <= 35% heavy model calls.
3. **Fine-Tuning Evaluated:** LoRA pilot completes with recorded drug recall and non-regression checks on `us_conv`.
4. **Final Architecture Blueprint:** `docs/results/S3/DECISION.md` committed, defining the complete AQIS production bot stack.
5. **Compute Units:** Colab consumption within the budget.
