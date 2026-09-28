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
| F03 | `tests/aqis_lab/test_aqis_platform.py` (new in this WP) | `platform_detail_lines`, plus new AST resolution helpers; `test_FR_0_5_01_platform_details_only_from_platform_module` gains evasion cases | The scan matched text only, so `from platform import machine` and `__import__("os").uname()` passed | CAP-PLAT-003 (must-catch 5) |
| F04 | `tests/aqis_lab/test_aqis_launcher.py` (new in this WP) | `logic_problems` (argument shapes of `subprocess.run`); new rejection cases in `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form` | Any `subprocess.run([...], check=True)` was allowed, so `bash -c "if …"` passed | CAP-NB-001 (must-catch 4) |
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
