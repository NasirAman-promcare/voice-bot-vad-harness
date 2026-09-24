---
name: wp-build
description: Build an approved AQIS lab work package exactly as planned, test-first, with evidence. Use when the owner types /wp-build followed by a WP ID.
disable-model-invocation: true
effort: high
argument-hint: "[WP-ID]"
---

Build work package $ARGUMENTS.

Preconditions (use the ask-owner skill if any fails):
1. Run `git fetch origin main && git merge --no-edit origin/main` to pick up the owner's approval.
2. `docs/approvals/$ARGUMENTS.md` exists and contains `STATUS: APPROVED`. Its conditions override the plan.
3. `docs/progress/$ARGUMENTS/PLAN.md` exists. You are not on `main`.
4. If `aqis_lab/deploy/dev_bootstrap.sh` exists, run it first.

For each requirement, in plan order:
1. Write its tests first, named by requirement ID. Run them and confirm they fail for the expected reason.
2. Implement the real behaviour inside the change budget.
3. Run the requirement's tests, then the fast suite. Fix the code, never the test.
4. Add or update the module header and the `docs/capabilities/REGISTRY.md` rows.
5. Record the requirement in `docs/progress/$ARGUMENTS/EVIDENCE.md` (template: `docs/process/templates/EVIDENCE.md`).
6. Commit with the message `$ARGUMENTS <REQ-ID>: <what>`, then push.

At any blocker, use the ask-owner skill immediately.

When every requirement is done:
- Run every acceptance command in the spec and paste the real outputs into `EVIDENCE.md`.
- Run the audit gate if it exists. List owner-run checks (Colab, Oracle) with exact commands and expected outputs.
- Self-check against `docs/process/AUDIT_PROTOCOL.md` and fix what you find.
- Set STATUS to `READY-FOR-AUDIT`, open or update the pull request to `main`, and end with `✅ READY FOR AUDIT — owner: run /wp-audit $ARGUMENTS`, followed by the owner-run checks.
