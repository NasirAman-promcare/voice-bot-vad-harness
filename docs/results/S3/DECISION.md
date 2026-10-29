# Sprint 3 (WP-1.3) Decision Note: Model Routing Cascade & Targeted Fine-Tuning

**Date:** 29 October 2026  
**Status:** Approved by Owner & Reviewer  
**Commit:** `1afc2e1` (the code that produced these numbers: `bf7c7db` plus the four Colab runtime fixes, committed in `1afc2e1`) | **Config Hash:** `4ac9f213`  
**Dataset:** 6,300 evaluated turns, 1,500 prompt-biased turns (3,000 total transcriptions across both models), 1,600 evaluated fine-tuning turns (3,200 total transcriptions across base and LoRA)  

---

## 1. Executive Summary & Core Decisions

1. **Cascade Routing Policy: CONDITIONAL HEURISTIC ROUTE (or PURE HEAVY ON CLOUD GPU)**
   * **Target Gate:** The aggressive safety gate ($\le 12.0\%$ pooled Target WER at $\le 35\%$ escalation) was **not met** by practical heuristic gating ($14.25\%$ achieved).
   * **Finding:** While an ideal Oracle pairing reaches **$11.28\%$ Target WER** at 35% escalation, the cheap metadata features tried (duration, words per second, digits, channel, non-speech ratio, and a hybrid of them) cannot reliably predict specific word errors. **The confidence and entropy policies were not evaluated in this run:** the 46 of 6,300 turns for which stage 1 produced no words had no confidence, which marked those policies unavailable (and left confidence out of the hybrid gate). See *Open item* below.
   * **Production Recommendation:** 
     * Where cloud GPU budget is unconstrained: Route finalized turns directly to **`qwen3-asr-1.7b` Base** ($13.32\%$ Target WER across all turns, 95.6% number accuracy).
     * Where GPU compute must be minimized: Use **`channel` escalation** (telephone-channel turns first, then WebRTC; it does not look at noise, and has no score threshold: the telephone group alone is larger than the 35% budget, so the 14.25% is a seeded random 35% of telephone turns), achieving $14.25\%$ WER while saving $53.7\%$ GPU compute vs. All-Heavy.

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
* **Oracle Bound (35% Escalation):** **$11.28\%$ Target WER** (an upper bound on any gate; its WER difference from stage 1 is −3.73 points, 95% CI −4.10 to −3.36).
* **Best Practical Policy (`channel` at 35%):** **$14.25\%$ Target WER**, saving 53.6% GPU compute with 296 ms added latency (`channel` against stage 1: −0.76 points, 95% CI −0.97 to −0.57).

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
| **Post-Turn ASR** | `qwen3-asr-1.7b` (Base)| GPU Worker (NVIDIA L4) | Heavy post-turn transcription for final NLU/LLM response generation. |

---

## 4. Open item (30 October 2026)

The cascade section above was produced before the confidence-based policies could run: `confidence`, `entropy` and the confidence part of the `hybrid` gate were marked unavailable because 46 of 6,300 turns (stage 1 produced no words) had no token confidence. The code now scores such turns as least confident (confidence and entropy 0.0, the maximum-entropy end) and counts them in `policies.json`; a turn that has words but no confidence still makes the policy unavailable. **Section 2A and the cascade recommendation stand until `cascade` is rerun on Colab with that code and this note is updated.** The unmet 12.0% gate is not expected to change on its own: whether a confidence signal closes the gap between 14.25% and the 11.28% oracle is exactly what the rerun measures.
