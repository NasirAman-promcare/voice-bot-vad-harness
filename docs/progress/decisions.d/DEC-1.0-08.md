# DEC-1.0-08 — Model request parameters come from the pool; none is sent by default
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-11
Spec basis: the owner's BLK-1.0-12 answer (2026-10-11), which asks the OpenAI-compatible client to forward `reasoning_effort`, `temperature` and `top_p` from the pool, with defaults `"high"` and `0.5`, and to use a socket timeout of at least 180 s (GLM-5.3-Flash) and 360 s (Kimi-K3). The pool on `main` (`dbfba0e`) carries these values per model. WO-1.0-10 must-catch 11, enforced by its read-only acceptance test: "Both clients send no temperature".

Question: the requested defaults collide with must-catch 11, whose assertion I may not change without the owner. Both enabled models define every value, so a default would never be used with the current pool.

Options:
1. **Send each value only when the pool defines it.** This gives exactly the owner's requests for GLM-5.3-Flash and Kimi-K3. A model without values sends none, so must-catch 11 holds. The socket timeout is `max(--timeout, timeout_seconds)` in both clients. The pool loader validates the four optional fields: effort a non-empty string, temperature 0 to 2, top_p above 0 and at most 1, timeout a positive integer.
2. **Send the defaults as written.** This changes must-catch 11's assertion for the OpenAI client, which needs the owner's explicit approval of that test change.

Choice: 1, reported to the owner with option 2 offered.
- WO-1.0-10 B1 (optional model fields) and B11 (request body) are amended.
- Test first: `tests/aqis_lab/outsourcing/test_model_params_wo_1_0_10.py`, `15 failed, 4 passed` before the change (the 4 are timeout controls).
- After it, all 406 outsourcing tests pass. Break recipes MC-WO-1.0-10-15 and -16 are caught.

Why: the owner's goal is that the two NVIDIA models get their verified parameters, and option 1 delivers that exactly, with no hidden default and no weakened test.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Cannot-do note: on requirements, the change follows the owner's instruction and keeps must-catch 11.

Reversal: replace the forwarding loop in `openai_client._build_payload` with the owner's defaults, after the owner approves changing must-catch 11's test.
