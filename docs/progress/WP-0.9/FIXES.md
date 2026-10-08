# FIXES — WP-0.9

## Round 2 (audit round 1 findings WP-0.9-F01 to F07)
Owner approval: `docs/approvals/WP-0.9.md` on `main` (`604e9a4`): "Round 2 Fixes: fix WP-0.9-F01, WP-0.9-F02, WP-0.9-F03, WP-0.9-F04, WP-0.9-F05, WP-0.9-F06, and WP-0.9-F07", with the owner's instructions in the session chat (2026-10-08). Branch merged with `origin/main` at `7c1f147`.

### Change budget
| File | Functions or parts | Findings | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| `tests/aqis_lab/aqis_memo_testutil.py` | `debt_problems`, new constant `PHASE0_DEBT_IDS` and helper `phase0_debt_ids_at`; `audit_rounds`; `link_problems` | F01, F02, F07 | F01: phase 0 rows were found by their current Target cell, and an approval was required only of rows that call themselves moved. F02: the round table read every `WP-0.*/AUDIT.md`, including WP-0.9's own. F07: a path counted as evidence when anything existed there, inside the repository or not | CAP-DOC-019, CAP-DOC-020 |
| `tests/aqis_lab/test_aqis_phase0_memo.py` | new break cases and tests (WP-0.9's own test file, new in this WP) | F01, F02, F03, F07 | F03: four checks had no case that fails when the check is removed | CAP-DOC-019, CAP-DOC-020 |
| `docs/progress/PHASE0_MEMO.md` | "Lessons for the process": the sentence before the round table | F02 | the memo did not say which WPs the table covers | CAP-DOC-019 |
| `tools/audit/gate.py` | `_ignores_for`, `_pytest_skips`, `test_functions` (the call only), module docstring | F04 | conftests were read only between the file and the collected folder; pytest also applies those above it, up to the rootdir (the repository root, where CI runs pytest) | CAP-AUDIT-005, CAP-AUDIT-006 |
| `tests/aqis_lab/test_aqis_debt_wp09.py` | new test for a conftest above the collected folder (WP-0.9's own test file) | F04 | | CAP-AUDIT-005, CAP-AUDIT-006 |
| `docs/tools/AUDIT_GATE.md` | the conftest rule | F04 | | — |
| `tests/aqis_lab/aqis_baseline_testutil.py` | `body_text` | F05 | every `ID`-headed table in Sources was exempt, not only the one `sources_table` reads (the first) | CAP-BASE-002 |
| `tests/aqis_lab/test_aqis_tier2_baseline.py` | `UNCITED_INSERTS`: one new case | F05 | | CAP-BASE-002 |
| `docs/progress/WP-0.9/EVIDENCE.md` | a "Deviations from the plan" section; round 2 results | F06 | the changes to planned tests were not recorded | — |
| `docs/capabilities/REGISTRY.md` | Tests cells of CAP-DOC-019, CAP-DOC-020, CAP-AUDIT-005, CAP-AUDIT-006, CAP-BASE-002 | all | | — |

`tests/aqis_lab/aqis_baseline_testutil.py` and `tests/aqis_lab/test_aqis_tier2_baseline.py` are existing test files; the approval's `ALLOW-EDIT` lines name both.

**F01: which IDs are pinned.** The owner asked to pin "the 19 Phase 0 DEBT IDs (DEBT-001 through 007, 009, 010, 012-021)". `DEBT.md` at `254c1e3` (the commit WP-0.9 started from) has 30 rows with a phase 0 target: DEBT-001 to DEBT-026 and DEBT-028 to DEBT-031. The 19 that targeted WP-0.9 are DEBT-001 to 007, 009, 016, 019, 022 to 026 and 028 to 031. The owner's list omits DEBT-022 to 026 and 028 to 031, among them DEBT-025, the only moved row, and includes rows that targeted other phase 0 WPs. Pinning only those 19 would leave nine rows exposed to the very bypass F01 describes. So `PHASE0_DEBT_IDS` pins all 30. That set contains every ID the owner named, so it is strictly stronger, never weaker. A test also checks that the pinned set equals the phase 0 rows of `DEBT.md` at `254c1e3`, read with `git show`.

### Baseline before the change
`.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_debt_wp09.py tests/aqis_lab/test_aqis_tier2_baseline.py tests/aqis_lab/test_aqis_gate_registry.py tests/aqis_lab/test_aqis_gate_trace.py tests/aqis_lab/test_aqis_gate_parity.py tests/aqis_lab/test_aqis_gate_checks.py tests/aqis_lab/test_aqis_gate_v2.py -q -p no:cacheprovider` → `2 failed, 234 passed in 64.50s`. The two failures are F02: `test_FR_0_9_01_audit_round_counts_and_lessons_cite_records` and `test_FR_0_9_01_memo_passes_every_check`, because round 1's `docs/progress/WP-0.9/AUDIT.md` now exists.
