# EVIDENCE — WP-0.8 Consent, recording guide, filler library v0 and targets

Environment: cloud VM (`cloud-vm`), Ubuntu 24.04, x86_64, 4 CPUs, Python 3.13.14 in `.venv` (`dev_bootstrap.sh`: "OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef"), uv 0.8.17. Branch `claude/beautiful-bohr-gf9yck`.

Owner inputs used:
- `docs/approvals/WP-0.8.md` on `main` (`61c50c7`):
  - BLK-013: option 1 (a), with the sources committed in `docs/specs/sources/`;
  - questions 2 to 8 as recommended: close all five debts here; `changes` required for every dataset; both locks as `--gpu` build constraints;
  - the consent scheme `ca-sNNN` / `ca-cNNN`, the consent facts (a) to (f), owner blanks for targets and retention, and deviations D1 to D3 accepted.
- `docs/specs/sources/AQIS_Test_Lab_Blueprint.md` and `docs/specs/sources/AQIS_Test_Lab_Build_Plan.md` (`61c50c7`).

## Baseline before any change
- The fast suite at `bd0fa9c` (after merging `main`) gave `1 failed, 1747 passed, 55 deselected in 338.65s`.
- The failure was `test_FR_0_0_12_asset_pins_match_repository`: `git cat-file blob 14796262…:corpus-v1.tar.gz` exited 128, because this session's clone was shallow (`git rev-parse --is-shallow-repository` → `true`).
- After `git fetch --unshallow origin`, the same test gives `1 passed, 63 deselected in 5.53s`. That is an environment fact of this checkout, not a code fault. No file was changed.

## Requirements

### FR-0.8-01 — Consent form (`docs/recording/CONSENT_FORM.md`, CAP-DOC-014)
- **Tests** (`tests/aqis_lab/test_aqis_recording_docs.py`, with the helpers in `tests/aqis_lab/aqis_docs_testutil.py`):
  - `test_FR_0_8_01_consent_form_has_every_required_section`
  - `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`
  - `test_FR_0_8_01_contact_is_an_owner_blank`
  - `test_FR_0_8_01_blank_check_detects_a_filled_in_value`
  - `test_FR_0_8_01_fits_one_page_word_budget`
  - `test_FR_0_8_01_plain_english_sentences_and_no_legal_jargon`
  - `test_FR_0_8_01_consent_block_has_signature_date_and_consent_reference`
  - `test_FR_0_8_01_owner_facts_appear_as_given`
- **Tests first:** all 8 failed with `FileNotFoundError: … docs/recording/CONSENT_FORM.md` (`8 failed in 0.34s`).
- **Where each statement comes from:**

  | Form section | Content | Source |
  | --- | --- | --- |
  | Why we are recording | "testing, benchmark measurement, and error diagnosis for voice bot pipelines" | approval, question 6 (c), word for word |
  | Why we are recording | hears when you speak, writes down what you say, reads your tone of voice | blueprint title: "Testing VAD, Transcription and Voice Emotion Models" |
  | What we record | about 80 prompts, own phone, about 30 minutes; some prompts ask for a feeling | Build Plan, "Campaign A" (80 prompts, about 30 minutes, own phones, 20 emotional variants) |
  | What we record | phone, room, background noise, accent group; a speaker code, no name | spec FR-0.8-03 (session form fields); approval question 5 (pseudonymous `ca-sNNN`) |
  | How we store your recordings | "Google Drive (AQIS_LAB), Google Colab, and Oracle Cloud VM", "Audio is never stored on GitHub" | approval, question 6 (b), word for word |
  | How we store your recordings | the signed form is kept offline by the owner | approval, question 5 ("Signed consent forms kept offline by owner") |
  | Who can see them | "Only the AQIS test lab owner (@Nasir) and authorized project raters/evaluators" | approval, question 6 (a), word for word |
  | How long we keep them | `[OWNER DECIDES: how long recordings are kept]` | FR-0.8-01: a blank for the owner |
  | Your right to withdraw | "within 30 days of recording", "deleted from active dataset pools" | approval, question 6 (e), word for word |
  | Contact | `[OWNER DECIDES: contact email/phone]` | approval, question 6 (f), word for word |
  | Your consent | tick boxes (read, 18 years or older, agree, withdrawal), name, signature, date; consent reference `ca-c___` | deviation D2 (accepted, question 8); approval question 6 (d); approval question 5 |

- **Measures:** 325 words (limit 450); 25 sentences, average 11.4 words, longest 22 (limits 20 and 30).
- **Run:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py -q -p no:cacheprovider
8 passed in 0.04s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or FR_0_8_01 or test_FR_0_0_04"
14 passed, 1810 deselected in 6.27s
```
- **Owner-run:** a print preview on one page (see "Owner-run checks").
- Status: DONE

### FR-0.8-04 — Filler library v0 (`docs/fillers/FILLER_LIBRARY_v0.md`, CAP-DOC-017)
- **Tests** (`tests/aqis_lab/test_aqis_filler_library.py`):
  - `test_FR_0_8_04_library_has_about_20_fillers`
  - `test_FR_0_8_04_risk_levels_are_the_blueprint_four_and_all_used`
  - `test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level`
  - `test_FR_0_8_04_every_filler_has_a_never_play_context`
  - `test_FR_0_8_04_ids_and_texts_unique`
  - `test_FR_0_8_04_every_context_used_is_defined`
  - `test_FR_0_8_04_blueprint_examples_are_in_the_library_at_their_level`
  - `test_FR_0_8_04_blueprint_never_play_rules_are_encoded`
  - `test_FR_0_8_04_checks_detect_missing_level_or_context`

  The risk levels, the 8 examples and the 3 never-play rules are parsed from `docs/specs/sources/AQIS_Test_Lab_Blueprint.md`, not from the library.
- **Tests first:** `9 failed in 0.47s`, because the library did not exist. The blueprint parse gave:
```text
{'0': ('Backchannel', 'Always.', ['Okay.', 'Mm-hmm.']), '1': ('Process', 'Always.', ['One moment.', 'Let me check that.']), '2': ('Empathy or warmth', 'Clear negative or positive tone, with high confidence.', ["I'm sorry to hear that.", 'Great!']), '3': ('Content judgement', 'Right dialogue act and suitable tone, with very high confidence.', ["That's a good point.", 'Good question.'])}
['Never play Level 2 Empathy (positive/cheerful) on negative/distressed callers or complaints.', 'Never play Level 3 Content judgement on direct questions, yes/no answers, or digit strings.', 'Always fall back to Level 0 or Level 1 when model confidence is low.']
```
- **Content:**
  - 20 fillers, 5 per level. The 8 blueprint examples are used word for word at their level. The other 12 texts are drafted in the style of their level, for owner review.
  - 12 contexts:
    - 8 come from the blueprint: rules 1 to 3, and the Level 2 "Allowed when" column;
    - 4 are marked "Drafted in WP-0.8 for owner review".
  - **Why there are drafted contexts:** the blueprint allows Levels 0 and 1 "Always", while FR-0.8-04 and must-catch 2 need a never-play context for every filler. The drafted contexts come from what each phrase says, for example that "Okay." after "cancel my order" can sound like a promise.
  - **"Good question." is a blueprint Level 3 example, but rule 2 forbids Level 3 on direct questions.** Its intended use is therefore an open, indirect question, and it carries the rule 2 contexts.
- **Run:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_filler_library.py -q -p no:cacheprovider
9 passed in 0.04s
```
- Status: DONE

### FR-0.8-05 — Targets options (`docs/decisions/TARGETS_OPTIONS.md`, CAP-DOC-018)
- **Tests** (`tests/aqis_lab/test_aqis_targets_options.py`):
  - `test_FR_0_8_05_four_targets_each_with_2_or_3_options`
  - `test_FR_0_8_05_every_option_has_trade_offs_and_a_citation`
  - `test_FR_0_8_05_citations_name_sections_of_the_committed_blueprint`
  - `test_FR_0_8_05_document_does_not_choose`
  - `test_FR_0_8_05_choice_check_detects_a_filled_decision`
  - `test_FR_0_8_05_decision_record_format_is_documented`
  - `test_FR_0_8_05_harm_rate_counts_recomputed`
- **Tests first:** `7 failed in 0.35s`, because the document did not exist.
- **Failures fixed in the document while writing it** (the tests were not changed):
  - "(example value)" inside a citation named a heading that does not exist;
  - quoting the consent form's retention blank counted as a fifth owner blank;
  - two "What it gives" cells said only "the blueprint's example value";
  - one count was written "At most", not "at most".

  The citation pattern was tightened before the document was written, because a citation at the end of a table cell (followed by `|`) would not have matched, and the whole-document check would have skipped it.
- **Content and sources:**
  - Each section quotes its blueprint bullet from "Quantitative Targets" word for word.
  - Options:
    - harm rate: below 1 %, 2 % (blueprint example) or 5 %;
    - practical margin: 0.25, 0.5 (blueprint example) or 1.0 points;
    - timing budget: 95 %, 90 % (blueprint value) or 80 % of turns;
    - gate escalation: 10 %, 20 % or 30 %, the three rates the blueprint evaluates.

    Values that are not the blueprint's are proposals to show the range, and the document says so.
  - The harm-rate options state the exact one-sided binomial thresholds out of the Build Plan's 500 rated filler turns (phase 4 filler pack): at most 1, 4 and 16 wrong. `test_FR_0_8_05_harm_rate_counts_recomputed` recomputes them from `math.comb`. A scratchpad check gave the same values: `0.01 max wrong 1 cdf 0.0398 next 0.1234`; `0.02 max wrong 4 cdf 0.0281 next 0.0652`; `0.05 max wrong 16 cdf 0.0343 next 0.0559`.
  - Every decision line is `**Decision:** [OWNER DECIDES: <target> option]`. The section "How the owner decides" gives the `DECISION:` line format for `docs/approvals/WP-0.8.md`, as approved in question 7 (a).
- **Run:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider
7 passed in 0.04s
```
- **Owner decisions** (BLK-014 I, `docs/approvals/WP-0.8.md` on `main`, `b4b327e`):
  - harm-rate = HR-B;
  - margin = PM-B;
  - timing-budget = TB-B;
  - gate-escalation = GE-B;
  - retention = "3 years from the date of recording, after which all voice recordings are permanently deleted."

  As approved in question 7 (a), the documents keep their owner blanks, and the decisions live only in the approval file.
- **Decision test:** `test_FR_0_8_05_owner_decisions_name_existing_options`. Every target has exactly one `DECISION:` line naming one of that target's option IDs in `TARGETS_OPTIONS.md`, and there is a retention line. The same check rejects a misnamed option (`XX-`), a missing margin line and a second timing-budget line, so it is not empty.
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider
8 passed in 0.07s
```
- Status: DONE

### FR-0.8-02 — Recording guide (`docs/recording/RECORDING_GUIDE.md`, CAP-DOC-015)
- **Owner inputs:** BLK-014 answers A to G in `docs/approvals/WP-0.8.md` (`b4b327e`, merged as `8845e01`), plus the Build Plan's "Campaign A".
- **Tests** (`tests/aqis_lab/test_aqis_recording_docs.py`):
  - `test_FR_0_8_02_guide_has_every_required_section`
  - `test_FR_0_8_02_prompt_families_total_80`
  - `test_FR_0_8_02_prompt_families_match_the_build_plan`
  - `test_FR_0_8_02_file_names_are_valid_and_unique`
  - `test_FR_0_8_02_delivered_format_is_the_working_format`
  - `test_FR_0_8_02_every_quality_check_has_a_pass_rule`
  - `test_FR_0_8_02_owner_values_appear_as_given`
  - `test_FR_0_8_02_choice_lists_equal_the_owner_lists`
  - `test_FR_0_8_02_guide_has_no_owner_blank_left`
- **Where the expected values come from** (never from the guide):
  - families and counts: parsed from the Build Plan;
  - thresholds, noise and accent lists, split, transfer path and phone use: parsed from the approval's answers A to G;
  - working format: the phase 0 overview's sentence;
  - file-name rule: the registry importer's `[a-z0-9-]+\.wav`;
  - clash check: the committed `data/registry/sources.csv`.
- **Tests first:** with the guide and session form missing, 13 tests failed with `FileNotFoundError` (`14 failed, 7 passed in 1.04s`; the 14th failure is explained under "Consent facts after the approval rewrite" below).
- **One fix to the new test:** the threshold pattern used `\b` after the unit, which cannot match "0.1%," in the approval, so the approval's 0.1 % was not extracted (`At index 2 diff: ('0.3', 's') != ('0.1', '%')`). The pattern now uses `(?![A-Za-z])`. The guide was not changed for it, and the check still requires all four thresholds of answer D in the pass rules.
- **Content:**
  - About campaign A, from the Build Plan: 22 speakers, 80 prompts, about 30 minutes, own phones, about 1,760 turns. The 11/11 split is answer A.
  - Speaker IDs `ca-s001` to `ca-s022` and consent references `ca-cNNN` (question 5).
  - The 7 families `f1` to `f7` with the Build Plan's counts.
  - Phone (G); rooms `room-quiet` and `room-everyday-noise` (A, G); the noise list (E); the accent list (F).
  - File naming `<speaker-id>-<family-id>-<NN>.wav`: all 1,760 names are valid, unique and clash with no registry clip ID.
  - Format: the original kept, converted to 16 kHz, mono, 16-bit PCM WAV (C).
  - Transfer: one `ca-sNNN.tar.gz` per speaker session to `MyDrive/AQIS_LAB/campaign_a/raw/` (B).
  - Quality checks with the thresholds of D, plus a complete-set check that every prompt has exactly one file.
  - The guide does not say whether sessions are in person or remote, because answer B does not decide it.
- **Run:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py -q -p no:cacheprovider -k FR_0_8_02
9 passed, 12 deselected in 0.14s
```
- Status: DONE

### FR-0.8-03 — Session form (`docs/recording/SESSION_FORM.md`, CAP-DOC-016)
- **Tests:**
  - `test_FR_0_8_03_session_form_has_every_field`: the six FR-0.8-03 fields plus session date (UTC) and notes (D1).
  - `test_FR_0_8_03_choices_equal_the_recording_guide_lists`: room, noise and accent choice IDs equal the guide's tables, in order.
  - `test_FR_0_8_03_speaker_id_and_consent_reference_formats_match_the_guide`
  - `test_FR_0_8_03_asks_for_no_identifying_details`: no field for a name, email, phone number, address, birth or age; the device field asks for the phone's make and model.
- **Tests first:** the 4 tests failed with `FileNotFoundError: … docs/recording/SESSION_FORM.md`.
- **Run:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py -q -p no:cacheprovider
21 passed in 0.13s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or FR_0_8_ or test_FR_0_0_04"
43 passed, 1810 deselected in 9.03s
```
- Status: DONE

### Consent facts after the approval rewrite (FR-0.8-01)
- **What happened:** the owner's rewrite of `docs/approvals/WP-0.8.md` (`b4b327e`) replaced the earlier CONDITIONS. It keeps "Questions 2 to 8: as recommended in PLAN.md", but no longer lists the consent facts of question 6:
  - (a) access;
  - (b) services;
  - (c) purpose;
  - (e) the 30-day withdrawal window.

  These had no recommendation in PLAN.md, because only the owner could give them. The owner gave them in the approval committed to `main` at `61c50c7`, and nothing in the rewrite changes them.
- **Effect:** after the merge, `test_FR_0_8_01_owner_facts_appear_as_given` failed with `AssertionError: a`, because the current file no longer holds line (a).
- **Change:** the test now reads the facts from the owner's commit itself (`git show 61c50c7:docs/approvals/WP-0.8.md`). It first checks that the commit is an ancestor of `HEAD` and that the file there starts `STATUS: APPROVED`, `WP: WP-0.8`, `APPROVED-BY: owner`. CI checks out the full history (`fetch-depth: 0` in `.github/workflows/aqis-lab-ci.yml`). The consent form was not changed.
- **For the owner:** if you want the current approval to list the facts again, re-add the six lines. The test can then read the current file again.
- **Run:** `8 passed, 13 deselected in 0.22s` (`-k FR_0_8_01`).

## Acceptance
AT-0.8-01 (the auditor checks completeness, and that no value was invented where the owner must decide) can be run only once FR-0.8-02 and FR-0.8-03 are written and the owner's `DECISION:` lines are on `main` (BLK-014). The evidence for it so far:
- the source table under FR-0.8-01;
- the content notes under FR-0.8-04 and FR-0.8-05;
- the must-catch proof below.

Fast suite at `5819521`:
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
1785 passed, 55 deselected in 310.70s (0:05:10)
```
Audit gate at `5819521`: the only findings are the parts paused by BLK-014.
```text
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.8
docs/specs/phase-0/WP-0.8-consent-fillers-targets.md:17: [F3] MAJOR: FR-0.8-02 is not in any test function name under tests/aqis_lab/ (expected FR_0_8_02)
docs/specs/phase-0/WP-0.8-consent-fillers-targets.md:18: [F3] MAJOR: FR-0.8-03 is not in any test function name under tests/aqis_lab/ (expected FR_0_8_03)
docs/specs/phase-0/WP-0.8-consent-fillers-targets.md:23: [F4] MAJOR: AT-0.8-01 does not appear in docs/progress/WP-0.8/EVIDENCE.md
3 findings: FAIL (0.6 s)
```

## Debts closed (question 2)

### DEBT-010 — registry licence must equal the dataset's licence (WP-0.4-F03)
- **Code:** `aqis_lab/registry/registry.py`, `check_records`, one added check:
  - when a row's dataset is known, its licence is in the licence table and its split is one of the dataset's splits, the licence must equal `dataset.licence_for_split(split)`;
  - otherwise there is a problem at column `licence`.

  Also changed: the module docstring (CAP-REG-001, CHANGE LOG), `docs/data/REGISTRY_FORMAT.md` (one validation bullet) and the `REGISTRY.md` row CAP-REG-001.
- **Tests:**
  - `test_FR_0_4_01_rejects_licence_that_differs_from_its_dataset`, parametrised:
    - a LibriSpeech row relabelled `CC0-1.0`;
    - a MUSAN noise row with the music subset's licence;
    - a MUSAN music row with the dataset licence instead of the subset's.

    The valid music and noise rows prove the check uses the subset's licence.
  - `test_FR_0_4_01_committed_registry_licences_equal_dataset_licences`.
- **Tests first:** before the fix, the three parametrised cases failed with `AssertionError: []` / `assert 0 == 1` (no problem reported). The committed-registry test passed.
- **After the fix:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_registry_validate.py tests/aqis_lab/test_aqis_registry_build.py -q -p no:cacheprovider -m "not slow and not network"
63 passed in 19.03s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or debt_wp08 or registry" -m "not slow and not network"
99 passed, 1708 deselected in 23.47s
$ .venv/bin/python -m aqis_lab registry validate; echo "exit $?"
/home/user/voice-bot-vad-harness/data/registry/sources.csv: OK, 6559 rows (librispeech 5559, musan 990, tts 10)
exit 0
```
- Status: DONE

### DEBT-012 — `changes` required for every dataset (WP-0.4-F05)
- **Approval:** questions 2 and 3 as recommended; BLK-014 H with `ALLOW-EDIT: tests/aqis_lab/aqis_packs_testutil.py` and `ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_validate.py` (`docs/approvals/WP-0.8.md` on `main`, `b4b327e`).
- **Code:**
  - `aqis_lab/registry/schemas/datasets.v1.json`: `"changes"` added to the common `required` list, beside `attribution`.
  - `aqis_lab/packs/licences.py`, `licences_markdown`: the "Changes made" line is `dataset['changes']`, with no default, and the module CHANGE LOG is updated.
  - `aqis_lab/registry/datasets.py`: header test list and CHANGE LOG only.
  - `docs/data/REGISTRY_FORMAT.md`: `changes` is described as required.
  - `REGISTRY.md` rows CAP-REG-002 and CAP-PACK-007.
  - `format_version` stays 1, because every committed dataset already states `changes`.
- **Approved test-data edits** (4 lines; each only adds a `changes` value, and no assertion changes):
```text
-             "attribution": f"{source} test attribution text"}
+             "attribution": f"{source} test attribution text", "changes": f"{source} test changes text"}
-                                  "attribution": "Recorded by the lab owner for AQIS lab use only."}
+                                  "attribution": "Recorded by the lab owner for AQIS lab use only.",
+                                  "changes": "WAV header rewritten in the canonical form (samples unchanged)."}
-                        "clip_prefix": "owner-", "attribution": "owner", "homepage": None},
+                        "clip_prefix": "owner-", "attribution": "owner", "homepage": None, "changes": "owner"},
-                     "speaker_prefix": "k-", "tags": ["synthetic"], "attribution": "a", "homepage": None}}
+                     "speaker_prefix": "k-", "tags": ["synthetic"], "attribution": "a", "homepage": None, "changes": "c"}}
```
- **Test:** `test_FR_0_4_07_dataset_without_changes_is_rejected`, parametrised `download` and `local`. The same entry loads with `changes`, and is refused with a `DatasetsError` naming `changes` and the dataset without it.
- **Tests first:** `Failed: DID NOT RAISE DatasetsError` for both cases (`2 failed, 13 deselected in 0.87s`).
- **Scratch measurement before approval** (BLK-014): requiring `changes` without the 4 test-data lines gave `70 failed, 160 passed, 1509 deselected, 64 errors`.
- **After the change:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_registry_validate.py tests/aqis_lab/test_aqis_packs_licences.py -q -p no:cacheprovider -m "not slow and not network"
64 passed in 24.90s
$ .venv/bin/python -m aqis_lab registry validate; echo "exit $?"
/home/user/voice-bot-vad-harness/data/registry/sources.csv: OK, 6559 rows (librispeech 5559, musan 990, tts 10)
exit 0
$ .venv/bin/python -m aqis_lab pack verify data/packs/smoke/v1; echo "exit $?"
pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10
exit 0
```
- Status: DONE

### DEBT-018 — smoke `--bundle-dir` goes through the Drive write guard (WP-0.7-F05)
- **Code:** `aqis_lab/smoke.py`, `run_smoke`:
  - the `bundle_dir` default is resolved right after the platform check;
  - then `drive.check_write_path(bundle_dir, system)` runs, and a `DriveError` becomes `SmokeInputError` (`ERROR:`, exit 2), before any preflight, run or write.

  Also changed: the module docstring (CAP-SMOKE-002, CHANGE LOG) and the `REGISTRY.md` row CAP-SMOKE-002.
- **Tests:**
  - `test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab`: a Colab view with a stand-in Drive mount; the bundle folder is `MyDrive/elsewhere/bundles`. Expected: exit 2, the message names the path and `AQIS_LAB`, the mount tree is unchanged and `--work-dir` is not created.
  - `test_NFR_0_5_02_smoke_accepts_bundle_dir_inside_aqis_lab`: the guard lets `MyDrive/AQIS_LAB/bundles` through, and the smoke stops later at the GPU preflight's own message.
- **Tests first:** before the fix, the refusal test failed because the GPU preflight stopped first:
```text
E       assert ('refusing to write' in 'task parakeet-offline cannot run on this machine: Parakeet Unified runs only on a CUDA GPU and this machine has no GP...rm found none). It is never skipped or replaced: run it on a GPU target (the Colab T4 runtime; runbook in docs/colab/)')
1 failed, 1 passed, 4 deselected in 0.46s
```
- **After the fix:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_smoke_launcher.py -q -p no:cacheprovider -m "not slow and not network"
22 passed, 12 deselected in 10.64s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent"
1 passed, 1808 deselected in 1.48s
```
- Status: DONE

### DEBT-020 — two smoke behaviours get tests (WP-0.7-F07)
- **Code:** none. `aqis_lab/smoke.py` changed only in its module docstring (CAP-SMOKE-003 and CAP-SMOKE-004 test lists, CHANGE LOG). The `REGISTRY.md` rows CAP-SMOKE-003 and CAP-SMOKE-004 also list the new tests.
- **Tests:**
  - `test_FR_0_7_07_smoke_revalidates_each_event_log_before_storing` (parametrised `first`, `middle`, `last`):
    - a real harness-vad run is copied into a bundle folder;
    - one `events.jsonl` record loses its `run_id`;
    - `_check_and_store` must raise `SmokeFailure` (exit 1) naming `events.jsonl line <n> is not valid event log v1` and `run_id`, and nothing must be stored.
  - `test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows` (parametrised over the three committed bundles):
    - `_report` regenerates the committed `PHASE0_SMOKE.md` byte for byte, once the runs and score tables are put back in the config's order (`BUNDLE.json` stores them sorted);
    - the summary lines equal values recomputed in the test from `results.jsonl` (median and maximum with `statistics`, 4 decimals; transcripts equal to batch; Parakeet processing time and GPU);
    - the count is also checked after one real-speed transcript hash is changed, because in every committed bundle all transcripts are equal.
- **Break proof** (scratch worktree `wt2` of `1ae1fee`, the new test file copied in, one exact replacement per break, `git checkout` after each):

  | Break | Change | Result of `pytest tests/aqis_lab/test_aqis_debt_wp08.py -k FR_0_7_07` |
  | --- | --- | --- |
  | none | — | `6 passed, 6 deselected in 2.21s` |
  | B1 | `_check_and_store`: `bad = []` (re-validation removed) | `3 failed, 3 passed, 6 deselected in 7.77s` (the three re-validation cases) |
  | B2 | `_stats`: `statistics.mean` instead of `median` | `3 failed, 3 passed, 6 deselected in 2.05s` (the three bundles) |
  | B3 | `_report`: `same = len(rows)` | `3 failed, 3 passed, 6 deselected in 1.99s` (the three bundles; before the changed-hash step was added, B3 gave `6 passed`) |
- **Run here:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or debt_wp08"
13 passed, 1802 deselected in 3.24s
```
- Status: DONE

### DEBT-021 — registry text and the `--gpu` build constraints (WP-0.7-F08)
- **(a)** The `REGISTRY.md` row CAP-DOCTOR-002 again ends "…; minimums documented in `docs/doctor/DOCTOR.md` equal the config". This is the clause commit `75b4e8d` dropped. Its test `test_FR_0_5_02_minimums_documented_equal_config` is listed and passes.
- **(b)** `aqis_lab/deploy/dev_bootstrap.sh`: the `--gpu` `uv pip sync` now passes `--build-constraints "$LOCK" --build-constraints "$GPU_LOCK"` (owner decision, question 4 (a): both locks). Also changed: the header (CAP-ENV-001 text and tests, CHANGE LOG) and the `REGISTRY.md` row CAP-ENV-001.
  - **Test:** `test_FR_0_7_03_bootstrap_gpu_build_constraints_include_the_gpu_lock`. It checks the command as written: the `--gpu` sync names both locks as build constraints, and the CPU-only sync names only the CPU lock.
  - **Why the test reads the command:** both locks are installed in the same `uv pip sync`, so a differing setuptools pin between them already fails the main install. The extra build constraint therefore cannot change what an install does while the two pins agree, which is what the audit meant by "equivalent today". The existing `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints` is unchanged and still passes.
  - **Tests first:**
```text
E       assert '--require-hashes --strict --build-constraints "$LOCK" --build-constraints "$GPU_LOCK" "$LOCK" "$GPU_LOCK"' in '"$UV" pip sync --python "$VENV/bin/python" --require-hashes --strict --build-constraints "$LOCK" "$LOCK" "$GPU_LOCK" \\ || fail "hash-checked install of $LOCK_REL and $GPU_LOCK_REL failed (see the uv message above)."'
1 failed, 12 deselected in 0.46s
```
  - **uv behaviour with two constraint files** (scratchpad, uv 0.8.17):
    - setup: a local source package `tinypkg` built with `setuptools`, and the wheels `setuptools-84.0.0` and `setuptools-80.9.0` in a find-links folder;
    - one file `setuptools==84.0.0`, or the same file twice: `Installing build requirement: setuptools==84.0.0`;
    - the setuptools blocks with hashes cut from `phase0.txt` and `phase0-gpu.txt` (byte-identical, `cmp`) as two `--build-constraints`: `Installing build requirement: setuptools==84.0.0`, `Installed 1 package`;
    - the CPU block plus a GPU block pinned to 80.9.0:
```text
  ├─▶ No solution found when resolving: `setuptools`
      conclude that your requirements are unsatisfiable.
```
  - **After the change:**
```text
$ bash -n aqis_lab/deploy/dev_bootstrap.sh && echo "syntax ok"
syntax ok
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_locks_gpu.py tests/aqis_lab/test_aqis_bootstrap.py -q -p no:cacheprovider -m "not slow and not network"
28 passed, 6 deselected in 3.93s
$ bash aqis_lab/deploy/dev_bootstrap.sh
OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef
```
  - **Owner-run:** `bash aqis_lab/deploy/dev_bootstrap.sh --gpu` on Colab. It is part of the existing Colab launcher flow, and its output is listed under "Owner-run checks".
- Status: DONE

## Must-catch proof
Each break was made in a scratch worktree of `5819521` (`$SCRATCHPAD/wt2`, its own checkout, with `.venv` linked in), as one exact text replacement that had to match once, then reverted with `git checkout -- docs`.

Command:
```text
pytest tests/aqis_lab/test_aqis_recording_docs.py tests/aqis_lab/test_aqis_filler_library.py tests/aqis_lab/test_aqis_targets_options.py -q
```

| Must-catch | Break | Named tests that fail | Result |
| --- | --- | --- | --- |
| 1. No value the owner must decide is filled in by Claude | M1a: the consent form's retention blank is replaced by "2 years" | `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`, `test_FR_0_8_01_blank_check_detects_a_filled_in_value` | `2 failed, 22 passed in 0.23s` |
| 1. (targets) | M1b: `**Decision:** [OWNER DECIDES: harm-rate option]` is replaced by `**Decision:** HR-B` | `test_FR_0_8_05_document_does_not_choose`, `test_FR_0_8_05_choice_check_detects_a_filled_decision` | `2 failed, 22 passed in 0.13s` |
| 2. Every filler has a risk level and at least one never-play context | M2a: fil-001's "Never play when" cell is emptied | `test_FR_0_8_04_every_filler_has_a_never_play_context` | `1 failed, 23 passed in 0.12s` |
| 2. (risk level) | M2b: fil-001's level is emptied | `test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level`, `test_FR_0_8_04_risk_levels_are_the_blueprint_four_and_all_used`, `test_FR_0_8_04_blueprint_examples_are_in_the_library_at_their_level` | `3 failed, 21 passed in 0.17s` |

Must-catch 1 also applies to the recording guide and session form (FR-0.8-02 and FR-0.8-03). They are not written yet (BLK-014), so their part of the proof follows once they are.
