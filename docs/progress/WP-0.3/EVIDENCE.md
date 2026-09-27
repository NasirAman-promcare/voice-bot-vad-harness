# EVIDENCE — WP-0.3

Environment: cloud VM (Ubuntu 24.04, x86_64, 4 vCPUs), Python 3.13.12 in `.venv` (Colab probe: 3.13), lock `requirements/aqis_lab/phase0.txt` sha256 `1524a39ec1c2777a6ea7aefd69bc963a693fcc3e88413eb3fa26c0949ab6b801` after this WP's additions, branch `claude/charming-knuth-atc1dq`. Approval: `docs/approvals/WP-0.3.md` on `main` (`2879cf4`), "Questions 1-7: as recommended in PLAN.md".

Baseline before any change (change-control step 3, for `aqis_lab/__main__.py` and the lock): fast suite `998 passed, 9 deselected in 69.84s`.

## Lock additions (supports FR-0.3-01, FR-0.3-06, FR-0.3-07; plan question 5)
- Change: `requirements/aqis_lab/phase0.in` gained one commented block (`whisper-normalizer==0.1.1`, `pyarrow`, `jiwer==4.0.0`); `phase0.txt` was regenerated with the command recorded in its header (`uv pip compile requirements/aqis_lab/phase0.in --universal --python-version 3.13 --generate-hashes --output-file requirements/aqis_lab/phase0.txt`, passed again as `--custom-compile-command`).
- Existing pins unchanged: `git diff --stat requirements/` showed only insertions.
```text
 requirements/aqis_lab/phase0.in  |   7 +
 requirements/aqis_lab/phase0.txt | 302 +++++++++++++++++++++++++++++++++++++++
 2 files changed, 309 insertions(+)
+click==8.5.0 \
+indic-num2words==1.3.2 \
+jiwer==4.0.0 \
+more-itertools==11.1.0 \
+pyarrow==25.0.1 \
+rapidfuzz==3.14.6 \
+regex==2026.9.10 \
+whisper-normalizer==0.1.1 \
```
- CAP-ENV-002 tests, including the slow network ones (regeneration is reproducible; installable with plain `pip --require-hashes`): `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_lock.py -v -p no:cacheprovider`
```text
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_every_pin_has_hashes PASSED [ 16%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_generated_from_in_file PASSED [ 33%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_command_documented PASSED [ 50%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_environment_matches_lock PASSED [ 66%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_is_reproducible PASSED [ 83%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_installable_with_plain_pip PASSED [100%]
============================== 6 passed in 7.43s ===============================
```
- Registry: CAP-ENV-002 "What it does" now names the added packages (only that cell changed).

## Requirements

### FR-0.3-01 — Wrapped, pinned, idempotent Whisper English normaliser
- Module: `aqis_lab/scoring/normalise.py` (CAP-SCORE-001), package marker `aqis_lab/scoring/__init__.py`.
- Tests (`tests/aqis_lab/test_aqis_scoring_normalise.py`): `test_FR_0_3_01_exposes_name_and_version`, `test_FR_0_3_01_identity_fits_the_run_card_contract` (the identity put into the WP-0.2 run card fixture, ID recomputed, `validate_run_card` passes), `test_FR_0_3_01_installed_package_is_the_pinned_version`, `test_FR_0_3_01_refuses_other_package_version` (0.1.15, 0.1.2, 0.0.10, 0.1.1.post1), `test_FR_0_3_01_refuses_missing_package`, `test_FR_0_3_01_equals_whisper_where_whisper_is_idempotent` (20,000 seeded inputs, seed 20260927, both variants), `test_FR_0_3_01_idempotent_on_generated_inputs` (the same 20,000 inputs, both variants), `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point` (`minus five`, `oh one`, `double oh seven`, `$1.50`), `test_FR_0_3_01_fixed_point_raises_when_not_reached`, `test_FR_0_3_01_rejects_non_text_input`, `test_FR_0_3_01_output_has_single_spaces_and_no_edge_spaces`, `test_FR_0_3_01_typographic_apostrophes_fold_to_ascii` (approved question 4), `test_FR_0_3_01_module_functions_are_the_two_variants`, and `test_FR_0_3_01_matches_openai_whisper_original` (marked `slow` and `network`: downloads `openai_whisper-20250625.tar.gz`, checks sha256 `37a91a39…eb96`, loads only its `whisper/normalizers` files and compares with the pinned package on 20,000 inputs, seed 20260928).
- Tests first: before `aqis_lab/scoring/` existed, collection failed with `E   ModuleNotFoundError: No module named 'aqis_lab.scoring'`.
- Correction to two new tests during the build (both written in this build, never committed before the fix; the code was not changed to fit them):
  - The `$1.50` case asserted `whisper(first_pass).strip() != first_pass.strip()`. That is false: plain Whisper differs from its own second pass there only by the leading space (`' one.50'` → `'one.50'`). The premise now compares the untrimmed texts (`whisper(first_pass) != first_pass`), which is what plan finding 4 states.
  - The U+02BC case asserted that plain Whisper gives `don t`. It gives `donʼt`, because Unicode classes U+02BC as a letter, so Whisper keeps it. The premise now names both outputs. Folding is still needed, because neither output is `do not`.
- Import warning: the wrapper ignores only the `SyntaxWarning` that Python 3.13 raises while compiling `whisper_normalizer/basic.py` (an invalid `\X` escape in a docstring, plan risk 3), and only during that import. It is listed under INVARIANTS in the module header.
- Commands and output (real):
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_scoring_normalise.py -q -p no:cacheprovider -m "not slow" -k FR_0_3_01
24 passed, 14 deselected in 27.51s
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_scoring_normalise.py -q -p no:cacheprovider -k matches_openai
1 passed, 37 deselected in 4.28s
```
- Status: DONE

### FR-0.3-02 — NORMALISATION.md with at least 30 examples, each a test
- Document: `docs/contracts/NORMALISATION.md` (CAP-DOC-005): normalisers with names and versions, the steps (lab rules and Whisper's own), the filler list, variants, surprising behaviours, 72 examples (every FR-0.3-02 category at least 3 times, plus British spelling and fixed-point rows), usage, and the change policy.
- Tests (`tests/aqis_lab/test_aqis_scoring_examples.py`): `test_FR_0_3_02_documented_example` (72 cases: main output, disfluency-aware output, both settled), `test_FR_0_3_02_at_least_30_examples_cover_every_category`, `test_FR_0_3_02_parser_reads_every_table_row`.
- Independent confirmation of the expected outputs: each expected output was written from Whisper's rules (most were first seen while planning), then checked with a scratch script that runs OpenAI's original `openai-whisper` 20250625 `whisper/normalizers` files (from the source archive, sha256 `37a91a39…eb96`) with the approved lab rules (fold apostrophes, trim, repeat until settled), and also runs `aqis_lab`:
```text
72 examples, 0 disagreements (OpenAI original openai-whisper 20250625 with the lab rules, and aqis_lab)
```
- The tests fail for the right reasons. With the document moved aside, collection fails (`FileNotFoundError` from `read_text`). With one expected output changed (T05 `at 90 clock` → `at 9 oclock`) in a copy:
```text
FAILED tests/aqis_lab/test_aqis_scoring_examples.py::test_FR_0_3_02_documented_example[T05]
1 failed, 73 passed in 0.15s
```
  The document was then restored (`cmp` identical).
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_scoring_examples.py -q -p no:cacheprovider`
```text
74 passed in 0.16s
```
- Status: DONE

### FR-0.3-04 — Per-utterance alignment, counts, CER and empty references
- Module: `aqis_lab/scoring/wer.py` (CAP-SCORE-002): `align`, `words`, `characters`, `score_utterance`, `score_corpus`.
- Tests (`tests/aqis_lab/test_aqis_scoring_align.py`, 23 cases): `test_FR_0_3_04_hand_counted_alignments` (9 pairs counted by hand), `test_FR_0_3_04_tie_break_follows_documented_rule` (two tie cases worked through by hand in the test's comments), `test_FR_0_3_04_errors_equal_edit_distance` (3,000 random pairs against a textbook distance in `aqis_scoring_testutil.py`), `test_FR_0_3_04_alignment_ops_rebuild_both_texts`, `test_FR_0_3_04_reference_length_is_hits_subs_dels`, `test_FR_0_3_04_cer_counts_characters_including_spaces`, `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_reference_empty_after_normalisation` (`Um.` is empty in the main variant, not in the disfluency-aware one), `test_FR_0_3_04_empty_reference_enters_corpus_totals`, `test_FR_0_3_04_both_texts_empty`, `test_FR_0_3_04_utterance_score_records_texts_and_normaliser`, `test_FR_0_3_04_words_rejects_text_that_is_not_normalised`.
- Tests first: before `wer.py` existed, collection of the three new modules failed with `E   ImportError: cannot import name 'wer' from 'aqis_lab.scoring'`.
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_04`
```text
23 passed, 1132 deselected in 0.63s
```
- Status: DONE

### FR-0.3-05 — Corpus WER and CER as totals; the mean, labelled
- Module: `aqis_lab/scoring/wer.py` (CAP-SCORE-003): `corpus_summary`, `CorpusSummary` (`corpus_wer`, `mean_utterance_wer`, `utterances_with_wer`, `empty_references`, `corpus_cer` and every total). Printed labels are in the `score` command (FR-0.3-06 section; `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled`).
- Tests (`tests/aqis_lab/test_aqis_scoring_corpus.py`): `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words` (1 error over 1 + 9 words: corpus 0.1, mean 0.5), `test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled`, `test_FR_0_3_05_corpus_wer_undefined_without_reference_words`, `test_FR_0_3_05_corpus_cer_is_total_errors_over_total_reference_characters`, `test_FR_0_3_05_summary_totals_are_sums_of_utterances`, `test_FR_0_3_05_score_corpus_rejects_duplicate_clip_and_non_text`.
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_05` (before the command tests existed)
```text
6 passed, 1149 deselected in 0.41s
```
- Printed report: `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled` (both variants; the expected numbers are the fixture's hand counts, written in the test's comments), `test_FR_0_3_05_cli_prints_undefined_rates`. With them: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_05` → `9 passed, 1173 deselected in 1.01s`.
- Status: DONE

### FR-0.3-07 — Cross-check against the pinned jiwer
- Tests (`tests/aqis_lab/test_aqis_scoring_crosscheck.py`):
  - `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs` (asserts at least 200 pairs);
  - `test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs`;
  - `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` (both variants: totals, `jiwer.wer` and `jiwer.cer` on the whole list, with the texts first normalised by the lab);
  - `test_FR_0_3_07_generated_pairs_cover_edge_cases`, which also proves that the tie-heavy pairs exercise the tie-break: a traceback preferring insertion first disagrees with jiwer on at least 5 of them;
  - `test_FR_0_3_07_jiwer_is_the_pinned_version`;
  - `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` (marked `slow`: 20,000 pairs over 2 to 4 word vocabularies).
- Generated pairs (seed 30703): 212 pairs, with words taken from real normaliser output: `{'identical': 21, 'empty-reference': 11, 'empty-hypothesis': 11, 'both-empty': 1, 'repeated-words': 2, 'tie-heavy': 80, 'random-edits': 80, 'long': 6}` (the long pairs have 300-word references).
- Correction to the plan: the plan's FR-0.3-07 row says the generated words "include digits, `%`, `£` and `'`". Normalised text never contains `'`: Whisper expands contractions and then removes apostrophes. The characters actually present are letters, digits, space, `$ % . ¢ £ €`. The coverage test asserts that set; the first version of it (asserting `'`) failed for this reason before it was committed.
- Commands and output (real):
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_07
6 passed, 1149 deselected in 13.08s
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_scoring_crosscheck.py -q -p no:cacheprovider -m slow
1 passed, 5 deselected in 1.36s
```
- Status: DONE

### FR-0.3-03 — Fillers removed in the main score, kept in the disfluency-aware score; both reported and labelled
- Code: `aqis_lab/scoring/normalise.py` (`MAIN`, `DISFLUENCY_AWARE`, `FILLERS`; approved question 3: Whisper's own list), `aqis_lab/scoring/wer.py` (`score_corpus` scores every clip under both), `aqis_lab/scoring/table.py` (`variant`, `normaliser_name` and `normaliser_version` on every row), and `aqis_lab/commands/score.py` (one labelled block per variant).
- Tests:
  - `test_FR_0_3_03_main_removes_each_listed_filler` and `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler` (all six fillers, in three casings);
  - `test_FR_0_3_03_documented_filler_list_matches_normaliser` (the list in `NORMALISATION.md` = `FILLERS` = the pinned class's pattern);
  - `test_FR_0_3_03_both_variants_scored_and_labelled`;
  - `test_FR_0_3_03_cli_prints_both_labelled_variants`.
- Tests first: `test_FR_0_3_03_documented_filler_list_matches_normaliser` failed with `FileNotFoundError: ... docs/contracts/NORMALISATION.md` until the document existed. The corpus and command tests failed at collection with `ImportError: cannot import name 'wer'` (then `'table'`) before those modules existed.
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_03`
```text
15 passed, 1167 deselected in 0.65s
```
- Status: DONE

### FR-0.3-06 — Traceable score rows in Parquet and CSV, schema in SCORE_TABLE.md
- Code:
  - `aqis_lab/scoring/table.py` (CAP-SCORE-004);
  - `aqis_lab/commands/score.py` (CAP-SCORE-005);
  - `aqis_lab/__main__.py`: one `COMMANDS` entry and one CHANGE LOG line, inside the change budget (`git diff -U0` shows only those two added lines).
- Document: `docs/contracts/SCORE_TABLE.md` (CAP-DOC-006), covering:
  - columns, the alignment tie-break rule, empty references and corpus numbers;
  - `summary.json` (approved addition D4) and the `schema_version` column (approved addition D3);
  - input files and the change policy.
- Fixtures: `tests/aqis_lab/fixtures/scoring/ref.csv` and `hyp.csv`. They hold 12 clips: exact match, substitution, deletions, insertion, filler, numbers, an empty reference, a filler-only reference, an empty hypothesis, a typographic apostrophe, punctuation and a multi-line quoted text. The `run_card_id` is that of the WP-0.2 fixture `valid_run_card.json`.
- Tests (`tests/aqis_lab/test_aqis_scoring_table.py`, `test_aqis_scoring_cli.py`):
  - `test_FR_0_3_06_every_row_carries_trace_fields`;
  - `test_FR_0_3_06_hashes_are_sha256_of_raw_text` (hashlib over the fixture texts read with the `csv` module);
  - `test_FR_0_3_06_parquet_schema_matches_score_table_doc`, `test_FR_0_3_06_csv_header_matches_score_table_doc` and `test_FR_0_3_06_csv_and_parquet_hold_the_same_rows`;
  - `test_FR_0_3_06_rows_sorted_by_clip_and_variant` and `test_FR_0_3_06_rejects_invalid_run_card_id_and_clip_id`;
  - `test_FR_0_3_06_input_errors_exit_2` (10 cases: missing file, both wrong headers, wrong field count, blank line, duplicate clip in either file, clip sets differ, several run cards, no clips);
  - `test_FR_0_3_06_non_utf8_input_exit_2` and `test_FR_0_3_06_accepts_bom_and_multiline_text`;
  - `test_FR_0_3_06_refuses_to_overwrite_output` (outputs byte- and mtime-identical after a refused second run);
  - `test_FR_0_3_06_summary_matches_rows`, `test_FR_0_3_06_score_listed_by_dispatcher` and `test_FR_0_3_06_cli_lists_written_files`.
- Tests first: collection failed with `E   ImportError: cannot import name 'table' from 'aqis_lab.scoring'` before `table.py` existed.
- Dispatcher capability (CAP-CLI-001) before and after the `COMMANDS` edit: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_0_01 or FR_0_2_04_cli_listed_by_dispatcher"` → before `8 passed, 1147 deselected in 2.00s`, after `8 passed, 1174 deselected in 2.17s`.
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_3_06`
```text
23 passed, 1159 deselected in 3.63s
```
- Status: DONE

### NFR-0.3-01 — Deterministic; no network access
- Tests (`tests/aqis_lab/test_aqis_scoring_nfr.py`, linked to CAP-SCORE-005):
  - `test_NFR_0_3_01_repeat_runs_give_identical_files`: two command runs, the second with both input files' rows shuffled, `PYTHONHASHSEED` 1 against 4242, and a different `LC_ALL` and `TZ`. All three output files are byte-identical, and so is the printed report apart from its last line, which names the output folder.
  - `test_NFR_0_3_01_no_network_during_scoring`: runs the command in a subprocess with a Python audit hook that records every `socket.*`, `urllib.*`, `http.*` and `ssl.*` event, and requires none while scoring. As a control, a `socket.getaddrinfo("localhost", 80)` after scoring must be recorded, which proves the hook works.
  - `test_NFR_0_3_01_scoring_code_imports_no_network_modules`: an AST scan of the 5 lab modules and of the two Whisper files the normaliser runs (`whisper_normalizer/english.py`, `basic.py`).
- Command and output (real): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k NFR_0_3_01`
```text
3 passed, 1182 deselected in 1.75s
```
- Status: DONE

## Must-catch proof
Each break was made in a copy of the branch under `/tmp/wp03mut` (tracked and untracked files copied; the copy imports its own `aqis_lab`, checked with `aqis_lab.scoring.wer.__file__`). The named test modules were run with the project `.venv`, and the file was restored after each break. Script: `/tmp/wp03mut/mutate.py` (one exact-string replacement per break, asserted to match once). Real output:
```text
== 1a fixed point removed (one pass only): 4 failed, 33 passed, 1 deselected in 12.60s
   FAILED test_FR_0_3_01_idempotent_on_generated_inputs
   FAILED test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point
== 1b normaliser_version dropped from rows: 1 failed, 21 passed in 3.10s
   FAILED test_FR_0_3_06_every_row_carries_trace_fields
== 2a deletion and insertion preference swapped: 4 failed, 25 passed in 8.15s
   FAILED test_FR_0_3_04_tie_break_follows_documented_rule
   FAILED test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs
   FAILED test_FR_0_3_07_corpus_totals_and_wer_match_jiwer
   FAILED test_FR_0_3_07_tie_heavy_pairs_match_jiwer
== 2b common prefix/suffix step removed: 4 failed, 25 passed in 8.47s
   FAILED test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs
   FAILED test_FR_0_3_07_corpus_totals_and_wer_match_jiwer
   FAILED test_FR_0_3_07_tie_heavy_pairs_match_jiwer
   FAILED test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs
== 3 corpus_wer is the mean of per-utterance WERs: 6 failed, 30 passed in 12.82s
   FAILED test_FR_0_3_04_empty_reference_enters_corpus_totals
   FAILED test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words
   FAILED test_FR_0_3_05_corpus_wer_undefined_without_reference_words
   FAILED test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled
   FAILED test_FR_0_3_05_summary_totals_are_sums_of_utterances
   FAILED test_FR_0_3_07_corpus_totals_and_wer_match_jiwer
== 4a empty references left out of totals: 4 failed, 26 passed in 0.31s
   FAILED test_FR_0_3_04_empty_reference_enters_corpus_totals
   FAILED test_FR_0_3_05_corpus_wer_undefined_without_reference_words
   FAILED test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled
   FAILED test_FR_0_3_05_summary_totals_are_sums_of_utterances
== 4b empty reference gets WER 0: 5 failed, 18 passed in 0.27s
   FAILED test_FR_0_3_04_both_texts_empty
   FAILED test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined
   FAILED test_FR_0_3_04_empty_reference_enters_corpus_totals
   FAILED test_FR_0_3_04_reference_empty_after_normalisation
   FAILED test_FR_0_3_04_reference_length_is_hits_subs_dels
== 5 disfluency-aware variant built with filler removal on: 12 failed, 99 passed, 1 deselected in 13.24s
   FAILED test_FR_0_3_01_equals_whisper_where_whisper_is_idempotent
   FAILED test_FR_0_3_02_documented_example
   FAILED test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler
== 6a normalised text hashed instead of raw text: 2 failed, 20 passed in 3.02s
   FAILED test_FR_0_3_06_accepts_bom_and_multiline_text
   FAILED test_FR_0_3_06_hashes_are_sha256_of_raw_text
== 6b hyp_sha256 dropped (reference hash written twice): 1 failed, 21 passed in 2.97s
   FAILED test_FR_0_3_06_hashes_are_sha256_of_raw_text
== N1 rows kept in input order (all three sorts removed): 2 failed, 23 passed in 3.37s
   FAILED test_FR_0_3_06_rows_sorted_by_clip_and_variant
   FAILED test_NFR_0_3_01_repeat_runs_give_identical_files
== N2 network lookup during scoring: 2 failed, 1 passed in 0.75s
   FAILED test_NFR_0_3_01_no_network_during_scoring
   FAILED test_NFR_0_3_01_scoring_code_imports_no_network_modules
```
| # | Must-catch behaviour | Breaks | Caught by |
| --- | --- | --- | --- |
| 1 | Idempotent; name and version in every row | 1a, 1b | `test_FR_0_3_01_idempotent_on_generated_inputs`, `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point`; `test_FR_0_3_06_every_row_carries_trace_fields` |
| 2 | S, D and I equal jiwer | 2a, 2b | `test_FR_0_3_07_*` (fast: char counts, corpus totals; slow: tie-heavy), `test_FR_0_3_04_tie_break_follows_documented_rule` |
| 3 | Corpus WER is total errors over total reference words | 3 | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words` and 5 more |
| 4 | Empty references follow the rule | 4a, 4b | `test_FR_0_3_04_empty_reference_enters_corpus_totals`, `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined` and more |
| 5 | Main removes fillers; disfluency-aware keeps them | 5 | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler`, `test_FR_0_3_02_documented_example` (disfluency rows) |
| 6 | Every row carries `run_card_id`, `clip_id` and both hashes | 6a, 6b | `test_FR_0_3_06_hashes_are_sha256_of_raw_text`, `test_FR_0_3_06_every_row_carries_trace_fields` |

Two gaps were found by this proof and closed before this record:
- **Break 2a.** The first run of 2a failed only the jiwer character and corpus tests, not `test_FR_0_3_04_tie_break_follows_documented_rule` as the plan expected, because none of its hand cases had a cell where the order of the deletion and insertion checks matters. An exhaustive search over short pairs found the smallest such case: reference `a a b c` against hypothesis `b c b` (the lab rule and jiwer give 1 hit, 2 substitutions, 1 deletion; insertion-first gives 2 hits, 2 deletions, 1 insertion). It was added to the test with its distance matrix worked out by hand in the comments. The fast word-level cross-check still does not catch 2a on its own: its 212 pairs happen to contain no such cell. The character-level and corpus cross-checks and the hand case do.
- **Break N1.** The first N1 removed only the sort in `table.py` and nothing failed, because `score_corpus` and the command sort as well. With all three sorts removed, the break is real and two tests fail.

## Acceptance commands

### AT-0.3-01 — Fast suite
`.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"`
```text
1174 passed, 11 deselected in 108.38s (0:01:48)
```
The fast suite includes the 72 documented examples (`test_FR_0_3_02_documented_example`) and the jiwer cross-check (212 generated pairs). The baseline before this WP was `998 passed, 9 deselected in 69.84s`. The two new deselected tests are this WP's slow tests.

Slow and network tests that can run on this VM: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "(slow or network) and not gpu and not colab and not oracle" -rA`
- The first run was `2 failed, 9 passed`. The two failures were WP-0.0's `test_FR_0_0_12_provisions_harness_end_to_end` and `test_FR_0_0_12_second_run_downloads_nothing_within_60s`. Their only failing step was provisioning's `git-status` check: my working tree had uncommitted edits at the time (`[FAIL] git-status: git status --porcelain is not empty ...  M aqis_lab/commands/score.py ...`). Every provisioning step itself passed.
- After committing (`git status --porcelain` empty), `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_harness_provision.py -q -p no:cacheprovider -m slow -rA`:
```text
PASSED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_provisions_harness_end_to_end
PASSED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_second_run_downloads_nothing_within_60s
PASSED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_rebuilds_venv_left_without_pip
3 passed, 61 deselected in 52.08s
```
- The other 9 of the first run passed, including this WP's `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` and `test_FR_0_3_01_matches_openai_whisper_original`, and the lock tests `test_FR_0_0_03_regeneration_is_reproducible` and `test_FR_0_0_03_lock_installable_with_plain_pip`.

### AT-0.3-02 — `score` writes both tables and prints corpus WER and CER
`rm -rf /tmp/score && .venv/bin/python -m aqis_lab score --ref tests/aqis_lab/fixtures/scoring/ref.csv --hyp tests/aqis_lab/fixtures/scoring/hyp.csv --out /tmp/score`
```text
variant main (normaliser aqis-whisper-english 1+whisper-normalizer-0.1.1)
  utterances 12, empty references 2
  corpus WER 0.210526 = 8 errors / 38 reference words (S 1, D 5, I 2, H 32)
  mean per-utterance WER 0.191667 over 10 utterances (not the corpus WER; 2 undefined)
  corpus CER 0.196203 = 31 errors / 158 reference characters (S 1, D 20, I 10, H 137)
variant disfluency_aware (normaliser aqis-whisper-english-keep-disfluencies 1+whisper-normalizer-0.1.1)
  utterances 12, empty references 1
  corpus WER 0.250000 = 10 errors / 40 reference words (S 1, D 7, I 2, H 32)
  mean per-utterance WER 0.287879 over 11 utterances (not the corpus WER; 1 undefined)
  corpus CER 0.220859 = 36 errors / 163 reference characters (S 1, D 25, I 10, H 137)
wrote /tmp/score/scores.parquet, /tmp/score/scores.csv, /tmp/score/summary.json
exit=0
8b09fb32522320da98b84565cca80b841ec379aebaac26f76a59bb9d46ef895c  /tmp/score/scores.csv
3440f26a934e09b9d10cceec5a85362b312b6f0f5b2e25f5ab668fb8e1aed695  /tmp/score/scores.parquet
669efbf41dfed2e932c24d2b5fd31416c5e27a1a894a0c9948dcd13872184a2b  /tmp/score/summary.json
```
The word counts equal the hand counts written in `tests/aqis_lab/test_aqis_scoring_cli.py`: main 8 / 38, disfluency-aware 10 / 40.

### AT-0.3-03 — Audit gate with `--wp WP-0.3`
`git fetch origin main && .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.3`
```text
aqis-audit-gate: base origin/main (merge-base 2879cf4890c2), head 5c046a451ad5, approvals origin/main 2879cf4890c2, wp WP-0.3
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.3 s)
(exit code 0; run with the working tree holding this section, head 5c046a4 plus uncommitted EVIDENCE.md)
```

## Owner-run checks
None. The spec runs WP-0.3 on the cloud VM only, and every test runs here. CI (GitHub Actions, Ubuntu) runs the fast suite on a second machine; its results are below. The same scores on Colab and Oracle are proved by WP-0.7 (exit criterion E1).

## audit-allow lines
None (the gate reports `Exempted lines (# audit-allow): 0` and `Exempted files (ALLOW-PATTERNS-IN): 0`).

## CI (GitHub Actions, `aqis-lab-ci`) on commit `6a11552`
All four jobs succeeded:
- **Push run** [36324281656](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36324281656): job `lab` success, job `harness-regression` success.
- **Pull request run** [36324308658](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36324308658), for PR https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/3 with title "WP-0.3 Text normaliser and scorer": job `lab` success, job `harness-regression` success.

Excerpts from the pull request run (real):
```text
[lab] 1174 passed, 11 deselected in 86.45s (0:01:26)
[lab] Work package from the pull request title: WP-0.3
[lab] aqis-audit-gate: base origin/main (merge-base 2879cf4890c2), head bcbada67ec7b, approvals origin/main 2879cf4890c2, wp WP-0.3
[lab] Exempted lines (# audit-allow): 0
[lab] Exempted files (ALLOW-PATTERNS-IN): 0
[lab] Findings: 0
[lab] 0 findings: OK (0.2 s)
[harness-regression] FAILED tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge - ... did not complete within 3.0s
[harness-regression] ========================= 1 failed, 21 passed in 4.26s =========================
[harness-regression] baseline: 22 tests, 21 passed; this run: 22 tests, 21 passed
[harness-regression] RESULT: PASS
```
The one harness failure is the recorded baseline failure (`docs/baselines/harness_tests_baseline.md`, lines 186 and 377), so the harness regression baseline is unchanged. `head bcbada67ec7b` is GitHub's merge commit of the PR head `6a11552` into `main`.

## Status
Every requirement (FR-0.3-01 to FR-0.3-07, NFR-0.3-01) is DONE, and AT-0.3-01 to AT-0.3-03 pass. There are no owner-run checks and no open blockers. WP-0.3 is READY-FOR-AUDIT.

## Round 2 (audit findings; approval `20ba9ba`)
- **WP-0.3-F01 (MAJOR), fixed with tests only.** Two new tests cover the ways a clip can be on one side only: `test_FR_0_3_06_one_sided_clip_is_an_input_error` (3 cases) and `test_FR_0_3_06_more_input_and_output_errors_exit_2` (5 cases, sibling checks in the same functions that had no test). The details, the reproduction and the mutation proof are in `docs/progress/WP-0.3/FIXES.md`, "Round 2". Summary: the auditor's breaks X2 and X2m each now fail a named new test, and so do 5 sibling breaks (S1 to S5). Fast suite `1182 passed, 11 deselected`; gate `0 findings: OK`.
- **WP-0.3-F02 and WP-0.3-F03 (MINOR)** are accepted debt: `docs/progress/DEBT.md` rows DEBT-008 (target WP-0.6) and DEBT-009 (target WP-0.5).
- **CI for round 2** (`aqis-lab-ci`, commits `c3464c2` and `52fab02`): every job succeeded:
  - push runs [36329183764](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36329183764) and [36329200040](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36329200040);
  - pull request runs [36329187110](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36329187110) and [36329204032](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/36329204032).

  Each run passed both `lab` and `harness-regression`. Excerpts from pull request run 36329204032 on `52fab02` (real):
```text
[lab] 1182 passed, 11 deselected in 89.24s (0:01:29)
[lab] Work package from the pull request title: WP-0.3
[lab] aqis-audit-gate: base origin/main (merge-base 20ba9bad5eff), head 421f9e696640, approvals origin/main 20ba9bad5eff, wp WP-0.3
[lab] Findings: 0
[lab] 0 findings: OK (0.2 s)
[harness-regression] ========================= 1 failed, 21 passed in 4.22s =========================
[harness-regression] baseline: 22 tests, 21 passed; this run: 22 tests, 21 passed
[harness-regression] RESULT: PASS
```
  The one harness failure is the recorded baseline failure (`test_loss_category`), unchanged. Round 2 status: READY-FOR-AUDIT.
