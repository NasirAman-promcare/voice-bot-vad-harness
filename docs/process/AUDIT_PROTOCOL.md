# Audit protocol (version 3)

Used by the auditor agents for every work package, and by the builder as a self-check. Each item gets PASS, FAIL or N/A, a reason, and evidence: a command with an output excerpt, or `file:line`.

**What changed from version 2.** Depth follows the WP's risk tier. Must-catch proofs are break recipes that a script applies, so re-audits and CI check them without manual breaks. An advisory mutation report aims exploratory breaks. Rounds are capped. Claude may accept some MAJOR findings as debt inside the phase. Documentation WPs build no checker code unless their spec asks.

## Tiers

| Tier | Applies to | Auditor | Items |
| --- | --- | --- | --- |
| T1 | Contracts, scoring, data integrity, enforcement tooling (hooks, gates, relay, merge gate) | `wp-auditor-deep` (Opus, xhigh) | A1 to A15; up to 10 exploratory breaks |
| T2 | Ordinary lab code | `wp-auditor` (Opus, high) | A1 to A14; up to 3 exploratory breaks where risk shows |
| T3 | Documents, configuration, process records | `doc-checker` (Sonnet, medium) | The T3 checklist in `.claude/agents/doc-checker.md` |

The spec's "Risk tier" sets the tier; T1 if the spec does not say.

## Items

| ID | Check | How |
| --- | --- | --- |
| A1 | Scope, dependencies, plan | Dependencies MERGED; branch not `main`; plan self-approved with plan-checker clean, or approved DECISIONs; plan matches spec |
| A2 | Requirement coverage | Every requirement ID has an implementation, a collected test named after it, and an `EVIDENCE.md` entry |
| A3 | Acceptance commands | Re-run every acceptance command; outputs match the spec |
| A4 | Suites and CI | Re-run the fast suite (and slow where the spec needs it); CI green on the audited commit |
| A5 | Test integrity | No test deleted, skipped, xfailed or weakened; every modified test is in `TEST_CHANGES.md` as an allowed kind with no assertion weakened |
| A6 | Must-catch proof | The break suite for the WP: one recipe per must-catch behaviour, every recipe applies cleanly and its named tests fail. A missing or meaningless recipe is CRITICAL |
| A7 | Compromise scan | The audit gate; new functions read for stubs, fake data, swallowed errors, test-shaped values |
| A8 | Scope diff | Changes inside the change budget and the spec's "Touches"; guarded paths only where the spec or an approval allows; no NEVER path changed |
| A9 | Capabilities | Headers present and complete; no capability removed without a retirement record |
| A10 | Contracts | Outputs validate against the relevant contracts |
| A11 | Environment parity | No absolute paths; one platform module; locks pinned; owner-run checks listed and marked blocking or post-merge |
| A12 | Reproducibility, traceability | Deterministic where required; result rows carry run card and clip IDs |
| A13 | Errors and logging | Failures raise or emit structured error events; nothing fails silently |
| A14 | Documentation, licences, data | Usage documented; licences present; no real personal data; outsourced files pass the work-order review checklist |
| A15 | Exploratory breaks (bounded) | T1: up to 10; T2: up to 3. Only in code changed since the last audited commit, aimed by the mutation report |

## Re-audits
Exactly: each open finding (fixed or not, with evidence); the tier's items applied to the diff since the last audited commit; the suites, the gate, CI and the full break suite for the WP. Unchanged, previously audited code is not searched again.

## Severity
- **CRITICAL**: a requirement unmet; compromise; a NEVER path changed; test integrity broken; a must-catch behaviour without a working recipe and a failing test; CI red on the audited commit.
- **MAJOR**: evidence incomplete; parity risk; a blocking owner-run check missing; a traceability gap; an exploratory break that survives and can make a check report success wrongly.
- **MINOR**: documentation, naming, lower-risk behaviour without a test.
An exploratory-break survivor is never CRITICAL.

## Verdict and debt
**PASS** needs zero CRITICAL and every MAJOR fixed or accepted as debt. Claude may accept a MAJOR as debt only when all hold: the target WP is in the same phase; it touches no exit criterion and no must-catch behaviour; a decision record names it. Otherwise only the owner can accept it (a DECISION blocker). MINOR findings never block; the builder records them as debt fragments. Every report ends with a recommendation per open finding.

## Caps
Round 3: the report adds a convergence table (counts by severity per round, and whether any open finding is inside the must-catch list). Round 5: no further rounds without an owner DECISION (accept debt, amend the spec, or stop).

## Break recipe and mutation report
Recipe format: `docs/process/templates/BREAK_RECIPE.md`. The mutation report (`docs/progress/<WP>/MUTATION.md`, from CI) is advisory: it never blocks, it aims A15.
