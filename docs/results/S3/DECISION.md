# Sprint 3 (WP-1.3) Decision Note: Model Routing Cascade & Targeted Fine-Tuning

**Date:** 29 October 2026 (cascade sections revised the same day, after the confidence rerun)  
**Status:** Approved by Owner & Reviewer (29 October); the revision awaits their re-approval  
**Commit:** cascade `7056734`; prompt biasing and fine-tuning `1afc2e1` (`bf7c7db` plus the four Colab runtime fixes) | **Config Hash:** `4ac9f213`  
**Dataset:** 6,300 evaluated turns, 1,500 prompt-biased turns (3,000 total transcriptions across both models), 1,600 evaluated fine-tuning turns (3,200 total transcriptions across base and LoRA)  

---

## 1. Executive Summary & Core Decisions

1. **Cascade Routing Policy: CONFIDENCE-GATED ROUTE (or PURE HEAVY ON CLOUD GPU)**: neither meets the 12.0% gate
   * **Target Gate:** The safety gate ($\le 12.0\%$ pooled Target WER at $\le 35\%$ escalation) was **not met** by any practical gate. The best, stage 1's own token confidence, reaches $13.80\%$ at 35% escalation. Only the perfect-knowledge oracle ($11.28\%$) clears it, and it needs 25% escalation to do so ($11.75\%$).
   * **Finding:** Parakeet's mean token confidence is the strongest practical signal. At 35% escalation it cuts stage 1's pooled WER by 1.22 points (8.1% relative; $15.02\%$ to $13.80\%$), about 33% of the 3.73 points the oracle gains, against 20% for `channel` and 15% for random selection. Duration, words per second, digits, channel and the non-speech ratio each recover only 0.49 to 0.76 points, and a hybrid gate trained on them plus confidence ($14.19\%$) does worse than confidence alone.
   * **Production Recommendation:**
     * Where cloud GPU budget is unconstrained: Route finalized turns directly to **`qwen3-asr-1.7b` Base** ($13.32\%$ Target WER across all turns, 95.6% number accuracy).
     * Where GPU compute must be minimized: Use the **confidence gate** (Section 2A). Escalate a turn to the base model when stage 1's mean token confidence is at or below $0.9660$, which sends 35% of the target turns. Against sending everything to the heavy model it costs $0.48$ points of WER (95% CI +0.21 to +0.73, so the loss is real) and saves $63.1\%$ of GPU compute, with 296 ms of added latency averaged over all turns.

2. **Context & Keyword Prompt Biasing: REJECTED (NO-GO)**
   * **Finding:** Prompt context biasing on `granite-speech-4.1-2b` and `qwen3-asr-1.7b` showed no consistent effect on drug recall: changes of −0.97 to +0.65 points for Granite and −0.33 to 0.00 points for Qwen3-ASR. No significance test was run on recall; the paired WER intervals include zero in 11 of 12 biased cells (Qwen3-ASR medical noise_10 improved by 0.18 points).
   * **Decision:** Omit context prompt lists from ASR inference to save prompt token latency.

3. **Clinical LoRA Fine-Tuning: REJECTED (DECISIVE NO-GO)**
   * **Finding:** 4-bit QLoRA fine-tuning on medical terms delivered a modest recall gain ($52.1\%$ → $57.9\%$ on phone audio), but caused **severe catastrophic forgetting (+2.1% to +2.7% absolute WER degradation)** across everyday conversational English (`us_conv`).
   * **Decision:** Deploy the **pre-trained base model (`qwen3-asr-1.7b`)**. The base model's general linguistic stability far outweighs the narrow domain gain.

---

## 2. Quantitative Scorecard Summary

### A. Cascade Gate Trade-Offs (Target: pooled WER <= 12.0% at <= 35% escalation)
* **Stage 1 Live Transcriber (`parakeet-tdt-0.6b-v2`):** $15.02\%$ Target WER ($18.27\%$ mean slice WER).
* **Stage 2 Heavy Transcriber (`qwen3-asr-1.7b`):** $13.32\%$ Target WER ($16.55\%$ mean slice WER).
* **Best Practical Policy (`confidence` at 35%):** **$13.80\%$ Target WER**, saving 63.1% GPU compute with 296 ms added latency.
* **Oracle Bound (35% Escalation):** **$11.28\%$ Target WER**, an upper bound on any gate.

All policies escalate 35% of the 6,300 target turns to `qwen3-asr-1.7b` (2,205 turns). Differences are in WER points of the pooled target set, with 95% speaker-cluster bootstrap intervals; "GPU saving" is against sending every turn to the heavy model, from audio seconds and the Sprint 1 RTFx.

| Policy | Target WER | Change vs stage 1 [95% CI] | Change vs all-heavy [95% CI] | GPU saving |
|---|---|---|---|---|
| `confidence` | 13.80% | -1.22 [-1.52, -0.93] | +0.48 [+0.21, +0.73] | 63.1% |
| `entropy` | 14.09% | -0.93 [-1.19, -0.67] | +0.77 [+0.48, +1.06] | 65.7% |
| `hybrid` | 14.19% | -0.82 [-1.07, -0.57] | +0.87 [+0.64, +1.10] | 31.0% |
| `channel` | 14.25% | -0.76 [-0.97, -0.57] | +0.93 [+0.65, +1.19] | 53.7% |
| `nonspeech` | 14.28% | -0.73 [-0.96, -0.50] | +0.96 [+0.69, +1.24] | 55.8% |
| `words_per_s` | 14.34% | -0.68 [-0.97, -0.42] | +1.01 [+0.70, +1.31] | 46.7% |
| `duration` | 14.46% | -0.56 [-0.85, -0.28] | +1.13 [+0.86, +1.42] | 22.7% |
| `random` | 14.47% | -0.55 [-0.71, -0.38] | +1.15 [+0.88, +1.41] | 53.2% |
| `digits` | 14.53% | -0.49 [-0.69, -0.31] | +1.20 [+0.93, +1.48] | 47.5% |
| `oracle` (upper bound, not a policy) | 11.28% | -3.73 [-4.10, -3.36] | -2.04 [-2.22, -1.86] | 49.7% |

* **Confidence against `channel`:** 13.80% against 14.25%, 0.45 points lower on the point estimate. No paired test between the two policies was run, and their intervals against stage 1 overlap slightly, so "confidence is better than `channel`" rests on the point estimate alone. What the point estimates do show is that `confidence` is the only practical policy whose gain over stage 1 (1.22 points) is more than twice that of random selection (0.55).
* **A real threshold:** `channel` has none (its score is tied across the whole telephone group, which is larger than the 35% budget, so its figure is a seeded random 35% of telephone turns). `confidence` has one (`thresholds.json`): escalate when mean token confidence is at or below $0.9660$ (`max_prob` method, blank tokens excluded, mean over tokens; the entropy-based variant's threshold is $0.1797$). Both thresholds were set on the same 6,300 turns that were scored, so the 35% operating point is in-sample; no held-out check was run.
* **Turns with no stage 1 words:** 46 of 6,300 turns (0.73%) have no token confidence. They are scored as least confident (0.0), so the gate always escalates them. This is a stated rule, counted in `policies.json`, not a measurement.
* **Cohere as the heavy model** does not help: even the oracle only reaches 12.09% at 35% escalation, and its best practical gate (`confidence`) reaches 14.67%.

### B. Prompt Biasing vs. Unbiased Baseline (1,500 prompt-biased turns; 3,000 total transcriptions across both models)
* **Granite Speech 4.1 2B:**
  * Clean Medical Drug Recall: $49.19\%$ → $49.84\%$ (+0.65 points).
  * Telephone Medical Drug Recall: $46.28\%$ → $45.31\%$ (−0.97 points).
* **Qwen3-ASR 1.7B:**
  * Clean Medical Drug Recall: $57.28\%$ → $57.28\%$ (Unchanged).
  * Telephone Medical Drug Recall: $52.43\%$ → $52.10\%$ (Unchanged).
  * Numbers Accuracy: Unchanged at $85.1\%$ (Clean) and $84.7\%$ (Phone).

### C. LoRA Fine-Tuning Pilot (1,600 evaluated turns; 3,200 total transcriptions across base and LoRA)

* **Methodological Rigor Note (Speaker Overlap):**
  * In `eka_medical`, every speaker in the pool has turns in the 300-turn evaluation set. As a result, the training set draws from the same pool of speakers (utterance-disjoint, but not speaker-disjoint).
  * This is an *easier* learning setting than evaluating on completely unseen speakers. Despite this advantage, fine-tuning failed to hit the 75% recall target and catastrophically degraded general English by > 2.0% WER. This decisively confirms the pre-trained base model as the only production-viable choice.
* **Drug Recall (Medical Phone):** $52.10\%$ → $57.93\%$ (Failed target $\ge 75.0\%$).
* **WER (Medical Phone):** $9.96\%$ → $11.52\%$ (+1.57 points: worse, though the paired interval includes zero). Medical clean improved, $8.27\%$ → $7.29\%$ (also within the interval).
* **General Conversational Degradation (`us_conv/phone`):** $12.82\%$ → $15.51\%$ (+2.68% WER regression).
* **General Conversational Degradation (`us_conv/clean`):** $11.06\%$ → $13.19\%$ (+2.13% WER regression).
* **Numbers Degradation (`numbers/phone`):** $12.24\%$ → $14.00\%$ (+1.76% WER regression).

---

## 3. Final Voice Bot End-to-End Stack Specification

| Component | Champion Model | Runtime Host | Operational Role |
|---|---|---|---|
| **VAD** | `silero_v5` | Host CPU (Oracle Arm) | Frame size 32 ms (512 samples at 16 kHz); suppresses background room noise (0.31% FAR on silence). |
| **Turn Endpoint** | `fixed_1000` | Host CPU (Oracle Arm) | 1,000 ms silence post-VAD offset; ensures < 3.0% false interruption rate. |
| **Emotion Transfer**| `emotion2vec_seed` | Host CPU (Oracle Arm) | 20M params; triggers human agent transfer if anger confidence > 0.75. |
| **Live Streaming** | `parakeet-tdt-0.6b-v2` | GPU Worker (NVIDIA L4) | Streams partial transcripts during speech to drive conversational fillers. |
| **Cascade Gate** | `confidence` | GPU Worker (NVIDIA L4) | Reads stage 1's mean token confidence; at or below 0.9660 (35% of turns) the turn goes to the post-turn model, above it the stage 1 transcript is kept. Skip the gate and send every turn on when GPU budget allows. |
| **Post-Turn ASR** | `qwen3-asr-1.7b` (Base)| GPU Worker (NVIDIA L4) | Heavy post-turn transcription for final NLU/LLM response generation (escalated turns, or every turn if the gate is skipped). |

---

## 4. Compute and provenance

* **Colab compute:** about 1.83 estimated units for Sprint 3 (0.87 h CPU and 1.03 h on an L4, 28 sessions starting between 27 October 11:41 and 29 October 16:34 UTC, which includes the cascade rerun), against the brief's 20 to 30. Source: `units.csv`, with the rates of the build plan.
* **Cascade rerun:** the table above is the rerun with the 46 word-less turns scored as least confident (code `7056734`; config hash unchanged); the first run's figures for the policies that do not use confidence are identical in it. The prompt-biasing and fine-tuning figures are from the first run (`1afc2e1`).
* **Files:** `cascade.csv`, `headline.csv`, `thresholds.json`, `policies.json`, `summary.json`, `prompt.csv`, `finetune.csv`, `scorecard.md`, `tradeoff.png` in this folder; `s3_report.zip` holds the aggregates.
