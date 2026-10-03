# AUDIT — WP-0.1, round 4

Auditor: wp-auditor · Date: 2026-10-03 · Commit audited: `58865d43a4e5572ad195c4810194f85d940a6ae6` · Previous audited commit: `e052cc86ed86e321c31baa1db1ae6fbe9b678fc3` · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 · MAJOR: 5 (fixed 3: F1, F2, F3; accepted as debt 2: F4, F8; open 0) · MINOR: 4 (fixed 2: F6, F7; accepted as debt 2: F5, F9; open 0)

The two findings left open in round 3 are now accepted as debt, as the protocol requires:
- **The owner's line is on `main`.** Commit `3c3f233` on `origin/main`, by the owner, changes the CONDITIONS line of `docs/approvals/WP-0.1.md` to: "Debt accepted: WP-0.1-F4 (target WP-0.9), WP-0.1-F5 (target WP-0.9), WP-0.1-F8 (target WP-0.9), and WP-0.1-F9 (target WP-0.9) accepted in docs/progress/DEBT.md."
- **The DEBT rows exist.** DEBT-030 (F8) and DEBT-031 (F9) are in `docs/progress/DEBT.md`. Both are OPEN, with target WP-0.9.

No code, test, SUMMARY.md, raw file or registry line changed since round 3. In my own re-runs:
- All 13 must-catch breaks are caught, with the same failure counts as in rounds 2 and 3.
- The fast and slow suites pass.
- The gate reports 0 findings.
- CI is green on `58865d4`.
- AT-0.1-01 holds on five newly drawn numbers.

There is no CRITICAL finding and no open MAJOR finding, so the verdict is PASS.

## Scope of this audit
Re-audit under protocol version 2, round 4. It covers:
1. **Open findings from round 3:** F8 and F9. Both are now accepted as debt. I checked the approval line on `main` and the DEBT rows. The code they concern is byte-identical to round 3, so round 3's breaks X4, X4-inv, H1, H3, H4 and H5 still describe it. I did not re-run them.
2. **A1 to A15 on the diff `e052cc8..58865d4`.** Four commits:
   - `8ca22f7`: the round 3 audit report.
   - `3c3f233`: the owner's approval change, on `main`.
   - `88872ff`: a merge of `main`, which brings in only that approval change.
   - `58865d4`: the builder's records: DEBT-030 and DEBT-031, a "Round 3" section in EVIDENCE.md, and the STATUS row set to READY-FOR-AUDIT.

   `git diff e052cc8 58865d4 -- tests aqis_lab tools config requirements notebooks docs/baselines docs/capabilities docs/progress/BLOCKERS.md docs/progress/WP-0.1/FIXES.md docs/progress/WP-0.1/PLAN.md .github .claude docs/process docs/specs` gives 0 lines. `git diff 8ca22f7 58865d4 -- docs/progress/WP-0.1/AUDIT.md` gives 0 lines, so the builder did not touch the round 3 report.
3. **The full set:** the fast and slow suites, the gate, CI, AT-0.1-01 and the complete must-catch proof.

**How breaks were made.**
- Every break was made in a fresh copy of `git archive 58865d4`, extracted under `/tmp/claude-0/…/scratchpad/r4/base/` and copied to `runs/<break>/`.
- A script applied each edit. Text replacements had to match exactly once on the stated line. `433.6 ms` appears twice in `03_report.ipynb`, so only line 136 was edited. Inventory rows were rewritten by item and file name.
- `diff -rq` against the unbroken base confirmed that only the intended files changed.
- The script then ran `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider -rf --tb=line` from the copy's root.
- The tests resolve the repository root from their own file (`aqis_testutil.ROOT`), so they read the copy. mc1a's message reports the copy's edited value: "the source gives '433.7', SUMMARY.md shows '433.6'".
- The unbroken copy gives `44 passed in 17.88s`.
- `git status --porcelain` gave 0 lines in the working repository before and after the breaks.

Every content break also fails the self-test cases, because each case first asserts that the unedited copy has no problems. The counts below include them.

## Round 3 findings: status
| Finding | Status | Evidence |
| --- | --- | --- |
| **WP-0.1-F8 (MAJOR)** | **Accepted as debt (WP-0.9)** | The approval line on `main` (`3c3f233`) names "WP-0.1-F8 (target WP-0.9)". The DEBT-030 row describes the gap as round 3 found it: `body_text` (`aqis_baseline_testutil.py:706`) skips every table line in Sources and blanks cells by position in Raw inventory, and X4 and X4-inv give `44 passed`. It gives the fix and the risk, with target WP-0.9 and status OPEN. The code is unchanged (empty diff on `tests/`). |
| **WP-0.1-F9 (MINOR)** | **Accepted as debt (WP-0.9)** | The same approval line names "WP-0.1-F9 (target WP-0.9)". The DEBT-031 row names the four untested parts and the missing category-completeness check: `_report` (`:776`), the one-row-per-operating-point check (`:920`), the extra-citation check in `_cell_problems` (`:890`), and `expr` operand binding in `_shape` (`:802`). These match round 3's H1, H3, H4 and H5. Target WP-0.9, status OPEN. |
| WP-0.1-F1, F2, F3, F6, F7 | Closed in round 2, unchanged | No change to the code or records they concern. All 13 must-catch breaks are caught (below). |
| WP-0.1-F4, F5 | Accepted as debt, unchanged | DEBT-028 and DEBT-029, both OPEN with target WP-0.9. They are still named in the approval line. `git diff --name-only origin/main...HEAD -- docs/baselines/tier2_vad/2026-10-03/raw` lists nothing. |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none" (`WP-0.1-tier2-baseline.md:3`). The branch is `claude/practical-knuth-wsgvud`, not `main`. `git show origin/main:docs/approvals/WP-0.1.md` starts with `STATUS: APPROVED`, and `git diff origin/main HEAD -- docs/approvals/` gives 0 lines. PR #9 is open, with head `58865d4` and base `main`, not merged (REST `pulls/9`). |
| A2 Requirement coverage | PASS | Unchanged since round 2. 18 test functions are collected (44 cases): FR-0.1-01 has 6, FR-0.1-02 has 10 and FR-0.1-03 has 2. `pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider` gives `44 passed in 18.34s`. EVIDENCE.md still lists each one. |
| A3 Acceptance commands | PASS | AT-0.1-01: I drew five rows with `random.SystemRandom().sample` from the 350 Sources rows whose Value holds a digit (359 rows in all), and checked each against the raw files with `jq`, `grep` and `sed`, without the test helper. **S233** `14688`: Σ`payload.metrics.tn` over `scoring_clip` records of `webrtc_vad_mode2` gives `[14688,224]`. **S38** `5`: `run_config.yaml:17` is `warmup_clip_count: 5`. **S277** `0.869`: `run.log:3992` is "Tier 2 Completed for 'webrtc_vad_mode3': … F1: 0.869". **S338** `103799`: Σ`payload.diagnostics.packet_count` over `webrtc_vad_mode2` `scoring_clip` records gives `[103799,224]`. **S300** `433`: Σ`payload.diagnostics.missing_packets` over `ten_vad` `scoring_clip` records gives `[433,224]`, and none of the 224 records lacks the key. The cells citing them are all in the right column and row: `14688 [S233]` (line 77, Σtn), `5 [S38]` (39, warm-up clips), `0.869 … [S277]` (67, F1 of `webrtc_vad_mode3`), `103799 [S338]` (90, Packets received) and `433 [S300]` (86, Missing packets of `ten_vad`). All five match. |
| A4 Test suites and CI | PASS | **Fast:** `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` gives `1856 passed, 55 deselected in 238.40s`. **Slow:** `-m "slow and not gpu and not colab and not oracle and not network"` gives `5 passed, 1906 deselected in 71.51s`. **CI on `58865d4`:** workflow `aqis-lab-ci`, run 37128134797 (push) and run 37128139885 (pull_request). Both concluded `success`, with jobs `lab` and `harness-regression` `success` in each (`gh api …/actions/runs/<id>/jobs`). The only non-success step is "Work package ID from pull request title" in the push run. It is `skipped` because it runs only for pull requests. |
| A5 Test integrity | PASS | No test file changed since `e052cc8`. `git diff --name-status origin/main...HEAD -- tests/` shows only the two added WP files (`A`), so no merged test was touched. |
| A6 Must-catch proof | PASS | 13 of 13 breaks caught. See the table below. |
| A7 Compromise scan | PASS | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` gives `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`, `Findings: 0`, `0 findings: OK`, exit 0. No function was added or changed, so there is nothing new to read. |
| A8 Scope diff | PASS | `e052cc8..58865d4` changes `docs/approvals/WP-0.1.md` (the owner's change, identical to `main`), `docs/progress/DEBT.md` (two rows added, none changed or removed), the WP-0.1 row of `docs/progress/STATUS.md`, `docs/progress/WP-0.1/EVIDENCE.md` (one section appended) and `docs/progress/WP-0.1/AUDIT.md` (the round 3 report). No protected path, raw file, test or SUMMARY.md line changed. |
| A9 Capabilities | PASS | Unchanged. The registry has 149 `CAP-` rows. The 18 test names in CAP-BASE-002 equal the 18 collected test functions (`diff` of the two sorted lists is empty). |
| A10 Contracts | N/A | No lab contract covers a baseline summary, and the spec names none. Unchanged since round 1. |
| A11 Environment parity | PASS | No change. The bootstrap gives `OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34…`. `docs/environment/colab_probe.txt:3` gives Python 3.13.15. The major.minor versions match (3.13). No owner-run checks. |
| A12 Reproducibility and traceability | PASS | 44 passed both in the repository and in the clean `/tmp` copy. The self-tests edit `tmp_path` copies only. No Sources row and no cited number changed. |
| A13 Errors and logging | N/A for the diff | No code changed. The round 2 result stands: unreadable inputs become a named problem, and a missing approval quote raises. |
| A14 Documentation, licences, data | PASS | EVIDENCE.md has a new "Round 3" section. It says no code, test or SUMMARY.md changed, which is true (empty diff). It quotes `1856 passed, 55 deselected` and `Findings: 0`, which match my re-runs. DEBT-030 and DEBT-031 state the gap, the risk, the fix, the approval and the target. FIXES.md has no round 3 section, which is correct, because nothing was fixed. No data was added. |
| A15 Exploratory breaks | N/A (0 of 10 used) | No code was added or changed since `e052cc8`, so there is no target. |

## Must-catch proof (A6)
Each break was made in a fresh copy of `58865d4`, as described in Scope. The unbroken copy gives `44 passed`. These are the same 13 breaks as in rounds 2 and 3, and every count equals round 3's.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1. Every number matches its cited raw file | mc1a: `03_report.ipynb` line 136, `firered_vad` Onset Latency `433.6 ms` changed to `433.7 ms` | `test_FR_0_1_02_every_number_matches_its_cited_source` ("S154 … the source gives '433.7', SUMMARY.md shows '433.6'"), `…_report_log_and_records_agree`, `test_FR_0_1_03_raw_files_unchanged_since_inventory` | Caught (`8 failed, 36 passed`) |
| 1 | mc1b: `raw_evaluations.jsonl` line 854, `firered_vad` `mean_wallclock_pipeline_latency_ms` `471.66` changed to `1471.66` | `…_every_number_matches_its_cited_source` (S160), the FR-0.1-03 hash test | Caught (`7 failed`) |
| 1 | mc1c: the same field changed to `471.80`. This moves the median only | `…_every_number_matches_its_cited_source` ("S161 … gives 471.8, shown under '1 dp' as '471.8'; SUMMARY.md shows '471.7'"), the hash test | Caught (`7 failed`) |
| 1 | mc1d: `NETWORK.md` line 8, `port 10000/udp` changed to `port 10001/udp` (S13, text) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1e: `run_config.yaml` line 18, `decision_threshold: 0.5` changed to `0.6` (S24, YAML) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1f: `raw_evaluations.jsonl` line 3, the uncited field `stream_length_discrepancy_ms` `13.5` changed to `13.6` | `test_FR_0_1_03_raw_files_unchanged_since_inventory` ("SHA-256 6c037c1e…, the Raw inventory says ff3b47c2…") | Caught (`1 failed`) |
| 1 | mc1g: mc1b **and** the R5 inventory row updated to the new bytes and SHA-256, so the hash test cannot decide | `…_every_number_matches_its_cited_source` ("S160 … gives 584.7815458937198, shown under '1 dp' as '584.8'; SUMMARY.md shows '580.0'"). The hash test passes (`1 passed` when run alone) | Caught (`6 failed`) |
| 1 | mc1h: mc1a **and** the R6 inventory row updated | `…_every_number_matches_its_cited_source` (S154, as mc1a), `…_report_log_and_records_agree` | Caught (`7 failed`) |
| 2. A missing raw file is reported as missing | mc2a: `run.log` (R7) deleted | `test_FR_0_1_01_raw_folder_has_every_required_item` ("2026-10-03: R7 raw/run.log missing or empty") and 10 other test functions | Caught (`32 failed`) |
| 2 | mc2b: `03_report.ipynb` (R6) deleted | `…_raw_folder_has_every_required_item` ("2026-10-03: R6 raw/03_report.ipynb missing or empty") and others | Caught (`25 failed`) |
| 2 | mc2c: `NETWORK.md` (R4) emptied | `…_raw_folder_has_every_required_item` ("2026-10-03: R4 raw/NETWORK.md missing or empty"), `…_raw_files_agree_on_the_run` ("R4 raw/NETWORK.md: does not answer …"), `…_every_number_matches_its_cited_source`, the hash test | Caught (`21 failed`) |
| 2 | mc2d: `jingle_stanzas_debug_listener.log` (R8) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item` ("R8 missing: no listener log listed in the Raw inventory"), `…_raw_files_agree_on_the_run` | Caught (`14 failed`) |
| 2 | mc2e: `raw_evaluations.jsonl` (R5) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item` ("2026-10-03: R5 has no file in the Raw inventory") and others | Caught (`38 failed`) |

## Exploratory breaks (A15, at most 10)
None. No code was added or changed since the last audited commit.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| — | — | — | — |

## Findings
No new findings this round.

| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.1-F1 | MAJOR | A15 | Fixed in round 2: each table cell cites exactly the Sources of its own row and column. | Round 2; unchanged | Closed |
| WP-0.1-F2 | MAJOR | A15 | Fixed in round 2 for what it named. The leftover gap is F8. | Round 2; unchanged | Closed (see F8) |
| WP-0.1-F3 | MAJOR | A15 | Fixed in round 2: each `raw_problems` consistency rule has a negative self-test. | Round 2; unchanged | Closed |
| WP-0.1-F4 | MAJOR | A15 | The hash test compares raw files only with the builder-written inventory. | DEBT-028; approval "Debt accepted" line | Accepted as debt (WP-0.9) |
| WP-0.1-F5 | MINOR | A2, A14 | SUMMARY.md omits the manifest count per category. | DEBT-029; same line | Accepted as debt (WP-0.9) |
| WP-0.1-F6 | MINOR | A14 | Fixed in round 2. | Round 2; unchanged | Closed |
| WP-0.1-F7 | MINOR | A6 | Fixed in round 2. | mc2d still fails `…_raw_folder_has_every_required_item` with "R8 missing: no listener log listed in the Raw inventory" | Closed |
| WP-0.1-F8 | MAJOR | A15 | The citation check exempts every table in the Sources and Raw inventory sections, not only the named table, so a second table there could hold an uncited number. The current SUMMARY.md has one table in each. | DEBT-030; approval line on `main` (`3c3f233`); code unchanged since round 3 | Accepted as debt (WP-0.9) |
| WP-0.1-F9 | MINOR | A15 | Four parts of `binding_problems` have no isolating self-test, and the Conditions table has no category-completeness check. The current content is correct. | DEBT-031; same approval line; code unchanged since round 3 | Accepted as debt (WP-0.9) |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 4 open (F1 to F4) | 3 open (F5 to F7) | None. Every must-catch break was caught. |
| 2 | 0 | 1 open (F8, new); F1, F2, F3 fixed; F4 accepted as debt | 1 open (F9, new); F6, F7 fixed; F5 accepted as debt | None. 13 of 13 caught. |
| 3 | 0 | 1 open (F8, unchanged); no new finding | 1 open (F9, unchanged); no new finding | None. 13 of 13 caught. |
| 4 | 0 | 0 open; F8 accepted as debt; no new finding | 0 open; F9 accepted as debt; no new finding | None. 13 of 13 caught, with the same counts as rounds 2 and 3. |

Round 3 recommended PASS with debt. The owner accepted that recommendation on `main`, and the records now meet the protocol's conditions for accepted debt. The audit has converged.

## For the owner
- **audit-allow lines:** none. The gate reports `Exempted lines (# audit-allow): 0`.
- **Approvals used:** `docs/approvals/WP-0.1.md` on `main` at `3c3f233`. It holds `STATUS: APPROVED`, the conditions on questions 1 and 6 and on R6, "BLK-016 Rulings Confirmed", "Round 2 Fixes" (F1, F2, F3, F7, F6) and "Debt accepted" (F4, F5, F8, F9, all with target WP-0.9).
- **Debt accepted so far (WP-0.1):**
  - DEBT-027: the owner's statement on wall-clock latency; target: the Phase 2 VAD timing work.
  - DEBT-028 (F4), DEBT-029 (F5), DEBT-030 (F8) and DEBT-031 (F9): target WP-0.9.
  - All five are OPEN.
- **Owner-run checks still pending:** none. The Tier 2 run was your input, and it is committed.
- **Which debt matters most for WP-0.9.** DEBT-028 carries the most real risk of the four. Today, a later change could alter a raw baseline file together with its inventory row, and the hash test would still pass. In mc1g above the hash test passes, and only the value check catches the change. A change to a field that SUMMARY.md does not cite, such as mc1f's, would then pass every test (round 1's F4). The cheapest fix is yours to make, because the builder cannot edit `docs/process/`: add `docs/baselines/tier2_vad/*/raw/**` to `docs/process/PROTECTED_PATHS.txt`. DEBT-030 and DEBT-031 matter only if someone later edits SUMMARY.md or the test helper.
- **Next step:** review and merge PR #9, then set WP-0.1 to MERGED in `docs/progress/STATUS.md`.
