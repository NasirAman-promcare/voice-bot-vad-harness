# PLAN — WP-0.2 Contracts: event log, run card, pack manifest

Spec: `docs/specs/phase-0/WP-0.2-contracts.md`  ·  Planned by session: https://claude.ai/code/session_01MBwfEheKCMo33riZUiqjUk  ·  Date: 2026-09-27
Branch: `claude/beautiful-dijkstra-8pbq6l`  ·  Base: `origin/main` at `014b051`  ·  Depends on: WP-0.0 (MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, the three records every later module uses are defined in three places that are tested to agree: a contract document (`docs/contracts/`), a JSON Schema 2020-12 file (`aqis_lab/contracts/schemas/`), and a validator (`aqis_lab/contracts/validate.py`). `validate_event`, `validate_run_card` and `validate_manifest` raise one exception that names every failing field by JSON Pointer. `python -m aqis_lab contracts validate <file> --kind event|run_card|manifest` prints a per-record report and exits non-zero on any invalid record. `aqis_lab/contracts/canonical.py` gives deterministic canonical JSON and the `run_card_id`. Valid and invalid fixtures cover every event type and every field.

## What I found in the repository (read-only inspection)
1. **Spec sources.** The spec's "Read first" names the blueprint sections "Lab architecture" and "Metrics catalogue". The blueprint is not in the repository. You said the spec is self-contained and `docs/specs/phase-0/` is authoritative (session notes 1 and 2), so the plan relies on the spec, the Phase 0 overview conventions and the later Phase 0 specs that consume these contracts (WP-0.3 to WP-0.7). The folder `aqis-kit-patch-3/` holds copies of the specs that are byte-identical to `docs/specs/` (checked with `cmp`).
2. **Python and lock.** The Colab probe says Python 3.13.15, so the lab Python is 3.13. `.venv` bootstraps to 3.13.12. `requirements/aqis_lab/phase0.txt` already pins `jsonschema==4.26.0` with hashes, plus its dependencies `referencing`, `rpds-py`, `attrs` and `jsonschema-specifications`. **No lock change is needed.**
3. **`*.jsonl` is git-ignored.** The root `.gitignore` (a GUARDED path) has `*.jsonl` on line 12. `git check-ignore -v tests/aqis_lab/fixtures/contracts/valid_events.jsonl` confirms it. The fixture named in AT-0.2-02 would therefore never be committed. In a scratch repository, a nested `.gitignore` containing `!*.jsonl` in the fixture folder re-includes the files there and nowhere else (see question 6).
4. **Validation speed (NFR-0.2-01).** In a scratchpad benchmark on this VM (4 vCPUs) with the pinned jsonschema and an event schema shaped like the one below, 100,000 events took:
   - 31 s with one schema whose event types are chosen by `if`/`then` blocks;
   - 12 to 14 s with the event type dispatched first, in one process, including JSON parsing, the non-finite-number check and the date check;
   - 4.1 to 4.8 s with the same work split over 4 worker processes.

   The cost is jsonschema's per-field descent (about 4 µs per property). One process therefore cannot meet the 10 s target without weakening the schema (see question 2).
5. **Regex semantics.** jsonschema applies `pattern` with Python's `re.search`. Two differences from JSON Schema's ECMA-262 regular expressions matter here:
   - `^[a-z0-9-]+$` accepts `"clip-1\n"`, because Python's `$` also matches before a final newline;
   - `\d` accepts non-ASCII digits such as `١٢`.

   jsonschema's `integer` type also accepts `1.0`. All three were verified in the venv.
6. **CLI dispatcher.** `aqis_lab/__main__.py` maps command names to modules in `COMMANDS`. Registering `contracts` needs one new entry there (you approved `aqis_lab/__main__.py` for the change budget, session note 3). No existing test checks the exact contents of `COMMANDS`.
7. **Gate and hooks.** The compromise scan reads only `.py .sh .bash .yml .yaml .toml .cfg .ini .in` files, so `.json`/`.jsonl` fixtures are not scanned. `tests/aqis_lab/fixtures/**` is also covered by `ALLOW-PATTERNS-IN` in `docs/approvals/WP-0.0.md`. `tests/aqis_lab/conftest.py` already keeps `fixtures/` out of collection. Traceability (check f) needs every FR/NFR ID in PLAN.md, in a collected test name and in EVIDENCE.md, and every AT ID in PLAN.md and EVIDENCE.md.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.2-01 | Event log v1 schema as specified under "Event log v1" below: envelope, 10 event types with one payload sub-schema each, `clip_id` and `audio_time_s` rules; `validate_event(record)` | `aqis_lab/contracts/__init__.py`, `aqis_lab/contracts/schemas/event_log.v1.json`, `aqis_lab/contracts/validate.py`, `docs/contracts/EVENT_LOG.md`, fixtures `valid_events.jsonl`, `invalid_events.jsonl`, `invalid_events.expected.json`, `.gitignore` (see question 6) | none | `test_FR_0_2_01_schema_is_valid_draft_2020_12`, `test_FR_0_2_01_valid_fixture_covers_every_event_type`, `test_FR_0_2_01_valid_fixture_passes`, `test_FR_0_2_01_rejects_missing_required_field` (parametrised over every spec field and every payload field), `test_FR_0_2_01_rejects_wrong_type_or_enum` (parametrised per field), `test_FR_0_2_01_clip_id_null_only_for_run_level_events`, `test_FR_0_2_01_null_audio_time_needs_reason`, `test_FR_0_2_01_final_word_timings`, `test_FR_0_2_01_error_payload_fields`, `test_FR_0_2_01_rejects_unknown_field`, `test_FR_0_2_01_invalid_fixture_names_expected_pointers` | AT-0.2-01, AT-0.2-02 |
| FR-0.2-02 | Run card v1 schema as specified under "Run card v1" below; `validate_run_card(card)` also checks that `run_card_id` equals the ID computed by FR-0.2-05 | `aqis_lab/contracts/schemas/run_card.v1.json`, `docs/contracts/RUN_CARD.md`, fixtures `valid_run_card.json`, `invalid_run_card_*.json` | none | `test_FR_0_2_02_schema_is_valid_draft_2020_12`, `test_FR_0_2_02_valid_fixture_passes`, `test_FR_0_2_02_rejects_missing_required_field` (every top-level and nested field), `test_FR_0_2_02_rejects_wrong_type_or_enum` (including every `mode` and `platform` value outside the enums), `test_FR_0_2_02_model_needs_version_or_checksum`, `test_FR_0_2_02_processing_keeps_step_order_per_path`, `test_FR_0_2_02_rejects_run_card_id_mismatch`, `test_FR_0_2_02_rejects_unknown_field` | AT-0.2-01 |
| FR-0.2-03 | Pack manifest v1 schema as specified under "Pack manifest v1" below; `validate_manifest(manifest)` adds the checks JSON Schema cannot express (unique `clip_id`, unique archive names, each clip's `archive` listed in `archives[]`) | `aqis_lab/contracts/schemas/pack_manifest.v1.json`, `docs/contracts/PACK_MANIFEST.md`, fixtures `valid_manifest.json`, `invalid_manifest_*.json` | none | `test_FR_0_2_03_schema_is_valid_draft_2020_12`, `test_FR_0_2_03_valid_fixture_passes`, `test_FR_0_2_03_rejects_missing_required_field` (every manifest, clip and archive field), `test_FR_0_2_03_rejects_wrong_type_or_enum`, `test_FR_0_2_03_version_must_be_semver`, `test_FR_0_2_03_owner_and_campaign_clips_need_consent_ref`, `test_FR_0_2_03_rejects_duplicate_clip_id`, `test_FR_0_2_03_rejects_duplicate_archive_name`, `test_FR_0_2_03_clip_archive_must_be_listed`, `test_FR_0_2_03_rejects_unsafe_member_path`, `test_FR_0_2_03_rejects_unknown_field` | AT-0.2-01 |
| FR-0.2-04 | `ContractValidationError` carries every failing field as `(pointer, message)` pairs (RFC 6901 escaping; see "Validators"); loaders reject non-JSON, NaN/Infinity, numbers that overflow to infinity and duplicate keys; `python -m aqis_lab contracts validate <file> --kind event\|run_card\|manifest` (events as JSON Lines, one record per line; run card and manifest as one JSON document) prints one report line per record and a summary; exit 0 all valid, 1 any invalid or no records, 2 usage or unreadable file | `aqis_lab/commands/contracts.py` | `aqis_lab/__main__.py`: `COMMANDS` (one entry added) and the module docstring's CHANGE LOG (one line added); nothing else | `test_FR_0_2_04_error_names_every_failing_pointer`, `test_FR_0_2_04_pointer_escapes_tilde_and_slash`, `test_FR_0_2_04_missing_field_pointer_names_the_field`, `test_FR_0_2_04_rejects_nan_infinity_and_overflow`, `test_FR_0_2_04_rejects_duplicate_keys`, `test_FR_0_2_04_rejects_integer_written_as_float`, `test_FR_0_2_04_patterns_reject_trailing_newline_and_non_ascii_digits`, `test_FR_0_2_04_cli_valid_events_exit_0`, `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields`, `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails` (first, middle and last line; must-catch 6), `test_FR_0_2_04_cli_unparsable_and_blank_lines_are_invalid_records`, `test_FR_0_2_04_cli_empty_file_fails`, `test_FR_0_2_04_cli_run_card_and_manifest_kinds`, `test_FR_0_2_04_cli_missing_file_exit_2`, `test_FR_0_2_04_cli_listed_by_dispatcher`, `test_FR_0_2_04_dispatch_matches_full_schema_on_all_fixtures`, `test_FR_0_2_04_worker_pool_report_identical_to_single_process` (only if question 2 is accepted), `test_FR_0_2_04_seq_counts_from_zero_per_run` (only if question 5 is accepted) | AT-0.2-02 |
| FR-0.2-05 | `canonical_json(value) -> bytes`: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` encoded as UTF-8; rejects non-string keys, non-JSON types (tuple, set, bytes, custom objects), NaN/Infinity and unencodable strings with `CanonicalJSONError`. `compute_run_card_id(card)`: SHA-256 hex of the canonical card without `run_card_id`, `created_utc` and `notes`. `sha256_canonical(value)` for other content IDs (used for `pack.sha256`, see decision 7) | `aqis_lab/contracts/canonical.py` | none | `test_FR_0_2_05_canonical_bytes_match_definition` (a hand-written byte literal, including non-ASCII text, nesting and number forms), `test_FR_0_2_05_key_order_does_not_change_bytes`, `test_FR_0_2_05_run_card_id_computed_independently` (the test's own recursive encoder plus `hashlib`; no call into `canonical.py`), `test_FR_0_2_05_run_card_id_ignores_only_the_three_excluded_fields`, `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json` | AT-0.2-01 |
| FR-0.2-06 | `$id` = `urn:aqis-lab:contracts:<kind>:<major>.<minor>`, which equals the schema's `schema_version` constant; before schema validation, `schema_version` is read and checked, so an unknown major (or a newer minor, decision 1) raises `UnsupportedSchemaVersionError` with a clear message at `/schema_version`; each contract document has a "Versioning and change policy" section | (in the three schemas, `validate.py` and the three documents) | none | `test_FR_0_2_06_schema_ids_carry_version`, `test_FR_0_2_06_rejects_unknown_major_version` (all three kinds; major 0, 2 and 10), `test_FR_0_2_06_rejects_newer_minor_version`, `test_FR_0_2_06_rejects_malformed_schema_version`, `test_FR_0_2_06_documents_describe_change_policy` | AT-0.2-01 |
| FR-0.2-07 | Each document lists its fields in tables whose first column is the field path (notation under "Documents"). A test-only schema walker (resolves `$ref`, follows `properties`, `items` and the per-type payload branches) and a test-only document parser produce the two field sets, which must be equal | (in the three documents) | none | `test_FR_0_2_07_documents_and_schemas_list_same_fields` (parametrised per kind), `test_FR_0_2_07_comparison_detects_missing_and_extra_fields` (on edited copies, so the check cannot be empty) | AT-0.2-01 |
| NFR-0.2-01 | See question 2. Recommended: bulk validation (the CLI and `validate_event_lines`) splits a file over worker processes, keeping per-record results and order identical to one process | (in `validate.py`, `commands/contracts.py`) | none | `test_NFR_0_2_01_validates_100k_events_under_10s` (marked `slow`: runs the CLI on a generated 100,000-event file covering every event type, requires exit 0, 100,000 OK lines and a wall time under 10 s) | `.venv/bin/python -m pytest tests/aqis_lab -q -m slow -k NFR_0_2_01` |
| NFR-0.2-02 | `aqis_lab/contracts/` and `aqis_lab/commands/contracts.py` import only the standard library, `aqis_lab` and `jsonschema`; no compiled or non-Python files in `aqis_lab/contracts/` other than the JSON schemas | — | none | `test_NFR_0_2_02_contracts_code_is_pure_python_with_pinned_jsonschema` (AST import scan; `jsonschema` exact pin with hashes in `phase0.txt`; file-type scan) | AT-0.2-01 |
| AT-0.2-01 | Run as written | — | — | all of the above | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` |
| AT-0.2-02 | Run as written, both files | — | — | `test_FR_0_2_04_cli_*` | `.venv/bin/python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/valid_events.jsonl --kind event` (exit 0) and the same with `invalid_events.jsonl` (exit 1, names the failing fields) |
| AT-0.2-03 | Run as written after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.2` |

**Change budget for existing files** (nothing else that already exists is touched):
- `aqis_lab/__main__.py`: add the `"contracts"` entry to `COMMANDS`, and one CHANGE LOG line in the module docstring. `build_parser` and `main` stay byte-identical. The CAP-CLI-001 behaviour is unchanged, so its registry row stays as it is.
- `docs/capabilities/REGISTRY.md`: new rows appended; existing rows byte-identical.
- `docs/progress/STATUS.md`: the WP-0.2 row only.
- `docs/progress/BLOCKERS.md`: append-only, and only if I get blocked. `docs/progress/DEBT.md`: rows added only if an audit finding is accepted as debt.
- No GUARDED or NEVER path changes, so no `ALLOW-EDIT` is needed.

**New files**: those in the table, plus these:
- `docs/progress/WP-0.2/EVIDENCE.md`.
- Test modules `tests/aqis_lab/test_aqis_contracts_event_log.py`, `test_aqis_contracts_run_card.py`, `test_aqis_contracts_manifest.py`, `test_aqis_contracts_validate.py` (FR-0.2-04 API), `test_aqis_contracts_cli.py`, `test_aqis_contracts_canonical.py`, `test_aqis_contracts_versioning.py`, `test_aqis_contracts_docs.py` and `test_aqis_contracts_nfr.py`. The `test_aqis_` prefix keeps basenames unique across the repository (FR-0.0-04).
- Registry rows, all ACTIVE and introduced by WP-0.2:
  - CAP-CONTRACTS-001: event log v1 schema and `validate_event`.
  - CAP-CONTRACTS-002: run card v1 schema and `validate_run_card`, including the ID check.
  - CAP-CONTRACTS-003: pack manifest v1 schema and `validate_manifest`, including the cross-record checks.
  - CAP-CONTRACTS-004: canonical JSON and content IDs (`canonical.py`).
  - CAP-CONTRACTS-005: schema versioning and version rejection.
  - CAP-CONTRACTS-006: the `contracts validate` command (`aqis_lab/commands/contracts.py`).
  - CAP-DOC-002: the contract documents, kept identical to the schemas.

## Design details

Field names that the spec gives are used exactly. Where the spec describes a group in words, such as "`pack` (manifest ID, version, SHA-256)", I chose the member names below. Your approval of this plan fixes them. Rows marked **decision** or **question** are not in the spec.

### Common rules for all three contracts
- JSON Schema 2020-12 (`"$schema": "https://json-schema.org/draft/2020-12/schema"`). Every object is closed (`additionalProperties: false`), so misspelt fields are rejected. The only open objects are `model.settings`, processing-step `params` and clip `recipe`.
- Every field listed in the spec is **required to be present**. Fields that may be empty use `null`, never omission, except `audio_time_reason` and the optional `words` of a `final` payload.
- Formats:
  - IDs (`clip_id`, `manifest_id`, `source`, `split`): lowercase letters, digits and hyphens (Phase 0 convention).
  - SHA-256 values: 64 lowercase hex characters.
  - UTC timestamps: `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, with a fraction of 1 to 9 digits and a real calendar date and time. The pattern is in the schema, and the validator checks the date through a `date-time` format checker.
- Portable regular expressions (finding 5): patterns use ASCII classes (`[0-9]`, `[a-z]`), never `\d` or `\w`, and end in `$(?!\n)`, which means "end of text" in both ECMA-262 and Python.
- Strict numbers (decision 2): the validator's `integer` type accepts only JSON integers written without a fraction or exponent (`5`, not `5.0` or `5e0`). NaN, Infinity and numbers that overflow to infinity are rejected everywhere, each at its own pointer. This keeps canonical JSON, and therefore IDs, unambiguous.

### Event log v1 (`event_log.v1.json`, `$id` `urn:aqis-lab:contracts:event_log:1.0`)
| Field | Type and rule | Basis |
| --- | --- | --- |
| `schema_version` | `"1.0"` | spec |
| `run_id` | non-empty string without whitespace | spec (format: decision) |
| `run_card_id` | SHA-256 hex | spec |
| `seq` | integer ≥ 0 | spec |
| `component` | `vad`, `turn_end`, `live_stt`, `heavy_stt`, `emotion`, `filler`, `analyzer`, `fix`, `runner` | spec |
| `event_type` | `run_started`, `run_finished`, `clip_started`, `clip_finished`, `speech_start`, `speech_end`, `partial`, `final`, `timing_mark`, `error` | spec |
| `clip_id` | ID or null. Must be null for `run_started` and `run_finished`. Must be an ID for `clip_started`, `clip_finished`, `speech_start`, `speech_end`, `partial` and `final`. Either for `timing_mark` and `error`, where null marks a run-level event | spec; the split by type is decision 3 |
| `audio_time_s` | number ≥ 0, or null | spec |
| `audio_time_reason` | non-empty string; required when `audio_time_s` is null and not allowed otherwise | spec; "not allowed otherwise" is decision 4 |
| `wall_time_ns` | integer ≥ 0, from the monotonic clock | spec |
| `wall_clock_utc` | UTC timestamp | spec and Phase 0 conventions |
| `host_id` | non-empty string | spec |
| `payload` | object with the sub-schema of its `event_type` (table below) | spec |

Payload sub-schemas (question 3 covers the rows the spec leaves open):
| `event_type` | Payload fields | Basis |
| --- | --- | --- |
| `final` | `text` (string); optional `words`: array of `{word: non-empty string, start_s: number ≥ 0, end_s: number ≥ start_s}` | spec |
| `error` | `code` (non-empty string), `message` (non-empty string), `run_continues` (boolean) | spec |
| `partial` | `text` (string) | question 3 |
| `timing_mark` | `mark` (ID naming what is marked, such as `first-partial`) | question 3 |
| `run_finished` | `status`: `completed` or `failed` | question 3 |
| `run_started`, `clip_started`, `clip_finished`, `speech_start`, `speech_end` | no fields (`{}`); the envelope already carries run, clip and times | question 3 |

`end_s ≥ start_s` cannot be written in JSON Schema, so `validate_event` checks it and reports `/payload/words/<i>/end_s`.

### Run card v1 (`run_card.v1.json`, `$id` `urn:aqis-lab:contracts:run_card:1.0`)
| Field | Type and rule | Basis |
| --- | --- | --- |
| `schema_version` | `"1.0"` | question 1 (deviation D1) |
| `run_card_id` | SHA-256 hex, equal to `compute_run_card_id(card)` | spec FR-0.2-02 and FR-0.2-05 |
| `pack` | `{manifest_id: ID, version: semantic version, sha256: SHA-256 hex}`; null allowed only when `mode` is `human_session` | spec; nullability is question 3 |
| `model` | `{family: non-empty string, name: non-empty string, version: non-empty string or null, checksum: SHA-256 hex or null, settings: object}`; at least one of `version` and `checksum` is not null | spec ("version or checksum") |
| `processing` | `{vad: [step…], stt: [step…], emotion: [step…]}`, each an ordered array (possibly empty) of `{name: non-empty string, params: object}` | spec |
| `mode` | `batch`, `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay`, `human_session` | spec |
| `machine` | `{platform: cloud-vm, colab, kaggle or oracle; gpu: non-empty string or null; cpu_model, architecture, os: non-empty strings; python_version: X.Y.Z with an optional suffix}` | spec; the member names match what WP-0.5 FR-0.5-01 fills |
| `seed` | integer ≥ 0 | spec |
| `normaliser` | `{name: non-empty string, version: non-empty string}` or null | spec; nullability is question 3 |
| `lock` | `{file: repository-relative POSIX path without "..", sha256: SHA-256 hex}` | spec |
| `git` | `{commit: full 40- or 64-character lowercase hex, dirty: boolean}` | spec |
| `created_utc` | UTC timestamp | spec |
| `notes` | string (may be empty) | spec |

### Pack manifest v1 (`pack_manifest.v1.json`, `$id` `urn:aqis-lab:contracts:pack_manifest:1.0`)
| Field | Type and rule | Basis |
| --- | --- | --- |
| `schema_version` | `"1.0"` | question 1 (deviation D1) |
| `manifest_id` | ID (a stable pack name such as `smoke`; the pack's content is identified by `version` and its SHA-256) | spec |
| `version` | semantic version (semver.org 2.0.0 grammar, ASCII digits) | spec |
| `purpose` | non-empty string | spec |
| `created_utc` | UTC timestamp | spec |
| `clips[]` | at least one clip; `clip_id` unique | spec; uniqueness from the Phase 0 conventions |
| `clips[].clip_id` | ID | spec |
| `clips[].source` | ID; the values `owner` and `campaign` mark owner and campaign recordings | question 4 |
| `clips[].source_ref` | non-empty string | spec |
| `clips[].licence` | non-empty string | spec |
| `clips[].speaker_id` | non-empty string or null (null for non-speech clips such as noise, music and silence) | spec; nullability is question 3 |
| `clips[].consent_ref` | non-empty string or null; must be a string when `source` is `owner` or `campaign` | spec |
| `clips[].split` | ID | spec |
| `clips[].duration_s` | number > 0 | spec |
| `clips[].sample_rate_hz` | integer > 0 | spec |
| `clips[].channels` | integer ≥ 1 | spec |
| `clips[].sha256` | SHA-256 hex | spec |
| `clips[].archive` | archive file name, which must equal one `archives[].name` | spec; the reference check is decision 5 |
| `clips[].member_path` | relative POSIX path inside the archive: no leading `/`, no `..` or empty segment, no backslash | spec (format: decision 5) |
| `clips[].transcript` | string or null | spec |
| `clips[].recipe` | object or null; the members are not fixed in v1.0 (WP-0.4 FR-0.4-04 defines source clip IDs, SNR, seed and gains, added as a minor version) | spec |
| `clips[].tags[]` | array of unique non-empty strings (may be empty) | spec |
| `archives[]` | at least one; `name` unique | spec |
| `archives[].name` | file name without `/` | spec |
| `archives[].sha256` | SHA-256 hex | spec |
| `archives[].bytes` | integer ≥ 0 | spec |
| `archives[].n_members` | integer ≥ 0 | spec |

### Validators (`aqis_lab/contracts/validate.py`)
- **Public API**:
  - `validate_event(record)`, `validate_run_card(card)`, `validate_manifest(manifest)`: return `None` when the record is valid, otherwise raise `ContractValidationError`;
  - `load_json_document(path)` and `iter_json_lines(path)`: strict loaders;
  - `validate_event_lines(path)`: the bulk path used by the CLI.
- **Exceptions**:
  - `ContractValidationError(ValueError)` has `.kind`, `.errors` (a tuple of `FieldError(pointer, message)`, sorted by pointer) and `.pointers`. Its message lists every pointer with its reason.
  - `UnsupportedSchemaVersionError(ContractValidationError)` is raised for a rejected version.
  - `CanonicalJSONError(ValueError)` is raised by `canonical.py`.
- **Pointers** (RFC 6901, with `~` escaped as `~0` and `/` as `~1`):
  - a missing field is reported at the field itself, for example `/payload/text` or `/clips/3/sha256`, not at its parent;
  - an unexpected field is reported at that field;
  - a failing `oneOf`/`anyOf` branch is reported at its deepest error;
  - the whole record is the empty pointer, printed as `(document)`.
- **Order of checks**: (1) the record is a JSON object; (2) the `schema_version` check (FR-0.2-06); (3) the JSON Schema; (4) non-finite numbers; (5) the checks JSON Schema cannot express, listed in the tables above. All errors from steps 3 to 5 are collected and raised together.
- **Event type dispatch (speed)**: the schema file selects each event type's rules through `if`/`then` blocks. At load time the validator builds one validator per event type from the same file, with the other types' `if`/`then` blocks left out. An `if`/`then` without `else` whose `if` is false adds nothing, so the result is the same. Records with a missing or unknown `event_type` use the full schema. A test runs both paths on every valid and invalid fixture and on every generated mutation, and requires the same verdict and the same pointers.
- **Stream checks for event files**: see question 5.

### Command (`python -m aqis_lab contracts validate <file> --kind event|run_card|manifest [--workers N]`)
- Output: one line per record, then a summary:
  ```text
  line 1: OK
  line 7: INVALID /payload/text: 'text' is a required property
  line 7: INVALID /seq: -1 is less than the minimum of 0
  event: 25 records, 10 valid, 15 invalid
  ```
  Run cards and manifests report as `record 1`. A record with several failing fields gets one line per field.
- Loading rules:
  - non-UTF-8 text, invalid JSON, a blank line, a non-object value, NaN or Infinity literals and duplicate keys are each an INVALID record at `(document)`;
  - a file with no records exits 1;
  - a missing or unreadable file exits 2 with an `ERROR:` line.
- `--workers` exists only for question 2 (default: the usable CPUs from `os.process_cpu_count()`; `1` means in-process). The pool starts only for files with at least 5,000 records. If worker processes cannot start, the command exits 2 and names `--workers 1`; it never falls back silently.

### Canonical JSON and IDs (`aqis_lab/contracts/canonical.py`)
- `canonical_json` works as in the FR-0.2-05 row: sorted keys, `,` and `:` separators, raw UTF-8 (no `\u` escapes for non-ASCII), no NaN or Infinity. Only `dict` (string keys), `list`, `str`, `int`, `float`, `bool` and `None` are accepted, so nothing is converted silently.
- `compute_run_card_id(card)` hashes the canonical card without `run_card_id`, `created_utc` and `notes`. Any other field changes the ID, including `schema_version` if question 1 is accepted.

### Documents (`docs/contracts/*.md`)
- Each document has these sections: purpose, file format, a field table per object (path, type, required or nullable, meaning), rules across fields, a valid example, validating (the API and the command), and "Versioning and change policy".
- Path notation in the first column of the field tables:
  - JSON Pointer from the record root, with `*` for any array item: `/pack/manifest_id`, `/clips/*/sha256`, `/processing/vad/*/params`;
  - event payload fields sit in tables under the heading `### Payload: <event_type>`, with paths such as `/payload/text`.
- The FR-0.2-07 test compares these paths with the schema, both ways.

### Versioning and change policy (decision 1; documented in each contract document)
- `schema_version` is `"<major>.<minor>"`, and the `$id` carries the same `<major>.<minor>`. The file name carries the major version (`.v1.json`).
- **Minor** version: additions that every existing valid record survives. Examples: a new optional field, a new event type, a new enum value, or members defined inside a previously open object.
  - The v1 schema file always describes the newest v1 minor version and accepts every v1 minor version up to it.
  - A validator rejects a record whose minor version is newer than its own, with a clear "update aqis_lab" message, because it cannot judge fields it does not know.
- **Major** version: anything else, including a removed or renamed field, a changed type or meaning, a field that becomes required, a removed enum value, or a changed ID definition.
  - A new major version gets a new file (`.v2.json`), and the old file stays so that old records still validate.
  - Validators reject a major version they do not know, naming the major versions they support.
- The document, schema, fixtures and tests change in the same commit. The FR-0.2-07 test keeps the documents and the schemas equal.

### Must-catch proof (planned)
| # | Behaviour | Tests that must fail when it is broken |
| --- | --- | --- |
| 1 | Omitting each required field is rejected, naming it by JSON Pointer | `test_FR_0_2_01/02/03_rejects_missing_required_field`: the expected field lists are written in the test from the spec text, not read from the schemas |
| 2 | Wrong types and values outside enums are rejected | `test_FR_0_2_01/02/03_rejects_wrong_type_or_enum`, `test_FR_0_2_04_rejects_integer_written_as_float` |
| 3 | An unknown major version is rejected | `test_FR_0_2_06_rejects_unknown_major_version` |
| 4 | `run_card_id` equals the SHA-256 of the canonical card as defined, computed independently | `test_FR_0_2_05_run_card_id_computed_independently`, `test_FR_0_2_05_canonical_bytes_match_definition` |
| 5 | Documents and schemas list exactly the same fields | `test_FR_0_2_07_documents_and_schemas_list_same_fields`, `test_FR_0_2_07_comparison_detects_missing_and_extra_fields` |
| 6 | `contracts validate` exits non-zero on any invalid record in a JSON Lines file | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails` |

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to questions 1 to 7 below, as CONDITIONS in `docs/approvals/WP-0.2.md` (or "as recommended") | They fix record fields and behaviour that later WPs depend on | Before `/wp-build WP-0.2` |

No data, credentials, network hosts, Colab runs or Oracle runs are needed.

## Owner-run checks planned
None. The spec runs this WP on the cloud VM only. The code is pure Python on the pinned lock; CI (GitHub Actions, Ubuntu) runs the fast suite on a second machine.

## Risks and questions
1. **(Deviation D1) `schema_version` in run cards and pack manifests.** FR-0.2-06 requires validators to reject unknown major versions, but FR-0.2-02 and FR-0.2-03 give run cards and manifests no field that carries the version, so a validator cannot tell which version a record claims. I propose adding `schema_version` (`"1.0"`) as a required field of both, as the event log already has it. It is part of the `run_card_id` hash, because the FR-0.2-05 definition excludes only three fields. **Recommended: accept.** If you reject it, FR-0.2-06 can only be met for event logs, and I would stop and ask how to handle the other two.
2. **NFR-0.2-01 cannot be met in one process (finding 4).** With the pinned jsonschema, 100,000 events take 12 to 14 s in one process and 4 to 5 s with 4 worker processes. Options:
   - **(a) Recommended.** Bulk validation (the CLI and `validate_event_lines`) uses a worker-process pool for files of at least 5,000 records, with the same report and order as one process (a test proves it) and a `--workers` option. The NFR test times the CLI on a 100,000-event file. Single-record `validate_event` stays in-process (about 120 µs per event). On Colab's 2 vCPUs it would take about 8 to 9 s.
   - **(b)** Change the target, for example to under 20 s in one process.
   - **(c)** Drop rules from the schema to gain speed. Not recommended: it weakens validation.
3. **Fields the spec leaves open.** Please accept or change:
   - **(a)** The payloads of `partial` (`text`), `timing_mark` (`mark`) and `run_finished` (`status`: `completed`/`failed`), and empty payloads for the other five non-`final`, non-`error` types.
   - **(b)** Null allowed for `pack` only when `mode` is `human_session`: a live human session has no pack, so otherwise a record would need invented pack data.
   - **(c)** Null allowed for `normaliser`, for runs that produce no text, such as VAD.
   - **(d)** Null allowed for `speaker_id`, for non-speech clips.

   **Recommended: accept all four.** Anything more (for example word confidence in `final`, or recipe members) comes as a minor version in the WP that needs it.
4. **Which clips need `consent_ref`.** The spec says "required for owner and campaign recordings" but defines no field that says which clips those are. I propose that the `source` values `owner` and `campaign` mark them. WP-0.4 then uses `source: owner` for `data/owner_smoke/` clips. **Recommended: accept.**
5. **Per-run sequence check in `contracts validate --kind event`.** `seq` is a "per-run counter from 0", which no single record can show. Options:
   - **(a) Recommended.** The command also checks that, for each `run_id` in the file, `seq` runs 0, 1, 2, … in file order with no gap or repeat, and reports failures per record at `/seq`. This makes later WPs keep one counter per run, including across a resume in WP-0.5. `wall_time_ns` is not compared across records, because a monotonic clock is per process and host.
   - **(b)** Per-record checks only, as FR-0.2-04's wording can also be read.
6. **Committing the `.jsonl` fixtures (finding 3).** Options:
   - **(a) Recommended.** A new file `tests/aqis_lab/fixtures/contracts/.gitignore` containing `!*.jsonl` re-includes JSON Lines files in that folder only. It sits in a LAB-OWNED path and needs no approval.
   - **(b)** You add `!tests/aqis_lab/fixtures/contracts/*.jsonl` to the root `.gitignore`, or add `ALLOW-EDIT: .gitignore` for me to do it.
   - **(c)** I force-add the files (`git add -f`). Not recommended: a new fixture could silently be left out.
7. **NFR-0.2-02 "pure Python" reading.** The lab code will be pure Python, and its only third-party import is the pinned `jsonschema`. `jsonschema` itself depends on `rpds-py`, a compiled wheel that is already pinned with hashes for x86_64 and aarch64 in `phase0.txt` and installs on this VM, CI and Colab. **Please confirm that reading.** No stricter reading is possible with jsonschema 4.x.

**Design decisions made in this plan** (approving the plan accepts them; tell me to change any):
- **Decision 1:** the versioning policy above, including rejecting a newer minor version.
- **Decision 2:** strict integers and no non-finite numbers.
- **Decision 3:** the `clip_id` split by event type.
- **Decision 4:** `audio_time_reason` present only with a null `audio_time_s`.
- **Decision 5:** the manifest checks across records and the safe `member_path` rule.
- **Decision 6:** the `$id` form `urn:aqis-lab:contracts:<kind>:<major>.<minor>`.
- **Decision 7:** the run card's `pack.sha256` is the SHA-256 of the manifest's canonical JSON (the Phase 0 convention for content IDs), so formatting a manifest file does not change it.

**Other risks**:
- The NFR test is a timing test. Under option 2(a) the measured margin is about 2×. I will record five timed runs in EVIDENCE.md.
- Closed objects (`additionalProperties: false`) mean that every new field needs a minor version. This is the purpose of the change policy.

## Deviations
- **D1**: add `schema_version` to the run card and the pack manifest (question 1). This is the only proposed deviation from the spec's field lists. Everything marked "decision" or "question" in the tables above fills in something the spec leaves open; none of it contradicts the spec.
