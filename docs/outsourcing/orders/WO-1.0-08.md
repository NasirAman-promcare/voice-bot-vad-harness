---
id: WO-1.0-08
wp: WP-1.0
title: New hooks (loop guard, bash guard) and settings v4, staged
model: default
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/ESCALATION.md
  - docs/process/AUTONOMY.md
  - docs/outsourcing/refs/claude-code-hooks.md
  - .claude/settings.json
interfaces:
  - kit-staging/.claude/hooks/_protected.py
outputs:
  - kit-staging/.claude/hooks/_loopstate.py
  - kit-staging/.claude/hooks/loop_guard.py
  - kit-staging/.claude/hooks/bash_guard.py
  - kit-staging/.claude/settings.json
  - tests/aqis_lab/kit/test_loop_guard.py
  - tests/aqis_lab/kit/test_bash_guard.py
  - tests/aqis_lab/kit/test_settings_v4.py
steps:
  - kit-staging/.claude/hooks/_loopstate.py
  - kit-staging/.claude/hooks/loop_guard.py, tests/aqis_lab/kit/test_loop_guard.py
  - kit-staging/.claude/hooks/bash_guard.py, tests/aqis_lab/kit/test_bash_guard.py
  - kit-staging/.claude/settings.json, tests/aqis_lab/kit/test_settings_v4.py
read_only_tests:
  - tests/aqis_lab/kit/test_acceptance_wo_1_0_08.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/kit/test_loop_guard.py tests/aqis_lab/kit/test_bash_guard.py tests/aqis_lab/kit/test_settings_v4.py tests/aqis_lab/kit/test_acceptance_wo_1_0_08.py -q --tb=short
---

# WO-1.0-08 — New hooks (loop guard, bash guard) and settings v4, staged

## 1. Context
Two gaps remain in enforcement. Claude can repeat a failing command many times without changing strategy, and nothing stops a raw merge or a push to `main` now that Claude merges through the merge gate. Both hooks follow the attached hooks reference exactly. The loop guard is advisory and must never block work because of its own bug; the bash guard is enforcement and must fail closed for commands that look like merges or pushes. `_protected.py` (staged by WO-1.0-07) classifies NEVER paths.

## 2. Your job
Write the loop guard (PostToolUse and PreToolUse on Bash), the bash guard (PreToolUse on Bash) and the version 4 settings that register them, into `kit-staging/.claude/`.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `kit-staging/.claude/hooks/_loopstate.py` | Failure signatures and the state file | `signature(command, tool_response) -> Signature or None` (None when the call did not fail); `record_failure`, `record_success`, `count`, `is_environment(signature)`; state in `.git/aqis-loop.json` with a file lock | 300 |
| `kit-staging/.claude/hooks/loop_guard.py` | Entry point: `loop_guard.py post` and `loop_guard.py pre` | as the hooks reference defines for each event | 200 |
| `kit-staging/.claude/hooks/bash_guard.py` | Entry point: block raw merges, pushes to `main` and shell writes into NEVER paths | as the hooks reference defines for PreToolUse | 250 |
| `kit-staging/.claude/settings.json` | Settings version 4 | the current settings plus the entries in B8 | 80 |
| `tests/aqis_lab/kit/test_*.py` | Subprocess tests with real JSON input | | 300 each |

## 4. Required behaviour
- **B1** Failure detection uses the reference's PostToolUse fields for the Bash tool: a non-zero exit status, or a pytest summary reporting failures or errors. Record which fields you used in the module header. A command that runs the relay (any Python interpreter with `-m tools.outsourcing.relay`, alone or as one part of a chained command) and exits 11 or 12 is a resumable pause, not a failure: it is never counted and never matched as an environment signature.
- **B2** A signature is the hash of: the command with whitespace collapsed, paths under `/tmp` and scratch folders replaced by `<tmp>`, hexadecimal runs of 7 or more characters by `<hex>`, numbers by `<n>`; plus either the sorted failing pytest node IDs, or the last non-empty output line containing `error`, `exception`, `failed`, `fatal`, `denied` or `not found` (case-insensitive), normalised the same way. The loop ID shown to Claude is `LOOP-` plus the first 8 hex characters.
- **B3** Post mode: on the 3rd occurrence of a signature, return additional context exactly: `LOOP GUARD <LOOP-id>: this failure has repeated 3 times. Stop retrying. Classify it (owner capability or not), then climb the escalation ladder in .claude/rules/10-autonomy-and-escalation.md.` On a later success of the same normalised command, reset that signature.
- **B4** Environment signatures (`host_not_allowed`, `x-deny-reason`, `No space left on device`, `Disk quota exceeded`, `429`, `rate limit`, `quota`, `401`, `403`, `Repository not found`, `gated`) trigger at the 2nd occurrence: `LOOP GUARD <LOOP-id>: environment failure (<matched text>). This needs an owner capability (ACCESS or COMPUTE). Raise a blocker naming the exact host, path or service instead of retrying.`
- **B5** Pre mode: when the normalised command's signature has 5 or more occurrences and no file in `docs/progress/blockers.d/` or `docs/progress/decisions.d/` contains its `LOOP-` token, block with: `Blocked by the loop guard: <LOOP-id> failed 5 times. Cite this ID in a blocker or decision record before running it again.`
- **B6** The loop guard fails open: any internal error exits 0 without output and appends to `.git/aqis-loop-errors.log`. That catch-all line ends with `# audit-allow: loop guard fails open by design`.
- **B7** The bash guard blocks, with a message naming the merge gate as the only route: `gh pr merge` in any form; `gh api` calls whose path contains `/merge` or that use method `PUT` on a pull request; `git push` whose refspec targets `main` or `master` (including `HEAD:main`, `+main`, `:main`, `refs/heads/main`); `git update-ref refs/heads/main`; and shell writes into NEVER paths (`>`, `>>`, `tee`, `sed -i`, `cp`, `mv`, `rm` with a NEVER path argument). It allows commands that start with `.venv/bin/python -m tools.autonomy.merge_gate` or `python3 -m tools.autonomy.merge_gate`. If it cannot parse a command that contains `merge`, `push` or a NEVER path, it blocks with an explanation (fail closed). Every other command passes.
- **B8** Settings version 4: everything in the current `.claude/settings.json`, plus a PreToolUse entry for matcher `Bash` running `bash_guard.py` and then `loop_guard.py pre`, a PostToolUse entry for matcher `Bash` running `loop_guard.py post`, and the deny rule `Bash(gh pr merge *)`. Keep `advisorModel`. Commands use `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/...` like the existing entries.

- **B9** Amendment for the current hooks reference (DEC-1.0-03, 2026-10-10). It replaces the event names in B1, B3 and B8.
  - **Events.** A Bash command that exits non-zero reaches hooks as **PostToolUseFailure**: the input has `tool_name`, `tool_input.command` and `error`, whose first line is `Exit code N`, followed by the output. A Bash command that exits 0 reaches hooks as **PostToolUse**, with `tool_response`.
  - **Post mode.** `loop_guard.py post` handles both:
    - A Bash PostToolUseFailure is a failure. Its signature is the normalised command plus the failing pytest node IDs, or the last matching error line, taken from `error`. If `error` has no recognisable line, the signature is the command and the exit status (E3).
    - A Bash PostToolUse is a success and resets the signature (B3), unless its output reports pytest failures or errors.
    - A relay run whose `error` begins `Exit code 11` or `Exit code 12` is a pause: never counted, never matched (B1, E5).
  - **Output.** Messages go in `{"hookSpecificOutput": {"hookEventName": "<the event that fired>", "additionalContext": "<message>"}}` on stdout, with exit code 0.
  - **Settings.** Settings v4 (B8) register `loop_guard.py post` under both `PostToolUse` and `PostToolUseFailure`, each with matcher `Bash`.
  - **Tests.** The acceptance tests send exactly these JSON shapes.

## 5. Edge cases you must handle
- **E1** Commands chained with `&&`, `;` or `|` → each part is checked by the bash guard.
- **E2** `git push origin claude/wp-1-3-x` → allowed.
- **E3** A failing command whose output has no recognisable error line → signature from the command and the exit status only.
- **E4** Concurrent hook runs → the state file stays valid JSON (lock plus atomic replace).
- **E5** A relay run that exits 11 with "daily quota" in its output, twice in a row → no LOOP GUARD message; the same run exiting 8 is counted as usual.

## 6. Never
- Never block work because the loop guard itself failed.
- Never allow a raw merge or a push to `main`, whatever the quoting.
- Never write outside `.git/` state and log files.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the attached hooks reference does not give the PostToolUse fields B1 needs, or describes a different way to return additional context.

## 8. Must-catch behaviours
1. The 3rd identical failure returns the LOOP GUARD message; the 2nd does not.
2. The 5th blocks the same command until a fragment cites the loop ID.
3. A success of the same command resets the count.
4. An environment signature escalates at the 2nd occurrence.
5. `gh pr merge 12 --merge` and `git push origin HEAD:main` are blocked; the merge gate command is allowed.
6. A shell write into `CLAUDE.md` or `.claude/` is blocked.
7. The loop guard exits 0 when its state file is corrupt.
8. Settings v4 contains every current entry plus the new ones.
9. Relay exits 11 and 12 are never counted as failures or environment signatures.

## 9. Definition of Done
- **D1** Every file in section 3 exists with the module header standard.
- **D2** B1 to B9 and E1 to E5 are implemented; point at each.
- **D3** Tests run the hooks as subprocesses with JSON on stdin in scratch repositories.
- **D4** `tests/aqis_lab/kit/test_acceptance_wo_1_0_08.py` passes unmodified.
- **D5** No placeholder or swallowed error, except the loop guard's documented fail-open path.
