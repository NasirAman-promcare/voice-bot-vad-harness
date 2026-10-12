# BLK-1.0-13 — The NVIDIA key does not reach this session; relay work continues in a new session
Status: RESOLVED
WP: WP-1.0
Owner capability: ACCESS
Raised: 2026-10-12
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 through the relay)
Time needed: 5 minutes, plus starting a new session
Loop: none

What I need: the NVIDIA API key stored as a network secret (API credential) for `integrate.api.nvidia.com` in the aqis-lab environment, and a new Claude Code session on branch `claude/wp-1-0-operating-model-v2` to continue WP-1.0.

Why: the relay's clients never send a key. The session proxy adds it per host (WO-1.0-10 B11), and a session gets its credentials when it starts. This session started with injected credentials for `api.mistral.ai`, `generativelanguage.googleapis.com` and `huggingface.co` only. No NVIDIA variable is present either. So every NVIDIA chat request leaves without a key, while NVIDIA's model listing, which needs no key, works.

What I tried:
- **Final pool with the forwarded parameters** (`dbfba0e`, DEC-1.0-08). The rebuilt request bodies match your verified parameters:
  - glm: `reasoning_effort "high"`, `temperature 0.5`, `top_p 1.0`;
  - kimi: `reasoning_effort "high"`, `temperature 1.0`, `top_p 0.95`.
- **WO-1.0-04 run.** `PAUSED-BUSY`, `moonshotai/kimi-k3: 18` requests, all rejected.
- **`.relay/rejections.jsonl`.** 34 rejections, all `upstream request failed`, arriving seconds apart: no 15-minute timeouts, an immediate refusal.
- **Environment.** No NVIDIA-named variable exists, and the session documentation says new secrets are picked up by a new session.

Options:
1. **Store the key as a network secret and continue in a new session (recommended).**
2. **Wait for Gemini's quota.** Not available: you disabled Gemini in the pool.

Exact steps:
1. In the Claude Code environment menu (session title bar) → Edit the aqis-lab environment.
2. Under **Network secrets** (or **API credentials**), add your NVIDIA key for host `integrate.api.nvidia.com` with header `Authorization: Bearer <key>`. If the key is only an environment variable today, move it there.
3. Start a new Claude Code session on this repository, branch `claude/wp-1-0-operating-model-v2`.
4. In it, say: "Continue WP-1.0 from docs/progress/status.d/WP-1.0.md (BLK-1.0-13 answered)."

Meanwhile: nothing in WP-1.0 is left that does not need the relay, except records. The next session starts from the status fragment's handover note.

Owner answer: 2026-10-12. The new session (https://claude.ai/code/session_013CiaVYjshaAGNKoix51V7R) has the key injected for `integrate.api.nvidia.com`; a small chat request returns HTTP 200 with `Nvcf-Status: fulfilled`. Correction: the missing key did not explain the rejections. With the key present, the WO-1.0-03 request still gets `502 upstream request failed`, after exactly 30 seconds. Any non-streaming reply that takes more than 30 seconds fails this way, and a streamed one succeeds. The 502 carries none of NVIDIA's headers (`Nvcf-Reqid`, `Date`), so an intermediary on the session's egress path produces it, not NVIDIA. The same cause explains BLK-1.0-12's rejections. Follow-up: BLK-1.0-14 and BLK-1.0-15.
