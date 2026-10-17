# Sprint 1 (WP-1.1): speech-to-text benchmark for our callers

**Approved:** by the owner on 17 Oct 2026.
**When:** the week of 19 Oct 2026.
**GPU budget:** no more than 15 Colab units of the ~70 available.
**People:** Claude Code (Sonnet) builds it, the owner runs it on Colab, and Opus reviews the results with the owner.
**This file:** owner-owned; Claude reads it and never edits it.

## 1. The question
Which open speech-to-text models transcribe our callers best over phone lines and WebRTC? For each model we want to know where it breaks (accent, channel, noise, numbers, medical words, silence), how fast it is, and whether a mix of models would beat the best single one.

The answers decide four things:
1. **The live model.** It is fast, runs while the caller speaks, and feeds the filler choice.
2. **The heavy model.** It re-transcribes hard audio after the caller stops.
3. **Routing.** Whether to build routing between models (Sprint 3), using the oracle check in section 5.
4. **Fine-tuning.** Where fine-tuning could pay, so Sprint 3 can decide go or no-go.

## 2. Test set (slices)
All slices use public data and run as evaluation only. Their licences permit commercial evaluation; prep records each licence and stops if a dataset card says "non-commercial".

| Slice | Source (licence) | Stands for | Recording | Utterances | Conditions |
| --- | --- | --- | --- | --- | --- |
| `us_conv` | EdAcc test + validation, speakers whose L1 is "Mainstream US English" (CC BY-SA 4.0) | US callers, conversation | Zoom calls, wideband | 300 | all 7 |
| `sa_conv` | EdAcc test + validation, L1 Hindi, Urdu, Sinhalese or Indian English (CC BY-SA 4.0) | South Asian callers (Indian, Pakistani, Sri Lankan), same setup as `us_conv` | Zoom calls | 300 | all 7 |
| `sa_india` | Svarah test, gated (CC BY 4.0) | Indian English across 117 speakers: read speech, spontaneous speech and everyday tasks (IDs, brands) | phone app | 400 | all 7 |
| `medical` | Eka medical ASR evaluation set, English (MIT) | clinical words: drugs, findings and tests, with entity labels | clinical conversations | 300 | all 7 |
| `numbers` | Earnings-22 `chunked` test (CC BY-SA 4.0) | amounts, dates and figures from speakers worldwide | conference calls | 200 (each with at least 2 digit tokens) | all 7 |
| `us_phone` | HarperValleyBank (CC BY 4.0) | real 8 kHz customer-service calls with names, amounts and times | real telephone | 300 | native only |
| `anchor` | LibriSpeech test-other (CC BY 4.0) | checks our ruler against published numbers | audiobooks | 500 | clean, phone |
| `nonspeech` | MUSAN noise and music, plus digital silence (public domain or CC BY 4.0) | hallucination when there is no speech | none | 100 (60 noise and 20 music clips at −35 to −15 dBFS RMS, plus 20 silence) | clean, phone, webrtc |

**Selection rules** (all seeded and repeatable):
- **Length and content:** keep utterances of 1 to 30 s with at least 3 words after cleaning.
- **Speakers:** pick round robin across speakers, so no speaker dominates a slice.
- **Svarah:** stratify by speech type if the field exists, with 100 read, 150 spontaneous and 150 everyday.
- **Eka:** keep only utterances with at least one medical entity.
- **HarperValleyBank:** take half caller turns and half agent turns. Pick turns that contain digits first, up to half the slice.

**Bootstrap clusters:** every utterance keeps a speaker ID; where none exists, use the session or file ID. The bootstrap resamples these clusters.

**Reference cleaning:** cleaning rules are set per source in the config. Tags such as `<laugh>` are dropped. Utterances marked overlap, unintelligible or foreign-language are dropped. The prep report counts each rule's drops. Inspect each source's real tags before writing the rules.

**Not used in Sprint 1:**
- **Common Voice:** it is now distributed only through Mozilla Data Collective (account needed) and the English set is very large. Revisit it as fine-tuning data in Sprint 3.
- **Recording people:** we do not record anyone.

## 3. Conditions
| Condition | What it does |
| --- | --- |
| `clean` | the audio as published, at 16 kHz |
| `noise_10`, `noise_0` | MUSAN noise (free-sound) at 10 dB and 0 dB SNR, using `aqis_lab.packs.mix.mix_clip`, with a seeded noise clip and offset per utterance |
| `phone` | FIR band-pass 300 to 3400 Hz (511 taps, Kaiser β 8), then 8 kHz, G.711 μ-law (ITU reference algorithm), then back to 16 kHz |
| `phone_noise_10` | noise at 10 dB first (the caller's room), then `phone` |
| `webrtc` | Opus through libopus: 16 kHz mono, VOIP mode, 16 kbps, 20 ms frames, in-band FEC on, and 2% seeded random packet loss. A lost packet is rebuilt from the next packet's FEC when that packet arrived, otherwise by PLC. The output is trimmed by the encoder lookahead, so lengths match. |
| `webrtc_noise_10` | noise at 10 dB first, then `webrtc` |
| `native` | `us_phone` only: real 8 kHz telephone audio, upsampled to 16 kHz |

- **Paired noise:** one utterance uses the same noise draw in all three `*_10` conditions, so channel effects are paired.
- **Verified code:** the channel code in Appendix B was checked on 17 Oct 2026:
  - phone: within 0.1 dB at 1 and 3 kHz, −6 dB at 300 and 3400 Hz, and at least 96 dB rejection above 3.7 kHz;
  - Opus: 2% loss gave 58 of 3,001 packets lost, 57 rebuilt by FEC and 1 by PLC; same seed, same output.
- **Dependencies:** none beyond numpy and the system libopus, which Colab has.
- **Strength:** 16 kbps with 2% loss is a weak-network call. Real Jitsi calls usually run at a higher bitrate.

## 4. Models
| Name | Hugging Face ID | Stack | Role | Licence | Notes |
| --- | --- | --- | --- | --- | --- |
| `whisper-large-v3` | `openai/whisper-large-v3` | hf | heavy (baseline) | MIT | the reference everyone knows |
| `whisper-large-v3-turbo` | `openai/whisper-large-v3-turbo` | hf | live | MIT | fast Whisper |
| `parakeet-tdt-0.6b-v2` | `nvidia/parakeet-tdt-0.6b-v2` | nemo | live | CC BY 4.0 | card: test-other 3.19, μ-law 8 kHz 3.52; RTFx about 3,380 |
| `parakeet-unified-0.6b` | `nvidia/parakeet-unified-en-0.6b` | nemo | live | NVIDIA Open Model License | offline and streaming in one model; Phase 0 already ran it |
| `canary-qwen-2.5b` | `nvidia/canary-qwen-2.5b` | nemo | heavy | CC BY 4.0 | mean 5.63, test-other 3.10; trained on audio up to 40 s |
| `granite-speech-4.1-2b` | `ibm-granite/granite-speech-4.1-2b` | hf | heavy | Apache 2.0 | mean 5.33; can bias keywords (tested in Sprint 3) |
| `cohere-transcribe-2b` | `CohereLabs/cohere-transcribe-03-2026` | hf | heavy | Apache 2.0, gated | mean 5.42, test-other 2.37; its card warns that it transcribes noise and silence |
| `qwen3-asr-1.7b` | `Qwen/Qwen3-ASR-1.7B` | qwen | heavy | Apache 2.0 | mean 5.76; `qwen-asr` package |
| `voxtral-realtime-4b` | `mistralai/Voxtral-Mini-4B-Realtime-2602` | hf | live | Apache 2.0 | streaming; 480 ms delay is the card's recommended setting |

**Optional if time allows:** `ibm-granite/granite-speech-4.1-2b-nar` and `Qwen/Qwen3-ASR-0.6B`, both fast.
**Later sprints:** Kyutai STT and Nemotron streaming go to Sprint 2 (latency). Paid APIs are judged by their published numbers only.

**How to run every model:**
- **Decoding:** load each model once and warm it up on 2 clips. Batch clips by length. Use the card's default decoding (greedy where the card gives no other setting), force English, and use no keywords or context prompts.
- **What to record:** the resolved model revision (commit SHA), dtype, batch size, decoding settings, library versions and peak GPU memory.
- **Precision:** use bf16 on L4. NeMo models can use fp32 or fp16 if bf16 misbehaves; record which.
- **Timing:** call `torch.cuda.synchronize()` around each timed batch. Load time and warm-up are not timed.
- **Install recipes:** the Hugging Face cards, checked on 17 Oct 2026.
  - Cohere needs `transformers>=5.4.0` and the class `CohereAsrForConditionalGeneration`.
  - Voxtral Realtime needs `transformers>=5.2.0` and `mistral-common[audio]`.
  - Granite needs `transformers>=4.52.1`; use the prompt from its card.
  - Canary-Qwen needs `nemo-toolkit[asr,speechlm2]`, NeMo 3.0.0 as in the Phase 0 GPU lock, and `SALM.generate` with batched `audios` and `audio_lens`.
  - Qwen3-ASR needs `qwen-asr` 0.0.6 on its transformers backend. The card recommends Python 3.12; try Colab's 3.13 first, and use `uv venv --python 3.12` only if that fails.
- **If a model fails:** after one fix attempt and one changed approach, drop it from Sprint 1 and write the reason in the scorecard. Do not block the sprint on one model.

## 5. Metrics and report
1. **WER and CER** per model × slice × condition. Normalise with the `aqis_lab.scoring` MAIN variant (Whisper English normaliser, fillers removed). Corpus WER is total errors divided by total reference words. Give a 95% CI by speaker-cluster bootstrap (1,000 resamples, fixed seed).
2. **Target WER (the headline).** Take the 6 caller slices (`us_conv`, `sa_conv`, `sa_india`, `medical`, `numbers`, `us_phone`). For each, compute WER on its target conditions (`phone`, `phone_noise_10`, `webrtc`, `webrtc_noise_10`; for `us_phone`, `native`). The headline is the mean over the 6 slices, so each caller type counts once.
3. **Accent gap:** WER(`sa_conv`) divided by WER(`us_conv`) per condition. Both slices share the same recording setup, so the gap is fair.
4. **Channel and noise cost:** WER(condition) divided by WER(`clean`) per slice.
5. **Number accuracy:** the share of reference tokens with digits that the alignment marks as hits. Measured on `numbers`, `us_phone`, `sa_india` and `medical`.
6. **Medical term recall:** an Eka entity (drug, finding, test) counts as found when its normalised words appear, contiguous and in order, in the normalised hypothesis. Reported per category.
7. **Hallucination:** the share of `nonspeech` clips with at least one output word after normalisation, and mean words per clip, per condition.
8. **Speed:** RTFx when batched (L4, after warm-up), and batch-1 latency p50 and p95 on 50 clips of 3 to 8 s. Also report parameter count and peak GPU memory.
9. **Oracle check:** per slice × condition and on the target set, compare three WERs:
   - the best single model;
   - the oracle of all models (per utterance, the fewest errors among models);
   - the best pair of models.
10. **Paired comparisons:** for the top 4 models on the target set, the paired speaker bootstrap of the WER difference. Report each pair as "A beats B" or "too close to call".

**Report outputs:**
- **Scorecard** (`scorecard.md` + `scorecard.csv`): one row per model with:
  - role, target WER [CI] and clean WER;
  - accent gap, phone cost and WebRTC cost;
  - number accuracy, medical recall and hallucination rate;
  - RTFx, p50 latency, licence and status.
- **Cell table:** `cells.csv`, one row per model × slice × condition with WER, CI, CER, utterances and words.
- **Oracle and speed:** `oracle.csv` and `speed.csv`.
- **Weakness map:** `weakness_map.png`, a heatmap of WER relative to the best model in each cell. The scorecard also lists each model's 3 worst cells.

## 6. Build (Claude Code)
### 6.1 Files
- `aqis_lab/bench/`: glue in about eight short modules.
  - Loading:
    - `config.py`: strict load of `config/aqis_lab/s1.yaml`.
    - `sources.py`: dataset loaders and reference cleaning.
    - `select.py`: seeded, speaker-balanced selection, as pure functions.
  - Processing:
    - `conditions.py`: the channels from Appendix B, plus noise through `packs.mix`.
    - `models.py`: one small wrapper per family, imports inside the wrapper.
    - `run.py`: copy, then compute, then resume.
  - Output:
    - `score.py`: scoring through `aqis_lab.scoring`, plus entities, bootstrap, oracle, hallucination and speed.
    - `report.py`: tables and the heatmap.
  - Command line: `__main__.py`.
- `config/aqis_lab/s1.yaml`: the starting values in Appendix A. Revisions are filled in at the first run.
- Locks in `requirements/aqis_lab/`, hash-pinned for Python 3.13 x86_64 with the uv command in each header:
  - `s1-prep` (`datasets`, `huggingface_hub`, `soxr` for resampling, `matplotlib`). Compile it with `-c phase0.txt` and install it on top of the phase 0 lock. Decode audio with soundfile, or with Colab's ffmpeg for formats soundfile cannot read (Eka's m4a);
  - `s1-nemo`;
  - `s1-hf`;
  - `s1-qwen`.
  Each GPU stack gets its own venv on Colab, created with uv. The runner imports only numpy, pyarrow and the stack.
- `notebooks/aqis_lab/s1_asr_benchmark.ipynb`: follows the Phase 0 launcher pattern (Drive mount, clone at a tag with the `GITHUB_TOKEN` header, bootstrap, unit log).
  - **Cell 1:** `STAGE` and `MODELS`.
  - **Tokens:** `HF_TOKEN` comes from Colab Secrets and goes to the subprocess environment only.
  - **Last cell:** writes the unit log, then calls `google.colab.runtime.unassign()`, so the GPU stops costing units when the run ends.
- Ruler tests in `tests/aqis_lab/test_s1_*.py` (section 6.4).
- `docs/progress/WP-1.1/PLAN.md` and `EVIDENCE.md`: a few lines each; CI's gate requires both for a WP-1.1 pull request.

### 6.2 Command line
`python -m aqis_lab.bench <action>`, where the action is one of:
- `prep` (CPU);
- `smoke`, `run --stage anchor|pilot|full --model <name>` and `speed --model <name>` (GPU);
- `score` and `report` (CPU).

Every action reads the same config and writes to `--out` (a Drive folder).

### 6.3 Data and result files (on Drive under `AQIS_LAB/s1/`)
- **Prepared data:** `data/<slice>/<condition>.parquet`, one row per utterance. Columns:
  - identity: `utt_id`, `source`, `licence`;
  - audio: `audio` (16 kHz mono int16 bytes), `n_samples`, `duration_s`;
  - text: `ref_text` (as published), `ref_clean`;
  - speakers: `speaker`, `cluster`;
  - `meta` (JSON: accent, L1, gender, speech type, entities, noise draw, loss seed).

  `data/manifest.json` holds the config hash, git commit, dataset revisions, counts and hours. `data/LICENCES.md` holds the attributions.
- **Predictions:** `preds/<model>/<slice>__<condition>.parquet`, written atomically. An existing file is skipped, which makes runs resumable. Columns:
  - identity: `utt_id`, `model`, `hf_id`, `revision`, `stack`;
  - output: `hyp`;
  - batch timing: `batch_id`, `batch_audio_s`, `batch_wall_s`;
  - run facts: `versions` (JSON), `dtype`, `gpu`, `git_commit`, `seed`, `utc`.
- **Report:** `report/` holds the files from section 5. `report/s1_report.zip` holds the aggregates only.
- **What goes to the repo:** the owner uploads the aggregates to `docs/results/S1/`. Audio and per-utterance texts stay on Drive.

### 6.4 Ruler tests (expected values worked out by hand or from the definition)
1. **Cleaning and selection:**
   - per-source tag rules on fixed examples;
   - selection is deterministic for a seed, round robin across speakers, and respects the filters and N.
2. **Noise:** achieved SNR equals the target within 0.05 dB; the noise draw is seeded and shared across the `*_10` conditions.
3. **Phone:**
   - length is preserved;
   - tones at 1 and 3 kHz lose less than 0.5 dB; 5 kHz loses at least 50 dB;
   - μ-law decode gives 0x00 → −32124, 0x80 → 32124 and 0xFF → 0;
   - encode(decode(c)) = c for every code except 0x7F, which maps to 0xFF;
   - SQNR is at least 35 dB on a full-scale signal.
4. **WebRTC:**
   - same seed gives the same output;
   - the lost-packet count equals the seeded pattern;
   - FEC plus PLC counts add up to the losses;
   - length is preserved;
   - on a 10 s amplitude-modulated harmonic signal, the bitrate from the packet bytes is within 10% of 16 kbps.
5. **WER and CER:** bench scoring uses the MAIN normaliser, and corpus WER equals total errors over total reference words on a hand-worked example.
6. **Entities:** digit-token hits on hand-made pairs; medical entity matches, where a partial match or a match out of order counts as a miss.
7. **Bootstrap:**
   - the same seed gives the same CI;
   - it resamples speakers, not utterances: with 2 speakers of very different sizes, the CI differs from the utterance-level CI;
   - identical speakers collapse the CI to a point.
8. **Oracle:** a hand-made 3-model example gives the expected oracle and best pair.
9. **Hallucination:** counts only clips with output words after normalisation.
10. **Result rows:** every prediction row has all the columns in section 6.3, and a missing column fails.

The model wrappers have no unit tests. The `smoke` stage checks them on Colab: it prints hypotheses next to references, and fails if a model returns empty or identical text for speech clips.

### 6.5 CI and the pull request
- **CI change:** add one step to the `lab` job in `.github/workflows/aqis-lab-ci.yml`, before the fast suite: `sudo apt-get install -y --no-install-recommends libopus0`. Leave the other steps as they are; Phase 0 tests check them.
- **Pull request:** branch `s1/asr-bench`, titled `WP-1.1: S1 ASR benchmark`. Merge it when CI is green.
- **Tag:** after the merge, push the tag `s1-colab-1` (the notebook clones it). Then give the owner the tag and the notebook path.

## 7. Colab runs (owner)
### 7.1 One-time setup (about 15 minutes)
1. **Hugging Face:** Settings → Access Tokens → create a **Read** token. Then open these pages and accept their terms:
   - `ai4bharat/Svarah`
   - `CohereLabs/cohere-transcribe-03-2026`
   - any other gated page the prep names
2. **Colab:** open the key icon (Secrets) and add `HF_TOKEN` with notebook access on. `GITHUB_TOKEN` is already there from Phase 0.
3. **Drive:** make sure `MyDrive/AQIS_LAB` has at least 10 GB free.

### 7.2 Stages
| Stage | Runtime | About | Units |
| --- | --- | --- | --- |
| `prep`: download, select, clean, render the 7 conditions | CPU | 60 to 90 min | 0.1 |
| `smoke`, all models; then `anchor` for Parakeet TDT v2, Canary-Qwen and Cohere | L4 | 45 min, with installs | 1.3 |
| `pilot`: 100 per slice, in clean, phone and webrtc, all models | L4 | 90 min | 2.6 |
| `full`: everything else | L4 | 3 to 4 h | 6 |
| `speed`: batch-1 latency, all models | L4 | 30 min | 0.9 |
| `score` and `report` | CPU | 20 min | 0.03 |
| Reserve for reruns | | | 3 |
| **Total** | | | **about 14** |

- **Per session:** set `STAGE`, choose the runtime type, then run all cells. The last cell frees the runtime by itself.
- **Interruptions:** keep the browser tab open during long stages. If the session drops, rerun the same stage and finished files are skipped.
- **GPU type:** use an L4. If no L4 is offered, run only the NeMo models on a T4 (T4 has no bf16), or ask before using an A100.
- **Units left:** about 55 units remain for Sprint 2 (mostly CPU) and the Sprint 3 fine-tuning pilot. If your units renew before 2 November, say so and the pilot moves earlier.

### 7.3 Schedule
| When | What |
| --- | --- |
| Sat–Sun 17–18 Oct | upload the reset kit; Claude Code builds WP-1.1 |
| Mon 19 | `prep`, then `smoke` and `anchor` |
| Tue 20 | `pilot` (first ranking) |
| Wed 21 | `full` |
| Thu 22 | `speed`, `score` and `report`; upload the aggregates |
| Fri 23 | review with Opus; write the decision note |

## 8. Sprint 1 is done when
1. **Tests:** the ruler tests pass in the fast suite, and CI is green.
2. **Anchor:** on the 500-utterance anchor, clean WER is within ±0.7 points of the published LibriSpeech test-other figure for:
   - Parakeet TDT v2 (3.19);
   - Canary-Qwen (3.10);
   - Cohere (2.37).

   Parakeet's phone-to-clean ratio is between 1.0 and 1.4 (its card gives 1.10 for 8 kHz μ-law). **If the anchor fails, fix the ruler before reading any other number.**
3. **Coverage:** all 9 models ran on every slice and condition, or the scorecard gives a one-line reason for each gap.
4. **Traceability:** every prediction row can be traced to its model revision, slice, condition, seed, commit and GPU.
5. **Results:** the scorecard, cell table, oracle table, weakness map and decision note are in `docs/results/S1/`.
6. **Units:** no more than 15 units used, as recorded in `AQIS_LAB/logs/units.csv`.

## 9. Decision note (`docs/results/S1/DECISION.md`, one page, written at the review)
- **Live pick and runner-up.** Choose the lowest target WER among `live` models with a batch-1 p50 of 300 ms or less for 3 to 8 s clips on L4. Sprint 2 then checks CPU latency on Oracle.
- **Heavy pick and runner-up.** Choose the lowest target WER, then the best number accuracy and medical recall.
- **Routing.** Build it in Sprint 3 only if the best pair's oracle WER on the target set is no more than 0.85 × the best single model's. Otherwise stay with one model per role.
- **Fine-tuning candidates.** List a model and slice when:
  - the accent gap is 1.3 or more, or medical recall is below 80%; and
  - open training data exists for it.

  Give a go or no-go for the Sprint 3 pilot.
- **Surprises and open questions,** at most 5 lines.

## 10. Out of scope, and what to do when something fails
- **Out of scope:**
  - streaming and CPU latency, VAD and turn-end, and emotion (Sprint 2);
  - keyword biasing, fine-tuning and cascades (Sprint 3);
  - paid APIs;
  - long-form audio, and diarization.
- **A gated dataset or model is refused:** run without it, and mark it in the scorecard.
- **HarperValleyBank cannot be fetched:** drop `us_phone` and say so. The `phone` condition still covers telephony.
- **A source has fewer utterances than N:** take all of them and report the real N.

## Appendix A: `config/aqis_lab/s1.yaml` (starting values)
```yaml
schema: s1-v1
seed: 20261019
normaliser: main                    # aqis_lab.scoring MAIN variant
bootstrap: {resamples: 1000, unit: speaker, ci: 0.95}
utterance: {min_s: 1.0, max_s: 30.0, min_ref_words: 3}

sources:                            # prep records the resolved revision of each
  edacc: {hf: edinburghcstr/edacc, splits: [test, validation], licence: CC-BY-SA-4.0}
  svarah: {hf: ai4bharat/Svarah, splits: [test], licence: CC-BY-4.0, gated: true}
  eka_medical: {hf: ekacare/eka-medical-asr-evaluation-dataset, config: en, splits: [test], licence: MIT}
  earnings22: {hf: distil-whisper/earnings22, config: chunked, splits: [test], licence: CC-BY-SA-4.0}
  harper_valley_bank: {git: https://github.com/cricketclub/gridspace-stanford-harper-valley, licence: CC-BY-4.0}
  librispeech-test-other: {registry: librispeech-test-other}   # python -m aqis_lab registry fetch
  musan: {registry: musan}

slices:
  us_conv:   {source: edacc, l1: ["Mainstream US English"], n: 300}
  sa_conv:   {source: edacc, l1: [Hindi, Urdu, Sinhalese, "Indian English"], n: 300}
  sa_india:  {source: svarah, n: 400, stratify: {read: 100, spontaneous: 150, everyday: 150}}
  medical:   {source: eka_medical, n: 300, require_entities: true}
  numbers:   {source: earnings22, n: 200, min_digit_tokens: 2, max_s: 20.0, min_s: 3.0}
  us_phone:  {source: harper_valley_bank, n: 300, native_rate_hz: 8000, conditions: [native]}
  anchor:    {source: librispeech-test-other, n: 500, conditions: [clean, phone]}
  nonspeech: {source: musan, n: 100, mix: {noise: 60, music: 20, silence: 20}, level_dbfs: [-35, -15],
              length_s: [3, 8], conditions: [clean, phone, webrtc]}

conditions:
  clean: {}
  noise_10: {noise: musan-noise, snr_db: 10}
  noise_0: {noise: musan-noise, snr_db: 0}
  phone: {channel: g711_mulaw, band_hz: [300, 3400], fir_taps: 511, kaiser_beta: 8.0}
  phone_noise_10: {noise: musan-noise, snr_db: 10, channel: g711_mulaw}   # channel settings as in phone
  webrtc: {channel: opus, bitrate_bps: 16000, frame_ms: 20, fec: true, loss: 0.02}
  webrtc_noise_10: {noise: musan-noise, snr_db: 10, channel: opus}        # channel settings as in webrtc
default_conditions: [clean, noise_10, noise_0, phone, phone_noise_10, webrtc, webrtc_noise_10]
target_conditions: [phone, phone_noise_10, webrtc, webrtc_noise_10, native]
caller_slices: [us_conv, sa_conv, sa_india, medical, numbers, us_phone]

models:
  whisper-large-v3:       {hf: openai/whisper-large-v3, stack: hf, role: heavy, batch: 16, dtype: bf16, language: en}
  whisper-large-v3-turbo: {hf: openai/whisper-large-v3-turbo, stack: hf, role: live, batch: 32, dtype: bf16, language: en}
  parakeet-tdt-0.6b-v2:   {hf: nvidia/parakeet-tdt-0.6b-v2, stack: nemo, role: live, batch: 64}
  parakeet-unified-0.6b:  {hf: nvidia/parakeet-unified-en-0.6b, stack: nemo, role: live, batch: 64, mode: offline}
  canary-qwen-2.5b:       {hf: nvidia/canary-qwen-2.5b, stack: nemo, role: heavy, batch: 32,
                           prompt: "Transcribe the following: {audio}"}
  granite-speech-4.1-2b:  {hf: ibm-granite/granite-speech-4.1-2b, stack: hf, role: heavy, batch: 16, dtype: bf16,
                           prompt: "<|audio|>transcribe the speech with proper punctuation and capitalization."}
  cohere-transcribe-2b:   {hf: CohereLabs/cohere-transcribe-03-2026, stack: hf, role: heavy, batch: 32, dtype: bf16,
                           language: en, gated: true}
  qwen3-asr-1.7b:         {hf: Qwen/Qwen3-ASR-1.7B, stack: qwen, role: heavy, batch: 32, dtype: bf16, language: English}
  voxtral-realtime-4b:    {hf: mistralai/Voxtral-Mini-4B-Realtime-2602, stack: hf, role: live, batch: 16, dtype: bf16,
                           delay_ms: 480}
optional_models:
  granite-speech-4.1-2b-nar: {hf: ibm-granite/granite-speech-4.1-2b-nar, stack: hf, role: live}
  qwen3-asr-0.6b:            {hf: Qwen/Qwen3-ASR-0.6B, stack: qwen, role: live}

stages:
  smoke: {per_slice: 3, conditions: [clean, phone, webrtc]}
  anchor: {slices: [anchor], models: [parakeet-tdt-0.6b-v2, canary-qwen-2.5b, cohere-transcribe-2b]}
  pilot: {per_slice: 100, conditions: [clean, phone, webrtc]}
  full: {}
speed: {clips: 50, length_s: [3, 8], warmup: 3, batch: 1, from_slices: [us_conv, sa_conv], condition: clean}
anchor_published_test_other_wer: {parakeet-tdt-0.6b-v2: 3.19, canary-qwen-2.5b: 3.10, cohere-transcribe-2b: 2.37}
gpu: {default: NVIDIA L4, t4_ok_stacks: [nemo]}
```

## Appendix B: channel code (checked on 17 Oct 2026; adapt it, keep the behaviour)
```python
import ctypes, ctypes.util
import numpy as np

# Phone: FIR band-pass at 16 kHz, decimate to 8 kHz, G.711 mu-law (14-bit ITU reference algorithm), back to 16 kHz.
SEG_END = np.array([0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF])

def ulaw_encode(x):                       # int16 -> uint8 codes
    v = x.astype(np.int32) >> 2
    mask = np.where(v < 0, 0x7F, 0xFF)
    v = np.minimum(np.abs(v), 8159) + (0x84 >> 2)
    seg = np.searchsorted(SEG_END, v)
    u = np.where(seg >= 8, 0x7F, (seg << 4) | ((v >> (seg + 1)) & 0xF))
    return (u ^ mask).astype(np.uint8)

def ulaw_decode(u):                       # uint8 codes -> int16
    u = (~u.astype(np.int32)) & 0xFF
    t = (((u & 0x0F) << 3) + 0x84) << ((u & 0x70) >> 4)
    return np.where(u & 0x80, 0x84 - t, t - 0x84).astype(np.int16)

def bandpass_fir(fs=16000, lo=300.0, hi=3400.0, taps=511, beta=8.0):
    n = np.arange(taps) - (taps - 1) / 2
    h = (2 * hi / fs) * np.sinc(2 * hi / fs * n) - (2 * lo / fs) * np.sinc(2 * lo / fs * n)
    return h * np.kaiser(taps, beta)

def _conv_same(x, h):                     # zero-phase FFT convolution, same length as x
    n = len(x) + len(h) - 1
    m = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(h, m), m)[:n]
    d = (len(h) - 1) // 2
    return y[d:d + len(x)]

def phone_channel(x16, h=bandpass_fir()):
    y8 = _conv_same(x16.astype(np.float64), h)[::2]
    y8 = ulaw_decode(ulaw_encode(np.clip(np.round(y8), -32768, 32767).astype(np.int16))).astype(np.float64)
    up = np.zeros(len(x16)); up[::2] = y8[:(len(x16) + 1) // 2]
    return np.clip(np.round(2 * _conv_same(up, h)), -32768, 32767).astype(np.int16)

# WebRTC: Opus via libopus, seeded loss, FEC from the next packet when it arrived, else PLC.
_OPUS = ctypes.CDLL(ctypes.util.find_library("opus") or "libopus.so.0")
_OPUS.opus_encoder_create.restype = ctypes.c_void_p
_OPUS.opus_decoder_create.restype = ctypes.c_void_p
_OPUS.opus_strerror.restype = ctypes.c_char_p
_OPUS.opus_encode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16), ctypes.c_int, ctypes.c_char_p, ctypes.c_int32]
_OPUS.opus_decode.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int16),
                              ctypes.c_int, ctypes.c_int]
VOIP = 2048
SET_BITRATE, SET_COMPLEXITY, SET_INBAND_FEC, SET_PACKET_LOSS_PERC, GET_LOOKAHEAD = 4002, 4010, 4012, 4014, 4027

def _ok(code, what):
    if code < 0:
        raise RuntimeError(f"libopus {what}: {_OPUS.opus_strerror(code).decode()}")
    return code

def webrtc_channel(x, seed, sr=16000, bitrate=16000, loss=0.02, frame_ms=20):
    err = ctypes.c_int()
    enc = ctypes.c_void_p(_OPUS.opus_encoder_create(sr, 1, VOIP, ctypes.byref(err))); _ok(err.value, "encoder")
    dec = ctypes.c_void_p(_OPUS.opus_decoder_create(sr, 1, ctypes.byref(err))); _ok(err.value, "decoder")
    try:
        for req, val in ((SET_BITRATE, bitrate), (SET_COMPLEXITY, 10), (SET_INBAND_FEC, 1),
                         (SET_PACKET_LOSS_PERC, round(loss * 100))):
            _ok(_OPUS.opus_encoder_ctl(enc, ctypes.c_int(req), ctypes.c_int(val)), f"ctl {req}")
        la = ctypes.c_int32(); _ok(_OPUS.opus_encoder_ctl(enc, ctypes.c_int(GET_LOOKAHEAD), ctypes.byref(la)), "lookahead")
        n = sr * frame_ms // 1000
        total = len(x) + la.value
        padded = np.zeros(total + (-total) % n, np.int16); padded[:len(x)] = x
        buf, packets = ctypes.create_string_buffer(4000), []
        for i in range(0, len(padded), n):
            frame = np.ascontiguousarray(padded[i:i + n])
            k = _ok(_OPUS.opus_encode(enc, frame.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)), n, buf, 4000), "encode")
            packets.append(buf.raw[:k])
        lost = np.random.default_rng(seed).random(len(packets)) < loss
        pcm, out = (ctypes.c_int16 * n)(), np.empty(len(packets) * n, np.int16)
        fec = plc = 0
        for i, p in enumerate(packets):
            if not lost[i]:
                k = _OPUS.opus_decode(dec, p, len(p), pcm, n, 0)
            elif i + 1 < len(packets) and not lost[i + 1]:
                k = _OPUS.opus_decode(dec, packets[i + 1], len(packets[i + 1]), pcm, n, 1); fec += 1
            else:
                k = _OPUS.opus_decode(dec, None, 0, pcm, n, 0); plc += 1
            _ok(k, "decode")
            out[i * n:(i + 1) * n] = np.frombuffer(pcm, np.int16, count=n)
        return out[la.value:la.value + len(x)], {"packets": len(packets), "bytes": sum(map(len, packets)),
                                                 "lost": int(lost.sum()), "fec": fec, "plc": plc}
    finally:
        _OPUS.opus_encoder_destroy(enc); _OPUS.opus_decoder_destroy(dec)
```

## Appendix C: sources (checked on 17 Oct 2026)
- **Model cards:**
  - Parakeet TDT 0.6B v2 (WER, μ-law and MUSAN tables): https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
  - Parakeet Unified: https://huggingface.co/nvidia/parakeet-unified-en-0.6b
  - Canary-Qwen 2.5B: https://huggingface.co/nvidia/canary-qwen-2.5b
  - Granite Speech 4.1 2B: https://huggingface.co/ibm-granite/granite-speech-4.1-2b
  - Cohere Transcribe: https://huggingface.co/CohereLabs/cohere-transcribe-03-2026
  - Qwen3-ASR 1.7B: https://huggingface.co/Qwen/Qwen3-ASR-1.7B
  - Voxtral Mini 4B Realtime: https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602
- **NeMo Speech 3.0.0 SpeechLM2 (SALM):** https://docs.nvidia.com/nemo/speech/3.0.0/speechlm2/intro.html
- **Model overview, July 2026:** https://www.marktechpost.com/2026/07/23/best-open-speech-recognition-asr-models-in-2026-wer-languages-latency-and-license-compared/
- **Datasets:**
  - EdAcc: https://huggingface.co/datasets/edinburghcstr/edacc and https://arxiv.org/abs/2303.18110
  - Svarah: https://huggingface.co/datasets/ai4bharat/Svarah and https://arxiv.org/abs/2305.15760
  - Eka medical ASR: https://huggingface.co/datasets/ekacare/eka-medical-asr-evaluation-dataset
  - Earnings-22: https://huggingface.co/datasets/distil-whisper/earnings22 and https://arxiv.org/abs/2203.15591
  - HarperValleyBank: https://github.com/cricketclub/gridspace-stanford-harper-valley and https://arxiv.org/abs/2010.13929
- **Common Voice move to Mozilla Data Collective:** https://huggingface.co/spaces/mozilla-foundation/README
