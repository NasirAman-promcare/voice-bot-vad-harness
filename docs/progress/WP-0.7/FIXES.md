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

### Reproduce: the new tests first
- F01: the rewritten test passes on the real code: all 19 expected lines, both variants (`7 passed, 1 deselected in 5.79s` for `test_aqis_parity.py -m "not slow"`). It fails on the auditor's break MC6d, below.
- F02, F03: the new tests pass on the real code, which was already correct (the findings were about missing tests). Each fails on the auditor's break X1 or X10, below.
- F04, before the code change: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_smoke.py -q -p no:cacheprovider -m "not slow"`:
```text
E       assert (0 == 1)
E        +  where 0 = len([])
E       SystemExit: 2
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_from_scratch_supersedes_the_old_runs
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_cli_parses_every_option
2 failed, 10 passed, 12 deselected in 7.99s
```
  After the change: `12 passed, 12 deselected in 9.79s`.

### How the F02 test makes a trace fail on one row
The store's DuckDB view reads every partition's part files, and `query_run_card` keeps the rows that name the run card. The test puts into the smoke's store, in the partition of another real run (a `clip-stats` run of the same pack), a copy of the part file that the real `add_batch` wrote for one harness-vad row: the row that sorts last. So the smoke lists that row twice, and `trace_row` refuses only that row (`… is stored 2 times`). A smoke that traced only the first row of each run card would miss it. The same check on a clean store returns `traced == 60 ==` the stored rows.

### Must-catch: the auditor's breaks against the new tests
In a fresh clone of `0615214` (`/tmp/wp07-mc`), each break applied, the named test run, then the file restored with `git checkout -- .`:
```text
### MC6d: parity compares per-clip WER of the main variant only (audit round 1, F01)
broken: aqis_lab/parity.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 1.24s
FAILED tests/aqis_lab/test_aqis_parity.py::test_FR_0_7_08_reports_every_per_clip_difference
restored: ?? .venv

### X1: the smoke traces only the first row of each run card but counts every row (audit round 1, F02)
broken: aqis_lab/smoke.py (1 file changed, 3 insertions(+), 3 deletions(-))
summary: 1 failed in 2.11s
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_failed_trace_of_any_row_stops_the_smoke
restored: ?? .venv

### X10: phase0 smoke exits 0 on a SmokeFailure (audit round 1, F03)
broken: aqis_lab/commands/phase0.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 1.47s
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_failed_run_exits_1_with_error
restored: ?? .venv

### F04: run_smoke no longer passes from_scratch to the runner (audit round 1, F04)
broken: aqis_lab/smoke.py (1 file changed, 1 insertion(+), 1 deletion(-))
summary: 1 failed in 2.01s
FAILED tests/aqis_lab/test_aqis_smoke.py::test_FR_0_7_07_from_scratch_supersedes_the_old_runs
restored: ?? .venv

```

### Verify
- Baseline set again (same command as the baseline, all markers, real cloud smoke included): `105 passed in 262.22s (0:04:22)` (the 101 before, plus the 4 new tests).
- Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider`: `1747 passed, 54 deselected in 259.07s (0:04:19)`.
- Network-only tests (F06; DEBT-019): `.venv/bin/python -m pytest tests/aqis_lab -q -m "network and not slow and not gpu and not colab and not oracle" -p no:cacheprovider`: `12 passed, 1789 deselected in 83.28s (0:01:23)`.
- Audit gate: `git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.7`
```text
aqis-audit-gate: base origin/main (merge-base a592af0ad4ea), head 06152143dda9, approvals origin/main a592af0ad4ea, wp WP-0.7
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.8 s)
```
- `git diff -U0 a50a786..0615214 -- aqis_lab/`: the hunks are inside `run_smoke` (one argument and the `RunOptions` keyword) and `build_parser`/`main` of `aqis_lab/commands/phase0.py`, plus the two headers (CAPABILITIES lines and CHANGE LOG). No other production code changed.
- F04 end to end, with the acceptance command as written, on a clean tree at `0615214`. The default folders still held my runs from `0a534ce`:
```text
ERROR: task vosk-batch: the run folder /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/runs/vosk-batch holds another run: its run card differs at /git/commit; use another --out, or --from-scratch to move it aside and start again
exit 2
2026-10-02T10:45:16.006797Z previous run folder moved to /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/runs/vosk-batch.superseded-20261002T104515Z (--from-scratch)
2026-10-02T10:46:50.234536Z previous run folder moved to /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/runs/harness-vad.superseded-20261002T104650Z (--from-scratch)
2026-10-02T10:46:50.830814Z previous run folder moved to /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/runs/vosk-realspeed.superseded-20261002T104650Z (--from-scratch)
smoke complete: bundle /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke-bundles/phase0-smoke-cloud-20261002T104515Z (23 files, 225 rows traced), archive /home/user/voice-bot-vad-harness/data/raw/aqis_lab/smoke/cloud/phase0-smoke-cloud-20261002T104515Z.tar, 134.2 s
real	2m14.868s
exit 0
```
  `parity data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar data/raw/aqis_lab/smoke/cloud/phase0-smoke-cloud-20261002T104515Z.tar`: `parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)`, exit 0. The bundle made at `0615214` equals the committed one from `0a534ce`.
- CI on the pushed commit: in the pull request, https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/7.

### BLK-011 — fixture git repositories and background maintenance (owner option 1, `28ab7f4`)
- Cause: CI's push run on `0b12344` (run 278, attempt 1) failed `test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing` with `FileNotFoundError: … tree/.git/objects/maintenance.lock`. The CI runner's git 2.55.0 starts automatic maintenance in a detached background process after `git commit`, and the test listed the fixture tree while that process wrote and removed the lock. The pull-request run on the same commit and one re-run passed. This VM has git 2.43.0, which does not show it.
- Change budget: `tests/aqis_lab/aqis_testutil.py`, `hermetic_git_env` only (docstring and returned environment). The `git diff -U0` hunks are `@@ -78 +78,3 @@` and `@@ -83,0 +86,5 @@`, both in `hermetic_git_env`. It now sets `GIT_CONFIG_COUNT=2`, `GIT_CONFIG_KEY_0=maintenance.auto`, `GIT_CONFIG_VALUE_0=0`, `GIT_CONFIG_KEY_1=gc.auto` and `GIT_CONFIG_VALUE_1=0`. In a fixture repository, `git config --get` reads `maintenance.auto = 0` and `gc.auto = 0`, and `--show-origin` reads `command line:	0`.
- Baseline, every test file that uses `hermetic_git_env` or `fixture_repo`: `.venv/bin/python -m pytest <the 11 files> -q -m "not gpu and not colab and not oracle" -p no:cacheprovider`. Its first runs failed `test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor` (`1 failed, 224 passed`, twice). That test runs the doctor, whose disk minimum is 10 GB, and the VM had 11 GB free before pytest's temporary folders grew. After I removed my old pytest folders, the `/tmp` clone and the superseded smoke runs (14 GB free), the baseline was `225 passed, 1 deselected in 116.54s`.
- After the change, on a clean tree at `97aa673`: the same command gave `225 passed, 1 deselected in 113.73s (0:01:53)`.
- Fast suite: `1747 passed, 54 deselected in 249.68s (0:04:09)`. Audit gate:
```text
aqis-audit-gate: base origin/main (merge-base 28ab7f4fc2f8), head 97aa6735b207, approvals origin/main 28ab7f4fc2f8, wp WP-0.7
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.7 s)
```
- The race cannot be reproduced on this VM's git 2.43.0. CI on the newer runners is the check: see the pull request.
