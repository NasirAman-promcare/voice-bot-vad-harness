# DEC-1.0-03 — The loop guard listens on PostToolUseFailure as well as PostToolUse
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-10
Spec basis: FR-1.0-08 (the hooks "exactly as WO-1.0-08 specifies") and must-catch 9 ("The loop guard warns at 3, blocks at 5, resets on success, and escalates environment failures at 2"). WO-1.0-08 B1 reads failures from "the reference's PostToolUse fields for the Bash tool"; its section 7 anticipates a reference that does not give them. Rule 70: hooks "follow the current Claude Code hooks reference for input and output".

Question: The current reference (`docs/outsourcing/refs/claude-code-hooks.md`, saved 2026-10-10) says PostToolUse "runs immediately after a tool completes successfully". A Bash command that exits non-zero fires PostToolUseFailure instead, with `error` whose first line is `Exit code N`. How does the loop guard see failures?

Options:
1. Register `loop_guard.py post` for both events.
   - A Bash PostToolUseFailure is a failure: the signature comes from the command and the `error` text. A relay exit of 11 or 12 is a pause.
   - A Bash PostToolUse is a success, which resets the signature, unless its output reports pytest failures or errors.
   - The additional context goes in `hookSpecificOutput.additionalContext`, with `hookEventName` set to the event that fired.
2. Keep PostToolUse only, as written. The guard would never see a failed command, so must-catch 9 could not hold.

Choice: 1. WO-1.0-08 is amended in B1, B3 and B8. Its acceptance tests send both events' real JSON.

Why: the reference section "PostToolUseFailure", lines "Runs when a tool that started executing fails" and "For Bash and PowerShell, a command that ran and exited produces a first line `Exit code N`". The existing hooks read input as the reference says: the guard reads `tool_input.file_path`, the Stop hook answers with `decision`/`reason`, and session context prints plain text. So the spec's DECISION trigger ("contradicts how the existing hooks read input") does not apply.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: remove the PostToolUseFailure entry from the staged settings, and read failures from PostToolUse again if the reference changes back.
