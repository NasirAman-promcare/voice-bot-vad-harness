CAP: CAP-ENV-005
Module: `aqis_lab/deploy/harness_provision.sh`
Functions: whole script
What it does: Entry point for harness provisioning: runs harness_provision.py with the system python3 (3.10+) and passes options and exit code through
Tests: `test_FR_0_0_12_places_data_only_in_ignored_paths`, `test_FR_0_0_12_rejects_unknown_step`, `test_FR_0_0_12_provisions_harness_end_to_end`
Introduced by: WP-0.0 FR-0.0-12
Status: ACTIVE
