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

### FR-0.5-08 — Colab launcher notebook
- Tests (`tests/aqis_lab/test_aqis_launcher.py`):
  - `test_FR_0_5_08_launcher_has_at_most_6_cells` (1 markdown and 5 code cells, no committed outputs);
  - `test_FR_0_5_08_tag_is_one_variable_in_first_cell` (`AQIS_TAG = "aqis-lab-wp-0.5-colab-1"`, assigned once, used as `--branch`);
  - `test_FR_0_5_08_launcher_cells_contain_no_logic` (must-catch 4);
  - `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form` (19 forms, each rejected: `if`, `for`, `while`, `def`, `try`, `with`, a comprehension, a conditional expression, a comparison, `lambda`, `!` and `%` lines, an unlisted import, `os.system`, `subprocess.run` without `check=True` or with `check=False`, `open`, indexing, `os.chdir`);
  - `test_FR_0_5_08_token_only_reaches_the_clone_command` (the token is read inside the clone's `env` and never held in a variable);
  - `test_FR_0_5_08_clone_failure_never_shows_token` (stand-in `google.colab` module; a failing clone's output, traceback and every notebook variable are free of the token);
  - `test_FR_0_5_08_launcher_commands_exist_and_parse` (3 cases: the notebook's `RUN_ARGS` and both runbook variants; every `python -m aqis_lab` call's arguments are parsed by that command's own parser);
  - `test_FR_0_5_08_runbook_matches_launcher` (tag, `RUN_ARGS`, `RUN_OUT`, the pytest command, and the minimums and rate tables equal their config files).
- Test-first: before the notebook existed, `9 failed, 19 passed`. The 9 failures were `FileNotFoundError` on the notebook and the runbook; the 19 passes were the checker's rejection cases, which need no notebook.
- Catch while building: `test_FR_0_5_08_runbook_matches_launcher` found that the runbook named the run folder only by its Drive-relative path; `RUN_OUT` is now given in full.
- Design points:
  - Token: the clone gets its header through git's `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` environment variables, built inline from `userdata.get("GITHUB_TOKEN")`. No variable holds the token, so a failed clone (stopped by `check=True`) leaves nothing behind and needs no `if` or `try`.
  - Ordering: `drive layout` runs before `unitlog start`, because the unit log lives in `AQIS_LAB/logs`.
- Command: the fast command with `-k FR_0_5_08` → `28 passed, 1470 deselected in 0.84s`.
- Fast suite after FR-0.5-08: `1481 passed, 17 deselected in 201.70s (0:03:21)`.
- Status: DONE (the Colab run itself is OC-0.5-01 and OC-0.5-02)

### NFR-0.5-01 — Runner overhead under 5 % (accepted debt DEBT-013, target WP-0.7)
- Measured with the scripts under "Measurements" (same process, same staged smoke pack, same `clip-stats` task, fsync on in both; direct loop = read and check every clip, compute, write one results file atomically).
- First build of the runner: `direct median 72.9 ms; runner median 139.8 ms; overhead 91.8 %`.
- A profile showed three genuine inefficiencies in my own new code, which I removed without dropping any check:
  - `SystemView.real()` copied the whole environment on every call; it is now built once per process.
  - A staged pack was re-validated with jsonschema on every run. It is now reused without validation only when its marker names exactly the source's manifest bytes (file SHA-256), and the staged copy's bytes equal them. Those bytes were validated and verified at staging.
  - `git_state` made four git calls; it now makes two, with the same rules.
- After: `direct median 68.1 ms; runner median 96.6 ms; overhead 41.9 %`. A second measurement (11 alternating repetitions):
```text
{'direct': 75.4, '1 shard': 100.8, '6 shards': 137.7, '60 shards': 466.8}
overhead 1 shard 33.7 %; fixed per run ~25.4 ms; per extra shard ~6.20 ms
```
- What remains is fixed per-run work that the runner has to do:
  - two git subprocesses for the run card's commit and dirty flag (8.4 ms);
  - run-card validation, the canonical manifest hash and the shard plan;
  - about ten atomic writes and fsyncs (card, plan, shard results, marker, `results.jsonl`, log lines).

  5 % of a ~70 ms workload is 3.5 ms, less than the two git calls alone. The plan named this as risk 1 and committed to stop and ask rather than slow the task, drop fsyncs or change the comparison.
- Owner decision (BLK-008 option 1, `docs/approvals/WP-0.5.md` on `main`): the 5 % limit is checked in WP-0.7 with Vosk on the smoke pack and is DEBT-013 until then. WP-0.5 records the measured fixed overhead.
- **Recorded fixed overhead: about 25 to 30 ms per run, about 6 ms per extra shard.** On the ~70 ms `clip-stats` workload that is 34 to 42 %.
- Test: `test_NFR_0_5_01_overhead_measured_against_direct_loop` (`tests/aqis_lab/test_aqis_runner_nfr.py`, marker `slow`). It runs the measurement above, asserts that both loops write byte-identical results (so the comparison is like for like), and prints the numbers. It does **not** assert the 5 % limit (DEBT-013).
  - Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_runner_nfr.py -q -s -p no:cacheprovider`
```text
NFR-0.5-01 measurement: direct median 71.5 ms; runner median 101.4 ms; fixed overhead 29.9 ms (41.8 %); 5 % limit deferred to WP-0.7 (DEBT-013)
1 passed in 3.54s
```
  - An earlier run of the same test gave `direct median 76.3 ms; runner median 104.2 ms; fixed overhead 27.8 ms (36.4 %)`.
- Status: PARTIAL by owner decision: measured and recorded; the 5 % check is accepted debt DEBT-013 (target WP-0.7).
- Fast suite after the optimizations: `1481 passed, 17 deselected in 202.64s (0:03:22)`.

### NFR-0.5-02 — Nothing writes to Drive except under AQIS_LAB
- Tests (`tests/aqis_lab/test_aqis_drive_guard.py`; Drive test double: a folder plus a generated `fuse.drive` mountinfo line):
  - `test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab`. Each of these is refused before any byte is written, and the whole stand-in Drive is compared before and after:
    - `doctor` report `--out`, `run --out` (in `MyDrive/Personal` and at the Drive root);
    - `write_bytes`, `append_bytes`, `make_dirs` outside `AQIS_LAB`;
    - `unitlog` and `doctor` writing through an `AQIS_LAB/logs` link that points elsewhere on Drive.
  - `test_NFR_0_5_02_writes_under_aqis_lab_allowed`: doctor report, unit log and a full run under `AQIS_LAB` succeed, and nothing else on Drive changes.
- Code: `check_write_path` in `aqis_lab/drive.py` (built with FR-0.5-02). `write_bytes`, `append_bytes` and `make_dirs` always apply it.
- **Guarded commands:** `doctor`, `drive layout`, `run` and `unitlog`, which are all the commands WP-0.5 adds and all the commands the launcher runs; they write only through those functions.
- **Not guarded yet (audit finding WP-0.5-F01):** `score --out`, `pack build --out`, `registry build --out` and `registry fetch`. They are merged WP-0.3 and WP-0.4 code that writes directly. The owner accepted this as DEBT-014, target WP-0.7: before running on Colab, WP-0.7 routes every remaining lab writer through `aqis_lab.drive`. (Round 1 of this record said "every lab write", which was wrong: finding WP-0.5-F02.)
- Order of work: the guard was built with FR-0.5-02 and these tests were written afterwards. Break NFR2 below shows the main test fails when the guard is switched off.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_drive_guard.py -q -p no:cacheprovider` → `2 passed in 7.82s`.
- Status: PARTIAL: met for every WP-0.5 command and for the launcher; the older writers are DEBT-014 (target WP-0.7).

## Accepted debt with target WP-0.5 (question 13 (a))
- Tests (`tests/aqis_lab/test_aqis_debt_wp05.py`, test-only; no existing test or production file changed):
  - DEBT-009:
    - `test_FR_0_3_01_normaliser_checks_package_version_on_first_use`;
    - `test_FR_0_3_06_score_turns_normaliser_version_error_into_exit_2`.

    Both use a real installed-package record (`whisper_normalizer-0.1.2.dist-info`) placed first on `PYTHONPATH`.
  - DEBT-011: `test_FR_0_4_03_one_clip_per_speaker_when_candidates_share_a_speaker`, a generated registry where all but 6 test-clean rows share one speaker.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp05.py -q -p no:cacheprovider` → `3 passed in 7.23s`.
- Breaks D9a, D9b and D11 below: each test fails when its behaviour is removed.
- `docs/progress/DEBT.md` (Status column only):
  - DEBT-011: CLOSED.
  - DEBT-009: stays OPEN, partly done. The `NormalisationError` branch of `score` still has no test: reaching it needs a normaliser that never settles, which only a stand-in library could give, and the rules allow test doubles only for external services.

## Must-catch proof
- Script: `mutate.py` in the session scratchpad.
- Method, for each break:
  1. Copy every tracked and untracked (not ignored) file into `/tmp/aqis-wp05-mutations` as a fresh git repository.
  2. Apply exactly one break.
  3. Run the named tests with `-k`.

| # | Break (in the copy only) | Result |
| --- | --- | --- |
| MC1a | `doctor` python check always PASS | `1 failed`: `test_FR_0_5_02_fails_on_python_version_other_than_probe` |
| MC1b | `doctor` lock differences ignored | `3 failed`: `test_FR_0_5_02_fails_on_package_version_other_than_lock`, `test_FR_0_5_02_fails_on_package_missing_from_lock`, `test_FR_0_5_02_fails_on_lock_package_not_installed` |
| MC1c | missing `AQIS_LAB` not checked | `1 failed`: `test_FR_0_5_02_colab_fails_when_aqis_lab_missing` |
| MC1d | Drive write check not attempted (read-only folder passes) | `1 failed`: `test_FR_0_5_02_colab_fails_when_aqis_lab_read_only` |
| MC2 | every shard treated as unfinished (recomputed on resume) | `2 failed`: `test_FR_0_5_05_restart_skips_finished_shards`, `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` |
| MC3 | a results file without its marker counts as finished | `2 failed`: `test_FR_0_5_05_results_without_marker_not_finished`, `test_FR_0_5_06_kill_during_result_write_never_counts` |
| MC4 | an `if` added to launcher cell 5 | `1 failed`: `test_FR_0_5_08_launcher_cells_contain_no_logic` |
| MC5 | `platform.machine()` read in `aqis_lab/runner/card.py` | `1 failed`: `test_FR_0_5_01_platform_details_only_from_platform_module` |
| MC6 | unit log uses the CPU rate for every runtime | `3 failed, 1 passed`: the T4, A100 and L4 cases of `test_FR_0_5_07_appends_row_with_estimate_from_rate_table` (the CPU case rightly passes) |
| MC6b | unit log multiplies the *rounded* hours by the rate | first run: `4 passed` (survived). A case was added (1.00005 h × 5.40: exact 5.4003, from rounded hours 5.4000). Rerun: `1 failed, 4 passed`, the new A100 case |
| NFR2 | Drive guard switched off | `1 failed`: `test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab` |
| D9a | normaliser version check not called | `1 failed`: `test_FR_0_3_01_normaliser_checks_package_version_on_first_use` |
| D9b | `score` no longer catches `NormaliserVersionError` | `1 failed`: `test_FR_0_3_06_score_turns_normaliser_version_error_into_exit_2` |
| D11 | one-clip-per-speaker rule removed from `choose` | `1 failed`: `test_FR_0_4_03_one_clip_per_speaker_when_candidates_share_a_speaker` |

Every must-catch behaviour of the spec (1 to 6) has at least one named test that fails when it is broken.

## Acceptance commands
### AT-0.5-01
`.venv/bin/python -m aqis_lab doctor --target cloud` (from the repository root):
```text
check         status expected               actual                         detail
---------------------------------------------------------------------------------
platform      PASS   cloud-vm               cloud-vm                       signal: environment variable CLAUDE_CODE_REMOTE=true
python        PASS   3.13                   3.13.12                        major.minor 3.13 equals the Colab probe's 3.13 (docs/environment/colab_probe.txt; owner decision: major.minor)
lock          PASS   24 packages            24 installed                   installed packages equal requirements/aqis_lab/phase0.txt
disk          PASS   >= 10 GB               31,067,639,808 bytes (31.07 GB) free on the file system of /home/user/voice-bot-vad-harness/data/raw/aqis_lab/work; minimum 10 GB (config/aqis_lab/doctor.yaml)
ram           PASS   >= 4 GB                16,292,495,360 bytes (16.29 GB) MemAvailable; minimum 4 GB (config/aqis_lab/doctor.yaml)
gpu           SKIP   not requested          none                           --expect-gpu not given
result: PASS
report: /home/user/voice-bot-vad-harness/data/raw/aqis_lab/doctor/doctor_cloud-vm_20260928T100354Z.json
exit 0
```

### AT-0.5-02
- Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"`
```text
1487 passed, 18 deselected in 205.80s (0:03:25)
```
- Slow CPU suite: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "slow and not gpu and not colab and not oracle and not network"`
```text
3 passed, 1502 deselected in 12.58s
```
  The three slow tests: `test_NFR_0_2_01_validates_100k_events_under_10s`, `test_NFR_0_5_01_overhead_measured_against_direct_loop`, `test_FR_0_3_07_tie_heavy_pairs_match_jiwer`.
- The kill-and-resume tests (`test_FR_0_5_06_*`) are in the fast suite.

### AT-0.5-03
The audit gate with `--wp WP-0.5`: see "Audit gate" below.

## Audit gate
`git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.5` (on commit `7fbb3bd`):
```text
aqis-audit-gate: base origin/main (merge-base 408d7ad91a57), head 7fbb3bd09338, approvals origin/main 408d7ad91a57, wp WP-0.5
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.6 s)
```

## Owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| OC-0.5-01 | Colab, CPU runtime | Launcher `notebooks/aqis_lab/phase0_launcher.ipynb` with `AQIS_TAG = "aqis-lab-wp-0.5-colab-1"`, cells 1 to 4 with `RUN_ARGS = ["--shard-clips", "10"]`; then one extra cell: `!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab`; then cell 5 (steps in `docs/colab/COLAB_RUNBOOK.md`) | Doctor table: `platform`, `python`, `lock`, `disk`, `ram`, `drive-mount`, `drive-folder` PASS, `gpu` SKIP, `result: PASS`; pytest: `3 passed` (`test_FR_0_5_01_colab_runtime_detected`, `test_FR_0_5_02_colab_doctor_passes_on_colab`, `test_FR_0_5_07_colab_session_recorded`) | `docs/environment/doctor_colab_<timestamp>.json` and `docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt` (to be committed by the owner) |
| OC-0.5-02 | Colab, same notebook | Pass 1: `RUN_ARGS = ["--shard-clips", "10", "--max-shards", "2"]`, all cells; **Runtime → Disconnect and delete runtime**; pass 2: `RUN_ARGS = ["--shard-clips", "10"]`, all cells | Pass 1 log ends `stopped after 2 computed shard(s) (--max-shards 2); 4 shard(s) remain`. Pass 2 log: `session 2 start`, `shard 00000 skipped`, `shard 00001 skipped`, shards 00002 to 00005 `started`/`finished`, `run complete: 6 shard(s), 2 skipped and 4 computed in this session`. `units.csv` has one row per session | `docs/progress/WP-0.5/OC-0.5-02_runner.log` and `docs/progress/WP-0.5/OC-0.5-02_units.csv` (to be committed by the owner) |

The tag `aqis-lab-wp-0.5-colab-1` is created and pushed on the audited commit once the audit passes (question 12 (a)).

## Changes to existing files (inside the change budget)
- `aqis_lab/__main__.py`: four `COMMANDS` entries (`doctor`, `drive`, `run`, `unitlog`) and four CHANGE LOG lines. `build_parser` and `main` are unchanged. `git diff -U0 origin/main -- aqis_lab/__main__.py`:
```text
+  2026-09-28 WP-0.5 FR-0.5-02: `doctor` command registered in COMMANDS.
+  2026-09-28 WP-0.5 FR-0.5-03: `drive` command registered in COMMANDS.
+  2026-09-28 WP-0.5 FR-0.5-05: `run` command registered in COMMANDS.
+  2026-09-28 WP-0.5 FR-0.5-07: `unitlog` command registered in COMMANDS.
+    "doctor": ("aqis_lab.commands.doctor", "check Python, lock, disk, RAM, GPU and Drive; PASS/FAIL report"),
+    "drive": ("aqis_lab.commands.drive", "create the Google Drive AQIS_LAB folder layout; report crowded folders"),
+    "run": ("aqis_lab.commands.run", "run a task over a pack in resumable shards (copy then compute)"),
+    "unitlog": ("aqis_lab.commands.unitlog", "Colab session compute-unit log (start, end)"),
```
- `docs/capabilities/REGISTRY.md`: rows appended only (CAP-PLAT-001 to 003, CAP-DOCTOR-001 to 004, CAP-DRIVE-001 to 004, CAP-RUN-001 to 009, CAP-UNIT-001 to 004, CAP-NB-001, CAP-DOC-009 to 011). Existing rows are unchanged.
- `docs/progress/DEBT.md`:
  - the Status cells of DEBT-009 and DEBT-011;
  - the new row DEBT-013 (owner decision, BLK-008).
- `docs/progress/BLOCKERS.md`: BLK-008 appended and resolved.
- `docs/progress/STATUS.md`: the WP-0.5 row.
- No GUARDED or NEVER path, no existing test file and no lock file changed.

## audit-allow lines
None.

## CI
Workflow `aqis-lab-ci` on commit `879bf4cc5f823785ea44443132a706d7166a882d` (read with the GitHub Actions API):

| Run | Event | Job | Conclusion | Steps |
| --- | --- | --- | --- | --- |
| 36407566033 | push | `lab` | success | fast lab test suite success; audit gate (`--base origin/main`) success |
| 36407566033 | push | `harness-regression` | success | provisioning, harness tests and regression check against the baseline all success |
| 36407605458 | pull_request (PR #5) | `lab` | success | fast lab test suite success; work package ID from the title (`WP-0.5`) success; audit gate (`--wp WP-0.5`) success |
| 36407605458 | pull_request (PR #5) | `harness-regression` | success | provisioning, harness tests and regression check all success |

Every earlier push of this WP was green as well (runs 198 to 201).
Pull request: https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/5

## Round 2 (audit round 1 findings)
The details are in `docs/progress/WP-0.5/FIXES.md`.
- F02 to F08 fixed.
- F01 accepted as DEBT-014 (target WP-0.7).
- F09: DEBT-009 re-targeted to WP-0.9.

New tests:
- `test_FR_0_5_01_platform_scan_resolves_imports` (12 cases, F03);
- `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands` (14 cases, F04);
- `test_FR_0_5_05_resume_refused_when_card_differs` (7 cases, F05);
- `test_FR_0_5_04_changed_source_manifest_is_staged_again` (F06);
- `test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing` (F07);
- `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` (F08).

Changed test functions (all in files new in WP-0.5):
- `platform_detail_lines` now resolves imports with `ast` (F03);
- `logic_problems` now allows only the launcher's command shapes (F04);
- `test_FR_0_5_08_launcher_cells_contain_no_logic` now pins `PY`.

Every re-applied auditor break (A15-1 to A15-5, A15-7, break 5a) now fails a named test.

Results:
- Fast suite: `1523 passed, 18 deselected in 194.87s (0:03:14)`.
- Slow CPU suite: `3 passed, 1538 deselected in 12.63s`.
- AT-0.5-01: `result: PASS`.
- AT-0.5-03 gate: `0 findings: OK`.
