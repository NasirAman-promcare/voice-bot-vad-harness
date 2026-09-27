# AUDIT — WP-0.2, round 3

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: 53d4be725c7007d2ea557c933b5fbf480a05bd66 · Previous audited commit: 39f2d71cc596ef50c508921d0de0596c08a4add2 · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 open (F01 fixed) · MAJOR: 1 (fixed 1, accepted as debt 0, open 0) · MINOR: 4 (fixed 2, accepted as debt 2, open 0)

All four fixes the owner ordered in round 2 are on the branch and hold up when checked:
- **F01 (CRITICAL, must-catch 2) is fixed.** Each of the four schema `type` removals now fails a named new test, and still leaves the round-1 contract tests green (`712 passed`). So the new tests are what protect these rules.
- **F02 (MAJOR, must-catch 6) is fixed.** CB6-2 now fails `test_FR_0_2_04_last_record_without_final_newline_is_validated` and `test_FR_0_2_04_cli_last_line_without_final_newline_fails`.
- F03 and F05 (MINOR) are fixed. F04 and F06 are recorded as DEBT-006 and DEBT-007 (target WP-0.9), as the approval's round-2 condition says.

The fixes add tests only. The two production modules changed only in their header docstrings: the code after each docstring is byte-identical to `39f2d71`, and the ASTs without the docstring are equal. No schema, fixture, contract document or existing test changed. The full must-catch proof, redone with my own harness, has no real gap left. 211 of 223 breaks fail a named test. The other 12 are equivalent: across 8,112 wrong values, none is accepted that the unmodified code rejects. This round has no new findings.

## Scope of this audit
Re-audit, round 3, as the protocol defines it:
1. **The six round-2 findings.** Each was re-checked; its status is in the Findings table.
2. **Items A1 to A15 on the diff `39f2d71..53d4be7`.** It has five commits:
   - `beff403`: the round-2 audit report and the STATUS row.
   - `cd7c917`: a merge of `origin/main` that brings in the approval's round-2 condition.
   - `5fbe983`: the fixes.
   - `53d4be7`: EVIDENCE and STATUS only.

   Changed files: `tests/aqis_lab/test_aqis_contracts_gaps.py` (new), the header docstrings of `aqis_lab/contracts/validate.py` and `aqis_lab/commands/contracts.py`, `docs/capabilities/REGISTRY.md`, `docs/progress/DEBT.md`, `docs/progress/STATUS.md`, `docs/progress/WP-0.2/{AUDIT,EVIDENCE,FIXES}.md`, and `docs/approvals/WP-0.2.md` (from `main`, identical to `main`). Unchanged code that passed earlier rounds was not searched again.
3. **Full suites, the gate, CI on `53d4be7`, AT-0.2-01 to AT-0.2-03, and the complete must-catch proof (A6).**

**Method.** The breaks ran in five throwaway git clones of `53d4be7`, `/tmp/aqis-audit-wp02-r3/c1` to `c5`, with `origin/main` set to `e3439be`.
- The clones use the project `.venv` through a symlink, which is excluded in each clone's `.git/info/exclude`. Bytecode writing was off (`PYTHONDONTWRITEBYTECODE=1`).
- `aqis_lab` imports from the clone (`/tmp/aqis-audit-wp02-r3/c1/aqis_lab/contracts/validate.py`).
- Baseline in each of `c1` to `c4`: `998 passed, 9 deselected`, with a clean `git status`.
- Control: re-serialising all three schemas with no content change gives `758 passed, 1 deselected` for the contract tests and `998 passed, 9 deselected` for the whole fast suite. The rewriting method alone breaks nothing.
- After each break, every changed file was restored and compared byte for byte against the saved bytes, and `git status --porcelain` had to be empty. At the end, all five clones and the working tree are clean.
- Scripts: `/tmp/aqis-audit-wp02-r3/harness.py` (runner), `make_code_breaks.py` and `code_breaks.json` (code and document breaks), `probe.py` and `equiv.py` (equivalence probe). Results: `breaks.jsonl`, `equiv.json`.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `git show origin/main:docs/progress/STATUS.md`: WP-0.0 `MERGED`. Branch `claude/beautiful-dijkstra-8pbq6l`, not `main`. `origin/main` = `e3439be`. `docs/approvals/WP-0.2.md` on `main`: `STATUS: APPROVED`, `- Questions 1-7: as recommended in PLAN.md.`, `- Round 2: fix WP-0.2-F01, F02, F03 and F05. WP-0.2-F04 and WP-0.2-F06 are accepted as debt in docs/progress/DEBT.md (target WP-0.9).` `git diff origin/main HEAD -- docs/approvals/WP-0.2.md` is empty. |
| A2 Requirement coverage | PASS | `pytest --collect-only`: `1007 tests collected` (round 2: 961; +46 in the new file). Tests named after each ID: FR_0_2_01 284, FR_0_2_02 187, FR_0_2_03 172, FR_0_2_04 35, FR_0_2_05 15, FR_0_2_06 60, FR_0_2_07 4, NFR_0_2_01 1, NFR_0_2_02 1. New file: `…rejects_non_object_word_items` 14, `…rejects_wrong_clip_id_type_on_either_level_events` 12, `…human_session_pack_must_be_object_or_null` 7, `…rejects_non_object_archive_items` 7, `…cli_documents_without_final_newline` 4, `…cli_last_line_without_final_newline_fails` 1, `…last_record_without_final_newline_is_validated` 1. `EVIDENCE.md` lists each under "Round 2 fixes". |
| A3 Acceptance commands | PASS | AT-0.2-01: `998 passed, 9 deselected in 63.65s`, exit 0. AT-0.2-02: the valid fixture gives `event: 23 records, 23 valid, 0 invalid`, exit 0. The invalid fixture gives `event: 96 records, 2 valid, 94 invalid`, exit 1, and names each field, for example `line 4: INVALID /seq: required field is missing`. AT-0.2-03: `aqis-audit-gate: base origin/main (merge-base e3439be0c320), head 53d4be725c70, approvals origin/main e3439be0c320, wp WP-0.2` … `Findings: 0` / `0 findings: OK (0.2 s)`, exit 0. |
| A4 Test suites and CI | PASS | Fast suite (working tree): `998 passed, 9 deselected in 63.65s`. Slow suite (`-m "slow and not gpu and not colab and not oracle"`): `9 passed, 998 deselected in 100.98s`; NFR-0.2-01 call `6.43s` (limit 10 s). CI on `53d4be7`, from the GitHub API: push run 36314635128 (#142) and pull_request run 36314638513 (#143), jobs `lab` and `harness-regression` all `success`. Every `lab` step succeeded, and the WP ID step is skipped on push, by design. I could not read the job log text: the proxy denied `productionresultssa3.blob.core.windows.net`. Step conclusions only. |
| A5 Test integrity | PASS | `git diff --name-status 39f2d71..HEAD -- tests/`: `A tests/aqis_lab/test_aqis_contracts_gaps.py` only. No existing test or fixture changed. In the WP diff there is no `skip`, `xfail`, `skipif`, `importorskip` or `audit-allow`. The only marker is the spec-required `@pytest.mark.slow` on NFR-0.2-01. The new file has 21 `assert` statements. Each test also checks that the valid neighbours (`null` and an ID, `pack` null or an object, a valid file without a final newline) are accepted, so they cannot pass by rejecting everything. `pointers()` (`aqis_contracts_testutil.py:81`) returns the empty set only when the validator returns `None`, and it checks that each pointer is in the message. |
| A6 Must-catch proof | PASS | 223 breaks: 178 schema-keyword removals and 45 code and document breaks (tables below). 211 fail a named test. The 12 survivors are all equivalent, shown by the probe. The four F01 breaks and CB6-2 now each fail a named new test. Re-run without `-x`, the round-1 contract files still give `712 passed` under each of the five, and the new file gives `12 failed`, `14 failed`, `7 failed`, `7 failed` and `2 failed`, the same as the builder's EVIDENCE table. |
| A7 Compromise scan | PASS | Gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`, `Findings: 0`. A grep of the WP diff (`tests/`, `aqis_lab/`) for stub, placeholder, fake, broad-except and skip words finds nothing. No production code changed in this round (AST comparison: code after the module docstring byte-identical to `39f2d71` in both changed modules). |
| A8 Scope diff | PASS | The changes match the change budget in `FIXES.md`: the new test file; header docstrings and CHANGE LOG lines in `validate.py` and `commands/contracts.py`; test-cell additions and two new rows in `REGISTRY.md`; two DEBT rows; EVIDENCE, FIXES and STATUS. No NEVER or GUARDED path changed: `git diff origin/main HEAD -- docs/approvals docs/specs docs/process .claude CLAUDE.md requirements` is empty, and every test file is under the LAB-OWNED `tests/aqis_lab/**`. `beff403`'s `AUDIT.md` is untouched since (`git diff beff403 HEAD -- docs/progress/WP-0.2/AUDIT.md` is empty). PR 2 is open, head `53d4be7`, `mergeable_state: clean`. |
| A9 Capabilities | PASS | Registry: 32 rows before, 34 after. None removed; CAP-DOC-003 and CAP-DOC-004 added. In CAP-CONTRACTS-001, 002, 003, 006 and 007, the old test list is a prefix of the new one. CAP-DOC-002's Functions cell only gained text. The header lists match the registry: the fast suite passes `test_FR_0_0_08_module_headers_match_registry`, and break A15-01 shows the check is live. The gate's `module_exists` (`tools/audit/gate.py:534`) takes one existing file per Module cell, so adding two rows is a sound way to fix F05. Break A15-02 shows the new rows are parsed and their test names checked. |
| A10 Contracts | PASS | Fixtures unchanged since round 2 (`git diff 39f2d71..HEAD -- tests/aqis_lab/fixtures aqis_lab/contracts/schemas docs/contracts` is empty). Recomputed with the standard library: `run_card_id` of `valid_run_card.json` matches its definition (`92544853e82e…`), and `pack.sha256` equals the SHA-256 of the canonical `valid_manifest.json`. All 23 events carry the `run_card_id`, and every non-null event `clip_id` is a manifest clip. The fixture covers all 10 event types. |
| A11 Environment parity | PASS | The new test uses `sys.executable` and `ROOT` and contains no absolute path (grep for `/home`, `/tmp`, `/root` finds nothing). Bootstrap: `OK: .venv ready: Python 3.13.12, lock sha256 5c9a64eb…`. The Colab probe records `3.13.15`, so major.minor match. No lock or CI workflow changed. The spec runs this WP on the cloud VM only, so no owner-run checks are needed. |
| A12 Reproducibility and traceability | PASS | Unchanged since round 1. CB4-1 to CB4-9 confirm that the canonical-bytes and `run_card_id` tests protect determinism. |
| A13 Errors and logging | PASS | Unchanged since round 1. The untested `WorkerPoolError` path (F04) is now DEBT-006. |
| A14 Documentation, licences, data | PASS | F03 fixed. `EVIDENCE.md` now says run #123 (36308454812) on `4f752e0` failed and runs #124 to #130 were green. The API agrees: #123 `failure`; #124 `b3e8a03`, #125 `5939fe7`, #126 `cb96d44`, #127 `2527f84`, #128 `616fddd`, #129 `0a4e2ef` and #130 `3459ffa` all `success`. The round-2 CI table (runs 36314464969 and 36314461977 on `5fbe983`, all `success`) matches the API. `DEBT.md` has DEBT-006 (F04) and DEBT-007 (F06), target WP-0.9, citing the approval at `e3439be`. |
| A15 Exploratory breaks | PASS | Since `39f2d71`, production changed only in its header docstrings. 2 breaks made there and in the new registry rows; both caught (table below). |

## Must-catch proof (A6)
**Schema breaks.** One keyword is removed per run across all three schemas: each entry of every `required` list, and every `type` and `enum` keyword. The walker visits schema positions only (`properties`, `$defs`, `items`, `not`, `then`, `else`, `allOf` and similar), so a property named `type` is never taken for a keyword. `if` selectors are skipped, because they choose rules rather than state them. This is the same scope as round 2, and gives the same counts: required 23, 38 and 27; type and enum 34, 32 and 24. Each break runs the 758 contract tests with `-x`. Each survivor then runs the whole fast suite.

**Code and document breaks.** These are exact text substitutions, each checked to match exactly once, and each result checked to parse (Python compiles, JSON loads).

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Omitting each required field is rejected, naming it by JSON Pointer | Every entry of every `required` list removed, one per run (88: event 23, run card 38, manifest 27) | For example the `schema_is_valid_draft_2020_12` tests, which compare the top-level `required` list with the spec; `test_FR_0_2_0N_rejects_missing_required_field[…]` for nested fields; `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` for payload fields | 88/88 caught |
| 1 | CB1-1 missing field reported at its parent's pointer | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 1 | CB1-2 only the first of several missing fields reported | `test_FR_0_2_01_error_payload_fields` | Caught |
| 1 | CB1-3 pointer escapes applied in the wrong order | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 1 | CB1-4 missing `schema_version` reported at the document pointer | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 Wrong types and values outside enums are rejected | Every `type` and `enum` keyword removed, one per run (90: event 34, run card 32, manifest 24) | For example `test_FR_0_2_01_rejects_wrong_type_or_enum[final-path70-1]` (`$defs/word/properties/word`); and CLI tests for the run-level and clip-level `clip_id` rules | 78 caught. 12 survive the whole fast suite (`998 passed, 9 deselected` each), and all 12 are equivalent (probe below). **No real gap** |
| 2 | F01-1: `properties/clip_id` `type` removed (`event_log.v1.json`) | `test_FR_0_2_01_rejects_wrong_clip_id_type_on_either_level_events[7-timing_mark]` | Caught (round 2: survived) |
| 2 | F01-2: `$defs/word` `type` removed | `test_FR_0_2_01_rejects_non_object_word_items[1-0]` | Caught (round 2: survived) |
| 2 | F01-3: `properties/pack` `type` removed (`run_card.v1.json`) | `test_FR_0_2_02_human_session_pack_must_be_object_or_null[1]` | Caught (round 2: survived) |
| 2 | F01-4: `$defs/archive` `type` removed (`pack_manifest.v1.json`) | `test_FR_0_2_03_rejects_non_object_archive_items[1]` | Caught (round 2: survived) |
| 2 | CB2-1 strict `integer` accepts booleans | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-2 default `integer` type (accepts `1.0`) | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-3 calendar check of UTC timestamps removed | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-4 validators built without the format checker | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-5 per-type event validators lose their payload branch | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-6 "must not be null" errors dropped (model `version` and `checksum` both null) | `test_FR_0_2_02_model_needs_version_or_checksum` | Caught |
| 2 | CB2-7 non-finite numbers accepted by the validator | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 3 An unknown major schema version is rejected | CB3-1 `SUPPORTED_VERSIONS` claims major 2 for events | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | CB3-2 major version always read as 1 | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | CB3-3, CB3-4, CB3-5 version check skipped for events, run cards, manifests (one per run) | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]`, `[2.0-2-run_card]`, `[2.0-2-manifest]` | Caught (3/3) |
| 3 | CB3-6 version check removed and the event `schema_version` enum widened to `type: string` | `test_FR_0_2_06_schema_ids_carry_version[event]` | Caught |
| 4 `run_card_id` is the SHA-256 of the canonical card as defined, computed independently | CB4-1 `machine` also excluded; CB4-2 `notes` not excluded; CB4-3 `created_utc` not excluded | `test_FR_0_2_05_run_card_id_computed_independently` (each) | Caught (3/3) |
| 4 | CB4-4 keys not sorted; CB4-5 spaces after separators; CB4-6 non-ASCII escaped; CB4-7 SHA3-256 | `test_FR_0_2_05_canonical_bytes_match_definition` (each) | Caught (4/4) |
| 4 | CB4-8 `validate_run_card` never compares `run_card_id` | `test_FR_0_2_04_cli_run_card_and_manifest_kinds` | Caught |
| 4 | CB4-9 canonical JSON accepts NaN and Infinity | `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json[nan-]` | Caught |
| 5 Documents and schemas list the same fields | CB5-1 `/seed` row removed from `RUN_CARD.md`; CB5-5 undocumented `git.branch` added to the run card schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` (each) | Caught (2/2) |
| 5 | CB5-2 row `/payload/confidence` (not in the schema) added under `final`; CB5-4 `/host_id` row removed; CB5-7 `timing_mark` payload heading renamed | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` (each) | Caught (3/3) |
| 5 | CB5-3 `/clips/*/tags` renamed `/clips/*/labels`; CB5-6 undocumented `archives[].compression` added to the schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` (each) | Caught (2/2) |
| 5 | CB5-8 `payload_final.words` removed from the schema but still documented | `test_FR_0_2_04_cli_valid_events_exit_0` first (the valid fixture has word timings) | Caught |
| 6 `contracts validate` exits non-zero on any invalid record in a JSON Lines file | CB6-1 exit 0 when exactly one record is invalid; CB6-9 exit decided by the last record only | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[first]` (each) | Caught (2/2) |
| 6 | CB6-2 `split_json_lines` always drops the last line (F02 re-check) | `test_FR_0_2_04_last_record_without_final_newline_is_validated`; without `-x`, also `test_FR_0_2_04_cli_last_line_without_final_newline_fails` | **Caught (round 2: survived)** |
| 6 | CB6-3 blank lines dropped; CB6-4 unparsable line treated as valid; CB6-6 last report not counted; CB6-7 per-run `seq` errors dropped; CB6-8 schema errors of a parsed line discarded | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` (each) | Caught (5/5) |
| 6 | CB6-5 worker pool drops the last chunk | `test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files` | Caught |
| 6 | CB6-10 file with no records exits 0 | `test_FR_0_2_04_cli_empty_file_fails` | Caught |
| 6 | CB6-11 invalid run card or manifest document reported valid | `test_FR_0_2_04_cli_run_card_and_manifest_kinds` | Caught |

**How the 12 survivors were judged.** My probe (`/tmp/aqis-audit-wp02-r3/probe.py`) puts each of 13 wrong values into the valid fixtures. The values are `7`, `1.5`, `true`, `false`, `null`, `"s"`, `""`, `[]`, `["x"]`, `[1]`, `[null]`, `{}` and `{"a": 1}`. They go at every location: the record root, every object member and every array item.
- The record variants are all 23 events; `timing_mark` and `error` on the other level as well; the run card with its own `mode` and with `human_session`; and the manifest.
- Run cards are re-hashed after each change, so an ID mismatch cannot hide a gap.
- That makes 8,112 wrong values. The unmodified code accepts 662, all of them allowed (for example `"s"` for a string field, or `null` for `speaker_id`).

For each survivor, I compared the set of accepted values with the baseline:

- **All 12 accept nothing new and reject nothing new.**
  - The root `type: object` of each schema: the code rejects a non-object before the schema runs.
  - The event `properties/payload` type, and the types of `payload_empty`, `payload_run_finished`, `payload_partial`, `payload_final`, `payload_timing_mark` and `payload_error`: the other of the two object checks still applies.
  - The run card's `not {type: null}` on `model.version` and on `model.checksum`. It becomes `not {}`, which still rejects both being null. The fixture has `checksum: null`, so the probe covered the both-null case. A direct check also gives the same two pointers (`/model/checksum`, `/model/version`); only the message changes, from "must not be null here" to "field is not allowed here", and the `Rule:` text is kept.
- **The probe is sensitive.** On the four F01 breaks it finds 140, 28, 10 and 25 newly accepted values. Those four breaks are now caught by tests.

## Exploratory breaks (A15, at most 10)
| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| A15-01 `test_FR_0_2_01_rejects_non_object_word_items` removed from the CAP-CONTRACTS-001 header line only (the registry still lists it) | `aqis_lab/contracts/validate.py` module header (changed in `5fbe983`) | No: `test_FR_0_0_08_module_headers_match_registry` fails. The gate alone reports `0 findings`; the header check lives in the test | — |
| A15-02 CAP-DOC-004's test cell names a test that does not exist | `docs/capabilities/REGISTRY.md:40` (row added in `5fbe983`) | No: the gate reports `[E3] MAJOR: CAP-DOC-004: names tests that do not exist`, and `test_FR_0_0_08_repository_registry_is_consistent` fails | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.2-F01 | CRITICAL | A6 (must-catch 2) | **Fixed.** The four schema type rules without a test now each have one: `clip_id` on `timing_mark` and `error`, non-object `payload.words` items, a non-object `pack` with `mode: human_session`, and non-object `archives` items | Each of the four `type` removals leaves the round-1 contract files green (`712 passed, 1 deselected`) and fails the matching new test: `12 failed`, `14 failed`, `7 failed`, `7 failed` in `test_aqis_contracts_gaps.py`. All 46 new cases pass on the unmodified code | Closed |
| WP-0.2-F02 | MAJOR | A15 in round 1 (inside must-catch 6) | **Fixed.** `validate_event_lines` and `contracts validate` are now tested on a file whose invalid last record has no final newline, and on a valid file without one. Run card and manifest documents without a final newline are also tested | CB6-2: round-1 files `712 passed`; new file `2 failed, 44 passed`, failing `test_FR_0_2_04_cli_last_line_without_final_newline_fails` and `test_FR_0_2_04_last_record_without_final_newline_is_validated` | Closed |
| WP-0.2-F03 | MINOR | A14 / A4 | **Fixed.** The CI paragraph in `EVIDENCE.md` now lists run #123 on `4f752e0` as failed and runs #124 to #130 as green | GitHub API run list for the branch: #123 `failure`, #124 to #130 `success` on the seven listed commits | Closed |
| WP-0.2-F04 | MINOR | A13 | **Accepted as debt: DEBT-006.** The `WorkerPoolError` path (exit 2, "rerun with --workers 1") still has no test | `docs/progress/DEBT.md` DEBT-006, target WP-0.9, citing `docs/approvals/WP-0.2.md` at `e3439be` | Accept as debt, target WP-0.9 (done) |
| WP-0.2-F05 | MINOR | A9 | **Fixed.** A Module cell must name one existing file (`module_exists`, `tools/audit/gate.py:534`). So instead of listing three files in one cell, `RUN_CARD.md` and `PACK_MANIFEST.md` have their own rows, CAP-DOC-003 and CAP-DOC-004, with the same tests. CAP-DOC-002's Functions cell points to them | `docs/capabilities/REGISTRY.md:38-40`; the gate reports `0 findings`; A15-02 shows the new rows are checked | Closed |
| WP-0.2-F06 | MINOR | A14 | **Accepted as debt: DEBT-007.** A wrong-typed `clip_id` on a clip-level event still gives two report lines at the same pointer | `docs/progress/DEBT.md` DEBT-007, target WP-0.9, citing the approval at `e3439be` | Accept as debt, target WP-0.9 (done) |

No new findings in round 3.

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 4 | F01 (behaviour 2), F02 (behaviour 6) |
| 2 | 1 | 1 | 4 | F01 (behaviour 2), F02 (behaviour 6); no fix attempted |
| 3 | 0 open (F01 fixed) | 0 open (F02 fixed) | 0 open (F03, F05 fixed; F04, F06 accepted as debt) | None |

No open finding sits inside the must-catch list, and nothing new was found. The verdict is PASS.

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- Approvals used: `docs/approvals/WP-0.2.md` on `main` at `e3439be`:
  - "Questions 1-7: as recommended in PLAN.md";
  - "Round 2: fix WP-0.2-F01, F02, F03 and F05. WP-0.2-F04 and WP-0.2-F06 are accepted as debt in docs/progress/DEBT.md (target WP-0.9)".
- Debt accepted so far: WP-0.2-F04 (DEBT-006) and WP-0.2-F06 (DEBT-007), both MINOR, target WP-0.9. No MAJOR finding was accepted as debt.
- Owner-run checks still pending: None. The spec runs this WP on the cloud VM only.
- Note: CI job logs could not be read from here, because the proxy denied `productionresultssa3.blob.core.windows.net`. Job and step conclusions were read through the GitHub API, and all are `success`.
- Next step: review and merge PR 2 (https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/2).
