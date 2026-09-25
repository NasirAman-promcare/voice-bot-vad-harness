# EVIDENCE — WP-0.0

Environment: cloud VM (Ubuntu 24.04.4 LTS, x86_64), Python 3.13.12 in `.venv` (Colab probe: 3.13), uv 0.8.17, lock `requirements/aqis_lab/phase0.txt` sha256 `5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422`. Git commits are given per section.

## Requirements

### FR-0.0-01 — `python -m aqis_lab version`
- Tests: `test_FR_0_0_01_version_prints_package_commit_python`, `test_FR_0_0_01_version_marks_dirty_tree`, `test_FR_0_0_01_version_fails_loudly_outside_git`, `test_FR_0_0_01_dispatcher_rejects_unknown_command`
- Tests first: all four failed before implementation (`No module named aqis_lab.__main__; 'aqis_lab' is a package and cannot be directly executed`; exit code 1 instead of 2).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_version.py -v -p no:cacheprovider`, then `.venv/bin/python -m aqis_lab version`
- Output (real excerpt):
```text
tests/aqis_lab/test_aqis_version.py::test_FR_0_0_01_version_prints_package_commit_python PASSED
tests/aqis_lab/test_aqis_version.py::test_FR_0_0_01_version_marks_dirty_tree PASSED
tests/aqis_lab/test_aqis_version.py::test_FR_0_0_01_version_fails_loudly_outside_git PASSED
tests/aqis_lab/test_aqis_version.py::test_FR_0_0_01_dispatcher_rejects_unknown_command PASSED
============================== 4 passed in 0.54s ===============================
aqis_lab 0.0.1 commit=7c2c2bb+dirty python=3.13.12
EXIT=0
```
- Status: DONE

### FR-0.0-02 — dev_bootstrap.sh
- Tests: `test_FR_0_0_02_fails_when_probe_missing`, `test_FR_0_0_02_fails_when_probe_unreadable[directory|no_version_line|conflicting_versions]`, `test_FR_0_0_02_fails_when_uv_missing`; slow+network: `test_FR_0_0_02_creates_venv_with_probe_python`, `test_FR_0_0_02_second_run_changes_nothing_within_30s`, `test_FR_0_0_02_rejects_lock_with_wrong_hash`
- Tests first: before the script existed, all fast FR-0.0-02 tests failed with `FileNotFoundError: ... aqis_lab/deploy/dev_bootstrap.sh` (run with a throwaway `uv run --with pytest==9.1.1` interpreter, since no lock existed yet).
- Command: `bash aqis_lab/deploy/dev_bootstrap.sh` (first run, then `time` on a second run)
- Output (real excerpt):
```text
Colab probe requires Python 3.13 (docs/environment/colab_probe.txt)
Using uv 0.8.17 at /root/.local/bin/uv
Using CPython 3.13.12 interpreter at: /usr/bin/python3.13
Creating virtual environment at: .venv
...
Installed 11 packages in 7ms
OK: .venv ready: Python 3.13.12, lock sha256 5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422
---
Colab probe requires Python 3.13 (docs/environment/colab_probe.txt)
Using uv 0.8.17 at /root/.local/bin/uv
Reusing .venv (Python 3.13)
Resolved 11 packages in 8ms
Audited 11 packages in 0.11ms
OK: .venv ready: Python 3.13.12, lock sha256 5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422

real	0m0.095s
```
- Tampered lock (pytest hashes zeroed), real output tail:
```text
      Expected:
        sha256:0000000000000000000000000000000000000000000000000000000000000000
      Computed:
        sha256:37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c
ERROR: hash-checked install of requirements/aqis_lab/phase0.txt failed (see the uv message above).
```
- Command: `.venv/bin/python -m pytest tests/aqis_lab -v -p no:cacheprovider -k "FR_0_0_02 or FR_0_0_03 or FR_0_0_04"` (no marker filter, so slow and network tests ran)
```text
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_fails_when_probe_missing PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_fails_when_probe_unreadable[directory] PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_fails_when_probe_unreadable[no_version_line] PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_fails_when_probe_unreadable[conflicting_versions] PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_fails_when_uv_missing PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_creates_venv_with_probe_python PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_second_run_changes_nothing_within_30s PASSED
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_rejects_lock_with_wrong_hash PASSED
```
- Status: DONE

### FR-0.0-03 — phase0 lock
- Tests: `test_FR_0_0_03_every_pin_has_hashes`, `test_FR_0_0_03_lock_generated_from_in_file`, `test_FR_0_0_03_regeneration_command_documented`, `test_FR_0_0_03_environment_matches_lock`; slow+network: `test_FR_0_0_03_regeneration_is_reproducible`, `test_FR_0_0_03_lock_installable_with_plain_pip`
- Tests first: all four fast tests failed with `FileNotFoundError: ... requirements/aqis_lab/phase0.txt` before the lock existed.
- Regeneration command (documented in `phase0.in` and recorded in the `phase0.txt` header): `uv pip compile requirements/aqis_lab/phase0.in --universal --python-version 3.13 --generate-hashes --output-file requirements/aqis_lab/phase0.txt` (run with the same string as `--custom-compile-command`).
- Pins (real `grep -E '^[a-z]' requirements/aqis_lab/phase0.txt`): attrs 26.1.0, colorama 0.4.6 (`sys_platform == 'win32'` only), iniconfig 2.3.0, jsonschema 4.26.0, jsonschema-specifications 2025.9.1, packaging 26.3, pluggy 1.6.0, pygments 2.21.0, pytest 9.1.1, pyyaml 6.0.3, referencing 0.37.0, rpds-py 2026.6.3.
- Output (same command as FR-0.0-02):
```text
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_every_pin_has_hashes PASSED
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_generated_from_in_file PASSED
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_command_documented PASSED
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_environment_matches_lock PASSED
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_is_reproducible PASSED
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_installable_with_plain_pip PASSED
```
- Status: DONE

### FR-0.0-04 — lab test discovery and markers
- Tests: `test_FR_0_0_04_all_five_markers_registered`, `test_FR_0_0_04_lab_tests_use_only_registered_markers`, `test_FR_0_0_04_harness_collection_unchanged`, `test_FR_0_0_04_no_pytest_config_outside_lab`, `test_FR_0_0_04_no_test_basename_collisions`
- Output (same command as FR-0.0-02):
```text
tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_all_five_markers_registered PASSED
tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_lab_tests_use_only_registered_markers PASSED
tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_harness_collection_unchanged PASSED
tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_no_pytest_config_outside_lab PASSED
tests/aqis_lab/test_aqis_markers.py::test_FR_0_0_04_no_test_basename_collisions PASSED
```
- Harness re-run with every lab file present (commit `5a8c50b`, same harness venv and command as FR-0.0-11), real output:
```text
=================== 1 failed, 21 passed, 1 warning in 6.00s ====================
GIT STATUS (incl. ignored) IDENTICAL
identical per-test outcomes: True 22 22
```
(the last line compares the per-test outcomes in the two JUnit files, baseline vs re-run)
- Status: DONE

### FR-0.0-11 — harness regression baseline
- Record: `docs/baselines/harness_tests_baseline.md` (commit `e223af1`, taken before any lab file existed). The two tests were written after the record (they check it); the mutation check below shows they fail when the record is incomplete.
- Tests: `test_FR_0_0_11_baseline_records_command_and_environment`, `test_FR_0_0_11_baseline_lists_every_harness_test` (expected list computed by AST from `tests/regression`)
- Command (full form in the baseline document): `PYTHONDONTWRITEBYTECODE=1 "$HARNESS_VENV/bin/python" -m pytest tests/regression -rA -p no:cacheprovider --junitxml=...`
- Output (real excerpt):
```text
FAILED tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge
=================== 1 failed, 21 passed, 1 warning in 6.33s ====================
EXIT=1
GIT STATUS (incl. ignored) IDENTICAL
```
- Mutation check: deleting the `test_rtp_sequence_reset` row from the baseline made the test fail: `AssertionError: missing ['tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_reset'], unknown []` (file restored afterwards).
- Status: DONE (the one failure is recorded, not fixed, as the spec requires)

### FR-0.0-05 — audit gate checks (a) to (d), CLI, merge-base, JSON
- Tests (`tests/aqis_lab/test_aqis_gate_checks.py`, fixture repositories with a bare origin): `test_FR_0_0_05_a_detects_never_path`, `test_FR_0_0_05_a_detects_guarded_path_without_approval`, `test_FR_0_0_05_a_passes_guarded_path_with_main_approval`, `test_FR_0_0_05_a_ignores_approval_committed_only_on_branch`, `test_FR_0_0_05_a_ignores_expired_or_withdrawn_approval[WITHDRAWN-|APPROVED-EXPIRES]`, `test_FR_0_0_05_b_detects_modified_existing_test`, `test_FR_0_0_05_b_detects_deleted_existing_test`, `test_FR_0_0_05_b_passes_new_test_and_approved_edit`, `test_FR_0_0_05_c_detects_each_code_pattern`, `test_FR_0_0_05_c_detects_each_test_pattern`, `test_FR_0_0_05_c_scans_only_added_lines`, `test_FR_0_0_05_c_includes_uncommitted_and_untracked_work`, `test_FR_0_0_05_d_detects_new_module_without_header`, `test_FR_0_0_05_d_passes_module_with_header_or_short_file`, `test_FR_0_0_05_clean_branch_exits_zero`, `test_FR_0_0_05_uses_merge_base_not_ref_tip`, `test_FR_0_0_05_json_output_schema`, `test_FR_0_0_05_bad_base_ref_exits_2`
- Expected pattern hits come from the hand-written `tests/aqis_lab/fixtures/gate/expected.json`, not from gate output.
- Tests first: all 19 failed before `tools/audit/gate.py` existed (`No module named tools.audit.gate`, and the resulting empty JSON output).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_gate_checks.py -q -p no:cacheprovider` → `19 passed in 2.88s`. After the registry check was added, `test_FR_0_0_05_b_detects_deleted_existing_test` also asserts the registry finding E3: deleting the only test named by a registry row is correctly reported by check (e) too.
- Status: DONE

### FR-0.0-06 — parity with the Stop hook
- Tests (`tests/aqis_lab/test_aqis_gate_parity.py`): `test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos` × 16 scenarios. Each runs the real `.claude/hooks/stop_gate.py` (subprocess, `CLAUDE_PROJECT_DIR` = fixture) and the gate on the same repository and compares normalised (a) to (d) findings; every scenario except the 3 clean ones must produce findings. Also `test_FR_0_0_06_pattern_tables_identical_to_stop_hook` (labels, regex sources and flags, allow and header regexes, lab directories, hunk regex) and `test_FR_0_0_06_path_classification_identical_to_hook` (27 paths, 7 globs × 13 probes, compared with `_protected.py`, run with `python -B` so no bytecode is written in `.claude/`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_gate_exemptions.py tests/aqis_lab/test_aqis_gate_parity.py -q -p no:cacheprovider` → `22 passed in 4.49s`
- These tests were written after the (a) to (d) code; mutation checks M1, M3, M7 and M12 below show they fail when the gate diverges.
- Status: DONE. Accepted difference (owner decision 2): the gate reads approvals at `origin/main`; the hook reads them at the merge-base.

### FR-0.0-07 — exemptions listed
- Tests: `test_FR_0_0_07_audit_allow_with_reason_exempts_and_is_listed`, `test_FR_0_0_07_audit_allow_without_reason_does_not_exempt`, `test_FR_0_0_07_audit_allow_exempts_only_its_line`, `test_FR_0_0_07_allow_patterns_in_exempts_file_and_is_listed`
- Real gate output on this branch (exemptions section):
```text
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 4
  tests/aqis_lab/fixtures/gate/allow_lines.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/code_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tools/audit/patterns.py: tools/audit/patterns.py (WP-0.0.md)
```
- Mutation M2 (an audit-allow comment without a reason exempts the line) makes 3 of these tests fail.
- Status: DONE

### FR-0.0-08 — registry consistency
- Tests: `test_FR_0_0_08_detects_row_with_missing_test`, `test_FR_0_0_08_detects_row_with_missing_module`, `test_FR_0_0_08_detects_row_removed_since_base`, `test_FR_0_0_08_detects_malformed_row`, `test_FR_0_0_08_detects_missing_registry`, `test_FR_0_0_08_passes_consistent_registry`, `test_FR_0_0_08_repository_registry_is_consistent`
- Tests first: before check (e) existed, the detection tests failed (`assert [] == [('E3', 6), ('E3', 7)]`, `assert [] == [('E4', 6), ('E4', 7)]`, `assert [] == [('E5', 5)]`, `assert [] == [('E2', 6), ('E2', 7)]`, `assert [] == ['E1']`).
- `test_FR_0_0_08_detects_missing_registry` first expected only E1. The gate also reported E5, because every row present at the base is missing when the file is deleted, which is what FR-0.0-08 requires. The expectation of this new test was corrected to `["E1", "E5"]`.
- Status: DONE

### FR-0.0-09 — requirement traceability (`--wp`)
- Tests: `test_FR_0_0_09_detects_id_missing_from_plan`, `test_FR_0_0_09_detects_id_missing_from_test_names`, `test_FR_0_0_09_detects_id_missing_from_evidence`, `test_FR_0_0_09_underscore_matching_respects_boundaries`, `test_FR_0_0_09_ignores_other_wp_ids_in_spec`, `test_FR_0_0_09_reports_unknown_wp`, `test_FR_0_0_09_passes_complete_traceability`
- Rules as agreed (owner decision 1): FR/NFR IDs must be in PLAN.md, a test function name and EVIDENCE.md; AT/OC IDs in PLAN.md and EVIDENCE.md; only the WP's own IDs count.
- Tests first: before check (f) existed they failed (`assert [] == [('F3', 5)]`, `assert [] == [('F3', 4), ('F4', 4)]`, `assert [] == ['F1']`, ...).
- Command: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_gate_registry.py tests/aqis_lab/test_aqis_gate_trace.py -q -p no:cacheprovider` → `14 passed` (after the E1/E5 correction above).
- Status: DONE

### FR-0.0-10 — CI
- Tests: `test_FR_0_0_10_ci_triggers_push_and_pull_request`, `test_FR_0_0_10_ci_bootstraps_probe_python_and_hashed_lock`, `test_FR_0_0_10_ci_runs_fast_suite_with_exact_markers`, `test_FR_0_0_10_ci_gate_base_selection`, `test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows`
- Tests first: all 5 failed with `FileNotFoundError: ... .github/workflows/aqis-lab-ci.yml` before the file existed.
- Real CI run on push: https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36121608490 (run 1, commit `5a8c50b`, conclusion **success**). Real log excerpt:
```text
aqis_lab 0.0.1 commit=5a8c50b python=3.13.7
83 passed, 5 deselected in 11.99s
  EVENT_NAME: push
aqis-audit-gate: base origin/main (merge-base 475890df5238), head 5a8c50b65324, approvals origin/main 475890df5238, wp -
Findings: 0
0 findings: OK (0.1 s)
```
- The runner warns that `actions/checkout@v4` and `astral-sh/setup-uv@v6` target the deprecated Node.js 20 and are forced to run on Node.js 24. This is informational; both steps succeeded.
- The pull-request run is AT-0.0-04 (owner check).
- Status: DONE for the push event; the pull-request run is confirmed by the owner (AT-0.0-04).

### NFR-0.0-01 — gate runtime under 60 s
- Test: `test_NFR_0_0_01_gate_runtime_under_60s` (the real repository, `--base origin/main --wp WP-0.0`)
- Real runtime: the gate reports `(0.1 s)` on this repository (see "Audit gate" below).
- Status: DONE

### NFR-0.0-02 — file:line and rule in every message
- Test: `test_NFR_0_0_02_every_message_names_file_line_and_rule`. A single fixture repository triggers A1, A2, B1, B2, C1, C2, D1, E3, E4, F2, F3 and F4, and every finding line must match `path:line: [RULE] SEVERITY: message`. Mutation M4 (drop the rule from the message) makes it fail.
- Status: DONE

### NFR-0.0-03 — standard library plus pinned dependencies
- Test: `test_NFR_0_0_03_imports_are_stdlib_or_pinned`. An AST scan of every import in `aqis_lab/` and `tools/` checks it against `sys.stdlib_module_names`, first-party packages and the import names of packages pinned in `phase0.txt`. `tools/` must use the standard library only. Mutation M9 (`import yaml` in the gate) makes it fail.
- Status: DONE

## Mutation spot-checks (builder self-check, in a scratch clone outside the repository)
Each mutation was applied alone and reverted afterwards (real output):
```text
M1 drop 'hack' pattern => 5 failed, 18 passed, 65 deselected in 5.23s
M2 audit-allow without reason exempts => 3 failed, 1 passed, 84 deselected in 1.05s
M3 ignore STATUS: APPROVED => 1 failed, 23 passed, 64 deselected in 5.78s
M4 message without rule => 1 failed, 87 deselected in 0.45s
M5 no lookbehind boundary => 1 failed, 6 passed, 81 deselected in 1.84s
M6 skip removed-row check => 2 failed, 5 passed, 81 deselected in 1.35s
M7 ignore untracked in changes => 9 failed, 14 passed, 65 deselected in 5.93s
M8 version ignores untracked => 1 failed, 4 passed, 83 deselected in 0.93s
M9 gate imports yaml => 1 failed, 87 deselected in 0.12s
M10 bootstrap always recreates venv => 1 failed, 87 deselected in 0.46s
M11 bootstrap skips hash requirement => 1 failed, 87 deselected in 0.30s
M12 d-check threshold off-by-one => 3 failed, 17 passed, 68 deselected in 5.54s
```
M10 fails for the right reason: the `.venv` snapshot differs after the second run.

## Acceptance commands
### AT-0.0-01 — `bash aqis_lab/deploy/dev_bootstrap.sh && .venv/bin/python -m aqis_lab version`
```text
Colab probe requires Python 3.13 (docs/environment/colab_probe.txt)
Using uv 0.8.17 at /root/.local/bin/uv
Reusing .venv (Python 3.13)
Resolved 11 packages in 25ms
Audited 11 packages in 0.19ms
OK: .venv ready: Python 3.13.12, lock sha256 5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422
aqis_lab 0.0.1 commit=5a8c50b python=3.13.12
EXIT=0
```
In a fresh clone (first run, creating `.venv`), the same command gave `Installed 11 packages` and `aqis_lab 0.0.1 commit=5a8c50b python=3.13.12`.

### AT-0.0-02 — `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"`
```text
83 passed, 5 deselected in 15.04s
```
Slow and network CPU tests: `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow or network"` → `5 passed, 83 deselected in 6.41s`. Whole lab suite: `.venv/bin/python -m pytest tests/aqis_lab -q` → `88 passed in 19.86s`.

### AT-0.0-03 — `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0`
See "Audit gate" below.

### AT-0.0-04 — CI green on the pull request
Owner-run check; see below. The push-event run on the same workflow is green (FR-0.0-10).

## Audit gate
Command: `git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` (real output, exit code 0):
```text
aqis-audit-gate: base origin/main (merge-base 475890df5238), head 5a8c50b65324, approvals origin/main 475890df5238, wp WP-0.0
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 4
  tests/aqis_lab/fixtures/gate/allow_lines.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/code_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tools/audit/patterns.py: tools/audit/patterns.py (WP-0.0.md)
Findings: 0
0 findings: OK (0.2 s)
EXIT=0
```
The Stop hook also reports no problems on this branch (`echo '{"stop_hook_active": true}' | CLAUDE_PROJECT_DIR=$PWD python3 -B .claude/hooks/stop_gate.py` prints nothing).

## Owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| AT-0.0-04 CI green on the PR | GitHub → the WP-0.0 pull request → Checks (or the Actions tab) | Open the `aqis-lab-ci` run for the PR's latest commit (`pull_request` event) | Every step green; "Version" prints `python=3.13.x`; "Fast lab test suite" ends `83 passed, 5 deselected` (or more passed, no failures); the "Audit gate" step shows `EVENT_NAME: pull_request` and ends `0 findings: OK` | Pending (owner) |

Round 1 had no Colab or Oracle checks. Round 2 adds the Colab check OC-0.0-01, and the audit round 2 fixes settle Oracle (owner decision on F16). Both are listed under "Round 2 owner-run checks" below. (Corrected for audit finding F22.)

## audit-allow lines
None. No line in the repository carries an `audit-allow` exemption; the gate reports `Exempted lines (# audit-allow): 0`. Files exempted by the owner approval (`ALLOW-PATTERNS-IN`, `docs/approvals/WP-0.0.md`): `tools/audit/patterns.py`, `tests/aqis_lab/fixtures/gate/allow_lines.py`, `tests/aqis_lab/fixtures/gate/code_patterns.py`, `tests/aqis_lab/fixtures/gate/test_patterns.py`.

## Differences from the plan's file list (no behaviour deviations)
- Added `tests/aqis_lab/aqis_testutil.py`: shared test helpers (an independent probe and lock parser, hermetic git environment). It is not a test module.
- Added `test_FR_0_0_08_detects_missing_registry` (registry file deleted), beyond the planned FR-0.0-08 tests.
- Registry rows added beyond the plan's list:
  - `CAP-CLI-003`: `aqis_lab.__version__`.
  - `CAP-BASE-001`: the harness baseline record.
  - `CAP-AUDIT-009`: gate CLI and reports.
- Scope check: `git diff --stat origin/main...HEAD` touches only new lab files plus these existing files:
  - `docs/progress/STATUS.md`: WP-0.0 row only.
  - `docs/capabilities/REGISTRY.md`: appended rows only.
  - `docs/progress/BLOCKERS.md`: BLK-001 appended, then resolved.
  - No GUARDED or NEVER path is changed, and no path carries an absolute filesystem location.

---

# Round 2 (after audit round 1, Amendment 1)

- **Environment:** cloud VM (Ubuntu 24.04.4 LTS, x86_64).
  - Lab `.venv`: Python 3.13.12, uv 0.8.17, `phase0.txt` sha256 `5c9a64eb0ded6484…`.
  - Harness `.venv-harness`: Python 3.13.12, `harness-extras.txt` sha256 `339abead3e1b65b9…`.
- **Base:** `origin/main` `e4b38ac` (kit patch 2, Stop hook v3), with Round 2 approval `2528e74`.
- **Owner decisions:** R2-1 as amended by BLK-005 (option 1), R2-2, R2-3 A, R2-4, BLK-004 option 1.
- **Commits:** Round 2 commits run from `1ede332` to the end of this branch. Each requirement's tests were committed before its implementation, so the order can be checked with `git log --stat` (F07).

## Findings F01 to F10 (AT-0.0-08)
| Finding | Proof | Result |
| --- | --- | --- |
| F01 | `test_FR_0_0_02_uses_version_named_by_probe` (probe says 3.99, expects exit 1, `Python 3.99` in stderr, no `.venv`) | Auditor mutation `PY="3.13"`: `F01 PY=3.13 hard-coded => 1 failed, 9 passed, 93 deselected` |
| F02 | `test_FR_0_0_05_a_uses_approval_added_on_main_after_branch_point`, `test_FR_0_0_05_a_honours_withdrawal_on_main_after_branch_point` (`approve_on_main(..., merge_into_branch=False)`) | Auditor mutation `load_approvals(git, base)`: `F02 approvals at merge-base => 2 failed, 19 passed, 82 deselected` |
| F03 | `test_FR_0_0_01_version_marks_dirty_tree` now stages an edit and a deletion | Auditor mutation (`git diff --name-only` plus untracked): `F03 +dirty misses staged => 1 failed, 4 passed, 98 deselected` |
| F04 | `gate.py`: `read_changed_file`, `diff_against_base`, `load_protected`, registry, spec and test-file reads now raise `GateError` (exit 2). Tests: `test_FR_0_0_06_fails_closed_on_unreadable_changed_file`, `test_FR_0_0_06_fails_closed_when_protected_paths_unreadable[missing/directory]`, `test_FR_0_0_06_fails_closed_on_git_error` (the last also shows the Stop hook reports `GATE ERROR`) | Round 2 mutation R3 (dangling symlink skipped silently): `1 failed` |
| F05 | Docstring of `test_FR_0_0_04_harness_collection_unchanged` states its limits; its pytest subprocesses use `PYTHONDONTWRITEBYTECODE=1`. The combined run in `.venv-harness` is recorded under FR-0.0-04 below | Harness outcomes identical alone and combined (22 of 22) |
| F06 | `test_FR_0_0_08_module_headers_match_registry`, added before the fix (commit `9897ce2` fails, `7fb578d` passes). Headers and registry synced; the three package markers have full headers. Correction (audit F20): `ALLOW_REASON_RE` was not in the CAP-AUDIT-008 row until the round 2 audit fixes, which also added `LAB_CODE_DIRS`, `LAB_CI_FILES`, `LAB_TEST_DIR`, `SCANNED_SUFFIXES` and `glob_to_regex` | Passes; it caught one more mismatch during round 2 (the `harness_provision.py` header), which was fixed |
| F07 | NFR commands and output below. **History, stated accurately:** in round 1, the check (e), check (f) and FR-0.0-07 code landed in `3f7d52a` together with checks (a) to (d), **before** their tests were committed. The titles of `b8bbe52`, `65be1e1`, `6fe8c71` and `b2067a0` describe test files only. Pushed history is not rewritten. In round 2, tests and implementation are separate commits; example checked in a scratch clone: `1ede332` (tests only) `17 failed, 32 passed`, `5ae3ce3` (fix) `49 passed` | See below |
| F08 | Owner approved the round-1 additions (`docs/approvals/WP-0.0.md`, condition R2-4) | Approved |
| F09 | Replacement decoding everywhere; `repository_root` catches `TimeoutExpired`; F1 cites `docs/specs/**/<WP>-*.md:1`. Test: `test_FR_0_0_06_decodes_non_utf8_with_replacement` (a Latin-1 byte in a new and in a modified lab file gives the finding, exit 1, no traceback) | Passes |
| F10 | `test_FR_0_0_01_version_prints_package_commit_python` compares only with the AST-read `__version__`; the literal is gone | Passes |

## FR-0.0-06 (amended) — the gate matches Stop hook v2/v3, fails closed, wider scan
- **Tests** (`tests/aqis_lab/test_aqis_gate_v2.py` and `test_aqis_gate_parity.py`):
  - `test_FR_0_0_06_scans_v2_file_types_and_dirs`
  - `test_FR_0_0_06_flags_pytestmark_and_param_skips`
  - `test_FR_0_0_06_decodes_non_utf8_with_replacement`
  - the three `test_FR_0_0_06_fails_closed_*` tests
  - `test_FR_0_0_06_approvals_none_when_origin_main_unverifiable`
  - `test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos`, 20 scenarios; new: `v2_file_types`, `pytestmark`, `added_then_deleted_in_worktree`, `non_utf8`
  - `test_FR_0_0_06_pattern_tables_identical_to_stop_hook`, which also compares the suffixes and the CI-file glob
- **Tests first:** before the fix, `13 failed, 17 passed` (for example, `JSONDecodeError` when the gate crashed on non-UTF-8, `AttributeError: module 'tools.audit.patterns' has no attribute 'LAB_CODE_DIRS'`, AD file reported as `D` instead of `A`). After the fix: `30 passed in 7.62s`.
- **Stop hook v3** (`e4b38ac`) changes only memory and reporting ("Detection rules are unchanged from version 2"); the parity tests run against v3.
- **Round 2 mutations** (scratch clone, one at a time, real output):
```text
R1 old status mapping (AD as deleted) => 1 failed, 29 passed, 98 deselected in 7.01s
R2 drop shell pattern => 7 failed, 28 passed, 93 deselected in 8.02s
R3 dangling symlink skipped silently => 1 failed, 29 passed, 98 deselected in 7.60s
```
- **Status:** DONE. Differences G1 and G2 are accepted (R2-2) and documented in `docs/tools/AUDIT_GATE.md`.

## FR-0.0-10 (amended) — WP ID from the pull request title
- **Tests:**
  - `test_FR_0_0_10_ci_takes_wp_from_pr_title`
  - `test_FR_0_0_10_pr_title_parser`, which runs the workflow's own shell step with `PR_TITLE`/`GITHUB_ENV`:
    - accepts `WP-0.0 …`, `WP-0.12: …`, `WP-1.3`;
    - rejects a missing ID, `WP-0.0x`, lower case, brackets, `WP-0`, and a two-line title that tries to write its own `WP_ID=`;
  - `test_FR_0_0_10_ci_gate_base_selection` (updated to the amended gate step).
- **Tests first:** `6 failed, 2 passed` before the workflow change; `8 passed in 0.20s` after it.
- **Mutation:** R8 (title regex without the trailing boundary) gives `1 failed`.
- **Status:** DONE locally. The pull-request run is AT-0.0-04 / AT-0.0-07 (owner).

## FR-0.0-11 (amended) — provisioned baseline and the regression job
- **Record:** `docs/baselines/harness_tests_baseline.md`, with "Provisioned baseline (round 2)" (commit tested `d6b2364`) first and the round 1 baseline kept under "History (round 1)".
- **Tool:** `tools/harness/regression_check.py`.
- **CI job:** `harness-regression` (provision, run tests with JUnit output, regression check).
- **Tests:**
  - `test_FR_0_0_11_regression_check_flags_newly_failing_baseline_pass`
  - `test_FR_0_0_11_regression_check_flags_missing_baseline_pass`
  - `test_FR_0_0_11_regression_check_passes_same_or_better`
  - `test_FR_0_0_11_regression_check_rejects_unreadable_inputs`
  - `test_FR_0_0_11_regression_check_accepts_repository_baseline`
  - `test_FR_0_0_11_ci_has_harness_regression_job`
  - `test_FR_0_0_11_baseline_records_command_and_environment` and `test_FR_0_0_11_baseline_lists_every_harness_test`, both now requiring both sections
- **Tests first:** `5 failed` (module missing; no Round 2 section yet) before the implementation; `7 passed` after.
- **Mutation:** R7 (missing baseline tests tolerated) gives `1 failed`.
- **AT-0.0-06:** `PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m pytest tests/regression -rA -p no:cacheprovider --junitxml=<scratch>`. Real output:
```text
FAILED tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge
========================= 1 failed, 21 passed in 5.07s =========================
GIT STATUS (incl. ignored) IDENTICAL
```
  No import or collection errors.
- **Regression check on that report:** `.venv-harness/bin/python -B -m tools.harness.regression_check --junit <scratch>/r2_junit.xml`
```text
baseline: 22 tests, 21 passed; this run: 22 tests, 21 passed
RESULT: PASS
EXIT=0
```
- **Status:** DONE locally. AT-0.0-07 (the CI job green on the PR) is for the owner to confirm.

## FR-0.0-04 — combined run in the harness environment (F05)
`PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m pytest tests/regression tests/aqis_lab -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider -q --junitxml=<scratch>`, then a comparison of the harness test cases with the harness-only run:
Re-run after the round 2 audit fixes (audit F22: the earlier excerpt `2 failed, 128 passed` predated later tests):
```text
2 failed, 152 passed, 7 deselected in 41.75s
harness outcomes identical alone vs combined with lab tests: True 22 22 21 passed
FAILED tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge
FAILED tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_environment_matches_lock
```
The lab failure is expected in that environment: `test_FR_0_0_03_environment_matches_lock` asserts that the running interpreter is the lab `.venv`, and `.venv-harness` is not.

## FR-0.0-12 — harness provisioning
- **Files:**
  - `aqis_lab/deploy/harness_provision.sh`, a wrapper around `harness_provision.py` (standard library, system `python3` 3.10 or newer);
  - `requirements/aqis_lab/harness-extras.in` and `harness-extras.txt`, hash-checked;
  - `requirements/aqis_lab/harness-vcs.txt`, the TEN VAD commit `22a3bcd4…` (BLK-004 option 1);
  - `config/aqis_lab/harness_assets.json`: corpus commit `14796262a824…` (BLK-005 option 1), sha256 `ef4d5da1…`; FireRedVAD commit `7990aac…` with per-file sha256; torch not installed (R2-3).
- **Tests:**
  - Fast, each running the real script in a throwaway git tree with local sources:
    - `test_FR_0_0_12_places_data_only_in_ignored_paths`
    - `test_FR_0_0_12_second_data_run_downloads_nothing`
    - `test_FR_0_0_12_reads_corpus_at_pinned_commit`
    - `test_FR_0_0_12_fails_on_asset_checksum_mismatch`
    - `test_FR_0_0_12_rejects_lfs_pointer_file`
    - `test_FR_0_0_12_manifest_mismatch_is_an_error`
    - `test_FR_0_0_12_refuses_target_that_git_does_not_ignore`
    - `test_FR_0_0_12_never_writes_token` (sentinel `GITHUB_TOKEN` found nowhere in the tree, `.git` or the cache)
    - `test_FR_0_0_12_rejects_unknown_step`
    - `test_FR_0_0_12_harness_extras_lock_is_hash_pinned`
    - `test_FR_0_0_12_asset_pins_match_repository`
  - Slow and network, on this repository: `test_FR_0_0_12_provisions_harness_end_to_end`, `test_FR_0_0_12_second_run_downloads_nothing_within_60s`.
- **Tests first:** `8 failed` (script missing) before the implementation; later `6 failed` (`KeyError: 'tag'`) before the pin-by-commit change.
- **Mutations** (one at a time, real output):
```text
R4 corpus sha not verified => 1 failed, 10 passed, 117 deselected in 2.97s
R5 LFS pointer accepted => 1 failed, 10 passed, 117 deselected in 2.83s
R6 ignore check skipped => 1 failed, 10 passed, 117 deselected in 2.72s
R9 corpus read from working tree, not pinned commit => 1 failed, 10 passed, 117 deselected in 2.73s
```
- **First real run:** it found that tag `corpus-v1` does not contain the archive (BLK-005). My Round 2 plan had stated otherwise; the correction is in `PLAN.md`.
- **Where the harness expects its data, and how it is provided:**
  - clips at `corpus/audio/<name>.wav`: 229 symlinks into `~/.cache/aqis/corpus/<sha256>/extracted/`, inside the ignored real directory `corpus/audio/`;
  - weights at `pretrained_models/FireRedVAD/Stream-VAD`: a symlink into `~/.cache/aqis/firered/<commit>/repo/Stream-VAD`, inside the ignored `pretrained_models/`;
  - the tracked `corpus/manifest.json` is compared with the archive's copy (byte-identical) and never written.

### AT-0.0-05 — provision twice from scratch
Command: remove `.venv-harness`, `~/.cache/aqis`, `corpus/audio` and `pretrained_models` (all created by provisioning), then run `bash aqis_lab/deploy/harness_provision.sh` twice. Real output:
```text
run 1: exit=0 elapsed=44.2s Downloads this run: 5 RESULT: PASS git-status=[]
run 2: exit=0 elapsed=0.7s Downloads this run: 0 RESULT: PASS git-status=[]
```
Run 1 table (real):
```text
| system | PASS | already installed: git-lfs, libc++1, libopus0 |
| python | PASS | .venv-harness Python 3.13; installed run_phase.py install all, requirements/aqis_lab/harness-extras.txt (hash-checked), requirements/aqis_lab/harness-vcs.txt |
| ten-vad | PASS | ten_vad 1.0.6.8 at commit 22a3bcd4509d (pinned) |
| imports | PASS | imported numpy, scipy, soundfile, yaml, aiortc, av, websockets, opuslib, pytest, pytest_asyncio, webrtcvad, kaldi_native_fbank, ten_vad; TenVad native library loaded |
| torch | INFO | not installed, decision R2-3 |
| corpus | PASS | corpus-v1 from git at commit 14796262a824, sha256 ef4d5da1e30f verified; 229 manifest clips available under corpus/audio/ (229 links created) |
| weights | PASS | https://huggingface.co/FireRedTeam/FireRedVAD at 7990aaccc6b7: Stream-VAD/model.pth.tar, Stream-VAD/cmvn.ark sha256 verified, no LFS pointers; available at pretrained_models/FireRedVAD/Stream-VAD |
| git-status | PASS | git status --porcelain is empty |
```
The system packages were installed by the first provisioning attempt in this session. Its real output: `[PASS] system: installed git-lfs, libc++1; already present: libopus0`.

- **Slow and network suite:** `.venv/bin/python -m pytest tests/aqis_lab -v -p no:cacheprovider -m "slow or network"`
```text
tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_provisions_harness_end_to_end PASSED
tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_second_run_downloads_nothing_within_60s PASSED
====================== 7 passed, 121 deselected in 8.09s =======================
```
- **Status:** DONE.

## FR-0.0-13 — Colab harness setup
- **Doc:** `docs/colab/HARNESS_SETUP.md`, cells 1 to 6:
  1. settings;
  2. clone with the `GITHUB_TOKEN` secret in a one-off `-c http.extraHeader` for the clone command only;
  3. assert there is no extraheader in git config and the remote is unchanged;
  4. uv 0.8.17 if missing;
  5. provision and write the report;
  6. download the report.
- **Tests:** `test_FR_0_0_13_colab_doc_cells_are_valid_python`, `test_FR_0_0_13_token_used_only_for_the_clone_command`, `test_FR_0_0_13_one_provisioning_command_and_report`.
- **Tests first:** `3 failed` (`FileNotFoundError`) before the doc; `3 passed` after.
- **Owner-run check:** OC-0.0-01, below.
- **Status:** DONE, pending OC-0.0-01.

## NFR-0.0-01/02/03 — commands and output (F07)
- **Command:** `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_gate_nfr.py -v -p no:cacheprovider`
```text
tests/aqis_lab/test_aqis_gate_nfr.py::test_NFR_0_0_01_gate_runtime_under_60s PASSED
tests/aqis_lab/test_aqis_gate_nfr.py::test_NFR_0_0_02_every_message_names_file_line_and_rule PASSED
tests/aqis_lab/test_aqis_gate_nfr.py::test_NFR_0_0_03_imports_are_stdlib_or_pinned PASSED
============================== 3 passed in 0.62s ===============================
```
- **NFR-0.0-01:** the gate on this repository reports its own time: `0 findings: OK (0.2 s)`, see "Round 2 audit gate" below.
- **Mutations:** round 1 M4 (rule missing from the message) and M9 (`import yaml` in the gate) each made the NFR tests fail. `tools/harness/` and `aqis_lab/deploy/harness_provision.py` are also covered by `test_NFR_0_0_03_imports_are_stdlib_or_pinned` (standard library only).

## Round 2 fast suite
`.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` (AT-0.0-02): `121 passed, 7 deselected in 20.40s`.

## Round 2 owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| AT-0.0-04 and AT-0.0-07: CI green on the PR | GitHub, PR #1, Checks | Open the `aqis-lab-ci` run for the latest commit (`pull_request` event) | Job `lab` green, with the step "Work package ID from pull request title" printing `WP-0.0` and the gate running with `--wp WP-0.0`, ending `0 findings: OK`. Job `harness-regression` green, with the provisioning table all PASS (torch INFO) and `RESULT: PASS` from the regression check | Green on `9016ee7` (round 4): pull request run `36163086560` and push run `36163080671`, both jobs success. Earlier: `033322b` (BLK-006) pull request `36156782531`, push `36156776526`; `d35290b` (round 3) pull request `36151741552`. Owner to confirm on the latest commit |
| OC-0.0-01: Colab harness setup | Colab, fresh CPU runtime (x86_64) | Before the merge: in cell 1 of `docs/colab/HARNESS_SETUP.md` set `BRANCH = "claude/hopeful-noether-yinc4e"` (`main` has no provisioning script until the merge, audit F15). Run cells 1 to 6, then commit the downloaded file as `docs/environment/colab_harness_provision.txt` | A `platform / PASS / Ubuntu ... on Linux x86_64` row and every other row PASS (torch `INFO / not installed, decision R2-3`), `RESULT: PASS`, `exit code: 0`, `git status --porcelain: []`. A wrong branch stops cell 2 with `fatal: Remote branch <name> not found in upstream origin` and `RuntimeError: git clone of branch <name> from https://github.com/... failed (exit 128)`, with no command line shown | Pending (owner) |
| Oracle VM (owner decision F16, approval conditions round 3) | Oracle VM, only if it is Debian or Ubuntu on x86_64 | `bash aqis_lab/deploy/harness_provision.sh` in a clone of the branch | **Debian or Ubuntu on x86_64:** as on Colab. **Arm (aarch64):** exit 1 at once, a single row `platform / FAIL / harness provisioning needs Debian or Ubuntu on Linux x86_64; this machine is Linux aarch64. TEN VAD at commit 22a3bcd4509d ships its native library only for Linux x86_64 ... no Arm (aarch64) binary ...`. **x86_64 with another distribution** (for example Oracle Linux, `ID=ol`): exit 1 at once, a single row `platform / FAIL / harness provisioning needs Debian or Ubuntu on Linux x86_64; this machine runs ol (...), not debian or ubuntu. the system step installs packages with apt-get ...`. In both FAIL cases: `Downloads this run: 0`, `RESULT: FAIL`. The harness is not supported there; this is the owner's decision, not a defect | Not needed unless the owner runs the harness on Oracle (`docs/environment/oracle_probe.txt` is still missing) |

## Round 2 audit gate
Command: `git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` (AT-0.0-03). Real output:
```text
aqis-audit-gate: base origin/main (merge-base e4b38ac63d3f), head caa9a1e8fb03, approvals origin/main e4b38ac63d3f, wp WP-0.0
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 6
  tests/aqis_lab/fixtures/gate/allow_lines.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/code_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/non_utf8.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_pytestmark.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tools/audit/patterns.py: tools/audit/patterns.py (WP-0.0.md)
Findings: 0
0 findings: OK (0.2 s)
EXIT=0
```

AT-0.0-01 re-run: `bash aqis_lab/deploy/dev_bootstrap.sh && .venv/bin/python -m aqis_lab version` (last lines):
```text
OK: .venv ready: Python 3.13.12, lock sha256 5c9a64eb0ded6484a9bb7bf9b0fad9c5aa3ca321abfca499e24ceabd5461d422
aqis_lab 0.0.1 commit=caa9a1e+dirty python=3.13.12
EXIT=0
```
The commit shown is `+dirty` because this evidence file was being edited when the command ran.

## Round 2 audit fixes (F11 to F22)
Root causes, change budget and baseline are in `docs/progress/WP-0.0/FIXES.md`. The owner decisions on F16 (Linux x86_64 only, fail fast elsewhere) and F17 (approval conditions updated on `main` at `227dac4`) are recorded there. `origin/main` was merged first (`d0b387b`).

**Baseline before any change:**
- Fast suite: `121 passed, 7 deselected in 20.64s`.
- Slow and network suite: `7 passed, 121 deselected in 8.67s`.

**Test-first, red run.**
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not network" -k "FR_0_0_12 or FR_0_0_13"`.
- Run after the new tests and the config pins, before any code or doc fix. Result: `6 failed, 18 passed, 115 deselected in 9.71s`.
- The failures, each for the named reason:
```text
E   subprocess.CalledProcessError: Command '['git', '-c', 'http.extraHeader=Authorization: Basic eC1hY2Nlc3MtdG9rZW46Z2hwX0FVRElUX0YxNF90b2tlbl92YWx1ZV8wMTIzNDU2Nzg5YWJjZGVm', 'clone', '--branch', 'main', ...   (F14 reproduced: the base64 token is in the error)
E   assert '`BRANCH = "claude/hopeful-noether-yinc4e"`' in 'Run cells 1 to 6 on a fresh runtime.'   (F15)
E   assert 0 == 1  ... setarch linux32 ... RESULT: PASS   (F16: provisioning ran every step on an i686 machine)
E   AssertionError: ('system_packages', ... RESULT: PASS ...)  assert 0 == 2   (F21: a missing key gave PASS)
E   AssertionError: Stream-VAD/model.pth.tar is a Git LFS pointer, not content   (F21: no git lfs pull detail)
E   AttributeError: 'Provisioner' object has no attribute 'reinstall_reason'   (F18: no pip check in the skip)
```

**Guard code that was already correct (F11, F12, F13, F19).** For these findings the new tests pass as they should. Proof that they guard the code is the auditor's own mutations, applied one at a time in a scratch copy and reverted. Script: `scratchpad/mutate.py`; each line is `-m "not slow and not network" -k <filter>`.
```text
### F11 PR-title regex without ^ (.github/workflows/aqis-lab-ci.yml) -k 'FR_0_0_10': 1 failed, 6 passed, 132 deselected in 0.55s
### F12 step_verify blinded (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 2 failed, 17 passed, 120 deselected in 11.15s
### F13 skipped accepted (tools/harness/regression_check.py) -k 'FR_0_0_11': 1 failed, 8 passed, 130 deselected in 0.49s
### F13 TEN VAD commit never compared (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 1 failed, 18 passed, 120 deselected in 10.91s
### F19 F1 cites docs/specs (tools/audit/gate.py) -k 'FR_0_0_09 or NFR_0_0_02': 1 failed, 7 passed, 131 deselected in 2.09s
### F16 platform check removed (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 1 failed, 18 passed, 120 deselected in 11.24s
### F18 pip check removed (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 1 failed, 18 passed, 120 deselected in 11.46s
### F21 lfs detail dropped (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 1 failed, 18 passed, 120 deselected in 11.65s
### F21 required keys not checked (aqis_lab/deploy/harness_provision.py) -k 'FR_0_0_12': 1 failed, 18 passed, 120 deselected in 11.42s
### F14 clone with check=True (docs/colab/HARNESS_SETUP.md) -k 'FR_0_0_13': 1 failed, 4 passed, 134 deselected in 0.15s
```
The failing test in each case:
- F11: `test_FR_0_0_10_pr_title_parser`.
- F12: `test_FR_0_0_12_fails_when_tree_was_dirty_before` and `test_FR_0_0_12_fails_when_provisioning_dirties_tree`.
- F13: `test_FR_0_0_11_regression_check_flags_newly_skipped_baseline_pass` and `test_FR_0_0_12_rejects_ten_vad_at_other_commit`.
- F19: `test_FR_0_0_09_reports_unknown_wp`.
- F16: `test_FR_0_0_12_fails_fast_on_machine_without_ten_vad_binary`.
- F18: `test_FR_0_0_12_reinstalls_when_pip_check_fails`.
- F21: `test_FR_0_0_12_reports_lfs_pull_failure_detail` and `test_FR_0_0_12_rejects_config_missing_required_key`.
- F14: `test_FR_0_0_13_clone_failure_never_shows_token`.

| Finding | Fix | Tests (requirement) |
| --- | --- | --- |
| F11 | Rejected titles with the ID later in the title: `Guardrails WP-0.0`, `Fix typo, see WP-0.3 notes`, ` WP-0.0 leading space` | `test_FR_0_0_10_pr_title_parser` (FR-0.0-10) |
| F12 | Tests only; `step_verify` was already correct. (1) An untracked file exists before the run: `git-status` FAIL, `RESULT: FAIL`, exit 1. (2) The cache is inside the tree: `git status changed during provisioning`, `?? cache-in-tree/`, exit 1 | `test_FR_0_0_12_fails_when_tree_was_dirty_before`, `test_FR_0_0_12_fails_when_provisioning_dirties_tree` (FR-0.0-12) |
| F13 | (1) A skipped outcome of a baseline pass is a regression. (2) A real offline `pip install` of a local git package, built by an in-tree PEP 517 backend in a scratch venv: the pinned commit gives PASS; another commit gives `ten_vad commit is <first>, pinned <second>`; a plain-folder install gives `commit is None` | `test_FR_0_0_11_regression_check_flags_newly_skipped_baseline_pass` (FR-0.0-11), `test_FR_0_0_12_rejects_ten_vad_at_other_commit` (FR-0.0-12) |
| F14 | Cell 2 keeps only the exit code (no `check=True`), sets `GIT_TERMINAL_PROMPT=0`, deletes the token and header before checking the result, and raises `RuntimeError` naming only the branch and the repository | `test_FR_0_0_13_clone_failure_never_shows_token` runs cells 1 and 2 for real, with a failing clone and a stand-in for `google.colab.userdata`. The token and its base64 form are in neither the traceback, the output nor any variable left behind (FR-0.0-13) |
| F15 | The OC-0.0-01 steps start with `BRANCH = "claude/hopeful-noether-yinc4e"` and state the output for a wrong branch. The EVIDENCE owner-run row matches | `test_FR_0_0_13_oc_steps_use_pull_request_branch` (FR-0.0-13) |
| F16 | Owner decision: a `platform` pin (`Linux`, `["x86_64"]`, with the reason) in `harness_assets.json`. `check_platform` runs before any step. Elsewhere there is a single `platform` FAIL row naming the machine and saying TEN VAD has no Arm binary, with 0 downloads and nothing written. Documented in both script headers, `docs/colab/HARNESS_SETUP.md` and the owner-run table | `test_FR_0_0_12_platform_pin_is_linux_x86_64`, `test_FR_0_0_12_fails_fast_on_machine_without_ten_vad_binary`, which uses `setarch linux32`, a real non-x86_64 machine type (FR-0.0-12) |
| F17 | Owner updated `docs/approvals/WP-0.0.md` on `main` (`227dac4`): corpus at commit `1479626`, TEN VAD pinned in `harness-vcs.txt`. Merged at `d0b387b` | Gate below reads approvals at `227dac4` |
| F18 | `pip check` added to the install skip, as the plan says (`reinstall_reason`). The `dev_bootstrap.sh` change log line was added. Remaining differences are listed below | `test_FR_0_0_12_reinstalls_when_pip_check_fails` (FR-0.0-12) |
| F19 | Assertion that F1 cites `docs/specs/**/WP-8.8-*.md` at line 1 | `test_FR_0_0_09_reports_unknown_wp` (FR-0.0-09) |
| F20 | CAP-AUDIT-008 lists `ALLOW_REASON_RE`, `LAB_CODE_DIRS`, `LAB_CI_FILES`, `LAB_TEST_DIR`, `SCANNED_SUFFIXES`, `glob_to_regex`, with a matching description. The F06 line above is corrected | `test_FR_0_0_08_module_headers_match_registry`, gate check (e) |
| F21 | Required config keys: a missing key gives exit 2, `ERROR: ... has no '<key>' key`. The `git lfs pull` exit code and last stderr lines go into the weights FAIL detail. `git cat-file blob` gets a 3600 s timeout, with `TimeoutExpired`/`OSError` turned into a FAIL row | `test_FR_0_0_12_rejects_config_missing_required_key`, `test_FR_0_0_12_reports_lfs_pull_failure_detail` (FR-0.0-12). There is no test for the timeout itself: a git read of more than an hour cannot be produced in a test |
| F22 | Corrected: the owner-run note, the provisioning test docstring, `AUDIT_GATE.md` (an unreadable approval does not count; that is the one read that does not exit 2), and the FR-0.0-04 combined run excerpt (re-run: `2 failed, 152 passed`, harness outcomes identical). The FireRedVAD licence (`Apache-2.0`, from `license: apache-2.0` in `README.md` at the pinned commit) is recorded in `harness_assets.json` | Documentation |

### Differences from the Round 2 plan (audit F18; for the owner's acknowledgement)
1. **Python module.** `aqis_lab/deploy/harness_provision.py` holds the provisioning logic. The plan listed only `harness_provision.sh`, which is now a thin wrapper. Registry rows CAP-ENV-005 (the `.sh`) and CAP-ENV-006 (the pins file) were added for them.
2. **Test files.** `tests/aqis_lab/test_aqis_gate_v2.py` and `tests/aqis_lab/test_aqis_colab_doc.py` are new test files the plan did not name.
3. **`tools/audit/gate.py`.** `load_approvals` changed to take the approvals ref, and `check_registry` changed to fail closed on the base read. `glob_to_regex` moved to `tools/audit/patterns.py` so the gate and the pattern tables share one copy. None of these were in the budget table.
4. **`dev_bootstrap.sh`.** Its header test list changed (F06), although the plan said "Unchanged". The missing change log line has now been added. No code changed.
5. **CI `harness-regression` job.** It runs `tests/regression` alone, not together with the lab tests. The reasons:
   - In `.venv-harness`, `test_FR_0_0_03_environment_matches_lock` fails by design, because it asserts the lab `.venv`.
   - Every lab test would show up as "newly passing" in the regression check.

   The combined run is recorded above instead ("FR-0.0-04 — combined run", `True 22 22 21 passed`), and job `lab` runs the lab suite. **The owner is asked to acknowledge this, or to ask for the combined run in CI.**
6. **Round 2 audit fixes.**
   - New functions `check_platform`, `reinstall_reason` and `report`, and the `platform` and `firered.licence` config keys, listed in FIXES.md.
   - The Arm fail-fast is the owner's F16 decision, given in chat. The approval file on `main` does not record it yet.

**Suites after the fixes.**
- Fast suite: `132 passed, 7 deselected in 31.55s`.
- Slow and network suite, on the committed tree `a6c78af`: `7 passed, 132 deselected in 9.93s`, including `test_FR_0_0_12_provisions_harness_end_to_end` and `test_FR_0_0_12_second_run_downloads_nothing_within_60s`; `git status --porcelain` empty afterwards.
- Before that commit, the two provisioning slow tests failed because the working tree held the uncommitted fixes. Provisioning reported `git-status | FAIL | git status --porcelain is not empty (it was not empty before provisioning either)`: the F12 behaviour, working as specified.

**AT-0.0-05 re-run after the fixes.** A fresh `git clone --no-local` of `a6c78af` with no `.venv-harness`, `corpus/audio` or `pretrained_models`, and an empty `AQIS_CACHE`. Command: `bash aqis_lab/deploy/harness_provision.sh`, run twice:
```text
run 1 exit=0 elapsed=48.3s git-status=[]
run 2 exit=0 elapsed=1.1s git-status=[]
```
Run 1 table (real output):
```text
| Step | Result | Detail |
| --- | --- | --- |
| platform | PASS | Linux x86_64 |
| system | PASS | already installed: git-lfs, libc++1, libopus0 |
| python | PASS | .venv-harness Python 3.13; installed (first install) run_phase.py install all, requirements/aqis_lab/harness-extras.txt (hash-checked), requirements/aqis_lab/harness-vcs.txt |
| ten-vad | PASS | ten_vad 1.0.6.8 at commit 22a3bcd4509d (pinned) |
| imports | PASS | imported numpy, scipy, soundfile, yaml, aiortc, av, websockets, opuslib, pytest, pytest_asyncio, webrtcvad, kaldi_native_fbank, ten_vad; TenVad native library loaded |
| torch | INFO | not installed, decision R2-3 |
| corpus | PASS | corpus-v1 from git at commit 14796262a824, sha256 ef4d5da1e30f verified; 229 manifest clips available under corpus/audio/ (229 links created) |
| weights | PASS | https://huggingface.co/FireRedTeam/FireRedVAD at 7990aaccc6b7: Stream-VAD/model.pth.tar, Stream-VAD/cmvn.ark sha256 verified, no LFS pointers; available at pretrained_models/FireRedVAD/Stream-VAD |
| git-status | PASS | git status --porcelain is empty |
Downloads this run: 5
RESULT: PASS
```
Run 2 ends with `| python | PASS | .venv-harness Python 3.13; requirements unchanged and pip check passes, nothing installed |`, `Downloads this run: 0` and `RESULT: PASS`.

## Round 3 audit fixes (F23 to F27)
Root causes and the change budget are in `docs/progress/WP-0.0/FIXES.md`, "Round 3 audit fixes". The owner's go-ahead and the new conditions are in `docs/approvals/WP-0.0.md` on `main` (`1bade2d`), merged here at `8a5383a`. Difference 5 above (the `harness-regression` job runs the harness tests on their own) is acknowledged there.

**Baseline before any change** (`8a5383a`), fast suite:
- git-lfs 3.4.1 (this VM): `132 passed, 7 deselected in 34.52s`.
- git-lfs 3.7.0 on PATH (the version on the GitHub runner, downloaded to the scratchpad): `1 failed, 131 passed, 7 deselected in 29.92s`. This reproduces the CI failure. The real CI log (job `lab`, run `36149406313`) shows the same: `FAILED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_reports_lfs_pull_failure_detail - AssertionError: Stream-VAD/model.pth.tar is a Git LFS pointer, not content`, `1 failed, 131 passed, 7 deselected in 17.81s`.

**Root cause checks** (scratch repositories, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`):
```text
pointer, no .gitattributes:  lfs 3.7.0 rc=0 "Skipping object checkout, Git LFS is not installed for this repository."   lfs 3.4.1 rc=2 "remote missing object"
pointer, LFS .gitattributes: lfs 3.7.0 rc=2 "remote missing object"   lfs 3.4.1 rc=2 "remote missing object"
real LFS content, no install:    lfs 3.7.0 rc=0 "Skipping object checkout ..." content: version https://git-lfs.g...   lfs 3.4.1 the same
real LFS content, install --local: lfs 3.7.0 rc=0 content: real model content   lfs 3.4.1 the same
```

**Test-first, red run.** New tests added, before any code change. `-m "not slow and not network"`, `test_aqis_harness_provision.py`: `5 failed, 20 passed` with git-lfs 3.4.1, and the same 5 with 3.7.0. The failures:
```text
E   [FAIL] weights: Stream-VAD/model.pth.tar is a Git LFS pointer, not content   (F23: real LFS content not checked out without a global LFS install)
E   AssertionError: Stream-VAD/model.pth.tar is a Git LFS pointer, not content   (F26: no git lfs output when the pull exits 0)
E   KeyError: 'distributions'   (F24: no distribution pin)
E   assert 0 == 1 ... | platform | PASS | Linux x86_64 | ... RESULT: PASS   (F24: a distribution outside the pin ran every step)
E   AttributeError: 'Provisioner' object has no attribute 'venv_problem'   (F27)
```
With the realistic `.gitattributes` in the fixture, `test_FR_0_0_12_reports_lfs_pull_failure_detail` (the CI failure) passes on both git-lfs versions. It did not need to change.

**After the fixes** (`test_aqis_harness_provision.py`, fast): `25 passed, 3 deselected` with git-lfs 3.4.1 and `25 passed, 3 deselected` with git-lfs 3.7.0.

**Mutations.** Each fix was removed in turn in a scratch copy, then restored. Script: `scratchpad/mutate3.py`.
```text
### F23 no git lfs install --local (git-lfs 3.4.1) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 16.47s
### F23 no git lfs install --local (git-lfs 3.7.0) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 15.13s
### F26 no output when pull exits 0 (git-lfs 3.4.1) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 15.09s
### F26 no output when pull exits 0 (git-lfs 3.7.0) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 15.00s
### F24 distribution not checked (git-lfs 3.4.1) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 15.99s
### F25 no sudo prefix (git-lfs 3.4.1) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 15.92s
### F27 venv_problem ignores pip (git-lfs 3.4.1) -m 'not slow and not network' -k 'FR_0_0_12': 1 failed, 24 passed, 121 deselected in 13.12s
### F27 step_python ignores venv_problem (git-lfs 3.4.1) -m 'slow or network' -k 'rebuilds_venv': 1 failed, 145 deselected in 2.18s
```
The F27 step mutation fails for the named reason: `[FAIL] python: python scripts/run_phase.py install failed (exit 1): .../.venv-harness/bin/python: No module named pip`.

| Finding | Fix | Tests (requirement) |
| --- | --- | --- |
| F23 | `step_weights` runs `git lfs install --local` in the weights cache clone before `git lfs pull`, so Git LFS works whatever the machine's global or system git config says. The fixture's weights repository carries the LFS `.gitattributes` rule of the real Hugging Face repository (`*.tar filter=lfs ...`) | `test_FR_0_0_12_fetches_lfs_content_without_global_lfs_install`: a real LFS repository in the test's folder, a hermetic git config, and the content checked out. The CI test `test_FR_0_0_12_reports_lfs_pull_failure_detail` now passes on git-lfs 3.4.1 and 3.7.0 (FR-0.0-12) |
| F24 | `check_platform` also requires the `/etc/os-release` ID to be `debian` or `ubuntu` (the new `distributions` pin, owner decision F16). Otherwise there is a single `platform` FAIL row naming the distribution and the reason, with nothing run, downloaded or written. The Oracle owner-run row reads "Debian or Ubuntu on x86_64" and gives the expected FAIL rows for Arm and for other distributions. The platform notes in the Colab doc and the script headers are updated | `test_FR_0_0_12_platform_pin_is_debian_or_ubuntu`, `test_FR_0_0_12_fails_fast_on_unsupported_distribution` (FR-0.0-12) |
| F25 | Test only; `step_system` was correct. The test runs the script as an unprivileged user: as uid 65534 through `setpriv` when root, directly otherwise. Stand-in `dpkg-query`, `sudo` and `apt-get` sit in the test's temporary folder, and the test asserts the exact calls `sudo -n apt-get update -y` and `sudo -n apt-get install -y aqis-standin-package`, run with a non-zero uid. It is never skipped. As the conditions require, the slow real-repository tests put stand-ins on PATH for `apt-get` and `sudo` that refuse to run. **Real non-root evidence from CI:** job `harness-regression`, run `36149406313` (runner user, not root) printed `DOWNLOAD: sudo -n apt-get update -y`, `DOWNLOAD: sudo -n apt-get install -y libc++1 libopus0` and `| system | PASS | installed libc++1, libopus0; already present: git-lfs |` | `test_FR_0_0_12_non_root_uses_sudo_for_missing_package` (FR-0.0-12) |
| F26 | Whenever pointer files remain after `git lfs pull`, the FAIL row carries git-lfs's exit code and last output lines: `git lfs pull failed (exit N): ...`, or `git lfs pull finished (exit 0) but left pointer files: ...` | `test_FR_0_0_12_reports_lfs_output_when_pull_leaves_pointers` (a pointer with an invalid oid; git-lfs exits 0) (FR-0.0-12) |
| F27 | New `venv_problem`: no working Python, the wrong Python, or no working pip means the venv is broken. `step_python` then prints `rebuilding .venv-harness: <reason>` and rebuilds it with `uv venv --seed --clear`, and fails only if it is still broken afterwards | `test_FR_0_0_12_venv_problem_detects_venv_without_pip` (fast), `test_FR_0_0_12_rebuilds_venv_left_without_pip` (slow, network: a clone whose `.venv-harness` has no pip is repaired, and `python`, `ten-vad` and `imports` PASS) (FR-0.0-12) |

**Suites after the fixes** (commit `d35290b`, clean tree):
```text
fast git-lfs 3.4.1: 138 passed, 8 deselected in 35.82s
fast git-lfs 3.7.0: 138 passed, 8 deselected in 32.45s
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_creates_venv_with_probe_python PASSED [ 12%]
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_second_run_changes_nothing_within_30s PASSED [ 25%]
tests/aqis_lab/test_aqis_bootstrap.py::test_FR_0_0_02_rejects_lock_with_wrong_hash PASSED [ 37%]
tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_provisions_harness_end_to_end PASSED [ 50%]
tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_second_run_downloads_nothing_within_60s PASSED [ 62%]
tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_rebuilds_venv_left_without_pip PASSED [ 75%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_is_reproducible PASSED [ 87%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_installable_with_plain_pip PASSED [100%]
================= 8 passed, 138 deselected in 91.49s (0:01:31) =================
git status lines after: 0
```

**CI on `d35290b`** (AT-0.0-04, AT-0.0-07; logs read through the GitHub API):
- Push run `36151733422` (run 39): `success`.
- Pull request run `36151741552` (run 40): job `lab` `success`, job `harness-regression` `success`.
- Job `lab` (`108126423593`), steps "Work package ID from pull request title" and "Audit gate":
```text
PR_TITLE: WP-0.0 Guardrails and audit tooling
Work package from the pull request title: WP-0.0
aqis-audit-gate: base origin/main (merge-base 1bade2dc66cc), head bceb1bbc4f40, approvals origin/main 1bade2dc66cc, wp WP-0.0
Findings: 0
0 findings: OK (0.2 s)
```
- The earlier red runs (`a6c78af`, `202c440`, `5cdf131`) all failed on the one git-lfs version test fixed here.

**Gate** (local): `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` → `Findings: 0`, `0 findings: OK (0.2 s)`. The Stop hook prints nothing.

## Colab owner check fix (BLK-006)
The owner's Colab verification (`docs/progress/WP-0.0/OWNER_VERIFY_COLAB_WP-0.0_20260925T151855Z.md`, on `aa9e74c`) failed on four tests. All four made scratch venvs with `python -m venv`, and `ensurepip` fails there: Colab's Python 3.13 is Ubuntu's, without `python3.13-venv`.

The owner's decision (BLK-006 option 1, CONDITIONS in `docs/approvals/WP-0.0.md`):
- The shared helper `pip_venv` in `tests/aqis_lab/aqis_testutil.py` makes those venvs with `uv venv --seed`, as provisioning does.
- `scratch_venv` in `test_aqis_harness_provision.py` and the venv creation line of `test_FR_0_0_03_lock_installable_with_plain_pip` use it. Assertions are unchanged.

Reproduction and proof, on a Colab-like Python (uv-installed CPython 3.13.7 with its `ensurepip` wheels removed; details in FIXES.md):
```text
before:  4 failed   (test_FR_0_0_12_rejects_ten_vad_at_other_commit, test_FR_0_0_12_reinstalls_when_pip_check_fails,
                     test_FR_0_0_12_venv_problem_detects_venv_without_pip, test_FR_0_0_03_lock_installable_with_plain_pip)
after:   4 passed, 142 deselected in 10.85s
```
On this VM the fast suite gives `138 passed, 8 deselected in 27.53s`.

The owner's Colab report also shows every other check as PASS or INFO. Version, gate and a clean `git status` passed. The harness tests gave `1 failed, 21 passed`, the recorded baseline.

### BLK-006 records completed (audit finding F32)
- **Gate** on `033322b` (the BLK-006 commit, run locally before pushing): `0 findings: OK (0.2 s)`. The Stop hook printed nothing.
- **Slow suite** on `033322b`, clean tree: `8 passed, 138 deselected in 60.39s`, `git status lines: 0`.
- **CI on `033322b`:** pull request run `36156782531` (`lab` success, including the "Work package ID from pull request title" and "Audit gate" steps; `harness-regression` success) and push run `36156776526` (both jobs success).
- **Owner's Colab re-run on `033322b`:** `docs/progress/WP-0.0/OWNER_VERIFY_COLAB_WP-0.0_20260925T155908Z.md` shows every check PASS (fast `138 passed`, slow `8 passed`, gate `0 findings`, clean tree), and harness tests INFO `1 failed, 21 passed`, the recorded baseline.
- **Difference not listed in round 3:** the `_about` text of `config/aqis_lab/harness_assets.json` was also edited in round 3 (`d35290b`) to name the round 3 platform conditions. That is text only; no key a program reads changed.
- **Status history:** STATUS stayed READY-FOR-AUDIT while BLK-006 was open (`8099955` to `d403bad`). It should have been marked blocked.

## Round 4 audit fixes (F28 to F32)
Root causes, change budget and the F31 system fix are in `docs/progress/WP-0.0/FIXES.md`, "Round 4 audit fixes". No gate or provisioning code changed: F28 and F29 add tests, F30 adds pins, and F31 and F32 correct the system and the records.

**New tests.**
- **Parity scenarios** in `test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos`:
  - `never_section_stripped`, `renamed_lab_test`, `renamed_harness_test`, `readme_approval`, `expired_approval` and `unapproved_status`, which cover checks (a) and (b);
  - `multi_pattern_line`, `late_header` and `modified_headerless_module`, which cover checks (c) and (d).

  Every rule in PLAN.md "Parity with the Stop hook" now has a scenario.
- **FR-0.0-05 detection tests:** `test_FR_0_0_05_a_builtin_never_list_applies_when_policy_section_removed`, `test_FR_0_0_05_a_approvals_readme_approves_nothing`, `test_FR_0_0_05_a_detects_renamed_guarded_harness_test` (A2 `D`, A2 `A`, B2) and `test_FR_0_0_05_b_detects_renamed_existing_lab_test` (B2).
- **FR-0.0-12:** `test_FR_0_0_12_asset_licences_recorded`.

**Test-first.** Against the current code, the 13 new F28 and F29 tests passed (`1 failed, 13 passed`). The gate is correct, so these tests prove themselves through the mutations below. The one failure was the F30 licence test: `E       KeyError: 'licence'`.

**Mutations** (the auditor's M26, M23, M24, M16, M17 and M18, plus the EXPIRES and STATUS rules). Each was applied alone to `tools/audit/gate.py` in a scratch copy, then restored. Command: `-m "not slow and not network" -k "FR_0_0_05 or FR_0_0_06"`.
```text
### M26 built-in NEVER list removed: 2 failed, 62 passed, 96 deselected in 15.09s
### M23 --no-renames removed from the committed diff: 4 failed, 60 passed, 96 deselected in 14.54s
### M24 README.md counted as an approval: 2 failed, 62 passed, 96 deselected in 14.61s
### M16 every matching pattern reported: 1 failed, 63 passed, 96 deselected in 15.18s
### M17 header searched in the whole module: 1 failed, 63 passed, 96 deselected in 15.03s
### M18 header required for modified modules too: 1 failed, 63 passed, 96 deselected in 14.73s
### MX EXPIRES ignored: 2 failed, 62 passed, 96 deselected in 15.88s
### MS any STATUS counts as approved: 3 failed, 61 passed, 96 deselected in 16.17s
```
Each mutation fails at least one named new test (FIXES.md lists them).

| Finding | Fix | Tests (requirement) |
| --- | --- | --- |
| F28 | Tests only. The built-in NEVER list survives a stripped `[NEVER]` section; `--no-renames` makes a renamed test a deleted test; `docs/approvals/README.md` approves nothing | 3 parity scenarios and 4 detection tests above (FR-0.0-05, FR-0.0-06) |
| F29 | Tests only. First pattern wins; header within the first 80 lines; header required only for new modules. EXPIRES and STATUS rules also added to parity | 5 parity scenarios above (FR-0.0-06) |
| F30 | `licence` for `ten_vad`: Apache-2.0 with Agora's additional conditions, condition 1 quoted, pointing to the LICENSE at commit `22a3bcd4509d`. `licence` for `corpus`: LibriSpeech CC BY 4.0 (https://www.openslr.org/12/) and MUSAN CC BY 4.0 (https://www.openslr.org/17/), both read from those OpenSLR pages on 2026-09-25 (`License: CC BY 4.0`, `License: Attribution 4.0 International (CC BY 4.0)`). The per-source registry belongs to WP-0.4 | `test_FR_0_0_12_asset_licences_recorded` (FR-0.0-12) |
| F31 | The `python3.13` link in `/root/.local/bin` was removed with `uv python uninstall`, and `command -v python3.13` now gives `/usr/bin/python3.13`. The two false sentences in FIXES.md and BLOCKERS.md now carry a correction note | System check commands in FIXES.md |
| F32 | The records above: BLK-006 gate, slow suite and CI; the CI row; the `_about` difference; the owner's Colab reports | Records |

**Suites after the fixes** (commit `9016ee7`, clean tree; git-lfs 3.7.0 from the scratchpad on PATH for the second line):
```text
fast git-lfs 3.4.1: 152 passed, 8 deselected in 32.97s
fast git-lfs 3.7.0: 152 passed, 8 deselected in 34.09s
slow/network: 8 passed, 152 deselected in 58.93s
gate: 0 findings: OK (0.3 s)
git status lines after: 0
commit: 9016ee7
```
**CI on `9016ee7`:** pull request run `36163086560`, success; push run `36163080671`, success; both jobs in each.

