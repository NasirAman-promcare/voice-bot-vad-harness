STATUS: APPROVED
WP: WP-0.7
APPROVED-BY: owner
DATE: 2026-10-02
PLAN: docs/progress/WP-0.7/PLAN.md
ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_fetch.py
ALLOW-EDIT: tests/aqis_lab/aqis_testutil.py
CONDITIONS:
- Questions 1 to 16: as recommended in PLAN.md, with the specifics below.
- Question 1: WebRTC VAD, mode 2, 20 ms frames (webrtc_vad_mode2 through the harness registry).
- Question 5: driver 580.82.07 is 580 or newer, so the GPU lock takes torch from PyPI (CUDA 13) as NeMo resolves it. No allowlist change.
- BLK-010: option 1 (test_FR_0_4_02_no_raw_corpus_committed in test_aqis_registry_fetch.py allows smoke bundles).
- BLK-011: option 1. In tests/aqis_lab/aqis_testutil.py, update hermetic_git_env only, adding git config to disable background auto-maintenance (maintenance.auto=0, gc.auto=0) in test repositories.
- Approved: the Vosk adapter reseeds the C library random generator with 1 before every clip, recorded as c_rand_seed_per_clip: 1 in every Vosk run card.
- Approved: the --bundle-dir option of phase0 smoke; the run mode declared per runner task; the smoke launcher check accepting the approved dev_bootstrap.sh --gpu step.
- Round 2 Fixes: fix WP-0.7-F01 (full expected lines for parity test including disfluency_aware), WP-0.7-F02 (test smoke trace failure handling), WP-0.7-F03 (test phase0 smoke exit 1 on failure), and WP-0.7-F04 (--from-scratch pass-through in phase0 smoke).
- Debt accepted: WP-0.7-F05 (target WP-0.8), WP-0.7-F06 (target WP-0.9), WP-0.7-F07 (target WP-0.8), and WP-0.7-F08 (target WP-0.8) accepted in docs/progress/DEBT.md.
- Noted: two tests (one FR-0.7-01 test and the 8 kHz VAD failure case) were written after their code; the must-catch breaks cover them.
- OC-0.7-01, OC-0.7-02 and the three-way parity check run after the audit, on the tagged commits. The audit lists them as pending by design, not as a finding.
