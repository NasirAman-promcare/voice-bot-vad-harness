# FIXES — WP-0.6

## Round 2 (audit round 1 findings; approval `docs/approvals/WP-0.6.md` on `main`, `73d1198`)
Fix F01, F02, F03, F05 and F07. F04 (target WP-0.7), F06 (target WP-0.9) and F08 (target WP-0.7) are accepted as debt: DEBT-015, DEBT-016 and DEBT-017 in `docs/progress/DEBT.md`.

### Change budget
| File | Functions | Finding | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| `tests/aqis_lab/test_aqis_trace.py` | new `git_out`, `historical_run`, `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash` | F01 | Every stored test row came from a run at the current commit with the current lock, so a trace printing the checkout's commit or lock hash passed | none (test only) |
| `tests/aqis_lab/aqis_results_testutil.py` | new `part_file`, `rewrite_part` | F02, F03 | helpers for the tamper tests | none (test only) |
| `tests/aqis_lab/test_aqis_results_store.py` | new `test_FR_0_6_02_add_rejects_tampered_stored_rows` | F02 | the `row_sha256` and part-file-name checks of `add` had no test | none (test only) |
| `tests/aqis_lab/test_aqis_results_cli.py` | new `tampered_store`, `test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store` | F02, F03 | no reader was tested against a damaged store | none (test only) |
| `aqis_lab/results/views.py` | `connect` only (plus header) | F03 | `connect` built the views straight from the files without the checks `read_partition` and `load_stored_card` do, so `query` and `trace` accepted a part file changed in place and joined a copied run card twice | CAP-RESULTS-005 (views, query), CAP-TRACE-001 (trace reads through the view) |
| `aqis_lab/deploy/oracle_setup.sh` | step 6: the two `aqis_lab.oracle_config get` reads (plus header change log) | F05 | the reads ran in the caller's folder, where `aqis_lab` cannot be imported | CAP-ENV-007 |
| `tests/aqis_lab/test_aqis_oracle_setup.py` | new `test_FR_0_6_01_runs_from_any_directory` | F05 | no test started the script outside the repository root | none (test only) |
| `tests/aqis_lab/test_aqis_oracle_config.py` | new `test_FR_0_6_02_default_store_equals_oracle_results_store` | F07 (4) | the plan's promised test was missing | none (test only) |
| `docs/progress/DEBT.md` | new rows DEBT-015, DEBT-016, DEBT-017 | F04, F06, F08 | owner decision | none |
| `docs/capabilities/REGISTRY.md` | test lists of CAP-RESULTS-001, -002, -005, CAP-TRACE-001, CAP-ENV-007, CAP-ORACLE-001 | all | new tests | none |

F07 (1) to (3) are accepted as recorded deviations (approval): `parse_cpu_list` and three path constants in `aqis_lab/platform.py`, no `--config` on `oracle_setup.sh`, the runner log line `cores: …`.

### Baseline (before any change)
`.venv/bin/python -m pytest tests/aqis_lab/test_aqis_results_store.py tests/aqis_lab/test_aqis_results_cli.py tests/aqis_lab/test_aqis_trace.py tests/aqis_lab/test_aqis_oracle_setup.py tests/aqis_lab/test_aqis_oracle_config.py -q -p no:cacheprovider -m "not oracle"`
```text
78 passed, 1 deselected in 27.83s
```

### Budget changes during the fix
- `aqis_lab/results/store.py`: the file checks of `read_partition` (content equal to the SHA-256 in the name, readable Parquet, schema) moved unchanged into a new `check_part_file`, which `read_partition` and `views.connect` both call. Reason: `connect` first ran all of `read_partition`, including every row check. That hid the second case of the round-1 test `test_FR_0_6_03_row_not_matching_its_id_is_reported` (a duplicated row ID) behind its first case. Editing that test is not allowed, so `connect` does the file and card checks, and `query_run_card` and `trace` keep checking every row they return.
- `aqis_lab/commands/results.py` and `aqis_lab/trace.py`: header test lists only (`test_FR_0_0_08_module_headers_match_registry` requires each header to equal its registry row).
- The new CLI test expects `results add` to succeed ("nothing written") when a stray run card copy sits in another run card's folder, because `add` reads only the partition it writes to.

### Verification
- **Reproduced first.** F01: the audit's breaks MC2b and MC2c survived before the new test (audit report). F02/F03: before the `connect` change, the new CLI test failed its `file-in-place`, `truncated` and `card-copy` cases (`3 failed, 2 passed`). F05: `test_FR_0_6_01_runs_from_any_directory` failed with `ERROR: cannot read paths.work_dir from config/aqis_lab/oracle.yaml.`
- **Breaks in a throwaway copy** (`/tmp/aqis-round2-breaks`, script `round2_breaks.py` in the session scratchpad; each run `-k "FR_0_6_02 or FR_0_6_03"`, fast markers):
```text
MC2b trace prints the checkout's commit | aqis_lab/trace.py | rc=1 | 1 failed, 46 passed, 1618 deselected in 31.19s | failed: test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash
MC2c trace prints the lock file's current hash | aqis_lab/trace.py | rc=1 | 1 failed, 46 passed, 1618 deselected in 33.32s | failed: test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash
X1 verify_record skips row_sha256 | aqis_lab/results/store.py | rc=1 | 2 failed, 45 passed, 1618 deselected in 32.63s | failed: test_FR_0_6_02_add_rejects_tampered_stored_rows, test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store
X2 part file not compared with its name | aqis_lab/results/store.py | rc=1 | 3 failed, 44 passed, 1618 deselected in 31.89s | failed: test_FR_0_6_02_add_rejects_tampered_stored_rows, test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store
X3 query does not check its rows | aqis_lab/results/views.py | rc=1 | 1 failed, 46 passed, 1618 deselected in 36.97s | failed: test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store
X11 connect skips the card-folder check | aqis_lab/results/views.py | rc=1 | 1 failed, 46 passed, 1618 deselected in 35.89s | failed: test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store
X12 connect skips the part-file checks | aqis_lab/results/views.py | rc=1 | 2 failed, 45 passed, 1618 deselected in 30.45s | failed: test_FR_0_6_02_query_trace_and_add_reject_a_damaged_store
```
- **Linked tests after the change** (same command as the baseline): `78 passed` before; after, the store, CLI and trace files `46 passed in 31.07s`, and the setup and config files `40 passed, 1 deselected in 8.29s`. Registry and header tests: `12 passed in 2.06s`.
- **Suites at `719d7f4`:** fast `1640 passed, 25 deselected in 209.04s`; slow `3 passed, 1662 deselected in 9.85s`; WP-0.6 network `5 passed, 1660 deselected in 6.65s` (including `test_FR_0_6_01_runs_from_any_directory`).
- **Gate:** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.6` gives `0 findings: OK (0.5 s)`.
- **Scope:** `git diff -U0 5954dd4 719d7f4 -- aqis_lab` changes only `check_part_file` (new), `read_partition` (calls it) and the header in `store.py`; `connect` and the header in `views.py`; header lines in `trace.py` and `commands/results.py`; and the two step-6 reads plus the header in `oracle_setup.sh`.
- **CI on `719d7f4`:** push run 246 and pull-request run 247 `success`.
