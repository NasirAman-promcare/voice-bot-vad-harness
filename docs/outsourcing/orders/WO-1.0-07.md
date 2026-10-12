---
id: WO-1.0-07
wp: WP-1.0
title: Hook updates (spec allowances, stop gate v4, session context v2), staged
model: default
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 65000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/AUTONOMY.md
  - docs/process/ESCALATION.md
  - docs/process/PROTECTED_PATHS.txt
  - docs/outsourcing/refs/claude-code-hooks.md
  - .claude/hooks/_protected.py
  - .claude/hooks/guard_protected.py
  - .claude/hooks/stop_gate.py
  - .claude/hooks/session_context.py
  - .claude/hooks/.gitignore
  - docs/process/templates/FRAGMENTS.md
  - tests/aqis_lab/fixture_repo.py
  - tests/aqis_lab/test_aqis_gate_parity.py
  - tests/aqis_lab/test_aqis_gate_v2.py
  - tests/aqis_lab/test_aqis_debt_wp09.py
interfaces:
  - tools/index/__main__.py
  - tools/progress/__main__.py
  - tools/progress/render.py
outputs:
  - kit-staging/.claude/hooks/_protected.py
  - kit-staging/.claude/hooks/guard_protected.py
  - kit-staging/.claude/hooks/stop_gate.py
  - kit-staging/.claude/hooks/session_context.py
  - kit-staging/.claude/hooks/.gitignore
  - tests/aqis_lab/kit/__init__.py
  - tests/aqis_lab/kit/test_protected_v4.py
  - tests/aqis_lab/kit/test_guard_v4.py
  - tests/aqis_lab/kit/test_stop_gate_v4.py
  - tests/aqis_lab/kit/test_session_context_v2.py
steps:
  - kit-staging/.claude/hooks/_protected.py, tests/aqis_lab/kit/__init__.py, tests/aqis_lab/kit/test_protected_v4.py
  - kit-staging/.claude/hooks/guard_protected.py, tests/aqis_lab/kit/test_guard_v4.py
  - kit-staging/.claude/hooks/stop_gate.py, tests/aqis_lab/kit/test_stop_gate_v4.py
  - kit-staging/.claude/hooks/session_context.py, kit-staging/.claude/hooks/.gitignore, tests/aqis_lab/kit/test_session_context_v2.py
read_only_tests:
  - tests/aqis_lab/kit/test_acceptance_wo_1_0_07.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/kit/test_protected_v4.py tests/aqis_lab/kit/test_guard_v4.py tests/aqis_lab/kit/test_stop_gate_v4.py tests/aqis_lab/kit/test_session_context_v2.py tests/aqis_lab/kit/test_acceptance_wo_1_0_07.py tests/aqis_lab/test_aqis_gate_parity.py tests/aqis_lab/test_aqis_gate_v2.py tests/aqis_lab/test_aqis_debt_wp09.py -q --tb=short
---

# WO-1.0-07 — Hook updates (spec allowances, stop gate v4, session context v2), staged

**Before sending (Claude):** save the current Claude Code hooks reference sections for PreToolUse, PostToolUse, Stop and SessionStart input and output to `docs/outsourcing/refs/claude-code-hooks.md`, and add to `context` every test file found by `rg -l "stop_gate|_protected" tests/aqis_lab` (the WP-0.0 parity tests import the hook's tables and parse its messages). Add the same test files to the `verify` command; WO-1.0-08 shares `tests/aqis_lab/kit`, so `verify` names files, never the folder. *(Done 2026-10-10. The reference is `docs/outsourcing/refs/claude-code-hooks.md`. The search finds seven files: four are about the hooks and are added; three match only by chance and are left out: `tests/aqis_lab/ci/test_wp_1_0_requirements.py`, `outsourcing/test_acceptance_wo_1_0_01.py` and `outsourcing/test_workorder.py`.)*

## 1. Context
The four hooks in your context enforce the lab's rules today (stop gate version 3). Under the new operating model, guarded-path allowances may also come from the WP spec, allowed kinds of test change are permitted with a record, blocker fragments are linted, and the stop gate runs only the tests a change affects. You write the new versions into `kit-staging/.claude/hooks/`; after audit the owner copies them into `.claude/`. Hooks follow the attached reference exactly.

## 2. Your job
Produce version 4 of the stop gate and updated guard, protected-path and session-context hooks, starting from the current files and keeping every existing behaviour unless this order changes it.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `kit-staging/.claude/hooks/_protected.py` | Protected-path classification, approvals, and now spec allowances and the current WP | everything the current file offers, unchanged, plus `current_wp(root) -> str or None` and `spec_allowances(root, ref, wp) -> list[pattern]` | 400 |
| `kit-staging/.claude/hooks/guard_protected.py` | PreToolUse guard for Edit, Write, NotebookEdit | unchanged entry point | 200 |
| `kit-staging/.claude/hooks/stop_gate.py` | Stop hook version 4 | unchanged entry point; `HOOK_VERSION = "4"` | 400 per file; split helpers into `_stopgate_*.py` siblings if needed (add them to outputs via QUESTIONS first) |
| `kit-staging/.claude/hooks/session_context.py` | SessionStart context, at most 15 lines | unchanged entry point | 150 |
| `kit-staging/.claude/hooks/.gitignore` | Same content as today | | 10 |
| `tests/aqis_lab/kit/test_*.py` | Tests that run each hook as a subprocess with real JSON input in scratch git repositories | | 300 each |

## 4. Required behaviour
- **B1** `current_wp`: from a branch named `claude/wp-<x>-<y>-<slug>` → `WP-<x>.<y>`; otherwise from the status fragment in `docs/progress/status.d/` whose `Branch:` equals the current branch; otherwise none.
- **B2** `spec_allowances(root, ref, wp)`: read, with `git show` at `ref` (normally `origin/main`, fetched if missing; none if still missing, i.e. fail closed), the spec file `docs/specs/**/<wp>-*.md`; return the `- <pattern>` lines of its `## Allowed guarded edits` section, ignoring `None`. Never read the spec from the working tree.
- **B3** The guard allows a GUARDED path when an approved `ALLOW-EDIT` line on `origin/main` matches (as today) or a spec allowance for the current WP matches. NEVER paths stay blocked. On bad input or an internal error the guard blocks (fail closed), as today.
- **B4** Stop gate test selection: when `tools/index` exists, run `python -m tools.index impact --base origin/main`; run the listed tests, or the full fast suite when it prints `all`, fails, or the tool is missing. When the WP's status fragment in the working tree says READY-FOR-AUDIT, always run the full fast suite. Keep version 3's caching by lab fingerprint.
- **B5** Existing-test changes: a modified existing test file passes only if `docs/progress/<WP>/TEST_CHANGES.md` has a row naming it, and, for every test function in it: the function still exists; its count of `assert` statements plus `pytest.raises` and `pytest.warns` blocks did not fall; it gained no skip or xfail (decorators, `pytest.skip(`, `pytest.xfail(`, `pytestmark`). Compare with the `origin/main` version using `ast`. A deleted test file, a deleted test function, a fallen assertion count or a new skip blocks even with a record. Without a record, behave as version 3 (an approval is needed).
- **B6** Blocker lint: when `tools/progress` exists, run `python -m tools.progress lint --changed-from origin/main`; any issue blocks with the lint's own messages.
- **B7** Keep the scanned directories and every pattern table exactly as version 3 has them. The audit gate's parity tests compare these tables with `tools/audit/patterns.py`, so any change would break `main` until both sides change together. Code in `kit-staging/` is scanned by the relay's checks instead, and audited at T1. Lines that must hold a flagged pattern (the copied pattern tables, and the documented fail-closed and fail-safe handlers of B3 and B10) end with `# audit-allow: <reason>`; a trailing comment leaves a table's values unchanged. If the parity tests compare source lines rather than values, return QUESTIONS.
- **B8** What Claude sees is at most 40 lines; the full report goes to `.git/aqis-stop-gate.log`.
- **B9** Keep every version 3 behaviour not changed here: NEVER and GUARDED change detection since the merge base, the memory of known problem sets in `.git/aqis-stop-gate.json`, silence while an open blocker covers a known set, the fail-closed main-ref lookup, and the pattern tables' names and message formats that the parity tests read.
- **B10** Session context prints at most 15 lines: branch; current WP and its status; open blockers for the WP and in total (fragments plus legacy `BLOCKERS.md` entries); the owner-queue item count if `OWNER_QUEUE.md` exists; whether the probe files exist; and `Navigate: docs/index/MAP.md first.` It never fails the session: on any error it prints one line and exits 0.

- **B11** Pins (amended by Claude with the acceptance tests; each is checked there):
  1. **Spec allowance lines.** Lines of `## Allowed guarded edits` up to the next `## ` heading that start with `- `. Each value is stripped of surrounding backticks. A value of `None` (any case) gives nothing. `spec_allowances` returns the values as glob strings, in file order. Only one matching spec file counts (E2). The guard's message for E2 names every matching path.
  2. **Ref.** `spec_allowances(root, "origin/main", wp)` fetches `origin/main` once when it is missing. It never falls back to a local `main`; only approvals keep version 3's `main_ref` fallback.
  3. **The stop gate honours spec allowances too.** A GUARDED change since the merge base passes when an approval or the current WP's spec allowance on `origin/main` matches it, exactly as the guard decides. NEVER paths are never unlocked.
  4. **TEST_CHANGES rows.** A row names a file when its first cell, stripped of backticks and spaces, equals the file's repository path. `conftest.py` and other test-folder `.py` files without test functions pass with a row, as long as no test function was lost. The rows are read from the working tree, at `docs/progress/<current WP>/TEST_CHANGES.md`.
  5. **Assertion count (B5).** Per test function (`test*` functions, including methods of `Test*` classes): `assert` statements, plus `with` items calling `pytest.raises` or `pytest.warns`. Skips are decorators or marks with `skip`, `skipif` or `xfail`; calls `pytest.skip(` or `pytest.xfail(`; or a module-level `pytestmark` naming any of them. A gained skip is a skip that the `origin/main` version lacked. Every blocking message names the file path (the new path for E3) and the function.
  6. **Test selection (B4).** The stop gate runs `<python> -m tools.index impact --base origin/main` from the project root. It passes the printed lines as pytest arguments, with version 3's `-q -x -p no:cacheprovider -m "<fast markers>"`. It runs the full fast suite when the first line is `all`, the command exits non-zero, or `tools/index/__main__.py` is missing. An empty selection runs no tests. A status fragment `docs/progress/status.d/<current WP>.md` in the working tree with `Status: READY-FOR-AUDIT` forces the full fast suite. The cached result's fingerprint also covers the selection.
  7. **Blocker lint (B6).** It runs `<python> -m tools.progress lint --changed-from origin/main` when `tools/progress/__main__.py` exists. Any non-zero exit blocks, showing the lint's output lines.
  8. **Open blockers (B9, B10).** The open blocker IDs are the union of the fragments in `docs/progress/blockers.d/` with a `Status: OPEN` line and the legacy `BLOCKERS.md` entries `## BLK-…` with `STATUS: OPEN`. An ID found in both counts once. The stop gate's quiet rule uses this union.
  9. **Report (B8).** The text Claude sees (`reason` or `systemMessage`) is at most 40 lines, the explanation lines included. Each stop writes the full, untruncated list of problems to `.git/aqis-stop-gate.log`, replacing the previous report.
  10. **Session context lines (B10).** The context includes these lines, exactly:
      - `- Branch: <branch>`;
      - `- WP: <WP> (<status>)` when there is a current WP;
      - `- Open blockers: <n> for <WP> (<ids, comma-separated, or none>), <m> in total` (without a current WP: `- Open blockers: <m> in total`);
      - `- Owner queue: <k> items`, only when `docs/progress/OWNER_QUEUE.md` exists, where `<k>` counts the items as `tools.progress` renders them (open blockers, decisions and checks);
      - one line per probe file, saying `present` or `MISSING`;
      - `Navigate: docs/index/MAP.md first.`.
      The current WP's status fragment is read directly. If it exists but cannot be read (for example, it is a folder), the hook prints a single line saying so, and still exits 0.

## 5. Edge cases you must handle
- **E1** A shallow clone without `origin/main` → spec allowances are empty after one fetch attempt (fail closed); the stop gate's existing behaviour for a missing main ref stays.
- **E2** Two spec files match the WP → no allowances, and the guard's message names both files.
- **E3** A test file renamed (git rename) → treated as modified under its new name and compared with the old content.
- **E4** Non-UTF-8 bytes in a changed file → handled as version 3 does (decode with replacement), never a crash.

## 6. Never
- Never weaken a version 3 check that this order does not name.
- Never read approvals or specs from the working tree.
- Never call the network except `git fetch` of `origin/main`.
- Never write outside `.git/` state files and logs.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the current hook code contradicts this order, if the attached hooks reference contradicts how the current hooks read input, or if `stop_gate.py` cannot stay within 400 lines (propose the sibling helper files to add to `outputs`).

## 8. Must-catch behaviours
1. A spec allowance on `origin/main` allows a GUARDED edit on that WP's branch.
2. The same allowance does not apply on another WP's branch.
3. An allowance added only on the work branch has no effect.
4. A modified test whose assertion count fell is blocked even with a TEST_CHANGES row.
5. A new skip marker is blocked.
6. Impact-selected tests run when available; the full suite runs when impact prints `all` or fails, and always at READY-FOR-AUDIT.
7. What Claude sees from the stop gate never exceeds 40 lines.
8. A blocker fragment without a capability class blocks the stop.
9. A change under a NEVER path is still blocked, and the known-problem memory still works.

## 9. Definition of Done
- **D1** Every file in section 3 exists, starts from the current code, and carries the module header standard.
- **D2** B1 to B11 and E1 to E4 are implemented; point at each, and list every version 3 behaviour you kept.
- **D3** Tests run the hooks as subprocesses with JSON on stdin, in scratch repositories with an `origin` remote.
- **D4** `tests/aqis_lab/kit/test_acceptance_wo_1_0_07.py` and the WP-0.0 parity tests pass unmodified.
- **D5** No placeholder or swallowed error; enforcement fails closed.
