---
name: ask-owner
description: Ask the project owner for something only they can provide (ACCESS, COMPUTE, EXTERNAL-AI, DECISION, PHYSICAL or KIT). Use only after checking that the rules do not let you do it yourself and, for anything but a capability, that the escalation ladder is exhausted.
---

1. Name the capability class. If none fits, do not ask: climb the ladder or decide with a decision record.
2. Write `docs/progress/blockers.d/BLK-<WP>-<nn>.md` from `docs/process/templates/BLOCKER.md`: what you need, why, what you tried (commands and results), options with trade-offs and your recommendation, at most 7 exact steps the owner can copy, the time it takes, and what you do meanwhile.
3. Commit and push it.
4. Continue all work that does not depend on the answer. End your turn or report with `🛑 OWNER ACTION NEEDED (<class>): BLK-<WP>-<nn>` followed by the steps.

Batch requests: if several needs will arise in this WP, raise them together, ordered by what they unblock.
