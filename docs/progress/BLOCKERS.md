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

## BLK-004 — TEN VAD commit pin cannot live in the hash-checked harness-extras.txt
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** a decision on where and how the TEN VAD commit pin lives.

**Why:** the approval condition says "Pin TEN VAD to the commit currently installed, in requirements/aqis_lab/harness-extras.txt". FR-0.0-12(b) says that file is "pinned with hashes", so provisioning installs it with `pip install --require-hashes`. These cannot both hold:
- pip's hash-checking mode rejects version-control requirements ("we don't have a way to hash version control repositories"). If any line in a file has `--hash`, the whole file is in that mode, so a `ten-vad @ git+https://github.com/TEN-framework/ten-vad.git@<commit>` line breaks the install.
- The hashable alternative, a GitHub archive (`https://github.com/TEN-framework/ten-vad/archive/<commit>.tar.gz --hash=sha256:...`), is **blocked in this cloud environment**. The proxy answers 403, "GitHub access to this repository is not enabled for this session". `add_repo` confirms that only anonymous git clone/fetch is served for public repositories, not archives. Provisioning on the cloud VM (AT-0.0-05, AT-0.0-06) would therefore fail. GitHub also does not strictly guarantee archive bytes stay identical.

**What I tried:**
- `git ls-remote https://github.com/TEN-framework/ten-vad.git HEAD` gives `22a3bcd4509d0faaa8eef4881e8af5f39c178950`, the commit `tier1.txt` installs today (its `setup.py` says `ten_vad` 1.0.6.8).
- `git clone` of that commit works here.
- `curl` of the archive and of `codeload.github.com` returns 403 from the proxy.
- `add_repo` for read access: "already available ... anonymous git reads (clone/fetch)" only.

**Options:**
1. **(Recommended)** Keep `harness-extras.txt` fully hash-checked (pytest, pytest-asyncio, opuslib and their dependencies). Put the TEN VAD pin in a second file, `requirements/aqis_lab/harness-vcs.txt`, containing `ten-vad @ git+https://github.com/TEN-framework/ten-vad.git@22a3bcd4509d0faaa8eef4881e8af5f39c178950`. Provisioning installs it with `pip install --no-deps -r`, and the commit SHA (content-addressed by git) is the integrity check. After install it verifies `direct_url.json` records that exact commit, and `harness-extras.txt` points to the file in a comment. Works on the VM, CI, Colab and Oracle.
2. Put the git line in `harness-extras.txt` and install that file **without** `--require-hashes` (the git line has no hash; the PyPI lines keep theirs, but pip will not enforce them). This weakens FR-0.0-12(b).
3. Use a hashed GitHub archive URL in `harness-extras.txt`. This needs the cloud environment to allow GitHub archive downloads (`codeload.github.com` through the session proxy), which I cannot change, and accepts the risk that GitHub changes archive bytes.

**Paused until answered:** FR-0.0-12 (provisioning), and the parts that depend on it: FR-0.0-11 amended (provisioned baseline, `harness-regression` CI job), AT-0.0-05 to AT-0.0-07. Already done in this round: FR-0.0-06 amended, F01 to F04, F06, F09 and F10 (pushed, fast suite 99 passed).

**Owner answer:** Option 1 (session chat, 2026-09-25). `harness-extras.txt` stays fully hash-checked; the TEN VAD commit goes in `requirements/aqis_lab/harness-vcs.txt`, and provisioning verifies the installed commit (`22a3bcd4…`).
