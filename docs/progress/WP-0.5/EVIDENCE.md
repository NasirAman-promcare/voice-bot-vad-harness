# EVIDENCE — WP-0.5

Environment:
- cloud VM (Ubuntu 24.04.4 LTS, x86_64, 4 vCPUs, "Intel(R) Xeon(R) Processor @ 2.80GHz"), Python 3.13.12 in `.venv` (Colab probe: 3.13);
- lock `requirements/aqis_lab/phase0.txt` sha256 `84151d8f77b8512288620fdb82325fc2b22551da77324e171b7cdf055d732acc` (unchanged by this WP);
- branch `claude/magical-goldberg-kjvw5r`;
- approval `docs/approvals/WP-0.5.md` on `main`: questions 2 to 14 as recommended. The Colab unit rates come from the Build Plan (March 2026): cpu 0.08, Tesla T4 1.19, NVIDIA L4 1.71, NVIDIA A100-SXM4-40GB 5.40 units per hour. Source: "AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026)";
- Colab facts: `docs/environment/colab_platform_probe.txt` on `main`:
  - `COLAB_RELEASE_TAG` is set;
  - no `nvidia-smi` on a CPU runtime (exit 127);
  - CPU "Intel(R) Xeon(R) CPU @ 2.20GHz";
  - Drive mounted at `/content/drive` with type `fuse.drive`;
  - 206 GB free disk and 11 GB available RAM.

Baseline before any change (change-control step 3, for `aqis_lab/__main__.py` and the registry): `bash aqis_lab/deploy/dev_bootstrap.sh`, then the fast suite: `1365 passed, 14 deselected in 185.57s`.

All test outputs below are real excerpts from this session. Fast command, per requirement:
`.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network" -k <ID>`.

## Requirements
### FR-0.5-01 — Platform detection and machine facts
- Tests (`tests/aqis_lab/test_aqis_platform.py`):
  - `test_FR_0_5_01_detects_each_platform_from_its_signal` (5 cases);
  - `test_FR_0_5_01_unknown_platform_is_an_error` (4 cases);
  - `test_FR_0_5_01_conflicting_signals_are_an_error`;
  - `test_FR_0_5_01_gpu_type_from_nvidia_smi_else_null` (4 cases; stand-in `nvidia-smi`, the GPU test double);
  - `test_FR_0_5_01_failing_nvidia_smi_is_an_error`;
  - `test_FR_0_5_01_cpu_model_from_cpuinfo_or_lscpu`;
  - `test_FR_0_5_01_os_from_os_release`;
  - `test_FR_0_5_01_memory_disk_and_mount_facts`;
  - `test_FR_0_5_01_real_machine_facts`;
  - `test_FR_0_5_01_machine_block_valid_in_run_card`;
  - `test_FR_0_5_01_platform_details_only_from_platform_module` (must-catch 5; allow-list per question 7 (a)).
- Colab-only test: `test_FR_0_5_01_colab_runtime_detected` in `tests/aqis_lab/test_aqis_colab_live.py` (marker `colab`, OC-0.5-01).
- Test-first: before `aqis_lab/platform.py` existed, collection failed with `ImportError: cannot import name 'platform' from 'aqis_lab'`.
- Command: the fast command with `-k FR_0_5_01`.
```text
.....................                                                    [100%]
21 passed, 1380 deselected in 2.01s
```
- Real machine block on this VM (`.venv/bin/python -c "from aqis_lab import platform as p; print(p.machine_block()); print(p.machine_info().signals)"`):
```text
{'platform': 'cloud-vm', 'gpu': None, 'cpu_model': 'Intel(R) Xeon(R) Processor @ 2.80GHz', 'architecture': 'x86_64', 'os': 'Ubuntu 24.04.4 LTS', 'python_version': '3.13.12'}
('environment variable CLAUDE_CODE_REMOTE=true',)
```
- The Colab-only test fails here, as it must off Colab (`-m colab`): `1 failed, 1400 deselected`.
- Fast suite after FR-0.5-01 (the FR-0.5-02 test file, written next and not yet committed, set aside):
  - `1 failed, 1385 passed, 15 deselected in 190.00s`;
  - the one failure was `test_FR_0_0_04_lab_tests_use_only_registered_markers`, caused only by that uncommitted file's import error;
  - with the file set aside: `tests/aqis_lab/test_aqis_markers.py`, `5 passed in 4.63s`.
- Registry: rows CAP-PLAT-001 to CAP-PLAT-003. The first run caught a header/registry mismatch (`test_FR_0_0_08_module_headers_match_registry`); the header now lists the Colab test too.
- Status: DONE

### FR-0.5-02 — Doctor
- Tests (`tests/aqis_lab/test_aqis_doctor.py`):
  - `test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json`;
  - `test_FR_0_5_02_fails_on_python_version_other_than_probe`, `test_FR_0_5_02_fails_on_package_version_other_than_lock`, `test_FR_0_5_02_fails_on_package_missing_from_lock`, `test_FR_0_5_02_fails_on_lock_package_not_installed` (must-catch 1);
  - `test_FR_0_5_02_fails_below_disk_minimum`, `test_FR_0_5_02_fails_below_ram_minimum`;
  - `test_FR_0_5_02_gpu_skipped_without_expect_gpu`, `test_FR_0_5_02_expect_gpu_fails_without_gpu`, `test_FR_0_5_02_expect_gpu_passes_with_gpu`;
  - `test_FR_0_5_02_fails_when_target_is_not_this_platform`;
  - `test_FR_0_5_02_colab_fails_when_drive_not_mounted`, `test_FR_0_5_02_colab_fails_when_aqis_lab_missing`, `test_FR_0_5_02_colab_fails_when_aqis_lab_read_only` (must-catch 1; run as root under `setpriv --bounding-set -dac_override,-dac_read_search`, so the folder's mode applies), `test_FR_0_5_02_colab_drive_checks_pass_when_writable`;
  - `test_FR_0_5_02_any_fail_exits_non_zero`, `test_FR_0_5_02_minimums_documented_equal_config`.
- Colab-only test: `test_FR_0_5_02_colab_doctor_passes_on_colab` (marker `colab`, OC-0.5-01).
- Test-first: before `aqis_lab/doctor.py` existed, collection of the test file failed (`1 error during collection`), and the whole fast suite stopped with `Interrupted: 1 error during collection`.
- New files:
  - `aqis_lab/doctor.py`, `aqis_lab/commands/doctor.py`;
  - `aqis_lab/drive.py`: the write guard and atomic writes that every lab write uses;
  - `config/aqis_lab/doctor.yaml`: minimums of 10 GB disk and 4 GB RAM on every target, owner decision, question 8 (a);
  - `docs/doctor/DOCTOR.md`.
- Existing file changed: `aqis_lab/__main__.py`, one `COMMANDS` entry and one CHANGE LOG line (see "Changes to existing files" below).
- Plan detail made concrete: the Drive write check file is `AQIS_LAB/doctor_write_check.json`, at the top of `AQIS_LAB` (the plan said `logs/`). The check then does not depend on `drive layout` having run first. It is still one reused file that is never deleted.
- Command: the fast command with `-k FR_0_5_02` → `17 passed, 1408 deselected in 4.02s`.
- AT-0.5-01 run (see "Acceptance commands"): exit 0; every row PASS, `gpu` SKIP.
- Two real catches while building:
  - The first registry row for the doctor command held `\|` inside a cell, which the gate reads as a cell border (E2, caught by `test_FR_0_0_08_repository_registry_is_consistent`).
  - My must-catch 5 scan caught the words `nvidia-smi` and `COLAB_` (in a doc file name) in the new modules. The module text was reworded; the scan was not loosened.
- Status: DONE

### FR-0.5-03 — Drive layout
- Tests (`tests/aqis_lab/test_aqis_drive.py`; Google Drive replaced by a folder and a generated `fuse.drive` mountinfo line):
  - `test_FR_0_5_03_creates_missing_layout_folders`;
  - `test_FR_0_5_03_never_deletes_or_changes_existing_content` (full snapshot of names, modes and bytes before and after);
  - `test_FR_0_5_03_refuses_when_aqis_lab_missing`;
  - `test_FR_0_5_03_layout_name_that_is_a_file_is_an_error`;
  - `test_FR_0_5_03_warns_before_folder_exceeds_1000_items` (boundary: 999 → 1,000 entries, no warning; 1,000 → 1,001, one warning and the file is still written; replacing a file, a folder on local disk: no warning);
  - `test_FR_0_5_03_layout_reports_crowded_folders`.
- Code: `ensure_layout`, `crowded_folders` and `warn_if_crowded` in `aqis_lab/drive.py`. `warn_if_crowded` is called by `write_bytes`, `append_bytes` and `make_dirs` before they add an entry. `aqis_lab/commands/drive.py` provides `drive layout`.
- **Order of work (stated plainly):** I wrote these tests before the code, but first ran them after implementing. To show they fail for the right reason, I ran them against a scratch copy of the tree with `ensure_layout`, `LayoutResult`, `crowded_folders` and the `warn_if_crowded` calls removed:
```text
E       AttributeError: module 'aqis_lab.drive' has no attribute 'ensure_layout'
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_creates_missing_layout_folders
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_never_deletes_or_changes_existing_content
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_refuses_when_aqis_lab_missing
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_layout_name_that_is_a_file_is_an_error
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_warns_before_folder_exceeds_1000_items
FAILED tests/aqis_lab/test_aqis_drive.py::test_FR_0_5_03_layout_reports_crowded_folders
6 failed in 0.78s
```
- Command: the fast command with `-k "FR_0_5_02 or FR_0_5_03"` → `23 passed, 1402 deselected in 5.17s`.
- FR-0.5-02 and FR-0.5-03 are committed together: the FR-0.5-03 crowding warning sits inside the FR-0.5-02 write functions of `aqis_lab/drive.py`.
- Fast suite after both: `1409 passed, 16 deselected in 206.81s (0:03:26)`.
- Status: DONE

### FR-0.5-04 — Copy then compute
- Tests (`tests/aqis_lab/test_aqis_stage.py`):
  - `test_FR_0_5_04_stages_repository_pack_to_local_disk`;
  - `test_FR_0_5_04_stages_pack_from_drive_folder` (Drive test double);
  - `test_FR_0_5_04_rejects_changed_archive_and_stages_nothing`;
  - `test_FR_0_5_04_interrupted_staging_is_redone`;
  - `test_FR_0_5_04_restaging_a_staged_pack_copies_nothing`;
  - `test_FR_0_5_04_run_reads_only_local_extracted_clips` (the source archives are overwritten after staging; the run still gives the reference results);
  - `test_FR_0_5_04_work_dir_on_drive_is_refused`;
  - `test_FR_0_5_04_changed_extracted_clip_stops_the_run`.
- Test-first: before `aqis_lab/runner/` existed, collection failed with `ModuleNotFoundError: No module named 'aqis_lab.runner'` (this file and the FR-0.5-05 and FR-0.5-06 files).
- Code: `aqis_lab/runner/stage.py`, reusing `verify_pack` (WP-0.4, unchanged) on the local copy before anything is extracted.
- Status: DONE (fast command output under FR-0.5-06)

### FR-0.5-05 — Resumable runner
- Tests (`tests/aqis_lab/test_aqis_runner.py`):
  - `test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work` (expected shards computed in the test by its own greedy rule);
  - `test_FR_0_5_05_shard_size_is_configurable`;
  - `test_FR_0_5_05_shard_results_written_atomically_with_marker`;
  - `test_FR_0_5_05_results_without_marker_not_finished` (must-catch 3);
  - `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished` (4 cases, must-catch 3);
  - `test_FR_0_5_05_restart_skips_finished_shards`;
  - `test_FR_0_5_05_starting_over_requires_from_scratch`, `test_FR_0_5_05_from_scratch_keeps_old_run_folder`;
  - `test_FR_0_5_05_changed_card_or_plan_refused`;
  - `test_FR_0_5_05_resume_rule_for_other_cpu_model` (question 4 (b));
  - `test_FR_0_5_05_run_card_valid_and_traceable` (expected pack hash, lock hash and git commit computed in the test);
  - `test_FR_0_5_05_result_rows_carry_run_card_and_clip_ids` (clip statistics recomputed in the test with `wave` and `array`);
  - `test_FR_0_5_05_clip_failure_stops_run_without_marker`;
  - `test_FR_0_5_05_max_shards_stops_cleanly` (question 5);
  - `test_FR_0_5_05_runner_doc_matches_code`.
- Code: `aqis_lab/runner/tasks.py`, `card.py`, `plan.py`, `store.py`, `run.py`, `aqis_lab/commands/run.py`, `docs/runner/RUNNER.md`. Existing file changed: `aqis_lab/__main__.py`, one `COMMANDS` entry and one CHANGE LOG line.
- Expected-work ratio of `clip-stats`, measured with the script in `docs/runner/RUNNER.md` ("Expected work"):
```text
audio 390.935 s; passes [0.0638, 0.0697, 0.0652, 0.0637, 0.0661, 0.0709, 0.0735]; median 0.0661 s; ratio 0.000169
```
- Catches while building:
  - `test_FR_0_5_05_runner_doc_matches_code` found that `RUNNER.md` did not name the plan fields `task` and `shards`; the doc was fixed.
  - The test's own regular expression first left out digits (`results_sha256`) and was corrected.
- Plan acceptance command, the same run twice (`--out` and `--work-dir` in the scratchpad; machine JSON shortened to `{...}`):
```text
2026-09-28T09:22:22.946805Z run complete: 6 shard(s), 0 skipped and 6 computed in this session; results.jsonl sha256 5ac0fa121384d459d6d3155b25302047c5f4f2e8d5583e6669ec5b0b78df21cc (60 rows)
complete: 6 shard(s) computed, 0 skipped, 0 remaining
exit 0
2026-09-28T09:22:23.497769Z session 2 start: task clip-stats 1.0; pack smoke 1.0.0; run card d344a4efd7c34463a4b59bef8697f19c7f6b75fb866c1d3169f5c3dec6bde8aa; plan 2c89d1e222459c6250b4bb47ea038788e1a1510df1a4bec880f9865b2b4f86f2 with 6 shard(s); machine {...}
2026-09-28T09:22:23.499822Z shard 00000 skipped: finished (marker verified, results sha256 e2a0a63fa39a09023a66612ca3c7a81bf2ec5d0043cc0c7a5919b344f50520c7, 10 rows)
…
2026-09-28T09:22:23.507217Z shard 00005 skipped: finished (marker verified, results sha256 ec9f595ecd755f2121666cfa9680249c82910dc1f8ee7502251cf0408c098fca, 10 rows)
2026-09-28T09:22:23.511668Z run complete: 6 shard(s), 6 skipped and 0 computed in this session; results.jsonl sha256 5ac0fa121384d459d6d3155b25302047c5f4f2e8d5583e6669ec5b0b78df21cc (60 rows)
complete: 0 shard(s) computed, 6 skipped, 0 remaining
exit 0
```
- The plan's wording "`6 shard(s) skipped`" appears in the log as `6 skipped and 0 computed`, and as one `skipped` line per shard.
- Status: DONE

### FR-0.5-06 — Kill and resume
- Tests (`tests/aqis_lab/test_aqis_runner_resume.py`):
  - `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` (must-catch 2). The first clip of shard 3 becomes a named pipe, the real run is SIGKILLed once exactly 3 markers exist, then it is resumed.
    - Asserted: `results.jsonl` is byte-identical to an uninterrupted run's.
    - Asserted: the 6 files of shards 0 to 2 keep their bytes, inode and mtime.
    - Asserted: the second session's log skips shards 0 to 2 and starts shards 3 to 5.
  - `test_FR_0_5_06_kill_during_result_write_never_counts`: a half-written `.partial` file, a results file without a marker, and a deleted `results.jsonl`.
- Repeated 5 times to check it is deterministic: `2 passed` each time (4.12 to 5.24 s).
- Command: the fast command with `-k "FR_0_5_04 or FR_0_5_05 or FR_0_5_06"`:
```text
28 passed, 1425 deselected in 16.38s
```
- Fast suite after FR-0.5-04 to FR-0.5-06: `1437 passed, 16 deselected in 212.38s (0:03:32)`.
- Status: DONE

### FR-0.5-07 — Unit log
- Tests (`tests/aqis_lab/test_aqis_unitlog.py`):
  - `test_FR_0_5_07_appends_row_with_estimate_from_rate_table` (4 cases: T4, CPU, A100 across midnight, L4 for 1 s; must-catch 6. The expected hours and units are computed in the test with `fractions` from the two timestamps and the committed rate);
  - `test_FR_0_5_07_append_never_rewrites_existing_rows`;
  - `test_FR_0_5_07_unknown_runtime_type_is_an_error` (must-catch 6);
  - `test_FR_0_5_07_every_rate_names_its_source` (5 malformed tables);
  - `test_FR_0_5_07_committed_rates_equal_owner_figures`;
  - `test_FR_0_5_07_unclosed_session_is_closed_at_next_start` (question 11 (a));
  - `test_FR_0_5_07_run_and_doctor_keep_last_seen_current`;
  - `test_FR_0_5_07_refuses_outside_colab`;
  - `test_FR_0_5_07_writes_only_under_aqis_lab_logs`.
- Colab-only test: `test_FR_0_5_07_colab_session_recorded` (marker `colab`). The plan named it `test_FR_0_5_07_colab_session_row_appended`. It was renamed because at OC-0.5-01 time the session is open (started by the launcher), so the check is the open-session record; the row itself is proved by OC-0.5-02's committed `units.csv`.
- Test-first: before `aqis_lab/unitlog.py` existed: `ImportError: cannot import name 'unitlog' from 'aqis_lab'`.
- Rates (`config/aqis_lab/colab_rates.yaml`): exactly the approval's figures, each with the approval's source text: cpu 0.08, Tesla T4 1.19, NVIDIA L4 1.71, NVIDIA A100-SXM4-40GB 5.40 units per hour; source "AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026)".
- **A real bug caught by the test:**
  - The first implementation divided with `decimal` at its default 28 digits: 1 h 7 min 13.5 s = 1.12041666… h, stored as …667.
  - × 5.40 gave 6.050250…002, which rounded to `6.0503`. The exact value is 6.05025, which rounds half-even to `6.0502`, as the test computed.
  - `estimate` now uses exact fractions and integer half-even rounding (`round_half_even`).
- Wiring (change budget inside this WP's own new files): `run` updates the unit log's last-seen time after each shard and at the end, and `doctor` after writing its report, when `--drive-mount` is given.
- Command: the fast command with `-k FR_0_5_07` → `16 passed, 1454 deselected in 2.32s`.
- Fast suite after FR-0.5-07: `1453 passed, 17 deselected in 208.26s (0:03:28)`.
- Status: DONE
