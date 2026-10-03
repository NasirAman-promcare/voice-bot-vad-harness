# PLAN — WP-0.8 Consent, recording guide, filler library v0 and targets

Spec: `docs/specs/phase-0/WP-0.8-consent-fillers-targets.md`  ·  Planned by session: https://claude.ai/code/session_01L48B7DHkHhYAqxs9WH35hb  ·  Date: 2026-10-02
Branch: `claude/beautiful-bohr-gf9yck`  ·  Base: `origin/main` at `edac3e9`  ·  Depends on: none

## Summary
When this WP is done, five people-facing documents are ready for phase 1:
- `docs/recording/CONSENT_FORM.md`: a one-page, plain-English consent form. The retention period, and anything else only you can set, stays as a marked owner blank.
- `docs/recording/RECORDING_GUIDE.md`: the campaign A guide, matching the Build Plan. It covers the 80-prompt structure by family, devices and rooms, file naming, format, transfer and quality checks.
- `docs/recording/SESSION_FORM.md`: the form filled in at each recording session.
- `docs/fillers/FILLER_LIBRARY_v0.md`: about 20 fillers across the four risk levels. Each has an ID, text, intended use and the contexts where it must never play.
- `docs/decisions/TARGETS_OPTIONS.md`: 2 or 3 options with trade-offs for each of four targets, each option citing the blueprint. The document does not choose; you decide in the approval file.

Tests read each document and check every requirement, including both must-catch behaviours. If you agree (question 2), this WP also closes the five accepted debts that target WP-0.8: DEBT-010, DEBT-012, DEBT-018, DEBT-020 and DEBT-021.

**One blocker:** the blueprint and Build Plan are not in the repository, and this spec takes most of its content from them (BLK-013, question 1).

## What I found in the repository (read-only inspection)
Nothing in the repository was changed. The only commands that wrote anything were `dev_bootstrap.sh` (it builds `.venv`, which git ignores) and short read-only scripts in the session scratchpad.

1. **Spec sources are missing, and this spec depends on them.**
   - "Read first" names the blueprint sections "Test data strategy" and "Voice emotion and the filler selector", and the Build Plan sections "Dataset architecture" and "Phase 1".
   - Neither document is in the repository. `find` and `grep -ri` for "blueprint", "build plan", "80-prompt", "risk level", "harm" and "escalation" match only the specs and earlier plans.
   - WP-0.2 to WP-0.7 met the same gap and relied on your instruction that the specs are complete on their own. WP-0.8 is different, because its requirements say:
     - "matching the Build Plan" (FR-0.8-02);
     - "the four risk levels" without naming them (FR-0.8-04);
     - "citing the blueprint" (FR-0.8-05).
   - So I cannot write the content of FR-0.8-02, FR-0.8-04 or FR-0.8-05 without inventing it. FR-0.8-01 and FR-0.8-03 also need Build Plan facts: where recordings are stored, and the device, room, noise-source and accent-group categories. I raised **BLK-013** (question 1).
2. **Five accepted debts target this documents-only WP.**
   - `docs/progress/DEBT.md` has DEBT-010, DEBT-012 (from `docs/approvals/WP-0.4.md`), DEBT-018, DEBT-020 and DEBT-021 (from `docs/approvals/WP-0.7.md`), all OPEN with target WP-0.8.
   - All five are code or test fixes, but the spec says WP-0.8 "Runs on: documents only".
   - WP-0.7 closed the debts that targeted it, so there is precedent. Still, closing these here puts code into a documents WP (question 2).
3. **Consent references must be files in the repository.**
   - `_consent_problem` in `aqis_lab/registry/registry.py` accepts an owner or campaign consent reference only if it resolves, inside the repository, to a non-empty file.
   - `_owner` in `aqis_lab/registry/importers.py` needs a `consent_file` beside the recordings.
   - The WP-0.4 approval keeps these code paths "for the Phase 1 campaign recordings".
   - A signed consent form carries a name and a signature, and the overview says never to commit real personal data. So the signed form cannot be the file the registry points to (question 5).
4. **Rules that campaign recordings must already meet.** The `owner` importer:
   - accepts in a folder only files named `[a-z0-9-]+\.wav`, plus `transcripts.csv` and the consent file;
   - sets `clip_id` to the dataset's `clip_prefix` plus the file stem;
   - gives every row of a folder one `speaker_id`;
   - rejects any WAV not already in the working format, 16 kHz mono 16-bit PCM (`require_working_format`).

   The guide's file naming and delivered format must meet these rules. If the Build Plan says otherwise, I report the conflict and do not adapt either side quietly (risk 1).
5. **The gate needs tests even for documents.**
   - Check (f) needs each FR ID in a collected test name under `tests/aqis_lab/`.
   - Documents already have registry rows with tests (`CAP-DOC-001` to `CAP-DOC-013`), so the next free ID is `CAP-DOC-014`.
   - The compromise scan reads only code files. `.md` files are not scanned.
6. **Where the files go.**
   - `docs/recording/`, `docs/fillers/` and `docs/decisions/` do not exist yet, and none of them is a protected path.
   - `tests/aqis_lab/` is LAB-OWNED, so new test files there need no approval.
7. **Facts behind the debt plan** (checked in `.venv` and the scratchpad):
   - **DEBT-010.** Every row of the committed registry (6,559 rows) has the licence that `licence_for_split` gives its dataset and split, with 0 mismatches. So the new check rejects nothing that is committed today.
   - **DEBT-012.** All four datasets in `data/registry/datasets.yaml` already set `changes`.
   - **DEBT-018.** The Drive test helper `drive_view` builds a Colab runtime. The smoke's task preflight on Colab stops without a GPU, so the Drive check must come before the preflight to be testable, and so that nothing runs or is written first.
   - **DEBT-020.**
     - `smoke._report` regenerates the committed cloud and Oracle reports byte for byte once the runs are put back in the target's task order from `config/aqis_lab/phase0_smoke.yaml`.
     - The Colab report also needs its score tables put back in `scored_tasks` order.
     - The cause is that `BUNDLE.json` is written with sorted keys.
     - Recomputed independently, the medians and maxima match the printed summary lines, for example cloud first-partial latency: median 565.286285 → "565.2863", maximum 728.311356 → "728.3114".
   - **DEBT-021.**
     - The `--gpu` sync passes `--build-constraints "$LOCK"` (the CPU lock).
     - The existing test `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints` requires every sync line to contain `--require-hashes --strict --build-constraints "$LOCK"`, so replacing the CPU lock there would break an existing test.
     - `uv 0.8.17 pip sync --help`: "-b, --build-constraints … using the given requirements files".
     - Both locks pin `setuptools==84.0.0`.
     - Commit `75b4e8d` dropped the clause from the `CAP-DOCTOR-002` registry row.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.8-01 | Consent form under "Consent form" below: fixed headings for purpose, what is recorded, how it is stored, who can access it, how long it is kept, right to withdraw and contact, then a consent block (deviation D2). Plain English and one page are checked by measurable rules. Retention is the owner blank `[OWNER DECIDES: how long recordings are kept]`. Facts only you can give come from question 6, copied word for word from the approval | `docs/recording/CONSENT_FORM.md`; `tests/aqis_lab/test_aqis_recording_docs.py`; `tests/aqis_lab/aqis_docs_testutil.py` | `docs/capabilities/REGISTRY.md`: row `CAP-DOC-014` appended | `test_FR_0_8_01_consent_form_has_every_required_section`, `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value`, `test_FR_0_8_01_contact_is_an_owner_blank` (if question 6 (f) is (a)), `test_FR_0_8_01_fits_one_page_word_budget`, `test_FR_0_8_01_plain_english_sentences_and_no_legal_jargon`, `test_FR_0_8_01_consent_block_has_signature_date_and_consent_reference`, `test_FR_0_8_01_blank_check_detects_a_filled_in_value` | AT-0.8-01 |
| FR-0.8-02 | Recording guide under "Recording guide" below, with every fact taken from the Build Plan (BLK-013) and checked against the importer rules (finding 4) | `docs/recording/RECORDING_GUIDE.md` | `REGISTRY.md`: row `CAP-DOC-015` appended | `test_FR_0_8_02_guide_has_every_required_section`, `test_FR_0_8_02_prompt_families_total_80`, `test_FR_0_8_02_prompt_families_match_the_build_plan`, `test_FR_0_8_02_file_names_are_valid_and_unique`, `test_FR_0_8_02_delivered_format_is_the_working_format`, `test_FR_0_8_02_every_quality_check_has_a_pass_rule` | AT-0.8-01 |
| FR-0.8-03 | Session form under "Session form" below: speaker ID, device, room, noise source, accent group and consent reference (plus deviation D1). The choice lists equal the guide's lists, and the form asks for nothing that identifies a person | `docs/recording/SESSION_FORM.md` | `REGISTRY.md`: row `CAP-DOC-016` appended | `test_FR_0_8_03_session_form_has_every_field`, `test_FR_0_8_03_choices_equal_the_recording_guide_lists`, `test_FR_0_8_03_speaker_id_and_consent_reference_formats_match_the_guide`, `test_FR_0_8_03_asks_for_no_identifying_details` | AT-0.8-01 |
| FR-0.8-04 | Filler library under "Filler library" below: a risk-level table (from the blueprint), a never-play context table (deviation D3) and a filler table of 20 rows | `docs/fillers/FILLER_LIBRARY_v0.md`; `tests/aqis_lab/test_aqis_filler_library.py` | `REGISTRY.md`: row `CAP-DOC-017` appended | `test_FR_0_8_04_library_has_about_20_fillers`, `test_FR_0_8_04_risk_levels_are_the_blueprint_four_and_all_used`, `test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level`, `test_FR_0_8_04_every_filler_has_a_never_play_context`, `test_FR_0_8_04_ids_and_texts_unique`, `test_FR_0_8_04_every_context_used_is_defined`, `test_FR_0_8_04_checks_detect_missing_level_or_context` | AT-0.8-01 |
| FR-0.8-05 | Targets document under "Targets options" below: one section per target, with 2 or 3 options, trade-offs and a blueprint citation for each option, and a decision line that is always the owner blank. No recommendation (question 7) | `docs/decisions/TARGETS_OPTIONS.md`; `tests/aqis_lab/test_aqis_targets_options.py` | `REGISTRY.md`: row `CAP-DOC-018` appended | `test_FR_0_8_05_four_targets_each_with_2_or_3_options`, `test_FR_0_8_05_every_option_has_trade_offs_and_a_citation`, `test_FR_0_8_05_citations_name_sections_of_the_committed_blueprint`, `test_FR_0_8_05_document_does_not_choose`, `test_FR_0_8_05_choice_check_detects_a_filled_decision`, `test_FR_0_8_05_owner_decisions_name_existing_options` (question 7 (a), added once your decisions are on `main`) | AT-0.8-01 |
| AT-0.8-01 | The auditor checks completeness against each requirement and that no value was invented where you must decide. `EVIDENCE.md` lists, for each document, every owner-given value with the approval line it comes from, and every citation with its source section | — | — | all of the above | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_8"`; the full fast suite; `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.8` |

### Debt work (only if question 2 is (a))
| Debt | Fix | Changed files and functions (change budget) | Tests (new file `tests/aqis_lab/test_aqis_debt_wp08.py`) | Acceptance command |
| --- | --- | --- | --- | --- |
| DEBT-010 | When a row's dataset is known, its licence is in the licence table and its split is one of the dataset's splits, the licence must equal `dataset.licence_for_split(split)`. Otherwise there is a problem at column `licence` naming both licences, the dataset and the split | `aqis_lab/registry/registry.py`: `check_records` (one added check) and the module docstring (CAP-REG-001 text and tests, CHANGE LOG); `docs/data/REGISTRY_FORMAT.md`: validation section, one sentence; `REGISTRY.md`: row CAP-REG-001; `docs/progress/DEBT.md`: DEBT-010 Status cell | `test_FR_0_4_01_rejects_licence_that_differs_from_its_dataset` (parametrised: a LibriSpeech row relabelled to another licence of the table; a MUSAN noise row given the music subset's licence), `test_FR_0_4_01_committed_registry_licences_equal_dataset_licences` | `.venv/bin/python -m aqis_lab registry validate`: exit 0 (baseline at planning: "OK, 6559 rows (librispeech 5559, musan 990, tts 10)") |
| DEBT-012 | `changes` becomes required (question 3), and `LICENCES.md` always prints the dataset's own `changes` text, never "none; the files are used as they are". `format_version` stays 1, because every existing `datasets.yaml` already carries `changes` | `aqis_lab/registry/schemas/datasets.v1.json`: `"changes"` added to the `required` list that already holds `attribution`; `aqis_lab/packs/licences.py`: `licences_markdown` (the "Changes made" line, no default) and the module docstring (CHANGE LOG); `aqis_lab/registry/datasets.py`: module docstring only (CAP-REG-002 tests); `docs/data/REGISTRY_FORMAT.md`: the line "optional `changes`"; `REGISTRY.md`: rows CAP-REG-002 and CAP-PACK-007; `DEBT.md`: DEBT-012 Status cell | `test_FR_0_4_07_dataset_without_changes_is_rejected` (a download dataset and a local dataset); the existing WP-0.4 licence and pack tests show the committed `LICENCES.md` is unchanged | `.venv/bin/python -m aqis_lab pack verify data/packs/smoke/v1`: exit 0 (baseline at planning: "pack smoke 1.0.0: OK, 60 clips in 5 archives") |
| DEBT-018 | `run_smoke` checks `--bundle-dir` with `drive.check_write_path(bundle_dir, system)` right after the platform check and before any task preflight. A `DriveError` becomes `SmokeInputError` (exit 2), so nothing runs and nothing is written | `aqis_lab/smoke.py`: `run_smoke` (the `bundle_dir` line moves up, plus the check) and the module docstring (CAP-SMOKE-002 text and tests, CHANGE LOG); `REGISTRY.md`: row CAP-SMOKE-002; `DEBT.md`: DEBT-018 Status cell | `test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab` (Colab view from `drive_view`: exit 2, the message names the path and `AQIS_LAB`, nothing is created on the mount or in `--out` or `--work-dir`); `test_NFR_0_5_02_smoke_accepts_bundle_dir_inside_aqis_lab` (the same view with a folder inside `MyDrive/AQIS_LAB` passes the check and stops later, at the GPU preflight's own message) | fast suite |
| DEBT-020 | Tests only | `aqis_lab/smoke.py`: module docstring only (CAP-SMOKE-003 and CAP-SMOKE-004 test lists); `REGISTRY.md`: rows CAP-SMOKE-003 and CAP-SMOKE-004 (test lists); `DEBT.md`: DEBT-020 Status cell | `test_FR_0_7_07_smoke_revalidates_each_event_log_before_storing`: a real harness-vad run is copied into a bundle folder, and one line of its `events.jsonl` (first, middle or last, parametrised) is replaced by an invalid record. `_check_and_store` then raises `SmokeFailure` naming the file, the line and "is not valid event log v1", and the store gets no rows. The test fails if the re-validation is removed. `test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows`: for each committed bundle, `_report` regenerates the committed report byte for byte, with runs and score tables in the config's order (finding 7). Each summary line must then state the values recomputed in the test from `results.jsonl`, as a median and maximum with `statistics` at the documented 4 decimals: the real-speed latencies, the count of real-speed transcripts equal to batch, and Parakeet's processing time and GPU | fast suite |
| DEBT-021 | (a) Put back the dropped clause in the `CAP-DOCTOR-002` row: "; minimums documented in `docs/doctor/DOCTOR.md` equal the config". (b) Per question 4: the `--gpu` sync passes the GPU lock as a build constraint too | (a) `REGISTRY.md`: row CAP-DOCTOR-002, "What it does" cell. (b) `aqis_lab/deploy/dev_bootstrap.sh`: the `--gpu` `"$UV" pip sync` line (adds `--build-constraints "$GPU_LOCK"`) and its header comment (CHANGE LOG); `REGISTRY.md`: row CAP-ENV-001; `DEBT.md`: DEBT-021 Status cell | (a) The existing `test_FR_0_5_02_minimums_documented_equal_config` is already listed in the row. (b) `test_FR_0_7_03_bootstrap_gpu_build_constraints_include_the_gpu_lock`: the `--gpu` sync names both locks as build constraints, and the CPU-only sync names only the CPU lock. The existing `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints` stays unchanged and green. Before relying on it, I check in the scratchpad that two constraint files pinning different setuptools versions make uv fail. If uv quietly picks one, I stop and ask | fast suite |

## Design details

### Owner blanks (must-catch 1)
- An owner blank is written `[OWNER DECIDES: <what>]`, for example `[OWNER DECIDES: how long recordings are kept]`. It is visible on screen and on paper, and a test can find it with one regular expression.
- Fields that a participant or the person running the session fills in (name, signature, date, speaker ID) are written as a blank line `______`. They are not owner decisions.
- Planned owner blanks:

  | Document | Owner blank | Source of the rule |
  | --- | --- | --- |
  | CONSENT_FORM.md | retention period | FR-0.8-01 ("a blank for the owner to fill") |
  | CONSENT_FORM.md | contact | question 6 (f) (a) |
  | CONSENT_FORM.md | any other fact in question 6 that you choose to leave open | question 6 |
  | TARGETS_OPTIONS.md | the decision on the harm-rate target, the practical margin, the timing budget and the gate escalation limit (4 blanks) | FR-0.8-05 |

- No owner blank is ever replaced by Claude. Your decisions are recorded in the approval file (question 7).
- **Values you give in the approval** (question 6) are copied word for word. `EVIDENCE.md` maps each one to its approval line, so the auditor can tell them apart from invented values.

### Consent form (`docs/recording/CONSENT_FORM.md`)
- **Headings, in order:**
  1. Why we are recording.
  2. What we record.
  3. How we store your recordings.
  4. Who can see them.
  5. How long we keep them.
  6. Your right to withdraw.
  7. Contact.
  8. Your consent (deviation D2).
- **Contents:**
  - The purpose is to test speech technology for a voice bot: speech recognition, voice activity and end-of-turn detection, voice emotion and filler selection. The wording comes from the blueprint (BLK-013).
  - "What we record" covers your voice reading the prompts, plus the session details on the session form. No name is stored with the recordings.
  - Storage and access come from the Build Plan and from your answers to question 6.
  - Withdrawal says how to withdraw, that no reason is needed, and what happens to the recordings (question 6 (e)).
- **Consent block:**
  - tick-box statements (I have read this form; I am 18 or older if question 6 (d) is (a); I agree to be recorded for the purpose above);
  - name, signature and date;
  - the consent reference, which you fill in.
- **Plain English rules, checked by test:**
  - UK English, in the second person;
  - average sentence length of 20 words or fewer, and no sentence over 30 words;
  - none of these words: hereby, herein, hereinafter, whereas, pursuant, notwithstanding, aforementioned, thereof, heretofore.
- **One page:**
  - The test caps the whole file at 450 words. One A4 or US Letter page at 11 pt holds about 500 words, and the consent block needs room.
  - You also print it once (owner-run check), because a word count can only stand in for a page count.

### Recording guide (`docs/recording/RECORDING_GUIDE.md`)
Every fact comes from the Build Plan (BLK-013). The sections are:
1. **About campaign A**: who records, how long a session takes, and what happens before the session (signed consent, session form).
2. **The 80 prompts**: a table with family ID, family, number of prompts, what the family tests, and example prompts if the Build Plan gives them. The counts total 80. If the Build Plan lists the prompt texts, the guide includes them word for word. Otherwise it gives the structure only, as FR-0.8-02 asks, and the texts are written in phase 1.
3. **Devices**: a table of device IDs with descriptions and setup guidance (distance, orientation, settings to switch off).
4. **Rooms and noise**: tables of room IDs and noise-source IDs, with guidance.
5. **Accent groups**: a table of accent-group IDs.
6. **Speaker IDs and consent references**: the formats from question 5, and where the signed form is kept (never in the repository).
7. **File naming**: the rule, for example `<speaker-id>-<family-id>-<NN>.wav` if the Build Plan does not define one, with examples. Every name must match `[a-z0-9-]+\.wav`, and every `clip_id` must be unique across speakers.
8. **Format**: the recording format the Build Plan gives, and the delivered working format (16 kHz, mono, 16-bit PCM WAV), with the conversion stated if the two differ.
9. **Transfer**: the Build Plan's route, for example to `MyDrive/AQIS_LAB`. Within the Colab limits in `.claude/rules/40-environment-parity.md`, recordings travel as one archive per session, never thousands of loose files, and no folder holds more than 10,000 items.
10. **Quality checks**: a table with check, how to check and pass rule, for example duration, clipping, background level, and the transcript matching the prompt. The thresholds come from the Build Plan.

### Session form (`docs/recording/SESSION_FORM.md`)
- **Fields:** a table with field, entry and how to fill it. The fields are speaker ID, device, room, noise source, accent group and consent reference, plus session date (UTC) and notes (deviation D1).
- **Choices:** device, room, noise source and accent group are chosen from the IDs listed in the guide.
- **Nothing that identifies a person:** there is no field for name, address, phone, email or date of birth. Speaker IDs are pseudonymous.

### Filler library (`docs/fillers/FILLER_LIBRARY_v0.md`)
- **Scope note:** a filler here is a short bot utterance played while the bot prepares its answer. It is not the disfluencies ("um", "uh") that the WP-0.3 scorer removes.
- **Risk levels:** a table with level ID, name, meaning and blueprint citation. It has exactly the blueprint's four levels.
- **Never-play contexts** (deviation D3): a table of context IDs (`ctx-…`) and their meanings, from the blueprint where it names them.
- **Fillers:** a table with ID (`fil-001` to `fil-020`), risk level, text, intended use, and "never play when" (one or more context IDs). IDs do not encode the level, so moving a filler to another level does not change its ID.
- **Count and texts:** 20 fillers, with every level used. The texts follow the bot's domain and voice from the blueprint (question 1, fallback (iv)). The test accepts 18 to 22, my reading of "about 20".

### Targets options (`docs/decisions/TARGETS_OPTIONS.md`)
- **One section per target:** the harm-rate target, the practical margin for model comparisons, the timing budget and the gate escalation limit.
- **Each section has:**
  - what the target measures, from the blueprint;
  - an options table (option ID such as `HR-A`, value, what it gives, what it costs, citation of a blueprint section by its heading);
  - the line `**Decision:** [OWNER DECIDES: <target>]`.
- **No recommendation:** no option is marked as preferred or recommended, because the WP does not choose (question 7 (b)).
- **"How to record your decision":** points to `docs/approvals/WP-0.8.md` and the line format of question 7.

### How the tests read the documents
- `tests/aqis_lab/aqis_docs_testutil.py` holds the shared parsers. It splits a Markdown file into sections by heading, reads pipe tables by header name, finds owner blanks, counts words and splits sentences.
- Each test computes its expected values from the spec or from another source (the Build Plan, the importer rules, another document), never from the document under test.
- Three tests run their check on an edited copy and must see it fail:
  - `test_FR_0_8_01_blank_check_detects_a_filled_in_value`;
  - `test_FR_0_8_04_checks_detect_missing_level_or_context`;
  - `test_FR_0_8_05_choice_check_detects_a_filled_decision`.

  This proves the checks are not empty.
- Two tests compare against the committed sources (BLK-013):
  - `test_FR_0_8_02_prompt_families_match_the_build_plan` compares the family names and counts;
  - `test_FR_0_8_05_citations_name_sections_of_the_committed_blueprint` checks that every cited heading exists.

  Both read `docs/specs/sources/`. If you commit the sources only as PDF, these two checks fall to the auditor, because the lock has no PDF reader and adding one would widen the WP.

### Must-catch proof (planned)
1. "No value the owner must decide is filled in by Claude":
   - put "2 years" in the retention blank → `test_FR_0_8_01_retention_is_an_owner_blank_with_no_value` fails;
   - put "HR-B" in one decision line → `test_FR_0_8_05_document_does_not_choose` fails.
2. "Every filler has a risk level and at least one context where it must never play":
   - empty one filler's "never play when" cell → `test_FR_0_8_04_every_filler_has_a_never_play_context` fails;
   - empty one filler's risk level → `test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level` fails.

Each break is made in a copy under `/tmp`, and the result is recorded in `EVIDENCE.md`.

### Registry rows (appended; no existing row changes except the debt rows above)
| ID | Module | What it does |
| --- | --- | --- |
| CAP-DOC-014 | `docs/recording/CONSENT_FORM.md` | One-page plain-English consent form with the required sections and owner blanks |
| CAP-DOC-015 | `docs/recording/RECORDING_GUIDE.md` | Campaign A recording guide matching the Build Plan |
| CAP-DOC-016 | `docs/recording/SESSION_FORM.md` | Session form whose choices equal the guide's lists |
| CAP-DOC-017 | `docs/fillers/FILLER_LIBRARY_v0.md` | Filler library v0: every filler has a risk level and a never-play context |
| CAP-DOC-018 | `docs/decisions/TARGETS_OPTIONS.md` | Options for the four targets, each with a citation; decisions left to the owner |

## Parts that do not depend on owner inputs
- Once the plan is approved, the debt work (question 2 (a)) can be built before BLK-013 is answered.
- All five documents wait for BLK-013, because their content comes from the blueprint and Build Plan.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | The blueprint and Build Plan in `docs/specs/sources/` on `main`, preferably as Markdown or text (BLK-013, question 1) | The content of all five documents | Before `/wp-build` writes the documents |
| 2 | Answers to questions 2 to 8 in `docs/approvals/WP-0.8.md` CONDITIONS | Scope, debt fixes, consent design, deviations | With the approval |
| 3 | The consent facts of question 6, word for word as they should appear | FR-0.8-01: I must not invent them | With the approval |
| 4 | Your decisions on the four targets and the retention period, as `DECISION:` lines in the approval (question 7) | Overview: "Decisions on targets and retention … Approval file" | After you read the drafted `TARGETS_OPTIONS.md`, before the audit |
| 5 | The owner-run checks below | One page, people-facing wording | Before merging |

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| Consent form fits one page | Your computer | Open `docs/recording/CONSENT_FORM.md` on GitHub, then print preview at A4 or US Letter with default margins | One page |
| Wording of the five documents | The pull request | Read the five documents | Your OK, or edits you ask for |

## Risks and questions
### Risks
1. **The Build Plan may conflict with the importer.** It may name files in ways the importer rejects (capitals, underscores) or give a recording format other than the working format. I will report any conflict and not adapt either side quietly. Changing the importer is outside this WP.
2. **One speaker per folder.** The importer takes one speaker per folder, so the guide plans one folder per speaker session, which works today. If the Build Plan lays folders out differently, phase 1 needs importer changes, and I will report that.
3. **Not legal advice.** The consent form is plain English. Voice recordings are personal data, and inferring emotion from them may count as sensitive processing in some places. Depending on where recording happens, you may need a privacy notice or a legal review. I cannot judge that.
4. **One page is checked by a word budget.** A word count can only stand in for a page count. Your print check closes the gap.
5. **Fixed structure.** The tests depend on fixed headings and table columns. Later edits must keep them, and each document says so in one line at the top.
6. **Wider audit scope.** Closing the debts brings code into the audit of a documents WP (question 2).

### Questions
1. **(BLK-013) The blueprint and Build Plan.**
   - **(a) Recommended:** commit both documents whole, as Markdown or text, to `docs/specs/sources/` on `main`.
   - **(b)** Commit only the four named sections plus every passage on the four targets.
   - **Fallbacks:** for anything the documents do not cover, tell me in the approval: (i) the prompt families and counts; (ii) device, room, noise-source and accent-group categories; (iii) the four risk levels; (iv) the bot's domain and voice for filler texts; (v) the speaker-ID format; (vi) quality-check thresholds.
2. **Debts that target this documents-only WP** (DEBT-010, 012, 018, 020, 021).
   - **(a) Recommended:** close all five here as planned under "Debt work". This follows your approvals that set the target, and it can be built while BLK-013 is open.
   - **(b)** Retarget all five to WP-0.9.
   - **(c)** Decide per debt.
3. **DEBT-012: where `changes` becomes required.**
   - **(a) Recommended:** for every dataset. `LICENCES.md` then always states the dataset's own changes, and no current file breaks.
   - **(b)** Only for datasets whose licence has `attribution_required: true`. Others would still need some text, so I would ask you for it.
4. **DEBT-021 (b): the `--gpu` build constraints.**
   - **(a) Recommended:** pass both locks as build constraints. The existing test stays unchanged, and if the two setuptools pins ever differ, the install fails loudly (checked first, as in "Debt work").
   - **(b)** Pass only the GPU lock, as the WP-0.7 plan said. This needs `ALLOW-EDIT: tests/aqis_lab/test_aqis_locks_gpu.py`, because the existing test requires `"$LOCK"` on every sync line.
   - **(c)** Change no code, and close the debt by recording that the CPU lock is intended.
5. **Consent references and personal data.**
   - **(a) Recommended:**
     - The speaker ID is `ca-sNNN` (pseudonymous). The consent reference is `ca-cNNN`, with the same number, written on the signed form and the session form.
     - The signed form, with its name and signature, never goes into the repository or `AQIS_LAB`; you keep it somewhere only you can open.
     - In phase 1, the repository gets one consent record per speaker, holding no name: the consent reference, speaker ID, consent form version (commit and SHA-256), date signed and withdrawal status. That record is the file the registry's `consent_ref` points to. WP-0.8 only describes this in the guide and creates no record and no code.
   - **(b)** The Build Plan's own scheme, if it has one.
   - **(c)** A scheme you describe.
6. **Consent form facts only you can give.** Please write them as they should appear. The retention period stays blank, as FR-0.8-01 requires.
   - **(a) Who can see the recordings:** only you, or you and named roles (no names needed).
   - **(b) Which services store or process them:** today the lab uses Google Drive (`AQIS_LAB`), Google Colab and an Oracle Cloud VM. GitHub holds only non-personal records and results, never audio. Confirm this, or add others, for example a paid speech API.
   - **(c) Use:** testing only, or also training or fine-tuning models, or publication. The narrowest promise is the easiest to keep.
   - **(d) Minimum age:** **(a) Recommended:** 18 or older; **(b)** none stated.
   - **(e) Withdrawal:**
     - what happens: recommended, recordings and clips are deleted and left out of future packs, and results already computed stay only as totals that cannot identify the person;
     - the deadline in days: give a number, or leave it as an owner blank.
   - **(f) Contact:** **(a) Recommended:** an owner blank you fill on each printed copy, which keeps contact details out of the repository; **(b)** the contact text, given in the approval.
7. **Your decisions on targets and retention.**
   - **(a) Recommended:**
     - The documents keep their owner blanks.
     - After reading the drafted `TARGETS_OPTIONS.md`, you add lines to `docs/approvals/WP-0.8.md` on `main`, such as `DECISION: harm-rate = HR-B` (one per target) and `DECISION: retention = <your wording>`.
     - I then add `test_FR_0_8_05_owner_decisions_name_existing_options`, which checks that each line names one of the four targets and one of its option IDs, and the WP goes to audit.
   - **(b)** Record decisions later, in phase 1. The WP closes with the options only, and nothing checks the decisions now.
   - **Also:** should `TARGETS_OPTIONS.md` give my recommendation? Recommended: **no**, because "the WP does not choose".
8. **Accept deviations D1, D2 and D3 below?** Recommended: yes, all three.

## Deviations
Each addition goes beyond the spec's wording. I list it here so that nothing is added silently. Accept or reject each one (question 8).
- **D1 — Session form adds two fields:** session date (UTC) and notes. **Reason:** quality checks and re-recordings refer to a session by speaker and date, and notes capture problems the checks find.
- **D2 — Consent form adds a consent block:** tick-box statements, name, signature, date and consent reference. **Reason:** a consent form needs a place to give consent. The consent reference links the paper form to the session form (FR-0.8-03) and to the registry, without putting a name in the repository.
- **D3 — Filler library defines never-play contexts once, with IDs, and fillers refer to them.** **Reason:** each "must never play" context then means the same thing across fillers, and the phase 1 selector can check it by ID. It changes the format, not the content FR-0.8-04 asks for.

No other deviation. The debt work is in scope only if you choose question 2 (a).
