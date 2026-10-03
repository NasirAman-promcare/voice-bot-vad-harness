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
STATUS: RESOLVED
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

**Owner answer:** Option 1 (`docs/approvals/WP-0.7.md` on `main`, `6ed6229`, 2026-10-02): `ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_fetch.py`, changing only `test_FR_0_4_02_no_raw_corpus_committed` so it also accepts `data/runs/phase0-smoke/phase0-smoke-(cloud|colab|oracle)-<YYYYMMDDTHHMMSSZ>.tar` and nothing else; the WP-0.7 test proving committed bundles hold no audio stays. Done after merging `main`: the one-line change, with every other rule of the test unchanged; the test passes (`docs/progress/WP-0.7/EVIDENCE.md`).

## BLK-011 — CI runners' newer git races the fixture repositories (intermittent red CI)
STATUS: RESOLVED
WP: WP-0.7  ·  Raised: 2026-10-02  ·  Session: https://claude.ai/code/session_01DHNEPSgrExgeGVsAYja18g

**What I need:** your decision on a one-function change to the shared test helper `hermetic_git_env` in `tests/aqis_lab/aqis_testutil.py`, a guarded file that no approval lets me edit.

**Why:**
- CI's push run on `0b12344` (run 278, attempt 1) failed on a WP-0.6 test that WP-0.7 does not touch, `tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing`:
```text
E       FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-0/test_FR_0_6_01_dry_run_explain0/tree/.git/objects/maintenance.lock'
1 failed, 1746 passed, 54 deselected in 149.26s (0:02:29)
```
- Root cause:
  - The CI runner has git 2.55.0 (in the job log); this VM has git 2.43.0.
  - On newer git, `git commit` starts automatic maintenance in a detached background process.
  - The test's fixture repository (`make_tree`, with `hermetic_git_env()`) is committed and then listed at once by `tree_snapshot`. The background process created `.git/objects/maintenance.lock` and removed it between the listing and the `lstat`.
- It is timing-dependent:
  - the pull-request run on the same commit (279) passed;
  - one re-run of the failed job (278, attempt 2) passed.

  CI on `0b12344` is now green in both runs. Every fixture repository made with `hermetic_git_env` can hit the same race on CI. The files that use it: `fixture_repo.py`, `test_aqis_colab_doc.py`, `test_aqis_gate_v2.py`, `test_aqis_harness_provision.py`, `test_aqis_oracle_setup.py`, `test_aqis_version.py`.

**What I tried:**
- Read the job log, `make_tree` and `hermetic_git_env`.
- Re-ran the failed job once, the one re-run allowed. It passed.
- Changed nothing outside the round 2 budget.

**Options:**
1. **(Recommended)** Add `ALLOW-EDIT: tests/aqis_lab/aqis_testutil.py` for the function `hermetic_git_env` only. I'd add `GIT_CONFIG_COUNT=2`, `GIT_CONFIG_KEY_0=maintenance.auto`, `GIT_CONFIG_VALUE_0=false`, `GIT_CONFIG_KEY_1=gc.auto`, `GIT_CONFIG_VALUE_1=0` to the environment it returns. Fixture repositories then never start background maintenance, on any git version. No caller passes its own `GIT_CONFIG_*` values. Every test that uses the helper runs before and after; nothing else changes.
2. Accept it as debt and re-run CI when it happens. No test file changes, but CI on newer runners turns red now and then for a reason unrelated to the change under test.

**Paused until answered:** nothing in WP-0.7 round 2 depends on this. F01 to F04 are fixed and pushed, the debts are recorded, and CI on `0b12344` is green. Only the helper change waits.

**Owner answer:** Option 1 (`docs/approvals/WP-0.7.md` on `main`, `28ab7f4`, 2026-10-02): `ALLOW-EDIT: tests/aqis_lab/aqis_testutil.py`, `hermetic_git_env` only, with `maintenance.auto=0` and `gc.auto=0`. Done after merging `main`: the environment it returns now sets `GIT_CONFIG_COUNT=2`, `maintenance.auto` 0 and `gc.auto` 0 (`git config --show-origin --get maintenance.auto` in a fixture repository: `command line:	0`); the tests that use it pass before and after (`docs/progress/WP-0.7/FIXES.md`, round 2, BLK-011).

## BLK-012 — `results add` aborted at interpreter exit once on CI (WP-0.6 Parquet read from Python-owned bytes)
STATUS: RESOLVED
WP: WP-0.7  ·  Raised: 2026-10-02  ·  Session: https://claude.ai/code/session_01DHNEPSgrExgeGVsAYja18g

**What I need:** your decision on an intermittent native crash in WP-0.6's results-store code: fix it now, with an approval covering two WP-0.6 functions, or accept it as debt.

**Why:**
- CI's push run on `99064c4` (run 283, attempt 1) failed `tests/aqis_lab/test_aqis_results_cli.py::test_FR_0_6_02_add_exit_codes`. The second `python -m aqis_lab results add` of the same run printed its correct result (`… 60 already stored (nothing written)`) and then the process aborted at exit:
```text
E       AssertionError: assert (-6 == 0)
… stderr='terminate called without an active exception\n'
1 failed, 1746 passed, 54 deselected in 196.42s (0:03:16)
```
- That path reads every stored part file through `check_part_file` (`aqis_lab/results/store.py`): `pq.read_table(io.BytesIO(data), use_threads=False)`. `from_score_folder` (`aqis_lab/results/ingest.py`) does the same with `pa.BufferReader(bytes)`. Both hand Arrow a buffer that belongs to Python.
- Most likely cause, which I could not prove (no reproduction): the mechanism of the WP-0.7 parity defect (FR-0.7-08, EVIDENCE.md).
  - An Arrow pool thread drops the last reference to a Python-owned buffer during interpreter shutdown. Releasing it needs the GIL.
  - Under the parity code this hung the exit: gdb showed `PyBuffer::~PyBuffer` → `PyGILState_Ensure` on one thread, and `ThreadPool::Shutdown` from `exit()` on the main thread.
  - Python 3.13 makes such a late thread exit by a forced unwind. Inside a C++ destructor that may not throw, that ends in `std::terminate`, which prints exactly this message and aborts (-6).
- WP-0.7 did not change these two functions. Its `store.py` change (DEBT-015) is in `_ensure_store`, which this path does not reach once the store exists.

**What I tried:**
- No reproduction in 1,200 runs of the exact call (the second `results add` of a finished smoke run), all under pytest:
  - 600 with this VM's Python 3.13.12 and `PYTHONFAULTHANDLER=1`: `codes {0: 600}`;
  - 600 in a fresh venv on CI's Python 3.13.7, built from the hash-checked lock: `codes {0: 600}`.
- Earlier, 600 plain runs of each WP-0.6 read pattern also gave no hang (EVIDENCE.md).
- One re-run of the failed job (run 283, attempt 2): passed. The pull-request run on the same commit (284) passed as well. CI on `99064c4` is green in both runs, both jobs.

**Options:**
1. **(Recommended)** Add `ALLOW-EDIT`-style approval for `aqis_lab/results/store.py` (`check_part_file` only) and `aqis_lab/results/ingest.py` (`from_score_folder` only), the same fix as WP-0.7's parity root-cause fix:
   - copy the bytes into memory Arrow owns (`pa.BufferOutputStream`);
   - read through a `ParquetFile` that is closed at once;
   - with a slow regression test that runs `results add` repeatedly and requires every run to exit 0.

   Trade-off: it touches WP-0.6 capabilities CAP-RESULTS-002 and CAP-RESULTS-00x, and the regression test cannot prove the fix, because the abort never reproduced here.
2. Accept it as debt (target WP-0.8), and re-run CI when it recurs. Nothing changes now, but `results add`, `results query` and `trace` can very rarely abort at exit after doing their work correctly. On Oracle the nightly sync and `results add` run unattended, where an abort would show as a failed command.

**Paused until answered:** nothing in WP-0.7 round 2 depends on this:
- F01 to F04 are fixed;
- BLK-011 is fixed;
- STATUS is READY-FOR-AUDIT;
- CI on `99064c4` is green.

Only the store and ingest change waits.

**Owner answer:** Option 1 (`docs/approvals/WP-0.7.md` on `main`, `a7e0d4e`, 2026-10-02): in `check_part_file` (`aqis_lab/results/store.py`) and `from_score_folder` (`aqis_lab/results/ingest.py`), copy the bytes into Arrow-owned memory (`pa.BufferOutputStream`) before `pq.read_table`, and add a repeat regression test. Done after merging `main`: both functions read from the Arrow-owned copy; `test_FR_0_6_02_repeated_results_add_always_exits_cleanly` (slow) runs `results add --run` and `--scores` 60 times each in fresh processes, every one exiting 0 (`docs/progress/WP-0.7/FIXES.md`, BLK-012). The abort never reproduced here, so the test guards the path but cannot prove the fix on its own.

## BLK-013 — WP-0.8 needs the blueprint and Build Plan sections its spec cites
STATUS: RESOLVED
WP: WP-0.8  ·  Raised: 2026-10-02  ·  Session: https://claude.ai/code/session_01L48B7DHkHhYAqxs9WH35hb

**What I need:** the text of the AQIS Test Lab blueprint and Build Plan committed to `main` under `docs/specs/sources/`. At least these parts:
- blueprint "Test data strategy";
- blueprint "Voice emotion and the filler selector";
- Build Plan "Dataset architecture";
- Build Plan "Phase 1";
- every blueprint passage on the harm-rate target, the practical margin for model comparisons, the timing budget and the gate escalation limit.

Markdown or plain text is best, because tests can then read them.

**Why:** this spec takes most of its content from these documents:
- FR-0.8-02 must match the Build Plan: the 80-prompt structure by family, device and room guidance, file naming, format, transfer and quality checks.
- FR-0.8-04 uses the blueprint's four risk levels.
- FR-0.8-05 must cite the blueprint for every option.
- FR-0.8-01 and FR-0.8-03 need the Build Plan's facts on storage, devices, rooms, noise sources and accent groups.

Earlier WPs could rely on specs that were complete on their own. This one says outright that its content comes from these documents, so writing it without them would mean inventing that content.

**What I tried:**
- `find` for blueprint, Build Plan, `.pdf` and `.docx` files: none in the repository, including `aqis-kit-patch-3/`.
- `grep -ri` for "blueprint", "build plan", "80-prompt", "risk level", "harm" and "escalation": only the specs and earlier plans match.
- WP-0.2 to WP-0.7 recorded the same gap. WP-0.5 took its unit rates from figures the owner pasted into the approval.

**Options:**
1. **(Recommended)** Commit both documents whole, as Markdown or text, to `docs/specs/sources/` on `main`. I cannot change files there, so the auditor can check every citation against them, and nothing I need is left out. About 5 minutes.
2. Commit only the four named sections plus the passages on the four targets. This works the same if nothing else is cited. The risk is that a needed passage is missing and I have to ask again.
3. For any item the documents do not cover, decide it yourself in the approval (PLAN.md, question 1 lists these items).

**Paused until answered:** the content of all five WP-0.8 documents. Planning is complete, and no document, code or test has been written. Once the plan is approved, the debt work (PLAN.md, question 2) does not depend on this answer and can be built first.

**Owner answer:** Option 1 (`docs/approvals/WP-0.8.md` on `main`, `61c50c7`): the owner committed `docs/specs/sources/AQIS_Test_Lab_Blueprint.md` and `docs/specs/sources/AQIS_Test_Lab_Build_Plan.md`, and approved questions 2 to 8 as recommended, with the consent facts and the consent scheme given in the approval. Merged into this branch (`bd0fa9c`).

## BLK-014 — WP-0.8: recording-guide facts the Build Plan does not give, two test-file edits for DEBT-012, and your target decisions
STATUS: RESOLVED
WP: WP-0.8  ·  Raised: 2026-10-02  ·  Session: https://claude.ai/code/session_01L48B7DHkHhYAqxs9WH35hb

**What I need:**
1. Your answers to items A to G below, for the recording guide (FR-0.8-02) and the session form (FR-0.8-03).
2. Two `ALLOW-EDIT` lines for DEBT-012 (item H).
3. Your `DECISION:` lines for the four targets and retention (item I), as approved in question 7 (a).

**Why:**
- **FR-0.8-02 and FR-0.8-03.** FR-0.8-02 asks for "file naming, format, transfer, and quality checks, matching the Build Plan". The committed Build Plan (`docs/specs/sources/AQIS_Test_Lab_Build_Plan.md`) gives the 80-prompt families, 22 speakers, about 30 minutes, "own phones" and "half quiet rooms, half everyday noise". It says nothing on:
  - recording format;
  - transfer;
  - quality checks and their thresholds;
  - noise sources;
  - accent groups;
  - how the quiet and noisy halves are split.

  The session form needs fixed choice lists for noise source and accent group. Writing these myself would invent values.
- **DEBT-012.** You chose "`changes` required for every dataset" (question 3). I tried it in a scratch worktree: making `changes` required in `aqis_lab/registry/schemas/datasets.v1.json` breaks 70 existing fast tests and errors 64 more, because the test helpers build datasets without `changes`. I cannot edit existing test files without your approval.

**What I tried:**
- I read both committed sources in full; the facts above are not in them.
- For DEBT-012, in a scratch worktree only, I added `changes` to 4 lines of 2 existing test files. The fast suite was then green, apart from one test that fails in a scratch worktree even without any change (`test_FR_0_0_06_fails_closed_on_changed_file_it_cannot_read`; it passes in the real checkout). The 4 lines only add a `changes` value to test datasets; no assertion changes:
```text
tests/aqis_lab/aqis_packs_testutil.py      download_entry: add "changes": f"{source} test changes text"
tests/aqis_lab/aqis_packs_testutil.py      owner-smoke entry: add "changes": "WAV header rewritten in the canonical form (samples unchanged)."
tests/aqis_lab/test_aqis_registry_validate.py  _datasets owner-smoke entry: add "changes": "owner"
tests/aqis_lab/test_aqis_registry_validate.py  test_FR_0_4_01_datasets_file_rejects_unknown_licence_and_keys entry: add "changes": "c"
```

**Options** (my recommendation is marked; any value you give is used word for word):
- **A. Quiet and noisy halves.**
  - **(a) Recommended:** by speaker. 11 speakers record all 80 prompts in a quiet room and 11 in everyday noise. Each session stays in one place, and every prompt family stays whole.
  - **(b)** Within each speaker, 40 prompts in each condition. This gives a paired comparison, but needs two places per session and splits the 15-prompt and 5-prompt families unevenly.
- **B. How sessions run and how files travel.**
  - **(a) Recommended:**
    - Sessions are in person with you.
    - The speaker records on their own phone with its built-in voice recorder.
    - Before the speaker leaves, you copy the files to your computer and run the quality checks.
    - You upload one archive per session (`ca-sNNN.zip`) to `MyDrive/AQIS_LAB/campaign_a/raw/`.
    - With the speaker's agreement, the files are then deleted from their phone.
  - **(b)** Remote sessions. Each speaker uploads to a Drive folder shared only with them, and you move the files into `AQIS_LAB`.
- **C. Recording format.**
  - **(a) Recommended:** whatever the phone's built-in recorder writes (often M4A/AAC), kept as the original. In phase 1 the lab converts a copy to the working format (16 kHz, mono, 16-bit PCM WAV), which the registry importer requires. "Own phones" is the test condition, and the phone's codec is part of it.
  - **(b)** A recorder app that writes WAV. Cleaner audio, but not what callers' phones send, and speakers must install an app.
- **D. Quality checks.** I propose these. Accept them, or give other values.
  1. every prompt has exactly one file, and the file plays;
  2. you listen, and the speaker said the prompt;
  3. no clipping: at most 0.1 % of samples at full scale;
  4. not too quiet: peak at least −30 dBFS;
  5. at least 0.3 s of silence before and after the speech;
  6. a quiet-room session has no background noise you can hear; an everyday-noise session has the noise named on the session form.

  A failed check means re-recording that prompt in the same session.
- **E. Noise sources** (session form choices).
  - **(a) Proposed:** `none` (quiet room), `tv-radio-music`, `people-talking`, `traffic-street`, `household-appliance`, `other` (described in the notes).
  - **(b)** Your own list.
- **F. Accent groups** (session form choices).
  - **(a) Recommended:** you give the list of groups you recruit for. The Build Plan says only "mixed accents", and I cannot choose groups.
  - **(b)** The speaker describes their accent in their own words, and groups are formed later.
- **G. Phone use and room IDs.**
  - **(a) Recommended:**
    - hold the phone as for a normal call, using its built-in microphone, with no headset or earbuds;
    - the device field is the phone's make and model;
    - the room IDs are `quiet` and `everyday-noise`, plus a free description in the notes.
  - **(b)** Other phone use, such as speakerphone on a table.

  File naming needs no answer. I will use the approved plan's rule, `<speaker-id>-<family-id>-<NN>.wav` (for example `ca-s001-f2-07.wav`), which satisfies the registry's file and clip ID rules.
- **H. DEBT-012.**
  - **(a) Recommended:** add these two lines to `docs/approvals/WP-0.8.md` on `main`:
```text
ALLOW-EDIT: tests/aqis_lab/aqis_packs_testutil.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_validate.py
```
  - **(b)** Retarget DEBT-012 to WP-0.9 and close it there.
- **I. Your decisions** (question 7 (a)). After reading `docs/decisions/TARGETS_OPTIONS.md`, add these lines to `docs/approvals/WP-0.8.md` on `main`. I then add the check that each line names an existing option.
```text
DECISION: harm-rate = HR-?
DECISION: margin = PM-?
DECISION: timing-budget = TB-?
DECISION: gate-escalation = GE-?
DECISION: retention = <your wording>
```

**Paused until answered:**
- FR-0.8-02 and FR-0.8-03 (items A to G);
- DEBT-012 (item H);
- the decision check, the AT-0.8-01 evidence and READY-FOR-AUDIT (item I).

Done and pushed: DEBT-010, DEBT-018, DEBT-020, DEBT-021, FR-0.8-01, FR-0.8-04 and FR-0.8-05, with must-catch proof. The fast suite is green: `1785 passed, 55 deselected`.

**Owner answer:** Answered in `docs/approvals/WP-0.8.md` on `main` (`b4b327e`), merged into this branch (`8845e01`):
- (A) by speaker, 11 quiet-room and 11 everyday-noise speakers;
- (B) one tar.gz archive per speaker session, uploaded to `MyDrive/AQIS_LAB/campaign_a/raw/`;
- (C) the phone recorder's original kept, converted to 16 kHz mono 16-bit PCM WAV;
- (D) clipping at most 0.1 %, peak at least -30 dBFS and at most -1 dBFS, at least 0.3 s of silence padding, verbatim prompt match;
- (E) noise sources `ns-fan`, `ns-traffic`, `ns-tv`, `ns-chatter`, `ns-kitchen`, `ns-generator`, `ns-ambient`, `ns-none`;
- (F) accent groups `acc-south-asian-general`, `acc-urdu-influence`, `acc-punjabi-influence`, `acc-pashto-influence`, `acc-sindhi-influence`, `acc-neutral-urban`, `acc-other`;
- (G) handheld phone 10-15 cm from the mouth, no headset; quiet room or everyday noise room;
- (H) `ALLOW-EDIT: tests/aqis_lab/aqis_packs_testutil.py` and `ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_validate.py`;
- (I) `DECISION:` harm-rate = HR-B, margin = PM-B, timing-budget = TB-B, gate-escalation = GE-B, retention = 3 years from the date of recording.

## BLK-015 — WP-0.1 needs your Tier 2 raw outputs and your choice of baseline run
STATUS: RESOLVED
WP: WP-0.1  ·  Raised: 2026-10-03  ·  Session: https://claude.ai/code/session_01NVq6FhCHSL6tz42EFj3VhC

**What I need:**
- your choice of the Tier 2 run that becomes the baseline;
- that run's raw outputs (items R1 to R8 in `docs/progress/WP-0.1/PLAN.md`) committed to `main` under `docs/baselines/tier2_vad/<YYYY-MM-DD>/raw/`, including `NETWORK.md`, which only you can write.

**Why:**
- FR-0.1-01 checks this folder for completeness, and FR-0.1-02 takes every number in `SUMMARY.md` from it.
- The spec puts the run and the commit on you ("Owner steps" 1 and 2). The folder does not exist yet.
- The repository already holds a Tier 2 run, but it was made with the harness before commit `bb0ed2e`. Its configuration, harness version and console log are not recorded (PLAN.md finding 2). So I cannot simply use it.

**What I tried:**
- `git ls-tree -r --name-only origin/main -- docs/baselines`: only `harness_tests_baseline.md`.
- Read `results/run_output/raw_evaluations.jsonl`: one Tier 2 run, `vad_eval_run_20260913_001_20260923_072436`, 1,344 scored clips over 6 operating points, no failures.
- `git show bb0ed2e`: the same commit changed `orchestrator.py`, `bots/listener_bot.py`, `webrtc_bridge/media_session.py`, `reporting.py` and set `config/run_config.yaml` back to `tier1`.
- `git log` on `README.md`: it holds only the title in every commit, so there are no written Tier 2 run instructions.

**Options:**
1. **(Recommended)** Make a new full Tier 2 run with today's harness on `main`, using the suggested steps in PLAN.md ("Owner needs"), and commit `raw/`. This matches the spec, and every required item can be captured.
2. Use the 2026-09-23 run. You also supply its run configuration as used, the harness commit and local changes, and its console log. This accepts deviation D2 (an older harness). If any of these cannot be supplied, it is missing, and I must stop again.

**Paused until answered:** all of `/wp-build WP-0.1`. Every requirement reads the raw folder, so no part of the build is independent of it.

**Owner answer:** Option 1 (`docs/approvals/WP-0.1.md` on `main`, `75e39d9`: questions 1 to 6 as recommended, plus conditions on question 6 and R6). The owner committed a new run, `vad_eval_run_20260913_001_20261003_075907`, to `docs/baselines/tier2_vad/2026-10-03/raw/` (`e3786b5`). Merged into this branch. The completeness check found gaps, raised as BLK-016.

## BLK-016 — WP-0.1: NETWORK.md misses three required points; two raw details differ from the approved checks
STATUS: RESOLVED
WP: WP-0.1  ·  Raised: 2026-10-03  ·  Session: https://claude.ai/code/session_01NVq6FhCHSL6tz42EFj3VhC

**What I need:**
- the three facts missing from `docs/baselines/tier2_vad/2026-10-03/raw/NETWORK.md`;
- your ruling on two small differences between the raw files and the checks approved in PLAN.md (R3 and R8).

**Why:** FR-0.1-01 says: "List anything missing and stop and ask; never reconstruct missing data." The approved definition of "complete" (PLAN.md, R1 to R8) needs NETWORK.md to answer five points. It answers three of them.

**What I checked** (read-only, after merging `origin/main` at `e3786b5`):
- **R1, R2, R5, R6, R7 are complete and consistent.**
  - `raw_evaluations.jsonl` holds one run, `vad_eval_run_20260913_001_20261003_075907`: 1 `run_context` record, 224 `scoring_clip` and 224 `tier2_pipeline_latency` records for each of the 6 operating points, and no `clip_failure` record. All 10 categories are covered.
  - `run_config.yaml` agrees with the `run_context` record.
  - `run.log` runs from "Loaded run configuration" (line 1) to "Completed Successfully" (line 3993), with one "Tier 2 Completed" line per operating point (lines 3987-3992).
  - The `03_report.ipynb` output shows exactly this run ID. Its `orchestrator` row is the quirk named in the approval.
- **R3 commit is fine.** `harness_version.txt` names `75e39d9`, committed at 06:38 UTC, before the run started at 07:59 UTC.
- **`02_tier2_live_pipeline.ipynb` is not the baseline run's log.** Its outputs belong to an earlier, aborted attempt, `…_20261003_074053`, which failed at 07:40 with `libc++.so.1: cannot open shared object file`. I will list it in the inventory as that attempt. `run.log` serves as R7.
- **R4 gaps.** `NETWORK.md` answers the VM shape and region, where both bots ran (Google Colab), "public internet", and "Impairment: None". It does **not** state:
  1. the Jitsi version;
  2. whether a TURN relay was used (or "no TURN relay");
  3. the run's start and end time in UTC (it gives only the date).
- **R3 difference.** The approved check allows changed tracked files only in `config/run_config.yaml`, `results/run_output/` and the notebooks the run rewrites. `harness_version.txt` also lists ` M run.log`, the repository-root log, which I take to be where you captured the console output.
- **R8 difference.** The approved check says the Jingle logs cover the run "from the first to the last record time stamp".
  - Both logs start at 07:59:11, which is 3.4 s after the `run_context` record (07:59:07.75), so the check fails by 3.4 s.
  - They do cover every clip record (first 08:00:04.52, last 11:34:52.93): the listener log ends 11:34:52.94, the speaker log 11:34:53.03.
  - The gap is consistent with signalling starting only after the results store opens (`orchestrator.py`: `store_run_context` runs before the bots join).

**Options:**
1. **(Recommended)** Do all three:
   - (a) Add the three missing facts to `NETWORK.md` on `main`. If a fact is unknown, write "not recorded"; SUMMARY.md then says so and cites that line.
   - (b) Confirm that the root `run.log` change was your capture of the console output, so R3 also allows it.
   - (c) Accept R8 as "the logs cover every clip record". I record the 3.4 s before the first clip as a fact, with sources.
2. For the start and end times only: let SUMMARY.md take them from `run.log` lines 1 and 3993 (direct citations, not reconstruction), instead of from NETWORK.md. The Jitsi version and the TURN statement are still needed from you.
3. Keep R3 and R8 exactly as approved. Then the raw folder fails them, and you would need a new run with the console log captured outside the repository and Jingle logging starting before the store opens. That second part would mean a harness change, which this WP does not allow, so R8 could not be met.

**Paused until answered:** all of `/wp-build WP-0.1`. The plan makes every requirement depend on a complete raw folder. No test, test helper, SUMMARY.md or registry row has been written.

**Owner answer:** Option 1 (session chat, 2026-10-03):
- (a) NETWORK.md on `main` (`a3420c3`) now states the Jitsi version, "No TURN relay" and start and end times (UTC). Merged into this branch (`c9932e3`).
- (b) Confirmed: the root `run.log` change was only the console capture from `tee`, so R3 allows it.
- (c) Accepted: R8 is met when the Jingle logs cover every clip evaluation record (08:00:04 to 11:34:52).

## BLK-017 — WP-0.9: the approval's ALLOW-EDIT lines name other files than the approved debt rows need; the unit-log copy misses the Colab GPU sessions
STATUS: RESOLVED
WP: WP-0.9  ·  Raised: 2026-10-04  ·  Session: https://claude.ai/code/session_01FYixR4QztgtCJqCD8TQGUi

**What I need:** (A) the four `ALLOW-EDIT` lines the approved debt table needs; (B) a complete copy of the Colab unit log, or your ruling on the missing sessions.

**Why:**
- (A) `docs/approvals/WP-0.9.md` (`0ce38e1`) accepts the per-row debt table (Q2), but its `ALLOW-EDIT` lines are:
  - `tests/aqis_lab/test_aqis_gate_v2.py` and `tests/aqis_lab/test_aqis_scoring_cli.py`, which exist but no planned row edits;
  - `tests/aqis_lab/test_aqis_gate.py` and `tests/aqis_lab/test_aqis_contracts.py`, which do not exist.

  The plan (question 2) needs these instead:

  | File | Rows |
  | --- | --- |
  | `tests/aqis_lab/test_aqis_ci.py` | DEBT-019 (job set at line 38) |
  | `tests/aqis_lab/test_aqis_recording_docs.py` | DEBT-026 (`OWNER_FACT_BREAKS`) |
  | `tests/aqis_lab/aqis_baseline_testutil.py` | DEBT-029, DEBT-030, DEBT-031 |
  | `tests/aqis_lab/test_aqis_tier2_baseline.py` | DEBT-029, DEBT-030, DEBT-031 |

  Without them those five rows cannot be closed as approved, and must-catch 2 cannot be met. I will not use the four granted lines, because they are outside the plan's change budget.
- (B) FR-0.9-02 reports the Colab units used so far "from the unit log". `docs/progress/WP-0.9/OC-0.9-01_units.csv` has two sessions:
  - `colab-2026-09-28-531d3d09acdc` (CPU, 0.0002 units);
  - `colab-2026-10-02-1e6bd941ec9e` (Tesla T4, 14:12:11Z to 14:14:22Z, 0.0432 units).

  The second matches the doctor report `docs/environment/doctor_colab_20261002T141212Z.json` (created 14:12:12Z). Committed evidence shows Colab GPU work that no row covers:
  - the T4 smoke run behind `data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar` (`BUNDLE.json`: created 2026-10-02T14:01:01Z, `elapsed_s` 374.45, GPU Tesla T4; its runner logs start at 14:01:04Z);
  - the `--gpu` bootstrap of OC-0.8-03.

  The memo would therefore report 0.0434 units, which looks understated. I will not estimate the missing sessions.

**What I tried:** compared each `ALLOW-EDIT` path with `tests/aqis_lab/` (`ls`); recomputed both unit-log rows from start, end and rate (both correct: 0.03629 h × 1.19 = 0.0432); read the Colab bundle's `BUNDLE.json` and runner logs.

**Options:**
1. (A) Replace the four `ALLOW-EDIT` lines in `docs/approvals/WP-0.9.md` on `main` with the four above. **Recommended.** It takes a minute and keeps the approved table.
2. (A) Move DEBT-019, 026, 029, 030 and 031 to a later WP you name. This needs no test edits, but carries the gaps into phase 1.
3. (B) Commit the full `MyDrive/AQIS_LAB/logs/units.csv` if it has more rows than the copy. **Recommended** if it does.
4. (B) If those sessions were run without `unitlog start`/`end`, say so in the approval. The memo then reports the logged 0.0434 units, lists the unlogged sessions by name as unmetered, and records your statement. Nothing is estimated.

**Paused until answered:** all WP-0.9 build work. The plan does not mark any part as independent of this answer.

**Owner answer:** Options 1 and 4 (`docs/approvals/WP-0.9.md` on `main`, `699acd5`, merged into this branch):
- (A) The four `ALLOW-EDIT` lines now name `tests/aqis_lab/test_aqis_ci.py`, `tests/aqis_lab/test_aqis_recording_docs.py`, `tests/aqis_lab/aqis_baseline_testutil.py` and `tests/aqis_lab/test_aqis_tier2_baseline.py`.
- (B) "Unit log: the logged 0.0434 units in docs/progress/WP-0.9/OC-0.9-01_units.csv is accepted; the Colab T4 smoke run (14:01Z, ~374 s) and OC-0.8-03 bootstrap are noted as unmetered sessions." The owner confirmed in the session chat (2026-10-04) that the committed CSV is the Drive file.
