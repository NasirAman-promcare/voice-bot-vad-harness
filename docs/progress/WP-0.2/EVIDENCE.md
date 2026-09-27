# EVIDENCE — WP-0.2

Environment: cloud VM (Ubuntu 24.04, x86_64, 4 vCPUs), Python 3.13.12 in `.venv` (Colab probe: 3.13), lock `requirements/aqis_lab/phase0.txt` sha256 `5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422` (jsonschema 4.26.0), branch `claude/beautiful-dijkstra-8pbq6l`. Approval: `docs/approvals/WP-0.2.md` on `main` (`6f89741`), "Questions 1-7: as recommended in PLAN.md".

Baseline before any change (change-control step 3, for `aqis_lab/__main__.py`): fast suite `240 passed, 8 deselected in 49.32s`; `-k FR_0_0_01` `7 passed`.

## Requirements

### FR-0.2-01 — Event log v1
- Tests (`tests/aqis_lab/test_aqis_contracts_event_log.py`, 258 test cases): `test_FR_0_2_01_schema_is_valid_draft_2020_12`, `test_FR_0_2_01_valid_fixture_covers_every_event_type`, `test_FR_0_2_01_valid_fixture_passes`, `test_FR_0_2_01_rejects_missing_required_field` (12 fields × 10 event types), `test_FR_0_2_01_rejects_missing_required_payload_field`, `test_FR_0_2_01_rejects_missing_required_word_field`, `test_FR_0_2_01_rejects_wrong_type_or_enum` (every envelope and payload field), `test_FR_0_2_01_clip_id_null_only_for_run_level_events`, `test_FR_0_2_01_null_audio_time_needs_reason`, `test_FR_0_2_01_final_word_timings`, `test_FR_0_2_01_error_payload_fields`, `test_FR_0_2_01_rejects_unknown_field`, `test_FR_0_2_01_invalid_fixture_names_expected_pointers`.
- Fixtures: `valid_events.jsonl` (23 events, two runs, every event type and component, run- and clip-level `timing_mark` and `error`, null and numeric audio times, `final` with and without words), `invalid_events.jsonl` (96 lines) with the failing pointers of every line written by hand in `invalid_events.expected.json`. Field lists in the tests come from the spec text (`tests/aqis_lab/aqis_contracts_testutil.py`), not from the schema. `tests/aqis_lab/fixtures/contracts/.gitignore` (`!*.jsonl`, approved question 6) lets git see the JSON Lines fixtures.
- Tests first: before `aqis_lab/contracts/` existed, collection failed with `ModuleNotFoundError: No module named 'aqis_lab.contracts'`. The first implementation then failed `test_FR_0_2_01_null_audio_time_needs_reason` (`assert {''} == {'/audio_time_reason'}`): jsonschema loses the property path for a `false` subschema, so "not allowed" is now written as `{"not": {}}`.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_event_log.py -q -p no:cacheprovider`, then a report of the invalid fixture through `validate_event_lines`.
- Output (real excerpt):
```text
258 passed in 0.53s
1 [('/schema_version', 'required field is missing')]
2 [('/run_id', 'required field is missing')]
3 [('/run_card_id', 'required field is missing')]
92 []
93 [('/seq', "seq 2 is out of order for run_id 'run-seq-a': expected 1 (seq counts 0")]
94 [('/seq', "seq 2 is out of order for run_id 'run-seq-a': expected 3 (seq counts 0")]
95 []
96 [('/seq', "seq 1 is out of order for run_id 'run-seq-b': expected 0 (seq counts 0")]
94 of 96 lines invalid
```
  Lines 92 and 95 are valid on purpose: they set up the sequence cases (a run's first record, and the record that continues after a gap).
- Fast suite after FR-0.2-01: `498 passed, 8 deselected in 46.73s`.
- Status: DONE
- Correction (found while building FR-0.2-05): the FR-0.2-01 commit `4f752e0` was pushed with a `validate.py` header that listed 7 of the 13 tests in the CAP-CONTRACTS-001 registry row. The fast-suite run quoted above was taken before I appended that row, so it did not show the problem. The existing WP-0.0 test `test_FR_0_0_08_module_headers_match_registry` then failed (`1 failed, 512 passed`). I changed the header only, to list all 13 tests. After the fix: `513 passed, 8 deselected in 46.53s`.

### FR-0.2-05 — Canonical JSON and IDs
Built before FR-0.2-02, because the run card's ID check (FR-0.2-02) uses it.
- Tests (`tests/aqis_lab/test_aqis_contracts_canonical.py`, 15 cases): `test_FR_0_2_05_canonical_bytes_match_definition` (hand-written byte literal: sorted keys, `,`/`:`, raw UTF-8 `\xc3\xa9`, escapes, number forms), `test_FR_0_2_05_key_order_does_not_change_bytes`, `test_FR_0_2_05_run_card_id_computed_independently` (the test's own recursive encoder plus `hashlib`; never calls `canonical.py` for the expected value), `test_FR_0_2_05_run_card_id_ignores_only_the_three_excluded_fields`, `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json` (NaN, ±Infinity, tuple, set, bytes, object, non-string key, unpaired surrogates, with pointers).
- Tests first: `E   ModuleNotFoundError: No module named 'aqis_lab.contracts.canonical'` (re-shown by moving the module aside after implementation).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_canonical.py -q -p no:cacheprovider`
- Output (real excerpt):
```text
15 passed in 0.03s
```
- Fast suite: `513 passed, 8 deselected in 46.53s`. Gate (`--base origin/main`, no `--wp`): `0 findings: OK (0.1 s)`.
- Status: DONE

### FR-0.2-02 — Run card v1
- Tests (`tests/aqis_lab/test_aqis_contracts_run_card.py`, 180 cases): `test_FR_0_2_02_schema_is_valid_draft_2020_12`, `test_FR_0_2_02_valid_fixture_passes` (every mode and platform, human session without pack, no normaliser, checksum-only model, GPU run, SHA-256 git commit), `test_FR_0_2_02_rejects_missing_required_field` (all 13 top-level fields, every nested member, step fields), `test_FR_0_2_02_rejects_wrong_type_or_enum` (every field), `test_FR_0_2_02_model_needs_version_or_checksum`, `test_FR_0_2_02_pack_null_only_for_human_session`, `test_FR_0_2_02_processing_keeps_step_order_per_path`, `test_FR_0_2_02_rejects_run_card_id_mismatch` (including fixtures `invalid_run_card_id.json` and `invalid_run_card_fields.json`, expected pointers written by hand in `invalid_expected.json`), `test_FR_0_2_02_rejects_unknown_field`, `test_FR_0_2_02_open_objects_accept_any_members`. Mutated cards get the ID their content defines from `rehash`, which uses the standard library directly, so each case shows only its intended field.
- Tests first: `E   ImportError: cannot import name 'validate_run_card' from 'aqis_lab.contracts.validate'`. The first implementation then failed 2 cases (`rejects_missing_required_field[model/version]`, `rejects_wrong_type_or_enum[('model', 'version')-1]`): the `anyOf` form of "version or checksum" also reported `/model/checksum`. The rule is now "when both are null, both are reported", written as an `if`/`then` in the schema; the tests are unchanged.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_run_card.py -q -p no:cacheprovider`, then `validate_run_card` on `invalid_run_card_fields.json`.
- Output (real excerpt):
```text
180 passed in 0.46s
run card record is invalid (4 problems):
  /mode: 'fast' is not one of ['batch', 'realspeed_cpu', 'gpu_compute_delay', 'tier2_live', 'nearlive_replay', 'human_session']
  /model/family: required field is missing
  /run_card_id: does not match the SHA-256 of the canonical run card without run_card_id, created_utc and notes (751b4eccf873cf9fd8a2f41969d4e5b4213b81800d7ac3e2bcfe1c63232673ca)
  /seed: required field is missing
```
- Fast suite: `693 passed, 8 deselected in 48.11s`.
- Status: DONE

### FR-0.2-03 — Pack manifest v1
- Tests (`tests/aqis_lab/test_aqis_contracts_manifest.py`, 165 cases): `test_FR_0_2_03_schema_is_valid_draft_2020_12`, `test_FR_0_2_03_valid_fixture_passes`, `test_FR_0_2_03_rejects_missing_required_field` (7 manifest, 16 clip and 4 archive fields), `test_FR_0_2_03_rejects_wrong_type_or_enum`, `test_FR_0_2_03_version_must_be_semver`, `test_FR_0_2_03_owner_and_campaign_clips_need_consent_ref`, `test_FR_0_2_03_rejects_duplicate_clip_id`, `test_FR_0_2_03_rejects_duplicate_archive_name`, `test_FR_0_2_03_clip_archive_must_be_listed`, `test_FR_0_2_03_rejects_unsafe_archive_name`, `test_FR_0_2_03_rejects_unsafe_member_path`, `test_FR_0_2_03_rejects_unknown_field`, `test_FR_0_2_03_recipe_accepts_any_members`, `test_FR_0_2_03_invalid_fixture_names_expected_pointers`.
- Tests first: `E   ImportError: cannot import name 'validate_manifest' from 'aqis_lab.contracts.validate'`.
- Test corrections before any implementation run (authoring slips, no code had been run against them): a wrong tag *element* is reported at `/clips/0/tags/0`, not `/clips/0/tags`, so those values moved to their own row; the clip `archive` field was missing from the wrong-value table and was added.
- First implementation run: 1 failure, `rejects_missing_required_field[archives/1/name]`. It showed that two of my expectations disagreed about clips that name an archive whose name is missing or not a string. The rule is now: references are judged only when every archive has a string name, because a nameless entry might be the clip's archive and the schema already reports that entry. `test_FR_0_2_03_rejects_unsafe_archive_name` was changed to state that rule for the `None` and `1` cases (its other cases are unchanged); the code was changed to match.
- Messages: a cross-field rule subschema described as `Rule: ...` now has that text appended to its error (consent, `pack` null, version or checksum).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_manifest.py -q -p no:cacheprovider`, then `validate_manifest` on `invalid_manifest_fields.json`.
- Output (real excerpt):
```text
165 passed in 0.55s
pack manifest record is invalid (4 problems):
  /archives/0/n_members: required field is missing
  /clips/1/clip_id: duplicate clip_id 'ls-test-clean-0001': already used by /clips/0
  /clips/2/archive: archive 'smoke-v1-009.tar' is not listed in /archives
  /clips/3/consent_ref: None is not of type 'string'. Rule: owner and campaign recordings need a consent reference.
```
- Fast suite: `858 passed, 8 deselected in 47.79s`.
- Status: DONE

### FR-0.2-04 — Validators and the `contracts validate` command
- Tests, API (`tests/aqis_lab/test_aqis_contracts_validate.py`): `test_FR_0_2_04_error_names_every_failing_pointer`, `test_FR_0_2_04_pointer_escapes_tilde_and_slash`, `test_FR_0_2_04_missing_field_pointer_names_the_field`, `test_FR_0_2_04_rejects_nan_infinity_and_overflow`, `test_FR_0_2_04_rejects_duplicate_keys`, `test_FR_0_2_04_rejects_integer_written_as_float`, `test_FR_0_2_04_patterns_reject_trailing_newline_and_non_ascii_digits`, `test_FR_0_2_04_non_json_python_values_rejected`, `test_FR_0_2_04_non_object_record_rejected`, `test_FR_0_2_04_rule_errors_explain_the_rule`, `test_FR_0_2_04_dispatch_matches_full_schema_on_all_fixtures` (per-type validators give the same errors as the full schema on more than 200 records: every fixture record, every event type with each field removed, and wrong values), `test_FR_0_2_04_seq_counts_from_zero_per_run` (question 5), `test_FR_0_2_04_worker_pool_report_identical_to_single_process` (question 2).
- Tests, command (`tests/aqis_lab/test_aqis_contracts_cli.py`): `test_FR_0_2_04_cli_valid_events_exit_0`, `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` (every line's pointers equal the hand-written `invalid_events.expected.json`), `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails` (first, middle, last), `test_FR_0_2_04_cli_unparsable_and_blank_lines_are_invalid_records` (non-UTF-8, blank, BOM, array, duplicate key, NaN, truncated; CRLF accepted), `test_FR_0_2_04_cli_empty_file_fails`, `test_FR_0_2_04_cli_run_card_and_manifest_kinds`, `test_FR_0_2_04_cli_missing_file_exit_2`, `test_FR_0_2_04_cli_listed_by_dispatcher`, `test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files`.
- Tests first: 12 of the 29 failed before the command and the pool existed. The dispatcher answered `python -m aqis_lab: error: argument command: invalid choice: 'contracts' (choose from version)` with exit 2, and the pool tests failed with `ImportError: cannot import name 'POOL_MIN_RECORDS'`. The other 17 API tests passed at once: FR-0.2-01 to FR-0.2-03 had already built those validator properties (pointers, strict parsing, the `seq` check), and these tests pin them down as FR-0.2-04 behaviour.
- After implementation, 1 failure came from my own test: a spot-check expected `line 5: INVALID /seq`, but `/seq` is the fourth field removed, so it is line 4 (the full comparison against `invalid_events.expected.json` in the same test passed). I corrected the literal to line 4. I also gave the event-log `clip_id` and `audio_time_reason` rules `Rule:` text and extended `test_FR_0_2_04_rule_errors_explain_the_rule` to cover them.
- Change budget: `git diff -U0 aqis_lab/__main__.py` shows exactly two added lines, the `COMMANDS` entry and a CHANGE LOG line; `build_parser` and `main` are unchanged. `-k FR_0_0_01` still passes (part of the fast suite below).
- Commands: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_validate.py tests/aqis_lab/test_aqis_contracts_cli.py -q -p no:cacheprovider`, then the command on both event fixtures.
- Output (real excerpt):
```text
29 passed in 10.89s
$ .venv/bin/python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/valid_events.jsonl --kind event
line 22: OK
line 23: OK
event: 23 records, 23 valid, 0 invalid
exit=0
$ .venv/bin/python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/invalid_events.jsonl --kind event
line 1: INVALID /schema_version: required field is missing
line 2: INVALID /run_id: required field is missing
line 3: INVALID /run_card_id: required field is missing
line 4: INVALID /seq: required field is missing
...
line 94: INVALID /seq: seq 2 is out of order for run_id 'run-seq-a': expected 3 (seq counts 0, 1, 2, ... per run, in file order)
line 95: OK
line 96: INVALID /seq: seq 1 is out of order for run_id 'run-seq-b': expected 0 (seq counts 0, 1, 2, ... per run, in file order)
event: 96 records, 2 valid, 94 invalid
exit=1
```
- Registry: CAP-CONTRACTS-006 (the command) and CAP-CONTRACTS-007 (the validator API). CAP-CONTRACTS-007 is a row the plan's list did not name: FR-0.2-04's API guarantees live in `validate.py` and belong to none of the three per-contract rows. The first gate run found my CAP-CONTRACTS-006 row malformed (`[E2] ... 9 cells, expected 7`: `\|` inside a cell splits the row), so I reworded that cell.
- Untested branch (stated here, not hidden): the `WorkerPoolError` path, taken when worker processes cannot start or die, which gives exit 2 with "rerun with --workers 1". Making process creation fail needs a resource limit that root ignores, or a test double for the OS, which the rules allow only for external services.
- Fast suite: `887 passed, 8 deselected in 56.43s`. Gate (`--base origin/main`): `0 findings: OK (0.1 s)`.
- Status: DONE

### FR-0.2-06 — Versioning
- Tests (`tests/aqis_lab/test_aqis_contracts_versioning.py`, 60 cases): `test_FR_0_2_06_schema_ids_carry_version`, `test_FR_0_2_06_rejects_unknown_major_version` (all three kinds; `2.0`, `0.1`, `10.0`, `2.5`), `test_FR_0_2_06_rejects_newer_minor_version` (`1.1`, `1.10`), `test_FR_0_2_06_rejects_malformed_schema_version` (12 malformed values, plus a missing version with another error present), `test_FR_0_2_06_documents_describe_change_policy`.
- Tests first: `E   ImportError: cannot import name 'UnsupportedSchemaVersionError' from 'aqis_lab.contracts.validate'`. After the version check was in, only the 3 document tests failed (`3 failed, 57 passed`), because `docs/contracts/` did not exist yet. The three contract documents written at this step (`EVENT_LOG.md`, `RUN_CARD.md`, `PACK_MANIFEST.md`) are the FR-0.2-01 to 03 deliverables, and FR-0.2-07 checks them.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_versioning.py -q -p no:cacheprovider`, then `validate_run_card` on the valid card with `schema_version` set to `2.0`, `1.1` and `1`.
- Output (real excerpt):
```text
60 passed in 0.21s
UnsupportedSchemaVersionError | run card record is invalid (1 problem):
  /schema_version: run card schema_version '2.0' has major version 2, which this validator does not know; it knows major version 1 (up to 1.0)
UnsupportedSchemaVersionError | run card record is invalid (1 problem):
  /schema_version: run card schema_version '1.1' is newer than this validator (1.0); update aqis_lab to validate it
ContractValidationError | run card record is invalid (1 problem):
  /schema_version: must be a string '<major>.<minor>' such as '1.0', got '1'
```
- Fast suite: `947 passed, 8 deselected in 57.02s`. Gate (`--base origin/main`): `0 findings: OK (0.2 s)`.
- Status: DONE

### FR-0.2-07 — Documents match schemas
- Tests (`tests/aqis_lab/test_aqis_contracts_docs.py`): `test_FR_0_2_07_documents_and_schemas_list_same_fields` (per kind; also requires the spec's fields, written out independently, to be among them, and one payload heading per event type), `test_FR_0_2_07_comparison_detects_missing_and_extra_fields` (a dropped document row, an added row, a field removed from a payload sub-schema, and a payload table under the wrong event type are all found, so the check cannot pass vacuously). The schema walker and the document parser are test code, independent of `aqis_lab/contracts`.
- Tests first: the documents were written at FR-0.2-06, so this test passed on its first run. To show it fails for the right reason, I moved `docs/contracts/` aside and got `E       FileNotFoundError: [Errno 2] No such file or directory: '.../docs/contracts/EVENT_LOG.md'`; then I restored it. The must-catch proof (below) breaks one document and one schema in a copy.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_docs.py -q -p no:cacheprovider`
- Output (real excerpt):
```text
4 passed in 0.03s
```
- Fast suite: `951 passed, 8 deselected in 56.96s`.
- Status: DONE
