---
name: wo-write
description: Turn part of a planned AQIS lab work package into a step-planned Gemini work order with read-only acceptance tests, send it through the relay (or Jules, or AI Studio) and act on the result. Use when a plan marks code for outsourcing.
effort: high
argument-hint: "[WP-ID and the plan part to outsource]"
---

Write and send a work order for: $ARGUMENTS

1. Confirm it is worth outsourcing: about 150 or more new lines across clear interfaces. Contract design, edits under about 50 lines, cross-cutting refactors and debugging stay with you.
2. Confirm the acceptance tests for this part exist, are committed and fail for the expected reason.
3. Get the next ID: `.venv/bin/python -m tools.progress new-id --kind WO --wp <WP>` (until WP-1.0: the next free `WO-<WP>-<nn>` in `docs/outsourcing/orders/`).
4. Write `docs/outsourcing/orders/<WO>.md` from `docs/process/outsourcing/templates/WORK_ORDER.md`:
   - front matter complete: `model: default` unless the plan names a model; `outputs` lists every file the implementer may create; `context` holds what must be read in full, `interfaces` the modules it only calls; `read_only_tests` the acceptance tests; `verify` the exact commands;
   - a step plan by the template's sizing rules: one module and its tests per step, leaf modules first, the command line last;
   - files split by responsibility, each at most 300 lines, with the public API described in words;
   - numbered behaviours mapped to spec IDs, edge cases, the Never list, the must-catch list, the Definition of Done;
   - no implementation code: describe, don't write.
5. Check it: `.venv/bin/python -m tools.outsourcing validate --wo <path>`, then `.venv/bin/python -m tools.outsourcing.relay --wo <path> --dry-run`. Split any step over about 30,000 tokens, and compare the expected requests with today's remaining requests (`.venv/bin/python -m tools.outsourcing.relay --status`).
6. Commit and push the order and its acceptance tests, then send it:
   - relay: run `.venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/<WO>.md` in the background and keep working on what does not depend on it (the next order's tests, break recipes, debt fixes). Two relays for independent orders may run at once in one session; they pace together. Reach Gemini only through the relay.
   - Jules or AI Studio (before the relay exists, or when the API cannot be used): an EXTERNAL-AI blocker with exact steps; for AI Studio, one step at a time with `relay --wo <path> --pack-step K --out <file>`, imported with `python -m tools.outsourcing import --wo <path> --bundle <file> --step K`.
7. Act on the relay's exit code:
   - 0: `git merge --no-ff wo/<WO>`, push, `git push origin --delete wo/<WO>`, then review per `docs/process/outsourcing/templates/WO_REVIEW_CHECKLIST.md`. A Jules pull request is merged the same way once its scope check passes (CI's scope job; before WO-1.0-09 exists, run `.venv/bin/python -m tools.outsourcing scope --wo <path> --base <WP branch> --head origin/wo/<WO>` yourself; before WO-1.0-01 exists, compare the changed paths with the order's outputs by hand): `git fetch origin wo/<WO>`, then `git merge --no-ff origin/wo/<WO>`.
   - 11 (every eligible model's daily quota is used up): continue other work. If nothing else is left, arrange the same command for 10 minutes after the printed reset (a scheduling tool in the session if there is one, otherwise the status note `WAITING: pool reset <time PKT>`) and stop. Never use another key, account or project to get round it.
   - 12 (service busy): continue other work and rerun after at least 30 minutes. After a second 12 on the same day, if the order blocks the WP, raise an EXTERNAL-AI item for Jules.
   - 13 (step too large) or 5 (output cut off): split the step, or move called modules to `interfaces`; commit; rerun.
   - 4 (questions): answer by amending the order; commit; rerun. Never guess in your own code.
   - 8 (attempts exhausted): read the summary's remaining failures; fix gaps under about 30 lines yourself, otherwise clarify the order and rerun.
   - 2 or 14: read the message, fix the order or the checkout, rerun.
   - 6 (secret): take the secret-looking file out of the order, or fix the file if it should not hold one; never send it.
   - 10 (network or unexpected API response): rerun after a few minutes; if it repeats, read the summary's error, and raise an ACCESS item only if a host or credential is the cause.
   - 7, or a report line `ACCESS:` or `POOL:`, or a provider reported unverified: one ACCESS item for the owner (operator guide section 1.5), raised once.
   - 9 (integrity): stop; it is a CRITICAL finding.
8. Read only the relay's printed report and the summary; never the raw logs in `.relay/` (use `log-digest` if one must be read).
