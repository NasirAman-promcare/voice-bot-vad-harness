# Sprint 2 (WP-1.2) Decision Note: Live Conversational Stack Selection

**Date:** 27 October 2026  
**Status:** Approved by Owner & Reviewer  
**Commit:** `6dfe702` | **Config Hash:** `7a75f314`  
**Dataset:** 400 VAD clips (1,200 segments), 300 conversational turns, 200 streamed utterances, 1,200 emotion clips  

---

## 1. VAD Selection
* **Primary Pick: `silero_v5`**
  * **Configuration:** Threshold `0.5`, 32 ms frame window, 64 ms min speech, 100 ms silence smoothing.
  * **False Alarm Rate (FAR):** **0.31% on phone silence**, 1.01% on native telephony, 1.02% on WebRTC.
  * **Compute & Latency:** $RTF = 0.009$ (110x real-time on CPU), onset $p_{50} = 104 - 160	ext{ ms}$.
  * **Operational Role:** Runs on host CPU before STT to completely suppress background noise hallucinations.
* **Why TEN VAD was rejected:**
  * While TEN VAD caught slightly more speech on telephone lines (24.5% vs 33.9% MDR), it suffered an unacceptable **13.8% false alarm rate on silence** and **13.5% on noise** (10x to 44x worse than Silero v5).
  * In addition, TEN VAD is restricted to x86_64, whereas Silero v5 runs natively on our Oracle ARM VM at 40% lower compute overhead ($RTF = 0.009$ vs $0.015$).
* **Other Disqualified:** WebRTC VAD (33%–88% FAR on noise/silence); Silero v4 (51% missed speech rate on phone).

---

## 2. Turn-End Policy
* **Primary Pick: `fixed_1000` (1,000 ms silence post-VAD offset)**
  * **False Interruption Rate (FIR):** **2.70% on phone**, **2.96% on native** (the only policy meeting $	ext{FIR} < 3.0\%$).
  * **Latency:** $p_{50} = 1,156	ext{ ms}$ ($p_{95} = 1,228	ext{ ms}$).
  * **Conversational Policy for Voice Bot:** 
    1. Silence < 500 ms: Caller is pausing mid-turn; bot remains silent.
    2. Silence 500–700 ms: Trigger filler acknowledgment ("Mm-hmm", "Understood") if partial STT indicates unfinished clause.
    3. Silence >= 1,000 ms: Final endpoint triggered; bot replies.
* **Disqualified:** `smart_turn` and `fixed_300` (failed safety gate with 20%–24% false interruptions).

---

## 3. Live STT Routing (CPU vs. GPU Fallback)
* **Benchmark Finding:**
  * Parakeet TDT v2 INT8 whole-clip offline inference on 1 Arm CPU thread is real-time viable ($RTF = 0.152$).
  * Rolling window streaming inference on 1 Arm thread exceeds real-time ($RTF = 0.79$ at 640ms chunks; $RTF = 2.95$ at 160ms chunks).
* **Architectural Decision: FALLBACK TO GPU WORKER FOR LIVE STREAMING.**
  * Frame-by-frame live streaming STT is routed to cloud GPU workers (Sprint 1 benchmark: **515x RTFx, 113 ms latency on L4 GPU**).
  * Oracle Arm CPUs host the Jitsi bridge, VAD (`silero_v5`), turn-end timers, and fallback turn-based transcription.

---

## 4. Emotion & Frustration Detection
* **Primary Pick: `emotion2vec_seed`**
  * **Frustration / Anger Recall on Telephony:** **85.67%** [95% CI: 80.81%, 90.48%] (Passes $\ge 70.0\%$ gate).
  * **WebRTC Accuracy:** 91.83% UAR, 96.00% frustration recall.
  * **Footprint:** 20M parameters (runs in < 15 ms).
  * **Operational Role:** Trigger human agent transfer whenever frustration confidence exceeds 0.75 across two consecutive turns.

---

## 5. Five Key Findings & Surprises
1. **Silero v5 decisively defeated TEN VAD on real telephony:** TEN VAD’s 13.8% false alarm rate on silence would cause constant bot mis-triggers; Silero v5 achieved 0.31%.
2. **WebRTC VAD is completely obsolete:** Classical energy VAD cannot be used in production voice bots; it triggers on 50%–88% of silence frames.
3. **The 300ms turn-end myth:** Every model reacting in < 500 ms (including Smart Turn) cuts off callers mid-sentence in ~22% of turns. Real customer calls require $\ge 1,000	ext{ ms}$ silence or filler bridging.
4. **Parakeet TDT rolling streaming is CPU-bound:** Re-encoding the context window without cache state on a single CPU core is not real-time viable, cementing our GPU live streaming architecture.
5. **Emotion2vec Seed beats Base on telephony:** The compact 20M seed model generalized significantly better to 8 kHz telephone compression (85.7% recall) than the 90M base model (54.0% recall).
