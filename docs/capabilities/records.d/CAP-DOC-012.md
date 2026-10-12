CAP: CAP-DOC-012
Module: `docs/oracle/ORACLE_RUNBOOK.md`
Functions: before you start, clone, install uv and rclone, setup, doctor, core reservation, configure rclone, first sync, nightly schedule, report results back, when something fails, update
What it does: Oracle runbook: the owner's exact steps (read-only deploy key clone, uv 0.8.17 and rclone, `oracle_setup.sh`, doctor rows and minimums, cores 2-3 for timing and 0-1 for batch, headless rclone Drive setup with scope `drive`, sync, a `flock`-guarded nightly cron line, OC-0.6-01 and OC-0.6-02 reporting); commands parse and values equal the settings files
Tests: `test_FR_0_6_06_runbook_has_each_required_step`, `test_FR_0_6_06_runbook_commands_exist_and_parse`, `test_FR_0_6_06_runbook_matches_config`
Introduced by: WP-0.6 FR-0.6-06
Status: ACTIVE
