<!-- AQIS lab WP-0.8 FR-0.8-04. Tests read the three tables of this file (tests/aqis_lab/test_aqis_filler_library.py):
keep their columns, the fil-NNN and ctx-... IDs and the Source wording when editing. -->
# Filler library v0

A **filler** is a short phrase the voice bot says after the caller stops talking, while it prepares its answer. A bot cannot know a turn has ended as fast as a person can, so the filler buys time (blueprint, "Timing Budget": filler start under 150 ms, filler length 0.8 to 1.5 s). The filler selector picks one by voice emotion and dialogue act (blueprint, "Voice Emotion and the Filler Selector").

These are not the disfluencies ("um", "uh") that the WP-0.3 scorer removes from transcripts.

Version 0 is text only: no voice and no audio has been chosen. Every filler has an ID, a risk level, its text, its intended use and at least one context where it must never play. A filler ID never changes, even if its level does.

## Risk levels
The blueprint's risk ladder ("The Filler Library as a Risk Ladder"). The higher the level, the more the filler commits to, so the more it can hurt when it misfires.

| Level | Name | Commits to | Allowed when | Source |
| --- | --- | --- | --- | --- |
| 0 | Backchannel | Nothing | Always. | Blueprint, risk ladder, Level 0 |
| 1 | Process | Only that the bot is working | Always. | Blueprint, risk ladder, Level 1 |
| 2 | Empathy or warmth | The caller's feeling | Clear negative or positive tone, with high confidence. | Blueprint, risk ladder, Level 2 |
| 3 | Content judgement | What the caller said | Right dialogue act and suitable tone, with very high confidence. | Blueprint, risk ladder, Level 3 |

## Never-play contexts
Each context is defined once and filler rows refer to it by ID.
- **Blueprint contexts.** These come from the blueprint's never-play rules and from the risk ladder's "Allowed when" column.
- **Drafted contexts.** Contexts marked "Drafted in WP-0.8 for owner review" are not in the blueprint. The blueprint allows Level 0 and Level 1 fillers "Always", but FR-0.8-04 asks for at least one never-play context for every filler. These contexts come from what each phrase says, and the owner decides whether to keep them.

| Context ID | Never play when | Source |
| --- | --- | --- |
| ctx-negative-caller | The caller sounds negative or distressed. | Blueprint, Never-Play Contexts, rule 1 |
| ctx-complaint | The caller is making a complaint. | Blueprint, Never-Play Contexts, rule 1 |
| ctx-direct-question | The caller's turn is a direct question. | Blueprint, Never-Play Contexts, rule 2 |
| ctx-yes-no-answer | The caller's turn is a yes or no answer. | Blueprint, Never-Play Contexts, rule 2 |
| ctx-digit-string | The caller's turn is a digit string, such as a phone or account number. | Blueprint, Never-Play Contexts, rule 2 |
| ctx-low-confidence | The emotion or dialogue-act model's confidence is low (fall back to Level 0 or Level 1). | Blueprint, Never-Play Contexts, rule 3 |
| ctx-unclear-tone | The caller's tone is neither clearly negative nor clearly positive. | Blueprint, risk ladder, Level 2 "Allowed when" |
| ctx-positive-caller | The caller sounds pleased or cheerful (a sympathy filler would misread them). | Blueprint, risk ladder, Level 2 "Allowed when" |
| ctx-request-to-act | The caller asked the bot to do something, such as cancel or change an order: a plain "okay" can sound like a promise to do it. | Drafted in WP-0.8 for owner review |
| ctx-yes-no-question | The caller asked a yes or no question: a backchannel such as "mm-hmm" can sound like "yes". | Drafted in WP-0.8 for owner review |
| ctx-call-ending | The caller is saying goodbye or ending the call: there is nothing left to work on. | Drafted in WP-0.8 for owner review |
| ctx-thanks-only | The caller only said thank you: there is nothing to check or look into. | Drafted in WP-0.8 for owner review |

## Fillers
| ID | Level | Text | Intended use | Never play when |
| --- | --- | --- | --- | --- |
| fil-001 | 0 | "Okay." | Acknowledge any finished turn while the answer is prepared (blueprint example). | ctx-request-to-act, ctx-yes-no-question |
| fil-002 | 0 | "Mm-hmm." | Acknowledge a statement the caller has finished (blueprint example). | ctx-yes-no-question, ctx-request-to-act |
| fil-003 | 0 | "Right." | Acknowledge a statement or an explanation. | ctx-yes-no-question, ctx-request-to-act |
| fil-004 | 0 | "Uh-huh." | Acknowledge a short statement. | ctx-yes-no-question, ctx-request-to-act |
| fil-005 | 0 | "I see." | Acknowledge a description of a situation. | ctx-yes-no-question, ctx-call-ending |
| fil-006 | 1 | "One moment." | Cover a short wait while the bot works on the caller's request (blueprint example). | ctx-call-ending |
| fil-007 | 1 | "Let me check that." | Cover a lookup the caller's turn needs (blueprint example). | ctx-call-ending, ctx-thanks-only |
| fil-008 | 1 | "Just a second." | Cover a short wait while the bot works on the caller's request. | ctx-call-ending |
| fil-009 | 1 | "Let me look into that." | Cover a longer lookup for a question or a problem. | ctx-call-ending, ctx-thanks-only |
| fil-010 | 1 | "Bear with me a moment." | Cover a longer wait while the bot works on the caller's request. | ctx-call-ending, ctx-thanks-only |
| fil-011 | 2 | "I'm sorry to hear that." | Respond to a clear negative tone, with high confidence (blueprint example). | ctx-positive-caller, ctx-unclear-tone, ctx-low-confidence |
| fil-012 | 2 | "Great!" | Respond to a clear positive tone, with high confidence (blueprint example). | ctx-negative-caller, ctx-complaint, ctx-unclear-tone, ctx-low-confidence |
| fil-013 | 2 | "That sounds frustrating." | Respond to a clear negative tone, with high confidence. | ctx-positive-caller, ctx-unclear-tone, ctx-low-confidence |
| fil-014 | 2 | "Oh, that's lovely." | Respond to a clear positive tone, with high confidence. | ctx-negative-caller, ctx-complaint, ctx-unclear-tone, ctx-low-confidence |
| fil-015 | 2 | "I understand, that's not easy." | Respond to a clear negative tone, with high confidence. | ctx-positive-caller, ctx-unclear-tone, ctx-low-confidence |
| fil-016 | 3 | "That's a good point." | Respond to a statement that argues a point, when the dialogue act and tone suit it, with very high confidence (blueprint example). | ctx-direct-question, ctx-yes-no-answer, ctx-digit-string, ctx-low-confidence |
| fil-017 | 3 | "Good question." | Respond to an open, indirect question such as "I wonder why the price went up", with very high confidence; never a direct question (rule 2) (blueprint example). | ctx-direct-question, ctx-yes-no-answer, ctx-digit-string, ctx-low-confidence |
| fil-018 | 3 | "That makes sense." | Respond to the caller explaining their reasons, with very high confidence. | ctx-direct-question, ctx-yes-no-answer, ctx-digit-string, ctx-low-confidence |
| fil-019 | 3 | "Fair enough." | Respond to the caller stating a preference or a decision, with very high confidence. | ctx-direct-question, ctx-yes-no-answer, ctx-digit-string, ctx-low-confidence, ctx-negative-caller |
| fil-020 | 3 | "That's an interesting idea." | Respond to the caller suggesting something, with very high confidence. | ctx-direct-question, ctx-yes-no-answer, ctx-digit-string, ctx-low-confidence |
