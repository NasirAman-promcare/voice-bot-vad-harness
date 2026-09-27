# PLAN — WP-0.3 Text normaliser and scorer

Spec: `docs/specs/phase-0/WP-0.3-normaliser-scorer.md`  ·  Planned by session: https://claude.ai/code/session_01USCcigWgrMyTEQ8pS6Ck1U  ·  Date: 2026-09-27
Branch: `claude/charming-knuth-atc1dq`  ·  Base: `origin/main` at `92063ab`  ·  Depends on: WP-0.0 and WP-0.2 (both MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, every system is scored the same way.
- **Normaliser.** `aqis_lab/scoring/normalise.py` wraps the Whisper English text normaliser at a hash-pinned version. It gives a main normaliser (fillers removed) and a disfluency-aware one (fillers kept), both idempotent, each with a name and version.
- **Scorer.** `aqis_lab/scoring/wer.py` aligns each utterance at word and character level. It counts hits, substitutions, deletions and insertions exactly as the pinned `jiwer` does. It then computes corpus-level WER and CER as total errors over total reference units, and reports the mean of per-utterance WERs beside it, labelled.
- **Score table.** `aqis_lab/scoring/table.py` writes one score row per clip and variant, as Parquet and CSV. Each row carries `run_card_id`, `clip_id`, both text hashes, the normaliser's name and version, and every count.
- **Command.** `python -m aqis_lab score --ref … --hyp … --out …` writes both tables and prints corpus WER and CER for both variants.
- **Documents.** `docs/contracts/NORMALISATION.md` and `docs/contracts/SCORE_TABLE.md` document the behaviour, and tests keep both documents true.

## What I found in the repository and environment (read-only inspection)
1. **Spec sources.** "Read first" names the blueprint section "Metrics catalogue". The blueprint is not in the repository; the WP-0.2 plan recorded your instruction that `docs/specs/phase-0/` is authoritative and self-contained. This plan relies on the spec, the Phase 0 overview conventions and the specs that use the scorer (WP-0.5 run cards, WP-0.6 trace, WP-0.7 smoke run and parity). `aqis-kit-patch-3/docs/specs/` is byte-identical to `docs/specs/` (`cmp`, every file).
2. **Python and dependencies.** The Colab probe says Python 3.13.15, so the lab Python is 3.13. `requirements/aqis_lab/phase0.txt` has no normaliser, no Parquet writer and no `jiwer`. This WP must add them (see question 5).
3. **Which package is "the Whisper English text normaliser".** I checked every candidate in a scratch Python 3.13 environment:
   - **`openai-whisper` (OpenAI's own package, latest `20250625`).** The class is `whisper.normalizers.EnglishTextNormalizer`. Importing `whisper.normalizers` first runs `whisper/__init__.py`, which imports `torch`. The package also requires `numba`, `tiktoken` and, on x86_64 Linux, `triton`. It is published as a source archive only (sha256 `37a91a39…eb96`, no wheel). The PyPI `torch` wheel for Linux pulls several GB of CUDA libraries. **Not usable in the CPU lock.**
   - **`whisper-normalizer` (a standalone MIT-licensed copy of Whisper's normalisers).** It has 24 releases:
     - `0.1.0` and `0.1.1` are the Whisper code. The only change is how `english.json` is located; the file itself is byte-identical to OpenAI's (sha256 `6607f948…2465`).
     - Every release from `0.1.2` to the latest `0.1.15` adds four rules that are **not** in Whisper: `kinda → kind of`, `sorta → sort of`, `dunno → do not know` and `cause → because`. The last one turns "the cause of the fire" into "the because of the fire".
     - Every `0.0.x` release downloads `english.json` from GitHub each time the normaliser is created, which breaks NFR-0.3-01.
   - **Behaviour check.** I ran OpenAI's original `whisper/normalizers` files, taken from the `openai-whisper 20250625` source archive, against `whisper-normalizer 0.1.1` on 100,000 generated inputs (number words, currency, symbols, contractions, British spellings, fillers). There were **0 differences**.
   - **Details of `0.1.1`.** The wheel's sha256 is `e8aa45e6…f085`. It needs `more-itertools`, `regex` and `indic-num2words`; the last is pure Python, Apache-2.0, and is used only by the package's Indic normaliser.
4. **The Whisper normaliser is not idempotent (conflict with FR-0.3-01).** A second pass changes some outputs:
   - `minus five` → `-5` → `5`;
   - `oh one` → `01` → `one`;
   - `double oh seven` → `007` → `7`;
   - `$1.50` → ` one.50` (with a leading space, because Whisper writes `1` as `one`) → `one.50`.

   This is a case the spec lists under "Stop and ask", so question 1 asks you to decide.
   - **Convergence measurement.** Applying the normaliser repeatedly (trimming the ends each pass) until the text stops changing always settled, after at most 3 changing passes: 200,000 generated inputs × 2 variants (the full result is in "Measurements" at the end).
5. **Other Whisper behaviours worth knowing** (they apply to references and hypotheses alike, and the document will show each as an example):
   - Filler list: Whisper removes exactly `hmm`, `mm`, `mhm`, `mmm`, `uh` and `um`. `er`, `erm` and `ah` stay (question 3).
   - `mm-hmm` normalises to an empty text, and `uh-huh` to `huh`.
   - `o` is read as zero: `B-O-B` → `b 0 b`, `I O U` → `i 0 u`, `at 9 o'clock` → `at 90 clock`, `Mr. O'Brien` → `mister 0 brien`.
   - The digit 1 is written as a word: `1` → `one`, `1/4` → `one 4`.
   - `seven thirty` → `730` but `7:30` → `7 30`. Dates: `3/3/2024` → `3 3 2024`, `2024-03-03` → `2024 3 3`.
   - Possessive `'s` becomes `is`: `McDonald's` → `mcdonald is`.
   - Currency: `fifty cents` → `¢50` and `five pounds` → `£5`. Percent: `ten percent` → `10%`.
   - **Typographic apostrophes are not handled.** `don't` → `do not`, but `don’t` (U+2019, as typed on phones and Macs) → `don t`. A reference typed with `’` scored against a model that writes `'` gets 2 word errors for the same word (question 4).
6. **Alignment convention.** Several minimum-edit alignments can exist. For example, reference `a b` against hypothesis `b c` is either 2 substitutions, or 1 deletion + 1 hit + 1 insertion. `jiwer 4.0.0` takes its alignment from `rapidfuzz` (`Levenshtein.opcodes`), so "counts match exactly" (FR-0.3-07) needs the same tie-break. In a scratch prototype I tested this rule:
   - match the common prefix and suffix first, as rapidfuzz does;
   - then, tracing back from the end, take a deletion whenever it lies on a minimum path;
   - otherwise take an insertion when `D[i][j-1] = D[i-1][j-1] − 1`;
   - otherwise take the diagonal step.

   A plain dynamic-programming aligner with this rule gave **0 count differences** on 73,000 random pairs, many of them tie-heavy (alphabets of 2 to 30 symbols, lengths 0 to 80). It also matched on long pairs up to 2,500 × 2,500 tokens and one 5,000 × 4,870-token pair. Without the prefix/suffix step it differed on 360 of those pairs. The six simple preference orders (for example "deletion, then diagonal, then insertion") differ on 0.9 % to 9 % of 20,000 small pairs.
7. **`jiwer 4.0.0` and empty references.** It accepts an empty reference, counts the hypothesis words as insertions, and adds them to corpus totals. That agrees with FR-0.3-04. Its own per-sentence "wer" for an empty reference is the insertion count, whereas the spec says undefined; only the counts are compared, so this does not matter.
8. **Parquet.** `pyarrow 25.0.1` has cp313 wheels for x86_64 and aarch64, including musllinux. It installs and writes Parquet without numpy. Three writes of the same table were byte-identical (`created_by` = `parquet-cpp-arrow version 25.0.1`).
9. **Lock trial.** In the scratchpad, `uv pip compile` with the recorded command and `whisper-normalizer==0.1.1`, `pyarrow` and `jiwer==4.0.0` added resolved cleanly for 3.13 on both architectures, and every existing pin stayed at its version. New pins: `click 8.5.0`, `indic-num2words 1.3.2`, `jiwer 4.0.0`, `more-itertools 11.1.0`, `pyarrow 25.0.1`, `rapidfuzz 3.14.6`, `regex 2026.9.10` and `whisper-normalizer 0.1.1`. The first attempt timed out fetching metadata from `files.pythonhosted.org`; the retry succeeded. PyPI is reachable from this VM, so no new network host is needed.
10. **Repository fit.** The CLI dispatcher (`aqis_lab/__main__.py`, `COMMANDS`) needs one new entry. The harness folder `scoring/` (GUARDED) scores VAD only and is unrelated; the new code lives in `aqis_lab/scoring/`. The root `.gitignore` ignores `*.jsonl` but not `*.csv`, so CSV fixtures commit normally. The existing lock tests (CAP-ENV-002) accept new direct requirements as long as the lock is regenerated with the recorded command.
11. **Environment probes.** `docs/environment/oracle_probe.txt` is missing. This WP runs on the cloud VM only, so it is not needed now; see risk 6.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.3-01 | `whisper_normalizer.english.EnglishTextNormalizer` from `whisper-normalizer==0.1.1` (question 2), pinned with hashes. `normalise(text)` = the Whisper normaliser applied until a fixed point (question 1). The wrapper raises `NormaliserVersionError` if the installed package version is not the pinned one. Each normaliser object exposes `.name` and `.version`, and `normaliser_identity()` gives the `{name, version}` object the run card contract expects | `aqis_lab/scoring/__init__.py`, `aqis_lab/scoring/normalise.py` | none | `test_FR_0_3_01_exposes_name_and_version`, `test_FR_0_3_01_installed_package_is_the_pinned_version`, `test_FR_0_3_01_refuses_other_package_version`, `test_FR_0_3_01_equals_whisper_where_whisper_is_idempotent` (generated inputs, compared with the package's own class), `test_FR_0_3_01_idempotent_on_generated_inputs` (≥ 20,000 seeded inputs, both variants), `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point`, `test_FR_0_3_01_fixed_point_raises_when_not_reached`, `test_FR_0_3_01_rejects_non_text_input`, `test_FR_0_3_01_output_has_single_spaces_and_no_edge_spaces`, `test_FR_0_3_01_typographic_apostrophes_fold_to_ascii` (only if question 4 is accepted), `test_FR_0_3_01_matches_openai_whisper_original` (marked `slow` and `network`: downloads the `openai-whisper 20250625` source archive, checks its sha256, loads its `whisper/normalizers` files alone and compares outputs on 20,000 generated inputs) | AT-0.3-01 |
| FR-0.3-02 | `NORMALISATION.md` has a behaviour summary, the lab's wrapper rules, the filler list, the variant definition, a "surprising behaviours" section (finding 5), name and version, and a change policy. It also has an examples table with at least 45 rows: every category in the spec at least 3 times, plus the non-idempotent inputs and the quirks. Columns: ID, category, input, main output, disfluency-aware output. A test parses the table and checks every row for both variants. **Expected outputs** are written from Whisper's rules (the Whisper paper's Appendix C and the source), then confirmed against OpenAI's original code in a scratch environment. Any row where my hand-written expectation and the code disagree is reported to you before it goes in, never silently changed | `docs/contracts/NORMALISATION.md` | none | `test_FR_0_3_02_documented_example` (parametrised, one case per table row: main output, disfluency-aware output, and both are fixed points), `test_FR_0_3_02_at_least_30_examples_cover_every_category`, `test_FR_0_3_02_parser_reads_every_table_row` (so rows cannot be dropped silently) | AT-0.3-01 |
| FR-0.3-03 | Main normaliser: Whisper's filler removal on. Disfluency-aware: the same pinned class with only its filler pattern (`ignore_patterns`) switched off; everything else is the same (question 3 fixes the list). Every clip is scored under both variants; rows carry `variant` = `main` or `disfluency_aware` and that variant's normaliser name and version; the command prints both, labelled | (in `normalise.py`, `wer.py`, `commands/score.py`, `NORMALISATION.md`) | none | `test_FR_0_3_03_main_removes_each_listed_filler`, `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler`, `test_FR_0_3_03_documented_filler_list_matches_normaliser`, `test_FR_0_3_03_both_variants_scored_and_labelled`, `test_FR_0_3_03_cli_prints_both_labelled_variants` | AT-0.3-01, AT-0.3-02 |
| FR-0.3-04 | `align(ref_tokens, hyp_tokens)`: unit-cost Levenshtein alignment with the tie-break in finding 6. It returns the operations (hit, substitution, deletion, insertion with their indices) and the counts. Words are the normalised text split on single spaces. Characters are the Unicode code points of the normalised text, spaces included, as jiwer's default CER counts them. `score_utterance` gives word and character counts, reference length (hits + substitutions + deletions) and WER and CER. **Empty reference** (empty after normalisation, judged per variant): insertions count, per-utterance WER (and CER for zero reference characters) is `null`, and the utterance stays in corpus totals | `aqis_lab/scoring/wer.py` | none | `test_FR_0_3_04_hand_counted_alignments`, `test_FR_0_3_04_tie_break_follows_documented_rule`, `test_FR_0_3_04_errors_equal_edit_distance` (a separate textbook distance written in the test), `test_FR_0_3_04_alignment_ops_rebuild_both_texts`, `test_FR_0_3_04_reference_length_is_hits_subs_dels`, `test_FR_0_3_04_cer_counts_characters_including_spaces`, `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_reference_empty_after_normalisation`, `test_FR_0_3_04_empty_reference_enters_corpus_totals`, `test_FR_0_3_04_both_texts_empty` | AT-0.3-01 |
| FR-0.3-05 | `corpus_summary(scores)` per variant: `corpus_wer` = total errors / total reference words; `mean_utterance_wer` = unweighted mean over utterances whose WER is defined, with how many were left out; `corpus_cer` the same way over characters. A total of 0 reference units gives `null`. The command prints them on separate labelled lines, with the exact fraction | (in `wer.py`, `commands/score.py`) | none | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words` (hand-computed: 1 error in a 1-word reference and 0 errors in a 9-word reference give a mean of 0.50 but a corpus WER of 0.10), `test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled`, `test_FR_0_3_05_corpus_wer_undefined_without_reference_words`, `test_FR_0_3_05_corpus_cer_is_total_errors_over_total_reference_characters`, `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled` | AT-0.3-02 |
| FR-0.3-06 | Score rows as listed under "Score table" below, one per clip and variant. `ref_sha256`/`hyp_sha256` = SHA-256 of the UTF-8 text exactly as given, before normalisation. Written with explicit pyarrow types to `scores.parquet` and with the same columns to `scores.csv`. `SCORE_TABLE.md` lists every column (name, Parquet type, CSV form, null rule, meaning), the alignment rule, the empty-reference rule, the input formats and the change policy | `aqis_lab/scoring/table.py`, `aqis_lab/commands/score.py`, `docs/contracts/SCORE_TABLE.md`, fixtures `tests/aqis_lab/fixtures/scoring/ref.csv`, `hyp.csv` | `aqis_lab/__main__.py`: `COMMANDS` (one entry) and the docstring CHANGE LOG (one line) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_hashes_are_sha256_of_raw_text` (hashlib in the test), `test_FR_0_3_06_parquet_schema_matches_score_table_doc`, `test_FR_0_3_06_csv_header_matches_score_table_doc`, `test_FR_0_3_06_csv_and_parquet_hold_the_same_rows`, `test_FR_0_3_06_rows_sorted_by_clip_and_variant`, `test_FR_0_3_06_rejects_invalid_run_card_id_and_clip_id`, `test_FR_0_3_06_input_errors_exit_2` (missing file, wrong header, wrong field count, duplicate clip, clip sets differ, more than one `run_card_id`, not UTF-8, no clips), `test_FR_0_3_06_refuses_to_overwrite_output`, `test_FR_0_3_06_summary_matches_rows` (only if question 7 is accepted), `test_FR_0_3_06_score_listed_by_dispatcher` | AT-0.3-02 |
| FR-0.3-07 | A seeded generator (seed recorded in the test) makes ≥ 200 pairs from a word list by random substitutions, deletions and insertions. The pairs include identical, empty-reference, empty-hypothesis, both-empty, repeated-word, tie-heavy (2 or 3 word vocabulary) and 300-word pairs. The words come from real normaliser output, so they include digits, `%`, `£` and `'`. Word counts are compared with `jiwer.process_words`, character counts with `jiwer.process_characters`, per pair and as corpus totals, including `jiwer.wer` on the whole list | — | none | `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs` (asserts ≥ 200 pairs), `test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer`, `test_FR_0_3_07_generated_pairs_cover_edge_cases`, `test_FR_0_3_07_jiwer_is_the_pinned_version`, `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` (marked `slow`: 20,000 pairs) | AT-0.3-01 |
| NFR-0.3-01 | No clock, randomness, locale, environment or dict-order input to any result; rows sorted. The scoring code imports no network module, and the normaliser loads its word map from the installed package | (all scoring modules) | none | `test_NFR_0_3_01_repeat_runs_give_identical_files` (two command runs with input rows shuffled and different `PYTHONHASHSEED`: byte-identical output files), `test_NFR_0_3_01_no_network_during_scoring` (runs the command in a subprocess with a Python audit hook that records every `socket.*` event and fails on any), `test_NFR_0_3_01_scoring_code_imports_no_network_modules` (AST scan of `aqis_lab/scoring/` and `commands/score.py`) | AT-0.3-01 |
| AT-0.3-01 | Run as written | — | — | all of the above | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` |
| AT-0.3-02 | Run as written, on a fresh output folder (the command refuses to overwrite) | — | — | `test_FR_0_3_0*_cli_*` | `rm -rf /tmp/score && .venv/bin/python -m aqis_lab score --ref tests/aqis_lab/fixtures/scoring/ref.csv --hyp tests/aqis_lab/fixtures/scoring/hyp.csv --out /tmp/score` (exit 0; `scores.parquet` and `scores.csv` written; corpus WER and CER printed for both variants) |
| AT-0.3-03 | Run as written after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.3` |

**Change budget for existing files** (nothing else that already exists is touched):
- `aqis_lab/__main__.py`: add the `"score"` entry to `COMMANDS` and one CHANGE LOG line to the module docstring. `build_parser` and `main` stay byte-identical. CAP-CLI-001's behaviour is unchanged, so its registry row stays as it is.
- `requirements/aqis_lab/phase0.in` (LAB-OWNED): append one commented block with `whisper-normalizer==0.1.1`, `pyarrow` and `jiwer==4.0.0`. Existing lines stay byte-identical.
- `requirements/aqis_lab/phase0.txt` (LAB-OWNED): regenerated only with the command recorded in its header. Existing pins are expected to stay unchanged, and the build checks that with `git diff`.
- `docs/capabilities/REGISTRY.md`:
  - append new rows;
  - in the CAP-ENV-002 row, update only the "What it does" cell so it names the added packages (the lock's content changes);
  - all other rows stay byte-identical.
- `docs/progress/STATUS.md`: the WP-0.3 row only. `docs/progress/BLOCKERS.md`: append-only, and only if I get blocked. `docs/progress/DEBT.md`: rows only if an audit finding is accepted as debt.
- No GUARDED or NEVER path changes, so no `ALLOW-EDIT` is needed. No existing test file changes.

**New files** (besides the table):
- `docs/progress/WP-0.3/EVIDENCE.md`.
- Test modules (the `test_aqis_` prefix keeps basenames unique, FR-0.0-04):
  - `tests/aqis_lab/test_aqis_scoring_normalise.py` (FR-0.3-01 and FR-0.3-03);
  - `test_aqis_scoring_examples.py` (FR-0.3-02);
  - `test_aqis_scoring_align.py` (FR-0.3-04);
  - `test_aqis_scoring_corpus.py` (FR-0.3-05);
  - `test_aqis_scoring_table.py` (FR-0.3-06);
  - `test_aqis_scoring_crosscheck.py` (FR-0.3-07);
  - `test_aqis_scoring_cli.py`;
  - `test_aqis_scoring_nfr.py`.
- Fixtures: the `hyp.csv` fixture uses the `run_card_id` of the WP-0.2 fixture `tests/aqis_lab/fixtures/contracts/valid_run_card.json`, so the fixture rows trace to a valid run card.
- Registry rows, all ACTIVE and introduced by WP-0.3:
  - CAP-SCORE-001: the main and disfluency-aware normalisers, with name, version, the pinned-version check and the fixed point (`normalise.py`).
  - CAP-SCORE-002: alignment and per-utterance counts (`wer.py` `align`, `score_utterance`).
  - CAP-SCORE-003: corpus totals, corpus WER and CER, and the labelled mean (`wer.py` `corpus_summary`).
  - CAP-SCORE-004: the score table in Parquet and CSV (`table.py`).
  - CAP-SCORE-005: the `score` command (`commands/score.py`).
  - CAP-DOC-005: `NORMALISATION.md`, kept true by its example tests.
  - CAP-DOC-006: `SCORE_TABLE.md`, kept identical to the written schema.

## Design details
Rows marked **question** need your answer. Everything else is a design decision that approving the plan accepts; tell me to change any of it.

### Normalisers (`aqis_lab/scoring/normalise.py`)
- **Pinned package.** `WHISPER_NORMALIZER_VERSION = "0.1.1"`. On first use the wrapper compares it with `importlib.metadata.version("whisper-normalizer")` and raises `NormaliserVersionError` naming both versions if they differ. The Whisper class is created once, lazily.
- **Rule for both variants** (question 1):
  - `step(x)` = the Whisper normaliser applied to `x`, then leading and trailing whitespace removed;
  - `normalise(text)` applies `step` until the text stops changing, at most 10 passes, and returns that text;
  - if the text is still changing after 10 passes, it raises `NormalisationError` with the input. It never returns a text that is not a fixed point.
  - The measured maximum is 3 changing passes, so 4 calls including the confirming one (see "Measurements").
  - The fixed-point loop is a general helper `fixed_point(step, text, max_passes)`. Its failure path is therefore tested with a real function that never settles, without replacing the normaliser.
- **Typographic apostrophes** (question 4, option a): before the first pass, `’` (U+2019), `‘` (U+2018) and `ʼ` (U+02BC) become `'`.
- **Variants**:
  - `MAIN`: Whisper's own filler removal is on.
  - `DISFLUENCY_AWARE`: a separate instance of the same class whose `ignore_patterns` is a pattern that never matches; nothing else differs. Whisper's spelling map still applies in this variant, so `mhm` becomes `hmm`; the document shows this.
- **Names and versions**:
  - `MAIN.name = "aqis-whisper-english"`;
  - `DISFLUENCY_AWARE.name = "aqis-whisper-english-keep-disfluencies"`;
  - both have `version = "1+whisper-normalizer-0.1.1"`: lab wrapper rules version 1, on top of the pinned package version. A change to either part changes the version string.
  - `normaliser_identity()` returns `{"name": MAIN.name, "version": MAIN.version}` for run cards (WP-0.5 and WP-0.7).
- **API**: `normalise(text)` (main), `normalise_keep_disfluencies(text)`, `MAIN`, `DISFLUENCY_AWARE`, `VARIANTS` (`{"main": MAIN, "disfluency_aware": DISFLUENCY_AWARE}`) and `normaliser_identity()`. Input must be `str`, otherwise `TypeError`.

### Alignment and scores (`aqis_lab/scoring/wer.py`)
- **Tokens**: words = `text.split(" ")` of the normalised text, or `[]` if it is empty. Characters = `list(text)`, Unicode code points with single spaces between words.
- **Alignment**:
  - my own dynamic-programming aligner in pure Python, independent of `jiwer` and `rapidfuzz`, with unit costs and the tie-break from finding 6;
  - time is proportional to n·m; memory is one byte per cell for the traceback plus two rows of distances;
  - equal tokens compare by string equality.
- **Results**:
  - `UtteranceScore` holds, for words and for characters: `ref_len`, `hyp_len`, `hits`, `substitutions`, `deletions`, `insertions` and `errors`, with the alignment operations;
  - it also holds `wer` and `cer`: `errors / ref_len`, or `None` when `ref_len` is 0.
  - `score_corpus(pairs, run_card_id)` scores each pair under both variants.
  - `corpus_summary(scores)` returns the per-variant totals and rates described in the FR-0.3-05 row.

### Score table (`aqis_lab/scoring/table.py`, `SCORE_TABLE.md`)
One row per clip and variant, sorted by `clip_id`, then `variant` (`disfluency_aware` before `main`, by plain string order).
| Column | Parquet type (nullable) | Meaning |
| --- | --- | --- |
| `schema_version` | string (no) | `"1.0"`, score table schema version (addition, question 7) |
| `run_card_id` | string (no) | 64 lowercase hex, from the hypothesis file |
| `clip_id` | string (no) | lowercase letters, digits and hyphens |
| `variant` | string (no) | `main` or `disfluency_aware` |
| `normaliser_name`, `normaliser_version` | string (no) | that variant's normaliser |
| `ref_sha256`, `hyp_sha256` | string (no) | SHA-256 hex of the raw text's UTF-8 bytes |
| `ref_words`, `hyp_words`, `hits`, `substitutions`, `deletions`, `insertions`, `errors` | int64 (no) | word counts; `ref_words` = hits + substitutions + deletions |
| `wer` | float64 (yes) | `errors / ref_words`; null for an empty reference |
| `ref_chars`, `hyp_chars`, `char_hits`, `char_substitutions`, `char_deletions`, `char_insertions`, `char_errors` | int64 (no) | character counts |
| `cer` | float64 (yes) | `char_errors / ref_chars`; null when `ref_chars` is 0 |

- **CSV format**: UTF-8, header row, `\n` line ends, minimal quoting. Null is an empty field. Floats are written with Python's shortest round-trip form (`repr`), so CSV and Parquet hold the same numbers.
- **Parquet format**: pyarrow with an explicit schema and default options. The file's key-value metadata records `schema_version`.
- **Normalised texts are not stored** in the table, only their counts. `UtteranceScore` keeps the texts and the alignment for callers that need them.

### Command (`python -m aqis_lab score --ref REF.csv --hyp HYP.csv --out DIR`)
- **Inputs** (question 6):
  - `REF.csv` has the exact header `clip_id,text`; `HYP.csv` has the exact header `run_card_id,clip_id,text`;
  - UTF-8, with a leading byte-order mark accepted;
  - text may be empty and may contain line breaks when quoted.
- **Input errors** (each exits 2 with an `ERROR:` line naming the file and line):
  - a missing or unreadable file, or text that is not UTF-8;
  - a wrong header or a wrong number of fields;
  - an invalid `clip_id` or `run_card_id`;
  - a `clip_id` repeated within a file;
  - a clip present in only one file (all such clips are listed);
  - more than one `run_card_id` in the hypothesis file;
  - no clips.

  A missing hypothesis is never treated as empty; an explicitly empty text is allowed.
- **Output**:
  - `DIR/scores.parquet`, `DIR/scores.csv` and, if question 7 is accepted, `DIR/summary.json` (canonical JSON from `aqis_lab.contracts.canonical`, with per-variant totals and rates and the SHA-256 of both table files);
  - `DIR` is created if missing;
  - if any of these files already exists, the command exits 2 and changes nothing;
  - each file is written under a `.part` name and renamed when complete.
- **Printed report** (one block per variant, then the file list):
  ```text
  variant main (normaliser aqis-whisper-english 1+whisper-normalizer-0.1.1)
    utterances 12, empty references 2
    corpus WER 0.103448 = 6 errors / 58 reference words (S 3, D 1, I 2, H 54)
    mean per-utterance WER 0.118750 over 10 utterances (not the corpus WER; 2 undefined)
    corpus CER 0.041096 = 12 errors / 292 reference characters (S 6, D 4, I 2, H 282)
  variant disfluency_aware (normaliser aqis-whisper-english-keep-disfluencies 1+whisper-normalizer-0.1.1)
    ...
  wrote /tmp/score/scores.parquet, /tmp/score/scores.csv
  ```
- **Exit codes**: 0 written; 2 any usage, input or output error, or a wrong normaliser package version.

### Must-catch proof (planned)
| # | Behaviour | Break I will make in a copy under `/tmp` | Tests that must fail |
| --- | --- | --- | --- |
| 1 | Idempotent; name and version in every row | remove the fixed-point loop (one pass only); drop `normaliser_version` from rows | `test_FR_0_3_01_idempotent_on_generated_inputs`, `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point`; `test_FR_0_3_06_every_row_carries_trace_fields` |
| 2 | S/D/I equal `jiwer` exactly | swap the deletion and insertion preference; remove the prefix/suffix step | `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs`, `test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs`, `test_FR_0_3_04_tie_break_follows_documented_rule` |
| 3 | Corpus WER = total errors / total reference words | return the mean of per-utterance WERs as `corpus_wer` | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` |
| 4 | Empty references follow the rule | leave empty references out of totals; give them WER 0 | `test_FR_0_3_04_empty_reference_enters_corpus_totals`, `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined` |
| 5 | Main removes fillers; disfluency-aware keeps them | build the disfluency-aware variant with filler removal on | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler`, `test_FR_0_3_02_documented_example[…]` |
| 6 | Every row carries `run_card_id`, `clip_id` and both hashes | hash the normalised text instead of the raw text; drop `hyp_sha256` | `test_FR_0_3_06_hashes_are_sha256_of_raw_text`, `test_FR_0_3_06_every_row_carries_trace_fields` |

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to questions 1 to 7 below, as CONDITIONS in `docs/approvals/WP-0.3.md` (or "as recommended") | They decide the normaliser's behaviour, its package, the filler list and the score table format that later WPs depend on | Before `/wp-build WP-0.3` |

No data, credentials, new network hosts, Colab runs or Oracle runs are needed. The build downloads packages from PyPI, which this VM already reaches.

## Owner-run checks planned
None. The spec runs this WP on the cloud VM only, and everything in it can run here. CI (GitHub Actions, Ubuntu) runs the fast suite on a second machine. Identical scores on Colab and Oracle are proved later by WP-0.7 (Phase 0 exit criterion E1).

## Risks and questions
### Questions for you
1. **(Deviation D1) Idempotence.** FR-0.3-01 requires idempotent normalisation, but the Whisper normaliser is not idempotent (finding 4). Options:
   - **(a) Recommended.** `normalise` applies the Whisper normaliser until the text stops changing (at most 10 passes, and an error if it does not settle), trimming the ends each pass.
     - Idempotent by construction.
     - The result equals plain Whisper wherever plain Whisper is already idempotent. A test proves this on generated inputs.
     - It differs only on inputs such as `minus five` (→ `5` rather than `-5`) and `oh one` (→ `one` rather than `01`).
     - Scores stay comparable with published Whisper-normalised WERs except for such inputs.
   - **(b)** Plain single-pass Whisper output, with FR-0.3-01's idempotence dropped or limited to the documented examples. This weakens a spec requirement and must-catch 1, so I would need that decision written in the approval.
2. **Which package is "the Whisper English normaliser"** (finding 3). Options:
   - **(a) Recommended.** `whisper-normalizer==0.1.1`, hash-pinned. Its English normaliser is Whisper's code, checked by source comparison and by 0 differences on 100,000 inputs against OpenAI's original. The spec's "pinned version" is then this package version, and the slow network test `test_FR_0_3_01_matches_openai_whisper_original` keeps checking the equivalence.
   - **(b)** Copy OpenAI's three MIT-licensed files (`basic.py`, `english.py`, `english.json` from `openai-whisper 20250625`) into `aqis_lab/scoring/` with the licence, and have a test check their SHA-256 against the source archive. This avoids depending on a third-party repackaging, but it is a copy rather than a wrapped package.
   - **(c)** `openai-whisper` itself. Not possible in the CPU lock: it needs `torch` (several GB from PyPI) and has no wheel.
   - **(d)** The newest `whisper-normalizer` (0.1.15). Not recommended: its four extra rules are not Whisper's, and `cause → because` corrupts ordinary sentences.
3. **Filler list for the main score** (FR-0.3-03, finding 5). Options:
   - **(a) Recommended.** Whisper's own list: `hmm`, `mm`, `mhm`, `mmm`, `uh`, `um`. The main score is then standard Whisper normalisation, comparable with model cards and papers.
   - **(b)** Whisper's list plus lab additions that you choose, for example `er`, `erm`, `ehm`, `uhm` and `hm`, which are common in British speech.
     - The lab list is removed in the main variant and kept in the disfluency-aware one.
     - The normaliser version records it.
     - Scores are then less directly comparable with published Whisper-normalised numbers.
4. **(Deviation D2, only if accepted) Typographic apostrophes** (finding 5). Options:
   - **(a) Recommended.** Before the first pass, fold `’`, `‘` and `ʼ` into `'`.
     - Without it, a reference typed as `don’t` scores 2 word errors against a correct `don't`.
     - This matters for owner recordings, whose transcripts are typed by hand.
     - It changes Whisper's output only for texts that contain those characters, where Whisper's own output is broken (`don t`).
   - **(b)** Plain Whisper; transcripts must then use `'`, and the document warns about it.
5. **Lock additions.**
   - Added to `phase0.in`: `whisper-normalizer==0.1.1` and `jiwer==4.0.0` exactly (the spec says pinned; a newer normaliser changes behaviour), and `pyarrow` (pinned by the lock).
   - The resulting lock adds 8 packages (finding 9). `jiwer` is used only by tests but goes into the single CPU lock, as `pytest` does.
   - `pyarrow` is a 48 MB wheel, so bootstrap and CI take a few seconds longer.

   **Recommended: accept.**
6. **`score` input files.**
   - **(a) Recommended.** The two CSV formats and the strict matching rules under "Command". CSV is easy to write by hand and from WP-0.4's `transcripts.csv`. WP-0.7 will call the Python API directly on pack transcripts and adapter output, so no event-log input is added here.
   - **(b)** JSON Lines instead of CSV: stricter types, but harder to write by hand, and `*.jsonl` fixtures need the nested `.gitignore` used in WP-0.2.
7. **(Additions D3 and D4) Output beyond the spec's field list.**
   - **D3:** a `schema_version` column (`"1.0"`), matching the WP-0.2 versioning policy, so the table can change later without ambiguity.
   - **D4:** a `summary.json` beside the two tables, holding the printed corpus numbers and the SHA-256 of both table files. The printed report is then kept on record and can be traced.

   **Recommended: accept both.** If you reject them, the numbers are only printed, and the table has no version column.

### Design decisions made in this plan (approving the plan accepts them)
- One row per clip **and** variant, with a `variant` column, rather than two sets of columns in one row.
- The hashes are of the raw text as given (the spec's "SHA-256 of reference and hypothesis"). WP-0.7 parity compares raw transcripts this way, so a normalisation difference cannot hide a transcript difference.
- CER counts spaces between words, like `jiwer`'s default CER, so the character counts can be cross-checked exactly.
- "Empty reference" means empty after normalisation, judged per variant: `um` is an empty reference in the main variant but not in the disfluency-aware one.
- The S/D/I split among equally short alignments follows jiwer 4.0.0 (finding 6). The rule is written out in `SCORE_TABLE.md`.
- The `score` command refuses to overwrite existing output, in line with the append-only results store planned for WP-0.6.
- Per-utterance alignments are returned by the API but not written to the table.

### Other risks
1. **Whisper's quirks are documented, not corrected** (finding 5). They apply equally to references and hypotheses, but they can merge or split tokens: `7:30` gives 2 words and `seven thirty` gives 1. Only D1 and, if accepted, D2 change Whisper's behaviour.
2. **Dependence on an older third-party copy** (`whisper-normalizer 0.1.1`, April 2025) if question 2(a) is accepted. The hash lock, the version check and the network test against OpenAI's original limit the risk.
3. **Warning on import.** `whisper_normalizer/basic.py` 0.1.1 has an invalid escape (`\X`) in a docstring. Python 3.13 prints a `SyntaxWarning` when it first compiles that file. It is harmless and does not change results; the lab does not run Python with warnings turned into errors.
4. **Cost on very long texts.** Alignment time grows with n × m.
   - Prototype timings: 1,500 × 1,500 tokens about 0.8 s, and 5,000 × 4,870 tokens about 11 s.
   - A 10-minute clip scored by characters (about 8,000 × 8,000) would need about 64 MB and roughly half a minute.
   - Phase 0 clips last 3 to 35 s. If a later phase scores long recordings as single clips, a faster aligner with the same tie-break can be added then as a new version.
5. **`jiwer` on extremely long inputs.** I verified equal counts up to about 5,000 tokens. Beyond some size, `rapidfuzz` may switch to a different internal method that could pick another equally short alignment. Total errors would still agree; only the S/D/I split could differ. The cross-check covers pairs up to 300 words.
6. **Oracle.** `docs/environment/oracle_probe.txt` is missing. `pyarrow`'s Linux wheels need glibc 2.28 or newer (`manylinux_2_28`), which Oracle Linux 8+ and Ubuntu 20.04+ provide. WP-0.6 confirms this on the real VM.
7. **Network flakiness when regenerating the lock.** One trial `uv pip compile` timed out on `files.pythonhosted.org` and the retry passed. If it fails twice in the build, I stop and ask.

## Deviations
- **D1**: normalisation is Whisper's normaliser applied until it reaches a fixed point, so that FR-0.3-01's idempotence holds (question 1).
- **D2**: fold typographic apostrophes before normalising (question 4; only if you accept it).
- **D3**: `schema_version` column in the score table (question 7).
- **D4**: `summary.json` output beside the two tables (question 7).

Everything else fills in something the spec leaves open and is listed under "Design decisions"; none of it contradicts the spec.

## Measurements
All planning measurements were made in the scratchpad, never in the repository, with Python 3.13.12 and the package versions in finding 9.
- **Fixed point.** 200,000 seeded random inputs of 1 to 8 tokens (number words, ordinals, currency and symbols, fillers, contractions, 50 words from Whisper's spelling map), `step` as defined above:
  - main: 4,073 already fixed; 186,345 fixed after one pass; 9,442 after two; 140 after three;
  - disfluency-aware: 4,837, 185,712, 9,314 and 137;
  - none needed more. So about 4.8 % of these inputs are not idempotent under plain Whisper. They are far denser in numbers and symbols than real transcripts.
- **Tie-break.** 73,000 random pairs (3 seeds, alphabets of 2 to 30 symbols, lengths 0 to 80) and 28 long pairs (200 to 2,500 tokens), plus one 5,000 × 4,870-token pair: 0 count differences from `rapidfuzz`, and therefore from `jiwer 4.0.0`.
- **Equivalence.** OpenAI `openai-whisper 20250625` `whisper/normalizers` against `whisper-normalizer 0.1.1`: 0 differences on 100,000 generated inputs.
