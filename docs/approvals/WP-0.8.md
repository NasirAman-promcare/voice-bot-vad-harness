STATUS: APPROVED
WP: WP-0.8
APPROVED-BY: owner
DATE: 2026-10-02
PLAN: docs/progress/WP-0.8/PLAN.md
ALLOW-EDIT: tests/aqis_lab/aqis_packs_testutil.py
ALLOW-EDIT: tests/aqis_lab/test_aqis_registry_validate.py
CONDITIONS:
- BLK-013: RESOLVED. Sources committed in docs/specs/sources/.
- BLK-014: RESOLVED with the specific owner answers below:
  * (A) Split: By speaker (11 quiet room speakers, 11 everyday noise speakers, each recording 80 prompts).
  * (B) Transfer: One tar.gz archive per speaker session uploaded to MyDrive/AQIS_LAB/campaign_a/raw/.
  * (C) Format: Phone recorder original kept; converted to 16 kHz mono 16-bit PCM WAV.
  * (D) Quality checks: Clipping <= 0.1%, peak >= -30 dBFS and <= -1 dBFS, padding >= 0.3 s silence, verbatim prompt match.
  * (E) Noise sources: ns-fan, ns-traffic, ns-tv, ns-chatter, ns-kitchen, ns-generator, ns-ambient, ns-none.
  * (F) Accent groups: acc-south-asian-general, acc-urdu-influence, acc-punjabi-influence, acc-pashto-influence, acc-sindhi-influence, acc-neutral-urban, acc-other.
  * (G) Device & room: Handheld phone (10-15 cm, no headset); quiet room vs everyday noise room.
  * (H) DEBT-012: Edit allowed in aqis_packs_testutil.py and test_aqis_registry_validate.py to add changes field to test fixtures.
  * (I) DECISION: harm-rate = HR-B
  * (I) DECISION: margin = PM-B
  * (I) DECISION: timing-budget = TB-B
  * (I) DECISION: gate-escalation = GE-B
  * (I) DECISION: retention = 3 years from the date of recording, after which all voice recordings are permanently deleted.
- Questions 2 to 8: as recommended in PLAN.md.
