# AQIS Test Lab — Blueprint for Testing VAD, Transcription and Voice Emotion Models
Sep 24, 2026 · @Nasir

## Timing Budget
Humans usually reply within about 0 to 200 ms, with a median near 100 ms across ten languages (Stivers et al., 2009). A bot cannot know a turn has ended that fast, so the filler buys time.
- Onset delay: Under 100 ms, plus a pre-roll buffer
- Turn-end delay: 300 to 700 ms, tuned per caller type
- Filler start: Under 150 ms
- Finalisation: Under 300 ms
- Gate decision: Under 50 ms
- Heavy turnaround: Filler length minus reply start-up
- Filler length: 0.8 to 1.5 s
- Latency condition: t_final + t_gate + t_heavy + t_reply <= t_turn_end + d_filler

## Voice Emotion and the Filler Selector
### The Filler Library as a Risk Ladder
- Level 0. Backchannel: Commits to nothing. Examples: "Okay.", "Mm-hmm." Allowed when: Always.
- Level 1. Process: Commits only that the bot is working. Examples: "One moment.", "Let me check that." Allowed when: Always.
- Level 2. Empathy or warmth: Commits to caller feeling. Examples: "I'm sorry to hear that.", "Great!" Allowed when: Clear negative or positive tone, with high confidence.
- Level 3. Content judgement: Commits to what caller said. Examples: "That's a good point.", "Good question." Allowed when: Right dialogue act and suitable tone, with very high confidence.

### Never-Play Contexts (Misfires & Harm)
- Never play Level 2 Empathy (positive/cheerful) on negative/distressed callers or complaints.
- Never play Level 3 Content judgement on direct questions, yes/no answers, or digit strings.
- Always fall back to Level 0 or Level 1 when model confidence is low.

## Quantitative Targets
- Harm rate target: Share of fillers rated 'wrong' (such as cheerful filler to upset caller) must be strictly below target (e.g., <2%).
- Practical margin: Win declared only if difference interval excludes zero and gap exceeds practical margin (e.g., >=0.5 points meaning-changing error).
- Timing budget: Estimated timing budget met on at least 90% of turns.
- Gate escalation limit: Gate evaluated at 10%, 20%, and 30% escalation rate.
