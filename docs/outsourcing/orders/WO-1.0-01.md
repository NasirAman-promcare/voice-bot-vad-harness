---
id: WO-1.0-01
wp: WP-1.0
title: Work-order parser, step plans, bundle importer, scope check and paste pack
model: default
channel: jules                     # bootstrap: sent first, together with WO-1.0-10 (independent of it)
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
  - tests/aqis_lab/outsourcing/test_paths.py
  - tests/aqis_lab/outsourcing/test_secrets.py
  - tests/aqis_lab/outsourcing/test_workorder.py
  - tests/aqis_lab/outsourcing/test_bundle.py
  - tests/aqis_lab/outsourcing/test_importer.py
  - tests/aqis_lab/outsourcing/test_scope.py
  - tests/aqis_lab/outsourcing/test_pack.py
  - tests/aqis_lab/outsourcing/test_cli.py
steps:
  - tools/outsourcing/__init__.py, tests/aqis_lab/outsourcing/__init__.py, tools/outsourcing/paths.py, tests/aqis_lab/outsourcing/test_paths.py
  - tools/outsourcing/secrets.py, tests/aqis_lab/outsourcing/test_secrets.py
  - tools/outsourcing/workorder.py, tests/aqis_lab/outsourcing/test_workorder.py
  - tools/outsourcing/bundle.py, tests/aqis_lab/outsourcing/test_bundle.py
  - tools/outsourcing/importer.py, tests/aqis_lab/outsourcing/test_importer.py
  - tools/outsourcing/scope.py, tests/aqis_lab/outsourcing/test_scope.py
  - tools/outsourcing/pack.py, tests/aqis_lab/outsourcing/test_pack.py
  - tools/outsourcing/__main__.py, tests/aqis_lab/outsourcing/test_cli.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_paths.py tests/aqis_lab/outsourcing/test_secrets.py tests/aqis_lab/outsourcing/test_workorder.py tests/aqis_lab/outsourcing/test_bundle.py tests/aqis_lab/outsourcing/test_importer.py tests/aqis_lab/outsourcing/test_scope.py tests/aqis_lab/outsourcing/test_pack.py tests/aqis_lab/outsourcing/test_cli.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py -q --tb=short
---

# WO-1.0-01 — Work-order parser, step plans, bundle importer, scope check and paste pack

## 1. Context
The lab outsources bulk code to Gemini through work orders (format: `WORK_ORDER.md`) and receives answers in a fixed text format (`RETURN_FORMAT.md`). A work order is delivered in steps: each step asks for at most a module and its tests, because small requests get better answers and fit the free tier's per-minute token limit. This order builds the deterministic pieces every channel needs: reading a work order and its step plan, turning an answer into files safely, checking that a branch changed only what an order allowed, and producing a single paste file for the manual channel. The relay (WO-1.0-02 and WO-1.0-11) builds on these. `PROTECTED_PATHS.txt` defines NEVER, GUARDED and LAB-OWNED paths; `tools/audit/patterns.py` and `tools/audit/gate.py` already exist from WP-0.0: if either already contains a function that classifies a path against `PROTECTED_PATHS.txt`, reuse it instead of writing a second one.

## 2. Your job
Provide a package `tools.outsourcing` with a command-line entry point (`python -m tools.outsourcing <subcommand>`) offering `validate`, `import`, `scope` and `pack`, plus importable functions for the relay. Everything is deterministic, works offline, and refuses rather than guesses.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/__init__.py` | Package marker and version string | `__version__` | 30 |
| `tools/outsourcing/__main__.py` | Command-line dispatch for the four subcommands; maps exceptions to exit codes | `main(argv) -> int` | 150 |
| `tools/outsourcing/workorder.py` | Parse and validate a work order file and its step plan | `WorkOrder` frozen dataclass with every front-matter field plus the body text; `load_work_order(path, repo_root) -> WorkOrder`; `Step` frozen dataclass (number, paths); `plan_steps(order) -> tuple[Step, ...]`; raises `WorkOrderError` with the field and the reason | 300 |
| `tools/outsourcing/paths.py` | Normalise repository-relative paths and classify them | `normalise(path) -> str` (rejects absolute, `..`, backslashes, empty); `classify(path, repo_root) -> "NEVER" | "GUARDED" | "LAB-OWNED" | "FREE"` | 200 |
| `tools/outsourcing/secrets.py` | Detect secret-looking files and content | `secret_reasons(path, text) -> list[str]` (empty means clean) | 150 |
| `tools/outsourcing/bundle.py` | Parse an answer in RETURN_FORMAT | `parse_bundle(text) -> Bundle` (manifest rows, files in order, DOD rows, questions); raises `BundleError`, and its subclass `TruncatedBundle` for truncation signs | 300 |
| `tools/outsourcing/importer.py` | Write a parsed bundle to disk, all or nothing | `import_bundle(bundle, order, repo_root, mode, dry_run, expected=None) -> ImportReport`; `mode` is `first` or `fix`; `expected` is a set of output paths (default: all outputs); raises `QuestionsReturned` and `ImportRefused` | 250 |
| `tools/outsourcing/scope.py` | Compare a branch's changes with an order's allowed paths | `check_scope(order, repo_root, base_ref, head_ref) -> ScopeReport`; raises `ScopeError` when the base ref cannot be found | 200 |
| `tools/outsourcing/pack.py` | Assemble the single paste file for the paste channel | `build_pack(order, repo_root) -> Pack` (text plus size figures); raises `SecretRefused` and `PackTooLarge` | 200 |
| `tests/aqis_lab/outsourcing/test_*.py` | Unit tests: one file per module above (`test_cli.py` for `__main__.py`) | | 300 each |

## 4. Required behaviour
- **B1** `load_work_order` reads the front matter between the first two `---` lines using exactly the subset grammar in `WORK_ORDER.md` (top-level `key: value`; lists as `  - item`; ` #` comments). Required keys: `id`, `wp`, `title`, `model`, `channel`, `attempt_budget`, `risk_tier`, `max_output_tokens`, `context`, `outputs`, `read_only_tests`, `allowed_dependencies`, `verify`. Optional keys: `interfaces` and `steps` (lists). Unknown keys, duplicate keys, tabs, nested structures or a missing required key raise `WorkOrderError`.
- **B2** Validation: `id` matches `WO-<n>.<n>-<nn>` and its WP part equals `wp` (`WP-<n>.<n>`); `model` is `default` or a model name of letters, digits, dots and hyphens; `channel` is `api`, `jules` or `paste`; `attempt_budget` is an integer 1 to 5; `risk_tier` is T1, T2 or T3; `max_output_tokens` is a positive integer; `outputs` and `verify` are non-empty; every path is normalised; no output is classified NEVER or GUARDED (LAB-OWNED and FREE are allowed); no output lies under `tests/aqis_lab/breaks/`; no path appears in more than one of `outputs`, `context`, `interfaces` and `read_only_tests`; every context path, interface and read-only test exists in the repository; every interface ends in `.py`.
- **B3** Step plan: each `steps` item is a comma-separated list of output paths (spaces around commas ignored, each path normalised). Every path in a step is in `outputs`; every output is in exactly one step; there are at most 10 steps; a step has at most 3 paths not counting `__init__.py` files. Without `steps`, the plan is one step holding every output, allowed only when `outputs` has at most 3 paths not counting `__init__.py` files; otherwise `WorkOrderError` says "add a steps list". `plan_steps` returns the steps numbered from 1, in order.
- **B4** `parse_bundle` recognises the four blocks of RETURN_FORMAT with markers alone on their lines (surrounding whitespace and CRLF line endings tolerated, a UTF-8 byte-order mark ignored). A FILE block's content has one surrounding fenced code block removed if present; the result must end with exactly one newline (added if missing).
- **B5** `parse_bundle` raises `BundleError` for: a FILE without its END marker, an END marker with no open block, any non-blank text outside the four blocks, nested or overlapping markers, a path listed twice, a FILE whose path is missing from the manifest or a manifest row with no FILE, an empty file, and truncation signs (as `TruncatedBundle`). Truncation signs are: a line consisting only of `...` or `…` (optionally commented), or a line containing, case-insensitively, "rest of the file", "remains unchanged", "same as before", "unchanged code", "existing code here" or "omitted for brevity".
  - **B5 amendment (2026-10-11, BLK-1.0-07 option 1, RETURN_FORMAT.md on `main`).** Before parsing, `parse_bundle` removes one code fence that wraps the whole reply: the first non-blank line is three or more backticks with an optional info word, and the last non-blank line is the same backticks alone, on a different line. Any other text outside the blocks, a second fence, or an unmatched fence is still a `BundleError`. Tests: `tests/aqis_lab/outsourcing/test_outer_fence_wo_1_0_01.py`.
- **B6** A non-empty QUESTIONS block is returned as questions; `import_bundle` then refuses with `QuestionsReturned` and writes nothing.
- **B7** `import_bundle` in `first` mode requires every path of `expected` exactly once; in `fix` mode it accepts any non-empty subset of `expected`. Any path outside `expected` fails the whole import. Writes are atomic (scratch file in the same directory, then rename), create parent folders, never follow a symlink out of the repository, and nothing is written unless every check passes. The report lists path, bytes, lines and SHA-256 for each file.
- **B8** `check_scope` collects every path changed between the merge base of `base_ref` and `head_ref` (default `HEAD`), plus staged, unstaged and untracked files when `head_ref` is `HEAD`. Allowed: the order's outputs, `docs/outsourcing/returns/<id>/**` and `docs/outsourcing/ledger.d/<id>.md`. Any other path, and any deletion, is a violation listed in the report. If the base ref is missing it fetches it once; if it is still missing it raises, never reports "no changes".
- **B9** `build_pack` produces one text: FOUNDATION, then the order (front matter and body), then each context file, each interface file and each read-only test wrapped as `=== CONTEXT: <path> ===` … `=== END CONTEXT ===`, then RETURN_FORMAT. It refuses any file for which `secret_reasons` is non-empty. It reports characters and an estimated token count (characters divided by 3.5, rounded up) and raises when the text exceeds 600,000 characters.
- **B10** `secret_reasons` flags paths named `.env`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, and content containing a private-key header (a line starting `-----BEGIN` and ending `PRIVATE KEY-----`), or tokens shaped like Hugging Face (`hf_` plus at least 30 letters and digits), GitHub (`ghp_` plus 36 letters and digits, or `github_pat_` plus at least 22 letters, digits and underscores), Google API keys (`AIza` plus 35 letters, digits, `-` or `_`) or Anthropic keys (`sk-ant-` plus at least 20 letters, digits, `-` or `_`). A bare prefix is not a token, so the detector's own source is clean.
- **B11** The CLI prints at most 25 lines and uses exit codes: 0 success; 1 scope violation (or `ScopeError`); 2 invalid work order; 3 invalid bundle or refused import; 4 questions returned; 5 truncation detected (`TruncatedBundle`); 6 secret detected (`SecretRefused`). `pack --out <path>` writes the pack to a file; `import --wo <path> --bundle <path> [--mode first|fix] [--step K] [--dry-run]`, where `--step K` sets `expected` to step K's paths; `scope --wo <path> [--base origin/main] [--head HEAD]`; `validate --wo <path>` also prints the step plan, one line per step.

- **B12** Interface details the acceptance tests rely on (added by Claude with the acceptance test, 2026-10-10):
  - `WorkOrder` attributes are named exactly as the front-matter keys. List values are tuples of strings, and absent optional lists are empty tuples. `attempt_budget` and `max_output_tokens` are `int`. There are also `body` (the text after the front matter) and `path`.
  - `Step.paths` is a tuple of normalised paths.
  - `classify` reads `<repo_root>/docs/process/PROTECTED_PATHS.txt`.
  - `build_pack` reads FOUNDATION and RETURN_FORMAT from `<repo_root>/docs/process/outsourcing/`. `Pack` has `text`, `characters` and `estimated_tokens`.
  - Exceptions live in the module that raises them:
    - `WorkOrderError` in `workorder`;
    - `BundleError` and `TruncatedBundle` in `bundle`;
    - `QuestionsReturned` and `ImportRefused` in `importer`;
    - `ScopeError` in `scope`;
    - `SecretRefused` and `PackTooLarge` in `pack`.
  - An answer holding only a QUESTIONS block parses, with or without an empty MANIFEST and DOD. `Bundle.questions` is a tuple of the numbered questions' texts, and empty without a QUESTIONS block.
  - Truncation lines (B5) are matched with leading and trailing whitespace ignored.
  - The command line takes the repository root from `git rev-parse --show-toplevel` run in the current directory. `--wo`, `--bundle` and `--out` accept absolute paths or paths relative to the current directory. `scope` prints each violating path on a line of its own. `pack --out` writes nothing when it refuses.
  - The acceptance test runs `python -m tools.outsourcing` from inside scratch repositories with `PYTHONPATH` set to this repository.

## 5. Edge cases you must handle
- **E1** A bundle whose FILE marker uses `./tools/...` or trailing spaces → normalised; a backslash path → rejected.
- **E2** Content that itself contains a line `=== END FILE ===` inside a fenced block → still ends the file (markers win); the rest of that content then lies outside any block and the real END marker has no open block, so `parse_bundle` raises `BundleError`. Document this in the module header.
- **E3** A work order whose front matter has a value with a ` #` inside quotes → quotes are not supported by the subset; raise a clear error.
- **E4** A repository where `origin/main` is absent (shallow or single-branch clone) → B8's fetch-then-raise rule.
- **E5** An output path that already exists as a directory → import fails, nothing written.
- **E6** A `steps` item with an empty element (`a.py, , b.py`) or a trailing comma → `WorkOrderError` naming the step.

## 6. Never
- Never execute, import or evaluate any code from a bundle.
- Never reach the network, except the single `git fetch` in B8.
- Never write outside the repository root or outside `outputs`.
- Never treat an error as "clean" or "no changes".

## 7. When this order is wrong or incomplete
Return QUESTIONS if `tools/audit` already has a protected-path classifier whose behaviour differs from `PROTECTED_PATHS.txt` as described, or if the repository layout contradicts this order.

## 8. Must-catch behaviours
1. A FILE path not in `outputs` (or, with `expected`, not in `expected`) fails the import and writes nothing.
2. A missing END marker fails the import.
3. Each truncation sign in B5 fails the import.
4. A QUESTIONS block stops the import with exit code 4.
5. `scope` reports an extra changed file and a deletion as violations.
6. `pack` refuses a `.env` file and content holding a private key.
7. A work order with an output under a NEVER or GUARDED path is invalid.
8. A missing base ref is never reported as "no changes".
9. A step plan that misses an output, repeats one, or names a path outside `outputs` is invalid, and so is an order of more than 3 outputs without `steps`.
10. Every module of `tools/outsourcing`, `secrets.py` included, passes `secret_reasons`; text after a stray END marker fails the parse.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B12 and E1 to E6 are implemented; point at each.
- **D3** Unit tests cover every behaviour and edge case and pass.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` passes unmodified.
- **D5** No placeholder, swallowed error or network use beyond B8.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md` and every file in `context`. Then write the files on branch `wo/WO-1.0-01` (based on the WP-1.0 branch that holds the acceptance test), one step at a time in the order of `steps`, run the verify command until it passes, and open a pull request titled `WO-1.0-01: work-order tools` with the DOD table as its description. WO-1.0-10 may be in progress at the same time on its own branch; it touches none of your files.
