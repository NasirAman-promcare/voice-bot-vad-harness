# AUDIT — <WP-ID>, round <n>

Auditor: <wp-auditor | wp-auditor-deep | doc-checker> · Tier: <T1 | T2 | T3> · Date: <YYYY-MM-DD> · Commit audited: `<sha>` · Previous audited commit: <sha or "first audit"> · Protocol: version 3

## Verdict: PASS | FAIL
CRITICAL: <n> · MAJOR: <n> (fixed <n>, accepted as debt <n>, open <n>) · MINOR: <n>

## Scope of this audit
<First audit, or re-audit: open findings, diff since the previous audited commit, suites, CI, break suite.>

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| The tier's items, one row each | | |

## Must-catch proof (A6, break suite)
| Recipe | Behaviour | Applies cleanly | Named tests failed | Meaningful? |
| --- | --- | --- | --- | --- |

## Exploratory breaks (A15: T1 up to 10, T2 up to 3)
| Break | Where | Aimed by | Survived? | Severity |
| --- | --- | --- | --- | --- |

## Test changes reviewed
| File | Kind recorded | Assertions weakened? | Verdict |
| --- | --- | --- | --- |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or debt (target WP; Claude may accept / owner must) |
| --- | --- | --- | --- | --- | --- |

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |

## For the owner
- audit-allow lines: <list or None>
- Allowances used (spec or approval): <list>
- Decision records touching this audit: <list or None>
- Owner-run checks still pending (blocking / post-merge): <list or None>
