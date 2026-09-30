# Vosk adapter

The lab's first live speech-to-text adapter (FR-0.7-02). It runs Vosk 0.3.45 on the CPU with the model `vosk-model-small-en-us-0.15`. The code is in `aqis_lab/adapters/vosk_stt.py` (class `VoskAdapter`, event-log component `live_stt`), with the model download in `aqis_lab/adapters/model_cache.py`.

The runner uses it in two tasks (`docs/runner/RUNNER.md`):
- `vosk-batch`: every clip, as fast as the CPU allows (mode `batch`);
- `vosk-realspeed`: 20 ms frames delivered at real time by `aqis_lab/realspeed.py` (mode `realspeed_cpu`).

## Model
The pin is in `config/aqis_lab/models.yaml`:

| Item | Value |
| --- | --- |
| URL | `https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip` |
| Size | 41,205,931 bytes |
| SHA-256 | `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498` |
| Licence | Apache-2.0 |
| Files | 14 member files, each pinned by SHA-256 and size |

Alphacephei publishes no checksum. The archive pin is the SHA-256 of the download made while planning (PLAN.md, finding 3). The Colab and Oracle runs download the archive again, so they confirm the pin independently.

**Cache.** The default cache is `data/raw/aqis_lab/models/` on local disk (git-ignored). `--model-cache` chooses another folder. A cache on a Google Drive mount is refused. The model is kept in `<cache>/vosk-model-small-en-us-0.15/<first 16 hex of the SHA-256>/`.

How a fetch works:
1. The archive is downloaded to a `.partial` file.
2. Its size and SHA-256 are checked **before** anything is extracted.
3. It is extracted into a `.staging-…` folder, and every member is checked against its own pin. A member that is missing, extra, changed or outside the model folder stops the fetch.
4. Only then is the folder renamed into place, made read-only and given a `.verified.json` marker.

Every later load checks all 14 files again. Any mismatch raises an error with code `model-checksum` that names the file and the expected and actual values. Nothing unverified is ever loaded. A download failure raises an error with code `model-download`.

## OpenBLAS kernel
`libvosk.so` for x86_64 contains OpenBLAS, which picks a CPU kernel when it loads. Different kernels can change a transcript. Measured on the 60 smoke clips, Haswell and SkylakeX differ from Prescott on one clip (PLAN.md, finding 5). So the adapter fixes the kernel (owner decision, question 6):
- It sets `OPENBLAS_CORETYPE=Prescott` and `OPENBLAS_NUM_THREADS=1` only while `vosk` is imported, then restores the process environment. Child processes are not affected.
- It then reads the active kernel from the library itself (the `gotoblas` table against each `gotoblas_<KERNEL>` table) and the thread count (`openblas_get_num_threads`).
- If `vosk` was already loaded in the process with another kernel or thread count, it raises `vosk-library-loaded`. The fix is to start a new process.
- The aarch64 library (Oracle) has no kernel dispatch. The adapter records it as a fixed build. It needs `libatomic.so.1` from the Ubuntu package `libatomic1` (`docs/oracle/ORACLE_RUNBOOK.md`, OC-0.7-02).

## Feeding and events
- Input is 16 kHz mono 16-bit audio. It is fed in 20 ms frames (320 samples) in both tasks; the last part-frame is fed as it is. The frame size matters: 20 ms and 500 ms feeds gave different transcripts on 6 of 60 clips (finding 5).
- A `partial` event is written whenever the partial text changes.
- A `final` event is written for every Vosk result and for the closing `FinalResult()`. It holds `text` and, when the result has words, `words` (`word`, `start_s`, `end_s`, from `SetWords(True)`).
- Each event's `audio_time_s` is the audio fed so far, in seconds.
- Any failure while opening or processing writes one `error` event (`run_continues: false`), then raises (`aqis_lab/adapters/base.py`, `guarded`).

## Result row fields
After `clip_id`, `run_card_id`, `task` and `task_version`:

| Field | Meaning |
| --- | --- |
| `text` | The clip transcript: the texts of the clip's `final` events joined by single spaces, empty ones left out |
| `text_sha256` | SHA-256 of `text` as UTF-8; this is what `parity` compares |
| `finals`, `partials`, `words`, `events` | Counts for the clip |
| `audio_s` | Clip length in seconds |

`vosk-realspeed` rows hold the same fields plus `first_partial_latency_ms`, `finalisation_latency_ms`, `max_frame_lag_ms` and `wall_s` (definitions in `docs/runs/PHASE0_SMOKE.md`).

## Run card
The `model` block: family `vosk`, name `vosk-model-small-en-us-0.15`, version `0.15`, checksum = the archive's SHA-256. Settings:

| Setting | Value |
| --- | --- |
| `sample_rate_hz` | 16000 |
| `feed_samples` | 320 |
| `words` | true |
| `partial_events` | `when the partial text changes` |
| `library` | `vosk 0.3.45` |
| `openblas_coretype` | `Prescott` |
| `openblas_num_threads` | 1 |
| `log_level` | -1 |

## Same result everywhere
The same samples, model, kernel and frame size give byte-identical events and text, run after run (finding 5). The aarch64 build gave the same 60 transcripts in emulation (finding 6). The real Oracle and Colab runs are checked by `parity` (OC-0.7-03). Word confidences are not compared: they differ in the last digit between builds.

## Packages
`vosk==0.3.45` is in `requirements/aqis_lab/phase0.txt`. Its dependency `srt` exists only as a source archive. It is the one approved source build (owner decision, question 2): it is built with the lock's own hash-checked setuptools (`--build-constraints`), on Oracle too (`SOURCE_BUILDS=(srt)` in `aqis_lab/deploy/oracle_setup.sh`).
