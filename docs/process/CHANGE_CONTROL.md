# Change control (version 2)

This keeps later work from quietly removing or weakening what already works: a readable header in every module, a registry generated from those headers, a change budget for every edit, and fragments instead of shared tables.

## 1. Module header
Every Python module in `aqis_lab/`, `tools/` and `kit-staging/` starts with a docstring in this form. The Lab Map, the registry and the outsourcing header check all read it.

```text
"""Short purpose of the module in one line.

CAPABILITIES:
  CAP-<AREA>-<NNN>: what it does [tests: test_FR_1_2_01_..., test_FR_1_2_04_...]
INPUTS AND OUTPUTS: what goes in and what comes out, in one or two lines.
CONTRACTS: event-log v1, run-card v1 (only those that apply).
INVARIANTS:
  - Things that must stay true.
NOT IN SCOPE:
  - What this module deliberately does not do.
CHANGE LOG:
  2026-10-12 WP-1.2 FR-1.2-01 created.
"""
```

## 2. Capability registry
`docs/capabilities/REGISTRY.md` is generated on `main` from module headers (from WP-1.0). A capability that disappears from every header fails CI unless `docs/capabilities/retired.d/<CAP-ID>.md` records its retirement, with the WP and the owner decision or decision record that allowed it. Rows are never deleted silently.

## 3. Change budget
Before editing an existing file, the plan names the exact functions that will change. After the edit, `git diff -U0` shows changes only inside those functions, and every test linked to the file's capabilities still passes.

## 4. Guarded-path allowances
Two sources, both read only from `origin/main`:
- the WP spec's section `## Allowed guarded edits`, one path or pattern per line (applies only on that WP's branch, from WP-1.0's hook update);
- owner approval files in `docs/approvals/<ID>.md` with `STATUS: APPROVED` and `ALLOW-EDIT:` lines (legacy, still honoured).
NEVER paths in `PROTECTED_PATHS.txt` cannot be unlocked; the owner edits them.

## 5. Existing tests
Allowed kinds, each recorded in `docs/progress/<WP>/TEST_CHANGES.md` (format in `templates/FRAGMENTS.md`) and confirmed by the auditor: adding cases; refactoring a helper or fixture without changing any assertion; renaming. Never without the owner: deleting a test, adding skip or xfail, removing or weakening an assertion. From WP-1.0, the stop gate blocks a modified test whose assertion count fell or which gained a skip marker, even with a record.

## 6. Fragments and IDs
Shared tables become one file per item (formats in `templates/FRAGMENTS.md`, `templates/BLOCKER.md`, `templates/DECISION.md`):

| Kind | Fragment | Generated table (on `main` only) |
| --- | --- | --- |
| Status | `docs/progress/status.d/<WP>.md` | `docs/progress/STATUS.md` |
| Blocker | `docs/progress/blockers.d/<BLK-ID>.md` | `BLOCKERS.md`, `OWNER_QUEUE.md` |
| Debt | `docs/progress/debt.d/<DEBT-ID>.md` | `DEBT.md` |
| Decision | `docs/progress/decisions.d/<DEC-ID>.md` | `DECISIONS.md` |
| Outsourcing | `docs/outsourcing/ledger.d/<WO-ID>.md` | `docs/outsourcing/LEDGER.md` |

New IDs carry the WP: `BLK-1.3-01`, `DEC-1.3-01`, `DEBT-1.3-01`, `WO-1.3-01`; findings stay `WP-1.3-F01`. Legacy IDs keep their names and are migrated to fragments by WP-1.0. Branches never regenerate the tables, so parallel WPs never conflict on them.
