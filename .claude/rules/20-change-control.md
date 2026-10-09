# Change control and regression protection

Before editing an existing file: read its module header and its rows in `docs/index/MAP.md`; write the exact functions you will change (your change budget, matching the plan); run its tests and linked capability tests and record the result.

While editing: change only budgeted functions and keep everything else byte-identical. Never remove, rename or weaken a capability listed in a header. Never reformat or "clean up" unrelated code.

After editing: re-run the file's tests and every linked capability test; update the header's change log; check `git diff -U0` stays inside the budget.

## Guarded paths
Edit a guarded path only when the WP spec on `main` lists it under "Allowed guarded edits" (from WP-1.0's hook update) or an owner approval file on `main` lists it with `ALLOW-EDIT:`. NEVER paths cannot be unlocked by you.

## Existing tests
Allowed, each named in `docs/progress/<WP>/TEST_CHANGES.md` and confirmed by the auditor:
- adding cases;
- refactoring a helper or fixture without changing any assertion;
- renaming a test.
Never without the owner: deleting a test, adding skip or xfail, removing or weakening an assertion. Until WP-1.0's hooks are installed, any edit to an existing test still needs an `ALLOW-EDIT:` approval.

## Parallel-safe records
- Never edit the generated tables (`STATUS.md`, `BLOCKERS.md`, `DEBT.md`, `DECISIONS.md`, `OWNER_QUEUE.md`, `docs/index/*`, `docs/capabilities/REGISTRY.md` once generated). Write fragments instead: `docs/progress/status.d/<WP>.md`, `blockers.d/`, `debt.d/`, `decisions.d/` (formats in `docs/process/templates/FRAGMENTS.md`).
- New IDs carry their WP: `BLK-1.3-01`, `DEC-1.3-01`, `DEBT-1.3-01`, findings `WP-1.3-F01`, work orders `WO-1.3-01`. Legacy IDs (BLK-001, DEBT-034) keep their names.
- Touch only the paths your WP's "Touches" list names; overlapping paths with a running WP is a coordination problem for the coordinator, not something to resolve by editing their files.
