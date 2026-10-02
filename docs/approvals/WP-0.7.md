STATUS: APPROVED
WP: WP-0.7
APPROVED-BY: owner
DATE: 2026-09-30
PLAN: docs/progress/WP-0.7/PLAN.md
ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_fetch.py
CONDITIONS:
- Questions 1 to 16: as recommended in PLAN.md, with the specifics below.
- Question 1: WebRTC VAD, mode 2, 20 ms frames (webrtc_vad_mode2 through the harness registry).
- Question 5: driver 580.82.07 is 580 or newer, so the GPU lock takes torch from PyPI (CUDA 13) as NeMo resolves it. No allowlist change.
- BLK-010: option 1. In tests/aqis_lab/test_aqis_registry_fetch.py change only test_FR_0_4_02_no_raw_corpus_committed, so that it also accepts data/runs/phase0-smoke/phase0-smoke-(cloud|colab|oracle)-<YYYYMMDDTHHMMSSZ>.tar and nothing else. Every other rule in that test stays as it is. The WP-0.7 test proving committed bundles hold no audio must stay.
- Approved: the Vosk adapter reseeds the C library random generator with 1 before every clip, recorded as c_rand_seed_per_clip: 1 in every Vosk run card.
- Approved: the --bundle-dir option of phase0 smoke; the run mode declared per runner task; the smoke launcher check accepting the approved dev_bootstrap.sh --gpu step.
- Noted: two tests (one FR-0.7-01 test and the 8 kHz VAD failure case) were written after their code; the must-catch breaks cover them.
- OC-0.7-01, OC-0.7-02 and the three-way parity check run after the audit, on the tagged commits. The audit lists them as pending by design, not as a finding.
