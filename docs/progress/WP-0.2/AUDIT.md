# AUDIT — WP-0.2, round 2

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: 39f2d71cc596ef50c508921d0de0596c08a4add2 · Previous audited commit: 81b58f1c1637d760691f84c778727f0fd071f534 · Protocol: version 2

## Verdict: FAIL
CRITICAL: 1 · MAJOR: 1 (fixed 0, accepted as debt 0, open 1) · MINOR: 4 (open 2, accepted as debt 2)

**No fixes were made after round 1.** The branch head `39f2d71` is the round-1 audit commit. Since `81b58f1`, only two files have changed: `docs/progress/WP-0.2/AUDIT.md` (the round-1 report) and `docs/progress/STATUS.md` (the WP-0.2 row). No code, test, schema, fixture or contract document changed.

The owner's round-2 condition on `main` (`e3439be`) says: fix WP-0.2-F01, F02, F03 and F05; F04 and F06 are accepted as debt, target WP-0.9. None of the four fixes is on the branch, and `docs/progress/DEBT.md` has no rows yet for F04 or F06.

I re-ran everything myself and got the same result as round 1:
- **F01 (CRITICAL, must-catch 2)** is still open. Removing any one of four schema type rules leaves the whole fast suite green (`952 passed`). With those breaks in place, the validators accept 52 wrong-typed values that the unmodified code rejects.
- **F02 (MAJOR, inside must-catch 6)** is still open. If `split_json_lines` drops the last line unconditionally, the whole fast suite stays green (`952 passed`). With that break, `contracts validate` reports `event: 22 records, 22 valid, 0 invalid` with exit 0 for a 23-record file with no final newline and an invalid last record. The unmodified code gives `23 records, 22 valid, 1 invalid`, exit 1.

Everything else passes: the fast and slow suites, the gate, CI on `39f2d71`, the three acceptance commands, and the other 214 must-catch breaks (each caught or shown equivalent). Both blocking fixes need tests only.

## Scope of this audit
Re-audit, round 2, as the protocol defines it:
1. **The six round-1 findings.** Each was re-checked and has its status in the Findings table.
2. **Items A1 to A15 on the diff `81b58f1..39f2d71`.** That diff has two files, both records in `docs/progress/`. Code that passed round 1 and has not changed was not searched again. A15 has no new or changed code to break.
3. **Full suites, the gate, CI on `39f2d71`, AT-0.2-01 to AT-0.2-03, and the complete must-catch proof (A6).** I redid the proof with my own harness rather than round 1's.

**Method.** I made four throwaway git clones of `39f2d71` in `/tmp/aqis-audit-wp02-r2/c1` to `c4`, with `origin/main` set to `e3439be`. They share the project `.venv` through a symlink, and bytecode writing was switched off. I checked that `aqis_lab` imports from the clone, not from the working tree.
- Unlike round 1's `git archive` copy, the clones give a clean baseline: `952 passed, 9 deselected`. Every break result below is therefore judged against zero failures.
- Re-serialising the three schemas with no change of content gives `712 passed` for the contract tests and `952 passed` for the whole fast suite in each clone. The rewriting method alone breaks nothing.
- Every changed file was restored and compared byte for byte (`cmp` or an assert against the saved bytes). At the end, all four clones and the working tree have an empty `git status --porcelain`.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `git show origin/main:docs/progress/STATUS.md`: WP-0.0 `MERGED`. Branch `claude/beautiful-dijkstra-8pbq6l`, not `main`. `git show origin/main:docs/approvals/WP-0.2.md` (`e3439be`): `STATUS: APPROVED`, `- Questions 1-7: as recommended in PLAN.md.` and `- Round 2: fix WP-0.2-F01, F02, F03 and F05. WP-0.2-F04 and WP-0.2-F06 are accepted as debt in docs/progress/DEBT.md (target WP-0.9).` |
| A2 Requirement coverage | PASS | `pytest --collect-only`: 961 lab tests. Tests named after each ID: FR_0_2_01 258, FR_0_2_02 180, FR_0_2_03 165, FR_0_2_04 29, FR_0_2_05 15, FR_0_2_06 60, FR_0_2_07 4, NFR_0_2_01 1, NFR_0_2_02 1. Every FR, NFR and AT ID appears in both `EVIDENCE.md` and `PLAN.md`. The same as round 1; nothing changed. |
| A3 Acceptance commands | PASS | AT-0.2-01: `952 passed, 9 deselected in 59.76s`, exit 0. AT-0.2-02: the valid fixture gives `event: 23 records, 23 valid, 0 invalid`, exit 0. The invalid fixture gives `event: 96 records, 2 valid, 94 invalid`, exit 1, and names each failing field, for example `line 4: INVALID /seq: required field is missing`. AT-0.2-03: `aqis-audit-gate: base origin/main (merge-base 6f897411d876), head 39f2d71cc596, approvals origin/main e3439be0c320, wp WP-0.2` … `0 findings: OK (0.2 s)`, exit 0. |
| A4 Test suites and CI | PASS | Fast suite: `952 passed, 9 deselected in 59.76s`. Slow suite (`-m "slow and not gpu and not colab and not oracle"`): `9 passed, 952 deselected in 89.43s`. NFR-0.2-01 run alone three times: call times 5.96 s, 5.61 s and 5.49 s, all under 10 s. CI on `39f2d71`, read from the GitHub API: push run 36311975195 (#135) and pull_request run 36311977170 (#136), jobs `lab` and `harness-regression` both `success`. Every `lab` step succeeded; the WP ID step is skipped on push, by design. |
| A5 Test integrity | PASS | No test or fixture changed since `81b58f1`. In `git diff --name-status origin/main...HEAD -- tests/` all 20 entries are `A`. There is no `skip`, `xfail`, `skipif`, `importorskip` or `audit-allow` in the WP diff. The only marker is `@pytest.mark.slow` on the NFR-0.2-01 timing test, which the spec requires. |
| A6 Must-catch proof | FAIL | 216 breaks: 178 schema-keyword removals and 38 code and document breaks (tables below). Behaviours 1, 3, 4 and 5 are fully protected. **Behaviour 2 has 4 real gaps (F01)**, the same as round 1. **In behaviour 6, break CB6-2 survives (F02)**; it is round 1's A15-01, re-run to check that finding. |
| A7 Compromise scan | PASS | Gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`, `Findings: 0`. A grep of the WP diff for stub and compromise words finds nothing. No code changed since round 1, so round 1's reading of every new function stands. |
| A8 Scope diff | PASS | The diff since `81b58f1` is `A docs/progress/WP-0.2/AUDIT.md` and `M docs/progress/STATUS.md`; in STATUS, only the WP-0.2 row changed (`READY-FOR-AUDIT` to `AUDIT-FAIL`). No protected path, spec, approval, `.claude/` file or lock changed in the WP diff. PR 2 is open, `mergeable_state: clean`. |
| A9 Capabilities | PASS | No module or registry row changed since round 1. The registry cell for CAP-DOC-002 is still incomplete (F05, MINOR, open). |
| A10 Contracts | PASS | Recomputed independently with the standard library: the `run_card_id` of `valid_run_card.json` equals its definition (`92544853e82e…`), and all 23 valid events carry it. `pack.sha256` equals the SHA-256 of the canonical `valid_manifest.json`, and `manifest_id` and `version` match. Every event `clip_id` is a manifest clip. All valid fixtures validate. |
| A11 Environment parity | PASS | Nothing changed since round 1. `.venv` runs Python 3.13.12 and the Colab probe records 3.13.15; major.minor match. The bootstrap reports lock sha256 `5c9a64eb…`, and no lock changed. The spec runs this WP on the cloud VM only, so no owner-run checks are needed. |
| A12 Reproducibility and traceability | PASS | Unchanged since round 1. Breaks CB4-3 to CB4-6 (below) confirm that the canonical-bytes tests protect determinism. |
| A13 Errors and logging | PASS | Unchanged since round 1. The untested `WorkerPoolError` path (F04) has been accepted as debt by the owner. |
| A14 Documentation, licences, data | PASS | Unchanged since round 1. The inaccurate CI sentence at `EVIDENCE.md:279` is still there (F03, MINOR, open). |
| A15 Exploratory breaks | N/A | No code was added or changed since the last audited commit, so there is nothing to break. The round-1 survivor A15-01 was re-run as CB6-2 to check F02. |

## Must-catch proof (A6)
**Schema breaks.** One keyword is removed per run across all three schemas: each entry of every `required` list, and every `type` and `enum` keyword. The walker treats the schemas as schema trees, so a property that happens to be called `type` is never mistaken for a keyword. `if` selectors are skipped, because they choose rules rather than state them. Each break was run first against the 712 contract tests; each survivor was then run against the whole fast suite. The script is `/tmp/aqis-audit-wp02-r2/schema_breaks.py`.

**Code and document breaks.** These are exact text substitutions, each checked to match once. The script is `/tmp/aqis-audit-wp02-r2/code_breaks.py`.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Omitting each required field is rejected, naming it by JSON Pointer | Every entry of every `required` list removed, one per run (88: event 23, run card 38, manifest 27) | For example `test_FR_0_2_02_rejects_missing_required_field[model/version]`, `[machine/architecture]` and `[processing/vad/1/name]`; `test_FR_0_2_03_rejects_missing_required_field[clips/0/consent_ref]` and `[archives/1/sha256]`; `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` (event payload `text`, `code`); `test_FR_0_2_01_rejects_missing_required_word_field` | 88/88 caught. Top-level removals are caught first by the `schema_is_valid_draft_2020_12` tests, which compare the `required` list with the spec's field list |
| 1 | CB1-1 missing field reported at its parent's pointer | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 1 | CB1-2 only the first of several missing fields reported | `test_FR_0_2_01_error_payload_fields` | Caught |
| 1 | CB1-3 pointer escapes applied in the wrong order (`/` becomes `~01`) | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 Wrong types and values outside enums are rejected | Every `type` and `enum` keyword removed, one per run (90: event 34, run card 32, manifest 24) | For example `test_FR_0_2_01_rejects_wrong_type_or_enum[final-path0-5]` (run_id); `test_FR_0_2_02_rejects_wrong_type_or_enum[('model',)-None]`; `test_FR_0_2_03_rejects_wrong_type_or_enum[('manifest_id',)-1]`; `test_FR_0_2_03_version_must_be_semver[1_1]`; `test_FR_0_2_04_cli_run_card_and_manifest_kinds` (`mode` enum) | 74 caught. 16 survive the whole fast suite (`952 passed` each). The probe (below) shows 12 of them are equivalent. **4 are real gaps: F01** |
| 2 | CB2-1 strict `integer` type accepts integral floats such as `1.0` | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-2 strict `integer` type accepts booleans | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-3 calendar check of UTC timestamps removed | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | CB2-4 validators built without the format checker | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 3 An unknown major schema version is rejected | CB3-1 `SUPPORTED_VERSIONS` claims major 2 for events | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | CB3-2 major version always read as 1 | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | CB3-3 unknown-major check removed (minor check tolerates it) | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | CB3-4, CB3-5, CB3-6 version check skipped for manifests, run cards, events (one per run) | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-manifest]`, `[2.0-2-run_card]`, `[2.0-2-event]` | Caught (3/3) |
| 3 | CB3-7 version check removed and the event `schema_version` enum replaced by `type: string`, so an unknown major is accepted | `test_FR_0_2_06_schema_ids_carry_version[event]` | Caught |
| 4 `run_card_id` is the SHA-256 of the canonical card as defined, computed independently | CB4-1 `machine` also excluded from the ID | `test_FR_0_2_05_run_card_id_computed_independently` | Caught |
| 4 | CB4-2 `notes` no longer excluded | `test_FR_0_2_05_run_card_id_computed_independently` | Caught |
| 4 | CB4-3 keys not sorted; CB4-4 spaces after separators; CB4-5 non-ASCII escaped; CB4-6 SHA3-256 instead of SHA-256 | `test_FR_0_2_05_canonical_bytes_match_definition` (each) | Caught (4/4) |
| 4 | CB4-7 `validate_run_card` never compares `run_card_id` | `test_FR_0_2_04_cli_run_card_and_manifest_kinds` | Caught |
| 4 | CB4-8 canonical JSON accepts NaN and Infinity | `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json[nan-]` | Caught |
| 5 Documents and schemas list the same fields | CB5-1 `/machine/gpu` row removed from `RUN_CARD.md` | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` | Caught |
| 5 | CB5-2 row `/clips/*/language` (not in the schema) added to `PACK_MANIFEST.md` | `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` | Caught |
| 5 | CB5-3 `/archives/*/n_members` renamed `/archives/*/members` in the document | `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` | Caught |
| 5 | CB5-4 undocumented `confidence` added to the event `word` schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` | Caught |
| 5 | CB5-5 undocumented `lock.url` added to the run card schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` | Caught |
| 5 | CB5-6 `error` payload heading renamed, so its rows sit under the wrong type | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` | Caught |
| 5 | CB5-7 `tags` removed from the clip schema but still documented | `test_FR_0_2_04_cli_run_card_and_manifest_kinds` first; run alone, `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` also fails | Caught |
| 6 `contracts validate` exits non-zero on any invalid record in a JSON Lines file | CB6-1 exit 0 when exactly one record is invalid | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[first]` | Caught |
| 6 | CB6-3 blank lines dropped before validation | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | CB6-4 unparsable line treated as valid | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | CB6-5 worker pool drops the last chunk | `test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files` | Caught |
| 6 | CB6-6 last report not counted as invalid | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | CB6-7 per-run `seq` errors dropped from the report | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | CB6-8 schema errors of a parsed line discarded | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | CB6-9 exit code decided by the last record only | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[first]` | Caught |
| 6 | CB6-2 `split_json_lines` always drops the last line (round 1's A15-01) | None: `712 passed` for the contract tests, `952 passed, 9 deselected` for the whole fast suite | **Survives: F02** |

**How the 16 survivors of the `type` and `enum` removals were judged.** The probe script is `/tmp/aqis-audit-wp02-r2/probe.py`. For each survivor, it applied the break and put wrong values into the valid fixtures at the affected place: `7`, `1.5`, `true`, `false`, `null`, `"s"`, `""`, `[]`, `["x"]`, `[1]`, `[null]`, `{}` and `{"a": 1}`. Run cards were re-hashed after each change, so an ID mismatch could not hide a gap. The results were compared with the same probe on the unmodified code; that baseline accepts only values that are valid, such as `clip_id: null` on run-level events or `pack: null` with `human_session`.

- **12 equivalent: every wrong value is still rejected.**
  - The root `type: object` of each schema (13 records each). The code rejects a non-object before the schema runs.
  - The event `payload` type, and the types of `payload_empty`, `payload_run_finished`, `payload_partial`, `payload_final`, `payload_timing_mark` and `payload_error` (299 records each). The other of the two object checks still applies.
  - The run card's `not {type: null}` on `model.version` and on `model.checksum` (27 records each). It becomes `not {}`, which still rejects both being null.
- **4 real gaps: F01.**
  - `properties/clip_id/type` in `event_log.v1.json`: 20 wrong values accepted, `7`, `1.5`, `true`, `false`, `[]`, `["x"]`, `[1]`, `[null]`, `{}` and `{"a": 1}`, on both `timing_mark` and `error`.
  - `$defs/word/type`: 11 accepted as `payload.words[0]` of a `final` event, for example `"s"`, `7`, `null` and `["x"]`.
  - `properties/pack/type` in `run_card.v1.json`: 10 accepted with `mode: human_session`, for example `"s"`, `7`, `true` and `[]`.
  - `$defs/archive/type` in `pack_manifest.v1.json`: 11 accepted as `archives[0]`, for example `"s"`, `7`, `null` and `[]`.
  - The unmodified code rejects all 52.

## Exploratory breaks (A15, at most 10)
| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| None | No code added or changed since `81b58f1` | — | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.2-F01 | CRITICAL | A6 (must-catch 2) | **Not fixed (round 1 finding).** Four schema type rules have no test. If any one is removed, wrong types are accepted and every test passes. (1) Event `clip_id` on `timing_mark` and `error`, the two types where it may be null or an ID. (2) Items of a `final` payload's `words` must be objects. (3) `pack` when `mode` is `human_session`. (4) Items of `archives` must be objects. The code is correct today; this is a test gap | Removing `type` at `event_log.v1.json` `properties/clip_id`, `$defs/word`, `run_card.v1.json` `properties/pack` or `pack_manifest.v1.json` `$defs/archive` gives `712 passed` for the contract tests and `952 passed, 9 deselected` for the whole fast suite, each against a clean baseline. The probe shows 20, 11, 10 and 11 wrong values accepted (52 in total); the unmodified code rejects all of them. No test file has changed since round 1 | **Fix now, tests only** (required by the owner's round-2 condition). Add wrong-type cases for: `clip_id` on `timing_mark` and `error`; a non-object item in `payload.words`; a non-object, non-null `pack` with `mode: human_session`; a non-object item in `archives`. Add them as new cases or new test functions; that tightens the tests and changes no production code. The next audit will re-run these four breaks, and each must fail a named test |
| WP-0.2-F02 | MAJOR | A15 in round 1 (inside must-catch 6) | **Not fixed (round 1 finding).** No test gives the validator or the command a JSON Lines file without a final newline. If `split_json_lines` drops the last line unconditionally, `contracts validate` reports a file whose invalid last record has no final newline as all valid, with exit 0, and every test passes. The severity is kept at MAJOR: the finding and its evidence are unchanged, and the owner has already ordered the fix | CB6-2: `712 passed` and `952 passed, 9 deselected`. With the break, a 23-line file with no final newline and `component: "asr"` on the last line gives `event: 22 records, 22 valid, 0 invalid`, exit 0. The unmodified code gives `line 23: INVALID /component: …` and `event: 23 records, 22 valid, 1 invalid`, exit 1. Every non-empty JSON Lines input built in `tests/aqis_lab/test_aqis_contracts_*.py` (the slow NFR test too) and both `.jsonl` fixtures end in `\n` | **Fix now, tests only** (required by the owner's round-2 condition). Add a test that runs `contracts validate` and `validate_event_lines` on a file whose invalid last record has no final newline, and requires exit 1 and that line in the report |
| WP-0.2-F03 | MINOR | A14 / A4 | **Not fixed.** `EVIDENCE.md:279` still says "Every earlier WP-0.2 commit's push run was also green (runs 126 to 130 …)". Push run #123 (36308454812) on `4f752e0` failed at step "Fast lab test suite", and runs #124 and #125 are not mentioned | GitHub API: run 36308454812, job `lab` `failure`, step "Fast lab test suite" `failure`; runs #124 (`b3e8a03`) and #125 (`5939fe7`) `success` | **Fix now** (one sentence; required by the owner's round-2 condition). MINOR never blocks |
| WP-0.2-F04 | MINOR | A13 | The `WorkerPoolError` path (exit 2, "rerun with --workers 1") has no test. **The owner accepted it as debt** in the approval's round-2 condition, target WP-0.9. The row in `docs/progress/DEBT.md` has not been written yet | `validate.py:538-539`, `commands/contracts.py:77-79`; `grep WP-0.2 docs/progress/DEBT.md` finds nothing | **Accept as debt**, target WP-0.9. The builder adds the DEBT row with the round-2 fixes |
| WP-0.2-F05 | MINOR | A9 | **Not fixed.** Registry row CAP-DOC-002 names only `docs/contracts/EVENT_LOG.md` in its module column, although the capability covers all three contract documents | `docs/capabilities/REGISTRY.md:38` | **Fix now** (one cell; required by the owner's round-2 condition). MINOR never blocks |
| WP-0.2-F06 | MINOR | A14 | A wrong-typed `clip_id` on a clip-level event gets two report lines at the same pointer, but CAP-CONTRACTS-006 says "one per failing field". **The owner accepted it as debt** in the approval's round-2 condition, target WP-0.9. The DEBT row has not been written yet | AT-0.2-02 invalid fixture, line 26: `/clip_id: 7 is not of type 'string', 'null'` and `/clip_id: 7 is not of type 'string'. Rule: …` | **Accept as debt**, target WP-0.9. The builder adds the DEBT row with the round-2 fixes |

## Convergence (round 3 onwards)
Not applicable: this is round 2. For the next round, the counts so far are:

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 4 | F01 (behaviour 2), F02 (behaviour 6) |
| 2 | 1 | 1 | 4 | F01 (behaviour 2), F02 (behaviour 6); no fix attempted |

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- Approvals used: `docs/approvals/WP-0.2.md` on `main` at `e3439be`:
  - "Questions 1-7: as recommended in PLAN.md", the same as round 1;
  - the round-2 condition to fix F01, F02, F03 and F05 and to accept F04 and F06 as debt, target WP-0.9.
- Debt accepted so far:
  - WP-0.2-F04 and WP-0.2-F06, target WP-0.9, named in the approval. Their rows in `docs/progress/DEBT.md` have not been written yet.
  - No MAJOR finding has been accepted as debt.
- Owner-run checks still pending: None. The spec runs this WP on the cloud VM only.
- Next step: the round-2 fixes have not been built. They are four test additions, one EVIDENCE sentence, one registry cell and two DEBT rows. After they are built, a round-3 audit re-runs the four F01 breaks and CB6-2.
