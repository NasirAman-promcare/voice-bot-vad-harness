WP: WP-1.0
Title: Operating model v2: tooling, migration and Phase 0 debts
Status: IN-BUILD
Tier: T1
Size: L
Branch: claude/wp-1-0-operating-model-v2
PR: none yet
Thread model: Opus high
Updated: 2026-10-12
Note: relay blocked by BLK-1.0-13 (NVIDIA key not injected in this session); continue in a new session (handover below)

Handover for the next session (2026-10-12):
- **Done in this session:**
  - Acceptance tests are committed and failing first for WO-1.0-03 to WO-1.0-09.
  - Relay fixes are in, each test first: whole-reply and per-block fences (BLK-1.0-07, BLK-1.0-08); daily counts on send (DEC-1.0-06); the rejection log `.relay/rejections.jsonl` (DEC-1.0-07); per-model request parameters and timeouts (DEC-1.0-08); unique ranks; the whole checks table in the report.
  - The orders are trimmed (WO-1.0-03 about 23k tokens per step, WO-1.0-04 about 44k).
- **Next:**
  1. Confirm `.venv/bin/python -m tools.outsourcing.relay --models` exits 0.
  2. Run `relay --wo docs/outsourcing/orders/WO-1.0-03.md --timeout 1200` and the same for WO-1.0-04. If they are rejected, read `.relay/rejections.jsonl`.
  3. Review each returned branch `wo/<WO>` with the WO review checklist and merge it.
  4. Then WO-1.0-05 and WO-1.0-06 (after 03 and 04), WO-1.0-07 (after 03 and 04), WO-1.0-08 (after 07), and WO-1.0-09 (after 01, 03, 04 and 06).
  5. Then the tooling runs: the index build with `--adopt-registry` and `progress migrate`.
- **Open items:**
  - Fix the `[tests: test_x.py]` file-name references in the `tools/outsourcing` headers before the first registry generation (the gate's E3 check).
  - WO-1.0-03 check: does `impact` select a changed test file itself?
  - Close-out: the break recipes for WO-1.0-03 to WO-1.0-09, NFR-1.0-02 timing, the full fast suite, READY-FOR-AUDIT, the audit and the KIT blocker for the kit install.
