# FIXES — WP-0.9

## Round 2 (audit round 1 findings WP-0.9-F01 to F07)
Owner approval: `docs/approvals/WP-0.9.md` on `main` (`604e9a4`): "Round 2 Fixes: fix WP-0.9-F01, WP-0.9-F02, WP-0.9-F03, WP-0.9-F04, WP-0.9-F05, WP-0.9-F06, and WP-0.9-F07", with the owner's instructions in the session chat (2026-10-08). Branch merged with `origin/main` at `7c1f147`.

### Change budget
| File | Functions or parts | Findings | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| `tests/aqis_lab/aqis_memo_testutil.py` | `debt_problems`, new constants `PHASE0_DEBT_IDS`, `REVIEWED_WPS`, `WP09_START`; `audit_rounds`; `link_problems` and new helper `repo_file` (also used by the lesson and Pack v1 plan path checks) | F01, F02, F07 | F01: phase 0 rows were found by their current Target cell, and an approval was required only of rows that call themselves moved. F02: the round table read every `WP-0.*/AUDIT.md`, including WP-0.9's own. F07: a path counted as evidence when anything existed there, inside the repository or not | CAP-DOC-019, CAP-DOC-020 |
| `tests/aqis_lab/test_aqis_phase0_memo.py` | new break cases and tests (WP-0.9's own test file, new in this WP) | F01, F02, F03, F07 | F03: four checks had no case that fails when the check is removed | CAP-DOC-019, CAP-DOC-020 |
| `docs/progress/PHASE0_MEMO.md` | "Lessons for the process": the sentence before the round table | F02 | the memo did not say which WPs the table covers | CAP-DOC-019 |
| `tools/audit/gate.py` | `_ignores_for`, `_pytest_skips`, `test_functions` (the call only), module docstring | F04 | conftests were read only between the file and the collected folder; pytest also applies those above it, up to the rootdir (the repository root, where CI runs pytest) | CAP-AUDIT-005, CAP-AUDIT-006 |
| `tests/aqis_lab/test_aqis_debt_wp09.py` | new test for a conftest above the collected folder (WP-0.9's own test file) | F04 | | CAP-AUDIT-005, CAP-AUDIT-006 |
| `docs/tools/AUDIT_GATE.md` | the conftest rule | F04 | | — |
| `tests/aqis_lab/aqis_baseline_testutil.py` | `body_text` | F05 | every `ID`-headed table in Sources was exempt, not only the one `sources_table` reads (the first); the same held for `Item`-headed tables in Raw inventory (fixed as the same category) | CAP-BASE-002 |
| `tests/aqis_lab/test_aqis_tier2_baseline.py` | `UNCITED_INSERTS`: two new cases (Sources and Raw inventory) | F05 | | CAP-BASE-002 |
| `docs/progress/WP-0.9/EVIDENCE.md` | a "Deviations from the plan" section; round 2 results | F06 | the changes to planned tests were not recorded | — |
| `docs/capabilities/REGISTRY.md` | Tests cells of CAP-DOC-019, CAP-DOC-020, CAP-AUDIT-005, CAP-AUDIT-006, CAP-BASE-002 | all | | — |

`tests/aqis_lab/aqis_baseline_testutil.py` and `tests/aqis_lab/test_aqis_tier2_baseline.py` are existing test files; the approval's `ALLOW-EDIT` lines name both.

**F01: which IDs are pinned.** The owner asked to pin "the 19 Phase 0 DEBT IDs (DEBT-001 through 007, 009, 010, 012-021)". `DEBT.md` at `254c1e3` (the commit WP-0.9 started from) has 30 rows with a phase 0 target: DEBT-001 to DEBT-026 and DEBT-028 to DEBT-031. The 19 that targeted WP-0.9 are DEBT-001 to 007, 009, 016, 019, 022 to 026 and 028 to 031. The owner's list omits DEBT-022 to 026 and 028 to 031, among them DEBT-025, the only moved row, and includes rows that targeted other phase 0 WPs. Pinning only those 19 would leave nine rows exposed to the very bypass F01 describes. So `PHASE0_DEBT_IDS` pins all 30. That set contains every ID the owner named, so it is strictly stronger, never weaker. A test also checks that the pinned set equals the phase 0 rows of `DEBT.md` at `254c1e3`, read with `git show`.

### Baseline before the change
`.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_debt_wp09.py tests/aqis_lab/test_aqis_tier2_baseline.py tests/aqis_lab/test_aqis_gate_registry.py tests/aqis_lab/test_aqis_gate_trace.py tests/aqis_lab/test_aqis_gate_parity.py tests/aqis_lab/test_aqis_gate_checks.py tests/aqis_lab/test_aqis_gate_v2.py -q -p no:cacheprovider` → `2 failed, 234 passed in 64.50s`. The two failures are F02: `test_FR_0_9_01_audit_round_counts_and_lessons_cite_records` and `test_FR_0_9_01_memo_passes_every_check`, because round 1's `docs/progress/WP-0.9/AUDIT.md` now exists.

### Fixes and their tests
Each new test was run before its fix and failed for the reason named. Commands from the repository root:

| Finding | Fix | Test (first run, before the fix) |
| --- | --- | --- |
| F01 | `PHASE0_DEBT_IDS` pins the 30 IDs. `debt_problems` reports a pinned row that is missing. A pinned row that is not CLOSED must name a later WP first in its Target cell and cite an approval naming the row (or its finding) and that WP, whatever its wording. | `test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09`; `test_FR_0_9_01_debt_check_covers_every_pinned_row` (30 cases: reopened at WP-0.9, quietly moved to WP-1.0, deleted). First run: `ImportError` (`PHASE0_DEBT_IDS` did not exist). |
| F02 | `audit_rounds` reads only `REVIEWED_WPS` (WP-0.0 to WP-0.8); the memo's sentence before the round table says so. | `test_FR_0_9_01_audit_rounds_cover_only_the_reviewed_wps`; the baseline's two F02 failures pass. |
| F03 | Tests only (the checks existed): X1, X2, X8, X9. | `test_FR_0_9_03_memo_verdict_and_commit_must_be_the_reports`, `test_FR_0_9_03_audited_commit_must_be_an_ancestor_of_head`, `test_FR_0_9_02_unit_log_check_reports_a_wrong_row` (estimate, hours, rate), `test_FR_0_9_02_owner_quotes_must_be_in_the_approval` (3 quotes). They pass on the current code; the break proofs below show each fails when its check is removed. |
| F04 | `_ignores_for(directory, root, cache)` walks to the repository root. `_pytest_skips` passes `root`; the docstrings and `docs/tools/AUDIT_GATE.md` say so. | `test_FR_0_0_09_index_applies_conftests_above_the_collected_folder` (2 cases; pytest itself is the oracle). First run: `2 failed`, `assert [] == [('E3', 6)]` (the gate counted tests that pytest does not collect). |
| F05 | `body_text` exempts only the first `ID` table of Sources and the first `Item` table of Raw inventory. | `test_FR_0_1_02_check_reports_uncited_numbers_in_every_section[sources-second-table-same-header]` and `[inventory-second-table-same-header]`. First run: `2 failed, 9 passed`. |
| F06 | "Deviations from the plan" in `EVIDENCE.md`. | record only |
| F07 | `repo_file`: a link must be a regular file inside the repository (no folder, no absolute path, no `..` or link out of it). | `test_FR_0_9_01_evidence_check_reports_each_broken_link[folder-link]`, `[outside-repository]` and `[escaping-repository]`. First run: `3 failed` (no problem reported). |

### Break proofs
Each break was applied alone in a clone at `1a06c4a` (`/tmp/wp09-breaks`); the named tests were run, then the file was restored. Afterwards the clone was clean. Every break was caught:

| Break | What it removes | Failing tests |
| --- | --- | --- |
| F01-wording | rows need an approval only if they say "moved" | `test_FR_0_9_01_debt_check_covers_every_pinned_row`, all 30 cases |
| F01-deleted | the missing-row report | the same 30 cases |
| F01-19-ids | pin only the owner's 19 IDs | `test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09` |
| F01-MC2-h | (data) DEBT-019 rewritten to WP-1.0, OPEN, no "moved", citing only `WP-0.9.md` | `test_FR_0_9_01_no_open_debt_row_targets_phase_0`, `…_open_issues_list_every_open_debt_and_blocker`, `…_memo_passes_every_check` |
| F02 | `REVIEWED_WPS` widened to WP-0.9 | `test_FR_0_9_01_audit_rounds_cover_only_the_reviewed_wps`, `…_audit_round_counts_and_lessons_cite_records`, `…_memo_passes_every_check` |
| X1-verdict, X1-commit | the verdict, then the commit comparison | `test_FR_0_9_03_memo_verdict_and_commit_must_be_the_reports` |
| X2-ancestor | the ancestor check | `test_FR_0_9_03_audited_commit_must_be_an_ancestor_of_head` |
| X8-estimate, X8-hours, X8-rate | each unit log comparison | `test_FR_0_9_02_unit_log_check_reports_a_wrong_row`, the matching case each time |
| X9-quotes | the quote comparison | `test_FR_0_9_02_owner_quotes_must_be_in_the_approval`, all 3 cases |
| F07 | the `repo_file` check | `test_FR_0_9_01_evidence_check_reports_each_broken_link[folder-link]`, `[outside-repository]`, `[escaping-repository]` |
| F04 | conftests read only up to the collected folder | `test_FR_0_0_09_index_applies_conftests_above_the_collected_folder`, both cases |
| F05 | every `ID`/`Item` table exempt | `test_FR_0_1_02_check_reports_uncited_numbers_in_every_section[sources-second-table-same-header]`, `[inventory-second-table-same-header]` |

### Verification
The baseline modules after the change: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_debt_wp09.py tests/aqis_lab/test_aqis_tier2_baseline.py tests/aqis_lab/test_aqis_gate_registry.py tests/aqis_lab/test_aqis_gate_trace.py tests/aqis_lab/test_aqis_gate_parity.py tests/aqis_lab/test_aqis_gate_checks.py tests/aqis_lab/test_aqis_gate_v2.py -q -p no:cacheprovider` → `283 passed in 69.06s (0:01:09)` (before: `2 failed, 234 passed`; the 47 added are this round's new tests and cases).

`git diff -U0 7c1f147 HEAD` touches only the files and functions in the change budget. Fast suite at `35d214e`: `1970 passed, 55 deselected`. Gate: 0 findings. CI runs 388 and 389 on `35d214e`: success, all three jobs. Details in `EVIDENCE.md`, "Round 2".

## Round 3 (audit round 2 findings WP-0.9-F08 to F11)
Owner approval: `docs/approvals/WP-0.9.md` on `main` (`1d82748`): "Round 3 Fixes: fix WP-0.9-F08, WP-0.9-F09, WP-0.9-F10, WP-0.9-F11", and "Debt IDs: confirmed that pinning all 30 phase 0 rows is correct". Instructions in the session chat (2026-10-08). Branch merged with `origin/main` at `464b201`.

### Change budget
| File | Functions or parts | Findings | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| `tests/aqis_lab/aqis_memo_testutil.py` | `debt_problems` (the approval match and its docstring); new helper `names_id` | F08 | an approval counted when the whole file named the row and the new WP anywhere, as plain substrings | CAP-DOC-020 |
| `tests/aqis_lab/test_aqis_phase0_memo.py` | `DEBT_BREAKS`: two cases; new helper `_new_row`; new tests `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line`, `test_FR_0_9_01_lessons_cite_files_in_the_repository`, `test_FR_0_9_02_pack_v1_plan_cites_files_in_the_repository` (WP-0.9's own test file) | F08, F10, F11 | F10, F11: checks without a case that fails when they are removed | CAP-DOC-019, CAP-DOC-020 |
| `tests/aqis_lab/aqis_baseline_testutil.py` | `summary_sections` | F09 | the section reader kept HTML comments, while `body_text` removed them. So `sources_table`, `inventory_table` and `binding_problems` could read a commented-out table, while the visible one was exempt and never compared | CAP-BASE-002 |
| `tests/aqis_lab/test_aqis_tier2_baseline.py` | new helpers `_set_cell`, `_first_inventory_sha`, `HIDDEN_TABLE_EDITS`; new test `test_FR_0_1_02_commented_out_table_does_not_hide_the_visible_one` | F09 | | CAP-BASE-002 |
| `docs/progress/WP-0.9/EVIDENCE.md`, `docs/capabilities/REGISTRY.md` (Tests cells of CAP-DOC-019, CAP-DOC-020, CAP-BASE-002), `docs/progress/STATUS.md` | records | all | | — |

**F09 fix location.** The owner asked for comments to be removed before `sources_table` and `inventory_table` parse. Both read their section through `summary_sections`, and so does `binding_problems` (the per-row tables). Removing comments in `summary_sections` therefore covers the two named readers and the third reader of the same kind with one change (skill step 6, "fix the category"). The committed summaries contain no HTML comment (`grep -c "<!--"`: 0), so their results do not change.

**F08 whole-ID matching.** The auditor also noted that the finding-ID match was a plain substring match (`WP-0.1-F4` would match `WP-0.1-F40`). `names_id` matches the debt ID, the finding ID and the WP ID each as a whole ID. The Q8 line ("DEBT-025 moves to WP-4.5") still approves the one real move.

### Baseline before the change
At `464b201` (after the merge, before any round 3 change), in the clone `/tmp/wp09-breaks`: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_debt_wp09.py tests/aqis_lab/test_aqis_tier2_baseline.py tests/aqis_lab/test_aqis_gate_registry.py tests/aqis_lab/test_aqis_gate_trace.py tests/aqis_lab/test_aqis_gate_parity.py tests/aqis_lab/test_aqis_gate_checks.py tests/aqis_lab/test_aqis_gate_v2.py -q -p no:cacheprovider` → `283 passed in 69.72s`.

### Tests first
- F08: `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows[moved-citing-unrelated-lines]` (A15-1: DEBT-016 → WP-4.5, OPEN, citing `WP-0.9.md`, question 5). `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line` has six cases on a copy of the approvals folder holding one approval line: the debt and the WP; the finding and the WP; different lines; a longer finding ID; a longer debt ID; a longer WP ID. First run, before the fix: `5 failed, 72 passed` (A15-1 and the four "not approved" cases).
- F09: `test_FR_0_1_02_commented_out_table_does_not_hide_the_visible_one`, with cases `[sources]` (A15-5: S6's Value set to forty `1`s), `[raw-inventory]` (one SHA-256 set to zeros) and `[headline-binding]` (two Headline rows swapped). Each runs a control without the hidden copy, then the same edit under an unedited commented-out copy. First run: `3 failed`. Each failure was the hidden case ("the edited visible table passed (hidden copy above it: True)"); every control was reported.
- F10, F11: `test_FR_0_9_01_lessons_cite_files_in_the_repository` and `test_FR_0_9_02_pack_v1_plan_cites_files_in_the_repository` (cases folder, outside the repository, escaping through `..`), and `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows[new-unpinned-row-open-at-phase-0]` (a new DEBT-034, target WP-0.9, OPEN). These cover checks that already worked, so they passed at once; the break proofs below show each fails when its check is removed.

### Break proofs
Each break was applied alone in the clone at `9c1c317`, the named tests were run, and the file was restored. The clone was clean afterwards. Runner: `builder_breaks.py` in the session scratchpad; the earlier `breaks.py` there had been replaced by the auditor's own script.

| Break | What it removes | Result |
| --- | --- | --- |
| F08-whole-file | back to "the cited files name both, anywhere" | CAUGHT: `[moved-citing-unrelated-lines]`, `[different-lines]`, `[longer-finding-id]`, `[longer-debt-id]`, `[longer-wp-id]` |
| F08-substring | `names_id` back to a plain substring test | CAUGHT: `[longer-finding-id]`, `[longer-debt-id]`, `[longer-wp-id]` |
| F09 | `summary_sections` keeps comments again | CAUGHT: `[sources]`, `[raw-inventory]`, `[headline-binding]` |
| F10-lesson (A15-2) | lesson path check back to `.exists()` | CAUGHT: `test_FR_0_9_01_lessons_cite_files_in_the_repository`, all 3 cases |
| F10-plan (A15-3) | Pack v1 plan path check back to `.exists()` | CAUGHT: `test_FR_0_9_02_pack_v1_plan_cites_files_in_the_repository`, all 3 cases |
| F11 (A15-4) | "targets phase 0 but is OPEN" limited to pinned rows | CAUGHT: `[new-unpinned-row-open-at-phase-0]` |

### Verification
Baseline modules after the change, same command: `300 passed in 70.09s` (283 before; the 17 added are this round's new tests and cases). `git diff -U0 464b201` touches only the budgeted functions and records. Fast suite, gate and CI: `EVIDENCE.md`, "Round 3".
