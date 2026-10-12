CAP: CAP-TEST-001
Module: `tests/aqis_lab/conftest.py`
Functions: `pytest_configure`, `collect_ignore`
What it does: Registers the markers slow, gpu, colab, oracle, network for lab tests and keeps gate fixtures out of collection, without affecting harness test discovery
Tests: `test_FR_0_0_04_all_five_markers_registered`, `test_FR_0_0_04_lab_tests_use_only_registered_markers`, `test_FR_0_0_04_harness_collection_unchanged`, `test_FR_0_0_04_no_pytest_config_outside_lab`, `test_FR_0_0_04_no_test_basename_collisions`
Introduced by: WP-0.0 FR-0.0-04
Status: ACTIVE
