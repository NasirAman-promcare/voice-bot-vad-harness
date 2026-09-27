# AUDIT — WP-0.3, round 2

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: f930bdc6c0ffb3fa5378ed07577d56643500d6f4 · Previous audited commit: df677eddbb82cb28ef678ebb2b26cc11d52343de · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 1 (fixed 0, accepted as debt 0, open 1) · MINOR: 2 (accepted as debt by the owner 2, `DEBT.md` rows not yet written)

Nothing has changed on the branch since round 1. The only commit after the audited `df677ed` is `f930bdc`, which is the round 1 audit report and the STATUS row. There are no code, test, evidence or debt changes. The owner's round 2 condition on `main` (`20ba9ba`) says to fix WP-0.3-F01, and to record F02 and F03 as debt. The builder has not yet done this round 2 work.

So the result is the same as round 1:
- **F01 (MAJOR) is still open.** No test covers either direction of a clip-set mismatch on its own. I re-ran the round 1 break (X2: reference-only check dropped) and its mirror (X2m: hypothesis-only check dropped), and both survive with `177 passed`. Under X2, a clip with no hypothesis is scored as 3 deletions (WER 1.0) and the command exits 0. Under X2m, a hypothesis for a clip that is not in the reference file is silently dropped and the command exits 0. The unmodified code rejects both inputs (exit 2, no output). This is a missing test, not a code defect.
- **F02 and F03 (MINOR)** are accepted as debt in the owner's round 2 condition. Their `DEBT.md` rows do not exist yet; the builder adds them.

Everything else still holds. Both suites, the gate, CI on `f930bdc` and all three acceptance commands pass. All 21 of my must-catch breaks fail a named test. The AT-0.3-02 output files are byte-identical to `EVIDENCE.md`.

## Scope of this audit
Re-audit, round 2, as the protocol defines it:
1. **The three round 1 findings.** Each was re-checked; its status is in the Findings table.
2. **Items A1 to A15 on the diff `df677ed..f930bdc`.** It is one commit, `f930bdc`. It adds `docs/progress/WP-0.3/AUDIT.md` (the round 1 report) and changes the WP-0.3 row of `docs/progress/STATUS.md` from `READY-FOR-AUDIT` to `AUDIT-FAIL`. `git diff --name-only df677ed HEAD -- aqis_lab tools tests requirements config docs/contracts docs/capabilities` is empty. `main` gained one commit since the merge-base: `20ba9ba`, which adds the round 2 condition to `docs/approvals/WP-0.3.md`. The branch has not merged it; the gate and hooks read approvals from `origin/main`, so this does not matter for the audit. Unchanged code that passed round 1 was not searched again.
3. **The full suites, the gate, CI on `f930bdc`, AT-0.3-01 to AT-0.3-03, and the complete must-catch proof (A6).** I re-ran or read all of these myself.

**Method.**
- I made three throwaway copies of `f930bdc` with `git archive HEAD`: `/tmp/wp03audit2`, `/tmp/wp03audit2b` and `/tmp/wp03audit2c`. Each uses the project `.venv` through a symlink.
- `aqis_lab` imports from the copy: the `__file__` of `normalise`, `wer`, `table` and `score` are all under `/tmp/wp03audit2/`. The tests' `ROOT` comes from the test file's own location, and `run_score` runs with `cwd=ROOT`, so the CLI subprocesses also use the copy.
- Each break is an exact-string replacement, asserted to match exactly once. Bytecode writing was off (`PYTHONDONTWRITEBYTECODE=1`), and `__pycache__` was cleared before and after each run.
- Each run is `pytest tests/aqis_lab -k "FR_0_3 or NFR_0_3" -m "not network"`: the 176 fast WP-0.3 tests plus the slow tie-heavy cross-check. The unmodified copy gives `177 passed, 1008 deselected in 50.98s`.
- After each run, every changed file was restored and checked by SHA-256. At the end, `diff -r -x __pycache__` showed all three copies' `aqis_lab/` and `tests/aqis_lab/` identical to the branch. `git status --porcelain` in the repository was empty.
- My break set is my own, written for this round. Besides the round 1 breaks, it adds M2d (substitution costs 2), M3c (the printed corpus WER is the mean), M4e (an empty reference gets WER = insertions) and M5c (variant labels swapped).

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.0 and WP-0.2 are `MERGED` in `git show origin/main:docs/progress/STATUS.md`. The branch is `claude/charming-knuth-atc1dq`, not `main`, and PR #3 is open with head `f930bdc`. `git show origin/main:docs/approvals/WP-0.3.md` (`20ba9ba`) says `STATUS: APPROVED`. Its CONDITIONS are "Questions 1-7: as recommended in PLAN.md" and "Round 2: fix WP-0.3-F01 (add asymmetric clip-set input error tests). WP-0.3-F02 and WP-0.3-F03 are accepted as debt in docs/progress/DEBT.md (target WP-0.6 and WP-0.5)." |
| A2 Requirement coverage | PASS | No change since round 1. `pytest --collect-only -k "FR_0_3 or NFR_0_3"` gives `178/1185 tests collected`: FR_0_3_01 25, FR_0_3_02 74, FR_0_3_03 15, FR_0_3_04 23, FR_0_3_05 9, FR_0_3_06 23, FR_0_3_07 6, NFR_0_3_01 3. |
| A3 Acceptance commands | PASS | **AT-0.3-01:** fast suite `1174 passed, 11 deselected in 111.52s`, exit 0. This includes the 72 `test_FR_0_3_02_documented_example` cases and the jiwer cross-checks. **AT-0.3-02:** `rm -rf /tmp/score && .venv/bin/python -m aqis_lab score --ref tests/aqis_lab/fixtures/scoring/ref.csv --hyp tests/aqis_lab/fixtures/scoring/hyp.csv --out /tmp/score` exits 0. It prints `corpus WER 0.210526 = 8 errors / 38 reference words (S 1, D 5, I 2, H 32)` and `corpus CER 0.196203 = 31 errors / 158 reference characters` for `main`, and `corpus WER 0.250000 = 10 errors / 40 reference words` for `disfluency_aware`. Each variant also has a separate `mean per-utterance WER … (not the corpus WER; …)` line. It writes `scores.parquet` `3440f26a934e…`, `scores.csv` `8b09fb325223…` and `summary.json` `669efbf41dfe…`, which equal `EVIDENCE.md:264-266`. **AT-0.3-03:** `aqis-audit-gate: base origin/main (merge-base 2879cf4890c2), head f930bdc6c0ff, approvals origin/main 20ba9bad5eff, wp WP-0.3 … Findings: 0 … 0 findings: OK (0.6 s)`, exit 0. |
| A4 Test suites and CI | PASS | Fast: as AT-0.3-01. Slow and network (`-m "(slow or network) and not gpu and not colab and not oracle"`): `11 passed, 1174 deselected in 88.54s`, exit 0. This includes `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` and `test_FR_0_3_01_matches_openai_whisper_original`. CI on `f930bdc`, read from the GitHub API: push run 36327136448 and pull_request run 36327139287 are both `completed success`, and in each the jobs `lab` and `harness-regression` are `success` with no failed step. |
| A5 Test integrity | PASS | `git diff df677ed HEAD -- tests/` is empty. A grep of the WP-0.3 test files for `pytest.skip`, `pytest.xfail`, `mark.skip`, `mark.xfail`, `importorskip` and `audit-allow` finds nothing. |
| A6 Must-catch proof | PASS | 21 breaks across all 6 behaviours, all caught by named tests (table below). |
| A7 Compromise scan | PASS | Gate: 0 findings, 0 exempted lines, 0 exempted files. No production code changed since `df677ed`, so there is nothing new to read. |
| A8 Scope diff | PASS | The diff since `df677ed` is the round 1 report and one STATUS cell, both auditor files. No code, test, lock, contract, registry or protected path changed. |
| A9 Capabilities | PASS | `docs/capabilities/REGISTRY.md` and the module headers are unchanged since round 1. The linked tests are collected and pass in both suites. |
| A10 Contracts | PASS | Unchanged since round 1. `test_FR_0_3_01_identity_fits_the_run_card_contract`, `test_FR_0_3_06_parquet_schema_matches_score_table_doc` and `test_FR_0_3_06_csv_header_matches_score_table_doc` pass. |
| A11 Environment parity | PASS | `git diff --quiet df677ed HEAD -- requirements/` holds. The pins are unchanged: `jiwer==4.0.0`, `pyarrow==25.0.1`, `whisper-normalizer==0.1.1`. `.venv` is Python 3.13.12, and the Colab probe is `3.13.15`, so the major.minor matches. `dev_bootstrap.sh`: `OK: .venv ready: Python 3.13.12, lock sha256 1524a39e…`. The spec runs on the cloud VM only, so no owner-run checks apply. |
| A12 Reproducibility and traceability | PASS | My AT-0.3-02 files are byte-identical to the builder's and to round 1. `test_NFR_0_3_01_repeat_runs_give_identical_files` passes. Must-catch 1 and 6 hold (A6). |
| A13 Errors and logging | PASS | Unchanged since round 1. F02 is re-confirmed: `--out <scratch>/afile/sub`, where `afile` is a regular file, gives `NotADirectoryError: [Errno 20] Not a directory: …`, exit 1. It fails loudly, and the owner has accepted it as debt. |
| A14 Documentation, licences, data | PASS | `NORMALISATION.md`, `SCORE_TABLE.md`, `EVIDENCE.md`, licences and fixtures are unchanged since round 1, where they passed. The round 2 records the approval implies are missing because no round 2 build has happened: a round 2 `EVIDENCE.md` entry for F01, and the `DEBT.md` rows for F02 and F03. See "For the owner". |
| A15 Exploratory breaks | N/A | No code was added or changed since `df677ed`, so there were 0 exploratory breaks. The two breaks X2 and X2m re-check open finding F01 and are reported under that finding. |

## Must-catch proof (A6)
| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Idempotent | M1a: `Normaliser.__call__` returns one `_step`, with no fixed point (`normalise.py:120`) | `test_FR_0_3_01_idempotent_on_generated_inputs`, `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point` (3 cases), `test_FR_0_3_02_documented_example[X01..X03]` (7 failed) | Caught |
| 1 Name and version in every row | M1b: rows write `normaliser_version.split("+")[-1]` (`whisper-normalizer-0.1.1`) (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 1 Name and version in every row | M1c: rows write `aqis-whisper-english` as `normaliser_name` for both variants (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 2 S, D and I equal jiwer | M2a: insertion checked before deletion in the traceback (`wer.py:98-101`) | `test_FR_0_3_04_tie_break_follows_documented_rule`, `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs`, `…char_counts…`, `…corpus_totals_and_wer…`, `…tie_heavy_pairs…` (5 failed) | Caught |
| 2 | M2b: common prefix and suffix steps switched off (`wer.py:134`, `137`) | all four `test_FR_0_3_07_*` count tests (4 failed) | Caught |
| 2 | M2c: diagonal preferred over deletion when both are minimal (`wer.py:98`) | `test_FR_0_3_04_tie_break_follows_documented_rule` and all four `test_FR_0_3_07_*` count tests (5 failed) | Caught |
| 2 | M2d: a substitution costs 2 (`wer.py:92`) | `test_FR_0_3_04_hand_counted_alignments`, `test_FR_0_3_04_errors_equal_edit_distance`, all four `test_FR_0_3_07_*` and 8 more (14 failed) | Caught |
| 3 Corpus WER = total errors / total reference words | M3a: `corpus_wer` = mean of the per-utterance WERs (`wer.py:253`) | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` and 7 more (9 failed) | Caught |
| 3 | M3b: `corpus_wer` divides by hypothesis words (`wer.py:253`) | `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled` (both variants), `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` and 4 more (7 failed) | Caught |
| 3 | M3c: the printed "corpus WER" shows the mean per-utterance WER (`score.py:135`) | `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled[main]`, `[disfluency_aware]` | Caught |
| 4 Empty references follow the rule | M4a: empty-reference utterances left out of the corpus word totals (`wer.py:244`) | `test_FR_0_3_04_empty_reference_enters_corpus_totals` and 8 more (9 failed) | Caught |
| 4 | M4b: an empty reference gets rate 0.0, not undefined (`wer.py:60`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_both_texts_empty` and 9 more (11 failed) | Caught |
| 4 | M4c: an empty reference's hypothesis words are not counted as insertions (`wer.py:179`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined` and 8 more (9 failed) | Caught |
| 4 | M4d: empty-reference rows dropped from the table (`table.py:90`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 4 | M4e: an empty reference's WER = insertions / 1 (`wer.py:60`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_05_cli_prints_undefined_rates` and 9 more (11 failed) | Caught |
| 5 Main removes fillers, disfluency-aware keeps them | M5a: disfluency-aware variant built with `keeps_disfluencies=False` (`normalise.py:124`) | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler` (6 fillers), `test_FR_0_3_02_documented_example[F01..F05]` and 6 more (17 failed) | Caught |
| 5 | M5b: main variant built with `keeps_disfluencies=True` (`normalise.py:123`) | `test_FR_0_3_03_main_removes_each_listed_filler` (6 fillers), `test_FR_0_3_02_documented_example[F01..F05]` and 7 more (18 failed) | Caught |
| 5 | M5c: the two variants' labels swapped, so rows labelled `main` keep fillers (`normalise.py:123-124`) | `test_FR_0_3_03_both_variants_scored_and_labelled`, `test_FR_0_3_03_cli_prints_both_labelled_variants`, `test_FR_0_3_06_every_row_carries_trace_fields` and 6 more (9 failed) | Caught |
| 6 Every row carries `run_card_id`, `clip_id` and both hashes | M6a: `hyp_sha256` of the normalised hypothesis (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |
| 6 | M6b: `ref_sha256` computed from the hypothesis text (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text`, `test_FR_0_3_06_accepts_bom_and_multiline_text` | Caught |
| 6 | M6c: rows carry `"0" * 64` instead of the input's `run_card_id` (`score.py:181`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 6 | M6d: rows carry `clip_id[:3]` (`table.py:92`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |

## Exploratory breaks (A15, at most 10)
None. No code was added or changed since the previous audited commit `df677ed`.

These two breaks re-check open finding F01; they are not exploratory:

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X2 Reference-only check dropped (`if only_ref or only_hyp:` becomes `if only_hyp:`), and a missing hypothesis read as `""` | `score.py:121`, `124` | **Yes**, `177 passed`. CLI in the copy: a reference file with `c-1,a b c` and `c-2,d e f`, and a hypothesis file with only `c-1`, give exit 0 and a `main` row `c-2 ref_words 3 hyp_words 0 deletions 3 wer 1.0` | MAJOR (F01, from round 1) |
| X2m Hypothesis-only check dropped (`if only_ref or only_hyp:` becomes `if only_ref:`) | `score.py:121` | **Yes**, `177 passed`. CLI in the copy: references `c-1`, `c-2` and hypotheses `c-1`, `c-2`, `c-3` give exit 0; `c-3` is silently not scored | Same finding (F01) |

With the unmodified code, both inputs give `ERROR: the two files must list the same clips; only in …: c-2; only in …: none` (and the mirror naming `c-3`), exit 2, with no output folder.

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.3-F01 | MAJOR | A15 in round 1 (outside the must-catch list) | **Open, not fixed.** No commit since `df677ed` touches `tests/`. The rule "a missing hypothesis is an error, never an empty text" (`SCORE_TABLE.md:109`, `score.py:10`, CAP-SCORE-005) still has no test for either one-sided mismatch. The only clip-set case, `clip-sets-differ` (`test_aqis_scoring_table.py:167-168`, `190-191`), has an extra clip on both sides at once, so it passes as long as either check survives. If the reference-only check is lost, an incomplete run (an adapter that crashed on some clips) is reported as successfully scored, with those clips counted as all deletions. If the hypothesis-only check is lost, hypotheses for clips not in the reference are dropped without a word | X2 and X2m above, both `177 passed`; `git diff df677ed HEAD -- tests/` empty | **Fix now, tests only**, as the owner's round 2 condition already orders. Add two `INPUT_ERRORS` cases, one with a clip only in the reference file and one with a clip only in the hypothesis file. Each must require exit 2, `ERROR:` with the one-sided clip named in stderr, and no output folder. No production change is needed. The next audit will re-run X2 and X2m, and each must fail a named test |
| WP-0.3-F02 | MINOR | A13 | An `--out` folder that cannot be created gives an uncaught traceback and exit 1, not `ERROR:` and exit 2 (`score.py:154`, outside the `try`). Nothing is written, and the failure is loud. Unchanged since round 1 | Re-run this round: `NotADirectoryError: [Errno 20] Not a directory: …/afile/sub`, `exit=1` | **Accept as debt, target WP-0.6.** The owner accepted this in the round 2 condition (`20ba9ba`). The builder still has to add the `DEBT.md` row |
| WP-0.3-F03 | MINOR | A13 | No test covers the version check's wiring: that the normaliser calls `check_package_version` on first use (`normalise.py:81-82`), and that `score` maps `NormaliserVersionError` or `NormalisationError` to exit 2 (`score.py:180-183`). The hash-pinned lock and `test_FR_0_3_01_installed_package_is_the_pinned_version` limit the risk. Unchanged since round 1 | `grep -rl -E 'installed_package_version\|_whisper_english_normaliser\|dist-info' tests/aqis_lab/` matches only the unit test of `check_package_version` and the unrelated harness provisioning test | **Accept as debt, target WP-0.5.** The owner accepted this in the round 2 condition (`20ba9ba`). The builder still has to add the `DEBT.md` row |

## Convergence (round 3 onwards)
Not applicable: round 2. For reference:

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 0 | 1 | 2 | None |
| 2 | 0 | 1 (same F01, open) | 2 (accepted as debt) | None |

## For the owner
- **Why this round fails:** the round 2 fixes were never built. The branch head is still the round 1 audit commit, and STATUS was `AUDIT-FAIL`, not `READY-FOR-AUDIT`, when this audit ran. The next step is `/wp-build WP-0.3` for round 2. The builder should:
  1. add the two F01 tests;
  2. add `DEBT.md` rows for F02 (target WP-0.6) and F03 (target WP-0.5);
  3. record the round 2 evidence;
  4. set READY-FOR-AUDIT.

  After that, `/wp-audit WP-0.3` again. That audit will be small: the F01 tests, the new DEBT rows, the suites, CI and the must-catch proof.
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- Approvals used: `docs/approvals/WP-0.3.md` on `main` (`20ba9ba`). It holds "Questions 1-7: as recommended in PLAN.md" and the round 2 condition: fix F01; F02 and F03 accepted as debt with targets WP-0.6 and WP-0.5.
- Debt accepted so far: WP-0.3-F02 (target WP-0.6) and WP-0.3-F03 (target WP-0.5), both by the owner's round 2 condition. Neither has a `DEBT.md` row yet.
- Owner-run checks still pending: None. The spec runs this WP on the cloud VM only.
