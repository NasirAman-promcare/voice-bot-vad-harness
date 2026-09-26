---
name: wp-audit
description: Independent audit of an AQIS lab work package by the wp-auditor subagent. Use when the owner types /wp-audit followed by a WP ID.
disable-model-invocation: true
context: fork
agent: wp-auditor
background: false
argument-hint: "[WP-ID]"
---

Audit work package $ARGUMENTS under `docs/process/AUDIT_PROTOCOL.md` version 2.

1. Run `git fetch origin main`. If `docs/progress/$ARGUMENTS/AUDIT.md` exists, read its "Commit audited" value: this is a re-audit, scoped to the previous findings, the diff since that commit, the full suites, CI and the complete must-catch proof. Otherwise it is a first audit.
2. If `aqis_lab/deploy/dev_bootstrap.sh` exists, run it so tests run in the project environment.
3. Work through items A1 to A15. Re-run every test and acceptance command yourself. Keep code breaks within A6 and A15.
4. Write `docs/progress/$ARGUMENTS/AUDIT.md` from `docs/process/templates/AUDIT_REPORT.md`, including the round number, the finding table with a recommendation for each finding, and the verdict.
5. Set $ARGUMENTS in `docs/progress/STATUS.md` to `AUDIT-PASS` or `AUDIT-FAIL`. Commit and push only AUDIT.md and STATUS.md.
6. Return a short summary: verdict, counts by severity, the findings that block a pass, the ones you recommend accepting as debt, and owner-run checks still pending.
