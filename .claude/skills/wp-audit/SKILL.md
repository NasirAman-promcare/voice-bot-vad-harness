---
name: wp-audit
description: Independent audit of an AQIS lab work package by the wp-auditor subagent. Use when the owner types /wp-audit followed by a WP ID.
disable-model-invocation: true
context: fork
agent: wp-auditor
background: false
argument-hint: "[WP-ID]"
---

Audit work package $ARGUMENTS independently.

Inputs: the spec for $ARGUMENTS under `docs/specs/`, `docs/progress/$ARGUMENTS/PLAN.md`, `docs/approvals/$ARGUMENTS.md`, `docs/progress/$ARGUMENTS/EVIDENCE.md`, and this branch's diff against `origin/main`.

1. Run `git fetch origin main`, then `git diff --stat origin/main...HEAD` and read the full diff.
2. If `aqis_lab/deploy/dev_bootstrap.sh` exists, run it so tests run in the project environment.
3. Work through `docs/process/AUDIT_PROTOCOL.md` items A1 to A14 in order. Re-run every test and acceptance command yourself.
4. Write `docs/progress/$ARGUMENTS/AUDIT.md` from `docs/process/templates/AUDIT_REPORT.md`, including the finding table and the verdict.
5. Set $ARGUMENTS in `docs/progress/STATUS.md` to `AUDIT-PASS` or `AUDIT-FAIL`. Commit and push only AUDIT.md and STATUS.md.
6. Return a short summary: verdict, finding counts by severity, the most important findings, and owner-run checks still pending.
