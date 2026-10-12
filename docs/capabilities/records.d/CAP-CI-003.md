CAP: CAP-CI-003
Module: `.github/workflows/aqis-lab-ci.yml`
Functions: job `lab-network`
What it does: CI job `lab-network` on push and pull request: the same bootstrap as job `lab`, then the lab tests marked only `network` (`-m "network and not slow and not gpu and not colab and not oracle"`), so every test whose only lab marker is `network` runs in CI; read-only permissions
Tests: `test_FR_0_0_10_ci_runs_network_only_tests`, `test_FR_0_0_10_ci_triggers_push_and_pull_request`, `test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows`
Introduced by: WP-0.9 DEBT-019
Status: ACTIVE
