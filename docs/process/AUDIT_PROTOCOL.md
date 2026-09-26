# Audit protocol (version 2)

Used by the `wp-auditor` subagent for every work package, and by the builder as a self-check. Each item gets PASS, FAIL or N/A, a reason, and evidence: a command with an output excerpt, or `file:line`.

**What changed from version 1.** Mutation testing is now bounded: a fixed must-catch list (A6) plus at most 10 exploratory breaks in new or changed code (A15). Re-audits check the previous findings and what changed, not everything again. Only real risks block a pass. Version 1 treated every surviving code break as CRITICAL and let each round search wider, so audits could never converge.

## Items

| ID | Check | How |
| --- | --- | --- |
| A1 | Scope and dependencies | Dependencies are MERGED; branch is not `main`; approval on `main` says `STATUS: APPROVED` |
| A2 | Requirement coverage | Every requirement ID has an implementation, a test named after it that pytest actually collects, and an `EVIDENCE.md` entry |
| A3 | Acceptance commands | Re-run every acceptance command; outputs match the spec |
| A4 | Test suites and CI | Re-run the fast and slow suites; CI is green on the audited commit |
| A5 | Test integrity | No existing test modified or deleted without `ALLOW-EDIT`; no skip, xfail or trivial assert without a justified `audit-allow` |
| A6 | Must-catch proof | For every behaviour in the spec's "Must-catch behaviours" list, break it in a copy under `/tmp`; a named test must fail. If the spec has no list, stop and ask the owner for one |
| A7 | Compromise scan | Run the audit gate; read new functions for stubs, fake data, swallowed errors and values hard-coded to satisfy tests |
| A8 | Scope diff | Changes stay inside the plan's change budget; no protected path changed without approval |
| A9 | Capabilities | New modules have headers; registry updated; no row removed; linked tests exist and run |
| A10 | Contracts | Outputs validate against the relevant contracts |
| A11 | Environment parity | No absolute paths; one platform module; locks pinned; Python matches the Colab probe; owner-run checks listed |
| A12 | Reproducibility and traceability | Deterministic where the spec requires; result rows carry run card and clip IDs |
| A13 | Errors and logging | Failures raise or emit structured error events; nothing fails silently |
| A14 | Documentation, licences, data | Usage documented; `EVIDENCE.md` complete; licences present; no real personal data |
| A15 | Exploratory breaks (bounded) | At most 10 more breaks, chosen by risk, only in code added or changed since the last audited commit (first audit: the WP's new code) |

## Re-audits

A re-audit covers exactly:
1. each open finding from the previous report: fixed or not, with evidence;
2. items A1 to A15 applied to the diff since the last audited commit;
3. the full test suites, the gate, CI, and the complete must-catch proof (A6).

Code that passed an earlier audit and has not changed is not searched again.

## Severity

- **CRITICAL**: a requirement unmet; compromise; a protected path changed; test integrity broken; a must-catch behaviour that no test protects; CI red on the audited commit.
- **MAJOR**: evidence incomplete; parity risk; an owner-run check missing without an owner note; a traceability gap; an A15 break that survives and can make a check report success wrongly.
- **MINOR**: documentation, naming, and lower-risk behaviour without a test.

An A15 survivor is never CRITICAL.

## Verdict

**PASS** requires zero CRITICAL findings, and every MAJOR finding either fixed or accepted by the owner as debt. Accepted debt needs a CONDITIONS line in the approval naming the finding and a target WP, plus a row in `docs/progress/DEBT.md`. MINOR findings never block; the builder records them in `DEBT.md`.

Otherwise **FAIL**. Every report ends with a recommendation for each open finding: fix now, or accept as debt with a target WP.

## Convergence (round 3 onwards)

Compare finding counts by severity with the previous round, and say whether any open finding sits inside the must-catch list. If none does, recommend PASS with debt to the owner.
