STATUS: APPROVED
WP: WP-0.4
APPROVED-BY: owner
DATE: 2026-09-27
PLAN: docs/progress/WP-0.4/PLAN.md
CONDITIONS:
- Questions 1-9: as recommended in PLAN.md.
- Deviation from FR-0.4-03, decided by the owner: the 10 "owner" clips are replaced by 10 synthetic TTS clips in data/tts_smoke/ (category "tts", source "tts"), generated with hexgrad/Kokoro-82M as recorded in data/tts_smoke/GENERATION.md. Their transcripts are the exact TTS input texts. They need no consent reference. Their licence is Apache-2.0 with attribution to hexgrad/Kokoro-82M.
- Keep the owner-recording and consent code paths and their tests, using generated test inputs, for the Phase 1 campaign recordings. No owner recordings are committed in phase 0; question 4 does not apply.
- Every document and report calls these clips synthetic, never recordings. They must never be used to judge or compare models.
- Round 2: fix WP-0.4-F01 (verify rejects non-regular files/broken symlinks), WP-0.4-F02 (verify rejects duplicate member paths), and WP-0.4-F06 (doc note). WP-0.4-F03 (target WP-0.8), WP-0.4-F04 (target WP-0.5), and WP-0.4-F05 (target WP-0.8) are accepted as debt in docs/progress/DEBT.md.
