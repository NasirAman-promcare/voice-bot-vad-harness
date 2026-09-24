# Change control

This keeps later fixes from quietly removing or weakening what already works. It combines a readable header in every module, a registry that links each capability to its tests, and a change budget for every edit.

## 1. Module header

Every Python module in `aqis_lab/` and `tools/` starts with a docstring in this form:

```python
"""Short purpose of the module in one line.

CAPABILITIES:
  CAP-CONTRACTS-001: validates event-log records against schema v1 [tests: test_FR_0_2_01_valid_event, test_FR_0_2_04_reports_json_pointer]
  CAP-CONTRACTS-002: computes stable run-card IDs [tests: test_FR_0_2_05_run_card_id_stable]
INPUTS AND OUTPUTS: what goes in and what comes out, in one or two lines.
CONTRACTS: event-log v1, run-card v1 (only the ones that apply).
INVARIANTS:
  - Things that must stay true, for example "never writes outside the output directory".
NOT IN SCOPE:
  - What this module deliberately does not do.
CHANGE LOG:
  2026-09-25 WP-0.2 FR-0.2-01 created.
"""
```

A docstring, not loose comments, so tools can read and check it.

## 2. Capability registry

`docs/capabilities/REGISTRY.md` has one row per capability: ID, module, functions, description, tests, introducing WP and requirement, and status. Rows are never deleted. Retiring a capability needs an owner approval ID in its status column.

## 3. Change budget

Before editing an existing file, the plan names the exact functions that will change. The builder changes nothing else. After the edit, `git diff -U0` must show changes only inside those functions, and every test linked to the file's capabilities must still pass.

## 4. Approval files

Only the owner writes approval files, and only on `main`, in `docs/approvals/<ID>.md`. The hooks read them from `origin/main`, so an approval created on a work branch has no effect. Format:

```text
STATUS: APPROVED
WP: WP-0.2
APPROVED-BY: owner
DATE: 2026-09-25
EXPIRES: 2026-10-31                       (optional)
CONDITIONS:
- Anything the builder must do differently from the plan.
ALLOW-EDIT: vad_adapters/some_file.py      (optional; unlocks one guarded path or pattern)
ALLOW-PATTERNS-IN: tools/audit/patterns.py (optional; exempts a file from the compromise scan)
```

`ALLOW-EDIT` also covers modifying or deleting an existing test. Paths in the NEVER list of `PROTECTED_PATHS.txt` cannot be unlocked; the owner edits those directly.
