# BLK-1.0-06 — No pool model can return a work order today: Gemini reports its daily quota used, Mistral Large is not on the key
Status: OPEN
WP: WP-1.0
Owner capability: ACCESS
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay, FR-1.0-13)
Time needed: 10 minutes
Loop: none

What I need: a check of the Gemini key's real daily quota for the T1 flash models, and either access to `mistral-large-2512` on the Mistral key or its removal from `config/aqis_lab/model_pool.json`.

Why: FR-1.0-13 sends WO-1.0-03 to WO-1.0-09 through the relay. The relay's T1 models are gemini-3.8/3.7/3.6/3.5-flash, codestral-2508 and mistral-large-2512. Today none of them can return an order: Gemini refuses, Codestral's replies are refused by the parser (BLK-1.0-07), and Mistral Large is not reachable.

What I tried:
- **Four relay runs today** for WO-1.0-03 and WO-1.0-04. The reports are in `docs/progress/WP-1.0/EVIDENCE.md`.
- **Gemini overload.** Gemini answered "overloaded" 34 times (HTTP 503, or a 429 without quota details).
- **Gemini daily quota.** Then every T1 flash model answered with a 429 whose quotaId contains `PerDay`. The relay marks a model exhausted only on that answer: `.relay/governor.json` has `exhausted_until` 23:59:59 UTC for gemini-3.8, 3.7, 3.6 and 3.5-flash. Their success counts for today are empty, so no Gemini request succeeded today. Codestral's 9 successes were counted normally.
- **Model list.** `.venv/bin/python -m tools.outsourcing.relay --models` printed `present` for every Gemini model and `codestral-2508`, and `mistral-large-2512: missing`.
- **Mistral Large.** A run pinned to `mistral-large-2512` (exit 7) got a credential error from `api.mistral.ai`, although codestral-2508 answers with the same key. So this is model access, not a bad key.

Options:
1. **Check and fix both (recommended).**
   - Gemini: look up the per-day limits and today's usage in AI Studio. If another app uses the same project, give the relay its own key.
   - Mistral: give the key access to Mistral Large, or remove the model from the pool.
   - After that, the relay runs again after the next quota reset.
2. **Wait for the Gemini reset only** (about 00:00 UTC) and rerun. This is cheap, but if the quota really is near zero, the same refusal comes back.
3. **Remove mistral-large-2512 from the pool only.** This avoids its credential error, which also stops the whole Mistral provider for that run, Codestral included. The Gemini question stays open.

Exact steps:
1. Open https://aistudio.google.com/ with the account that owns the relay's Gemini key, then choose **Dashboard → Usage and limits** (or **Rate limits**).
2. For gemini-3.8-flash, 3.7-flash, 3.6-flash and 3.5-flash, write down the requests-per-day limit and today's usage. Note whether anything else uses this project or key.
3. Open https://console.mistral.ai/ → **Organization → Limits** and check whether `mistral-large-2512` is enabled for the key's workspace. If it is not, either enable it, or delete its entry in `config/aqis_lab/model_pool.json` on `main`.
4. Reply in this session with the two numbers from step 2 for each model, and which choice you made in step 3.

Meanwhile:
- WO-1.0-03 to -09 have their acceptance tests and orders ready.
- I keep the relay's own records correct.
- I rerun the relay once the Gemini quotas reset.
