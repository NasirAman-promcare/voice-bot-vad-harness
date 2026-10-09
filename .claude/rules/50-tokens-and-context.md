# Tokens and context

Usage limits bind before anything else. Every turn re-sends the conversation, and output and thinking cost five times input.

- **Right model for the job** (`docs/process/MODEL_ROUTING.md`): mechanical work goes to the Haiku agents (`Explore`, `test-runner`, `log-digest`); judgement stays on Opus; building runs on the thread's model. Consult the advisor only when finalising a plan, at ladder step 3, and before READY-FOR-AUDIT.
- **Bulk code goes to Gemini.** New code of about 150 lines or more across clear interfaces is written as work orders and sent through the relay (`/wo-write`). Keep in Claude: contract design, edits under about 50 lines, cross-cutting refactors, live debugging.
- **Read narrowly.** Lab Map first, then exact line ranges. Never `cat` a large file or a whole log.
- **Run narrowly.** Affected tests while building; the full suite once before audit; everything else in CI. Never paste whole test logs into the conversation.
- **No idle spend.** No scheduled check-ins, no polling, no watching pull requests after merge, no chatty messages between sessions.
- **Fresh threads for new work.** Prompt caching lasts about an hour; reviving an older thread re-reads all of it. Compact at natural boundaries with a focus line.
- **Planning chats are not for code.** The same budget pays for them.
