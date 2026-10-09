# Review checklist for outsourced code

Claude runs this after the relay reports success, before READY-FOR-AUDIT; the auditor runs it again under A14. Read headers and diffs first, whole files only where an item needs it.

| # | Check | How |
| --- | --- | --- |
| 1 | Scope | `python -m tools.outsourcing scope --wo <path> --base origin/main` is clean: only `outputs` and the WO's record files changed |
| 2 | Read-only tests untouched | `git diff --stat origin/main -- <read_only_tests>` shows nothing |
| 3 | Headers | Every file has the full header standard; CAPABILITIES name real, collected tests |
| 4 | Behaviours | Each B and E item from the work order maps to code you can point at (spot-check the DOD table; do not trust it) |
| 5 | Test-shaped code | No branch keyed on acceptance-test inputs, fixture names or magic values; results computed, not looked up |
| 6 | Errors | Named exception types; no bare or swallowing `except`; messages say what, why and what to do |
| 7 | Determinism | Seeds explicit; sorted iteration; no wall clock or network in core logic |
| 8 | Boundaries | Imports only from allowed modules and `allowed_dependencies`; nothing imports tests |
| 9 | Size and shape | Files at most 400 lines, functions at most 40; no dead code, unused parameters or speculative options |
| 10 | Duplication | Nothing re-implements an existing module the work order named (reuse ladder) |
| 11 | Secrets and data | No keys, tokens, personal data or absolute paths; no network calls the order did not ask for |
| 12 | Break suite | The WP's break recipes still apply and are caught with the new code |
| 13 | Ledger | `docs/outsourcing/returns/<WO>/summary.md` and the ledger fragment exist |

Outcome: ACCEPT (continue), FIX ORDER (send through the relay), CLARIFY (amend the work order and resend), or TAKE OVER (Claude fixes a gap under about 30 lines itself, with a test first).
