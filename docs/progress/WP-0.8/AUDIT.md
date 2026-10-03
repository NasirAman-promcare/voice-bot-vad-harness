# AUDIT — WP-0.8, round 2

Auditor: wp-auditor · Date: 2026-10-03 · Commit audited: 24132fea55b9bc65525f45e568dd629586d2bbea · Previous audited commit: 72023169f75dce215ec4f1b587ed66baa63f501c · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 (round 1's F01 fixed) · MAJOR: 5 (fixed 2, accepted as debt 2, open 1) · MINOR: 5 (F08 fixed; F06 and F07 accepted as debt, DEBT-024 and DEBT-025; F10 and F11 new, open)

The round 1 blockers are dealt with:
- **F01 is fixed.** M1h, the break that survived round 1, now fails `test_FR_0_8_01_owner_facts_appear_as_given`. All 19 must-catch breaks are caught.
- **F02 is fixed.** The owner restored the question 5 and question 6 lines on `main` (`f97f492`). The test now reads them from the current approval and no longer needs git history, which also closes F08.
- **F03 is fixed for every case I re-made.** E1 to E3 each fail the owner-fact test, and so does a whole new paragraph added to an owner-fact section.
- **F04 to F07 are accepted as debt.** The approval has a CONDITIONS line naming them, and `DEBT.md` has rows DEBT-022 to DEBT-025, all with target WP-0.9.

The fast and slow suites pass, CI is green on the audited commit, and the gate is clean. The documents have not changed since round 1.

One new MAJOR finding blocks the pass (F09). It is the part of F03 that the fix does not reach: the consent block. The new check reads only lines that start `- [ ] `. A sentence added to "Your consent" passes every test, and so does an extra tick box written `* [ ]`. Each can give an access promise the owner never made, on the block participants sign. The committed form has neither. The fix is test-only and small. Two new MINOR findings cover a gap in the new guard test (F10) and stale lines in EVIDENCE (F11).

## Scope of this audit
Re-audit, as protocol version 2 requires:
- **Round 1 findings:** each of F01 to F08.
- **Items A1 to A15 on the diff `7202316..24132fe`.** That diff has 7 files:
  - test code: `tests/aqis_lab/test_aqis_recording_docs.py` (the owner-fact block and the imports);
  - the owner's approval, `docs/approvals/WP-0.8.md`, from owner commit `f97f492` on `main`, merged in `5064d19`;
  - records: the `REGISTRY.md` row CAP-DOC-014, four new rows in `DEBT.md`, and the WP-0.8 records (AUDIT, EVIDENCE, FIXES).
  - No production code and no document under `docs/recording/`, `docs/fillers/` or `docs/decisions/` changed.
- **The full set:** the fast and slow suites, the gate, CI and the complete must-catch proof.

Unchanged code that passed round 1 was not searched again. In particular, these were not re-probed beyond the A6 set:
- the debt fixes in `aqis_lab/`;
- the retention and contact checks;
- the guide, form, filler and targets tests.

**How breaks were made:**
- All breaks were made in my own throwaway clone, `/tmp/wp08-audit-r2`: a local `git clone` checked out at `24132fe`, with `.venv` linked.
- A probe test run inside the clone printed `AQIS /tmp/wp08-audit-r2/aqis_lab/__init__.py /tmp/wp08-audit-r2 /tmp/wp08-audit-r2/docs/approvals/WP-0.8.md`. So `aqis_lab`, the tests' `ROOT` and the approval the tests read all came from the clone.
- A script applied each break as exact text replacements, each of which had to match once. It then ran the three document test files with `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py tests/aqis_lab/test_aqis_filler_library.py tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider -rf --tb=no`.
- After each run it restored the tree with `git checkout -- docs tests aqis_lab` and asserted that `git status --porcelain` was only `?? .venv`. The unbroken baseline was `45 passed in 0.19s`.

## Round 1 findings: status
| Finding | Status | Evidence |
| --- | --- | --- |
| F01 (CRITICAL) withdrawal window in its own section not pinned | **Fixed** | I re-made M1h (30 → 14 days in "Your right to withdraw" only). It gives `2 failed, 43 passed`: `test_FR_0_8_01_owner_facts_appear_as_given`, plus the parametrised case `…_rejects_changed_window_and_additions[M1h-window-14-days]`, whose target text the break removed. `owner_fact_problems` (`test_aqis_recording_docs.py:171-183`) now compares each of the four owner-fact sections with exact text, and the tick-box list as a whole. |
| F02 (MAJOR) owner facts traced to a superseded approval | **Fixed** | The approval on `main` has the restored lines. Owner commit `f97f492` ("Restore Q5/Q6 consent lines (F02) …", author NasirAman-promcare) adds the question 5 line and question 6 (a) to (f). `_approval_fact` (`:128-132`) reads the current `docs/approvals/WP-0.8.md`; `FACTS_COMMIT`, `_owner_approval_with_facts` and `import subprocess` are gone. Three breaks show the current approval drives the check: X4 (approval window → 14 days, form unchanged), X5 (the question 5 and 6 lines removed, as at `b4b327e`) and X6 (question 5 storage changed). Each fails `…_owner_facts_appear_as_given`. "Questions 2 to 8: as recommended in PLAN.md" still follows the restored lines. I read the explicit question 5 and 6 lines as governing, as the commit message says. |
| F03 (MAJOR) invented additions beside owner wording | **Fixed for the four prose sections; residual gap in the consent block (F09)** | E1, E2 and E3 re-made: each gives `2 failed, 43 passed`, and `…_owner_facts_appear_as_given` is among the failures. X3 (a new paragraph "Our technology partners may also hear them." in "Who can see them") fails it too. X1 and X2 in the consent block survive (F09). |
| F04 (MAJOR) targets "does not choose" word list | **Accepted as debt** | CONDITIONS line in the approval on `main`: "Debt accepted: WP-0.8-F04 (target WP-0.9), …". `DEBT.md` row DEBT-022: target WP-0.9, OPEN. |
| F05 (MAJOR) rule 1 keyed on the word "positive" | **Accepted as debt** | Same CONDITIONS line. DEBT-023: target WP-0.9, OPEN. |
| F06 (MINOR) drafted content not marked | **Accepted as debt** | Same CONDITIONS line. DEBT-024: target WP-0.9, OPEN. |
| F07 (MINOR) harm-rate counts embed a test method | **Accepted as debt** | Same CONDITIONS line. DEBT-025: target WP-0.9, OPEN. |
| F08 (MINOR) owner-fact test needed full git history | **Fixed** | In a depth-1 clone (`git clone --depth 1`, `is-shallow-repository` `true`, 1 commit), `pytest tests/aqis_lab/test_aqis_recording_docs.py -k FR_0_8_01` gives `15 passed, 13 deselected in 0.09s`. |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none". Branch `claude/beautiful-bohr-gf9yck`, not `main`. `git show origin/main:docs/approvals/WP-0.8.md` starts `STATUS: APPROVED`, and its `diff` with the branch copy is empty. It holds "Round 2 Fixes: fix WP-0.8-F01, WP-0.8-F02, WP-0.8-F03" and the debt line for F04 to F07. The merge `5064d19` brought in only `docs/approvals/WP-0.8.md` (`git diff d35747b 5064d19 --stat`). `git diff --name-only 7202316 HEAD -- requirements .claude CLAUDE.md docs/specs docs/process docs/progress/WP-0.8/PLAN.md` is empty. |
| A2 Requirement coverage | PASS (see F11) | `pytest --collect-only -k FR_0_8` collects FR-0.8-01: 15 (the round 1 eight, plus the 7 cases of `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions`), FR-0.8-02: 9, FR-0.8-03: 4, FR-0.8-04: 9, FR-0.8-05: 8. That is 45 tests. Every ID has an `EVIDENCE.md` section. The new test is named at `EVIDENCE.md:193`, but not in the FR-0.8-01 test list (F11). |
| A3 Acceptance commands | PASS (see F09, F11) | `pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k FR_0_8`: `45 passed, 1818 deselected in 3.43s`. AT-0.8-01: the five documents are byte-identical to round 1 (none is in `git diff --name-only 7202316 HEAD`), so round 1's document-by-document review stands. I re-checked the consent form against the restored approval. Question 6 (a), (b), (c) and (e) and question 5 appear word for word in their sections (`CONSENT_FORM.md:9`, `:15`, `:18`, `:24`). The tick boxes carry (d) and the (e) window (`:33`, `:35`). Retention and contact are still owner blanks (`:21`, `:27`). The approval now records the retention decision ("3 years …"). The form correctly keeps the blank, as FR-0.8-01 asks. |
| A4 Test suites and CI | PASS | Fast suite: `1808 passed, 55 deselected in 253.56s (0:04:13)`, exit 0 (round 1: 1801, plus the 7 new cases). Slow suite (`-m "slow and not gpu and not colab and not oracle and not network"`): `5 passed, 1858 deselected in 88.90s`, exit 0. The tree was clean before and after. CI on `24132fe`: run 37049159155 (push) and run 37049166166 (pull_request) both have `lab` success and `harness-regression` success. In the PR `lab` job (110977953231), the steps "Fast lab test suite" and "Audit gate (pull request base with --wp …)" are both success. The log text could not be downloaded (`results-receiver.actions.githubusercontent.com` … `Forbidden`), so I checked conclusions and steps through the API. |
| A5 Test integrity | PASS | One test file changed: `test_aqis_recording_docs.py`. It is new in this WP (`git cat-file -e origin/main:…` gives `exists on disk, but not in 'origin/main'`), and it changed under the round 2 fix condition. The new `test_FR_0_8_01_owner_facts_appear_as_given` is strictly stronger than the old one. Before, each owner phrase only had to appear somewhere in the form. Now each owner-fact section and the tick-box list must equal text built from the approval. No other test changed (`git diff -U0`: hunks only at the imports and lines 128-214). There is no `skip`, `xfail` or `audit-allow`. Each new parametrised case asserts that its target text occurs exactly once before it applies the break, so no case can pass on a missing target. |
| A6 Must-catch proof | PASS | 19 breaks over the 2 behaviours, the same set as round 1: **19 caught, 0 survived** (table below). |
| A7 Compromise scan | PASS | Gate: `aqis-audit-gate: base origin/main (merge-base f97f4929b4d5), head 24132fea55b9, approvals origin/main f97f4929b4d5, wp WP-0.8 … Exempted lines (# audit-allow): 0 … Findings: 0 … 0 findings: OK (2.7 s)`, exit 0. I grepped the added lines of `git diff -U0 7202316 HEAD -- tests/ aqis_lab/ tools/` for stub words, `skip`, `xfail`, `except`, `audit-allow` and absolute paths: no match. No production code changed in this round. |
| A8 Scope diff | PASS | The changed files match the FIXES.md change budget. The test hunks are the import lines and the owner-fact block. `REGISTRY.md` changes one row, CAP-DOC-014. `DEBT.md` adds four rows and changes no existing row. The records are WP-0.8's own. The approval change is the owner's own commit. No protected path changed without approval (gate: 0 findings). |
| A9 Capabilities | PASS | `REGISTRY.md` has 148 rows at `7202316` and at `HEAD`, with the same IDs in the same order. CAP-DOC-014 keeps every old test and adds `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions`. Its text is stronger ("exactly as `docs/approvals/WP-0.8.md` words them, with nothing changed or added"). For the consent block, that claim is wider than the check (F09). `test_FR_0_0_08_repository_registry_is_consistent` passes in the fast suite. |
| A10 Contracts | N/A | No data contract applies to the documents, and no code with a contract changed. |
| A11 Environment parity | PASS | `.venv` is Python 3.13.14; `docs/environment/colab_probe.txt` says 3.13.15. No lock changed. No absolute path in the added lines. The test no longer runs git, and it passes in a shallow clone (F08). The owner-run checks are listed in `EVIDENCE.md` "Owner-run checks", with command and expected output. |
| A12 Reproducibility and traceability | PASS | The owner values in the expected text are read from the current approval at run time. X4 to X6 show that a change in the approval, not in the form, makes the test fail. The connecting prose in `expected_owner_fact_sections` and `expected_tick_boxes` is the form's own wording, pinned on purpose: that is what makes any added or changed word fail. See "For the owner". |
| A13 Errors and logging | PASS | When the approval lacks a line, the check fails loudly instead of passing. X5 gives `8 failed`, and `_approval_fact` asserts on a missing label. A question 6 (b) or (e) line with a different shape makes the tuple unpacking raise `ValueError`. |
| A14 Documentation, licences, data | PASS (see F11) | FIXES.md records the findings, root cause, change budget, the tests-first failures (`5 failed, 3 passed` with the round 1 logic), the fix, the break proof, the suite, the gate and CI. `DEBT.md` has the four approved rows. No personal data was added. The stale spots in EVIDENCE are F11. |
| A15 Exploratory breaks | 8 made, 3 survived | Table below. X1 and X2 survive (F09). X7, a break of the guard test's checker, survives (F10). E1 to E3 were re-made to verify F03; they are not counted here. |

## Must-catch proof (A6)
All 19 breaks from round 1, re-made at `24132fe`. Unbroken: `45 passed in 0.19s`.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 No owner value filled in by Claude | M1a retention blank → "2 years" | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`, `…_blank_check_detects_a_filled_in_value` (`2 failed, 43 passed`) | Caught |
| 1 | M1b retention blank → "3 years from the date of recording" | same 2 tests (`2 failed, 43 passed`) | Caught |
| 1 | M1c blank kept, ", and never more than five years" added beside it | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value` (`1 failed, 44 passed`) | Caught |
| 1 | M1d contact blank → `aqis-lab@example.org` | `test_FR_0_8_01_contact_is_an_owner_blank` (`1 failed, 44 passed`) | Caught |
| 1 | M1e `**Decision:** [OWNER DECIDES: timing-budget option]` → `**Decision:** TB-B` | `test_FR_0_8_05_document_does_not_choose` (`1 failed, 44 passed`) | Caught |
| 1 | M1f GE-B value marked "(preferred)" | `test_FR_0_8_05_document_does_not_choose` (`1 failed, 44 passed`) | Caught |
| 1 | M1g owner access wording → "Only the lab owner and the project team" | `test_FR_0_8_01_owner_facts_appear_as_given` (`2 failed, 43 passed`; the other is the E1 case, whose target is gone) | Caught |
| 1 | **M1h withdrawal window in "Your right to withdraw" 30 → 14 days** (survived round 1) | **`test_FR_0_8_01_owner_facts_appear_as_given`** (`2 failed, 43 passed`; the other is the M1h case) | **Caught (F01 fixed)** |
| 1 | M1i "a paid speech API" inserted into the owner's services | `test_FR_0_8_01_owner_facts_appear_as_given` (`2 failed, 43 passed`) | Caught |
| 1 | M1j guide padding 0.3 s → 0.5 s | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` (`1 failed, 44 passed`) | Caught |
| 1 | M1k guide peak -30 → -24 dBFS | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` (`1 failed, 44 passed`) | Caught |
| 1 | M1l invented noise source `ns-music` added to the guide and the form | `test_FR_0_8_02_choice_lists_equal_the_owner_lists` (`1 failed, 44 passed`) | Caught |
| 1 | M1m transfer path → `MyDrive/AQIS_LAB/recordings/` | `test_FR_0_8_02_owner_values_appear_as_given` (`1 failed, 44 passed`) | Caught |
| 2 Every filler has a risk level and a never-play context | M2a fil-001 "Never play when" emptied | `test_FR_0_8_04_every_filler_has_a_never_play_context` (`1 failed, 44 passed`) | Caught |
| 2 | M2b fil-012 level emptied | `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used`, `…_blueprint_examples_are_in_the_library_at_their_level` (`3 failed, 42 passed`) | Caught |
| 2 | M2c fil-020 level → `4` | `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used` (`2 failed, 43 passed`) | Caught |
| 2 | M2d fil-008 contexts → `none` | `test_FR_0_8_04_every_filler_has_a_never_play_context` (`1 failed, 44 passed`) | Caught |
| 2 | M2e fil-005 contexts → undefined `ctx-sometimes` | `test_FR_0_8_04_every_context_used_is_defined` (`1 failed, 44 passed`) | Caught |
| 2 | M2f a 21st filler row with no level and no context | `…_every_filler_has_a_never_play_context`, `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used` (`3 failed, 42 passed`) | Caught |

## Exploratory breaks (A15, at most 10)
These breaks target only what changed since `7202316`: the owner-fact check (`owner_fact_problems`, `expected_owner_fact_sections`, `expected_tick_boxes`, `_approval_fact`) and the approval lines it reads.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1 "By signing, you also agree that our technology partners may hear your recordings." added after "Tick each box that is true for you." | `CONSENT_FORM.md` "Your consent" | **Yes** (`45 passed in 0.12s`) | MAJOR (F09) |
| X2 a fifth tick box `* [ ] I agree that our technology partners may hear my recordings.` added below the four | `CONSENT_FORM.md` "Your consent" | **Yes** (`45 passed in 0.12s`) | MAJOR (F09) |
| X3 a new paragraph "Our technology partners may also hear them." after the access sentence | `CONSENT_FORM.md` "Who can see them" | No: `…_owner_facts_appear_as_given` (`1 failed, 44 passed`) | — |
| X4 approval (e) window 30 → 14 days, form unchanged | `docs/approvals/WP-0.8.md` | No: `…_owner_facts_appear_as_given` (`1 failed, 44 passed`) | — |
| X5 the question 5 and 6 lines removed (the `b4b327e` state) | `docs/approvals/WP-0.8.md` | No: `…_owner_facts_appear_as_given` and all 7 parametrised cases (`8 failed, 37 passed`) | — |
| X6 question 5 "kept offline by owner" → "scanned to Google Drive by owner" | `docs/approvals/WP-0.8.md` | No: same 8 tests (`8 failed, 37 passed`) | — |
| X7 section comparison weakened from equality to containment (`if _flat(expected) not in actual:`) | `test_aqis_recording_docs.py` `owner_fact_problems` | **Yes** (`45 passed in 0.26s`) | MINOR (F10) |
| X8 tick-box comparison removed (`if False:`) | `test_aqis_recording_docs.py` `owner_fact_problems` | No: `…[tick-box-age]`, `…[tick-box-window]` (`2 failed, 43 passed`) | — |

Round 1 breaks re-made to verify F03 (not counted above):
- E1 (wider access) gives `2 failed, 43 passed`.
- E2 (training and sale) gives `2 failed, 43 passed`.
- E3 (7-day deadline) gives `2 failed, 43 passed`.

`test_FR_0_8_01_owner_facts_appear_as_given` fails in each.

**Why X1 and X2 survive:**
- `owner_fact_problems` reads the consent block with `re.findall(r"^- \[ \] (.+)$", found.get("Your consent", ""), re.M)` (`test_aqis_recording_docs.py:179`).
- It never looks at the block's other lines. It also misses a tick box written with another list marker (`*`, `+`) or pre-ticked (`[x]`), which GitHub still renders as a tick box.
- The consent-block test (`:117`) uses the same pattern and only asks for at least three boxes with given words.
- The block also passes the word budget (450) and the sentence-length limits after either break.

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.8-F01 | CRITICAL | A6 | Fixed. The withdrawal window in its own section is now pinned. | M1h caught; A6 19 of 19 | Closed |
| WP-0.8-F02 | MAJOR | A2, A5, A14 | Fixed. The owner restored the question 5 and 6 lines on `main`, and the test reads the current approval. | `f97f492`; X4 to X6 | Closed |
| WP-0.8-F03 | MAJOR | A15 | Fixed for the four prose owner-fact sections (E1 to E3 and X3 caught). The consent block is not covered: F09. | E1 to E3, X3 above | Closed; the residual gap continues as F09 |
| WP-0.8-F04 | MAJOR | A15 | Accepted as debt. | DEBT-022; approval CONDITIONS | Accepted (WP-0.9) |
| WP-0.8-F05 | MAJOR | A15 | Accepted as debt. | DEBT-023; approval CONDITIONS | Accepted (WP-0.9) |
| WP-0.8-F06 | MINOR | A3, A14 | Accepted as debt. | DEBT-024 | Accepted (WP-0.9) |
| WP-0.8-F07 | MINOR | A3 | Accepted as debt. | DEBT-025 | Accepted (WP-0.9) |
| WP-0.8-F08 | MINOR | A11 | Fixed. The test no longer needs git history. | Depth-1 clone: `15 passed, 13 deselected` | Closed |
| WP-0.8-F09 | MAJOR | A15 | The owner-fact check does not cover the consent block beyond lines written exactly `- [ ] `. Two breaks pass every test. X1 adds a sentence to "Your consent". X2 adds a fifth tick box written `* [ ]`. Each promises that "technology partners" may hear the recordings. That contradicts the owner's access fact, question 6 (a), on the block participants tick and sign. CAP-DOC-014 now says the owner facts are in their sections "and tick boxes … with nothing changed or added". For the consent block, the check does not support that claim. This is the same class as F03, and the committed form has neither addition. | X1, X2 above; `test_aqis_recording_docs.py:179` (and `:117`); `CONSENT_FORM.md:29-41`; `REGISTRY.md` CAP-DOC-014 | **Fix now (test only).** In `owner_fact_problems`, check the whole "Your consent" section. Its non-empty lines must be exactly: the intro line, the four tick boxes built from the approval, and the `Name:`, `Signature:` and `Date:` fill-in lines. Count every task-list item, whatever its list marker or box state (`^[-*+] \[[ xX]\]`). Add X1 and X2 as cases of `OWNER_FACT_BREAKS`. Your wording review of this form is still pending, so the form is likely to be edited soon. That is when this check matters. |
| WP-0.8-F10 | MINOR | A15 | The guard test `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions` does not notice the section comparison being weakened from equality to containment (X7: `45 passed`). All 7 of its cases change text inside an existing sentence, so a containment check still reports them. None appends a whole sentence. With that weakening in place, X3 (a new paragraph in "Who can see them") would pass. Reaching this needs an approved edit to the test itself, so the risk is low. | X7 above; `OWNER_FACT_BREAKS` (`test_aqis_recording_docs.py:193-205`) | Fix with F09: add an appended-sentence case (X3) to `OWNER_FACT_BREAKS`. Otherwise the builder records it in `DEBT.md`, target WP-0.9. |
| WP-0.8-F11 | MINOR | A2, A14 | `EVIDENCE.md` is stale in two places after round 2. (1) The FR-0.8-01 section still lists 8 tests and the round 1 runs (`8 passed in 0.04s`, `14 passed, 1810 deselected`); the new test appears only at line 193. (2) The AT-0.8-01 table says the consent facts come from "approval question 6 (owner commit `61c50c7`)", while the test now reads the current approval (`f97f492`). The round 2 runs are in FIXES.md, which EVIDENCE points to. | `EVIDENCE.md:19-28`, `:47-52`, `:201` | Fix with F09 (records only). Otherwise the builder records it in `DEBT.md`, target WP-0.9. |

## Convergence (round 3 onwards)
This is round 2. The table is given for the owner's tracking.

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 3 | F01 (must-catch 1). F03 is next to it: additions beside owner values. |
| 2 | 0 open (F01 fixed) | 1 open (F09); F02 and F03 fixed; F04 and F05 accepted as debt | 2 open (F10, F11); F08 fixed; F06 and F07 accepted as debt | None. All 19 must-catch breaks are caught. F09 is an A15 survivor next to must-catch 1 (additions beside owner values), the class round 1 also put under A15. |

## For the owner
- **audit-allow lines:** none (gate: `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.8.md` on `main` (`f97f492`). It holds:
  - `STATUS: APPROVED`;
  - `ALLOW-EDIT` for `tests/aqis_lab/aqis_packs_testutil.py` and `tests/aqis_lab/test_aqis_registry_validate.py` (round 1);
  - the BLK-014 answers A to I, including the `DECISION:` lines;
  - the restored question 5 and 6 lines;
  - "Round 2 Fixes: fix WP-0.8-F01, WP-0.8-F02, WP-0.8-F03";
  - the debt line for F04 to F07.
- **Debt accepted so far:** F04 to F07, as DEBT-022 to DEBT-025, all with target WP-0.9 and status OPEN. DEBT-010, DEBT-012, DEBT-018, DEBT-020 and DEBT-021 are closed by this WP. I verified that in round 1, and that code has not changed since.
- **The consent wording is now pinned by a test.** `expected_owner_fact_sections` and `expected_tick_boxes` hold the form's connecting prose word for word, around your question 5 and 6 wording. That is the intended effect of the F01 and F03 fix. But if your wording review changes any of the four owner-fact sections or the tick boxes, the test has to change with it. That change needs your approval, as a fix condition or an `ALLOW-EDIT` line.
- **Owner-run checks still pending:**
  1. The consent form fits one page: print preview of `docs/recording/CONSENT_FORM.md` at A4 or US Letter. Expected: one page.
  2. Wording review of the five documents. This includes the 12 drafted filler texts, the 4 drafted never-play contexts and the drafted guide descriptions (DEBT-024). Expected: your OK or edits.
  3. DEBT-021 on a Colab GPU runtime: `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`. Expected: `OK: .venv ready: …` and `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …`.
- **To reach PASS:**
  1. F09 must be fixed, or accepted as debt by a CONDITIONS line naming it with a target WP plus a `DEBT.md` row. The recommended route is a round 3 fix condition "fix WP-0.8-F09, WP-0.8-F10, WP-0.8-F11": test-only changes plus EVIDENCE lines.
  2. Then a round 3 re-audit, scoped to these three findings and the new diff.
