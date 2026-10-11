# DEC-1.0-06 — Every sent request counts toward a model's day, as the providers count it
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-11
Spec basis: FR-1.0-14 (the rate governor "exactly as WO-1.0-10 specifies"). WO-1.0-10 section 2 says the governor "paces each model and each provider under its limits before anything is rejected"; its B5 counted a request toward the day only "after a success".

Question: The owner's Gemini dashboard on 2026-10-11 showed gemini-3.6-flash at 22/20, 3.7 at 21/20 and 3.8 at 19/20 requests per day (owner's BLK-1.0-06 answer). `.relay/governor.json` held no daily count for any of them, because no Gemini request had succeeded. Google counts the requests it rejects as overloaded too. With B5 as written, `relay --status` printed `Count today: 0/20`, and pacing kept sending requests the provider had already counted. When does a request count toward the day?

Options:
1. When it is sent: `wait_for_slot` adds one to the model's and the provider's day count; `record_result` keeps the token accounting.
2. Keep "after a success". The relay's own counts and pacing then stay out of step with the provider whenever requests are rejected.

Choice: 1. WO-1.0-10 B5 is amended. Tests first in `tests/aqis_lab/outsourcing/test_relay_run_fixes_wo_1_0_10.py`, for both API shapes: two rejections and one success count as 3, and six rejections ending in ServiceBusy count as 6. Before the fix: `4 failed` (`assert 19 == 17`). After it: all 364 outsourcing tests pass. Break recipe `MC-WO-1.0-10-12-count-sent-requests.patch` is caught (`4 failed`).

Why: section 2's intent is pacing under the provider's limits, and the provider's limit counts sent requests (the dashboard figures above). Every existing test sends one start and one result per slot, so its counts are unchanged.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no (the limits are unchanged; the count now matches how they are applied)
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: move the two daily-count lines from `wait_for_slot` back into `record_result`.
