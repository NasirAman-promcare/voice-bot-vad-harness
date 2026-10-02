# FIXES — WP-0.7

## Round 2: audit round 1 findings F01 to F04
Source: `docs/progress/WP-0.7/AUDIT.md` (round 1, `afe681e`). The owner approved the fixes in `docs/approvals/WP-0.7.md` on `main` (`a592af0`, "Round 2 Fixes"), merged into this branch first. F05 to F08 are accepted debt (DEBT-018 to DEBT-021).

### Change budget
| Finding | File | Functions | Root cause | Capabilities at risk |
| --- | --- | --- | --- | --- |
| F01 (CRITICAL) | `tests/aqis_lab/test_aqis_parity.py` | `test_FR_0_7_08_reports_every_per_clip_difference` | The test asserted 7 named lines. It checked the summary count against the lines the command itself printed, so missing lines (for example every `disfluency_aware` line) went unnoticed. | CAP-PARITY-002, CAP-PARITY-003 (the test only; no code change) |
| F02 (MAJOR) | `tests/aqis_lab/test_aqis_smoke.py` | new tests `test_FR_0_7_07_smoke_traced_rows_equal_the_stored_rows` (slow, network: the cloud fixture's store) and `test_FR_0_7_07_failed_trace_of_any_row_stops_the_smoke` (fast: the real `_check_and_store` over a real harness-VAD run, with a store that holds one later row twice) | The smoke's trace loop over every stored row had no test, so a loop that traced only the first row of each run card still passed. | CAP-SMOKE-003 (the test only; no code change) |
| F03 (MAJOR) | `tests/aqis_lab/test_aqis_smoke.py` | new test `test_FR_0_7_07_failed_run_exits_1_with_error` (fast CLI test: a model cache folder without its verification marker) | No test reached `SmokeFailure` → exit 1 through `phase0 smoke`. | CAP-SMOKE-005 (the test only; no code change) |
| F04 (MINOR) | `aqis_lab/smoke.py`; `aqis_lab/commands/phase0.py` | `run_smoke` (new `from_scratch` argument passed to every task's `RunOptions`); `build_parser` and `main` (new `--from-scratch`) | The runner's message after a new commit says "use another --out, or --from-scratch", but `phase0 smoke` had no way to pass `--from-scratch`, so a fixed `--out` (the defaults, Colab's `RUN_OUT`) could not be run again at a new tag. | CAP-SMOKE-002, CAP-SMOKE-005: the resume of an unchanged run must keep working (`test_FR_0_7_07_second_run_resumes_and_stores_nothing_new`); new test `test_FR_0_7_07_from_scratch_supersedes_the_old_runs` |

Documents: `docs/runs/PHASE0_SMOKE.md` (options table), the OC-0.7-01 section of `docs/colab/COLAB_RUNBOOK.md` and the OC-0.7-02 block of `docs/oracle/ORACLE_RUNBOOK.md` (how to run again at a new tag); `docs/capabilities/REGISTRY.md` (CAP-SMOKE-002, -003, -005); `docs/progress/DEBT.md` (DEBT-018 to DEBT-021). Nothing else changes.

### Baseline (before any change)
`.venv/bin/python -m pytest tests/aqis_lab/test_aqis_parity.py tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_smoke_launcher.py tests/aqis_lab/test_aqis_runner_events.py tests/aqis_lab/test_aqis_runner_resume.py tests/aqis_lab/test_aqis_oracle_runbook.py tests/aqis_lab/test_aqis_launcher.py tests/aqis_lab/test_aqis_gate_registry.py -q -p no:cacheprovider` (all markers, including the real cloud smoke):
```text
101 passed in 286.45s (0:04:46)
```
