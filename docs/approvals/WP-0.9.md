STATUS: APPROVED
WP: WP-0.9
APPROVED-BY: owner
DATE: 2026-10-04
PLAN: docs/progress/WP-0.9/PLAN.md
ALLOW-EDIT: tests/aqis_lab/test_aqis_ci.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_recording_docs.py
ALLOW-EDIT: tests/aqis_lab/aqis_baseline_testutil.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_tier2_baseline.py
CONDITIONS:
- Questions 1 to 10: as recommended in PLAN.md, except where stated below.
- Q1: accepted. Order: build, then /phase-audit 0 on this branch, then the memo links its report, then /wp-audit WP-0.9, then merge. E6 covers WP-0.0 to WP-0.8 (deviation D1). The owner has updated .claude/skills/phase-audit/SKILL.md.
- Q2: per-row debt table accepted, including the static-rules option for DEBT-004.
- Q3: DEBT-028: the raw-baseline line is in [NEVER], moved by the owner on main.
- Q4: Campaign A: not started: 0 of 22 recruited, 0 consents signed, 0 sessions recorded, quiet/noise split 0/0. Budget: 50 Colab units a month (Google AI Plus), planned use 40 of them.
- Q5: K11.5b, DEBT-016 and DEBT-009 closed as recorded permanent limits. For DEBT-009, the existing search of about 5,000 inputs (at most 4 passes against a limit of 10) is the evidence; no further search.
- Q6: "pack v1 plan" means the phase 1 Calibration and Campaign A packs. The memo states only what the sources fix and marks each open item as an owner decision.
- Q7: DEBT-024 is settled by the owner's WP-0.8 wording review.
- Q8: DEBT-025 moves to WP-4.5 (offline filler picker evaluation in the build plan).
- Q9: the committed Colab check is accepted as E2's Colab evidence.
- Q10: remove aqis-kit-patch-2.zip and aqis-kit-patch-3/ from the repository in this WP.
- Unit log: the logged 0.0434 units in docs/progress/WP-0.9/OC-0.9-01_units.csv is accepted; the Colab T4 smoke run (14:01Z, ~374 s) and OC-0.8-03 bootstrap are noted as unmetered sessions.
