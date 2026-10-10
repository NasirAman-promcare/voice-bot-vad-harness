# EVIDENCE — WP-1.0

Environment: cloud VM, Linux x86_64, Python 3.13.16 (`.venv` from `bash aqis_lab/deploy/dev_bootstrap.sh`, lock sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`), branch `claude/wp-1-0-operating-model-v2`.

## Environment fixes made in this session (VM only; no repository change)
- **Shallow clone.** `git rev-parse --is-shallow-repository` printed `true` and `git rev-list --count HEAD` printed `203`. Five history-reading tests failed with `fatal: Not a valid commit name …` and `git cat-file … returned non-zero exit status 128`. The fix was `git fetch -q --unshallow origin`, after which the same check printed `false`.
- **uv version.** The VM had `uv 0.11.32`, but the lab pins 0.8.17. Four `test_aqis_oracle_setup.py` tests failed with `ERROR: /root/.local/bin/uv reports 'uv 0.11.32 …', but oracle_setup.sh needs uv 0.8.17`. The fix was `uv self update 0.8.17`, which printed `success: Downgraded uv from v0.11.32 to v0.8.17!`.
- **After both fixes.** `.venv/bin/python -m pytest -q --tb=line -p no:cacheprovider tests/aqis_lab/test_aqis_harness_provision.py tests/aqis_lab/test_aqis_oracle_setup.py tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_trace.py -m "not slow and not gpu and not colab and not oracle and not network"` printed `171 passed, 21 deselected in 46.23s`.

## Acceptance tests written first (failing for the expected reason)
| File | Tests | Command | Result |
| --- | --- | --- | --- |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` | 63 | `.venv/bin/python -m pytest <file> -q --tb=line` | `63 failed`: each fails with `ModuleNotFoundError: No module named 'tools.outsourcing'`, or, in the CLI tests, with the subprocess's `No module named tools.outsourcing` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py` | 31 | same | `31 failed`, all `ModuleNotFoundError: No module named 'tools.outsourcing'` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py` | 20 | same | `20 failed`, all `ModuleNotFoundError: No module named 'tools.outsourcing'` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_11.py` | 23 | same | `23 failed`: each fails with `ModuleNotFoundError: No module named 'tools.outsourcing'`, or, in the subprocess runs, with `Error while finding module specification for 'tools.outsourcing.relay'` |

Imports sit inside the tests, so the rest of the suite still runs while these wait. A diagnostic fast-suite run (not AT-1.0-01) at `d2f8f59` printed `103 failed, 1978 passed, 55 deselected in 384.26s`. The 103 failures are the 94 wave-1 acceptance tests plus the 9 environment failures above, which pass after the fixes.

## Requirements
### FR-1.0-11 — DEBT-033 and DEBT-034
- **DEBT-033.** The test passes: `.venv/bin/python -m pytest tests/aqis_lab/ci/test_wp_1_0_requirements.py -q --tb=line` reported `test_FR_1_0_11_debt033_parakeet_doc_names_the_gpu_in_file` as passing, with the 7 other tests failing for the expected reasons (no `.relay/` line yet, no GPU output yet, no migrated fragments yet, no orders done yet, no tools yet).
- **DEBT-034, test.** `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py -q --tb=short -k move_approval` printed `7 passed, 71 deselected in 2.63s`.
- **DEBT-034, proof that the new case catches the defect.** I removed the look-behind `(?<![\w.-])` from `names_id` in `tests/aqis_lab/aqis_memo_testutil.py`, then restored the file from a copy (`git diff --stat` empty afterwards). With the look-behind removed, the same command printed `FAILED …[longer-debt-id-on-the-left]` and `1 failed, 6 passed, 71 deselected`: only the new case failed.
- Status: PARTIAL. DEBT-032 waits on BLK-1.0-03, and the debt fragments come with the WO-1.0-04 migration.

## Acceptance commands
Not run yet: the tools do not exist until the work orders land.

## audit-allow lines
None so far.
