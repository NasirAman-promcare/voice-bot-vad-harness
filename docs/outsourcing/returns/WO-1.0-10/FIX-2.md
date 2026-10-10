# FIX 2 for WO-1.0-10 (taken over by Claude)

## Findings
These come from the review of FIX-1. The tests were written first, in `tests/aqis_lab/outsourcing/test_fix_wo_1_0_10_02.py`, and 2 of 52 failed before the fix:
1. `governor.py` was 531 lines, over the Foundation's 400-line hard limit (`assert 531 <= 400`).
2. `wait_for_provider` slept while it held the state lock, which blocked every other process (`assert [True] == [False]`).

The B7 classification rows and retry-delay forms already behaved as the order says (50 passed). They are now pinned by tests, because FIX-1 added few unit tests.

## Fix (Claude, under the take-over rule: a refactor and edits under 50 lines)
- **New file.** The records, state file handling and lock moved, unchanged in behaviour, to the new output `tools/outsourcing/governor_state.py`, added to the order's `outputs` and step 3. `governor.py` is now 390 lines.
- **Lock.** `wait_for_provider` decides under the lock, sleeps outside it and decides again, like `wait_for_slot`.
- **Side effect.** After a corrupt start (E3), loading a saved adaptive factor no longer resets it to 0.75 on every load. A later slowdown below 0.75 now persists, as B8 requires.

## Result
`.venv/bin/python -m pytest tests/aqis_lab/outsourcing -q` printed `320 passed`. The one other failure in that run was a defect in my own HTTP-date test: the date was built at collection time. I fixed the test, and the affected files then printed `111 passed`. `python -m tools.audit.gate --base origin/main` printed `0 findings: OK`.
