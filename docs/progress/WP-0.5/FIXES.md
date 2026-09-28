# FIXES — WP-0.5

## Round 2 (audit round 1: `docs/progress/WP-0.5/AUDIT.md`)
Owner decision (`docs/approvals/WP-0.5.md` on `main`, `a4d55a8`):
- fix WP-0.5-F02 to F08;
- F01 is accepted as debt DEBT-014 (target WP-0.7: before running on Colab, WP-0.7 routes every remaining lab writer through `aqis_lab.drive`);
- DEBT-009 is re-targeted to WP-0.9 (F09).

Baseline before any change: the affected test files (`test_aqis_platform.py`, `test_aqis_launcher.py`, `test_aqis_runner.py`, `test_aqis_stage.py`, `test_aqis_runner_resume.py`, `test_aqis_drive_guard.py`, `test_aqis_unitlog.py`, `test_aqis_gate_registry.py`) → `108 passed in 15.30s`.

### Change budget
| Finding | File | Functions or parts changed | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| F02 | `docs/progress/WP-0.5/EVIDENCE.md` | NFR-0.5-02 section (status, list of guarded commands) | The record said "every lab write" and DONE, but only the WP-0.5 writers use the guard (F01) | none (records) |
| F02 | `docs/capabilities/REGISTRY.md` | CAP-DRIVE-001 row, "What it does" cell only | Same overstatement | CAP-DRIVE-001 (wording only) |
| F02 | `docs/colab/COLAB_RUNBOOK.md` | "Drive layout" bullet "Only under `AQIS_LAB`" | Same overstatement | CAP-DOC-011 (its test does not read this line) |
| F02, F01, F09 | `docs/progress/DEBT.md` | new row DEBT-014; DEBT-009 Target WP cell → WP-0.9 | Owner decision | none |
| F03 | `tests/aqis_lab/test_aqis_platform.py` (new in this WP) | `platform_detail_lines`, plus new AST resolution helpers; new test `test_FR_0_5_01_platform_scan_resolves_imports` (12 import forms) | The scan matched text only, so `from platform import machine` and `__import__("os").uname()` passed | CAP-PLAT-003 (must-catch 5) |
| F04 | `tests/aqis_lab/test_aqis_launcher.py` (new in this WP) | `logic_problems` (argument shapes of `subprocess.run`); new test `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands` (14 cases) | Any `subprocess.run([...], check=True)` was allowed, so `bash -c "if …"` passed | CAP-NB-001 (must-catch 4) |
| F05 | `tests/aqis_lab/test_aqis_runner.py` (new in this WP) | new test `test_FR_0_5_05_resume_refused_when_card_differs` (parametrised) | Only `/seed`, the plan and `/machine/gpu` refusals were tested | CAP-RUN-007 |
| F06, F07 | `tests/aqis_lab/test_aqis_stage.py` (new in this WP) | new tests `test_FR_0_5_04_changed_source_manifest_is_staged_again`, `test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing` | `_reuse`'s byte check and the `verify_pack` result had no test of their own | CAP-RUN-001 |
| F08 | `aqis_lab/commands/run.py` | `main` only (+ header CHANGE LOG) | One `except` caught every `OSError`/`DriveError` of the whole run and called it a unit-log error | CAP-RUN-009 |
| F08 | `tests/aqis_lab/test_aqis_runner.py` | new test `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` | — | CAP-RUN-009 |

Header-only additions made while recording (surgical-fix step 7). Each is the test list of a capability plus one CHANGE LOG line:
- `aqis_lab/platform.py` (CAP-PLAT-003);
- `aqis_lab/runner/stage.py` (CAP-RUN-001);
- `aqis_lab/runner/run.py` (CAP-RUN-007);
- `aqis_lab/drive.py` (CAP-DRIVE-001 wording, F02).

Sibling gap fixed in the same category as F04 (surgical-fix step 6): the checker trusts `PY`. `test_FR_0_5_08_launcher_cells_contain_no_logic` now also requires exactly one `PY = WORKDIR + '/.venv/bin/python'`.

No production module other than `aqis_lab/commands/run.py` changes behaviour. No test file that existed at the base (`origin/main`) changes: all the test files above are new in WP-0.5.

### Reproduction (tests fail before the fix)
| Finding | Test | Before the fix |
| --- | --- | --- |
| F03 | `test_FR_0_5_01_platform_scan_resolves_imports` (12 import forms) | `12 failed, 21 deselected` (text-only scan) |
| F04 | `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands` (14 command shapes) | `14 failed, 28 deselected` |
| F08 | `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` | `AssertionError`: stderr was `ERROR: unit log (last-seen time): [Errno 21] Is a directory: '…/results.jsonl.partial' -> '…/results.jsonl'` |
| F05, F06, F07 | `test_FR_0_5_05_resume_refused_when_card_differs` (7 fields), `test_FR_0_5_04_changed_source_manifest_is_staged_again`, `test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing` | The shipped code already behaves correctly, so these pass on it. They are proven by re-applying the auditor's breaks (next table) |

### Verification: the auditor's breaks, re-applied in a copy under `/tmp`
Harness: `mutate_r2.py` in the session scratchpad. It makes a fresh copy for each break and runs the named tests with `-k`.

| Break | Result |
| --- | --- |
| A15-4: Python, OS and architecture made resumable | `3 failed, 4 passed`: `…[/machine/architecture]`, `…[/machine/os]`, `…[/machine/python_version]` |
| A15-7: `/git/commit` and `/git/dirty` ignored on resume | `2 failed, 5 passed`: `…[/git/commit]`, `…[/git/dirty]` |
| Lock and pack hashes ignored on resume (sibling of A15-7) | `2 failed, 5 passed`: `…[/lock/sha256]`, `…[/pack/sha256]` |
| A15-3: staged pack reused without the manifest byte checks | `1 failed`: `test_FR_0_5_04_changed_source_manifest_is_staged_again` |
| A15-5: `verify_pack` result ignored in staging | `1 failed`: `test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing` |
| 5a: `__import__('os').uname()` in `aqis_lab/runner/card.py` | `1 failed`: `test_FR_0_5_01_platform_details_only_from_platform_module` |
| A15-1: `from platform import machine as host_arch` in `aqis_lab/runner/card.py` | `1 failed`: `test_FR_0_5_01_platform_details_only_from_platform_module` |
| A15-2: `bash -c "if …; then rm -rf …; fi"` appended to launcher cell 4 | `1 failed`: `test_FR_0_5_08_launcher_cells_contain_no_logic` |
| F08 undone (run I/O error reported as a unit-log error again) | `1 failed`: `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` |

### After the fix
- Affected test files: all pass (platform 33, launcher 42, runner 26, stage 10, registry and platform together 45).
- Fast suite: `1523 passed, 18 deselected in 194.87s (0:03:14)`.
- Slow CPU suite: `3 passed, 1538 deselected in 12.63s`.
- `doctor --target cloud`: `result: PASS`.
- Audit gate `--base origin/main --wp WP-0.5`: `0 findings: OK`.
- `git diff -U0` on production code: `aqis_lab/commands/run.py` changes only `main`, a new private exception class `_UnitLogTouchError` used by `main`, and the header (test list and CHANGE LOG). The other four modules change in their header docstrings only.

### Records (F02, F01, F09)
- `EVIDENCE.md` NFR-0.5-02: lists the guarded commands (`doctor`, `drive layout`, `run`, `unitlog`) and the unguarded older writers. Status is now PARTIAL with DEBT-014.
- `REGISTRY.md` CAP-DRIVE-001, `COLAB_RUNBOOK.md` "Only under `AQIS_LAB`" and the `aqis_lab/drive.py` header now say the same, and tell the owner not to point the older commands at Drive.
- `DEBT.md`:
  - new row DEBT-014 (F01, target WP-0.7, the owner's condition text);
  - DEBT-009's Target WP is now WP-0.9 (F09).

### CI (round 2)
Workflow `aqis-lab-ci` on commit `d122fe8`: runs 36412859717 and 36412864571 (push and PR #5). Both `lab` jobs (fast suite and audit gate, the PR run with `--wp WP-0.5`) and both `harness-regression` jobs: success.

## Round 3 (audit round 2: `docs/progress/WP-0.5/AUDIT.md`)
Owner decision (`docs/approvals/WP-0.5.md` on `main`, `59619d1`): fix WP-0.5-F10, F11 and F12. No new debt.

Baseline before any change: `test_aqis_launcher.py`, `test_aqis_runner.py` and `test_aqis_gate_registry.py` → `80 passed in 7.27s`.

### Change budget
| Finding | File | Functions or parts changed | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| F10 | `tests/aqis_lab/test_aqis_launcher.py` (new in this WP) | `logic_problems` (new `first_cell` argument: settings may be assigned only in cell 1, and later cells only `PY`); `test_FR_0_5_08_launcher_cells_contain_no_logic` (passes the cell position; every cell-1 setting assigned exactly once across all cells, in cell 1); new `HIDDEN_LOGIC` case `reassign_workdir` (break E4) | `rm -rf WORKDIR` was allowed whatever `WORKDIR` held, and only cell 1's first value was pinned | CAP-NB-001 (must-catch 4) |
| F11 | `tests/aqis_lab/test_aqis_runner.py` (new in this WP) | `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log`: a third case where the unit log's session-file write fails with an `OSError` | Only the `UnitLogError` branch of the F08 wrapper was exercised | CAP-RUN-009 |
| F12 | `docs/progress/WP-0.5/EVIDENCE.md` | FR-0.5-02 "New files" bullet for `aqis_lab/drive.py` | Round-1 "every lab write" wording left over | none (records) |
| F12 | `aqis_lab/drive.py` | module summary line (header only) plus a CHANGE LOG line | Same leftover wording | none (header only) |
| F12 (same category, step 6) | `aqis_lab/drive.py` header and `docs/capabilities/REGISTRY.md` | CAP-DRIVE-003 description: "every lab write" → writes through `write_bytes`, `append_bytes` or `make_dirs` (all WP-0.5 commands; DEBT-014 for the older writers) | The crowding warning has the same limit as the guard | CAP-DRIVE-003 (wording only) |

No production behaviour changes in round 3.

### Reproduction
| Finding | Test | Before the fix |
| --- | --- | --- |
| F10 | `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands[reassign_workdir]` (break E4 as a case) | `1 failed` (the checker accepted `WORKDIR = "/content/drive/MyDrive"` followed by `rm -rf WORKDIR`) |
| F11 | third case of `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` (the session file's atomic write fails: its `.partial` path is a folder, so an `OSError`) | Passes on the shipped code, which is correct. Proven by break E3 below |

A consequence handled in the same change: the older forbidden-form cases of `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form` assigned `x = …`, which the new rule rejects on its own. They now assign `PY`, the one name a later cell may assign. Each is therefore still rejected by its construct alone; checked one by one, none of their problems is the assignment rule.

### Verification: breaks re-applied in a copy under `/tmp`
Harness: `wp05_r3_breaks.py` in the session scratchpad.

| Break | Result |
| --- | --- |
| E3: unit-log wrapper narrowed to `except (UnitLogError,)` | `1 failed`: `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` |
| E4: cell 2 gains `WORKDIR = "/content/drive/MyDrive"` before `rm -rf WORKDIR` | `1 failed, 44 passed`: `test_FR_0_5_08_launcher_cells_contain_no_logic` |
| Cell 1 assigns `WORKDIR` a second time | `2 failed`: `test_FR_0_5_08_launcher_cells_contain_no_logic`, `test_FR_0_5_08_runbook_matches_launcher` |
| Cell 4 re-points `RUN_OUT` | `4 failed`: `test_FR_0_5_08_launcher_cells_contain_no_logic` and the 3 cases of `test_FR_0_5_08_launcher_commands_exist_and_parse` |
| Cell 5 re-points `DRIVE_MOUNT` | `1 failed`: `test_FR_0_5_08_launcher_cells_contain_no_logic` |

**Limit stated plainly (F11).** The wrapper also catches `DriveError` from `touch`. That branch needs a Google Drive mount, which the `run` command reads from the real system, and there is none on the cloud VM, so no test reaches it through the command. The `OSError` case above fails break E3. The Drive refusal of the unit-log write itself is tested in-process by `test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab`.

### After the fix
- `test_aqis_launcher.py`: `43 passed`. The runner, registry, platform and Drive tests pass.
- Fast suite: `1524 passed, 18 deselected in 150.94s (0:02:30)`.
- Slow CPU suite: `3 passed, 1539 deselected in 8.36s`.
- `doctor --target cloud`: `result: PASS`.
- Audit gate `--base origin/main --wp WP-0.5`: `0 findings: OK`.
- `git diff -U0 -- aqis_lab`: only the `aqis_lab/drive.py` header (summary line, CAP-DRIVE-003 wording, one CHANGE LOG line). No production behaviour changed.
- F12: `EVIDENCE.md` (FR-0.5-02 "New files") and the `drive.py` summary no longer say "every lab write". The same wording in CAP-DRIVE-003 (the `drive.py` header and the registry row) was fixed as a sibling. The one remaining mention, in the NFR-0.5-02 section, quotes the round-1 wording as wrong.

### CI (round 3)
Workflow `aqis-lab-ci` on commit `719de94`: run 36431204531 (push) and run 36431211029 (PR #5, with `--wp WP-0.5` from the title). Conclusion success for both.
