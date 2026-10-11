# BLK-1.0-10 — The four NVIDIA entries in model_pool.json miss required fields, so the relay refuses the whole pool
Status: RESOLVED
WP: WP-1.0
Owner capability: KIT
Raised: 2026-10-11
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (every relay run: WO-1.0-03 to WO-1.0-09; AT-1.0-09)
Time needed: 10 minutes
Loop: none

What I need: the four NVIDIA model entries in `config/aqis_lab/model_pool.json` (a NEVER path, so only you can edit it) rewritten in the pool's model format, with each model's real input and output token limits.

Why: the relay loads the pool before anything else and refuses an invalid pool, Gemini included (WO-1.0-10 B1). After merging `7155ea6`, `.venv/bin/python -m tools.outsourcing.relay --models` prints `Relay error: Model 'z-ai/glm-5-3' rank invalid` and exits 2.

What I tried:
- **Compared the new entries with the format.** The NVIDIA entries are `{"provider": "nvidia", "tiers": [...], "rpm": 40, "tpm": 500000}`. The loader (`tools/outsourcing/limits.py`, WO-1.0-10 B1) requires `rank` (a unique positive integer: a lower rank is tried first), `risk_tiers` (not `tiers`), `max_input_tokens` and `max_output_tokens`, and reads `tpm_input` (not `tpm`). The Gemini entries show the format, for example `"gemini-3.8-flash": {"provider": "gemini", "rank": 1, "risk_tiers": ["T1","T2","T3"], "rpm": 5, "tpm_input": 250000, "rpd": 20, "max_input_tokens": 1048576, "max_output_tokens": 65536}`.
- **Free ranks.** Ranks in use are 1 to 4 and 7 to 10 (Gemini); 5, 6 and 11 upward are free.
- **Token limits.** I cannot fill in the NVIDIA models' token limits myself: invented limits would be fake data. They come from each model's NVIDIA catalog page.
- **Credential.** Not checked yet: the relay clients send no key, the session proxy adds it, and `--models` cannot run until the pool loads. This session's proxy list, fixed at session start, names Gemini, Mistral and Hugging Face only. If `--models` then reports a credential error for NVIDIA, the environment needs `integrate.api.nvidia.com` added as an injected credential.

Options:
1. **NVIDIA after the four T1 Gemini models (recommended).** Ranks 5, 6, 11 and 12. Gemini goes first while its 20 requests a day per model last; the NVIDIA models then take over.
2. **NVIDIA first.** Ranks 1 to 4 for NVIDIA, with the Gemini models renumbered to 5, 6, 11, 12, 13, 14, 15, 16 in their current order.

Exact steps:
1. On GitHub, `main`, open `config/aqis_lab/model_pool.json` and choose Edit.
2. Replace the four NVIDIA entries with entries of this form, one per model, with the ranks of the option you choose:
   `"z-ai/glm-5-3": {"provider": "nvidia", "rank": 5, "risk_tiers": ["T1","T2","T3"], "rpm": 40, "tpm_input": 500000, "max_input_tokens": <input limit>, "max_output_tokens": <output limit>}`
3. For `<input limit>` and `<output limit>`, use each model's context length and maximum output tokens from its page on build.nvidia.com.
4. Commit to `main` and tell this session "BLK-1.0-10 answered". I then run `relay --models` and, if all are present, WO-1.0-03 and WO-1.0-04.

Meanwhile: WO-1.0-03 and WO-1.0-04 are back on `model: default`, because codestral-2508 is no longer in the pool. Nothing else depends on the relay until they return.

Owner answer: 2026-10-11 (`00c8f91`): the NVIDIA entries were rewritten with ranks 5 to 8 and their token limits. The pool loads and the NVIDIA credential works. Two follow-ups are in BLK-1.0-11: repeated ranks 7 and 8, and both GLM names missing at NVIDIA.
