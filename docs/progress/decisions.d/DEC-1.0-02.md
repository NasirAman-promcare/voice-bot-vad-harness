# DEC-1.0-02 — DEBT-034's added test case relies on the WP-0.9 approval's ALLOW-EDIT line
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-10
Spec basis: FR-1.0-11 ("DEBT-032, DEBT-033 and DEBT-034 are closed as their rows describe, each with a test"). DEBT-034's row: "Fix: in WP-1.0, add the case `"- X{debt} moves to {wp}."` (not approved) to that test". `docs/approvals/WP-0.9.md` on `main` accepts WP-0.9-F12 as DEBT-034 with target WP-1.0, and carries `ALLOW-EDIT: tests/aqis_lab/test_aqis_phase0_memo.py` with no `EXPIRES` line.

Question: Under the interim rules, an edit to an existing test needs an owner `ALLOW-EDIT` approval. Is a new approval file needed for the one added case?

Options:
1. Use the existing approval: the same owner file that sets DEBT-034's target names the test file. Record the change in `TEST_CHANGES.md` as add-cases.
2. Ask the owner for a new `ALLOW-EDIT` line in `docs/approvals/WP-1.0.md`, which costs an owner action for the same file and the same fix.

Choice: 1. One parametrize row and its id are added. The six existing cases and every assertion stay byte-identical.

Why: the v3 hooks honour any approved `ALLOW-EDIT` on `origin/main` (`.claude/hooks/_protected.py` `load_approvals`: no WP scoping; this file has no expiry). The fix is exactly the one the approval file accepted.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: revert the added parametrize row and request a WP-1.0 approval line.
