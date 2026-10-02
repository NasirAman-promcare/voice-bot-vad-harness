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
- **The first fix was not enough.** In the slow suite, `test_FR_0_7_08_parity_process_always_exits` failed once (`TimeoutExpired … timed out after 60 seconds`). Six more runs of the test: 5 passed, 1 failed. A probe test in the `/tmp` clone ran the CLI inside pytest with `gdb` attached on a timeout: `runs 190 hangs 1`. It showed the same deadlock: a pool thread in `arrow::py::PyBuffer::~PyBuffer` → `PyGILState_Ensure`, reached from `arrow::io::BufferReader::~BufferReader` in `libparquet`, while the main thread waits in `arrow::internal::ThreadPool::Shutdown` from `exit()`. So closing the `ParquetFile` does not stop a pool thread from holding the last reference. Outside pytest the hang did not show in 760 runs; this is timing, not a different cause.
  - Root-cause fix: `_scores` copies the bytes into memory Arrow owns (`pa.BufferOutputStream`), so nothing Arrow releases at exit is a Python object. Probe after the fix, inside pytest: `runs 1000 hangs 0`.
  - WP-0.6's read patterns, in the same pytest probe, 600 runs each: `ingest runs 600 hangs 0`, `store runs 600 hangs 0`. Both pass `use_threads=False`, so no pool thread takes the buffer. Nothing outside WP-0.7 changes.
  - The test now runs the CLI 120 times (40 before).
- Fast suite after FR-0.7-07 and FR-0.7-08: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider`
```text
1734 passed, 51 deselected in 197.83s (0:03:17)
```

### DEBT-014 — the four older writers refuse Drive outside `MyDrive/AQIS_LAB` (NFR-0.5-02)
- Code, each change only in the planned function, plus its header text and CHANGE LOG:
  - `aqis_lab/commands/score.py` `write_outputs` (CAP-SCORE-005);
  - `aqis_lab/packs/build.py` `build_pack` (CAP-PACK-005; the pack folder and its staging folder);
  - `aqis_lab/commands/registry.py` `main`, build branch (CAP-REG-005; `--out` and its staging file);
  - `aqis_lab/registry/fetch.py` `fetch_dataset` (CAP-REG-003; the cache, archive, `.part`, extraction and staging paths).

  Each calls `aqis_lab.drive.check_write_path` before it reads or writes anything, and turns a `DriveError` or `PlatformError` into the command's own input error (`ERROR:`, exit 2). The imports are inside the functions, so the rest of each file is byte-identical (`git diff -U0`: one CAPABILITIES line, two CHANGE LOG lines and one hunk inside the named function per file).
- Tests: `tests/aqis_lab/test_aqis_debt_wp07.py`, `test_NFR_0_5_02_*`. The Drive test double is the WP-0.5 one: a local folder with a generated `fuse.drive` mountinfo line, installed as `SystemView.real`. Each command runs through its real `main`, with inputs it can really process: generated CSVs, and the WP-0.4 generated world with archives served over local HTTP. So without the guard it really writes to Drive. Three kinds of target are refused: a folder beside `AQIS_LAB`, `MyDrive` itself, and the Drive root. The same command with a folder inside `AQIS_LAB` succeeds.
- Tests first (real tree, before the fix): `4 failed in 3.05s`, each `assert 0 == 2`, meaning the command wrote to Drive and exited 0. One test of mine then failed for my own reason: `capsys` also held the set-up's download log. I fixed the test (`capsys.readouterr()` after set-up), not the code.
- The writers' existing tests, before and after: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_scoring_cli.py tests/aqis_lab/test_aqis_scoring_table.py tests/aqis_lab/test_aqis_packs_build.py tests/aqis_lab/test_aqis_packs_smoke.py tests/aqis_lab/test_aqis_registry_build.py tests/aqis_lab/test_aqis_registry_fetch.py tests/aqis_lab/test_aqis_drive_guard.py tests/aqis_lab/test_aqis_debt_wp05.py tests/aqis_lab/test_aqis_debt_wp06.py -q -p no:cacheprovider -m "not slow and not network"`
```text
before: 96 passed, 3 deselected in 30.46s
after:  96 passed, 3 deselected in 25.11s
```

### DEBT-015 items 2 to 4 — sync and store error paths
- Code, each change only in the planned function, plus header text and CHANGE LOG:
  - `aqis_lab/sync.py` `_check_destination` (item 2): a failed `rclone lsf` shows rclone's own message. It is `SyncFailed` (exit 1) unless rclone's exit code is 3, its documented "directory not found", which keeps the "must already exist" guidance and now shows rclone's message too.
  - `aqis_lab/sync.py` `run_sync` (item 3): `subprocess.TimeoutExpired` from `rclone copy` prints the copy's output so far, then raises `SyncFailed` (`ERROR:`, exit 1).
  - `aqis_lab/results/store.py` `_ensure_store` (item 4): the folder is created race-safely. A folder holding anything other than the store's own `.lock`, `STORE.json` or `STORE.json.partial` is refused before any file is made in it. `STORE.json` is then re-checked and published only while holding the store lock. `add_batch` needed no change.
- Real rclone behaviour, measured here (`rclone lsf aqisdrive:AQIS_LAB --dirs-only`):
  - an alias remote to an unconfigured remote: `Failed to create file system for "aqisdrive:AQIS_LAB": didn't find section in config file`, exit 1;
  - an alias remote to an empty folder: `error listing: directory not found`, exit 3.
- Tests: `test_FR_0_6_05_failed_remote_listing_shows_rclone_message` (real rclone, the expected message taken from rclone itself in the test); `test_FR_0_6_05_rclone_timeout_is_an_error` (real rclone for every call except `copy`, which a wrapper on `PATH` replaces with a process that never finishes; the time limit is set to 2 s for the test); `test_FR_0_6_02_simultaneous_first_adds_are_safe` (12 rounds of 4 processes, started with `spawn` and held at a barrier, adding to the same new store).
- Tests first (real tree, before the fix), 3 failed:
```text
AssertionError: ERROR: aqisdrive:AQIS_LAB not found: AQIS_LAB/results must already exist on Google Drive; … (assert 2 == 1)
subprocess.TimeoutExpired: Command '[…/bin/rclone', 'copy', …]' timed out after 2 seconds
AssertionError: (1, [('error', "FileExistsError: [Errno 17] File exists: '…/store-1'"), ('ok', 60), ('ok', 0), ('ok', 0)])
```
  In the pre-fix copy, with `spawn`, round 0 gave the misleading message the debt describes: `StoreInputError: …/store-0 is not a results store (no STORE.json) and is not empty`.
- One regression found and fixed on the way: `test_FR_0_6_06_runbook_has_each_required_step` reads `section "<name>"` from source lines, and my first message split it across two lines. The message now keeps it on one line. The test is unchanged.
- The files' existing tests, before and after: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_sync.py tests/aqis_lab/test_aqis_results_cli.py tests/aqis_lab/test_aqis_results_store.py tests/aqis_lab/test_aqis_trace.py tests/aqis_lab/test_aqis_debt_wp06.py -q -p no:cacheprovider -m "not slow and not network"`: before `63 passed in 31.96s`. After all debt fixes, together with the DEBT-014 files, `test_aqis_debt_wp07.py` and `test_aqis_oracle_runbook.py`: `1 failed, 167 passed` (the runbook regression above), then after the fix `26 passed in 13.24s` for `test_aqis_oracle_runbook.py`, `test_aqis_sync.py` and `test_aqis_debt_wp07.py`.
- New debt tests (before the DEBT-013 test was added): `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp07.py -q -p no:cacheprovider`: `7 passed in 8.20s`. In the pre-fix copy (`/tmp/wp07-mustcatch`, its own git repository at `8c1d2f6`): `7 failed in 6.87s`.

### Defect found by the DEBT-013 measurement: Vosk results depended on earlier clips in the process (fixed; FR-0.7-02)
- **What happened.** The first run of `test_NFR_0_5_01_runner_overhead_under_5_percent_on_vosk_batch` failed its like-for-like check. The runner and the direct loop, in the same process, gave different bytes for one clip:
```text
AssertionError: direct … At index 8648 diff: b'5' != b'6'
ls-test-other-3080-5040-0016 {'events': (16, 15), 'partials': (15, 14)}
```
- **Cause.** Kaldi dithers the features (the model's `conf/mfcc.conf` sets no `--dither`, so the default 1.0 applies) with noise from the C library's `rand()`. `libvosk.so` imports `rand`, `rand_r` and `srand` from glibc (`nm -D`), and that generator is one for the whole process. Measured on that clip, 2 model loads × 10 repeats in one process, three separate processes (`partials`, text hash, partial-event hash):
  - every process printed the same sequence of 20 results;
  - within a process the 20 results were all different, with 4 different transcripts (`d95e96069738`, `81fd88a2fbac`, `5a47641ea9b3`, `6b5b3ce0a45d`).

  With `srand(1)` before each repeat, all 20 were identical: `{(14, 'd95e96069738', '475944e22772'): 20}`. So the adapter's documented invariant ("the same samples, model, kernel and feed size give the same events and text") and the plan's "same bytes on a rerun" did not hold within a process. The consequences:
  - a resumed run could differ from an uninterrupted one;
  - `vosk-realspeed` depended on the batch run before it;
  - cross-machine parity depended on the whole history of each process.

  The existing `test_FR_0_7_02_same_input_gives_identical_transcript` repeats one clip twice, which happened not to show it.
- **Fix** (`aqis_lab/adapters/vosk_stt.py`, my own WP-0.7 module):
  - `start_clip` reseeds the C library's `rand()` with `C_RAND_SEED = 1` before each clip, and the run card records `c_rand_seed_per_clip: 1`.
  - glibc's `rand()` starts from seed 1, so each clip is computed exactly as the first clip of a fresh process.
  - The dither itself is unchanged: the pinned model files are never modified.
  - CAP-VOSK-001 and -003, `docs/adapters/VOSK.md` ("Feature dither").
  - **For the owner:** this is a new recorded setting in the Vosk run card, of the same kind as the OpenBLAS kernel pin (question 6).
- **Test first:** `test_FR_0_7_02_clip_result_independent_of_earlier_clips` (`network`) processes that clip 10 times, with 0 to 2 other clips before each repeat, in one process. Every repeat's fields and events must be identical and equal to Vosk run directly on the clip in a fresh process. Before the fix: `AssertionError: [14, 14, 14, 14, 14, 14, ...]` (`assert False`), `1 failed`. After: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_vosk.py -q -p no:cacheprovider`: `9 passed in 31.32s`; with the model-block test also checking `c_rand_seed_per_clip`, `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_vosk.py tests/aqis_lab/test_aqis_debt_wp07.py -q -p no:cacheprovider -m "not slow"`: `16 passed, 1 deselected in 38.25s`.

### DEBT-013 — NFR-0.5-01 (runner overhead under 5 %) on a real workload
- Test: `tests/aqis_lab/test_aqis_debt_wp07.py::test_NFR_0_5_01_runner_overhead_under_5_percent_on_vosk_batch` (`slow`, `network`), measured the way WP-0.5 measured `clip-stats`. The runner and a direct loop (the same adapter, model load included, every clip of the same staged pack, one fsynced results file) run in the same process. Each timed run must give the reference run's `results.jsonl` byte for byte. The test takes medians of 3 alternating repetitions and asserts an overhead under 5 %.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp07.py -q -p no:cacheprovider -k NFR_0_5_01 -s`
```text
NFR-0.5-01 on vosk-batch: direct median 69.03 s, runner median 69.15 s, overhead 0.18 % (limit 5 %); all times {'direct': [71683369841, 69028080052, 67309865828], 'runner': [69151041110, 70240005252, 66631015780]}
1 passed, 7 deselected in 483.68s (0:08:03)
```
- The runner's fixed cost measured in WP-0.5 (about 25 ms per run, 6 ms per shard) is negligible against a real model's work, as the WP-0.5 approval expected. The first run of this test found the Vosk dither defect above; the numbers are from the run after its fix.
- After DEBT-013, DEBT-014, DEBT-015 and the dither fix: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_runner_events.py tests/aqis_lab/test_aqis_realspeed.py -q -p no:cacheprovider` (all markers, with the real cloud smoke): `35 passed in 151.45s (0:02:31)`. Fast suite: `1741 passed, 53 deselected in 200.34s (0:03:20)`.

## Acceptance commands

### AT-0.7-01 and NFR-0.7-01 — `phase0 smoke --target cloud` on a clean tree, contracts, trace
- Tree clean at `0a534ce` (`git status --short` printed nothing). Command: `time .venv/bin/python -m aqis_lab phase0 smoke --target cloud` (default folders: run folders and archive in `data/raw/aqis_lab/smoke/cloud`, store `data/raw/aqis_lab/results`, bundle `data/raw/aqis_lab/smoke-bundles`). Excerpt:
```text
2026-09-30T17:04:40.551480Z cores: no reservation (platform cloud-vm)
2026-09-30T17:05:51.662705Z run complete: 1 shard(s), 0 skipped and 1 computed in this session; results.jsonl sha256 2f42f17998622d836338e5fb8ea80af3e9df5846cb842f730e1bb46f1bce7da0 (60 rows)
2026-09-30T17:05:51.697661Z cores: no reservation (platform cloud-vm)
2026-09-30T17:05:52.037619Z run complete: 1 shard(s), 0 skipped and 1 computed in this session; results.jsonl sha256 70615de08363a75f1531f110aa8bba3d4527b333832ab4aeeb3aacc937f3ad34 (60 rows)
2026-09-30T17:05:52.088935Z cores: no reservation (platform cloud-vm)
2026-09-30T17:06:18.721877Z run complete: 1 shard(s), 0 skipped and 1 computed in this session; results.jsonl sha256 5fc67ae2ad3098abd175de42c5f8ac57b725cb61ceaa612e8f8772f7241a5888 (5 rows)
scored vosk-batch natural: utterances 40, empty references 0
scored vosk-batch synthetic-tts: utterances 10, empty references 0
smoke complete: bundle /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z (23 files, 225 rows traced), archive /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/phase0-smoke-cloud-20260930T170440Z.tar, 105.7 s
real	1m46.181s
exit=0
```
- NFR-0.7-01: 105.7 s on this VM (limit 900 s); `BUNDLE.json` `elapsed_s` records it, and `test_NFR_0_7_01_cloud_smoke_within_15_minutes` asserts it.
- Contracts: every run card and every event log of the bundle.
```text
$ .venv/bin/python -m aqis_lab contracts validate --kind run_card data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/vosk-batch/run_card.json
run_card: 1 record, 1 valid, 0 invalid
exit 0
$ .venv/bin/python -m aqis_lab contracts validate --kind run_card data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/harness-vad/run_card.json
run_card: 1 record, 1 valid, 0 invalid
exit 0
$ .venv/bin/python -m aqis_lab contracts validate --kind run_card data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/vosk-realspeed/run_card.json
run_card: 1 record, 1 valid, 0 invalid
exit 0
$ .venv/bin/python -m aqis_lab contracts validate --kind event data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/vosk-batch/events.jsonl
event: 894 records, 894 valid, 0 invalid
exit 0
$ .venv/bin/python -m aqis_lab contracts validate --kind event data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/harness-vad/events.jsonl
event: 462 records, 462 valid, 0 invalid
exit 0
$ .venv/bin/python -m aqis_lab contracts validate --kind event data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20260930T170440Z/runs/vosk-realspeed/events.jsonl
event: 81 records, 81 valid, 0 invalid
exit 0
```
- `trace` on one row of each kind, with row IDs taken from the bundle's report. Excerpt; every call exited 0, and the full output shows each row's run card:
```text
$ .venv/bin/python -m aqis_lab trace fa8f7d0a7dafdde0e282855c88ca7ecb029181b5938c0270e7ba623a05150d39   # score
kind: score
clip_id: ls-test-clean-1188-133604-0029
run_card_id: 5eb8cb06f90d81fd2eb8290d3bdc09e4e799c57e2eb835e0f011b49673b70350
git_commit: 0a534ce22bf7d1d0b5d266920d2302bced0ef865 (dirty: false)
exit 0
$ .venv/bin/python -m aqis_lab trace 994765df172b2bae9503c7136c8bde30ec91eeab06d563e9dc87c1c4d0b0d57a   # vosk-batch
kind: run-result
clip_id: ls-test-clean-1188-133604-0029
run_card_id: 5eb8cb06f90d81fd2eb8290d3bdc09e4e799c57e2eb835e0f011b49673b70350
git_commit: 0a534ce22bf7d1d0b5d266920d2302bced0ef865 (dirty: false)
exit 0
$ .venv/bin/python -m aqis_lab trace fd80b149df8e3bc822c3a474660175743dde9510d2aadc653742fa5f61bec643   # vosk-realspeed
kind: run-result
clip_id: ls-test-clean-3570-5695-0009
run_card_id: 7a61ecfefa4b184d488bd377edf9e3858ee2e945b945bf6e464ef2b3b15d3bee
git_commit: 0a534ce22bf7d1d0b5d266920d2302bced0ef865 (dirty: false)
exit 0
$ .venv/bin/python -m aqis_lab trace 1881693905111f2044839f86c6b8ee97f0216a4e304dda41772d1d944dca21d0   # harness-vad
kind: run-result
clip_id: ls-test-clean-1188-133604-0029
run_card_id: 14db429d748b304b375a9a21bd00846001180575f86156a4f87c76bbc11ff3be
git_commit: 0a534ce22bf7d1d0b5d266920d2302bced0ef865 (dirty: false)
exit 0
```
  My first pick of the score row took the summary table's `summary.json` SHA-256 instead of a row ID. `trace` refused it correctly (`ERROR: result row cc9156be… is not in the results store …`, exit 1), and the row above comes from the "WER per clip" table.
- The bundle is committed as `data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar` (808,960 bytes). Its report is byte-copied into `docs/runs/PHASE0_SMOKE.md` ("Reports"). `test_FR_0_7_07_committed_bundles_and_their_reports_in_docs` checks every committed bundle against its `BUNDLE.json`, a clean tree whose commit is an ancestor of `HEAD`, and the report copy: `1 passed, 19 deselected in 0.41s`. Parity of the committed archive against the bundle folder: `parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)`.

## Must-catch proof
Every break was made in a fresh clone of this branch at `175a361` (`/tmp/wp07-mc`; `.venv` and the test model cache are symlinks to the real ones). The script applied one exact text replacement per break, ran the named tests with `.venv/bin/python -m pytest -q -p no:cacheprovider <tests>`, printed pytest's summary and every `FAILED` line, and restored the file with `git checkout -- .`; `git status` then showed only the untracked `.venv` link. Breaks 1 to 6 are the plan's must-catch list. 7 to 9 add DEBT-017, the dither reseed and the committed report copy.
```text
### 1a: sink no longer validates events
broken: aqis_lab/adapters/base.py (1 file changed, 1 deletion(-))
summary: 5 failed in 0.24s
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_sink_refuses_invalid_event[bad0]
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_sink_refuses_invalid_event[bad1]
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_sink_refuses_invalid_event[bad2]
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_sink_refuses_invalid_event[bad3]
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_sink_refuses_invalid_event[bad4]
### 1b: sink no longer validates and the VAD emits an event type outside event log v1
broken: aqis_lab/adapters/base.py, aqis_lab/adapters/harness_vad.py (2 files changed, 1 insertion(+), 2 deletions(-))
summary: 1 failed in 0.79s
FAILED tests/aqis_lab/test_aqis_runner_events.py::test_FR_0_7_01_events_validate_against_event_log_v1
restored: ?? .venv

### 2: guarded() no longer emits the error event
broken: aqis_lab/adapters/base.py (1 file changed, 3 deletions(-))
summary: 2 failed in 0.84s
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_adapter_failure_emits_error_event_and_raises
FAILED tests/aqis_lab/test_aqis_runner_events.py::test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event
restored: ?? .venv

### 3: Parakeet preflight no longer refuses a machine without a GPU
broken: aqis_lab/adapters/parakeet_unified.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 2 failed in 6.75s
FAILED tests/aqis_lab/test_aqis_parakeet.py::test_FR_0_7_03_refuses_without_gpu
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_03_colab_smoke_without_gpu_fails_never_skips
restored: ?? .venv

### 4a: the download's SHA-256 is no longer checked
broken: aqis_lab/adapters/model_cache.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.44s
FAILED tests/aqis_lab/test_aqis_model_cache.py::test_FR_0_7_02_model_rejected_when_checksum_differs
restored: ?? .venv

### 4b: a fetched model's files are no longer checked at load
broken: aqis_lab/adapters/model_cache.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.25s
FAILED tests/aqis_lab/test_aqis_model_cache.py::test_FR_0_7_02_changed_model_file_rejected_at_load
restored: ?? .venv

### 5: the feeder no longer waits for each frame's real-time deadline
broken: aqis_lab/realspeed.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.25s
FAILED tests/aqis_lab/test_aqis_realspeed.py::test_FR_0_7_05_feeder_never_faster_than_real_time
restored: ?? .venv

### 6: parity no longer reports a changed transcript hash
broken: aqis_lab/parity.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.82s
FAILED tests/aqis_lab/test_aqis_parity.py::test_FR_0_7_08_reports_every_per_clip_difference
restored: ?? .venv

### 7: the real-speed feeder no longer pins itself (DEBT-017)
broken: aqis_lab/realspeed.py (1 file changed, 1 deletion(-))
summary: 1 failed in 3.47s
FAILED tests/aqis_lab/test_aqis_realspeed.py::test_FR_0_7_05_feeder_pins_every_thread_to_timing_cores
restored: ?? .venv

### 8: the Vosk adapter no longer reseeds the dither generator per clip
broken: aqis_lab/adapters/vosk_stt.py (1 file changed, 1 deletion(-))
summary: 1 failed in 21.98s
FAILED tests/aqis_lab/test_aqis_vosk.py::test_FR_0_7_02_clip_result_independent_of_earlier_clips
restored: ?? .venv

### 9: the report copied into docs/runs/PHASE0_SMOKE.md differs from the committed bundle
broken: docs/runs/PHASE0_SMOKE.md (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.39s
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_committed_bundles_and_their_reports_in_docs
restored: ?? .venv

```
Two more, for the FR-0.7-01 tests added last (below), in the same clone after committing those tests there:
```text
### 10: the harness VAD adapter declares a component outside event log v1
broken: aqis_lab/adapters/harness_vad.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.27s
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_every_adapter_declares_component_model_and_settings
restored: ?? .venv

### 11: a runner task reads and processes a clip outside the failure guard
broken: aqis_lab/runner/tasks.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 0.25s
FAILED tests/aqis_lab/test_aqis_adapters_base.py::test_FR_0_7_01_clip_in_wrong_format_emits_error_event_and_raises
restored: ?? .venv
```
Also proved in the sections above:
- the parity exit hang (`test_FR_0_7_08_parity_process_always_exits`, old line restored: `TimeoutExpired`);
- the seven debt tests against the pre-fix code (`7 failed in 6.87s`).

### FR-0.7-01 — two planned tests added at the end
Comparing the plan's test names with the test files showed two planned tests missing. One was `test_FR_0_7_01_every_adapter_declares_component_model_and_settings`. The other was `test_FR_0_7_08_cloud_colab_oracle_bundles_identical`, which the plan adds for OC-0.7-03 once the Colab and Oracle bundles are committed. The plan also named "an 8 kHz clip for the VAD" as a real failure for must-catch 2, and no test had it. I wrote these after the code they test, so no failing first run exists. Breaks 10 and 11 above show that each fails when its behaviour is broken.
- `test_FR_0_7_01_every_adapter_declares_component_model_and_settings` (`tests/aqis_lab/test_aqis_adapters_base.py`, CAP-ADAPT-001). Every adapter task of the runner names an `Adapter` subclass with a name and an event-log component (Vosk `live_stt`, harness VAD `vad`, Parakeet `heavy_stt`). Its task's run-card mode is in the run-card enum. Its model block has exactly family, name, version, checksum and non-empty settings.
  - **Difference from the plan's wording:** the plan lists `mode` among the `Adapter` attributes. The build declares the mode on the runner task (`AdapterTask.mode`), because the one Vosk adapter serves two modes (`vosk-batch` `batch`, `vosk-realspeed` `realspeed_cpu`). The run card records the mode as the plan says.
- `test_FR_0_7_01_clip_in_wrong_format_emits_error_event_and_raises` (CAP-RUN-010). The real `harness-vad` task gets an 8 kHz WAV clip. It writes `clip_started`, then one `error` event (`harness-vad-clip-failed`, the message naming 8000 Hz, `run_continues: false`), then raises `AdapterError`.
- The base-class tests in that file use `ListeningAdapter`, a small concrete subclass of the abstract `Adapter` defined in the test, to reach `guarded()` and the sink directly. It replaces no production component. Real adapter failures are tested with the real adapters: a damaged Vosk model (`test_FR_0_7_01_vosk_unusable_model_emits_error_event_and_raises`), a Vosk model cache without its marker through the runner (`test_FR_0_7_01_runner_stops_on_adapter_error_with_error_event`), and the 8 kHz VAD clip above.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_adapters_base.py -q -p no:cacheprovider`: `16 passed in 0.39s`.

## Owner-run checks
The WP-0.7 tests that cannot run on this VM are the two `colab`+`gpu` tests in `tests/aqis_lab/test_aqis_smoke_live.py`. `pytest -m "colab or gpu" --collect-only` collects 5 tests: those two, plus WP-0.5's three Colab tests. The Oracle check runs WP-0.6's 2 `oracle` tests (`pytest -m oracle --collect-only`: `test_FR_0_6_01_setup_passes_on_oracle`, `test_FR_0_6_04_real_oracle_pinning`). The tags are pushed only after the audit passes.

| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| OC-0.7-01 | Colab, **T4 GPU** runtime; launcher `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` at tag `aqis-lab-wp-0.7-colab-1` | Cells 1 to 4 (`docs/colab/COLAB_RUNBOOK.md`, "OC-0.7-01"). Cell 3: `dev_bootstrap.sh --gpu`. Cell 4: `drive layout`, `unitlog start`, `doctor --target colab --expect-gpu`, then `phase0 smoke --target colab --out /content/drive/MyDrive/AQIS_LAB/results/phase0-smoke-colab --drive-mount /content/drive`. Then one extra cell: `!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m "colab or gpu"`. Then cell 5 | Cell 3: `OK: .venv ready: Python 3.13.x, lock sha256 87a1cc34…` and `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …`. Doctor: `gpu` PASS `Tesla T4`, `lock` PASS naming `requirements/aqis_lab/phase0.txt + requirements/aqis_lab/phase0-gpu.txt`, `result: PASS`. Smoke: logs of the five tasks, then `smoke complete: bundle … archive /content/drive/MyDrive/AQIS_LAB/results/phase0-smoke-colab/phase0-smoke-colab-<stamp>.tar`. pytest: `5 passed` | the `.tar` into `data/runs/phase0-smoke/`; `docs/environment/doctor_colab_<timestamp>.json`; the output of cells 3 and 4 and of pytest in `docs/progress/WP-0.7/OC-0.7-01_colab.txt` |
| OC-0.7-02 | Oracle VM, clone at tag `aqis-lab-wp-0.7-oracle-1` | 1. `dpkg -s libatomic1 \| grep Status` 2. `bash aqis_lab/deploy/oracle_setup.sh` 3. `.venv/bin/python -m aqis_lab phase0 smoke --target oracle` 4. `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle` (`docs/oracle/ORACLE_RUNBOOK.md`, "OC-0.7-02") | 1: `Status: install ok installed`. 2: six steps PASS; step 4 names `srt` as the approved source build. 3: the batch runs log `cores: batch on 0-1 …`, the real-speed run logs `cores: timing on 2-3 …`, and the last line is `smoke complete: … archive data/raw/aqis_lab/smoke/oracle/phase0-smoke-oracle-<stamp>.tar …`. 4: `2 passed` | the `.tar` into `data/runs/phase0-smoke/`; the output of all four in `docs/progress/WP-0.7/OC-0.7-02_oracle.txt` |
| OC-0.7-03 | This cloud VM, by Claude, after both bundles are committed | `.venv/bin/python -m aqis_lab parity data/runs/phase0-smoke/<A>.tar data/runs/phase0-smoke/<B>.tar` for cloud↔colab, cloud↔oracle and colab↔oracle; then add `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` and copy the two reports into `docs/runs/PHASE0_SMOKE.md` | Exit 0, `parity: identical (…)` for each pair. Any `DIFFERENT` line goes to the owner as a blocker with every line, never hidden | parity outputs in `docs/runs/PHASE0_SMOKE.md` |

## Audit-allow lines
None: `grep -rn "audit-allow" aqis_lab tools` finds no WP-0.7 line (checked with the audit gate below).

### Slow suite, first full run (AT-0.7-02), and what it found
- Command: `time .venv/bin/python -m pytest tests/aqis_lab -q -m "slow and not gpu and not colab and not oracle" -p no:cacheprovider`: `3 failed, 31 passed, 1761 deselected in 1339.65s (0:22:19)`.
  - `test_FR_0_0_12_provisions_harness_end_to_end` and `test_FR_0_0_12_second_run_downloads_nothing_within_60s`: `[FAIL] git-status: git status --porcelain is not empty`. I had edited files while the suite ran, and these tests need a clean tree. They are rerun on a clean tree.
  - `test_FR_0_7_08_parity_process_always_exits`: the remaining parity exit hang, fixed above.
- The next fast-suite run failed 6 tests: `6 failed, 1738 passed, 53 deselected`.
  - Five were WP-0.5 doctor tests, with the doctor's `disk` row FAIL: 5.66 GB free against the 10 GB minimum. The disk was full of my own leftovers: the scratch GPU environment (6.4 GB) and its packages in the uv cache (`uv cache clean` of the GPU-only packages: `Removed 18295 files (5.3GiB)`), and old pytest folders (2.3 GB). After cleaning, the doctor gives `disk PASS … 14,007,123,968 bytes (14.01 GB)` and `result: PASS`, and the doctor tests pass. Nothing in the code changed for this.
  - The sixth was `tests/aqis_lab/test_aqis_registry_fetch.py::test_FR_0_4_02_no_raw_corpus_committed`: `AssertionError: assert ['data/runs/p...T170440Z.tar'] == []`. This WP-0.4 test allows no `.tar` under `data/` except pack archives, and the approved plan (question 11) commits the smoke bundles as `data/runs/phase0-smoke/<name>.tar`. The test is an existing, guarded file, so this is BLK-010 (`docs/progress/BLOCKERS.md`), for the owner. `test_FR_0_7_07_committed_bundles_and_their_reports_in_docs` now also checks that a committed bundle holds only result files (`.json`, `.jsonl`, `.md`, `.csv`, `.parquet`, `.log`), never audio; the cloud bundle holds 9, 6, 1, 2, 2 and 3 of those.

### BLK-010 resolved — the approved change to `test_FR_0_4_02_no_raw_corpus_committed`
- Owner answer: option 1 (`docs/approvals/WP-0.7.md` on `main`, `6ed6229`, merged into this branch as `bb901b9`). The same approval also approves:
  - the per-clip Vosk reseed (`c_rand_seed_per_clip: 1`);
  - `--bundle-dir`;
  - the run mode declared per runner task;
  - the smoke launcher check accepting `dev_bootstrap.sh --gpu`.

  It notes the two tests written after their code, and sets OC-0.7-01, OC-0.7-02 and the three-way parity to run after the audit on the tagged commits.
- Before the change: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_registry_fetch.py -q -p no:cacheprovider -m "not slow and not network"`: `1 failed, 15 passed, 1 deselected in 14.85s` (`test_FR_0_4_02_no_raw_corpus_committed`).
- The change, the whole `git diff -U0`:
```text
@@ -215 +215,2 @@ def test_FR_0_4_02_no_raw_corpus_committed():
-    allowed = re.compile(r"^data/(tts_smoke/[0-9]{2}\.wav|packs/[a-z0-9-]+/v[0-9]+/[a-z0-9.-]+\.tar)$")
+    allowed = re.compile(r"^data/(tts_smoke/[0-9]{2}\.wav|packs/[a-z0-9-]+/v[0-9]+/[a-z0-9.-]+\.tar"
+                         r"|runs/phase0-smoke/phase0-smoke-(cloud|colab|oracle)-[0-9]{8}T[0-9]{6}Z\.tar)$")
```
- Checked against names: the pattern accepts `…/phase0-smoke-cloud-20260930T170440Z.tar` and `…/phase0-smoke-oracle-20261003T101010Z.tar`. It still rejects `…/phase0-smoke-kaggle-….tar`, `…/corpus.tar`, `….tar.gz`, `data/runs/other/….tar` and a stamp without a time. Pack archives and `data/tts_smoke/NN.wav` are still accepted.
- After: the same command, `16 passed, 1 deselected in 30.74s`. `test_FR_0_7_07_committed_bundles_and_their_reports_in_docs` still checks that each committed bundle holds result files only.

### AT-0.7-02 — fast suite, slow suite, audit gate (final, on a clean tree at `4fa02a1`)
- Slow suite, second full run, nothing edited while it ran (`git status --short` empty before and after): `time .venv/bin/python -m pytest tests/aqis_lab -q -m "slow and not gpu and not colab and not oracle" -p no:cacheprovider`
```text
4fa02a1 WP-0.7 BLK-010: accept committed smoke bundles in test_FR_0_4_02_no_raw_corpus_committed (owner option 1)
34 passed, 1763 deselected in 2224.96s (0:37:04)
real	37m5.457s
```
  This includes the two WP-0.0 provisioning tests that the first run failed on a dirty tree, the 120-run parity exit test, the DEBT-013 overhead test and the real cloud smoke tests. It took longer than the first run (22 min) because WP-0.4's pack-build tests read the large archives from disk again.
- Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider`
```text
1744 passed, 53 deselected in 285.31s (0:04:45)
```
- Audit gate: `git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.7`
```text
aqis-audit-gate: base origin/main (merge-base 6ed6229ea0a6), head 4fa02a11a327, approvals origin/main 6ed6229ea0a6, wp WP-0.7
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.9 s)
```
- CI on `4fa02a1` (run 270, https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36969185359): `harness-regression` success; `lab` success (fast suite, then the audit gate). CI on the final commit is in the pull request.
- Pending by design (approval of 2026-10-02): OC-0.7-01, OC-0.7-02 and the three-way parity (OC-0.7-03) run after the audit on the tagged commits; see "Owner-run checks".
