STATUS: APPROVED
WP: WP-0.8
APPROVED-BY: owner
DATE: 2026-10-02
PLAN: docs/progress/WP-0.8/PLAN.md
CONDITIONS:
- BLK-013: Option 1(a). Committed Build Plan and Blueprint text sources under docs/specs/sources/.
- Questions 2 to 8: as recommended in PLAN.md, with specific owner values below.
- Debt closing (Q2): Close all five debts (DEBT-010, DEBT-012, DEBT-018, DEBT-020, DEBT-021) in this WP.
- DEBT-012 (Q3): 'changes' field required for every dataset in datasets.yaml.
- DEBT-021 (Q4): Pass both CPU and GPU lock as build constraints in dev_bootstrap.sh --gpu.
- Consent scheme (Q5): Speaker ID is ca-sNNN (pseudonymous) and consent reference is ca-cNNN. Signed consent forms kept offline by owner.
- Consent facts (Q6):
  * (a) Access: Only the AQIS test lab owner (@Nasir) and authorized project raters/evaluators.
  * (b) Services: Google Drive (AQIS_LAB), Google Colab, and Oracle Cloud VM. Audio is never stored on GitHub.
  * (c) Purpose: Testing, benchmark measurement, and error diagnosis for voice bot pipelines.
  * (d) Minimum age: 18 years or older.
  * (e) Withdrawal: Right to withdraw within 30 days of recording; recordings will be deleted from active dataset pools.
  * (f) Contact: Owner blank [OWNER DECIDES: contact email/phone] filled in per printed copy.
- Targets & Retention (Q7): Documents keep owner blanks in options tables; formal DECISION lines added to approval after options review.
- Deviations (Q8): Accept deviations D1 (session date/notes), D2 (consent block), and D3 (never-play context IDs).
