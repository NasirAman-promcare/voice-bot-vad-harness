STATUS: APPROVED
WP: WP-0.0
APPROVED-BY: owner
DATE: 2026-09-27
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
- F16 decision: harness provisioning supports Debian or Ubuntu on x86_64 only.
- CI: the harness-regression job runs the harness tests on their own, separately from the lab job.
- Tests and audits must never run real apt-get, sudo or other system-changing commands.
- BLK-006 decision: Option 1 approved (uv venv --seed for test helpers).
- Round 5: fixes for WP-0.0-F33 to F38 approved.
- OC-0.0-01: The Colab harness provisioning verification summary is accepted.
- Round 6: fixes for WP-0.0-F39 to F46 approved.
- BLK-007 decision: Option 1 approved (monkeypatch geteuid in root test).
- F44 accepted as a known limit: a test file replaced by a symlink is not reported by the hook or the gate.
- AT-0.0-04 and AT-0.0-07 confirmed green by the owner in the Actions tab.
- Round 8: debt entries DEBT-001 to DEBT-003 approved.
- Round 9 (final): fixes for WP-0.0-F56, F57, F58, F59 and F61 approved. F55 and F60 are accepted as debt in docs/progress/DEBT.md (target WP-0.9).
