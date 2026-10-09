---
name: wp-build
description: Build a planned AQIS lab work package test-first with evidence, writing small parts directly and sending bulk code to Gemini through work orders. Use during a WP, normally from wp-run.
effort: high
argument-hint: "[WP-ID]"
---

Build work package $ARGUMENTS from `docs/progress/$ARGUMENTS/PLAN.md`.

Preconditions: the plan says `PLAN-STATUS: SELF-APPROVED`, or the parts you build do not depend on an open DECISION. You are not on `main`. Run `git fetch origin main && git merge --no-edit origin/main`, then the bootstrap script.

For each requirement, in plan order:
1. Its tests exist and fail for the expected reason (acceptance tests were written in wp-run step 2; add unit tests as needed).
2. Implement:
   - **Outsourced parts**: use `wo-write`, then run the relay and read only its summary. On success, review with `docs/process/outsourcing/templates/WO_REVIEW_CHECKLIST.md`. On exhaustion, fix gaps under about 30 lines yourself, otherwise clarify the order or move it to a stronger model.
   - **Your parts**: implement inside the change budget, with the reuse ladder: existing module, standard library, a dependency already locked, one clear line, and only then new code.
3. Run the affected tests. Fix the code, never the test.
4. Update module headers (the Lab Map and registry are generated from them on `main`).
5. Record the requirement in `EVIDENCE.md` and commit `$ARGUMENTS <REQ-ID>: <what>`.

When every requirement is done:
- Run the break suite for $ARGUMENTS (or apply each recipe by hand until WP-1.0 lands) and record the result.
- Run every acceptance command in the spec and the full fast suite; paste real outputs into `EVIDENCE.md`.
- Run the audit gate and the progress lint. List owner-run checks with commands and expected outputs, each marked blocking or post-merge as the spec says.
- Push and wait for CI on the head. Never mark READY-FOR-AUDIT while any job is red or running.
- Return to wp-run step 4. Do not schedule check-ins or post pull request comments.

At any obstacle, climb the escalation ladder; ask the owner only for a capability.
