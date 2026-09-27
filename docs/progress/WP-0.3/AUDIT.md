# AUDIT — WP-0.3, round 3

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: 050bbf44d0b80ace94c5583999350d275f513983 · Previous audited commit: f930bdc6c0ffb3fa5378ed07577d56643500d6f4 · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 · MAJOR: 1 (fixed 1, accepted as debt 0, open 0) · MINOR: 2 (accepted as debt by the owner 2: DEBT-008, DEBT-009)

The round 2 work has now been built. **WP-0.3-F01 is fixed.** Two new tests cover a clip that is only in one file: `test_FR_0_3_06_one_sided_clip_is_an_input_error` (3 cases) and `test_FR_0_3_06_more_input_and_output_errors_exit_2` (5 sibling error paths).
- I re-ran the round 1 breaks X2 (reference-only check dropped) and X2m (hypothesis-only check dropped). Each now fails a named new test.
- No production code changed. The only change in `aqis_lab/` is the `score.py` module docstring: the CAP-SCORE-005 test list and one CHANGE LOG line.
- F02 and F03 are recorded in `docs/progress/DEBT.md` as DEBT-008 (target WP-0.6) and DEBT-009 (target WP-0.5). Both rows cite the owner's round 2 condition on `main` (`20ba9ba`).

Both suites, the gate and CI on `050bbf4` pass, and so do all three acceptance commands. All 28 of my must-catch breaks fail a named test. All 6 exploratory breaks are caught as well.

## Scope of this audit
Re-audit, round 3, as the protocol defines it:
1. **The three open findings from round 2.** Each was re-checked; its status is in the Findings table.
2. **Items A1 to A15 on the diff `f930bdc..050bbf4`.** This is five commits:
   - `bc669b4`: the round 2 report and the STATUS row;
   - `6659b9a`: a merge of `origin/main`, which only brings in the owner's round 2 approval line;
   - `c3464c2`: the F01 tests, the `score.py` docstring, the registry cell, `DEBT.md`, `FIXES.md` and `EVIDENCE.md`;
   - `52fab02`: a line count in `FIXES.md`;
   - `050bbf4`: the CI results in `EVIDENCE.md` and the STATUS row.

   Unchanged code that passed earlier audits (`normalise.py`, `wer.py`, `table.py` and the code of `score.py`) was not searched again.
3. **The full suites, the gate, CI on `050bbf4`, AT-0.3-01 to AT-0.3-03, and the complete must-catch proof (A6).** I re-ran or read all of these myself.

**Method.**
- **Copies.** I made three throwaway copies of `050bbf4` with `git archive HEAD`: `/tmp/wp03audit3`, `/tmp/wp03audit3b` and `/tmp/wp03audit3c`. Each uses the project `.venv` through a symlink. `aqis_lab` imports from the copy: the `__file__` of `normalise`, `wer`, `table` and `commands.score` are all under `/tmp/wp03audit3/`. The tests' `ROOT` comes from the test file's own location, and `run_score` runs with `cwd=ROOT`, so the CLI subprocesses also use the copy.
- **Breaks.** Each break is an exact-string replacement, checked to match exactly once before it is applied. Bytecode writing was off (`PYTHONDONTWRITEBYTECODE=1`), and `__pycache__` was cleared before and after each run.
- **Runs.** Each run is `pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_3 or NFR_0_3" -m "not network"`: the 184 fast WP-0.3 tests plus the slow tie-heavy cross-check. The unmodified copy gives `185 passed, 1008 deselected in 49.63s`.
- **Restore.** After each run, every changed file was restored and checked by SHA-256. At the end, `diff -r -x __pycache__` showed all three copies' `aqis_lab/` and `tests/aqis_lab/` identical to the branch. `git status --porcelain` in the repository was empty.
- **Break set.** My break set is my own. It keeps the round 2 breaks, with M4c moved to the aligner's empty-sequence branch. It adds six new breaks: M1d, M2e, M3d, M4f, M5d and M6e.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `git show origin/main:docs/progress/STATUS.md`: WP-0.0 and WP-0.2 are `MERGED`. The branch is `claude/charming-knuth-atc1dq`, not `main`, and its head equals `origin/claude/charming-knuth-atc1dq` (`050bbf4`). GitHub API: PR #3 is `open`, head `050bbf44d0b8`, base `main`. `git show origin/main:docs/approvals/WP-0.3.md` (`20ba9ba`) says `STATUS: APPROVED`, with the round 2 condition "fix WP-0.3-F01 … WP-0.3-F02 and WP-0.3-F03 are accepted as debt in docs/progress/DEBT.md (target WP-0.6 and WP-0.5)". `git diff --stat origin/main HEAD -- docs/approvals/ docs/specs/ docs/process/ CLAUDE.md .claude/` is empty. |
| A2 Requirement coverage | PASS | `pytest --collect-only -k "FR_0_3 or NFR_0_3"` gives `186/1193 tests collected`: FR_0_3_01 25, FR_0_3_02 74, FR_0_3_03 15, FR_0_3_04 23, FR_0_3_05 9, FR_0_3_06 31 (23 before, plus the 8 new cases), FR_0_3_07 6, NFR_0_3_01 3. All 8 new cases are collected and pass (`8 passed, 22 deselected in 1.23s`). The F01 work is recorded under "Round 2" in `EVIDENCE.md`, with the details in `FIXES.md`. |
| A3 Acceptance commands | PASS | **AT-0.3-01:** fast suite `1182 passed, 11 deselected in 111.17s (0:01:51)`, exit 0. This includes the 72 `test_FR_0_3_02_documented_example` cases and the jiwer cross-checks. **AT-0.3-02:** `rm -rf /tmp/score && .venv/bin/python -m aqis_lab score --ref tests/aqis_lab/fixtures/scoring/ref.csv --hyp tests/aqis_lab/fixtures/scoring/hyp.csv --out /tmp/score` exits 0. For `main` it prints `corpus WER 0.210526 = 8 errors / 38 reference words (S 1, D 5, I 2, H 32)` and `corpus CER 0.196203 = 31 errors / 158 reference characters`. For `disfluency_aware` it prints `corpus WER 0.250000 = 10 errors / 40 reference words`. Each variant also has a separate `mean per-utterance WER … (not the corpus WER; …)` line. It writes `scores.parquet` `3440f26a934e…`, `scores.csv` `8b09fb325223…` and `summary.json` `669efbf41dfe…`, which equal `EVIDENCE.md:264-266`. **AT-0.3-03:** `aqis-audit-gate: base origin/main (merge-base 20ba9bad5eff), head 050bbf44d0b8, approvals origin/main 20ba9bad5eff, wp WP-0.3 … Findings: 0 … 0 findings: OK (0.3 s)`, exit 0. |
| A4 Test suites and CI | PASS | **Fast suite:** as AT-0.3-01. **Slow and network** (`-m "(slow or network) and not gpu and not colab and not oracle"`): `11 passed, 1182 deselected in 79.82s`, exit 0. This includes `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` and `test_FR_0_3_01_matches_openai_whisper_original`. **CI on `050bbf4`** (GitHub API): push run 36329419642 and pull_request run 36329422104 are both `completed success`. In each, the jobs `lab` and `harness-regression` are `success`, with no step other than `success` or `skipped`. The four earlier round 2 runs that `EVIDENCE.md` cites also exist and are `completed success`: 36329183764 and 36329187110 on `c3464c2`, and 36329200040 and 36329204032 on `52fab02`. The proxy refused the job-log download (`CONNECT tunnel failed, response 403`), so I checked run, job and step conclusions only, not the log lines quoted in `EVIDENCE.md`. |
| A5 Test integrity | PASS | `git diff f930bdc HEAD -- tests/` removes no lines (count of `-` lines: 0). The two new test functions are appended at the end of `tests/aqis_lab/test_aqis_scoring_table.py`, and no existing test changed. A grep of the eight WP-0.3 test files for `pytest.skip`, `pytest.xfail`, `mark.skip`, `mark.xfail`, `importorskip`, `audit-allow` and trivial asserts finds nothing. The new tests check independent values: exit 2, `ERROR:` at the start of stderr, empty stdout, the one-sided clip named after its own file with `none` for the other file, and no output folder (or, for `out-is-a-file`, the file unchanged). The inputs are written with the `csv` module in the test, not by the code under test. |
| A6 Must-catch proof | PASS | 28 breaks across all 6 behaviours, each caught by named tests (table below). |
| A7 Compromise scan | PASS | Gate: 0 findings, 0 exempted lines, 0 exempted files. `git diff -U0 f930bdc HEAD -- aqis_lab` changes only the `score.py` module docstring: the CAP-SCORE-005 test list and the line `2026-09-27 WP-0.3 round 2 F01: header lists the new one-sided clip and input/output error tests (header only).`. There is no new production function to read. The new test code has no hard-coded outputs taken from the implementation, no mocks and no skips. |
| A8 Scope diff | PASS | The changed files match the change budget in `FIXES.md`: the test file (appended only), the `score.py` docstring, the CAP-SCORE-005 registry row, `DEBT.md` (two rows appended), `FIXES.md`, `EVIDENCE.md` (appended) and the STATUS row. `docs/approvals/WP-0.3.md` changed only through the merge of `main` (`git diff bc669b4 6659b9a --stat`: that one file, 1 line). It equals `main`. No lock, contract, config, tooling or harness path changed. One small note: the CAP-SCORE-005 "Introduced by" cell also gained `; round 2 F01`, which the `FIXES.md` budget does not mention. This follows the registry's existing convention (CAP-BASE-001, CAP-CI-001 and CAP-DOC-003/004 carry the same kind of round note) and removes nothing, so it is not a finding. |
| A9 Capabilities | PASS | The registry has 41 `CAP-` rows before and after, so no row was removed. The CAP-SCORE-005 Tests cell and the `score.py` header both list the two new tests. `test_FR_0_0_08_module_headers_match_registry` and the other FR_0_0_08 tests pass (`12 passed`). All linked tests are collected and pass in the fast suite. |
| A10 Contracts | PASS | `docs/contracts/` has not changed since `f930bdc`. `test_FR_0_3_01_identity_fits_the_run_card_contract`, `test_FR_0_3_06_parquet_schema_matches_score_table_doc` and `test_FR_0_3_06_csv_header_matches_score_table_doc` pass in the fast suite. The new tests enforce the documented input rule `SCORE_TABLE.md:109` ("a missing hypothesis is an error, never an empty text"). |
| A11 Environment parity | PASS | `git diff --quiet f930bdc HEAD -- requirements/` holds. The pins are unchanged: `jiwer==4.0.0`, `pyarrow==25.0.1`, `whisper-normalizer==0.1.1`. `.venv` is Python 3.13.12, and `docs/environment/colab_probe.txt` gives `3.13.15`, so the major.minor matches. `dev_bootstrap.sh`: `OK: .venv ready: Python 3.13.12, lock sha256 1524a39e…`. The new tests use `tmp_path` and paths derived from `ROOT`, with no absolute paths. The spec runs on the cloud VM only, so no owner-run checks apply. |
| A12 Reproducibility and traceability | PASS | My AT-0.3-02 files are byte-identical to the builder's and to rounds 1 and 2. `test_NFR_0_3_01_repeat_runs_give_identical_files` passes. Must-catch 1 and 6 hold (A6). |
| A13 Errors and logging | PASS | The new tests pin eight error paths of `read_records`, `read_inputs` and `_refuse_existing` to `ERROR:`, exit 2 and no output. F02 was re-confirmed and is unchanged: `--out <scratch>/afile/sub`, where `afile` is a regular file, gives `NotADirectoryError: [Errno 20] Not a directory: …`, exit 1. It fails loudly, and it is accepted debt (DEBT-008). |
| A14 Documentation, licences, data | PASS | `EVIDENCE.md` has a "Round 2" section: F01 fixed, the new tests, fast suite `1182 passed`, the gate, and the CI runs. My runs confirm its numbers. `FIXES.md` records root cause, change budget, baseline, reproduction and mutation proof. I re-ran its mutation claims (S1 to S5, X2 and X2m), and they hold (A15 and F01). `DEBT.md` has DEBT-008 and DEBT-009, each with risk, the approval commit `20ba9ba` and the target WP. Licences and fixtures are unchanged. The new test data is synthetic (`a b c`, `c-1`), with no personal data. |
| A15 Exploratory breaks | PASS | Since `f930bdc` no production code changed, only tests and a docstring. So I used 6 of the 10 breaks on the checks the 8 new tests claim to protect: the builder's S1 to S5 from `FIXES.md`, and X3 for the new "names the right file" assertion. All 6 are caught; there are no survivors. |

## Must-catch proof (A6)
| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Idempotent | M1a: `Normaliser.__call__` returns one `_step`, with no fixed point (`normalise.py:120`) | `test_FR_0_3_01_idempotent_on_generated_inputs`, `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point` (3 cases), `test_FR_0_3_02_documented_example[X01..X03]` (7 failed) | Caught |
| 1 Name and version in every row | M1b: rows write `normaliser_version.split("+")[-1]` (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 1 | M1c: rows write `aqis-whisper-english` as `normaliser_name` for both variants (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 1 | M1d (new): the normaliser's version is the bare package version `0.1.1`, without the wrapper's rules version (`normalise.py:99`) | `test_FR_0_3_01_exposes_name_and_version`, `test_FR_0_3_03_cli_prints_both_labelled_variants`, `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 2 S, D and I equal jiwer | M2a: the traceback prefers an insertion over a deletion when both are minimal (`wer.py:98-101`) | `test_FR_0_3_04_tie_break_follows_documented_rule`, `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs`, `…char_counts…`, `…corpus_totals_and_wer…`, `…tie_heavy_pairs…` (5 failed) | Caught |
| 2 | M2b: common prefix and suffix steps switched off (`wer.py:134`, `137`) | all four `test_FR_0_3_07_*` count tests (4 failed) | Caught |
| 2 | M2c: diagonal preferred over deletion when both are minimal (`wer.py:98`) | `test_FR_0_3_04_tie_break_follows_documented_rule` and all four `test_FR_0_3_07_*` count tests (5 failed) | Caught |
| 2 | M2d: a substitution costs 2 (`wer.py:92`) | `test_FR_0_3_04_hand_counted_alignments` (2 cases), `test_FR_0_3_04_errors_equal_edit_distance`, all four `test_FR_0_3_07_*` and 7 more (14 failed) | Caught |
| 2 | M2e (new): a substitution in the traceback is counted as a deletion (`wer.py:118`) | `test_FR_0_3_04_alignment_ops_rebuild_both_texts`, `test_FR_0_3_04_reference_length_is_hits_subs_dels`, all four `test_FR_0_3_07_*` and 7 more (13 failed) | Caught |
| 3 Corpus WER = total errors / total reference words | M3a: `corpus_wer` = mean of the per-utterance WERs (`wer.py:253`) | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` and 7 more (9 failed) | Caught |
| 3 | M3b: `corpus_wer` divides by hypothesis words (`wer.py:253`) | `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled` (both variants), `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` and 4 more (7 failed) | Caught |
| 3 | M3c: the printed "corpus WER" shows the mean per-utterance WER (`score.py:136`) | `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled[main]`, `[disfluency_aware]` | Caught |
| 3 | M3d (new): `summary.json` writes the mean per-utterance WER as `corpus_wer` (`score.py:191`) | `test_FR_0_3_06_summary_matches_rows` | Caught |
| 4 Empty references follow the rule | M4a: empty-reference utterances left out of the corpus word totals (`wer.py:244`) | `test_FR_0_3_04_empty_reference_enters_corpus_totals` and 8 more (9 failed) | Caught |
| 4 | M4b: an empty reference gets rate 0.0, not undefined (`wer.py:60`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_both_texts_empty` and 9 more (11 failed) | Caught |
| 4 | M4c: an empty reference's hypothesis words are not counted as insertions (aligner's empty-sequence branch, `wer.py:82`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_hand_counted_alignments[-a b-expected5]` and 15 more (17 failed) | Caught |
| 4 | M4d: empty-reference rows dropped from the table (`table.py:90`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 4 | M4e: an empty reference's WER = insertions / 1 (`wer.py:60`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_05_cli_prints_undefined_rates` and 9 more (11 failed) | Caught |
| 4 | M4f (new): the mean per-utterance WER counts an undefined WER as 0.0 (`wer.py:248`) | `test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled`, `test_FR_0_3_05_cli_prints_undefined_rates` and 5 more (7 failed) | Caught |
| 5 Main removes fillers, disfluency-aware keeps them | M5a: disfluency-aware variant built with `keeps_disfluencies=False` (`normalise.py:124`) | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler` (6 fillers), `test_FR_0_3_02_documented_example[F01..F05]` and 6 more (17 failed) | Caught |
| 5 | M5b: main variant built with `keeps_disfluencies=True` (`normalise.py:123`) | `test_FR_0_3_03_main_removes_each_listed_filler` (6 fillers), `test_FR_0_3_02_documented_example[F01..F05]` and 7 more (18 failed) | Caught |
| 5 | M5c: the two variants' labels swapped, so rows labelled `main` keep fillers (`normalise.py:123-124`) | `test_FR_0_3_03_both_variants_scored_and_labelled`, `test_FR_0_3_03_cli_prints_both_labelled_variants`, `test_FR_0_3_06_every_row_carries_trace_fields` and 6 more (9 failed) | Caught |
| 5 | M5d (new): the disfluency-aware variant still removes every filler except `um` (`normalise.py:35`) | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler[hmm, mm, mhm, mmm, uh]`, `test_FR_0_3_02_documented_example[F02..F05]` and 2 more (11 failed) | Caught |
| 6 Every row carries `run_card_id`, `clip_id` and both hashes | M6a: `hyp_sha256` of the normalised hypothesis (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |
| 6 | M6b: `ref_sha256` computed from the hypothesis text (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text`, `test_FR_0_3_06_accepts_bom_and_multiline_text` | Caught |
| 6 | M6c: rows carry `"0" * 64` instead of the input's `run_card_id` (`score.py:182`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 6 | M6d: rows carry `clip_id[:3]` (`table.py:92`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |
| 6 | M6e (new): the CSV file writes `"0" * 64` in the `run_card_id` column, while Parquet stays right (`table.py:124`) | `test_FR_0_3_06_csv_and_parquet_hold_the_same_rows` | Caught |

## Exploratory breaks (A15, at most 10)
No production code changed since `f930bdc`. These 6 breaks check that the 8 new tests protect what `FIXES.md` says they protect. All are in `aqis_lab/commands/score.py`.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| S1: the `clip_id` check runs only for the reference file (`if clip_column == 0 and not is_clip_id(clip_id):`) | `score.py:95` | No. `test_FR_0_3_06_more_input_and_output_errors_exit_2[hyp-bad-clip-id]` fails | — |
| S2: `except OSError` becomes `except PermissionError` when reading a file | `score.py:62` | No. `test_FR_0_3_06_input_errors_exit_2[missing-ref-file]` and `…more_input_and_output_errors_exit_2[hyp-missing-file]` fail | — |
| S3: `except csv.Error` becomes `except UnicodeError` | `score.py:86` | No. `…more_input_and_output_errors_exit_2[ref-unterminated-quote]` fails | — |
| S4: an empty file is accepted as having a header (`if first is not None and first != header:`) | `score.py:74` | No. `…more_input_and_output_errors_exit_2[ref-empty-file]` fails | — |
| S5: the `--out`-is-not-a-folder check becomes `if False:` | `score.py:145` | No. `…more_input_and_output_errors_exit_2[out-is-a-file]` fails | — |
| X3: the error message lists each file's one-sided clips under the other file's name | `score.py:123-124` | No. All 3 `test_FR_0_3_06_one_sided_clip_is_an_input_error` cases fail | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.3-F01 | MAJOR | A15 in round 1 (outside the must-catch list) | **Fixed.** `test_FR_0_3_06_one_sided_clip_is_an_input_error` covers a clip only in the reference file, a clip only in the hypothesis file, and an empty reference file with one hypothesis. Each case requires exit 2, `ERROR:`, empty stdout, the clip named after its own file with `none` for the other file, and no output folder. The rule "a missing hypothesis is an error, never an empty text" (`SCORE_TABLE.md:109`, CAP-SCORE-005) is now protected in both directions | X2 (reference-only check dropped, missing hypothesis read as `""`): `1 failed, 184 passed`, `FAILED test_FR_0_3_06_one_sided_clip_is_an_input_error[clip-only-in-ref]`. X2m (hypothesis-only check dropped): `2 failed, 183 passed`, `FAILED …[clip-only-in-hyp]`, `FAILED …[ref-empty-hyp-has-clip]`. The unmodified copy gives `185 passed` | Closed. No further action |
| WP-0.3-F02 | MINOR | A13 | An `--out` folder that cannot be created gives an uncaught traceback and exit 1, not `ERROR:` and exit 2 (`score.py:155`, outside the `try`). Nothing is written, and the failure is loud. Unchanged since round 1 | Re-run this round: `NotADirectoryError: [Errno 20] Not a directory: …/afile/sub`, `exit=1`. `DEBT.md` row DEBT-008 cites `20ba9ba` | **Accept as debt, target WP-0.6** (already accepted by the owner; DEBT-008) |
| WP-0.3-F03 | MINOR | A13 | No test covers the wiring of the version check: that the normaliser calls `check_package_version` on first use (`normalise.py:82`), and that `score` maps `NormaliserVersionError` or `NormalisationError` to exit 2 (`score.py:183-184`). The hash-pinned lock and `test_FR_0_3_01_installed_package_is_the_pinned_version` limit the risk. Unchanged since round 1 | `git diff f930bdc HEAD -- aqis_lab/scoring tests/aqis_lab/test_aqis_scoring_normalise.py` is empty. `DEBT.md` row DEBT-009 cites `20ba9ba` | **Accept as debt, target WP-0.5** (already accepted by the owner; DEBT-009) |

No new findings this round.

## Convergence (round 3 onwards)
| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 1 (F01) | 2 (F02, F03) | None |
| 2 | 0 | 1 (F01, open) | 2 (accepted as debt) | None |
| 3 | 0 | 0 open (F01 fixed) | 2 (accepted as debt: DEBT-008, DEBT-009) | None |

The counts went down, and no open finding sits inside the must-catch list. PASS, with the two MINOR findings carried as debt.

## For the owner
- **Next step:** review and merge PR #3, then set WP-0.3 to `MERGED` in `docs/progress/STATUS.md`.
- **audit-allow lines:** None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- **Approvals used:** `docs/approvals/WP-0.3.md` on `main` (`20ba9ba`). It holds "Questions 1-7: as recommended in PLAN.md" and the round 2 condition: fix F01; F02 and F03 accepted as debt with targets WP-0.6 and WP-0.5.
- **Debt accepted so far:**
  - WP-0.3-F02, as DEBT-008, target WP-0.6;
  - WP-0.3-F03, as DEBT-009, target WP-0.5.

  Both rows are in `docs/progress/DEBT.md`, marked `OPEN`.
- **Owner-run checks still pending:** None. The spec runs this WP on the cloud VM only.
- **Audit limit:** the proxy refused the CI job-log download. So CI was checked through run, job and step conclusions from the GitHub API, not through the log lines quoted in `EVIDENCE.md`.
