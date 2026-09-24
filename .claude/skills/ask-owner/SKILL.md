---
name: ask-owner
description: Stop and ask the project owner for help. Use immediately whenever you are blocked or missing access, data, credentials, a network host or a decision; when a spec is unclear, contradictory or impossible; when a test seems wrong; or whenever you feel tempted to simplify, mock, skip, approximate or work around anything.
---

Follow `.claude/rules/10-stop-and-ask.md` exactly:

1. Append a BLOCKER entry to `docs/progress/BLOCKERS.md` using `docs/process/templates/BLOCKER.md`.
2. Commit and push it.
3. End your turn with a message that starts with `🛑 OWNER ACTION NEEDED`, then numbered, plain-language steps for the owner, then what stays paused.

Do not continue any work that depends on the answer.
