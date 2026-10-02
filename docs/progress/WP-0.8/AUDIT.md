# AUDIT — WP-0.8, round 1

Auditor: wp-auditor · Date: 2026-10-02 · Commit audited: 72023169f75dce215ec4f1b587ed66baa63f501c · Previous audited commit: first audit · Protocol: version 2

## Verdict: FAIL
CRITICAL: 1 · MAJOR: 4 (fixed 0, accepted as debt 0, open 4) · MINOR: 3

The five documents are complete against FR-0.8-01 to FR-0.8-05. In my reading under AT-0.8-01, none of them invents a value where the owner must decide. Every retention, contact and target decision is still an owner blank, and the owner's `DECISION:` lines name existing options. The five debt fixes are real and well tested: all four of my code breaks there were caught. The fast and slow suites pass, CI is green on the audited commit and the gate is clean.

The pass is blocked by test protection and by one traceability gap, not by the documents' current content:
- Must-catch 1 is only partly protected (F01). The withdrawal window in "Your right to withdraw" can be changed to a value the owner never gave, such as 14 days, and every test still passes.
- The consent form's owner facts trace only to a superseded approval (F02). The approval now on `main` no longer contains them, and the builder pointed the test at the old commit instead of asking.
- Three exploratory breaks show document checks that report success wrongly (F03 to F05).

All fixes are small: test-only changes, plus one approval edit by the owner.

## Scope of this audit
First audit. The diff is `origin/main` (merge-base `b4b327e`) to `7202316`: 25 files.
- **Production code (debt work, question 2):**
  - `aqis_lab/registry/registry.py` (`check_records`);
  - `aqis_lab/registry/schemas/datasets.v1.json`;
  - `aqis_lab/packs/licences.py` (`licences_markdown`);
  - `aqis_lab/smoke.py` (`run_smoke`);
  - `aqis_lab/deploy/dev_bootstrap.sh`;
  - headers in `aqis_lab/registry/datasets.py`.
- **Documents:** the five deliverables under `docs/recording/`, `docs/fillers/` and `docs/decisions/`.
- **Tests:**
  - new: `test_aqis_recording_docs.py`, `test_aqis_filler_library.py`, `test_aqis_targets_options.py`, `test_aqis_debt_wp08.py` and the helper `aqis_docs_testutil.py`;
  - edited under `ALLOW-EDIT`: `aqis_packs_testutil.py` and `test_aqis_registry_validate.py`.
- **Records:** `REGISTRY.md`, `REGISTRY_FORMAT.md`, `DEBT.md`, `BLOCKERS.md`, `STATUS.md`, PLAN and EVIDENCE.

**How breaks were made:**
- All breaks were made in my own throwaway clone, `/tmp/wp08-audit`: a local `git clone` checked out at `7202316`, with full history and `.venv` linked.
- A probe test run inside the clone printed `AQIS /tmp/wp08-audit/aqis_lab/__init__.py /tmp/wp08-audit`, so `aqis_lab` and the tests' `ROOT` both come from the clone.
- A script applied each break as one exact text replacement that had to match once. After each run it restored the tree with `git checkout -- docs aqis_lab tests`, and `git status --porcelain` showed only `?? .venv` every time.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none". Branch `claude/beautiful-bohr-gf9yck`, not `main`. `git show origin/main:docs/approvals/WP-0.8.md` starts `STATUS: APPROVED` and equals the branch copy. `git diff origin/main HEAD -- docs/approvals docs/specs docs/process .claude CLAUDE.md` is empty: the sources and the approval came only from owner commits `61c50c7` and `b4b327e` on `main`. PLAN.md is unchanged since `957467a`, the commit the owner approved. |
| A2 Requirement coverage | PASS (see F02) | `pytest --collect-only -k "FR_0_8"` collects FR-0.8-01: 8, FR-0.8-02: 9, FR-0.8-03: 4, FR-0.8-04: 9, FR-0.8-05: 8 (38 tests). Each test is named after its ID, and every ID has an `EVIDENCE.md` section. AT-0.8-01 is a manual auditor check (A3). The debt tests collect 15 (`test_aqis_debt_wp08.py`). |
| A3 Acceptance commands | PASS (see F02, F06, F07) | `pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_8"`: `38 passed, 1818 deselected in 1.35s`. My AT-0.8-01 review, document by document, is under "AT-0.8-01 review" below. Every requirement is met. Every owner blank is untouched. Every owner value in the documents is the owner's own wording (but see F02 on which approval holds it). The debt commands: `aqis_lab registry validate` gives `OK, 6559 rows (librispeech 5559, musan 990, tts 10)`, exit 0; `aqis_lab pack verify data/packs/smoke/v1` gives `pack smoke 1.0.0: OK, 60 clips in 5 archives; …`, exit 0; `bash -n dev_bootstrap.sh` gives `syntax ok`. |
| A4 Test suites and CI | PASS | Fast suite: `1801 passed, 55 deselected in 353.18s`, exit 0. Slow suite (`-m "slow and not gpu and not colab and not oracle and not network"`): `5 passed, 1851 deselected in 133.26s`. The builder did not run it; it says so in EVIDENCE. CI on `7202316`: run 37043585668 (push) and run 37043591265 (pull_request) both have `lab` success and `harness-regression` success. In the PR run, the steps "Fast lab test suite" and "Audit gate" are both success. I could not download the log text (the results host answered `Forbidden`), so I checked the conclusions and steps through the API. The network suite (43 tests) was not run; the protocol does not require it. |
| A5 Test integrity | PASS (see F02) | Only two existing test files changed, both under the approval's `ALLOW-EDIT`. Their 4 hunks only add a `changes` value to test datasets; no assertion changed (`git diff b4b327e HEAD -- tests/aqis_lab/aqis_packs_testutil.py tests/aqis_lab/test_aqis_registry_validate.py`). The new tests have no `skip`, `xfail` or `importorskip`. Three tests prove their own checks are not empty: `…_blank_check_detects_a_filled_in_value`, `…_checks_detect_missing_level_or_context` and `…_choice_check_detects_a_filled_decision`. One new test was changed after a failure: `_approval_fact` was re-pointed from the current approval to `git show 61c50c7:…` (commit `0db1836`). That is covered in F02. |
| A6 Must-catch proof | **FAIL (F01)** | 19 breaks over the 2 behaviours: 18 caught, 1 survived (M1h). See the table below. |
| A7 Compromise scan | PASS | Gate: `aqis-audit-gate: base origin/main (merge-base b4b327edd783), head 72023169f75d … Exempted lines (# audit-allow): 0 … Findings: 0 … 0 findings: OK (0.9 s)`, exit 0. My grep of all added lines in `aqis_lab`, `tests`, `tools` and the five documents found no stub word, `pass` body, broad `except`, skip or `audit-allow`. The Markdown documents contain no "TODO", "placeholder", "TBD" or similar. The production changes are real checks with errors that name the problem (DEBT-010, -012 and -018), or exact command changes (DEBT-021). No production code checks whether it is under test. |
| A8 Scope diff | PASS | Every changed file is inside `aqis_lab/`, `tests/aqis_lab/` or `docs/{recording,fillers,decisions,progress,capabilities,data}/`: `git diff origin/main HEAD --name-only` filtered to anything else is empty. The code hunks match PLAN.md "Debt work": `check_records` (one `elif`), the schema `required` list, the "Changes made" line of `licences_markdown`, the `bundle_dir` move plus the guard in `run_smoke`, the `--gpu` sync line, and headers and CHANGE LOGs. `REGISTRY_FORMAT.md` changed two lines, as planned. No protected path changed without approval. |
| A9 Capabilities | PASS | `REGISTRY.md`: 143 rows before, 148 after, none missing. The 8 changed rows (CAP-ENV-001, CAP-REG-001, CAP-REG-002, CAP-PACK-007, CAP-DOCTOR-002, CAP-SMOKE-002/003/004) keep every old word in order and every old test (script check). The CAP-DOCTOR-002 clause is back (DEBT-021 (a)). Five rows were added (CAP-DOC-014 to 018). Module headers carry CHANGE LOG lines for each debt. Each document has an HTML-comment header naming its tests. `test_FR_0_0_08_repository_registry_is_consistent` passes in the fast suite. |
| A10 Contracts | PASS | The documents have no data contract. The committed registry validates under the new licence rule, and the smoke pack verifies under the stricter schema (A3). `test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows` regenerates the three committed `PHASE0_SMOKE.md` files byte for byte. |
| A11 Environment parity | PASS (see F08) | `.venv` is Python 3.13.14; `docs/environment/colab_probe.txt` says 3.13.15 (same major.minor). The locks are unchanged (bootstrap: `lock sha256 87a1cc34…`). No absolute path in the new files (grep for `/home/`, `/root/`, `/content/`). The owner-run checks are listed in EVIDENCE with command and expected output, including the Colab `--gpu` bootstrap for DEBT-021. |
| A12 Reproducibility and traceability | PASS | The documents are static. Their tests compute expected values from the spec, the Build Plan, the blueprint, the approval or the registry, not from the document under test. I checked each test's source of truth. The committed smoke reports are reproduced exactly by `_report` (A10). |
| A13 Errors and logging | PASS | DEBT-018: a Drive `--bundle-dir` outside `AQIS_LAB` raises `SmokeInputError` (exit 2) before any preflight or write. The test checks that the mount tree is unchanged and `--work-dir` was not created. DEBT-012: a dataset without `changes` raises `DatasetsError` naming `changes` and the dataset. DEBT-010: a problem at column `licence` names both licences, the dataset and the split. |
| A14 Documentation, licences, data | PASS (see F02, F06) | Usage is documented in each document's header comment and in `REGISTRY_FORMAT.md`. EVIDENCE has every FR, the debts, acceptance, the gate, CI, the owner-run checks and the must-catch proof. No personal data: speaker IDs are pseudonymous, signed forms stay offline, and the only name is the owner's handle `@Nasir`, written by the owner in the approval. |
| A15 Exploratory breaks | 9 made, 5 survived | Table below. E1 to E5 survive in the document tests (F03, F04, F05). E6 to E9 are breaks of the debt code; all were caught. |

## AT-0.8-01 review (manual, as the spec asks)
| Requirement | Complete? | Values the owner must decide | Content not from the owner or the sources |
| --- | --- | --- | --- |
| FR-0.8-01 consent form | Yes. Purpose, what is recorded, storage, access, retention, withdrawal and contact are in order, plus the consent block (D2). About 327 visible words. | Retention: `[OWNER DECIDES: how long recordings are kept]`, with nothing beside it (`CONSENT_FORM.md:21`). Contact: `[OWNER DECIDES: contact email/phone]`, which is the owner's own wording for 6 (f). The access, services, purpose, 18+ and 30-day withdrawal wording is the owner's, word for word, from `61c50c7` (see F02). | Only connecting prose: "To withdraw, contact us and give your consent reference", "or someone has read it to me", and an example of the purpose taken from the blueprint title. None of it is an owner decision. |
| FR-0.8-02 recording guide | Yes. The 80-prompt structure by family matches the Build Plan exactly (7 families, 15/10/10/10/10/20/5), plus phone, rooms and noise, file naming, format, transfer and quality checks. | All the BLK-014 answers A to G are present as given: thresholds 0.1 %, -30 and -1 dBFS, 0.3 s and verbatim; the noise and accent lists; the split 11/11; the `MyDrive/AQIS_LAB/campaign_a/raw/` path; 10-15 cm with no headset. | The descriptions of the owner's IDs, the room IDs, the re-record rule, and "no earbuds or external microphone" (F06). |
| FR-0.8-03 session form | Yes. All six fields plus D1 (date, notes). The choice IDs equal the guide's. There is no identifying field. | None left open. | — |
| FR-0.8-04 filler library | Yes. 20 fillers, 5 per level. Each has an ID, text, use, risk level and at least one context. The 8 blueprint examples are at their levels. Blueprint rules 1 to 3 hold in every row (I checked fil-011 to fil-020 by hand). | None. The four drafted contexts are marked "Drafted in WP-0.8 for owner review". | The 12 drafted texts are not marked as drafted in the document (F06). |
| FR-0.8-05 targets | Yes. Four targets, 3 options each, with what each gives and costs. Every option cites `Blueprint § Quantitative Targets`. The document makes no recommendation. | Four decision lines are owner blanks. The approval holds `DECISION:` HR-B, PM-B, TB-B and GE-B, all existing option IDs, and a retention line. The non-blueprint option values are labelled "values proposed here to show the range". | The harm-rate counts embed a test method the owner has not chosen (F07). |

## Must-catch proof (A6)
Command, in `/tmp/wp08-audit`: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py tests/aqis_lab/test_aqis_filler_library.py tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider -rf --tb=no`. Unbroken: `38 passed in 0.33s`.

For must-catch 1, the A6 set breaks each owner blank (filled in, or a value added beside it) and replaces each kind of owner value with one the owner did not give. Adding text beside an owner value was explored under A15.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 No owner value filled in by Claude | M1a retention blank → "2 years" | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`, `…_blank_check_detects_a_filled_in_value` (2 failed) | Caught |
| 1 | M1b retention blank → "3 years from the date of recording" (the owner's decision, which the documents must not carry) | same 2 tests | Caught |
| 1 | M1c blank kept, ", and never more than five years" added beside it | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value` | Caught |
| 1 | M1d contact blank → `aqis-lab@example.org` | `test_FR_0_8_01_contact_is_an_owner_blank` | Caught |
| 1 | M1e `**Decision:** [OWNER DECIDES: timing-budget option]` → `**Decision:** TB-B` | `test_FR_0_8_05_document_does_not_choose` | Caught |
| 1 | M1f GE-B value marked "(preferred)" | `test_FR_0_8_05_document_does_not_choose` | Caught |
| 1 | M1g owner access wording replaced by "Only the lab owner and the project team" | `test_FR_0_8_01_owner_facts_appear_as_given` | Caught |
| 1 | **M1h withdrawal window in "Your right to withdraw" changed from 30 to 14 days** | **none: `38 passed in 0.22s`** | **Survived (F01)** |
| 1 | M1i services: "a paid speech API" inserted into the owner's list | `test_FR_0_8_01_owner_facts_appear_as_given` | Caught |
| 1 | M1j guide padding 0.3 s → 0.5 s | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` | Caught |
| 1 | M1k guide peak -30 → -24 dBFS | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` | Caught |
| 1 | M1l invented noise source `ns-music` added to the guide and the form | `test_FR_0_8_02_choice_lists_equal_the_owner_lists` | Caught |
| 1 | M1m transfer path → `MyDrive/AQIS_LAB/recordings/` | `test_FR_0_8_02_owner_values_appear_as_given` | Caught |
| 2 Every filler has a risk level and a never-play context | M2a fil-001 "Never play when" emptied | `test_FR_0_8_04_every_filler_has_a_never_play_context` | Caught |
| 2 | M2b fil-012 level emptied | `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used`, `…_blueprint_examples_are_in_the_library_at_their_level` | Caught |
| 2 | M2c fil-020 level → `4` | `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used` | Caught |
| 2 | M2d fil-008 contexts → `none` (no context ID) | `test_FR_0_8_04_every_filler_has_a_never_play_context` | Caught |
| 2 | M2e fil-005 contexts → an undefined `ctx-sometimes` | `test_FR_0_8_04_every_context_used_is_defined` | Caught |
| 2 | M2f a 21st filler row with no level and no context | `…_every_filler_has_a_never_play_context`, `…_every_filler_has_id_text_use_and_risk_level`, `…_risk_levels_are_the_blueprint_four_and_all_used` | Caught |

**Why M1h survives:**
- `test_FR_0_8_01_owner_facts_appear_as_given` (`tests/aqis_lab/test_aqis_recording_docs.py:150-165`) only checks that each owner phrase appears somewhere in the whole form.
- "within 30 days of recording" appears twice: in the withdrawal section (`CONSENT_FORM.md:24`) and in the tick box (`:35`).
- So the section the participant reads can state a window the owner never gave, while the tick box keeps the phrase that satisfies the test.

## Exploratory breaks (A15, at most 10)
Made in code and documents added or changed by this WP. The commands are as in A6, plus the debt test files named in each row.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| E1 owner access phrase kept, ", and our technology partners may also hear them" appended | `CONSENT_FORM.md` "Who can see them" | Yes (`38 passed`) | MAJOR (F03) |
| E2 owner purpose kept, ", and to train and sell speech models" appended | `CONSENT_FORM.md` "Why we are recording" | Yes (`38 passed`) | MAJOR (F03) |
| E3 invented deadline "within 7 days of your request" added to the withdrawal outcome | `CONSENT_FORM.md` "Your right to withdraw" | Yes (`38 passed`) | MAJOR (F03) |
| E4 "The lab will work to HR-B." added above the untouched harm-rate decision line | `TARGETS_OPTIONS.md` | Yes (`38 passed`) | MAJOR (F04) |
| E5 fil-014 (a cheerful Level 2 filler) loses `ctx-negative-caller` and `ctx-complaint`; its use is reworded "clear happy tone" | `FILLER_LIBRARY_v0.md` | Yes (`38 passed`) | MAJOR (F05) |
| E6 DEBT-010 compares with the dataset licence instead of `licence_for_split` | `registry.py` `check_records` | No: 6 failed, including all 3 `…_rejects_licence_that_differs_from_its_dataset` and `…_committed_registry_licences_equal_dataset_licences` | — |
| E7 DEBT-018 guard checks `DEFAULT_BUNDLES`, not the `--bundle-dir` given | `smoke.py` `run_smoke` | No: `test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab` failed | — |
| E8 DEBT-021 `--gpu` sync back to the CPU lock as the only build constraint | `dev_bootstrap.sh` | No: `test_FR_0_7_03_bootstrap_gpu_build_constraints_include_the_gpu_lock` failed | — |
| E9 DEBT-012 `changes` optional again and the old default text restored | `datasets.v1.json`, `licences.py` | No: `test_FR_0_4_07_dataset_without_changes_is_rejected[download]` and `[local]` failed | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.8-F01 | CRITICAL | A6 | Must-catch 1 is only partly protected. Changing the withdrawal window in "Your right to withdraw" to a value the owner never gave (14 days instead of the owner's 30) passes every test. The owner-fact test checks each phrase against the whole form, and the same phrase also sits in the tick box. The form would then contradict itself and promise participants a window the owner did not set. The document itself is correct today; the test is incomplete. This follows the same rule as WP-0.7-F01: a must-catch behaviour only partly pinned by its test. | M1h above; `test_aqis_recording_docs.py:153-165` (`text = … read(CONSENT)`, then `phrase.lower() in text`); `CONSENT_FORM.md:24` and `:35` | **Fix now (test only).** Check each owner fact inside the section it belongs to: (a) in "Who can see them", (b) in "How we store your recordings", (c) in "Why we are recording", (e) in "Your right to withdraw" and, separately, in its tick box, and (d) in its tick box. Prove the fix with M1h. |
| WP-0.8-F02 | MAJOR | A2, A5, A14 | The consent form's owner facts trace only to a superseded approval. These are access, services, purpose, the 30-day window with "deleted from active dataset pools", and "signed forms kept offline". The owner's rewrite of `docs/approvals/WP-0.8.md` (`b4b327e`, now on `main`) dropped those lines and says only "Questions 2 to 8: as recommended in PLAN.md". PLAN question 6 has no recommended value for (a), (b) or (c). For (e) it says to give a number "or leave it as an owner blank", and it recommends different wording for what happens on withdrawal ("deleted and left out of future packs, and results already computed stay only as totals…"). Read on its own, the current approval does not support the form's wording. The builder did not raise a blocker. Instead it changed its own new test (`0db1836`) to read the facts from `git show 61c50c7:…`, and recorded this in EVIDENCE ("Consent facts after the approval rewrite"). The values are the owner's own words, so nothing was invented and must-catch 1 is not broken. But the authority for a participant-facing promise rests on a file the owner has since replaced, and rule 10 says an ambiguous approval is a stop-and-ask. | `git show 61c50c7:docs/approvals/WP-0.8.md` (Q5 and Q6 lines) vs `git show origin/main:docs/approvals/WP-0.8.md` (no Q5 or Q6 lines); PLAN.md question 6; `test_aqis_recording_docs.py:127-147` (`FACTS_COMMIT = "61c50c7"`); EVIDENCE.md lines 190-201 | **Fix now (owner action, one edit).** Re-add the Q5 and Q6 lines to the CONDITIONS of `docs/approvals/WP-0.8.md` on `main`, or add one line confirming that the Q5 and Q6 values of `61c50c7` stand. Then the builder points `_approval_fact` back at the current approval, which also closes F08. If you prefer, accept as debt (WP-0.9). |
| WP-0.8-F03 | MAJOR | A15 | The consent owner-fact check accepts invented additions next to an owner phrase, because it only tests that the phrase is present. E1 (wider access), E2 (training and selling models) and E3 (a 7-day deletion deadline) all pass every test. Each would put a promise the owner did not make on a form participants sign. The committed form has none of these (AT-0.8-01 review). | E1 to E3 above; `test_aqis_recording_docs.py:150-165` | **Fix now, together with F01** (same test). Compare each owner-fact section with the expected sentence built from the approval's wording, rather than searching for a substring. Prove the fix with E1 to E3. |
| WP-0.8-F04 | MAJOR | A15 | The targets "does not choose" check is a fixed word list (`recommend`, `preferred`, `chosen`, …) plus an exact decision line. A sentence that picks an option in other words ("The lab will work to HR-B.") passes. The committed document makes no choice, and the owner has already decided in the approval, so the risk is limited to later edits. | E4 above; `test_aqis_targets_options.py:25-26` (`CHOOSING_RE`), `:38-53` | **Accept as debt (WP-0.9).** Suggested check: option IDs (`HR-A` … `GE-C`) may appear only in the option tables' "Option" column and in the "How the owner decides" block. |
| WP-0.8-F05 | MAJOR | A15 | The blueprint rule 1 check finds "cheerful" Level 2 fillers by the word "positive" in "Intended use". A cheerful filler whose use is worded differently can lose `ctx-negative-caller` and `ctx-complaint`, so it could play to an upset caller (the blueprint's own example of harm), and the check still passes. The committed library is correct: fil-012 and fil-014 carry both contexts. | E5 above; `test_aqis_filler_library.py:123` (`if row["Level"] == "2" and "positive" in row["Intended use"]`) | **Accept as debt (WP-0.9).** Key the rule on something the library states explicitly, such as the tone a Level 2 filler is for, not on the wording of its use. |
| WP-0.8-F06 | MINOR | A3, A14 | Some drafted content is not marked for owner review, unlike the filler library's drafted contexts. In the guide and form: descriptions of the owner's IDs (`ns-fan` "Fan or air conditioner", `acc-neutral-urban` "Neutral urban English", …), the room IDs `room-quiet` and `room-everyday-noise` (the owner gave room kinds, not IDs), the rule that a failed recording is re-recorded "by the same speaker, in the same room and with the same phone" (proposed in BLK-014 D, which the owner's answer did not adopt), and "No earbuds or external microphone either". In the filler library: the 12 non-blueprint texts, which are marked only by the absence of "(blueprint example)". None of this is an owner decision the spec reserves, and the owner-run wording review covers it. But the descriptions decide how speakers and noise get labelled. | `RECORDING_GUIDE.md:41`, `:48-51`, `:57-64`, `:71-77`, `:106`; `FILLER_LIBRARY_v0.md:46-63` | Accept as debt (WP-0.9): mark the drafted descriptions and rules, or have the owner confirm them in the wording review. |
| WP-0.8-F07 | MINOR | A3 | The harm-rate options state how many wrong fillers of 500 each allows "for an exact one-sided binomial test to show, with 95 % confidence" that the rate is below target: HR-A 1, HR-B 4, HR-C 16. Neither the blueprint ("strictly below target (e.g., <2%)") nor the owner chose that method or confidence level. Read as an observed share, HR-B allows up to 9 of 500 (4 and 24 for HR-A and HR-C). The document states the method openly, and the arithmetic is right (`test_FR_0_8_05_harm_rate_counts_recomputed`). But the owner's "HR-B" may later be read as "at most 4 of 500" without that choice ever being made. | `TARGETS_OPTIONS.md:26`, `:30-32` | Accept as debt (WP-0.9): record that the HR-B decision is the rate only, and carry the decision rule (method, confidence) to the phase 4 plan as an owner question. |
| WP-0.8-F08 | MINOR | A11 | `test_FR_0_8_01_owner_facts_appear_as_given` runs `git merge-base --is-ancestor 61c50c7 HEAD` and `git show 61c50c7:…`, so it fails in a shallow clone. The risk is low: CI and `owner_verify.ipynb` clone full history, the shallow Colab launchers run only `-m colab` tests, and `test_FR_0_0_12_asset_pins_match_repository` already needs history. | `test_aqis_recording_docs.py:131-141`; `notebooks/aqis_lab/phase0_launcher.ipynb:52` (`--depth 1`); `.github/workflows/aqis-lab-ci.yml:26` (`fetch-depth: 0`) | Closes with F02's fix. Otherwise accept as debt (WP-0.9). |

## Debts closed by this WP (verified)
| Debt | Verified | Evidence |
| --- | --- | --- |
| DEBT-010 | Yes | `check_records` compares with `licence_for_split`. E6 shows the MUSAN subset cases are pinned. The committed registry validates (6,559 rows). |
| DEBT-012 | Yes | `changes` is in the common `required` list and the default text is gone. E9 is caught. The approved test edits only add `changes`. The pack still verifies. |
| DEBT-018 | Yes | The guard runs right after the platform check, before any preflight or write. E7 is caught. The "accepts inside `AQIS_LAB`" test stops later, at the GPU preflight. |
| DEBT-020 | Yes | The event-log re-validation is tested at the first, middle and last line, and nothing is stored. The summary lines are recomputed from rows, and the committed reports regenerate byte for byte (fast suite). |
| DEBT-021 | Yes, except the owner-run check | The CAP-DOCTOR-002 clause is restored. `--gpu` passes both locks, and E8 is caught. The Colab `--gpu` run is still pending (owner-run). |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 3 | F01 (must-catch 1). F03 is next to it: additions beside owner values. |

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`).
- Approvals used: `docs/approvals/WP-0.8.md` on `main` (`b4b327e`): `STATUS: APPROVED`, `ALLOW-EDIT` for `tests/aqis_lab/aqis_packs_testutil.py` and `tests/aqis_lab/test_aqis_registry_validate.py`, the BLK-014 answers A to I, and the `DECISION:` lines. The builder also relied on the superseded version at `61c50c7` for the Q5 and Q6 consent facts (F02).
- Debt accepted so far: none for WP-0.8 findings. DEBT-010, DEBT-012, DEBT-018, DEBT-020 and DEBT-021 are closed by this WP (verified above).
- Owner-run checks still pending:
  1. The consent form fits one page: print preview of `docs/recording/CONSENT_FORM.md` at A4 or US Letter. Expected: one page.
  2. Wording review of the five documents, including the 12 drafted filler texts, the 4 drafted never-play contexts and the drafted guide descriptions (F06). Expected: your OK or edits.
  3. DEBT-021 on a Colab GPU runtime: `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`. Expected: `OK: .venv ready: …` and `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …`.
- To reach PASS:
  1. Fix F01 (test only).
  2. Fix F02 (one approval edit by you, then a test re-point).
  3. For F03 to F05, either fix them or accept them as debt with a CONDITIONS line and `DEBT.md` rows.
  4. The builder records F06 to F08 in `DEBT.md`.
