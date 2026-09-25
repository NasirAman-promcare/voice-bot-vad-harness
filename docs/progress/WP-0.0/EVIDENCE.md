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
- Status: DONE (harness re-run comparison added at the end of the build, below)

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
