# Escalation ladder, loop guard and the owner queue

## The ladder
1. **Fix it yourself**: at most 2 attempts with the same approach.
2. **Change strategy**: build a minimal reproduction, read the relevant docs, write down at least two competing hypotheses, test the cheapest discriminating one; 1 more attempt.
3. **Second opinion**: consult the advisor, or launch `second-opinion` with only the problem statement, commands and outputs.
4. **Owner**: a capability request (allowed at any step when a capability applies) or, after steps 1 to 3, a DECISION with the options you see.

## Owner capability classes
| Class | Typical requests | Typical time |
| --- | --- | --- |
| ACCESS | accept dataset terms; add an API credential; allow a network host; request a cloud quota; install a GitHub App | 2 to 15 min |
| COMPUTE | run a Colab GPU notebook; run a command on the Oracle VM before the runner exists | 10 to 60 min |
| EXTERNAL-AI | start a Jules task; paste a pack into AI Studio and upload the reply | 1 to 10 min |
| DECISION | change a requirement or threshold; accept debt beyond the phase; approve a deviation; spend money | 5 min |
| PHYSICAL | record, listen, rate, test with people | varies |
| KIT | commit kit or spec files; install staged hooks; interim merge | 5 to 15 min |

## Failure signatures and the loop guard (hook from WP-1.0)
- A failure signature is the normalised command plus either the sorted failing test IDs (pytest) or the last error line, with paths, numbers, hashes and timestamps stripped.
- **3 occurrences**: the hook injects `LOOP GUARD <LOOP-id>: this failure has repeated 3 times. Stop retrying. Classify it (owner capability or not), then climb the escalation ladder.`
- **5 occurrences**: the hook blocks that normalised command until a blocker or decision fragment contains the `LOOP-<id>` token.
- **Environment signatures** (proxy 403 with `host_not_allowed` or `x-deny-reason`, `No space left on device`, quota or `429`, `401`, `403` from an API, `Repository not found`, a gated dataset): after the second occurrence, raise ACCESS or COMPUTE with the exact host, path or service.
- A signature resets when the same command later succeeds.
- The loop guard is advisory code: it fails open and logs its own errors to `.git/aqis-loop-errors.log`.

## Other caps
- Audit round 3: convergence memo. Round 5: DECISION.
- A finding that returns in two consecutive rounds: likely spec ambiguity; DECISION with the competing readings.
- Size budget, counted in context compactions: S 1, M 2, L 4. At twice the budget, post a status memo as a DECISION (continue, split or reduce scope, never silently).

## The owner queue
`docs/progress/OWNER_QUEUE.md`, generated on `main` from open blocker fragments, decision records awaiting review and queued post-merge checks. Order: items that unblock the most running or ready WPs first, then by age. Each item shows its class, steps and time. The coordinator mentions new items once in its daily summary; it never re-asks.

## Blocker lint (from WP-1.0)
A blocker fragment fails lint, and the stop gate blocks, when it lacks a valid capability class, has no steps or more than 7, lacks "Time needed" or "Meanwhile", or its ID does not match its file name.
