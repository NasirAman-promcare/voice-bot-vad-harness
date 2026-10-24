# Sprint 2 (WP-1.2): Live Stack Benchmark (VAD, Turn-End, Streaming STT, and Emotion)

**Approved:** by the owner on 24 Oct 2026.
**When:** the week of 26 Oct 2026.
**Compute budget:** Oracle Cloud always-free Arm VM (4 OCPU, 24 GB RAM, CPU work) + no more than 5 Colab units for GPU emotion validation.
**People:** Claude Code (Sonnet) builds it, the owner runs it on Oracle and Colab, and Opus reviews the results with the owner.
**This file:** owner-owned; Claude reads it and never edits it.

---

## 1. The Question
Now that speech-to-text accuracy is proven (Parakeet TDT v2 for live, Qwen3-ASR 1.7B for heavy), how does the bot interact in real time with our callers over phone lines and WebRTC?

The benchmark decides four core components of the live conversational pipeline:
1. **The Voice Activity Detector (VAD):** Which VAD detects speech onset and offset most accurately under 8 kHz telephony and room noise without cutting off quiet syllables or triggering on background noise?
2. **Turn-End Detection (Endpointing):** How fast can the bot detect that a caller has finished their turn without interrupting mid-sentence when they pause to think?
3. **Live Streaming STT Latency on CPU:** Can our live STT champion (`parakeet-tdt-0.6b-v2`) run on CPU in real-time ($RTF < 0.35$, streaming chunk delay <= 250 ms) on Oracle Arm CPUs (Ampere A1) using our Phase 0 `aiortc` Jitsi bridge?
4. **Emotion & Frustration Detection:** Which model detects caller frustration or anger accurately under phone-line compression to trigger human agent escalation?

---

## 2. Test Sets & Ground Truth

### 2.1 Acoustic Conditions (Reused from Sprint 1)
All evaluations test the same 5 acoustic conditions verified in Sprint 1:
`clean`, `noise_10` (10 dB MUSAN noise), `noise_0` (0 dB noise), `phone` (G.711 mu-law 8 kHz), and `webrtc` (Opus 16 kbps with 2% packet loss).

### 2.2 Slices & Datasets
| Component | Dataset (Licence) | Content | Target Condition | Evaluation Goal |
|---|---|---|---|---|
| **VAD Accuracy & Timing** | `s1/data/us_phone` + `s1/data/sa_conv` + `s1/data/nonspeech` (CC BY 4.0 / Public Domain) | Real telephone audio, conversational pauses, room noise, music, and silence (1,200 audio segments). | `phone`, `webrtc`, `noise_10`, `noise_0` | Speech onset/offset alignment against millisecond ground truth; false alarms on non-speech. |
| **Turn-End Detection** | HarperValleyBank (`us_phone`, CC BY 4.0) | 300 natural customer conversational turns with real pauses (150 caller turns, 150 agent turns). | `phone`, `native` | False interruption rate (cutting the user off mid-sentence) vs. response latency. |
| **Streaming STT on CPU** | Sprint 1 Anchor + US Conv (CC BY 4.0) | 200 conversational and telephony utterances streamed in 20 ms frames (160 samples per packet). | `phone`, `webrtc` | Wall-clock latency, chunk processing time, and RTF on Oracle Arm CPU. |
| **Emotion Detection** | CREMA-D (Open Database Licence / CC BY-SA 4.0) | 1,200 utterances across 4 operational classes: Neutral, Anger/Frustration, Sadness, Happiness. | `clean`, `phone`, `webrtc`, `noise_10` | Unweighted Average Recall (UAR) and Frustration Recall under phone compression. |

---

## 3. Candidate Models & Systems

### 3.1 Voice Activity Detectors (VAD)
1. **`silero-vad-v5`** (`snakers4/silero-vad`, MIT): 5th generation ONNX/PyTorch model, 32 ms frame window.
2. **`silero-vad-v4`** (`snakers4/silero-vad`, MIT): Standard production reference baseline.
3. **`firered-vad`** (`FireRedTeam/FireRedVAD`, Apache 2.0): High-robustness acoustic VAD designed for noisy speech.
4. **`webrtc-vad`** (`webrtcvad`, BSD): Classical GMM energy/spectral VAD (aggressiveness modes 1, 2, and 3).
5. **`ten-vad`** (Agora TEN framework, Apache 2.0): Lightweight conversational VAD (*tested on x86_64 only due to lack of aarch64 build*).

### 3.2 Turn-End Detection (Endpointing)
1. **Fixed Silence Thresholds:** Baseline acoustic silence timers of 300 ms, 500 ms, 700 ms, and 1,000 ms following VAD speech-offset.
2. **Smart Turn:** Semantic + acoustic turn-completion boundary detector (predicts whether a pause is mid-sentence or end-of-turn).
3. **TEN Turn Detection:** Conversational endpointing model combining acoustic silence duration and partial transcript tokens.

### 3.3 Streaming Speech-to-Text on CPU
1. **`parakeet-tdt-0.6b-v2`** (Sprint 1 Live Winner, CC BY 4.0): Streamed in chunk sizes of 160 ms, 320 ms, and 640 ms using ONNX Runtime / PyTorch INT8 and FP32 on Oracle Arm.
2. **`parakeet-unified-0.6b`** (Sprint 1 Live Runner-up, NVIDIA Open Model License): Streaming mode chunked evaluation.

### 3.4 Emotion & Frustration Detection
1. **`emotion2vec_plus_seed`** (`FunASR/emotion2vec_plus_seed`, Apache 2.0): Lightweight 20M parameter emotion embedding model.
2. **`emotion2vec_plus_base`** (`FunASR/emotion2vec_plus_base`, Apache 2.0): Full 90M parameter representation.
3. **`wav2vec2-emotion`** (`superb/wav2vec2-base-superb-er`, MIT / Apache 2.0): Standard Hugging Face emotion classifier.
4. **Acoustic Baseline:** Classical pitch (F0 variance), RMS energy contour, and speaking rate via standard acoustic DSP.

---

## 4. Metrics & Evaluation Standards

1. **VAD Accuracy:**
   * **False Alarm Rate (FAR):** Percentage of non-speech/silence frames falsely flagged as speech (must be < 2.0%).
   * **Missed Detection Rate (MDR):** Percentage of speech frames dropped or clipped (must be < 1.0%).
   * **Onset Lag (p50, p95):** Time in ms from true speech onset to VAD trigger (target <= 40 ms).
   * **Hangover Cutoff:** Accuracy of preserving sentence-final unvoiced fricatives and trailing stops.
2. **Turn-End Performance:**
   * **False Interruption Rate (FIR):** Percentage of pauses mid-sentence where the bot triggered an endpoint and interrupted the caller. Strict requirement: FIR < 3.0%.
   * **Endpoint Latency (p50, p95):** Time in ms from the caller's last spoken phoneme to the turn-end trigger. Target: <= 300 ms.
3. **Streaming CPU Performance:**
   * **Real-Time Factor (RTF):** Processing time divided by audio duration on 1 thread of Oracle Ampere A1 Arm core (must be RTF <= 0.35 for real-time safety).
   * **Chunk Latency:** Time to return partial transcription tokens after a 200 ms audio chunk is fed.
4. **Emotion & Frustration Metrics:**
   * **Unweighted Average Recall (UAR):** Mean recall across the 4 emotion classes.
   * **Frustration / Anger Recall:** True positive detection rate for caller frustration (target >= 75%).
   * **Phone Cost:** UAR(phone) / UAR(clean).

---

## 5. Build Specifications (Claude Code)

### 5.1 Directory & Code Structure
All code is implemented in `aqis_lab/live/`:
* `config.py`: Strict loader for `config/aqis_lab/s2.yaml`.
* `vad.py`: Standard interface `VADAdapter` wrapping Silero, WebRTC, FireRed, and TEN.
* `turn.py`: Turn-end detector evaluating fixed timers vs. predictive models.
* `streaming.py`: Frame-by-frame (20 ms / 160 sample) streaming bridge wrapping Parakeet TDT via Phase 0's `aiortc` harness.
* `emotion.py`: Unified wrapper for emotion models.
* `score.py`: Scoring engine computing DET curves, FIR, latencies, and UAR with speaker bootstrap intervals.
* `report.py`: Generates `scorecard.md`, `live_stack.csv`, and latency trade-off plots.
* `__main__.py`: CLI entry point (`prep`, `smoke`, `vad`, `turn`, `stream`, `emotion`, `report`).

### 5.2 Ruler Tests (`tests/aqis_lab/test_s2_*.py`)
1. **Frame Invariants:** Streamed 20 ms frames retain exact length and amplitude; no dropped samples.
2. **VAD Alignment:** Synthetic tone bursts at known millisecond boundaries prove onset and offset latency calculation is mathematically exact.
3. **FIR Calculation:** Hand-worked multi-pause turn proves false interruption rate matches definition.
4. **Endpoint Latency:** Test audio with 400 ms mid-sentence pause does not trigger endpoint on 500 ms threshold; 600 ms end pause triggers at exactly t = 500 ms.
5. **Emotion Metrics:** UAR and confusion matrices match hand-worked 4-class calculations.

### 5.3 Locks & CI
* Lock file: `requirements/aqis_lab/s2-live.txt` hash-pinned for Python 3.13 x86_64 and aarch64.
* Branch: `s2/live-stack`. Pull Request: `WP-1.2: S2 Live Stack benchmark`.
* Tag on completion: `s2-colab-1`.

---

## 6. Execution Plan

| Stage | Machine | Runtime | Focus |
|---|---|---|---|
| `prep` | Oracle Arm VM / CPU | ~15 min | Extract CREMA-D emotion data, generate 20 ms Jitsi frame streams. |
| `smoke` | Oracle Arm VM | ~5 min | 1 clip per model to verify zero crashes. |
| `vad` | Oracle Arm VM (and x86) | ~30 min | Benchmark VAD accuracy, onset lag, and non-speech false alarms. |
| `turn` | Oracle Arm VM | ~25 min | Benchmark False Interruption Rate vs. endpoint latency. |
| `stream` | Oracle Arm VM | ~30 min | CPU streaming STT latency and RTF of Parakeet TDT on Arm. |
| `emotion` | Colab L4 GPU | ~20 min | Benchmark emotion2vec+ and alternatives on CREMA-D across channels. |
| `report` | Oracle Arm VM / CPU | ~10 min | Generate scorecard, trade-off curves, and write-up. |

---

## 7. Sprint 2 Is Done When
1. **Tests:** All unit tests pass in fast suite, and CI is green.
2. **VAD Selection:** One VAD is chosen with FAR < 2%, MDR < 1%, and onset lag <= 40 ms.
3. **Turn-End Picked:** Endpointing policy selected with FIR < 3% and p50 latency <= 300 ms.
4. **Streaming Viability:** Parakeet TDT v2 demonstrated running on Oracle Arm CPU with RTF < 0.35 and chunk latency <= 250 ms, OR fallback GPU routing recorded.
5. **Emotion Model:** Frustration detection accuracy >= 70% verified under 8 kHz telephone audio.
6. **Results Committed:** Scorecard and `docs/results/S2/DECISION.md` committed to `main`.
7. **Units:** Colab unit consumption <= 5 units.

---

## 8. Decision Note Template (`docs/results/S2/DECISION.md`)
* **VAD Selection:** Winning model, frame size, and threshold parameters.
* **Turn-End Policy:** Chosen model/threshold, false interruption rate, and reaction delay.
* **Live STT CPU Routing:** Arm CPU real-time factor, chunk latency, and whether STT runs on Oracle CPU or requires cloud GPU workers.
* **Emotion Model:** Selected model, frustration recall under telephony, and CPU/GPU memory footprint.
* **Surprises & Gaps:** Maximum 5 lines.

---

## Appendix A: `config/aqis_lab/s2.yaml` (Starting Values)
```yaml
schema: s2-v1
seed: 20261026

vad:
  silero_v5:
    repo: snakers4/silero-vad
    model_version: v5
    threshold: 0.5
    min_speech_ms: 64
    min_silence_ms: 100
  silero_v4:
    repo: snakers4/silero-vad
    model_version: v4
    threshold: 0.5
  firered_vad:
    hf: FireRedTeam/FireRedVAD
  webrtc_vad:
    mode: 2
  ten_vad:
    supported_arch: [x86_64]
    hop_size_ms: 16

turn_end:
  fixed_thresholds_ms: [300, 500, 700, 1000]
  predictive:
    smart_turn:
      max_wait_ms: 800

stt_streaming:
  model: parakeet-tdt-0.6b-v2
  chunk_sizes_ms: [160, 320, 640]
  target_rtf_max: 0.35

emotion:
  emotion2vec_seed:
    hf: FunASR/emotion2vec_plus_seed
  wav2vec2_er:
    hf: superb/wav2vec2-base-superb-er
