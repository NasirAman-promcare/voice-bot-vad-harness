---
name: surgical-fix
description: Fix a bug, a failed audit finding or a failed owner-run check in existing AQIS lab code without breaking, removing or weakening anything else. Use whenever an existing file must be corrected.
effort: high
argument-hint: "[problem description, audit finding ID or report path]"
---

Fix: $ARGUMENTS

1. **Reproduce.** Write a failing test that captures the problem, named after the finding or requirement ID. Run it and show the failure.
2. **Locate.** Read the module header, registry rows and callers. Write a change budget in `docs/progress/<WP>/FIXES.md`: file, functions to change, root cause, capabilities at risk.
3. **Baseline.** Run the module's tests and every capability test linked to the file; record the results.
4. **Change only the budget.** Fix the root cause, not the symptom. No refactors, renames or formatting changes anywhere else.
5. **Verify.** The new test passes; every baseline test still passes; `git diff -U0` touches only budgeted functions; the audit gate passes; CI is green on the pushed commit.
6. **Fix the category, not only the instance.** When a finding says a behaviour has no test, look for sibling behaviours in the same function with the same gap and cover them too, inside the change budget.
7. **Record.** Update the header change log and the registry. Add the evidence to `FIXES.md`.
8. **Escalate.** If the fix needs changes outside the budget, to existing tests or to capabilities, use the ask-owner skill instead.
