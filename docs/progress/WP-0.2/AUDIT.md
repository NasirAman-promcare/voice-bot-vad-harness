# AUDIT — WP-0.2, round 1

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: 81b58f1c1637d760691f84c778727f0fd071f534 · Previous audited commit: first audit · Protocol: version 2

## Verdict: FAIL
CRITICAL: 1 · MAJOR: 1 (fixed 0, accepted as debt 0, open 1) · MINOR: 4

The production code does what the spec and the approved plan say. I found no stubs, fake data, swallowed errors or scope drift. Every suite, the gate, CI on the audited commit and the three acceptance commands give the expected output.

The audit fails because tests are missing, not because of a code defect:
- **F01 (CRITICAL).** Four type rules in the schemas are not protected by any test. This is must-catch behaviour 2, "wrong types are rejected". If any one of the four is removed, the whole fast suite still passes and wrong-typed values are accepted. The code rejects all of them today.
- **F02 (MAJOR).** No test uses a JSON Lines file without a final newline. If a later change drops the last line of such a file, `contracts validate` passes a file whose last record is invalid, with exit 0, and the tests stay green. The code is correct today.

Both fixes are tests only.

## Scope of this audit
First audit of WP-0.2: the whole diff `origin/main...81b58f1` (merge-base `6f89741`), which has 35 files. I checked:
- items A1 to A15;
- the fast and slow suites, the gate, CI and AT-0.2-01 to AT-0.2-03, all re-run or read myself;
- the complete must-catch proof (A6), with my own breaks, not the builder's script;
- 10 exploratory breaks (A15) in the WP's new code.

All breaks were made in a throwaway copy of the audited commit (`git archive 81b58f1` into `/tmp/aqis-audit-wp02/base`), run with the project `.venv` and bytecode writing switched off. Each file was restored after its run and checked byte-identical with `cmp` against `81b58f1`. The working tree was not changed (`git status --porcelain` is empty).

The copy is not a git checkout, so 5 WP-0.0 tests fail there with no break at all: `test_FR_0_0_13_oc_steps_use_pull_request_branch`, `test_NFR_0_0_01_gate_runtime_under_60s`, `test_FR_0_0_08_repository_registry_is_consistent`, `test_FR_0_0_12_asset_pins_match_repository` and `test_FR_0_0_01_version_prints_package_commit_python`. The unmodified copy gives `5 failed, 947 passed`. Full-suite results under a break are judged against that baseline.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.0 is `MERGED` in `docs/progress/STATUS.md` on `origin/main`. Branch `claude/beautiful-dijkstra-8pbq6l`, not `main`. `git show origin/main:docs/approvals/WP-0.2.md`: `STATUS: APPROVED`, `CONDITIONS: Questions 1-7: as recommended in PLAN.md.` |
| A2 Requirement coverage | PASS | `pytest --collect-only` collects tests named after every ID: FR_0_2_01 258, FR_0_2_02 180, FR_0_2_03 165, FR_0_2_04 29, FR_0_2_05 15, FR_0_2_06 60, FR_0_2_07 4, NFR_0_2_01 1, NFR_0_2_02 1 (961 lab tests in total). Every FR, NFR and AT ID appears in both `EVIDENCE.md` and `PLAN.md`. Each FR has code in `aqis_lab/contracts/` or `aqis_lab/commands/contracts.py`. |
| A3 Acceptance commands | PASS | AT-0.2-01: `952 passed, 9 deselected in 58.46s`, exit 0. AT-0.2-02, valid fixture: 23 `line n: OK` lines, `event: 23 records, 23 valid, 0 invalid`, exit 0. Invalid fixture: `event: 96 records, 2 valid, 94 invalid`, exit 1; every invalid line names its pointer, for example `line 4: INVALID /seq: required field is missing` and `line 57: INVALID /payload/words/0/end_s: required field is missing`. AT-0.2-03: `aqis-audit-gate: base origin/main (merge-base 6f897411d876), head 81b58f1c1637 ... 0 findings: OK (0.2 s)`, exit 0. The invalid fixture has invalid lines for all 10 event types and for every envelope and payload field. |
| A4 Test suites and CI | PASS | Fast suite: `952 passed, 9 deselected`. Slow suite (`-m "slow and not gpu and not colab and not oracle"`): `9 passed, 952 deselected in 58.83s`. NFR-0.2-01 run alone three times: 5.20 s, 5.40 s and 5.13 s, each under the 10 s limit. CI on `81b58f1`: push run 36310374131 and pull_request run 36310376547, jobs `lab` and `harness-regression` both `success`, and every `lab` step (bootstrap, fast suite, WP ID, gate) `success`. I read these conclusions from the GitHub API. I could not read the log text: the log download host returns a proxy 403. |
| A5 Test integrity | PASS | `git diff --name-status origin/main...HEAD`: every test file is new (`A`), and no test from `main` was changed or deleted. There is no `skip`, `xfail` or `audit-allow` in the new tests. The only marker is `@pytest.mark.slow` on the NFR-0.2-01 timing test, which the spec requires. The expected pointers in `invalid_events.expected.json` and `invalid_expected.json` are consistent with the fixture lines I checked. |
| A6 Must-catch proof | FAIL | 203 breaks across all 6 behaviours (table below). Behaviours 1 and 3 to 6 are fully protected. Behaviour 2 has 4 real gaps, which are F01. |
| A7 Compromise scan | PASS | The gate reports 0 findings, with 0 exempted lines and 0 exempted files. I read every new function. There are no stubs, TODOs or placeholders. The fixtures are labelled "illustrative", and no value was found to be hard-coded to satisfy a test. The only `except` that returns an empty result is `_run_card_rules` `except CanonicalJSONError: return []` (`validate.py:324-325`). It is justified: `_json_value_errors` reports the same values at their pointers, and A15-04 shows that a test protects this path. |
| A8 Scope diff | PASS | The changed files match the plan's list. `aqis_lab/__main__.py` has +2 lines: the `COMMANDS` entry and one CHANGE LOG line. `REGISTRY.md` only has appended rows. `STATUS.md` has the WP-0.2 row only. No GUARDED or NEVER path was changed. `tests/aqis_lab/fixtures/contracts/.gitignore` is LAB-OWNED and was approved under question 6a. The extra row CAP-CONTRACTS-007 is disclosed in EVIDENCE and is inside the approved scope. |
| A9 Capabilities | PASS | All four new modules have the standard header. Rows CAP-CONTRACTS-001 to 007 and CAP-DOC-002 were added and no row was removed. `test_FR_0_0_08_module_headers_match_registry` passes in the fast suite. All linked tests are collected. One registry cell is incomplete (F05, MINOR). |
| A10 Contracts | PASS | All valid fixtures validate. The event fixtures' `run_card_id` equals the defined ID of `valid_run_card.json` (`92544853…`). In the run card fixture, `pack.sha256 == sha256_canonical(valid_manifest.json)`, and `manifest_id` and `version` match the manifest. |
| A11 Environment parity | PASS | A grep of the new code, tests and documents finds no absolute paths. Schemas are found from `__file__`. Python 3.13 matches the Colab probe (`3.13.15`). `jsonschema==4.26.0` is pinned with hashes, and the lock is unchanged. The `spawn` context and `os.process_cpu_count()` are available on 3.13. The spec runs on the cloud VM only, so no owner-run checks are needed. |
| A12 Reproducibility and traceability | PASS | Canonical JSON is deterministic, and a test checks it against an independent encoder. Errors are sorted by pointer. The worker-pool report is identical to the one-process report (tested). Every event carries `run_card_id` and `clip_id`. |
| A13 Errors and logging | PASS | An invalid record raises `ContractValidationError` naming every pointer. An unreadable file gives exit 2 with `ERROR: cannot read`. A worker failure raises `WorkerPoolError` and gives exit 2 with `rerun with --workers 1`; there is no silent fallback. That path has no test (F04, MINOR; the builder disclosed it). |
| A14 Documentation, licences, data | PASS | The three contract documents cover the fields, the rules across fields, validation usage and the change policy. `EVIDENCE.md` has an entry for every ID. One CI sentence in it is inaccurate (F03, MINOR). No third-party code or data was added, so licences are not affected. The fixtures hold no personal data: the LibriSpeech speaker `1089` is a public dataset ID. |
| A15 Exploratory breaks | FAIL | 10 breaks, 9 caught, 1 survivor that can make the command report success wrongly (F02). |

## Must-catch proof (A6)
The schema breaks remove each keyword separately, one at a time, across all three schemas. `if` selectors are skipped, because they choose rules rather than state them. Each break was first run against its kind's test file and then against all contract tests. Every break that still survived was run against the whole fast suite.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Omitting each required field is rejected, naming it by JSON Pointer | Every entry of every `required` list removed, one per run (88 breaks: event 23, run card 38, manifest 27) | For example `test_FR_0_2_01_rejects_missing_required_payload_field[error-run_continues]`, `test_FR_0_2_01_rejects_missing_required_word_field[start_s]`, `test_FR_0_2_02_rejects_missing_required_field[machine/python_version]`, `test_FR_0_2_03_rejects_missing_required_field[clips/0/consent_ref]`, `test_FR_0_2_03_rejects_missing_required_field[archives/1/n_members]` | 88/88 caught. The static `schema_is_valid` tests catch top-level removals first. With those tests deselected, `rejects_missing_required_field[...]` catches every top-level removal except `schema_version`. That one is equivalent: the version check rejects a missing `schema_version` before the schema runs, and `rejects_missing_required_field[schema_version-*]` covers it. |
| 1 (pointer names the field) | Missing field reported at its parent's pointer | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 1 (pointer names the field) | `/` no longer escaped as `~1` in pointers | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 Wrong types and values outside enums are rejected | Every `type` and `enum` keyword removed, one per run (90 breaks) | For example `test_FR_0_2_01_rejects_wrong_type_or_enum[final-path12-1]` (seq), `test_FR_0_2_02_rejects_wrong_type_or_enum[('mode',)-'fast']`, `test_FR_0_2_02_rejects_wrong_type_or_enum[('machine', 'platform')-'aws']`, `test_FR_0_2_03_rejects_wrong_type_or_enum[('clips', 0, 'channels')-1.0]` | 74 caught. 12 are equivalent: a probe of 52 wrong-typed records shows the value is still rejected by another rule. **4 survive the whole fast suite and let wrong types through: F01** |
| 2 | Strict `integer` type accepts `1.0` | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | Strict `integer` type accepts booleans | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 2 | Calendar check of UTC timestamps removed | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 3 An unknown major schema version is rejected | `SUPPORTED_VERSIONS` claims major 2 for events | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | Major version always read as 1 | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-event]` | Caught |
| 3 | Version check skipped for manifests | `test_FR_0_2_06_rejects_unknown_major_version[2.0-2-manifest]` | Caught |
| 4 `run_card_id` is the SHA-256 of the canonical card as defined, computed independently | `machine` also excluded from the ID | `test_FR_0_2_05_run_card_id_computed_independently` | Caught |
| 4 | `notes` no longer excluded | `test_FR_0_2_05_run_card_id_computed_independently` | Caught |
| 4 | Keys not sorted | `test_FR_0_2_05_canonical_bytes_match_definition` | Caught |
| 4 | SHA3-256 instead of SHA-256 | `test_FR_0_2_05_canonical_bytes_match_definition` | Caught |
| 4 | `validate_run_card` never compares `run_card_id` | `test_FR_0_2_04_cli_run_card_and_manifest_kinds` | Caught |
| 4 | Canonical JSON accepts NaN | `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json[nan-]` | Caught |
| 5 Documents and schemas list the same fields | `/machine/os` row removed from `RUN_CARD.md` | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` | Caught |
| 5 | Row `/clips/*/language` (not in the schema) added to `PACK_MANIFEST.md` | `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` | Caught |
| 5 | `/archives/*/bytes` renamed in the document | `test_FR_0_2_07_documents_and_schemas_list_same_fields[manifest]` | Caught |
| 5 | `timing_mark` payload heading renamed, so its row sits under the wrong type | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` | Caught |
| 5 | Undocumented `priority` added to the `error` payload schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[event]` | Caught |
| 5 | Undocumented `machine.ram_gb` added to the run card schema | `test_FR_0_2_07_documents_and_schemas_list_same_fields[run_card]` | Caught |
| 6 `contracts validate` exits non-zero on any invalid record in a JSON Lines file | Exit 0 when exactly one record is invalid | `test_FR_0_2_04_cli_one_invalid_line_anywhere_fails[first]` | Caught |
| 6 | Last record not counted | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | Unparsable line treated as valid | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | Blank lines dropped before validation | `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | Caught |
| 6 | Worker pool drops the last chunk | `test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files` | Caught |

The 12 equivalent survivors under behaviour 2 are:
- the root `type: object` of all three schemas: the code rejects non-objects before the schema runs (`validate.py:404-408`);
- the event `payload` type and the 6 `$defs/payload_*` types: the other of the two object checks still applies;
- the run card's `not {type: null}` on `model.version` and `model.checksum`: it becomes `not {}`, which still fails when both are null.

The 4 real gaps (F01) each leave `5 failed, 947 passed` in the whole fast suite. That is the copy's baseline, so no test catches them.

## Exploratory breaks (A15, at most 10)
All 10 are in `aqis_lab/contracts/validate.py` or `canonical.py`, which are new in this WP. Each was run against all contract tests.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| A15-01 `split_json_lines` always drops the last line (the last record is lost when there is no final newline) | `validate.py:475-476` | **Yes.** 712 contract tests passed. With the break, a 23-line file with no final newline and an invalid last record gives `event: 22 records, 22 valid, 0 invalid`, exit 0. The unmodified code gives `23 records, 22 valid, 1 invalid`, exit 1 | MAJOR (F02) |
| A15-02 `_json_value_errors` does not look inside arrays | `validate.py:288-290` | No: `test_FR_0_2_04_rejects_nan_infinity_and_overflow` | — |
| A15-03 Unknown fields produce no error | `validate.py:236-239` | No: `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | — |
| A15-04 Non-finite numbers not reported (the path that `_run_card_rules` relies on) | `validate.py:294-297` | No: `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | — |
| A15-05 A run's first `seq` may be any number | `validate.py:504` | No: `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | — |
| A15-06 Per-type event validators lose the common `if`/`then` blocks | `validate.py:223` | No: `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` | — |
| A15-07 Duplicate `clip_id` and archive names never detected | `validate.py:342-343` | No: `test_FR_0_2_04_cli_run_card_and_manifest_kinds` | — |
| A15-08 A newer minor version passes the version check | `validate.py:397` | No: `test_FR_0_2_06_rejects_newer_minor_version[1.1-event]` | — |
| A15-09 Word order checked for the first word only | `validate.py:310` | No: `test_FR_0_2_01_final_word_timings` | — |
| A15-10 Canonical JSON check does not look inside arrays | `canonical.py:39-41` | No: `test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json[bad2-/a/1]` | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.2-F01 | CRITICAL | A6 (must-catch 2) | Four schema type rules have no test. If any one is removed, wrong types are accepted and the whole fast suite still passes. (1) Event `clip_id` type for the two event types where it may be null or an ID, `timing_mark` and `error`: `clip_id` values `7`, `true`, `["c"]` and `{"a": 1}` are accepted. The existing wrong-type cases use only `final`. (2) Items of a `final` payload's `words` must be objects: `words: ["hello"]`, `[1]` and `[null]` are accepted. (3) `pack` when `mode` is `human_session`: `"smoke"`, `5`, `[]` and `true` are accepted. The existing cases use mode `batch`, where the `else` rule also checks the type. (4) Items of `archives` must be objects: `"x"`, `5`, `null` and `[]` are accepted, and the clip-to-archive reference check is then skipped, so the manifest is reported valid. The code rejects all 52 probe records today, so this is a test gap, not a defect. EVIDENCE says the wrong-type tests cover "every envelope and payload field" and "every field"; these four context-dependent rules are not covered | Breaks: remove `type` at `event_log.v1.json:20` (`clip_id`), `event_log.v1.json:68` (`$defs/word`), `run_card.v1.json:13` (`pack`) and `pack_manifest.v1.json:56` (`$defs/archive`). Each gives `712 passed` for the contract tests and `5 failed, 947 passed` for the whole fast suite (the copy's baseline) | **Fix now, tests only.** Add wrong-type cases for: `clip_id` on `timing_mark` and `error`; a non-object item in `payload.words`; a non-object, non-null `pack` with `mode: human_session`; a non-object item in `archives`. Add them as new cases or new test functions (tightening only); no production change is needed. The re-audit will re-run these four breaks, and each must fail a named test |
| WP-0.2-F02 | MAJOR | A15 (inside must-catch 6) | No test gives the validator or the command a JSON Lines file without a final newline. If `split_json_lines` drops the last line unconditionally, `contracts validate` reports a file with an invalid last record as all valid, with exit 0, and every test passes. A file without a final newline is valid JSON Lines, so this is a case of must-catch behaviour 6. The protocol says an A15 survivor is never CRITICAL, so it is rated MAJOR | A15-01 above; `validate.py:472-477`. The unmodified code handles the case correctly (exit 1) | **Fix now, tests only.** Add a test that runs `contracts validate` (and `validate_event_lines`) on a file whose last record is invalid and has no final newline, and requires exit 1 and that line in the report |
| WP-0.2-F03 | MINOR | A14 / A4 | `EVIDENCE.md:279` says "Every earlier WP-0.2 commit's push run was also green". Push run 123 (36308454812) on `4f752e0` failed at step "Fast lab test suite". The cause (the `validate.py` header listing 7 of 13 tests) is disclosed at `EVIDENCE.md:30`, but only as a local test failure, not as a CI failure. The audited commit is green | GitHub API: run 36308454812, job `lab` `failure`, step 6 "Fast lab test suite" `failure` | **Fix now** (one sentence) together with F01 and F02. MINOR never blocks |
| WP-0.2-F04 | MINOR | A13 | The `WorkerPoolError` path has no test: worker processes that cannot start or that die should give exit 2 with "rerun with --workers 1". The builder disclosed this in EVIDENCE. The path fails loudly and cannot report success | `validate.py:538-539`, `commands/contracts.py:77-79` | **Accept as debt**, target WP-0.9 |
| WP-0.2-F05 | MINOR | A9 | Registry row CAP-DOC-002 names only `docs/contracts/EVENT_LOG.md` in its module column, although the capability covers all three contract documents | `docs/capabilities/REGISTRY.md:38` | **Fix now** with F01 (one cell), or accept as debt, target WP-0.9 |
| WP-0.2-F06 | MINOR | A14 | A wrong-typed `clip_id` on a clip-level event gets two report lines at the same pointer: the envelope type error and the per-type rule error. CAP-CONTRACTS-006 says "one per failing field". The pointer and the exit code are correct | `contracts validate` on `invalid_events.jsonl`, line 26: `/clip_id: 7 is not of type 'string', 'null'` and `/clip_id: 7 is not of type 'string'. Rule: ...` | **Accept as debt**, target WP-0.9 |

## Convergence (round 3 onwards)
Not applicable: round 1.

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- Approvals used: `docs/approvals/WP-0.2.md` on `main` (`6f89741`), "Questions 1-7: as recommended in PLAN.md". This covers deviation D1 (`schema_version` in run cards and manifests), the worker pool for NFR-0.2-01, the payload fields, nullable `pack`, `normaliser` and `speaker_id`, `consent_ref` for `owner` and `campaign`, the per-run `seq` check, the nested `.gitignore` and the pure-Python reading.
- Debt accepted so far: None for WP-0.2.
- Owner-run checks still pending: None. The spec runs this WP on the cloud VM only. NFR-0.2-01 was not measured on Colab: the builder's estimate is about 9 s on 2 vCPUs, and the spec does not require that measurement.
