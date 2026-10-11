# BLK-1.0-07 — Codestral wraps every reply in one code fence, which RETURN_FORMAT and WO-1.0-01 B5 refuse
Status: RESOLVED
WP: WP-1.0
Owner capability: DECISION
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (WO-1.0-03 to WO-1.0-09 on codestral-2508, the only T1 model answering today)
Time needed: 5 minutes
Loop: none

What I need: a choice on whether the bundle parser may remove one code fence that wraps a whole reply.

Why: `RETURN_FORMAT.md` (owner-owned) says "Nothing else: no greetings, no summaries, no explanations outside these blocks". WO-1.0-01 B5 makes "any non-blank text outside the four blocks" a `BundleError`. Codestral-2508 returns the right blocks, but always inside one fence: the first line is ```` ```text ````, the last line is ```` ``` ````. So every Codestral attempt fails, and a bundle error uses up the step's attempts without switching model.

What I tried:
- **WO-1.0-04, runs 1 to 3.** All nine Codestral replies, three per run, start with ```` ```text ```` and end with ```` ``` ```` (`.relay/logs/WO-1.0-04/step-1/attempt-*/response.raw`). WO-1.0-03's run did the same.
- **Fix-turn wording.** Bundle errors now get a fix turn that names the error and the rule (DEC-1.0-05, tested). The new text reached Codestral: it is in `attempt-3/request.json`, saying "start with the line `=== MANIFEST ===` … not even a code fence around the whole answer". Codestral fenced its reply again.

Options:
1. **Allow one outer fence (recommended).** `parse_bundle` removes exactly one fence pair, and only when it wraps the whole reply: the first non-blank line is ```` ``` ```` or ```` ```<word> ````, and the last non-blank line is ```` ``` ````. Everything inside is then parsed as strictly as today. Any other text outside the blocks, a second fence, or an unclosed fence stays a `BundleError`. I would amend WO-1.0-01 B5 and add tests, test first, plus a break recipe. RETURN_FORMAT.md would need your matching sentence, because it is a NEVER path.
2. **Keep the parser strict and take Codestral out of tier T1** in `config/aqis_lab/model_pool.json`. The relay then depends on Gemini alone (BLK-1.0-06).
3. **Keep everything as it is.** Codestral attempts keep failing; relay work waits for Gemini.

Exact steps:
1. Reply with "option 1", "option 2" or "option 3".
2. For option 1, on GitHub, `main`, edit `docs/process/outsourcing/templates/RETURN_FORMAT.md`. Under "Nothing else: …", add the line: `The relay removes one code fence that wraps the whole answer; anything else outside the blocks is refused.` Commit to `main`.
3. For option 2, on `main`, remove `"T1"` from the `tiers` list of `codestral-2508` in `config/aqis_lab/model_pool.json`.
4. Tell this session "BLK-1.0-07 answered".

Meanwhile: no code change until you answer; the parser stays as WO-1.0-01 specifies.

Owner answer: 2026-10-11, "option 1"; the owner added the rule to RETURN_FORMAT.md on `main` (`7f3c38f`). Implemented test first in `90f71f2` (FIXES.md, FIX-BLK-1.0-07). Codestral's replies need more than this rule (BLK-1.0-08).
