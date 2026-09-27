# FIXES — WP-0.2

## Round 2 fixes: WP-0.2-F01, F02, F03, F05; debt F04, F06
Authority: `docs/approvals/WP-0.2.md` on `main` (`e3439be`): "Round 2: fix WP-0.2-F01, F02, F03 and F05. WP-0.2-F04 and WP-0.2-F06 are accepted as debt in docs/progress/DEBT.md (target WP-0.9)." Audit reports: `docs/progress/WP-0.2/AUDIT.md` (rounds 1 and 2).

### Root causes
- **F01 (CRITICAL, must-catch 2).** Four schema `type` rules had no test that fails when the rule is removed. In each case the only wrong-type tests use a context where a second rule catches the value anyway:
  1. `event_log.v1.json` `properties/clip_id` `type`. Every wrong-type `clip_id` case used `final`, whose clip-level branch also requires a string. `timing_mark` and `error` have no such branch.
  2. `$defs/word` `type`. No test put a non-object item in `payload.words`.
  3. `run_card.v1.json` `properties/pack` `type`. Every wrong-type `pack` case used `mode: batch`, where the `human_session` rule also requires an object.
  4. `pack_manifest.v1.json` `$defs/archive` `type`. No test put a non-object item in `archives`. Without the rule, the clip-to-archive check is also skipped, because an archive has no string name, so such a manifest would pass.

  The production code was correct. This was a test gap.
- **F02 (MAJOR, must-catch 6).** Every JSON Lines input in the tests ended with `\n`, so nothing checked that `split_json_lines` keeps a last record that has no final newline. This was a test gap; the code was correct.
- **F03 (MINOR).** The CI sentence in EVIDENCE.md was wrong: push run #123 on `4f752e0` failed, and runs #124 and #125 were not mentioned.
- **F05 (MINOR).** The CAP-DOC-002 module cell names only `EVENT_LOG.md`.

### Change budget
| File | What changes | Capabilities at risk |
| --- | --- | --- |
| `tests/aqis_lab/test_aqis_contracts_gaps.py` | **new file**: tests for F01 (four rules, including sibling non-object items and wrong types) and F02 (validator API and command, including files that do not end in a newline) | none (adds tests) |
| `aqis_lab/contracts/validate.py` | module docstring only: the new test names in the CAP-CONTRACTS-001, 002, 003 and 007 lines, and a CHANGE LOG line. No code changes | CAP-CONTRACTS-001/002/003/007 (header must equal the registry, `test_FR_0_0_08_module_headers_match_registry`) |
| `aqis_lab/commands/contracts.py` | module docstring only: the new test names in the CAP-CONTRACTS-006 line, and a CHANGE LOG line | CAP-CONTRACTS-006 |
| `docs/capabilities/REGISTRY.md` | the tests cells of the CAP-CONTRACTS-001, 002, 003, 006 and 007 rows (additions only). F05: a Module cell must name one existing file (gate `module_exists`, rule G33), so it cannot list three documents. Two rows are added instead: CAP-DOC-003 (`RUN_CARD.md`) and CAP-DOC-004 (`PACK_MANIFEST.md`). CAP-DOC-002 keeps its capability; only its Functions cell gains a pointer to them | none removed or weakened |
| `docs/progress/WP-0.2/EVIDENCE.md` | the CI sentence (F03), a round-2 section | — |
| `docs/progress/DEBT.md` | two rows added: F04, F06 | — |
| `docs/progress/WP-0.2/FIXES.md`, `docs/progress/STATUS.md` | this record; the WP-0.2 row | — |

No existing test is modified, and no schema or production code changes.

### Baseline (before any change, after merging `origin/main` at `e3439be`)
- Fast suite: `952 passed, 9 deselected in 57.47s`.
- Contract tests and the registry/header tests (`-k "FR_0_2 or FR_0_0_08"`): `725 passed, 236 deselected in 17.64s`.

### Evidence
- Reproduction: the five audited breaks, applied one at a time in a scratch copy, each leave the round-1 contract tests green (`712 passed`) and each fail a named new test. The table and the real output are in `EVIDENCE.md`, "Round 2 fixes".
- The new tests pass against the unchanged code: `46 passed in 1.33s`.
- Fast suite after the change: `998 passed, 9 deselected in 57.68s`; every baseline test still passes. Gate with `--wp WP-0.2`: `0 findings: OK`.
- `git diff -U0 aqis_lab/`: only header docstring lines (the tests lists of CAP-CONTRACTS-001, 002, 003, 006 and 007, and two CHANGE LOG lines). There are no code lines, and no existing test file changed.
- Category check (skill step 6): the audit's 216-break run found exactly these four real type gaps (12 other surviving `type` removals were equivalent). For the no-final-newline gap, the sibling input of a run card or manifest document without a final newline is now covered too (`test_FR_0_2_04_cli_documents_without_final_newline`).
