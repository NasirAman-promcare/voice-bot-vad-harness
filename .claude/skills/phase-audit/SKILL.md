---
name: phase-audit
description: Full end-of-phase audit across all AQIS lab work packages in a phase, by the deep auditor. Use when the owner types /phase-audit followed by a phase number; wp-run launches the deep auditor with these steps itself for a phase's review WP.
disable-model-invocation: true
context: fork
agent: wp-auditor-deep
background: false
argument-hint: "[phase number, for example 1]"
---

Audit phase $ARGUMENTS as a whole.

1. Confirm every WP of the phase has an AUDIT.md with verdict PASS and is MERGED; list exceptions.
2. In a fresh, full (not shallow) clone under `/tmp` of the branch under review, or of `origin/main` when auditing merged work, install from the lock files exactly as documented, then run the full lab suite (fast plus slow CPU tests), the break suite with `--all`, and the phase's end-to-end smoke command.
3. Check each exit criterion in the phase overview with evidence. Blocking owner-run results must exist as committed reports; post-merge ones must all be done by phase exit. A missing one is MAJOR.
4. Traceability: trace 5 random result rows to run card, pack manifest version, clip, git commit and lock hash.
5. Reproducibility: re-run one run card and compare result hashes.
6. Regression: re-run the harness baseline command and compare; confirm no protected path changed without an approval or a spec allowance.
7. Process health: audit rounds per WP, owner touches per WP, debt rows opened and closed, decision records vetoed. Report them as numbers.
8. Write `docs/progress/PHASE-$ARGUMENTS-AUDIT.md` with the verdict, commit and push it, and return a summary.
