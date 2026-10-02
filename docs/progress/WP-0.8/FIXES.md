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

### Reproduce (tests first)
- **Step 1.** The round 1 logic was moved, unchanged, into `owner_fact_problems(text)` (each phrase anywhere in the form), now reading the current approval (F02).
- **Step 2.** The new `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions` applies the auditor's breaks to copies of the form, plus three of the same kind:
  - M1h: 30 days changed to 14 in "Your right to withdraw" only;
  - E1: wider access;
  - E2: training and sale;
  - E3: a 7-day deadline;
  - the tick-box window changed;
  - the tick-box age changed;
  - a service added.
- **Result with the round 1 logic:** five breaks were not reported.
```text
FAILED …::test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions[E1-wider-access]
FAILED …::test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions[E2-training-and-sale]
FAILED …::test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions[E3-deletion-deadline]
FAILED …::test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions[M1h-window-14-days]
FAILED …::test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions[tick-box-window]
5 failed, 3 passed, 20 deselected in 0.19s
```

### Fix
- **F01 and F03.** `owner_fact_problems` now compares four sections with the exact text built from the approval: "Why we are recording", "How we store your recordings", "Who can see them" and "Your right to withdraw".
  - The owner's question 6 (a), (b), (c) and (e) wording fills the slots, and the form's fixed connecting prose surrounds it. The question 5 line must say "Signed consent forms kept offline by owner".
  - The consent tick boxes must equal the list built from (d) and (e).
  - Any changed or added word in those sections is reported.
- **F02 and F08.** `_approval_fact` reads the question 6 lines of the current `docs/approvals/WP-0.8.md`. `FACTS_COMMIT`, `_owner_approval_with_facts` and `import subprocess` are removed, so the test no longer needs git history.
- **No document changed.** The committed consent form already matches the approval exactly.

### Verify
- Tests:
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_recording_docs.py -q -p no:cacheprovider
28 passed in 0.18s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or FR_0_8_ or test_FR_0_0_04"
51 passed, 1812 deselected in 8.99s
```
- **Break proof** in a scratch worktree of `fdf0129`: the unbroken documents give `45 passed in 0.33s`, and the auditor's surviving breaks are now caught:

  | Break | Fails | Result |
  | --- | --- | --- |
  | M1h withdrawal window 30 → 14 days in its own section | `test_FR_0_8_01_owner_facts_appear_as_given` | `2 failed, 43 passed in 0.23s` |
  | E1 ", and our technology partners may also hear them" | `test_FR_0_8_01_owner_facts_appear_as_given` | `2 failed, 43 passed in 0.27s` |
  | E2 ", and to train and sell speech models" | `test_FR_0_8_01_owner_facts_appear_as_given` | `2 failed, 43 passed in 0.22s` |
  | E3 " within 7 days of your request" | `test_FR_0_8_01_owner_facts_appear_as_given` | `2 failed, 43 passed in 0.21s` |

  The second failure in each row is the parametrised break test, whose target text is no longer in the broken copy. The other six must-catch breaks (M1a to M1d, M2a, M2b) still fail their named tests (EVIDENCE, "Must-catch proof").
- **Scope:** `git diff -U0` of the test file shows hunks only at the import line and in the owner-fact block (`_approval_fact` through `test_FR_0_8_01_owner_facts_appear_as_given`). No document or production file changed.
- **Full fast suite and gate at `fdf0129`:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
1808 passed, 55 deselected in 322.30s (0:05:22)
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.8
aqis-audit-gate: base origin/main (merge-base f97f4929b4d5), head fdf012937ef6, approvals origin/main f97f4929b4d5, wp WP-0.8
Findings: 0
0 findings: OK (0.6 s)
```

### Debt recorded
F04 to F07 are DEBT-022 to DEBT-025 in `docs/progress/DEBT.md`, all with target WP-0.9, under the approval's round 2 condition. F08 is closed by the F02 fix.

### CI on the round 2 head
Commit `fa2c949`, PR #8. Every job is green:

| Run | Job | Conclusion |
| --- | --- | --- |
| 37048381022 | lab | success |
| 37048381022 | harness-regression | success |
| 37048388420 | lab | success |
| 37048388420 | harness-regression | success |

The pull-request `lab` job (110975378867) runs the gate with `--wp WP-0.8`:
```text
aqis-audit-gate: base origin/main (merge-base f97f4929b4d5), head 0c1459161e65, approvals origin/main f97f4929b4d5, wp WP-0.8
Findings: 0
0 findings: OK (0.4 s)
```
