# PLAN: WP-1.2 S2 Live Stack benchmark

Spec: `docs/specs/sprints/WP-1.2-S2-live-stack.md` (section 5)  ·  Branch: `s2/live-stack`  ·  Base: `origin/main` at `22baec1`

## What gets built
- `aqis_lab/live/`: `config`, `streaming`, `vad`, `turn`, `emotion`, `score`, `report` and `__main__` as the brief lists them, plus `results` (traced, resumable result files), `prep` (the test sets) and `stages` (the vad, turn, stream and emotion runners and the smoke).
- `config/aqis_lab/s2.yaml`: Appendix A plus the keys the stages need (conditions per component, scoring, gates, data, pins). The loader refuses unknown and missing keys.
- `requirements/aqis_lab/s2-live.in/.txt`: one universal lock (uv 0.8.17, Python 3.13, hashes, `-c phase0.txt`) for aarch64 and x86_64.
- `notebooks/aqis_lab/s2_live_stack.ipynb` (Colab: `prep`, `smoke`, `emotion`, `report`) and `docs/oracle/S2_RUNBOOK.md` (Oracle Arm: `vad`, `turn`, `stream`).
- CI: no workflow change is needed (the S2 tests run in the existing `lab` job). The lock check that needs PyPI is a `network` test, which the existing `lab-network` job runs.

## Order
1. Ruler tests first (`tests/aqis_lab/test_s2_*.py`): frame invariants, VAD alignment, FIR, endpoint latency, emotion metrics (brief 5.2 items 1 to 5), plus the strict config, the lock, traced result files and the emotion selection. They failed on import before any `aqis_lab/live` code existed.
2. Code, config, lock, notebook, runbook.
3. Fast suite and gate green, PR `WP-1.2: S2 Live Stack benchmark`, merge, tag `s2-colab-1`.

## Definitions the ruler tests fix (so the numbers mean one thing)
- **Frame decisions:** a decision is made at the end of the frame that carries it. Onset lag = end of the first flagged frame that holds or follows the true onset, minus the onset. Offset lag = end of the flagged run that holds the last speech sample, minus the true end (negative: the end was clipped). A segment never flagged is a miss, not a lag.
- **FAR and MDR:** samples, over the whole frames the VAD scored (the same samples for reference and VAD), totals over totals, optionally leaving out a collar around every reference boundary (0 and 50 ms are both reported; 50 ms is the primary figure).
- **FIR:** pauses (gaps between words of at least 200 ms) that contain a trigger, over all such pauses. A trigger in speech is counted separately as spurious. Endpoint latency = first trigger after the last word, minus the end of that word.
- **UAR:** mean of the four class recalls; frustration recall = anger recall; phone cost = UAR(phone) / UAR(clean).
- Bootstrap intervals resample speakers (HarperValleyBank, Sprint 1 slices) or actors (CREMA-D), seeded.

## Where this build departs from the brief (each is listed in the pull request)
1. **Emotion model id.** `FunASR/emotion2vec_plus_seed` and `_base` do not exist on Hugging Face (404). The models are `emotion2vec/emotion2vec_plus_seed` and `emotion2vec/emotion2vec_plus_base`, pinned in `s2.yaml`.
2. **VAD reference.** The brief asks for "millisecond ground truth". No source has it for `sa_conv` (EdAcc has utterance times only), so `sa_conv` is not scored for VAD. The reference for `us_phone` is HarperValleyBank's *machine* word offsets and durations (merged when closer than 200 ms), and the non-speech clips have no speech by construction. The machine timings' own error is not known and may be near the 40 ms onset target, which the decision note must say.
3. **Clip counts.** The brief says 1,200 VAD segments; the set here is the 300 `us_phone` turns plus 100 non-speech clips, each under 5 conditions. The turn set takes 150 agent and 150 caller turns that have at least one 200 ms pause and a 1.5 s tail; if fewer qualify, the prep note says so.
4. **Frame size.** "20 ms frames (160 samples per packet)" holds at 8 kHz. The streaming bridge cuts 16 kHz audio into 20 ms frames of 320 samples (20 ms at 16 kHz, checked in `test_s2_frames.py`); each VAD uses its own native frame (Silero 512 samples = 32 ms, WebRTC 160, FireRed 160, TEN 256).
5. **TEN Turn Detection is not built.** It is a 7.6B-parameter LLM that reads the words spoken so far; it cannot run on the Oracle CPU, and the turn set carries no transcript at the time of each pause. The predictive candidate that is built is Pipecat Smart Turn v3.2 (CPU ONNX). TEN Turn can be added in a follow-up on Colab.
6. **Streaming is a rolling-window re-decode.** Parakeet TDT v2 is not a cache-aware streaming model, so each 160, 320 or 640 ms chunk re-reads the trailing 4 s with onnx-asr (INT8 and FP32, one thread). The report also gives the RTF of one whole-clip decode, which is what a bot pays at the end of a turn. `parakeet-unified-0.6b` streaming mode is not run (no CPU build; its NeMo streaming API was not checked).
7. **Jitsi path.** The live `aiortc` path is not built; `streaming.py` makes the same 20 ms RTP-style packets (sequence, timestamp, payload) from a clip, so the CPU numbers are the decode cost only.
8. **Fixed timers count whole VAD frames.** With the 32 ms Silero frame a 300 ms timer fires at 320 ms of silence; the Silero v5 smoothing also adds up to 128 ms before silence starts. Both appear in the endpoint latency, as they would in the bot.
9. **Gates.** Section 4 asks frustration recall >= 75% and section 7 asks >= 70% on phone audio; both are in `scoring.gates` and the scorecard checks the 70% gate and shows the 75% target.
10. **Locks.** One universal lock instead of two: FunASR (emotion2vec+) and TEN VAD carry an `x86_64` marker, so the Oracle VM installs neither; only `textgrid` builds from source there. `ten_vad` and the emotion models are not run on aarch64 (the brief accepts this for TEN).
11. **Pinned files.** Silero model files are fetched from GitHub at a pinned commit; their SHA-256 is recorded on first fetch in `models/pins.json` and checked afterwards (this cloud session downloads no models, so the hash cannot be in the config).
12. **CREMA-D licence.** The Hugging Face card (`confit/cremad-parquet`) states none; the upstream licence, ODbL-1.0, is recorded in the config and the manifest.
13. As in Sprint 1, libraries outside the phase 0 lock load through `aqis_lab.bench.lib()` so the two Phase 0 guard tests (stdlib-or-pinned imports; torch/NeMo only in the GPU adapter) stay unchanged.

## What this build does not check
The model wrappers (Silero, FireRed, TEN, WebRTC through the harness; Smart Turn; onnx-asr Parakeet; emotion2vec+ through FunASR; wav2vec2) and the corpus loaders (HarperValleyBank word timings, CREMA-D parquet) were not run here: the cloud session downloads no corpora or models. The Oracle and Colab smoke runs check them. Synthetic clips with known boundaries drove the VAD and turn stages and the scorecard end to end (`tests/aqis_lab/test_s2_pipeline.py`).
