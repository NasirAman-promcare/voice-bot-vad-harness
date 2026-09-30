# EVIDENCE — WP-0.6 Oracle worker, results store and traceability

Environment: cloud VM (`cloud-vm`, signal `CLAUDE_CODE_REMOTE=true`), Ubuntu 24.04.4 LTS, x86_64, 4 CPUs, Python 3.13.12 in `.venv`, lock `requirements/aqis_lab/phase0.txt` sha256 `5cb021306b9335293fb3f2d10de1cee54adf8763da4b51a75b8f5ee3bf5e6337`, rclone v1.60.1 (Ubuntu package), uv 0.8.17. Code at `6034fb0` unless a line says otherwise. Branch `claude/relaxed-davinci-iwk5gi`.

Owner inputs used: `docs/environment/oracle_probe.txt` and `docs/approvals/WP-0.6.md` on `main` (`6ad251b`): questions 1-16 as recommended; VM.Standard.A1.Flex (Ampere A1, aarch64, 4 OCPUs, 24 GB); cores 2-3 reserved for timing runs, batch runs on 0-1; DEBT-008 closed in this WP. BLK-009 resolved (`0c2ef51`).

## Requirements

### FR-0.6-01 — `oracle_setup.sh` (venv on the Colab Python, lock, doctor; idempotent; x86_64 and aarch64; clear stop naming a package without a build)
- Code: `aqis_lab/deploy/oracle_setup.sh` (CAP-ENV-007), `aqis_lab/oracle_config.py` (CAP-ORACLE-001), `config/aqis_lab/oracle.yaml`.
- Tests: `test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing`, `test_FR_0_6_01_dry_run_in_this_repository_reuses_venv`, `test_FR_0_6_01_refuses_unsupported_architecture` (with and without `--dry-run`), `test_FR_0_6_01_refuses_unsupported_operating_system`, `test_FR_0_6_01_refuses_glibc_below_minimum`, `test_FR_0_6_01_supports_x86_64_and_aarch64`, `test_FR_0_6_01_setup_pin_read_by_script_equals_yaml`, `test_FR_0_6_01_missing_build_names_the_package`, `test_FR_0_6_01_fails_when_uv_missing`, the `test_FR_0_6_01_config_*` tests (`tests/aqis_lab/test_aqis_oracle_config.py`); network: `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds`, `test_FR_0_6_01_refuses_other_uv_version` (slow), `test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor` (slow), `test_FR_0_6_01_second_run_changes_nothing` (slow); oracle: `test_FR_0_6_01_setup_passes_on_oracle`.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_01 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
33 passed, 1624 deselected in 3.44s
```
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_6" -m "network and not oracle" -rA`
```text
PASSED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_refuses_other_uv_version
PASSED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds
PASSED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor
PASSED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_second_run_changes_nothing
4 passed, 1653 deselected in 5.77s
```
  (The last run is after the fix below; the first run of this command gave `1 failed, 3 passed` on `second_run_changes_nothing`, see "Doctor report names within one second".)
- aarch64: this VM is x86_64. The aarch64 path is proven by resolving every lock pin against PyPI for `aarch64-manylinux_2_28` with binary builds only (`every_lock_package_has_x86_64_and_aarch64_builds`), and by OC-0.6-01 on the Ampere A1 VM.
- Status: DONE (OC-0.6-01 pending, owner-run).

### FR-0.6-02 — Results store (append-only files partitioned by `run_card_id`, never overwritten, documented schema, DuckDB view; `results query --run-card <id>`)
- Code: `aqis_lab/results/store.py` (CAP-RESULTS-001, -002), `ingest.py` (-003, -004), `views.py` (-005), `aqis_lab/commands/results.py` (-006); schema `docs/results/RESULTS_STORE.md` (CAP-DOC-013); lock adds `duckdb==1.5.6` only (`fab8340`).
- Tests: `tests/aqis_lab/test_aqis_results_store.py`, `tests/aqis_lab/test_aqis_results_cli.py` (all `test_FR_0_6_02_*`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_02 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
31 passed, 1626 deselected in 17.30s
```
- Real run on the smoke pack (scratchpad folder `demo`):
```text
$ .venv/bin/python -m aqis_lab results add --run demo/run --store demo/store
stored 60 row(s) for run card 195f01a7ad82b063e47e3f1289d85761d12c215b44f4c9d55de8d4d590410ed0 in .../demo/store/run_card_id=195f01a7ad82b063e47e3f1289d85761d12c215b44f4c9d55de8d4d590410ed0/part-72b763d069827d97be6a7d15b9574db06884144e2c3a0dc9790c0566c4a7f798.parquet
add exit 0
$ .venv/bin/python -m aqis_lab results query --run-card 195f01a7…0ed0 --store demo/store
query exit 0 lines 60
{"added_by":"aqis_lab 0.0.1 commit=6034fb0 python=3.13.12","added_utc":"2026-09-29T06:47:23.508179Z","clip_id":"ls-test-clean-1188-133604-0029","identity":{"clip_id":"ls-test-clean-1188-133604-0029","kind":"run-result","run_card_id":"195f01a7…0ed0","task":"clip-stats","task_version":"1.0"},"kind":"run-result","result_row_id":"f594a4f07acbd247a06ac2629d0f7c40db86ccc4c6216f6faa538a68b2fa183a","row":{"channels":1,"clip_id":"ls-test-clean-1188-133604-0029","peak_abs":8916,...
```
- DuckDB offline: `test_FR_0_6_02_duckdb_needs_no_network` runs the view with every proxy pointing at a closed port and an empty `HOME`; `parquet` and `json` report `STATICALLY_LINKED`, 60 rows, and nothing is written to `HOME`.
- Status: DONE.

### FR-0.6-03 — `python -m aqis_lab trace <result-row-id>`
- Code: `aqis_lab/trace.py` (CAP-TRACE-001), `aqis_lab/commands/trace.py` (CAP-TRACE-002).
- Tests: `tests/aqis_lab/test_aqis_trace.py` (all `test_FR_0_6_03_*`); every one of 126 stored rows (two run cards and six score rows) is traced and compared with the source `run_card.json` read in the test.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_03 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
9 passed, 1648 deselected in 4.39s
```
- Real run:
```text
$ .venv/bin/python -m aqis_lab trace f594a4f07acbd247a06ac2629d0f7c40db86ccc4c6216f6faa538a68b2fa183a --store demo/store
result_row_id: f594a4f07acbd247a06ac2629d0f7c40db86ccc4c6216f6faa538a68b2fa183a
kind: run-result
clip_id: ls-test-clean-1188-133604-0029
run_card_id: 195f01a7ad82b063e47e3f1289d85761d12c215b44f4c9d55de8d4d590410ed0
pack_manifest_id: smoke
pack_version: 1.0.0
pack_sha256: 90df3820e368a5d67c9036be77dfd70a4f5cfcdbd57bd170e64abb08ed3692ef
git_commit: 6034fb087135d93b97769d0e4605be9b02d63a69 (dirty: false)
lock_file: requirements/aqis_lab/phase0.txt
lock_sha256: 5cb021306b9335293fb3f2d10de1cee54adf8763da4b51a75b8f5ee3bf5e6337
run_card:
{
  "created_utc": "2026-09-29T06:47:22.626765Z",
trace exit 0
```
- Status: DONE.

### FR-0.6-04 — Timing runs pinned to the reserved cores, batch runs kept off them; a test reads the process CPU affinity
- Code: `aqis_lab/timing/cores.py` (CAP-CORES-001, -002); `aqis_lab/platform.py` new functions only (CAP-PLAT-004); `aqis_lab/runner/run.py` (`RunOptions.cores_config`, `run`); `aqis_lab/doctor.py` (`run_doctor`, `_check_cores`); `docs/runner/RUNNER.md`, `docs/doctor/DOCTOR.md`.
- Tests: `tests/aqis_lab/test_aqis_timing_cores.py`. `test_FR_0_6_04_timing_process_pinned_to_reserved_cores` and `test_FR_0_6_04_batch_run_kept_off_reserved_cores` read `Cpus_allowed_list` of **every thread** in `/proc/<pid>/task/*/status` of the running process, from outside it; the Oracle cores are the allowed test double (a generated system tree with the `OracleCloud.com` tag and topology files), the pinning itself is real.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_04 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
15 passed, 1642 deselected in 3.77s
```
- Real runner on this VM logs the platform rule: `2026-09-29T06:47:23.129253Z cores: no reservation (platform cloud-vm)`.
- Committed reservation: `cores.reserved_for_timing: [2, 3]` (approval), probe `On-line CPU(s) list: 0-3`, so batch runs use 0-1 (`test_FR_0_6_04_committed_reservation_fits_oracle_probe`).
- Status: DONE (the real-VM check `test_FR_0_6_04_real_oracle_pinning` runs in OC-0.6-01).

### FR-0.6-05 — `python -m aqis_lab sync [--dry-run]`: one way to `AQIS_LAB/results` with rclone, never deleting remote files; missing remote points to the runbook
- Code: `aqis_lab/sync.py` (CAP-SYNC-001, -002), `aqis_lab/commands/sync.py` (CAP-SYNC-003); CI job `lab` installs rclone from the Ubuntu archive (`.github/workflows/aqis-lab-ci.yml`).
- Tests: `tests/aqis_lab/test_aqis_sync.py`, with the real rclone and an rclone `alias` remote on a local folder as the Drive test double.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_05 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
17 passed, 1640 deselected in 7.11s
```
- CI (real rclone on GitHub's runner): run 235 on `e0d263c`, the first commit with sync and the rclone step: `success`.
- Status: DONE (OC-0.6-02 pending, owner-run).

### FR-0.6-06 — Oracle runbook
- File: `docs/oracle/ORACLE_RUNBOOK.md` (CAP-DOC-012): before you start, clone (read-only deploy key), install uv and rclone, setup, doctor, core reservation (with the optional `system.slice AllowedCPUs=0-1` setting, your choice), configure rclone for Google Drive (headless `rclone authorize "drive"`, scope `drive`), first sync, nightly sync schedule (`flock -n` cron line), report results back (OC-0.6-01, OC-0.6-02), when something fails, update to a new tag.
- Tests: `test_FR_0_6_06_runbook_has_each_required_step`, `test_FR_0_6_06_runbook_commands_exist_and_parse`, `test_FR_0_6_06_runbook_matches_config`.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_6_06 -m "not slow and not gpu and not colab and not oracle and not network"`
```text
3 passed, 1654 deselected in 0.77s
```
- Status: DONE.

### DEBT-008 (approval: "closed in this WP")
- Fix: `write_outputs` in `aqis_lab/commands/score.py` creates `--out` inside its error handling.
- Test `test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2` (`tests/aqis_lab/test_aqis_debt_wp06.py`). Before the fix it failed for the right reason:
```text
>       assert proc.returncode == 2, proc.stderr
E       assert 1 == 2
1 failed in 0.29s
```
  After: `1 passed, 1656 deselected in 1.12s`; all WP-0.3 tests: `187 passed, 1467 deselected in 39.33s`.
- `docs/progress/DEBT.md` DEBT-008 set to CLOSED.

## Must-catch proof
Each behaviour broken in a copy of the repository under `/tmp/aqis-mustcatch` (script in the session scratchpad, `mustcatch.py`), then the named tests run there. Every break is caught:

| # | Break | Tests that failed |
| --- | --- | --- |
| 1 | `add_batch` stores a conflicting row instead of refusing (`if conflicts:` → `if False:`) | `test_FR_0_6_02_refuses_to_overwrite_existing_rows` |
| 1 | `publish` replaces with `os.replace` instead of a hard link | `test_FR_0_6_02_existing_files_never_replaced` |
| 2 | `trace` reads the first stored run card instead of the row's own | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock`, `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card` |
| 3 | Only the calling thread is pinned (`os.sched_setaffinity(0, cpus)`) | `test_FR_0_6_04_timing_process_pinned_to_reserved_cores`, `test_FR_0_6_04_batch_run_kept_off_reserved_cores` |
| 3 | The runner does not pin batch runs | `test_FR_0_6_04_batch_run_kept_off_reserved_cores` |
| 4 | `rclone sync` instead of `rclone copy` | `test_FR_0_6_05_never_deletes_remote_files`, `test_FR_0_6_05_command_is_copy_only` |
| 4 | `--immutable` removed | `test_FR_0_6_05_never_replaces_a_remote_file`, `test_FR_0_6_05_command_is_copy_only` |
| 5 | Architecture check removed from `oracle_setup.sh` | `test_FR_0_6_01_refuses_unsupported_architecture` (both parameters) |
| 5 | Operating-system check removed | `test_FR_0_6_01_refuses_unsupported_operating_system` |

Real output:
```text
MC1a conflict stored instead of refused | aqis_lab/results/store.py | rc=1 | 1 failed, 1656 deselected in 2.86s | failed: test_FR_0_6_02_refuses_to_overwrite_existing_rows
MC1b publish replaces instead of hard link | aqis_lab/results/store.py | rc=1 | 1 failed, 1656 deselected in 2.51s | failed: test_FR_0_6_02_existing_files_never_replaced
MC2 trace reads the first stored card, not the row's | aqis_lab/trace.py | rc=1 | 2 failed, 1655 deselected in 3.98s | failed: test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card, test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock
MC3 only the calling thread is pinned | aqis_lab/timing/cores.py | rc=1 | 2 failed, 1655 deselected in 3.19s | failed: test_FR_0_6_04_batch_run_kept_off_reserved_cores, test_FR_0_6_04_timing_process_pinned_to_reserved_cores
MC3b batch runs not pinned | aqis_lab/runner/run.py | rc=1 | 1 failed, 1656 deselected in 2.46s | failed: test_FR_0_6_04_batch_run_kept_off_reserved_cores
MC4 rclone sync instead of copy | aqis_lab/sync.py | rc=1 | 2 failed, 1655 deselected in 2.69s | failed: test_FR_0_6_05_command_is_copy_only, test_FR_0_6_05_never_deletes_remote_files
MC4b no --immutable | aqis_lab/sync.py | rc=1 | 2 failed, 1655 deselected in 2.70s | failed: test_FR_0_6_05_command_is_copy_only, test_FR_0_6_05_never_replaces_a_remote_file
MC5a architecture not checked | aqis_lab/deploy/oracle_setup.sh | rc=1 | 2 failed, 1655 deselected in 2.72s | failed: test_FR_0_6_01_refuses_unsupported_architecture
MC5b operating system not checked | aqis_lab/deploy/oracle_setup.sh | rc=1 | 1 failed, 1656 deselected in 2.83s | failed: test_FR_0_6_01_refuses_unsupported_operating_system
```

## Acceptance commands

### AT-0.6-01 — dry run explains each step; the fast suite passes, including results-store, trace and affinity tests
```text
$ bash aqis_lab/deploy/oracle_setup.sh --dry-run
oracle_setup.sh --dry-run: explaining each step; nothing will be changed
step 1/6 platform: PASS x86_64 (supported: x86_64 aarch64); Ubuntu 24.04.4 LTS (ubuntu:24.04; supported: ubuntu:24.04); glibc 2.39 (minimum 2.28)
step 2/6 tools: PASS git version 2.43.0 at /usr/bin/git; uv 0.8.17 at /root/.local/bin/uv
step 3/6 python: PASS Python 3.13 (docs/environment/colab_probe.txt); uv finds /home/user/voice-bot-vad-harness/.venv/bin/python3
step 4/6 wheels: would check that each of the 26 pins in requirements/aqis_lab/phase0.txt has a binary build for x86_64-manylinux_2_39 and Python 3.13 (uv pip compile --only-binary :all:); it stops naming every package without one
step 5/6 venv: would reuse .venv (Python 3.13) and sync requirements/aqis_lab/phase0.txt (sha256 5cb021306b9335293fb3f2d10de1cee54adf8763da4b51a75b8f5ee3bf5e6337) with hash checking (aqis_lab/deploy/dev_bootstrap.sh)
step 6/6 doctor: would run .venv/bin/python -m aqis_lab doctor --target oracle --work-dir <paths.work_dir> --out <paths.doctor_reports> (config/aqis_lab/oracle.yaml) and exit with its status
DRY RUN: nothing was changed
exit 0
```
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"
1633 passed, 24 deselected in 217.71s (0:03:37)
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "slow and not gpu and not colab and not oracle and not network"
3 passed, 1654 deselected in 9.94s
```
(Both at `6034fb0`. Baseline before WP-0.6 at `7a13e60`: `1524 passed, 18 deselected`.)

### AT-0.6-02 — audit gate with `--wp WP-0.6`
See "Audit gate" below.

## Audit gate
```text
$ git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6
aqis-audit-gate: base origin/main (merge-base 6ad251bd8beb), head 6034fb087135, approvals origin/main 6ad251bd8beb, wp WP-0.6
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.4 s)
```

## CI
| Run | Commit | Result |
| --- | --- | --- |
| 233 | `7dea4c8` FR-0.6-04 | success |
| 234 | `0a072cf` FR-0.6-02, FR-0.6-03 | success |
| 235 | `e0d263c` FR-0.6-05 (first run with the rclone step) | success |
| 236 | `8421bd6` FR-0.6-01 | failure: `test_FR_0_0_08_repository_registry_is_consistent`, `malformed registry row: duplicate capability ID CAP-ENV-004` (`1 failed, 1629 passed`); fixed in the next commit |
| 237 | `951d2e9` capability ID CAP-ENV-007 | success |
| 238 | `6034fb0` FR-0.6-06 | success |
| 239 | `920960c` evidence and second-run test | success: job `lab` (bootstrap, rclone step, fast suite, audit gate) and job `harness-regression` (provision, harness tests, regression check) |

## Findings and changes from the plan (for the auditor)
1. **Runner log line.** The plan said `session N cores: …`; the line is `cores: …`. An existing test (`test_FR_0_5_05_restart_skips_finished_shards`) finds the last `" session "` in `runner.log`, and I must not change existing tests; the new text keeps it passing (106 runner, doctor, platform and core tests passed after the change).
2. **No `--config` option on `oracle_setup.sh`.** The script always reads the repository's `config/aqis_lab/oracle.yaml`, like the doctor's `cores` check and `sync`'s default, so the three can never read different settings. Tests use their own throwaway tree with a generated `oracle.yaml`. (`sync` keeps `--config`.)
3. **pyarrow exit hang.** With pyarrow 25.0.1 on this VM, a process that read a Parquet file with threads (`pq.read_table(...)`) and then exited hung in native code (all threads in `futex_do_wait`, no Python frames) in **8 of 20** plain runs; `results add` with a conflict hung in 4 of 15 runs. With `use_threads=False`: **0 of 20** plain runs and **0 of 30** `results add` runs hung. All lab and test reads of Parquet in WP-0.6 are single-threaded; `test_FR_0_6_02_add_and_query_exit_promptly` runs ten adds and ten queries in subprocesses with a 60 s limit each. Parquet files are small, so there is no speed cost.
4. **Stale `.partial` files.** `results add` removes `.partial` files left by an interrupted add, but only while it holds the store lock, so no live add owns them (`test_FR_0_6_02_interrupted_add_leaves_no_row` found that they would otherwise stay forever).
5. **Doctor report names within one second (WP-0.5 behaviour, not changed).** `doctor_<platform>_<YYYYMMDDTHHMMSSZ>.json` has one-second resolution (FR-0.5-02) and a report is never replaced, so two doctor runs in the same second fail with `ERROR: refusing to replace …` and exit 2. Two `oracle_setup.sh` runs less than a second apart hit this (measured: 3 of 8 back-to-back pairs with a warm uv cache). `test_FR_0_6_01_second_run_changes_nothing` therefore starts its second run 1.1 s later; with that it passed 5 of 5. A real setup takes several seconds, so the owner does not meet this; it fails loudly if it ever happens. Recommendation: accept as is, or give report names sub-second resolution in a later WP (that would change the FR-0.5-02 file name format).
6. **Keyword name.** `run_doctor(..., oracle_config_path=None)` rather than `oracle_config`, so it does not shadow the `aqis_lab.oracle_config` module inside the function.
7. **Test remote name.** The sync tests name their rclone remote `aqisdrive`: rclone reads remotes from environment variables `RCLONE_CONFIG_<NAME>_TYPE`, which cannot hold the hyphen of `aqis-drive`. The committed `aqis-drive` is checked by `test_FR_0_6_05_drive_destination_is_fixed_by_spec`, the config tests and the runbook test.

## Owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| OC-0.6-01 | Oracle VM, clone at tag `aqis-lab-wp-0.6-oracle-1` (pushed after the audit passes) | 1. `bash aqis_lab/deploy/oracle_setup.sh --dry-run` 2. `bash aqis_lab/deploy/oracle_setup.sh` 3. `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle` | 1: six `step` lines, `DRY RUN: nothing was changed`, exit 0. 2: steps 1-5 PASS (step 1 names aarch64 and Ubuntu 24.04.4 LTS), then the doctor table with `platform`, `python`, `lock`, `disk`, `ram`, `cores` PASS (`timing on 2-3, batch on 0-1`) and `gpu` SKIP; `OK: the Oracle setup is complete and the doctor passed.`; exit 0. 3: `2 passed` (`test_FR_0_6_01_setup_passes_on_oracle`, `test_FR_0_6_04_real_oracle_pinning`; the only `oracle`-marked tests, per `pytest -m oracle --collect-only`), nothing failed | `docs/environment/doctor_oracle_<timestamp>.json`, `docs/progress/WP-0.6/OC-0.6-01_oracle.txt` |
| OC-0.6-02 | Oracle VM, after "Configure rclone for Google Drive" in the runbook | 1. `.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --out data/raw/aqis_lab/runs/oc-0.6-02 --seed 0` 2. `.venv/bin/python -m aqis_lab results add --run data/raw/aqis_lab/runs/oc-0.6-02` 3. `.venv/bin/python -m aqis_lab sync --dry-run` | 1: `cores: batch on 0-1 (timing reserved 2-3; …)` and `run complete`. 2: `stored 60 row(s) for run card …`. 3: `destination aqis-drive:AQIS_LAB/results`, `mode DRY RUN`, `Skipped copy as --dry-run is set` for `STORE.json`, the `run_card.json` and one `part-….parquet`, `DRY RUN: nothing was copied`, exit 0 | `docs/progress/WP-0.6/OC-0.6-02_sync_dry_run.txt` |

## audit-allow lines
None.

## Round 2 (audit round 1 findings)
Approval: `docs/approvals/WP-0.6.md` on `main` (`73d1198`). Details, change budget and outputs: `docs/progress/WP-0.6/FIXES.md`.

| Finding | Result | Tests |
| --- | --- | --- |
| F01 (CRITICAL) | Fixed with a test only. A stored run card names an earlier commit of this repository and that commit's lock hash (both unlike the checkout's); trace must print the card's values. Breaks MC2b and MC2c are now caught | `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash` |
| F02 (MAJOR) | Fixed with tests. X1, X2 and X3 are now caught | `test_FR_0_6_02_add_rejects_tampered_stored_rows`, `test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store` (row text changed, part file changed in place, truncated part file, card copy) |
| F03 | Fixed. `views.connect` checks every stored card (valid, in its own folder) and every part file (the checks `add` uses) before making the views, so `query` and `trace` give `ERROR:` and exit 1 on a damaged store | the same test; breaks X11 and X12 are caught |
| F04 | Accepted as DEBT-015 (target WP-0.7). Item (1), the truncated part file, is now an `ERROR:` with exit 1 (F03 fix) | the `truncated` case above |
| F05 | Fixed: step 6 reads its settings in the repository root | `test_FR_0_6_01_runs_from_any_directory` (slow, network) |
| F06 | Accepted as DEBT-016 (target WP-0.9) | — |
| F07 | (1)-(3) accepted as recorded deviations; (4) fixed | `test_FR_0_6_02_default_store_equals_oracle_results_store` |
| F08 | Accepted as DEBT-017 (target WP-0.7) | — |

Suites at `719d7f4`:
```text
fast (not slow, gpu, colab, oracle, network): 1640 passed, 25 deselected in 209.04s (0:03:29)
slow (not gpu, colab, oracle, network):       3 passed, 1662 deselected in 9.85s
WP-0.6 network (-k FR_0_6 -m "network and not oracle"): 5 passed, 1660 deselected in 6.65s
```
Gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6` gives `0 findings: OK (0.5 s)`. CI on `719d7f4`: push run 246 and pull-request run 247 `success`.
