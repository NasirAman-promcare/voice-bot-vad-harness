# AUDIT — WP-0.5, round 2

Auditor: wp-auditor · Date: 2026-09-28 · Commit audited: d96668daa17574443305d17cb01b8a330a009d03 · Previous audited commit: b9c4fe7c6f95ae8d598a284dc2cfb6568b2e720b · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 6 (fixed 4, accepted as debt 1, open 1) · MINOR: 6 (fixed 3, resolved by re-targeting 1, open 2)

All nine round-1 findings are dealt with:
- **Fixed:** F02 to F08. Every round-1 break I re-applied now fails a named test.
- **Accepted as debt:** F01, as DEBT-014 (target WP-0.7).
- **Resolved:** F09. DEBT-009 is re-targeted to WP-0.9.

The suites, the gate, CI and the acceptance commands all pass, and all 22 must-catch breaks are caught.

The verdict is FAIL because of one new MAJOR finding, in code added in this round:
- **F10:** the new launcher command check (the F04 fix) allows `rm -rf WORKDIR` but does not pin what `WORKDIR` is. A second `WORKDIR = "/content/drive/MyDrive"` in cell 2 turns the launcher's first command into deleting the owner's whole Google Drive, and every FR-0.5-08 and NFR-0.5-02 test still passes. The committed notebook is safe. The fix is test-only and small. The builder already applied the same fix to `PY`, which depends on `WORKDIR`. My round-1 recommendation for F04 listed `rm -rf WORKDIR` as an allowed shape without asking for `WORKDIR` to be pinned, so this gap partly follows from my own advice.

Two new MINOR findings do not block:
- **F11:** one branch of the F08 fix is untested.
- **F12:** two sentences still carry the round-1 "every lab write" overstatement.

## Scope of this audit
This is a re-audit under protocol version 2. It covers:
1. each round-1 finding;
2. items A1 to A15 on the diff `b9c4fe7..d96668d`;
3. the full suites, the gate, CI and the complete must-catch proof.

Code that passed round 1 and has not changed was not searched again.
- **Diff since `b9c4fe7`:** 16 files, +546 −22.
  - Production code: `aqis_lab/commands/run.py` changes `main`, adds `_UnitLogTouchError` and updates its header. `aqis_lab/drive.py`, `aqis_lab/platform.py`, `aqis_lab/runner/run.py` and `aqis_lab/runner/stage.py` change their header docstrings only.
  - Tests: `test_aqis_platform.py`, `test_aqis_launcher.py`, `test_aqis_runner.py` and `test_aqis_stage.py`. All four are new in WP-0.5 and none exists on `main`.
  - Records: `REGISTRY.md`, `COLAB_RUNBOOK.md`, `DEBT.md`, `EVIDENCE.md`, `FIXES.md`, `STATUS.md` and the round-1 `AUDIT.md`.
  - `docs/approvals/WP-0.5.md` arrived through the merge of `main`. It is identical to `main` (`git diff origin/main HEAD -- docs/approvals` is empty).
- **Environment:** `bash aqis_lab/deploy/dev_bootstrap.sh` gives `OK: .venv ready: Python 3.13.12, lock sha256 84151d8f77b8512288620fdb82325fc2b22551da77324e171b7cdf055d732acc`.
- **Breaks** were made only in a throwaway copy, `/tmp/aqis-wp05-audit-r2`:
  - The copy is a tar copy of the clean tree at `d96668d`, with `.git` and without `.venv`, `data/raw` and `__pycache__`.
  - Imports resolve to the copy (`aqis_lab.__file__` = `/tmp/aqis-wp05-audit-r2/aqis_lab/__init__.py`). The unmodified copy gives `155 passed, 1386 deselected` on `-k "FR_0_5 or NFR_0_5"`.
  - Each code break is an exact-string replacement, checked to occur exactly once. Notebook breaks edit one cell's source.
  - A control run (notebook re-serialised, no change) left the file byte-identical: `155 passed`.
  - After each break the copy was restored with `git checkout -- .`, and `git status --short` in the copy was checked to be empty.
  - The repository itself was never modified by a break. `git status --short` was empty before I wrote this report.
- **Probes** ran the shipped code, unchanged, in my scratchpad: a full run and a repeat run, a run-card validation, and the round-1 F08 probe. They are not code breaks.

## Previous findings
| ID | Severity | Status | Evidence |
| --- | --- | --- | --- |
| WP-0.5-F01 | MAJOR | **Accepted as debt** | The round 2 CONDITIONS line in `docs/approvals/WP-0.5.md` on `main` (`a4d55a8`) names F01 and target WP-0.7. `DEBT.md` row DEBT-014 has the same text, target WP-0.7, status `OPEN` |
| WP-0.5-F02 | MAJOR | **FIXED** | All four places cited in round 1 now state the truth. `EVIDENCE.md` NFR-0.5-02 lists the guarded commands (`doctor`, `drive layout`, `run`, `unitlog`) and the unguarded ones, and says `Status: PARTIAL … DEBT-014`. `REGISTRY.md` CAP-DRIVE-001 and the `drive.py` header name the same split. `COLAB_RUNBOOK.md` limits the claim to the launcher's commands and tells the owner not to point `score`, `pack build` or `registry` at Drive. Two sentences not cited in round 1 still overstate it (new MINOR F12) |
| WP-0.5-F03 | MAJOR | **FIXED** | `platform_detail_lines` now adds an `ast` resolution of imports to the unchanged text scan. My re-applied break 5a (`__import__("os").uname()` in `card.py`) and round-1 A15-1 (`from platform import machine as host_arch`) both fail `test_FR_0_5_01_platform_details_only_from_platform_module`. The new `test_FR_0_5_01_platform_scan_resolves_imports` covers 12 import forms and passes on the real tree |
| WP-0.5-F04 | MAJOR | **FIXED** (for the reported form; see new F10) | `command_shape_problems` allows only the launcher's own command shapes, and `PY` is pinned to one `WORKDIR + '/.venv/bin/python'`. Re-applied A15-2 (`bash -c "if …; then rm -rf …; fi"` in cell 4) fails `test_FR_0_5_08_launcher_cells_contain_no_logic`. The 14 cases of `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands` pass |
| WP-0.5-F05 | MAJOR | **FIXED** | `test_FR_0_5_05_resume_refused_when_card_differs` is parametrised over `/machine/python_version`, `/machine/os`, `/machine/architecture`, `/git/commit`, `/git/dirty`, `/lock/sha256` and `/pack/sha256`. `_edit_card` keeps the card ID, the plan ID and the markers consistent, so only the named field differs, and the test requires the error to name it. Re-applied A15-4: 3 failed (`[/machine/architecture]`, `[/machine/os]`, `[/machine/python_version]`). Re-applied A15-7: 2 failed (`[/git/commit]`, `[/git/dirty]`) |
| WP-0.5-F06 | MINOR | **FIXED** | Re-applied A15-3 (`_reuse` without the manifest byte checks) fails `test_FR_0_5_04_changed_source_manifest_is_staged_again`. The test also checks a bytes-only change (same JSON, other indentation) |
| WP-0.5-F07 | MINOR | **FIXED** | Re-applied A15-5 (`verify_pack` result ignored) fails `test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing`. The test appends bytes after the tar end and asserts that the members are still intact |
| WP-0.5-F08 | MINOR | **FIXED** (one branch untested: new MINOR F11) | My probe of the shipped code, with `results.jsonl` turned into a folder, gives `ERROR: cannot write the run folder …: [Errno 21] Is a directory: …`, exit 2. Undoing the fix (break V-F08) fails `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log`, and so do A15 breaks E1 and E2 |
| WP-0.5-F09 | MINOR | **Resolved** (re-targeted) | The approval condition "DEBT-009 is re-targeted to WP-0.9 (F09)" is recorded. The DEBT-009 Target WP cell reads `WP-0.9 (re-targeted from WP-0.5 by docs/approvals/WP-0.5.md, round 2, finding WP-0.5-F09)` |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `git show origin/main:docs/progress/STATUS.md`: WP-0.2 and WP-0.4 are `MERGED`. The branch is `claude/magical-goldberg-kjvw5r` (not `main`), and `HEAD` = `origin/claude/magical-goldberg-kjvw5r` = `d96668d`. Merge-base with `origin/main` is `a4d55a8` (= `origin/main`). GitHub API: PR #5 `open`, `merged False`, head `d96668d`, base `main`. `docs/approvals/WP-0.5.md` on `main` says `STATUS: APPROVED`, with the round 2 condition (fix F02 to F08, F01 as debt with target WP-0.7, DEBT-009 to WP-0.9) |
| A2 Requirement coverage | PASS | `pytest --collect-only tests/aqis_lab` collects: FR_0_5_01 34 (1 `colab`), FR_0_5_02 18 (1 `colab`), FR_0_5_03 6, FR_0_5_04 10, FR_0_5_05 26, FR_0_5_06 2, FR_0_5_07 18 (1 `colab`), FR_0_5_08 42, NFR_0_5_01 1 (`slow`) and NFR_0_5_02 2. That is round 1 plus the new tests (+12, +2, +8, +14). Every ID has an `EVIDENCE.md` entry. Two IDs are PARTIAL, each with debt the owner accepted: NFR-0.5-01 (DEBT-013) and NFR-0.5-02 (DEBT-014) |
| A3 Acceptance commands | PASS | **AT-0.5-01:** `.venv/bin/python -m aqis_lab doctor --target cloud --out <scratchpad>/doctor`. `platform`, `python`, `lock`, `disk` and `ram` are `PASS`, `gpu` is `SKIP not requested`, then `result: PASS`, exit 0. **AT-0.5-02:** see A4; the kill-and-resume tests are in the fast suite. **AT-0.5-03:** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.5` gives `Findings: 0`, `0 findings: OK`, exit 0 |
| A4 Test suites and CI | PASS | **Fast:** `1523 passed, 18 deselected in 209.96s`, exit 0. **Slow CPU**, run alone: `3 passed, 1538 deselected in 16.90s`, exit 0. My first slow run overlapped the fast suite and failed the WP-0.2 timing test `test_NFR_0_2_01_validates_100k_events_under_10s` (`took 11.76 s`); alone it takes `8.03 s`. That is CPU contention I caused, not a WP-0.5 change. The NFR-0.5-01 overhead printed 40.3, 31.5 and 25.9 ms in three runs, around the recorded "about 25 to 30 ms"; the 5 % limit is DEBT-013. **CI** on `d96668d` (GitHub API check-runs, 4 of 4): workflow `aqis-lab-ci` runs 36413302703 (push) and 36413307743 (pull_request). Jobs `lab` and `harness-regression` are all `completed success`. `d122fe8` (the code commit) is green as well: runs 36412859717 and 36412864571 |
| A5 Test integrity | PASS | `git diff --name-status --diff-filter=MDR origin/main HEAD -- tests/` is empty, so no test that exists on `main` changed and none was deleted. The four test files changed in round 2 are new in WP-0.5. The only removed test lines are the old text loop in `platform_detail_lines`, and the new code keeps the same `FORBIDDEN` regexes and `ALLOWED` list. The other changed test code only adds checks (`logic_problems`, `test_FR_0_5_08_launcher_cells_contain_no_logic`). No `skip`, `xfail`, `importorskip`, trivial assert or `audit-allow` was added |
| A6 Must-catch proof | PASS | 22 breaks across the 6 behaviours, and all 22 fail a named test (table below). The round-1 survivor 5a is now caught |
| A7 Compromise scan | PASS | **Gate:** `Findings: 0`, `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`. **Grep** of lines added since `b9c4fe7` in `aqis_lab`, `tools`, `config`, `notebooks` and `tests` for `TODO`, `FIXME`, `XXX`, placeholder, simplif, for now, temporar, hack, dummy, fake, `NotImplementedError`, bare `pass` and broad `except`: none. **Reading the F08 change:** `_UnitLogTouchError` keeps the original error as `__cause__` and prints it. Every branch exits 2 with an `ERROR:` line. Nothing is swallowed |
| A8 Scope diff | PASS | The production change sits inside the F08 budget: `main` in `commands/run.py`, the private `_UnitLogTouchError` class that `main` uses, and the header. The class is outside `main`, but it is disclosed in `FIXES.md` ("After the fix"). The other four modules change only their header docstrings (test lists and CHANGE LOG; CAP-DRIVE-001 wording for F02), as `FIXES.md` states. **`REGISTRY.md`:** 6 rows changed in place (CAP-PLAT-003, CAP-RUN-001, -007, -009, CAP-NB-001, CAP-DRIVE-001) and none removed (87 rows before and after). **`DEBT.md`:** the DEBT-009 Target WP cell, plus the new DEBT-014 row. **Runbook:** one bullet. The gate reports no protected path |
| A9 Capabilities | PASS | Each touched module's header lists the new tests and has a round 2 CHANGE LOG line. The registry rows match the headers. Header/registry consistency is checked by `test_FR_0_0_08_*` in the passing fast suite and by the gate |
| A10 Contracts | PASS | No contract changed. A run card made by the changed `run` command validates: `contracts validate --kind run_card` gives `record 1: OK`, `1 valid, 0 invalid` |
| A11 Environment parity | PASS | The added production lines contain no absolute paths. The locks are unchanged (`84151d8f…`). Python is 3.13.12 against the probe's 3.13. `aqis_lab/platform.py` changes in its header only. The owner-run checks OC-0.5-01 and OC-0.5-02 are listed with commands and expected output (`EVIDENCE.md:344-345`) |
| A12 Reproducibility and traceability | PASS | Probe: `run --shard-clips 10` gives `6 computed`. The same command again gives `6 skipped and 0 computed`, with the same `results.jsonl sha256 47f307b4…` (60 rows). The resume refusals that question 4 (b) requires are now pinned by tests (F05) |
| A13 Errors and logging | PASS (MINOR F11) | F08 is fixed: a run-folder write error is reported as a run-folder error, and a unit-log failure as a unit-log error (probe and test). Break E3 shows that the `OSError` and `DriveError` branch of the unit-log wrapper has no test (F11) |
| A14 Documentation, licences, data | PASS (MINOR F12) | All of F02's cited places are fixed. `EVIDENCE.md` has a "Round 2" section, and `FIXES.md` records the reproductions and the re-applied breaks. DEBT-009 and DEBT-014 match the approval. There is no new data. Two leftover "every lab write" sentences remain (F12) |
| A15 Exploratory breaks | **FAIL** (F10; MINOR F11) | 5 breaks, all in code added in round 2 (the F08 handler and the F04 command check). 3 are caught (E1, E2, E5) and 2 survive. E4 can make the no-logic check report success wrongly (MAJOR F10). E3 cannot give wrong data (MINOR F11). The 8 re-applied round-1 breaks verify the previous findings and are not counted here |

## Must-catch proof (A6)
Runs: `pytest tests/aqis_lab -q -p no:cacheprovider -rf -m "not slow and not gpu and not colab and not oracle and not network" -k "<ids>"` in `/tmp/aqis-wp05-audit-r2`. These are my own breaks, the same 22 as round 1.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Doctor fails on another Python | 1a `doctor.py`: python status always `PASS` | `test_FR_0_5_02_fails_on_python_version_other_than_probe` | CAUGHT |
| 1 Doctor fails on a lock difference | 1b `doctor.py`: `elif installed[name] != version:` → `elif False:` | `test_FR_0_5_02_fails_on_package_version_other_than_lock` | CAUGHT |
| 1 | 1c `doctor.py`: loop over installed-but-not-locked packages emptied | `test_FR_0_5_02_fails_on_package_missing_from_lock` | CAUGHT |
| 1 | 1d `doctor.py`: "in the lock but not installed" problem → `pass` | `test_FR_0_5_02_fails_on_lock_package_not_installed` | CAUGHT |
| 1 Doctor fails on a missing Drive folder | 1e `doctor.py`: missing `AQIS_LAB` row returns `PASS` | `test_FR_0_5_02_colab_fails_when_aqis_lab_missing` | CAUGHT |
| 1 Doctor fails on a read-only Drive folder | 1f `doctor.py`: write check replaced by `back = data` | `test_FR_0_5_02_colab_fails_when_aqis_lab_read_only`, `…_colab_drive_checks_pass_when_writable` (2 failed) | CAUGHT |
| 1 Any FAIL gives a non-zero exit | 1g `commands/doctor.py`: always `return 0` | `test_FR_0_5_02_expect_gpu_fails_without_gpu`, `…_fails_when_target_is_not_this_platform`, `…_colab_fails_when_aqis_lab_read_only`, `…_any_fail_exits_non_zero` (4 failed) | CAUGHT |
| 2 Finished shards skipped after an interruption | 2a `run.py`: `if finished:` → `if False:` | 10 failed, including `test_FR_0_5_05_restart_skips_finished_shards` and `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` | CAUGHT |
| 2 Byte-identical results | 2b `run.py`: rows use the rebuilt card, not the stored one (`return card, plan, notes`) | `test_FR_0_5_05_resume_rule_for_other_cpu_model` | CAUGHT |
| 2 | 2c `run.py`: `results.jsonl` joined in reverse shard order | 4 failed, including `test_FR_0_5_05_shard_results_written_atomically_with_marker` | CAUGHT |
| 3 No marker, not finished | 3a `store.py`: a results file without a marker counts as finished | `test_FR_0_5_05_results_without_marker_not_finished`, `test_FR_0_5_06_kill_during_result_write_never_counts` | CAUGHT |
| 3 | 3b `store.py`: marker SHA-256 and size check → `if False:` | `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished[…results sha256]` | CAUGHT |
| 3 | 3c `store.py`: marker plan check → `if False:` | `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished[…another plan]` | CAUGHT |
| 4 No logic in the launcher | 4a cell 5 gains `RESULT = 1 if AQIS_TAG else 0` | `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 4 | 4b cell 3 gains `try: … except Exception: pass` | `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 4 | 4c cell 4 gains `!ls /content` | 6 failed, including `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 5 Platform details only from `aqis_lab.platform` | 5a `card.py`: `"machine": {**machine, "architecture": __import__("os").uname().machine}` | `test_FR_0_5_01_platform_details_only_from_platform_module` | CAUGHT (survived in round 1) |
| 5 | 5b `commands/unitlog.py`: Colab decided from `"COLAB_RELEASE_TAG" in os.environ` | `test_FR_0_5_01_platform_details_only_from_platform_module` | CAUGHT |
| 6 Correct estimate from the rate table | 6a `unitlog.py`: units × 1.01 | 6 failed: 4 of the 5 estimate cases, `…_append_never_rewrites_existing_rows` and `…_unclosed_session_is_closed_at_next_start` | CAUGHT |
| 6 | 6b `unitlog.py`: half-up instead of half-even rounding | `test_FR_0_5_07_appends_row_with_estimate_from_rate_table` (both A100 cases) | CAUGHT |
| 6 Appends | 6c `unitlog.py`: `append_bytes` → `write_bytes` (overwrite) | `test_FR_0_5_07_append_never_rewrites_existing_rows`, `…_unclosed_session_is_closed_at_next_start` | CAUGHT |
| 6 | 6d `unitlog.py`: unknown runtime falls back to the CPU rate | `test_FR_0_5_07_unknown_runtime_type_is_an_error` | CAUGHT |

## Exploratory breaks (A15, at most 10)
| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| E1 run-folder write error exits 0 (`return 2` → `return 0` in the `(DriveError, OSError)` handler) | `aqis_lab/commands/run.py`, `main` | No: `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` | — |
| E2 unit-log wrapper re-raises the raw error (`raise _UnitLogTouchError(exc) from exc` → `raise`) | `aqis_lab/commands/run.py`, `main` (`on_shard`) | No: `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` | — |
| E3 unit-log wrapper narrowed to `except (UnitLogError,)`: a Drive or OS write failure in `touch` is then reported as "cannot write the run folder" | `aqis_lab/commands/run.py`, `main` (`on_shard`) | **Yes**: `155 passed` on `-k "FR_0_5 or NFR_0_5"` | MINOR (F11) |
| E4 cell 2 gains `WORKDIR = "/content/drive/MyDrive"` just before `subprocess.run(["rm", "-rf", WORKDIR], check=True)` | launcher notebook; tests the new `command_shape_problems` | **Yes**: `155 passed` on `-k "FR_0_5 or NFR_0_5"`; `44 passed` on `-k "FR_0_5_08 or NFR_0_5_02"` | MAJOR (F10) |
| E5 cell 1's own setting changed to `WORKDIR = "/content/drive/MyDrive/AQIS_LAB"` | launcher notebook, cell 1 | No: `test_FR_0_5_08_runbook_matches_launcher` (it pins cell 1's `WORKDIR` to `/content/aqis`) | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.5-F01 | MAJOR | A2; NFR-0.5-02 | Four older writers (`score --out`, `pack build --out`, `registry build --out` and `registry fetch`) make no Drive check | DEBT-014; approval on `main` (`a4d55a8`) | **Accepted as debt, target WP-0.7** (owner decision). Closed for this WP |
| WP-0.5-F02 | MAJOR | A2, A14 | **FIXED.** The records said every lab write is guarded | "Previous findings" | Closed |
| WP-0.5-F03 | MAJOR | A6; must-catch 5 | **FIXED.** The platform scan was a text match | Breaks 5a and V-A15-1 caught | Closed |
| WP-0.5-F04 | MAJOR | A15; must-catch 4 | **FIXED** for logic inside a command. See F10 for the variable the new check trusts | Break V-A15-2 caught | Closed |
| WP-0.5-F05 | MAJOR | A15, A12 | **FIXED.** Resume refusals were untested | Breaks V-A15-4 and V-A15-7 caught | Closed |
| WP-0.5-F06 | MINOR | A15 | **FIXED.** The staged-manifest reuse check was untested | Break V-A15-3 caught | Closed |
| WP-0.5-F07 | MINOR | A15 | **FIXED.** The archive-level hash check was untested | Break V-A15-5 caught | Closed |
| WP-0.5-F08 | MINOR | A13 | **FIXED.** Run I/O errors were reported as unit-log errors | Probe; break V-F08 caught | Closed |
| WP-0.5-F09 | MINOR | A14 | **Resolved.** DEBT-009 is re-targeted to WP-0.9 | `DEBT.md` row DEBT-009 | Closed |
| WP-0.5-F10 | MAJOR | A15; FR-0.5-08, NFR-0.5-02; the check behind must-catch 4 | **The launcher check trusts `WORKDIR`, and `WORKDIR` is the path given to `rm -rf`.** `command_shape_problems` (`tests/aqis_lab/test_aqis_launcher.py:49-86`) accepts `["rm", "-rf", WORKDIR]` whatever `WORKDIR` holds. Only cell 1's first `WORKDIR` is pinned (`test_FR_0_5_08_runbook_matches_launcher`, line 318); a later assignment is not checked. So `WORKDIR = "/content/drive/MyDrive"` added to cell 2 before the `rm -rf` passes every WP-0.5 test. The launcher would then delete the owner's whole Google Drive, while `test_FR_0_5_08_launcher_cells_contain_no_logic` reports that the cells only take the allowed steps. The launcher's `rm -rf` runs outside `aqis_lab.drive`, so the NFR-0.5-02 guard does not apply to it. The builder closed this gap for `PY` (exactly one `PY = WORKDIR + '/.venv/bin/python'`) but not for `WORKDIR`, which `PY` depends on. The committed notebook is safe: `WORKDIR` is `/content/aqis` and it is assigned once | Break E4 survives (`155 passed`); break E5 (cell 1 value) is caught | **Fix now** (test-only, in a file new in this WP; a few lines). Require every cell-1 setting (`AQIS_TAG`, `REPO`, `WORKDIR`, `DRIVE_MOUNT`, `AQIS_DRIVE`, `RUN_OUT`, `RUN_ARGS`) to be assigned exactly once across all cells, in cell 1, as the test already does for `AQIS_TAG` and `PY`. Add the E4 form to `HIDDEN_LOGIC` as a case. If you would rather not reopen the build, accepting it as debt with target WP-0.7 (fix before WP-0.7 edits the launcher) is defensible, because the committed notebook is safe. A round 3 is needed either way |
| WP-0.5-F11 | MINOR | A13, A15; FR-0.5-05 | **Only the `UnitLogError` branch of the F08 wrapper is tested.** In `aqis_lab/commands/run.py:65-69`, `on_shard` wraps `UnitLogError`, `DriveError` and `OSError` from `touch`. The second half of `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` triggers only a `UnitLogError` (an unreadable session file). Narrowing the wrapper to `(UnitLogError,)` passes all 155 WP-0.5 tests. A refused or failed Drive write of the session file would then be reported as `ERROR: cannot write the run folder …`. The exit code stays 2 and the failure is loud; only the label would be wrong. The shipped code is correct | Break E3 | Fix in the next round, since there will be one: one case with the session file's write refused, for example an `AQIS_LAB/logs` link pointing elsewhere on Drive, the pattern the NFR-0.5-02 tests already use. It should expect `ERROR: unit log`. Otherwise accept as debt, target WP-0.7 |
| WP-0.5-F12 | MINOR | A14; F02 residue | **Two sentences still say every lab write is guarded.** (1) `EVIDENCE.md:67` (FR-0.5-02 section): "`aqis_lab/drive.py`: the write guard and atomic writes that every lab write uses". (2) The `aqis_lab/drive.py:1` module summary: "Google Drive rules for every lab write". Round 1 did not cite them, and the NFR-0.5-02 section, CAP-DRIVE-001 and the runbook now state the truth. Both still contradict DEBT-014 | Lines cited | Fix in the next round (two wording edits; the `drive.py` edit is header-only). Otherwise accept as debt, target WP-0.7, where DEBT-014 makes the sentences true |

## Convergence (round 3 onwards)
Not required at round 2. For the record:

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 5 open | 4 open | F03 (must-catch 5), F04 (must-catch 4) |
| 2 | 0 | 1 open (F10, new); 4 fixed; 1 accepted as debt (F01) | 2 open (F11, F12, new); 3 fixed; 1 resolved (F09) | None of the must-catch behaviours is unprotected: all 22 A6 breaks are caught. F10 is a gap in the check behind must-catch 4 (a trusted variable, not logic in a cell) |

## For the owner
- **audit-allow lines:** None (gate: `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.5.md` on `main` (`a4d55a8`):
  - questions 2 to 14 as recommended;
  - the Colab unit rates from the Build Plan;
  - BLK-008 option 1 (DEBT-013);
  - round 2: fix F02 to F08, F01 as DEBT-014 (target WP-0.7), DEBT-009 re-targeted to WP-0.9.
- **Debt accepted so far for WP-0.5:**
  - DEBT-013 (NFR-0.5-01 5 % target, target WP-0.7);
  - DEBT-014 (F01, older writers without the Drive guard, target WP-0.7);
  - DEBT-009 (re-targeted to WP-0.9).
- **To reach PASS:** fix F10, or accept it as debt with a CONDITIONS line and a `DEBT.md` row. Since a round 3 is needed either way, I recommend fixing it: it is a few test lines in a file new in this WP. F11 and F12 do not block; they are one test case and two wording edits, so fixing them in the same round costs little.
- **Owner-run checks still pending:**
  - OC-0.5-01 (doctor and `pytest -m colab` on a Colab CPU runtime);
  - OC-0.5-02 (stop after 2 shards, delete the runtime, resume).

  Both come after the audit passes, from the tag `aqis-lab-wp-0.5-colab-1` on the audited commit. They are the first real test of atomic rename, folder `fsync` and append on Google Drive's FUSE mount. The committed launcher's `rm -rf` targets `/content/aqis` (local disk), so running it as committed is safe.
