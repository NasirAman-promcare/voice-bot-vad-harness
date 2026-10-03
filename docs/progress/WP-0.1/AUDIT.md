# AUDIT — WP-0.1, round 3

Auditor: wp-auditor · Date: 2026-10-03 · Commit audited: `e052cc86ed86e321c31baa1db1ae6fbe9b678fc3` · Previous audited commit: `49f2274c2e7b07bac862f08df18f5739c3ce23a2` · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 5 (fixed 3: F1, F2, F3; accepted as debt 1: F4; open 1: F8) · MINOR: 4 (fixed 2: F6, F7; accepted as debt 1: F5; open 1: F9, does not block)

**Nothing changed since round 2.** The only commit after `49f2274` is `e052cc8`, which holds the round 2 audit report and its STATUS row. No fix was made, and `main` has no new approval: it still ends at `264532a`. So the two open round 2 findings are still open, unchanged:
- **F8 (MAJOR)** still blocks. I re-made the round 2 break X4, and it still passes all 44 tests. I also confirmed by a break the inventory half of F8, which round 2 had found only by reading the code.
- **F9 (MINOR)** is still open and does not block. H1, H3, H4 and H5 each still pass all 44 tests.

Everything else holds:
- All 13 must-catch breaks are caught, with the same failure counts as in round 2.
- The fast and slow suites pass.
- The gate reports 0 findings.
- CI is green on `e052cc8`.
- AT-0.1-01 holds on five newly drawn numbers.

**Convergence (round 3).** Neither open finding sits inside the must-catch list, so under the protocol I recommend PASS with debt. That needs your decision. The verdict stays FAIL until F8 is either fixed or named as accepted debt in the approval on `main`.

## Scope of this audit
This is a re-audit under protocol version 2, round 3. **The WP was at AUDIT-FAIL, not READY-FOR-AUDIT, when this audit was requested.** There is no round 3 build, no "Round 3" section in `FIXES.md`, and no new line in `docs/approvals/WP-0.1.md`. This round therefore confirms the current state. It does not review a fix.

What this round covered:
1. **Open findings from round 2:** F8 and F9, re-checked with breaks. F1 to F7 were closed or accepted in round 2. Their code and records are unchanged (`git diff 49f2274 e052cc8` is empty outside the two audit records), so I did not re-test them beyond the full suites and the must-catch proof.
2. **A1 to A15 on the diff `49f2274..e052cc8`.** That diff is two files, both auditor records: `docs/progress/WP-0.1/AUDIT.md` (round 2 report) and the WP-0.1 row of `docs/progress/STATUS.md` (READY-FOR-AUDIT to AUDIT-FAIL). `git diff 49f2274 e052cc8 -- tests aqis_lab tools config requirements notebooks docs/baselines docs/capabilities docs/progress/DEBT.md docs/progress/BLOCKERS.md docs/progress/WP-0.1/EVIDENCE.md docs/progress/WP-0.1/FIXES.md docs/progress/WP-0.1/PLAN.md .github` gives 0 lines.
3. **The full set:** the fast and slow suites, the gate, CI, AT-0.1-01 and the complete must-catch proof.

**How breaks were made.**
- Every break was made in a fresh copy of `git archive e052cc8`, extracted under `/tmp/claude-0/…/scratchpad/r3/base/` and copied to `runs/<break>/`.
- A script applied each edit. Text replacements had to match exactly once, and on the stated line. Inventory rows were rewritten by item and file name.
- `diff -rq` against the unbroken base confirmed that only the intended files changed.
- The script then ran the repository's `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider -rf --tb=line` from the copy's root.
- The tests read the copy. mc1h's message reports the copy's edited value: "the source gives '433.7', SUMMARY.md shows '433.6'".
- The unbroken copy gives `44 passed in 16.41s`.
- The working repository was clean before and after (`git status --porcelain`: 0 lines) until this report was written.

Every content break also fails some self-test cases (`…_check_reports_a_changed_raw_value`, `…_check_reports_each_inconsistency`, `…_check_reports_cells_in_the_wrong_row_or_column`, `…_check_reports_uncited_numbers_in_every_section`), because each case first asserts that the unedited copy has no problems. The counts below include them.

## Round 2 findings: status
| Finding | Status | Evidence |
| --- | --- | --- |
| **WP-0.1-F8 (MAJOR)** | **Open, unchanged** | `body_text` is byte-identical to round 2 (`aqis_baseline_testutil.py:717-724`). Two breaks confirm it. **X4** (round 2's break, re-made): a second table appended after the Sources table, `\| Note \| Detail \|` / `\| Scored clips \| 1500 \|`, gives `44 passed in 17.05s`. **X4-inv**, the inventory half that round 2 found only by reading the code: a second table placed before `## Sources`, `\| Note \| Detail \| Count \| Size \|` / `\| Scored clips \| see the run log \| 1500 \| 9000 \|`, gives `44 passed in 17.01s`. The blanked cells are chosen by **position**, from the first table's header (Bytes and SHA-256 are the 3rd and 4th cells), and that applies to every `\|` line of the section. My first try at X4-inv put `1500` in the 2nd column. That number was caught (`6 failed`, "body line 113: a number without a citation: '\| Scored clips \| 1500 \|\|'"), but the `9000` in the 4th column was blanked, as the code predicts. The current SUMMARY.md is still clean: Raw inventory holds one table (lines 107 to 118: header, separator, 10 rows), and Sources holds one table (lines 124 to 484: header, separator, 359 rows). |
| **WP-0.1-F9 (MINOR)** | **Open, unchanged** | Round 2's helper loosenings, re-made: H1 (`_report` no longer checks `row`), H3 (`if keys != points:` changed to `if False:`), H4 (`if sid not in used:` changed to `if False:`), H5 (`_shape` returns `True` after the shape check). Each gives `44 passed` (17.82s, 17.50s, 16.87s and 17.57s). |
| WP-0.1-F1, F2, F3, F6, F7 | Closed in round 2, unchanged | No change to the code or records they concern. All 13 must-catch breaks are caught with the round 2 counts (below). |
| WP-0.1-F4, F5 | Accepted as debt, unchanged | DEBT-028 and DEBT-029, both OPEN with target WP-0.9. The approval line "Debt accepted: WP-0.1-F4 (target WP-0.9) and WP-0.1-F5 (target WP-0.9)" is on `main`. On this branch, `git diff --name-only origin/main...HEAD` lists no file under `raw/`. |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none" (`WP-0.1-tier2-baseline.md:3`). The branch is `claude/practical-knuth-wsgvud`, not `main`. `git show origin/main:docs/approvals/WP-0.1.md` starts with `STATUS: APPROVED`. `git diff origin/main HEAD -- docs/approvals/` gives 0 lines. PR #9 is open, with head `e052cc8` and base `main` (REST `pulls/9`). |
| A2 Requirement coverage | PASS | Unchanged since round 2. 18 test functions, 44 collected: FR-0.1-01 has 6, FR-0.1-02 has 10, FR-0.1-03 has 2. `pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider` gives `44 passed in 23.07s`. EVIDENCE.md is unchanged and lists each one. |
| A3 Acceptance commands | PASS | AT-0.1-01: I drew five rows with `random.SystemRandom().sample` from the 327 numeric Sources rows (359 in all) and checked each against the raw files with `jq`, without the test helper. **S198** `149886`: Σ`payload.metrics.tp` over `scoring_clip` records of `webrtc_vad_mode1` gives `149886`. **S106** `13554`: the same sum for `ten_vad` in `quiet/whispered speech` gives `13554`. **S168** `9065`: Σ`payload.metrics.fn` over `webrtc_vad_mode0` `scoring_clip` records gives `9065`. **S343** `17`: null `mean_offset_hangover_latency_ms` over `webrtc_vad_mode2` `tier2_pipeline_latency` records gives `17` (all 224 records have the key). **S188** `-16.3`: report cell 3, output 1 (`text/markdown`), row `webrtc_vad_mode0`, column "Offset Hangover", gives `-16.3 ms`. The SUMMARY.md cells citing them show `149886 [S198]` (line 76), `13554 [S106]` (73), `9065 [S168]` (75), `17 [S343]` (90) and `-16.3 [S188] [S191]` (64). All five match. |
| A4 Test suites and CI | PASS | Fast: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` gives `1856 passed, 55 deselected in 233.57s`. Slow: `-m "slow and not gpu and not colab and not oracle and not network"` gives `5 passed, 1906 deselected in 68.56s`. CI on `e052cc8`, workflow `aqis-lab-ci`: run 37126312566 (push) and run 37126314231 (pull_request) both concluded `success`, and jobs `lab` and `harness-regression` are `success` in both (`gh api …/actions/runs/<id>/jobs`). The only non-success step is "Work package ID from pull request title" in the push run, which is `skipped` because it runs only for pull requests. |
| A5 Test integrity | PASS | No test file changed since `49f2274`. `git diff --name-status origin/main...HEAD -- tests/` shows only the two added WP files (`A`), so no merged test was touched. |
| A6 Must-catch proof | PASS | 13 of 13 breaks caught; see the table below. |
| A7 Compromise scan | PASS | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` gives `Exempted lines (# audit-allow): 0`, `Findings: 0`, `0 findings: OK`, exit 0. No function was added or changed since round 2, so there is nothing new to read. |
| A8 Scope diff | PASS | `49f2274..e052cc8` changes only `docs/progress/WP-0.1/AUDIT.md` and the WP-0.1 row of `docs/progress/STATUS.md`. Both are auditor records. No protected path, raw file or SUMMARY.md line changed. |
| A9 Capabilities | PASS | Unchanged. The registry has 149 `CAP-` rows. The 18 test names in CAP-BASE-002 equal the 18 collected test functions (`diff` of the two sorted lists is empty). |
| A10 Contracts | N/A | No lab contract covers a baseline summary, and the spec names none (unchanged since round 1). |
| A11 Environment parity | PASS | No change. The bootstrap gives `OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34…`. `docs/environment/colab_probe.txt` gives Python 3.13.15. The major.minor versions match (3.13). No owner-run checks. |
| A12 Reproducibility and traceability | PASS | 44 passed both in the repository and in the clean `/tmp` copy. The self-tests edit `tmp_path` copies only. No Sources row and no cited number changed. |
| A13 Errors and logging | N/A for the diff | No code changed. The round 2 result stands: unreadable inputs become a named problem, and a missing approval quote raises. |
| A14 Documentation, licences, data | PASS | EVIDENCE.md and FIXES.md are unchanged since round 2, and their round 2 claims were verified then. There is no round 3 section, because there was no round 3 build. No data was added. |
| A15 Exploratory breaks | N/A (0 of 10 used) | No code was added or changed since `49f2274`, so there is no target. The breaks in "Round 2 findings: status" re-check open findings (re-audit step 1). They are not new A15 breaks, and they stay within what F8 and F9 already name. |

## Must-catch proof (A6)
Each break was made in a fresh copy of `e052cc8`, as described in Scope. The unbroken copy gives `44 passed`. These are the same 13 breaks as in round 2, so the results can be compared one for one.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1. Every number matches its cited raw file | mc1a: `03_report.ipynb` line 136, `firered_vad` Onset Latency `433.6 ms` changed to `433.7 ms` | `test_FR_0_1_02_every_number_matches_its_cited_source`, `…_report_log_and_records_agree`, `test_FR_0_1_03_raw_files_unchanged_since_inventory` | Caught (`8 failed, 36 passed`) |
| 1 | mc1b: `raw_evaluations.jsonl` line 854, `firered_vad` `mean_wallclock_pipeline_latency_ms` `471.66` changed to `1471.66` | `…_every_number_matches_its_cited_source`, the FR-0.1-03 hash test | Caught (`7 failed`) |
| 1 | mc1c: the same field changed to `471.80`. This moves the median only; the mean is unchanged at 1 dp | `…_every_number_matches_its_cited_source`, S161 only ("gives 471.8, shown under '1 dp' as '471.8'; SUMMARY.md shows '471.7'"), and the hash test | Caught (`7 failed`) |
| 1 | mc1d: `NETWORK.md` line 8, `port 10000/udp` changed to `port 10001/udp` (S13, text) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1e: `run_config.yaml` line 18, `decision_threshold: 0.5` changed to `0.6` (S24, YAML) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1f: `raw_evaluations.jsonl` line 3, the uncited field `stream_length_discrepancy_ms` `13.5` changed to `13.6` | `test_FR_0_1_03_raw_files_unchanged_since_inventory` ("SHA-256 6c037c1e…, the Raw inventory says ff3b47c2…") | Caught (`1 failed`) |
| 1 | mc1g: mc1b **and** the R5 inventory row updated to the new bytes and SHA-256, so the hash test cannot decide | `…_every_number_matches_its_cited_source` (S160 "gives 584.78…, shown under '1 dp' as '584.8'; SUMMARY.md shows '580.0'", and S161). The hash test passes | Caught (`6 failed`) |
| 1 | mc1h: mc1a **and** the R6 inventory row updated | `…_every_number_matches_its_cited_source` ("S154 … the source gives '433.7', SUMMARY.md shows '433.6'"), `…_report_log_and_records_agree` | Caught (`7 failed`) |
| 2. A missing raw file is reported as missing | mc2a: `run.log` (R7) deleted | `test_FR_0_1_01_raw_folder_has_every_required_item` ("R7 missing: raw/run.log does not exist") and 6 other named tests | Caught (`32 failed`) |
| 2 | mc2b: `03_report.ipynb` (R6) deleted | `…_raw_folder_has_every_required_item` ("R6 missing: raw/03_report.ipynb does not exist") and 6 others | Caught (`25 failed`) |
| 2 | mc2c: `NETWORK.md` (R4) emptied | `…_raw_folder_has_every_required_item`, `…_raw_files_agree_on_the_run` ("R4 raw/NETWORK.md: does not answer …"), `…_every_number_matches_its_cited_source`, the hash test | Caught (`21 failed`) |
| 2 | mc2d: `jingle_stanzas_debug_listener.log` (R8) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item` ("R8 missing: no listener log listed in the Raw inventory"), `…_raw_files_agree_on_the_run` | Caught (`14 failed`) |
| 2 | mc2e: `raw_evaluations.jsonl` (R5) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item` ("R5 missing: no file listed for it in the Raw inventory") and 6 others | Caught (`38 failed`) |

## Exploratory breaks (A15, at most 10)
None this round, because no code was added or changed since the last audited commit. The re-checks of F8 and F9 are in "Round 2 findings: status".

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| — | — | — | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.1-F1 | MAJOR | A15 | Fixed in round 2: each table cell cites exactly the Sources of its own row and column. | Round 2; unchanged | Closed |
| WP-0.1-F2 | MAJOR | A15 | Fixed in round 2 for what it named. The leftover gap is F8. | Round 2; unchanged | Closed (see F8) |
| WP-0.1-F3 | MAJOR | A15 | Fixed in round 2: each `raw_problems` consistency rule has a negative self-test. | Round 2; unchanged | Closed |
| WP-0.1-F4 | MAJOR | A15 | Accepted as debt. | DEBT-028; approval line "Debt accepted" | Accepted (WP-0.9) |
| WP-0.1-F5 | MINOR | A2, A14 | Accepted as debt. | DEBT-029; same line | Accepted (WP-0.9) |
| WP-0.1-F6 | MINOR | A14 | Fixed in round 2. | Round 2; unchanged | Closed |
| WP-0.1-F7 | MINOR | A6 | Fixed in round 2. | mc2d still fails `…_raw_folder_has_every_required_item` with "R8 missing: …" | Closed |
| WP-0.1-F8 | MAJOR | A15 | **Open, unchanged since round 2.** The citation check exempts more than the two tables it means to. **Sources section:** `body_text` skips every line starting with `\|` (`aqis_baseline_testutil.py:717-718`), not only the rows of the table headed `ID`. **Raw inventory section:** it blanks the cells at the positions of the first table's Bytes and SHA-256 columns in every `\|` line of the section (`:719-724`), not only in the table headed `Item`. So an uncited number in a second table in either section passes every test, and FR-0.1-02's check reports success wrongly. The comment at `:68-70`, FIXES.md and the CAP-BASE-002 row all describe a narrower exemption: only the cells of the Sources table, and the Bytes and SHA-256 cells of the inventory. **The current SUMMARY.md is clean:** each of the two sections holds only its own table. | X4: `44 passed`. X4-inv: `44 passed`. Table counts in "Round 2 findings: status" | **Accept as debt, target WP-0.9.** This follows the protocol's round 3 convergence rule: F8 is not inside the must-catch list. All 13 must-catch breaks are caught, and every number in the current SUMMARY.md is cited and resolved. Reaching the gap needs a later edit to a dated baseline, and that edit would itself go through a WP and an audit. If you would rather close it now, the fix is still a few lines, as round 2 described. Exempt only the rows of the table headed `ID`, and the Bytes and SHA-256 cells of the table headed `Item`, chosen by header, not by position. Read any other `\|` line in those sections as body text, and add two `UNCITED_INSERTS` cases matching X4 and X4-inv. |
| WP-0.1-F9 | MINOR | A15 | **Open, unchanged since round 2.** Four parts of `binding_problems` have no self-test that fails when that part alone is removed: the report-row binding (`:780`), one row per operating point (`:920`), extra citations (`:890`), and the binding of `expr` operands (`:812-815`). The Conditions table also has no check that every category has a row (round 2, from reading the code). The current content is correct. | H1, H3, H4, H5: `44 passed` each | **Accept as debt, target WP-0.9.** MINOR never blocks, and reaching any of these gaps needs a later edit to the helper, which would be an audited change to a merged test. If you approve a round 3 fix for F8, round 2's four isolating cases are cheap to add in the same round. |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 4 open (F1 to F4) | 3 open (F5 to F7) | None. Every must-catch break was caught. |
| 2 | 0 | 1 open (F8, new); F1, F2, F3 fixed; F4 accepted as debt | 1 open (F9, new); F6, F7 fixed; F5 accepted as debt | None. 13 of 13 caught. |
| 3 | 0 | 1 open (F8, unchanged); no new finding | 1 open (F9, unchanged); no new finding | None. 13 of 13 caught, with the same counts as round 2. |

**F8 sits beside must-catch behaviour 1, not inside it.**
- The spec defines that behaviour by its test: "the auditor changes one raw value in a copy and the check reports the mismatch". All 8 breaks of that kind are caught, including the two that also update the inventory hash (mc1g and mc1h).
- F8 is about a number that has no citation at all, which is FR-0.1-02's "every number cites its source". It can only arise if a later edit adds a second table to the Sources or Raw inventory section.

Counts did not change from round 2 to round 3 because no fix was made, not because a fix failed. No open finding is in the must-catch list, so under the protocol **I recommend PASS with debt**: accept F8 and F9 as debt with target WP-0.9.

## For the owner
- **audit-allow lines:** none (the gate reports `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.1.md` on `main` (`264532a`). It holds `STATUS: APPROVED`, the conditions on questions 1 and 6 and on R6, "BLK-016 Rulings Confirmed", "Round 2 Fixes" (F1, F2, F3, F7, F6) and "Debt accepted" (F4, F5). It names neither F8 nor F9.
- **Debt accepted so far:**
  - DEBT-027: the owner's statement on wall-clock latency; target: the Phase 2 VAD timing work.
  - DEBT-028 (F4): target WP-0.9.
  - DEBT-029 (F5): target WP-0.9.
  - All three are OPEN.
- **Owner-run checks still pending:** none. The Tier 2 run was your input, and it is committed.
- **Why this round found nothing new.** The audit was requested while the WP was at AUDIT-FAIL, with no fix and no new approval. Another audit without a decision from you will give the same result.
- **To reach PASS, choose one:**
  1. **Accept F8 and F9 as debt (my recommendation under the round 3 rule).** Add a CONDITIONS line to `docs/approvals/WP-0.1.md` on `main`, for example: "Debt accepted: WP-0.1-F8 (target WP-0.9) and WP-0.1-F9 (target WP-0.9)". The builder then appends two rows to `docs/progress/DEBT.md` (next IDs: DEBT-030 and DEBT-031). A short re-audit then confirms the line and the rows, and can pass.
  2. **Fix F8 now, and F9 too if you wish.** Add a "Round 3 Fixes" line naming WP-0.1-F8 (and WP-0.1-F9). The builder fixes it, and a re-audit checks the fix with X4, X4-inv and H1, H3, H4, H5.
