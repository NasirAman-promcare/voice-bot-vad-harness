# DEC-1.0-05 — A fix turn after a bundle error or refused import says what went wrong and restates RETURN_FORMAT
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-10
Spec basis: FR-1.0-02 (the relay "exactly as WO-1.0-02 … and WO-1.0-11 specify"). WO-1.0-02 B11 gives the fix reason for `MAX_TOKENS` and for "`SAFETY`, `RECITATION` or an empty answer", but none for the bundle errors and refused imports that WO-1.0-11's stepper also sends as `stop_reason`. RETURN_FORMAT.md: "Nothing else: no greetings, no summaries, no explanations outside these blocks"; a fence is allowed only right after a FILE marker.

Question: On the WO-1.0-04 relay run (2026-10-10), codestral-2508 wrapped its whole reply in a ```` ```text ```` fence three times. `parse_bundle` refused each reply, correctly (WO-1.0-01 B5): `Bundle error: Non-blank text outside block: '```text'` (from `.relay/logs/WO-1.0-04/step-1/attempt-{1,2,3}/response.raw`). The fix turn said "Your answer was blocked or empty (Bundle error: …)", which is false and never told the model the format rule. What should the fix reason say for these cases?

Options:
1. Bundle errors and refused imports get their own reason. It names the error and restates RETURN_FORMAT's rules: start with `=== MANIFEST ===`; nothing before, between or after the blocks; a fence only inside a FILE block. The B11 wording stays for MAX_TOKENS, SAFETY, RECITATION and empty answers.
2. Let the parser tolerate one fence around the whole reply. That changes WO-1.0-01 B5, a must-catch parsing rule, so it would be a spec deviation.
3. Leave it. A fallback model that fences its answer then always uses up the step's attempts.

Choice: 1. Test first: `tests/aqis_lab/outsourcing/test_relay_run_fixes_wo_1_0_02.py`. It had 2 failures for the right reason before the fix; after it, all 347 outsourcing tests pass. The change is limited to `fixorder._format_stop_reason`.

Why: the wording only restates rules that RETURN_FORMAT.md already gives. B11's wording keeps applying to every reason it names. The parser stays as strict as WO-1.0-01 B5 requires.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: remove the `elif` branch in `_format_stop_reason`.
