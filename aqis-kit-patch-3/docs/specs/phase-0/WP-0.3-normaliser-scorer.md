# WP-0.3 — Text normaliser and scorer

- **Depends on**: WP-0.0, WP-0.2
- **Runs on**: cloud VM
- **Read first**: AQIS Test Lab blueprint section "Metrics catalogue"

## Goal
One text normaliser and one scorer that every system is judged by, producing corpus-level WER and CER with full error counts and traceable score rows.

## Deliverables
- `docs/contracts/NORMALISATION.md`, `docs/contracts/SCORE_TABLE.md`
- `aqis_lab/scoring/normalise.py`, `aqis_lab/scoring/wer.py`, `aqis_lab/scoring/table.py`
- `python -m aqis_lab score` command

## Functional requirements
- **FR-0.3-01** Wrap the Whisper English text normaliser at a pinned version; `normalise(text)` returns normalised text and the wrapper exposes the normaliser's name and version. Normalisation is idempotent.
- **FR-0.3-02** `NORMALISATION.md` documents the behaviour with at least 30 examples covering numbers, currency, dates, times, ordinals, contractions, hyphens, disfluencies, casing, punctuation and spelled-out letters. Every example is a test.
- **FR-0.3-03** Disfluencies: the main score removes the listed fillers (such as "um", "uh"); a disfluency-aware variant keeps them. Both are reported and labelled.
- **FR-0.3-04** Per-utterance alignment with substitutions, deletions, insertions, hits and reference length, plus CER. Empty references are defined: insertions count, per-utterance WER is undefined, and the utterance still enters corpus totals.
- **FR-0.3-05** Corpus-level WER is total errors divided by total reference words, never the mean of per-utterance WERs. Both numbers are reported, clearly labelled.
- **FR-0.3-06** Score rows carry `run_card_id`, `clip_id`, SHA-256 of reference and hypothesis, normaliser name and version, all counts, and are written as Parquet and CSV with the schema documented in `SCORE_TABLE.md`.
- **FR-0.3-07** Cross-check against an independent implementation (pinned `jiwer`) on at least 200 generated reference and hypothesis pairs: counts match exactly.

## Non-functional requirements
- **NFR-0.3-01** Deterministic; no network access.

## Acceptance commands
- **AT-0.3-01** The fast suite passes, including all 30+ documented examples and the cross-check.
- **AT-0.3-02** `python -m aqis_lab score --ref <fixture> --hyp <fixture> --out /tmp/score` writes both table formats and prints corpus-level WER and CER.
- **AT-0.3-03** The audit gate passes with `--wp WP-0.3`.

## Stop and ask if
- The normaliser package is unavailable for the probe's Python version, or its behaviour contradicts an example in this spec.

## Must-catch behaviours
1. Normalisation is idempotent, and the normaliser's name and version are recorded in every score row.
2. Substitution, deletion and insertion counts match the independent `jiwer` check exactly.
3. Corpus-level WER is total errors over total reference words, never the mean of per-clip WERs.
4. Empty references follow the defined rule.
5. The main score removes disfluencies and the disfluency-aware score keeps them.
6. Every score row carries `run_card_id`, `clip_id` and both text hashes.
