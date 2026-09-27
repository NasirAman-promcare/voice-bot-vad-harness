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
