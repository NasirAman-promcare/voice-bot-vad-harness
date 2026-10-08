# AUDIT — WP-0.9, round 3

Auditor: wp-auditor · Date: 2026-10-08 · Commit audited: `fc608085934d21bb412a1c7fb582ce48c71cd9d7` · Previous audited commit: `2155e3da4d2c1d2624a838eb60c10775d0f1735d` · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 · MAJOR: 0 (fixed 0, accepted as debt 0, open 0) · MINOR: 1

All four round 2 findings are fixed (F08 to F11). I checked each one myself; the evidence is under "Round 2 findings" below.
- **F08 (MAJOR).** A move is now approved only by an approval line that names the row (or its finding) and the new WP, each as a whole ID. Round 2's survivor, DEBT-016 quietly moved to WP-4.5 citing `WP-0.9.md`, is now caught by the must-catch test itself.
- **F09 (MAJOR).** A commented-out table can no longer stand in for the visible one. Round 2's probe now reports the same problems as the control.

The complete must-catch proof passes: 32 breaks, all caught. The fast suite, the slow and network tests, the gate and CI on `fc60808` are green. The fast and slow runs had two disk-only failures, both explained under A4.

One new MINOR finding, which does not block. Removing the left boundary of the new `names_id` match leaves every test green (F12). No ID used in this repository can exploit it.

## Scope of this audit
- **Re-audit, round 3**, of branch `claude/great-heisenberg-h85gm9`, pull request #10:
  - head `fc60808`; merge base with `origin/main` `1d82748`;
  - the previous audited commit is `2155e3d`. Seven commits since:
    - the round 2 report `c5ee46c`;
    - the owner's approval `1d82748` on `main`, merged at `464b201`;
    - the fixes `9c1c317`;
    - three record commits `49c57e4`, `bfa2f9a` and `fc60808`;
  - 9 paths changed.
- **Covered:**
  - each round 2 finding: fixed or not, with evidence;
  - A1 to A15 applied to the diff since `2155e3d`;
  - the fast suite, the slow and network tests, the gate and CI;
  - the complete must-catch proof (A6).
- **Not searched again:** code that passed round 1 or round 2 and has not changed since `2155e3d`. That includes `repo_file`, `link_problems`, `audit_rounds`, `body_text`, `pipe_table`, the gate and the phase audit report.
- **Method:**
  - Every break ran alone in a throwaway clone, `/tmp/wp09-audit3`, at `fc60808` with `origin/main` set to `1d82748`. My break script was outside the clone.
  - After each break the clone was reset with `git reset --hard` and `git clean -fd`, then confirmed clean with `git status --porcelain` (recorded for every break).
  - The clone was removed at the end.
  - The F09 probes imported the checker read-only from the repository and edited only copies of the baseline folder in my scratchpad.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `docs/progress/STATUS.md`: WP-0.0 to WP-0.8 MERGED. The branch is not `main`. `git show origin/main:docs/approvals/WP-0.9.md` starts `STATUS: APPROVED` and is byte-identical to the branch copy. It holds "Round 3 Fixes: fix WP-0.9-F08, WP-0.9-F09, WP-0.9-F10, WP-0.9-F11" and the 30-row pin confirmation. Both were added by the owner's commit `1d82748` on `main` (author NasirAman-promcare), merged into the branch at `464b201`. |
| A2 Requirement coverage | PASS | `pytest --collect-only` lists 23 `test_FR_0_9_*` functions (77 cases with parameters): FR-0.9-01 14 functions and 62 cases, FR-0.9-02 5 and 11, FR-0.9-03 4 and 4. Round 2 had 20 functions and 63 cases. The 14 new cases are the three new functions (6 + 3 + 3) plus two `DEBT_BREAKS` cases. Each new test is collected and named in `EVIDENCE.md`, "Round 3". That includes `test_FR_0_1_02_commented_out_table_does_not_hide_the_visible_one` (3 cases), filed under DEBT-030. |
| A3 Acceptance commands | PASS | **AT-0.9-01.** `docs/progress/PHASE-0-AUDIT.md` is unchanged since round 1: `## Verdict: PASS`, commit audited `079571e`, an ancestor of HEAD. Since `079571e`, outside `docs/` only `tools/audit/gate.py` and five test files changed. `git diff --name-only 079571e HEAD -- aqis_lab/ config/` is empty, so the phase audit's PASS still stands. **Plan's command:** `pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9"` gives `77 passed, 1965 deselected in 13.78s`, as `EVIDENCE.md` claims. |
| A4 Test suites and CI | PASS | **Fast suite** at `fc60808`, 13.1 GB free: `1987 passed, 55 deselected in 268.32s (0:04:28)`, as `EVIDENCE.md` claims. My first run, while my clone was on disk, had 5 failures, all in `test_aqis_doctor.py`. The doctor's real disk check read `9,994,133,504 bytes (9.99 GB)` against its 10 GB minimum. With 11.5 GB free, that file gave `17 passed`. **Slow and network tests:** `44 passed, 1 failed, 1997 deselected in 962.34s`. The failure was `test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor`, at `{'disk': 'FAIL'}`, after the run had brought free space down to 9.7 GB. I removed my own pytest temporary folders from this session. With 13.1 GB free, that test gave `1 passed`. As in round 2, three MUSAN tests were left out because their 11 GB archive does not fit: `test_FR_0_4_02_dataset_pins_match_openslr`, `test_FR_0_4_05_rebuild_equals_committed_smoke_pack` and `test_NFR_0_4_01_smoke_build_under_2_minutes`. None of their code changed; the phase audit ran them green at `079571e`. **CI** on `fc60808`: run 401 (push) and run 402 (pull request) both succeeded, jobs `lab`, `lab-network` and `harness-regression`. Every step was success, including "Fast lab test suite" and the "Audit gate" step; run 401's PR-title step was skipped on push. Runs 397 to 400 on `49c57e4` and `bfa2f9a` also succeeded. I read job and step results with `gh run view`. |
| A5 Test integrity | PASS | Four test files changed since `2155e3d`. `aqis_baseline_testutil.py` and `test_aqis_tier2_baseline.py` are on `main` and named by `ALLOW-EDIT` lines on `main`. `aqis_memo_testutil.py` is new in WP-0.9 and also has an `ALLOW-EDIT` line. `test_aqis_phase0_memo.py` is new in WP-0.9 and not on `main`. **Removed lines:** only the old bodies and docstrings of `summary_sections` and `debt_problems`. No test function or case was removed or loosened. The existing `[moved-without-approval]` case and `…_debt_check_covers_every_pinned_row` match the problem text by its unchanged prefix ("no cited approval names"). **Added lines:** no skip, xfail, trivial assert or `audit-allow` (gate, plus my own grep of the added lines). |
| A6 Must-catch proof | PASS | 32 breaks, all caught by a named test (table below): must-catch 1, 14 breaks; must-catch 2, 18 breaks. That includes round 2's F08 survivor as a data break (MC2-p), a second row of the same kind (MC2-q), and both F08 reverts (MC2-r, MC2-s). |
| A7 Compromise scan | PASS | `python -m tools.audit.gate --base origin/main --wp WP-0.9`: `Exempted lines (# audit-allow): 0`, `Findings: 0`, `0 findings: OK (0.6 s)`, exit 0. I read the new and changed code: `debt_problems`, `names_id`, `summary_sections`, `_new_row`, `_set_cell`, `_first_inventory_sha` and the four new tests. There are no stubs, fake data or swallowed errors. The new tests build expected values independently: the finding ID comes from `DEBT.md`; each hidden-table case runs a control without the hidden copy; the F10 cases use paths that exist but are a folder, outside the repository, or escape through `..`. **Real approvals:** I scanned every line of every approval on `main` for a pinned row (or its finding) together with a WP outside phase 0. Only one line qualifies: `WP-0.9.md` Q8, "DEBT-025 moves to WP-4.5", the one real move. **Limit:** a same-line text match would still accept an owner line that names both IDs in some other sense ("DEBT-016 does not move to WP-4.5"). Approvals are owner-only `[NEVER]` files, so I raise no finding. Weak spot: F12. |
| A8 Scope diff | PASS | `git diff -U0 464b201 HEAD` (after the merge) touches 8 files. The code hunks sit only in the budgeted parts: `summary_sections` and its CHANGE LOG line; `debt_problems` and the new `names_id`; two `DEBT_BREAKS` cases, `_new_row` and the three new tests (with their `BAD_PATHS` table); and the new helpers and test in `test_aqis_tier2_baseline.py`. Records: `EVIDENCE.md`, `FIXES.md`, three `REGISTRY.md` Tests cells, `STATUS.md`. I classified the 9 paths changed since `2155e3d` with the hook's own `classify`: 4 `None`, 4 `LAB`, 1 `NEVER`. The `NEVER` path is `docs/approvals/WP-0.9.md`, changed only by the owner's commit `1d82748` on `main`. `docs/progress/WP-0.9/AUDIT.md` changed only in my round 2 commit `c5ee46c`. The F09 fix sits in the shared reader `summary_sections` rather than in `sources_table` and `inventory_table`. It covers those two and `binding_problems` with one change; `FIXES.md` explains this, and `summary_sections` was in the approved budget. |
| A9 Capabilities | PASS | `REGISTRY.md` has 152 rows before and after: none added, none removed, no test dropped (row-by-row comparison of `2155e3d` and HEAD). Tests added: CAP-BASE-002 +1, CAP-DOC-019 +2, CAP-DOC-020 +1. All other cells are unchanged. The descriptions of CAP-DOC-020 and CAP-BASE-002 do not mention the new "one line, whole ID" and "comments removed" details, but they remain true. `aqis_baseline_testutil.py` has a new CHANGE LOG line. Module headers are required only in `aqis_lab/` and `tools/`, and neither changed. The header and registry tests pass in the fast suite. |
| A10 Contracts | N/A | No contract output or validator changed in this round. |
| A11 Environment parity | PASS | No absolute paths in the added code except `/etc/hostname`, which is test input for the "outside the repository" cases. The "escaping" case is built from `ROOT`'s own depth. Both rely on `/etc/hostname` existing, which holds on the Ubuntu VM, Colab and Oracle (Linux). No lock, config or workflow changed. `.venv` is Python 3.13.14; the Colab probe requires 3.13 (bootstrap: `OK: .venv ready: Python 3.13.14`). No new owner-run checks. |
| A12 Reproducibility and traceability | PASS | The new checks and tests are deterministic. Approval files are read in sorted order, and the new tests write only under `tmp_path`. No new result rows. |
| A13 Errors and logging | PASS | `summary_sections` and `names_id` have no error path to swallow. `debt_problems` reports through its problem list. An unclosed `<!--` above the visible Sources table makes the check fail loudly, with 1,027 problems (probe A15-2); it does not pass. |
| A14 Documentation, licences, data | PASS | `EVIDENCE.md`, "Round 3", lists the new tests by requirement and the gate, FR-0.9 and fast-suite runs at `49c57e4`, plus CI runs 398 to 400. I reproduced the gate output, `77 passed` and `1987 passed, 55 deselected`. `FIXES.md`, "Round 3", has the change budget, root causes, tests written first and 6 break proofs; my own breaks confirm all six. No personal data, and no new data that needs a licence. |
| A15 Exploratory breaks | PASS | 7 made (6 code breaks, 1 probe), 1 survived: A15-7, which gives F12 (MINOR). An A15 survivor is never CRITICAL, and this one cannot plausibly make a check report success wrongly (see F12). |

## Round 2 findings
| ID | Severity (round 2) | Status | Evidence |
| --- | --- | --- | --- |
| WP-0.9-F08 | MAJOR | Fixed | **Round 2's survivor.** MC2-p, my re-run of A15-1 (DEBT-016 → `WP-4.5`, ``OPEN (`docs/approvals/WP-0.9.md`, question 5)``), now fails the must-catch test `test_FR_0_9_01_no_open_debt_row_targets_phase_0`. **Second row.** MC2-q does the same with DEBT-009, and the memo names it; it is caught too. **Reverts.** Back to a whole-file match (MC2-r): `[moved-citing-unrelated-lines]` and `[different-lines]` fail. Back to plain substrings (MC2-s): `[longer-debt-id]`, `[longer-finding-id]` and `[longer-wp-id]` fail. **Today's approvals.** The scan in A7 shows that only Q8's line can approve a move, and the real DEBT-025 move still passes. Residual: F12. |
| WP-0.9-F09 | MAJOR | Fixed | **Probe** (no code change, current checker): a commented-out copy of the Sources table above the visible one, with S6's visible Value set to forty `1`s, now gives 2 problems. The control without the hidden copy gives the same 2 problems ("cites S6, whose Value is '1111…'" and the raw-file mismatch); round 2 gave `0 []`. I also probed Raw inventory, which I had not probed in round 2. A hidden copy above it with one visible SHA-256 set to zeros gives 1 problem (`raw/run_config.yaml: SHA-256 f481a0ec…, the Raw inventory says 0000…`). The unedited file, with or without the hidden copy, gives 0 problems. **Revert** R-F09 (`summary_sections` keeps comments): all three cases of `test_FR_0_1_02_commented_out_table_does_not_hide_the_visible_one` fail. |
| WP-0.9-F10 | MINOR | Fixed | R-F10-lesson (lesson path check back to `.exists()`): `test_FR_0_9_01_lessons_cite_files_in_the_repository` fails, all 3 cases. R-F10-plan (Pack v1 plan check back to `.exists()`): `test_FR_0_9_02_pack_v1_plan_cites_files_in_the_repository` fails, all 3 cases. |
| WP-0.9-F11 | MINOR | Fixed | R-F11 (the "targets phase 0 but is OPEN" report limited to pinned rows): `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows[new-unpinned-row-open-at-phase-0]` fails. |

Round 2 also asked the owner to confirm the 30-row pin. The owner did so on `main` (`1d82748`): "Debt IDs: confirmed that pinning all 30 phase 0 rows is correct, overriding the 19 initially named."

## Must-catch proof (A6)
Each break was made alone in `/tmp/wp09-audit3`, and the clone was confirmed clean after each one. I ran `.venv/bin/python -m pytest -q -p no:cacheprovider -rf tests/aqis_lab/test_aqis_phase0_memo.py` (77 tests) each time.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1. Each exit criterion E1 to E6 links to evidence that exists | MC1-a: `git mv` E2's `docs/progress/WP-0.5/OC-0.5-02_runner.log` | `test_FR_0_9_01_exit_criteria_link_evidence_that_exists`, `…_memo_passes_every_check` | CAUGHT |
| 1 | MC1-b: renamed E3's test `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock` in `test_aqis_trace.py` | same two | CAUGHT |
| 1 | MC1-c: `git rm` E1's Oracle bundle `.tar` | same two | CAUGHT |
| 1 | MC1-d: E3's Evidence cell replaced by plain words | same two | CAUGHT |
| 1 | MC1-e: the E6 row deleted from the memo | same two | CAUGHT |
| 1 | MC1-l: E4's first path replaced by the folder `docs/baselines/tier2_vad/2026-10-03` | same two, plus `[folder-link]` and `[renamed-path]` | CAUGHT |
| 1 | MC1-m: E4's first path replaced by `/etc/hostname` | same two, plus `[outside-repository]` and `[renamed-path]` | CAUGHT |
| 1 | MC1-f to MC1-k: checker loosened, one at a time. It no longer checks: (f) path existence and `repo_file`; (g) collected test names; (h) commits; (i) a link in each row; (j) all six rows; (k) the criterion's wording | `test_FR_0_9_01_evidence_check_reports_each_broken_link`, cases (f) `renamed-path`, `folder-link`, `outside-repository`, `escaping-repository`; (g) `unknown-test`; (h) `unknown-commit`; (i) `no-link`; (j) `missing-row`; (k) `changed-criterion` | CAUGHT (6 of 6) |
| 1 | MC1-n: checker no longer applies `repo_file` | `[folder-link]`, `[outside-repository]`, `[escaping-repository]` | CAUGHT |
| 2. Every open phase 0 debt row is closed or moved to a named later WP, with the owner's approval | MC2-a: DEBT-001 Status `OPEN` | `…_no_open_debt_row_targets_phase_0`, `…_open_issues_list_every_open_debt_and_blocker`, `[left-open]`, `…_memo_passes_every_check` | CAUGHT |
| 2 | MC2-b: DEBT-019 Status `OPEN` | `…_no_open_debt_row_targets_phase_0` and 2 more | CAUGHT |
| 2 | MC2-c: DEBT-025's move cites `docs/approvals/WP-0.8.md` | `…_no_open_debt_row_targets_phase_0`, `[moved-without-approval]` | CAUGHT |
| 2 | MC2-d: DEBT-025 moved to WP-4.6 | `…_no_open_debt_row_targets_phase_0`, `[moved-to-unnamed-wp]` | CAUGHT |
| 2 | MC2-e: DEBT-001 `WP-1.0 (moved from WP-0.9)`, `OPEN, moved to WP-1.0`, no approval | `…_no_open_debt_row_targets_phase_0` and 3 more | CAUGHT |
| 2 | MC2-f: DEBT-001 `WP-1.0`, `OPEN`, no "moved", `DEBT.md` only | `…_no_open_debt_row_targets_phase_0` and 3 more | CAUGHT |
| 2 | MC2-g: as MC2-f, and the memo names DEBT-001 | `…_no_open_debt_row_targets_phase_0`, `[left-open]` | CAUGHT |
| 2 | MC2-h: DEBT-019 `WP-1.0`, ``OPEN (`docs/approvals/WP-0.9.md`)``, no "moved"; the memo names it | `…_no_open_debt_row_targets_phase_0` | CAUGHT |
| 2 | MC2-l: the DEBT-019 row deleted | `…_no_open_debt_row_targets_phase_0`, `…_debt_check_covers_every_pinned_row[DEBT-019]` | CAUGHT |
| 2 | MC2-p (new; round 2's F08 survivor): DEBT-016 `WP-4.5`, ``OPEN (`docs/approvals/WP-0.9.md`, question 5)`` | `…_no_open_debt_row_targets_phase_0`, `[moved-citing-unrelated-lines]` | CAUGHT |
| 2 | MC2-q (new): DEBT-009 `WP-4.5`, ``OPEN (`docs/approvals/WP-0.9.md`, question 5)``; the memo names it | `…_no_open_debt_row_targets_phase_0` | CAUGHT |
| 2 | MC2-j: checker ignores open phase 0 targets | `…_debt_check_covers_every_pinned_row` (30 cases), `[left-open]`, `[new-unpinned-row-open-at-phase-0]` (32 failed) | CAUGHT |
| 2 | MC2-k: checker no longer reads the move approval | `…_debt_check_covers_every_pinned_row` (30 cases), `[moved-without-approval]`, `[moved-citing-unrelated-lines]` and the four not-approved cases of `…_move_approval_names_row_and_wp_on_one_line` (36 failed) | CAUGHT |
| 2 | MC2-m: checker no longer reports a missing pinned row | `…_debt_check_covers_every_pinned_row` (30 cases) | CAUGHT |
| 2 | MC2-n: checker back to selecting rows by the word "moved" | `…_debt_check_covers_every_pinned_row` (30 cases), `[moved-citing-unrelated-lines]` and the four not-approved one-line cases (35 failed) | CAUGHT |
| 2 | MC2-o: DEBT-019 dropped from `PHASE0_DEBT_IDS` | `…_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09` | CAUGHT |
| 2 | MC2-r (new): F08 reverted, each cited approval matched as one block of text | `[moved-citing-unrelated-lines]`, `…_move_approval_names_row_and_wp_on_one_line[different-lines]` | CAUGHT |
| 2 | MC2-s (new): `names_id` reverted to a plain substring test | `…_move_approval_names_row_and_wp_on_one_line[longer-debt-id]`, `[longer-finding-id]`, `[longer-wp-id]` | CAUGHT |

As in rounds 1 and 2, MC2-i is not counted: a pinned row set to `CLOSED` with no approval cited and no evidence. The approved plan asks for an approval citation only on moved rows, and closures rest on the approval's Q2 table.

## Exploratory breaks (A15, at most 10)
Only in code added or changed since `2155e3d`. My re-checks of round 2's findings are listed under "Round 2 findings" and not counted here. Unless the row says otherwise, I ran the 77 tests of `test_aqis_phase0_memo.py`. For A15-1 I ran `test_FR_0_1_02_commented_out_table_does_not_hide_the_visible_one`.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| A15-1: comments removed only within one line (`re.S` dropped) | `aqis_baseline_testutil.summary_sections` | No: `[sources]`, `[raw-inventory]` and `[headline-binding]` failed | — |
| A15-2: probe, no code change. An unclosed `<!--` and an unedited copy of the Sources table above the visible one, which has S6 set to forty `1`s | `summary_sections` and `body_text` | No issue: 1,027 problems with or without the visible edit. The check fails loudly rather than passing. A renderer would hide the rest of the page, so no wrong value is shown as checked | — |
| A15-3: the row's ID may be on any line of the cited approvals; only the new WP must be on the matching line | `aqis_memo_testutil.debt_problems` | No: `[moved-citing-unrelated-lines]`, `[different-lines]` failed | — |
| A15-4: the new WP may be on any line; only the row's ID must be on the matching line | `debt_problems` | No: the same two failed | — |
| A15-5: the finding-ID route dropped (only the debt ID approves) | `debt_problems` | No: `[finding-and-wp]` failed | — |
| A15-6: `repo_file`'s containment test removed, so a path that escapes through `..` counts as a file. This tests the new F10 cases | `repo_file`, as used by the new tests | No: `[escaping-repository]` failed in all three tests that have it (evidence links, lessons, Pack v1 plan) | — |
| A15-7: `names_id` without its look-behind `(?<![\w.-])` | `aqis_memo_testutil.names_id` | Yes: `77 passed`. Every "longer ID" case extends the ID on the right (`DEBT-0160`, `WP-0.6-F060`, `WP-4.50`); none puts characters before it | MINOR → F12 |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.9-F12 | MINOR | A15 | `names_id`'s left boundary has no test. Without it, a longer ID that ends in the row's ID or the new WP's ID would count as naming it, for example `XDEBT-016` or `AWP-4.5`. The docstring promises "not as part of a longer one", and the tests check only IDs extended on the right. No ID scheme in this repository produces such a string: DEBT, WP, finding, BLK and PH0 IDs all stand alone. Approvals are owner-only files. So the risk that a quiet move passes this way is very low. | A15-7; `tests/aqis_lab/aqis_memo_testutil.py` `names_id`; `tests/aqis_lab/test_aqis_phase0_memo.py` `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line` | **Accept as debt (WP-1.0).** Add one case, such as `"- X{debt} moves to {wp}."` → not approved, to `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line`. |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 2 | F01 (must-catch 2) |
| 2 | 0 | 2 | 2 | None inside the list. F08 sat in must-catch 2's area, but as an A15 survivor (MAJOR) |
| 3 | 0 | 0 | 1 | None. F12 is in must-catch 2's code (`names_id`), but it is an A15 survivor with no realistic path, and all 18 must-catch 2 breaks are caught |

The counts fall each round, and no open finding sits inside the must-catch list. My recommendation to the owner is **PASS, with F12 recorded as debt for WP-1.0**.

## For the owner
- **audit-allow lines:** None.
- **Approvals used:**
  - `docs/approvals/WP-0.9.md` on `main` (`1d82748`): Q1 to Q10, the six `ALLOW-EDIT` lines, the unit-log note, "Round 2 Fixes", "Debt IDs" and "Round 3 Fixes".
  - Round 3 used the `ALLOW-EDIT` lines for `aqis_baseline_testutil.py`, `test_aqis_tier2_baseline.py` and `aqis_memo_testutil.py`. `test_aqis_phase0_memo.py` is new in WP-0.9 and not on `main`.
- **Debt accepted so far** (unchanged since round 1):
  - DEBT-025, moved to WP-4.5 (Q8);
  - DEBT-032 and DEBT-033, phase audit MINORs, target WP-1.0;
  - DEBT-027, phase 2;
  - DEBT-009, DEBT-016 and DEBT-005 K11.5b, closed as recorded permanent limits (Q5).
- **To record before merge:** F12 (MINOR) as a `DEBT.md` row, target WP-1.0. The protocol has the builder record MINORs. A new OPEN row must also be named in the memo's Open issues. Otherwise `test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker` and `test_FR_0_9_01_memo_passes_every_check` fail, as `open_issue_problems` requires.
- **Owner-run checks still pending:** None for WP-0.9; AT-0.9-01 and OC-0.9-01 are done. DEBT-032 carries the full `dev_bootstrap.sh --gpu` output on a Colab GPU runtime to WP-1.0.
- **Environment notes from this audit:**
  - The doctor's disk check (10 GB minimum, `config/aqis_lab/doctor.yaml`) runs against the real file system in the fast and slow suites. On this VM, free space was 9.7 to 13.1 GB during the audit. Five doctor tests and one Oracle setup test failed whenever free space dipped below 10 GB, and passed again above it. This is not a WP-0.9 problem. Auditors and builders on this VM should check `df` before quoting a red suite.
  - The three MUSAN tests were again not run (11 GB archive), so nothing was downloaded.
  - I removed my clone `/tmp/wp09-audit3` and my own pytest temporary folders from this session. `/tmp/wp09-breaks` (the builder's clone), `/tmp/phase0-audit` and `/tmp/phase0-audit2` are not mine, and I left them.
