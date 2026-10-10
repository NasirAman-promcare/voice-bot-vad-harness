# FIX 1 for WO-1.0-11

Your previous answer (PR #15) is merged into `claude/wp-1-0-operating-model-v2` at `8d8d5b4`, with two changes made on merge:

- **Bootstrap change left out.** The branch's change to `aqis_lab/deploy/dev_bootstrap.sh` is not part of the merge. It wrote a `sitecustomize.py` into every `.venv` that patched Python's import machinery whenever `tools.outsourcing` appeared on the command line. That file is outside the order's outputs. It is also code that behaves differently for particular invocations, which the Foundation forbids.
  - The failures it worked around came from the acceptance test's scratch `tools` package shadowing the repository's own. Claude fixed that test (the scratch package is now `lab_demo`).
  - Never change files outside the order's outputs, and never change the environment to make a test pass. When a read-only test seems wrong, write it into the pull request description as a question.
- **Renamed names.** Claude renamed `dummy_spec`, `dummy_part` and `dummy_wo`, because the compromise scan forbids the word.

All acceptance tests pass. Claude's review found the gaps below; fix the root cause in each case. The public API of section 3 and B24 of `docs/outsourcing/orders/WO-1.0-11.md` stays as it is.

## Failed checks
All are in `tests/aqis_lab/outsourcing/test_fix_wo_1_0_11_01.py`, a read-only test written by Claude. Before your fix: `14 failed`.

1. **`test_FR_1_0_02_fix01_exhausted_run_prints_its_report`, `…_questions_run_prints_its_report`, `…_integrity_run_prints_its_report`**: stdout is empty.
   - Only an accepted run prints anything. B18 requires the report on every finish:
     - the result's display name on the first line;
     - parts done of total;
     - requests per model, retries by kind and minutes waited;
     - tokens in and out;
     - any POOL or ACCESS line;
     - the checks table, naming each check with PASS or FAIL;
     - the summary path;
     - for the paused results, the resume command and time;
     - for ACCEPTED, the merge command.
   - At most 25 lines. Put the report in the new module `tools/outsourcing/report.py`.
2. **`test_FR_1_0_02_fix01_step_log_records_the_orders_sha256`**: the run records `sha` instead of the order's SHA-256.
   - `relay.py` uses `order.sha256 if hasattr(order, "sha256") else "sha"`. `WorkOrder` has no such attribute, so a made-up value is written to the record.
   - B7: compute the SHA-256 of the order file's bytes as read from the worktree, and say in the summary when it differs from the last run's.
3. **`test_FR_1_0_02_fix01_governor_state_is_relay_governor_json`**: the state file is `.relay/governor_state.json`. WO-1.0-10 B6 names `.relay/governor.json`.
4. **`test_FR_1_0_14_fix01_failed_listing_is_an_error_not_missing[server-error|forbidden]`**: a failed listing printed `Error listing models …` and then reported every model "missing". B20: a failed listing is not "missing".
   - **Credential error:** print the ACCESS line of B9 and exit 7.
   - **Network failure or unexpected response:** exit 10.
   - Never print "missing" for a provider whose listing failed.
5. **`test_FR_1_0_02_fix01_final_fix_is_committed_only_after_checks_pass`**: exit 2, `Relay error: On branch wo/WO-9.9-03`.
   - Two defects:
     - `run_final` commits and pushes each round's files before the full checks run again. B16 says "When they pass, commit and push".
     - A commit with nothing to commit raises, and `main` turns that into exit 2.
   - **Fix:**
     - Commit only after a passing round.
     - Never commit when nothing changed.
     - After the last failed round, finish with EXHAUSTED and its report, and discard that round's uncommitted files (they stay in `.relay/logs` for inspection).
   - Put the final verification in the new module `tools/outsourcing/stepper_final.py`, re-exported by `stepper.run_final`.
6. **`test_FR_1_0_02_fix01_ledger_counts_every_replys_tokens`**: `assert 2010 == 3012`. The ledger sums only accepted parts. B24 says the sums cover every reply received with HTTP 200, including failed attempts, fix turns and final rounds.
7. **`test_FR_1_0_02_fix01_relay_modules_follow_the_shape_rules`** (all 5 modules):
   - **Swallowed or broad handlers:**
     - `relay.py`: the `--models` catch-all, the push failure ignored in `_finalize_records`, the lock release, and `main`'s `except Exception` that maps everything to exit 2.
     - `stepper.py`: lines 234 and 485.
   - **Functions over 40 lines:** `_choose_default` (46), `open_worktree` (56), `write_summary` (91), `_attempt_part_loop` (222), `run_final` (100), `run` (121).
   - **File size:** `stepper.py` is 497 lines, over the 400-line hard limit.
   - **Required handling:**
     - Map each exception to its `Result` as B9 and B17 say:
       - `WorktreeError` → GIT (14);
       - `ApiError` and `TransportError` → NETWORK (10);
       - `WorkOrderError`, `LimitsError` and `NoEligibleModel` → INVALID (2), or TOO_LARGE (13) when size alone ruled the models out.
     - A push that fails after records are committed is GIT (14), and the report says the commit is local only (B17).
   - Split functions by responsibility.

## Files you may change
- `tools/outsourcing/router.py`
- `tools/outsourcing/worktree.py`
- `tools/outsourcing/ledger.py`
- `tools/outsourcing/stepper.py`
- `tools/outsourcing/stepper_final.py` (new)
- `tools/outsourcing/report.py` (new)
- `tools/outsourcing/relay.py`
- `tests/aqis_lab/outsourcing/test_router.py`
- `tests/aqis_lab/outsourcing/test_worktree.py`
- `tests/aqis_lab/outsourcing/test_ledger.py`
- `tests/aqis_lab/outsourcing/test_stepper.py`
- `tests/aqis_lab/outsourcing/test_report.py` (new)
- `tests/aqis_lab/outsourcing/test_relay.py`

Add unit tests for every behaviour you change.

## Rules
- Return only the files you change, each complete.
- Do not touch any other file. In particular, do not touch `aqis_lab/`, `.gitignore`, the environment, or any `tools/outsourcing` module of another order.
- Never touch the read-only tests: `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_*.py` and `tests/aqis_lab/outsourcing/test_fix_wo_1_0_*.py`.
- If a failure shows the work order itself is wrong, write a QUESTIONS section into the pull request description instead of guessing.

## Verify
```text
.venv/bin/python -m pytest tests/aqis_lab/outsourcing -q --tb=short
.venv/bin/python -m tools.audit.gate --base origin/main
```
Every test must pass, and the audit gate must report `0 findings: OK`.

## Channel notes (Jules)
1. Read `docs/process/outsourcing/FOUNDATION.md`, `docs/outsourcing/orders/WO-1.0-11.md` and this file.
2. Work on branch `wo/WO-1.0-11-fix-1` from `claude/wp-1-0-operating-model-v2`.
3. Run both verify commands until they pass.
4. Open a pull request against `claude/wp-1-0-operating-model-v2` titled `WO-1.0-11 FIX 1: reports, records, listing errors, final fixes, shape`. Its description is the DOD table for items 1 to 7 above.
