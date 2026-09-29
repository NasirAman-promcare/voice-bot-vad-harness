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
