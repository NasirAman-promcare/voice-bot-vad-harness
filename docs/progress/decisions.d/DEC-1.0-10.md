# DEC-1.0-10 — Impact selection includes the changed and new test files themselves
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-12
Spec basis: FR-1.0-03 and WO-1.0-03 B11 ("tests: test files that import any affected module, plus tests named for capability tests listed in the affected modules' headers"); CLAUDE.md names impact "Tests affected by your change", and NFR-1.0-02 has the stop gate run it.

Question: should `impact` select a test file that the change itself edits or adds? B11's wording selects only test files that import an affected module, and a test file does not import itself.

Options:
1. Select every test file in the affected set, as well as the importers of affected modules (changed or new test files run).
2. Keep the literal reading: a change to a test alone selects nothing, and the stop gate runs no test for it.

Choice: 1, with B11 clarified in WO-1.0-03.

Why: a probe on 2026-10-12 (scratch repository, branch editing only `tests/aqis_lab/test_gamma.py`) gave `ImpactResult(all=False, reason=None, lines=())`; the same for a new untracked test file. The purpose of impact selection is to run the tests a change affects, and a changed test is the most directly affected one. `test_impact_changed_tests.py`: `2 failed` before the change, `2 passed` after; `tests/aqis_lab/index`: `118 passed`.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: remove the `# DEC-1.0-10` line in `tools/index/impact.affected_tests`, the B11 clarification and `test_impact_changed_tests.py`.
