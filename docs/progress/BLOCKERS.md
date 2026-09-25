# Blockers

Claude appends an entry here (template: `docs/process/templates/BLOCKER.md`) whenever it needs you. Answer in the session chat or under "Owner answer", then set `STATUS: RESOLVED`.

<!-- entries start below -->

## BLK-001 — WP-0.0 approval file is not recognised by the hooks
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** `docs/approvals/WP-0.0.md` on `main` to contain a line that reads exactly `STATUS: APPROVED` (at the start of the line, no bullet or bold).

**Why:** The hooks (`.claude/hooks/_protected.py`, `load_approvals`) and the `/wp-build` precondition only accept an approval with a line matching `^STATUS:\s*APPROVED\s*$`. The committed file (main `1da3140`) says `- **Status**: APPROVED`, so the whole file is ignored. Its `ALLOW-PATTERNS-IN` lines therefore have no effect, and the Stop hook would block the build as soon as `tools/audit/patterns.py` or `tests/aqis_lab/fixtures/**` exist.

**What I tried:** `git fetch origin main`, then `load_approvals('.', 'origin/main')` from the hook code → `approved files: []`, `ALLOW-PATTERNS-IN rules: []`. I cannot edit `docs/approvals/` (NEVER path).

**Options:**
1. Edit `docs/approvals/WP-0.0.md` on `main` so it follows `docs/process/templates/APPROVAL.md`, with `STATUS: APPROVED` as a plain line. Recommended; takes a minute.
2. Keep the current file. Not workable: the build would be blocked by the Stop hook.

**Paused until answered:** all of `/wp-build WP-0.0`.

**Owner answer:** Owner rewrote `docs/approvals/WP-0.0.md` on main (`475890d`) in the template format. Verified: `load_approvals('.', 'origin/main')` → approved files `['WP-0.0.md']`, ALLOW-PATTERNS-IN `['tools/audit/patterns.py', 'tests/aqis_lab/fixtures/**']`.

## BLK-002 — Parity test red after kit patch 1 (Stop hook v2) until Round 2 is approved
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** your Round 2 approval on `main` (see "What I need from you" in `docs/progress/WP-0.0/PLAN.md`, Round 2), so I can bring `tools/audit/patterns.py` and `tools/audit/gate.py` in line with Stop hook v2.

**Why:** after merging `origin/main` (kit patch 1, `ae73c4f`), `test_FR_0_0_06_pattern_tables_identical_to_stop_hook` fails. The hook's test-skip regex no longer has the leading `@`, its `LAB_CODE_DIRS` gained `config/aqis_lab/` and `requirements/aqis_lab/`, and it has a new "errors silenced in shell" pattern. The Stop hook blocks every stop, and CI on PR #1 is red. The test is correct: it detects exactly this drift.

**What I tried:** ran the fast suite (`1 failed, 82 passed`) and Stop hook v2 read-only (this is the only problem it reports). I did not change code, because the owner asked for plan-only this turn and the fix belongs to the Round 2 change budget.

**Options:**
1. Approve Round 2. The build fixes this first (FR-0.0-06 amended). Recommended.
2. None other: weakening or skipping the parity test is not allowed.

**Paused until answered:** all Round 2 code work. The branch stays red in the meantime, and the Stop hook will show a warning on my next stop.

**Owner answer:** Round 2 approved on main (`2528e74`, conditions R2-1 to R2-4). Fixed in `5ae3ce3` (gate and patterns match Stop hook v2/v3); fast suite `95 passed`.

## BLK-003 — Approval says Stop hook v3 (kit patch 2) is on main, but it is not
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** either kit patch 2 (Stop hook v3) committed to `main`, or your confirmation that I should build Round 2 against the Stop hook v2 now on `main`.

**Why:** `docs/approvals/WP-0.0.md` (main `2528e74`) says: "Stop hook v3 (kit patch 2) is on main. Merge origin/main first; its detection rules equal v2." FR-0.0-06 (amended) requires the gate to match the Stop hook exactly. My parity tests import the hook's tables and parse its messages directly, so they depend on the exact hook file, not only on its detection rules.

**What I tried:** `git fetch origin main && git merge --no-edit origin/main`. `origin/main` = `2528e74` ("Update WP-0.0.md"). Its parent is `ae73c4f` ("Apply AQIS kit patch 1"). `git log origin/main -- .claude/` shows only patch 1 and the original kit. `.claude/hooks/stop_gate.py` line 2 reads "Stop hook (version 2)". `git ls-remote origin` shows no other branch or tag carrying a patch.

**Options:**
1. Commit kit patch 2 to `main`, then say continue. I merge it and build against v3. Recommended if v3 exists: no rework.
2. Confirm "build against v2 on main". I start now; if v3 lands later and changes names or message formats, the parity tests will show exactly what differs and I fix it in a follow-up commit.

**Paused until answered:** all Round 2 build work (every part touches the gate, the parity tests or both).

**Owner answer:** Owner committed kit patch 2 (Stop hook v3) to main (`e4b38ac`) and said continue. Merged into this branch. v3 changes only the hook's memory and reporting; its detection rules equal v2 (verified by reading the diff), so Round 2 builds against v3.
