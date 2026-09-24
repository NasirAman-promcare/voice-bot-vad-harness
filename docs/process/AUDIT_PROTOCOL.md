# Audit protocol

Used by the `wp-auditor` subagent for every work package, and by the builder as a self-check. Each item gets PASS, FAIL or N/A, a reason, and evidence: a command with an output excerpt, or `file:line`.

## Items

| ID | Check | How |
| --- | --- | --- |
| A1 | Scope and dependencies | Dependencies are MERGED; branch is not `main`; approval file exists on `main` with `STATUS: APPROVED` |
| A2 | Requirement coverage | Every requirement ID in the spec has an implementation, at least one test named after it, and an `EVIDENCE.md` entry. List any missing |
| A3 | Acceptance commands | Re-run every acceptance command in the spec; outputs match what the spec expects |
| A4 | Test suites | Re-run the fast suite and the slow CPU suite yourself; record pass counts |
| A5 | Test integrity | No existing test modified or deleted without an `ALLOW-EDIT` approval; no skip, xfail or trivial assert without a justified `audit-allow` |
| A6 | Mutation spot-check | In a copy under `/tmp`, break the core logic of three requirements, one at a time; each must make its tests fail. A test that still passes is CRITICAL |
| A7 | Compromise scan | Run the audit gate; then read every new function for stubs, fake data, swallowed errors and values hard-coded to satisfy tests |
| A8 | Scope diff | Every changed file and function is in the plan's change budget or listed as a new file; no protected path changed without approval |
| A9 | Capabilities | Every new module has a header; the registry is updated; no capability row removed; linked tests exist and pass |
| A10 | Contracts | Outputs validate against the relevant contracts (event log, run card, pack manifest, score table) |
| A11 | Environment parity | No absolute paths; one platform-detection module; locks pinned; Python matches the Colab probe; owner-run checks listed with commands and expected output |
| A12 | Reproducibility and traceability | A rerun gives identical hashes where the spec requires determinism; every result row carries its run card ID and clip ID |
| A13 | Errors and logging | Failures raise or emit structured error events; nothing fails silently |
| A14 | Documentation, licences, data | Usage documented for new commands; `EVIDENCE.md` complete; every clip and model has a licence entry; no real personal data; `PARTIAL` labels and `audit-allow` lines listed |

## Severity and verdict

- **CRITICAL**: requirement unmet, compromise found, protected path changed, test integrity broken, a mutation that tests fail to catch.
- **MAJOR**: evidence incomplete, parity risk, owner-run check missing, traceability gap, header or registry missing.
- **MINOR**: documentation, naming, clarity.

The verdict is **PASS** only with zero CRITICAL and zero MAJOR findings. Otherwise **FAIL**, with a concrete fix for each finding. Finding IDs use the form `WP-x.y-F01`.
