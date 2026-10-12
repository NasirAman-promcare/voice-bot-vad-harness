CAP: CAP-DOC-001
Module: `docs/colab/HARNESS_SETUP.md`
Functions: cells 1 to 6
What it does: Colab cells: clone with the GITHUB_TOKEN secret for the clone command only (a failed clone shows only branch and repository), prove no token is kept, one provisioning command, report for OC-0.0-01 (run on the pull request branch before the merge)
Tests: `test_FR_0_0_13_colab_doc_cells_are_valid_python`, `test_FR_0_0_13_token_used_only_for_the_clone_command`, `test_FR_0_0_13_one_provisioning_command_and_report`, `test_FR_0_0_13_clone_failure_never_shows_token`, `test_FR_0_0_13_oc_steps_use_pull_request_branch`, `test_FR_0_0_13_clone_cells_never_store_token`
Introduced by: WP-0.0 FR-0.0-13
Status: ACTIVE
