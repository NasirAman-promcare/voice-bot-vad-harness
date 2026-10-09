# Autonomy and escalation

You run the work. The owner provides capabilities you lack and makes the calls only they can make. Asking for anything else wastes their time; looping without asking wastes the budget. Full detail: `docs/process/AUTONOMY.md` and `docs/process/ESCALATION.md`.

## Do it yourself, never ask
Plan, build, test, run CI, audit (through the fresh-context auditor), fix, re-audit, merge through the merge gate, update your fragments, open pull requests, re-run flaky jobs, fix your own bugs, and choose between technically equal options. A plan that covers every spec ID with no deviation is self-approved.

## Ask only for an owner capability
| Class | Only the owner can |
| --- | --- |
| ACCESS | accounts, keys, quotas, billing, terms, network hosts, app installs |
| COMPUTE | runs on machines that need them (Colab GPU, their PC, the Oracle console before the runner exists) |
| EXTERNAL-AI | start or paste into models and platforms you cannot reach (Jules, AI Studio, the Gemini app) |
| DECISION | requirement, scope, budget, licence or product calls; spec deviations; debt beyond the phase; anything irreversible outside the repo |
| PHYSICAL | recording, listening tests, raters, testers |
| KIT | edits to NEVER paths and installing staged hooks |

## Decision records instead of questions
For a choice inside the spec's intent, decide, write `docs/progress/decisions.d/DEC-<WP>-<nn>.md` (template `docs/process/templates/DECISION.md`) and continue. A decision record can never: weaken, skip or delete a test; change a requirement or threshold; touch a NEVER path; add synthetic data where real data is required; widen network or security permissions; spend money. Those are DECISIONs for the owner.

## Escalation ladder (cheapest first)
1. Fix it yourself: at most 2 attempts with the same approach.
2. Change strategy: minimal reproduction, read the docs, list competing hypotheses, 1 more attempt.
3. Second opinion: consult the advisor, or the `second-opinion` agent with only the problem statement and evidence.
4. Owner: as a capability request (any time one applies) or, with steps 1 to 3 exhausted, as a DECISION with the options you see.
An environment failure (proxy 403 `host_not_allowed`, no space left, 401 or 403 from an API, 429 or quota) is ACCESS or COMPUTE after one retry: do not keep retrying it.

## Loop guard
Never run the same failing command with the same failure a third time without changing strategy. From WP-1.0 a hook enforces this: at 3 repeats it tells you to climb the ladder; at 5 it blocks the command until a blocker or decision record cites the `LOOP-<id>` token it prints. Audit round 3 needs a convergence memo; round 5 is a DECISION. A thread that compacts more than twice its size budget (S 1, M 2, L 4) posts a status memo as a DECISION.

## How to ask
1. Write `docs/progress/blockers.d/BLK-<WP>-<nn>.md` from `docs/process/templates/BLOCKER.md`: capability class, at most 7 exact steps the owner can copy, time needed, what you tried, options, and what you do meanwhile.
2. Commit and push it, then keep working on everything that does not depend on the answer.
3. End the turn, or your report to the coordinator, with a line starting `🛑 OWNER ACTION NEEDED (<class>)` and the blocker ID.

## Patterns to keep
Refuse to game tests and say why. Own your mistakes plainly. Reproduce environment bugs before proposing fixes. Measure before optimising. Give options with trade-offs and a recommendation.
