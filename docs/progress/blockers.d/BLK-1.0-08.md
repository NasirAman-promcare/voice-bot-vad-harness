# BLK-1.0-08 — Codestral fences each block separately, which the new outer-fence rule does not cover (my BLK-1.0-07 diagnosis was wrong)
Status: RESOLVED
WP: WP-1.0
Owner capability: DECISION
Raised: 2026-10-11
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 on codestral-2508, the primary model you chose)
Time needed: 5 minutes
Loop: none

What I need: a choice on whether the parser may also remove a code fence wrapped tightly around a single block.

Why: you chose codestral-2508 as the primary model. BLK-1.0-07 said Codestral wraps the whole answer in one fence. That was my mistake: I checked only the first and last lines. In fact Codestral wraps each block separately, copying RETURN_FORMAT.md's per-block examples:
- a ```` ```text ```` line directly before `=== MANIFEST ===`, each `=== FILE: … ===` and `=== DOD ===`;
- a ```` ``` ```` line directly after each `=== END … ===`.
The outer-fence rule you approved is implemented and tested (`90f71f2`), but those per-block fences are still "anything else outside the blocks", which RETURN_FORMAT.md now explicitly refuses.

What I tried:
- **The approved rule.** Re-parsed all nine saved Codestral replies with it. All are still refused: `Non-blank text outside block: '```'`.
- **A per-block rule, as a scratch experiment.** Removing a fence line directly before a block's opening marker, and its matching closing line directly after that block's END marker, made all six saved WO-1.0-03 and WO-1.0-04 replies parse with today's checks. The four files of each step came out complete: for example `tools/progress/fragments.py` with 165 lines, `tools/index/headers.py` with 72. That code is not committed.

Options:
1. **Allow a fence wrapped tightly around one block (recommended).**
   - What is removed: a line of three or more backticks, with an optional word, directly before a block's opening marker, together with the same backticks alone directly after that block's END marker.
   - What stays refused: anything else outside the blocks, a fence that is not tight against the markers, and an unmatched fence.
   - What I do: test first, amend WO-1.0-01 B5, and add a break recipe.
   - What you do: add a matching sentence to RETURN_FORMAT.md.
   Codestral then works as the primary model.
2. **Keep the rule as it is now, and use Gemini.** The Gemini quotas reset at 07:00 UTC (12:00 PKT). Default routing then tries the Gemini models first and keeps Codestral as a fallback that cannot pass. This is about 80 Gemini requests a day for the T1 work.
3. **Rewrite the examples in RETURN_FORMAT.md without the ```` ```text ```` fences** (for example, indented), so that Codestral stops copying them. It is uncertain whether Codestral follows that, and it takes a relay run to find out.

Exact steps:
1. Reply with "option 1", "option 2" or "option 3".
2. For option 1, on GitHub, `main`, edit `docs/process/outsourcing/templates/RETURN_FORMAT.md`. After the line you added (`The relay removes one code fence that wraps the whole answer; …`), add: `It also removes a code fence wrapped tightly around a single block: a fence line directly before the block's opening marker and its closing line directly after the block's END marker.` Commit to `main`.
3. Tell this session "BLK-1.0-08 answered".

Meanwhile: from 07:00 UTC I could run WO-1.0-03 and WO-1.0-04 on Gemini with default routing. That goes against "Codestral primary", so I do it only if you reply "option 2". I fix the relay's daily counting, which counted only successes while Google counts every request (DEC-1.0-06).

Owner answer: 2026-10-11, "option 1"; the owner added the sentence to RETURN_FORMAT.md on `main` (`5aafe78`). Implemented test first (FIXES.md, FIX-BLK-1.0-08); all six saved Codestral replies parse. WO-1.0-03 and WO-1.0-04 run on codestral-2508.
