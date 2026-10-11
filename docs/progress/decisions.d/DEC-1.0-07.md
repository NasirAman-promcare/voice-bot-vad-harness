# DEC-1.0-07 — The relay keeps every classified rejection with the provider's message
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-11
Spec basis: FR-1.0-14 (the governor "exactly as WO-1.0-10 specifies"), rule 00-no-compromise ("Silent failure: … returning empty results on error without raising or emitting a structured error event"), and WO-1.0-11 B17 (the summary carries the governor's report).

Question: The classifier's verdict carries the provider's message, but the governor kept only per-kind counts. On 2026-10-11 the WO-1.0-04 run on the new pool ended `PAUSED-DAILY`, `Retries: OVERLOADED: 30, DAILY: 3`. Every NVIDIA model was rejected six times. Nothing showed whether that was real overload, an unlabelled rate limit, or a refused 85,000-token request. That is the third such diagnosis in this WP stopped for lack of the message (BLK-1.0-06, the WO-1.0-03 runs). Where should the message go?

Options:
1. `Governor.record_rejection` appends one JSON line per rejection to `rejections.jsonl` next to the state file (`.relay/`, git-ignored). Each line holds UTC time, model, provider, kind, scope and message. The message is the classifier's text, lower-cased.
2. Keep counts only; each such stop then needs a separate investigation.

Choice: 1. Test first: `tests/aqis_lab/outsourcing/test_rejection_log_wo_1_0_10.py`. Before the fix: `2 failed, 1 passed` (no file). After it: all 387 outsourcing tests pass.
- The first run after the fix failed my new test's case-sensitive message check. The classifier keeps the message lower-cased, so the test now compares without case.
- Break recipe `MC-WO-1.0-10-14-rejections-recorded.patch` is caught.
- `governor.py` is 396 lines; the writer lives in `governor_state.py`.

Why: a structured record of each error event is what the no-silent-failure rule asks for, and the message is already in the verdict. Nothing is sent anywhere, and no key appears: messages come from the provider's error body, and the clients send no key (WO-1.0-10 B11).

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: remove the `append_rejection` call in `record_rejection`.
