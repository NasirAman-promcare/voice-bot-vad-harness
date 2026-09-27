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
