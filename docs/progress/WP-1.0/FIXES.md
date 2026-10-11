# FIXES — WP-1.0

## FIX-BLK-1.0-07 — parse_bundle removes one code fence wrapping the whole reply (owner answer: option 1)
- **Source.** BLK-1.0-07, answered "option 1" on 2026-10-11. `RETURN_FORMAT.md` on `main` (`7f3c38f`), line 48: "The relay removes one code fence that wraps the whole answer; anything else outside the blocks is refused."
- **Root cause.** WO-1.0-01 B5 refuses any non-blank text outside the four blocks. codestral-2508 wraps every reply in one ```` ```text ```` … ```` ``` ```` pair, so every Codestral attempt fails (EVIDENCE: relay runs 1 to 4).
- **Change budget.** File `tools/outsourcing/bundle.py`:
  - a new private function `_strip_outer_fence`;
  - one call to it in `parse_bundle`, before marker parsing;
  - the header change log.
  Nothing else changes. Order `docs/outsourcing/orders/WO-1.0-01.md` B5 gets the amendment text.
- **Callers (unchanged).** `tools/outsourcing/stepper.py:282`, `stepper_final.py:82` and `__main__.py:107` (CLI `import`).
- **Capabilities at risk.** CAP-OUTSOURCING-005: markers win over fences inside FILE content; every other B5 refusal; truncation signs.
- **Rule.** The pair is removed only when all of these hold:
  - the first non-blank line, stripped, is three or more backticks plus an optional info word;
  - the last non-blank line, stripped, is the same backticks alone;
  - the two lines are different lines.
  Anything else is left unchanged, so a stray fence still fails as text outside the blocks.
- **Evidence.**
  - Before the fix: `.venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_outer_fence_wo_1_0_01.py -q` gave `6 failed, 7 passed`. Each failure was `BundleError: Non-blank text outside block: '```text'` (or the opening fence of that case). The 7 passes are the refusal controls.
  - Baseline before the fix (`test_bundle.py`, `test_acceptance_wo_1_0_01.py`, `test_review_fixes_wo_1_0_01.py`): `83 passed`. After the fix, the same files plus the new test: `96 passed`.
  - `git diff -U0 tools/outsourcing/bundle.py` shows hunks only in the change log, the new `OUTER_FENCE_RE` and `_strip_outer_fence`, and the one changed line in `parse_bundle`.
  - Break recipe `MC-WO-1.0-01-11-outer-fence-only.patch` removes every fence line anywhere. It is caught: `4 failed`.
- **Real replies: still refused, by design.** Re-parsing the nine saved Codestral replies (`.relay/logs/WO-1.0-0{3,4}/step-1/attempt-*/response.raw`) still fails with `Non-blank text outside block: '```'`. Codestral fences each block separately, not the whole answer: lines 0, 9, 11, 22 … of the WO-1.0-04 reply. My BLK-1.0-07 description looked only at the first and last lines and was wrong. The approved rule is in place, but it does not cover Codestral's replies. That is BLK-1.0-08.

## FIX-DEC-1.0-06 — every sent request counts toward the day
- **Source.** The owner's Gemini dashboard (BLK-1.0-06 answer) against `.relay/governor.json`. Decision record: DEC-1.0-06.
- **Change budget.** `tools/outsourcing/governor.py`: `Governor.wait_for_slot` (two count lines added), `Governor.record_result` (its two count lines removed), and the header change log. WO-1.0-10 B5 is amended.
- **Capabilities at risk.** CAP-OUTSOURCING-GOVERNOR: daily exhaustion (mc03), restart persistence (mc07), and parallel processes losing no update (fix01).
- **Evidence.**
  - Baseline (`test_governor.py`, `test_acceptance_wo_1_0_10.py`, `test_fix_wo_1_0_10_0{1,2}.py`, `test_acceptance_wo_1_0_11.py`, `test_relay.py`): `135 passed`.
  - New test before the fix: `4 failed` (`assert 19 == 17`).
  - After the fix, `.venv/bin/python -m pytest tests/aqis_lab/outsourcing -q -m "not slow and not gpu and not colab and not oracle and not network"`: `364 passed in 73.85s`.
  - `git diff -U0` shows hunks only in the change log, `wait_for_slot` and `record_result`. `governor.py` is 391 lines, under the 400-line limit.
  - Break recipe `MC-WO-1.0-10-12-count-sent-requests.patch` is caught: `4 failed`.

## FIX-BLK-1.0-08 — parse_bundle removes a code fence wrapped tightly around a single block (owner answer: option 1)
- **Source.** BLK-1.0-08, answered "option 1" on 2026-10-11. `RETURN_FORMAT.md` on `main` (`5aafe78`): "It also removes a code fence wrapped tightly around a single block: a fence line directly before the block's opening marker and its closing line directly after the block's END marker."
- **Root cause.** codestral-2508 fences every block separately: lines 0, 9, 11, 22 … of `.relay/logs/WO-1.0-04/step-1/attempt-1/response.raw`.
- **Change budget.** File `tools/outsourcing/bundle.py`:
  - a new private function `_strip_block_fences`, with its marker patterns;
  - the line in `parse_bundle` that now calls it before `_strip_outer_fence`;
  - the header change log.
  WO-1.0-01's B5 amendment is extended.
- **Order of the two rules.** Block pairs come first, then the outer fence. Codestral's per-block shape starts and ends with fence lines, so outer-first would remove the wrong pair. Only exact pairs are removed: the opening fence directly before an opening marker, and the same backticks directly after that block's END marker. Lines inside blocks are never touched. An unpaired fence stays and is refused as text outside the blocks.
- **Capabilities at risk.** The same as FIX-BLK-1.0-07 (CAP-OUTSOURCING-005).
- **Evidence.**
  - Before the fix: `.venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_block_fence_wo_1_0_01.py -q` gave `9 failed, 8 passed`, each failure `BundleError: Non-blank text outside block: '```'` or the case's fence. The 8 passes are the refusal controls.
  - After the fix, the first run of the same file plus the fence and bundle tests gave `1 failed, 112 passed`. The failure was my new test's expected value: it assumed questions keep their numbers, but the parser strips them (existing review-fix behaviour). The test now compares with the parse of the unfenced text, like every other case. That file was new and uncommitted.
  - Then `.venv/bin/python -m pytest tests/aqis_lab/outsourcing -q -m "not slow and not gpu and not colab and not oracle and not network"` gave `381 passed in 70.87s`.
  - `git diff -U0` shows hunks only in the change log, the new `_strip_block_fences` with its two patterns, and the one changed line in `parse_bundle`.
  - All six saved Codestral replies (`.relay/logs/WO-1.0-0{3,4}/step-1/attempt-*/response.raw`) now parse, four files each: for example `tools/progress/fragments.py` with 165 lines and `tools/index/headers.py` with 72.
  - Break recipes: `MC-WO-1.0-01-12-block-fences-removed.patch` (rule removed) is caught, `2 failed`. `MC-WO-1.0-01-13-block-fence-pairs-exact.patch` (a closing fence that merely starts with the opening's backticks) is caught, `1 failed`.
