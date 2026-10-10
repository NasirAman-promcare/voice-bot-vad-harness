# BLK-1.0-02 — Approval line for the spec's allowed .gitignore edit (FR-1.0-10)
Status: RESOLVED
WP: WP-1.0
Owner capability: KIT
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (FR-1.0-10)
Time needed: 2 minutes
Loop: none

What I need: an approval file on `main` with `ALLOW-EDIT: .gitignore`.

Why: The WP-1.0 spec lists `.gitignore` under "Allowed guarded edits" (add `.relay/`). AUTONOMY.md interim rule 3 says spec allowances take effect only with this WP's hook update, so the installed v3 guard and stop gate still need an owner approval. `docs/approvals/` is a NEVER path, which only you can edit.

What I tried:
- Read `.claude/hooks/_protected.py` `load_approvals`: only `ALLOW-EDIT` lines in approved files on `origin/main` unlock a GUARDED path. No current approval names `.gitignore` (checked with `grep -rn gitignore docs/approvals/`: no match).

Options:
1. Add the approval file below (one line of scope). (recommended)
2. Wait for the kit v4 install. That comes after the merge, so FR-1.0-10 could not be in this WP's merge.

Exact steps:
1. On GitHub, open the repository on branch `main` and choose Add file > Create new file.
2. Name it `docs/approvals/WP-1.0.md`.
3. Paste these six lines:
   `STATUS: APPROVED`
   `WP: WP-1.0`
   `APPROVED-BY: owner`
   `DATE: 2026-10-10`
   `PLAN: docs/progress/WP-1.0/PLAN.md`
   `ALLOW-EDIT: .gitignore`
4. Commit directly to `main`, then tell this session "approval committed".

Meanwhile: everything else. The `.gitignore` line is a one-line change, made once the approval is on `main`.

Owner answer: 2026-10-10, owner committed `docs/approvals/WP-1.0.md` on `main` (STATUS: APPROVED, ALLOW-EDIT: .gitignore). Claude added `.relay/` in `9c8bdbb`; `test_FR_1_0_10_gitignore_ignores_relay` passes.
