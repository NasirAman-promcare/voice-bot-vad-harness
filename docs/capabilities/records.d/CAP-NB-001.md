CAP: CAP-NB-001
Module: `notebooks/aqis_lab/phase0_launcher.ipynb`
Functions: 1 markdown and 5 code cells
What it does: Colab launcher with no logic: mounts Drive, clones the private repository at the pinned tag `AQIS_TAG` (the only variable the owner edits besides `RUN_ARGS`) with the `GITHUB_TOKEN` secret read only inside the clone's environment, installs the lock with `dev_bootstrap.sh`, and calls `drive layout`, `unitlog start`, `doctor --target colab`, `run` and `unitlog end`, every call with `check=True`
Tests: `test_FR_0_5_08_launcher_has_at_most_6_cells`, `test_FR_0_5_08_tag_is_one_variable_in_first_cell`, `test_FR_0_5_08_launcher_cells_contain_no_logic`, `test_FR_0_5_08_logic_checker_rejects_each_forbidden_form`, `test_FR_0_5_08_token_only_reaches_the_clone_command`, `test_FR_0_5_08_clone_failure_never_shows_token`, `test_FR_0_5_08_launcher_commands_exist_and_parse`, `test_FR_0_5_08_logic_checker_rejects_logic_inside_commands`
Introduced by: WP-0.5 FR-0.5-08
Status: ACTIVE
