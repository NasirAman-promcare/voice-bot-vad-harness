# BLK-1.0-14 — Replies slower than 30 seconds fail unless streamed: approve a streaming wire format (WO-1.0-10 B13)
Status: OPEN
WP: WP-1.0
Owner capability: DECISION
Raised: 2026-10-12
Session: https://claude.ai/code/session_013CiaVYjshaAGNKoix51V7R
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay)
Time needed: 2 minutes
Loop: none

What I need: your approval to amend WO-1.0-10 B13 so the OpenAI-shape client asks for a streamed reply (`"stream": true, "stream_options": {"include_usage": true}`) and assembles it.

Why: FR-1.0-13 sends WO-1.0-03 to WO-1.0-09 through the relay. Every work-order step takes minutes to answer. B13 specifies a single JSON reply, and in this session any non-streamed reply slower than 30 seconds fails. FR-1.0-14 says "exactly as WO-1.0-10 specifies", so changing the wire format is your call.

What I tried (2026-10-12, NVIDIA key injected, small requests return 200):
- **WO-1.0-03 step 1, as the relay builds it** (83,398-byte body, glm-5.3-flash, `max_tokens 16384`, `reasoning_effort high`), sent with curl: `502` after 30.5 s, body `upstream request failed`.
- **A small prompt with a long answer** ("2500-word essay", no reasoning parameters): `502` after 30.5 s. Size and parameters are not the cause; the time to the first byte is.
- **The same WO-1.0-03 body with `"stream": true`**: `200`, first byte after 3.7 s, finished after 555 s.
- **Where the 502 comes from.** It carries only `Content-Type: text/plain`, `X-Content-Type-Options: nosniff`, `Content-Length` and `Connection: close`. NVIDIA's own replies carry `Nvcf-Reqid`, `Nvcf-Status` and `Date`. So an intermediary on the session's egress path produces it, not NVIDIA. The local agent proxy lists no failure for it. BLK-1.0-12's and BLK-1.0-13's rejections are consistent with the same cause. Streamed replies ran 928 s (Kimi) and 1,977 s (GLM) without being cut, so the 15-minute gateway limit from the BLK-1.0-12 answer does not apply to them.
- **Built, test first, pending your approval** (commit `57a2afe`, not yet used for any relay run):
  - The client sends the two stream fields.
  - New module `tools/outsourcing/sse.py` joins only `delta.content` (reasoning is never output). It takes the finish from the last `finish_reason` and the token counts from the usage chunk, so pacing stays exact.
  - An error event raises `ApiError`. A stream cut before its end is retried like a network error (at most 3 times, then `TransportError`).
  - A JSON reply is still parsed exactly as B13 says.
  - Results: `test_stream_wo_1_0_10.py` 7 failed before the change and 7 passed after; all 413 outsourcing tests pass. Break recipes MC-WO-1.0-10-17 and -18 are caught.

Options:
1. **Approve streaming as a B13 amendment (recommended).** It is the only route through a 30-second first-byte limit that I control. The JSON path stays, so a provider that ignores `stream` still works. I add the amendment line to WO-1.0-10 B13, write DEC-1.0-09 and run WO-1.0-03 and WO-1.0-04.
2. **Keep B13 as written.** I revert `57a2afe`. Every relay step then fails in cloud sessions, so WO-1.0-03 to WO-1.0-09 would have to go through Jules or the paste channel. That changes FR-1.0-13 and is also yours to decide.

Exact steps:
1. Reply "BLK-1.0-14: option 1" (or option 2).

Meanwhile: BLK-1.0-15 (the models' output budget) is a separate owner item. I keep the records current and prepare the WO-1.0-03 review. No relay run uses the streaming code until you answer.

Owner answer:
