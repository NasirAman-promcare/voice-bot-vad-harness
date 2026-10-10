---
id: WO-1.0-11
wp: WP-1.0
title: Relay orchestration - model router, worktree, ledger, step runner and command line
model: default
channel: jules                     # bootstrap: sent after WO-1.0-02 is merged; the relay exists once this order is
attempt_budget: 3
risk_tier: T1
max_output_tokens: 40000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/templates/FRAGMENTS.md
  - docs/process/outsourcing/README.md
  - config/aqis_lab/model_pool.json
  - tests/aqis_lab/outsourcing/stub_model_server.py
interfaces:
  - tools/outsourcing/workorder.py
  - tools/outsourcing/bundle.py
  - tools/outsourcing/importer.py
  - tools/outsourcing/chat.py
  - tools/outsourcing/limits.py
  - tools/outsourcing/governor.py
  - tools/outsourcing/gemini_client.py
  - tools/outsourcing/openai_client.py
  - tools/outsourcing/records.py
  - tools/outsourcing/prompt.py
  - tools/outsourcing/checks.py
  - tools/outsourcing/fixorder.py
  - tools/outsourcing/steplog.py
outputs:
  - tools/outsourcing/router.py
  - tools/outsourcing/worktree.py
  - tools/outsourcing/ledger.py
  - tools/outsourcing/stepper.py
  - tools/outsourcing/relay.py
  - tests/aqis_lab/outsourcing/test_router.py
  - tests/aqis_lab/outsourcing/test_worktree.py
  - tests/aqis_lab/outsourcing/test_ledger.py
  - tests/aqis_lab/outsourcing/test_stepper.py
  - tests/aqis_lab/outsourcing/test_relay.py
steps:
  - tools/outsourcing/router.py, tests/aqis_lab/outsourcing/test_router.py
  - tools/outsourcing/worktree.py, tests/aqis_lab/outsourcing/test_worktree.py
  - tools/outsourcing/ledger.py, tests/aqis_lab/outsourcing/test_ledger.py
  - tools/outsourcing/stepper.py, tests/aqis_lab/outsourcing/test_stepper.py
  - tools/outsourcing/relay.py, tests/aqis_lab/outsourcing/test_relay.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_11.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing -q --tb=short
---

# WO-1.0-11 — Relay orchestration: model router, worktree, ledger, step runner and command line

## 1. Context
WO-1.0-10 built the model clients for both API shapes, the pool loader and the governor, which paces every model and provider under its limits, retries rate limits and overloads itself, and raises named exceptions for what it cannot fix. WO-1.0-02 built the relay's building blocks: records and exit codes, provider-neutral requests, checks, fix orders and the step log. This order wires them into the relay that a Claude Code session runs, usually in the background while it works on something else. A router sends each step to the best model in `config/aqis_lab/model_pool.json` that may serve the order's risk tier and still has quota, so one model's daily limit never stops the build. The relay works in its own git worktree on branch `wo/<WO>`, commits and pushes each accepted step, and resumes exactly where it stopped, from any session. Its stdout is read by Claude, so it stays short; full logs go to files.

## 2. Your job
`python -m tools.outsourcing.relay --wo <path> [options]` runs one `api`-channel work order step by step, then verifies the whole order, and exits with the code of its `Result`. `--status` reports quota use, `--models` checks the pool's model names against each provider, `--dry-run` plans and measures without sending, and `--pack-step` writes one step for the paste channel.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/router.py` | Choose the model for each step part; build its client; per-model results from the step logs | `model_stats(root) -> ModelStats` (per model: parts, parts accepted at the first attempt, attempts; plus unreadable logs); `Router(pool, governor, stats)`; `Router.choose(order, input_estimate, exclude) -> ModelSpec`; `client_for(spec, governor, timeout, base_url_override) -> client`; raises `PoolExhausted` (earliest reset) and `NoEligibleModel` (reason) | 250 |
| `tools/outsourcing/worktree.py` | The order's worktree and branch | `read_step_log(root, wo_id) -> text or None` (from `wo/<WO>` without checking it out); `open_worktree(root, wo_id, wp_branch) -> Worktree` (path, branch, base commit); `discard_attempt(worktree, paths)`; `commit(worktree, paths, message)`; `push(worktree)`; `remove(worktree)`; raises `WorktreeError` carrying git's message | 250 |
| `tools/outsourcing/ledger.py` | The summary and the ledger fragment | `write_summary(path, outcome)`, `write_ledger_fragment(path, outcome)` (B17) | 200 |
| `tools/outsourcing/stepper.py` | Run one step part, or the final verification, with its fix rounds and model switches | `RunContext` (order, plan, worktree, router, governor, step log, options, clock, sleeper, log root); `run_part(ctx, part) -> StepOutcome`; `run_final(ctx) -> StepOutcome` | 300 |
| `tools/outsourcing/relay.py` | Command line, the run loop, the printed report, and the status, models, dry-run and pack modes | `run(options) -> RelayOutcome`; `main(argv) -> int` | 300 |
| `tests/aqis_lab/outsourcing/test_*.py` | Unit and end-to-end tests with the stub server, scratch git repositories with a local bare `origin`, and a simulated clock | | 300 each |

## 4. Required behaviour
**The router**
- **B1** `Router.choose`:
  - An order whose `model` is not `default` may use only that model: it must exist, belong to an enabled provider and list the order's `risk_tier`, otherwise `NoEligibleModel` (the relay gives `INVALID`); if it is exhausted for the day, `PoolExhausted`.
  - With `default`, the candidates are `Pool.candidates(risk_tier)` minus models in `exclude`, models for which `Governor.exhausted_until` gives a time, and models whose `max_input_tokens` or input-token ceiling (`limits.effective`) is below `input_estimate`.
  - Order: by `rank`, except that a model with at least 8 recorded parts whose first-pass rate is 25 percentage points or more below that of the best model with at least 8 recorded parts moves behind all others, keeping their relative order. The choice is the first candidate for which `Governor.delay_for` is 0, else the first candidate.
  - No candidate left: `PoolExhausted` with the earliest reset among the models that would otherwise qualify, or `NoEligibleModel` when none qualifies at all (its reason says whether size alone ruled them out).
- **B2** `model_stats` reads every `docs/outsourcing/returns/*/steps.md` with `steplog.parse`. A log that does not parse is listed as unreadable in the stats and in the summary, and its parts are left out; it never stops the run. `client_for` returns a `GeminiClient` or an `OpenAIClient` built from the `ModelSpec`, according to its provider's `api`, with the provider's `base_url` unless `--api-base` overrides it (a testing aid that applies to every provider).

**Starting a run**
- **B3** Options: `--wo PATH`, `--attempts N` (1 to 5, default the order's `attempt_budget`), `--api-base URL`, `--timeout SECONDS` per API call (default 300), `--verify-timeout SECONDS` per test or verify command (default 600), `--pool PATH` (default `config/aqis_lab/model_pool.json`), `--dry-run`, `--status`, `--models`, `--restart`, `--pack-step K --out PATH`, `--no-push`. They fill `records.RelayOptions`.
- **B4** Load the order with `load_work_order` and its plan with `plan_steps`; refuse with `INVALID` unless `channel` is `api`. Load the pool. The main checkout must be on a branch named `claude/wp-…`, and the order and every file it sends must be committed there without local changes; other uncommitted work in the main checkout is allowed and never touched. A lock file `.relay/locks/<WO>.lock` held by a live process → `GIT` ("another relay is running this order").
- **B5** Before touching any branch, read the step log from `wo/<WO>` (local, or `origin/wo/<WO>` after one fetch) with `read_step_log`. If it names a different WP branch from the current one → `INVALID` naming both, with no merge and no records.
- **B6** Worktree (`open_worktree`), in `.relay/wt/<WO>` on branch `wo/<WO>`:
  - the branch comes from the local `wo/<WO>` when it contains `origin/wo/<WO>`, from `origin/wo/<WO>` when that is ahead, and is created from the WP branch's head when neither exists; branches that have diverged → `GIT`;
  - an existing worktree is reused when it is on `wo/<WO>`; uncommitted changes to the order's outputs and record files belong to an attempt that did not pass and are discarded (`discard_attempt`); any other uncommitted change → `GIT` naming the paths;
  - if the WP branch has commits that `wo/<WO>` lacks, they are merged in (`--no-ff --no-edit`); a conflict aborts the merge and gives `GIT` naming the paths;
  - the base commit for scope checks is then the WP branch's head, so only the relay's own changes are ever in scope. The order is loaded again from the worktree, and every file sent is read there, never from the main checkout.
- **B7** Resume: `StepLog.next_part(plan)` gives the next part; a run start is recorded (UTC time, the order's SHA-256, the WP branch, `default` or the pinned model). If the order's hash differs from the last run's, the summary says "order amended since the last run". An accepted file whose hash changed since acceptance is listed in the summary, never re-requested. `--restart` starts a new step log, so every step is requested again and the answers replace the files.

**One step part** (`stepper.run_part`)
- **B8** Build the request with `prompt.step_request` (`SecretInRequest` → `SECRET`), choose the model with `Router.choose` using the request's measured size, and send it with the model's client, which measures it again and paces and retries rate limits itself. All fix turns of a part stay on the model that answered its first attempt.
- **B9** Model switches, which never use up an attempt; each starts the part again in a fresh conversation on the next choice (`exclude` grows with every model left behind) and is recorded in the step log and the summary:
  - `DailyQuotaExhausted` → switch; when `Router.choose` raises `PoolExhausted`, record the stop with the earliest reset and finish with `PAUSED_DAILY`, printing it in UTC, provider time and Asia/Karachi with the command that resumes;
  - `ServiceBusy` → switch to a model of another provider when there is one; otherwise wait 5 minutes and send the same request again, then 10 minutes and again, with the run's clock and sleeper, and if still busy record the stop and finish with `PAUSED_BUSY`;
  - `ModelError` (no quota on this tier, or an unknown model name) → leave that model out for the rest of the run, report "POOL: remove or rename <model>", and switch; with nothing left → `INVALID`;
  - `CredentialError` → leave every model of that provider out for the rest of the run, report "ACCESS: add or fix the <provider> credential on the aqis-lab environment", and switch; with nothing left → `CREDENTIAL`.

  - `StepTooLarge` → leave that model out for this part and switch to one that fits; when size alone leaves no model, finish with `TOO_LARGE`, with the figure, the limits and "split this step, or move context files that are only called into `interfaces`".

  Other client exceptions: `ApiError` and `TransportError` → `NETWORK`.
- **B10** Raw records: save each request's size figures, sent paths and model, and each raw response, as JSON under `.relay/logs/<WO>/step-<label>/attempt-<n>/` (final rounds under `final/attempt-<n>/`); check logs go to the same folder. Never print file contents or full logs to stdout.
- **B11** Import: parse the answer with `parse_bundle`. The first attempt imports in `first` mode with `expected` = the part's files; a fix attempt imports in `fix` mode with `expected` = the files that fix allows. A `BundleError` is a failed attempt with its message as the failure. A QUESTIONS block → B15.
- **B12** Quick checks (`checks.quick_checks`, with the main checkout's interpreter). On a failure with attempts left, a fix turn in the same conversation (`prompt.with_fix_turn`): the fix order from `build_fix_order` allows the part's files plus any earlier output that a failing log names, whose full text is attached as CURRENT blocks. An earlier file changed this way is recorded again under the current part. An integrity failure → B15 at once.
- **B13** Cut-off answers: a finish of `MAX_TOKENS`, `SAFETY` or `RECITATION`, or an answer with no text, is a failed attempt whose fix order carries that `stop_reason`. A part of two or more files that is cut off is split into one fresh request per file, in the part's order (labels `<k>.1`, `<k>.2`, …), each its own part in the step log. A one-file part still cut off on its last attempt → `CUT_OFF` ("output cut off: split this file's work").
- **B14** Accepting a part: record it in the step log with the model and provider that wrote it, then commit exactly the part's files, any earlier file changed under B12, and the step log, with the message `<WP> <WO> step <label>/<n>: <file names> (relay, <model>)`. Push `wo/<WO>` unless `--no-push`.
- **B15** Questions: the questions go into the summary, a stop with reason `QUESTIONS` goes into the step log, nothing is imported, and the run finishes with `QUESTIONS`. Integrity: a failed integrity check finishes with `INTEGRITY` at once; nothing is committed and the worktree is kept for inspection.

**Finishing**
- **B16** Final verification (`stepper.run_final`), after the last part: `checks.full_checks`. On a failure with attempts left, `prompt.final_fix_request` with `focus_paths` = the outputs the failing logs name and all outputs allowed, sent to a model chosen by the router (model switches as in B9); import in `fix` mode with `expected` = all outputs; run the full checks again. When they pass, commit and push the round's files with `<WP> <WO> final fix <n> (relay, <model>)`. After the last attempt without a pass → `EXHAUSTED`, listing the remaining failures.
- **B17** Records at every finish after B6: `docs/outsourcing/returns/<WO>/summary.md` (the result's display name; per part the files, attempts, model, provider, tokens and seconds waited; model switches with their reasons; the checks table; the governor's report; unverified providers; files written) and `docs/outsourcing/ledger.d/<WO>.md` (the ledger row of `FRAGMENTS.md` with total requests, tokens and the models used). They are committed with the step log and pushed, except after an integrity failure (nothing committed) or when the finish itself came from a git or push failure (committed locally, not pushed).
- **B18** Printed report, at most 25 lines: the result; parts done of total; requests per model, retries by kind and minutes waited; tokens in and out; any POOL or ACCESS line from B9; the checks table; the summary path; for `PAUSED_DAILY` and `PAUSED_BUSY`, the resume command and the earliest useful time; for `ACCEPTED`, the merge command `git merge --no-ff wo/<WO>`. On `ACCEPTED` the worktree is removed; the branch stays. The process exits with `Result.exit_code`.

**Other modes**
- **B19** `--status` (no `--wo`): from the pool and the governor's report, without sending anything: per model, its provider, rank, risk tiers, requests counted today against the daily limit (configured and server-learned), exhausted until, and the first-pass rate from `model_stats`; per provider, monthly tokens against `tokens_per_month` and whether it is unverified; the next resets in UTC, provider time and Asia/Karachi.
- **B20** `--models` (no `--wo`): for every enabled provider, `list_models` once, then one line per pool model of that provider: present or missing. Exit `ACCEPTED` when all are present, else `INVALID`. No generation request is sent.
- **B21** `--dry-run`: build every part's request from the main checkout, without a worktree, using the outputs that already exist and noting those that do not; measure each offline (characters ÷ 3.5); print per step the estimate, the number of earlier outputs not yet written, and the model the router would choose now; then the expected requests (from the number of steps to steps × attempts + attempts) against the requests left today across the models eligible for the order's tier. Send nothing.
- **B22** `--pack-step K --out PATH`: write `prompt.step_pack` for step K, with earlier outputs from the main checkout, to PATH. Send nothing. The reply is imported with `python -m tools.outsourcing import --wo <path> --bundle <file> --step K`.
- **B23** Concurrency: several relay processes for different orders may run at once in one checkout. Each has its own worktree, log folder and lock; they share the governor's state file in the main checkout's `.relay/`, so their requests are paced together, and the router's preference for a model that can serve without waiting spreads them across the pool.

## 5. Edge cases you must handle
- **E1** A reply with several text parts → joined in order by the client; an empty text is a failed attempt (B13).
- **E2** A reply with no choices or candidates, or a block reason → a failed attempt with the reason recorded.
- **E3** `.relay/` does not exist → created; the WP lists it in `.gitignore` (not you).
- **E4** The WP branch gains a commit that changes the order or a read-only test during a run → this run continues with what it loaded; the next run merges the change (B6) and the summary notes it.
- **E5** A git lock held by another process → retry up to 5 times over 10 seconds, then `GIT` with git's message.
- **E6** The push is rejected because `origin/wo/<WO>` moved → `GIT` naming the remote commit; never force.
- **E7** A fresh session with an empty `.relay/` → B6 recreates the worktree from `origin/wo/<WO>` and B7 resumes from its step log.
- **E8** A rerun after a failed attempt left files in the worktree → those changes are discarded (B6) and the part is requested again; the run does not stop with `GIT`.
- **E9** Every provider but one is disabled → the router works with that provider alone; with none enabled → `INVALID` ("no enabled provider in the pool").

## 6. Never
- Never read, accept, log or store an API key or token, and never call a model API except through the WO-1.0-10 clients.
- Never send a part to a model whose `risk_tiers` lack the order's tier.
- Never write anywhere but `.relay/` and, in the worktree, the order's outputs and record files; never touch read-only tests.
- Never `git add -A` or `git add .`, amend, force-push, push any branch but `wo/<WO>`, or change the main checkout's working tree or branch.
- Never sleep for real in tests: the clock and sleeper are parameters.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the WO-1.0-02 or WO-1.0-10 interfaces lack something B1 to B23 need, or if `stepper.py` or `relay.py` cannot stay within 300 lines (propose a split, with the new files to add to `outputs` and `steps`).

## 8. Must-catch behaviours
1. End to end with the stub server, every request holds only allowed files, and no key appears in any request, log or written file.
2. A T1 order never goes to a model whose `risk_tiers` lack T1, and a pinned model that may not serve the order's tier gives exit 2.
3. A daily-quota rejection switches the part to the next eligible model without using an attempt; exit 11 comes only when every eligible model is exhausted, and the next run resumes at the same part without re-sending accepted ones.
4. A model with at least 8 recorded parts and a first-pass rate 25 points below the best is chosen after all others.
5. A credential error on one provider moves the run to the other providers and prints the ACCESS line; with no provider left, exit 7.
6. QUESTIONS → exit 4, nothing imported, earlier parts kept.
7. A read-only test changed during a test run → exit 9, and nothing is committed.
8. The relay's commits contain only the part's files, earlier files changed under B12 and the order's record files, and only on `wo/<WO>`.
9. A cut-off two-file part is split into one request per file; a cut-off one-file part ends with exit 5.
10. A rerun after a failed attempt discards that attempt's files and continues, instead of exiting 14; a step log naming another WP branch gives exit 2 before any merge or record.
11. The ledger fragment holds the token counts from the replies' usage figures and the model and provider of every part.
12. `--models` reports a pool model the provider does not list, and exits 2.
13. A request larger than one model's per-minute token limit is never retried on that model: it goes to a model that fits, without using an attempt, and exits 13 only when no eligible model fits.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B23 and E1 to E9 are implemented; point at each.
- **D3** Tests use only the local stub server, scratch repositories with a local bare `origin`, and a simulated clock; none reaches the internet or waits in real time.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_11.py` passes unmodified, and so does every other test in `tests/aqis_lab/outsourcing`.
- **D5** No placeholder, swallowed error or key handling anywhere.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md`, every file in `context` and every file in `interfaces`. Then branch `wo/WO-1.0-11` from the WP-1.0 branch after WO-1.0-02 is merged into it, and work one step at a time in the order of `steps`. Run the verify command until it passes, and open a pull request titled `WO-1.0-11: relay orchestration` with the DOD table.
