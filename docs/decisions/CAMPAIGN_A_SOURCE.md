# Decision: Campaign A uses public recordings (owner, 2026-10-09)

Campaign A will not record people. Its 22 development speakers come from public datasets.

Sources
- Core: Svarah (ai4bharat/Svarah, CC BY 4.0): 16 speakers, chosen by a fixed rule that spreads accent groups and gender, with read and spontaneous speech.
- Accent spread: Common Voice English (CC0), test split, accent "India and South Asia": 6 speakers with at least 30 validated clips, if its current download route allows; otherwise 6 more Svarah speakers.
- Short answers and single digits: Google Speech Commands (CC BY 4.0), as a supplement for VAD short-utterance tests.
- Monsoon en-IN stays a separate public test layer and is not part of campaign A.

Final exam set (campaign B)
- 25 speakers not used above, drawn by a fixed rule and sealed with a checksum before any Phase 1 run.

Accepted gaps
- No digit strings read in chunks, no bot-domain prompts, no acted emotional variants by these speakers, and no recordings on our own call path.
- "Finished or pausing" truth comes from natural pauses inside spontaneous clips and from clip ends.
- Noisy conditions come from the scenario builder, not real rooms.
- Results are provisional for our callers until a real-call check before production.

Still needed from people
- Three raters for filler fit in Phase 4.
