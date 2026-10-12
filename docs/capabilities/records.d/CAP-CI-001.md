CAP: CAP-CI-001
Module: `.github/workflows/aqis-lab-ci.yml`
Functions: job `lab`
What it does: CI job `lab` on push and pull request: bootstrap (Colab Python, hashed lock), version, fast lab suite, audit gate against the PR base with `--wp` from the PR title (or `origin/main` on push); read-only permissions
Tests: `test_FR_0_0_10_ci_triggers_push_and_pull_request`, `test_FR_0_0_10_ci_bootstraps_probe_python_and_hashed_lock`, `test_FR_0_0_10_ci_runs_fast_suite_with_exact_markers`, `test_FR_0_0_10_ci_takes_wp_from_pr_title`, `test_FR_0_0_10_pr_title_parser`, `test_FR_0_0_10_ci_gate_base_selection`, `test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows`
Introduced by: WP-0.0 FR-0.0-10 (amended round 2)
Status: ACTIVE
