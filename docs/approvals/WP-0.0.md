STATUS: APPROVED
WP: WP-0.0
APPROVED-BY: owner
DATE: 2026-09-25
PLAN: docs/progress/WP-0.0/PLAN.md (Round 1 and Round 2 sections)
ALLOW-PATTERNS-IN: tools/audit/patterns.py
ALLOW-PATTERNS-IN: tests/aqis_lab/fixtures/**
CONDITIONS:
- Round 2 approved as written in PLAN.md "Round 2", with these answers.
- R2-1: option A. Take corpus-v1.tar.gz from git at tag corpus-v1 and verify its SHA-256. This replaces "release asset" in FR-0.0-12(c).
- R2-2: accept G1 and G2; document both in docs/tools/AUDIT_GATE.md.
- R2-3: option A. Do not install torch; the provisioning report must list it as "not installed, decision R2-3".
- R2-4: the round-1 additions (aqis_testutil.py, CAP-CLI-003, CAP-BASE-001, CAP-AUDIT-009, test_FR_0_0_08_detects_missing_registry) are approved.
- Pin TEN VAD to the commit currently installed, in requirements/aqis_lab/harness-extras.txt.
- Stop hook v3 (kit patch 2) is on main. Merge origin/main first; its detection rules equal v2.
