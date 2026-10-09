# Fragment formats

Each fragment is a small markdown file with `Key: value` lines first, then optional free text. One item per file; the file name is the ID. Generated tables are built from these on `main` only.

## Status: `docs/progress/status.d/<WP>.md`
```markdown
WP: WP-1.3
Title: Analyzer calibration
Status: IN-BUILD
Tier: T2
Size: M
Branch: claude/wp-1-3-calibration
PR: https://github.com/<owner>/<repo>/pull/<n>
Thread model: Sonnet high
Updated: 2026-10-14
Note: <one line, optional>
```
Status values: NOT-STARTED, PLANNED, IN-BUILD, READY-FOR-AUDIT, AUDIT-FAIL, AUDIT-PASS, MERGE-READY, MERGED, OWNER-RUN, BLOCKED. On `main`, AUDIT-PASS and MERGE-READY render as MERGED.

## Debt: `docs/progress/debt.d/DEBT-<WP>-<nn>.md`
```markdown
ID: DEBT-1.3-01
Status: OPEN               (OPEN | CLOSED)
Severity: MINOR            (MINOR | MAJOR)
Source: WP-1.3-F04
Target WP: WP-1.10
Accepted by: DEC-1.3-02    (or: owner, BLK-1.3-03)
What: <one line>
Closed by: <commit or WP, when closed>
```

## Test changes: `docs/progress/<WP>/TEST_CHANGES.md`
One row per modified existing test file:

| File | Test functions | Kind (add-cases, helper-refactor, rename) | Why | Assertions before, after |
| --- | --- | --- | --- | --- |

## Outsourcing ledger: `docs/outsourcing/ledger.d/<WO>.md`
```markdown
WO: WO-1.3-01
Date: 2026-10-14
Model: gemini-3.7-flash
Model version: <as returned by the API>
Attempts: 2
Prompt tokens: <sum>
Output tokens: <sum>
Result: ACCEPTED           (ACCEPTED | EXHAUSTED | QUESTIONS | REJECTED)
Seconds: <wall clock>
```
