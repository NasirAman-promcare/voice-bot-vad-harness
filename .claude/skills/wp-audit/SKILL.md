---
name: wp-audit
description: Manual entry point for an independent audit of an AQIS lab work package, run by the deep auditor in a forked context. Use only when the owner types /wp-audit; wp-run launches auditors itself.
disable-model-invocation: true
context: fork
agent: wp-auditor-deep
background: false
argument-hint: "[WP-ID]"
---

Audit work package $ARGUMENTS under `docs/process/AUDIT_PROTOCOL.md` version 3.

1. `git fetch origin main`. If `docs/progress/$ARGUMENTS/AUDIT.md` exists, this is a re-audit scoped to its open findings and the diff since its "Commit audited"; otherwise a first audit.
2. Run the bootstrap script if it exists, so tests run in the project environment.
3. Apply the items for the WP's tier (the spec's "Risk tier"; T1 if absent). Re-run every test, the break suite and every acceptance command yourself.
4. Write `docs/progress/$ARGUMENTS/AUDIT.md` from `docs/process/templates/AUDIT_REPORT.md`, set the status fragment to AUDIT-PASS or AUDIT-FAIL, and commit and push only those two files.
5. Return: verdict, counts by severity, blocking findings, findings you recommend accepting as debt (with target WP and whether the debt rule allows Claude to accept it), and owner-run checks still pending.
