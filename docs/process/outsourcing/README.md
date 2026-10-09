# Outsourcing pipeline

Claude writes the work order and the acceptance tests; Gemini writes the code; the relay checks it and feeds failures back to Gemini up to the attempt budget; Claude audits once. The generation and fix rounds run outside Claude's conversation, so they cost no Claude tokens.

## Channels
| Channel | How | Owner effort | When |
| --- | --- | --- | --- |
| `api` (default) | A Claude session runs `python -m tools.outsourcing.relay --wo <path>`. The Gemini API key is an API credential on the `aqis-lab` cloud environment (header `x-goog-api-key`, host `generativelanguage.googleapis.com`); the agent proxy adds it, and no code, file or variable ever holds it | None | Everything, once WP-1.0 has built the relay |
| `jules` | The owner starts a Jules task: "Implement docs/outsourcing/orders/<WO>.md exactly as written, on branch wo/<WO>." Jules runs the verify commands in its VM and opens a pull request; CI's scope job checks it | About 1 minute | The bootstrap orders, and large orders that suit an agent |
| `paste` | `python -m tools.outsourcing pack --wo <path>` writes one file to paste into AI Studio or the Gemini app; the owner uploads the reply to `docs/outsourcing/inbox/<WO>.md`; Claude imports it | About 5 minutes | The relay is down or the API is unavailable |

## Files
- `docs/process/outsourcing/FOUNDATION.md`: the standing prompt (owner-controlled).
- `docs/process/outsourcing/templates/`: `WORK_ORDER.md`, `RETURN_FORMAT.md`, `FIX_ORDER.md`, `WO_REVIEW_CHECKLIST.md`.
- `docs/outsourcing/orders/<WO>.md`: one work order each (Claude writes these).
- `docs/outsourcing/returns/<WO>/summary.md`: attempts, tokens, checks and result for each order.
- `docs/outsourcing/ledger.d/<WO>.md`: one ledger row per order; `docs/outsourcing/LEDGER.md` is generated on `main`.
- `docs/outsourcing/inbox/`: replies uploaded on the paste channel.
- `.relay/` (git-ignored): raw responses and full check logs for debugging.

## Relay steps
1. Parse and validate the work order (front matter, paths, protected classes, secret patterns).
2. Send the Foundation (system instruction), the order, the context files and read-only tests, and the return format.
3. Import only declared paths, all or nothing; reject truncated or partial files.
4. Check: scope, headers, compromise patterns, read-only tests unchanged, then the `verify` commands.
5. On failure, send a fix order with trimmed failing output, up to `attempt_budget` attempts.
6. Write the summary and the ledger row; print at most 25 lines.

## Privacy and cost
- Use a paid Gemini API key for company code; confirm on Google's current terms page that paid-tier prompts are not used to improve its products. Free tiers may be. Set a budget alert of $10 a month.
- Only files listed in an order's `context` and `read_only_tests` are ever sent. The relay refuses files that look like secrets.
- Never send secrets, personal data or client data, whatever the channel.
