# BLK-1.0-04 — Two model names in the pool are not listed by their providers
Status: OPEN
WP: WP-1.0
Owner capability: KIT
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: nothing blocking. The relay leaves out a model its provider does not list ("POOL:" line). This item restores those two models to the pool.
Time needed: 3 minutes
Loop: none

What I need: correct or remove two entries in `config/aqis_lab/model_pool.json`. The file is owner-controlled (a NEVER path).

Why: AT-1.0-09. `.venv/bin/python -m tools.outsourcing.relay --models` confirms every enabled provider's credential works (both listings succeeded) and that 9 of the 11 pool models exist. Two do not.

What I tried:
- `.venv/bin/python -m tools.outsourcing.relay --models` → every model `present` except `gemini-3-flash: missing` and `mistral-large-2512: missing`; exit 2.
- Gemini's listing has no `gemini-3-flash`, but it has `gemini-3-flash-preview`.
- Mistral's listing for this account has no model whose name contains `large`.

Options:
1. Rename `gemini-3-flash` to `gemini-3-flash-preview` (T2/T3 only) and remove `mistral-large-2512`, or replace it with the name Mistral's console shows for Large on your plan. (recommended)
2. Leave the file as it is. The relay prints a `POOL:` line and leaves those models out on each run; T1 orders keep 4 Gemini models and Codestral.

Exact steps:
1. On GitHub, branch `main`, open `config/aqis_lab/model_pool.json` and choose Edit.
2. Rename the key `"gemini-3-flash"` to `"gemini-3-flash-preview"` (keep its values).
3. In the Mistral console (https://console.mistral.ai, Models), find the API name of Mistral Large on your plan. Put that name in place of `"mistral-large-2512"`, or delete that entry if none is listed.
4. Commit to `main` and tell this session "pool updated". I re-run `relay --models` and record AT-1.0-09.

Meanwhile: everything else. The relay works without these two models.

Owner answer:
