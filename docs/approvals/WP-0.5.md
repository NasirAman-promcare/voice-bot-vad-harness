STATUS: APPROVED
WP: WP-0.5
APPROVED-BY: owner
DATE: 2026-09-28
PLAN: docs/progress/WP-0.5/PLAN.md
CONDITIONS:
- Questions 2-14: as recommended in PLAN.md.
- Colab unit rates from Build Plan (March 2026): cpu: 0.08 units/hr, Tesla T4: 1.19 units/hr, NVIDIA L4: 1.71 units/hr, NVIDIA A100-SXM4-40GB: 5.40 units/hr. Source: AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026).
- BLK-008: Option 1 approved. NFR-0.5-01 percentage overhead target is deferred to WP-0.7 and recorded in docs/progress/DEBT.md (target WP-0.7). In WP-0.5, record the measured ~25 ms fixed overhead in EVIDENCE.md.
- Round 2: fix WP-0.5-F02, F03, F04, F05, F06, F07, F08. WP-0.5-F01 is accepted as debt in docs/progress/DEBT.md (target WP-0.7). DEBT-009 is re-targeted to WP-0.9.
- Round 3: fix WP-0.5-F10 (assert launcher cell-1 variables are assigned exactly once in cell 1), WP-0.5-F11 (unit-log touch failure test), and WP-0.5-F12 (wording alignment for DEBT-014).
