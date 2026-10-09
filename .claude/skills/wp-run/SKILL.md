---
name: wp-run
description: Run an AQIS lab work package end to end (plan, acceptance tests, build or outsource, independent audit, scoped fixes, merge gate, closeout), asking the owner only for owner capabilities. Use whenever asked to run, start or continue a WP.
effort: high
argument-hint: "[WP-ID, for example WP-1.3]"
---

Run work package $ARGUMENTS to MERGED. Rules that govern every step: `CLAUDE.md`, `.claude/rules/`, `docs/process/AUTONOMY.md`, `docs/process/ESCALATION.md`.

## 0. Orient (cheaply)
1. Read the spec for $ARGUMENTS under `docs/specs/` and the phase overview's dependency graph. Every dependency must be MERGED; if not, report that to the coordinator and stop (this is not an owner question).
2. Read `docs/index/MAP.md` and only the files the spec's "Read first" and "Touches" name.
3. If a branch and status fragment for $ARGUMENTS already exist, resume from the recorded status instead of starting over.
4. Create or update `docs/progress/status.d/$ARGUMENTS.md` (format `docs/process/templates/FRAGMENTS.md`). Branch: `claude/wp-<x>-<y>-<slug>`.

## 1. Plan
Follow the `wp-start` skill. It ends either with `PLAN-STATUS: SELF-APPROVED` (continue) or with DECISION blockers (continue every part that does not depend on them).

## 2. Acceptance tests first
Write the must-catch acceptance tests and one break recipe per must-catch behaviour (`docs/process/templates/BREAK_RECIPE.md`). Run them; they must fail for the expected reason. Commit and push.

## 3. Build
Follow the `wp-build` skill. Parts the plan marks for outsourcing go through `wo-write` and the relay. Until the relay exists (WP-1.0), an outsourced part is an EXTERNAL-AI request for Jules or AI Studio.

## 4. Ready for audit
The full fast suite, the audit gate, the break suite and CI are green on the pushed head. Set the status fragment to READY-FOR-AUDIT.

## 5. Independent audit
Launch the auditor with the Agent tool, a fresh context every time: `wp-auditor-deep` for tier T1, `wp-auditor` for T2, `doc-checker` for T3. The prompt contains only: the WP ID, the round number, the previous audited commit (if any), and "Audit under docs/process/AUDIT_PROTOCOL.md version 3; write docs/progress/$ARGUMENTS/AUDIT.md; return the summary." Never pass your own notes, reasoning or opinion of the code. For a phase's review WP, also launch `wp-auditor-deep` with "Follow the steps in .claude/skills/phase-audit/SKILL.md for phase <n>."

## 6. Fix loop
On FAIL, follow `surgical-fix` for the blocking findings, then return to step 4 and re-audit (scoped). Round 3 needs a convergence memo in `AUDIT.md`'s companion `FIXES.md`. Round 5 is a DECISION blocker. If the thread model is Sonnet and the WP needs a third round, tell the coordinator so it can move the fixes to Opus.

## 7. Owner-run checks
Checks the spec marks `blocking` must have a committed PASS report before merging: request them once, batched, as COMPUTE blockers with exact steps. Checks marked `post-merge` go into the queue and do not hold the merge.

## 8. Merge
Follow the `wp-merge` skill.

## 9. Closeout
Report to the coordinator (or the owner) in at most 10 lines: merged commit, debt rows created, decision records the owner should review, blockers still open, and anything later WPs must know (also saved to project memory when in a Project). Stop watching the pull request. Do not start another WP in this thread.

At every step: climb the escalation ladder before asking; never ask for something the rules let you do; never idle while independent work remains.
