---
id: WO-1.0-10
wp: WP-1.0
title: Model clients, rate governor and quota classification for the model pool
model: default
channel: jules                     # bootstrap: sent together with WO-1.0-01 (independent of it), before WO-1.0-02
attempt_budget: 3
risk_tier: T1
max_output_tokens: 40000
context:
  - docs/process/CHANGE_CONTROL.md
  - docs/process/outsourcing/README.md
  - config/aqis_lab/model_pool.json
outputs:
  - tools/outsourcing/chat.py
  - tools/outsourcing/limits.py
  - tools/outsourcing/quota.py
  - tools/outsourcing/governor.py
  - tools/outsourcing/governor_state.py
  - tools/outsourcing/gemini_client.py
  - tools/outsourcing/openai_client.py
  - tests/aqis_lab/outsourcing/stub_model_server.py
  - tests/aqis_lab/outsourcing/test_limits.py
  - tests/aqis_lab/outsourcing/test_quota.py
  - tests/aqis_lab/outsourcing/test_governor.py
  - tests/aqis_lab/outsourcing/test_gemini_client.py
  - tests/aqis_lab/outsourcing/test_openai_client.py
steps:
  - tools/outsourcing/chat.py, tools/outsourcing/limits.py, tests/aqis_lab/outsourcing/test_limits.py
  - tools/outsourcing/quota.py, tests/aqis_lab/outsourcing/test_quota.py
  - tools/outsourcing/governor.py, tools/outsourcing/governor_state.py, tests/aqis_lab/outsourcing/test_governor.py
  - tests/aqis_lab/outsourcing/stub_model_server.py
  - tools/outsourcing/gemini_client.py, tests/aqis_lab/outsourcing/test_gemini_client.py
  - tools/outsourcing/openai_client.py, tests/aqis_lab/outsourcing/test_openai_client.py
read_only_tests:
  - tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_limits.py tests/aqis_lab/outsourcing/test_quota.py tests/aqis_lab/outsourcing/test_governor.py tests/aqis_lab/outsourcing/test_gemini_client.py tests/aqis_lab/outsourcing/test_openai_client.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py -q --tb=short
---

# WO-1.0-10 — Model clients, rate governor and quota classification for the model pool

## 1. Context
The lab sends work-order steps to a **pool of models on free tiers**: several Gemini models through Google's own API, and models of other providers (Mistral now; NVIDIA or OpenRouter later) through their OpenAI-compatible chat-completions APIs. Each model has its own quota, and some providers add limits for the whole account (Mistral: requests per second, input tokens per minute, tokens per month; OpenRouter: free requests per day). The owner keeps the pool in `config/aqis_lab/model_pool.json` (in your context): providers, models, ranks, the risk tiers each model may serve, and the limits. Up to `share` relay processes, in parallel Claude threads on different machines, may use the same accounts at once. Rejections come back as HTTP 429 (Gemini: `RESOURCE_EXHAUSTED` with a `google.rpc.QuotaFailure` naming a `quotaId` and `quotaValue`, often a `google.rpc.RetryInfo`; OpenAI-compatible providers: an error message, a `Retry-After` header and often `x-ratelimit-*` headers). The session's network proxy attaches each provider's key to requests for that provider's host; this code never handles a key. The relay (WO-1.0-02 and WO-1.0-11) and its router call these modules; no Claude tokens are spent while they wait.

## 2. Your job
Provider-neutral request and reply records; a loader for the pool; a classifier for every kind of rejection from either API shape; a governor that paces each model and each provider under its limits before anything is rejected, learns lower limits from rejections and counts each day's and month's use; and two clients, one per API shape, with the same public interface.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/outsourcing/chat.py` | Provider-neutral records and the exceptions every client raises | frozen dataclasses `Turn` (role `user` or `assistant`, text), `ChatRequest` (system text, turns, max output tokens), `TokenCount` (value, estimated flag), `Reply` (text, finish: `STOP`, `MAX_TOKENS`, `SAFETY`, `RECITATION` or `OTHER`, block reason or none, prompt and output tokens, whether they are estimates, seconds waited for pacing, model, model version, raw JSON); exceptions `DailyQuotaExhausted` (model, provider, period `day` or `month`, server quota value, reset in UTC, provider time and Asia/Karachi), `ServiceBusy`, `StepTooLarge`, `CredentialError`, `ModelError`, `ApiError`, `TransportError` | 150 |
| `tools/outsourcing/limits.py` | Load and validate the pool; effective limits; day resets | `load_pool(path) -> Pool`; frozen `ProviderSpec` (name and every provider key of B1) and `ModelSpec` (name, its `ProviderSpec`, and every model key of B1); `Pool.providers()`, `Pool.models()`; `Pool.model(name) -> ModelSpec` (raises for unknown names or disabled providers); `Pool.candidates(risk_tier) -> list[ModelSpec]` (enabled providers, tier allowed, by rank); `effective(pool, model, adaptive_factor, server_limits) -> EffectiveLimits` (including the input-token ceiling of B3); `next_reset(pool, provider, now_utc) -> ResetTimes`; raises `LimitsError` | 250 |
| `tools/outsourcing/quota.py` | Classify an HTTP error response of either API shape | `classify(api, status, headers, body_text) -> QuotaVerdict` (kind, retry delay seconds or none, quota scope `model` or `provider`, server limit value or none, reset time or none, message) | 250 |
| `tools/outsourcing/governor.py` | Sliding-window pacing per model and per provider, persisted state, adaptive slowdown, learned limits, daily and monthly accounting | `Governor(pool, state_path, clock, sleeper, random)`; `delay_for(model, input_tokens) -> seconds` (no sleep); `wait_for_slot(model, input_tokens) -> seconds waited`; `wait_for_provider(provider) -> seconds waited` (spacing only, for listings); `record_result(model, prompt_tokens, output_tokens)`; `record_rejection(model, verdict)`; `remaining_today(model) -> int or None`; `exhausted_until(model) -> UTC time or None`; `report() -> GovernorReport` | 300 |
| `tools/outsourcing/governor_state.py` | The governor's records, state file and lock (split from `governor.py` in FIX-2 to keep it within 400 lines) | `FileLock`, the stats and report records, `load_stats`, `save_stats` | 200 |
| `tools/outsourcing/gemini_client.py` | Gemini `generateContent`, `countTokens` and model listing over HTTPS with the standard library, paced by the governor | `GeminiClient(spec, governor, timeout, base_url=None)` (`spec` a `ModelSpec`; `base_url` overrides the provider's); `count_tokens(request) -> TokenCount`; `generate(request) -> Reply`; `list_models() -> list[str]` | 300 |
| `tools/outsourcing/openai_client.py` | OpenAI-compatible `chat/completions` and model listing, paced by the governor | `OpenAIClient(spec, governor, timeout, base_url=None)`; `count_tokens(request) -> TokenCount`; `generate(request) -> Reply`; `list_models() -> list[str]` | 300 |
| `tests/aqis_lab/outsourcing/stub_model_server.py` | Local stand-in for both API shapes: replays a script of responses (successes, 429s with QuotaFailure/RetryInfo or with `Retry-After` and `x-ratelimit-*` headers, 400 `API_KEY_INVALID`, 402, 404, 500, 503, length or MAX_TOKENS finishes, non-JSON bodies, model lists) and records each request (path, headers, body) | a context manager yielding its base URL and the recorded requests; the script format documented in its module header | 250 |
| `tests/aqis_lab/outsourcing/test_*.py` | Unit tests per module, with a simulated clock and sleeper (no real waiting); the stub is imported as `from tests.aqis_lab.outsourcing import stub_model_server`, so the tests still import once WO-1.0-01 adds the package's `__init__.py` | | 300 each |

## 4. Required behaviour
- **B1** Pool file: JSON with `notes` (ignored), `share` (integer at least 1), `safety` (0.5 to 1.0), `providers` and `models`.
  - **B1 amendment (2026-10-11, owner's BLK-1.0-12 answer, DEC-1.0-08).** A model may also carry `reasoning_effort` (non-empty string), `temperature` (0 to 2), `top_p` (above 0, at most 1) and `timeout_seconds` (positive integer). The loader refuses any other value, naming the field, and repeated ranks (FIX-B1-ranks).
  - A provider has `api` (`gemini` or `openai`), `base_url`, `enabled`, `tier` (`free` or `paid`), `verified_on` (ISO date or empty), `day_reset` (an IANA zone name), `data_use` (text), and optionally `rpm`, `rps`, `tpm_input`, `rpd`, `tokens_per_month` (account-wide limits).
  - A model, keyed by its API name, has `provider`, `rank` (unique positive integer), `risk_tiers` (a non-empty subset of T1, T2, T3), `max_input_tokens`, `max_output_tokens`, and optionally `rpm`, `tpm_input`, `rpd`.
  - Unknown or missing keys, wrong types, a duplicate rank or an unknown provider raise `LimitsError` naming the key. A provider with an empty `verified_on` is reported as unverified.
- **B2** Effective limits for a model: each per-minute limit, of the model and of its provider, is `floor(limit × safety × adaptive_factor ÷ share)`, at least 1, where `limit` is the lower of the configured and the server-learned value (B12). A provider's `rps` becomes a minimum spacing of `share ÷ (rps × safety)` seconds between request starts to that provider. A model's `rpm` gives a spacing of `60 ÷ effective rpm` seconds. Daily and monthly limits are not divided by `share`: the local counts are estimates and the server's rejection is the authority.
- **B3** Measuring: `GeminiClient.count_tokens` posts `{"generateContentRequest": {"model": "models/<model>", …body}}` to `:countTokens` (free, own quota), so the system instruction is counted. `OpenAIClient.count_tokens` estimates `ceil(characters ÷ 3.5)`, marked as an estimate; so does the Gemini client when its call fails. Before every `generate`, a request whose input exceeds the model's `max_input_tokens` or `floor(tpm_input × safety)` of the model or its provider (an allowance no waiting can make room for) raises `StepTooLarge` with the figure and the limits, without sending.
- **B4** `wait_for_slot` sleeps until the earliest moment when one more request fits all of these, for the model and for its provider: requests started in the last 60 seconds fewer than the effective RPM; their input tokens plus this request's within the effective TPM, or no request in the window at all; the spacing since the last start; any cooldown ended. It returns the seconds waited.
- **B5** After a success, the window records the reply's prompt tokens in place of the measured figure; the daily counts of the model and of its provider increase by one, keyed by the date in the provider's `day_reset` zone; a provider with `tokens_per_month` adds the prompt and output tokens to the current month's total.
  - **B5 amendment (2026-10-11, DEC-1.0-06).** The daily counts increase when a request is sent (`wait_for_slot`), not after a success, because providers count rejected requests too. The window's token figure and the monthly tokens still update after a success.
- **B6** State persists in `.relay/governor.json`: per model and per provider, the last 60 seconds of starts with their tokens, daily counts, monthly tokens, the adaptive factor, cooldowns, exhausted-until times and server-learned limits with the date seen. `exhausted_until` gives a time when the model or its provider was marked exhausted, when the day's count of the model or provider has reached its effective daily limit, or when the provider's month total has reached `tokens_per_month`; otherwise none. `delay_for` gives the wait `wait_for_slot` would need now, without sleeping. It is written atomically under a file lock, so several processes on one machine see each other.
- **B7** Classification by `quota.classify`, in this order:
  - Gemini shape: 429 with a QuotaFailure `quotaValue` of `0` → `NO_QUOTA`; `quotaId` containing `PerDay` → `DAILY`; `PerMinute` with `Token` → `MINUTE_TOKENS`; `PerMinute` with `Request` → `MINUTE_REQUESTS`; any other 429 → `OVERLOADED`; 400 whose details carry the reason `API_KEY_INVALID` → `CREDENTIAL`.
  - OpenAI shape: 429 whose message or error code names a month or monthly → `MONTHLY` (scope `provider`); one that names a day, daily or a used-up quota, or whose `Retry-After` exceeds 3,600 seconds → `DAILY` (scope `provider` when the message names the account or the free-request allowance, else `model`); 429 whose message names tokens → `MINUTE_TOKENS`; other 429 → `MINUTE_REQUESTS`; 402 → `NO_QUOTA`.
  - Both shapes: 400, 413 or 422 that mentions tokens, size, length or context → `TOO_LARGE`; 401 or 403 → `CREDENTIAL`; 404 → `MODEL`; 500 → `SERVER_ERROR`; 502, 503, 504 or 529, or status `UNAVAILABLE` → `OVERLOADED`; anything unparseable → `OTHER`, with the raw status.
  - The retry delay comes from RetryInfo, from `Retry-After` (seconds or an HTTP date), or from `x-ratelimit-reset-requests` / `x-ratelimit-reset-tokens` (seconds or durations such as `1m30s`), whichever is present.
- **B8** Reactions, none of which count as relay attempts:
  - `MINUTE_TOKENS` for a request whose input alone exceeds the model's or the provider's per-minute token limit (configured or server-learned under B12): raise `StepTooLarge` at once, without retrying, because no wait can make room.
  - `MINUTE_*` otherwise: cool down for the longer of the retry delay (default 30 seconds) and the time until the oldest windowed start leaves the window, plus 1 to 5 seconds of jitter; multiply the model's adaptive factor by 0.75 (at least 0.25); retry. After 6 such retries for one request, raise `ServiceBusy`. After 10 successes in a row, multiply the factor by 1.1, up to 1.0.
  - `OVERLOADED`: exponential backoff with full jitter (base 5 seconds, factor 3, cap 120 seconds), at most 5 retries, then `ServiceBusy`. `SERVER_ERROR`: at most 2 retries with the same backoff, then `ServiceBusy`.
  - `DAILY`: mark the model (or, for scope `provider`, every model of that provider) exhausted until the next reset, and raise `DailyQuotaExhausted` (period `day`) at once, without retrying, with the reset from the response if given, else from `next_reset`. `MONTHLY`: the same for every model of the provider until the first day of the next month in the provider's zone (period `month`).
  - `NO_QUOTA`: raise `ModelError` at once: "the <tier> tier gives <model> no quota; remove it from the pool or enable billing".
  - `TOO_LARGE`: `StepTooLarge`. `CREDENTIAL`: `CredentialError` naming the provider and its host. `MODEL`: `ModelError`. `OTHER`: `ApiError` with the status and the provider's message, without retrying.
  - Network errors: at most 3 retries with backoff, then `TransportError`.
- **B9** `next_reset` uses `zoneinfo` with the provider's `day_reset` zone and also gives UTC and Asia/Karachi. If zone data is unavailable: America/Los_Angeles follows the United States daylight-saving rule (UTC−7 from the second Sunday of March 02:00 to the first Sunday of November 02:00 local, otherwise UTC−8), Asia/Karachi is UTC+5, UTC is UTC; any other zone raises `LimitsError`. The report states the fallback.
- **B10** The report gives, per model: requests sent, retries by kind, seconds waited, prompt and output tokens, the adaptive factor, effective and server-learned limits, requests counted today with the daily limit, cooldown end, exhausted until; per provider: the same account-wide figures and monthly tokens; and which providers are unverified.
- **B11** Clients send no key in any header, URL or body; the proxy adds it. They write nothing to stdout and leave saving raw responses to the relay.
  - **B11 amendment (2026-10-11, DEC-1.0-08).** The OpenAI-shape request carries `reasoning_effort`, `temperature` and `top_p` exactly when the model's pool entry sets them; otherwise none of them (must-catch 11). Both clients use a socket timeout of at least the model's `timeout_seconds`.
- **B12** Learning from rejections and headers: a server-stated limit lower than the configured one replaces it from then on, persisted with the date seen, and the report says "config says X, server says Y". Sources: a Gemini QuotaFailure `quotaValue` for the model's per-minute or per-day quota; the `x-ratelimit-limit-requests` and `x-ratelimit-limit-tokens` headers of OpenAI-shaped replies, applied to the model's per-minute limits, or to the provider's when the provider has account-wide per-minute limits and the model has none. A server value never raises a configured limit.
- **B13** Wire formats:
  - Gemini: `POST <base_url>/v1beta/models/<model>:generateContent` with `systemInstruction`, `contents` (`assistant` turns sent as role `model`) and `generationConfig.maxOutputTokens` = the lower of the request's and the model's `max_output_tokens`; the reply's text is its non-thought parts joined; `finishReason` and `usageMetadata` map onto `Reply`. A 200 reply with no candidates, or with `promptFeedback.blockReason`, is a `Reply` with empty text, finish `SAFETY` (with the block reason) or `OTHER`, never an exception.
  - OpenAI shape: `POST <base_url>/chat/completions` with `model`, `messages` (the system text as the first `system` message) and `max_tokens` = the same lower value; `finish_reason` `stop` → `STOP`, `length` → `MAX_TOKENS`, `content_filter` → `SAFETY`; `usage.prompt_tokens` and `usage.completion_tokens` map onto `Reply`. A 200 reply with no choices is a `Reply` with empty text and finish `OTHER`.
  - Neither sets temperature: providers' defaults apply, and Google recommends the default for Gemini 3 models.
  - `list_models`: Gemini `GET <base_url>/v1beta/models` (all pages) → model names without the `models/` prefix; OpenAI shape `GET <base_url>/models` → ids. Listing waits with `wait_for_provider` and never counts toward daily use.

- **B14** Interface details the acceptance tests rely on (added by Claude with the acceptance test, 2026-10-10):
  - **Simulated time.** `Governor(pool, state_path, clock, sleeper, random)`:
    - `clock()` returns the current time as POSIX seconds (a float, UTC);
    - `sleeper(seconds)` waits that long; tests pass a simulated sleeper that advances the clock;
    - `random` has the `random.Random` interface, and every jitter is a draw from it.
  - **One source of time.** Clients do every wait (pacing, cooldowns, backoff) through their governor's sleeper, and take every time they need from its clock, resets included.
  - **Fresh start.** An absent state file starts with adaptive factor 1.0. A corrupt one starts with 0.75 (E3).
  - **Records.**
    - `ChatRequest` has fields `system`, `turns` (a tuple of `Turn`) and `max_output_tokens`.
    - `Turn` has fields `role` and `text`.
    - `Reply` has at least `text`, `finish` (one of the five strings in section 3), `prompt_tokens` and `output_tokens`.
    - `DailyQuotaExhausted` has the attributes `model`, `provider`, `period` (`"day"` or `"month"`), `quota_value` (int or None), and `reset_utc`, `reset_provider` and `reset_karachi`. The three resets are timezone-aware datetimes for the same instant, in UTC, in the provider's `day_reset` zone and in Asia/Karachi.
  - **Report.** `Governor.report().models` maps each model name to a record with at least `adaptive_factor`, `requests`, `retries` (a mapping from kind to count) and `seconds_waited`. `.providers` maps each provider name to its record.
  - **Exceptions.** `LimitsError` lives in `limits`. Every other exception of section 3 lives in `chat`.
  - **Clients.**
    - They take `base_url` without a trailing slash, for example `http://127.0.0.1:<port>` in tests.
    - They use the standard library's HTTP client with its default proxy handling, so `NO_PROXY` applies.
    - A start is recorded by `wait_for_slot`, and `record_result` completes it (B5).

## 5. Edge cases you must handle
- **E1** Retry delays given as `"37s"`, `"1.5s"`, an HTTP date, `1m30s`, or missing.
- **E2** A state file from an earlier day in a provider's zone → that provider's daily counts are dropped; from an earlier month → monthly tokens are dropped; learned limits are kept.
- **E3** A corrupt or unreadable state file → start fresh with adaptive factor 0.75 and note it in the report.
- **E4** A model that is not in the pool, or belongs to a disabled provider → `LimitsError` naming it and, for the second, the provider.
- **E5** A 429 whose body is not JSON → `OVERLOADED` (Gemini) or `MINUTE_REQUESTS` with the `Retry-After` delay if present (OpenAI shape).
- **E6** An OpenAI-shaped reply with no `usage` → prompt tokens from the measured estimate, output tokens `ceil(characters ÷ 3.5)`, both marked as estimates in the reply.

## 6. Never
- Never send a request that B3 says cannot fit, and never retry a daily or no-quota rejection.
- Never let a server value raise a configured limit.
- Never read, accept, log or store a key; never print request or response bodies.
- Never sleep for real in tests: the clock, sleeper and random source are parameters.
- Never create `tools/outsourcing/__init__.py` or `tests/aqis_lab/outsourcing/__init__.py`: WO-1.0-01 owns them.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the pool file in your context does not fit B1, or if a behaviour here contradicts the outsourcing README.

## 8. Must-catch behaviours
1. In any 60-second window, requests never exceed the effective RPM of the model or of its provider, and a provider's `rps` spacing always holds (simulated clock).
2. In any 60-second window, input tokens never exceed the effective TPM of the model or its provider, except one request alone in an empty window.
3. A daily rejection marks the model (or, with provider scope, the provider's models) exhausted, a monthly one the provider's models until the next month, and either stops at once without a retry and gives the reset in the provider's zone, UTC and Asia/Karachi; a model whose day's count has reached its limit is exhausted without being asked, also in a second process and after a restart.
4. A per-minute rejection waits at least the retry delay and lowers the model's adaptive factor; 6 of them for one request raise `ServiceBusy`.
5. Overload backs off exponentially with jitter and raises `ServiceBusy` after 5 retries.
6. A request over a model's input limit or a whole per-minute token allowance raises `StepTooLarge` without being sent; a per-minute token rejection for a request larger than the server-stated limit raises `StepTooLarge` at once, without a retry.
7. After a process restart, starts from the last 60 seconds and the day's and month's counts still apply.
8. No key appears in any request of either client.
9. A server-stated lower limit (QuotaFailure or `x-ratelimit-limit-*`) replaces the configured one; a higher one never does; a quota value of 0 or HTTP 402 raises `ModelError` without a retry.
10. A 400 with reason `API_KEY_INVALID` and an HTTP 401 raise `CredentialError`; an unclassifiable error raises `ApiError`; neither is retried.
11. Both clients send no temperature and cap the output tokens at the model's `max_output_tokens`.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B14 and E1 to E6 are implemented; point at each.
- **D3** Tests use the stub server and a simulated clock; none waits in real time or reaches the internet.
- **D4** `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py` passes unmodified.
- **D5** No placeholder or swallowed error.

## 10. Channel notes
Jules: first read `docs/process/outsourcing/FOUNDATION.md` and every file in `context`. Then work on branch `wo/WO-1.0-10` from the WP-1.0 branch; this order does not need WO-1.0-01, and the two may run at the same time. Until WO-1.0-01 is merged, `tools.outsourcing` and the test folder import as namespace packages; that is expected. Work one step at a time in the order of `steps`, run the verify command until it passes, and open a pull request titled `WO-1.0-10: model clients and rate governor` with the DOD table.
