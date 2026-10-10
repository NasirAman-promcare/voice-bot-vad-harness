# WO-1.0-02 Summary

- **WO**: WO-1.0-02, relay building blocks (records, interface views, requests, checks, fix orders, step log)
- **Channel**: jules. PR #13 was on branch `wo/WO-1.0-02-12367345926886918834`, which Jules named with a suffix. Model and token counts are not reported by the Jules channel.
- **Result**: ACCEPTED after review fixes. Merged as `ae44745`.

## Claude's review (WO_REVIEW_CHECKLIST, 2026-10-10)
- **Scope.** `python -m tools.outsourcing scope --wo docs/outsourcing/orders/WO-1.0-02.md --base origin/claude/wp-1-0-operating-model-v2 --head origin/wo/WO-1.0-02-12367345926886918834` printed `Scope check passed: no violations.`. The read-only test is unchanged.
- **Tests.** All 20 acceptance tests and 11 unit tests pass (`31 passed`).
- **Outcome: TAKE OVER** (each fix with a failing test first, in `tests/aqis_lab/outsourcing/test_review_fixes_wo_1_0_02.py`):
  - The `read-only-tests` check reported a pass without comparing any hash, a fabricated result. It now compares each read-only test with its base-commit version.
  - A read-only test changed before the checks now gives an integrity failure (relay exit 9), whether scope or that check sees it first. Before, scope reported it as an ordinary violation, which would have produced a fix turn.
  - `kit-staging/` code, which the audit gate does not scan, now gets the gate's code patterns. WO-1.0-07 B7 relies on the relay to scan staged hooks.
- **Open, for the audit (not blocking WO-1.0-11):**
  - `checks.py` is 380 lines, above the 300 the order sets but within the 400-line hard limit.
  - A few broad `except Exception` handlers turn errors into failed checks. None hides an error as a pass.
  - Unit tests are thin: 11 in all.
