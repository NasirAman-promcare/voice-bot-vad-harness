# DEC-1.0-01 — Work on branch claude/wp-1-0-operating-model-v2, not the session's generated branch
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-10
Spec basis: CLAUDE.md "One WP per thread and per branch (`claude/wp-<x>-<y>-<slug>`)"; WO-1.0-07 B1 (`current_wp` from `claude/wp-<x>-<y>-<slug>`), WO-1.0-09 `refs.wp_from_branch`, WO-1.0-11 B4 (the relay requires a `claude/wp-…` branch).

Question: The cloud session was started on a generated branch (`claude/kind-clarke-jppays`). Which branch carries WP-1.0?

Options:
1. `claude/wp-1-0-operating-model-v2` — follows CLAUDE.md; the relay, the staged hooks and the CI helpers can derive the WP from it.
2. `claude/kind-clarke-jppays` — the session default; the relay refuses to run from it (WO-1.0-11 B4) and no tool can derive the WP.

Choice: 1, branch `claude/wp-1-0-operating-model-v2` from `origin/main` at `7d39036`.

Why: three work orders key off the branch name. The generated branch holds no commits beyond `main` (`git rev-parse HEAD origin/main` gave `7d39036…` for both), so nothing is lost.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: push the same commits to another branch and update the status fragment's `Branch:` line.
