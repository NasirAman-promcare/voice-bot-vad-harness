# BLK-1.0-11 — model_pool.json: two pairs of models share a rank, and both GLM names are unknown to NVIDIA
Status: OPEN
WP: WP-1.0
Owner capability: KIT
Raised: 2026-10-11
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (relay runs after the ones now running; 15 tests that load the real pool; AT-1.0-09)
Time needed: 5 minutes
Loop: none

What I need: two corrections to `config/aqis_lab/model_pool.json` on `main`, a NEVER path.

Why: the pool must give each model its own rank (WO-1.0-10 B1), and every enabled model must exist at its provider (AT-1.0-09).

What I tried:
- `.venv/bin/python -m tools.outsourcing.relay --models` after merging `00c8f91`:
  - every Gemini model is present;
  - `moonshotai/kimi-k3: present`, `deepseek-ai/deepseek-v4.1-flash: present`;
  - `z-ai/glm-5-3: missing`, `z-ai/glm-5-3-flash: missing`; exit 2.
  The NVIDIA credential works: NVIDIA answered the model listing.
- The ranks in the pool:
  - rank 7: `gemini-3-flash-preview` and `deepseek-ai/deepseek-v4.1-flash`;
  - rank 8: `gemini-2.5-flash` and `z-ai/glm-5-3-flash`.
- The relay loaded that pool, which was a bug: the loader now refuses a repeated rank (FIXES.md, FIX-B1-ranks). Until the ranks are distinct, the relay refuses the pool, and 15 tests that load the real pool fail.
- With only those two ranks changed to 11 and 12 (an in-memory copy), the pool loads.

Options:
1. **Give the two NVIDIA models free ranks, and fix or remove the two GLM entries (recommended).** deepseek-ai/deepseek-v4.1-flash moves to rank 11 and z-ai/glm-5-3-flash to rank 12. For the GLM entries, either correct their names to the IDs on their build.nvidia.com pages, or delete the entries.
2. **Correct the ranks only.** The two GLM models stay in the pool; each request to them gets a 404, and the router moves on to the next model. That costs one request each time.

Exact steps:
1. On GitHub, `main`, edit `config/aqis_lab/model_pool.json`.
2. Set `"rank": 11` for `deepseek-ai/deepseek-v4.1-flash` and `"rank": 12` for `z-ai/glm-5-3-flash` (or any ranks not used elsewhere).
3. For `z-ai/glm-5-3` and `z-ai/glm-5-3-flash`, open each model's page on build.nvidia.com and copy its exact model ID (shown in the page's code sample as `"model": "…"`). Replace the entry's key with it, or delete the entry.
4. Commit to `main` and tell this session "BLK-1.0-11 answered".

Meanwhile: the WO-1.0-03 and WO-1.0-04 runs started before the loader fix; they use the T1 models (Gemini 1–4, then GLM, Kimi, DeepSeek) and are not affected by the repeated ranks, which only change the order of the T2/T3 Gemini models.
