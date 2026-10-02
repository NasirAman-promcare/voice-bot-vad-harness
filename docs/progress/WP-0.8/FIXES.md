# FIXES — WP-0.8

## Round 2: WP-0.8-F01, WP-0.8-F02, WP-0.8-F03 (`/surgical-fix`)
Owner instruction and approval: `docs/approvals/WP-0.8.md` on `main` (`f97f492`):
- "Round 2 Fixes: fix WP-0.8-F01, WP-0.8-F02, WP-0.8-F03";
- the question 5 and question 6 lines restored;
- F04 to F07 accepted as debt, target WP-0.9.

`origin/main` was merged first (`5064d19`).

### Findings and root cause
- **F01 (CRITICAL).** Changing the withdrawal window in "Your right to withdraw" from 30 to 14 days passed every test.
- **F03 (MAJOR).** Invented additions beside an owner phrase passed every test: wider access (E1), training and selling models (E2), a 7-day deletion deadline (E3).
- **Root cause of both.** `test_FR_0_8_01_owner_facts_appear_as_given` only checked that each owner phrase appears somewhere in the whole form.
  - The 30-day phrase also sits in a tick box, so it was still found after M1h.
  - Text added next to a phrase was never looked at.
- **F02 (MAJOR).** The test read the owner facts from the superseded approval commit `61c50c7` (`git show`), because the approval rewrite `b4b327e` had dropped them. The owner has restored them on `main`. F08 (MINOR: the test needed full git history) closes with this fix.

### Change budget
| File | Functions or lines | Change |
| --- | --- | --- |
| `tests/aqis_lab/test_aqis_recording_docs.py` | `FACTS_COMMIT`, `_owner_approval_with_facts` (removed); `_approval_fact`; `test_FR_0_8_01_owner_facts_appear_as_given`; `import subprocess` (added in round 1 only for `_owner_approval_with_facts`) | Read the facts from the current `docs/approvals/WP-0.8.md` (question 6 lines); add `owner_fact_problems(text)`, which compares each owner-fact section (and the consent tick boxes) with the exact text built from the approval's wording; add `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions` |
| `docs/capabilities/REGISTRY.md` | row CAP-DOC-014 | Text and test list |
| `docs/progress/DEBT.md` | new rows DEBT-022 to DEBT-025 | F04 to F07, target WP-0.9 (owner approval) |
| `docs/progress/WP-0.8/EVIDENCE.md`, `FIXES.md` | records | Evidence |

The documents and the production code are not changed.

**Capabilities at risk:** CAP-DOC-014, whose tests are in `test_aqis_recording_docs.py`. Every other test in that file must stay green and unchanged.

### Baseline (before any change)
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py tests/aqis_lab/test_aqis_filler_library.py tests/aqis_lab/test_aqis_targets_options.py -q -p no:cacheprovider
38 passed in 0.47s
```
