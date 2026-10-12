# DEC-1.0-09 — The OpenAI-shape client asks for streamed replies
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-12
Spec basis: the owner's BLK-1.0-14 answer (2026-10-12, "option 1"), which approves amending WO-1.0-10 B13 so the OpenAI-shape client requests and assembles a streamed reply. FR-1.0-14 ("exactly as WO-1.0-10 specifies") now covers the amended B13.

Question: how should the client get replies longer than 30 seconds through the session's egress path? That path answers 502 `upstream request failed` to any non-streamed reply slower than 30 seconds.

Options:
1. **Stream every OpenAI-shape request; keep the JSON parser for providers that ignore `stream`.** Approved by the owner.
2. **Keep single JSON replies.** No work-order step can then pass through the relay from a cloud session.

Choice: 1.
- Code: `57a2afe` (`tools/outsourcing/sse.py`, `openai_client._build_payload`, `generate` and `_parse_openai_ok`).
- Tests: `test_stream_wo_1_0_10.py`.
- Break recipes: MC-WO-1.0-10-17 and -18.
- Records: B13 amendment in WO-1.0-10, and FIX-B13-stream in FIXES.md.

Why: it is the only route within the session's limits. Token counts still come from the provider's usage, so pacing (must-catch 13) is unchanged.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Cannot-do note: on requirements, the owner approved the B13 amendment.

Reversal: revert `57a2afe`'s changes to `openai_client.py` and the B13 amendment; `sse.py` and its tests go with them.
