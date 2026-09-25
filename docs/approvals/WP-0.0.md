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
- Round 3: fixes for WP-0.0-F23 to F27 approved as proposed on 2026-09-25: git lfs install --local before git lfs pull; always show git-lfs output when pointer files remain; rebuild a broken .venv-harness; the Oracle row reads "Debian or Ubuntu on x86_64"; a non-root test.
- F16 decision: harness provisioning supports Debian or Ubuntu on x86_64 only. Any other platform fails fast with one platform FAIL row naming the reason.
- CI: the harness-regression job runs the harness tests on their own, separately from the lab job, as described in EVIDENCE.md "Differences from the Round 2 plan". Both jobs must pass before merge.
- Tests and audits must never run real apt-get, sudo or other system-changing commands. Replace them with stand-in commands placed on PATH inside the test's temporary folder only.
- The non-root test runs the provisioning script as an unprivileged user (directly when not root, through setpriv when root). It must never be skipped, and it asserts that sudo -n is attempted for a missing package.
