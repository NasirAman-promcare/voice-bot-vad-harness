# AUDIT — WP-0.8, round 3

Auditor: wp-auditor · Date: 2026-10-03 · Commit audited: 8dc69d46428c6f8db3c05dd5a8ce0088561de79e · Previous audited commit: 24132fea55b9bc65525f45e568dd629586d2bbea · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 open (F01 was fixed in round 2) · MAJOR: 5 (fixed 3, accepted as debt 2, open 0) · MINOR: 6 (fixed 3: F08, F10, F11; accepted as debt 2: F06, F07; open 1: F12, new, does not block)

The three round 2 findings are fixed:
- **F09 (MAJOR) is fixed.** The check now reads every non-empty line of "Your consent". I re-made X1 (a sentence added to the block) and X2 (a fifth box written `* [ ]`), and both now fail `test_FR_0_8_01_owner_facts_appear_as_given`. Five more consent-block additions I tried were also caught (Y1 to Y5): a pre-ticked box, a numbered task item, a `###` part after the Date line, a promise on the Signature line, and an indented box.
- **F10 (MINOR) is fixed.** I loosened the section check from equality to containment again (X7). The new guard case `[X3-appended-sentence]` now fails.
- **F11 (MINOR) is fixed.** The FR-0.8-01 section of `EVIDENCE.md` lists both round 2 and 3 tests and the current runs. The AT-0.8-01 row cites the current approval. I re-ran both commands and got the same counts.

Other results:
- All 19 must-catch breaks are caught.
- The fast and slow suites pass, the gate reports 0 findings, and CI is green on the audited commit.
- No document or production file changed in this round.

One new MINOR finding (F12) does not block. The guard test would not notice two ways the new consent-block check could be loosened. Reaching either one needs an edit to the test itself.

## Scope of this audit
This is a re-audit under protocol version 2.
- **Round 2 findings:** each of F01 to F11, mainly the three that were open: F09, F10 and F11.
- **Items A1 to A15 on the diff `24132fe..8dc69d4`.** That diff has 7 files:
  - test code: `tests/aqis_lab/test_aqis_recording_docs.py`, in two hunks. The consent-block part of `owner_fact_problems` (`@@ -179,3 +179,20 @@`), and four new `OWNER_FACT_BREAKS` cases (`@@ -204,0 +222,15 @@`);
  - the owner's approval, `docs/approvals/WP-0.8.md`. It comes from owner commit `019d845` on `main`, merged in `dfb01a5`. That merge brought in only this file;
  - records: the `REGISTRY.md` row CAP-DOC-014, `STATUS.md`, and the WP-0.8 `AUDIT.md` (round 2 report), `EVIDENCE.md` and `FIXES.md`.
  - Nothing changed under `docs/recording/`, `docs/fillers/`, `docs/decisions/`, `aqis_lab/`, `tools/`, `requirements/`, `config/`, `.github/` or `docs/progress/DEBT.md` (`git diff --stat 24132fe HEAD -- …` is empty).
- **The full set:** the fast and slow suites, the gate, CI and the complete must-catch proof.

Code that passed rounds 1 and 2 and has not changed was not searched again. The A15 breaks only touch the new consent-block check and its guard cases.

**How breaks were made:**
- I made every break in my own throwaway clone, `/tmp/wp08-audit-r3`. It is a local `git clone` checked out at `8dc69d4`, with `.venv` linked.
- I ran a probe test inside the clone. It printed `AQIS /tmp/wp08-audit-r3/aqis_lab/__init__.py /tmp/wp08-audit-r3 /tmp/wp08-audit-r3/docs/approvals/WP-0.8.md`. So the package, the tests' `ROOT` and the approval the tests read all came from the clone.
- A script applied each break as exact text replacements. Each replacement had to match exactly once.
- The script then ran `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py tests/aqis_lab/test_aqis_filler_library.py tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider -rf --tb=no`.
- After each run it restored the tree with `git checkout -- docs tests aqis_lab`. It then checked that `git status --porcelain` showed only `?? .venv`.
- The unbroken baseline was `49 passed in 0.20s`. The working repository was clean before and after the audit.

## Round 2 findings: status
| Finding | Status | Evidence |
| --- | --- | --- |
| F01 (CRITICAL) withdrawal window in its own section not pinned | Fixed (round 2); still holds | M1h: `2 failed, 47 passed` (`…_owner_facts_appear_as_given`, and `[M1h-window-14-days]`, whose target the break removes) |
| F02 (MAJOR) owner facts read from a superseded approval | Fixed (round 2); still holds | `_approval_fact` (`test_aqis_recording_docs.py:128-132`) reads the current approval. The branch copy equals `origin/main` (`git diff origin/main HEAD -- docs/approvals/WP-0.8.md` is empty). |
| F03 (MAJOR) invented additions beside owner wording | Fixed (round 2); still holds | The guard cases E1 to E3 pass on the committed form, and each would fail if the check stopped reporting them. M1g and M1i are caught (A6 table). |
| F04, F05 (MAJOR) | Accepted as debt | The CONDITIONS line in the approval on `main`: "Debt accepted: WP-0.8-F04 (target WP-0.9), WP-0.8-F05 (target WP-0.9), …". `DEBT.md` rows DEBT-022 and DEBT-023: target WP-0.9, OPEN. |
| F06, F07 (MINOR) | Accepted as debt | Same line. DEBT-024 and DEBT-025: target WP-0.9, OPEN. |
| F08 (MINOR) | Fixed (round 2) | The test still runs no git command (no `subprocess` in the file). |
| **F09 (MAJOR)** consent block checked only on `- [ ] ` lines | **Fixed** | `owner_fact_problems` (`:179-198`) now builds the list of all non-empty lines of "Your consent". Each line is classed as box (any of `-`, `*`, `+` and any box state), field (`Name`, `Signature`, `Date` with only underscores) or text. The list must equal the intro line, the 4 unticked boxes from the approval and the 3 fields, in order. Re-made X1 gives `1 failed, 48 passed`, and re-made X2 (`* [ ]`) gives `1 failed, 48 passed`. Both failures are `test_FR_0_8_01_owner_facts_appear_as_given`. **Tests first, verified:** I put the round 2 three-line check back into the round 3 file. The new cases then give `3 failed, 9 passed, 20 deselected` (`[X1-consent-block-sentence]`, `[X2-extra-tick-box-plus-checked]`, `[X2-extra-tick-box-star]`), as `FIXES.md` says. |
| **F10 (MINOR)** guard test did not notice equality loosened to containment | **Fixed** | X7 re-made (`if _flat(expected) not in actual:`) gives `1 failed, 48 passed`: `[X3-appended-sentence]`. X8 re-made in its round 3 form (whole consent-block comparison removed, `if False:`) gives `5 failed, 44 passed`: `[X1-…]`, both `[X2-…]`, `[tick-box-age]`, `[tick-box-window]`. |
| **F11 (MINOR)** stale lines in EVIDENCE | **Fixed** | `EVIDENCE.md:28-29` lists both tests, with the guard's 11 cases. `:55-61` gives the round 3 runs. `:211` cites the current approval (`f97f492`) in place of `61c50c7`. I re-ran both commands: `49 passed in 0.11s` and `55 passed, 1812 deselected in 4.54s`, the same counts as EVIDENCE. |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | The spec says "Depends on: none". The branch is `claude/beautiful-bohr-gf9yck`, not `main`. `git show origin/main:docs/approvals/WP-0.8.md` starts `STATUS: APPROVED` and holds "Round 3 Fixes: fix WP-0.8-F09, WP-0.8-F10, WP-0.8-F11". Owner commit `019d845` (NasirAman-promcare) is the only change to the approval in the diff. The branch copy equals `main`'s. `git log 24132fe..HEAD -- docs/specs docs/process .claude CLAUDE.md requirements docs/progress/WP-0.8/PLAN.md` is empty. |
| A2 Requirement coverage | PASS | `pytest --collect-only -k FR_0_8` collects 49 tests: FR-0.8-01 19 (the 8 tests plus 11 guard cases), FR-0.8-02 9, FR-0.8-03 4, FR-0.8-04 9, FR-0.8-05 8. Every ID has an `EVIDENCE.md` section, and the FR-0.8-01 list now names both new tests (F11). |
| A3 Acceptance commands | PASS | `pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k FR_0_8` gives `49 passed, 1818 deselected in 0.84s`. AT-0.8-01: the five documents are unchanged since rounds 1 and 2, so the earlier review stands. I re-read the consent block (`CONSENT_FORM.md:29-41`). It holds the intro line, the four unticked boxes with the approval's (d) age and (e) window, and the Name, Signature and Date lines. Retention and contact are still owner blanks (`:21`, `:27`). |
| A4 Test suites and CI | PASS | Fast suite: `1812 passed, 55 deselected in 219.07s (0:03:39)`, exit 0. That is round 2's 1808 plus the 4 new guard cases. Slow suite (`-m "slow and not gpu and not colab and not oracle and not network"`): `5 passed, 1862 deselected in 83.81s (0:01:23)`, exit 0. CI on `8dc69d4`, workflow `aqis-lab-ci`: run 37101013814 (push) and run 37101016208 (pull_request) both concluded success. In each run, the `lab` and `harness-regression` jobs are success. In the PR `lab` job (111140391153), the steps "Fast lab test suite", "Work package ID from pull request title" and "Audit gate (pull request base with --wp …)" are success. The log text could not be downloaded: `productionresultssa17.blob.core.windows.net` returned `Forbidden`. So I checked job and step conclusions through the REST API. |
| A5 Test integrity | PASS | The only test file changed is `test_aqis_recording_docs.py`. It is new in this WP and changed under the round 3 fix condition. The new consent-block check is strictly stronger than round 2's. Round 2 compared only the `- [ ] ` lines. The new check compares every non-empty line, and it still requires the same 4 unticked boxes. All 7 earlier guard cases are byte-identical, and the hunk at `@@ -204,0 +222,15 @@` only adds lines. There is no `skip`, `xfail` or `audit-allow`. Each new case asserts that its target text occurs once before it applies the break. |
| A6 Must-catch proof | PASS | I made 19 breaks over the 2 behaviours, the same set as rounds 1 and 2: **19 caught, 0 survived** (table below). |
| A7 Compromise scan | PASS | Gate: `aqis-audit-gate: base origin/main (merge-base 019d84584158), head 8dc69d46428c, approvals origin/main 019d84584158, wp WP-0.8 … Exempted lines (# audit-allow): 0 … Findings: 0 … 0 findings: OK (0.4 s)`, exit 0. I grepped the added lines of `git diff -U0 24132fe HEAD -- tests/ aqis_lab/ tools/` for stub words, `skip`, `xfail`, `except`, `NotImplemented`, `audit-allow` and absolute paths: no match. No production code changed. |
| A8 Scope diff | PASS | The changed files match the round 3 change budget in `FIXES.md`. In the test file, only `owner_fact_problems` (consent-block part) and `OWNER_FACT_BREAKS` changed. `REGISTRY.md` changes one row, CAP-DOC-014. The records are WP-0.8's own. The approval change is the owner's own commit. Gate: 0 findings, so no protected path changed without approval. |
| A9 Capabilities | PASS | `REGISTRY.md` has 148 rows at `24132fe` and at `HEAD`, with the same IDs in the same order (identical md5 of the ID column). CAP-DOC-014 keeps every test. Its text now describes the whole-block check, and that matches the code. `test_FR_0_0_08_repository_registry_is_consistent` and the `test_FR_0_0_04` tests pass (`6 passed`). |
| A10 Contracts | N/A | No data contract applies to the documents, and no code with a contract changed. |
| A11 Environment parity | PASS | `.venv` is Python 3.13.14, and `docs/environment/colab_probe.txt` says 3.13.15: the same major.minor. No lock changed. The added lines contain no absolute path. The owner-run checks are listed in `EVIDENCE.md` "Owner-run checks", each with a command and expected output. |
| A12 Reproducibility and traceability | PASS | The expected tick boxes still come from the approval at run time (`expected_tick_boxes`, unchanged). The check is a pure function of the form and the approval. Runs are repeatable: same counts in my repository, my clone and the builder's records. |
| A13 Errors and logging | PASS | The check never passes quietly. If "Your consent" is missing, `found.get(…, "")` gives an empty list, which differs from the expected list and is reported. A duplicate heading raises in `sections` (`aqis_docs_testutil.py:48-49`). Every reported problem names the actual and the expected lines. |
| A14 Documentation, licences, data | PASS | `FIXES.md` round 3 records the findings, root cause, change budget, baseline, tests-first failures (verified above), fix, break proof, suite, gate and CI. EVIDENCE is refreshed (F11). No personal data was added. |
| A15 Exploratory breaks | 9 made, 2 survived | Table below. Y1 to Y5 (form) and Z2 and Z4 (check) are caught. Z1 and Z3 survive: F12, MINOR. Re-made breaks used to verify F09 and F10 (X1, X2, X3, X7, X8) are not counted here. |

## Must-catch proof (A6)
All 19 breaks from rounds 1 and 2, re-made at `8dc69d4`. Unbroken: `49 passed in 0.20s`.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 No owner value filled in by Claude | M1a retention blank → "2 years" | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`, `…_blank_check_detects_a_filled_in_value` (`2 failed, 47 passed`) | Caught |
| 1 | M1b retention blank → "3 years from the date of recording" | same 2 tests (`2 failed, 47 passed`) | Caught |
| 1 | M1c blank kept, ", and never more than five years" added beside it | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value` (`1 failed, 48 passed`) | Caught |
| 1 | M1d contact blank → `aqis-lab@example.org` | `test_FR_0_8_01_contact_is_an_owner_blank` (`1 failed, 48 passed`) | Caught |
| 1 | M1e `**Decision:** [OWNER DECIDES: timing-budget option]` → `**Decision:** TB-B` | `test_FR_0_8_05_document_does_not_choose` (`1 failed, 48 passed`) | Caught |
| 1 | M1f GE-B value marked "(preferred)" | `test_FR_0_8_05_document_does_not_choose` (`1 failed, 48 passed`) | Caught |
| 1 | M1g owner access wording → "Only the lab owner and the project team" | `test_FR_0_8_01_owner_facts_appear_as_given` (`3 failed, 46 passed`; the other two are the guard cases `[E1-wider-access]` and `[X3-appended-sentence]`, whose target text is gone) | Caught |
| 1 | M1h withdrawal window in "Your right to withdraw" 30 → 14 days | `test_FR_0_8_01_owner_facts_appear_as_given` (`2 failed, 47 passed`; the other is `[M1h-window-14-days]`) | Caught |
| 1 | M1i "a paid speech API" inserted into the owner's services | `test_FR_0_8_01_owner_facts_appear_as_given` (`2 failed, 47 passed`; the other is `[services-added]`) | Caught |
| 1 | M1j guide padding 0.3 s → 0.5 s | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` (`1 failed, 48 passed`) | Caught |
| 1 | M1k guide peak -30 → -24 dBFS | `test_FR_0_8_02_every_quality_check_has_a_pass_rule` (`1 failed, 48 passed`) | Caught |
| 1 | M1l invented noise source `ns-music` added to the guide and the session form | `test_FR_0_8_02_choice_lists_equal_the_owner_lists` (`1 failed, 48 passed`) | Caught |
| 1 | M1m transfer path → `MyDrive/AQIS_LAB/recordings/` | `test_FR_0_8_02_owner_values_appear_as_given` (`1 failed, 48 passed`) | Caught |
| 2 Every filler has a risk level and a never-play context | M2a fil-001 "Never play when" emptied | `test_FR_0_8_04_every_filler_has_a_never_play_context` (`1 failed, 48 passed`) | Caught |
| 2 | M2b fil-012 level emptied | `…_risk_levels_are_the_blueprint_four_and_all_used`, `…_every_filler_has_id_text_use_and_risk_level`, `…_blueprint_examples_are_in_the_library_at_their_level` (`3 failed, 46 passed`) | Caught |
| 2 | M2c fil-020 level → `4` | `…_risk_levels_are_the_blueprint_four_and_all_used`, `…_every_filler_has_id_text_use_and_risk_level` (`2 failed, 47 passed`) | Caught |
| 2 | M2d fil-008 contexts → `none` | `test_FR_0_8_04_every_filler_has_a_never_play_context` (`1 failed, 48 passed`) | Caught |
| 2 | M2e fil-005 contexts → undefined `ctx-sometimes` | `test_FR_0_8_04_every_context_used_is_defined` (`1 failed, 48 passed`) | Caught |
| 2 | M2f a 21st filler row `fil-021` with no level and no context | `…_risk_levels_are_the_blueprint_four_and_all_used`, `…_every_filler_has_id_text_use_and_risk_level`, `…_every_filler_has_a_never_play_context` (`3 failed, 46 passed`) | Caught |

## Exploratory breaks (A15, at most 10)
These target only code changed since `24132fe`: the consent-block part of `owner_fact_problems` and the new guard cases. Y breaks change the form; Z breaks loosen the check.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| Y1 an existing box pre-ticked: `- [x] I agree to be recorded for the purpose above.` | `CONSENT_FORM.md` "Your consent" | No: `…_owner_facts_appear_as_given` and the unchanged `…_consent_block_has_signature_date_and_consent_reference` (`3 failed, 46 passed`; the third is `[X2-extra-tick-box-plus-checked]`, whose target is gone) | — |
| Y2 a numbered task item `1. [ ] I agree that our technology partners may hear my recordings.` after the fourth box | `CONSENT_FORM.md` "Your consent" | No: `…_owner_facts_appear_as_given` (`1 failed, 48 passed`) | — |
| Y3 a `### Also` part with a partner-access sentence after the Date line | `CONSENT_FORM.md` "Your consent" | No: `…_owner_facts_appear_as_given` (`1 failed, 48 passed`) | — |
| Y4 a partner-access promise appended to the Signature fill-in line | `CONSENT_FORM.md` "Your consent" | No: `…_owner_facts_appear_as_given` (`1 failed, 48 passed`) | — |
| Y5 an indented, nested partner-access box under the age box | `CONSENT_FORM.md` "Your consent" | No: `…_owner_facts_appear_as_given` (`1 failed, 48 passed`) | — |
| Z1 the check ignores box state (`actual.append(("box", " ", …))`) | `test_aqis_recording_docs.py:192` | **Yes** (`49 passed in 0.15s`) | MINOR (F12) |
| Z2 the check skips text lines (`else: continue`) | `test_aqis_recording_docs.py:195-196` | No: `…_owner_facts_appear_as_given` fails on the unbroken form, because the expected intro line is missing (`1 failed, 48 passed`) | — |
| Z3 the fill-in match loosened from `re.fullmatch` to `re.match` | `test_aqis_recording_docs.py:190` | **Yes** (`49 passed in 0.17s`) | MINOR (F12) |
| Z4 ordered equality loosened to containment (`if not all(e in actual for e in expected):`) | `test_aqis_recording_docs.py:197` | No: `[X1-consent-block-sentence]`, `[X2-extra-tick-box-plus-checked]`, `[X2-extra-tick-box-star]` (`3 failed, 46 passed`) | — |

**What the survivors allow.** I ran each survivor together with a form change, to see what it would let through:
- **Z3 with Y4** (a promise on the Signature line) gives `49 passed in 0.16s`. Nothing reports it.
- **Z1 with a pre-ticked withdrawal box** gives `2 failed, 47 passed`. Only `[X2-extra-tick-box-star]` and `[tick-box-window]` fail, and only because their target line `- [ ] I understand …` is gone. `test_FR_0_8_01_owner_facts_appear_as_given` passes.
- Without Z1, the same pre-ticked box is caught (`3 failed`, including `…_owner_facts_appear_as_given`).

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.8-F01 | CRITICAL | A6 | Fixed in round 2; still holds. | M1h caught; A6 19 of 19 | Closed |
| WP-0.8-F02 | MAJOR | A2, A5, A14 | Fixed in round 2; still holds. | `_approval_fact`; approval equals `main` | Closed |
| WP-0.8-F03 | MAJOR | A15 | Fixed in round 2 for the four prose sections. The consent-block remainder was F09, now fixed. | E1 to E3 guard cases; M1g, M1i | Closed |
| WP-0.8-F04 | MAJOR | A15 | Accepted as debt. | DEBT-022; approval CONDITIONS | Accepted (WP-0.9) |
| WP-0.8-F05 | MAJOR | A15 | Accepted as debt. | DEBT-023; approval CONDITIONS | Accepted (WP-0.9) |
| WP-0.8-F06 | MINOR | A3, A14 | Accepted as debt. | DEBT-024 | Accepted (WP-0.9) |
| WP-0.8-F07 | MINOR | A3 | Accepted as debt. | DEBT-025 | Accepted (WP-0.9) |
| WP-0.8-F08 | MINOR | A11 | Fixed in round 2. | No git call in the test | Closed |
| WP-0.8-F09 | MAJOR | A15 | **Fixed.** The whole "Your consent" block is compared line by line with the approval-built list. | X1, X2 re-made and caught; Y1 to Y5 caught; tests-first `3 failed, 9 passed` verified | Closed |
| WP-0.8-F10 | MINOR | A15 | **Fixed.** The guard now catches equality loosened to containment. | X7 → `[X3-appended-sentence]` fails | Closed |
| WP-0.8-F11 | MINOR | A2, A14 | **Fixed.** The EVIDENCE FR-0.8-01 test list, the runs and the AT-0.8-01 source are current. | `EVIDENCE.md:28-29`, `:55-61`, `:211`; counts re-run | Closed |
| WP-0.8-F12 | MINOR | A15 | **New.** The guard test `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions` does not notice two ways the new consent-block check could be loosened. (1) Z1: the check ignores box state. None of its 11 cases pre-ticks an existing box; the only `[x]` case adds a fifth box, which the count still catches. (2) Z3: the fill-in lines are matched by prefix. No case adds text to a Name, Signature or Date line. With Z3, a promise on the Signature line (Y4) passes every test. Today's check catches both form changes (Y1, Y4). Reaching either gap needs an edit to the test itself, which needs owner approval. So the risk is low, the same class as F10. | Z1, Z3 and the survivor runs above; `OWNER_FACT_BREAKS` (`test_aqis_recording_docs.py:210-237`) | **Accept as debt, target WP-0.9.** The builder records a `DEBT.md` row. Fix whenever this test is next edited with approval: add two guard cases, an existing box pre-ticked (Y1) and text after a fill-in line (Y4). |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 3 | F01 (must-catch 1). F03 is next to it: additions beside owner values. |
| 2 | 0 open (F01 fixed) | 1 open (F09); F02 and F03 fixed; F04 and F05 accepted as debt | 2 open (F10, F11); F08 fixed; F06 and F07 accepted as debt | None |
| 3 | 0 | 0 open: F09 fixed; F04 and F05 accepted as debt | 1 open (F12, new, guard-test only); F10 and F11 fixed; F06 and F07 accepted as debt | None. All 19 must-catch breaks are caught, and F12 is outside the must-catch list. |

Open findings have fallen each round: 8, then 3, then 1 MINOR that does not block. No open finding is inside the must-catch list, so the protocol's convergence rule recommends PASS with debt. That matches this verdict.

## For the owner
- **audit-allow lines:** none (gate: `Exempted lines (# audit-allow): 0`).
- **Approvals used:** `docs/approvals/WP-0.8.md` on `main` (`019d845`). It holds:
  - `STATUS: APPROVED`;
  - `ALLOW-EDIT` for `tests/aqis_lab/aqis_packs_testutil.py` and `tests/aqis_lab/test_aqis_registry_validate.py`;
  - the BLK-014 answers A to I, with the `DECISION:` lines;
  - the question 5 and 6 lines;
  - "Round 2: fix WP-0.8-F01, WP-0.8-F02, WP-0.8-F03";
  - the debt line for F04 to F07;
  - "Round 3 Fixes: fix WP-0.8-F09, WP-0.8-F10, WP-0.8-F11".
- **Debt accepted so far:** F04 to F07, as DEBT-022 to DEBT-025, all with target WP-0.9 and status OPEN. F12 (MINOR) is recommended as debt with target WP-0.9. A `DEBT.md` row only counts as accepted once your approval names it. It does not block this PASS.
- **What the consent checks cover.** This scope note is from reading the code. It is not a finding.
  - The owner-fact test compares four sections and the "Your consent" section with text built from your approval: "Why we are recording", "How we store your recordings", "Who can see them" and "Your right to withdraw".
  - It does not compare other text on the form with your approval. That covers the lines above the first `##` section, "What we record", and anything under a new top-level `#` heading, because a `##` section ends at a `#` heading (`aqis_docs_testutil.py:39-55`).
  - No round has claimed otherwise, and I did not probe those places, so this re-audit stayed inside its scope.
  - Your wording review (check 2 below) covers them.
- **The consent wording is pinned by the test.** The connecting prose of the four owner-fact sections and the whole consent block is held word for word in `expected_owner_fact_sections`, `expected_tick_boxes` and the consent-block list. That includes "Tick each box that is true for you." and the Name, Signature and Date lines. If your wording review changes any of them, the test must change with it, and that needs your approval as a fix condition or an `ALLOW-EDIT` line.
- **Owner-run checks still pending:**
  1. The consent form fits on one page. Open the print preview of `docs/recording/CONSENT_FORM.md` at A4 or US Letter. Expected: one page.
  2. Review the wording of the five documents, including the 12 drafted filler texts, the 4 drafted never-play contexts and the drafted guide descriptions (DEBT-024). Expected: your OK, or edits.
  3. DEBT-021 on a Colab GPU runtime: run `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`. Expected: `OK: .venv ready: …` and `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …`.
- **Next step:** review PR #8 and merge it. After the merge, set WP-0.8 to `MERGED` in `STATUS.md`.
