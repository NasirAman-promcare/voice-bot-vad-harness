CAP: CAP-ENV-001
Module: `aqis_lab/deploy/dev_bootstrap.sh`
Functions: whole script
What it does: Builds `.venv` on the Colab Python major.minor with uv and installs the phase 0 lock with hash checking; idempotent; clear errors for a missing or unreadable probe and missing uv; passes the lock as `--build-constraints`, so the approved source-only package `srt` is built only with the lock's hash-checked setuptools (WP-0.7 question 2 (a)); `--gpu` also installs `phase0-gpu.txt` (WP-0.7 FR-0.7-03), with both locks as build constraints (WP-0.8 DEBT-021); an unknown option is an error
Tests: `test_FR_0_0_02_fails_when_probe_missing`, `test_FR_0_0_02_fails_when_probe_unreadable`, `test_FR_0_0_02_fails_when_uv_missing`, `test_FR_0_0_02_uses_version_named_by_probe`, `test_FR_0_0_02_creates_venv_with_probe_python`, `test_FR_0_0_02_second_run_changes_nothing_within_30s`, `test_FR_0_0_02_rejects_lock_with_wrong_hash`, `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints`, `test_FR_0_7_02_source_build_uses_only_the_locked_setuptools`, `test_FR_0_7_02_bootstrap_rejects_unknown_option`, `test_FR_0_7_03_bootstrap_gpu_needs_the_gpu_lock`, `test_FR_0_7_03_bootstrap_gpu_build_constraints_include_the_gpu_lock`, `test_FR_0_0_02_probe_repeating_one_version_is_accepted`, `test_FR_0_0_02_recreates_venv_built_on_another_python`
Introduced by: WP-0.0 FR-0.0-02
Status: ACTIVE
