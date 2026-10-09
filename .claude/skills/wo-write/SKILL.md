---
name: wo-write
description: Turn part of a planned AQIS lab work package into a Gemini work order with read-only acceptance tests, ready for the relay, Jules or AI Studio. Use when a plan marks code for outsourcing.
effort: high
argument-hint: "[WP-ID and the plan part to outsource]"
---

Write a work order for: $ARGUMENTS

1. Confirm it is worth outsourcing: about 150 or more new lines across clear interfaces. Contract design, edits under about 50 lines, cross-cutting refactors and debugging stay with you.
2. Confirm the acceptance tests for this part exist, are committed and fail for the expected reason.
3. Get the next ID: `.venv/bin/python -m tools.progress new-id --kind WO --wp <WP>` (until WP-1.0: the next free `WO-<WP>-<nn>` in `docs/outsourcing/orders/`).
4. Write `docs/outsourcing/orders/<WO>.md` from `docs/process/outsourcing/templates/WORK_ORDER.md`:
   - front matter complete: `outputs` lists every file the implementer may create; `context` lists only what it needs; `read_only_tests` lists the acceptance tests; `verify` lists the exact commands;
   - files split by responsibility, each at most 300 lines, with its public API described in words;
   - numbered behaviours mapped to spec IDs, edge cases, the Never list, the must-catch list, the Definition of Done;
   - no implementation code: describe, don't write.
5. Size check: the context pack (Foundation, order, context files, tests) stays under about 150k tokens; split the order if not.
6. Commit the order, then send it:
   - relay: `.venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/<WO>.md`;
   - Jules or AI Studio (before the relay exists, or if the relay is down): an EXTERNAL-AI blocker with exact steps, using `python -m tools.outsourcing pack --wo <path>` for the paste channel once it exists.
7. Read only the relay summary, then review per `docs/process/outsourcing/templates/WO_REVIEW_CHECKLIST.md`.
