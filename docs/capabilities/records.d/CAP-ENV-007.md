CAP: CAP-ENV-007
Module: `aqis_lab/deploy/oracle_setup.sh`
Functions: whole script
What it does: Oracle setup in six steps (platform, tools, python, wheels, venv, doctor): refuses an architecture, operating system or glibc outside the `setup` pin of `config/aqis_lab/oracle.yaml` before doing anything; needs git and uv 0.8.17; names every lock package without a binary build for this machine, except the owner-approved source-only packages in `SOURCE_BUILDS` (`srt`, WP-0.7 question 2 (a)); builds `.venv` with `dev_bootstrap.sh`; runs `doctor --target oracle` and exits with its status; `--dry-run` explains each step and changes nothing; idempotent; works when started from any folder (round 2, F05)
Tests: `test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing`, `test_FR_0_6_01_refuses_unsupported_architecture`, `test_FR_0_6_01_refuses_unsupported_operating_system`, `test_FR_0_6_01_refuses_glibc_below_minimum`, `test_FR_0_6_01_setup_pin_read_by_script_equals_yaml`, `test_FR_0_6_01_missing_build_names_the_package`, `test_FR_0_6_01_fails_when_uv_missing`, `test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor`, `test_FR_0_6_01_second_run_changes_nothing`, `test_FR_0_6_01_runs_from_any_directory`, `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds`
Introduced by: WP-0.6 FR-0.6-01
Status: ACTIVE
