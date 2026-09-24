---
name: phase-audit
description: Full end-of-phase audit across all AQIS lab work packages in a phase. Use when the owner types /phase-audit followed by a phase number.
disable-model-invocation: true
context: fork
agent: wp-auditor
background: false
argument-hint: "[phase number, for example 0]"
---

Audit phase $ARGUMENTS as a whole.

1. Confirm every WP of the phase has an AUDIT.md with verdict PASS and status MERGED; list exceptions.
2. In a fresh clone of `origin/main` under `/tmp`, install from the lock files exactly as documented, run the full lab test suite (fast plus slow CPU tests), and run the phase's end-to-end smoke command.
3. Check each exit criterion in `docs/specs/phase-$ARGUMENTS/00-PHASE-$ARGUMENTS-OVERVIEW.md` with evidence. Owner-run results (Colab, Oracle) must exist as committed reports; a missing one is a MAJOR finding.
4. Traceability: pick 5 random result rows and trace each to its run card, pack manifest version, clip, git commit and lock hash.
5. Reproducibility: re-run one run card and compare result hashes.
6. Regression: re-run the harness baseline command from `docs/baselines/harness_tests_baseline.md` and compare; confirm no protected path changed during the phase without an approval.
7. Write `docs/progress/PHASE-$ARGUMENTS-AUDIT.md` with the verdict, commit and push it, and return a summary.
