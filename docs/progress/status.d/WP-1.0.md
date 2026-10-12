WP: WP-1.0
Title: Operating model v2: tooling, migration and Phase 0 debts
Status: IN-BUILD
Tier: T1
Size: L
Branch: claude/wp-1-0-operating-model-v2
PR: none yet
Thread model: Opus high
Updated: 2026-10-12
Note: BLK-1.0-14 and BLK-1.0-15 answered; WO-1.0-03 and WO-1.0-04 running through the relay

Handover (2026-10-12, session 013CiaVYjshaAGNKoix51V7R):
- **Done:**
  - BLK-1.0-13 resolved: the NVIDIA key is injected.
  - The real cause of every `upstream request failed` is a 30-second first-byte limit on the session's egress path (EVIDENCE.md).
  - The streaming client is built test first and pending the owner's approval (BLK-1.0-14): `tools/outsourcing/sse.py`, 413 outsourcing tests pass, recipes MC-WO-1.0-10-17 and -18.
  - The models' output budget is measured (BLK-1.0-15).
- **Next, once both are answered:**
  1. Merge `origin/main` (new pool).
  2. On BLK-1.0-14 option 1: add the B13 amendment line to WO-1.0-10 and write DEC-1.0-09.
  3. `relay --models` exits 0; dry runs of WO-1.0-03 and WO-1.0-04.
  4. `relay --wo docs/outsourcing/orders/WO-1.0-03.md --timeout 1200`, then the same for WO-1.0-04.
  5. Review each `wo/<WO>` branch with the WO review checklist and merge it.
  6. WO-1.0-05 and WO-1.0-06 (after 03 and 04), WO-1.0-07 (after 03 and 04), WO-1.0-08 (after 07), WO-1.0-09 (after 01, 03, 04 and 06).
  7. The index build with `--adopt-registry` and `progress migrate`.
- **Open items:**
  - Fix the `[tests: test_x.py]` file-name references in the `tools/outsourcing` headers before the first registry generation (gate E3 needs test function names). Add `CAP-OUTSOURCING-SSE`'s row with the adoption.
  - WO-1.0-03 check: does `impact` select a changed test file itself?
  - Close-out: the break recipes for WO-1.0-03 to WO-1.0-09, NFR-1.0-02 timing, the full fast suite, READY-FOR-AUDIT, the audit, and the KIT blocker for the kit install.
- **Stale worktrees:** `.relay/wt/WO-1.0-03` and `-04` hold this morning's stopped runs. Restart with `--restart`, or let the relay resume them.
