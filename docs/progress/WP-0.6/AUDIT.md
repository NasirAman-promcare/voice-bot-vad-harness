# AUDIT — WP-0.6, round 2

Auditor: wp-auditor · Date: 2026-09-30 · Commit audited: 3501ca8396ca5e0e181bc6cb36c5bd3def97c170 · Previous audited commit: fbc6966c9fe78b185c0da240a0c9b52f61569f37 · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 open (round-1 F01 fixed) · MAJOR: 0 open (round-1 F02 fixed; fixed 1, accepted as debt 0, open 0) · MINOR: 1 new and open (F09); of round 1's six, F03, F05 and F07 (4) are fixed, F04, F06 and F08 are accepted as debt (DEBT-015 to DEBT-017), and F07 (1) to (3) are recorded deviations

Both round-1 blockers are fixed, and I confirmed each fix by breaking the code:
- **F01 (CRITICAL, must-catch 2) is fixed.** The new test stores a run card that names an earlier commit and that commit's lock hash. Round 1's surviving breaks MC2b (trace prints the checkout's commit) and MC2c (trace prints the lock file's current hash) now fail `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash`.
- **F02 (MAJOR) is fixed.** Round 1's breaks X1, X2 and X3 each fail a named test when re-made on the new code.
- **The complete must-catch proof passes:** all 16 breaks are caught.
- **Suites, gate, acceptance and CI:** the fast, slow and WP-0.6 network suites, the gate and both acceptance commands pass on my own runs. CI is green on the audited commit.

One new MINOR finding (F09). Two of my six exploratory breaks in the new reader code survive: `connect` checking only the first part file, and dropping the schema-version check. Under either break, every returned row is still checked. No result value, row identity, run card, commit or lock hash can come out wrong. It does not block the pass.

## Scope of this audit
This is a re-audit (round 2). It covers:
- each round-1 finding;
- items A1 to A15 on the diff `fbc6966..3501ca8`: 17 files, +414 −23;
- production changes, which are limited to `aqis_lab/results/views.py` (`connect`), `aqis_lab/results/store.py` (new `check_part_file`, called by `read_partition`), two lines of `aqis_lab/deploy/oracle_setup.sh`, and header lines in `aqis_lab/trace.py` and `aqis_lab/commands/results.py`;
- the full suites, the gate, CI and the complete must-catch proof.

Code that passed round 1 and has not changed was not searched again.

How I made the code breaks:
- **Where:** only in a fresh throwaway copy under `/tmp/claude-0/.../scratchpad/a2/repo`, with its own `.git`, its remote removed and `.venv` linked. I did not reuse the builder's break script from the same scratchpad; `audit_r2_breaks.py` is my own.
- **Validity:** each break is one exact text change that must match exactly once.
- **Clean-up:** each file was restored with `git checkout` after its break, and the copy's `git status` was clean after every break and at the end.
- **The real working tree:** never modified. `git status --short` was empty before I wrote this report.

## Round-1 findings
| ID | Round-1 severity | Status now | Evidence |
| --- | --- | --- | --- |
| WP-0.6-F01 | CRITICAL | **Fixed** | `historical_run` in `tests/aqis_lab/test_aqis_trace.py` copies a real run. The card names the parent of the last commit that changed `requirements/aqis_lab/phase0.txt` and that commit's lock SHA-256, with `run_card_id` recomputed by `compute_run_card_id` and checked by `validate_run_card`. The test asserts that both values differ from the checkout's, then traces all 60 rows and compares every field and the full card. MC2b and MC2c each give `1 failed, 9 passed`, and the failing test is the new one. In round 1 both survived |
| WP-0.6-F02 | MAJOR | **Fixed** | Re-made on the new code: X1 (`row_sha256` check removed) fails `test_FR_0_6_02_add_rejects_tampered_stored_rows` and `…_query_trace_and_add_reject_a_damaged_store[row-text]`. X2 (content-against-name check removed, now in `check_part_file`, so add, query and trace are all affected) fails `…_add_rejects_tampered_stored_rows`, `[file-in-place]` and `[truncated]`. X3 (`query_run_card` row check removed) fails `[row-text]` |
| WP-0.6-F03 | MINOR | **Fixed** | `connect` now checks every stored card with `load_stored_card` (valid, and in its own folder) and every part file with `check_part_file`. The test's four cases each give `ERROR:`, exit 1, empty stdout and no traceback from `results query`, `trace` and `results add` (`add` is excluded for the card copy, by design). My breaks X14 and X18 (weaker card checks) are caught. I also probed the sibling case with real inputs: a part file copied into another run card's folder. `query` of the folder that received it exits 1 ("run_card_id … differs from its identity's"), `trace` exits 1 ("stored 2 times"), and `add` of that run exits 1. See the DuckDB note under "For the owner" |
| WP-0.6-F04 | MINOR | Accepted as debt: DEBT-015, target WP-0.7 | Approval round-2 condition on `main` (`73d1198`) and the row in `docs/progress/DEBT.md`. Item (1) is done: a truncated part file now gives `ERROR: … no longer matches the SHA-256 in its name`, exit 1 (`[truncated]` case) |
| WP-0.6-F05 | MINOR | **Fixed** | Both step-6 reads run `cd "$ROOT" && …`. `test_FR_0_6_01_runs_from_any_directory` passes (slow, network). My break X16 (only the second read back in the caller's folder) fails it with `ERROR: cannot read paths.doctor_reports from config/aqis_lab/oracle.yaml.` `cd / && bash …/oracle_setup.sh --dry-run` exits 0 |
| WP-0.6-F06 | MINOR | Accepted as debt: DEBT-016, target WP-0.9 | Approval round-2 condition and the DEBT row |
| WP-0.6-F07 | MINOR | (4) **fixed**; (1) to (3) recorded deviations | `test_FR_0_6_02_default_store_equals_oracle_results_store` fails when `DEFAULT_STORE` moves (my break F07-4: `1 failed, 53 passed`). (1) to (3) are recorded as accepted deviations in `FIXES.md` and in the round-2 table in `EVIDENCE.md`. The approval text names only the (4) fix; being MINOR, (1) to (3) need no further approval |
| WP-0.6-F08 | MINOR | Accepted as debt: DEBT-017, target WP-0.7 | Approval round-2 condition and the DEBT row, which says WP-0.7 must call `pin_for_mode(<timing mode>)` in the real-speed feeder, with an affinity test |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.5 is `MERGED` in `docs/progress/STATUS.md`. The branch is `claude/relaxed-davinci-iwk5gi`, not `main`. `git show origin/main:docs/approvals/WP-0.6.md` starts `STATUS: APPROVED`, and its round-2 condition names F01, F02, F03, F05 and F07 to fix, and F04, F06 and F08 as debt |
| A2 Requirement coverage | PASS | The new tests are collected: the trace commit/lock test (1 item), `…_add_rejects_tampered_stored_rows` (1), `…_query_trace_and_add_reject_a_damaged_store` (4), `…_runs_from_any_directory` (1) and `…_default_store_equals_oracle_results_store` (1). All 31 test names cited in the changed registry rows and headers are collected (`pytest --collect-only` compared with the names in the diff: none missing). `EVIDENCE.md` has a round-2 table for every finding |
| A3 Acceptance commands | PASS | **AT-0.6-01:** `bash aqis_lab/deploy/oracle_setup.sh --dry-run` gives six `step N/6` lines and `DRY RUN: nothing was changed`, exit 0, with the tree still clean. It also works from `/`. The fast suite passes (A4). **AT-0.6-02:** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6` gives `Findings: 0`, `0 findings: OK (0.6 s)`, exit 0 |
| A4 Test suites and CI | PASS | **Fast:** `1640 passed, 25 deselected in 326.57s`, exit 0. **Slow** (`slow and not gpu and not colab and not oracle and not network`): `3 passed, 1662 deselected`. **WP-0.6 network** (`-k FR_0_6 -m "network and not oracle"`): `5 passed, 1660 deselected`, including `test_FR_0_6_01_runs_from_any_directory`. **CI on `3501ca8`** (GitHub API): push run 248 and pull-request run 249 are `success`. Both jobs (`lab`, `harness-regression`) and every step are `success`, including rclone, the fast suite and the gate with `--wp` |
| A5 Test integrity | PASS | `git diff fbc6966 HEAD -- tests/` has no removed lines. Every touched test file was created by this WP (`A` against `6ad251b`). No `skip`, `xfail`, `importorskip`, `audit-allow` or sleep was added. The new slow and network marks sit on a setup test that builds a real `.venv`, as its siblings do |
| A6 Must-catch proof | PASS | 16 breaks, 16 caught (table below). MC2b and MC2c, which survived in round 1, are now caught |
| A7 Compromise scan | PASS | The gate gives 0 findings and 0 `audit-allow`. A grep of the added lines in `aqis_lab tools config tests` finds no TODO, FIXME, placeholder, bare or broad `except`, `pass`, `NotImplementedError` or mocks. `check_part_file` is the old `read_partition` block moved without change (a `diff` of the de-indented blocks is identical). `connect` raises `StoreIntegrityError`, and nothing is swallowed. Nothing is hard-coded to satisfy a test |
| A8 Scope diff | PASS | The changes match the `FIXES.md` change budget. The one budget change (`check_part_file` in `store.py`) is disclosed with its reason, which I checked: running all of `read_partition` in `connect` would have hidden the second case of the round-1 test `test_FR_0_6_03_row_not_matching_its_id_is_reported`. `trace.py` and `commands/results.py` changed only in header lines. The only other paths changed are `docs/progress/`, `docs/capabilities/REGISTRY.md` and `docs/approvals/WP-0.6.md`; the approval change is the owner's commit `73d1198` on `main`, merged in `9dfd730`. No guarded or NEVER path changed |
| A9 Capabilities | PASS | The registry has 105 rows before and after. The five changed rows (CAP-RESULTS-002, -005, -006, CAP-TRACE-001, CAP-ENV-007) only gain text: the word diff removes nothing except final tokens that gained a comma or semicolon. The headers have change-log lines. `test_FR_0_0_08_module_headers_match_registry` passes in the fast suite |
| A10 Contracts | PASS | No contract changed in round 2. `connect` validates each stored card through `load_stored_card`, which calls `validate_run_card` |
| A11 Environment parity | PASS | No absolute paths in the added production lines (grep). No new dependency; the lock is unchanged (`5cb02130…`). `.venv` is Python 3.13.12 and the Colab probe gives 3.13. F05 is fixed. See the note on shallow clones below |
| A12 Reproducibility and traceability | PASS | F01 is fixed. Trace's commit and lock-hash lines are now protected by a test whose stored card differs from the checkout in both |
| A13 Errors and logging | PASS | A damaged store (row text changed, file changed in place, truncated file, card copy) gives `ERROR:` and exit 1 from `query`, `trace` and `add`, with no traceback (tested). DEBT-015 still records the open error-message items (2) to (4) |
| A14 Documentation, licences, data | PASS | `FIXES.md` and the round-2 section of `EVIDENCE.md` match my re-runs: fast `1640 passed, 25 deselected`, slow `3 passed`, network `5 passed`, gate `0 findings`, CI runs 246 and 247 green on `719d7f4` (and 248 and 249 on `3501ca8`). DEBT-015 to DEBT-017 are written as the approval says. No new data |
| A15 Exploratory breaks | 6 made, 2 survive | Table below. X13 and X15 survive (F09, MINOR). Counting the four round-1 re-checks as well, the total is 10 |

## Must-catch proof (A6)
Every break was made in the throwaway copy. I then ran `pytest tests/aqis_lab -m "not slow and not gpu and not colab and not oracle and not network" -k <FR group>`, where the FR group is `FR_0_6_02`, `FR_0_6_03`, `FR_0_6_04`, `FR_0_6_05` or `FR_0_6_01`. The set is round 1's, re-made on the current code.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Store refuses to overwrite rows | MC1a: a conflicting row goes to `new` instead of `conflicts` (`add_batch`) | `test_FR_0_6_02_refuses_to_overwrite_existing_rows` (also `…_add_exit_codes`, `…_add_and_query_exit_promptly`) | Caught |
| 1 | MC1b: `publish` unlinks an existing target, then links (so it replaces files) | `test_FR_0_6_02_existing_files_never_replaced` | Caught |
| 1 | MC1c: `existing = {}` (stored rows not read before writing) | `…_refuses_to_overwrite_existing_rows`, `…_existing_files_never_replaced` (10 failed) | Caught |
| 2 Trace returns exact card, manifest version, clip, commit, lock hash | MC2a: trace loads the first stored partition's card, with the card/row check off | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock`, `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card` | Caught |
| 2 | MC2b: the `git_commit:` line prints `git rev-parse HEAD` of the checkout | `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash` (`1 failed, 9 passed`) | **Caught** (survived in round 1) |
| 2 | MC2c: the `lock_sha256:` line prints the SHA-256 of the lock file on disk | `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash` (`1 failed, 9 passed`) | **Caught** (survived in round 1) |
| 3 Timing runs pinned to reserved cores | MC3a: timing mode pinned to the batch CPUs | `test_FR_0_6_04_timing_process_pinned_to_reserved_cores` | Caught |
| 3 | MC3b2: only the first-listed thread is pinned, and the read-back checks only that thread | `…_timing_process_pinned_to_reserved_cores`, `…_batch_run_kept_off_reserved_cores` | Caught |
| 3 | MC3b3: only the first-listed thread is pinned, read-back left in place | the same two tests | Caught |
| 3 | MC3c: the runner builds and logs the plan but does not pin (`runner/run.py`) | `…_batch_run_kept_off_reserved_cores` | Caught |
| 3 | MC3d: batch CPUs = every online CPU (reserved not excluded) | `…_batch_run_kept_off_reserved_cores` (5 failed) | Caught |
| 4 Sync never deletes remote files | MC4a: `"sy" + "nc"` instead of `"copy"` | `test_FR_0_6_05_never_deletes_remote_files` (real rclone), `…_command_is_copy_only` | Caught |
| 4 | MC4b: `--immutable` removed | `…_never_replaces_a_remote_file`, `…_command_is_copy_only` | Caught |
| 4 | MC4c: `"--delete-" + "excluded"` added to the argv | `…_command_is_copy_only` | Caught |
| 5 Setup stops on unsupported architecture or OS | MC5a: the architecture check prints a warning instead of `fail` | `test_FR_0_6_01_refuses_unsupported_architecture[False]` and `[True]` | Caught |
| 5 | MC5b: the OS is compared by `ID` only (any version of a listed ID passes) | `test_FR_0_6_01_refuses_unsupported_operating_system` | Caught |

## Exploratory breaks (A15, at most 10)
Only in code changed since `fbc6966`. Each was run against `-k "FR_0_6_02 or FR_0_6_03"` (fast markers, 47 tests), except X16 (`-m "slow and network" -k runs_from_any_directory`). The four round-1 re-checks (F02-X1, F02-X2, F02-X3, F07-4) are listed under "Round-1 findings".

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X13: `connect` checks only the first part file (`parts[:1]`) | `aqis_lab/results/views.py`, `connect` | **Yes**: `47 passed` | MINOR (F09) |
| X14: `connect` checks only the first stored card (`cards[:1]`) | `aqis_lab/results/views.py`, `connect` | No: `…_reject_a_damaged_store[card-copy]` | — |
| X15: `check_part_file` drops the schema-version and columns check | `aqis_lab/results/store.py`, `check_part_file` | **Yes**: `47 passed` | MINOR (F09) |
| X16: step 6 reads `paths.doctor_reports` in the caller's folder again | `aqis_lab/deploy/oracle_setup.sh` | No: `test_FR_0_6_01_runs_from_any_directory` (`ERROR: cannot read paths.doctor_reports …`); an unbroken control run passes | — |
| X17: `read_partition` (the add path) reads part files without `check_part_file` | `aqis_lab/results/store.py`, `read_partition` | No: `…_add_rejects_tampered_stored_rows`, `[file-in-place]`, `[truncated]` | — |
| X18: `connect` checks the card stored under the card's own ID, not the file in the folder | `aqis_lab/results/views.py`, `connect` | No: `[card-copy]` | — |

**What the two survivors let through.** I tested this on a real two-run-card store in the scratchpad (`a2/demo_x13`, `a2/demo_x15`):
- **X13:** I changed the later part file in place (`added_by`, `source_sha256`, name kept). The real code gives `ERROR:` and exit 1 from both `results query` and `trace`. With X13 applied, `query` exits 0 and prints 60 rows with `added_by 'someone else'` and `source_sha256 00000000…`, and `trace` exits 0.
- **X15:** a part file marked schema `2.0`, renamed after its own content. The real code gives exit 1. With X15 applied, `query` exits 0 with 60 rows.

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.6-F09 | MINOR | A15, A13 | Two file checks on the new read path have no test that fails without them. (1) `connect` checks every part file, but every damaged-store test uses a store with exactly one part file (`part_file` asserts it), so checking only the first file passes every test. (2) The schema-version and columns check in `check_part_file` has no test at all. Without either check, `results query` and `trace` exit 0 on a damaged store. **Why MINOR, not MAJOR:** under both breaks every returned row still passes `verify_record`, so no result value, identity, run card, commit or lock hash can be wrong. What gets through is only the add-provenance columns `source_file`, `source_sha256`, `added_utc` and `added_by` (X13), or a file of another schema version whose rows check (X15). Round 1 rated this same consequence MINOR (F03 (1)). A truncated later file still fails loudly (DuckDB error) | X13 and X15 survive (`47 passed` each); the demonstration above | Accept as debt, **target WP-0.7**, with DEBT-015, which already targets the store's error paths. The fix is test-only: in `test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store`, damage the later of two part files, and add a case with a part file of another schema version renamed after its content. X13 and X15 must then fail. It may also be fixed now if the builder is back in this WP for another reason |

## Convergence (round 3 onwards)
Not required at round 2. Shown for tracking.

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 6 | F01 (must-catch 2) |
| 2 | 0 | 0 | 1 (F09, new) | none |

## For the owner
- **Verdict:**
  - PASS: no CRITICAL, and no open MAJOR finding.
  - F09 is MINOR and does not block. The builder should record it in `docs/progress/DEBT.md` (recommended target WP-0.7).
- **audit-allow lines:** none. The gate reports `Exempted lines (# audit-allow): 0`.
- **Approvals used:** `docs/approvals/WP-0.6.md` on `main` (`73d1198`):
  - questions 1-16 as recommended;
  - reserved cores 2-3;
  - DEBT-008 closed;
  - the round-2 condition (fix F01, F02, F03, F05, F07; F04, F06, F08 as debt).
- **Debt accepted so far for WP-0.6:**
  - DEBT-015 (F04, WP-0.7; item 1 already done);
  - DEBT-016 (F06, WP-0.9);
  - DEBT-017 (F08, WP-0.7).
  - DEBT-008 (from WP-0.3) was closed in this WP.
- **Owner-run checks still pending:**
  - **OC-0.6-01:** on the Oracle VM, `oracle_setup.sh --dry-run`, then `oracle_setup.sh`, then `pytest -m oracle`. Commit the doctor JSON and `OC-0.6-01_oracle.txt`.
  - **OC-0.6-02:** configure the rclone remote, then `run`, `results add` and `sync --dry-run`. Commit `OC-0.6-02_sync_dry_run.txt`.
  - Both are planned at tag `aqis-lab-wp-0.6-oracle-1` after this audit. The commands and expected output are in `EVIDENCE.md`, "Owner-run checks". The aarch64 path has still not run on real hardware.
- **Note, not a finding (shallow clones):** the new F01 test reads git history (`git log` on the lock and `<commit>^`), so it errors in a depth-1 clone.
  - I checked this in a `--depth 1` clone: `4 failed, 1636 passed`. The other three failures are WP-0.0 tests that already need a pinned historical corpus commit and `origin/main`, so the fast suite already needed full history before this WP.
  - CI (`fetch-depth: 0`) and the Oracle runbook (`git clone` without `--depth`) use full clones.
  - The Colab launcher's `--depth 1` clone runs only `-m colab` tests.
- **Note, not a finding (DuckDB):** the `results` view takes `run_card_id` from the `run_card_id=<id>` folder name. DuckDB 1.5.6 auto-detects hive partitions.
  - This is why `query` refuses rows that sit in another run card's folder, which is correct.
  - It is not set explicitly in `views.py` and not documented in `RESULTS_STORE.md`.
  - If a later DuckDB version stopped auto-detecting, a copied part file would print its rows twice under its own run card, with exit 0.
  - Worth pinning `hive_partitioning` explicitly when the store is next touched (WP-0.7 with DEBT-015).
