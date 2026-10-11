---
id: WO-1.0-04
wp: WP-1.0
title: Progress fragments, generated tables, owner queue, lint and migration
model: codestral-2508
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/ESCALATION.md
  - docs/process/AUTONOMY.md
  - docs/process/templates/FRAGMENTS.md
  - docs/process/templates/BLOCKER.md
  - docs/process/templates/DECISION.md
  - docs/progress/STATUS.md
  - docs/progress/BLOCKERS.md
  - docs/progress/DEBT.md
  - tests/aqis_lab/aqis_memo_testutil.py
  - tests/aqis_lab/test_aqis_phase0_memo.py
  - tests/aqis_lab/test_aqis_debt_wp06.py
  - tests/aqis_lab/test_aqis_debt_wp07.py
  - tests/aqis_lab/test_aqis_debt_wp08.py
  - tests/aqis_lab/test_aqis_debt_wp09.py
  - tests/aqis_lab/test_aqis_gate_parity.py
outputs:
  - tools/progress/__init__.py
  - tools/progress/__main__.py
  - tools/progress/fragments.py
  - tools/progress/render.py
  - tools/progress/lint.py
  - tools/progress/migrate.py
  - tools/progress/ids.py
  - tests/aqis_lab/progress/__init__.py
  - tests/aqis_lab/progress/test_fragments.py
  - tests/aqis_lab/progress/test_render.py
  - tests/aqis_lab/progress/test_lint.py
  - tests/aqis_lab/progress/test_migrate.py
  - tests/aqis_lab/progress/test_ids.py
steps:
  - tools/progress/__init__.py, tests/aqis_lab/progress/__init__.py, tools/progress/fragments.py, tests/aqis_lab/progress/test_fragments.py
  - tools/progress/lint.py, tests/aqis_lab/progress/test_lint.py
  - tools/progress/render.py, tests/aqis_lab/progress/test_render.py
  - tools/progress/ids.py, tests/aqis_lab/progress/test_ids.py
  - tools/progress/migrate.py, tests/aqis_lab/progress/test_migrate.py
  - tools/progress/__main__.py
read_only_tests:
  - tests/aqis_lab/progress/test_acceptance_wo_1_0_04.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/progress -q --tb=short
---

# WO-1.0-04 — Progress fragments, generated tables, owner queue, lint and migration

**Before sending (Claude):** add to `context` every test file found by `rg -l "STATUS.md|BLOCKERS.md|DEBT.md" tests/aqis_lab`; B11 depends on them. *(Done 2026-10-10: seven files.)*

## 1. Context
Parallel work packages used to collide on shared tables (`STATUS.md`, `BLOCKERS.md`, `DEBT.md`). From now on each item is one fragment file (formats in `FRAGMENTS.md`, `BLOCKER.md`, `DECISION.md`), and the tables plus an owner queue are generated on `main` only. The three legacy files in your context must be migrated without losing a word or an ID.

## 2. Your job
`python -m tools.progress <build | check | lint | migrate | new-id>` reads and validates fragments and renders the tables.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/progress/fragments.py` | Parse fragment files of each kind into records | `load_all(repo_root) -> Fragments` (status, blockers, debt, decisions, ledger rows, each with its source path); raises `FragmentError` with path and line | 300 |
| `tools/progress/lint.py` | Validate fragments | `lint(fragments, changed_only_paths=None) -> list[LintIssue]` | 250 |
| `tools/progress/render.py` | Render the tables and the owner queue | `render_all(fragments, on_main) -> dict[path, text]` | 300 |
| `tools/progress/ids.py` | Allocate the next free ID | `next_id(kind, wp, repo_root) -> str` for BLK, DEC, DEBT, WO | 120 |
| `tools/progress/migrate.py` | One-time migration of the legacy files | `migrate(repo_root, dry_run) -> MigrationReport` | 300 |
| `tools/progress/__main__.py` | Command line | `build [--on-main] [--out DIR]`, `check`, `lint [--changed-from REF]`, `migrate [--dry-run]`, `new-id --kind K --wp WP` | 150 |
| `tests/aqis_lab/progress/test_*.py` | Unit tests per module | | 300 each |

## 4. Required behaviour
- **B1** Fragment folders: `docs/progress/status.d/`, `blockers.d/`, `debt.d/`, `decisions.d/`, and `docs/outsourcing/ledger.d/`. A fragment is `Key: value` lines followed by free text; blocker and decision fragments follow their templates' labelled lines.
- **B2** Lint rules: the ID equals the file name without `.md`; IDs are unique per kind; new IDs match `<KIND>-<n>.<n>-<nn>`, legacy IDs (`BLK-001`, `DEBT-034`) are accepted only for migrated fragments marked `Legacy: yes`; status values are from the lists in `FRAGMENTS.md`; a blocker has `Owner capability` in {ACCESS, COMPUTE, EXTERNAL-AI, DECISION, PHYSICAL, KIT}, `Exact steps` numbered 1 to at most 7, `Time needed`, `Meanwhile`, and `Unblocks`; a decision has Options, Choice, Why, all six cannot-do lines answered `no`, and Reversal; a debt row has Severity, Source, Target WP and Accepted by.
- **B3** `lint --changed-from REF` checks only fragments changed since the merge base with REF (the stop gate uses this), always including uniqueness checks against all fragments.
- **B4** `build` renders `docs/progress/STATUS.md`, `BLOCKERS.md`, `DEBT.md`, `DECISIONS.md`, `OWNER_QUEUE.md` and `docs/outsourcing/LEDGER.md`, each starting `<!-- Generated by tools.progress; do not edit. -->`. Tables sort by WP number (numerically: WP-1.10 after WP-1.9), then ID.
- **B5** With `--on-main`, a status of AUDIT-PASS or MERGE-READY renders as MERGED (fragments reach `main` only through a merge).
- **B6** OWNER_QUEUE lists open blockers, decision records newer than the last digest date (line `Last digest: YYYY-MM-DD` at the top of the previous OWNER_QUEUE.md, or all ACTIVE ones if absent), and post-merge owner-run checks listed in status fragments as `Pending check: …`. Order: blockers by the number of WPs in `Unblocks` that are not MERGED (descending), then by age (oldest first); then decisions; then checks. Each blocker shows class, time and its exact steps.
- **B7** `check` renders into a scratch folder and exits 1 if any generated table differs from the committed one.
- **B8** `migrate` converts: each STATUS.md row into a status fragment; each `## BLK-…` entry of BLOCKERS.md into a blocker fragment containing the entry's original text verbatim below the labelled lines, with `Legacy: yes`, its status, and `Owner capability: legacy` allowed only for legacy fragments; each DEBT.md row into a debt fragment with `Legacy: yes` and the row's cells verbatim. A dry run prints what it would create; a real run refuses if any target file exists.
- **B9** `new-id` prints the next free ID for the kind and WP, considering fragments and existing work orders.
- **B10** Output is byte-identical across runs.
- **B11** The generated `STATUS.md`, `BLOCKERS.md` and `DEBT.md` keep the legacy files' exact structure: the same headings, intro lines, table columns and entry layout. Every existing test that reads them, including the WP-0.9 memo checks, must pass unmodified. New-style IDs and fields fit into that structure; extra fields go into the free text of an entry, never into new columns.

- **B12** Interface details the acceptance tests rely on (added by Claude with the acceptance test, 2026-10-10):
  - **Command line.** `python -m tools.progress` takes the repository root from `git rev-parse --show-toplevel` in the current directory; `--out` accepts an absolute path or one relative to it. Exit codes:
    - `lint`: 0 when there are no errors (warnings, such as E4, are printed but do not fail), 1 when there are errors. Every message names the fragment's path, or its ID.
    - `check`: 0 or 1 (B7).
    - `build`: 0, or non-zero on a `FragmentError`.
    - `migrate`: 0, or non-zero when it refuses. A refusal names every target file that already exists and writes nothing.
    - `new-id`: prints only the ID.
  - **Generated files.** Every generated file's first line is exactly `<!-- Generated by tools.progress; do not edit. -->`.
    - For `STATUS.md`, `BLOCKERS.md` and `DEBT.md`, the rest is the legacy layout (B11). Its headings and intro lines are constants in `render.py`, copied verbatim from the legacy files, and never read from a generated file.
    - **The round-trip rule:** with only the fragments `migrate` created, each of the three files is that first line followed by the legacy file, byte for byte.
  - **Legacy fragments.**
    - **Status.** `WP`, `Title`, `Status`, `Branch`, `PR`, `Updated` and `Legacy: yes`. The legacy cell `<branch>, PR <url>` is split into `Branch` and `PR`.
    - **Blocker.** `ID`, `Status` (from the entry's `STATUS:` line), `WP`, `Owner capability: legacy`, `Legacy: yes`, a blank line, then the entry's text verbatim, from its `## BLK-` heading to the line before the next entry.
    - **Debt.** `ID`, `Status` (the first word of the row's Status cell), `Target WP`, `Legacy: yes`, and the row itself as one line, exactly as in `DEBT.md`; rendering prints that line. To close a legacy row, Claude edits both `Status` and the row's Status cell, and adds `Closed by`. Lint checks that `Status` and the cell agree.
  - **New-style fragments.**
    - A debt fragment renders into the legacy columns: From finding = `Source`, What is limited = `What`, Risk = an optional `Risk` line, Accepted in = `Accepted by`.
    - New-style blockers render as entries in the same layout as legacy ones.
  - **Owner queue and ledger.** Each open blocker in `OWNER_QUEUE.md` shows its ID, capability class, time needed and exact steps; RESOLVED blockers are not listed. Ledger fragments of the Jules channel hold `not reported by the Jules channel` for figures that channel does not report. Lint accepts that text.

## 5. Edge cases you must handle
- **E1** A legacy blocker whose `Owner answer` is empty and status OPEN (as BLK-010 may be) → migrated as OPEN, shown in the owner queue.
- **E2** A fragment with Windows line endings or a trailing space after a key → accepted.
- **E3** Two fragments claiming the same ID → lint error naming both paths.
- **E4** A status fragment for a WP not in any spec → lint warning, not an error.

## 6. Never
- Never edit or delete a fragment while rendering.
- Never alter legacy text during migration.
- Never treat a parse error as an empty fragment.

## 7. When this order is wrong or incomplete
Return QUESTIONS if a legacy file in your context has a structure this order does not describe.

## 8. Must-catch behaviours
1. Lint rejects a blocker without a valid capability class.
2. Lint rejects duplicate IDs and an ID that differs from its file name.
3. Migration keeps every legacy BLK and DEBT ID and its text verbatim (the rendered tables contain all of them).
4. The owner queue orders blockers by how many unmerged WPs they unblock.
5. Rendering is byte-identical across runs.
6. `--on-main` renders AUDIT-PASS and MERGE-READY as MERGED.
7. Existing tests that read `STATUS.md`, `BLOCKERS.md` or `DEBT.md` pass unmodified against the generated files.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B12 and E1 to E4 are implemented; point at each.
- **D3** Unit tests use scratch directories only.
- **D4** `tests/aqis_lab/progress/test_acceptance_wo_1_0_04.py` passes unmodified.
- **D5** No placeholder or swallowed error.
