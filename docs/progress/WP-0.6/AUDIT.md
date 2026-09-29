# AUDIT — WP-0.6, round 1

Auditor: wp-auditor · Date: 2026-09-29 · Commit audited: fbc6966c9fe78b185c0da240a0c9b52f61569f37 · Previous audited commit: first audit · Protocol: version 2

## Verdict: FAIL
CRITICAL: 1 · MAJOR: 1 (fixed 0, accepted as debt 0, open 1) · MINOR: 6 (open 6)

Most of the work is sound:
- The fast suite, the slow suite, the WP-0.6 network tests, the gate, the acceptance commands and CI on the audited commit all pass. I re-ran each of them myself.
- Must-catch behaviours 1, 3, 4 and 5 are protected: every break I made there was caught.
- I found no stubs, fake data or swallowed errors, and no existing test was changed.

Two findings block a pass:
- **F01 (CRITICAL, must-catch 2).** `trace` can print the checkout's *current* git commit or lock hash instead of the row's own, and every test still passes. Every test row comes from a run made at the current commit with the current lock, so the tests cannot tell the two apart. The shipped code reads the right values today. The gap is in the tests only, and the fix is test-only.
- **F02 (MAJOR, A15).** Three read-side integrity checks of the results store can each be removed with every test still passing: the `row_sha256` check, the part-file content-against-name check, and the per-row check in `results query`.

## Scope of this audit
First audit of WP-0.6. It covers items A1 to A15 on the whole WP diff `6ad251b..fbc6966`: 42 files, +4466 −14. It also covers the full suites, the gate, CI, the complete must-catch proof and 10 exploratory breaks in the new code.
- **Code breaks:** made only in a throwaway copy of the repository under `/tmp/claude-0/.../scratchpad/mc/repo`, with its own `.git`. Each file was restored with `git checkout` after its break, and `git status` was clean at the end.
- **The real working tree:** never modified (`git status --short` empty before this report).

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.5 is `MERGED` in `docs/progress/STATUS.md`. The branch is `claude/relaxed-davinci-iwk5gi`, not `main`. `git show origin/main:docs/approvals/WP-0.6.md` starts `STATUS: APPROVED`, with CONDITIONS: questions 1-16 as recommended, cores 2-3 reserved, DEBT-008 closed |
| A2 Requirement coverage | PASS | Every FR has code, tests named after it that pytest collects, and an `EVIDENCE.md` entry. Collected counts: FR-0.6-01 20, -02 22, -03 7, -04 16, -05 13, -06 3. All 117 test names cited in the new registry rows and headers are collected (script over `pytest --collect-only`) |
| A3 Acceptance commands | PASS | **AT-0.6-01:** `bash aqis_lab/deploy/oracle_setup.sh --dry-run` gives six `step N/6` lines, then `DRY RUN: nothing was changed`, exit 0, and the tree stays clean. The fast suite passes (A4). **AT-0.6-02:** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6` gives `Findings: 0`, `0 findings: OK (0.5 s)`, exit 0 |
| A4 Test suites and CI | PASS | **Fast:** `1633 passed, 24 deselected in 192.39s`, exit 0. **Slow:** (`slow and not network …`) `3 passed`. **WP-0.6 network** (`-k FR_0_6 -m "network and not oracle"`): `4 passed`. **Lock, bootstrap and runner-overhead slow/network tests** (the lock and runner changed): `16 passed`. **CI on `fbc6966`:** push run 241 and PR run 242 `success`, both jobs `lab` and `harness-regression`. The rclone step, fast suite and gate step all `success` (GitHub API). The job log itself could not be read: its storage host `productionresultssa12.blob.core.windows.net` is blocked by the proxy |
| A5 Test integrity | PASS | `git diff --name-status 6ad251b HEAD -- tests/` lists only added files (`A`). There are no `skip`, `xfail`, `skipif`, `importorskip` or `audit-allow` entries in the added tests. `test_FR_0_6_01_second_run_changes_nothing` (new in this WP) got a 1.1 s sleep in `920960c`. That is disclosed and justified in the test (see F06), and it is not a weakened pre-existing test |
| A6 Must-catch proof | **FAIL** | 16 effective breaks: 14 caught, 2 survive, both in must-catch 2 (MC2b, MC2c). See the table below and F01 |
| A7 Compromise scan | PASS | The gate reports 0 findings and 0 `audit-allow`. A grep of the added lines in `aqis_lab tools config` finds no TODO, FIXME, placeholder, bare `except`, `pass` or `NotImplementedError`. I read every new function: the only swallowed exception is `ProcessLookupError` for a thread that ended (`timing/cores.py`), which is justified. Nothing is hard-coded to satisfy a test. The test doubles are the Oracle CPU tree and an rclone `alias` for Drive, both allowed and both only in `tests/` |
| A8 Scope diff | PASS (see F07) | Changed files match the plan's change budget. No GUARDED or NEVER path changed: `.github/workflows/aqis-lab-ci.yml`, `config/aqis_lab/`, `requirements/aqis_lab/` and `tests/aqis_lab/` are lab-owned. Existing functions in `platform.py`, `doctor.py`, `runner/run.py` and `score.py` are unchanged apart from the budgeted ones. Small deviations are listed in F07 |
| A9 Capabilities | PASS | Every new module has the standard header. `oracle_setup.sh` omits CONTRACTS, as the accepted `dev_bootstrap.sh` does. The registry diff adds 18 rows. The 4 changed rows only append text (word diff): CAP-ENV-002, CAP-SCORE-005, CAP-DOCTOR-001, CAP-RUN-007. No row was removed. The linked tests exist and run (A2) |
| A10 Contracts | PASS | Stored run cards are validated with `validate_run_card` on add and on trace. The stored `run_card.json` equals the source byte for byte (`test_FR_0_6_02_add_run_folder_writes_partition_by_run_card`). Score folders are checked against score table 1.0 metadata and columns. The store schema in `RESULTS_STORE.md` is kept equal to the code by a test. The `run_card.v1.json` mode enum is fully mapped to timing or batch |
| A11 Environment parity | PASS | New code has no absolute paths (grep). The new CPU facts live in `aqis_lab/platform.py`. `duckdb==1.5.6` is pinned with hashes, and `test_FR_0_0_03_regeneration_is_reproducible` and `…_lock_installable_with_plain_pip` pass. `.venv` is Python 3.13.12, matching the Colab probe. duckdb's licence classifier is `MIT License`. I also checked that uv 0.8.17 accepts the exact step-4 target for the Oracle VM: `uv pip compile <26 pins> --only-binary :all: --python-platform aarch64-manylinux_2_39 --python-version 3.13` exits 0. Both owner-run checks are listed with commands and expected output. One robustness issue is in F05 |
| A12 Reproducibility and traceability | FAIL (via F01) | Row IDs are SHA-256 over the canonical identity (recomputed in the tests). Rows carry `run_card_id` and `clip_id`, and part files are content-addressed. Trace's commit and lock-hash lines are not protected (F01) |
| A13 Errors and logging | PASS with MINOR findings | Failures raise or print `ERROR:` with the documented exit codes, and I found nothing that fails silently. Some error paths end in a traceback or a misleading message (F04, F05). The read path accepts some damaged states (F02, F03) |
| A14 Documentation, licences, data | PASS (see F03) | `RESULTS_STORE.md`, `ORACLE_RUNBOOK.md`, `DOCTOR.md` and `RUNNER.md` are updated. `EVIDENCE.md` covers every FR, AT, the must-catch list, CI and the owner-run checks. Its outputs match my re-runs: same counts, same dry-run text, same gate output. The duckdb licence is recorded in PLAN.md finding 4. The data is the committed smoke pack only; no personal data |
| A15 Exploratory breaks | 10 made, 3 survive | See the table below. X1 to X3 survive (F02) |

## Must-catch proof (A6)
Every break was made in the throwaway copy. I then ran `pytest tests/aqis_lab -m "not slow and not gpu and not colab and not oracle and not network" -k "<named tests>"` there.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Store refuses to overwrite rows | MC1a: a conflicting row is appended to `new` instead of `conflicts` (`store.py`, `add_batch`) | `test_FR_0_6_02_refuses_to_overwrite_existing_rows` | Caught |
| 1 | MC1b: `publish` uses `os.replace` instead of `os.link` | `test_FR_0_6_02_existing_files_never_replaced` | Caught |
| 1 | MC1c: `existing = {}` (stored rows not read before writing) | `…_refuses_to_overwrite_existing_rows`, `…_existing_files_never_replaced` | Caught |
| 2 Trace returns exact card, manifest version, clip, commit, lock hash | MC2a: trace loads the first stored partition's card, not the row's | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock`, `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card` | Caught |
| 2 | MC2b: the `git_commit:` line prints `git rev-parse HEAD` of the checkout instead of `card['git']['commit']` (`trace.py:70`) | none: `2 passed`. A wider run (`-k "FR_0_6 or FR_0_5 or trace or results"`) also gives `278 passed` | **SURVIVES** (F01) |
| 2 | MC2c: the `lock_sha256:` line prints the SHA-256 of the lock file on disk instead of `card['lock']['sha256']` (`trace.py:72`) | none: `2 passed`, and `278 passed` on the wider run | **SURVIVES** (F01) |
| 3 Timing runs pinned to reserved cores | MC3a: timing mode pinned to the batch CPUs | `test_FR_0_6_04_timing_process_pinned_to_reserved_cores` | Caught |
| 3 | MC3b2: only the first-listed (main) thread is ever pinned, and the read-back is disabled | `…_timing_process_pinned_to_reserved_cores`, `…_batch_run_kept_off_reserved_cores` | Caught |
| 3 | MC3b3: only the main thread is pinned, read-back left in place | the same two tests | Caught |
| 3 | MC3c: the runner checks the plan but does not pin | `…_batch_run_kept_off_reserved_cores` | Caught |
| 3 | MC3d: batch CPUs = every online CPU (reserved not excluded) | `…_batch_run_kept_off_reserved_cores` | Caught |
| 4 Sync never deletes remote files | MC4a: `"sy" + "nc"` instead of `"copy"` (built so the constant scan cannot see it) | `test_FR_0_6_05_never_deletes_remote_files`, `…_command_is_copy_only` | Caught (by the real rclone test, not only the scan) |
| 4 | MC4b: `--immutable` removed | `…_never_replaces_a_remote_file`, `…_command_is_copy_only` | Caught |
| 4 | MC4c: `"--delete-" + "excluded"` added to the argv | `…_command_is_copy_only` | Caught |
| 5 Setup stops on unsupported architecture or OS | MC5a: the architecture check prints a warning instead of `fail` | `test_FR_0_6_01_refuses_unsupported_architecture` (both parameters) | Caught |
| 5 | MC5b: the OS is compared by `ID` only (any Ubuntu version passes) | `test_FR_0_6_01_refuses_unsupported_operating_system` | Caught |

- **MC3b was not a valid break.** My first variant pinned one thread per pass (`for tid in new[:1]`). `pin_process` repeats its listing until no thread is left, so it still pinned every thread and both tests correctly passed. I replaced it with MC3b2 and MC3b3, which really pin only one thread.
- **MC2b and MC2c really produce a wrong trace.** I checked this in the copy after each ran clean:
  - **MC2b:** after a later commit in the copy's own `.git`, `trace` printed `git_commit: a0362c81ab52…` for a row whose run card says `fbc6966c9fe7…`.
  - **MC2c:** after the lock file changed on disk, `trace` printed `lock_sha256: d1700b78…` for a row whose card says `5cb02130…`.

## Exploratory breaks (A15, at most 10)
Each was run against all 108 fast WP-0.6 tests (`-k FR_0_6`).

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1: `verify_record` no longer checks `row_sha256` | `aqis_lab/results/store.py:259` | **Yes**: `108 passed` | MAJOR (F02) |
| X2: `read_partition` no longer checks a part file's content against its name | `aqis_lab/results/store.py:278` | **Yes**: `108 passed` | MAJOR (F02) |
| X3: `query_run_card` no longer checks the rows it returns | `aqis_lab/results/views.py:93-94` | **Yes**: `108 passed` | MAJOR (F02) |
| X4: `trace_row` no longer calls `verify_record` | `aqis_lab/trace.py:48` | No: `test_FR_0_6_03_row_not_matching_its_id_is_reported` | — |
| X5: stale-partial cleanup also deletes `.parquet` files | `aqis_lab/results/store.py`, `_remove_stale_partials` | No: 9 tests fail | — |
| X6: sync reports success when rclone refused to replace a differing remote file | `aqis_lab/sync.py`, `run_sync` | No: `test_FR_0_6_05_never_replaces_a_remote_file` | — |
| X7: sync no longer requires `AQIS_LAB/results` to exist | `aqis_lab/sync.py`, `run_sync` | No: `test_FR_0_6_05_refuses_when_remote_results_folder_missing` | — |
| X8: setup continues after naming packages without a build | `aqis_lab/deploy/oracle_setup.sh`, step 4 | No: `test_FR_0_6_01_missing_build_names_the_package` | — |
| X9: a refused pin is ignored and the read-back disabled | `aqis_lab/timing/cores.py`, `pin_process` | No: `test_FR_0_6_04_pin_failure_is_an_error` | — |
| X10: the doctor `cores` row passes an impossible reservation | `aqis_lab/doctor.py`, `_check_cores` | No: `test_FR_0_6_04_doctor_oracle_cores_row` | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.6-F01 | CRITICAL | A6, A12; must-catch 2 | No test protects trace's **commit and lock hash** lines. Every stored row in `test_aqis_trace.py` comes from a `smoke_run` made in this checkout, so the run card's `git.commit` and `lock.sha256` always equal the checkout's current commit and lock hash. A trace that prints the current commit or the current lock hash instead of the row's own passes both must-catch tests. The full card printed below the fields is compared, but the named `git_commit:` and `lock_sha256:` lines are not independent of the checkout. The code at `trace.py:70,72` is correct today | Breaks MC2b and MC2c survive (`2 passed`, and `278 passed` on the wider run). The demonstration in the copy printed the wrong commit and the wrong lock hash (above) | **Fix now (tests only).** Add a stored row whose run card's `git.commit` and `lock.sha256` differ from the checkout's, then assert trace prints the card's values. Either run the runner in a throwaway git tree at another commit with a changed lock, or build a valid card with another commit and lock hash through the real card builder and `compute_run_card_id`. Then MC2b and MC2c must fail. Re-run the must-catch proof |
| WP-0.6-F02 | MAJOR | A15, A13 | Three read-side integrity checks have no test, and each can be removed with every WP-0.6 test passing. They are the `row_sha256` check (all readers), the part-file content-against-name check (`add`), and the per-row check in `results query`. Without them, a damaged or hand-edited row or part file reads as valid: `query` and `trace` exit 0, and `add` counts the rows as "already stored". `RESULTS_STORE.md` promises these checks ("Any difference is an integrity error, never a silent skip") | X1, X2 and X3 survive, each `108 passed` | **Fix now.** Add tests that change a stored row's `row` text while keeping its ID, rewrite a part file in place, and then run `results query`, `trace` and `results add`. Each must give `ERROR:` and exit 1. X1 to X3 must then fail |
| WP-0.6-F03 | MINOR | A13, A14 | `query` and `trace` do not do all the reader checks the document lists. (1) They never compare a part file's content with its name. After I rewrote a part file in place (`added_by`, `source_sha256` changed), `results query` printed the altered `added_by` with exit 0 (60 lines), and `trace` exited 0. Only `results add` refused it (exit 1). (2) The `results` view joins every `run_card.json` by its `run_card_id` without checking the folder. A copy of a card in another partition folder makes `results query` print every row twice with exit 0 (120 lines, 60 unique). The traced fields stay correct: they come from the validated card and the self-hashed identity | `RESULTS_STORE.md:65`; `views.py:75, 89`. Scratchpad stores `t1` and `t3` | **Fix now, together with F02** (small). Make `query` and `trace` use the same file check as `add` (`read_partition`), and read stored columns from `result_rows`, or check the card folder. Otherwise correct the document. Else accept as debt, target WP-0.7 |
| WP-0.6-F04 | MINOR | A13 | Some error paths end in a traceback or hide the cause. (1) A truncated part file makes `results query` and `trace` end with `_duckdb.InvalidInputException` and a Python traceback (exit 1), not `ERROR:`. One damaged file anywhere breaks both commands for every run card. (2) If `rclone lsf <remote>:AQIS_LAB` fails for any reason, such as an expired Drive token, sync reports "`AQIS_LAB` not found … must already exist" and drops rclone's own error text. (3) `subprocess.run(..., timeout=TIMEOUT_S)` for the copy does not catch `TimeoutExpired`. (4) `STORE.json` is created before the store lock is taken, so two first adds at once can fail with a traceback or a misleading "refusing to replace STORE.json". All of these fail loudly. None writes anything wrong | Truncation test in scratchpad `t2`: `query exit 1`, `trace exit 1`, both `Traceback … InvalidInputException`. By reading: `sync.py:90-94`, `sync.py:114-115`, `store.py:211-223, 337-338` | Accept as debt, target WP-0.7, or fix now alongside F02 |
| WP-0.6-F05 | MINOR | A11, A13 | `oracle_setup.sh` fails when started from outside the repository root. It derives `ROOT` from its own location, but the step-6 config reads `"$VENV/bin/python" -m aqis_lab.oracle_config get …` run in the caller's directory, where `aqis_lab` cannot be imported. Steps 1 to 5 pass and `.venv` is built, then it stops with the misleading `ERROR: cannot read paths.work_dir from config/aqis_lab/oracle.yaml.` The real cause is `No module named 'aqis_lab'`. From the root it works. The runbook says to run from `~/aqis`, so the owner should not hit this | `oracle_setup.sh:197-198`. A run from `/` in a throwaway tree exits 1 as described, and the same tree run from its root reaches the doctor | Fix now (run the two reads with `cd "$ROOT"`), or accept as debt, target WP-0.7 |
| WP-0.6-F06 | MINOR | A2 (FR-0.6-01 idempotency) | Two setup runs that start less than a second apart fail on the second run: the doctor report name has one-second resolution (FR-0.5-02) and is never replaced, so the doctor exits 2. State is unchanged. The builder measured 3 of 8 back-to-back pairs colliding with a warm cache, and the test sleeps 1.1 s. This is disclosed in EVIDENCE finding 5 | `test_aqis_oracle_setup.py:294-297`, commit `920960c` | Accept as debt, target WP-0.9 (or whichever WP may change the FR-0.5-02 name format) |
| WP-0.6-F07 | MINOR | A8 | Deviations from the approved plan. (1) `parse_cpu_list` and three constants were added to `aqis_lab/platform.py`. The change budget named only `online_cpus`, `core_siblings`, `thread_ids` and `thread_affinity`. It is in the header and the registry, but not in EVIDENCE's deviation list. (2) `oracle_setup.sh` has no `--config` option (disclosed). (3) The runner log line is `cores:`, not `session N cores:` (disclosed, to keep an existing test unchanged). (4) The plan promised "a test keeps `paths.results_store` equal to that default". No test references `store.DEFAULT_STORE`, so `results add` and `sync` could drift to different folders unnoticed | `platform.py:299`; `grep -rn DEFAULT_STORE tests/aqis_lab` finds nothing | Accept (1) to (3) as recorded deviations. Add the (4) test now or accept as debt, target WP-0.7 |
| WP-0.6-F08 | MINOR | A2 (FR-0.6-04 handoff) | Only the pinning function exists for timing runs; no timing run exists yet, as the approved plan says. The WP-0.7 spec does not say its real-speed feeder must call `aqis_lab.timing.cores.pin_for_mode`. `ORACLE_RUNBOOK.md:95` describes timing runs as already pinned. If WP-0.7 forgets the call, timing runs on Oracle would run unpinned with no error | WP-0.7 spec (grep: no mention of pinning or reserved cores); `docs/runner/RUNNER.md` "they arrive with WP-0.7" | Accept as debt, **target WP-0.7**: a debt row saying the real-speed feeder calls `pin_for_mode(<timing mode>)`, with a test that reads each thread's affinity |

## Convergence (round 3 onwards)
Not applicable: round 1.

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 6 | F01 (must-catch 2) |

## For the owner
- **What blocks a pass:** F01 (CRITICAL) and F02 (MAJOR). Both are fixed with tests. F01 needs no production change. F02 may need none either.
- **audit-allow lines:** none. The gate reports `Exempted lines (# audit-allow): 0`.
- **Approvals used:** `docs/approvals/WP-0.6.md` on `main` (`6ad251b`): questions 1-16 as recommended, reserved cores 2-3, DEBT-008 closed.
- **Debt accepted so far:** none for WP-0.6. DEBT-008 (from WP-0.3) is closed in this WP. I confirmed the fix: `test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2` passes in the fast suite.
- **Owner-run checks still pending:**
  - **OC-0.6-01:** on the Oracle VM, `oracle_setup.sh --dry-run`, then `oracle_setup.sh`, then `pytest -m oracle`. Commit the doctor JSON and `OC-0.6-01_oracle.txt`.
  - **OC-0.6-02:** configure the rclone remote, then `run`, `results add` and `sync --dry-run`. Commit `OC-0.6-02_sync_dry_run.txt`.
  - Both are expected only after the audit passes, at the tag `aqis-lab-wp-0.6-oracle-1`.
  - The aarch64 path has not run on real hardware. I confirmed only that every lock pin resolves to a binary for `aarch64-manylinux_2_39`, the exact target step 4 builds on the probe's glibc 2.39.
- **A note on the probe:** `docs/environment/oracle_probe.txt` is shorter than the probe the plan asked for. It has no `ID`/`VERSION_ID` or threads-per-core lines, and no git, uv or GitHub reachability lines.
  - The builder read `ubuntu:24.04` from `PRETTY_NAME` and one thread per core from the Neoverse-N1 model. Both are reasonable.
  - OC-0.6-01 will confirm them: the doctor `cores` row reads the real `thread_siblings_list`, and step 3 needs GitHub for uv's Python download.
