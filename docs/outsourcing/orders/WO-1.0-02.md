---
id: WO-1.0-02
wp: WP-1.0
title: Gemini relay with automatic fix rounds and ledger
model: gemini-3.7-flash
channel: jules                     # bootstrap: the relay does not exist yet
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/templates/FRAGMENTS.md
  - docs/process/outsourcing/README.md
  - docs/process/outsourcing/templates/FIX_ORDER.md
  - docs/process/outsourcing/templates/RETURN_FORMAT.md
  - tools/outsourcing/workorder.py
  - tools/outsourcing/bundle.py
  - tools/outsourcing/importer.py
  - tools/outsourcing/scope.py
  - tools/outsourcing/secrets.py
  - tools/audit/patterns.py
outputs:
  - tools/outsourcing/relay.py
  - tools/outsourcing/gemini_client.py
  - tools/outsourcing/checks.py
  - tools/outsourcing/fixorder.py
  - tools/outsourcing/ledger.py
  - tests/aqis_lab/outsourcing/stub_gemini_server.py
  - tests/aqis_lab/outsourcing/test_relay.py
  - tests/aqis_lab/outsourcing/test_gemini_client.py
  - tests/aqis_lab/outsourcing/test_checks.py
  - tests/aqis_lab/outsourcing/test_fixorder.py
  - tests/aqis_lab/outsourcing/test_ledger.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing -q --tb=short
---

# WO-1.0-02 — Gemini relay with automatic fix rounds and ledger

## 1. Context
WO-1.0-01 built the work-order parser, bundle importer, scope check and secret detector (in your context). This order builds the relay that a Claude Code session runs to send a work order to the Gemini API, import the answer, check it, and send fix orders until the checks pass or the attempt budget runs out. The session's network proxy attaches the Gemini API key to requests for `generativelanguage.googleapis.com` (header `x-goog-api-key`); the relay never handles a key. The relay's stdout is read by Claude, so it must be short; full logs go to files.

## 2. Your job
`python -m tools.outsourcing.relay --wo <path> [--attempts N] [--api-base URL] [--timeout SECONDS] [--dry-run]` runs one work order end to end and exits with a code that says what happened.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/gemini_client.py` | Call the Gemini `generateContent` REST endpoint with the standard library | `GeminiClient(api_base, model, timeout)`; `generate(system_text, turns, max_output_tokens, temperature) -> GeminiReply` (text, finish reason, prompt and output token counts, model version, raw JSON); raises `CredentialError` (401, 403), `ModelError` (404), `RateLimited` (429 after retries), `TransportError` | 250 |
| `tools/outsourcing/checks.py` | Run the post-import checks in order and collect results | `run_checks(order, repo_root, attempt_dir) -> CheckResults` (each check: name, passed, summary, log path) | 300 |
| `tools/outsourcing/fixorder.py` | Build a fix order from failed checks | `build_fix_order(order, results, attempt_number) -> str` following `FIX_ORDER.md` | 150 |
| `tools/outsourcing/ledger.py` | Write the summary file and the ledger fragment | `write_summary(...)`, `write_ledger_fragment(...)` in the formats of `FRAGMENTS.md` | 150 |
| `tools/outsourcing/relay.py` | Orchestrate attempts and the command line | `run(order_path, options) -> RelayOutcome`; `main(argv) -> int` | 300 |
| `tests/aqis_lab/outsourcing/stub_gemini_server.py` | Local stand-in for the Gemini API in tests: records each request (path, headers, body) and replies from a script of canned responses | a context manager that yields its base URL and the recorded requests | 150 |
| `tests/aqis_lab/outsourcing/test_*.py` | Unit tests per module above | | 300 each |

## 4. Required behaviour
- **B1** Load the order with `load_work_order`; refuse with exit 2 unless `channel` is `api`.
- **B2** Build the request: the system instruction is FOUNDATION.md; the first user turn is the order (front matter and body), then each context file and read-only test wrapped as in the paste pack, then RETURN_FORMAT.md. Refuse any secret-looking file (exit 6) and any request over 600,000 characters (exit 5). Generation settings: temperature 0.2, the order's `max_output_tokens`.
- **B3** Send to `<api-base>/v1beta/models/<model>:generateContent` (default api-base `https://generativelanguage.googleapis.com`). Send no key, in no header, parameter or body. Retry 429 and 503 up to 3 times with 2, 4 and 8 second waits; other transport errors once.
- **B4** Save each raw response as JSON under `.relay/<WO>/attempt-<n>/response.json`, and every check log under the same folder. Never print file contents or full logs to stdout.
- **B5** Attempt 1 imports in `first` mode; later attempts in `fix` mode. QUESTIONS → stop with exit 4, write the questions into the summary, write no files.
- **B6** Checks, in order, stopping at the first failure class but reporting all that ran: scope (WO-1.0-01); module headers of every output `.py` file contain the sections of `CHANGE_CONTROL.md` section 1; the compromise patterns of `tools/audit/patterns.py` find nothing in the outputs; the SHA-256 of every read-only test is unchanged; then each `verify` command with a timeout (default 600 seconds), capturing output to the attempt folder.
- **B7** After the verify commands, re-hash the read-only tests: any change is an integrity failure (exit 9) and stops everything.
- **B8** On a failed attempt with budget left, send the fix order from `build_fix_order` as a new user turn after the previous turns and the model's previous answer (multi-turn), with trimmed output: the first 20 and last 40 lines of each failing log, at most 120 lines in total.
- **B9** Finish reason `MAX_TOKENS`, `SAFETY` or an empty answer counts as a failed attempt with that reason in the fix order ("your answer was cut off: return fewer files per answer or shorter files").
- **B10** On success or exhaustion, write `docs/outsourcing/returns/<WO>/summary.md` (result, attempts, per-attempt tokens and model version, checks table, files written) and `docs/outsourcing/ledger.d/<WO>.md`. Print at most 25 lines: result, attempts, file count, checks table, tokens, and the summary path.
- **B11** Exit codes: 0 accepted; 2 invalid order or wrong channel; 4 questions; 5 oversize or truncation; 6 secret; 7 credential (print "ACCESS: add or fix the Gemini API credential on the aqis-lab environment"); 8 attempts exhausted (with the remaining failures listed); 9 integrity; 10 network. `--dry-run` builds and measures the request, prints its size, and sends nothing.

## 5. Edge cases you must handle
- **E1** The API returns several text parts → concatenate them in order.
- **E2** The API returns 200 with no candidates → failed attempt with the reason recorded.
- **E3** A verify command that hangs → killed at the timeout, recorded as failed, the next attempt proceeds.
- **E4** `.relay/` does not exist → created; it must be listed in `.gitignore` by the WP (not by you).
- **E5** The order changed on disk between attempts → refuse to continue (exit 2): the order is fixed for the duration of a run.

## 6. Never
- Never read, accept, log or store an API key or token.
- Never send a file that is not the Foundation, the order, a context file, a read-only test or the return format.
- Never edit files outside `outputs`, never touch read-only tests, and never `git commit` (Claude commits).

## 7. When this order is wrong or incomplete
Return QUESTIONS if the WO-1.0-01 functions you depend on lack something B1 to B11 need.

## 8. Must-catch behaviours
1. The request contains only the allowed files (the stub records it; the test compares).
2. No key appears in any request header, URL or body, or in any log.
3. A failing verify produces a fix order containing the trimmed output and the list of files allowed to change.
4. The run stops after the attempt budget with exit 8.
5. QUESTIONS → exit 4 and no files written.
6. HTTP 401 → exit 7 with the ACCESS message.
7. A read-only test modified during verify → exit 9.
8. The ledger fragment holds the token counts from the API's usage metadata.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B11 and E1 to E5 are implemented; point at each.
- **D3** Unit tests use only the local stub server; none reaches the internet.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py` passes unmodified.
- **D5** No placeholder, swallowed error or key handling anywhere.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md` and every file in `context`. Then branch `wo/WO-1.0-02` from the WP-1.0 branch after WO-1.0-01 is merged into it; run the verify command until it passes; open a pull request titled `WO-1.0-02: Gemini relay` with the DOD table.
