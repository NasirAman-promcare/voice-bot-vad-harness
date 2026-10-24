# Sprint 1 (WP-1.1) Decision Note: Speech-to-Text Selection

**Date:** 24 October 2026  
**Status:** Approved by Owner & Reviewer  
**Commit:** `5f3b76c` | **Config Hash:** `a3ea46e3`  
**Dataset:** 6,300 evaluated target utterances (120,362 words) across 9 models  

---

## 1. Live Model Pick & Runner-Up
*Criteria: Lowest target WER among `live` models with batch-1 p50 latency <= 300 ms on L4 GPU.*

* **Primary Pick: `parakeet-tdt-0.6b-v2`**
  * **Target WER:** 18.27% [95% CI: 16.94, 19.63]
  * **Speed & Latency:** p50 = 113 ms (p95 = 120 ms), 515.1x RTFx (fastest model tested)
  * **Hallucination Rate:** 2.0% on non-speech/silence (vs. 79.3% for Whisper-Turbo)
  * **Licence:** CC BY 4.0
* **Runner-Up: `parakeet-unified-0.6b`**
  * **Target WER:** 18.06% [95% CI: 16.70, 19.51] (statistically tied with TDT v2)
  * **Speed & Latency:** p50 = 180 ms (p95 = 233 ms), 352.6x RTFx
  * **Hallucination Rate:** 0.0% on non-speech
  * **Licence:** NVIDIA Open Model License

---

## 2. Heavy Model Pick & Runner-Up
*Criteria: Lowest target WER overall, then highest number accuracy and medical recall.*

* **Primary Pick: `qwen3-asr-1.7b`**
  * **Target WER:** 16.55% [95% CI: 15.23, 17.92] (decisive accuracy leader across all slices)
  * **Clean WER:** 10.24%
  * **Clinical & Numbers:** Best medical recall (74.2% overall, 88.4% clinical findings) and 85.2% number accuracy.
  * **Licence:** Apache 2.0
  * *Operational Constraint:* High non-speech hallucination (98.7% on silence). Must be gated behind upstream VAD.
* **Runner-Up: `cohere-transcribe-2b`**
  * **Target WER:** 18.30% [95% CI: 16.98, 19.74]
  * **Speed & Hallucination:** p50 = 228 ms, 216.7x RTFx, with only 11.3% non-speech hallucination.
  * **Clinical & Numbers:** 84.4% number accuracy, 71.9% medical recall.
  * **Licence:** Apache 2.0 (gated).

---

## 3. Routing Policy (Mixture of Models)
* **Best Single Model (Target Set):** `qwen3-asr-1.7b` = 13.32% WER
* **Best Pair (Target Set):** `cohere-transcribe-2b` + `qwen3-asr-1.7b` = 11.06% WER
* **Oracle Ratio:** 11.06% / 13.32% = 0.830 (<= 0.85)
* **Decision: GO FOR ROUTING IN SPRINT 3.** Yields a 17.0% relative error reduction over the best single model.

---

## 4. Targeted Fine-Tuning Candidates
* **Decision: GO FOR TARGETED SPRINT 3 PILOT.**
  1. **Medical Drug Entities:** Every model scored poorly on drug name recall (< 58%).
  2. **8 kHz Telephony (`us_phone` Native):** All models degraded to 33-36% WER on native phone audio.

---

## 5. Five Key Findings & Surprises
1. WebRTC Opus showed negligible degradation (1.00x-1.04x WER over clean), whereas G.711 mu-law phone degraded accuracy by 1.15x-1.41x.
2. Parakeet TDT v2 rendered Whisper Turbo obsolete (6x faster, 40% lower latency, 3.8% better target WER, virtually zero hallucination).
3. Voxtral Realtime 4B is unviable (5.4s latency, 30.42% target WER).
4. Qwen3-ASR 1.7B is the decisive accuracy champion (16.55% target WER), but requires upstream VAD.
5. Granite Speech collapsed under noisy telephony (43.50% WER), disqualifying it from phone bot usage.
