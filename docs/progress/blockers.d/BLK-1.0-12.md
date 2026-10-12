# BLK-1.0-12 — Every NVIDIA chat request fails with "upstream request failed", although the model list answers
Status: RESOLVED
WP: WP-1.0
Owner capability: ACCESS
Raised: 2026-10-11
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay until the Gemini quotas reset at 07:00 UTC)
Time needed: 10 minutes
Loop: none

What I need: a check, with your NVIDIA key, of why `integrate.api.nvidia.com` rejects every chat completion, and the status code and body you see.

Why: the relay sends the work orders. Today the Gemini models have used their daily quota (they reset at 07:00 UTC, 12:00 PKT), so only the four NVIDIA models can take a request, and none of them can.

What I tried:
- **Model listing.** `.venv/bin/python -m tools.outsourcing.relay --models` exits 0 and lists all four NVIDIA models as present. So the credential and the model list work.
- **Two runs of WO-1.0-03** (16:07 to 16:29 UTC, then about 16:35 UTC). Every chat request to z-ai/glm-5.3, moonshotai/kimi-k3, deepseek-ai/deepseek-v4.1-flash and z-ai/glm-5.3-flash was rejected: 48 of 48. The provider's message, recorded by the relay in `.relay/rejections.jsonl` (DEC-1.0-07), is the same each time: `upstream request failed`. The classifier counts it as OVERLOADED, so each model got its first request and 5 retries with backoff. Result: `PAUSED-BUSY`, `Tokens: in 0, out 0`.
- **Request size.** The second run used a trimmed order of about 23,000 input tokens per request (the first used about 68,000). Same result, so size above that point is not the cause.
- **Session proxy.** It records no relay failures (`recentRelayFailures: []`). The message comes from NVIDIA's side.

Options:
1. **You test one small request with your key and send me the status and body (recommended).** Typical causes are trial credits used up, a model not served on the free endpoint, or an account that needs phone or organisation verification before inference.
2. **Wait for the Gemini reset at 07:00 UTC** and run on gemini-3.8, 3.7 and 3.6-flash (60 requests a day, counted as sent since DEC-1.0-06). The NVIDIA question stays open.

Exact steps:
1. Run this on your own computer, with your NVIDIA key in place of `$NVIDIA_API_KEY`:
   `curl -s -w "\nHTTP %{http_code}\n" https://integrate.api.nvidia.com/v1/chat/completions -H "Authorization: Bearer $NVIDIA_API_KEY" -H "Content-Type: application/json" -d '{"model": "z-ai/glm-5.3", "messages": [{"role": "user", "content": "Say ok."}], "max_tokens": 16}'`
2. Repeat it with `"model": "moonshotai/kimi-k3"`.
3. Open https://build.nvidia.com/ → your account → **Credits** (or API keys), and note the remaining credits.
4. Reply with the two outputs (the body and the `HTTP` line) and the credits.

Meanwhile: once the Gemini quotas reset at 07:00 UTC, I run WO-1.0-03 and WO-1.0-04 on the Gemini models with default routing, unless you say otherwise.

Owner answer: 2026-10-11. The owner's live tests found the cause: the NIM gateway rejects unsupported sampling values, and GLM-5.3-Flash's default maximum reasoning outlasts the gateway's 15-minute limit. The pool (`dbfba0e`) now holds z-ai/glm-5.3-flash and moonshotai/kimi-k3 with explicit parameters. The client forwards them (DEC-1.0-08), and `relay --models` exits 0.
