# EVIDENCE — WP-0.7 First adapters and the smoke run

Environment: cloud VM (`cloud-vm`), Ubuntu 24.04.4 LTS, x86_64, 4 CPUs, Python 3.13.12 in `.venv`, uv 0.8.17, lock `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef` (after the WP-0.7 lock change). Branch `claude/clever-wright-gmps92`.

Owner inputs used: `docs/approvals/WP-0.7.md` on `main` (`a2d10f5`): questions 1 to 16 as recommended; question 1 WebRTC VAD mode 2, 20 ms frames (`webrtc_vad_mode2` through the harness registry); question 5 driver 580.82.07, so torch comes from PyPI (CUDA 13); `ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py`. T4 probe `docs/environment/colab_gpu_probe.txt` (Tesla T4, driver 580.82.07, compute capability 7.5, Python 3.13.15, 2 vCPUs).

## Requirements

### Locks and installs (FR-0.7-02, FR-0.7-03; owner decisions, questions 2 and 3)
- Code: `requirements/aqis_lab/phase0.in` and `phase0.txt` (CAP-ENV-002), `aqis_lab/deploy/dev_bootstrap.sh` (CAP-ENV-001), `aqis_lab/deploy/oracle_setup.sh` (CAP-ENV-007); the approved test edit `tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` (only that function, plus its helper `script_source_builds`).
- Lock change (regenerated with the recorded command; existing pins kept as preferences):
```text
$ diff <(grep -oE "^[a-z0-9_.-]+==[^ ]+" phase0.before.txt) <(grep -oE "^[a-z0-9_.-]+==[^ ]+" requirements/aqis_lab/phase0.txt)
> certifi==2026.7.22
> charset-normalizer==3.5.2
> idna==3.20
< packaging==26.3
> packaging==24.2
> requests==2.34.2
> setuptools==84.0.0
> srt==3.5.3
> tqdm==4.70.1
> urllib3==2.8.0
> vosk==0.3.45
> webrtcvad-wheels==2.0.14
> websockets==17.1
```
- Tests: `test_FR_0_7_02_lock_pins_vosk_webrtcvad_and_the_srt_build_tool`, `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints`, `test_FR_0_7_02_source_build_uses_only_the_locked_setuptools` (slow, network), `test_FR_0_7_02_bootstrap_rejects_unknown_option`, `test_FR_0_7_03_bootstrap_gpu_needs_the_gpu_lock`, `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` (network, approved edit).
- Tests first, against the previous `dev_bootstrap.sh` (`git show HEAD:aqis_lab/deploy/dev_bootstrap.sh`): 4 failed for the expected reasons (no `--build-constraints`; the source build picked the refusing setuptools: `ImportError: this setuptools is not the pinned one`; `--cpu` and `--gpu` accepted silently). With the new script:
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_locks_gpu.py -q -p no:cacheprovider
5 passed in 2.08s
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_lock.py tests/aqis_lab/test_aqis_bootstrap.py tests/aqis_lab/test_aqis_oracle_setup.py -q -p no:cacheprovider -m "not gpu and not colab and not oracle"
30 passed, 1 deselected in 39.35s
$ bash aqis_lab/deploy/oracle_setup.sh --dry-run | grep "step 4"
step 4/6 wheels: would check that each of the 37 pins in requirements/aqis_lab/phase0.txt has a binary build for x86_64-manylinux_2_39 and Python 3.13 (uv pip compile --only-binary :all:), except the approved source builds (srt); it stops naming every package without one
```
- Fast suite after this step: `1644 passed, 26 deselected in 210.16s`.
- Status: DONE for the CPU lock; the GPU lock is under FR-0.7-03.

### FR-0.7-02 — Vosk adapter and model cache (in progress: runner and smoke parts follow)
- Code: `aqis_lab/adapters/model_cache.py` (CAP-MODEL-001 to -003), `config/aqis_lab/models.yaml` (CAP-MODEL-004), `aqis_lab/adapters/vosk_stt.py` (CAP-VOSK-001 to -003).
- Tests: `tests/aqis_lab/test_aqis_model_cache.py`, `tests/aqis_lab/test_aqis_vosk.py`, `tests/aqis_lab/test_aqis_locks_gpu.py` (all `test_FR_0_7_02_*`); network tests use the real model downloaded from alphacephei.com and checked against the pins.
- Tests first: before `model_cache.py` and `vosk_stt.py` existed, both test files failed at collection (`ModuleNotFoundError: aqis_lab.adapters.model_cache` / `…vosk_stt`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_7_02"`
```text
28 passed, 1695 deselected in 23.19s
```
- OpenBLAS kernel on this session's VM: `OPENBLAS_CORETYPE` unset → `COOPERLAKE`; `Prescott` → `PRESCOTT`; `Haswell` → `HASWELL` (read from libvosk's `gotoblas` table with ctypes). The planning session's VM fell back to Prescott, so the default kernel really does change between machines; the adapter pins Prescott and 1 thread (owner decision, question 6) and `test_FR_0_7_02_openblas_kernel_pinned_and_verified` reads it back as `PRESCOTT`.

### FR-0.7-04 — Harness VAD adapter (WebRTC VAD mode 2, 20 ms; owner decision, question 1)
- Code: `aqis_lab/adapters/harness_vad.py` (CAP-HVAD-001 to -003). No file under `vad_adapters/` changed.
- Tests: `tests/aqis_lab/test_aqis_harness_vad.py` (`test_FR_0_7_04_*`; expected segments computed with `webrtcvad` directly on six real smoke clips: clean speech, noisy mix, noise, music, TTS, digital silence).
- Tests first: the file failed at collection before `harness_vad.py` existed (`ModuleNotFoundError`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_7_04"`
```text
13 passed, 1710 deselected in 0.95s
```
- Fast suite after both adapters: `1691 passed, 32 deselected in 202.21s`.

### FR-0.7-05 — Real-speed feeder (and DEBT-017)
- Code: `aqis_lab/realspeed.py` (CAP-RSPEED-001 to -003).
- Tests: `tests/aqis_lab/test_aqis_realspeed.py` (`test_FR_0_7_05_*`): the harness VAD as a fast real adapter, a 30 ms-per-frame test adapter for lateness, the real Vosk model for latencies (`network`), and the WP-0.6 Oracle cores test double for pinning (the test reads every thread's `Cpus_allowed_list` of the running feeder process; the child runs a second Python thread so more than the main thread is checked).
- Tests first: the file failed at collection before `realspeed.py` existed (`ModuleNotFoundError`). The first run of the pinning test showed one thread only (`{19471: {3}}`); the test now starts a second thread in the child so "every thread" is really exercised.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_7_05`
```text
7 passed, 1723 deselected in 23.51s
```

### FR-0.7-03 and FR-0.7-06 — Parakeet Unified adapter, GPU extras lock, lock sets (GPU path: OC-0.7-01)
- Code: `aqis_lab/adapters/parakeet_unified.py` (CAP-PARA-001 to -003), `aqis_lab/locks.py` (CAP-LOCKS-001, -002), `aqis_lab/doctor.py` (`_check_lock` only, CAP-DOCTOR-001), `requirements/aqis_lab/phase0-gpu.in` and `phase0-gpu.txt` (CAP-ENV-008), `aqis_lab/deploy/dev_bootstrap.sh --gpu` (CAP-ENV-001).
- GPU lock: 158 pins, `nemo-toolkit==3.0.0`, `torch==2.14.0` (CUDA 13, from PyPI; owner decision question 5), every pin shared with `phase0.txt` at the same version; `antlr4-python3-runtime` 4.9.3 is its only source-only package.
- Real install of both locks on this VM, with hash checking and the lock as build constraint (scratch venv; this is the `--gpu` sync command):
```text
$ uv pip sync -q --python <scratch>/bin/python --require-hashes --strict --build-constraints requirements/aqis_lab/phase0.txt requirements/aqis_lab/phase0.txt requirements/aqis_lab/phase0-gpu.txt
real	7m55.405s
exit 0
$ <scratch>/bin/python -c "import torch, nemo, nemo.collections.asr, importlib.metadata as m; print(...)"
torch 2.14.0+cu130 cuda 13.0 nemo 3.0.0 antlr4 4.9.3
```
- Tests: `tests/aqis_lab/test_aqis_parakeet.py` (refusals without GPU and without NeMo on this VM, model block, the GPU test double for the timing code, warm-up), `tests/aqis_lab/test_aqis_locks_gpu.py` (GPU lock, lock sets, doctor row), `tests/aqis_lab/test_aqis_runner_events.py::test_FR_0_7_03_runner_refuses_parakeet_without_gpu_before_writing`; GPU: `test_aqis_smoke_live.py` (`colab`, `gpu`: OC-0.7-01).
- Tests first: both files failed at collection before the modules existed (`ModuleNotFoundError: aqis_lab.locks` / `…parakeet_unified`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_7_03 or FR_0_7_06" -m "not colab and not gpu and not oracle"`
```text
16 passed, 1738 deselected in 9.70s
```
- Status: DONE on this VM; the GPU path (`test_FR_0_7_03_parakeet_transcribes_on_gpu`, `test_FR_0_7_06_gpu_compute_delay_on_colab_t4`) is owner-run (OC-0.7-01).

### Runner with adapter tasks and event logs (FR-0.7-01, FR-0.7-07)
- Code: `aqis_lab/runner/tasks.py` (CAP-RUN-003, new CAP-RUN-010), `card.py` (`build_run_card`), `plan.py` (`build_plan`), `store.py` (`write_shard`, `shard_finished`, `events_path`; CAP-RUN-011), `run.py` (`RunOptions`, `run`, `_open_run_folder`, `_compute_shard`, new helpers; CAP-RUN-012); `docs/runner/RUNNER.md`.
- Tests: `tests/aqis_lab/test_aqis_runner_events.py` (harness VAD task over the real smoke pack; Vosk runs are `network`). Tests first: collection failed before the tasks existed (`KeyError`/import errors); then all passed.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_runner_events.py -q -p no:cacheprovider`
```text
9 passed in 13.63s
```
- Existing runner tests unchanged and passing (`clip-stats` run folders, markers and cards are as before): `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_runner.py tests/aqis_lab/test_aqis_runner_resume.py tests/aqis_lab/test_aqis_runner_nfr.py tests/aqis_lab/test_aqis_stage.py -q -p no:cacheprovider`
```text
39 passed in 12.20s
```
- Defect found and fixed during this step: the Vosk adapter first set `OPENBLAS_*` in the process environment, which leaked into later child processes (numpy then started one thread, and `test_FR_0_6_04_timing_process_pinned_to_reserved_cores` saw 2 threads instead of 3 when run after the Vosk tests). The adapter now sets the variables only while libvosk loads, restores the environment, and reads the kernel and the thread count back from the library; `test_FR_0_7_02_openblas_kernel_pinned_and_verified` checks that the environment is unchanged. The WP-0.6 test passes again in the combined run.
- Fast suite after this step: `1715 passed, 39 deselected in 200.44s`.

### FR-0.7-07 — `phase0 smoke`, the result bundle and its report (and the Colab launcher for OC-0.7-01)
- Code: `aqis_lab/smoke.py` (CAP-SMOKE-001 to -004), `aqis_lab/commands/phase0.py` (CAP-SMOKE-005), `config/aqis_lab/phase0_smoke.yaml` (CAP-SMOKE-006), `aqis_lab/__main__.py` (`COMMANDS` entry `phase0`), `notebooks/aqis_lab/phase0_smoke_launcher.ipynb`; documents `docs/runs/PHASE0_SMOKE.md`, `docs/adapters/VOSK.md`, `docs/adapters/PARAKEET_UNIFIED.md`, `docs/adapters/HARNESS_VAD.md`, and the new OC-0.7-01 section of `docs/colab/COLAB_RUNBOOK.md` and OC-0.7-02 steps (inside "Report results back", plus one "When something fails" row) of `docs/oracle/ORACLE_RUNBOOK.md`. Existing runbook text is unchanged.
- Tests: `tests/aqis_lab/test_aqis_smoke.py` (4 fast tests; 11 `slow`+`network` tests share one real cloud smoke run with the real Vosk model, plus a second, resumed run), `tests/aqis_lab/test_aqis_smoke_launcher.py` (the WP-0.5 launcher rules, imported unchanged from `test_aqis_launcher.py`, applied to the new notebook), `tests/aqis_lab/test_aqis_smoke_live.py` (`colab`/`gpu`/`oracle`: owner-run).
- Tests first: the record of the first failing run of `test_aqis_smoke.py` was not kept. As a check made afterwards, in a copy of the tree (`/tmp/wp07-mustcatch`) without `aqis_lab/smoke.py` and `aqis_lab/parity.py`:
```text
E   ImportError: cannot import name 'smoke' from 'aqis_lab' (/tmp/wp07-mustcatch/aqis_lab/__init__.py)
E   ImportError: cannot import name 'parity' from 'aqis_lab' (/tmp/wp07-mustcatch/aqis_lab/__init__.py)
ERROR tests/aqis_lab/test_aqis_smoke.py
ERROR tests/aqis_lab/test_aqis_parity.py
```
  `test_aqis_smoke_launcher.py` against the runbook as committed before this step (same copy): `E       ValueError: substring not found` (the `## OC-0.7-01` section), `1 failed, 3 passed in 0.11s`. Its no-logic test also failed on the first run against the real notebook (below).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_smoke.py -q -p no:cacheprovider` (all markers, including the real cloud smoke)
```text
...................                                                      [100%]
19 passed in 131.28s (0:02:11)
```
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_smoke_launcher.py tests/aqis_lab/test_aqis_launcher.py tests/aqis_lab/test_aqis_oracle_runbook.py -q -p no:cacheprovider`: the launcher tests `4 passed`, the WP-0.5 launcher tests unchanged and passing (`46 passed` together with the first run), the Oracle runbook tests `3 passed`.
- **Launcher and the WP-0.5 rule checker.** The WP-0.5 checker (`test_aqis_launcher.command_shape_problems`) allows the bootstrap step only without options, and the approved plan (OC-0.7-01, question 13) has cell 3 run `dev_bootstrap.sh --gpu`. The first run reported exactly that:
```text
AssertionError: (3, ["line 4: command ['bash', 'aqis_lab/deploy/dev_bootstrap.sh', '--gpu'] is not one of the launcher's steps"])
```
  The WP-0.5 test file is unchanged. My new test expects exactly that one report on the line that holds `"aqis_lab/deploy/dev_bootstrap.sh", "--gpu"`, and nothing else in any cell. Every other rule (keywords, settings, token handling, no logic) applies to all cells unchanged.
- **Results store: now the plan's default.** The first version wrote to a new store beside each bundle. The plan says `--store` defaults to `data/raw/aqis_lab/results`, so `run_smoke` now uses `aqis_lab.results.store.DEFAULT_STORE`. The tests pass their own store. `test_FR_0_7_07_second_run_resumes_and_stores_nothing_new` now also checks that the second smoke run leaves every file of that store byte-identical.
- **Differences from the plan, for the owner.** One option is not in the plan's command line: `--bundle-dir` (default `data/raw/aqis_lab/smoke-bundles`). It is the local folder where the bundle is assembled and scored before the archive is written to `--out`. The plan puts the score folders on local disk and the bundle in `--out`; on Colab `--out` is on Drive. The option lets the tests keep the bundle in a temporary folder.

### FR-0.7-08 — `parity <A> <B>`
- Code: `aqis_lab/parity.py` (CAP-PARITY-001 to -003), `aqis_lab/commands/parity.py` (CAP-PARITY-004), `aqis_lab/__main__.py` (`COMMANDS` entry `parity`); bundle format and output in `docs/runs/PHASE0_SMOKE.md`.
- Tests: `tests/aqis_lab/test_aqis_parity.py`. The bundles are built by the test in the documented format, with real score tables from the WP-0.3 `score` command (`aqis_adapters_testutil.make_bundle`). The expected differences follow from how each test builds its bundles: 3 changed transcripts, 1 missing clip and 1 extra clip; a punctuation-only change that alters the hash but not the normalised WER; a total WER change; a damaged file, an extra file and a missing path; a task in one bundle only; folder and `.tar` giving the same lines. `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` is added for OC-0.7-03 once the Colab and Oracle bundles are committed.
- Tests first: see the collection errors under FR-0.7-07 (copy without `aqis_lab/parity.py`).
- **Defect found and fixed: the parity process sometimes never exited.** In the full fast suite, one `parity` CLI call hung until the test's 300 s timeout (`subprocess.TimeoutExpired … timed out after 300 seconds`, `1 failed, 1733 passed, 50 deselected in 503.26s`). `gdb` on a hung process showed the main thread in `arrow::internal::ThreadPool::Shutdown` from `exit()`, and a pool thread in `arrow::py::PyBuffer::~PyBuffer` → `PyGILState_Ensure`, reached from a `ParquetFileFragment` destructor. `pq.read_table(pa.BufferReader(bytes))` goes through Arrow's dataset layer, and a fragment holding the Python buffer was released only at interpreter exit. `_scores` now reads the table with `pq.ParquetFile(...)` in a `with` block, closed in the calling thread.
  - Reproduction (the CLI on two test bundles, each run with a 20 s limit), before: `runs 40: exit0 34, hangs 6`; after: `runs 100: exit0 100, hangs 0`.
  - The same check for the read patterns in WP-0.6's `results/ingest.py` (`pq.read_table(pa.BufferReader(…), use_threads=False)`) and `results/store.py` (`pq.read_table(io.BytesIO(…), use_threads=False)`), 60 runs each: `hangs 0` for both; the old parity pattern: `hangs 3`. So only the new parity code was affected, and nothing outside the change budget is touched.
  - New test `test_FR_0_7_08_parity_process_always_exits` (`slow`): 40 CLI runs, each must exit with its result within 60 s. With the old line put back in the copy: `subprocess.TimeoutExpired: … timed out after 60 seconds`, `1 failed, 7 deselected in 63.44s`. With the fix it passes.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_parity.py -q -p no:cacheprovider`
```text
........                                                                 [100%]
8 passed in 11.47s
```
- Fast suite after FR-0.7-07 and FR-0.7-08: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider`
```text
1734 passed, 51 deselected in 197.83s (0:03:17)
```
