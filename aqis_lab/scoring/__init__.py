"""AQIS lab scoring: the text normaliser and the WER/CER scorer every system is judged by (WP-0.3).

CAPABILITIES: none of its own (package marker; normalisers in aqis_lab/scoring/normalise.py, alignment and
  WER/CER in aqis_lab/scoring/wer.py, the score table in aqis_lab/scoring/table.py).
INPUTS AND OUTPUTS: none; importing this package has no side effects.
CONTRACTS: docs/contracts/NORMALISATION.md, docs/contracts/SCORE_TABLE.md.
INVARIANTS:
  - Importing the package imports no submodule, so it never loads whisper-normalizer or pyarrow by itself.
NOT IN SCOPE:
  - Producing transcripts (adapters, WP-0.7) and storing results (results store, WP-0.6).
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-01 created.
"""
