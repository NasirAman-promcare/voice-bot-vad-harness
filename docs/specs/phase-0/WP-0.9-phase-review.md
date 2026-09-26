# WP-0.9 — Phase 0 review

- **Depends on**: WP-0.0 to WP-0.8
- **Runs on**: cloud VM

## Goal
Close phase 0 with evidence, and hand phase 1 a clean start.

## Functional requirements
- **FR-0.9-01** `docs/progress/PHASE0_MEMO.md`: each exit criterion E1 to E6 with its evidence link; decisions taken; open issues; lessons for the process.
- **FR-0.9-02** Phase 1 prerequisites: campaign A recruiting status, pack v1 plan, the GPU budget used so far from the unit log.
- **FR-0.9-03** Run `/phase-audit 0`; the memo links its report.

## Acceptance
- **AT-0.9-01** `/phase-audit 0` returns PASS.

## Must-catch behaviours
1. Each exit criterion E1 to E6 links to evidence that exists.
2. Every open debt row in `docs/progress/DEBT.md` targeting phase 0 is either closed or moved to a named later WP, with the owner's approval.
