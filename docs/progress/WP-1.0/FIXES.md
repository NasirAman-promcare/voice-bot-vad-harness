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
