# Audit gate (`tools/audit/gate.py`)

The audit gate checks a branch's changes for the rule violations the AQIS lab cares about. It exits `0` only when it finds nothing. It is built by WP-0.0 (FR-0.0-05 to FR-0.0-09, NFR-0.0-01 to NFR-0.0-03; FR-0.0-06 amended in round 2 to match Stop hook version 2/3). It runs in CI (with `--wp` taken from the pull request title), and the Stop hook (`.claude/hooks/stop_gate.py`) calls it at the end of every Claude turn.

## Usage
Run from the repository root, with the project environment. The `tools` package is imported from the current folder. From any subfolder, including `docs/`, set `PYTHONPATH` to the repository root and it works the same. Without `PYTHONPATH`, a subfolder fails: from `docs/` with `No module named 'tools.audit'` (the folder `docs/tools/` is found instead of the package), elsewhere with `No module named 'tools'` (corrected for audit findings F45 and F54):

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
| 2 | Gate error: bad `--base`, malformed `--wp`, not a git repository, a git command that failed, or a file the gate must check that cannot be read. The message is on stderr and starts with `ERROR:`. A message about a file names `path:line`; a message about an argument (`--base`, `--wp`) or a failed git command names that argument or command instead (corrected for audit finding F45). The gate **fails closed**: an error is never reported as a clean pass |

## What "changes" means
- **Diff base.** The gate uses `git merge-base <ref> HEAD`, not the tip of `<ref>`. It sees only what this branch changed since it left `<ref>`, the same as a GitHub pull request diff and the Stop hook (owner-approved default 5f).
- **Changes checked.** Committed changes since the base, plus uncommitted changes and untracked files (`git status --untracked-files=all`, ignored files excluded).
- **Renames** count as a delete plus an add (`--no-renames`).
- **Added then removed.** A file added on the branch and later removed again is ignored.
- **Approvals.** Approvals are read from `docs/approvals/*.md` as committed on **`origin/main`**, never from the working tree or the branch.
  - A file counts only if it has a line `STATUS: APPROVED` and no past `EXPIRES: YYYY-MM-DD`. `README.md` is ignored.
  - An approval file that `git show` cannot read at that commit does not count, and neither does the whole folder if `git ls-tree` cannot list it. The gate does not stop with exit 2 here, unlike the reads in "Fail closed" below. A missing approval can only add A2, B1 or C findings, never hide one, so the result still errs toward failing.
  - If `origin/main` is missing, the gate fetches it once. If it still cannot be verified, **no approval counts**: the report says `approvals: none (origin/main not verifiable)` and JSON has `approvals_commit: null`. This can only add findings, never remove them. A stale local `origin/main` hides newer approvals, so run `git fetch origin main` first.
  - **Difference G1 (accepted, owner decisions 2 and R2-2):** the Stop hook reads approvals at the merge-base instead. The two agree whenever the branch contains the latest `main`, which is what `/wp-build` does first, and in every CI pull-request run. They differ only on a branch that has not merged a change to approvals from `main`. An approval added on `main` after the branch point counts for the gate but not for the hook, and an approval withdrawn there counts for the hook but not for the gate. Tests: `test_FR_0_0_05_a_uses_approval_added_on_main_after_branch_point`, `test_FR_0_0_05_a_honours_withdrawal_on_main_after_branch_point`.
- **Protected paths.** `docs/process/PROTECTED_PATHS.txt` is read from the working tree, as the hooks do. The built-in NEVER list always applies. Changing the file is itself an A1 finding. If the file is missing or unreadable the gate exits 2 (difference G2 below).
- **Status mapping** (Stop hook v2): an untracked (`?`) or staged-added (`A`) file counts as added, even when it was then deleted from the working tree (`AD`).
- **Decoding.** All git output and file content are decoded as UTF-8 with replacement (`\ufffd`), and `git diff` runs with `--text`, so bytes that are not valid UTF-8 never crash the gate.

## Checks and rules
Every finding is printed as `path:line: [RULE] SEVERITY: message` (NFR-0.0-02).

| Rule | Check | Severity | Finding |
| --- | --- | --- | --- |
| A1 | (a) protected paths | CRITICAL | A path on the NEVER list changed |
| A2 | (a) protected paths | CRITICAL | A GUARDED path changed with no matching `ALLOW-EDIT:` on `origin/main`. LAB-OWNED exceptions such as `tests/aqis_lab/**` are not guarded |
| B1 | (b) existing tests | CRITICAL | A `tests/**.py` file that existed at the base was modified with no `ALLOW-EDIT:` |
| B2 | (b) existing tests | CRITICAL | The same, but deleted |
| C1 | (c) compromise scan | COMPROMISE | An added line matches a code pattern (TODO markers, stub or shortcut wording, `NotImplementedError`, swallowed or bare `except`, type-check suppression, mocking, errors silenced in shell such as `\|\| true` or `2>/dev/null`); the label names the pattern. Scope: files under `aqis_lab/`, `tools/`, `config/aqis_lab/`, `requirements/aqis_lab/` and `.github/workflows/aqis-lab-*.yml` whose suffix is `.py .sh .bash .yml .yaml .toml .cfg .ini .in` |
| C2 | (c) compromise scan | COMPROMISE | An added line in `tests/aqis_lab/**.py` skips a test (including module-level `pytestmark = pytest.mark.skip...` and `pytest.param(..., marks=pytest.mark.skip...)`), marks an expected failure, or makes a trivial assertion |
| D1 | (d) headers | MAJOR | A new `aqis_lab/**.py` module with more than 5 non-blank lines has no `CAPABILITIES:` line in its first 80 lines |
| E1 | (e) registry | MAJOR | `docs/capabilities/REGISTRY.md` is missing or unreadable |
| E2 | (e) registry | MAJOR | Malformed table: no or wrong header, a row without 7 cells, or a duplicate capability ID |
| E3 | (e) registry | MAJOR | A row names no tests, or names a test that does not exist |
| E4 | (e) registry | MAJOR | A row names a module that does not exist |
| E5 | (e) registry | MAJOR | A row present at the base is gone (rows are never deleted) |
| F1 | (f) traceability | MAJOR | No spec, or more than one, matches `docs/specs/**/<WP>-*.md` (the finding cites that glob) |
| F2 | (f) traceability | MAJOR | A requirement ID is missing from `docs/progress/<WP>/PLAN.md` (or the file is missing) |
| F3 | (f) traceability | MAJOR | An `FR-`/`NFR-` ID is in no test function name under `tests/aqis_lab/` |
| F4 | (f) traceability | MAJOR | A requirement ID is missing from `docs/progress/<WP>/EVIDENCE.md` (or the file is missing) |

**Line numbers.**
- Pattern findings (C) cite the added line.
- File-level findings (A, B) cite the first changed line of a modified text file. For added, deleted or binary files they cite `1`.
- D1 cites line 1.
- Registry findings cite the row's line. E5 cites the row's line at the base.
- Traceability findings cite the spec line where the ID first appears.

**Parity with the Stop hook (FR-0.0-06, amended).** Checks (a) to (d) use the same detection rules as `.claude/hooks/stop_gate.py` version 2/3 (version 3 only adds memory; its detection rules equal version 2):
- The same glob conversion, sections, approval parsing, status mapping and decoding.
- The same scan scope and suffixes (see C1 and C2); the header check (d) applies to new `aqis_lab/**.py` files only.
- `ALLOW-PATTERNS-IN` skips both the pattern scan and the header check for that file.
- The first matching pattern on a line wins.

**Fail closed, and difference G2 (accepted, owner decision R2-2).** The gate exits 2 when:
- `PROTECTED_PATHS.txt` is missing or unreadable (the hook then uses only its built-in NEVER list);
- a changed file in the scan scope exists but is not a regular file, such as a dangling symlink, or cannot be read (the hook skips such a file silently);
- any `git diff` it needs fails, or the `git show` of `docs/capabilities/REGISTRY.md` at the base fails (the hook reports a `GATE ERROR` line too). An approval that cannot be read is the one exception: it simply does not count (see Approvals above).

A changed path that no longer exists at all (staged, then removed from the working tree) has nothing to scan, as in the hook. The parity tests compare findings on readable repositories and assert that the gate exits 2 in the error cases. Tests: `test_FR_0_0_06_fails_closed_*`, `test_FR_0_0_06_decodes_non_utf8_with_replacement`.

The pattern tables in `tools/audit/patterns.py` are copies of the hook's. `tests/aqis_lab/test_aqis_gate_parity.py` runs both tools on the same fixture repositories and compares their findings. It also compares the tables and path classification directly.

## In CI
Job `lab` of `.github/workflows/aqis-lab-ci.yml` runs the gate on every push with `--base origin/main`. On pull requests it takes the WP ID from the start of the pull request title (`WP-x.y ...`, one line only) and runs `--base origin/<base branch> --wp <WP-ID>`. A title without a WP ID fails the job (FR-0.0-10 amended).

## Exemptions (FR-0.0-07)
- **`# audit-allow: <reason>`** at the end of a line exempts that one line from check (c), but only when a reason follows the colon. The gate lists every such line with its reason under "Exempted lines". A line with `# audit-allow:` and no reason is scanned normally.
- **`ALLOW-PATTERNS-IN: <glob>`** in an approval on `origin/main` exempts whole files from checks (c) and (d). The gate lists every exempted changed lab file, its glob and the approval file under "Exempted files". WP-0.0 uses this for `tools/audit/patterns.py` and `tests/aqis_lab/fixtures/**`.

Exemptions never count as findings. They are printed first, so the findings stay visible in the last lines the Stop hook shows.

## Registry format (check e)
The table in `docs/capabilities/REGISTRY.md` has exactly the columns `Capability ID | Module | Functions | What it does | Tests | Introduced by | Status`. Cells cannot contain `|`, and backticks around values are ignored.
- **Module**: a repo-relative file path, for example `aqis_lab/commands/version.py` or `aqis_lab/deploy/dev_bootstrap.sh`, or a dotted Python module such as `aqis_lab.commands.version`, resolved to `.py` or `/__init__.py`.
- **Tests**: comma-separated test function names such as `test_FR_0_0_01_x`, or `path::name`, or `path::Class::name`. A name exists when pytest's default collection would run it, read from the source without running pytest. The rules (corrected for audit finding F47):
  - The file is under `tests/`, outside `tests/aqis_lab/fixtures/`, and named `test_*.py` or `*_test.py`. A module that sets `__test__ = False` has no tests.
  - The function name starts with `test` and is defined with `def` or `async def` at module level. It can also be a method of a class whose name starts with `Test`, including a class nested in such a class.
  - The class must not set `__test__ = False`. It must not define `__init__` or `__new__`, either itself or through a base class. Every base class must be defined in the same file (or be `object`). A base class imported from elsewhere cannot be read, so the class does not count; this is stricter than pytest.
  - Functions decorated with `fixture` or `property` are not tests. Functions nested inside other functions, and methods of any other class, are not tests either.
  - Tests inherited from a base class, and tests bound by assignment (`test_x = f`), are not counted either. This is also stricter than pytest.
  - **Known gaps (accepted debt DEBT-004, audit finding F55):** some pytest rules are not modelled, so the gate can still accept a name pytest does not run. These rules cover:
    - folders pytest skips, such as `build`, `dist`, `venv` and hidden folders;
    - files a `conftest.py` ignores;
    - a module or class switched off with a false `__test__` value other than `False`;
    - abstract `Test` classes;
    - a test name rebound after its `def`.

    Each case needs an unusual layout or construct that is visible in review (corrected for audit finding F61).

## Traceability (check f, `--wp`)
- The spec is the single file `docs/specs/**/<WP>-*.md`.
- **Requirement IDs** are the `FR-`, `NFR-`, `AT-` and `OC-` IDs carrying that WP's own number, so `FR-0.2-03` inside the WP-0.0 spec is ignored.
- **Every ID** must appear in `docs/progress/<WP>/PLAN.md` and `EVIDENCE.md`.
- **`FR-` and `NFR-` IDs** must also appear in the name of a test under `tests/aqis_lab/` that pytest collects, under the same rules as the registry's **Tests** column (fixtures excluded; audit finding F47). `AT-` and `OC-` IDs are acceptance commands and owner checks, so they need only the two documents (owner decision 1).
- **Matching**: in test names, `FR-0.2-03` matches `FR_0_2_03`. Matches need a non-alphanumeric character before and no digit after, so `NFR_0_2_03` never satisfies `FR-0.2-03` and `FR_0_2_031` never satisfies `FR-0.2-03`. The same boundaries apply to the hyphenated IDs in the documents.

## JSON report (`--json`)
```text
{tool, base_ref, base_commit, head_commit, approvals_ref, approvals_commit, wp, ok, seconds,
 findings: [{rule, check, severity, path, line, message, state, label, text}],
 exempted_lines: [{path, line, reason}],
 exempted_files: [{path, approval, glob}]}
```
`state` (`A`/`M`/`D`) is set for check (a) to (d) findings. `label` and `text` (the full added line) are set for C findings.

## Accepted limits
- **An existing test replaced by a symlink (owner decision, round 6 audit finding F44).**
  - **What happens:** a commit that replaces an existing test file with a symlink shows in `git diff --name-status` as a typechange (`T`). For example, `tests/aqis_lab/test_existing.py` could become a link to a weaker copy.
  - **Why nothing reports it:** check (b) looks only at modified (`M`) and deleted (`D`) tests, and a `tests/aqis_lab/` path is LAB-OWNED, so check (a) is silent too.
  - **Why it stays this way:** the Stop hook (`stop_gate.py:101,288`) has the same rule, and the gate must match the hook (FR-0.0-06). The owner accepted the limit under CONDITIONS in `docs/approvals/WP-0.0.md` on `main`: "F44 accepted as a known limit: a test file replaced by a symlink is not reported by the hook or the gate." (corrected for audit finding F54).
  - **Test:** the parity scenario `lab_test_replaced_by_symlink` in `tests/aqis_lab/test_aqis_gate_parity.py` records that the gate and the hook both report nothing. If the hook is changed to treat `T` as `M`, that scenario fails until the gate is changed the same way.

## Limits
- Standard library only (NFR-0.0-03). It runs on Python 3.10 or newer, so the Stop hook can fall back to the system `python3`.
- It is read-only and does not run tests. Its runtime on this repository is well under 60 s (NFR-0.0-01, measured in `docs/progress/WP-0.0/EVIDENCE.md`).
