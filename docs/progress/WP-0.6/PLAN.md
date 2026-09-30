# PLAN — WP-0.6 Oracle worker, results store and traceability

Spec: `docs/specs/phase-0/WP-0.6-oracle-worker-results.md`  ·  Planned by session: https://claude.ai/code/session_01Q6kwg6fLchZiuf9e84Zn2g  ·  Date: 2026-09-28
Branch: `claude/relaxed-davinci-iwk5gi`  ·  Base: `origin/main` at `7a13e60`  ·  Depends on: WP-0.5 (MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, the Oracle VM runs the lab the same way as the cloud VM and Colab, results are stored append-only, and any stored row can be traced back to what produced it.
- **Oracle setup.** `bash aqis_lab/deploy/oracle_setup.sh` checks the machine (architecture, operating system, C library), checks that every locked package has a build for it, builds `.venv` on the Colab Python from the hashed lock, and runs `doctor --target oracle`. `--dry-run` explains each step and changes nothing. A second run changes nothing but adds a new doctor report.
- **Results store.** `python -m aqis_lab results add` appends result rows as new Parquet files in one folder per `run_card_id`. It never replaces a file and refuses a row that would change an existing row. `python -m aqis_lab results query --run-card <id>` prints the rows. A DuckDB view `results` joins every row to its run card. `docs/results/RESULTS_STORE.md` documents the schema.
- **Trace.** `python -m aqis_lab trace <result-row-id>` prints the row's run card, pack manifest ID and version, clip, git commit and lock hash, after checking that the stored row and card are intact.
- **Core reservation.** On Oracle, timing runs are pinned to the reserved cores in `config/aqis_lab/oracle.yaml`, and batch runs (the WP-0.5 runner) are kept off them. Every thread of the process is pinned, not only the main one. Tests read each thread's CPU affinity to prove it.
- **Sync.** `python -m aqis_lab sync [--dry-run]` copies the results store one way to `AQIS_LAB/results` on Google Drive with `rclone copy --immutable`. It never deletes or replaces a remote file. A missing rclone remote gives a clear error that points to the runbook.
- **Runbook.** `docs/oracle/ORACLE_RUNBOOK.md` gives you exact steps: clone, setup, doctor, rclone configuration, a nightly sync schedule, and how to report results back.

## What I found in the repository and environment (read-only inspection)
1. **Spec sources.**
   - `docs/environment/oracle_probe.txt`, the first "Read first" file, **is missing**. The session-start hook reports the same. Without it I cannot fix the supported operating system, the reserved core numbers, or confirm the Oracle detection signal (question 1, blocker BLK-009).
   - The Build Plan section "Resource plan" is not in the repository (as in WP-0.5). I need its Oracle part, the VM shape and how many cores to reserve for timing (question 2).
   - `aqis-kit-patch-3/docs/specs/phase-0/WP-0.6-oracle-worker-results.md` is byte-identical to the spec (`diff -r` reports only the missing overview).
2. **Dependencies.** WP-0.5 is MERGED. No blocker was open before this plan.
3. **What WP-0.5 already gives this WP** (reused unchanged unless listed in the change budget):
   - `aqis_lab.platform` detects `oracle` from `/sys/class/dmi/id/chassis_asset_tag` = `OracleCloud.com`. This signal has never been checked on a real Oracle VM (WP-0.5 owner need 4).
   - `doctor --target oracle` already exists, with minimums 10 GB disk and 4 GB RAM (`config/aqis_lab/doctor.yaml`).
   - The runner writes run folders whose `results.jsonl` rows carry `run_card_id`, `clip_id`, `task` and `task_version`. Its docstring says "the results store (WP-0.6)" is out of its scope. Its run cards hold `pack` (manifest ID, version, SHA-256), `git.commit` and `lock.sha256`, exactly what trace must print.
   - The `score` command writes `scores.parquet` rows carrying `run_card_id`, `clip_id`, `variant`, normaliser and text hashes (`docs/contracts/SCORE_TABLE.md`).
   - `aqis_lab/deploy/dev_bootstrap.sh` builds `.venv` on the Colab probe's Python with uv and installs the lock with hash checking. `oracle_setup.sh` will call it, unchanged.
4. **Lock.**
   - DuckDB is not in `requirements/aqis_lab/phase0.txt`; FR-0.6-02 needs it.
   - `duckdb 1.5.6` (MIT licence, no dependencies) has CPython 3.13 wheels for `manylinux_2_28` on both x86_64 and aarch64. A trial compile in the scratchpad adds exactly one line to the lock: `duckdb==1.5.6`.
   - Its `parquet`, `json` and `icu` extensions are statically linked. With automatic extension installs switched off, a view over Parquet files and `json_extract` worked with no network and no `~/.duckdb` folder created.
   - All 25 current lock pins have CPython 3.13 wheels for `manylinux_2_28` on x86_64 and on aarch64. `numpy 2.5.3` has no `manylinux_2_17` aarch64 wheel. **So the Oracle VM needs glibc 2.28 or newer.**
5. **rclone** (measured in the scratchpad with a local stand-in remote):
   - This VM has rclone **1.60.1**, the Ubuntu 24.04 package.
   - `rclone copy --immutable --checksum` left a remote-only file untouched. It refused to replace a remote file with different content (`ERROR : a/f2: Source and destination exist but do not match: immutable file modified`, exit 6), including a same-size, same-time file with different bytes.
   - `--dry-run` created nothing.
   - A remote that is not configured fails with `didn't find section in config file`, exit 1.
   - `downloads.rclone.org` is **blocked** from this VM (HTTP 403 from the proxy).
6. **CPU affinity** (this VM):
   - 4 CPUs, 1 thread per core, allowed CPUs `0-3`, online `0-3`, no `isolcpus`, no DMI asset tag file.
   - **`os.sched_setaffinity(0, …)` pins only the calling thread.** After `import numpy`, three OpenBLAS threads kept CPUs `0-3` while the main thread moved to `3`. Pinning each thread in `/proc/self/task` fixed all four, and a child process inherited the pin. So the lab must pin every thread of the process.
7. **uv.** `uv 0.8.17` is on this VM. CI installs it with `astral-sh/setup-uv`, Colab with `pip install uv==0.8.17`. PyPI has uv 0.8.17 wheels for x86_64 (`manylinux_2_17`) and aarch64 (`manylinux_2_28`).
8. **Must-catch 5 of WP-0.5.** A scan in `tests/aqis_lab/test_aqis_platform.py` forbids the string `/proc/` and other machine-fact reads outside `aqis_lab/platform.py`. The new CPU and thread facts therefore go into `aqis_lab/platform.py` (change budget below). The scan and its allow-list stay unchanged.
9. **Accepted debt that targets WP-0.6.** DEBT-008: `score --out` into a folder that cannot be created ends with a traceback and exit 1, not `ERROR:` and exit 2 (`write_outputs` in `aqis_lab/commands/score.py`). The spec does not mention it (question 15).
10. **Existing harness on Arm.** The pinned TEN VAD ships no Arm library (WP-0.0, finding F16), so harness provisioning refuses aarch64. That matters to WP-0.7 if it wraps TEN VAD and Oracle is Arm, not to WP-0.6. The lab lock itself has Arm wheels (finding 4).
11. **Repository fit.** `/data/raw/` is git-ignored, so the default store, doctor and work folders under `data/raw/aqis_lab/` never dirty the tree. `config/aqis_lab/`, `requirements/aqis_lab/`, `tests/aqis_lab/` and `.github/workflows/aqis-lab-*.yml` are lab-owned. No GUARDED or NEVER path needs to change, so no `ALLOW-EDIT` is needed.
12. **Baseline.** Fast suite at `7a13e60` on this VM: `1524 passed, 18 deselected in 155.17s`.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.6-01 | Six steps, each printed as `step N/6 <name>: PASS/FAIL <detail>` (under `--dry-run`: `would …`): <br>1. `platform`: architecture, operating system and glibc against the `setup` pin in `oracle.yaml`. <br>2. `tools`: git and uv 0.8.17. <br>3. `python`: the Colab probe's major.minor, and which interpreter uv will use. <br>4. `wheels`: every applicable lock pin has a binary build for this architecture, glibc and Python. <br>5. `venv`: `aqis_lab/deploy/dev_bootstrap.sh`, unchanged. <br>6. `doctor`: `python -m aqis_lab doctor --target oracle` with the work and report folders from `oracle.yaml`. <br>Details under "Oracle setup" | `aqis_lab/deploy/oracle_setup.sh`, `aqis_lab/oracle_config.py` (loads and validates `oracle.yaml`), `config/aqis_lab/oracle.yaml` | none | `test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing`, `test_FR_0_6_01_refuses_unsupported_architecture` (must-catch 5; `setarch linux32` makes the kernel report i686, as in WP-0.0), `test_FR_0_6_01_refuses_unsupported_operating_system` (must-catch 5), `test_FR_0_6_01_refuses_glibc_below_minimum`, `test_FR_0_6_01_supports_x86_64_and_aarch64`, `test_FR_0_6_01_setup_pin_read_by_script_equals_yaml`, `test_FR_0_6_01_missing_build_names_the_package`, `test_FR_0_6_01_fails_when_uv_missing_or_other_version`, `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` (`network`), `test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor` (`slow`), `test_FR_0_6_01_second_run_changes_nothing` (`slow`), `test_FR_0_6_01_setup_passes_on_oracle` (`oracle`) | AT-0.6-01 (dry run) |
| FR-0.6-02 | `results add --run DIR` or `--scores DIR [--run-card FILE]` validates the source, computes each row's `result_row_id` from its identity fields, and appends one Parquet file per add under `<store>/run_card_id=<id>/`. Files are published by hard link, so an existing file can never be replaced. The run card is written once. Rows already stored with identical content are reported and not stored again; a row whose identity exists with other content stops the whole add, and nothing is written. `results query --run-card <id>` reads the DuckDB view and prints canonical JSON lines. Details under "Results store" | `aqis_lab/results/__init__.py`, `store.py`, `ingest.py`, `views.py`, `aqis_lab/commands/results.py`, `docs/results/RESULTS_STORE.md` | `requirements/aqis_lab/phase0.in` (add `duckdb` with a comment), `requirements/aqis_lab/phase0.txt` (regenerated with its recorded command; only `duckdb==1.5.6` is added); `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_6_02_add_run_folder_writes_partition_by_run_card`, `test_FR_0_6_02_add_score_folder_rows`, `test_FR_0_6_02_refuses_to_overwrite_existing_rows` (must-catch 1), `test_FR_0_6_02_existing_files_never_replaced` (must-catch 1), `test_FR_0_6_02_identical_rows_not_stored_twice`, `test_FR_0_6_02_row_id_computed_from_identity` (expected IDs computed in the test from the documented definition), `test_FR_0_6_02_rejects_incomplete_run_folder`, `test_FR_0_6_02_rejects_rows_of_another_run_card`, `test_FR_0_6_02_score_rows_need_their_run_card`, `test_FR_0_6_02_interrupted_add_leaves_no_row`, `test_FR_0_6_02_query_returns_rows_for_run_card`, `test_FR_0_6_02_query_unknown_run_card_exit_1`, `test_FR_0_6_02_query_rejects_malformed_id`, `test_FR_0_6_02_duckdb_view_equals_stored_files`, `test_FR_0_6_02_schema_documented_equals_code`, `test_FR_0_6_02_duckdb_needs_no_network`, `test_FR_0_6_02_store_on_drive_refused` (Drive test double) | `.venv/bin/python -m aqis_lab results query --run-card <id> --store <tmp store>` after a real smoke run and `results add` |
| FR-0.6-03 | `trace <result-row-id>` finds the row through the `results` view. It checks: exactly one row has the ID; the ID recomputes from the row's identity; the row's SHA-256 matches; the stored card validates (`validate_run_card`) and its ID equals the folder and the row. It then prints the fields and the full run card. Any failed check is an `ERROR:` and exit 1, never a partial answer. Output under "Trace" | `aqis_lab/trace.py`, `aqis_lab/commands/trace.py` | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock` (must-catch 2; every row of a real run and of a real score table, expected values read in the test from the source `run_card.json`, `results.jsonl` and `scores.parquet`), `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card` (must-catch 2), `test_FR_0_6_03_unknown_row_id_exit_1`, `test_FR_0_6_03_malformed_row_id_exit_2`, `test_FR_0_6_03_changed_run_card_is_reported`, `test_FR_0_6_03_row_not_matching_its_id_is_reported` | `.venv/bin/python -m aqis_lab trace <row id> --store <tmp store>` |
| FR-0.6-04 | `aqis_lab/timing/cores.py` maps every run-card mode to `timing` or `batch` (question 8). On the `oracle` platform it builds the core plan from `oracle.yaml`: reserved cores for timing, the other online cores for batch. It refuses a plan that leaves no batch core, names a core that is not online, or splits a physical core (question 10). `pin_for_mode(mode)` pins **every thread** of the process, reads each one back, and raises if any differs. On other platforms it pins nothing and says so. The runner pins itself to the batch cores before staging and logs the result. `doctor --target oracle` gains a `cores` row (question 11). Details under "Core reservation" | `aqis_lab/timing/__init__.py`, `aqis_lab/timing/cores.py` | `aqis_lab/platform.py`: new functions `online_cpus`, `core_siblings`, `thread_ids`, `thread_affinity` only, plus header lines; `aqis_lab/runner/run.py`: `RunOptions` (one new field `cores_config`), `run` (pin before staging, one log line); `aqis_lab/doctor.py`: `run_doctor` (call the new check for target `oracle`), new `_check_cores`; `docs/runner/RUNNER.md`, `docs/doctor/DOCTOR.md` | `test_FR_0_6_04_timing_process_pinned_to_reserved_cores` (must-catch 3; a real subprocess on an Oracle cores test double; the test reads `Cpus_allowed_list` of every thread in `/proc/<pid>/task/*/status`, numpy's threads included), `test_FR_0_6_04_batch_run_kept_off_reserved_cores` (must-catch 3; a real runner, held on a named-pipe clip as in FR-0.5-06, affinity read from outside while it runs), `test_FR_0_6_04_every_mode_is_timing_or_batch`, `test_FR_0_6_04_reservation_must_leave_a_batch_core`, `test_FR_0_6_04_reserved_core_must_be_online`, `test_FR_0_6_04_reservation_must_not_split_a_physical_core`, `test_FR_0_6_04_no_pinning_off_oracle`, `test_FR_0_6_04_pin_failure_is_an_error`, `test_FR_0_6_04_doctor_oracle_cores_row`, `test_FR_0_6_04_real_oracle_pinning` (`oracle`) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_6_04` |
| FR-0.6-05 | `sync [--dry-run] [--config FILE]`: <br>1. Load `oracle.yaml` (remote name, store path). <br>2. Find rclone (minimum 1.60.1) and check the remote is listed by `rclone listremotes`. <br>3. Check `AQIS_LAB/results/` exists on the remote; the lab never creates `AQIS_LAB`. <br>4. Run `rclone copy <store> <remote>:AQIS_LAB/results --immutable --checksum --no-update-modtime --exclude "*.partial" --exclude ".lock"` (plus `--dry-run`). <br>The command is built only from constants and is always `copy`. Missing rclone or remote: `ERROR:` naming the runbook section, exit 2. A refused replacement: `ERROR:` naming each file, exit 1 | `aqis_lab/sync.py`, `aqis_lab/commands/sync.py` | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG; `.github/workflows/aqis-lab-ci.yml`: job `lab`, one new step before the fast suite that installs rclone from the Ubuntu archive (question 5) | `test_FR_0_6_05_copies_store_to_aqis_lab_results` (real rclone; the remote is an rclone `alias` of a local folder, the Drive test double), `test_FR_0_6_05_never_deletes_remote_files` (must-catch 4), `test_FR_0_6_05_never_replaces_a_remote_file` (must-catch 4), `test_FR_0_6_05_dry_run_changes_nothing`, `test_FR_0_6_05_command_is_copy_only` (must-catch 4; the built command and a scan of `aqis_lab/sync.py` for delete-capable rclone commands and flags), `test_FR_0_6_05_missing_remote_points_to_runbook`, `test_FR_0_6_05_missing_rclone_points_to_runbook`, `test_FR_0_6_05_refuses_when_remote_results_folder_missing`, `test_FR_0_6_05_partial_files_not_copied` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_6_05` |
| FR-0.6-06 | Runbook sections in this order: before you start; clone (question 14); install uv and rclone; setup (`--dry-run`, then for real); doctor; core reservation; configure rclone for Google Drive (headless `rclone authorize "drive"`); first sync; nightly sync schedule (a `crontab` line with `flock`, so two syncs never overlap); reporting results back; when something fails; updating to a new tag | `docs/oracle/ORACLE_RUNBOOK.md` | none | `test_FR_0_6_06_runbook_has_each_required_step`, `test_FR_0_6_06_runbook_commands_exist_and_parse` (every `python -m aqis_lab …` line parses with the real parsers; every script path exists; the cron line has 5 time fields), `test_FR_0_6_06_runbook_matches_config` (remote name, paths and reserved cores equal `oracle.yaml`) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_6_06` |
| AT-0.6-01 | Run as written on this VM | — | — | all fast tests above | `bash aqis_lab/deploy/oracle_setup.sh --dry-run` (exit 0; six `step` lines; `DRY RUN: nothing was changed`), then `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` (exit 0, including the results-store, trace and affinity tests) |
| AT-0.6-02 | Run as written after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6` (exit 0, `0 findings`) |
| OC-0.6-01 | Owner, on Oracle: see "Owner-run checks planned" | — | — | `oracle`-marked tests | `bash aqis_lab/deploy/oracle_setup.sh`, then `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle` |
| OC-0.6-02 | Owner, on Oracle: see "Owner-run checks planned" | — | — | — | `.venv/bin/python -m aqis_lab sync --dry-run` |

**Change budget for existing files** (nothing else that already exists is touched):
- `aqis_lab/__main__.py`: three new `COMMANDS` entries (`results`, `trace`, `sync`) and one CHANGE LOG line each. `build_parser` and `main` stay byte-identical, so CAP-CLI-001 is unchanged.
- `aqis_lab/platform.py`: add `online_cpus`, `core_siblings`, `thread_ids` and `thread_affinity`, a CAP-PLAT-004 header line and a CHANGE LOG line. Every existing function and constant stays byte-identical.
- `aqis_lab/runner/run.py`: `RunOptions` gains `cores_config` (default: the repository's `config/aqis_lab/oracle.yaml`). `run` pins the process to the batch cores before staging and writes one `session N cores: …` log line. Header CAP-RUN-007 text and CHANGE LOG. `aqis_lab/commands/run.py` is not changed.
- `aqis_lab/doctor.py`: `run_doctor` appends the `cores` check for target `oracle`; new function `_check_cores`; header CAP-DOCTOR-001 text and CHANGE LOG.
- `aqis_lab/commands/score.py`: `write_outputs` only (move `out.mkdir` inside its `try`), CHANGE LOG, **only if question 15 is accepted**.
- `requirements/aqis_lab/phase0.in` and `phase0.txt`: add `duckdb`, regenerated with the recorded command (`uv pip compile … --universal --python-version 3.13 --generate-hashes`).
- `.github/workflows/aqis-lab-ci.yml`: one step in job `lab` (question 5). Job `harness-regression` is untouched.
- `docs/runner/RUNNER.md` (the `cores` log line and the Oracle rule), `docs/doctor/DOCTOR.md` (the `cores` row).
- `docs/capabilities/REGISTRY.md`: append new rows; update the text of CAP-ENV-002 (lock contents), CAP-DOCTOR-001 and CAP-RUN-007 because their behaviour grows. No row is removed.
- `docs/progress/STATUS.md` (WP-0.6 row), `docs/progress/DEBT.md` (DEBT-008 Status column, if question 15 is accepted; rows only for findings you accept as debt), `docs/progress/BLOCKERS.md` (append only).
- Not touched: `aqis_lab/deploy/dev_bootstrap.sh`, `aqis_lab/drive.py`, every existing test file, every GUARDED or NEVER path.

**New test files** (the `test_aqis_` prefix keeps basenames unique, FR-0.0-04): `tests/aqis_lab/test_aqis_oracle_setup.py`, `test_aqis_oracle_config.py`, `test_aqis_results_store.py`, `test_aqis_results_cli.py`, `test_aqis_trace.py`, `test_aqis_timing_cores.py`, `test_aqis_sync.py`, `test_aqis_oracle_runbook.py`, `test_aqis_oracle_live.py` (`oracle` marker only; runs on Oracle, never in the fast suite), `test_aqis_debt_wp06.py` (if question 15 is accepted), and the helper `tests/aqis_lab/aqis_results_testutil.py`. The helper builds stores from real runner and scorer output, Oracle core test doubles (a generated system tree with the `OracleCloud.com` tag and CPU topology files) and rclone `alias` remotes on local folders. It computes expected values independently of the code under test.

## Design details

### Oracle settings (`config/aqis_lab/oracle.yaml`, loaded by `aqis_lab/oracle_config.py`)
```yaml
schema_version: "1.0"
setup:                    # read by oracle_setup.sh before any Python exists: keep each value on one line
  architectures: "x86_64 aarch64"
  operating_systems: "ubuntu:24.04 <Oracle's ID:VERSION_ID from the probe>"   # question 3
  min_glibc: "2.28"       # the lock's wheels need manylinux_2_28 (finding 4)
paths:                    # relative paths are resolved from the repository root
  work_dir: data/raw/aqis_lab/work
  doctor_reports: data/raw/aqis_lab/doctor
  results_store: data/raw/aqis_lab/results
  logs: data/raw/aqis_lab/logs
cores:
  reserved_for_timing: [<from question 2>]
rclone:
  remote: aqis-drive
```
- The loader rejects unknown keys, missing keys, wrong types, duplicate or negative core numbers, and an empty reservation, naming the key.
- The Drive destination is fixed in code as `AQIS_LAB/results`, as the spec says. It is not a setting.
- The three `setup` values are plain one-line strings, so the shell script can read them before Python exists. A test proves that the script's reading equals the YAML reading. The script refuses the file if a key is missing, repeated or not in that form.
- `results`, `trace` and `sync` default to the same store folder, `data/raw/aqis_lab/results`. A test keeps `paths.results_store` equal to that default. The runbook says to pass `--store` if you ever change it.

### Oracle setup (`aqis_lab/deploy/oracle_setup.sh`)
- **Usage.** `bash aqis_lab/deploy/oracle_setup.sh [--dry-run] [--config FILE]`. The repository root comes from the script's location, as in `dev_bootstrap.sh`. No absolute paths.
- **Step 1, `platform`.** `uname -m` must be in `setup.architectures`. `ID:VERSION_ID` from `/etc/os-release` must be in `setup.operating_systems`. `getconf GNU_LIBC_VERSION` must be at least `setup.min_glibc`.
  - Failure: `ERROR: unsupported architecture i686: oracle_setup.sh supports x86_64 and aarch64 (config/aqis_lab/oracle.yaml, setup.architectures)`, or the same form for the operating system or glibc, then exit 1. Nothing else runs and nothing is written (must-catch 5).
- **Step 2, `tools`.** git on PATH; uv on PATH reporting `uv 0.8.17` (question 4). Otherwise `ERROR:` with the runbook's install command.
- **Step 3, `python`.** The major.minor from `docs/environment/colab_probe.txt`, parsed by the same rule as `dev_bootstrap.sh`. It reports `uv python find <X.Y>` if an interpreter exists; otherwise uv 0.8.17 downloads its checksum-verified managed build during step 5.
- **Step 4, `wheels`.** A binary build must exist for every applicable lock pin.
  - Check: `uv pip compile --no-deps --only-binary :all: --python-platform <arch>-manylinux_<glibc> --python-version <X.Y>` over the lock's pins. This form was measured in finding 4.
  - On failure, each pin is checked alone, and every failing package is named: `ERROR: no build of numpy 2.5.3 for aarch64 (glibc 2.27, Python 3.13) in requirements/aqis_lab/phase0.txt: <uv's reason>`, then exit 1. Nothing is installed.
  - Source builds are never used on Oracle: they would bring unpinned build tools and compiler differences.
- **Step 5, `venv`.** `bash aqis_lab/deploy/dev_bootstrap.sh`: reuse or create `.venv`, then `uv pip sync --require-hashes --strict`.
- **Step 6, `doctor`.** `.venv/bin/python -m aqis_lab doctor --target oracle --work-dir <paths.work_dir> --out <paths.doctor_reports>`. The paths are read with `.venv/bin/python -m aqis_lab.oracle_config get <key>`. The script's exit status is the doctor's.
- **`--dry-run`.** Steps 1 to 3 run their read-only checks. Steps 4 to 6 print exactly what they would do, with the current state (for example, `.venv exists with Python 3.13: would reuse it and sync …`). No command that writes anything runs, and the last line is `DRY RUN: nothing was changed`.
- **Idempotent** means: a second run downloads nothing, keeps `.venv` (same interpreter, same inode and mtime), installs nothing, and writes one new doctor report. The doctor never replaces a report (CAP-DOCTOR-002).
- **Tests on this VM.**
  - Tests run the script in a throwaway copy of the needed repository files, with `AQIS_CACHE` and uv's cache in the test's temporary folder.
  - A full run here ends with the doctor failing only its `platform` row: `cloud-vm` is not `oracle`. The test asserts exactly that, plus the venv and lock. The `oracle` test proves the full PASS on the real VM.
  - The missing-build test uses uv's own `UV_NO_INDEX` and `UV_FIND_LINKS` settings with wheels the test builds, one of them tagged only for Windows. No network is used and no production code changes for the test.

### Results store (`aqis_lab/results/`, `docs/results/RESULTS_STORE.md`)
- **Layout.**
  ```text
  <store>/STORE.json                         store schema version, written once
  <store>/.lock                              held (fcntl.flock) during each add, so two adds never interleave
  <store>/run_card_id=<64 hex>/run_card.json the run card, written once
  <store>/run_card_id=<64 hex>/part-<SHA-256 of the file>.parquet   one file per add, never replaced
  ```
- **Publishing a file.** Write `<name>.partial`, fsync it, `os.link` it to the final name, fsync the folder, then remove the `.partial`. `os.link` fails when the name exists, so no code path can replace a stored file (must-catch 1). An interrupted add leaves only a `.partial`, which readers and sync ignore and the next add replaces.
- **Store location.** The store must be on local disk: hard links are needed, and Google Drive's FUSE mount has none. A store folder on a Drive mount is refused with a clear error (question 7).
- **Row kinds** (question 6):

  | Kind | Source | Identity fields (`result_row_id` = SHA-256 of their canonical JSON) |
  | --- | --- | --- |
  | `run-result` | `results.jsonl` of a finished run folder | `kind`, `run_card_id`, `clip_id`, `task`, `task_version` |
  | `score` | `scores.parquet` of a `score` output folder | `kind`, `run_card_id`, `clip_id`, `variant`, `normaliser_name`, `normaliser_version`, `ref_sha256` |

  So a corrected reference text gives a new score row, while a different hypothesis for the same run card, clip, variant and reference is a conflict.
- **Columns of each part file** (Parquet; key-value metadata `aqis_results_store_schema_version` = `1.0`): `result_row_id`, `kind`, `run_card_id`, `clip_id`, `identity` (canonical JSON), `row` (the source row as canonical JSON, nothing dropped), `row_sha256`, `source_file`, `source_sha256`, `added_utc`, `added_by` (the `version` command's line). A test keeps this list identical to the document.
- **`results add --run DIR`** accepts only a finished run:
  - `run_card.json` validates;
  - `shard_plan.json` names the same card;
  - `results.jsonl` exists, and every line is a JSON object with this card's `run_card_id`;
  - the clip IDs equal the plan's clip IDs exactly, with none missing, none extra and none repeated.
- **`results add --scores DIR [--run-card FILE]`**:
  - `summary.json`'s file hashes match `scores.parquet` and `scores.csv`;
  - every row has one `run_card_id`;
  - that run card must already be in the store, or be given with `--run-card` (validated, same ID, then stored).
- **Adding rows again** (question 7): identical rows are reported as `already stored` and not written. A row whose identity exists with different content stops the whole add: `ERROR:` listing each conflicting row ID, exit 1, nothing written.
- **Exit codes.** `add`: 0 stored (or everything already stored), 1 conflict or integrity problem, 2 usage or input error. `query`: 0 rows printed, 1 no such run card, 2 usage (including a malformed ID or a missing store).
- **DuckDB** (`views.connect(store)`). One in-memory connection with automatic extension installs switched off, and three views:
  - `result_rows` over every part file;
  - `run_cards` over every `run_card.json`, read as text and parsed with `json_extract`, because `model.settings` is an open object;
  - **`results`**: `result_rows` joined to `run_cards`, adding `pack_manifest_id`, `pack_version`, `pack_sha256`, `git_commit`, `git_dirty`, `lock_file`, `lock_sha256` and `mode`.

  The document shows the view SQL and how to open it from Python. `results query` and `trace` both read through `results`, so the view is exercised on every call.
- **`results query --run-card <id> [--store DIR]`** prints one canonical JSON object per row, with `row` expanded, sorted by kind, clip ID, then row ID.

### Trace (`aqis_lab/trace.py`)
```text
result_row_id: <64 hex>
kind: run-result
clip_id: ls-test-clean-0001
run_card_id: <64 hex>
pack_manifest_id: smoke
pack_version: 1.0.0
pack_sha256: <64 hex>
git_commit: <40 hex> (dirty: false)
lock_file: requirements/aqis_lab/phase0.txt
lock_sha256: <64 hex>
run_card:
{ …the stored card, pretty-printed JSON… }
```
Before printing, trace checks the row and card as described in the requirements table. Exit codes: 0 printed, 1 not found or integrity problem, 2 malformed ID or missing store.

### Core reservation (`aqis_lab/timing/cores.py`)
- **Modes** (question 8). `batch` gets the batch cores. `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay` and `human_session` get the reserved cores. A test takes the mode list from `run_card.v1.json` and requires each mode in exactly one group, so a new mode cannot slip through.
- **Plan** (`oracle` platform only; question 9).
  - Reserved = `cores.reserved_for_timing`.
  - Batch = online CPUs minus reserved.
  - Refused, with an error naming the cores:
    - a reserved core that is not online;
    - an empty batch set;
    - a reservation that contains one thread of a physical core but not its siblings (question 10). Siblings come from `thread_siblings_list`.
- **Pinning.** `pin_for_mode(mode)` lists every thread of the process (`aqis_lab.platform.thread_ids`) and sets each thread's affinity. It repeats the listing until no new thread has appeared, then reads every thread back. Any difference, or a kernel refusal, raises `CoreError`. Child processes inherit the pin. It returns what it did, for the log.
- **Off Oracle.** Nothing is pinned, and the result says `no reservation (platform cloud-vm)`.
- **Runner.** At the start of `run()` (before staging, which extracts archives), the runner pins itself to the batch cores and logs `session N cores: batch on 0-1 (timing reserved 2-3, config/aqis_lab/oracle.yaml)`. Off Oracle it logs `session N cores: no reservation (platform cloud-vm)`. A `CoreError` stops the run with exit 2 before anything is computed. Timing runs arrive with WP-0.7's real-speed feeder, which calls the same function.
- **Doctor `cores` row** (target `oracle`; question 11). PASS shows the plan. FAIL gives the reason. Every other check still runs.
- **Tests on this VM.** Oracle cores are one of the external services the rules allow a test double for. The double is a generated system tree with the Oracle tag and CPU topology files, over this VM's real CPUs; GitHub's runner for a private repository may have only 2 CPUs, so the tests reserve the highest online CPU and need at least 2. The pinning itself is real. The test reads each thread's `Cpus_allowed_list` of the running process from outside.

### Sync (`aqis_lab/sync.py`)
- Only `rclone copy` is ever run. `sync`, `move`, `delete`, `purge`, `rmdir`, `rmdirs`, `dedupe`, `cleanup` and every `--delete-*` or `--backup-dir` flag are absent. A test checks the built command and scans the module.
- `--immutable` makes rclone refuse to replace a remote file that differs. `--checksum` compares content (Drive keeps MD5 hashes), not size and time. `--no-update-modtime` leaves remote file times alone. `.partial` and `.lock` files are excluded.
- Output: the source, the destination, the rclone version and the mode (`DRY RUN` or `COPY`), then rclone's own lines (`-v`), then a summary line.
- The runbook's cron line wraps the command in `flock -n`, so two nightly syncs never overlap. Store files are published by hard link, so a sync that runs during an add sees each file whole or not at all.

### Must-catch proof (planned)
| # | Behaviour | Tests that must fail when it is broken |
| --- | --- | --- |
| 1 | The results store refuses to overwrite existing rows | `test_FR_0_6_02_refuses_to_overwrite_existing_rows`, `test_FR_0_6_02_existing_files_never_replaced` |
| 2 | `trace` returns the exact run card, manifest version, clip, commit and lock hash | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock`, `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card` |
| 3 | Timing runs are pinned to the reserved cores | `test_FR_0_6_04_timing_process_pinned_to_reserved_cores`, `test_FR_0_6_04_batch_run_kept_off_reserved_cores` (a break that pins only the main thread fails both) |
| 4 | `sync` never deletes remote files | `test_FR_0_6_05_never_deletes_remote_files`, `test_FR_0_6_05_never_replaces_a_remote_file`, `test_FR_0_6_05_command_is_copy_only` |
| 5 | Setup stops with a clear message on an unsupported architecture or operating system | `test_FR_0_6_01_refuses_unsupported_architecture`, `test_FR_0_6_01_refuses_unsupported_operating_system` |

### Parts that do not depend on owner inputs
- **Build first:**
  - the results store, `results`, `trace` and the DuckDB view;
  - sync and its tests;
  - the core logic and its tests with generated settings;
  - the setup script's steps and tests with generated settings;
  - the runbook text that does not depend on Oracle facts;
  - DEBT-008 (if accepted).
- **Wait for the Oracle probe and your core figure (questions 1 and 2):** the committed values in `oracle.yaml` (operating systems, reserved cores), the runbook's install commands for Oracle's operating system, and the doctor `cores` minimum check against the real shape.

If an answer is still missing when I reach a part that needs it, I stop only that part.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | **`docs/environment/oracle_probe.txt`**: run the probe below on the Oracle VM and commit its output on `main` (blocker BLK-009) | The spec's "Read first" file. It fixes the supported operating system, glibc, the CPU layout for the reservation, whether uv, rclone and git exist, whether Jitsi runs on the same VM, and it confirms the `oracle` detection signal | Before `/wp-build WP-0.6` for the Oracle values; the rest of the build can start without it |
| 2 | **Reserved cores for timing**: the Build Plan's "Resource plan" figure (VM shape and how many cores to reserve), or your decision (question 2) | FR-0.6-04; I must not invent it | Before the committed `oracle.yaml` |
| 3 | Answers to questions 3 to 16 as CONDITIONS in `docs/approvals/WP-0.6.md` (or "as recommended") | They fix the operating-system rule, installs, store behaviour, core rules and procedures | Before `/wp-build WP-0.6` |
| 4 | SSH access to the Oracle VM, a read-only deploy key or token for this repository there (question 14), and Google Drive access for rclone | Clone and sync on Oracle | Before OC-0.6-01 |
| 5 | The two Oracle owner-run checks below, after the audit passes | OC-0.6-01, OC-0.6-02 | Before merging |

No cloud allowlist change is needed if you accept question 5 (a): PyPI and the Ubuntu archive are already reachable. Option (b) of question 5 needs `downloads.rclone.org`, which is blocked here today.

### Oracle probe (owner need 1)
On the Oracle VM, as the user that will run the lab, from your home folder:
```bash
{
echo "=== ORACLE PROBE ==="
uname -m; cat /etc/os-release | head -4; python3 --version; nproc; free -g | head -2; df -h / | tail -1; lscpu | grep "Model name"
echo "--- extra lines for WP-0.6 ---"
cat /sys/class/dmi/id/chassis_asset_tag
getconf GNU_LIBC_VERSION
grep -E "^(ID|VERSION_ID)=" /etc/os-release
lscpu | grep -E "^(Architecture|CPU\(s\)|On-line CPU|Thread\(s\) per core|Core\(s\) per|Socket|Vendor ID)"
lscpu -e=CPU,CORE,SOCKET,ONLINE
grep Cpus_allowed_list /proc/self/status
cat /sys/fs/cgroup/cpuset.cpus.effective 2>/dev/null || echo "no cgroup v2 cpuset file"
tr ' ' '\n' < /proc/cmdline | grep -E "isolcpus|nohz_full" || echo "no isolcpus"
for t in git curl uv rclone python3.13 flock crontab; do printf '%s: ' "$t"; command -v "$t" || echo "not found"; done
rclone version 2>/dev/null | head -1 || true
df -h "$HOME" | tail -1
systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}' | grep -i -E "jitsi|jicofo|jvb|prosody|nginx|coturn" || echo "no Jitsi services found"
sudo -n true 2>/dev/null && echo "sudo without password: yes" || echo "sudo without password: no"
curl -sS -o /dev/null -w "pypi.org %{http_code}\n" https://pypi.org/simple/
curl -sS -o /dev/null -w "github.com %{http_code}\n" https://github.com/
} 2>&1 | tee oracle_probe.txt
```
It prints no secrets. Commit `oracle_probe.txt` to `docs/environment/` on `main` (GitHub: **Add file → Upload files**). The first line group is the command in `docs/environment/README.md`; the rest is what WP-0.6 needs.

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| OC-0.6-01 | Oracle VM, in the clone at the tag from question 14 | 1. `bash aqis_lab/deploy/oracle_setup.sh --dry-run`. <br>2. `bash aqis_lab/deploy/oracle_setup.sh`. <br>3. `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle` (addition D7) | 1: six `step` lines and `DRY RUN: nothing was changed`, exit 0. <br>2: steps 1 to 5 PASS, then the doctor table with `platform`, `python`, `lock`, `disk`, `ram` and `cores` PASS and `gpu` SKIP; exit 0; it prints the JSON path. <br>3: ends with `passed`, nothing failed. <br>Commit `data/raw/aqis_lab/doctor/doctor_oracle_<timestamp>.json` to `docs/environment/`, and the output of all three as `docs/progress/WP-0.6/OC-0.6-01_oracle.txt` |
| OC-0.6-02 | Oracle VM, after "Configure rclone" in the runbook | 1. `.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --out data/raw/aqis_lab/runs/oc-0.6-02 --seed 0`. <br>2. `.venv/bin/python -m aqis_lab results add --run data/raw/aqis_lab/runs/oc-0.6-02`. <br>3. `.venv/bin/python -m aqis_lab sync --dry-run` (steps 1 and 2 are addition D8: they give the dry run something to list) | 1: `run complete`, and `runner.log` has `cores: batch on <batch cores>`. <br>2: `stored 60 rows` for one run card. <br>3: remote `aqis-drive:` found, `AQIS_LAB/results/` found, `DRY RUN`, two files listed as would-be copies (`run_card.json` and one `part-….parquet`), nothing deleted, exit 0. <br>Commit the output of all three as `docs/progress/WP-0.6/OC-0.6-02_sync_dry_run.txt` |

## Risks and questions
### Questions for you
1. **(Blocker BLK-009) Oracle probe.** Please run the probe above and commit it (owner need 1). Everything Oracle-specific in this plan is written to be filled from it. If it shows something this plan did not expect, I will list the change for you before building it. For example: an operating system without `apt`, no `OracleCloud.com` tag, glibc below 2.28, or cores that cannot be reserved.
2. **(FR-0.6-04) How many cores to reserve for timing, and which.**
   - **(a) Needed from you:** the Build Plan's "Resource plan" figure for the Oracle VM (shape, and cores reserved for timing), pasted into the approval CONDITIONS.
   - **(b)** If the Build Plan gives no figure, your own choice. My suggestion, for you to accept or change: reserve the highest-numbered half of the physical cores (at least one), whole physical cores only.

   I will not choose a number myself.
3. **(FR-0.6-01) What counts as a supported operating system.**
   - **(a) Recommended:** an explicit list in `oracle.yaml`, holding this cloud VM's `ubuntu:24.04` (needed for AT-0.6-01) and the Oracle probe's `ID:VERSION_ID`. Also require glibc 2.28 or newer, because the lock's wheels need it (finding 4). Anything else stops at step 1.
   - **(b)** glibc 2.28 or newer on any Linux distribution, without a list.
4. **(FR-0.6-01) uv on Oracle.**
   - **(a) Recommended:** the runbook installs uv 0.8.17 (one command). The setup script checks that `uv --version` says 0.8.17 and otherwise stops with that command. This matches CI (`setup-uv`, version pinned) and Colab (`pip install uv==0.8.17`).
   - **(b)** The setup script downloads the uv 0.8.17 wheel from PyPI for this architecture, checks a SHA-256 pinned in the script, and unpacks uv into `$AQIS_CACHE`. This gives one command and verified bytes, but adds a download step and two pinned hashes to maintain.
5. **(FR-0.6-05) Where rclone comes from.**
   - **(a) Recommended if Oracle runs Ubuntu:** the distribution package (`sudo apt-get install rclone`; 1.60.1 on Ubuntu 24.04, the same version as this VM). The runbook gives the command, and `sync` requires at least 1.60.1 and prints the version it used. CI's job `lab` gets one step, `sudo apt-get install -y rclone`, so the real-rclone tests run on every push. The setup script does not install system packages.
   - **(b)** The official rclone release, pinned by version and SHA-256, downloaded by the setup script and by CI. This needs `downloads.rclone.org` on the cloud allowlist (403 today).
6. **(FR-0.6-02) What the store holds.**
   - **(a) Recommended:** both runner result rows and score rows. Exit criterion E3 is about score rows ("any score row leads back to its run card…"), and WP-0.7 produces both.
   - **(b)** Runner result rows only; score rows join in WP-0.7.
7. **(FR-0.6-02) Adding rows, and where the store lives.**
   - **(a) Recommended:**
     - rows go in with an explicit `results add`; the runner and the scorer stay unchanged;
     - identical rows added again are reported and not stored twice; a changed row stops the whole add;
     - the store lives on local disk only, and Drive gets it through `sync`.

     How Colab's results reach the store is decided in WP-0.7, whose smoke run produces the Colab bundle.
   - **(b)** Any add containing an already stored row ID is refused, even when identical.
   - **(c)** Also allow a store directly on Drive. Without hard links, "never replaced" would rest on a check-then-rename, which is weaker.
8. **(FR-0.6-04) Which run modes are timing runs.**
   - **(a) Recommended:** `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay` and `human_session` run on the reserved cores; `batch` runs on the others.
   - **(b)** Your list.
9. **(FR-0.6-04) Where the reservation applies.**
   - **(a) Recommended:**
     - only on the `oracle` platform;
     - the runner keeps its batch runs off the reserved cores, and WP-0.7's timing code pins itself to them;
     - other lab commands (`score`, `pack build`, …) are not pinned;
     - on the cloud VM and Colab nothing is pinned, and the log says so.

     Programs outside the lab, such as Jitsi on the same VM, can still use the reserved cores. The runbook shows an optional systemd setting (`AllowedCPUs`) you may apply to keep them off. It is your choice, because it changes system services.
   - **(b)** Also start every lab command on Oracle off the reserved cores, through the dispatcher. That changes `aqis_lab/__main__.py`'s `main`, and every command then depends on platform detection.
10. **(FR-0.6-04) Hyper-threads.** On x86 Oracle shapes, one OCPU is two hardware threads of one physical core.
    - **(a) Recommended:** a reservation must hold whole physical cores (all sibling threads), otherwise it is refused. Batch work on a sibling thread would disturb timing on the same core.
    - **(b)** Accept any set of CPU numbers.
11. **(FR-0.6-04) Doctor `cores` row.**
    - **(a) Recommended:** `doctor --target oracle` checks the reservation against the real machine. The setup's final step then reports an impossible reservation at once, which is the spec's "stop and ask if core reservation is not possible on the shape".
    - **(b)** No doctor change; the first run finds it.
12. **(FR-0.6-05) Drive access for rclone.** The rclone Drive remote needs the full `drive` scope to see the `AQIS_LAB` folder you created. The narrower `drive.file` scope sees only files rclone itself created, and a copy would then quietly start a second `AQIS_LAB`.
    - **(a) Recommended:** scope `drive`, no root folder ID. `sync` refuses to run unless `AQIS_LAB/results/` already exists on the remote, so it can never create a second `AQIS_LAB`.
    - The token then sits in `~/.config/rclone/rclone.conf` (mode 600) on the Oracle VM with access to your whole Drive. If that is not acceptable, a separate Google account that shares only `AQIS_LAB` is the alternative. The runbook would then differ, and I would ask before changing it.
13. **(FR-0.6-02) Store file format.** Recommended: Parquet part files with the columns listed under "Results store". The source row is kept as canonical JSON, so nothing is lost for any task or score kind. `pyarrow` is already pinned. Say if you want typed per-kind columns instead; that needs a schema per row kind.
14. **(OC-0.6-01) Clone on Oracle and the pinned tag.**
    - **(a) Recommended:**
      - a read-only **deploy key** for this repository, created on the Oracle VM (`ssh-keygen`, then GitHub → Settings → Deploy keys, without write access);
      - after the audit passes, I push an annotated tag `aqis-lab-wp-0.6-oracle-1` on the branch head, and you check it out for both checks;
      - a later fix gets `-oracle-2`, as with Colab.
    - **(b)** A fine-grained read-only token, used through git's `GIT_CONFIG_*` variables as in the Colab launcher.
15. **(DEBT-008) Fix `score --out` into a folder that cannot be created.**
    - **(a) Recommended:** include it. `write_outputs` in `aqis_lab/commands/score.py` gets `out.mkdir` inside its `try`, so the command prints `ERROR:` and exits 2. It is tested by `test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2` in `tests/aqis_lab/test_aqis_debt_wp06.py`, and DEBT-008 is closed. No existing test changes.
    - **(b)** Move DEBT-008 to a later WP.
16. **(Additions beyond the spec's deliverables.)** Approving these accepts them:
    - **D1:** the command `results add` and the options `--store` and `--config`.
    - **D2:** extra files:
      - code: `aqis_lab/oracle_config.py`, `aqis_lab/results/{__init__,ingest,views}.py`, `aqis_lab/commands/{results,trace,sync}.py`, `aqis_lab/timing/__init__.py`;
      - document: `docs/results/RESULTS_STORE.md`.
    - **D3:** the `setup` section of `oracle.yaml` (question 3).
    - **D4:** the doctor `cores` row (question 11).
    - **D5:** the runner's pinning and its `cores` log line (question 9).
    - **D6:** the CI step for rclone (question 5).
    - **D7:** the `pytest -m oracle` step in OC-0.6-01.
    - **D8:** the run and `results add` steps before the dry run in OC-0.6-02.

    **Recommended: accept all.**

### Design decisions made in this plan (approving the plan accepts them)
- **Machine facts stay in one module.** Online CPUs, CPU siblings, thread IDs and thread affinity are read in `aqis_lab.platform`, like every other machine fact. `cores.py` only sets affinity.
- **Every thread is pinned** (finding 6), and the pin is read back and verified. A pin that did not take is an error, never a warning.
- **Nothing is replaced, nothing is deleted.** Store files are published by hard link. Sync is `rclone copy --immutable`. The only file the lab removes is its own `.partial` after a successful publish.
- **Row IDs come from identity, not content**, so a changed result for the same run card and clip is detected as a conflict instead of stored beside the old one.
- **Trace verifies before it prints.** A damaged or mismatched row or card is an error, never a best guess.
- **The setup script reuses `dev_bootstrap.sh`**, so the venv and lock rules are the same on every machine.
- **No source builds on Oracle.** The wheel check uses `--only-binary :all:`.
- **Timestamps** are UTC with `Z`. Durations use the monotonic clock in nanoseconds.
- **Exit codes** follow the lab's pattern: 0 success, 1 a failed check or conflict, 2 usage or input error.

### Other risks
1. **aarch64 on real hardware.** If the Oracle VM is x86_64, the aarch64 path is proven only by wheel resolution against PyPI (`test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds`), not by running on Arm. I will say so in `EVIDENCE.md`.
2. **Timing noise from other programs.** Jitsi, if it runs on the same VM, can still use the reserved cores (question 9). The runbook explains the optional system setting.
3. **rclone 1.60.1 is from 2022.** Google can change its Drive API. `sync` prints the rclone version, and a failure shows rclone's own message. OC-0.6-02 checks it on your real remote.
4. **Drive folder size.** One store folder per run card sits inside `AQIS_LAB/results`. Drive slows down past about 10,000 items per folder; phase 0 makes a handful of run cards. `RESULTS_STORE.md` states the limit.
5. **Hard links.** The store needs a local file system with hard links (ext4 and xfs on Oracle and this VM; overlay on Colab's local disk). A store on a file system without them fails loudly on its first add.
6. **Lock growth.** DuckDB adds a 20 MB wheel to every install, including Colab's launcher. The doctor's lock check needs the new lock, which the launcher installs from the tag.
7. **Clock-free proof.** Like FR-0.5-06, the batch-affinity test holds the run on a named-pipe clip. The affinity is then read while the run is certainly inside a shard, so there is no timing race.

## Deviations
None of the spec's requirements is changed. Additions D1 to D8 (question 16) go beyond the listed deliverables and need your acceptance. Questions 1 and 2 cannot be answered from the repository and need your inputs.

## Measurements
| What | Command | Result |
| --- | --- | --- |
| This VM | `nproc`, `lscpu`, `/etc/os-release`, `ldd --version` | 4 CPUs, 1 thread per core, Intel Xeon @ 2.10GHz, Ubuntu 24.04.4 LTS, glibc 2.39, affinity `0-3`, no `isolcpus`, no `chassis_asset_tag` file |
| Lock wheels per architecture | `uv pip compile <25 lock pins> --no-deps --only-binary :all: --python-platform <p> --python-version 3.13` | `aarch64-manylinux_2_28` exit 0; `x86_64-manylinux_2_28` exit 0; `aarch64-manylinux_2_17` exit 1: "numpy==2.5.3 has no usable wheels" |
| DuckDB wheels | the same with `duckdb` | `duckdb==1.5.6` on both; PyPI files `duckdb-1.5.6-cp313-cp313-manylinux_2_26_{x86_64,aarch64}.manylinux_2_28_*.whl` |
| DuckDB offline | scratch venv, `autoinstall_known_extensions=false` | `parquet`, `json`, `icu`: `STATICALLY_LINKED`, loaded; view over Parquet with `json_extract` returned the rows; no `~/.duckdb` created |
| Lock with DuckDB | `uv pip compile phase0.in + duckdb --universal --python-version 3.13 --generate-hashes` (scratchpad) | the only new pin is `duckdb==1.5.6` |
| rclone | `rclone copy --immutable [--checksum] src aqistest:dst` with `RCLONE_CONFIG_AQISTEST_TYPE=local` | remote-only file kept; differing remote file kept, exit 6 `immutable file modified`; `--dry-run` created nothing; unknown remote exit 1 `didn't find section in config file` |
| rclone download host | `curl -sI https://downloads.rclone.org/` | `HTTP/1.1 403 Forbidden` (proxy) |
| Thread affinity | `import numpy`; `os.sched_setaffinity(0, {3})`; read every `/proc/self/task` thread | main `[3]`, three other threads `[0, 1, 2, 3]`; after setting each thread: all `[3]`; child process `Cpus_allowed_list: 3` |
| uv wheels | PyPI JSON for uv 0.8.17 | `manylinux_2_17_x86_64` sha256 `b6d30d02…788f`; `manylinux_2_28_aarch64` sha256 `3941cecd…5d01` |
| Fast suite at base | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` | `1524 passed, 18 deselected in 155.17s` |
