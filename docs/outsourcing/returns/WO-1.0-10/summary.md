# WO-1.0-10 Summary

- **WO**: WO-1.0-10, model clients, rate governor and quota classification
- **Channel**: jules. PR #12 was on branch `wo/WO-1.0-10-1145507150263816511`, which Jules named with a suffix. Model and token counts are not reported by the Jules channel.
- **Result so far**: delivered and merged as `ad5f769`, with FIX-1 open.

## Claude's review (WO_REVIEW_CHECKLIST, 2026-10-10)
- **Scope.** The branch also changed `.gitignore`, adding `.venv/` and `.relay/`. That file is outside the order's outputs and is GUARDED, so the hunk was left out of the merge. FR-1.0-10's `.relay/` line was added separately under `docs/approvals/WP-1.0.md`.
- **Tests.** All 31 acceptance tests pass, together with 17 unit tests.
- **Defects the acceptance tests did not catch:**
  - The governor's read-modify-write is not atomic across processes: four processes recorded 600 requests and the state kept 215.
  - On a month's last day, its tokens are counted under the next month.
  - Per-day QuotaFailure values are not learned.
  - A daily rejection ignores the reset the response gives.
  - `list_models` swallows errors and returns partial lists.
  - A 200 reply that is not JSON escapes as `JSONDecodeError`.
  - Exceptions are swallowed in 5 modules.
  - Functions run over 40 lines, and statements are packed with semicolons.
- **Outcome: FIX ORDER.** `docs/outsourcing/returns/WO-1.0-10/FIX-1.md` goes to Jules, with read-only tests in `tests/aqis_lab/outsourcing/test_fix_wo_1_0_10_01.py`; before the fix they gave `22 failed, 2 passed`.

## FIX-1 (PR #14, branch `wo/WO-1.0-10-fix-1-12729969097301121945`, merged as `7f2897b`)
- **Scope and tests.** The scope check is clean. The read-only tests are unchanged. 139 tests passed on the branch: the FIX-1 tests (24), the WO-1.0-10 acceptance tests (31), the WO-1.0-01 acceptance tests (63) and the unit tests.
- **Concurrency.** The parallel-process test now records all 600 requests. `wait_for_slot` checks and takes a slot under one lock and sleeps outside it.
- **Still open, as FIX-2 items, sent after WO-1.0-11 so as not to change interfaces it builds on:**
  - `governor.py` is 531 lines, over the Foundation's hard limit of 400. Splitting it needs a new output file.
  - Only 4 unit tests were added, although FIX-1 asked for coverage of every B7 classification row and every B8 reaction.
  - `wait_for_provider` sleeps while it holds the state lock.
