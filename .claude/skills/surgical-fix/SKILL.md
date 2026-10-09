---
name: surgical-fix
description: Fix a bug, an audit finding or a failed owner-run check in existing AQIS lab code without breaking, removing or weakening anything else, within attempt budgets. Use whenever existing code must be corrected.
effort: high
argument-hint: "[finding IDs, problem description or report path]"
---

Fix: $ARGUMENTS

1. **Reproduce.** Write a failing test named after the finding or requirement ID. Show the failure.
2. **Locate.** Read the module header, its MAP and CALLERS lines, and the callers. Write the change budget in `docs/progress/<WP>/FIXES.md`: file, functions, root cause, capabilities at risk.
3. **Baseline.** Run the module's tests and its linked capability tests; record the result.
4. **Route.**
   - Code that came from a work order and needs more than about 30 changed lines: send a fix order through the relay (`docs/process/outsourcing/templates/FIX_ORDER.md`), naming only the files allowed to change.
   - Otherwise fix it yourself, inside the budget. Fix the root cause, not the symptom.
5. **Verify.** The new test passes, the baseline still passes, `git diff -U0` stays inside the budget, the gate and the break suite pass, and CI is green on the pushed head.
6. **Fix the category.** If a finding says a behaviour has no test, cover its sibling behaviours in the same function too, inside the budget.
7. **Existing tests.** Only the allowed kinds (rule 20), each recorded in `docs/progress/<WP>/TEST_CHANGES.md` with the reason.
8. **Record.** Header change log, `FIXES.md` evidence.

Budgets: at most 2 attempts per finding with one approach, then change strategy, then a second opinion (ladder). A finding that comes back in two consecutive rounds probably means the spec is ambiguous: raise it as a DECISION with the competing readings.
