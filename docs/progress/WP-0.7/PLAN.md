# PLAN — WP-0.7 First adapters and the smoke run

Spec: `docs/specs/phase-0/WP-0.7-adapters-smoke-run.md`  ·  Planned by session: https://claude.ai/code/session_01DHNEPSgrExgeGVsAYja18g  ·  Date: 2026-09-30
Branch: `claude/clever-wright-gmps92`  ·  Base: `origin/main` at `97de2ed`  ·  Depends on: WP-0.3, WP-0.5, WP-0.6 (all MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, three real components run on the smoke pack end to end, on the cloud VM, on Colab and on Oracle, and one command proves the Vosk results are identical across the three machines.
- **Adapters.** A common adapter contract (`aqis_lab/adapters/base.py`) and three adapters:
  - Vosk `vosk-model-small-en-us-0.15` on CPU, the model downloaded to a cache and checked by SHA-256;
  - NVIDIA Parakeet Unified (`nvidia/parakeet-unified-en-0.6b`) in offline mode on a GPU through NeMo, which refuses to run without a GPU;
  - one existing harness VAD, imported from `vad_adapters/` without changing it (you name which; question 1).

  Every adapter writes event-log v1 events. On a failure it writes an `error` event and then raises.
- **Real-speed feeder** (`aqis_lab/realspeed.py`). It feeds 20 ms frames no faster than real time, pins itself to the reserved timing cores on Oracle, and reports first-partial and finalisation latency.
- **Smoke run.** `python -m aqis_lab phase0 smoke --target cloud|colab|oracle` does the following:
  - runs Vosk in batch on all 60 clips, the harness VAD on all 60 clips, and real-speed Vosk on 5 clips;
  - on Colab only (the GPU target), runs Parakeet and measures its per-clip GPU time on 5 clips;
  - scores the speech clips with the WP-0.3 scorer, adds every row to the results store and checks that `trace` works on every row;
  - writes a result bundle and `PHASE0_SMOKE.md`, where every number cites the row it comes from.
- **Parity.** `python -m aqis_lab parity <bundle-A> <bundle-B>` compares transcript hashes and WER per clip and in total, and lists every difference.
- **Locks.** `requirements/aqis_lab/phase0.txt` gains Vosk and the harness VAD's package. The new `phase0-gpu.in`/`phase0-gpu.txt` pin NeMo and torch for Colab.
- **Documents.** `docs/adapters/VOSK.md`, `PARAKEET_UNIFIED.md`, `HARNESS_VAD.md`, and `docs/runs/PHASE0_SMOKE.md`.
- **Debt.** The four accepted debts that target WP-0.7 are closed: DEBT-013, DEBT-014, DEBT-015 (items 2 to 4) and DEBT-017.

## What I found in the repository and environment (read-only inspection and scratchpad experiments)
Nothing in the repository was changed. Every experiment below ran in the session scratchpad.

1. **Spec sources.**
   - The "Read first" blueprint sections ("VAD and end-of-turn test plan", "Live transcription test plan") are not in the repository, as in earlier WPs. You said the specs in `docs/specs/phase-0/` are authoritative. This plan relies on the spec, the Phase 0 overview, and the event log and run card contracts (`docs/contracts/EVENT_LOG.md`, `RUN_CARD.md`).
   - Where the blueprint would define a detail (the latency definitions, question 7), I ask you instead of guessing.
   - `aqis-kit-patch-3/docs/specs/phase-0/WP-0.7-adapters-smoke-run.md` is byte-identical to the spec (`cmp`).
2. **Dependencies.**
   - WP-0.3, WP-0.5 and WP-0.6 are MERGED. No blocker is open.
   - Four accepted debts name WP-0.7 as their target (`docs/progress/DEBT.md`):
     - **DEBT-013:** check NFR-0.5-01's 5 % runner overhead on a real workload.
     - **DEBT-014:** route `score`, `pack build`, `registry build` and `registry fetch` through the Drive guard before anything runs on Colab.
     - **DEBT-015:** items 2 to 4 (sync and store error paths).
     - **DEBT-017:** the real-speed feeder must call `pin_for_mode`, with a thread-affinity test.
3. **Network (the spec's owner need).**
   - `alphacephei.com` is **already reachable** from this VM: the model page gives HTTP 200, and I downloaded the model zip. So no allowlist change is needed for Vosk.
   - Alphacephei publishes no checksum (`….zip.sha256` returns 404). The pin therefore comes from my download:
     - 41,205,931 bytes;
     - SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`;
     - MD5 `09ab50ccd62b674cbaa231b825f9c1cb`.

     The Colab and Oracle runs download it again independently, so they confirm the pin.
   - `huggingface.co` and its file host `us.aws.cdn.hf.co` are reachable. `download.pytorch.org` and `api.ngc.nvidia.com` are blocked (HTTP 403 from the proxy).
4. **Vosk package.**
   - `vosk` 0.3.45 (Apache-2.0) has wheels for Linux x86_64 and aarch64.
   - Its `__init__.py` imports `srt`, `requests`, `tqdm` and `websockets`, and `srt` 3.5.3 (MIT, one pure-Python file) **exists only as a source archive**. Every other new pin has x86_64 and aarch64 wheels for Python 3.13.
   - WP-0.6 made "no source builds on Oracle" a rule: `oracle_setup.sh` step 4 and the existing test `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` both require a wheel for every pin. So adding Vosk needs your decision (question 2).
   - What I measured about building `srt` from source:
     - uv 0.8.17 can build `srt` with `--require-hashes` while taking its build tool, setuptools, from the hash-pinned lock (`--build-constraints`). The build used exactly the constrained setuptools version.
     - When the lock is also its own constraints file (this plan's design), the build installs the lock's setuptools from the same download uv hash-checked for the main install. A wrong setuptools hash in the lock stops the install.
     - A wrong hash in a separate constraints file also stopped the install.
     - `--only-binary :all: --no-binary srt` still requires wheels for every other package.
5. **Vosk results depend on three things beyond the audio.** All three are measured on the 60 smoke clips.
   - **Repeatability.** The same process settings give byte-identical output run after run.
   - **Chunk size.** Feeding 20 ms chunks and feeding 500 ms chunks gives different transcripts on 6 of 60 clips. So batch mode and real-speed mode both feed 20 ms frames, and the frame size is a recorded setting.
   - **OpenBLAS kernel.** `libvosk.so` (x86_64) contains OpenBLAS with run-time CPU dispatch (kernels Sandybridge, Haswell, SkylakeX, Zen, …). This VM's Xeon is not recognised, so it falls back to the `Prescott` kernel. Forcing kernels with `OPENBLAS_CORETYPE`:
     - Prescott and Sandybridge give the same transcripts;
     - Haswell and SkylakeX differ from Prescott on 1 clip (`ls-test-other-2609-156975-0000`: "frayed" against "freight");
     - word confidences differ between kernels even where the text is the same (for example on 32 clips between Haswell and SkylakeX).

     So Colab's CPU could pick another kernel than this VM and change a transcript. The number of OpenBLAS threads made no difference (60/60 clips identical with 1 and with 4 threads).
6. **Arm (Oracle) was checked in emulation.**
   - I ran the aarch64 Vosk wheel, the same file Oracle will install, under `qemu-aarch64-static -cpu neoverse-n1` with Ubuntu 24.04 arm64 Python.
   - **Transcripts:** all 60 were identical to x86 with the Prescott or Sandybridge kernel. They differed from Haswell and SkylakeX on the same 1 clip.
   - **Confidences:** the last digit differs on 34 clips (for example `0.845459` against `0.84546`). Parity does not compare confidences.
   - The aarch64 library has no kernel dispatch, and it needs `libatomic.so.1` (package `libatomic1`).
   - Emulation is exact IEEE arithmetic, but it is not the real Neoverse-N1. OC-0.7-02 is the proof.
7. **Speed on this VM.**
   - Vosk batch over all 60 clips (390.9 s of audio) takes 68 to 74 s in one thread, a real-time factor of about 0.18.
   - The 5 real-speed clips I propose last 25.6 s in total.
   - A full cloud smoke run should therefore take about 3 to 4 minutes, well inside NFR-0.7-01's 15 minutes.
   - One Vosk run over the pack writes 695 partial and 79 final events. WebRTC VAD mode 2 at 20 ms writes 340 speech start and end events. A bundle is a few MB.
8. **Harness VADs** (`vad_adapters/`, protected, read only).
   - **TEN VAD:** its library exists only for Linux x86_64 (`config/aqis_lab/harness_assets.json`, owner decision F16). It cannot run on the Arm Oracle VM, and it has extra licence conditions.
   - **FireRedVAD:** needs torch and downloaded weights. Neither is in the lab's CPU lock.
   - **WebRTC VAD** (`webrtc_vad_adapter.py`, package `webrtcvad-wheels` 2.0.14, MIT, fixed-point C): has x86_64 and aarch64 wheels for Python 3.13.
   - Every adapter gives one decision per frame. The harness's own scoring does no smoothing, and its framing helper `chunk_audio_stream` drops a final part-frame.
   - The registry's `get_adapter(name, frame_size_samples=…)` runs the harness's own conformance check before handing an adapter out.
9. **Parakeet Unified.**
   - Model: Hugging Face `nvidia/parakeet-unified-en-0.6b`, revision `fe53cd885760c96b6a5f51a0bfd362cb4584a98b`, file `parakeet-unified-en-0.6b.nemo`, 2,474,055,680 bytes, SHA-256 `ec23ed9150c8fde49072c3e2d61678ab903dbcef389d658db833420cbc1da35b`. My download matched that hash.
   - Licence: NVIDIA Open Model License.
   - The model card names **NeMo 2.7.3** as its runtime. It lists Volta, Ampere, Hopper and Blackwell GPUs, **not Turing (the T4)**.
10. **NeMo cannot simply be added on top of the CPU lock.**
    - NeMo 2.7.3 needs `jiwer<4`. The CPU lock pins `jiwer==4.0.0` (WP-0.3 approval, used by the scorer cross-check tests).
    - NeMo 2.7.3 and 3.0.0 both need `lightning<=2.4.0`, which needs `packaging<25`. The CPU lock has `packaging==26.3`.
    - With `packaging` at 24.2 in the CPU lock, **NeMo 3.0.0 resolves as pure extras for Python 3.13 on x86_64**:
      - 136 extra pins;
      - the 22 pins it shares with the CPU lock are all unchanged;
      - one extra, `antlr4-python3-runtime` 4.9.3 (needed by `hydra-core`), is again a source-only package.
    - NeMo 3.0.0 on CPU, in a scratch venv from that resolution:
      - loads the model (`EncDecRNNTBPEModel`, 29 s);
      - `transcribe([path])`, the model card's call, **fails** with `AttributeError: 'NoneType' object has no attribute 'get'`, because the model's config has no `validation_ds`;
      - `transcribe([numpy array])` **works**. It gave "Only there are two sorts of cloud and fire" and "Then Moses was afraid and said Surely the thing is known", both correct.
    - This was a feasibility check only. The adapter itself refuses to run without a GPU.
11. **torch for the T4.**
    - PyPI's torch 2.11 and later are CUDA 13 builds (`cuda-toolkit 13.0.x`; the resolution picked torch 2.14.0). CUDA 13 needs NVIDIA driver 580 or newer.
    - The Colab probe shows torch `2.11.0+cu128` preinstalled, but not the driver version.
    - If the Colab driver is older than 580, the lock must take torch `2.11.0+cu128` from `download.pytorch.org`, which is blocked here (question 5).
12. **What the contracts and existing tests fix.**
    - **Event log.**
      - `seq` must run 0, 1, 2, … per `run_id` in one file. So only a whole run's joined `events.jsonl` validates, not a single shard's part.
      - `host_id`, `wall_time_ns` (monotonic) and `wall_clock_utc` are required.
    - **Run card.**
      - It is closed except `model.settings` and step `params`.
      - It has one `lock` field and no place for a clip subset.
      - It holds `machine`, so the three machines' run cards always differ. Parity must compare per clip, not per run card.
    - **Runner.**
      - `test_FR_0_5_06_kill_and_resume…` expects exactly two files per finished shard.
      - `test_FR_0_5_05_runner_doc_matches_code` expects the marker's keys to equal the `done.json` line of `RUNNER.md`.
      - So a `clip-stats` run folder must stay exactly as it is. Event files and event marker fields exist only for tasks that write events.
    - **Doctor.** Its lock check requires the installed packages to equal `phase0.txt` exactly (`_check_lock`), so a Colab GPU environment would fail it today.
    - **Machine facts.** The scan in `tests/aqis_lab/test_aqis_platform.py` forbids `nvidia-smi`, `/proc/` and similar outside `aqis_lab/platform.py`. The GPU check and the host name therefore come from `aqis_lab.platform`.
    - **Git.** `.gitignore` ignores `*.jsonl`, so bundles are committed as one `.tar` file (question 11).
    - **Colab launcher.** `test_FR_0_5_08_launcher_commands_exist_and_parse` fixes the existing launcher's command sequence (`drive`, `unitlog`, `doctor`, `run`, `unitlog`), so the smoke gets its own launcher notebook (question 13).
13. **Baseline.** Fast suite at `97de2ed` on this VM: `1640 passed, 25 deselected in 215.13s`.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.7-01 | `Adapter` base class with the attributes `component` (event-log enum), `model_block()` (run-card v1 `model` block: family, name, version, checksum, settings) and `mode`, and the steps `open()`, `process_clip(clip, samples, sink)` and `close()`. An `EventSink` fills every envelope field (`run_id`, `run_card_id`, `seq`, `component`, `clip_id`, audio time or its reason, monotonic `wall_time_ns`, `wall_clock_utc`, `host_id`) and validates each record with `validate_event` **before** keeping it. `guarded(adapter, …)` catches any failure, writes one `error` event (`code`, `message`, `run_continues: false`) and raises `AdapterError` from the cause. Details under "Adapter contract" | `aqis_lab/adapters/__init__.py`, `aqis_lab/adapters/base.py` | `aqis_lab/platform.py`: new `host_name()` only | `test_FR_0_7_01_every_adapter_declares_component_model_and_settings`, `test_FR_0_7_01_events_validate_against_event_log_v1` (must-catch 1; every event of real Vosk, harness VAD and real-speed runs, record by record and as whole files with `validate_event_lines`), `test_FR_0_7_01_sink_refuses_invalid_event`, `test_FR_0_7_01_adapter_failure_emits_error_event_and_raises` (must-catch 2; real failures: damaged Vosk model files, an 8 kHz clip for the VAD), `test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_7_01` |
| FR-0.7-02 | Vosk 0.3.45 with `vosk-model-small-en-us-0.15`. `model_cache.fetch(pin)` downloads to `<cache>/models/<name>/`, checks size and SHA-256 **before** extracting, extracts through a staging folder, and checks every extracted file against per-file SHA-256 values pinned in `config/aqis_lab/models.yaml`. Every later load checks them again. Before `libvosk.so` loads, the adapter fixes the OpenBLAS kernel and 1 thread (question 6), then confirms the active kernel from the library's own table. It feeds 20 ms chunks and writes a `partial` event when the partial text changes, and a `final` event (with `words` from `SetWords(True)`) for every Vosk result plus the closing `FinalResult()`. Details under "Vosk" | `aqis_lab/adapters/vosk_stt.py`, `aqis_lab/adapters/model_cache.py`, `config/aqis_lab/models.yaml`, `docs/adapters/VOSK.md` | `requirements/aqis_lab/phase0.in` and `phase0.txt` (question 2 and 3) | `test_FR_0_7_02_model_downloaded_to_cache_and_verified` (`network`), `test_FR_0_7_02_model_rejected_when_checksum_differs` (must-catch 4; a real archive served from a local folder with a pin that does not match; nothing is extracted), `test_FR_0_7_02_changed_model_file_rejected_at_load` (must-catch 4), `test_FR_0_7_02_emits_partial_and_final_events_with_word_times` (`network`), `test_FR_0_7_02_same_input_gives_identical_transcript` (`network`), `test_FR_0_7_02_openblas_kernel_pinned_and_verified` (`network`, in a subprocess), `test_FR_0_7_02_refuses_when_vosk_already_loaded_with_other_kernel` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_7_02 -m "not gpu and not colab and not oracle"` |
| FR-0.7-03 | Parakeet adapter, offline mode, NeMo pinned in `phase0-gpu.txt` (questions 3 to 5). `open()` checks for a GPU (`aqis_lab.platform.gpu_type`), then that torch sees CUDA, then that NeMo is installed. Only then does it import torch and NeMo, fetch the `.nemo` file through `model_cache` (pinned revision, size, SHA-256), and load it with `restore_from(…, map_location="cuda")`. It transcribes in-memory audio (finding 10). With no GPU, no CUDA or no NeMo it raises `PlatformError` with a plain message naming the missing piece and `phase0-gpu.txt`. It is never skipped or replaced | `aqis_lab/adapters/parakeet_unified.py`, `requirements/aqis_lab/phase0-gpu.in`, `requirements/aqis_lab/phase0-gpu.txt`, `docs/adapters/PARAKEET_UNIFIED.md` | `aqis_lab/deploy/dev_bootstrap.sh` (`--gpu`; details under "Locks and installs") | `test_FR_0_7_03_refuses_without_gpu` (must-catch 3), `test_FR_0_7_03_refuses_without_nemo`, `test_FR_0_7_03_colab_smoke_without_gpu_fails_never_skips` (must-catch 3), `test_FR_0_7_03_gpu_lock_is_hashed_and_layers_on_cpu_lock`, `test_FR_0_7_03_gpu_lock_header_binds_cpu_lock_sha256`, `test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter`, `test_FR_0_7_03_parakeet_transcribes_on_gpu` (`colab`, `gpu`) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_7_03 -m "not gpu and not colab"` |
| FR-0.7-04 | Wraps the harness VAD you name (question 1; recommended WebRTC mode 2) through `vad_adapters.adapter_registry.get_adapter`, which also runs the harness's own conformance check. It uses 20 ms frames (the harness's `chunk_audio_stream`, whose part-frame rule is kept and recorded). It writes `speech_start` at the first speech frame of each run of speech frames, and `speech_end` at the end of its last speech frame. The harness files are imported, never copied or changed | `aqis_lab/adapters/harness_vad.py`, `docs/adapters/HARNESS_VAD.md` | `phase0.in`/`phase0.txt` (`webrtcvad-wheels` if question 1 (a)) | `test_FR_0_7_04_wraps_named_harness_vad_without_modifying_harness` (the imported module file is under `vad_adapters/`, and `git diff` of the protected harness paths is empty), `test_FR_0_7_04_emits_speech_start_and_speech_end`, `test_FR_0_7_04_segments_follow_frame_decisions` (expected segments computed in the test from `webrtcvad` directly), `test_FR_0_7_04_silence_gives_no_segment`, `test_FR_0_7_04_vad_package_has_x86_64_and_aarch64_builds` (`network`) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_7_04` |
| FR-0.7-05 | `RealSpeedFeeder` cuts a clip into 20 ms frames (320 samples; the last part-frame too, since Vosk takes any length). It delivers frame *k* no earlier than `t0 + (k+1) × 20 ms` on the monotonic clock, and checks the clock again before each delivery. A slow adapter delivers frames late, never skips one, and the lag is recorded. It writes a `timing_mark` `audio-end` at the last delivery. Every event carries audio time and wall time. Before it starts, the feeder calls `cores.pin_for_mode("realspeed_cpu")` (DEBT-017). First-partial and finalisation latency are computed from the event log by the definitions of question 7 | `aqis_lab/realspeed.py` | — | `test_FR_0_7_05_feeder_never_faster_than_real_time` (must-catch 5; each delivery at or after its deadline, and total time at least the clip's length, with a fast real adapter), `test_FR_0_7_05_frames_are_20_ms`, `test_FR_0_7_05_slow_adapter_frames_delivered_late_not_skipped`, `test_FR_0_7_05_every_event_has_audio_and_wall_time`, `test_FR_0_7_05_reports_first_partial_and_finalisation_latency` (expected values computed in the test from the events and the definitions), `test_FR_0_7_05_feeder_pins_every_thread_to_timing_cores` (DEBT-017; Oracle cores test double as in WP-0.6; reads `Cpus_allowed_list` of every thread of the running timing process) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_7_05` |
| FR-0.7-06 | Task `parakeet-compute-delay`, mode `gpu_compute_delay`, on the 5 subset clips (question 8). The model loads once, and its load time is recorded. One untimed warm-up transcription runs first (question 7). Each clip is timed on the monotonic clock around `transcribe`, with `torch.cuda.synchronize()` before the stop. The GPU type comes from `aqis_lab.platform` and is recorded in the run card, each row and the report | in `aqis_lab/adapters/parakeet_unified.py` | `aqis_lab/runner/tasks.py` (below) | `test_FR_0_7_06_compute_delay_rows_hold_gpu_and_per_clip_time` (a GPU test double, which the rules allow for GPUs, drives the real timing code), `test_FR_0_7_06_warm_up_not_timed`, `test_FR_0_7_06_gpu_compute_delay_on_colab_t4` (`colab`, `gpu`) | OC-0.7-01 |
| FR-0.7-07 | `phase0 smoke --target {cloud,colab,oracle} [--out DIR] [--store DIR] [--model-cache DIR] [--work-dir DIR] [--drive-mount DIR]`. It stops at once if the target is not this platform. Then it: <br>1. fetches and verifies the models; <br>2. runs, each as a resumable runner run with its own run card: `vosk-batch` (60 clips), `harness-vad` (60), `vosk-realspeed` (5), and on `colab` also `parakeet-offline` (60, question 9) and `parakeet-compute-delay` (5); <br>3. scores the transcripts with the WP-0.3 `score` command (natural speech and synthetic TTS separately, question 10); <br>4. adds every run and score folder to the results store; <br>5. validates every run card and `events.jsonl` and runs `trace` on every stored row; <br>6. writes the bundle and `PHASE0_SMOKE.md`. <br>Running it again resumes: finished shards are skipped and identical rows are not stored twice. Details under "Smoke run" | `aqis_lab/smoke.py`, `aqis_lab/commands/phase0.py`, `config/aqis_lab/phase0_smoke.yaml`, `docs/runs/PHASE0_SMOKE.md` | `aqis_lab/__main__.py`: `COMMANDS` (`phase0`); runner files (below) | `test_FR_0_7_07_target_must_match_platform`, `test_FR_0_7_07_smoke_creates_valid_run_card_for_every_run`, `test_FR_0_7_07_vosk_batch_on_all_60_clips`, `test_FR_0_7_07_speech_clips_scored_with_wp03_scorer` (the tables equal an independent `score` run on CSVs the test builds from the manifest and `results.jsonl`), `test_FR_0_7_07_harness_vad_on_all_clips`, `test_FR_0_7_07_realspeed_vosk_on_5_clips`, `test_FR_0_7_07_parakeet_only_on_gpu_target_and_report_says_so`, `test_FR_0_7_07_every_report_number_traces_to_a_row` (each number in the report is recomputed from the row or score file it cites), `test_FR_0_7_07_trace_works_on_every_row`, `test_FR_0_7_07_second_run_resumes_and_stores_nothing_new`, `test_FR_0_7_07_bundle_files_match_bundle_json` (the smoke tests are `slow`+`network`, using the real Vosk model) | AT-0.7-01 |
| FR-0.7-08 | `parity <A> <B>` (each a bundle folder or `.tar`) checks both bundles against their `BUNDLE.json` hashes. Then it compares, for every transcript task present in both (always `vosk-batch`): <br>- per clip: `text_sha256`; <br>- per clip and variant: `wer`; <br>- per score table: corpus WER, errors and reference words; <br>- the clip sets themselves. <br>It prints every difference, one line each (task, clip, field, A value, B value), then a summary and the two bundles' machine, lock and commit facts. Exit 0 identical, 1 differences (all listed), 2 input error | `aqis_lab/parity.py`, `aqis_lab/commands/parity.py` | `aqis_lab/__main__.py`: `COMMANDS` (`parity`) | `test_FR_0_7_08_identical_bundles_report_no_difference`, `test_FR_0_7_08_reports_every_per_clip_difference` (must-catch 6; bundles with several changed hashes and WERs, one missing clip and one extra clip; every one listed), `test_FR_0_7_08_total_wer_difference_reported`, `test_FR_0_7_08_damaged_bundle_is_input_error`, `test_FR_0_7_08_reads_folder_and_tar_alike`, `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` (added for OC-0.7-03 once the bundles are committed) | OC-0.7-03 |
| NFR-0.7-01 | The cloud smoke run takes about 3 to 4 minutes (finding 7). The test runs the real command and asserts under 900 s. `BUNDLE.json` records the run's elapsed time | — | — | `test_NFR_0_7_01_cloud_smoke_within_15_minutes` (`slow`, `network`) | `time .venv/bin/python -m aqis_lab phase0 smoke --target cloud` |
| AT-0.7-01 | Run as written on this VM. Then `contracts validate` on each run card and `events.jsonl`, and `trace` on rows picked from each kind | — | — | the FR-0.7-07 tests | `.venv/bin/python -m aqis_lab phase0 smoke --target cloud` (exit 0), then `.venv/bin/python -m aqis_lab trace <row id>` for a Vosk row, a VAD row, a real-speed row and a score row |
| AT-0.7-02 | Run as written | — | — | — | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"`, `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow and not gpu and not colab and not oracle"`, `git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.7` |
| OC-0.7-01 | Owner, Colab T4: see "Owner-run checks planned" | `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` (question 13) | `docs/colab/COLAB_RUNBOOK.md` (new OC-0.7-01 section; existing sections unchanged) | `colab`/`gpu` tests; `test_FR_0_7_07_smoke_launcher_cells_contain_no_logic`, `test_FR_0_7_07_smoke_launcher_commands_exist_and_parse`, `test_FR_0_7_07_token_only_reaches_the_clone_command` (the WP-0.5 launcher rules applied to the new notebook) | see below |
| OC-0.7-02 | Owner, Oracle: see below | — | `docs/oracle/ORACLE_RUNBOOK.md` (new OC-0.7-02 section; `libatomic1` check) | `oracle` tests | see below |
| OC-0.7-03 | Me, after both bundles are committed: `parity` cloud↔colab, cloud↔oracle and colab↔oracle. Any difference goes to you as a blocker, never hidden | — | `docs/runs/PHASE0_SMOKE.md` (parity section) | `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` | `.venv/bin/python -m aqis_lab parity data/runs/phase0-smoke/<cloud>.tar data/runs/phase0-smoke/<colab>.tar` (and the other two pairs) |
| DEBT-013 | NFR-0.5-01 on a real workload: `vosk-batch` over the smoke pack through the runner, against a direct loop over the same adapter, same clips and same output bytes | — | — | `test_NFR_0_5_01_runner_overhead_under_5_percent_on_vosk_batch` (`slow`, `network`) | `.venv/bin/python -m pytest tests/aqis_lab -q -k NFR_0_5_01 -m slow` |
| DEBT-014 | Each of the four writers calls `aqis_lab.drive.check_write_path` before it writes. A path on a Drive mount outside `MyDrive/AQIS_LAB` gives `ERROR:` and exit 2 | — | `aqis_lab/commands/score.py`: `write_outputs`; `aqis_lab/packs/build.py`: `build_pack`; `aqis_lab/commands/registry.py`: `main` (build branch); `aqis_lab/registry/fetch.py`: `fetch_dataset` | `test_NFR_0_5_02_score_refuses_drive_path_outside_aqis_lab`, `test_NFR_0_5_02_pack_build_refuses_drive_path_outside_aqis_lab`, `test_NFR_0_5_02_registry_build_refuses_drive_path_outside_aqis_lab`, `test_NFR_0_5_02_registry_fetch_refuses_drive_cache_outside_aqis_lab` (Drive test double as in WP-0.5) | `.venv/bin/python -m pytest tests/aqis_lab -q -k NFR_0_5_02` |
| DEBT-015 | (2) when `rclone lsf` fails, `sync` prints rclone's own message; (3) an rclone timeout is `ERROR:` and exit 1; (4) `STORE.json` is created only while the store lock is held | — | `aqis_lab/sync.py`: `_check_destination`, `run_sync`; `aqis_lab/results/store.py`: `_ensure_store`, `add_batch` | `test_FR_0_6_05_failed_remote_listing_shows_rclone_message`, `test_FR_0_6_05_rclone_timeout_is_an_error`, `test_FR_0_6_02_simultaneous_first_adds_are_safe` | `.venv/bin/python -m pytest tests/aqis_lab -q -k "FR_0_6_05 or FR_0_6_02"` |
| DEBT-017 | Covered by FR-0.7-05: the feeder pins itself, and the test reads every thread's affinity | — | — | `test_FR_0_7_05_feeder_pins_every_thread_to_timing_cores` | as FR-0.7-05 |

**Change budget for existing files.** Nothing else that already exists is touched.
- **`aqis_lab/__main__.py`:** two new `COMMANDS` entries (`phase0`, `parity`) and a CHANGE LOG line each.
- **`aqis_lab/runner/tasks.py`:**
  - new task classes for the adapters, and `TASKS` entries `vosk-batch`, `vosk-realspeed`, `harness-vad`, `parakeet-offline`, `parakeet-compute-delay`;
  - `ClipStats` gains the new task attributes with today's values (mode `batch`, normaliser none, deterministic, no events), so its behaviour and its rows are unchanged;
  - header: CAP-RUN-003 text, the invariant "output depends only on the clip bytes" restated for deterministic tasks (timing tasks record measured times), CHANGE LOG.
- **`aqis_lab/runner/card.py`:** `build_run_card` takes the mode, the normaliser and the lock from the task and from `aqis_lab.locks`. For `clip-stats` in a CPU environment the card is identical to today's.
- **`aqis_lab/runner/plan.py`:** `build_plan` gains an optional clip subset. The plan gets a `clip_selection` field only when a subset is given, so every existing plan and `plan_id` is unchanged.
- **`aqis_lab/runner/run.py`:**
  - `RunOptions` gains `clips` and `model_cache`;
  - `run` pins by the task's mode (it used the constant `batch`), opens and closes the task, keeps the run ID and joins `events.jsonl` for event-writing tasks;
  - `_compute_shard` passes an event sink and writes the shard's events;
  - `_open_run_folder` writes `run_id.txt` once for event-writing tasks;
  - header texts of CAP-RUN-007 and CAP-RUN-008, and CHANGE LOG.
- **`aqis_lab/runner/store.py`:**
  - `write_shard` takes optional event bytes. Only then does the marker gain `events_file`, `events_sha256`, `events_bytes`, `events` and `seq_first`;
  - `shard_finished` also checks the events file when the marker names one;
  - new `events_path`.
- **`aqis_lab/platform.py`:** new `host_name()`, a CAP-PLAT-002 header line and a CHANGE LOG line. Every existing function stays byte-identical.
- **`aqis_lab/doctor.py`:** `_check_lock` accepts exactly the CPU lock, or exactly the CPU lock plus the GPU lock, and names which (from `aqis_lab.locks`). CAP-DOCTOR-001 text and CHANGE LOG.
- **DEBT-014:** `aqis_lab/commands/score.py` (`write_outputs`), `aqis_lab/packs/build.py` (`build_pack`), `aqis_lab/commands/registry.py` (`main`), `aqis_lab/registry/fetch.py` (`fetch_dataset`), each with its CHANGE LOG.
- **DEBT-015:** `aqis_lab/sync.py` (`_check_destination`, `run_sync`) and `aqis_lab/results/store.py` (`_ensure_store`, `add_batch`), each with its CHANGE LOG.
- **`aqis_lab/deploy/dev_bootstrap.sh`:**
  - `--build-constraints "$LOCK"` on the sync (question 2);
  - a `--gpu` option that syncs `phase0.txt` and `phase0-gpu.txt` together, with the GPU lock as build constraints too;
  - header CAP-ENV-001 and CHANGE LOG.

  Without `--gpu`, the steps, messages and files are as today.
- **`aqis_lab/deploy/oracle_setup.sh`:** step 4 passes `--no-binary <name>` only for the approved source-only packages (a constant `SOURCE_BUILDS=(srt)`), and says so in its PASS line (question 2). Header and CHANGE LOG.
- **Locks:**
  - `requirements/aqis_lab/phase0.in` gains `vosk==0.3.45`, `webrtcvad-wheels` (question 1), `setuptools` (the source build's hash-pinned build tool, question 2) and `packaging<25` (question 3), each with a comment;
  - `phase0.txt` is regenerated with its recorded command. Every existing pin stays except `packaging` 26.3→24.2 (a test proves it).
- **Existing test, only with your `ALLOW-EDIT`:** `tests/aqis_lab/test_aqis_oracle_setup.py`, function `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds`. It changes to allow exactly the packages in `oracle_setup.sh`'s `SOURCE_BUILDS`, and it checks that each of those truly has no wheel and is pure Python (question 2). Nothing else in the file changes.
- **Documents:**
  - `docs/runner/RUNNER.md` (new tasks, event files, modes);
  - `docs/doctor/DOCTOR.md` (lock row);
  - `docs/colab/COLAB_RUNBOOK.md` and `docs/oracle/ORACLE_RUNBOOK.md` (new OC-0.7 sections only; existing text unchanged, because tests read it);
  - `docs/capabilities/REGISTRY.md` (new rows; updated text of CAP-ENV-001, CAP-ENV-002, CAP-ENV-007, CAP-RUN-003, CAP-RUN-004, CAP-RUN-005, CAP-RUN-006, CAP-RUN-007, CAP-RUN-008, CAP-DOCTOR-001, CAP-PLAT-002 and the four DEBT-014 writers; no row removed);
  - `docs/progress/STATUS.md`, `DEBT.md` (Status column of DEBT-013, 014, 015 and 017), `BLOCKERS.md` (append only).
- **Not touched:**
  - the existing launcher `notebooks/aqis_lab/phase0_launcher.ipynb`;
  - `aqis_lab/drive.py`, `aqis_lab/trace.py`, `aqis_lab/results/ingest.py`, `aqis_lab/timing/cores.py`, `config/aqis_lab/oracle.yaml`;
  - `.github/workflows/aqis-lab-ci.yml`: CI's fast suite needs no model download, because tests that need the real Vosk model are marked `network`;
  - every harness file under `vad_adapters/` and every other GUARDED or NEVER path.

**New test files.** The `test_aqis_` prefix keeps basenames unique.
- `tests/aqis_lab/test_aqis_adapters_base.py`, `test_aqis_model_cache.py`, `test_aqis_vosk.py`, `test_aqis_parakeet.py`, `test_aqis_harness_vad.py`, `test_aqis_realspeed.py`, `test_aqis_runner_events.py`, `test_aqis_locks_gpu.py`, `test_aqis_smoke.py`, `test_aqis_smoke_launcher.py`, `test_aqis_parity.py`, `test_aqis_debt_wp07.py`.
- `test_aqis_smoke_live.py`: markers `colab`, `gpu`, `oracle` only, never in the fast suite.
- The helper `tests/aqis_lab/aqis_adapters_testutil.py`. It holds:
  - a session-wide cache for the real Vosk model (downloaded once per test run, checked against the pin);
  - generated WAV clips;
  - the Oracle cores test double from WP-0.6;
  - the GPU test double (used only for FR-0.7-06's timing logic);
  - bundle builders for the parity tests.

## Design details

### Adapter contract (`aqis_lab/adapters/base.py`)
- `Adapter` is an abstract base class:
  - `component`: one of the event-log components. Vosk is `live_stt` (a streaming recogniser), Parakeet offline is `heavy_stt` and the harness VAD is `vad`;
  - `model_block()`: the run-card `model` object;
  - `open()`, `process_clip(clip, samples, sink)` and `close()`;
  - streaming adapters also offer `start_clip`, `feed(frame, sink)` and `finish_clip(sink)` for the real-speed feeder.

  Abstract methods have docstring-only bodies (no `pass`, no `NotImplementedError`).
- **Event sink.** `EventSink(run_id, run_card_id, seq_start, host_id, write)` stamps every envelope field. It calls `validate_event` on each record and raises before anything is written if a record is invalid (must-catch 1). Records are canonical JSON lines.
- **Audio time on each event.**
  - `partial` and `final`: the audio fed so far, in seconds.
  - `speech_start` and `speech_end`: the boundary.
  - `clip_started`: `0.0`. `clip_finished`: the clip length.
  - Run-level events: null, with reason `run-level event`.
- **Failures.** `guarded()` turns any exception from `open`, `process_clip`, `feed` or `finish_clip` into:
  - one `error` event, with clip ID when known, code `<adapter>-<kind>` (for example `vosk-model-checksum`, `vosk-clip-failed`) and `run_continues: false`;
  - then an `AdapterError` raised from the original exception.

  The runner turns that into its usual `ERROR` log line and exit 1. The failed shard's events file holds the error event until the shard is computed again.

### Runner with event logs
- Only tasks with `emits_events = True` get event files. `clip-stats` run folders stay exactly as today (finding 12).
- **Run ID.** `run_id` = `run-<UTC of the first session>-<first 12 hex of run_card_id>`, written once to `run_id.txt`. A resumed run keeps it.
- **Event order.** `run_started` has `seq` 0 (component `runner`), written to `events.head.jsonl` when the run folder is created. The shard with index *k* numbers its events from `1 + (events of shards 0 to k−1)`. Those counts are known because shards are computed in order and every earlier shard is finished and marked. Each clip is framed by `clip_started` and `clip_finished` (component `runner`).
- **Joining.** When every shard is finished, the runner joins `events.head.jsonl`, every shard's events and a closing `run_finished` (`completed`) into `events.jsonl`. It checks the result with `validate_event_lines` before writing it. `results.jsonl` is joined as today.
- **Markers.** A shard counts as finished only when its marker also matches the events file's SHA-256 and size.
- **Modes.** Each task declares its run-card mode: `vosk-batch`, `harness-vad` and `parakeet-offline` are `batch`; `vosk-realspeed` is `realspeed_cpu`; `parakeet-compute-delay` is `gpu_compute_delay`. The runner pins itself for that mode, so on Oracle timing runs go to cores 2-3 and batch runs to 0-1.
- **Normaliser.** Tasks that produce text record `normaliser_identity()` (`aqis-whisper-english`, `1+whisper-normalizer-0.1.1`); the VAD records null.
- **Lock.** A CPU environment records `requirements/aqis_lab/phase0.txt`. An environment with the GPU extras records `requirements/aqis_lab/phase0-gpu.txt`, whose header names the SHA-256 of the `phase0.txt` it was built on.
- **Clip subset.** A clip subset (`--clips`, used by the smoke for the 5-clip runs) goes into the shard plan's `clip_selection` (rule, seed, clip IDs), not the run card. The run card decides each clip's result; the plan decides which clips are computed. Resuming with another subset is refused, as today for another plan.
- **Result rows** (fields after `clip_id`, `run_card_id`, `task`, `task_version`):

  | Task | Fields | Same bytes on a rerun? |
  | --- | --- | --- |
  | `vosk-batch` | `text`, `text_sha256`, `finals`, `partials`, `words`, `events`, `audio_s` | yes, on the same machine and kernel |
  | `harness-vad` | `segments` (`[start_s, end_s]` pairs), `speech_s`, `frames`, `speech_frames`, `dropped_tail_samples` | yes |
  | `vosk-realspeed` | `text`, `text_sha256`, `first_partial_latency_ms`, `finalisation_latency_ms`, `max_frame_lag_ms`, `audio_s`, `wall_s` | no (measured times) |
  | `parakeet-offline` | `text`, `text_sha256`, `audio_s` | not promised (GPU arithmetic) |
  | `parakeet-compute-delay` | `processing_ms`, `rtf`, `gpu`, `text_sha256`, `audio_s` | no (measured times) |

  `text` is the clip transcript: the texts of the clip's `final` events joined by single spaces, empty ones skipped. `text_sha256` is the SHA-256 of its UTF-8 bytes, which is what parity compares. For timing tasks a resumed run keeps the times measured first, because finished shards are never computed again.

### Vosk (`aqis_lab/adapters/vosk_stt.py`)
- **Model pin** (`config/aqis_lab/models.yaml`):
  - URL `https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip`, 41,205,931 bytes, SHA-256 `30f26242…2498`;
  - the SHA-256 of each of the 14 extracted files;
  - licence Apache-2.0.
- **Run-card model block.** Family `vosk`, name `vosk-model-small-en-us-0.15`, version `0.15`, checksum = the zip's SHA-256. Settings:
  - `sample_rate_hz` 16000;
  - `feed_samples` 320;
  - `words` true;
  - `library` `vosk 0.3.45`;
  - `openblas_coretype` (question 6);
  - `openblas_num_threads` 1;
  - `log_level` −1.
- **Kernel pin.** The adapter sets the two OpenBLAS variables before `import vosk` and then reads the library's active kernel table (`gotoblas` against `gotoblas_<KERNEL>`) to confirm the pin took. If the kernel differs, or `vosk` was already imported in this process with other settings, it raises. The aarch64 library has no dispatch (finding 6); the adapter records `fixed build (no kernel dispatch)`.
- **Model cache.**
  - The default cache is `data/raw/aqis_lab/models/` (git-ignored); `--model-cache` changes it.
  - The zip is downloaded to `<name>.zip.partial` and checked for size and SHA-256 before it is renamed, then extracted into `.staging-<sha>` and checked file by file. Only then is the folder renamed and a `.verified` marker written.
  - A mismatch deletes only the lab's own `.partial` or staging files and raises `ModelChecksumError`. It names the expected and actual values.

### Parakeet Unified (`aqis_lab/adapters/parakeet_unified.py`)
- **Model pin.** Revision `fe53cd88…`, file `parakeet-unified-en-0.6b.nemo`, 2,474,055,680 bytes, SHA-256 `ec23ed91…a35b`, licence NVIDIA Open Model License (recorded in `PARAKEET_UNIFIED.md`). It is downloaded from `https://huggingface.co/nvidia/parakeet-unified-en-0.6b/resolve/<revision>/parakeet-unified-en-0.6b.nemo` to local disk (question 12).
- **Run-card model block.** Family `nemo`, name `nvidia/parakeet-unified-en-0.6b`, version = the revision, checksum = the file's SHA-256. Settings:
  - `mode` offline;
  - `decoding` the model's default greedy RNN-T decoding;
  - `batch_size` 1;
  - `dtype` float32;
  - `device` cuda;
  - `nemo` and `torch` versions;
  - `input` in-memory float32 samples (finding 10).
- **Isolation.** torch and NeMo are imported only inside `open()`. A test scans the package so that nothing else imports them (rule 40).

### Harness VAD (`aqis_lab/adapters/harness_vad.py`)
- It takes `get_adapter("<name>", frame_size_samples=320)` from `vad_adapters.adapter_registry`. The repository root is added to the import path explicitly, so it works from any folder.
- It frames each clip with the harness's `chunk_audio_stream` and turns the frame decisions into segments with no smoothing (finding 8). A speech run that reaches the last full frame ends at that frame's end.
- **Run-card model block.** Family `harness-vad`, name the adapter's ID (for example `webrtc_vad_mode2`), version `webrtcvad-wheels 2.0.14`, checksum null. Settings: mode, `frame_size_samples` 320, `harness_module` `vad_adapters.webrtc_vad_adapter`, `segmentation` `raw frame transitions`, `tail` `dropped (harness chunk_audio_stream)`. The harness code itself is identified by the run card's git commit.

### Smoke run (`aqis_lab/smoke.py`, `config/aqis_lab/phase0_smoke.yaml`)
- **Config.**
  - pack `data/packs/smoke/v1`;
  - seed 0;
  - the harness VAD name (question 1);
  - the OpenBLAS kernel (question 6);
  - the 5-clip subset rule and its resulting clip IDs (question 8);
  - which tasks run on which target;
  - score subsets: `natural` = test-clean, test-other and noisy (40 clips); `synthetic-tts` = tts (10 clips, labelled "plumbing only, never a model judgement"; question 10).

  A test keeps the committed clip IDs equal to what the rule computes.
- **Where things go.**
  - `--out` holds the run folders. On Colab this is Drive (`AQIS_LAB/results/phase0-smoke-colab`), so a runtime that dies can resume.
  - The results store (`--store`, local disk only; default `data/raw/aqis_lab/results`) and the score folders are written locally.
  - The bundle is written to `--out`.
- **The bundle** `phase0-smoke-<target>-<YYYYMMDDTHHMMSSZ>`:
  ```text
  BUNDLE.json        bundle_version, target, platform, machine, git, locks (file, sha256), elapsed_s, runs (task -> run_card_id),
                     scores (table -> summary sha256), files (path -> sha256, bytes)
  PHASE0_SMOKE.md    the report for this target
  runs/<task>/       run_card.json, shard_plan.json, results.jsonl, events.jsonl, runner.log
  scores/<task>-<subset>/   scores.parquet, scores.csv, summary.json
  ```
  It is also written as one deterministic `.tar` (sorted members, fixed mtime), which is what you upload.
- **The report.**
  - It covers: Vosk corpus WER and CER per subset (both normaliser variants, labelled as in WP-0.3), per-clip transcripts, VAD speech seconds per category, real-speed latencies (median and maximum over the 5 clips), and on Colab Parakeet WER and per-clip GPU times with the GPU type.
  - Every number cites the `run_card_id` and the `result_row_id` or score summary it comes from.
  - On `cloud` and `oracle` it states "Parakeet: not run — CPU target (FR-0.7-07: GPU target only)".
- **`docs/runs/PHASE0_SMOKE.md`** holds:
  - the cloud report, byte-copied from the committed cloud bundle;
  - after OC-0.7-01 and OC-0.7-02, the Colab and Oracle reports;
  - after OC-0.7-03, the three parity outputs.

  A test checks each report section against its committed bundle.

### Locks and installs
- **`phase0.txt`** changes: see the change budget.
- **`phase0-gpu.in`**: `nemo_toolkit[asr]==<question 4>`, torch (question 5) and a header naming the `phase0.txt` SHA-256 it was compiled against. It is compiled with `uv pip compile requirements/aqis_lab/phase0-gpu.in -c requirements/aqis_lab/phase0.txt --python-version 3.13 --python-platform x86_64-manylinux_2_28 --generate-hashes`, because the GPU extras are needed only on Colab, which is x86_64.
- **Tests.** One test proves that no GPU pin contradicts a CPU pin and that the header's SHA-256 equals today's `phase0.txt`. Another proves that `antlr4-python3-runtime` is the only source-only GPU package.
- **`dev_bootstrap.sh --gpu`** (Colab only) runs `uv pip sync --require-hashes --strict --build-constraints phase0-gpu.txt phase0.txt phase0-gpu.txt`.
- **`aqis_lab/locks.py`** (new) finds which lock set is installed. It compares installed distributions with the CPU lock alone and with the CPU lock plus the GPU lock. Exactly one must match, otherwise it is an error naming the differences. The doctor and the run card both use it.

### Must-catch proof (planned)
| # | Behaviour | Tests that must fail when it is broken |
| --- | --- | --- |
| 1 | Every adapter event validates against event log v1 | `test_FR_0_7_01_events_validate_against_event_log_v1`, `test_FR_0_7_01_sink_refuses_invalid_event` |
| 2 | An adapter failure emits an `error` event and raises | `test_FR_0_7_01_adapter_failure_emits_error_event_and_raises`, `test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event` |
| 3 | The Parakeet adapter refuses to run without a GPU and is never silently skipped | `test_FR_0_7_03_refuses_without_gpu`, `test_FR_0_7_03_colab_smoke_without_gpu_fails_never_skips` |
| 4 | The Vosk model is rejected when its checksum differs | `test_FR_0_7_02_model_rejected_when_checksum_differs`, `test_FR_0_7_02_changed_model_file_rejected_at_load` |
| 5 | The real-speed feeder cannot run faster than real time | `test_FR_0_7_05_feeder_never_faster_than_real_time` |
| 6 | `parity` reports every per-clip difference | `test_FR_0_7_08_reports_every_per_clip_difference` |

### Parts that do not depend on owner inputs
- **Build first:**
  - the adapter contract and event sink;
  - the runner's event log;
  - the model cache;
  - the real-speed feeder;
  - `parity`;
  - the smoke orchestration;
  - DEBT-014, DEBT-015 and DEBT-017.
- **Wait for your answers:**
  - Vosk's install and every Vosk test: questions 2, 3 and 6;
  - the harness VAD adapter: question 1;
  - the GPU lock: questions 4 and 5, and the T4 probe;
  - the smoke's subset, scoring split and bundle place: questions 8 to 11.

If an answer is still missing when I reach a part that needs it, I stop only that part.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to questions 1 to 16 as CONDITIONS in `docs/approvals/WP-0.7.md` (or "as recommended"), **including the harness VAD's name** (question 1) | The spec leaves the VAD to you; the other questions settle packages, definitions and procedures | Before `/wp-build WP-0.7` |
| 2 | If you accept question 2 (a): the line `ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py` in the approval | One existing test must allow the approved source-only packages | Before `/wp-build WP-0.7` |
| 3 | **Colab T4 probe**: run the cell below on a T4 runtime and commit its output as `docs/environment/colab_gpu_probe.txt` on `main` | The NVIDIA driver version decides which torch build the GPU lock can use (question 5) | Before I build the GPU lock; everything else can start without it |
| 4 | Only if the probe shows a driver older than 580: add `download.pytorch.org` to this cloud environment's allowlist | The CUDA 12.8 torch wheels and their hashes come from there (HTTP 403 today) | Before I build the GPU lock |
| 5 | Colab (T4) and Oracle owner-run checks after the audit passes | OC-0.7-01, OC-0.7-02 | Before merging |

No allowlist change is needed for Vosk: `alphacephei.com` already works from this VM (finding 3).

### Colab T4 probe (owner need 3)
**Runtime → Change runtime type → T4 GPU**, then one cell:
```text
!nvidia-smi
!nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
!python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
!python --version; nproc; free -g | head -2; df -h /content | tail -1
```
It prints no secrets.

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| OC-0.7-01 | Colab, **T4 GPU** runtime, launcher `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` at tag `aqis-lab-wp-0.7-colab-1` (question 14) | Cells 1 to 5 as in the new COLAB_RUNBOOK section. Cell 3 runs `dev_bootstrap.sh --gpu`. Cell 4 runs `doctor --target colab --expect-gpu`, then `phase0 smoke --target colab --out /content/drive/MyDrive/AQIS_LAB/results/phase0-smoke-colab --drive-mount /content/drive`. Then one extra cell: `!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m "colab or gpu"` | Doctor `result: PASS` with `gpu` PASS (`Tesla T4`) and `lock` PASS (CPU + GPU locks). The smoke ends with `smoke complete` and the bundle path; the pytest line ends in `passed`. Commit `…/phase0-smoke-colab-<stamp>.tar` to `data/runs/phase0-smoke/` on the pull request's branch, and the notebook output as `docs/progress/WP-0.7/OC-0.7-01_colab.txt` |
| OC-0.7-02 | Oracle VM, clone at tag `aqis-lab-wp-0.7-oracle-1` | 1. `dpkg -s libatomic1 \| grep Status` (if missing: `sudo apt-get install -y libatomic1`). <br>2. `bash aqis_lab/deploy/oracle_setup.sh`. <br>3. `.venv/bin/python -m aqis_lab phase0 smoke --target oracle`. <br>4. `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle` | 1: `install ok installed`. 2: six steps PASS; step 4 names `srt` as the one approved source build. 3: `smoke complete`, bundle path; `runner.log` of the real-speed run shows `cores: timing on 2-3`, the batch runs `cores: batch on 0-1`. 4: ends with `passed`. Commit the bundle `.tar` to `data/runs/phase0-smoke/` and the output of all four as `docs/progress/WP-0.7/OC-0.7-02_oracle.txt` |
| OC-0.7-03 | This cloud VM, by me | `parity` for the three pairs | Exit 0 and `0 differences` for each pair. Any difference: I record every line in a blocker and stop (spec: stop and ask) |

## Risks and questions
### Questions for you
1. **(FR-0.7-04) Which harness VAD to wrap.** The spec says you name it.
   - **(a) Recommended: WebRTC VAD, mode 2, 20 ms frames** (`webrtc_vad_mode2` through the harness registry).
     - It runs on x86_64 and on the Arm Oracle VM.
     - It is fixed-point C, so the same audio gives the same decisions everywhere.
     - It is MIT-licensed, and it adds one small package to the CPU lock.
     - Mode 2 is the harness adapter's own default. Name another mode if you prefer.
   - **(b) TEN VAD.** It has no Arm library, so the Oracle smoke could not run it and FR-0.7-07 would fail there. It also carries Agora's extra licence conditions.
   - **(c) FireRedVAD.** It needs torch and downloaded weights in the CPU lock on all three machines.
2. **(FR-0.7-02) Vosk's `srt` dependency exists only as source.** The same holds for `antlr4-python3-runtime` in the GPU lock. WP-0.6's rule is "no source builds on Oracle".
   - **(a) Recommended:** allow exactly these two pure-Python packages as source builds.
     - Their source archives are hash-pinned in the locks.
     - They are built only with the hash-pinned setuptools from the same lock (`--build-constraints`; measured in finding 4).
     - `oracle_setup.sh` lists `srt` as its only exception and still requires wheels for everything else.
     - Needs `ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py` for one test (see the change budget).
     - Limit: the plain `pip install --require-hashes` route builds `srt` with pip's own unpinned setuptools. The lab's supported installs (the bootstrap on all three machines and CI) use uv and the pin.
   - **(b)** I build an `srt` wheel once from the pinned source archive, commit it under `requirements/aqis_lab/wheels/`, and install with `--find-links`. The rule "every pin has a wheel" stays literally true, but the repository holds a binary we built ourselves. The same test and more scripts change.
   - **(c)** Use piwheels.org as an extra package index. It has wheels for pure-Python packages, but it is a third-party index, and it needs an allowlist entry.
3. **(FR-0.7-03) Lower `packaging` in the CPU lock from 26.3 to 24.2.**
   - **(a) Recommended.** NeMo's `lightning` needs `packaging<25`. With this one change, the GPU lock is truly "GPU extras" on top of the unchanged CPU pins. The Colab environment then has exactly the same CPU packages as the cloud VM and Oracle, which is what parity needs. `packaging` does not affect any result.
   - **(b)** Keep 26.3, and make `phase0-gpu.txt` a complete second lock that differs in `packaging`. The spec's "GPU extras" wording would then not hold, and Colab's CPU packages would differ from the other machines' in one package.
4. **(FR-0.7-03) NeMo version.**
   - **(a) Recommended: NeMo 3.0.0**, transcribing in-memory audio. It resolves on Python 3.13, and it loaded and transcribed correctly on CPU here (finding 10). Its file-path call fails for this model, and the adapter never uses it.
   - **(b) NeMo 2.7.3**, the model card's runtime. It needs `jiwer<4`, which conflicts with WP-0.3's exact pin `jiwer==4.0.0`. The GPU lock would then have to be a separate complete lock with jiwer 3.1.0, and the scorer cross-check tests could not run in the GPU environment.

   Either way, the T4 (Turing) is not in the model card's list of tested GPUs. OC-0.7-01 is the first run on a T4.
5. **(FR-0.7-03) torch for the T4.** Please run the T4 probe (owner need 3). Then:
   - **driver 580 or newer:** the GPU lock takes torch from PyPI (CUDA 13), as NeMo resolves it. No allowlist change.
   - **driver older than 580:** the GPU lock pins `torch==2.11.0+cu128`, the build Colab ships, from `https://download.pytorch.org/whl/cu128`. That needs `download.pytorch.org` on this environment's allowlist (owner need 4).
6. **(FR-0.7-02, FR-0.7-08) Fix Vosk's OpenBLAS kernel.**
   - **(a) Recommended: `OPENBLAS_CORETYPE=Prescott` and 1 thread on x86_64.**
     - It is the kernel this VM already falls back to.
     - It runs on every x86_64 CPU, and it is as fast here as Haswell (both 70 to 75 s for the pack).
     - In the Arm emulation it gave the same 60 transcripts as Oracle's library (findings 5 and 6).
     - The setting is recorded in every Vosk run card.
   - **(b) `Haswell`.** Also fixed and recorded, but it differed from the Arm result on 1 clip.
   - **(c) No setting.** Each x86 machine picks its own kernel, and E1 parity between the cloud VM and Colab becomes a matter of luck.
7. **(FR-0.7-05, FR-0.7-06) Definitions.** Recommended, all computed from the event log:
   - **First-partial latency** = wall time of the clip's first non-empty `partial` event − wall time at which the audio of the first recognised word's start was delivered. The word start comes from the `final` events' word times. An alternative is to measure from the start of the stream; say if you prefer it.
   - **Finalisation latency** = wall time of the clip's last `final` event − wall time of the `audio-end` mark (last frame delivered).
   - A clip with no recognised word has both values null, and the report says so.
   - **GPU per-clip time** = monotonic time around one `transcribe` call on in-memory audio, with CUDA synchronised before the stop. One untimed warm-up transcription (the first subset clip) runs before timing; model loading is reported separately.
8. **(FR-0.7-05, FR-0.7-06) Which 5 clips.**
   - Recommended: the same 5 clips for real-speed Vosk and for the GPU timing. That is two test-clean, one test-other, one noisy and one tts clip, each the lowest `sha256("aqis-phase0-subset-v1|<clip_id>")` in its category.
   - Today that gives: `ls-test-clean-3570-5695-0009`, `ls-test-clean-6829-68771-0030`, `ls-test-other-6128-63244-0013`, `smoke-mix-01` and `tts-smoke-04`, 25.6 s of audio.
   - Or name your own 5.
9. **(FR-0.7-07) How much Parakeet runs on Colab.**
   - **(a) Recommended:** Parakeet offline on all 60 clips, scored like Vosk, plus the 5-clip GPU timing run. It costs about 2 minutes of T4 time after the model is loaded.
   - **(b)** Only the 5-clip timing run.
10. **(FR-0.7-07) The 10 synthetic TTS clips.** `SMOKE_PACK.md` says they must never be used to judge models.
    - **(a) Recommended:** score them in their own table, `synthetic-tts`, labelled "plumbing only". The headline WER covers the 40 natural-speech clips.
    - **(b)** Score all 50 together.
    - **(c)** Do not score them at all.
11. **(FR-0.7-07, OC-0.7-01/02) Where bundles are committed.**
    - Recommended: `data/runs/phase0-smoke/<bundle name>.tar`, one file of a few MB per target, uploaded through GitHub's web page.
    - It is a `.tar` because `.gitignore` ignores `*.jsonl`, and because one file is easier to upload.
    - I commit the cloud bundle myself.
12. **(FR-0.7-03) Parakeet model on Colab.**
    - **(a) Recommended:** download it from Hugging Face to local disk at each session (about 2.5 GB, roughly a minute), then verify it.
    - **(b)** Keep a copy in `AQIS_LAB/models/` on Drive and copy it to local disk each session. This saves the download but uses 2.5 GB of your Drive.
13. **(OC-0.7-01) Launcher.**
    - **(a) Recommended:** a new notebook, `notebooks/aqis_lab/phase0_smoke_launcher.ipynb`. It has the same five cells and the same rules as the WP-0.5 launcher, and new tests apply those rules to it. The WP-0.5 launcher and its tests stay unchanged.
    - **(b)** Edit the existing launcher. That needs `ALLOW-EDIT: tests/aqis_lab/test_aqis_launcher.py`, because its tests fix the command list.
14. **(OC-0.7-01/02) Tags.** After the audit passes, I push `aqis-lab-wp-0.7-colab-1` and `aqis-lab-wp-0.7-oracle-1` on the audited commit. A later fix gets `-2`, as before.
15. **(DEBT-013, 014, 015, 017) Closing the four debts in this WP.** Your WP-0.5 and WP-0.6 approvals set WP-0.7 as their target, so the plan includes them. Say if you would rather move any of them.
16. **(Additions beyond the spec's deliverables.)** Approving these accepts them:
    - **D1: extra files.**
      - code: `aqis_lab/adapters/__init__.py`, `aqis_lab/adapters/model_cache.py`, `aqis_lab/locks.py`, `aqis_lab/smoke.py`, `aqis_lab/commands/phase0.py`, `aqis_lab/commands/parity.py`;
      - config: `config/aqis_lab/models.yaml`, `config/aqis_lab/phase0_smoke.yaml`;
      - notebook: `notebooks/aqis_lab/phase0_smoke_launcher.ipynb`.
    - **D2:** the options `--out`, `--store`, `--model-cache`, `--work-dir` and `--drive-mount` of `phase0 smoke`.
    - **D3:** the runner's new tasks, its event files, the `clip_selection` plan field and the `run_id.txt` file.
    - **D4:** `dev_bootstrap.sh --gpu`, and the doctor's check of the CPU-plus-GPU lock set.
    - **D5:** the result bundle format and its `.tar`.
    - **D6:** the Arm (qemu) emulation as a documented measurement in `EVIDENCE.md`. It is not a test.
    - **D7:** the `libatomic1` step in the Oracle runbook.

    **Recommended: accept all.**

### Design decisions made in this plan (approving the plan accepts them)
- **Every event is validated before it is written**, and a whole run's `events.jsonl` is validated again before it is published.
- **Nothing is skipped or replaced.**
  - A missing GPU, NeMo, model or harness package is an error that names what is missing.
  - A CPU target does not run Parakeet, because the spec says "on a GPU target", and the report says so.
- **Checksums before use.** Model archives are checked before they are extracted, and model files are checked every time they are loaded.
- **Machine facts stay in `aqis_lab.platform`**: the GPU check and the host name.
- **Vosk frames are 20 ms in both modes**, so a real-speed transcript can be compared with the batch transcript of the same clip. The report shows whether they match.
- **Timestamps** are UTC with `Z`. Durations use the monotonic clock in nanoseconds. Audio time is in seconds.
- **Exit codes** follow the lab's pattern: 0 success, 1 a failed check or differences found, 2 usage or input error.

### Requirements at risk as written
- **FR-0.7-08, "identical across cloud VM, Colab (CPU) and Oracle".**
  - It can hold only with a fixed OpenBLAS kernel on x86 (question 6).
  - The Arm emulation says it then holds for all 60 clips, but real Oracle hardware is proven only by OC-0.7-02.
  - If a difference appears, I stop and report every line (spec: "stop and ask").
- **FR-0.7-03 and FR-0.7-06 on a T4.** The model card does not list Turing GPUs, and the torch build depends on the driver (question 5). Nothing on this VM can prove the GPU path; OC-0.7-01 does.

### Other risks
1. **Colab CPU speed.** Colab's 2 vCPUs are slower than this VM. The Colab smoke (Vosk about 2 minutes, plus the GPU environment install of about 5 GB) is not bound by NFR-0.7-01, which is for the cloud VM.
2. **Drive writes on Colab.** The run folders live on Drive, so each shard write goes through Drive's slow FUSE mount. The smoke has few shards (default 30-minute shards), so this is a handful of writes per run.
3. **The Colab runtime dies mid-run.** Running cell 4 again resumes every runner run from Drive. Scores, the store and the bundle are rebuilt from the run folders, and identical rows are reported as already stored.
4. **`libatomic1` missing on Oracle.** Vosk's Arm library then fails to load, with a clear message. The runbook checks for it first.
5. **Hugging Face or alphacephei change a file.** The pins and checksums stop the run with a clear error. Nothing unverified is ever used.
6. **GPU lock size.** About 5 GB of downloads on Colab for each new runtime (torch and CUDA libraries), so cell 3 takes a few minutes.

## Deviations
None of the spec's requirements is changed. These points need your decision:
- **Question 2:** source builds of `srt` and `antlr4-python3-runtime`, against WP-0.6's "no source builds on Oracle" rule. It needs one `ALLOW-EDIT`.
- **Question 3:** `packaging` 24.2 in the CPU lock, so that the GPU lock can be "GPU extras" as the spec says.
- **Question 4:** NeMo 3.0.0 rather than the model card's 2.7.3.
- **Question 13:** a second launcher notebook for the smoke.
- **Question 16:** additions D1 to D7.

## Measurements
| What | Command | Result |
| --- | --- | --- |
| Hosts | `curl -sS -o /dev/null -I -w "%{http_code}"` | `alphacephei.com/vosk/models` 200; the model zip 200 (41,205,931 bytes); `….zip.sha256` 404; `huggingface.co` 200; `us.aws.cdn.hf.co` (206 on a range request); `download.pytorch.org` and `api.ngc.nvidia.com` 403 from the proxy |
| Vosk model | `sha256sum`, `md5sum`, `python -m zipfile -l` | SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`, MD5 `09ab50ccd62b674cbaa231b825f9c1cb`; 14 files (am, graph, conf, ivector, README) |
| Vosk package wheels | PyPI JSON for vosk 0.3.45 | `py3-none-manylinux_2_12_x86_64` (sha256 `25e02509…619f`) and `py3-none-manylinux2014_aarch64` (sha256 `54efb47d…2704`) |
| New CPU pins | `uv pip compile phase0.in` + `vosk==0.3.45`, `webrtcvad-wheels`, `packaging<25` (`--universal --python-version 3.13 --generate-hashes`, existing lock as preference) | adds certifi, charset-normalizer, idna, requests, srt, tqdm, urllib3, vosk 0.3.45, webrtcvad-wheels 2.0.14, websockets; changes only packaging 26.3→24.2 |
| Wheels per architecture | `uv pip compile <pin> --no-deps --only-binary :all: --python-platform {aarch64,x86_64}-manylinux_2_28 --python-version 3.13`, each pin | only `srt==3.5.3` has no wheel, on both |
| Source build with pinned setuptools | `uv pip sync --require-hashes --strict --build-constraints <lock> <lock>` (lock including `setuptools==84.0.0`, `-v`); the same lock with both setuptools hashes wrong; a separate constraints file with a wrong hash; a constraints file pinning 80.9.0 | install OK, and the build installed `setuptools==84.0.0` ("Registry requirement already cached", the download hash-checked for the main install); wrong hashes in the lock: exit 1 (`Computed: sha256:51a52592…`); wrong hash in a separate file: exit 1; the build used exactly the constrained 80.9.0 |
| Exception flag | `uv pip compile … --only-binary :all: --no-binary srt` for aarch64 manylinux 2.28 and 2.17 | 2.28 resolves; 2.17 still fails on numpy's missing wheel |
| Vosk repeatability and chunk size | scratch venv, 60 clips, 20 ms and 500 ms chunks | 20 ms twice: identical; 20 ms against 500 ms: 6 clips differ |
| Vosk OpenBLAS kernel | `OPENBLAS_CORETYPE=<k>`, 60 clips, text and full-output hashes | this VM's default = `Prescott` (`OPENBLAS_VERBOSE=2`); text hash Prescott = Sandybridge = default `ff6ec22a…`; Haswell = SkylakeX `13adb69e…` (1 clip differs); threads 1 against 4: 60/60 identical |
| Vosk on Arm (emulated) | `qemu-aarch64-static -cpu neoverse-n1`, Ubuntu 24.04 arm64 Python 3.12, aarch64 vosk wheel, same script | text hash `ff6ec22a…` (= Prescott); 0 transcript differences against Prescott and Sandybridge, 1 against Haswell and SkylakeX; confidences differ in the last digit on 34 clips; needs `libatomic.so.1`; 1045.7 s under emulation |
| Vosk speed | same, this VM | 60 clips, 390.9 s of audio: 67.9 to 74.6 s (real-time factor about 0.18) |
| Event counts | Vosk (partial when changed) and WebRTC mode 2 at 20 ms, 60 clips | 695 partial and 79 final events (795 words); 340 VAD boundary events |
| Parakeet file | HF API, `sha256sum` of the download | revision `fe53cd885760c96b6a5f51a0bfd362cb4584a98b`, 2,474,055,680 bytes, SHA-256 `ec23ed9150c8fde49072c3e2d61678ab903dbcef389d658db833420cbc1da35b` (download matched) |
| NeMo resolution | `uv pip compile` for x86_64-manylinux_2_28, Python 3.13, against the CPU lock | 2.7.3: conflicts on jiwer (`<4` against `==4.0.0`); 3.0.0: conflicts on packaging (`lightning<=2.4.0` needs `<25`); with packaging 24.2: 3.0.0 resolves, 136 extra pins, 22 shared pins identical, torch 2.14.0 (`cuda-toolkit 13.0.3`); only `antlr4-python3-runtime 4.9.3` has no wheel |
| NeMo 3.0.0 on CPU | scratch venv from that resolution | `restore_from` OK (29.2 s); `transcribe([path])` → `AttributeError: 'NoneType' object has no attribute 'get'` (`validation_ds`); `transcribe([np.float32 array])` → "Only there are two sorts of cloud and fire" (13.5 s), "Then Moses was afraid and said Surely the thing is known" (14.1 s) |
| torch CUDA builds | PyPI JSON | torch 2.11.0 and 2.14.0 depend on `cuda-toolkit 13.0.x` |
| 5-clip subset | rule of question 8 on the manifest | the 5 IDs listed there, 25.595 s |
| Fast suite at base | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` | `1640 passed, 25 deselected in 215.13s` (at `97de2ed`) |
