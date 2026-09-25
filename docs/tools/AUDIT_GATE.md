# Audit gate (`tools/audit/gate.py`)

The audit gate checks a branch's changes for the rule violations the AQIS lab cares about. It exits `0` only when it finds nothing. It is built by WP-0.0 (FR-0.0-05 to FR-0.0-09, NFR-0.0-01 to NFR-0.0-03). It runs in CI, and the Stop hook (`.claude/hooks/stop_gate.py`) calls it at the end of every Claude turn.

## Usage
Run from anywhere inside the repository, with the project environment:

```bash
git fetch origin main                                   # approvals are read from origin/main
.venv/bin/python -m tools.audit.gate --base origin/main                 # checks (a) to (e)
.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0     # plus (f) traceability
.venv/bin/python -m tools.audit.gate --base origin/main --json          # machine-readable report
```

| Exit code | Meaning |
| --- | --- |
| 0 | No findings |
| 1 | At least one finding (listed) |
| 2 | The gate could not run: bad `--base`, malformed `--wp`, not a git repository, or `origin/main` missing and not fetchable. The message is on stderr and starts with `ERROR:` |

## What "changes" means
- **Diff base.** The gate uses `git merge-base <ref> HEAD`, not the tip of `<ref>`. It sees only what this branch changed since it left `<ref>`, the same as a GitHub pull request diff and the Stop hook (owner-approved default 5f).
- **Changes checked.** Committed changes since the base, plus uncommitted changes and untracked files (`git status --untracked-files=all`, ignored files excluded).
- **Renames** count as a delete plus an add (`--no-renames`).
- **Added then removed.** A file added on the branch and later removed again is ignored.
- **Approvals.** Approvals are read from `docs/approvals/*.md` as committed on **`origin/main`**, never from the working tree or the branch.
  - A file counts only if it has a line `STATUS: APPROVED` and no past `EXPIRES: YYYY-MM-DD`. `README.md` is ignored.
  - If `origin/main` is missing, the gate fetches it once. A stale local `origin/main` hides newer approvals, so run `git fetch origin main` first.
  - **Known difference:** the Stop hook reads approvals at the merge-base instead. The two agree whenever the branch contains the latest `main`, which is what `/wp-build` does first, and in every CI pull-request run. They differ only on a branch that has not merged a newer approval from `main`. The owner accepted this (WP-0.0 plan, decision 2).
- **Protected paths.** `docs/process/PROTECTED_PATHS.txt` is read from the working tree, as the hooks do. The built-in NEVER list always applies. Changing the file is itself an A1 finding.

## Checks and rules
Every finding is printed as `path:line: [RULE] SEVERITY: message` (NFR-0.0-02).

| Rule | Check | Severity | Finding |
| --- | --- | --- | --- |
| A1 | (a) protected paths | CRITICAL | A path on the NEVER list changed |
| A2 | (a) protected paths | CRITICAL | A GUARDED path changed with no matching `ALLOW-EDIT:` on `origin/main`. LAB-OWNED exceptions such as `tests/aqis_lab/**` are not guarded |
| B1 | (b) existing tests | CRITICAL | A `tests/**.py` file that existed at the base was modified with no `ALLOW-EDIT:` |
| B2 | (b) existing tests | CRITICAL | The same, but deleted |
| C1 | (c) compromise scan | COMPROMISE | An added line in `aqis_lab/**.py` or `tools/**.py` matches a code pattern (TODO markers, stub or shortcut wording, `NotImplementedError`, swallowed or bare `except`, type-check suppression, mocking); the label names the pattern |
| C2 | (c) compromise scan | COMPROMISE | An added line in `tests/aqis_lab/**.py` skips a test, marks an expected failure, or makes a trivial assertion |
| D1 | (d) headers | MAJOR | A new `aqis_lab/**.py` module with more than 5 non-blank lines has no `CAPABILITIES:` line in its first 80 lines |
| E1 | (e) registry | MAJOR | `docs/capabilities/REGISTRY.md` is missing or unreadable |
| E2 | (e) registry | MAJOR | Malformed table: no or wrong header, a row without 7 cells, or a duplicate capability ID |
| E3 | (e) registry | MAJOR | A row names no tests, or names a test that does not exist |
| E4 | (e) registry | MAJOR | A row names a module that does not exist |
| E5 | (e) registry | MAJOR | A row present at the base is gone (rows are never deleted) |
| F1 | (f) traceability | MAJOR | No spec, or more than one, matches `docs/specs/**/<WP>-*.md` |
| F2 | (f) traceability | MAJOR | A requirement ID is missing from `docs/progress/<WP>/PLAN.md` (or the file is missing) |
| F3 | (f) traceability | MAJOR | An `FR-`/`NFR-` ID is in no test function name under `tests/aqis_lab/` |
| F4 | (f) traceability | MAJOR | A requirement ID is missing from `docs/progress/<WP>/EVIDENCE.md` (or the file is missing) |

**Line numbers.**
- Pattern findings (C) cite the added line.
- File-level findings (A, B) cite the first changed line of a modified text file. For added, deleted or binary files they cite `1`.
- D1 cites line 1.
- Registry findings cite the row's line. E5 cites the row's line at the base.
- Traceability findings cite the spec line where the ID first appears.

**Parity with the Stop hook (FR-0.0-06).** Checks (a) to (d) use the same rules as `.claude/hooks/stop_gate.py`:
- The same glob conversion, sections and approval parsing.
- `ALLOW-PATTERNS-IN` skips both the pattern scan and the header check for that file.
- The first matching pattern on a line wins.
- Only `.py` files are scanned.

The pattern tables in `tools/audit/patterns.py` are copies of the hook's. `tests/aqis_lab/test_aqis_gate_parity.py` runs both tools on the same fixture repositories and compares their findings. It also compares the tables and path classification directly.

## Exemptions (FR-0.0-07)
- **`# audit-allow: <reason>`** at the end of a line exempts that one line from check (c), but only when a reason follows the colon. The gate lists every such line with its reason under "Exempted lines". A line with `# audit-allow:` and no reason is scanned normally.
- **`ALLOW-PATTERNS-IN: <glob>`** in an approval on `origin/main` exempts whole files from checks (c) and (d). The gate lists every exempted changed lab file, its glob and the approval file under "Exempted files". WP-0.0 uses this for `tools/audit/patterns.py` and `tests/aqis_lab/fixtures/**`.

Exemptions never count as findings. They are printed first, so the findings stay visible in the last lines the Stop hook shows.

## Registry format (check e)
The table in `docs/capabilities/REGISTRY.md` has exactly the columns `Capability ID | Module | Functions | What it does | Tests | Introduced by | Status`. Cells cannot contain `|`, and backticks around values are ignored.
- **Module**: a repo-relative file path, for example `aqis_lab/commands/version.py` or `aqis_lab/deploy/dev_bootstrap.sh`, or a dotted Python module such as `aqis_lab.commands.version`, resolved to `.py` or `/__init__.py`.
- **Tests**: comma-separated test function names such as `test_FR_0_0_01_x`, or `path::name`, or `path::Class::name`. A name exists when a function with that name is defined in a Python file under `tests/`, excluding `tests/aqis_lab/fixtures/`. The function must be at module level, or a method of a class whose name starts with `Test`.

## Traceability (check f, `--wp`)
- The spec is the single file `docs/specs/**/<WP>-*.md`.
- **Requirement IDs** are the `FR-`, `NFR-`, `AT-` and `OC-` IDs carrying that WP's own number, so `FR-0.2-03` inside the WP-0.0 spec is ignored.
- **Every ID** must appear in `docs/progress/<WP>/PLAN.md` and `EVIDENCE.md`.
- **`FR-` and `NFR-` IDs** must also appear in a test function name under `tests/aqis_lab/` (fixtures excluded). `AT-` and `OC-` IDs are acceptance commands and owner checks, so they need only the two documents (owner decision 1).
- **Matching**: in test names, `FR-0.2-03` matches `FR_0_2_03`. Matches need a non-alphanumeric character before and no digit after, so `NFR_0_2_03` never satisfies `FR-0.2-03` and `FR_0_2_031` never satisfies `FR-0.2-03`. The same boundaries apply to the hyphenated IDs in the documents.

## JSON report (`--json`)
```text
{tool, base_ref, base_commit, head_commit, approvals_ref, approvals_commit, wp, ok, seconds,
 findings: [{rule, check, severity, path, line, message, state, label, text}],
 exempted_lines: [{path, line, reason}],
 exempted_files: [{path, approval, glob}]}
```
`state` (`A`/`M`/`D`) is set for check (a) to (d) findings. `label` and `text` (the full added line) are set for C findings.

## Limits
- Standard library only (NFR-0.0-03). It runs on Python 3.10 or newer, so the Stop hook can fall back to the system `python3`.
- It is read-only and does not run tests. Its runtime on this repository is well under 60 s (NFR-0.0-01, measured in `docs/progress/WP-0.0/EVIDENCE.md`).
