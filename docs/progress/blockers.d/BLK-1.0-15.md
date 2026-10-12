# BLK-1.0-15 — Both pool models spend the whole output budget on reasoning and never answer a work-order step
Status: OPEN
WP: WP-1.0
Owner capability: KIT
Raised: 2026-10-12
Session: https://claude.ai/code/session_013CiaVYjshaAGNKoix51V7R
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay)
Time needed: 5 minutes
Loop: none

What I need: a change to `config/aqis_lab/model_pool.json` on `main` (a NEVER path, so only you can make it) that lowers the two models' reasoning effort and raises their output limit to 60,000 tokens.

Why: FR-1.0-13 needs WO-1.0-03 to WO-1.0-09 to go through the relay. With today's pool, neither model returns any code for a real work-order step. They write the files inside their reasoning until `max_tokens` runs out, and the reply has no content.

What I tried (WO-1.0-03 step 1 as the relay builds it, about 21,700 prompt tokens, streamed; EVIDENCE.md has the figures):
- **kimi-k3 with the pool values** (`high`, `max_tokens 16384`): 928 s, finish `length`, `reasoning_tokens 16384`, content 0.
- **glm-5.3-flash with the pool values** (`high`, 16384): 555 s, finish `length`, content 0.
- **glm-5.3-flash, `medium`, 60000**: 1,977 s, finish `length`, `reasoning_tokens 60000`, content 0. The last reasoning chunks are code.
- **glm-5.3-flash, `low`, 60000**: 232 s, finish `stop`, 653 reasoning and 8,028 output tokens. The relay's `bundle.parse_bundle` refuses its reply: `BundleError: Nested block marker === FILE: tests/aqis_lab/index/__init__.py === inside FILE`.
- **kimi-k3, `none`, 60000**: 250 s, finish `stop`, no reasoning, 5,257 output tokens. `parse_bundle` accepts it: 4 manifest rows, 4 files, ending in `=== END DOD ===`.
- **Dry run of the change asked below**, on a scratch copy of the pool: `relay --models --pool <copy>` → both `present`, exit 0. `relay --dry-run` routes every step of WO-1.0-03 (~23k tokens) and WO-1.0-04 (~44k) to `moonshotai/kimi-k3`.
- **NVIDIA's limit**: `max_tokens` 60000 and 131072 are both accepted for both models.

Options:
1. **Kimi first with reasoning off, GLM second at `low`, both with 60,000 output tokens (recommended).** These are the only settings that gave a finished answer to a real step, and only Kimi's answer passed the relay's bundle parser. One sample per model, so GLM stays as the fallback. 60,000 matches the order's own `max_output_tokens`.
2. **Same reasoning values, ranks unchanged (GLM first).** This also works. GLM's single answer failed the bundle parser, so each step would probably need fix turns.
3. **Keep `high` and raise the output limit only.** I do not recommend it: at `medium` and 60,000 tokens GLM still never answered, and one step took 33 minutes.

Exact steps (option 1):
1. On GitHub, open `config/aqis_lab/model_pool.json` on `main` and click the pencil (Edit).
2. In `"moonshotai/kimi-k3"`, set `"rank": 1`, `"max_output_tokens": 60000`, `"reasoning_effort": "none"`.
3. In `"z-ai/glm-5.3-flash"`, set `"rank": 2`, `"max_output_tokens": 60000`, `"reasoning_effort": "low"`.
4. Leave temperature, top_p and timeout_seconds as they are. Commit to `main`.
5. Reply "BLK-1.0-15 done" (and your BLK-1.0-14 answer).

Meanwhile: I merge `main` into the WP branch as soon as it changes, then run `relay --models` and dry runs. The relay runs start only once BLK-1.0-14 is answered.

Owner answer:
