# AUDIT — WP-0.1, round 2

Auditor: wp-auditor · Date: 2026-10-03 · Commit audited: `49f2274c2e7b07bac862f08df18f5739c3ce23a2` · Previous audited commit: `43fcf563c86ebd9ba218f223c88beed327c5cd5a` · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 5 (fixed 3: F1, F2, F3; accepted as debt 1: F4; open 1: F8, new) · MINOR: 4 (fixed 2: F6, F7; accepted as debt 1: F5; open 1: F9, new, does not block)

All round 1 findings are resolved:
- **F1, F2, F3, F6 and F7 are fixed.** I re-made the round 1 breaks that survived: E1, E2, E3, E4, E6 and E10. Each one now fails a named test. The deleted-listener-log break now fails the test named for missing items.
- **F4 and F5 are accepted as debt.** Your approval names both, and DEBT-028 and DEBT-029 record them, each with target WP-0.9.

Other results:
- All 13 must-catch breaks are caught.
- The fast and slow suites pass, the gate reports 0 findings, and CI is green on the audited commit.
- No number in SUMMARY.md and no raw file changed in this round.

The verdict is FAIL because of one new MAJOR finding, **F8**, a leftover of the F2 fix:
- The citation check skips every table line in the Sources section, not only the Sources table.
- In the Raw inventory section, it blanks the Bytes and SHA-256 columns of every table line, not only those of the inventory table.
- An uncited number in a second table in the Sources section therefore passes every test (A15 break X4: `44 passed`).
- The current SUMMARY.md has no such table, so its content is clean.
- The fix is a few lines.

One new MINOR finding, **F9**, does not block. Four parts of the new cell-binding check have no self-test that fails when that part alone is removed.

## Scope of this audit
This is a re-audit under protocol version 2.
- **Round 1 findings:** each of F1 to F7.
- **Items A1 to A15 on the diff `43fcf56..49f2274`.** That diff has 9 files:
  - test code: `tests/aqis_lab/aqis_baseline_testutil.py` and `tests/aqis_lab/test_aqis_tier2_baseline.py`;
  - `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md`: 3 lines (the title, and two sentences in "Owner's statement");
  - the owner's approval, `docs/approvals/WP-0.1.md`, from owner commit `264532a` on `main`, merged in `3584636`;
  - records: the `REGISTRY.md` row CAP-BASE-002, two rows appended to `DEBT.md`, and the WP-0.1 `AUDIT.md` (round 1), `EVIDENCE.md` and `FIXES.md`.
  - Nothing changed under `raw/`, `aqis_lab/`, `tools/`, `config/`, `requirements/`, `notebooks/`, `.github/` or any harness path.
- **The full set:** the fast and slow suites, the gate, CI, AT-0.1-01 and the complete must-catch proof.

Code that passed round 1 and has not changed was not searched again. The A15 breaks touch only round 2 code: `binding_problems` and its helpers, and `body_text`.

**How breaks were made:**
- I made every break in a fresh extraction of `git archive 49f2274`, under `/tmp/claude-0/…/scratchpad/wp01-r2/runs/<break>/`.
- A script applied each edit. Text replacements had to match exactly once, and table edits were made by row label and column header.
- `diff -rq` against an unbroken extraction confirmed that only the intended files changed.
- The script then ran the repository's `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider -rf --tb=line` from the copy's root.
- The tests read the copy, because `aqis_testutil.ROOT` is `Path(__file__).parents[2]`. For example, mc1h's message reports the copy's edited value `'433.7'`.
- The unbroken extraction gave `44 passed in 31.56s`.
- To see each break's problem strings, a second script called `raw_problems`, `binding_problems` and `summary_problems` in a fresh copy.
- The working repository was clean before and after the audit (`git status --porcelain` is empty).

**Two notes on the counts:**
- Every content break also fails the 5 cases of `test_FR_0_1_02_check_reports_a_changed_raw_value`. Their first step asserts that the unedited folder has no problems.
- Some breaks likewise fail cases of the other self-tests, whose first step expects a clean copy.

## Round 1 findings: status
| Finding | Status | Evidence |
| --- | --- | --- |
| **F1 (MAJOR)** no check tied a cell's row or column to the Sources it cites | **Fixed** | `binding_problems` (`aqis_baseline_testutil.py:895-940`) is called from `summary_problems`. E1 re-made (all metric cells swapped between `ten_vad` and `firered_vad`): `7 failed, 37 passed`, including `test_FR_0_1_02_cells_cite_their_own_row_and_column`, with 100 problems such as "row 'ten_vad', column 'F1': cites S149, which is not a source of this row and column". E2 re-made (`ten_vad` F1 and Precision swapped): `7 failed`, the same test, 12 problems. The new A15 swaps X1, X2 and X5 and the row removal X3 are also caught (below). |
| **F2 (MAJOR)** three whole sections skipped by the citation check | **Fixed for what F2 named; leftover gap is F8** | `body_text` (`:706-725`) now reads the title, the prose of every section and the inventory's other columns. E3 re-made (a sentence with "15 ms" in "Owner's statement"): `6 failed`, `test_FR_0_1_02_every_number_cites_a_source`, "body line 95: a number without a citation: 'Decisions in this run arrive 15 ms early on average.'". E4 re-made ("(1500 scored clips, 3 % lost)" in the R5 "What it is" cell): `6 failed`, the same test, "body line 104: …". The exemptions for the Sources and Raw inventory sections still cover every `\|` line in those sections, not only their tables: F8. |
| **F3 (MAJOR)** `raw_problems` consistency checks had no negative self-test | **Fixed** | New `test_FR_0_1_01_check_reports_each_inconsistency`, 12 cases from R1 to R8. E6 re-made (the R5 count check disabled): `1 failed, 43 passed`, `[R5-clip-records-missing]`. E10 re-made (the R1 `run_context` comparison disabled): `1 failed, 43 passed`, `[R1-config-differs-from-run-context]`. Each case also asserts that every problem names its item. |
| F4 (MAJOR) raw files compared only with the builder-written inventory | Accepted as debt | The approval on `main` says: "Debt accepted: WP-0.1-F4 (target WP-0.9) and WP-0.1-F5 (target WP-0.9)". DEBT-028 has target WP-0.9 and status OPEN. On this branch, no raw file changed: `git diff --name-only origin/main...HEAD -- docs/baselines/tier2_vad/2026-10-03/raw` returns 0 lines. |
| F5 (MINOR) per-category manifest counts promised in PLAN.md, not shown | Accepted as debt | Same approval line. DEBT-029 has target WP-0.9 and status OPEN. |
| **F6 (MINOR)** EVIDENCE.md said every test failed at the tests-only commit | **Fixed** | `EVIDENCE.md` FR-0.1-01 "Test first" now says 17 failed and 1 passed. I re-ran the tests at `cb49333` in `/tmp` and got `17 failed, 1 passed in 0.35s`; the one pass was `test_FR_0_1_01_raw_folder_holds_no_audio`. |
| **F7 (MINOR)** a missing R8 log was not reported as "missing" | **Fixed** | `raw_problems` (`:282-284`). Must-catch break mc2d (listener log deleted and its inventory row removed) now fails `test_FR_0_1_01_raw_folder_has_every_required_item` with "R8 missing: no listener log listed in the Raw inventory". In round 1, that test passed. |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none". The branch is `claude/practical-knuth-wsgvud`, not `main`. `git show origin/main:docs/approvals/WP-0.1.md` gives `STATUS: APPROVED`, with the lines "BLK-016 Rulings Confirmed", "Round 2 Fixes" (F1, F2, F3, F7, F6) and "Debt accepted" (F4, F5). The branch copy equals `main`: `git diff origin/main HEAD -- docs/approvals/` returns 0 lines. |
| A2 Requirement coverage | PASS | 18 test functions, 44 collected, all named after their FR. FR-0.1-01 has 6: the 5 from round 1 plus `check_reports_each_inconsistency` (12 cases). FR-0.1-02 has 10: the 7 from round 1 plus `cells_cite_their_own_row_and_column`, `check_reports_cells_in_the_wrong_row_or_column` (7 cases) and `check_reports_uncited_numbers_in_every_section` (6 cases). FR-0.1-03 has 2. `pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider -rA` gives `44 passed in 16.50s`. The new tests are listed in EVIDENCE.md's "Round 2" section. |
| A3 Acceptance commands | PASS | AT-0.1-01: I drew five rows with `random.SystemRandom().sample` from the 327 numeric Sources rows and checked each against the raw files with `jq` or a direct notebook read, without the test helper. **S183** `0.926`: report cell 3 output 1, row `webrtc_vad_mode0`, Precision `0.926`. **S334** `86`: negative non-null `mean_offset_hangover_latency_ms` over `webrtc_vad_mode1` `tier2_pipeline_latency` records gives `86`. **S107** `0.978`: `ten_vad` Σtp `135820` and Σfp `3004` give `0.97836…`. **S295** `0`: null onset over `webrtc_vad_mode3` latency records with speech gives `0`. **S96** `10`: `webrtc_vad_mode1` `scoring_clip` in `packet-loss/jitter` gives `10`. All five match their SUMMARY.md cells. |
| A4 Test suites and CI | PASS | Fast: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` gives `1856 passed, 55 deselected in 230.40s`. Slow: `-m "slow and not gpu and not colab and not oracle and not network"` gives `5 passed, 1906 deselected in 69.91s`. CI on `49f2274`: run 37125004109 (push) and run 37125007822 (pull_request), workflow `aqis-lab-ci`; jobs `lab` and `harness-regression` are `success` in both, read with `gh api …/actions/runs/<id>/jobs`. The only non-success step is "Work package ID from pull request title" on the push run: `skipped`, because it has `if: github.event_name == 'pull_request'`. |
| A5 Test integrity | PASS | `git diff --name-status origin/main...HEAD -- tests/` shows only added files, so no merged test was touched. An AST comparison of `43fcf56` and `HEAD` shows the round 1 test functions unchanged except the helper `identifiers()`. It now also accepts the baseline folder's own name (`2026-10-03`), because the title line is now checked. FIXES.md discloses this, and the change makes the check stricter overall, since the title used to be skipped. A grep of the added lines for `skip`, `xfail`, `assert True`, `mock`, `monkeypatch`, `except Exception`, `except:` and `pass` finds nothing. |
| A6 Must-catch proof | PASS | 13 of 13 breaks caught; see the table below. |
| A7 Compromise scan | PASS | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` gives `Findings: 0`, `0 findings: OK`, exit 0. I read the new functions. There are no stubs or placeholders. `CELL_SPECS` holds column names, field paths and record types, never expected values. Read failures become a named problem (`:906-907`). A missing quoted statement in the approval raises (`owner_statement`, `:698-703`). The exemption scope of `body_text` is F8. |
| A8 Scope diff | PASS | The changed files match FIXES.md's change budget. An AST comparison of top-level definitions agrees with it: the changed definitions are `identifiers`, `body_text`, `raw_problems` and `summary_problems`. `UNCHECKED_SECTIONS` was removed. The added definitions are the binding helpers, `owner_statement` and the section constants. SUMMARY.md: 3 lines changed, with no number and no Sources row touched. REGISTRY.md: the CAP-BASE-002 row only. DEBT.md: 2 rows appended, 0 changed. BLOCKERS.md: unchanged since `43fcf56`. Raw files unchanged (0 lines, see F4). The gate's protected-path checks pass. |
| A9 Capabilities | PASS | CAP-BASE-002 was updated. The registry has 149 rows at `43fcf56` and at `HEAD`. The 18 test names in the row equal the 18 collected test functions (`diff` of the two sorted lists is empty). |
| A10 Contracts | N/A | No lab contract covers a baseline summary, and the spec names none (unchanged from round 1). |
| A11 Environment parity | PASS | No absolute paths in the added lines: a grep for `/home`, `/tmp` and `/content` finds nothing. No new dependency. `.venv` runs Python 3.13.14, which matches 3.13 in `docs/environment/colab_probe.txt`. The bootstrap gives `OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34…`. No owner-run checks. |
| A12 Reproducibility and traceability | PASS | 44 passed in the repository and in the clean `/tmp` extraction. The self-tests edit `tmp_path` copies only. No Sources row or cited number changed since round 1, so its traceability checks still hold. |
| A13 Errors and logging | PASS | `binding_problems` reports unreadable tables or raw files as a problem, never as an empty result. A table without the expected header becomes a problem. `owner_statement` raises `ValueError` when the approval lacks the quote. |
| A14 Documentation, licences, data | PASS | EVIDENCE.md has a "Round 2" section. I reproduced its counts: `44 passed`, `1856 passed, 55 deselected`, and gate `0 findings`. The F6 correction is accurate (A6 table, F6 row). FIXES.md gives the root cause, the change budget and test-first evidence for each finding. No new data was added. |
| A15 Exploratory breaks | 5 of 10 survived | See the table below. X4 survives and is F8 (MAJOR). H1, H3, H4 and H5 survive and are F9 (MINOR). |

## Must-catch proof (A6)
Each break was made in a fresh extraction of `49f2274`, as described in Scope. The unbroken copy gives `44 passed`.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1. Every number matches its cited raw file | mc1a: `03_report.ipynb` line 136, `firered_vad` Onset Latency `433.6 ms` changed to `433.7 ms` | `test_FR_0_1_02_every_number_matches_its_cited_source` (S154), `test_FR_0_1_02_report_log_and_records_agree`, `test_FR_0_1_03_raw_files_unchanged_since_inventory` | Caught (`8 failed, 36 passed`) |
| 1 | mc1b: `raw_evaluations.jsonl` line 854, `firered_vad` `mean_wallclock_pipeline_latency_ms` `471.66` changed to `1471.66` | `…_every_number_matches_its_cited_source` (S160, S161), the FR-0.1-03 hash test | Caught (`7 failed`) |
| 1 | mc1c: the same record, `471.66` changed to `471.80` (median only; the mean is unchanged at 1 dp) | `…_every_number_matches_its_cited_source` (S161 only) | Caught (`7 failed`) |
| 1 | mc1d: `NETWORK.md` line 8, `port 10000/udp` changed to `port 10001/udp` (S13, text) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1e: `run_config.yaml`, `decision_threshold: 0.5` changed to `0.6` (S24, YAML) | `…_every_number_matches_its_cited_source`, the hash test | Caught (`7 failed`) |
| 1 | mc1f: `raw_evaluations.jsonl` line 3, the uncited field `stream_length_discrepancy_ms` `13.5` changed to `13.6` | `test_FR_0_1_03_raw_files_unchanged_since_inventory` | Caught (`1 failed`) |
| 1 | mc1g: mc1b **and** the R5 inventory row updated to the new bytes and SHA-256, so the hash test cannot decide | `…_every_number_matches_its_cited_source` (S160, S161). The hash test passes | Caught (`6 failed`) |
| 1 | mc1h: mc1a **and** the R6 inventory row updated | `…_every_number_matches_its_cited_source` ("S154 … the source gives '433.7', SUMMARY.md shows '433.6'"), `…_report_log_and_records_agree` | Caught (`7 failed`) |
| 2. A missing raw file is reported as missing | mc2a: `run.log` (R7) deleted | `test_FR_0_1_01_raw_folder_has_every_required_item` ("R7 missing: raw/run.log does not exist"), `…_every_number_matches_its_cited_source` ("S5 (raw/run.log …): raw/run.log is missing") and others | Caught (`32 failed`) |
| 2 | mc2b: `03_report.ipynb` (R6) deleted | `…_raw_folder_has_every_required_item` and others | Caught (`25 failed`) |
| 2 | mc2c: `NETWORK.md` (R4) emptied | `…_raw_folder_has_every_required_item`, `…_raw_files_agree_on_the_run` ("R4 … does not answer 'where Jitsi ran'"), `…_every_number_matches_its_cited_source` (S2, S3, S7, …) | Caught (`21 failed`) |
| 2 | mc2d: `jingle_stanzas_debug_listener.log` (R8) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item` ("R8 missing: no listener log listed in the Raw inventory"), `…_raw_files_agree_on_the_run` | Caught (`14 failed`); the named test now fails (F7 fixed) |
| 2 | mc2e: `raw_evaluations.jsonl` (R5) deleted **and** its inventory row removed | `…_raw_folder_has_every_required_item`, `…_raw_files_agree_on_the_run`, `…_cells_cite_their_own_row_and_column` and others | Caught (`38 failed`) |

## Exploratory breaks (A15, at most 10)
These target only round 2 code. X breaks change SUMMARY.md content and test the new checks on bad content. H breaks loosen one part of the new check and test whether a self-test notices.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1: the VADs table's Library version cells (value and citation) swapped between `ten_vad` and `firered_vad` | `SUMMARY.md` VADs table | No: `…_cells_cite_their_own_row_and_column` ("row 'ten_vad', column 'Library version': cites S27, which is not a source of this row and column") | — |
| X2: only the "Negative wall-clock" cells swapped between `ten_vad` (185 [S306]) and `firered_vad` (0 [S316]) | `SUMMARY.md` Run health table | No: `…_cells_cite_their_own_row_and_column` ("cites S316, which is not a source of this row and column") | — |
| X3: the `webrtc_vad_mode3` row of the VADs table and its Sources rows S34 and S35 deleted | `SUMMARY.md` VADs table and Sources | No: `…_cells_cite_their_own_row_and_column` ("VADs table 'Operating point': rows […5 points], expected one per operating point […6 points]") | — |
| X4: a second table appended in the Sources section, after the Sources table: `\| Note \| Detail \|`, then `\| Scored clips \| 1500 \|` | `SUMMARY.md` Sources section; checked by `body_text:717` | **Yes** (`44 passed in 17.62s`; `summary_problems` returns 0 problems) | MAJOR (F8) |
| X5: an extra equal-valued citation, `0 [S130]` changed to `0 [S130] [S297]` (`ten_vad` clip failures) | `SUMMARY.md` headline "Clips with no onset" | No: `…_cells_cite_their_own_row_and_column` ("cites S297, which is not a source of this row and column") and the round 1 `…_headline_metrics_cover_every_operating_point` | — |
| H1: `_report` no longer checks the report row (`and loc.get("row") == key` removed) | `aqis_baseline_testutil.py:780` | **Yes** (`44 passed`) | MINOR (F9) |
| H2: `_agg` ignores `adapter_id` in `where` | `:798` | No: `[run-health-rows]` (`1 failed, 43 passed`) | — |
| H3: the one-row-per-operating-point check disabled (`if keys != points:` changed to `if False:`) | `:920` | **Yes** (`44 passed`) | MINOR (F9) |
| H4: the extra-citation check disabled (`if sid not in used:` changed to `if False:`) | `:890` | **Yes** (`44 passed`) | MINOR (F9) |
| H5: `_shape` returns after the shape check, without binding each operand to this row | `:812` | **Yes** (`44 passed`) | MINOR (F9) |

**What the survivors allow.** I ran H1 and H3 each together with the X break they guard against. This combines breaks already made; it does not search further:
- **H1 with X1** (Library versions swapped): `raw_problems`, `binding_problems` and `summary_problems` each return 0 problems.
- **H3 with X3** (a VAD missing from the VADs table): all three return 0 problems.
- Without H1 and H3, X1 and X3 are caught (above).

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.1-F1 | MAJOR | A15 | **Fixed.** Each table cell must cite exactly the Sources of its own row and column. | E1, E2 re-made and caught; X1, X2, X3, X5 caught | Closed |
| WP-0.1-F2 | MAJOR | A15 | **Fixed for what it named.** The Owner's statement prose, the inventory "What it is" cells, the section intros and the title are now checked. The remaining gap is F8. | E3, E4 re-made and caught; 6 `UNCITED_INSERTS` cases pass | Closed (see F8) |
| WP-0.1-F3 | MAJOR | A15 | **Fixed.** Each `raw_problems` consistency rule has a negative self-test. | E6 → `[R5-clip-records-missing]`; E10 → `[R1-config-differs-from-run-context]` | Closed |
| WP-0.1-F4 | MAJOR | A15 | Accepted as debt. | DEBT-028; approval CONDITIONS "Debt accepted" | Accepted (WP-0.9) |
| WP-0.1-F5 | MINOR | A2, A14 | Accepted as debt. | DEBT-029; same line | Accepted (WP-0.9) |
| WP-0.1-F6 | MINOR | A14 | **Fixed.** | `cb49333` re-run: `17 failed, 1 passed` | Closed |
| WP-0.1-F7 | MINOR | A6 | **Fixed.** | mc2d fails `…_raw_folder_has_every_required_item` with "R8 missing: …" | Closed |
| WP-0.1-F8 | MAJOR | A15 | **New. The F2 fix exempts more than the Sources and inventory tables.** In the Sources section, `body_text` skips every line that starts with `\|`, not only the rows of the table headed `ID` (`aqis_baseline_testutil.py:717`). In the Raw inventory section, it blanks the Bytes and SHA-256 columns of every `\|` line, not only those of the table headed `Item` (`:719-724`; this part is from reading the code, not a separate break). So a second table in either section is skipped by the citation check, wholly or partly. X4 shows it: an uncited "1500" in a second table in the Sources section passes all 44 tests, and FR-0.1-02's check reports success. The comment above the exemptions (`:68-70`), FIXES.md and the CAP-BASE-002 row all say only "the cells of the Sources table" are exempt. **The current file is clean.** The Sources section holds only its table (header, separator, 359 rows), and the Raw inventory section only its table (header, separator, 10 rows). | X4: `44 passed in 17.62s`, `summary_problems` returns 0 problems | **Fix now.** The fix is small and inside the F2 fix you ordered: exempt only the rows of the table headed `ID`, and the Bytes and SHA-256 cells of the table headed `Item`, and read any other `\|` line in those sections as body text. Add two `UNCITED_INSERTS` cases: a second table in the Sources section, and one in the Raw inventory section. If you would rather close the WP now, the alternative is debt with target WP-0.9. |
| WP-0.1-F9 | MINOR | A15 | **New. Four parts of `binding_problems` have no self-test that fails when that part alone is removed.** The 7 swap cases are each caught by several bindings at once, so none isolates these parts: H1, the report row binding (`:780`); H3, one row per operating point (`:920`); H4, extra citations (`:890`); H5, binding of `expr` operands (`:812-815`). With H1 or H3 removed, a wrong VADs table passes (X1 or X3, 0 problems). From reading the code, without a separate break: the Conditions table has no matching completeness check. `:932-939` binds each row's cells, but nothing requires every category to have a row. The current content is correct: X1, X2, X3 and X5 are caught. This is MINOR rather than MAJOR because reaching any of these gaps needs a later edit to the helper. Once merged, that is an edit to an existing test, which needs your approval and an audit. That is the same reasoning as WP-0.8-F12. Round 1's F3 was MAJOR because the checks it named had no negative test at all; here the binding check as a whole is pinned (H2 caught). | H1, H3, H4, H5: `44 passed` each. H1 with X1 and H3 with X3: 0 problems | **Fix in the F8 round**, because it is cheap there. Add cases that each isolate one part: the Library version swapped between `ten_vad` and `firered_vad` (H1); a VADs row deleted with its Sources rows (H3); an extra equal-valued citation in a Run health cell, such as `[S307]` beside `[S297]` (H4); and the `expr` citations of the equal-valued Precision cells of `webrtc_vad_mode0` and `webrtc_vad_mode1` (`[S173]`, `[S206]`) swapped (H5). Optionally add a category-completeness check. If you do not want it in that round, accept as debt with target WP-0.9. |

## Convergence (round 3 onwards)
This is round 2, so the protocol's convergence rule does not apply yet. The table is for comparison.

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 4 open (F1 to F4) | 3 open (F5 to F7) | None. Every must-catch break was caught. |
| 2 | 0 | 1 open (F8, new); F1, F2, F3 fixed; F4 accepted as debt | 1 open (F9, new); F6, F7 fixed; F5 accepted as debt | None. All 13 must-catch breaks are caught. F8 concerns uncited numbers outside the tables, not a changed or missing raw value. |

Open findings went from 7 to 2, and only F8 blocks.

## For the owner
- **audit-allow lines:** none (gate: `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.1.md` on `main` (`264532a`). It holds:
  - `STATUS: APPROVED`;
  - the conditions on questions 1 and 6 and on R6;
  - "BLK-016 Rulings Confirmed". This answers the round 1 request to confirm rulings (b) and (c);
  - "Round 2 Fixes" (F1, F2, F3, F7, F6);
  - "Debt accepted" (F4, F5, both with target WP-0.9).
- **Debt accepted so far:**
  - DEBT-027: the owner's statement on wall-clock latency; target: the Phase 2 VAD timing work.
  - DEBT-028 (F4) and DEBT-029 (F5): target WP-0.9.
  - All three are OPEN.
- **Owner-run checks still pending:** none. The Tier 2 run was your input and is committed.
- **To reach PASS, choose one:**
  1. Approve a round 3 fix of F8, and of F9 if you wish, with a "Round 3 Fixes" line in `docs/approvals/WP-0.1.md`. This is my recommendation.
  2. Accept F8 as debt: add a CONDITIONS line naming WP-0.1-F8 with target WP-0.9, and the builder adds a `DEBT.md` row.

  Either way, a short re-audit then confirms it.
- **A wording change in SUMMARY.md you may notice.** The stricter check reads every digit outside a code span as a number that needs a citation. To pass it, the builder made two changes in the Owner's statement section:
  - The precise cross-reference "DEBT-027" became "the row on wall-clock pipeline latency".
  - "question 6" became "its condition on negative and null latencies".

  Both are still findable, and neither changes a fact. If you want document IDs such as `DEBT-027` allowed in prose, that needs a small addition to the identifier list in a later fix.
