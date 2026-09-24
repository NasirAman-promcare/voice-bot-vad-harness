# Stop-and-ask protocol (no exceptions)

Stop and ask the owner when any of these happens:
- You need something you do not have: access, credentials, a network host, a file, data, a recording, a decision, a Colab or Oracle result.
- The spec is ambiguous, contradictory or impossible as written, or a test looks wrong.
- Meeting a requirement would need a protected file, an existing test, or code outside the approved plan.
- A command fails twice for a reason you cannot fix within these rules, such as a blocked network host.
- You notice yourself about to simplify, mock, skip, approximate or work around anything.

How to stop:
1. Append an entry to `docs/progress/BLOCKERS.md` using `docs/process/templates/BLOCKER.md`: ID, WP, what you need, why, what you tried, options with trade-offs, what stays paused.
2. Commit and push that file.
3. End your turn with a message that starts with `🛑 OWNER ACTION NEEDED` and gives the owner numbered, plain-language steps.
4. Do not continue work that depends on the answer. Independent parts may continue only if the plan marks them independent.

Network blocks: when a download fails with a proxy denial, report the exact host name so the owner can add it to the cloud environment allowlist. Never switch to a different source on your own.
