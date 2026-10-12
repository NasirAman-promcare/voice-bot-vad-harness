# DEC-1.0-11 — WO-1.0-07 is sent with about 77,000 input tokens per step
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-12
Spec basis: FR-1.0-07 and FR-1.0-13 (WO-1.0-07 through the relay). WO-1.0-07's own "Before sending" note requires the Claude Code hooks reference and every test that imports the hook tables (`rg -l "stop_gate|_protected" tests/aqis_lab`) in `context`. The work-order template asks to keep a step "under about 30,000 input tokens" so that a request fits the model's per-minute token limit.

Question: how should WO-1.0-07 be sized? Its required context alone is far above the template's step figure.

Options:
1. Send it as required, after moving the modules the hooks only call (`tools/index/__main__.py`, `tools/progress/__main__.py`, `tools/progress/render.py`) to `interfaces`: about 77,000 tokens per step (`relay --dry-run`: `~76960 tokens -> moonshotai/kimi-k3`).
2. Drop the hooks reference or the parity tests from `context`. The order says they are needed: the parity tests parse the hook's messages, and the hooks must read Claude Code's input format exactly.

Choice: 1.

Why: the template's figure protects the per-minute token limit, and the pool's models allow 500,000 input tokens a minute (`config/aqis_lab/model_pool.json`). WO-1.0-04 passed at about 44,000 tokens per step. Leaving out required context would make the implementer guess the hook interface, which FOUNDATION.md forbids.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: split WO-1.0-07 into smaller orders or trim the reference, and resend.
