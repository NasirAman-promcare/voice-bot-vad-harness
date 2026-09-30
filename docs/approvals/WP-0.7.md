STATUS: APPROVED
WP: WP-0.7
APPROVED-BY: owner
DATE: 2026-09-30
PLAN: docs/progress/WP-0.7/PLAN.md
ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py
CONDITIONS:
- Questions 1 to 16: as recommended in PLAN.md, with the specifics below.
- Question 1: WebRTC VAD, mode 2, 20 ms frames (webrtc_vad_mode2 through the harness registry).
- Question 5: driver 580.82.07 is 580 or newer, so the GPU lock takes torch from PyPI (CUDA 13) as NeMo resolves it. No allowlist change.
