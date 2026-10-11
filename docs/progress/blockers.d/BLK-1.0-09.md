# BLK-1.0-09 — codestral-2508 cannot pass the first step of WO-1.0-03; switch to default routing (Gemini first)?
Status: RESOLVED
WP: WP-1.0
Owner capability: DECISION
Raised: 2026-10-11
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay)
Time needed: 2 minutes
Loop: none

What I need: permission to run WO-1.0-03 and WO-1.0-04 (and the later orders) with `model: default`. The router then tries the four T1 Gemini flash models first, with codestral-2508 as fallback; mistral-large-2512 stays last and is not reached.

Why: you asked for codestral-2508 as the primary model. With the fence fixes in place, its replies parse, but it cannot produce working code for the smallest step of WO-1.0-03: the header parser, `tools/index/headers.py`, and its unit tests.

What I tried (two strategies, both on codestral-2508):
- **3 attempts per step** (default). Attempt 1 failed the header check. Attempts 2 and 3 failed its own unit tests, `4 failed, 2 passed`: `parse_header` returns empty capability, contract and change-log lists. Each fix turn traded one failure for another.
- **5 attempts per step** (`--attempts 5`). Attempts 1 to 3 failed the same way. Attempts 4 and 5 were malformed bundles: `Nested block marker === FILE: tests/aqis_lab/index/__init__.py === inside FILE`, that is, a file without its END marker. Report: `EXHAUSTED`, `Parts: 0/6`, `codestral-2508: 7` requests, `EXIT 8`.
- **WO-1.0-04 on codestral-2508.** Attempt 1 failed the header check, then `PAUSED-BUSY` after 6 overloaded answers. It is running again now.

Options:
1. **Default routing from now on (recommended).** The Gemini T1 flash models go first; their quotas reset at 07:00 UTC. That gives 80 requests a day over four models, now counted correctly (DEC-1.0-06). codestral-2508 is the fallback, and mistral-large-2512 is never reached.
2. **Keep codestral-2508, with work orders cut into smaller steps.** Each step's size has to be redesigned by hand, and the steps are already small; the failing one is one module of about 200 lines.
3. **Keep codestral-2508 as it is.** From this evidence, the relay will not deliver WO-1.0-03.

Exact steps:
1. Reply with "option 1", "option 2" or "option 3".

Meanwhile: WO-1.0-04 keeps running on codestral-2508 as you asked. Its result goes into this blocker's record.

Update 2026-10-11, WO-1.0-04 on codestral-2508 (resumed). Report: `EXHAUSTED`, `Parts: 0/6`, `Requests: codestral-2508: 8 | Retries: OVERLOADED: 5`, `tests: FAIL (command failed with returncode 2)`, `EXIT 8`. Attempt 1 failed the header check; attempts 2 and 3 failed `tests` with exit 2 (collection error). The report now shows the failing check (FIX-B18-report).

Owner answer: 2026-10-11. The owner removed Mistral from the environment and the pool, and enabled NVIDIA NIM models instead; default routing applies (the orders are back on `model: default`). Follow-up: BLK-1.0-10.
