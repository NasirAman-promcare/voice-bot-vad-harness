WP: WP-1.0
Title: Operating model v2: tooling, migration and Phase 0 debts
Status: IN-BUILD
Tier: T1
Size: L
Branch: claude/wp-1-0-operating-model-v2
PR: none yet
Thread model: Opus high
Updated: 2026-10-12
Note: WO-1.0-03 and WO-1.0-04 accepted and merged; WO-1.0-05, -06 and -07 running through the relay

Handover (2026-10-12, session 013CiaVYjshaAGNKoix51V7R, updated as work moves):
- **Done:**
  - BLK-1.0-13, -14 and -15 resolved; the streaming client (DEC-1.0-09); pool `da75708` merged.
  - WO-1.0-03 and WO-1.0-04 accepted through the relay and merged, with Claude repairs and take-overs recorded in FIXES.md.
  - Relay defects fixed, each test first with a break recipe: FIX-B14-earlier-files, FIX-B17-ledger-row, FIX-B3-split-siblings, FIX-B15-final-questions.
  - DEC-1.0-10 (impact selects changed tests) and DEC-1.0-11 (WO-1.0-07 step size).
  - The registry is adopted (40 records); AT-1.0-02 and AT-1.0-03 hold.
  - Every `tools/outsourcing` and `tools/progress` header names test functions.
- **In progress:** `relay --wo docs/outsourcing/orders/WO-1.0-0{5,6,7}.md --timeout 1200 --attempts 5`. Logs: `/tmp/claude-0/relay/wo0{5,6,7}.log` (session-local). If they are lost, rerun the same commands: the relay resumes from `wo/<WO>`.
- **Next:**
  1. Review and merge WO-1.0-05, -06 and -07 (checklist, scope, size and shape).
  2. Then WO-1.0-08 (after 07) and WO-1.0-09 (after 01, 03, 04 and 06).
  3. Run `progress migrate` for real; close DEBT-032 to -034 (FR-1.0-11); `.gitignore` `.relay/` (FR-1.0-10).
  4. Break recipes for the must-catch lists of WO-1.0-03 to -09.
  5. NFR-1.0-02 timing, the full fast suite, READY-FOR-AUDIT, the audit, then the KIT blocker for the kit install.
- **Environment notes:** clone with full history (`git fetch --unshallow origin`) or the WP-0.6/0.9 history tests fail. The oracle-setup tests need uv 0.8.17 (this VM has 0.11.32; the same failure on `main`).
