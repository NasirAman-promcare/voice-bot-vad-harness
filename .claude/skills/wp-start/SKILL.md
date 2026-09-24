---
name: wp-start
description: Start an AQIS lab work package by writing a complete plan for owner approval, without changing any code. Use when the owner types /wp-start followed by a WP ID.
disable-model-invocation: true
effort: xhigh
argument-hint: "[WP-ID, for example WP-0.2]"
---

Plan work package $ARGUMENTS. Do not create or change any code, tests, locks or configuration in this skill.

1. Read `CLAUDE.md`, every file in `.claude/rules/`, `docs/specs/phase-0/00-PHASE-0-OVERVIEW.md`, and the spec file for $ARGUMENTS under `docs/specs/`. Read every file the spec lists under "Read first".
2. Check dependencies: every WP under "Depends on" must be MERGED in `docs/progress/STATUS.md`. If not, use the ask-owner skill.
3. Inspect the parts of the repository the spec touches, read-only. Note anything that contradicts the spec or the environment probes in `docs/environment/`.
4. Write `docs/progress/$ARGUMENTS/PLAN.md` from `docs/process/templates/WP_PLAN.md`:
   - Every requirement ID in the spec, each with: approach, files to create, existing files and functions to change (the change budget), tests to write (named by requirement ID), and the acceptance commands that prove it.
   - "Owner needs": everything required from the owner (data, access, network hosts, decisions, Colab or Oracle runs), and when it is needed.
   - Risks and open questions. Mark any requirement you believe cannot be met as written.
   - Deviations: write "None", or list each proposed deviation with its reason for the owner to accept or reject. Never deviate silently.
5. Set $ARGUMENTS to `PLANNED` in `docs/progress/STATUS.md`. Commit and push both files.
6. End with `🛑 OWNER ACTION NEEDED: review docs/progress/$ARGUMENTS/PLAN.md; if you agree, commit docs/approvals/$ARGUMENTS.md to main (template: docs/process/templates/APPROVAL.md)`, followed by your numbered questions.
