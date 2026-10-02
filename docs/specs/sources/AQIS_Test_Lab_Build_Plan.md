# AQIS Test Lab — Build Plan
Sep 24, 2026 · @Nasir

## Summary
Build the lab in seven phases, 0 to 6. Each phase has its own run modes and its own right-sized dataset pack, and one locked final exam set, recorded from new speakers, is opened only in the last phase. GPU work runs on Colab as resumable batch jobs; CPU models, real-speed replays and live Jitsi tests run on your Oracle instances; paid APIs enter the scorecards as published benchmark numbers, not lab runs.

## Phases
- Phase 0: Foundations (Smoke pack: 60 clips)
- Phase 1: Data engine (Calibration pack: 2,000 synthetic clips; Campaign A: about 1,750 recorded turns)
- Phase 2: VAD, turn end, live STT (Live pack: about 3,500 real turns plus 6,000 sweep clips)
- Phase 3: Heavy STT and gate (Gate pack: about 3,000 turns plus 200 non-speech clips)
- Phase 4: Emotion and filler (Emotion pack: about 3,400 clips; filler pack: 500 rated turns)
- Phase 5: Fixes and diagnosis (Fix pack: 1,400 utterances x fix variants; Campaign B: about 1,000 turns, sealed)
- Phase 6: Final exam and pilot (Final exam set: 1,000 turns from 25 new speakers; 200 live turns)

## Two Recording Campaigns
### Campaign A
- When: Phase 1
- Speakers: 22, mixed accents, genders and ages
- Prompts per speaker: 80, about 30 minutes
- Prompt families:
  1. 15 short answers
  2. 10 digit strings
  3. 10 names and places
  4. 10 questions
  5. 10 requests or complaints
  6. 20 emotional variants
  7. 5 thinking pauses
- Conditions: Own phones; half quiet rooms, half everyday noise
- Total: About 1,760 turns

### Campaign B
- When: Phase 5
- Speakers: 25 new speakers, same kind of mix
- Prompts per speaker: 40, about 15 minutes
- Prompt families: The same families in proportion, with new items
- Conditions: Own phones, half quiet rooms, half everyday noise
- Total: About 1,000 turns, sealed
