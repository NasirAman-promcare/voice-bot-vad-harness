# AUDIT — WP-0.5, round 3

Auditor: wp-auditor · Date: 2026-09-28 · Commit audited: f3bde36cd9cad2065c38761e4ca3f0b6cd4deace · Previous audited commit: d96668daa17574443305d17cb01b8a330a009d03 · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 · MAJOR: 6 (fixed 5, accepted as debt 1, open 0) · MINOR: 6 (fixed 4, resolved by re-targeting 1, open 1)

The three round-2 findings are dealt with:
- **F10 (MAJOR): fixed.**
  - Only cell 1 may assign the launcher settings, and each setting is assigned exactly once in the notebook, in cell 1.
  - My round-2 break E4 (cell 2 sets `WORKDIR = "/content/drive/MyDrive"` before `rm -rf WORKDIR`) now fails `test_FR_0_5_08_launcher_cells_contain_no_logic`.
  - All 8 of my new breaks on the new rule are caught.
- **F12 (MINOR): fixed.** Both cited sentences now match DEBT-014.
- **F11 (MINOR): partly fixed; one MINOR residual stays open.**
  - My round-2 break E3 is now caught.
  - The wrapper's `DriveError` branch is still untested: break V-F11b survives. The shipped code is correct, and the failure stays loud (exit 2).
  - This does not block a pass. I recommend accepting it as debt.

The suites, the gate, CI on the audited commit and the acceptance commands all pass. All 22 must-catch breaks are caught. No new finding came out of this round. No open finding sits inside the must-catch list.

## Scope of this audit
This is a re-audit under protocol version 2. It covers:
1. the round-2 findings;
2. items A1 to A15 on the diff `d96668d..f3bde36`;
3. the full suites, the gate, CI and the complete must-catch proof.

Code that passed rounds 1 and 2 and has not changed was not searched again.

**Diff since `d96668d`:** 8 files, +209 −95.
- **Production code:** only the header docstring of `aqis_lab/drive.py` changed. That is the summary line, the CAP-DRIVE-003 wording and one CHANGE LOG line. No production behaviour changed.
- **Tests:**
  - `tests/aqis_lab/test_aqis_launcher.py`: new `SETTINGS` and `LATER_CELL_NAMES`; `logic_problems` gains `first_cell`; the no-logic test gains the exactly-once check; 9 forbidden-form inputs are rewritten; one new `HIDDEN_LOGIC` case.
  - `tests/aqis_lab/test_aqis_runner.py`: a third case appended to `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log`.
  - Neither file exists on `main`.
- **Records:** `REGISTRY.md` (CAP-DRIVE-003 wording), `EVIDENCE.md`, `FIXES.md`, and the round-2 `AUDIT.md`.
- **Approval:** `docs/approvals/WP-0.5.md` arrived through the merge of `main`. `git diff origin/main HEAD -- docs/approvals docs/specs docs/process .claude CLAUDE.md` is empty.
- **Unchanged:** the notebook, `config/`, the locks, `COLAB_RUNBOOK.md` and `DEBT.md`.

**Environment:** `bash aqis_lab/deploy/dev_bootstrap.sh` gives `OK: .venv ready: Python 3.13.12, lock sha256 84151d8f77b8512288620fdb82325fc2b22551da77324e171b7cdf055d732acc`.

**Breaks** were made only in a throwaway copy, `/tmp/aqis-wp05-audit-r3`:
- The copy is a tar copy of the clean tree at `f3bde36`, with `.git` and without `.venv`, `data/raw` and `__pycache__`.
- Imports resolve to the copy: `aqis_lab.__file__` = `/tmp/aqis-wp05-audit-r3/aqis_lab/__init__.py`, and `aqis_testutil.ROOT` = `/tmp/aqis-wp05-audit-r3`.
- **Test command for every break:** `pytest tests/aqis_lab -q -p no:cacheprovider -rf -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_5 or NFR_0_5"`. This is the whole WP-0.5 fast set.
- **Control:** the notebook re-serialised with no change gave `156 passed, 1386 deselected`, and `git diff` was empty. Round 2 had 155; the new `reassign_workdir` case adds one.
- **How each break was made:**
  - A code break is an exact-string replacement, checked to occur exactly once.
  - A notebook break edits one code cell. The notebook is written back with `json.dumps(indent=1, ensure_ascii=False)`, which reproduces the committed file byte for byte.
- **Restore:** after each break, `git checkout -- .`, then `git status --short --untracked-files=all` in the copy was checked to be empty.
- **The repository was never modified by a break.** `git status --short` was empty before I wrote this report.
- **Harness:** `wp05_r3_audit_breaks.py` in my session scratchpad.

**Probes** ran the shipped code, unchanged, in my scratchpad. They are not code breaks:
- a full run, then a repeat run;
- a run-card validation;
- the no-logic checker called on each forbidden-form input and each exploratory form.

## Previous findings
| ID | Severity | Status | Evidence |
| --- | --- | --- | --- |
| WP-0.5-F01 | MAJOR | **Accepted as debt** (unchanged) | CONDITIONS line in `docs/approvals/WP-0.5.md` on `main`; `DEBT.md` row DEBT-014, target WP-0.7 |
| WP-0.5-F02 to F08 | MAJOR / MINOR | **Fixed in round 2** | Round-2 report. The code they cover is unchanged since `d96668d`, and the full suite passes |
| WP-0.5-F09 | MINOR | **Resolved in round 2** (DEBT-009 re-targeted to WP-0.9) | `DEBT.md` unchanged since `d96668d` |
| WP-0.5-F10 | MAJOR | **FIXED** | See below |
| WP-0.5-F11 | MINOR | **Partly fixed; residual open** | See below |
| WP-0.5-F12 | MINOR | **FIXED** | See below |

**F10.**
- `logic_problems(source, first_cell)` lets cell 1 assign only the seven settings, and lets a later cell assign only `PY`.
- `test_FR_0_5_08_launcher_cells_contain_no_logic` requires each setting to be assigned in exactly one place, in cell 1 (`[i for i, target in assigned if target == name] == [1]`).
- Cell 1's `WORKDIR` value is pinned to `/content/aqis` by `test_FR_0_5_08_runbook_matches_launcher`.
- Cell-1 settings must be literals (`test_FR_0_5_08_tag_is_one_variable_in_first_cell`).
- So nothing in the notebook can change what `rm -rf WORKDIR` deletes.
- Re-applied E4 (V-E4): `1 failed` (`test_FR_0_5_08_launcher_cells_contain_no_logic`).
- **Rewritten inputs checked.** The 9 forbidden-form inputs that changed from `x = …` to `PY = …` do not weaken the test. Without the rewrite, the new rule would reject `x` on its own, and those cases would pass for the wrong reason. My probe shows that 0 of the 19 forbidden-form cases are rejected only by the assignment rule; each is still rejected by its own construct (`If`, `Try`, `ListComp`, `Subscript`, call `open`, and so on).
- `reassign_workdir` is the only `HIDDEN_LOGIC` case caught by the assignment rule alone, as intended.

**F11.**
- **What is fixed.** The new third case gives the session file an open session and makes `units_open_session.json.partial` a folder. The atomic write then fails with an `OSError`, and the test expects `ERROR: unit log (last-seen time):` with the `.partial` path. Re-applied E3 (wrapper narrowed to `(UnitLogError,)`): `1 failed` (`test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log`).
- **What is not fixed.** My round-2 text also named a *refused* write, that is a `DriveError`. That branch is still untested. Break V-F11b narrows the wrapper to `(UnitLogError, OSError)` and gives `156 passed`.
- `DriveError` subclasses `RuntimeError` (`aqis_lab/drive.py:34`), not `OSError`. Under V-F11b a Drive refusal from `touch` leaves the shard loop, which sits outside `run()`'s input `try` block (`aqis_lab/runner/run.py:179-187`). `main`'s `except (DriveError, OSError)` then reports it as `ERROR: cannot write the run folder …`, exit 2.
- **Builder's disclosure.** The builder disclosed the gap in `FIXES.md` ("no test reaches it through the command"). That is true for a subprocess. It is not a hard limit: `main()` called in-process, with `aqis_lab.platform._real_view` replaced by the stand-in Drive `SystemView` that the NFR-0.5-02 `world` fixture already builds, would reach the branch.
- Kept open as MINOR (details under Findings).

**F12.**
- `EVIDENCE.md:67` now reads "the Drive write guard and atomic writes that every WP-0.5 command uses (the older `score`, `pack build` and `registry` writers do not yet: DEBT-014, target WP-0.7)".
- The `aqis_lab/drive.py:1` summary now reads "Google Drive rules for the WP-0.5 commands' writes".
- The builder also fixed the same wording in CAP-DRIVE-003, in the header and in the registry row. This is surgical-fix step 6 (same category), inside the budgeted header, and disclosed in `FIXES.md`.
- The new wording is true: `make_dirs`, `write_bytes` and `append_bytes` each call `check_write_path` and `warn_if_crowded` (`drive.py:83-135`).
- `grep -i "every lab write"` over the records and `aqis_lab/` finds only two quotes of the old wording marked as wrong (`EVIDENCE.md:254`, `drive.py:18` CHANGE LOG).

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | **Dependencies:** `git show origin/main:docs/progress/STATUS.md` lists WP-0.2 and WP-0.4 as `MERGED`. **Branch:** `claude/magical-goldberg-kjvw5r` (not `main`); `HEAD` = `origin/claude/magical-goldberg-kjvw5r` = `f3bde36`; merge-base with `origin/main` = `59619d1` = `origin/main`. **PR:** GitHub API shows PR #5 `open`, `merged False`, head `f3bde36`, base `main`. **Approval:** `docs/approvals/WP-0.5.md` on `main` says `STATUS: APPROVED`, with the round 3 condition "fix WP-0.5-F10 …, WP-0.5-F11 …, and WP-0.5-F12". **Order:** it was merged into the branch (`1290d7c`) before the fix commit `719de94` |
| A2 Requirement coverage | PASS | **Collected** by `pytest --collect-only tests/aqis_lab`: FR_0_5_01 34, FR_0_5_02 18, FR_0_5_03 6, FR_0_5_04 10, FR_0_5_05 26, FR_0_5_06 2, FR_0_5_07 18, FR_0_5_08 43, NFR_0_5_01 1, NFR_0_5_02 2. This is round 2 plus the new `reassign_workdir` case. **Evidence:** `EVIDENCE.md` has a "Round 3" section. **PARTIAL, with owner-accepted debt:** NFR-0.5-01 (DEBT-013) and NFR-0.5-02 (DEBT-014) |
| A3 Acceptance commands | PASS | **AT-0.5-01:** `.venv/bin/python -m aqis_lab doctor --target cloud --out <scratchpad>/doctor`. `platform`, `python`, `lock`, `disk` and `ram` are `PASS`; `gpu` is `SKIP not requested`; `result: PASS`; exit 0. **AT-0.5-02:** see A4. **AT-0.5-03:** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.5` gives `Findings: 0`, `0 findings: OK`, exit 0 |
| A4 Test suites and CI | PASS | **Fast:** `1524 passed, 18 deselected in 168.56s`, exit 0. **Slow CPU**, run alone: `3 passed, 1539 deselected in 8.97s`, exit 0. NFR-0.5-01 printed `fixed overhead 15.1 ms (39.5 %)`; the 5 % limit is DEBT-013. **CI on `f3bde36`** (check-runs, 4 of 4 `completed success`): workflow `aqis-lab-ci`, run 36431687519 (`push`) and run 36431694960 (`pull_request`), jobs `lab` and `harness-regression`. **CI on the code commit `719de94`:** runs 36431204531 and 36431211029, 4 of 4 success |
| A5 Test integrity | PASS | `git diff --name-status --diff-filter=MDR origin/main HEAD -- tests/` is empty. The two test files changed since `d96668d` are new in WP-0.5 (`git cat-file -e origin/main:<file>` fails for both). **Removed lines:** the old `logic_problems` signature and docstring, the old one-line no-logic assert, and the 9 `x = …` inputs. The inputs were rewritten, not dropped, and each is still rejected by its own construct (see F10). No `skip`, `xfail`, `importorskip`, trivial assert or `audit-allow` was added |
| A6 Must-catch proof | PASS | 22 breaks across the 6 behaviours; all 22 fail a named test (table below) |
| A7 Compromise scan | PASS | **Gate:** `Findings: 0`, `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`. **Grep** of lines added since `d96668d` in `aqis_lab`, `tools`, `config`, `notebooks` and `tests`, for the rule-00 words, `NotImplementedError`, bare `pass` and broad `except`: one hit, "temporary", in a test comment describing the atomic write's temporary file. That is not a placeholder. The only production change is docstring text |
| A8 Scope diff | PASS | The changes match the round 3 change budget in `FIXES.md`: the launcher test (F10), the runner test (F11), the `EVIDENCE.md` bullet and the `drive.py` header (F12), and CAP-DRIVE-003 in the header and registry (same F12 category, disclosed). No notebook, config, lock, runbook or `DEBT.md` change. No protected path changed: `tests/aqis_lab/**` is LAB-OWNED, the approval file matches `main`, and the gate reports none |
| A9 Capabilities | PASS | **Rows:** `REGISTRY.md` has 87 rows at `d96668d` and at `HEAD`. All 59 rows from `main` are present and byte-identical. One WP-0.5 row (CAP-DRIVE-003) changed in place. **Header vs registry:** CAP-DRIVE-003 lists the same 6 tests in both places, and both name DEBT-014. `drive.py` has a round 3 CHANGE LOG line. `test_FR_0_0_08_*` (header and registry consistency) pass in the fast suite |
| A10 Contracts | PASS | No contract and no producer changed. **Probe:** a run card from the shipped `run` passes `contracts validate --kind run_card` with `record 1: OK`, `1 valid, 0 invalid`, exit 0 |
| A11 Environment parity | PASS | No production code line changed apart from docstring text, so no path was added. Locks unchanged (`84151d8f…`). Python 3.13.12 against the probe's 3.13.15 (major.minor 3.13, owner decision). `aqis_lab/platform.py` unchanged. OC-0.5-01 and OC-0.5-02 are listed with commands and expected output (`EVIDENCE.md:344-345`) |
| A12 Reproducibility and traceability | PASS | **First run:** `run --task clip-stats --pack data/packs/smoke/v1 --seed 0 --shard-clips 10` gives `6 shard(s) computed`. **Repeat:** `0 shard(s) computed, 6 skipped`. Both give `results.jsonl sha256 48b98c2c…` (60 rows). **Traceability:** every row carries `run_card_id` and `clip_id`, and the card records `git.commit` `f3bde36…` with `dirty: false`. **Hash change:** it differs from round 2's `47f307b4…` only because the card records the commit and the rows carry the card ID |
| A13 Errors and logging | PASS (MINOR F11 residual) | The `OSError` branch of the unit-log wrapper is now tested (E3 caught). The `DriveError` branch is not (V-F11b survives). With that branch removed, a Drive refusal would still exit 2 with the refusal message, under the wrong label. The shipped code labels it correctly. Nothing fails silently |
| A14 Documentation, licences, data | PASS | **F12** is fixed. `EVIDENCE.md` has a "Round 3" section. `FIXES.md` round 3 records the budget, the reproduction, the re-applied breaks and CI. **The builder's reported results match mine:** fast `1524 passed`, slow `3 passed`, gate `0 findings`, CI run IDs. **One overstatement:** `FIXES.md` presents the `DriveError` branch as unreachable here; it is reachable in-process (counted under F11). No new data |
| A15 Exploratory breaks | PASS | 8 breaks, all aimed at the new F10 rule, which is the only logic added or changed since `d96668d`. All 8 are caught (table below). The 3 verification breaks (V-E4, V-E3, V-F11b) check the round-2 findings and are not counted here |

## Must-catch proof (A6)
All 22 breaks ran in `/tmp/aqis-wp05-audit-r3` with the test command above. They are the same 22 breaks as rounds 1 and 2.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Doctor fails on another Python | 1a `doctor.py`: `status = "PASS" if running == expected else "FAIL"` → `status = "PASS"` | `test_FR_0_5_02_fails_on_python_version_other_than_probe` | CAUGHT |
| 1 Doctor fails on a lock difference | 1b `doctor.py`: `elif installed[name] != version:` → `elif False:` | `test_FR_0_5_02_fails_on_package_version_other_than_lock` | CAUGHT |
| 1 | 1c `doctor.py`: installed-but-not-locked loop → `for name in []:` | `test_FR_0_5_02_fails_on_package_missing_from_lock` | CAUGHT |
| 1 | 1d `doctor.py`: "in the lock but not installed" problem → `pass` | `test_FR_0_5_02_fails_on_lock_package_not_installed` | CAUGHT |
| 1 Doctor fails on a missing Drive folder | 1e `doctor.py`: missing `AQIS_LAB` row returns `PASS` | `test_FR_0_5_02_colab_fails_when_aqis_lab_missing` | CAUGHT |
| 1 Doctor fails on a read-only Drive folder | 1f `doctor.py`: write and read-back replaced by `back = data` | `test_FR_0_5_02_colab_fails_when_aqis_lab_read_only`, `…_colab_drive_checks_pass_when_writable` (2 failed) | CAUGHT |
| 1 Any FAIL gives a non-zero exit | 1g `commands/doctor.py`: always `return 0` | `test_FR_0_5_02_any_fail_exits_non_zero`, `…_expect_gpu_fails_without_gpu`, `…_fails_when_target_is_not_this_platform`, `…_colab_fails_when_aqis_lab_read_only`, `test_FR_0_5_07_run_and_doctor_keep_last_seen_current` (5 failed) | CAUGHT |
| 2 Finished shards skipped after an interruption | 2a `runner/run.py`: `if finished:` → `if False:` | 10 failed, including `test_FR_0_5_05_restart_skips_finished_shards` and `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` | CAUGHT |
| 2 Byte-identical results | 2b `runner/run.py`: resume returns the rebuilt card, not the stored one | `test_FR_0_5_05_resume_rule_for_other_cpu_model` | CAUGHT |
| 2 | 2c `runner/run.py`: final join over `reversed(plan["shards"])` | 4 failed, including `test_FR_0_5_05_shard_results_written_atomically_with_marker` | CAUGHT |
| 3 No marker, not finished | 3a `runner/store.py`: a results file without a marker counts as finished | `test_FR_0_5_05_results_without_marker_not_finished`, `test_FR_0_5_06_kill_during_result_write_never_counts` | CAUGHT |
| 3 | 3b `runner/store.py`: marker SHA-256 and size check → `if False:` | `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished[…results sha256…]` | CAUGHT |
| 3 | 3c `runner/store.py`: marker plan check → `if False:` | `test_FR_0_5_05_marker_with_wrong_hash_or_plan_not_finished[…another plan…]` | CAUGHT |
| 4 No logic in the launcher | 4a cell 5 gains `RESULT = 1 if AQIS_TAG else 0` | `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 4 | 4b cell 3 gains `try: import os / except Exception: pass` | `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 4 | 4c cell 4 gains `!ls /content` | 6 failed, including `test_FR_0_5_08_launcher_cells_contain_no_logic` | CAUGHT |
| 5 Platform details only from `aqis_lab.platform` | 5a `runner/card.py`: `"machine": {**machine, "architecture": __import__("os").uname().machine}` | `test_FR_0_5_01_platform_details_only_from_platform_module` | CAUGHT |
| 5 | 5b `commands/unitlog.py`: Colab decided from `"COLAB_RELEASE_TAG" not in os.environ` (with `import os`) | `test_FR_0_5_01_platform_details_only_from_platform_module` | CAUGHT |
| 6 Correct estimate from the rate table | 6a `unitlog.py`: units × `Fraction(101, 100)` | 6 failed: the estimate cases, `…_append_never_rewrites_existing_rows` and `…_unclosed_session_is_closed_at_next_start` | CAUGHT |
| 6 | 6b `unitlog.py`: half-up (`doubled >= denominator`) instead of half-even | `test_FR_0_5_07_appends_row_with_estimate_from_rate_table` (2 A100 cases) | CAUGHT |
| 6 Appends | 6c `unitlog.py`: `append_bytes` → `write_bytes` (overwrite) | `test_FR_0_5_07_append_never_rewrites_existing_rows`, `…_unclosed_session_is_closed_at_next_start` | CAUGHT |
| 6 | 6d `unitlog.py`: unknown runtime falls back to the CPU rate | `test_FR_0_5_07_unknown_runtime_type_is_an_error` | CAUGHT |

**Verification breaks for the round-2 findings** (same copy, same command; not counted under A15):

| Break | Where | Result |
| --- | --- | --- |
| V-E4: cell 2 gains `WORKDIR = "/content/drive/MyDrive"` before `rm -rf WORKDIR` | notebook | CAUGHT: `test_FR_0_5_08_launcher_cells_contain_no_logic` (F10 fixed) |
| V-E3: unit-log wrapper narrowed to `except (UnitLogError,)` | `aqis_lab/commands/run.py`, `main` | CAUGHT: `test_FR_0_5_05_run_io_error_is_not_reported_as_unit_log` (F11 `OSError` half fixed) |
| V-F11b: unit-log wrapper narrowed to `except (UnitLogError, OSError)` | `aqis_lab/commands/run.py`, `main` | **SURVIVES**: `156 passed` (F11 `DriveError` half still untested) |

## Exploratory breaks (A15, at most 10)
All 8 target the new rule "settings are assigned once, in cell 1". Each adds a way to change what a launcher command trusts.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1 cell 3 (install) gains `WORKDIR = "/content/drive/MyDrive"`: a later cell other than cell 2 | notebook | No: `test_FR_0_5_08_launcher_cells_contain_no_logic` ("WORKDIR may not be assigned in this cell") | — |
| X2 cell 2 gains `[WORKDIR] = ["/content/drive/MyDrive"]` before `rm -rf`: a list target | notebook | No: 4 failed, including `…_cells_contain_no_logic` ("assignment to something other than one name") | — |
| X3 cell 2 gains `REPO = "https://github.com/someone-else/other.git"` before the clone | notebook | No: `…_cells_contain_no_logic` | — |
| X4 cell 4 gains `AQIS_DRIVE = "/content/drive/MyDrive"` before `doctor --out AQIS_DRIVE + "/logs"` | notebook | No: 4 failed, `…_cells_contain_no_logic` and the 3 cases of `…_launcher_commands_exist_and_parse` | — |
| X5 cell 2 gains `WORKDIR: str = "/content/drive/MyDrive"`: an annotated assignment, which the exactly-once count does not see | notebook | No: `…_cells_contain_no_logic` ("AnnAssign is logic") | — |
| X6 cell 2's `rm -rf` becomes `["rm", "-rf", (WORKDIR := "/content/drive/MyDrive")]`: a walrus | notebook | No: `…_cells_contain_no_logic` ("NamedExpr is logic"; the command shape is also rejected) | — |
| X7 cell 2 gains `WORKDIR += "/../drive/MyDrive"`, which resolves to the Drive root | notebook | No: `…_cells_contain_no_logic` ("AugAssign is logic") | — |
| X8 cell 1 gains a second `WORKDIR = "/content/drive/MyDrive"` after `drive.mount` | notebook | No: `…_cells_contain_no_logic` (exactly-once check) and `…_runbook_matches_launcher` | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.5-F01 | MAJOR | A2; NFR-0.5-02 | Four older writers (`score --out`, `pack build --out`, `registry build --out`, `registry fetch`) make no Drive check | DEBT-014; approval on `main` | **Accepted as debt, target WP-0.7** (owner decision). Closed for this WP |
| WP-0.5-F02 | MAJOR | A2, A14 | **FIXED in round 2.** The records said every lab write is guarded | Round-2 report | Closed |
| WP-0.5-F03 | MAJOR | A6; must-catch 5 | **FIXED in round 2.** The platform scan was a text match | Breaks 5a and 5b caught again (A6) | Closed |
| WP-0.5-F04 | MAJOR | A15; must-catch 4 | **FIXED in round 2.** Logic inside a command | Breaks 4a to 4c caught again (A6) | Closed |
| WP-0.5-F05 | MAJOR | A15, A12 | **FIXED in round 2.** Resume refusals were untested | Round-2 report; code unchanged | Closed |
| WP-0.5-F06 | MINOR | A15 | **FIXED in round 2.** Staged-manifest reuse check untested | Round-2 report; code unchanged | Closed |
| WP-0.5-F07 | MINOR | A15 | **FIXED in round 2.** Archive-level hash check untested | Round-2 report; code unchanged | Closed |
| WP-0.5-F08 | MINOR | A13 | **FIXED in round 2.** Run I/O errors were reported as unit-log errors | Round-2 report; V-E3 caught | Closed |
| WP-0.5-F09 | MINOR | A14 | **Resolved in round 2.** DEBT-009 re-targeted to WP-0.9 | `DEBT.md` row DEBT-009 | Closed |
| WP-0.5-F10 | MAJOR | A15; FR-0.5-08, NFR-0.5-02 | **FIXED.** The launcher check trusted `WORKDIR` without pinning it | V-E4 caught; X1 to X8 caught | Closed |
| WP-0.5-F11 | MINOR | A13, A15; FR-0.5-05 | **Partly fixed; residual open.** The `DriveError` branch of the unit-log wrapper in `aqis_lab/commands/run.py:68` is untested. Narrowing the wrapper to `(UnitLogError, OSError)` passes all 156 WP-0.5 tests. A Drive refusal of the session-file write would then read `ERROR: cannot write the run folder …` instead of `ERROR: unit log …`. The exit code stays 2 and the refusal text is still printed. The shipped code is correct. The builder disclosed the gap. The stated reason is too strong: an in-process `main()` call with `aqis_lab.platform._real_view` replaced by the NFR-0.5-02 stand-in Drive view reaches the branch | V-F11b survives; `drive.py:34`; `runner/run.py:179-187` | **Accept as debt, target WP-0.7.** WP-0.7 already routes the remaining writers through `aqis_lab.drive` (DEBT-014) and runs on Colab. The builder records the row in `DEBT.md`. Test needed: one in-process case with the `logs` folder linked outside `AQIS_LAB`, expecting `ERROR: unit log`. Not worth reopening the build: the failure is loud, and only the label could go wrong, and only after a future edit |
| WP-0.5-F12 | MINOR | A14 | **FIXED.** Two sentences said every lab write is guarded | `EVIDENCE.md:67`; `drive.py:1` | Closed |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 5 open | 4 open | F03 (must-catch 5), F04 (must-catch 4) |
| 2 | 0 | 1 open (F10, new); 4 fixed; 1 accepted as debt (F01) | 2 open (F11, F12, new); 3 fixed; 1 resolved (F09) | None. All 22 A6 breaks were caught; F10 was a gap in the check behind must-catch 4 |
| 3 | 0 | 0 open; 5 fixed (F10 this round); 1 accepted as debt (F01) | 1 open (F11 residual); 4 fixed (F12 this round); 1 resolved | None. All 22 A6 breaks are caught, and no new finding came out of this round |

Every round has had fewer open findings than the one before, and this round found nothing new. No open finding sits inside the must-catch list. PASS, with F11's residual recorded as debt.

## For the owner
- **audit-allow lines:** None (gate: `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.5.md` on `main` (`59619d1`):
  - questions 2 to 14 as recommended;
  - the Colab unit rates from the Build Plan;
  - BLK-008 option 1 (DEBT-013);
  - round 2: fix F02 to F08, F01 as debt (target WP-0.7), DEBT-009 re-targeted to WP-0.9;
  - round 3: fix F10, F11 and F12.
- **Debt accepted so far for WP-0.5:**
  - DEBT-013 (NFR-0.5-01 5 % target, target WP-0.7);
  - DEBT-014 (F01, older writers without the Drive guard, target WP-0.7);
  - DEBT-009 (re-targeted to WP-0.9).
- **Recommended new debt:** F11 residual (MINOR, `DriveError` branch of the unit-log wrapper untested), target WP-0.7. Under the protocol, MINOR findings do not block; the builder records the `DEBT.md` row.
- **Owner-run checks still pending:**
  - OC-0.5-01: doctor and `pytest -m colab` on a Colab CPU runtime.
  - OC-0.5-02: stop after 2 shards, delete the runtime, resume.

  Both come after the audit passes, from the tag `aqis-lab-wp-0.5-colab-1`, which does not exist yet (`git ls-remote --tags origin` shows none). Create it on the commit you will merge. These are the first real test of atomic rename, folder `fsync` and append on Google Drive's FUSE mount. The committed launcher's `rm -rf` targets `/content/aqis` on local disk, and the notebook can no longer re-point it.
- **Housekeeping, outside WP-0.5:** the legend in `docs/progress/STATUS.md` lists `MERGED` twice and omits `AUDIT-PASS`. I set `AUDIT-PASS`, as the WP-0.3 and WP-0.4 audits did.
