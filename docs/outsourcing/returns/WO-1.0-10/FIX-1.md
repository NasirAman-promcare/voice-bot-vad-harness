# FIX 1 for WO-1.0-10

Your previous answer (PR #12, merged into `claude/wp-1-0-operating-model-v2` at `ad5f769`) passes the order's acceptance tests. Claude's review found defects that those tests did not catch. Fix the root cause in each case; do not special-case test inputs. The public API of section 3 and B14 of `docs/outsourcing/orders/WO-1.0-10.md` stays exactly as it is, because WO-1.0-02 and WO-1.0-11 build on it.

## Failed checks
All in `tests/aqis_lab/outsourcing/test_fix_wo_1_0_10_01.py`, a read-only test written by Claude. Before your fix: `22 failed, 2 passed`.

1. `test_FR_1_0_14_fix01_parallel_processes_lose_no_update`: four processes each record 150 requests on one state file; afterwards `remaining_today` must be `100000 - 600`.
   ```text
   AssertionError: assert 99785 == (100000 - (4 * 150))
   ```
   Cause: `Governor._load_state` and `_save_state` each take the lock separately, so another process's write between them is lost. B6 and B23 require every read-modify-write, including `wait_for_slot`'s check-and-take of a slot, to happen under one lock held from the read to the atomic replace.
2. `test_FR_1_0_14_fix01_tokens_on_a_months_last_day_count_for_that_month`
   ```text
   AssertionError: assert datetime.datetime(2026, 12, 1, 0, 0, tzinfo=datetime.timezone.utc) is None
   ```
   Cause: day and month keys come from the date of the next reset, so on 31 October the month key is already November. Key days and months by the current date in the provider's `day_reset` zone (B5, E2).
3. `test_FR_1_0_14_fix01_per_day_quota_value_is_learned`
   ```text
   AssertionError: assert 20 == 10
   ```
   Cause: B12 learns a QuotaFailure `quotaValue` for the per-minute and the per-day quota. Only per-minute values are learned now.
4. `test_FR_1_0_14_fix01_daily_rejection_uses_the_reset_the_response_gives`
   ```text
   AssertionError: assert datetime.datetime(2026, 10, 11, 0, 0, tzinfo=datetime.timezone.utc) == (datetime.datetime(2026, 10, 10, 12, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=7200))
   ```
   Cause: B8 says a daily rejection is exhausted "until the next reset … with the reset from the response if given, else from `next_reset`". `Retry-After` (and `RetryInfo`) on a DAILY verdict give that reset; the client and governor ignore it.
5. `test_FR_1_0_14_fix01_failed_model_listing_raises` (6 cases)
   ```text
   Failed: DID NOT RAISE any of (ApiError, ModelError, CredentialError, ServiceBusy, TransportError)
   ```
   Cause: both clients' `list_models` end on `except Exception: break` or on a non-200 `break` and return a partial or empty list. The relay's `--models` would then report every model "missing" instead of the failure. Classify a failed listing with `quota.classify` and raise the same named exceptions as `generate` (a 200 body that is not JSON → `ApiError`).
6. `test_FR_1_0_14_fix01_unparseable_reply_raises_api_error` (2 cases)
   ```text
   json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
   ```
   Cause: a 200 reply whose body is not JSON must raise `ApiError` ("unexpected API response"), never a raw `JSONDecodeError`.
7. `test_FR_1_0_14_fix01_no_swallowed_exceptions` (5 of 6 modules)
   ```text
   limits.py [186, 196]; quota.py [44, 69, 51, …]; governor.py [75]; gemini_client.py [71, 187]; openai_client.py [182, 66, 73]
   ```
   Cause: handlers whose body is only `pass`, `continue` or `break`, and `except Exception` without a re-raise (Foundation standard 3).
   - A parse attempt that may fail returns an explicit `None` from a small helper.
   - `count_tokens` may still fall back to the estimate (B3), but it catches only the errors a failed call produces (`urllib.error.URLError`, `OSError`, `ValueError`, and the client's own `ApiError`), never `Exception`.
   - The zone fallback of B9 catches only `zoneinfo.ZoneInfoNotFoundError`.
   - A corrupt state file (E3) catches only `OSError` and `ValueError`.
8. `test_FR_1_0_14_fix01_functions_at_most_40_lines_and_no_semicolons` (5 of 6 modules)
   ```text
   limits.py load_pool …; quota.py classify …; governor.py delay_for …, semicolons; gemini_client.py generate …; openai_client.py generate …
   ```
   Cause: Foundation standard 10 says functions are at most 40 lines. Statements packed with `;` and dataclass fields on one line make the code unreadable for audit.
   - Split functions by responsibility.
   - Put one statement per line.
   - Put one dataclass field per line.
   - The retry loop shared by both clients may move into one helper in an existing module of this order, such as `quota.py` or a function in `governor.py`. No new file.

## Files you may change
- `tools/outsourcing/chat.py`
- `tools/outsourcing/limits.py`
- `tools/outsourcing/quota.py`
- `tools/outsourcing/governor.py`
- `tools/outsourcing/gemini_client.py`
- `tools/outsourcing/openai_client.py`
- `tests/aqis_lab/outsourcing/stub_model_server.py`
- `tests/aqis_lab/outsourcing/test_limits.py`
- `tests/aqis_lab/outsourcing/test_quota.py`
- `tests/aqis_lab/outsourcing/test_governor.py`
- `tests/aqis_lab/outsourcing/test_gemini_client.py`
- `tests/aqis_lab/outsourcing/test_openai_client.py`

Add unit tests for every behaviour you change, with the stub server and a simulated clock. The current unit tests are thin: 17 in total, and 1 per client. D3 of the order asks for tests that cover B1 to B14 and E1 to E6; in particular, cover every classification row of B7 and every reaction of B8.

## Rules
- Return only the files you change, each complete, followed by the DOD table for the items affected.
- Do not touch any other file; in particular, do not touch `.gitignore` (your previous branch changed it outside the order's outputs, and the change was left out).
- Never touch the read-only tests: `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py` and `tests/aqis_lab/outsourcing/test_fix_wo_1_0_10_01.py`.
- If a failure shows the work order itself is wrong, write a QUESTIONS section into the pull request description instead of guessing.

## Verify
```text
.venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_limits.py tests/aqis_lab/outsourcing/test_quota.py tests/aqis_lab/outsourcing/test_governor.py tests/aqis_lab/outsourcing/test_gemini_client.py tests/aqis_lab/outsourcing/test_openai_client.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py tests/aqis_lab/outsourcing/test_fix_wo_1_0_10_01.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py -q --tb=short
```
Every test must pass.

## Channel notes (Jules)
1. Read `docs/process/outsourcing/FOUNDATION.md`, `docs/outsourcing/orders/WO-1.0-10.md` and this file.
2. Work on branch `wo/WO-1.0-10-fix-1` from `claude/wp-1-0-operating-model-v2`.
3. Run the verify command until it passes.
4. Open a pull request against `claude/wp-1-0-operating-model-v2` titled `WO-1.0-10 FIX 1: governor atomicity, resets, listings, shape`. Its description is the DOD table for items 1 to 8 above.
