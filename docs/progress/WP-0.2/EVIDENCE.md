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

### NFR-0.2-01 — 100,000 events in under 10 s on the cloud VM
- Approach (approved question 2, option a): event files of at least 5,000 records are split over worker processes (`spawn`; default count `os.process_cpu_count()`, 4 here), and the reports are identical to one process (`test_FR_0_2_04_worker_pool_report_identical_to_single_process`, `test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files`). The per-event-type validators also inline local `$ref`s whose siblings are annotations only, which does not change any result (`test_FR_0_2_04_dispatch_matches_full_schema_on_all_fixtures` still passes).
- Test: `test_NFR_0_2_01_validates_100k_events_under_10s` (marked `slow`). It runs the command on a generated 100,000-event file covering every event type, and requires exit 0, 100,000 OK lines and a wall time under 10 s.
- Measurements on this VM, for the same 100,000-event file:
  - Before the worker pool and the inlining (one process): 23.0 s.
  - With the worker pool: 6.52 s.
  - After inlining: 17.3 s in one process (`--workers 1`), 5.12 s with `--workers 4`.

  So the test would fail without the worker pool.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_nfr.py -q -s -p no:cacheprovider -k NFR_0_2_01`, five runs.
- Output (real excerpt, five runs):
```text
validated 100000 events in 5.03 s (validating 100000 records with 4 worker processes)
validated 100000 events in 4.87 s (validating 100000 records with 4 worker processes)
validated 100000 events in 5.08 s (validating 100000 records with 4 worker processes)
validated 100000 events in 5.26 s (validating 100000 records with 4 worker processes)
validated 100000 events in 5.20 s (validating 100000 records with 4 worker processes)
1 passed, 1 deselected in 5.67s
```
- Status: DONE. The margin is about 2×. On Colab's 2 vCPUs the same file would take about 9 s (estimated from the one-process time; not measured). The NFR applies to the cloud VM only.

### NFR-0.2-02 — Pure Python with pinned jsonschema
- Test: `test_NFR_0_2_02_contracts_code_is_pure_python_with_pinned_jsonschema`. It checks, by AST, that the only third-party import of `aqis_lab/contracts/*.py` and `aqis_lab/commands/contracts.py` is `jsonschema`, pinned `==4.26.0` with hashes in `phase0.txt` and installed at that version; and that `aqis_lab/contracts/` holds only `.py` modules and `schemas/*.json`. Approved question 7: jsonschema's own dependency `rpds-py` is a compiled wheel, already pinned with hashes.
- The test passed on its first run, because the code was pure Python from the start.
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_contracts_nfr.py -q -p no:cacheprovider -k NFR_0_2_02` (also part of the fast suite).
- Fast suite: `952 passed, 9 deselected in 57.55s`.
- Status: DONE

## Must-catch proof
Each break was made in a scratch copy of the repository (`git ls-files` plus the fixtures, under the session scratchpad in `/tmp`), one at a time and restored after its run. The named tests ran with `-x -m "not slow"`. The working tree was untouched (`git status --porcelain` empty afterwards).

| # | Behaviour (spec) | Break in the copy | First failing test (real output) |
| --- | --- | --- | --- |
| 1 | Omitting each required field is rejected, naming it by JSON Pointer | `seq` removed from the event `required` list | `test_FR_0_2_01_rejects_missing_required_field[seq-run_started]` |
| 1 | same | `notes` removed from the run card `required` list | `test_FR_0_2_02_rejects_missing_required_field[notes]` |
| 1 | same | `licence` removed from the clip `required` list | `test_FR_0_2_03_rejects_missing_required_field[clips/0/licence]` |
| 1 | same (pointer names the field) | missing field reported at its parent's pointer | `test_FR_0_2_01_rejects_missing_required_field[run_id-run_started]` |
| 2 | Wrong types and values outside enums are rejected | `asr` added to the `component` enum | `test_FR_0_2_01_rejects_wrong_type_or_enum[final-path18-asr]` |
| 2 | same | `fast` added to the `mode` enum | `test_FR_0_2_02_rejects_wrong_type_or_enum[('mode',)-'fast']` |
| 2 | same | clip `channels` type `integer` → `number` | `test_FR_0_2_03_rejects_wrong_type_or_enum[('clips', 0, 'channels')-1.0]` |
| 2 | same | strict integer type checker made to accept `1.0` | `test_FR_0_2_01_rejects_wrong_type_or_enum[final-path14-1.0]` |
| 3 | An unknown major schema version is rejected | major-version check disabled (`if False:`) | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` |
| 4 | `run_card_id` equals the SHA-256 of the canonical card, computed independently | `seed` added to the excluded fields | `test_FR_0_2_05_run_card_id_computed_independently` |
| 4 | same | canonical separators `", "` and `": "` | `test_FR_0_2_05_canonical_bytes_match_definition` |
| 4 | same | canonical output escapes non-ASCII (`ensure_ascii=True`) | `test_FR_0_2_05_canonical_bytes_match_definition` |
| 5 | Documents and schemas list exactly the same fields | `/model/checksum` row removed from `RUN_CARD.md` | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` |
| 5 | same | undocumented `reason` field added to the `run_finished` payload schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` |
| 6 | `contracts validate` exits non-zero on any invalid record in a JSON Lines file | command always returns 0 | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` |
| 6 | same | command counts only the first record | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[middle]` |

Command: `.venv/bin/python <scratchpad>/mustcatch.py "$PWD" <scratchpad>/mc "$PWD/.venv/bin/python"`. Output excerpt:
```text
MC1a event: 'seq' dropped from required
  FAILED tests/aqis_lab/test_aqis_contracts_event_log.py::test_FR_0_2_01_rejects_missing_required_field[seq-run_started]
  1 failed, 30 passed, 841 deselected in 0.79s
MC3 unknown major version accepted by the version check
  FAILED tests/aqis_lab/test_aqis_contracts_versioning.py::test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]
  1 failed, 949 deselected in 0.26s
MC4a run_card_id excludes 'seed' too
  FAILED tests/aqis_lab/test_aqis_contracts_canonical.py::test_FR_0_2_05_run_card_id_computed_independently
  1 failed, 2 passed, 946 deselected in 0.22s
MC5a RUN_CARD.md loses the /model/checksum row
  FAILED tests/aqis_lab/test_aqis_contracts_docs.py::test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]
  1 failed, 2 passed, 958 deselected in 0.23s
MC6b command counts only the first record
  FAILED tests/aqis_lab/test_aqis_contracts_cli.py::test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[middle]
  1 failed, 1 passed, 958 deselected in 0.61s
```
All 16 breaks were caught; no test had to be added.

## Acceptance commands

### AT-0.2-01 — the fast suite passes, including valid and invalid fixtures for every event type and field
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"
952 passed, 9 deselected in 56.53s
```
Slow suite as well: `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow and not gpu and not colab and not oracle" -p no:cacheprovider` → `9 passed, 952 deselected in 118.45s (0:01:58)` (8 WP-0.0 slow tests and NFR-0.2-01).

### AT-0.2-02 — `contracts validate` on the valid and the invalid event fixture
```text
$ .venv/bin/python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/valid_events.jsonl --kind event
line 1: OK
...
line 23: OK
event: 23 records, 23 valid, 0 invalid
exit=0
$ .venv/bin/python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/invalid_events.jsonl --kind event
line 1: INVALID /schema_version: required field is missing; without it the record's contract version is unknown
line 2: INVALID /run_id: required field is missing
line 3: INVALID /run_card_id: required field is missing
...
line 96: INVALID /seq: seq 1 is out of order for run_id 'run-seq-b': expected 0 (seq counts 0, 1, 2, ... per run, in file order)
event: 96 records, 2 valid, 94 invalid
exit=1
```

### AT-0.2-03 — the audit gate passes with `--wp WP-0.2`
See "Audit gate" below.

## Audit gate
The first run, before this section existed, reported exactly the three missing AT entries (`[F4] MAJOR: AT-0.2-0N does not appear in docs/progress/WP-0.2/EVIDENCE.md`, `3 findings: FAIL`). The run after this section was written is pasted below.
```text
$ git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.2
aqis-audit-gate: base origin/main (merge-base 6f897411d876), head 3459ffab0612, approvals origin/main 6f897411d876, wp WP-0.2
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.2 s)
exit=0
```

## Owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| None | — | — | The spec runs WP-0.2 on the cloud VM only; CI runs the fast suite on GitHub's Ubuntu runner | — |

## audit-allow lines
None.

## Deviations and decisions applied
- D1 (approved, question 1): `schema_version` added to the run card and the pack manifest.
- Questions 2 to 7 applied as recommended. Question 2: worker pool. Question 3: payload fields and the nullable `pack`, `normaliser` and `speaker_id`. Question 4: `owner`/`campaign` sources need `consent_ref`. Question 5: per-run `seq` check. Question 6: nested `.gitignore`. Question 7: the pure-Python reading.
- Differences from the plan text, all inside the approved scope:
  - FR-0.2-05 was built before FR-0.2-02, because the run card's ID check needs it.
  - The three contract documents were written with FR-0.2-06.
  - `validate_event_lines` takes the file's bytes, not a path.
  - CAP-CONTRACTS-007 is an extra registry row for the validator API.
  - Cross-field rule messages carry their `Rule:` text.

## CI
Pull request: https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/2 (title `WP-0.2 Contracts: event log, run card, pack manifest`). Every job is green on commit `45c4fe8`, the last commit with code, tests or fixtures:

| Run | Event | Job | Result | Real log excerpt |
| --- | --- | --- | --- | --- |
| 36310205390 | pull_request | `lab` | success | `952 passed, 9 deselected in 34.98s`; `Work package from the pull request title: WP-0.2`; gate `aqis-audit-gate: base origin/main (merge-base 6f897411d876), head 6170c2cb59ef, approvals origin/main 6f897411d876, wp WP-0.2` … `0 findings: OK (0.1 s)` |
| 36310205390 | pull_request | `harness-regression` | success | `1 failed, 21 passed in 4.26s` (the baseline's known failing test, `test_packet_loss_category_applies_drop_impairment_in_bridge`); `baseline: 22 tests, 21 passed; this run: 22 tests, 21 passed`; `RESULT: PASS` |
| 36310189503 | push | `lab` | success | (same commit) |
| 36310189503 | push | `harness-regression` | success | (same commit) |

Earlier WP-0.2 push runs (corrected in round 2, finding WP-0.2-F03):
- **Run #123** (36308454812) on `4f752e0` (FR-0.2-01) **failed** at step "Fast lab test suite". This was the header/registry mismatch recorded under FR-0.2-01 (`test_FR_0_0_08_module_headers_match_registry`), fixed in the next commit.
- Runs #124 to #130 were green: `b3e8a03`, `5939fe7`, `cb96d44`, `2527f84`, `616fddd`, `0a4e2ef`, `3459ffa`.

The commit that adds this section and sets STATUS changes only `docs/progress/`.

## Round 2 fixes (WP-0.2-F01, F02, F03, F05; debt F04, F06)
Authority: `docs/approvals/WP-0.2.md` on `main` (`e3439be`). Change budget, root causes and baseline: `docs/progress/WP-0.2/FIXES.md`. No production code or schema changed; the modules changed only in their header docstrings.

### F01 and F02 — the new tests
`tests/aqis_lab/test_aqis_contracts_gaps.py` (new, 46 cases):
- `test_FR_0_2_01_rejects_wrong_clip_id_type_on_either_level_events`: `timing_mark` and `error` with `clip_id` set to 7, 1.5, `true`, `[]`, `{}` or `["clip-1"]` are rejected at `/clip_id`; null and an ID are still accepted.
- `test_FR_0_2_01_rejects_non_object_word_items`: a non-object item (number, boolean, string, array or null) at index 0 or 1 of `payload.words` is rejected at `/payload/words/<i>`.
- `test_FR_0_2_02_human_session_pack_must_be_object_or_null`: with `mode: human_session`, `pack` null or an object is accepted; a number, boolean, string or array is rejected at `/pack`.
- `test_FR_0_2_03_rejects_non_object_archive_items`: a non-object `archives` item, replacing the first entry or appended at the end, is rejected at `/archives/<i>`.
- `test_FR_0_2_04_last_record_without_final_newline_is_validated`: `validate_event_lines` keeps and checks the last record when the file has no final newline, also with a final `\r`; this is also tested on a single-record file.
- `test_FR_0_2_04_cli_last_line_without_final_newline_fails`: the command reports `line 23: INVALID /component` and `event: 23 records, 22 valid, 1 invalid` with exit 1; the valid file without a final newline exits 0 with 23 records.
- `test_FR_0_2_04_cli_documents_without_final_newline` (the sibling case for run cards and manifests): valid documents exit 0 and invalid documents exit 1 without a final newline.

Against the unchanged code all 46 pass, because the code was already correct (a test gap, as the audit says).

### Proof: each audited break now fails a named test
The five breaks were made exactly as the audit describes, one at a time, in a scratch copy of the working tree (tracked files plus the new test file). Each break was restored before the next. For every break, the command runs the contract test files that existed in round 1, then the new file.

| Break (audit reference) | Round-1 contract tests | New tests | Failing test |
| --- | --- | --- | --- |
| F01-1 `event_log.v1.json` `properties/clip_id`: `type` removed | `712 passed` (the gap) | `12 failed, 34 passed` | `test_FR_0_2_01_rejects_wrong_clip_id_type_on_either_level_events` |
| F01-2 `event_log.v1.json` `$defs/word`: `type` removed | `712 passed` | `14 failed, 32 passed` | `test_FR_0_2_01_rejects_non_object_word_items` |
| F01-3 `run_card.v1.json` `properties/pack`: `type` removed | `712 passed` | `7 failed, 39 passed` | `test_FR_0_2_02_human_session_pack_must_be_object_or_null` |
| F01-4 `pack_manifest.v1.json` `$defs/archive`: `type` removed | `712 passed` | `7 failed, 39 passed` | `test_FR_0_2_03_rejects_non_object_archive_items` |
| F02 (CB6-2) `split_json_lines` always drops the last line | `712 passed` | `2 failed, 44 passed` | `test_FR_0_2_04_cli_last_line_without_final_newline_fails`, `test_FR_0_2_04_last_record_without_final_newline_is_validated` |

Command: `.venv/bin/python <scratchpad>/r2_breaks.py "$PWD" <scratchpad>/r2 "$PWD/.venv/bin/python"`, which runs `pytest -q -p no:cacheprovider -m "not slow"` in the copy. Output (real):
```text
F01-1 event_log properties/clip_id: type removed
  round-1 contract tests: 712 passed, 1 deselected in 11.13s
  new tests: 12 failed, 34 passed in 1.41s
  failing: test_FR_0_2_01_rejects_wrong_clip_id_type_on_either_level_events
F01-2 event_log $defs/word: type removed
  round-1 contract tests: 712 passed, 1 deselected in 10.79s
  new tests: 14 failed, 32 passed in 1.37s
  failing: test_FR_0_2_01_rejects_non_object_word_items
F01-3 run_card properties/pack: type removed
  round-1 contract tests: 712 passed, 1 deselected in 10.25s
  new tests: 7 failed, 39 passed in 1.25s
  failing: test_FR_0_2_02_human_session_pack_must_be_object_or_null
F01-4 pack_manifest $defs/archive: type removed
  round-1 contract tests: 712 passed, 1 deselected in 10.41s
  new tests: 7 failed, 39 passed in 1.33s
  failing: test_FR_0_2_03_rejects_non_object_archive_items
F02 CB6-2 split_json_lines always drops the last line
  round-1 contract tests: 712 passed, 1 deselected in 10.26s
  new tests: 2 failed, 44 passed in 1.11s
  failing: test_FR_0_2_04_cli_last_line_without_final_newline_fails, test_FR_0_2_04_last_record_without_final_newline_is_validated
```

### F03, F05; debt F04, F06
- F03: the CI paragraph under "## CI" now lists run #123 on `4f752e0` as failed and runs #124 to #130 as green; the run list was checked through the GitHub API.
- F05: a registry Module cell must name one existing file (the gate's `module_exists`, rule G33), so CAP-DOC-002 cannot list three documents there. `RUN_CARD.md` and `PACK_MANIFEST.md` now each have a row, CAP-DOC-003 and CAP-DOC-004, with the same tests. CAP-DOC-002's Functions cell points to them, and its capability is unchanged.
- F04 → DEBT-006, F06 → DEBT-007 in `docs/progress/DEBT.md` (target WP-0.9, accepted in the approval's round-2 condition).
- Registry and headers: the new tests are added to the CAP-CONTRACTS-001, 002, 003, 006 and 007 rows and to the matching lines in the `validate.py` and `commands/contracts.py` headers (header only, with CHANGE LOG lines).

### Checks after the fixes
- Fast suite: `998 passed, 9 deselected in 57.68s` (baseline `952`, plus the 46 new cases).
- Gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.2` → `0 findings: OK (0.2 s)`.
