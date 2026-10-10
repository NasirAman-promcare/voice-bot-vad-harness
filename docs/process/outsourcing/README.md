# Outsourcing pipeline

Claude writes the work order, its step plan and the acceptance tests; a model from the pool (Gemini, Mistral, others the owner enables) writes the code one step at a time; the relay checks each step and feeds failures back to that model up to the attempt budget; Claude audits once. Generation, fix rounds and every wait for the APIs' limits happen outside Claude's conversation, so they cost no Claude tokens, and Claude keeps building while the relay runs in the background.

## Channels
| Channel | How | Owner effort | When |
| --- | --- | --- | --- |
| `api` (default) | A Claude session runs `.venv/bin/python -m tools.outsourcing.relay --wo <path>` in the background. The relay works in its own worktree on branch `wo/<WO>`, commits and pushes each accepted step, and Claude merges the branch when the relay exits 0. Each provider's key is an API credential on the `aqis-lab` cloud environment (Gemini: header `x-goog-api-key` for `generativelanguage.googleapis.com`; Mistral: `Authorization: Bearer` for `api.mistral.ai`); the agent proxy adds it, and no code, file or variable ever holds it | None | Everything, once WP-1.0 has built the relay |
| `jules` | The owner starts a Jules task: "Implement docs/outsourcing/orders/<WO>.md exactly as written, on branch wo/<WO>." Jules works step by step, runs the verify commands in its VM and opens a pull request; CI's scope job checks it | About 1 minute | The bootstrap orders; overflow when the whole pool's daily quota or service is the bottleneck |
| `paste` | `.venv/bin/python -m tools.outsourcing.relay --wo <path> --pack-step K --out <file>` writes one step to paste into AI Studio; the owner uploads the reply to `docs/outsourcing/inbox/<WO>-step-K.md`; Claude imports it with `.venv/bin/python -m tools.outsourcing import --wo <path> --bundle <file> --step K`. Before the relay exists, `.venv/bin/python -m tools.outsourcing pack --wo <path>` packs the whole order | About 5 minutes per step | The API cannot be used and Jules is unavailable |

## Files
- `docs/process/outsourcing/FOUNDATION.md`: the standing prompt (owner-controlled).
- `docs/process/outsourcing/templates/`: `WORK_ORDER.md` (with the step-sizing rules), `RETURN_FORMAT.md`, `FIX_ORDER.md`, `WO_REVIEW_CHECKLIST.md`.
- `config/aqis_lab/model_pool.json`: the model pool: providers, models, ranks, the risk tiers each model may serve, and the limits the relay paces by (owner-controlled; a NEVER path).
- `docs/outsourcing/orders/<WO>.md`: one work order each (Claude writes these).
- `docs/outsourcing/returns/<WO>/steps.md`: the step log the relay resumes from; `summary.md`: attempts, tokens, checks and result.
- `docs/outsourcing/ledger.d/<WO>.md`: one ledger row per order; `docs/outsourcing/LEDGER.md` is generated on `main`.
- `docs/outsourcing/inbox/`: replies uploaded on the paste channel.
- `.relay/` (git-ignored): worktrees, raw responses, full check logs, and the governor's state.

## Relay steps
1. Validate the order and its step plan; open the worktree on `wo/<WO>` and merge in the WP branch's latest commits.
2. Resume at the first step the step log has not accepted.
3. For each step, choose the model (below) and send the Foundation, the order, the context files, interface views of the `interfaces` files and of earlier code outputs, the read-only tests, a step block naming exactly the files to return, and the return format.
4. Import only that step's files, all or nothing; reject truncated or partial files.
5. Quick checks: scope, headers, compromise patterns, read-only tests unchanged, compilation, the step's own tests.
6. On failure, a fix turn with the trimmed failing output, up to `attempt_budget` attempts per step; a cut-off answer splits the step into one request per file.
7. Commit and push each accepted step.
8. After the last step, run the full checks and the `verify` commands; on failure, final fix rounds with all outputs allowed.
9. Write the summary and the ledger row; print at most 25 lines.

## Exit codes
| Code | Meaning | What Claude does |
| --- | --- | --- |
| 0 | Accepted | Merge `wo/<WO>`, review with the checklist |
| 2 | Invalid order, unknown or unavailable model, no enabled provider, unsuitable checkout | Fix and rerun |
| 4 | Questions | Amend the order, rerun |
| 5 | An answer was cut off even for one file | Split the step's work, rerun |
| 6 | A file to send looks like a secret | Remove it from the order |
| 7 | Credential, with no other provider left to switch to | ACCESS item for the owner |
| 8 | Attempts exhausted | Fix small gaps or clarify the order |
| 9 | A read-only test changed | CRITICAL finding; stop |
| 10 | Network failure, or an unexpected API response, after retries | Rerun later; read the summary if it repeats |
| 11 | Every eligible model's daily quota used up (resumable) | Other work; rerun after the printed reset |
| 12 | Service busy after long backoff (resumable) | Other work; rerun after 30 minutes or more |
| 13 | A step's request is larger than the limits allow | Split the step or move called modules to `interfaces` |
| 14 | Git or worktree problem | Read git's message, fix, rerun |

## Model pool and free tiers
- **One pool, many quotas.** Each model has its own quota. On the lab's Gemini free tier (AI Studio, 9 October 2026) every Flash model (2.5, 3, 3.5, 3.6, 3.7, 3.8) allows 5 requests and 250,000 input tokens a minute and 20 requests a day; Flash-Lite 3.1 and 3.5 allow 15 a minute and 500 a day; Pro models get nothing. Mistral's free plan (Admin > Limits, 10 October 2026) sets limits per model with no daily cap: Codestral 25.08 625,000 tokens a minute and 2.08 requests a second, Mistral Large 25.12 250,000 and 1, Ministral 14B 937,500 and 0.5. Mistral Medium, Large 4 and Small allow only 20,000 tokens a minute, less than one of our requests, so they are not in the pool. Using several models and several providers this way is how their quotas are meant to be used.
- **One account per provider.** Limits belong to the account or project, not the key. Spreading work over extra accounts or projects to multiply a free quota is a way around documented limits: Google's API terms forbid it and Google may suspend access without notice; Groq, OpenRouter and Cohere forbid it in so many words. The lab never does it.
- **The router.** For each step the relay picks the highest-ranked model in `config/aqis_lab/model_pool.json` that may serve the order's risk tier, fits the request, and has quota left today, preferring one that can answer without waiting. A model whose code passes first time much less often than the best (25 points, after 8 steps) is tried after the others. Fix turns stay on the model that wrote the step. A model's daily limit, a busy service, a missing model or a bad credential moves the step to the next model in a fresh conversation, without using up an attempt; exit 11 comes only when every eligible model is used up.
- **Risk tiers.** Only models the owner lists for T1 (now Gemini 3.5 to 3.8 Flash, Codestral 25.08 and Mistral Large 25.12) write T1 orders; Gemini 3 and 2.5 Flash also write T2 and T3; Flash-Lite and Ministral 14B write only T3. Changing this is an owner decision in the pool file.
- **Pacing before rejection.** Each relay process spaces its requests per model and per provider and keeps 60-second windows of requests and input tokens within `limit × safety ÷ share`. It measures every request first and refuses a step that could never fit. Processes in one session share the governor's state, so parallel relays pace together and spread across the pool.
- **Rejections.** A per-minute rejection waits the time the provider gives, slows that model down by a quarter, and retries; it speeds back up after 10 successes. An overload backs off with jitter for up to about 5 minutes, then the step moves to another provider, or the relay waits 5 and 10 more minutes before exiting 12. A daily rejection marks the model used up until its reset (midnight Pacific for Gemini, which is 12:00 in Pakistan until 1 November 2026 and 13:00 after; midnight UTC for the others). Lower limits stated by a provider replace the configured ones.
- **Throughput.** WP-1.0's seven relay orders are T1 and have 34 steps: about 45 to 60 requests in a typical run. The four T1 Gemini models give 80 requests a day, and Codestral and Mistral Large have no daily cap, so daily limits no longer set the pace; generation time and checks do, and several relays can run at once. A model whose per-minute token limit is below a request is never chosen for it, and a provider's rejection for size moves the step to a model that fits at once, so no time is spent retrying a request that can never fit.
- **Adding a provider.** NVIDIA's API catalog and OpenRouter are in the pool file, switched off. An OpenAI-compatible provider is added with an entry in the pool file, an API credential for its host, and its host in the environment's allowed domains; no code changes. Free tiers checked on 10 October 2026 that cannot serve this lab: Groq (8,000 tokens a minute, below one request), GitHub Models (retired 30 July 2026), Hugging Face (no free credit), Cerebras (card and a short trial).

## Privacy and cost
- Each provider's free-tier data terms are in the pool file's `data_use`. Gemini free tier: Google may use what the relay sends and receives to improve its products, and human reviewers may read it; Google advises against sending sensitive, confidential or personal information. Mistral's free plan may train on it unless "Anonymous improvement data" is switched off in Admin > Privacy, which the owner does when enabling Mistral. NVIDIA's trial terms allow use to improve NVIDIA's models and limit use to testing and evaluation.
- The relay sends only the Foundation, work orders, the files an order lists, the order's own outputs and the return format: lab tooling, specs and tests.
- Never send secrets, personal data or client data, whatever the channel. A WP that would need such material in an order keeps that part with Claude, or the owner moves the project to a paid tier first.
- The relay refuses files that look like secrets.
