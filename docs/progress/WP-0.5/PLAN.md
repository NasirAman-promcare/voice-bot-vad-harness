# PLAN — WP-0.5 Platform detection, doctor, resumable runner and Colab launcher

Spec: `docs/specs/phase-0/WP-0.5-platform-doctor-runner-colab.md`  ·  Planned by session: https://claude.ai/code/session_016NHQnTY3XyGxfsvGCp1n9y  ·  Date: 2026-09-28
Branch: `claude/magical-goldberg-kjvw5r`  ·  Base: `origin/main` at `da0fd00`  ·  Depends on: WP-0.2 and WP-0.4 (both MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, the same lab commands run unchanged on the cloud VM, Colab and Oracle, and long runs survive a disconnect.
- **Platform.** `aqis_lab/platform.py` is the one place that works out where the lab runs (`cloud-vm`, `colab`, `kaggle` or `oracle`), the GPU type, CPU model, architecture, OS and Python version. It fills the run card's `machine` block.
- **Doctor.** `python -m aqis_lab doctor --target cloud|colab|oracle [--expect-gpu]` checks the Python version against the Colab probe, the installed packages against the lock, free disk and RAM against documented minimums, the GPU when asked, and, on Colab, the Drive mount and the `AQIS_LAB` folder. It prints a PASS/FAIL table, writes `doctor_<platform>_<UTC timestamp>.json`, and exits non-zero on any FAIL.
- **Drive.** The lab creates `AQIS_LAB/{packs,models,results,logs}` when they are missing. It never deletes anything, warns before any folder passes 1,000 items, and refuses to write anywhere on Drive outside `AQIS_LAB/`.
- **Runner.** `python -m aqis_lab run` first copies a pack's archives to local disk, checks every hash and extracts them there (copy then compute). It then splits the run into shards (by default at most 30 minutes of expected work each). Each shard's results are written atomically with a completion marker. A restart skips finished shards, and starting over needs an explicit `--from-scratch`. A test kills a real run partway, restarts it, and proves the final results are byte-identical to an uninterrupted run.
- **Colab.** A launcher notebook of at most 6 cells does four things only: mount Drive, clone the private repository at a pinned tag with the `GITHUB_TOKEN` secret, install the lock, and call lab commands. A static test proves it holds no logic. Each Colab session appends its estimated compute units to `AQIS_LAB/logs/units.csv`, from the rates in `config/aqis_lab/colab_rates.yaml`. `docs/colab/COLAB_RUNBOOK.md` gives the owner exact steps.

## What I found in the repository and environment (read-only inspection)
1. **Spec sources.**
   - "Read first" names the Build Plan sections "Resource plan" and "Run modes by phase". The Build Plan is not in the repository (`find` and `grep` for "Build Plan", "Resource plan" and "Run modes by phase" find only the specs).
   - As in WP-0.2 to WP-0.4, following your instruction that `docs/specs/phase-0/` is authoritative and self-contained, this plan relies on the spec, the phase 0 overview and `.claude/rules/40-environment-parity.md`.
   - **One requirement cannot be met from the spec alone.** FR-0.5-07 says "Initial rates are the Build Plan's figures with their source". I do not have those figures, and I will not invent them (question 1, owner need 2).
   - `aqis-kit-patch-3/docs/specs/phase-0/WP-0.5-platform-doctor-runner-colab.md` is byte-identical to the spec (`diff -r` reports only that the overview is missing there).
2. **Dependencies.** WP-0.2 and WP-0.4 are MERGED in `docs/progress/STATUS.md`. No blocker is open.
3. **Contracts I build on (WP-0.2, unchanged).**
   - The run card's `machine` block (`docs/contracts/RUN_CARD.md`) has exactly the FR-0.5-01 fields: `platform` (enum `cloud-vm`, `colab`, `kaggle`, `oracle`), `gpu` (string or null), `cpu_model`, `architecture`, `os` and `python_version`. The block is closed, so nothing else can be added to it. The same holds for the whole card.
   - `machine` is part of `run_card_id`, so the same run on a different CPU model has a different ID. This matters for resuming on a new Colab runtime (question 4).
   - Reused as they are: `sha256_canonical` and `compute_run_card_id` (`aqis_lab/contracts/canonical.py`), `validate_run_card` and `validate_manifest` (`aqis_lab/contracts/validate.py`), `verify_pack` (`aqis_lab/packs/verify.py`), and `read_wav` (`aqis_lab/packs/audio.py`).
4. **Existing code that already reads platform details** (must-catch 5 says "Platform details come from `aqis_lab.platform` only"; see question 7):
   - `aqis_lab/deploy/harness_provision.py`, `check_platform` (lines 124 to 140). It reads `platform.system()`, `platform.machine()` and `platform.freedesktop_os_release()` to refuse unsupported machines before provisioning.
   - `aqis_lab/commands/version.py:58`. It reads `platform.python_version()` for the `version` line.
   - `aqis_lab/deploy/dev_bootstrap.sh` and `harness_provision.sh`. They read the Python version of an interpreter before any lab environment exists.
   - No other `aqis_lab/` or `tools/` code reads machine facts (`grep` for `platform.`, `nvidia`, `cpuinfo`, `os-release`, `uname`, `COLAB`, `sys.version`).
5. **Code patterns I will mirror, not change.**
   - The probe parser: the regular expression shared by `dev_bootstrap.sh`, `harness_provision.py` and `tests/aqis_lab/aqis_testutil.py`. It reads the Python major.minor and fails when there are none or several.
   - The lock-match rule of `test_FR_0_0_03_environment_matches_lock`: every applicable lock entry is installed at its pinned version, and nothing else is installed.
6. **This cloud VM** (measured):
   - Ubuntu 24.04.4 LTS, x86_64, 4 CPUs, CPU "Intel(R) Xeon(R) Processor @ 2.80GHz", 15 GB RAM available, 30 GB free disk.
   - No `nvidia-smi`. Environment variable `CLAUDE_CODE_REMOTE` is set. git 2.43.0.
   - System Python is **3.13.12**, and the Colab probe says **3.13.15**. Rule 40 pins the major.minor (question 9).
   - `setpriv` (util-linux 2.39.3) is available. I checked in the scratchpad that a root process can write into a folder with mode 0555, and that the same write fails with `PermissionError` once `setpriv --bounding-set -dac_override,-dac_read_search` removes root's override. This is how the read-only Drive test runs as root (see "Doctor").
7. **Colab facts.**
   - Known from the committed files: `docs/environment/colab_probe.txt` gives Python 3.13.15, Linux x86_64 with glibc 2.39, and a Tesla T4 on a GPU runtime. `colab_harness_provision.txt` shows that `uv` plus `dev_bootstrap.sh` build `.venv` there.
   - **Not in any committed file:**
     - which environment variable identifies a Colab runtime;
     - whether a CPU runtime has an `nvidia-smi` command;
     - how the Drive mount appears in `/proc/self/mountinfo`;
     - the CPU model line;
     - free disk and RAM. The committed probe lacks the `df` and `free` lines that `docs/environment/README.md` asks for.

   Owner need 3 is a one-cell probe that answers these, so detection is built on facts rather than guesses.
8. **Oracle.** `docs/environment/oracle_probe.txt` is missing. The Oracle detection rule cannot be checked on a real Oracle VM until WP-0.6 (question 6, risk 3).
9. **Smoke pack** (`data/packs/smoke/v1/`, measured):
   - 60 clips in 5 tar archives (12.6 MB), 390.9 s of audio in total.
   - A plain-Python pass that reads every clip from the archives, hashes it and sums its squared samples takes **0.44 s** here.

   So any real work WP-0.5 can do on the smoke pack (there is no model until WP-0.7) finishes in about a second. This has three consequences:
   - With the default 30-minute shards, the smoke pack is one shard.
   - A person cannot disconnect a Colab runtime "partway" through such a run (question 5).
   - The runner's fixed costs weigh heavily against a sub-second workload (risk 1).
10. **Disk writes.** An atomic write here (write, fsync, rename, fsync the folder) takes a median of **0.61 ms** (p90 0.79 ms, 50 trials in the scratchpad).
11. **Repository fit.**
    - The root `.gitignore` (GUARDED) ignores `/data/raw/`, so default local work folders under `data/raw/aqis_lab/` need no `.gitignore` change.
    - It also ignores `*.jsonl` everywhere. This does not matter for committed evidence: the runner log that OC-0.5-02 commits is a `.log` file, and you upload through the GitHub website.
    - `aqis_lab/__main__.py` needs new `COMMANDS` entries. No lock change is needed: `pyyaml`, `numpy` and `jsonschema` are already pinned.
12. **Accepted debt that targets WP-0.5** (`docs/progress/DEBT.md`): DEBT-009 (no test covers the normaliser version-check wiring in `score`) and DEBT-011 (`test_FR_0_4_03_distinct_speakers_and_utterances` does not catch removal of the one-clip-per-speaker rule). The spec does not mention them (question 13).

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.5-01 | `detect()` reads the environment, a few system files and `nvidia-smi` through one `SystemView` (real system by default; tests pass a generated folder tree and environment). Each platform needs a positive signal; none or more than one is an error, never a default (question 6). Returns `platform`, `gpu` (type from `nvidia-smi` when present, else null), `cpu_model`, `architecture`, `os`, `python_version`. `machine_block()` gives the run card's `machine` object. Detection runs once per process. The disk, RAM and mount facts that the doctor and the Drive guard need come from this module too, so all machine facts have one source | `aqis_lab/platform.py` | none | `test_FR_0_5_01_detects_each_platform_from_its_signal`, `test_FR_0_5_01_unknown_platform_is_an_error`, `test_FR_0_5_01_conflicting_signals_are_an_error`, `test_FR_0_5_01_gpu_type_from_nvidia_smi_else_null` (a stand-in `nvidia-smi` on `PATH`: GPU test double), `test_FR_0_5_01_failing_nvidia_smi_is_an_error`, `test_FR_0_5_01_cpu_model_from_cpuinfo_or_lscpu` (generated x86_64 and aarch64 files), `test_FR_0_5_01_real_machine_facts` (this VM and CI: expected values read in the test from `uname -m`, `/etc/os-release` and `sys.version_info`), `test_FR_0_5_01_machine_block_valid_in_run_card`, `test_FR_0_5_01_platform_details_only_from_platform_module` (static scan, must-catch 5), `test_FR_0_5_01_colab_runtime_detected` (`colab` marker) | `.venv/bin/python -c "from aqis_lab import platform as p; print(p.machine_block())"` prints `platform: cloud-vm`, `gpu: None` and this VM's facts |
| FR-0.5-02 | `doctor` builds a list of checks. Each gives PASS, FAIL or SKIP with the expected value, the actual value and a detail. It prints a fixed-width table and writes `doctor_<platform>_<YYYYMMDDTHHMMSSZ>.json` to `--out` (default `data/raw/aqis_lab/doctor/`, git-ignored). Exit codes: 0 when nothing FAILs, 1 on any FAIL, 2 on a usage error or when the report cannot be written. The checks are listed under "Doctor" below | `aqis_lab/doctor.py`, `aqis_lab/commands/doctor.py`, `config/aqis_lab/doctor.yaml` (minimums, question 8), `docs/doctor/DOCTOR.md` | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json`, `test_FR_0_5_02_fails_on_python_version_other_than_probe`, `test_FR_0_5_02_fails_on_package_version_other_than_lock`, `test_FR_0_5_02_fails_on_package_missing_from_lock`, `test_FR_0_5_02_fails_on_lock_package_not_installed`, `test_FR_0_5_02_fails_below_disk_minimum`, `test_FR_0_5_02_fails_below_ram_minimum`, `test_FR_0_5_02_gpu_skipped_without_expect_gpu`, `test_FR_0_5_02_expect_gpu_fails_without_gpu`, `test_FR_0_5_02_expect_gpu_passes_with_gpu`, `test_FR_0_5_02_fails_when_target_is_not_this_platform`, `test_FR_0_5_02_colab_fails_when_drive_not_mounted`, `test_FR_0_5_02_colab_fails_when_aqis_lab_missing`, `test_FR_0_5_02_colab_fails_when_aqis_lab_read_only`, `test_FR_0_5_02_colab_drive_checks_pass_when_writable`, `test_FR_0_5_02_any_fail_exits_non_zero`, `test_FR_0_5_02_minimums_documented_equal_config`, `test_FR_0_5_02_colab_doctor_passes_on_colab` (`colab` marker) | AT-0.5-01 |
| FR-0.5-03 | `drive layout --drive-mount <mount>` works on `<mount>/MyDrive/AQIS_LAB` (you create `AQIS_LAB`; the lab never creates it). It creates only the missing `packs`, `models`, `results` and `logs` folders and never deletes, renames or rewrites anything. A layout name that exists as a file is an error. Every lab write that adds an entry to a Drive folder counts that folder's entries first and warns before the folder would pass 1,000 items (question 10). `drive layout` also reports every folder already over the limit | `aqis_lab/drive.py`, `aqis_lab/commands/drive.py` | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_5_03_creates_missing_layout_folders`, `test_FR_0_5_03_never_deletes_or_changes_existing_content` (full tree snapshot of names, bytes and modes before and after), `test_FR_0_5_03_refuses_when_aqis_lab_missing`, `test_FR_0_5_03_layout_name_that_is_a_file_is_an_error`, `test_FR_0_5_03_warns_before_folder_exceeds_1000_items` (exact boundary: 999 and 1,000 existing entries), `test_FR_0_5_03_layout_reports_crowded_folders`. Google Drive is replaced by a folder the test makes (Drive test double) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_5_03` |
| FR-0.5-04 | `stage_pack(source, work_dir)`: <br>1. Read the source's manifest strictly and validate it (WP-0.2 contract). <br>2. Copy the pack folder (manifest, `LICENCES.md`, `build_record.json`, archives) from Drive or the repository into a staging folder on local disk. <br>3. Run `verify_pack` on the local copy: every archive's size and SHA-256, and every member. <br>4. Extract each archive with safe-path rules, check every extracted clip's SHA-256 against the manifest, and write a `.staged` marker. <br>5. Rename the staging folder into place. <br>Only a staged pack with a valid marker is ever processed. The runner reads clips only from the local extracted copy and re-checks each clip's SHA-256 when it reads it. A work folder on a Drive mount is refused | `aqis_lab/runner/stage.py` | none | `test_FR_0_5_04_stages_repository_pack_to_local_disk`, `test_FR_0_5_04_stages_pack_from_drive_folder` (Drive test double), `test_FR_0_5_04_rejects_changed_archive_and_stages_nothing`, `test_FR_0_5_04_interrupted_staging_is_redone`, `test_FR_0_5_04_restaging_a_staged_pack_copies_nothing`, `test_FR_0_5_04_run_reads_only_local_extracted_clips` (the source is moved away after staging and the run still completes), `test_FR_0_5_04_work_dir_on_drive_is_refused`, `test_FR_0_5_04_changed_extracted_clip_stops_the_run` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_5_04` |
| FR-0.5-05 | The run folder layout, shard plan, atomic writes, markers and resume rules are under "Runner" below. The default shard holds at most 30 minutes of expected work: clip duration × the task's measured processing-time ratio (question 3). `--shard-minutes` and `--shard-clips` configure it. A shard counts as finished only when its marker exists, parses, names this plan and shard, and matches the results file's SHA-256 and size. `--from-scratch` moves the old run folder aside (rename, never delete) and starts again. Without it, a changed run card or shard plan is refused | `aqis_lab/runner/__init__.py`, `tasks.py`, `card.py`, `plan.py`, `store.py`, `run.py`, `aqis_lab/commands/run.py`, `docs/runner/RUNNER.md` | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work` (expected shards computed in the test from the manifest), `test_FR_0_5_05_shard_size_is_configurable`, `test_FR_0_5_05_shard_results_written_atomically_with_marker`, `test_FR_0_5_05_results_without_marker_not_finished` (must-catch 3), `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished` (must-catch 3), `test_FR_0_5_05_restart_skips_finished_shards`, `test_FR_0_5_05_starting_over_requires_from_scratch`, `test_FR_0_5_05_from_scratch_keeps_old_run_folder`, `test_FR_0_5_05_changed_card_or_plan_refused`, `test_FR_0_5_05_resume_rule_for_other_cpu_model` (question 4), `test_FR_0_5_05_run_card_valid_and_traceable`, `test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids`, `test_FR_0_5_05_clip_failure_stops_run_without_marker`, `test_FR_0_5_05_max_shards_stops_cleanly` (question 5) | `.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --seed 0 --shard-clips 10 --out <tmp>/r1` twice; the second run's log says `6 shard(s) skipped` |
| FR-0.5-06 | A test starts a real `python -m aqis_lab run` on the committed smoke pack in a subprocess with 6 shards. It stops it with SIGKILL while it is inside shard k+1, after k shards have their markers (method under "Kill-and-resume test"). It restarts the same command and compares the result with an uninterrupted run in another folder: `results.jsonl` is byte-identical, the k finished shards were skipped (runner log, and their marker and result files are unchanged byte for byte, inode and mtime), and only the remaining shards were computed | (tests only) | none | `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` (must-catch 2), `test_FR_0_5_06_kill_during_result_write_never_counts` | AT-0.5-02 |
| FR-0.5-07 | `unitlog start` and `unitlog end` (questions 1 and 11). A session's row is appended to `AQIS_LAB/logs/units.csv` with: session ID, platform, GPU type, start and end UTC, how the end was determined, hours, the rate used, estimated units and the rate's source. The estimate is hours × the rate for this runtime's GPU type (`cpu` when there is no GPU) from `config/aqis_lab/colab_rates.yaml`, computed with `decimal` and rounded half-even to 4 places. An unknown runtime type is an error, never a default rate. The CSV is only ever appended to. Outside Colab the command refuses | `aqis_lab/unitlog.py`, `aqis_lab/commands/unitlog.py`, `config/aqis_lab/colab_rates.yaml` (**needs the Build Plan figures, question 1**) | `aqis_lab/__main__.py`: `COMMANDS`, CHANGE LOG | `test_FR_0_5_07_appends_row_with_estimate_from_rate_table` (must-catch 6; expected value computed in the test with `fractions`), `test_FR_0_5_07_append_never_rewrites_existing_rows`, `test_FR_0_5_07_unknown_runtime_type_is_an_error`, `test_FR_0_5_07_every_rate_names_its_source`, `test_FR_0_5_07_committed_rates_equal_owner_figures` (figures typed into the test from your answer), `test_FR_0_5_07_unclosed_session_is_closed_at_next_start`, `test_FR_0_5_07_refuses_outside_colab`, `test_FR_0_5_07_colab_session_row_appended` (`colab` marker) | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_5_07` |
| FR-0.5-08 | `notebooks/aqis_lab/phase0_launcher.ipynb`: 1 markdown cell and 5 code cells (see "Launcher notebook"). Cell 1 holds `AQIS_TAG` and the other settings as plain literals. The static test parses every code cell with Python's `ast` and accepts only an allow-list: literal assignments, allowed imports, `drive.mount`, `userdata.get`, `base64` encoding, `subprocess.run([...], check=True)` and `del`. It rejects `if`, loops, `try`, `with`, functions, lambdas, comprehensions, conditional expressions, comparisons, shell magics (`!`, `%`) and any other call | `notebooks/aqis_lab/phase0_launcher.ipynb`, `docs/colab/COLAB_RUNBOOK.md` | none | `test_FR_0_5_08_launcher_has_at_most_6_cells`, `test_FR_0_5_08_tag_is_one_variable_in_first_cell`, `test_FR_0_5_08_launcher_cells_contain_no_logic` (must-catch 4), `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form` (the checker is shown to reject an `if`, a `for`, a `def`, a `try`, a `!` line, a comprehension and an unlisted call), `test_FR_0_5_08_token_only_reaches_the_clone_command`, `test_FR_0_5_08_clone_failure_never_shows_token` (stand-in `google.colab` module, as in FR-0.0-13), `test_FR_0_5_08_launcher_commands_exist_and_parse`, `test_FR_0_5_08_runbook_matches_launcher` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_5_08` |
| NFR-0.5-01 | Same process, same staged smoke pack, same task: a direct loop (read each clip, check its hash, compute, write one results file atomically) against `run` with its default shard size. Nine alternating repetitions after one warm-up each; compare medians with a monotonic clock. Overhead = (runner − direct) / direct < 5 % (risk 1) | (tests only) | none | `test_NFR_0_5_01_runner_overhead_under_5_percent` (`slow`) | `.venv/bin/python -m pytest tests/aqis_lab -q -m slow -k NFR_0_5_01` |
| NFR-0.5-02 | Every lab write goes through `drive.check_write_path(path, system)`. A path under any Drive mount that `aqis_lab.platform` finds must be inside `<mount>/MyDrive/AQIS_LAB/`; anything else is refused before any byte is written. Used by `doctor --out`, `run --out` and `--work-dir`, `drive layout` and `unitlog` | (in `aqis_lab/drive.py`) | none | `test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab` (every writing command, with a Drive mount test double; the whole stand-in Drive is compared before and after), `test_NFR_0_5_02_writes_under_aqis_lab_allowed` | `.venv/bin/python -m pytest tests/aqis_lab -q -k NFR_0_5_02` |
| AT-0.5-01 | Run as written, from the repository root | — | — | `test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json` | `.venv/bin/python -m aqis_lab doctor --target cloud` (exit 0; every row PASS except `gpu` SKIP; prints the JSON path) |
| AT-0.5-02 | Run both suites | — | — | all of the above | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` and `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow and not gpu and not colab and not oracle and not network"` (both exit 0; the kill-and-resume test is in the fast suite) |
| AT-0.5-03 | Run as written after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.5` (exit 0, `0 findings`) |
| OC-0.5-01 | Owner, in Colab: see "Owner-run checks planned" | — | — | `colab`-marked tests | Launcher cells 1 to 4, then one extra cell: `!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab` |
| OC-0.5-02 | Owner, in Colab: see "Owner-run checks planned" | — | — | — | Launcher with `RUN_ARGS` set as in the runbook; disconnect and delete the runtime; run again |

**Change budget for existing files** (nothing else that already exists is touched):
- `aqis_lab/__main__.py`: add four `COMMANDS` entries (`doctor`, `drive`, `run`, `unitlog`) and one CHANGE LOG line per command. `build_parser` and `main` stay byte-identical. CAP-CLI-001's behaviour is unchanged, so its registry row stays as it is.
- `docs/capabilities/REGISTRY.md`: append new rows only; every existing row stays byte-identical.
- `docs/progress/STATUS.md`: the WP-0.5 row only.
- `docs/progress/DEBT.md`: close DEBT-009 and DEBT-011 (Status column only) if question 13 is accepted, and add rows only for audit findings you accept as debt.
- `docs/progress/BLOCKERS.md`: append-only, and only if I get blocked.
- Not touched: no GUARDED or NEVER path, no existing test file, no lock file. So no `ALLOW-EDIT` is needed, whichever way question 7 goes, provided you choose (a).

**New files** (besides those in the table):
- `docs/progress/WP-0.5/EVIDENCE.md`.
- Test modules. The `test_aqis_` prefix keeps basenames unique (FR-0.0-04):
  - `tests/aqis_lab/test_aqis_platform.py`, `test_aqis_doctor.py`, `test_aqis_drive.py`, `test_aqis_stage.py`, `test_aqis_runner.py`, `test_aqis_runner_resume.py`, `test_aqis_runner_nfr.py`, `test_aqis_unitlog.py`, `test_aqis_launcher.py`;
  - `test_aqis_colab_live.py`: `colab` marker only; runs on Colab, never in the fast suite;
  - `test_aqis_debt_wp05.py`, if question 13 is accepted.
- The shared test helper `tests/aqis_lab/aqis_runner_testutil.py`. It builds generated system trees, stand-in Drive folders, generated locks and probes, and computes expected values independently of the code under test.

## Design details

### Platform (`aqis_lab/platform.py`)
- **Inputs.** One `SystemView(root, environ, path)` object holds everything the module reads:
  - the environment variables;
  - the files `/proc/cpuinfo`, `/proc/meminfo`, `/proc/self/mountinfo`, `/etc/os-release` and `/sys/class/dmi/id/chassis_asset_tag`;
  - the commands `nvidia-smi` and `lscpu`, found on `PATH`.

  The default is the real system. Tests pass a generated folder tree, a chosen environment and stand-in commands. The only absolute paths in lab code are these operating-system interface files, and they are resolved against `root`.
- **Platform signals** (question 6). Exactly one must match; none or several is `PlatformError`, naming what was found:

  | Platform | Signal |
  | --- | --- |
  | `colab` | environment variable `COLAB_RELEASE_TAG` is set (to be confirmed by owner need 3) |
  | `kaggle` | environment variable `KAGGLE_KERNEL_RUN_TYPE` is set |
  | `oracle` | `/sys/class/dmi/id/chassis_asset_tag` reads `OracleCloud.com`, the value cloud-init's Oracle data source checks |
  | `cloud-vm` | `CLAUDE_CODE_REMOTE=true` (this Claude Code cloud session) or `GITHUB_ACTIONS=true` (the CI runner, if you accept question 6) |
- **GPU.** `nvidia-smi --query-gpu=name --format=csv,noheader`:
  - Not on `PATH`: `None`.
  - Exit 0: one name gives that name, such as `Tesla T4`. Several identical names give `<n> x <name>`. Different names are joined with ` + `. No rows gives `None`.
  - Non-zero exit: `PlatformError` with its message. This is never turned into "no GPU", because a broken driver on a GPU runtime must not look like a CPU runtime. If owner need 3 shows that Colab CPU runtimes ship an `nvidia-smi` that fails, I stop and ask.
- **CPU model.** The first `model name` line of `/proc/cpuinfo`, else `lscpu`'s `Model name` (aarch64 kernels, such as Ampere on Oracle, have no `model name` line). If neither exists, `PlatformError`.
- **Other facts.**
  - Architecture: `platform.machine()`.
  - OS: `PRETTY_NAME` from `/etc/os-release`.
  - Python: `platform.python_version()`.
  - `memory_available_bytes()`: `MemAvailable` from `/proc/meminfo`.
  - `disk_free_bytes(path)`: `shutil.disk_usage` of the nearest existing folder.
  - `drive_mounts()`: mount points whose file-system type is the one owner need 3 shows for Colab's Drive.
- **Once per process.** `detect()` on the real system is cached, so a run card and a doctor report within one process always agree.

### Doctor (`aqis_lab/doctor.py`, `docs/doctor/DOCTOR.md`)
Checks, in this order. Every check runs even after an earlier FAIL:

| Check | PASS when | Notes |
| --- | --- | --- |
| `platform` | detection succeeds and the platform equals the target (`cloud` → `cloud-vm`) | Addition: without it, `--target colab` on the wrong machine could pass (question 14) |
| `python` | the running major.minor equals the Colab probe's (question 9) | Shows both full versions |
| `lock` | the installed distributions equal the applicable entries of `requirements/aqis_lab/phase0.txt` (name and version, markers evaluated), with nothing missing and nothing extra | Lists every difference and the lock's SHA-256 |
| `disk` | free space on the work folder's file system ≥ the target's minimum | `--work-dir`, default `data/raw/aqis_lab/work` |
| `ram` | `MemAvailable` ≥ the target's minimum | |
| `gpu` | with `--expect-gpu`: a GPU type is detected. Without it: SKIP ("not requested") | OC-0.5-01 expects SKIP |
| `drive-mount` (colab only) | `--drive-mount` is one of the Drive mounts `aqis_lab.platform` finds | |
| `drive-folder` (colab only) | `<mount>/MyDrive/AQIS_LAB` is a folder, and a check file `logs/doctor_write_check.json` can be written, fsynced, renamed into place and read back | Overwritten each time: one file, never deleted, never growing |

- Minimums live in `config/aqis_lab/doctor.yaml` per target and are shown in `DOCTOR.md` and the runbook. A test keeps the three identical.
- The JSON holds: format version, target, `--expect-gpu`, created UTC, `machine_block()` (or the detection error), the git commit, the lock SHA-256, every check (name, status, expected, actual, detail) and the overall result.
- **Read-only Drive test as root.** The stand-in `AQIS_LAB` folder gets mode 0555. On CI (not root), the mode alone makes writes fail. When the test runs as root (this VM, Colab), it runs the doctor in a subprocess under `setpriv --bounding-set -dac_override,-dac_read_search`, so root's override is gone and the mode applies exactly as it does for any user. The real code path runs in both cases (finding 6).

### Drive layout and the write guard (`aqis_lab/drive.py`)
- **Paths.** The Drive mount point is a command-line argument (`--drive-mount`; the notebook passes `/content/drive`). The lab folder is always `<mount>/MyDrive/AQIS_LAB`. No Drive path is hard-coded in lab code.
- **`ensure_layout`.** Creates only the missing folders among `packs`, `models`, `results` and `logs`. It never removes or renames anything. A layout name that exists as a file stops with an error.
- **`check_write_path(path, system)`.** Resolves the path, including symbolic links. For each Drive mount found, the path must be outside the mount or inside `<mount>/MyDrive/AQIS_LAB`. Otherwise it raises before anything is written.
- **`warn_if_crowded(folder, adding)`.** Before a lab write adds entries to a Drive folder, it counts the entries already there. If the result would pass 1,000, it prints one `WARNING:` line with the folder and the count. The write still happens (question 10).

### Copy then compute (`aqis_lab/runner/stage.py`)
- **Local layout.** `<work-dir>/packs/<manifest_id>/<version>/` holds `pack/` (the copied folder), `clips/` (the extracted members, at their manifest `member_path`) and `.staged`. The `.staged` marker records the manifest's canonical SHA-256, every archive's SHA-256 and the staging tool version.
- **Staging order.** Copy into `…/.staging-<pid>/`, verify, extract, check every clip, then rename into place. An interrupted staging leaves only a `.staging-*` folder, which is ignored and replaced on the next attempt.
- **Failure.** A failed verification reports every problem that `verify_pack` found, and nothing is staged.
- **Already staged.** A pack with a valid `.staged` marker and the same manifest SHA-256 is not copied again. Its clips are still hash-checked as the runner reads them.
- **Where the work folder may be.** It must be on local disk: a path on a Drive mount is refused (rule 40, "copy archives to local disk before processing").

### Runner (`aqis_lab/runner/`, `docs/runner/RUNNER.md`)
- **Command.** `python -m aqis_lab run --task clip-stats --pack <pack folder> --out <run folder> --seed <int> [--work-dir <dir>] [--shard-minutes 30] [--shard-clips N] [--max-shards N] [--from-scratch] [--drive-mount <mount>] [--notes TEXT]`. `--seed` is required: the run card needs one, and the lab never hides a missing input behind a default.
- **Task** (question 2). `clip-stats` version 1.0 reads each clip with `read_wav`, checks its SHA-256 against the manifest, and computes integers only:
  - `samples`, `sample_rate_hz`, `channels`;
  - `peak_abs`, `sum_samples`, `sum_squares`.

  Integers give the same bytes on every CPU and library build. The task declares its expected processing time per second of audio, measured on this VM with the command recorded in `RUNNER.md` and `EVIDENCE.md` (question 3). Tasks sit in a small registry, so WP-0.7 adds adapters without changing the runner.
- **Run card.** Built and validated with `validate_run_card` before anything runs:

  | Field | Value |
  | --- | --- |
  | `pack` | `manifest_id`, `version` and `sha256_canonical(manifest)` |
  | `model` | family `aqis-lab-task`, name `clip-stats`, version `1.0`, checksum null, settings `{}` |
  | `processing` | three empty lists |
  | `mode` | `batch` |
  | `machine` | `machine_block()` |
  | `seed` | from `--seed` |
  | `normaliser` | null (no text) |
  | `lock` | `requirements/aqis_lab/phase0.txt` and its SHA-256 |
  | `git` | full commit and the dirty flag, by the rule of the `version` command |
- **Shard plan.** Clips in manifest order are packed greedily. A shard closes when adding the next clip would pass `--shard-minutes` of expected work or `--shard-clips` clips. A single clip over the limit gets its own shard, and the log says so. `plan_id` is the SHA-256 of the canonical plan (run card ID, task, limits, the clip IDs of each shard).
- **Run folder** (`--out`, on Drive or local):

  | File | What it holds |
  | --- | --- |
  | `run_card.json` | The card |
  | `shard_plan.json` | The plan |
  | `shards/shard-NNNNN.jsonl` | One canonical-JSON row per clip, in manifest order. Each row carries `run_card_id` and `clip_id` |
  | `shards/shard-NNNNN.done.json` | The marker: plan ID, shard index, results SHA-256, bytes and row count, finished UTC, duration in monotonic nanoseconds, session number and that session's machine block |
  | `results.jsonl` | All shard files joined in order, written once every shard is finished |
  | `runner.log` | One line per event, UTC-stamped: session start with machine and plan, each shard skipped (with why it counts as finished) or started and finished, errors, the end |
- **Atomic write.** Write `name.partial`, fsync it, `os.replace` it to `name`, then fsync the folder. The results file is written before its marker. Every JSON file is re-read and checked after writing.
- **Resume.**
  - A run folder with no `run_card.json` starts a new run.
  - An existing card must equal the rebuilt card, apart from `created_utc`, `notes` and the resume rule for `machine` (question 4). The stored plan must equal the rebuilt plan. Otherwise the run stops with exit 2 and lists every difference.
  - Shards with a valid marker are skipped. A results file without a valid marker is recomputed and overwritten, and the log gives the reason.
- **`--from-scratch`.** Renames the old run folder to `<out>.superseded-<UTC>` and starts a new run. Nothing is deleted, which matters on Drive.
- **`--max-shards N`** (question 5). Stops cleanly after computing N shards in this session: exit 0, with a log line saying how many remain and how to continue.
- **Errors.** A clip that fails its hash check or cannot be read stops the run with exit 1. The error goes to `runner.log` and stderr, and that shard gets no marker. There are no partial results and no silent skips. Usage and input errors exit 2.
- **Not in this WP** (question 14): the runner does not write an event log in WP-0.5. The event-log v1 contract lets a resumed run continue its `seq` counter, and WP-0.7's adapters are the first components that emit events (FR-0.7-01). So the resumable event channel is designed with them, not ahead of them.

### Kill-and-resume test (FR-0.5-06)
- **Why the kill needs a fixed point.** The whole smoke pack takes about a second (finding 9). Killing "after k shards" by watching the clock would be a race and a flaky test.
- **How the test does it** (with `--shard-clips 10`, 6 shards):
  1. Stage the smoke pack.
  2. In the staged `clips/` folder, replace the first clip of shard k+1 with a named pipe (FIFO). The run blocks when it opens that clip.
  3. Start the real `run` command in a subprocess.
  4. Wait (60 s limit) until exactly k markers exist. The run cannot finish shard k+1, because its first clip never becomes readable, so no race is possible.
  5. Send SIGKILL.
  6. Put the real clip back. Its SHA-256 is checked when it is read.
  7. Run the same command again.
- **Assertions.**
  - The second session's log lists shards 0 to k−1 as skipped and k to 5 as computed.
  - Markers and result files of the first k shards are byte-identical, with the same inode and mtime.
  - `results.jsonl` is byte-identical to that of an uninterrupted run in another folder.
- **No test hooks.** The production code has none: the test only controls when one input file becomes readable.
- **Second test.** It leaves a `.partial` file and a results file without a marker, as a kill during writing would, and shows that neither counts as finished.

### Unit log (`aqis_lab/unitlog.py`)
- **`unitlog start --drive-mount <mount>`** runs right after installation in the launcher.
  - If `AQIS_LAB/logs/units_open_session.json` exists, a previous session never ran `end`. It is closed first: its row is appended with `end_basis=last-seen` and the end time the session last recorded (question 11).
  - It then records the new session: ID, start UTC, platform and GPU type from `aqis_lab.platform`.
- **Keeping `last_seen_utc` current.** `run` (after each shard) and `doctor` update it when `--drive-mount` is given.
- **`unitlog end`** appends the row with `end_basis=end-command`. A session is closed by appending its row; the open-session file is then rewritten (atomically) to say it is closed. It is never deleted, and no file is added per session.
- **CSV.** Header `session_id,platform,gpu_type,start_utc,end_utc,end_basis,hours,runtime,units_per_hour,estimated_units,rate_source`. `hours` and `estimated_units` are `decimal` values rounded half-even to 4 places; `runtime` is the rate key (`cpu` or the GPU type). The file is opened for append only, and a test proves the old bytes are a prefix of the new file.
- **`colab_rates.yaml`.** `schema_version`, then one entry per runtime (`cpu`, `Tesla T4`, …) with `units_per_hour` (a positive decimal written as a string) and `source` (non-empty). An unknown runtime type or a missing source is an error.

### Launcher notebook (`notebooks/aqis_lab/phase0_launcher.ipynb`)
| Cell | Content |
| --- | --- |
| 0 (markdown) | What the notebook does, the two secrets it needs, and a link to `docs/colab/COLAB_RUNBOOK.md` |
| 1 | Settings as literals: `AQIS_TAG`, `REPO`, `WORKDIR`, `DRIVE_MOUNT`, `RUN_OUT`, `RUN_ARGS`. Then `from google.colab import drive` and `drive.mount(DRIVE_MOUNT)` |
| 2 | Clone: read the token with `userdata.get("GITHUB_TOKEN")` and build the `Authorization` header. `subprocess.run(["rm", "-rf", WORKDIR], check=True)` gives a fresh clone. Then `subprocess.run(["git", "clone", "--depth", "1", "--branch", AQIS_TAG, REPO, WORKDIR], env=dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0=header, GIT_TERMINAL_PROMPT="0"), check=True)`, then `del token, header` |
| 3 | Install the lock: `pip install uv==0.8.17`, then `bash aqis_lab/deploy/dev_bootstrap.sh`, both with `check=True` |
| 4 | Lab commands: `unitlog start`, `drive layout`, `doctor --target colab --drive-mount DRIVE_MOUNT --out <AQIS_LAB>/logs`, `run --task clip-stats --pack data/packs/smoke/v1 --out RUN_OUT --seed 0 *RUN_ARGS` |
| 5 | `unitlog end` |

- **Token handling.** The token reaches only the clone command, through git's `GIT_CONFIG_*` environment variables. It is never part of a URL, `.git/config`, the command line or any output. `check=True` makes a failed clone stop the cell, and the error shows the command line, which holds no token. So no `if` is needed.
- **Where things go.** The lab code runs from `WORKDIR` on local disk. The work folder is local; the doctor JSON, run folder and unit log go to Drive under `AQIS_LAB`.
- **Tag** (question 12). The static test also checks that `AQIS_TAG` is assigned exactly once, in cell 1, to a string literal, and that every `python -m aqis_lab` command in the notebook exists and its arguments parse.

### Colab runbook (`docs/colab/COLAB_RUNBOOK.md`)
- Before you start: the `AQIS_LAB` folder, the `GITHUB_TOKEN` secret (fine-grained, read-only Contents, this repository only) and the tag.
- Opening and running the launcher, and what each cell prints.
- The Drive layout and the 1,000-item warning.
- Doctor minimums (the same table as `DOCTOR.md`).
- The unit log and how the estimate is made.
- The exact OC-0.5-01 and OC-0.5-02 procedures, and where to commit their outputs.
- What to do when a check fails: commit the output and run `/surgical-fix` in a session; do not debug in Colab.

### Must-catch proof (planned)
| # | Behaviour | Tests that must fail when it is broken |
| --- | --- | --- |
| 1 | `doctor` fails on another Python, packages that differ from the lock, and a missing or read-only Drive folder | `test_FR_0_5_02_fails_on_python_version_other_than_probe`, `…_fails_on_package_version_other_than_lock`, `…_fails_on_package_missing_from_lock`, `…_fails_on_lock_package_not_installed`, `…_colab_fails_when_aqis_lab_missing`, `…_colab_fails_when_aqis_lab_read_only` |
| 2 | After an interruption, finished shards are skipped and results are byte-identical | `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing`, `test_FR_0_5_05_restart_skips_finished_shards` |
| 3 | A shard without its marker never counts as finished | `test_FR_0_5_05_results_without_marker_not_finished`, `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished`, `test_FR_0_5_06_kill_during_result_write_never_counts` |
| 4 | The launcher has no logic beyond the allowed steps | `test_FR_0_5_08_launcher_cells_contain_no_logic`, `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form` |
| 5 | Platform details come from `aqis_lab.platform` only | `test_FR_0_5_01_platform_details_only_from_platform_module`. It scans `aqis_lab/**.py` and `tools/**.py`, apart from `aqis_lab/platform.py`, for `platform.` machine-fact calls, `os.uname`, `sys.version`, `sys.platform`, `shutil.disk_usage`, `os.statvfs`, and the strings `nvidia-smi`, `/proc/`, `/sys/class/dmi`, `os-release`, `lscpu`, `COLAB_`, `KAGGLE_`, `GITHUB_ACTIONS` and `CLAUDE_CODE_REMOTE`, with the allow-list of question 7 |
| 6 | The unit log appends a correct estimate from the rate table | `test_FR_0_5_07_appends_row_with_estimate_from_rate_table`, `test_FR_0_5_07_unknown_runtime_type_is_an_error` |

### Parts that do not depend on owner inputs
- Build first: the runner (FR-0.5-04 to FR-0.5-06, NFR-0.5-01), the Drive layout and guard (FR-0.5-03, NFR-0.5-02), the unit-log code and its tests using generated rate tables, the notebook and its static test, and the doctor checks that do not need Colab facts.
- Wait for owner need 3: the Colab detection signal, the Drive mount type and the Colab minimum values.
- Wait for owner need 2: the committed `colab_rates.yaml`.

If either is missing when I reach it, I record a blocker and stop only that part.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to questions 1 to 14 below, as CONDITIONS in `docs/approvals/WP-0.5.md` (or "as recommended") | They fix the runner's workload, resume rules, detection signals, minimums and the Colab procedures | Before `/wp-build WP-0.5` |
| 2 | **The Colab unit rates from the Build Plan** ("Resource plan"): compute units per hour for each runtime type the lab uses (at least CPU and T4; also L4 and A100 if the Build Plan gives them), with the source the Build Plan cites and its date. Paste them into the approval CONDITIONS, or commit the Build Plan's "Resource plan" section under `docs/` | FR-0.5-07 requires "the Build Plan's figures with their source". They are not in the repository, and I must not invent them | Before the `colab_rates.yaml` step of the build; the rest of FR-0.5-07 goes ahead |
| 3 | **Colab platform probe**, about 2 minutes: the two cells under "Colab platform probe" below. Commit the output as `docs/environment/colab_platform_probe.txt` on `main` | It confirms the Colab detection signal, whether CPU runtimes have `nvidia-smi`, how Drive appears as a mount, and Colab's free disk and RAM for the doctor minimums, so none of these is guessed | Before the build of FR-0.5-01 and the Colab checks of FR-0.5-02 |
| 4 | For WP-0.6's `oracle_probe.txt`, please add `cat /sys/class/dmi/id/chassis_asset_tag` to the Oracle probe command | It confirms the Oracle detection signal on the real VM | WP-0.6 (OC-0.6-01) at the latest; not blocking here |
| 5 | Google Drive folder `MyDrive/AQIS_LAB`, and the `GITHUB_TOKEN` Colab secret (fine-grained, read-only Contents access to this repository only; you may already have it from WP-0.0) | The launcher mounts Drive and clones the private repository | Before OC-0.5-01 |
| 6 | The Colab owner-run checks below, after the audit passes | OC-0.5-01, OC-0.5-02 | Before merging |

### Colab platform probe (owner need 3)
New Colab notebook on a CPU runtime. First cell (Python):
```python
from google.colab import drive
drive.mount("/content/drive")
```
Second cell (the whole cell runs in bash, so nothing in it is changed by the notebook):
```bash
%%bash
env | cut -d= -f1 | grep -i -E "colab|kaggle|gpu" | sort
which nvidia-smi; nvidia-smi --query-gpu=name --format=csv,noheader; echo "nvidia-smi exit $?"
grep -m1 "model name" /proc/cpuinfo; lscpu | grep "Model name"
grep -i drive /proc/self/mountinfo
ls -ld /content/drive/MyDrive/AQIS_LAB
df -h /content | tail -1; free -g | head -2
```
It prints only environment variable names, never their values. A second run on a T4 runtime is welcome but optional.

No network allowlist change is needed: WP-0.5 downloads nothing on the cloud VM. Colab needs PyPI (for `uv`) and GitHub, which it already reaches.

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| OC-0.5-01 | Colab, CPU runtime | Set `AQIS_TAG` in cell 1 (question 12). Run cells 1 to 4 with `RUN_ARGS = ["--shard-clips", "10"]`. Then, in one extra cell: `!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab` | The doctor table shows `platform`, `python`, `lock`, `disk`, `ram`, `drive-mount` and `drive-folder` PASS, and `gpu` SKIP; exit 0. The pytest line ends with `passed` and nothing failed. Commit `AQIS_LAB/logs/doctor_colab_<timestamp>.json` to `docs/environment/`, and the pytest output as `docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt` |
| OC-0.5-02 | Colab, same notebook | 1. Cell 1 with `RUN_ARGS = ["--shard-clips", "10", "--max-shards", "2"]`; run all cells. <br>2. **Runtime → Disconnect and delete runtime**. <br>3. Reconnect, set `RUN_ARGS = ["--shard-clips", "10"]`, run all cells again | The first pass's `runner.log` shows 2 of 6 shards finished and "4 remaining". The second pass shows `shard 00000 skipped` and `shard 00001 skipped`, then shards 2 to 5 computed and `results.jsonl` written. Commit `AQIS_LAB/results/wp05-smoke-clip-stats/runner.log` as `docs/progress/WP-0.5/OC-0.5-02_runner.log`, and `AQIS_LAB/logs/units.csv` as `docs/progress/WP-0.5/OC-0.5-02_units.csv` |

## Risks and questions
### Questions for you
1. **(FR-0.5-07) Colab unit rates.** The spec wants the Build Plan's figures with their source. I do not have the Build Plan.
   - **(a) Needed from you:** the figures and their source (owner need 2).
   - **(b)** Tell me which public source to take them from. I then record that source and date instead of the Build Plan.

   I have no recommendation of my own numbers, because I will not invent them.
2. **What the runner runs in WP-0.5.** There is no model until WP-0.7, but FR-0.5-05, FR-0.5-06, NFR-0.5-01 and OC-0.5-02 need a real run on the smoke pack.
   - **(a) Recommended:** a built-in `clip-stats` task, described under "Runner". It is real work (it reads, checks and measures every clip), integer-only, and so byte-identical everywhere, which also makes it an early cross-machine check of the pack itself. WP-0.7's adapters plug into the same task registry.
   - **(b)** No built-in task. Tests define a task inside `tests/`, and OC-0.5-02 moves to WP-0.7, where Vosk gives a long enough run. That is a deviation from the spec's owner-run checks.
3. **Shard size.** "30 minutes of expected work" needs an estimate per clip.
   - **(a) Recommended:** expected work = clip duration × the task's processing-time ratio. The ratio is measured on this VM and recorded with its command. `--shard-minutes` (default 30) and `--shard-clips` (optional) both limit a shard.
   - **(b)** Shard by audio minutes only, ignoring processing speed. This does not match "expected work".
4. **Resuming on a new Colab runtime.** "Disconnect and delete runtime" gives a new machine and wipes local disk; Colab CPU models vary between runtimes. `machine` is part of the run card and its ID.
   - **(a) Strict:** resume only when the rebuilt card is identical. On Colab, a resume after a new runtime would often be refused and need `--from-scratch`.
   - **(b) Recommended:** resume when everything but `machine.cpu_model` is identical: same platform, GPU type, architecture, OS and Python, and same pack, task, seed, lock and commit. The stored card keeps the first session's machine block. Every marker records the machine that computed its shard, and `runner.log` lists each session's machine. A different GPU type, architecture, OS or Python is refused.
   - **(c)** Resume on any machine, recording each one. Too loose for timing runs later.
5. **OC-0.5-02 "disconnect partway".** The smoke run takes about a second (finding 9), so no one can disconnect in the middle of it.
   - **(a) Recommended:** add `--max-shards N` (addition D5), a normal operator option that also helps fit long runs into Colab's session limits. The owner check stops after 2 of 6 shards, disconnects and deletes the runtime, then resumes (see "Owner-run checks planned").
   - **(b)** Keep OC-0.5-02 as written and try to disconnect within the second. This is not a repeatable check.
   - **(c)** Move OC-0.5-02 to WP-0.7 (deviation).
6. **Platform signals** (see "Platform").
   - **(a) Recommended:**
     - `COLAB_RELEASE_TAG` for Colab, confirmed by owner need 3 before I build it;
     - `KAGGLE_KERNEL_RUN_TYPE` for Kaggle, not checkable in phase 0 (risk 3);
     - the DMI asset tag `OracleCloud.com` for Oracle, confirmed in WP-0.6;
     - for `cloud-vm`, this Claude Code cloud session (`CLAUDE_CODE_REMOTE=true`) **and the GitHub Actions runner** (`GITHUB_ACTIONS=true`).

     The CI runner is another no-GPU Ubuntu cloud VM that runs the same fast suite. The run card's platform list has no other value for it, and without it every CI test that builds a run card or runs the doctor would fail. The doctor JSON records which signal matched.
   - **(b)** Treat CI as unknown: tests needing a real machine block would then need a separate marker and would not run in CI.
7. **Existing platform-detail code** (finding 4) and must-catch 5.
   - **(a) Recommended:** leave `harness_provision.py` (`check_platform`), `version.py` (`version_line`) and the two shell scripts unchanged. The must-catch 5 test carries an explicit allow-list naming exactly those lines, with reasons:
     - the harness check guards provisioning before any lab environment exists;
     - `version` prints the interpreter's version as tool output, not a run's machine facts;
     - the shell scripts run before any Python environment exists.

     All run cards, doctor reports and unit-log rows take their facts from `aqis_lab.platform`.
   - **(b)** Change those two Python files to call `aqis_lab.platform`. This touches merged, audited WP-0.0 code: a larger change budget and new tests there.
8. **Doctor minimums** ("documented minimums"; the spec gives no values).
   - **(a) Recommended, unless the Build Plan's "Resource plan" gives figures:** free disk ≥ 10 GB on the work folder's file system and available RAM ≥ 4 GB, the same on all three targets. They go in `config/aqis_lab/doctor.yaml`, `DOCTOR.md` and the runbook.
     - This VM has 30 GB free and 15 GB available, so it passes with a wide margin.
     - I will check the values against owner need 3 (Colab) before building.
     - WP-0.7 may raise them for its GPU extras, and WP-0.6 checks them on Oracle.
   - **(b)** Your figures.
9. **(D1) "Python version equals the Colab probe's".** This VM has 3.13.12 and Colab 3.13.15. Rule 40, which ranks above the spec, pins exactly the major.minor.
   - **(a) Recommended:** compare major.minor (3.13 = 3.13) and show both full versions in the report. A different major.minor fails (must-catch 1).
   - **(b)** Compare the full version. AT-0.5-01 would then fail on this VM and on CI, and I would have to stop.
10. **"Warns before any folder exceeds 1,000 items".**
    - **(a) Recommended:** before a lab write would make a Drive folder hold more than 1,000 entries, print one warning and still write. `drive layout` also warns about every folder already over 1,000.
    - **(b)** As (a), plus an early warning from 900 entries.
    - **(c)** Refuse such writes. This is stricter than "warns".
11. **Unit log session start and end.** Colab sessions often end by timeout or disconnect, with no chance to run a last cell.
    - **(a) Recommended:**
      - `unitlog start` right after installation records the start.
      - `unitlog end` in the last cell appends the row.
      - `run` and `doctor` keep a "last seen" time in `AQIS_LAB/logs/units_open_session.json`.
      - A session that never reached `end` is closed at the next `start` with end = last seen, marked `end_basis=last-seen`.

      The estimate undercounts the few minutes before `start`, and any idle time after the last command. The runbook says so.
    - **(b)** Only `start` and `end`. A session that dies without `end` gets no row.
12. **The pinned tag.**
    - **(a) Recommended:** once the audit passes, I create and push an annotated tag `aqis-lab-wp-0.5-colab-1` on the branch head. The committed notebook's `AQIS_TAG` already names it. You run the checks from exactly that commit. A later fix gets `-colab-2`.
    - **(b)** You create tags yourself on GitHub, and I leave `AQIS_TAG` for you to fill in.

    Both use git's `GIT_CONFIG_*` variables for the token (as in "Launcher notebook") and remove any old local clone first. The removal is local disk only, never Drive.
13. **Accepted debt that targets WP-0.5** (finding 12). Both would be test-only additions in a new file, `tests/aqis_lab/test_aqis_debt_wp05.py`; no existing test or production file changes.
    - **(a) Recommended: include both:**
      - **DEBT-009:** run `score` with a real installed-package record of another `whisper-normalizer` version placed first on the import path. Assert `ERROR:` and exit 2, and that the normaliser checks the version on first use.
      - **DEBT-011:** a generated registry where most candidates share a speaker. Assert one clip per speaker per category.

      If either test reveals a defect in merged code, I stop and ask rather than fix it.
    - **(b)** Leave them for WP-0.9.
14. **(Additions D2 to D8) Beyond the spec's deliverables.** Approving these accepts them:
    - **D2: the command names** `run`, `drive layout` and `unitlog start|end`.
    - **D3: the extra files** `aqis_lab/drive.py`, `aqis_lab/commands/{doctor,drive,run,unitlog}.py`, `config/aqis_lab/doctor.yaml`, `docs/doctor/DOCTOR.md` and `docs/runner/RUNNER.md`.
    - **D4: the doctor `platform` row.** It FAILs when `--target` is not this machine.
    - **D6: default local folders** under the git-ignored `data/raw/aqis_lab/` (`work/`, `doctor/`), so running commands from the repository root never makes the tree dirty.
    - **D7: no runner event log in WP-0.5** (see "Runner").
    - **D8: an extra step in OC-0.5-01**, the `pytest -m colab` cell.

    D5 is `--max-shards` (question 5).

    **Recommended: accept all.**

### Design decisions made in this plan (approving the plan accepts them)
- **One module for machine facts.** Every fact about the machine, including disk, RAM and mounts, comes from `aqis_lab.platform` through one `SystemView`. Tests pass generated trees; production code never checks whether it is under test.
- **No default when detection fails.** An unknown platform or a failing `nvidia-smi` is an error, never `cloud-vm` or "no GPU".
- **Clips checked twice.** Clips are hash-checked when staged and again when read.
- **Run folder safety.** Run folders are never deleted: `--from-scratch` renames. Shard outputs use write, fsync, rename and fsync of the folder. A marker proves its results file by SHA-256, so even a file system with weak rename guarantees, such as Drive, cannot make a shard look finished when it is not.
- **Result bytes.** Result rows are canonical JSON (sorted keys, no spaces), integer-valued for `clip-stats`, in manifest order.
- **Run exit codes.** 0 done (or stopped by `--max-shards`), 1 a clip failed, 2 usage or input error. Doctor exit codes: 0, 1 (any FAIL), 2.
- **Timestamps.** UTC with `Z` in files, `YYYYMMDDTHHMMSSZ` in file names. Durations use the monotonic clock in nanoseconds.
- **Notebook shape.** The launcher uses plain Python with `subprocess.run(..., check=True)`, never `!` magics, which do not stop a cell on failure (precedent: FR-0.0-13).

### Other risks
1. **NFR-0.5-01 on a sub-second workload.**
   - `clip-stats` with `numpy` should take about 0.1 s on the smoke pack. The runner's fixed costs (card, plan, marker, log, final results: about 5 atomic writes of 0.6 ms each, finding 10) could come close to 5 % of that.
   - I will measure honestly, with fsync on in both loops and the default single shard. If the overhead is 5 % or more, I will **stop and ask**. I will not slow the task, drop fsyncs or change the comparison.
2. **Drive behaviour cannot be tested here.** Atomic rename, fsync and mount type on Colab's Drive are covered by a Drive test double on this VM, and by OC-0.5-01 and OC-0.5-02 on real Colab. The marker's SHA-256 keeps a weak rename from ever producing a false "finished".
3. **Kaggle and Oracle signals.** Kaggle cannot be checked in phase 0 (no Kaggle check in any spec). Oracle is checked in WP-0.6 (owner need 4). If the Oracle probe disagrees, the fix is one signal in `aqis_lab.platform`, made with `/surgical-fix`.
4. **Colab runtime types.** TPU runtimes have no `nvidia-smi` and would be logged as `cpu`. Phase 0 uses CPU and T4 runtimes only; the runbook says so.
5. **Two runners on one run folder** (for example two browser tabs on Colab) could interleave writes. The spec does not ask for locking, and Drive's lock support is unknown, so the runbook warns against it. Markers still make every counted shard provably complete.
6. **Name `aqis_lab.platform`.** Inside the package, `import platform` still means the standard library (absolute imports), so existing modules are unaffected. A script run directly from inside `aqis_lab/` would see the lab module instead; nothing does that.
7. **The token.** While `git clone` runs, it sits in the environment of that process. That is the same exposure as the command-line approach of FR-0.0-13, on a single-user Colab machine. The runbook asks for a read-only, single-repository token.

## Deviations
- **D1**: the Python check compares major.minor, as rule 40 requires, where the spec says "equals" (question 9).
- **D2 to D8**: additions beyond the listed deliverables (questions 5 and 14).
- **Possible, depending on your answers:** question 2 (b) or 5 (c) would move OC-0.5-02 to WP-0.7. Question 1 cannot be met from the spec alone and needs your figures.

Everything else fills in something the spec leaves open and is listed under "Design details" and "Design decisions"; none of it contradicts the spec.

## Measurements
| What | Command | Result |
| --- | --- | --- |
| Python on this VM | `python3.13 --version` | `Python 3.13.12` (Colab probe: 3.13.15) |
| Machine | `lscpu`, `free -g`, `df -h /`, `nproc`, `uname -m` | Intel(R) Xeon(R) Processor @ 2.80GHz, 4 CPUs, 15 GB available, 30 GB free, x86_64 |
| Read-only folder as root | `chmod 0555` folder; `touch` as root; `setpriv --bounding-set -dac_override,-dac_read_search -- python3 -c "open(...,'w')"` | root write succeeds; with the override removed: `PermissionError: [Errno 13] Permission denied` |
| Smoke pack pass | plain-Python read, SHA-256 and sum of squares over all 60 members | 6,254,961 samples in 0.44 s |
| Atomic write | 50 × (write 2 KB, fsync, `os.replace`, fsync folder) in the scratchpad | median 0.608 ms, p90 0.788 ms |
