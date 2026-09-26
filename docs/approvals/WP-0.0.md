STATUS: APPROVED
WP: WP-0.0
APPROVED-BY: owner
DATE: 2026-09-25
PLAN: docs/progress/WP-0.0/PLAN.md (Round 1 and Round 2 sections)
ALLOW-PATTERNS-IN: tools/audit/patterns.py
ALLOW-PATTERNS-IN: tests/aqis_lab/fixtures/**
CONDITIONS:
- Round 2 approved as written in PLAN.md "Round 2", with these answers.
- R2-1: option A. Take corpus-v1.tar.gz from git at commit 1479626 and verify its SHA-256 (ef4d5da1...).
- R2-2: accept G1 and G2; document both in docs/tools/AUDIT_GATE.md.
- R2-3: option A. Do not install torch; the provisioning report must list it as "not installed, decision R2-3".
- R2-4: the round-1 additions (aqis_testutil.py, CAP-CLI-003, CAP-BASE-001, CAP-AUDIT-009, test_FR_0_0_08_detects_missing_registry) are approved.
- Pin TEN VAD commit (22a3bcd4...) in requirements/aqis_lab/harness-vcs.txt and verify after install.
- Stop hook v3 (kit patch 2) is on main.
- Round 3: fixes for WP-0.0-F23 to F27 approved.
- F16 decision: harness provisioning supports Debian or Ubuntu on x86_64 only. Any other platform fails fast with one platform FAIL row naming the reason.
- CI: the harness-regression job runs the harness tests on their own, separately from the lab job. Both jobs must pass before merge.
- Tests and audits must never run real apt-get, sudo or other system-changing commands. Replace them with stand-in commands placed on PATH inside the test's temporary folder only.
- Non-root test runs as unprivileged user and asserts sudo -n is attempted.
- BLK-006 decision: Option 1 approved (uv venv --seed for test helpers).
- Round 5: fixes for WP-0.0-F33 to F38 approved.
- OC-0.0-01: The Colab harness provisioning verification summary recorded in docs/environment/colab_harness_provision.txt and OWNER_VERIFY_COLAB_WP-0.0_20260925T155908Z.md is accepted.
- Round 6: fixes for WP-0.0-F39 to F44 approved (test coverage for gate hook parity rules, NFR requirement ID tracing in test names, provisioning weights/cache/apt checks, empty baseline table handling, TEN VAD native lib verification test, and documenting F44 symlink limit in AUDIT_GATE.md).
