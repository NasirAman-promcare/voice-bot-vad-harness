# FIXES — WP-0.1

## Round 2 (audit round 1 findings F1, F2, F3, F6, F7; approval `docs/approvals/WP-0.1.md`, "Round 2 Fixes")

The approval accepts F4 and F5 as debt (target WP-0.9): DEBT-028 and DEBT-029 in `docs/progress/DEBT.md`.

### Change budget
| File | Functions or parts | Finding | Root cause |
| --- | --- | --- | --- |
| `tests/aqis_lab/aqis_baseline_testutil.py` | new `binding_problems` with helpers `_cell_specs`, `_spec_problems`, `_expr_shape`; `summary_problems` (adds the binding problems) | F1 | `citation_problems` compares a cell's shown value only with the cited row's Value. Nothing ties the cited Sources row to the table row (operating point or category) or to the column (metric) the cell sits in |
| same | `UNCHECKED_SECTIONS` replaced by targeted exclusions; `body_text`; new `owner_statement` | F2 | `body_text` dropped three whole sections, so an invented number anywhere in them was never checked |
| same | `raw_problems` (R8 role check moved into the missing-items check) | F7 | A missing speaker or listener log was reported as "R8: … expected", not as missing, so the test named for missing items passed |
| same | module docstring (change log) | all | record |
| `tests/aqis_lab/test_aqis_tier2_baseline.py` | new tests (below); `identifiers` (adds the baseline folder name, now that the title line is checked) | F1, F2, F3, F7 | F3: `raw_problems`' consistency checks had no negative self-test |
| `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md` | title (date as a code span); "Owner's statement" section, the text outside the quote (no uncited digits) | F2 | The narrowed check now reads these lines |
| `docs/progress/WP-0.1/EVIDENCE.md` | FR-0.1-01 "Test first" line; a Round 2 section | F6 | The text said every test failed; at `cb49333` it was 17 failed and 1 passed |
| `docs/capabilities/REGISTRY.md` | row `CAP-BASE-002`: Tests cell and "What it does" | all | record |
| `docs/progress/DEBT.md` | rows DEBT-028 (F4) and DEBT-029 (F5) appended | F4, F5 | approval |
| `docs/progress/STATUS.md` | the WP-0.1 row | — | status |

Capabilities at risk: `CAP-BASE-002` only. Its 14 existing tests must keep passing unchanged.

### Baseline before any change
`.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider` → `18 passed in 9.55s` (branch at `3584636`, after merging `origin/main` `264532a`).

### Reproduction: new tests written before any fix
Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider -k "wrong_row or uncited_numbers or each_inconsistency"`, run on the unfixed helper:
```text
FAILED test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column[headline-rows]      (and 6 more swap cases)
FAILED test_FR_0_1_02_check_reports_uncited_numbers_in_every_section[owner-statement-outside-quote]  (and 5 more)
FAILED test_FR_0_1_01_check_reports_each_inconsistency[R8-listener-log-missing]
```
- **F1:** all 7 swap cases failed, which reproduces E1 and E2.
- **F2:** all 6 insert cases failed, which reproduces E3 and E4.
- **F7:** the R8 case failed with `["R8: the speaker and the listener log expected, …"]`, not "R8 missing".
- **F3:** the checks already work on bad data, so all 11 other `each_inconsistency` cases passed on the unfixed helper. The finding is that nothing failed when the checks were disabled. With the auditor's mutations applied (E6: `if expected is None or n != expected:` → `if expected is None:`; E10: the R1 comparison → `if False:`), the new cases fail:
  ```text
  FAILED test_FR_0_1_01_check_reports_each_inconsistency[R1-config-differs-from-run-context]
  FAILED test_FR_0_1_01_check_reports_each_inconsistency[R5-clip-records-missing]
  ```
  The helper was then restored with `git checkout`.
- **My own test-edit error.** At first the `R8-log-starts-after-first-clip` case also failed, because my edit was too weak: halving the speaker log still left lines stamped 07:59:11, which is before the first clip at 08:00:04. I corrected the edit to keep only lines from 09:00 UTC on. The helper was right.

### Fix
- **F1** `binding_problems`, called from `summary_problems`. For every cell of the VADs, Conditions (category), headline, frame-count and run-health tables, it requires exactly one cited source per expected kind, and nothing else. The expected kinds are:
  - the harness report cell in this row's operating point and the column's report column;
  - the run-log value after the column's label on this operating point's "Tier 2 Completed" line;
  - the derived row whose `op`, `field` and `where` (record type, this operating point, category or `has_speech`) belong to the column;
  - for `expr` rows, the formula shape (`A / (A + B)`, `2 * A * B / (A + B)`), with each referenced row bound in turn;
  - for the WebRTC mode, the run-configuration entry that names this operating point;
  - for a category, one count per operating point in this category.
- **F2** `body_text` now reads every section, including the title. Only three things are exempt:
  - a `>` line equal to the approval's quoted statement (`owner_statement`);
  - the Bytes and SHA-256 cells of the Raw inventory;
  - the Sources table rows.

  SUMMARY.md changed in three places to pass the narrowed check: the title's date became a code span, and two sentences in the owner's-statement section no longer contain uncited digits ("question 6", "DEBT-027"). The baseline folder name is now a known identifier.
- **F3** New test `test_FR_0_1_01_check_reports_each_inconsistency`, with 12 cases. Each edits a `tmp_path` copy and requires every problem to name the broken item:

  | Item | Cases |
  | --- | --- |
  | R1 | config differs from `run_context`; tier 2 not run |
  | R2 | key missing |
  | R3 | harness file changed |
  | R4 | point unanswered; start after the run began |
  | R5 | clip records missing; `clip_failure` |
  | R6 | mixed runs |
  | R7 | an operating point's line missing |
  | R8 | log starts after the first clip; listener log missing |
- **F6** EVIDENCE.md FR-0.1-01 "Test first" now says 17 failed and 1 passed, with the reason.
- **F7** In `raw_problems`, a speaker or listener log missing from the R8 inventory is reported as `R8 missing: no <role> log listed in the Raw inventory`, together with the other missing items. The old role check at the end of the function was removed, because it reported the same condition.

### Verification
- `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider` → `44 passed in 17.09s`. The 18 round-1 tests are unchanged and pass; 26 new collected tests are added.
- Guards cannot be disabled silently. Each mutation was applied to the fixed helper, which was then restored byte for byte (`cmp`):

  | Mutation | Result |
  | --- | --- |
  | M1: `_cell_problems` returns `[]` | `7 failed` (every swap case) |
  | M2: the whole owner's-statement section exempt again | `2 failed` (`owner-statement-outside-quote`, `owner-statement-second-quote`) |
  | M3: the R8 role check removed | `1 failed` (`R8-listener-log-missing`) |
- Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` → `1856 passed, 55 deselected in 225.93s`.
- Gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` → `0 findings: OK`.
- `git diff -U0` touches only the budgeted functions and parts listed above.
- Registry: the `CAP-BASE-002` row now lists 18 test functions and describes the round-2 checks.
