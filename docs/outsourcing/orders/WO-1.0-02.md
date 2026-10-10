---
id: WO-1.0-02
wp: WP-1.0
title: Relay building blocks - records, interface views, requests, checks, fix orders and step log
model: default
channel: jules                     # bootstrap: sent after WO-1.0-01 and WO-1.0-10 are merged; WO-1.0-11 follows it
attempt_budget: 3
risk_tier: T1
max_output_tokens: 40000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/outsourcing/README.md
  - docs/process/outsourcing/FOUNDATION.md
  - docs/process/outsourcing/templates/FIX_ORDER.md
  - docs/process/outsourcing/templates/RETURN_FORMAT.md
interfaces:
  - tools/outsourcing/chat.py
  - tools/outsourcing/workorder.py
  - tools/outsourcing/scope.py
  - tools/outsourcing/secrets.py
  - tools/audit/gate.py
  - tools/audit/patterns.py
outputs:
  - tools/outsourcing/records.py
  - tools/outsourcing/interface.py
  - tools/outsourcing/prompt.py
  - tools/outsourcing/checks.py
  - tools/outsourcing/fixorder.py
  - tools/outsourcing/steplog.py
  - tests/aqis_lab/outsourcing/test_records.py
  - tests/aqis_lab/outsourcing/test_interface.py
  - tests/aqis_lab/outsourcing/test_prompt.py
  - tests/aqis_lab/outsourcing/test_checks.py
  - tests/aqis_lab/outsourcing/test_fixorder.py
  - tests/aqis_lab/outsourcing/test_steplog.py
steps:
  - tools/outsourcing/records.py, tests/aqis_lab/outsourcing/test_records.py
  - tools/outsourcing/interface.py, tests/aqis_lab/outsourcing/test_interface.py
  - tools/outsourcing/prompt.py, tests/aqis_lab/outsourcing/test_prompt.py
  - tools/outsourcing/checks.py, tests/aqis_lab/outsourcing/test_checks.py
  - tools/outsourcing/fixorder.py, tests/aqis_lab/outsourcing/test_fixorder.py
  - tools/outsourcing/steplog.py, tests/aqis_lab/outsourcing/test_steplog.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_records.py tests/aqis_lab/outsourcing/test_interface.py tests/aqis_lab/outsourcing/test_prompt.py tests/aqis_lab/outsourcing/test_checks.py tests/aqis_lab/outsourcing/test_fixorder.py tests/aqis_lab/outsourcing/test_steplog.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py -q --tb=short
---

# WO-1.0-02 — Relay building blocks: records, interface views, requests, checks, fix orders and step log

## 1. Context
The relay has a Claude Code session send a work order to a pool of models one step at a time: each step asks for at most a module and its tests, is checked at once, and goes back to the model with the failures until it passes. WO-1.0-01 built the work-order parser with step plans, the importer, the scope check and the secret detector; WO-1.0-10 built the paced model clients and the provider-neutral `ChatRequest` record that both clients accept. This order builds the relay's pure building blocks; WO-1.0-11 then builds the orchestration (worktree, step runner, command line) on top of them. Nothing here calls the network or git, except the scope check and the test commands that `checks.py` runs.

## 2. Your job
Six modules, each usable and tested on its own: the shared records and exit codes, interface views of Python files, the provider-neutral requests sent to a model, the checks run after each step and at the end, the fix-order text, and the step log the relay resumes from.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/records.py` | Shared records of a relay run | frozen dataclasses `RelayOptions`, `StepPart` (label, paths), `Request` (a `chat.ChatRequest`, sent paths, missing paths, characters), `CheckResult` (name, passed, summary, log path, output paths named in the log, integrity flag), `CheckResults`, `StepRecord`, `StepOutcome`, `RelayOutcome`; enum `Result` with `exit_code` (B1) | 200 |
| `tools/outsourcing/interface.py` | Interface view of a Python file | `interface_view(path, text) -> str` (B2) | 200 |
| `tools/outsourcing/prompt.py` | Build every request sent to a model | `step_request(order, plan, part, root) -> Request`; `with_fix_turn(request, answer_text, fix_text, current_files) -> Request`; `final_fix_request(order, plan, root, fix_text, focus_paths) -> Request`; `step_pack(order, plan, part, root) -> str`; raises `SecretInRequest` naming the path | 300 |
| `tools/outsourcing/checks.py` | Run the checks and collect results | `quick_checks(order, part, worktree_path, log_dir, base_commit, python, timeout) -> CheckResults`; `full_checks(order, worktree_path, log_dir, base_commit, python, timeout) -> CheckResults`; `hash_read_only_tests(order, worktree_path) -> dict[path, sha256]` | 300 |
| `tools/outsourcing/fixorder.py` | The fix-order text | `build_fix_order(order, results, fix_number, allowed_paths, step_label, stop_reason) -> str` following `FIX_ORDER.md`; `trim_log(text) -> str` | 150 |
| `tools/outsourcing/steplog.py` | The step log `docs/outsourcing/returns/<WO>/steps.md` | `parse(text) -> StepLog`; `render(steplog) -> str`; `StepLog.next_part(plan) -> StepPart or None`; `StepLog.wp_branch`; read-only tuples `runs`, `accepted`, `switches`, `stops` of frozen records; `record_run_start(...)`, `record_accepted(...)`, `record_switch(...)`, `record_stop(...)` returning a new `StepLog`; raises `StepLogError` | 250 |
| `tests/aqis_lab/outsourcing/test_*.py` | Unit tests per module, in scratch directories and scratch git repositories | | 300 each |

## 4. Required behaviour
- **B1** `records.Result` has exactly these members and exit codes: `ACCEPTED` 0; `INVALID` 2 (invalid order, wrong channel, unknown or unavailable model, unsuitable checkout); `QUESTIONS` 4; `CUT_OFF` 5; `SECRET` 6; `CREDENTIAL` 7; `EXHAUSTED` 8; `INTEGRITY` 9; `NETWORK` 10 (network failure or an unexpected API response, after retries); `PAUSED_DAILY` 11; `PAUSED_BUSY` 12; `TOO_LARGE` 13; `GIT` 14. Its display name uses hyphens (`PAUSED-DAILY`). `RelayOptions` holds every option of the relay's command line: `wo`, `attempts`, `api_base`, `timeout`, `verify_timeout`, `pool`, `dry_run`, `status`, `models`, `restart`, `pack_step`, `out`, `no_push`. `StepRecord` holds a step part's label, its files with SHA-256, attempts, model, provider and model version, prompt and output tokens, and seconds waited.
- **B2** `interface_view` returns, in file order and without bodies: the module docstring, `__all__`, top-level constants whose literal value is under 80 characters, each public class with its bases, docstring, dataclass fields and public method signatures with their docstrings, and each public function's signature with its docstring. A file that does not parse is returned whole, with a first line saying so.
- **B3** `step_request` builds a `chat.ChatRequest`: the system text is FOUNDATION.md, `max_output_tokens` is the order's `max_output_tokens` (the client caps it at the chosen model's limit), and there is exactly one `user` turn. No other generation setting exists: the clients never send a temperature. The user turn holds, in this order:
  1. the order (front matter and body);
  2. each `context` file and each read-only test, wrapped `=== CONTEXT: <path> ===` … `=== END CONTEXT ===`;
  3. each `interfaces` file as its interface view, wrapped `=== INTERFACE: <path> ===` … `=== END INTERFACE ===`;
  4. every output of an earlier step that exists in the tree: `.py` files outside `tests/` as interface views (`=== ACCEPTED INTERFACE: <path> ===`), every other file in full (`=== ACCEPTED: <path> ===`), each closed by its `=== END … ===` line;
  5. a step block: `=== THIS STEP ===`, then "Step <label> of <n>. Return exactly these files, each complete: <paths>. Files from earlier steps are shown above; call them as shown and do not return them. Later steps will add: <paths, or none>. The tests you return must pass with only the files above and the files you return now.", then `=== END THIS STEP ===`;
  6. RETURN_FORMAT.md.

  Any file for which `secret_reasons` is non-empty raises `SecretInRequest` with its path; nothing is built.
- **B4** `with_fix_turn` appends the model's previous answer as an `assistant` turn, then a `user` turn holding the fix text followed by `=== CURRENT: <path> ===` … `=== END CURRENT ===` blocks with the full text of each file in `current_files`.
- **B5** `final_fix_request` is a new conversation: items 1 to 3 of B3; every output in `focus_paths` in full as a CURRENT block; the other outputs as in B3 item 4; then the fix text; then RETURN_FORMAT.md.
- **B6** `step_pack` returns FOUNDATION.md followed by the user turn of B3, for pasting into AI Studio.
- **B7** `quick_checks`, after a step part is imported, runs in this order, reporting every check that ran and stopping at the first that fails:
  1. scope: `check_scope` against `base_commit`;
  2. module headers: every `.py` file of the part has the sections of `CHANGE_CONTROL.md` section 1 (reuse the audit gate's header check if `tools/audit/gate.py` offers one);
  3. compromise patterns: the part's files are scanned with the same function the audit gate uses for added lines, applied to every line, so its `# audit-allow:` handling applies unchanged; if the gate offers no importable function for this, return QUESTIONS;
  4. the SHA-256 of every read-only test is unchanged;
  5. every `.py` file of the part compiles (`py_compile` into a scratch folder);
  6. if the part holds test files, `<python> -m pytest <those files> -q --tb=short` in `worktree_path`, with `timeout`, output saved under `log_dir`.
- **B8** `full_checks` runs scope, headers, patterns, read-only test hashes and compilation over all outputs, then each `verify` command in order: split with `shlex`, run without a shell, the worktree as working directory, a leading `.venv/bin/python` replaced by `python`, `PYTHONPATH` removed from the environment, each with `timeout`, output saved under `log_dir`.
- **B9** Integrity: both check functions hash the read-only tests before and after every test or verify run; a change produces a failed result with the integrity flag set, and nothing after it runs.
- **B10** A command that exceeds its timeout has its whole process group killed and is recorded as failed with "timed out after <n> s". Each result lists the output paths that its log names (exact path matches).
- **B11** `build_fix_order` follows `FIX_ORDER.md`: the failed checks with `trim_log` output (the first 20 and the last 40 lines of each failing log, at most 120 lines for all checks together, cut marks shown as `[… <n> lines …]`), and the allowed paths. With a `stop_reason` instead of failed checks: `MAX_TOKENS` → "Your answer was cut off before the end. Return the same files again, complete; keep comments and docstrings short."; `SAFETY`, `RECITATION` or an empty answer → "Your answer was blocked or empty (<reason>). Return the files again, complete, in RETURN_FORMAT form."
- **B12** The step log is a Markdown file with one table per kind: runs (UTC time, the order's SHA-256, WP branch, model), accepted parts (label, files with SHA-256, attempts, model, provider, model version, prompt and output tokens, seconds waited), model switches (UTC time, part label, from model, to model, reason) and stops (UTC time, reason such as `PAUSED-DAILY`, `PAUSED-BUSY` or `QUESTIONS`, reset time or empty). `render(parse(text)) == text` for every log `render` produced. Unknown or malformed lines raise `StepLogError`; a log is never treated as empty because it failed to parse. An absent file means an empty log.
- **B13** `next_part(plan)`: the accepted files are those of every accepted part. The next part is the first plan step that has a file not accepted; if some of its files are already accepted (an interrupted split), the part holds only the remaining files, labelled `<k>.<n>` with the next free sub-number. Matching is by path, so an amended plan keeps accepted files. `None` means every output is accepted. `wp_branch` is the WP branch of the first run.

- **B14** Interface details the acceptance tests rely on (added by Claude with the acceptance test, 2026-10-10):
  - **`Request`** has fields `chat` (the `chat.ChatRequest`), `sent_paths`, `missing_paths` and `characters`. `characters` is the length of the system text plus every turn's text. `StepPart(label, paths)` takes a string label (`"2"`, `"2.1"`) and a tuple of paths.
  - **Check records.** `CheckResult` has fields `name`, `passed`, `summary`, `log_path`, `output_paths` and `integrity`. `CheckResults(results)` holds a tuple of them in run order, with properties `passed` (every result passed) and `integrity_failed`.
  - **Check names.** In B7 order, the checks are named `scope`, `headers`, `patterns`, `read-only-tests`, `compile` and `tests`. The verify commands are `verify-1`, `verify-2`, and so on. A check that does not run has no result.
  - **Headers (B7 item 2).** Every `.py` file with a non-blank line, test files included, needs all six section labels of `CHANGE_CONTROL.md` section 1 in its module docstring.
  - **Patterns (B7 item 3).** Choose the table with `tools.audit.gate.scan_table(path)`. Apply it, with `tools.audit.patterns.ALLOW_RE`, exactly as `gate.check_patterns_and_headers` applies them to added lines, but to every line. This is the gate's importable function, so no QUESTIONS are needed for it.
  - **Interpreter.** A leading `.venv/bin/python` in a verify command is replaced by the interpreter passed as `python`.
  - **Fix orders.** `build_fix_order` reads each failed result's log from its `log_path`. `stop_reason` is `None` when the fix order is about failed checks. When the 120-line cap binds, checks keep their full trim in run order until the cap is reached. The rest are shortened, or left out with a one-line note.
  - **Step log.**
    - `steplog.parse("")` is the empty log.
    - The recording functions are methods of `StepLog` that return a new log:
      - `record_run_start(time_utc, order_sha256, wp_branch, model)`;
      - `record_accepted(step_record)`;
      - `record_switch(time_utc, label, from_model, to_model, reason)`;
      - `record_stop(time_utc, reason, reset_utc_or_None)`.
    - Times are timezone-aware datetimes.
    - `StepRecord` has fields `label`, `files` (a tuple of `(path, sha256)` pairs), `attempts`, `model`, `provider`, `model_version`, `prompt_tokens`, `output_tokens` and `seconds_waited`.
  - **`Result.<member>.display_name`** is the hyphenated display name.

## 5. Edge cases you must handle
- **E1** An interface file that does not parse → returned whole with the marker line (B2).
- **E2** A log or command output with bytes that are not UTF-8 → decoded with replacement, never a crash.
- **E3** A step part whose tests import a module from a later step → the test fails and is reported like any failure; nothing special-cases it.
- **E4** An earlier output listed in the plan but missing from the tree → left out of the request and listed in `Request.missing_paths`, so the caller can decide.
- **E5** A step log written by an older run that lacks a stops table → parsed as having no stops.

## 6. Never
- Never call a model API or `git` (except through `check_scope` and the test commands).
- Never send or embed a key, and never include a file that is not the Foundation, the order, a context, interface or read-only test file, an output of this order, or the return format.
- Never treat a parse error, a timeout or a missing log as a pass.

## 7. When this order is wrong or incomplete
Return QUESTIONS if `tools/audit/gate.py` offers no importable scan or header check (B7), or if the WO-1.0-01 interfaces lack something these modules need.

## 8. Must-catch behaviours
1. A step request holds only allowed files, in the order and wrapping of B3; earlier code outputs appear as interface views, and the step block names exactly the part's files.
2. A secret-looking file raises `SecretInRequest` naming it, and nothing is built.
3. A request carries the order's `max_output_tokens` and nothing else beyond the system text and turns.
4. A fix order holds at most 120 lines of trimmed output and only the allowed paths.
5. The compromise check passes a flagged line that ends with `# audit-allow: <reason>` and fails the same line without it, exactly as the audit gate does.
6. A read-only test changed during a test run gives an integrity failure, and nothing after it runs.
7. The step log round-trips byte for byte; `next_part` resumes at the first unaccepted file's step and reduces a partly accepted step to its remaining files.
8. Every `Result` maps to the exit code in B1.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B14 and E1 to E5 are implemented; point at each.
- **D3** Tests run offline, in scratch directories and scratch git repositories.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py` passes unmodified.
- **D5** No placeholder, swallowed error or key handling anywhere.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md`, every file in `context` and every file in `interfaces`. Then branch `wo/WO-1.0-02` from the WP-1.0 branch after WO-1.0-01 and WO-1.0-10 are merged into it, and work one step at a time in the order of `steps`. Run the verify command until it passes, and open a pull request titled `WO-1.0-02: relay building blocks` with the DOD table.
