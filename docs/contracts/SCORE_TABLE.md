# Score table

## Purpose
The score table holds one row per clip and normaliser variant. Every row leads back to the run that produced the hypothesis (`run_card_id`), the clip (`clip_id`), the exact texts compared (their SHA-256), and the normaliser used (name and version). It carries every count needed to recompute WER and CER. The scorer is `aqis_lab/scoring/` and the command is `python -m aqis_lab score` (WP-0.3, FR-0.3-04 to FR-0.3-07). The texts are normalised as described in `docs/contracts/NORMALISATION.md`.

## Files
`python -m aqis_lab score --ref REF.csv --hyp HYP.csv --out DIR` writes three files in `DIR`:
- `scores.parquet`: the rows, with the column types below. The file's key-value metadata holds `aqis_score_table_schema_version` = `1.0`.
- `scores.csv`: the same rows and columns in the same order. It is UTF-8 with a header row, `\n` line ends and minimal quoting. A null is an empty field, and floats are written in Python's shortest round-trip form (`repr`), so both files hold the same numbers.
- `summary.json`: the corpus numbers of both variants (see "Summary file"), as canonical JSON (sorted keys, no spaces, UTF-8).

Rows are sorted by `clip_id`, then `variant` (`disfluency_aware` before `main`). The same inputs give byte-identical files.

## Columns
| Column | Parquet type | Null | CSV form | Meaning |
| --- | --- | --- | --- | --- |
| `schema_version` | `string` | no | text | Score table schema version, `1.0`. |
| `run_card_id` | `string` | no | text | Run card of the run that produced the hypothesis: 64 lowercase hexadecimal characters. |
| `clip_id` | `string` | no | text | Clip scored: lowercase letters, digits and hyphens. |
| `variant` | `string` | no | text | `main` (fillers removed) or `disfluency_aware` (fillers kept). |
| `normaliser_name` | `string` | no | text | Normaliser of this variant, for example `aqis-whisper-english`. |
| `normaliser_version` | `string` | no | text | Its version, for example `1+whisper-normalizer-0.1.1`. |
| `ref_sha256` | `string` | no | text | SHA-256 (hex) of the reference text's UTF-8 bytes, exactly as given, before normalisation. |
| `hyp_sha256` | `string` | no | text | SHA-256 (hex) of the hypothesis text's UTF-8 bytes, exactly as given, before normalisation. |
| `ref_words` | `int64` | no | integer | Words in the normalised reference; equals `hits + substitutions + deletions`. |
| `hyp_words` | `int64` | no | integer | Words in the normalised hypothesis; equals `hits + substitutions + insertions`. |
| `hits` | `int64` | no | integer | Words aligned and equal. |
| `substitutions` | `int64` | no | integer | Words aligned but different. |
| `deletions` | `int64` | no | integer | Reference words missing from the hypothesis. |
| `insertions` | `int64` | no | integer | Hypothesis words not in the reference. |
| `errors` | `int64` | no | integer | `substitutions + deletions + insertions`, the word edit distance. |
| `wer` | `float64` | yes | float, or empty for null | `errors / ref_words`; null when the reference is empty. |
| `ref_chars` | `int64` | no | integer | Characters in the normalised reference, spaces between words included. |
| `hyp_chars` | `int64` | no | integer | Characters in the normalised hypothesis, spaces between words included. |
| `char_hits` | `int64` | no | integer | Characters aligned and equal. |
| `char_substitutions` | `int64` | no | integer | Characters aligned but different. |
| `char_deletions` | `int64` | no | integer | Reference characters missing from the hypothesis. |
| `char_insertions` | `int64` | no | integer | Hypothesis characters not in the reference. |
| `char_errors` | `int64` | no | integer | `char_substitutions + char_deletions + char_insertions`, the character edit distance. |
| `cer` | `float64` | yes | float, or empty for null | `char_errors / ref_chars`; null when `ref_chars` is 0. |

## Alignment
- **Words** are the normalised text split on single spaces; the empty text has no words. **Characters** are the normalised text's Unicode code points, including the single spaces between words, as `jiwer`'s default CER counts them.
- The alignment is a minimum-edit (Levenshtein) alignment with unit costs. Its `errors` is always the edit distance.
- **Tie-break.** When several minimum alignments exist, the split into substitutions, deletions and insertions follows `jiwer` 4.0.0, which gets its alignment from `rapidfuzz`:
  1. the longest common prefix and the longest common suffix are hits;
  2. on what remains, with `D[i][j]` the edit distance between the first `i` reference and first `j` hypothesis tokens, the path is traced back from the end;
  3. at each cell a **deletion** is taken when `D[i][j] = D[i-1][j] + 1`;
  4. otherwise an **insertion** is taken when `D[i][j-1] = D[i-1][j-1] - 1`;
  5. otherwise the **diagonal** step is taken (a hit or a substitution);
  6. what is left at the start is all deletions or all insertions.

  For example, reference `a b` against hypothesis `b c` gives 2 substitutions, and reference `a b` against `c a` gives 1 insertion, 1 hit and 1 deletion.
- The lab's aligner is its own pure-Python code. The tests compare its counts with the pinned `jiwer` on more than 200 generated pairs, and on 20,000 tie-heavy pairs in the slow suite (FR-0.3-07).
- **Cost.** Time grows with the product of the two lengths, and memory is one byte per cell. On the cloud VM, 1,500 × 1,500 tokens took about 1 s in a prototype.

## Empty references
A reference is empty when its normalised text is empty. This is judged per variant: `Um.` is empty in the main score but not in the disfluency-aware one.
- An empty reference still has a row: every hypothesis word is an insertion, and `wer` is null (undefined).
- It stays in the corpus totals: its insertions count as errors, and it adds 0 reference words.
- The same holds for characters and `cer`.

## Corpus numbers
For each variant:
- **`corpus_wer`** = total `errors` / total `ref_words` over all clips. This is the lab's WER. It is never the mean of per-clip WERs. It is null when there are no reference words at all.
- **`mean_utterance_wer`** = the unweighted mean of the per-clip `wer` values that are defined. It is reported beside the corpus WER, always labelled, with the number of clips it leaves out (`empty_references`). It is not the lab's WER.
- **`corpus_cer`** = total `char_errors` / total `ref_chars`.

The command prints both variants, main first. For example:
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
```
This is the real output for the test fixtures in `tests/aqis_lab/fixtures/scoring/` (12 clips).
Rates are printed with 6 decimals, or `undefined`.

## Summary file
`summary.json` has these keys:
- `schema_version`: `1.0`.
- `run_card_id`.
- `files`: the SHA-256 of `scores.parquet` and of `scores.csv`.
- `variants`: one object per variant, with `variant`, `normaliser_name`, `normaliser_version`, `utterances`, `empty_references`, `ref_words`, `hyp_words`, `hits`, `substitutions`, `deletions`, `insertions`, `errors`, `corpus_wer`, `utterances_with_wer`, `mean_utterance_wer`, `ref_chars`, `hyp_chars`, `char_hits`, `char_substitutions`, `char_deletions`, `char_insertions`, `char_errors` and `corpus_cer`. The rates are null when undefined.

## Input files
- **References**, `--ref`: CSV with the header `clip_id,text`.
- **Hypotheses**, `--hyp`: CSV with the header `run_card_id,clip_id,text`.

Both files are UTF-8, and a leading byte-order mark is accepted. A text may be empty and may contain line breaks or commas when quoted.

The command stops with `ERROR: ...` and exit code 2, writing nothing, when:
- a file is missing, unreadable or not UTF-8;
- a header is not exactly as above, or a record has the wrong number of fields (a blank line counts as one);
- a `clip_id` or `run_card_id` is not valid, or a `clip_id` repeats within a file;
- the two files do not list the same clips (every difference is named);
- the hypotheses carry more than one `run_card_id`;
- there are no clips at all;
- the normaliser package is not the pinned version;
- any output file already exists in `DIR` (results are never overwritten).

A missing hypothesis is an error, never an empty text; an explicitly empty text is scored. Output files are written under a `.part` name and renamed only when all three are complete.

## Versioning and change policy
- `schema_version` is `<major>.<minor>`, in the rows, in the Parquet metadata and in `summary.json`.
- A **minor** version adds something every existing reader survives, such as a new column at the end or a new key in the summary.
- A **major** version is anything else: a removed, renamed or reordered column, a changed type or meaning, or a changed alignment rule.
- The document, the code (`aqis_lab/scoring/table.py`) and the tests change in the same commit. The tests compare this column table with the written Parquet schema and CSV header.
