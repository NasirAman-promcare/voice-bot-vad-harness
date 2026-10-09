---
name: wp-start
description: Plan an AQIS lab work package against its spec and self-approve the plan when it conforms, raising DECISION blockers only for real deviations. Use at the start of a WP, normally from wp-run.
effort: high
argument-hint: "[WP-ID]"
---

Plan work package $ARGUMENTS. Change no code, tests, locks or configuration in this skill.

1. Read the spec for $ARGUMENTS, the phase overview, every file the spec lists under "Read first", and the relevant lines of `docs/index/MAP.md`. Inspect only the code the spec's "Touches" names.
2. Write `docs/progress/$ARGUMENTS/PLAN.md` from `docs/process/templates/WP_PLAN.md`:
   - every requirement ID with approach, files, change budget, tests and acceptance command;
   - the must-catch list mapped to acceptance tests and break recipes;
   - the build split: what you write, what goes to work orders (rule of thumb in `.claude/rules/50-tokens-and-context.md`);
   - owner needs, each with its capability class and when it is needed;
   - deviations from the spec: "None", or each one with its reason.
3. Run the `plan-checker` agent on the spec and the plan. Fix every coverage gap it reports.
4. Decide:
   - No deviations, no guarded edits beyond the spec's list, no new dependency the spec does not allow: write `PLAN-STATUS: SELF-APPROVED (<date>, plan-checker clean)` at the top of the plan.
   - Otherwise: one DECISION blocker per deviation, with options and a recommendation. Mark the parts that do not depend on them; those proceed.
5. Set the status fragment to PLANNED (or IN-BUILD if self-approved), commit and push.

Never ask the owner to approve a conforming plan, and never deviate silently.
