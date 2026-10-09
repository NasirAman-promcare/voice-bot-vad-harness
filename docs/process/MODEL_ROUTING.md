# Model routing

Judgement stays on Opus; building runs on Sonnet with an Opus advisor; mechanical work runs on Haiku; bulk code goes to Gemini. Relative API prices show how fast each model draws down plan usage (October 2026, per million tokens): Opus 5.5 $4 in / $20 out; Sonnet 5.5 $2 / $10; Haiku 5.5 $0.10 / $0.50 (prompts up to 100k tokens); Gemini 3.7 Flash $0.75 / $3.75 (introductory).

| Role | Model | Effort | Where it is set |
| --- | --- | --- | --- |
| Project coordinator | Sonnet 5.5 | low | Project settings |
| WP thread, T2 and T3 | Sonnet 5.5 + Opus advisor | high | Project settings; `advisorModel` in `.claude/settings.json` |
| WP thread, T1 | Opus 5.5 | high | Spec's thread model; the coordinator sets it for the thread |
| Plan checker | Sonnet | medium | `.claude/agents/plan-checker.md` |
| Auditor T2 | Opus | high | `wp-auditor` |
| Auditor T1, phase audit | Opus | xhigh | `wp-auditor-deep` |
| Checker T3 | Sonnet | medium | `doc-checker` |
| Explore, test runner, log digest | Haiku 5.5 | low | agent files (`Explore` overrides the built-in) |
| Second opinion | Opus | high | `second-opinion` |
| Bulk code | Gemini 3.7 Flash; a Gemini Pro model for hard modules | n/a | work order `model:` |

Rules:
- Consult the advisor only when finalising a plan, at ladder step 3, and before READY-FOR-AUDIT. Auditors and helper agents never consult it.
- A Sonnet-built WP that needs a third audit round moves its fixes to an Opus thread.
- Never `max` effort; `xhigh` only for T1 audits and phase audits.
- Haiku 5.5 is new (7 October 2026). If an agent fails on the model name, the owner changes `claude-haiku-5-5` to `haiku` in the agent file.
- Your subscription is used only by official Claude clients (Claude Code, claude.ai). No gateway or router may use it; non-Claude models are reached through their own APIs.
