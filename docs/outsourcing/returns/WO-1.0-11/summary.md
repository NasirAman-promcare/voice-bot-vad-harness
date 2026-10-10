# WO-1.0-11 Summary

- **WO**: WO-1.0-11, relay orchestration (router, worktree, ledger, stepper, command line)
- **Channel**: jules. PR #15 was on branch `wo/WO-1.0-11-6453972168397431084`, which Jules named with a suffix. Model and token counts are not reported by the Jules channel.
- **Result so far**: merged as `8d8d5b4`, with FIX-1 open.

## Claude's review (WO_REVIEW_CHECKLIST, 2026-10-10)
- **Scope: one violation.** `python -m tools.outsourcing scope …` reported `aqis_lab/deploy/dev_bootstrap.sh`.
  - The branch made the bootstrap write a `sitecustomize.py` into every `.venv`. That file patched Python's import machinery whenever `tools.outsourcing` appeared on the command line, so the code behaved differently for particular invocations.
  - That change is left out of the merge. Its cause was a defect in Claude's acceptance test: its scratch `tools` package shadowed the repository's own. The test now uses `lab_demo`, with no assertion changed.
- **Stale bytecode (an intermittent failure, traced to its root).** A rerun could judge a same-size fix by stale bytecode. This was fixed in `tools/outsourcing/checks.py` (WO-1.0-02 code): check commands now run with `PYTHONDONTWRITEBYTECODE=1`, and a deterministic test was added.
- **Tests.** After those fixes, all 23 acceptance tests and Jules's unit tests pass: `269 passed` for `tests/aqis_lab/outsourcing`.
- **Names (fixed on merge).** `dummy_spec`, `dummy_part` and `dummy_wo` were renamed, with no change in behaviour. The audit gate then reported `0 findings: OK`.
- **Outcome: FIX ORDER.** `docs/outsourcing/returns/WO-1.0-11/FIX-1.md` goes out with read-only tests in `tests/aqis_lab/outsourcing/test_fix_wo_1_0_11_01.py`; before the fix they gave `14 failed`. The gaps:
  - no report for any result but ACCEPTED;
  - the literal `sha` recorded as the order's hash;
  - the wrong state file name;
  - failed listings reported as "missing";
  - final-fix rounds committed before they pass;
  - a commit with nothing to commit gives exit 2;
  - the ledger counts only accepted parts;
  - swallowed or catch-all exceptions;
  - functions over 40 lines, and `stepper.py` at 497 lines.

## FIX-1 (PR #16, branch `wo/WO-1.0-11-fix-1-8105093573879212493`)
- **Checks.** The scope check is clean (`Scope check passed: no violations.`). `tests/aqis_lab/outsourcing` gave `337 passed`, including the 14 FIX-1 tests. The audit gate reported `0 findings: OK`.
- **Shape.** Every module of the order is now within 400 lines; `stepper.py` is 293 lines, with `stepper_final.py` and `report.py` new.
- **Spot checks.**
  - The step log takes the SHA-256 of the order file.
  - Each exception maps to its own exit code.
  - A failed push sets `push_ok` instead of being swallowed.
  - Final-fix rounds commit only after `full_checks` passes.
- **Result: ACCEPTED.**
