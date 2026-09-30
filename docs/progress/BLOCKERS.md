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

## BLK-005 — Tag corpus-v1 does not contain corpus-v1.tar.gz (my Round 2 plan was wrong)
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** a new decision for R2-1, the source of the corpus archive.

**Why:** your decision R2-1 is "Take corpus-v1.tar.gz from git at tag corpus-v1 and verify its SHA-256". That decision rests on my Round 2 plan, which said the archive was "identical at the tag and at HEAD". **That statement was wrong**: I misread a single `git ls-tree` output line while planning. The facts, all verified with git:
- Tag `corpus-v1` is commit `a3ebbf8` ("Upload full VAD harness codebase", 2026-09-14 10:29). Its tree has **no** `corpus-v1.tar.gz` (`git ls-tree corpus-v1` lists only code folders and files).
- The archive was first committed an hour later in `52ab506` ("Add Tier 1 benchmark results…", 2026-09-14 11:44): blob `745e7bc`, sha256 `832c8d3f…`. Its `corpus/manifest.json` **differs** from the tracked manifest.
- It was replaced in `1479626` ("Update Tier 2 live pipeline…", 2026-09-17): blob `4234c5f`, sha256 `ef4d5da1e30f6a296f84fb59d38bdb5644a9d3b41ac930b9a3e4e5dae64efbbb`, 46,353,268 bytes. This is the version at HEAD and on `main`. Its `corpus/manifest.json` is **byte-identical** to the tracked `corpus/manifest.json`, so it is the only archive the harness can use.

**What I tried:** a real provisioning run on this VM. Every other step passed (system packages, `.venv-harness`, TEN VAD commit verified, imports including the TenVad native library, FireRedVAD weights). The corpus step failed: `fatal: path 'corpus-v1.tar.gz' exists on disk, but not in 'a3ebbf8…'`.

**Options:**
1. **(Recommended)** Pin the corpus to commit `1479626` (the last commit that changed the archive) and blob `4234c5f`, verified by sha256 `ef4d5da1…`. Provisioning reads it from git objects at that commit: no network, no token, same bytes as the tracked file.
2. You move the tag `corpus-v1` to `1479626`, or create a new tag such as `corpus-v1.1` there. Provisioning then reads "from git at tag" exactly as R2-1 says. This is a GitHub action on your side, and moving an existing tag rewrites what `corpus-v1` means for anyone who fetched it.
3. Keep tag `corpus-v1` and additionally require the archive commit to be a descendant of it. This is option 1 with an extra check; it ties the pin to the tag without moving it.

**Paused until answered:** the corpus step of FR-0.0-12, the provisioned baseline and the `harness-regression` CI job (FR-0.0-11 amended), AT-0.0-05 to AT-0.0-07. Everything else is committed: provisioning code and tests (fast tests pass), locks, and the TEN VAD pin.

**Owner answer:** Option 1 (session chat, 2026-09-25): pin `corpus-v1.tar.gz` to commit `1479626` and verify sha256 `ef4d5da1…` directly from git. The owner also approved continuing the independent parts (FR-0.0-10, FR-0.0-13, FR-0.0-11).

## BLK-006 — Colab: scratch venvs with pip cannot be made with `python -m venv` (4 tests fail)
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-25  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** your choice of how tests create throwaway virtual environments that have pip. The fix also changes an existing test (`test_FR_0_0_03_lock_installable_with_plain_pip`, round 1), and the surgical-fix skill says to escalate for that.

**Why:** your Colab check `docs/progress/WP-0.0/OWNER_VERIFY_COLAB_WP-0.0_20260925T151855Z.md` failed on four tests:
- Fast: `test_FR_0_0_12_rejects_ten_vad_at_other_commit`, `test_FR_0_0_12_reinstalls_when_pip_check_fails` and `test_FR_0_0_12_venv_problem_detects_venv_without_pip`.
- Slow: `test_FR_0_0_03_lock_installable_with_plain_pip`.

All four create a scratch venv with `python -m venv <dir>`, which runs `ensurepip`.
- Colab's Python 3.13 is Ubuntu's `/usr/bin/python3.13` without the `python3.13-venv` package, and without that package `ensurepip` fails: `Command '[..., '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1`.
- This VM has `python3.13-venv 3.13.12-1+noble1` installed, so the tests passed here and in CI.
- Provisioning itself passed on Colab, because it makes `.venv-harness` with `uv venv --seed`, which needs no `ensurepip`.

**What I tried:**
- **Reproduced here** (Correction, audit finding F31: this did change the system. `uv python install` also created the link `/root/.local/bin/python3.13`, first on PATH, pointing at the scratchpad Python. It was removed in round 4 with `uv python uninstall`; see FIXES.md "Round 4 audit fixes".)**:** a uv-installed Python 3.13.7 in the scratchpad with its `ensurepip/_bundled` wheels removed. `python -m venv` → `venv rc=1` with the same `ensurepip` error.
- **The four tests with a lab venv on that Python:** `4 failed` (the same four as on Colab).
- **Candidate that works:** `uv venv --seed --python <that Python>` → `pip 26.2.1`, working pip.
- **Where uv gets pip:** from uv's cache, or else from PyPI. With `--offline` it worked here only because provisioning had already cached pip.

**Options:**
1. **(Recommended)** One shared test helper makes every scratch venv that needs pip with `uv venv --seed --python <the running Python>`. This is the same mechanism provisioning uses, already proven on Colab. It is used by the three round 3 tests and by `test_FR_0_0_03_lock_installable_with_plain_pip`, where only the venv-creation line changes, not the assertions. That test is already marked `slow` and `network`.
   - Trade-off: when uv's cache has no pip, the three fast tests download the pip wheel (about 2 MB) from PyPI. That happens on every CI `lab` run, because setup-uv prunes cached wheels. They would stay in the fast suite without a `network` marker, although they then use the network.
2. As option 1, but also mark the three fast tests `network`, so the markers are exact.
   - Trade-off: they leave the fast suite, so CI job `lab` no longer runs the F13, F18 and F27 guards unless the workflow gains a step that runs them. That workflow change would also need your approval.
3. As option 1, with `--offline`, and make every environment warm uv's cache with pip first (CI and Colab would need an extra setup step).
   - Trade-off: tests fail with "no cached pip" wherever that step was skipped. This is fragile.
4. The Colab procedure installs `python3.13-venv` with apt.
   - Trade-off: it fixes Colab only. It is a system change the lab tests would silently depend on, other machines (Oracle) can differ, and it goes against "same result everywhere". Not recommended.

**Paused until answered:** the fix for the Colab report, which covers those four tests and the `scratch_venv` helper. Nothing else is changed. The branch is as audited at `aa9e74c`, plus your report commit `22ce3c6` and this entry.

**Owner answer:** Option 1 (session chat, 2026-09-25; recorded under CONDITIONS in `docs/approvals/WP-0.0.md` on `main`, `d403bad`): use `uv venv --seed` in shared test helpers for throwaway test environments. Changing the venv creation line in `test_FR_0_0_03_lock_installable_with_plain_pip` is approved, with its assertions unchanged.

## BLK-007 — The root-path provisioning test (audit F43, P12) cannot run as root on the CI runner
STATUS: RESOLVED
WP: WP-0.0  ·  Raised: 2026-09-26  ·  Session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM

**What I need:** your choice of how `test_FR_0_0_12_root_installs_without_sudo` runs the script as root on a machine where the test itself is not root, as on the CI runner.

**Why:** audit F43 (P12) requires a test proving that as root `apt-get` is called without `sudo`. The test passes here, as real root. On the CI runner, which is not root, it runs the script as uid 0 of an unprivileged user namespace (`unshare --map-root-user`). GitHub's Ubuntu 24.04 runner blocks that: `unshare: write failed /proc/self/uid_map: Operation not permitted` (job `lab`, run `36231792360`; also `36231766392` and `36231008660`). CI is therefore red on one test: `1 failed, 203 passed`. Your conditions forbid real `sudo` in tests, and skipping a test is not allowed without your approval.

**What I tried:**
- Here: `setpriv --reuid=65534 … unshare --map-root-user id -u` printed `0`, and the test passes as root.
- On CI, the same test fails as quoted above.

Everything else in round 6 is green locally (fast `204 passed` with git-lfs 3.4.1 and 3.7.0, slow `8 passed`, gate `0 findings`). Of the round 6 mutations, 42 are caught and L8 is equivalent.

**Options:**
1. **(Recommended)** Test the root branch in-process. The test calls `Provisioner.step_system()` with `os.geteuid` replaced by a function that returns 0, inside the test only (pytest `monkeypatch`). The stand-in `dpkg-query`, `apt-get` and `sudo` stay on PATH, so the real `run` code path runs. It works identically on the VM, CI and Colab, and still fails under mutation P12.
   - Trade-off: the user id is a test double, which the rules reserve for external services. That needs your approval.
2. Add one CI step to job `lab` before the fast suite: `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`. The runner is thrown away after each job, and the test stays exactly as it is, a real subprocess.
   - Trade-off: a system-changing command in the CI workflow (not in a test), plus a workflow change outside the round 6 budget.
3. Run the test only where the test process is already root (this VM, Colab), and skip it with a stated reason elsewhere.
   - Trade-off: CI no longer covers P12, and a skip is a compromise pattern that needs your approval.

**Paused until answered:** only this test, and the final round 6 records. STATUS stays AUDIT-FAIL until CI is green. Everything else for F39 to F44 is committed and pushed (`bbfd928`).

**Owner answer:** Option 1 (2026-09-26; `docs/approvals/WP-0.0.md` on `main`, `8f11ab0`): "In test_FR_0_0_12_root_installs_without_sudo, use pytest monkeypatch for os.geteuid to return 0. Include minor fixes F45 and F46."

**Resolution:** the test now replaces `os.geteuid` with a function returning 0 through `monkeypatch`, inside the test only, and runs `Provisioner.step_system()` in-process with the stand-in commands on PATH. It passes here and fails under mutation P12 (`if os.geteuid() != 0:` changed to `if True:`). CI results are in EVIDENCE.md, "BLK-007 decision and minor fixes F45 and F46".

## BLK-008 — NFR-0.5-01 (runner overhead under 5 %) cannot be met on the sub-second WP-0.5 workload
STATUS: RESOLVED
WP: WP-0.5  ·  Raised: 2026-09-28  ·  Session: https://claude.ai/code/session_016NHQnTY3XyGxfsvGCp1n9y

**What I need:** your decision on how NFR-0.5-01 is measured or when it applies.

**Why:**
- NFR-0.5-01 asks for "runner overhead under 5 % against a direct loop on the smoke pack". Before any model exists (WP-0.7), the only real work on the smoke pack is the `clip-stats` task (question 2 (a)), which takes about 70 ms for all 60 clips.
- The runner must do some fixed work per run, whatever the size of the run:
  - build and validate the run card, including two `git` calls for the commit and dirty flag;
  - check the staged pack and build the shard plan;
  - write card, plan, shard results, marker, `results.jsonl` and log lines atomically, with fsync.

  That costs about 25 ms, and each extra shard about 6 ms. 5 % of 70 ms is 3.5 ms, less than the two `git` calls alone.
- The plan listed this as risk 1 and promised to stop and ask rather than slow the task, drop fsyncs or checks, or change the comparison.

**What I tried:**
- Measured on this VM: same process, same staged pack, fsync on in both loops, medians of alternating repetitions.
  - First build: overhead **91.8 %** (72.9 ms direct, 139.8 ms runner).
- A profile showed three real inefficiencies in my own new code. I removed them without dropping any check (commit `67f61cf`):
  - the system view was rebuilt on every call;
  - an identical staged manifest was re-validated on every run;
  - `git_state` made four git calls instead of two.
- Now:
  - overhead **33.7 %** with the default single shard (75.4 ms direct, 100.8 ms runner);
  - fixed about 25.4 ms per run, about 6.2 ms per extra shard (6 shards: 137.7 ms; 60 shards: 466.8 ms).
- Full numbers and commands: `docs/progress/WP-0.5/EVIDENCE.md`, "NFR-0.5-01".

**Options:**
1. **(Recommended) Measure NFR-0.5-01 in WP-0.7 with Vosk batch on the smoke pack**, the workload the requirement is really about.
   - That is tens of seconds of real work, so the runner's ~25 ms plus ~6 ms per shard is far below 5 %. The test `test_NFR_0_5_01_runner_overhead_under_5_percent` (marked `slow`) then lands in WP-0.7.
   - Here, the measured numbers stay in `EVIDENCE.md`, and NFR-0.5-01 is recorded in `docs/progress/DEBT.md` with target WP-0.7.
   - Trade-off: the WP-0.5 audit cannot check the 5 % figure; it checks the recorded measurements instead.
2. **Change the requirement to an absolute overhead limit in WP-0.5**, for example "at most 50 ms fixed per run and 10 ms per shard on the cloud VM". The `slow` test measures against those limits on the smoke pack now.
   - Trade-off: it is a different requirement, with figures you choose. 5 % of a 30-minute shard is 90 s, so any such limit is loose for real runs.
3. **Leave NFR-0.5-01 as written for WP-0.5.** WP-0.5 then cannot pass: I found no honest way to reach 5 % on a 70 ms workload.
   - Removing the run card's `git` provenance, the fsyncs or the validation would break other requirements (traceability E3, atomic markers).
   - Making the task slower on purpose would be gaming the test.

**Paused until answered:**
- NFR-0.5-01's test and final evidence;
- marking WP-0.5 `READY-FOR-AUDIT`;
- opening the pull request.

**Not dependent on the answer:** NFR-0.5-02 (Drive write guard tests), the DEBT-009 and DEBT-011 tests (question 13), the must-catch proof and the acceptance commands. I will continue them only if you say so.

**Owner answer:** Option 1 (session chat and `docs/approvals/WP-0.5.md` on `main`, 2026-09-28): the NFR-0.5-01 percentage target is deferred to WP-0.7 (Vosk on the smoke pack) and recorded as DEBT-013 in `docs/progress/DEBT.md`; WP-0.5 records the measured fixed overhead (about 25 ms per run, about 6 ms per extra shard) in `EVIDENCE.md`. The owner also approved continuing NFR-0.5-02, the DEBT-009 and DEBT-011 tests, the must-catch proof, the acceptance runs and the pull request.

## BLK-009 — Oracle probe missing; reserved-core figure not in the repository
STATUS: RESOLVED
WP: WP-0.6  ·  Raised: 2026-09-28  ·  Session: https://claude.ai/code/session_01Q6kwg6fLchZiuf9e84Zn2g

**What I need:**
1. `docs/environment/oracle_probe.txt` on `main`, made with the probe command in `docs/progress/WP-0.6/PLAN.md`, section "Oracle probe (owner need 1)".
2. The number of cores to reserve for timing on the Oracle VM: the Build Plan's "Resource plan" figure, or your decision (PLAN.md, question 2).

**Why:**
- The WP-0.6 spec lists `oracle_probe.txt` under "Read first", and the file does not exist.
- The probe decides the operating system that `oracle_setup.sh` accepts (FR-0.6-01) and whether glibc is new enough for the lock (2.28 or newer).
- It gives the CPU layout, and the core figure then gives the reserved cores in `config/aqis_lab/oracle.yaml` (FR-0.6-04).
- It confirms the `oracle` detection signal (`OracleCloud.com` asset tag), which has never been checked on a real Oracle VM.
- The spec says to stop and ask if "core reservation is not possible on the shape"; only the probe and the core figure can show that.

**What I tried:**
- `ls docs/environment/`: no `oracle_probe.txt`. The session-start hook also reports it MISSING.
- `grep -ri "resource plan"`: only the specs and the WP-0.5 plan mention it; the Build Plan is not in the repository.
- Measured what I could without the VM (PLAN.md, "Measurements"): every lock package, and DuckDB, has CPython 3.13 wheels for x86_64 and aarch64 (manylinux_2_28), so the architecture itself does not block a pinned dependency.

**Options:**
1. **(Recommended)** Run the probe on the Oracle VM and commit its output. Put the core figure (or "as suggested in question 2 (b)") in the approval CONDITIONS for WP-0.6. About 5 minutes.
2. Approve the plan first and send the probe later. I then build every part that does not depend on it (PLAN.md, "Parts that do not depend on owner inputs") and stop before the committed `oracle.yaml` values.

**Paused until answered:** the committed values in `config/aqis_lab/oracle.yaml` (supported operating systems, reserved cores), the Oracle-specific install steps in the runbook, and the owner-run checks. Planning is complete. No code has been written.

**Owner answer:** Owner committed `docs/environment/oracle_probe.txt` and `docs/approvals/WP-0.6.md` to `main` (`6ad251b`). The probe shows VM.Standard.A1.Flex: Ubuntu 24.04.4 LTS on aarch64 (Ampere Altra, Neoverse-N1), 4 CPUs online `0-3`, glibc 2.39, chassis asset tag `OracleCloud.com`, 22 GB available RAM, 38 GB free disk, rclone 1.60.1. The approval sets the reservation: cores 2-3 for timing runs, batch runs on cores 0-1 (highest-numbered half of the physical cores), and questions 1-16 as recommended. Merged into this branch (`f57cfc2`).

## BLK-010 — The committed smoke bundle breaks WP-0.4's "no raw corpus committed" test
STATUS: OPEN
WP: WP-0.7  ·  Raised: 2026-09-30  ·  Session: https://claude.ai/code/session_01DHNEPSgrExgeGVsAYja18g

**What I need:** your decision on how smoke bundles may be committed, because an existing guarded test forbids the approved place.

**Why:**
- You approved question 11: smoke bundles are committed as `data/runs/phase0-smoke/<bundle name>.tar`. I committed the cloud bundle there in `175a361` (`phase0-smoke-cloud-20260930T170440Z.tar`, 808,960 bytes).
- The WP-0.4 test `tests/aqis_lab/test_aqis_registry_fetch.py::test_FR_0_4_02_no_raw_corpus_committed` allows no `.tar`, `.gz`, `.zip` or audio file under `data/` except `data/tts_smoke/NN.wav` and pack archives `data/packs/<id>/v<n>/*.tar`. It now fails: `AssertionError: assert ['data/runs/p...T170440Z.tar'] == []`.
- The test is an existing, guarded file, and the WP-0.7 approval allows editing only `tests/aqis_lab/test_aqis_oracle_setup.py`. I will not change it, and I will not rename the archive to slip past it.
- Until this is settled, the fast suite on the branch has this one failure (`1 failed, 1743 passed, 53 deselected` on `28cce63`), so CI is red and the WP cannot be READY FOR AUDIT. The Colab and Oracle bundles (OC-0.7-01, OC-0.7-02) would hit the same rule.

**What I tried:**
- I checked what the bundle holds: only results, never audio (9 `.json`, 6 `.jsonl`, 3 `.log`, 2 `.csv`, 2 `.parquet`, 1 `.md`). `test_FR_0_7_07_committed_bundles_and_their_reports_in_docs` now checks this for every committed bundle, besides the hashes against `BUNDLE.json`.
- Everything else is done and pushed:
  - the audit gate: `0 findings: OK`;
  - the must-catch proofs 1 to 11;
  - AT-0.7-01 (CLI smoke, contracts, trace of four rows);
  - DEBT-013/014/015/017 closed;
  - EVIDENCE.md up to date.

**Options:**
1. **(Recommended)** Add `ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_fetch.py` to `docs/approvals/WP-0.7.md`, for the function `test_FR_0_4_02_no_raw_corpus_committed` only. I change one line: the allowed pattern also accepts `data/runs/phase0-smoke/phase0-smoke-(cloud|colab|oracle)-<YYYYMMDDTHHMMSSZ>.tar`, and nothing else. The test's rule against raw corpora stays as strict, and the WP-0.7 test proves those archives hold no audio. The approved location (question 11) and the runbooks stay as they are.
2. Commit bundles outside `data/`, for example `docs/runs/bundles/<name>.tar`. No protected file changes. But this departs from question 11, so I would move the committed file and change both runbooks, `docs/runs/PHASE0_SMOKE.md`, EVIDENCE.md and the test's path, and bundles would sit among documents.

**Paused until answered:**
- the final CI run and the pull request;
- STATUS READY-FOR-AUDIT;
- the second full slow-suite run on the final commit (the two WP-0.0 provisioning tests need a clean tree and are rerun then).

The code, tests and evidence of every requirement are done and pushed.

**Owner answer:**
