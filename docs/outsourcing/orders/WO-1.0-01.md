---
id: WO-1.0-01
wp: WP-1.0
title: Work-order parser, bundle importer, scope check and paste pack
model: gemini-3.7-flash
channel: jules                     # bootstrap: the relay does not exist yet
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/PROTECTED_PATHS.txt
  - docs/process/outsourcing/templates/WORK_ORDER.md
  - docs/process/outsourcing/templates/RETURN_FORMAT.md
  - tools/audit/patterns.py
  - tools/audit/gate.py
outputs:
  - tools/outsourcing/__init__.py
  - tools/outsourcing/__main__.py
  - tools/outsourcing/workorder.py
  - tools/outsourcing/paths.py
  - tools/outsourcing/secrets.py
  - tools/outsourcing/bundle.py
  - tools/outsourcing/importer.py
  - tools/outsourcing/scope.py
  - tools/outsourcing/pack.py
  - tests/aqis_lab/outsourcing/__init__.py
  - tests/aqis_lab/outsourcing/test_workorder.py
  - tests/aqis_lab/outsourcing/test_bundle.py
  - tests/aqis_lab/outsourcing/test_importer.py
  - tests/aqis_lab/outsourcing/test_scope.py
  - tests/aqis_lab/outsourcing/test_pack.py
  - tests/aqis_lab/outsourcing/test_secrets.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing -q --tb=short
---

# WO-1.0-01 — Work-order parser, bundle importer, scope check and paste pack

## 1. Context
The lab outsources bulk code to Gemini through work orders (format: `WORK_ORDER.md`) and receives answers in a fixed text format (`RETURN_FORMAT.md`). This order builds the deterministic pieces every channel needs: reading a work order, turning an answer into files safely, checking that a branch changed only what an order allowed, and producing a single paste file for the manual channel. The relay (WO-1.0-02) builds on these. `PROTECTED_PATHS.txt` defines NEVER, GUARDED and LAB-OWNED paths; `tools/audit/patterns.py` and `tools/audit/gate.py` already exist from WP-0.0: if either already contains a function that classifies a path against `PROTECTED_PATHS.txt`, reuse it instead of writing a second one.

## 2. Your job
Provide a package `tools.outsourcing` with a command-line entry point (`python -m tools.outsourcing <subcommand>`) offering `validate`, `import`, `scope` and `pack`, plus importable functions for the relay. Everything is deterministic, works offline, and refuses rather than guesses.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/__init__.py` | Package marker and version string | `__version__` | 30 |
| `tools/outsourcing/__main__.py` | Command-line dispatch for the four subcommands; maps exceptions to exit codes | `main(argv) -> int` | 150 |
| `tools/outsourcing/workorder.py` | Parse and validate a work order file | `WorkOrder` frozen dataclass with every front-matter field plus the body text; `load_work_order(path, repo_root) -> WorkOrder`; raises `WorkOrderError` with the field and the reason | 300 |
| `tools/outsourcing/paths.py` | Normalise repository-relative paths and classify them | `normalise(path) -> str` (rejects absolute, `..`, backslashes, empty); `classify(path, repo_root) -> "NEVER" | "GUARDED" | "LAB-OWNED" | "FREE"` | 200 |
| `tools/outsourcing/secrets.py` | Detect secret-looking files and content | `secret_reasons(path, text) -> list[str]` (empty means clean) | 150 |
| `tools/outsourcing/bundle.py` | Parse an answer in RETURN_FORMAT | `parse_bundle(text) -> Bundle` (manifest rows, files in order, DOD rows, questions); raises `BundleError` | 300 |
| `tools/outsourcing/importer.py` | Write a parsed bundle to disk, all or nothing | `import_bundle(bundle, order, repo_root, mode, dry_run) -> ImportReport`; `mode` is `first` or `fix` | 250 |
| `tools/outsourcing/scope.py` | Compare a branch's changes with an order's allowed paths | `check_scope(order, repo_root, base_ref, head_ref) -> ScopeReport` | 200 |
| `tools/outsourcing/pack.py` | Assemble the single paste file for the paste channel | `build_pack(order, repo_root) -> Pack` (text plus size figures) | 200 |
| `tests/aqis_lab/outsourcing/*.py` | Unit tests for each module above | one test file per module | 300 each |

## 4. Required behaviour
- **B1** `load_work_order` reads the front matter between the first two `---` lines using exactly the subset grammar in `WORK_ORDER.md` (top-level `key: value`; lists as `  - item`; ` #` comments). Unknown keys, duplicate keys, tabs, nested structures or a missing required key raise `WorkOrderError`.
- **B2** Validation: `id` matches `WO-<n>.<n>-<nn>` and its WP part equals `wp` (`WP-<n>.<n>`); `channel` is `api`, `jules` or `paste`; `attempt_budget` is an integer 1 to 5; `risk_tier` is T1, T2 or T3; `max_output_tokens` is a positive integer; `outputs` is non-empty; every path is normalised; no output is classified NEVER or GUARDED (LAB-OWNED and FREE are allowed); no output lies under `tests/aqis_lab/breaks/`; no output equals a context path or a read-only test; every context path and read-only test exists in the repository.
- **B3** `parse_bundle` recognises the four blocks of RETURN_FORMAT with markers alone on their lines (surrounding whitespace and CRLF line endings tolerated, a UTF-8 byte-order mark ignored). A FILE block's content has one surrounding fenced code block removed if present; the result must end with exactly one newline (added if missing).
- **B4** `parse_bundle` raises `BundleError` for: a FILE without its END marker, nested or overlapping markers, a path listed twice, a FILE whose path is missing from the manifest or a manifest row with no FILE, an empty file, and truncation signs. Truncation signs are: a line consisting only of `...` or `…` (optionally commented), or a line containing, case-insensitively, "rest of the file", "remains unchanged", "same as before", "unchanged code", "existing code here" or "omitted for brevity".
- **B5** A non-empty QUESTIONS block is returned as questions; `import_bundle` then refuses with `QuestionsReturned` and writes nothing.
- **B6** `import_bundle` in `first` mode requires every output exactly once; in `fix` mode it accepts any non-empty subset of outputs. Any path outside `outputs` fails the whole import. Writes are atomic (temporary file in the same directory, then rename), create parent folders, never follow a symlink out of the repository, and nothing is written unless every check passes. The report lists path, bytes, lines and SHA-256 for each file.
- **B7** `check_scope` collects every path changed between the merge base of `base_ref` and `head_ref` (default `HEAD`), plus staged, unstaged and untracked files when `head_ref` is `HEAD`. Allowed: the order's outputs, `docs/outsourcing/returns/<id>/**` and `docs/outsourcing/ledger.d/<id>.md`. Any other path, and any deletion, is a violation listed in the report. If the base ref is missing it fetches it once; if it is still missing it raises, never reports "no changes".
- **B8** `build_pack` produces one text: FOUNDATION, then the order (front matter and body), then each context file and each read-only test wrapped as `=== CONTEXT: <path> ===` … `=== END CONTEXT ===`, then RETURN_FORMAT. It refuses any file for which `secret_reasons` is non-empty. It reports characters and an estimated token count (characters divided by 4) and raises when the text exceeds 600,000 characters.
- **B9** `secret_reasons` flags paths named `.env`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, and content containing a private-key header, or tokens shaped like Hugging Face (`hf_` plus at least 30 alphanumerics), GitHub (`ghp_`, `github_pat_`), Google API keys (`AIza` plus 35 characters) or Anthropic keys (`sk-ant-`).
- **B10** The CLI prints at most 25 lines and uses exit codes: 0 success; 1 scope violation; 2 invalid work order; 3 invalid bundle; 4 questions returned; 5 truncation detected; 6 secret detected. `pack --out <path>` writes the pack to a file; `import --wo <path> --bundle <path> [--mode first|fix] [--dry-run]`; `scope --wo <path> [--base origin/main] [--head HEAD]`; `validate --wo <path>`.

## 5. Edge cases you must handle
- **E1** A bundle whose FILE marker uses `./tools/...` or trailing spaces → normalised; a backslash path → rejected.
- **E2** Content that itself contains a line `=== END FILE ===` inside a fenced block → still ends the file (markers win); the DOD and manifest must then fail to match, so the import fails. Document this in the module header.
- **E3** A work order whose front matter has a value with a ` #` inside quotes → quotes are not supported by the subset; raise a clear error.
- **E4** A repository where `origin/main` is absent (shallow or single-branch clone) → B7's fetch-then-raise rule.
- **E5** An output path that already exists as a directory → import fails, nothing written.

## 6. Never
- Never execute, import or evaluate any code from a bundle.
- Never reach the network, except the single `git fetch` in B7.
- Never write outside the repository root or outside `outputs`.
- Never treat an error as "clean" or "no changes".

## 7. When this order is wrong or incomplete
Return QUESTIONS if `tools/audit` already has a protected-path classifier whose behaviour differs from `PROTECTED_PATHS.txt` as described, or if the repository layout contradicts this order.

## 8. Must-catch behaviours
1. A FILE path not in `outputs` fails the import and writes nothing.
2. A missing END marker fails the import.
3. Each truncation sign in B4 fails the import.
4. A QUESTIONS block stops the import with exit code 4.
5. `scope` reports an extra changed file and a deletion as violations.
6. `pack` refuses a `.env` file and content holding a private key.
7. A work order with an output under a NEVER or GUARDED path is invalid.
8. A missing base ref is never reported as "no changes".

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B10 and E1 to E5 are implemented; point at each.
- **D3** Unit tests cover every behaviour and edge case and pass.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` passes unmodified.
- **D5** No placeholder, swallowed error or network use beyond B7.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md` and every file in `context`. Then write the files on branch `wo/WO-1.0-01` (based on the WP-1.0 branch that holds the acceptance test), run the verify command until it passes, and open a pull request titled `WO-1.0-01: work-order tools` with the DOD table as its description.
