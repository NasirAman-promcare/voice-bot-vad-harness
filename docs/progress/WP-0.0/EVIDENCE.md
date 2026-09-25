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

No Colab or Oracle checks belong to WP-0.0.

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
