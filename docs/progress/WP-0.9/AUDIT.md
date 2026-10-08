# AUDIT — WP-0.9, round 2

Auditor: wp-auditor · Date: 2026-10-08 · Commit audited: `2155e3da4d2c1d2624a838eb60c10775d0f1735d` · Previous audited commit: `f729dc05f91d84bd9a5bdddf265e4c82104058de` · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 2 (fixed 0, accepted as debt 0, open 2) · MINOR: 2

Round 1 findings: all 7 are fixed (F01 to F07). I checked each one myself; the evidence is under "Round 1 findings" below. The full must-catch proof passes: 28 breaks, all caught. The fast suite, the slow and network tests I could run, the gate and CI on `2155e3d` are all green.

The verdict is FAIL because two exploratory breaks of this round's new code survive, and each can make a check report success wrongly:
- **WP-0.9-F08 (MAJOR, must-catch 2 area).** The approval check accepts a cited approval that mentions the row and the new WP anywhere in its text, even in unrelated conditions. Example: DEBT-016 is rewritten to `WP-4.5`, `OPEN`, citing only `docs/approvals/WP-0.9.md`. That approval closes DEBT-016 (Q5) and moves a different row, DEBT-025, to WP-4.5 (Q8). All 125 FR-0.9, debt and memo tests pass. Before round 2, only rows that called themselves "moved" reached this check. Now it is the only guard against a quiet move of the 30 pinned rows.
- **WP-0.9-F09 (MAJOR).** The F05 fix exempts "the first Sources table headed ID". `body_text` finds that table after removing HTML comments, but `sources_table` reads the text with comments left in. A commented-out copy of the Sources table placed above the visible one is what `sources_table` reads, and the visible table is exempt. So a wrong value in the visible table passes with 0 problems. The round 1 code passed this probe too, so it is a gap the fix left open, not a regression.

## Scope of this audit
- **Re-audit, round 2**, of branch `claude/great-heisenberg-h85gm9`, pull request #10:
  - head `2155e3d`; merge base with `origin/main` `604e9a4`;
  - the previous audited commit is `f729dc0`; 7 commits since: the round 1 report `3b2f6f0`, the owner's approval `604e9a4` merged at `7c1f147`, the fixes `1a06c4a`, and three record commits;
  - 14 paths changed.
- **Covered:**
  - each round 1 finding: fixed or not, with evidence;
  - A1 to A15 applied to the diff since `f729dc0`;
  - the fast suite, the slow and network tests, the gate and CI;
  - the complete must-catch proof (A6).
- **Not searched again:** code that passed round 1 and has not changed. That includes the memo checks outside `debt_problems`, `audit_rounds`, `link_problems` and `repo_file`; the phase audit report; and the debt work from round 1.
- **Method:**
  - Every break ran alone in a throwaway clone, `/tmp/wp09-audit2`, at `2155e3d` with `origin/main` set to `604e9a4`. My break scripts were outside the clone.
  - After each break the clone was reset with `git reset --hard` and `git clean -fd`, then confirmed clean with `git status --porcelain`. The clone was removed at the end.
  - The F09 probe ran the clone's checker on a copy of the baseline folder in my scratchpad.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `docs/progress/STATUS.md`: WP-0.0 to WP-0.8 MERGED. The branch is not `main`. `git show origin/main:docs/approvals/WP-0.9.md` starts `STATUS: APPROVED` and is byte-identical to the branch copy. It holds the line "Round 2 Fixes: fix WP-0.9-F01, … and WP-0.9-F07", added by the owner's commit `604e9a4` on `main` (author NasirAman-promcare). That commit was merged into the branch at `7c1f147`. |
| A2 Requirement coverage | PASS | `pytest --collect-only` lists 20 `test_FR_0_9_*` functions (63 cases with parameters): FR-0.9-01 12, FR-0.9-02 4, FR-0.9-03 4. `EVIDENCE.md` covers FR-0.9-01 to FR-0.9-03 and AT-0.9-01. It also has a "Round 2" section listing the new tests by requirement, and a "Deviations from the plan" section (F06). The gate's traceability check (`--wp WP-0.9`) reports 0 findings. |
| A3 Acceptance commands | PASS | **AT-0.9-01.** `docs/progress/PHASE-0-AUDIT.md` has not changed since round 1: `## Verdict: PASS`, commit audited `079571e`, which is an ancestor of HEAD. Since `079571e`, the only changes outside `docs/` are `tools/audit/gate.py` and five test files (`git diff --name-only 079571e HEAD`). No `aqis_lab/` product code changed, so the phase audit's PASS still stands. **Plan's command:** `pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9"` gives `63 passed, 1962 deselected in 2.62s`. |
| A4 Test suites and CI | PASS | **Fast suite** at `2155e3d`: `1970 passed, 55 deselected in 284.22s (0:04:44)`. This run includes round 1's `AUDIT.md`, so F02 no longer breaks it. **Slow and network tests:** `45 passed, 1980 deselected in 915.74s`. Three MUSAN tests were left out: `test_FR_0_4_02_dataset_pins_match_openslr`, `test_FR_0_4_05_rebuild_equals_committed_smoke_pack` and `test_NFR_0_4_01_smoke_build_under_2_minutes`. Their 11 GB archive does not fit the 11 GB free on this VM. This round changes none of their code; the phase audit ran them green at `079571e`. **CI** on `2155e3d`: run 392 (push) and run 393 (pull request) both succeeded, jobs `lab`, `lab-network` and `harness-regression`. Every step was success (run 392's PR-title step was skipped on push), including "Fast lab test suite" and the "Audit gate" step. I read job and step results with `gh run view`. The logs themselves could not be downloaded: the proxy refuses `results-receiver.actions.githubusercontent.com` and `productionresultssa5.blob.core.windows.net`. As round 1 predicted, runs 385 and 386 on the round 1 report commit `3b2f6f0` failed in `lab` (F02). |
| A5 Test integrity | PASS | Five test files changed since `f729dc0`. **New in WP-0.9** (not on `origin/main`): `aqis_memo_testutil.py`, `test_aqis_phase0_memo.py` and `test_aqis_debt_wp09.py`. **Existing**, each named by an `ALLOW-EDIT` line on `main`: `aqis_baseline_testutil.py` and `test_aqis_tier2_baseline.py`. **Removed lines:** `test_aqis_tier2_baseline.py`, none (two cases added). `aqis_baseline_testutil.py`, only `body_text`'s exemption condition (narrowed to the first table) and its docstring. **Added lines:** 233 in `tests/` and `tools/`, with no skip, xfail, trivial assert or `audit-allow` (gate, plus my own grep). |
| A6 Must-catch proof | PASS | 28 breaks, all caught by a named test (table below): must-catch 1, 14 breaks; must-catch 2, 14 breaks. Round 1's survivor MC2-h is now caught by the must-catch test itself. |
| A7 Compromise scan | PASS | `python -m tools.audit.gate --base origin/main --wp WP-0.9`: `Exempted lines (# audit-allow): 0`, `Findings: 0`, `0 findings: OK (0.8 s)`, exit 0. I read the new and changed code: `debt_problems`, `repo_file`, `link_problems`, `audit_rounds`, `body_text`, `_ignores_for`, `_pytest_skips` and the new tests. There are no stubs, fake data or swallowed errors. The new tests compute expected values independently: the pinned IDs are compared with `git show 254c1e3:docs/progress/DEBT.md`, and the root-conftest case uses the pinned pytest as its oracle. Weak spots: F08 and F09. |
| A8 Scope diff | PASS | `git diff --stat 7c1f147 HEAD` (after the merge) changes 12 files, each in the change budget in `FIXES.md`. Per-path classification with the hook's own `classify` (14 paths since `f729dc0`): 8 `None`, 5 `LAB`, 1 `NEVER`. The `NEVER` path is `docs/approvals/WP-0.9.md`, changed only by the owner's commit `604e9a4` on `main` (`git log f729dc0..HEAD -- docs/approvals/WP-0.9.md` shows only that commit). Two small mismatches with the budget's wording, neither a finding: (a) the budget lists the Tests cells of CAP-AUDIT-006 and CAP-BASE-002, but those cells did not change (the F05 cases are parameters of an existing CAP-BASE-002 test); (b) "test_functions (the call only)" was in practice a docstring change in `test_functions`. |
| A9 Capabilities | PASS | `REGISTRY.md` has 152 rows before and after: none added, none removed, no test dropped from any row (row-by-row comparison of `f729dc0` and HEAD). Tests added: CAP-AUDIT-005 +1, CAP-DOC-019 +5, CAP-DOC-020 +2. Other cells unchanged. The CAPABILITIES header in `gate.py` lists the new CAP-AUDIT-005 test, and `gate.py` and `aqis_baseline_testutil.py` each have a new CHANGE LOG line. The header and registry tests pass in the fast suite. |
| A10 Contracts | N/A | No contract output or validator changed in this round. |
| A11 Environment parity | PASS | No absolute paths in the added code. `/etc/hostname` appears only as test input for the "outside the repository" rejection case. No lock, config or workflow changed. `.venv` is Python 3.13.14; the Colab probe requires 3.13. Two new tests need git history: `test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09` (`git show 254c1e3:…`) and the ancestor test (a `git clone --shared` of the repository). Full history is already a recorded condition (PLAN.md item 9), and CI checks out with `fetch-depth: 0`. No new owner-run checks. |
| A12 Reproducibility and traceability | PASS | The new checks and tests are deterministic. The pinned set is tied to a fixed commit (`WP09_START`). No new result rows. |
| A13 Errors and logging | PASS | `_ignores_for` now reads conftests up to the repository root. A non-literal ignore list in a conftest above the collected folder therefore also stops the gate with `ERROR: <conftest>:<line>` and exit 2. `audit_rounds` raises if a reviewed WP's `AUDIT.md` is missing. `repo_file` resolves without raising and reports through the caller's problem list. Nothing is swallowed. |
| A14 Documentation, licences, data | PASS | `docs/tools/AUDIT_GATE.md` states the corrected conftest rule. The memo says its round table covers WP-0.0 to WP-0.8. `EVIDENCE.md` records the deviations (F06), the round 2 runs and a disk incident during the builder's run. `FIXES.md` has the change budget, root causes and 15 break proofs. No personal data, and no new data that needs a licence. |
| A15 Exploratory breaks | FAIL | 7 made, 5 survived. A15-1 gives F08; A15-5 gives F09; A15-2 and A15-3 give F10; A15-4 gives F11. |

## Round 1 findings
| ID | Severity (round 1) | Status | Evidence |
| --- | --- | --- | --- |
| WP-0.9-F01 | CRITICAL | Fixed | **Pinned set.** `PHASE0_DEBT_IDS` pins the 30 rows that had a phase 0 Target in `DEBT.md` at `254c1e3`. I recomputed that myself: 30 phase 0 rows; 19 of them targeted WP-0.9; DEBT-027 is the only other row. **Break MC2-h** (DEBT-019 → `WP-1.0`, `OPEN`, no "moved", memo names it) is now caught by the must-catch test `test_FR_0_9_01_no_open_debt_row_targets_phase_0` (`1 failed, 62 passed`). MC2-f and MC2-g are now caught by it too. **New test.** `test_FR_0_9_01_debt_check_covers_every_pinned_row` tries reopened, quiet move and deleted on each of the 30 rows, whatever the row's current state. **Checker breaks.** Each of these fails the named tests: removing the missing-row report (MC2-m, 30 failed), going back to wording-based selection (MC2-n, 30 failed), and dropping DEBT-019 from the pin (MC2-o). What remains weak is the approval match itself: F08. |
| WP-0.9-F02 | MAJOR | Fixed | `audit_rounds` reads only `REVIEWED_WPS` (WP-0.0 to WP-0.8). Break R-F02, widening it to WP-0.9, fails `…_audit_round_counts_and_lessons_cite_records`, `…_audit_rounds_cover_only_the_reviewed_wps` and `…_memo_passes_every_check`. The fast suite and CI runs 392 and 393 are green with round 1's report in the tree. In my clone I also confirmed that this round 2 report and the STATUS change leave `test_aqis_phase0_memo.py` green. |
| WP-0.9-F03 | MAJOR | Fixed | Round 1's four survivors, re-run as breaks: X1 (verdict), X1 (commit), X2 (ancestor), X8 (estimate, hours, rate) and X9 (owner quotes). Each is now caught, by `test_FR_0_9_03_memo_verdict_and_commit_must_be_the_reports`, `test_FR_0_9_03_audited_commit_must_be_an_ancestor_of_head`, `test_FR_0_9_02_unit_log_check_reports_a_wrong_row[…]` (the matching case each time) and `test_FR_0_9_02_owner_quotes_must_be_in_the_approval` (3 cases). |
| WP-0.9-F04 | MAJOR | Fixed | Break R-F04 makes the walk stop at the collected folder again. Both cases of `test_FR_0_0_09_index_applies_conftests_above_the_collected_folder` then fail. Those cases compare the gate with what the pinned pytest collects from the repository root. Four `…_non_literal_collect_ignore_is_an_error` cases also fail, but only because the conftest path in the message changes. `AUDIT_GATE.md` states the corrected rule. My probe: `gate.test_functions` gives the same 1707-entry index with a relative and an absolute root (1.1 s for four calls). |
| WP-0.9-F05 | MAJOR | Fixed as reported | Break R-F05, exempting every `ID` and `Item` table again, fails `[sources-second-table-same-header]` and `[inventory-second-table-same-header]`. A related path remains open: F09. |
| WP-0.9-F06 | MINOR | Fixed (record only) | `EVIDENCE.md`, "Deviations from the plan": (a) the open-issues test compares with debt rows and blockers, not with owner-run tables; (b) the planned tests mapped to the built tests. |
| WP-0.9-F07 | MINOR | Fixed for exit-criteria links | `repo_file` is used in `link_problems`. Breaks MC1-l (folder), MC1-m (absolute path) and MC1-n (check removed) fail `[folder-link]`, `[outside-repository]` and `[escaping-repository]`. The same rule was extended to lesson and Pack v1 plan paths, without a test: F10. |

## Must-catch proof (A6)
Each break was made alone in `/tmp/wp09-audit2`, and the clone was confirmed clean after each one. Unless the row says otherwise, I ran `.venv/bin/python -m pytest -q -p no:cacheprovider -rf tests/aqis_lab/test_aqis_phase0_memo.py` (63 tests).

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1. Each exit criterion E1 to E6 links to evidence that exists | MC1-a: `git mv` E2's `docs/progress/WP-0.5/OC-0.5-02_runner.log` | `test_FR_0_9_01_exit_criteria_link_evidence_that_exists`, `…_memo_passes_every_check` | CAUGHT |
| 1 | MC1-b: renamed E3's test `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock` in `test_aqis_trace.py` | same two | CAUGHT |
| 1 | MC1-c: `git rm` E1's Oracle bundle `.tar` | same two | CAUGHT |
| 1 | MC1-d: E3's Evidence cell replaced by plain words | same two | CAUGHT |
| 1 | MC1-e: the E6 row deleted from the memo | same two | CAUGHT |
| 1 | MC1-l (new): E4's first path replaced by the folder `docs/baselines/tier2_vad/2026-10-03` | same two, plus the `[folder-link]` case | CAUGHT |
| 1 | MC1-m (new): E4's first path replaced by `/etc/hostname` | same two, plus `[outside-repository]` | CAUGHT |
| 1 | MC1-f to MC1-k: checker loosened, one at a time. It no longer checks: (f) path existence and `repo_file`; (g) collected test names; (h) commits; (i) a link in each row; (j) all six rows; (k) the criterion's wording | `test_FR_0_9_01_evidence_check_reports_each_broken_link`, cases (f) `renamed-path`, `folder-link`, `outside-repository`, `escaping-repository`; (g) `unknown-test`; (h) `unknown-commit`; (i) `no-link`; (j) `missing-row`; (k) `changed-criterion` | CAUGHT (6 of 6) |
| 1 | MC1-n (new): checker no longer applies `repo_file` | `[folder-link]`, `[outside-repository]`, `[escaping-repository]` | CAUGHT |
| 2. Every open phase 0 debt row is closed or moved to a named later WP, with the owner's approval | MC2-a: DEBT-001 Status `OPEN` | `…_no_open_debt_row_targets_phase_0`, `…_open_issues_list_every_open_debt_and_blocker`, `[left-open]`, `…_memo_passes_every_check` | CAUGHT |
| 2 | MC2-b: DEBT-019 Status `OPEN` | `…_no_open_debt_row_targets_phase_0` and 2 more | CAUGHT |
| 2 | MC2-c: DEBT-025's move cites `docs/approvals/WP-0.8.md` | `…_no_open_debt_row_targets_phase_0`, `[moved-without-approval]` | CAUGHT |
| 2 | MC2-d: DEBT-025 moved to WP-4.6 | `…_no_open_debt_row_targets_phase_0`, `[moved-to-unnamed-wp]` | CAUGHT |
| 2 | MC2-e: DEBT-001 `WP-1.0 (moved from WP-0.9)`, `OPEN, moved to WP-1.0`, no approval | `…_no_open_debt_row_targets_phase_0` and 3 more | CAUGHT |
| 2 | MC2-f: DEBT-001 `WP-1.0`, `OPEN`, no "moved", `DEBT.md` only | `…_no_open_debt_row_targets_phase_0` and 3 more | CAUGHT |
| 2 | MC2-g: as MC2-f, and the memo names DEBT-001 | `…_no_open_debt_row_targets_phase_0`, `[left-open]` | CAUGHT |
| 2 | MC2-h (round 1 survivor): DEBT-019 `WP-1.0`, `OPEN (docs/approvals/WP-0.9.md)`, no "moved"; the memo names it | `…_no_open_debt_row_targets_phase_0` | CAUGHT |
| 2 | MC2-l (new): the DEBT-019 row deleted | `…_no_open_debt_row_targets_phase_0`, `…_debt_check_covers_every_pinned_row[DEBT-019]` | CAUGHT |
| 2 | MC2-j: checker ignores open phase 0 targets | `…_debt_check_covers_every_pinned_row` (30 cases), `[left-open]` | CAUGHT |
| 2 | MC2-k: checker no longer reads the move approval | `…_debt_check_covers_every_pinned_row` (30 cases), `[moved-without-approval]` | CAUGHT |
| 2 | MC2-m (new): checker no longer reports a missing pinned row | `…_debt_check_covers_every_pinned_row` (30 cases) | CAUGHT |
| 2 | MC2-n (new): checker back to selecting rows by the word "moved" | `…_debt_check_covers_every_pinned_row` (30 cases) | CAUGHT |
| 2 | MC2-o (new): DEBT-019 dropped from `PHASE0_DEBT_IDS` | `…_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09` | CAUGHT |

As in round 1, MC2-i is not counted: a pinned row set to `CLOSED` with no approval cited and no evidence. The approved plan asks for an approval citation only on moved rows, and closures rest on the approval's Q2 table.

## Exploratory breaks (A15, at most 10)
Only in code changed since `f729dc0`. Round 1's breaks, re-run to check the fixes, are listed under "Round 1 findings" and not counted here.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| A15-1: probe, no code change. DEBT-016 rewritten to Target `WP-4.5`, Status ``OPEN (`docs/approvals/WP-0.9.md`, question 5)``. The memo already names DEBT-016 | `aqis_memo_testutil.debt_problems`: approval match `(debt in t or finding_id in t) and new.group(1) in t` | Yes. `pytest tests/aqis_lab -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9 or debt or DEBT or memo"`: `125 passed, 1900 deselected`. Today `WP-0.9.md` names DEBT-004, 009, 016, 024 and 028 for other reasons, and WP-4.5 for DEBT-025, so each of these five rows could be moved to WP-4.5 this way | MAJOR → F08 |
| A15-2: lesson path check back to `(Path(root) / p).exists()` | `lesson_problems` | Yes (63 passed) | MINOR → F10 |
| A15-3: Pack v1 plan path check back to `.exists()` | `prerequisite_problems` | Yes (63 passed) | MINOR → F10 |
| A15-4: the "targets phase 0 but is OPEN" report limited to pinned rows | `debt_problems` | Yes (63 passed). Today's code does report a new unpinned row: an added `DEBT-034 … WP-0.9 \| OPEN` gives `DEBT-034: targets WP-0.9 (phase 0) but is OPEN` | MINOR → F11 |
| A15-5: probe, no code change. A commented-out (`<!-- … -->`) copy of the Sources table placed above the visible one; S6's visible Value changed to forty `1`s | `aqis_baseline_testutil.body_text` and `sources_table` | Yes. `summary_problems` gives `0 []`. `sources_table` returns S6 = `75e39d95…` from the hidden copy, and `body_text` exempts the visible table. Control: the same visible change without the hidden copy gives 2 problems ("cites S6, whose Value is '1111…'" and the raw-file mismatch). The round 1 version of the file also gives `0 []` | MAJOR → F09 |
| A15-6: probe. `gate.test_functions` with relative root `.`, absolute root, and absolute root with a trailing `/` | `_ignores_for` loop end (`current == root`) | No issue: the same 1707 entries every time, no hang (1.1 s for all four calls) | — |
| A15-7: farthest conftest wins (`result[name] = …` instead of `setdefault`) | `tools/audit/gate.py` `_ignores_for` | No: `…_index_follows_pytest_collection_rules`, `…_index_counts_every_collected_probe_test` and `…[nearer-conftest-shadows-ignore]` failed | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.9-F08 | MAJOR | A15 (must-catch 2 area) | `debt_problems` approves a move if any cited approval file contains the row's debt ID (or its finding ID) and the new WP ID anywhere in its text. The two need not be in the same condition, or related at all. Since round 2, every pinned row that is not CLOSED reaches this match, so it is the only guard against a quiet move. `docs/approvals/WP-0.9.md` names five closed phase 0 rows for other reasons (Q2, Q3, Q5, Q7) and names WP-4.5 for DEBT-025 (Q8). Any of those five can therefore be reopened and moved to WP-4.5, citing that approval, and the must-catch test still passes. Today's `DEBT.md` is correct. The finding-ID match is also a plain substring match: `WP-0.1-F4` would match `WP-0.1-F40`. No approval has such a pair today. | A15-1 above; `tests/aqis_lab/aqis_memo_testutil.py` `debt_problems`, last condition | **Fix now.** Require the debt ID (or the finding ID, matched as a whole ID) and the new WP in the same condition line of the cited approval. Q8's line names both DEBT-025 and WP-4.5, so the real move still passes. Add A15-1 (DEBT-016 to WP-4.5 citing `WP-0.9.md`) as a `DEBT_BREAKS` case. |
| WP-0.9-F09 | MAJOR | A15 | `body_text` picks the exempt table after removing HTML comments, but `sources_table` and `inventory_table` read the section with comments left in, through `pipe_table`. If a commented-out pipe table headed `ID` comes before the visible Sources table, the checker reads the hidden one, and the visible one is exempt and never compared with the raw files. A reader then sees a Sources value that matches no raw file, and the check passes. Body numbers are still compared, with the hidden table's values. Likelihood is low, but this is a plausible editing accident: commenting out an old table and writing a new one below it. I probed Sources. Raw inventory uses the same pair of readers, and I did not probe it. | A15-5 above; `tests/aqis_lab/aqis_baseline_testutil.py` `body_text` versus `sources_table`, `inventory_table` and `pipe_table` | **Fix now** (the remainder of F05, in a file the approval already lets you edit). Make the table readers and `body_text` read the same text, for example by removing comments before `sources_table` and `inventory_table` parse. Or report any pipe table inside an HTML comment in those two sections. Add the probe as a case for Sources and for Raw inventory. If you prefer, accepting this as debt for WP-1.0 is a reasonable alternative: body numbers stay verified, and the gap needs a hidden table. |
| WP-0.9-F10 | MINOR | A15 | `repo_file` (no folders, no paths outside the repository) also applies to lesson citations and Pack v1 plan paths, but no test fails when either reverts to "the path exists". This is the same weakness round 1 rated MINOR for exit-criteria links (F07). The memo's current citations are all files. | A15-2, A15-3 | Accept as debt (WP-1.0). It is cheaper to add the two cases (a lesson citing a folder; a plan bullet citing `/etc/hostname`) while fixing F08. |
| WP-0.9-F11 | MINOR | A15 | No test fails when the "targets phase 0 but is OPEN" report is limited to the pinned rows. Every break case uses a pinned row. Today's code does report a new unpinned row (checked), so only the test is missing. | A15-4 | Accept as debt (WP-1.0), or add one `DEBT_BREAKS` case (a new row with Target `WP-0.9`, Status `OPEN`) while fixing F08. |

## Convergence (round 3 onwards)
Not required until round 3. For reference:

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 2 | F01 (must-catch 2) |
| 2 | 0 | 2 | 2 | F08 is in must-catch 2's area ("with the owner's approval"). The A6 breaks all pass; F08 is an A15 survivor, so it is MAJOR, not CRITICAL |

## For the owner
- **audit-allow lines:** None.
- **Approvals used:**
  - `docs/approvals/WP-0.9.md` on `main` (`604e9a4`): Q1 to Q10, the four `ALLOW-EDIT` lines (round 2 used those for `aqis_baseline_testutil.py` and `test_aqis_tier2_baseline.py`), the unit-log note, and "Round 2 Fixes: … F01 to F07".
- **One thing to confirm (no finding raised).** `FIXES.md` and `EVIDENCE.md` say your chat message asked to pin "the 19 Phase 0 DEBT IDs (DEBT-001 through 007, 009, 010, 012-021)". The builder pinned 30 instead.
  - What I checked: your 19 IDs are all among the 30. The 30 are exactly the rows with a phase 0 Target in `DEBT.md` at `254c1e3`. The 19 rows that targeted WP-0.9 at that commit are a different set: DEBT-001 to 007, 009, 016, 019, 022 to 026 and 028 to 031.
  - Why I raise no finding: pinning 30 checks more rows and never fewer. It matches must-catch 2's wording ("every open debt row … targeting phase 0"), and the builder disclosed it.
  - What I did not see: the chat itself. The rules make a conflict between your instruction and the spec a stop-and-ask, so please confirm the 30-row pin is what you want.
- **Debt accepted so far** (unchanged since round 1):
  - DEBT-025, moved to WP-4.5 (Q8);
  - DEBT-032 and DEBT-033, phase audit MINORs, target WP-1.0;
  - DEBT-027, phase 2;
  - DEBT-009, DEBT-016 and DEBT-005 K11.5b, closed as recorded permanent limits (Q5).
- **Owner-run checks still pending:** None for WP-0.9; AT-0.9-01 and OC-0.9-01 are done. DEBT-032 carries the full `dev_bootstrap.sh --gpu` output on a Colab GPU runtime to WP-1.0.
- **What blocks a pass:**
  - F08 and F09 (MAJOR): each needs a fix or your acceptance as debt (a CONDITIONS line plus a `DEBT.md` row);
  - F10 and F11 (MINOR) do not block. Each is two to four lines in the same test helpers as F08, so it is cheaper to fix them in the same round.
  - A round 3 re-audit would cover only these four findings, the diff since `2155e3d`, the suites, CI and the must-catch proof.
- **Environment notes from this audit:**
  - Free disk on this VM was 9.5 to 13 GB during the audit. The three MUSAN tests were not run, so the 11 GB archive was never downloaded and nothing had to be cleaned up.
  - The CI log hosts above are blocked by the proxy. If you want auditors to quote CI test counts, allow `results-receiver.actions.githubusercontent.com` and `productionresultssa5.blob.core.windows.net`.
  - `/tmp/wp09-breaks` (the builder's break clone), `/tmp/phase0-audit` and `/tmp/phase0-audit2` are not mine, and I left them. I removed my own clone, `/tmp/wp09-audit2`.
