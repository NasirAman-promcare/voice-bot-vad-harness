# AUDIT — WP-0.3, round 1

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: df677eddbb82cb28ef678ebb2b26cc11d52343de · Previous audited commit: first audit · Protocol: version 2

## Verdict: FAIL
CRITICAL: 0 · MAJOR: 1 (fixed 0, accepted as debt 0, open 1) · MINOR: 2

The production code does what the spec and the approved plan say. I found no stubs, fake data, swallowed errors or scope drift. Every suite, the gate, CI on the audited commit and the three acceptance commands give the expected output. All 18 of my must-catch breaks were caught by named tests.

The audit fails on one missing test, not on a code defect:
- **F01 (MAJOR).** No test gives the `score` command a reference clip that has no hypothesis. The only clip-set test has extra clips on both sides at once. If the reference-only check is dropped and a missing hypothesis is scored as empty text, all 177 WP-0.3 tests still pass. The command then exits 0 and writes scores for a hypothesis that does not exist. The code rejects this input today (exit 2).

The fix is tests only.

## Scope of this audit
First audit of WP-0.3: the whole diff `origin/main...df677ed` (merge-base `2879cf4`), which has 25 files, all additions except two changed lines (the CAP-ENV-002 "What it does" cell and the STATUS row). I checked:
- items A1 to A15;
- the fast and slow suites, the gate, CI and AT-0.3-01 to AT-0.3-03, all re-run or read myself;
- the complete must-catch proof (A6), with my own 18 breaks, not the builder's script;
- 10 exploratory breaks (A15) in the WP's new code.

All breaks were made in a throwaway copy of the audited commit (`git archive HEAD` into `/tmp/wp03audit`). I checked that the copy imports its own `aqis_lab` (`__file__` of all four modules). Each break was an exact-string replacement, asserted to match once. Each run used the project `.venv`, with bytecode writing off and `__pycache__` cleared. Each run covered the 177 WP-0.3 tests (`-k "FR_0_3 or NFR_0_3" -m "not network"`: the 176 fast tests plus the slow tie-heavy cross-check). The unmodified copy gives `177 passed`. Every file was restored after its run and checked by SHA-256. At the end, `diff -r` showed the copy's `aqis_lab/` identical to the branch. The working tree was not changed (`git status --porcelain` empty at `df677ed`).

I also made these independent checks, none of which change code:
- **Alignment against jiwer.** I used my own generator and seed, not the builder's: 40,000 word pairs (vocabularies of 1 to 200 tokens, lengths 0 to 100), 10,000 character pairs over `a`, `b` and space, and 6 pairs of 800 to 1,500 tokens. There were 0 count differences from `jiwer.process_words` and `jiwer.process_characters`.
- **Idempotence.** 60,000 random texts × 2 variants, built from number words, currency, symbols, `’`, NBSP, zero-width space, ligatures, Arabic digits, `½`, fillers and contractions. There were 0 `NormalisationError`s, 0 non-idempotent outputs and 0 spacing faults.
- **Fixture hand counts.** I recounted the 12 fixture clips by hand. Main has 8 errors over 38 reference words and disfluency-aware has 10 over 40. I recomputed corpus WER, mean WER and the raw-text SHA-256 values from `scores.csv` and `scores.parquet`, and all agree.

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.0 and WP-0.2 are `MERGED` in `git show origin/main:docs/progress/STATUS.md`. The branch is `claude/charming-knuth-atc1dq`, not `main`. `git show origin/main:docs/approvals/WP-0.3.md` has `STATUS: APPROVED` (commit `2879cf4`) and `CONDITIONS: Questions 1-7: as recommended in PLAN.md.` |
| A2 Requirement coverage | PASS | `pytest --collect-only` collects tests named after every ID: FR_0_3_01 25 (1 slow and network), FR_0_3_02 74, FR_0_3_03 15, FR_0_3_04 23, FR_0_3_05 9, FR_0_3_06 23, FR_0_3_07 6 (1 slow), NFR_0_3_01 3; 178 in total (176 fast, 2 slow). Each ID has code in `aqis_lab/scoring/` or `aqis_lab/commands/score.py`, and an entry with a command and output in `EVIDENCE.md`. |
| A3 Acceptance commands | PASS | **AT-0.3-01:** `1174 passed, 11 deselected in 118.27s`, exit 0. This includes the 72 `test_FR_0_3_02_documented_example` cases and the 212-pair jiwer cross-check. **AT-0.3-02:** `rm -rf /tmp/score && .venv/bin/python -m aqis_lab score --ref tests/aqis_lab/fixtures/scoring/ref.csv --hyp tests/aqis_lab/fixtures/scoring/hyp.csv --out /tmp/score` exits 0. It prints `corpus WER 0.210526 = 8 errors / 38 reference words` and `corpus CER 0.196203 = 31 errors / 158 reference characters` (main), with a labelled block for `disfluency_aware`. It writes `scores.parquet`, `scores.csv` and `summary.json`, and their SHA-256 values (`3440f26a…`, `8b09fb32…`, `669efbf4…`) equal those in `EVIDENCE.md`: byte-identical across sessions. **AT-0.3-03:** `aqis-audit-gate: base origin/main (merge-base 2879cf4890c2), head df677eddbb82 … Findings: 0 … 0 findings: OK (0.3 s)`, exit 0. |
| A4 Test suites and CI | PASS | Fast suite: `1174 passed, 11 deselected`. Slow and network (`-m "(slow or network) and not gpu and not colab and not oracle"`): `11 passed, 1174 deselected in 121.31s`. This includes `test_FR_0_3_07_tie_heavy_pairs_match_jiwer`, `test_FR_0_3_01_matches_openai_whisper_original` (downloads the OpenAI sdist and checks its SHA-256), both lock tests and the provisioning tests. CI on `df677ed`, read from the GitHub API: push run 36324571198 and pull_request run 36324574172, jobs `lab` and `harness-regression` all `success`. I could not read the log text, because the log download redirect returns a proxy 403. Arithmetic check of EVIDENCE: 998 baseline + 176 new fast tests = 1174; 9 + 2 new slow tests = 11 deselected. |
| A5 Test integrity | PASS | `git diff --diff-filter=MDR --name-status 2879cf4 HEAD -- tests/` is empty: every test file is new. There is no `skip`, `xfail`, `importorskip` or `audit-allow` in the new tests. The only markers are `slow` on the 20,000-pair tie-heavy test, and `slow` plus `network` on the OpenAI comparison, both as planned. Expected values are independent of the code: hand counts are written in comments (I re-derived them), the textbook distance is in `aqis_scoring_testutil.py`, hashes come from `hashlib`, and jiwer is the reference implementation. |
| A6 Must-catch proof | PASS | 18 breaks across all 6 behaviours, all caught by named tests (table below). |
| A7 Compromise scan | PASS | The gate reports 0 findings, 0 exempted lines and 0 exempted files. I read every new function. There are no stubs, TODOs or placeholders. No value is hard-coded to satisfy a test: names, versions and the schema version are the approved design. `installed_package_version` returns `None` only for `PackageNotFoundError`, and `check_package_version` then raises. `write_outputs` catches `OSError` only to delete partial files, then re-raises as `InputError`. The `SyntaxWarning` filter is scoped to one import and disclosed in the header. |
| A8 Scope diff | PASS | The changed files match the plan's change budget. `aqis_lab/__main__.py` has +2 lines: the `COMMANDS` entry and one CHANGE LOG line; `build_parser` and `main` are unchanged. In `REGISTRY.md`, one cell of CAP-ENV-002 changed (as planned) and 7 rows were appended. `phase0.in` gained one commented block, and `phase0.txt` has insertions only. `STATUS.md` changed only its WP-0.3 row. All changed paths are LAB-OWNED or unguarded. No GUARDED or NEVER path changed. |
| A9 Capabilities | PASS | All five new modules have the standard header. Rows CAP-SCORE-001 to 005 and CAP-DOC-005 and 006 were added, and no row was removed (`git diff` shows 1 `-|` line, the CAP-ENV-002 cell). Every test named in those rows and in the four module headers is collected (script check: 0 missing). |
| A10 Contracts | PASS | `normaliser_identity()` placed in the WP-0.2 run card fixture passes `validate_run_card` (test). The Parquet schema (names, types, nullability, `aqis_score_table_schema_version` = `1.0`) and the CSV header equal the `SCORE_TABLE.md` column table (tests). The 23 per-variant keys of `summary.json` equal the list in `SCORE_TABLE.md` (script check). The fixture `run_card_id` is the WP-0.2 run card's ID. |
| A11 Environment parity | PASS | A grep of the new code finds no absolute paths and no environment, clock, random or locale input. Python 3.13 matches the Colab probe (`3.13.15`). New pins are hash-locked, and the lock has cp313 manylinux and musllinux wheel hashes for both x86_64 and aarch64 for `pyarrow`, `regex` and `rapidfuzz` (checked against PyPI). The word list `english.json` is pure ASCII, so the package's `open()` without an encoding cannot vary by locale. The spec runs on the cloud VM only, so no owner-run checks are needed. `EVIDENCE.md` says so, and WP-0.7 proves cross-platform parity. |
| A12 Reproducibility and traceability | PASS | Determinism: `test_NFR_0_3_01_repeat_runs_give_identical_files` (shuffled rows, different `PYTHONHASHSEED`, `LC_ALL` and `TZ`), and my AT-0.3-02 files are byte-identical to the builder's. Every row carries `run_card_id`, `clip_id`, both raw-text SHA-256 values, the variant, and the normaliser name and version (must-catch 1 and 6). |
| A13 Errors and logging | PASS | Input errors give `ERROR: <file> line <n>: …` and exit 2, and no output is left behind (10 tested cases plus non-UTF-8). An existing output is never overwritten (tested). A text that never settles raises `NormalisationError`. Two lower-risk gaps: an `--out` that cannot be created gives a traceback and exit 1 instead of exit 2 (F02); the wiring of the package version check has no test (F03). Both fail loudly. |
| A14 Documentation, licences, data | PASS | `NORMALISATION.md` covers the normalisers, steps, filler list, variants, surprising behaviours, 72 examples, usage and the change policy. I checked its usage snippet and 7 extra claims (`$1`, `1/4`, `umbrella`, `Um,`, `mm-hmm`, `cause of the fire`, `2024-03-03`) against the code. `SCORE_TABLE.md` covers columns, the alignment rule, empty references, corpus numbers, the summary file, inputs and versioning. `EVIDENCE.md` has an entry for every ID. Licences of the new packages are permissive: whisper-normalizer MIT, jiwer Apache-2.0, pyarrow Apache-2.0, rapidfuzz MIT, regex Apache-2.0 and CNRI-Python, more-itertools MIT, indic-num2words Apache, click BSD-3-Clause. No third-party code is vendored. The fixtures are invented sentences, not personal data. |
| A15 Exploratory breaks | FAIL | 10 breaks, 9 caught, 1 survivor that lets the command report success on input it must reject (F01). |

## Must-catch proof (A6)
| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Idempotent | M1a: `Normaliser.__call__` returns one step, with no fixed point (`normalise.py:120`) | `test_FR_0_3_01_idempotent_on_generated_inputs`, `test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point`, `test_FR_0_3_02_documented_example` (7 failed) | Caught |
| 1 Name and version in every row | M1b: rows write `whisper-normalizer-0.1.1` as `normaliser_version` (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 1 Name and version in every row | M1c: rows write the main normaliser's name for both variants (`table.py:93`) | `test_FR_0_3_06_every_row_carries_trace_fields` | Caught |
| 2 S, D and I equal jiwer | M2a: insertion checked before deletion in the traceback (`wer.py:98-101`) | `test_FR_0_3_04_tie_break_follows_documented_rule`, `test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer`, `test_FR_0_3_07_tie_heavy_pairs_match_jiwer` | Caught |
| 2 | M2b: common prefix and suffix step removed (`wer.py:134`, `137`) | `test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs`, `…char_counts…`, `…corpus_totals_and_wer…`, `…tie_heavy_pairs…` | Caught |
| 2 | M2c: diagonal preferred over deletion when both are minimal (`wer.py:98`) | `test_FR_0_3_04_tie_break_follows_documented_rule` and all four `test_FR_0_3_07_*` count tests | Caught |
| 3 Corpus WER = total errors / total reference words | M3a: `corpus_wer` = mean of per-utterance WERs (`wer.py:253`) | `test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words` and 7 more (9 failed) | Caught |
| 3 | M3b: `corpus_wer` divides by hypothesis words (`wer.py:253`) | `test_FR_0_3_05_cli_prints_corpus_and_mean_labelled`, `test_FR_0_3_07_corpus_totals_and_wer_match_jiwer` and 4 more (7 failed) | Caught |
| 4 Empty references follow the rule | M4a: empty-reference words left out of corpus totals (`wer.py:244`) | `test_FR_0_3_04_empty_reference_enters_corpus_totals` and 7 more (9 failed) | Caught |
| 4 | M4b: empty reference gets rate 0.0, not undefined (`wer.py:60`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined`, `test_FR_0_3_04_both_texts_empty` and 8 more (11 failed) | Caught |
| 4 | M4c: an empty reference's hypothesis words not counted as insertions (`wer.py:175`) | `test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined` and 6 more (8 failed) | Caught |
| 4 | M4d: empty-reference rows dropped from the table (`table.py:90`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 5 Main removes fillers, disfluency-aware keeps them | M5a: disfluency-aware variant built with filler removal on (`normalise.py:124`) | `test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler`, `test_FR_0_3_02_documented_example` and 6 more (17 failed) | Caught |
| 5 | M5b: main variant keeps fillers (`normalise.py:123`) | `test_FR_0_3_03_main_removes_each_listed_filler`, `test_FR_0_3_02_documented_example` and 7 more (18 failed) | Caught |
| 6 Every row carries `run_card_id`, `clip_id` and both hashes | M6a: `hyp_sha256` of the normalised text (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |
| 6 | M6b: `ref_sha256` computed from the hypothesis text (`table.py:94`) | `test_FR_0_3_06_hashes_are_sha256_of_raw_text`, `test_FR_0_3_06_accepts_bom_and_multiline_text` | Caught |
| 6 | M6c: rows carry `"0" * 64` instead of the input's `run_card_id` (`score.py:181`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_summary_matches_rows` | Caught |
| 6 | M6d: rows carry a truncated `clip_id` (`table.py:92`) | `test_FR_0_3_06_every_row_carries_trace_fields`, `test_FR_0_3_06_hashes_are_sha256_of_raw_text` | Caught |

As the builder disclosed, the fast word-level cross-check alone does not catch M2a; the character-level and corpus cross-checks and the hand-worked tie case do.

## Exploratory breaks (A15, at most 10)
All 10 are in code new in this WP, chosen by risk: input pairing, fabricated input, alignment edges, rates, file formats and the pinned package.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1 Hypotheses paired with references by file order, not by `clip_id` | `score.py:124` | No: `test_NFR_0_3_01_repeat_runs_give_identical_files` | — |
| X2 A clip missing from the hypothesis file is scored as empty text (reference-only check dropped, `hyps.get(clip_id, "")`) | `score.py:121`, `124` | **Yes.** `177 passed`. With the break, a reference file with `c-1`, `c-2` and a hypothesis file with only `c-1` give exit 0, and `c-2` is scored as 3 deletions against an empty hypothesis. The unmodified code gives `ERROR: the two files must list the same clips; only in …/ref.csv: c-2; …`, exit 2 | MAJOR (F01) |
| X3 Common suffix allowed to overlap the prefix | `wer.py:137` | No: `test_FR_0_3_04_hand_counted_alignments`, `test_FR_0_3_04_errors_equal_edit_distance` and 11 more | — |
| X4 Insertion taken whenever it is on a minimum path | `wer.py:100` | No: `test_FR_0_3_04_tie_break_follows_documented_rule` and all four `test_FR_0_3_07_*` count tests | — |
| X5 Mean per-utterance WER divides by all utterances, including undefined ones | `wer.py:255` | No: `test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled` and 2 more | — |
| X6 CSV floats rounded to 6 decimals | `table.py:115` | No: `test_FR_0_3_06_csv_and_parquet_hold_the_same_rows` | — |
| X7 Package version comparison bypassed | `normalise.py:63` | No: `test_FR_0_3_01_refuses_other_package_version` | — |
| X8 CER characters exclude spaces | `wer.py:75` | No: `test_FR_0_3_04_cer_counts_characters_including_spaces` and 5 more | — |
| X9 Hypothesis always normalised by the main variant | `wer.py:175` | No: `test_FR_0_3_04_reference_empty_after_normalisation` | — |
| X10 One Whisper engine object shared by both variants | `normalise.py:81-90` | No: `test_FR_0_3_03_main_removes_each_listed_filler`, `test_FR_0_3_02_documented_example` and 5 more | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.3-F01 | MAJOR | A15 (outside the must-catch list) | The rule "a missing hypothesis is an error, never an empty text" has no test for the reference-only direction. `SCORE_TABLE.md:109`, the `score.py` header INVARIANTS (`score.py:10`) and CAP-SCORE-005 all state this rule. The only clip-set test, `clip-sets-differ`, puts an extra clip on both sides at once, so it passes as long as either direction is checked. If the reference-only check is lost, the command exits 0 and scores clips that have no hypothesis as all deletions. An incomplete run (for example an adapter that crashed on some clips) would then be reported as successfully scored. The code rejects this input today | X2 above; `score.py:120-124`; `test_aqis_scoring_table.py:167-168`, `190-191` | **Fix now, tests only.** Add two `INPUT_ERRORS` cases: a clip only in the reference file, and a clip only in the hypothesis file. Each must require exit 2, the clip named in stderr, and no output folder. No production change is needed. The re-audit will re-run X2 and its mirror (hypothesis-only check dropped), and each must fail a named test |
| WP-0.3-F02 | MINOR | A13 | An `--out` folder that cannot be created ends in an uncaught traceback with exit 1. The CAP-SCORE-005 header (`score.py:4`) and the plan (`PLAN.md:186`) promise `ERROR:` and exit 2 for any output error. `write_outputs` calls `out.mkdir(...)` outside its `try` (`score.py:154`), and `_refuse_existing` only handles an existing non-folder. Nothing is written, and the failure is loud | `--out <scratch>/afile/sub`, where `afile` is a regular file: `NotADirectoryError: [Errno 20] Not a directory: …/afile/sub`, `exit=1` | **Accept as debt**, target WP-0.6 (the results store takes over writing outputs). A fix is one moved line plus a test |
| WP-0.3-F03 | MINOR | A13 | The version check's wiring has no test. `check_package_version` is tested on its own (4 other versions, a missing package and the pinned version), but nothing tests two things: that the normaliser calls it on first use (`normalise.py:81-82`), and that `score` turns `NormaliserVersionError` or `NormalisationError` into `ERROR:` and exit 2 (`score.py:180-183`, documented at `SCORE_TABLE.md:106`). If the call were removed, another installed `whisper-normalizer` (such as 0.1.15, which rewrites `cause` as `because`) would score silently while rows still say `1+whisper-normalizer-0.1.1`. The risk is limited: the lock is hash-pinned, and `test_FR_0_3_01_installed_package_is_the_pinned_version` and `test_FR_0_0_03_environment_matches_lock` check the installed version in every CI run | `grep` of `tests/aqis_lab/`: no test references `installed_package_version`, `_whisper_english_normaliser`, or a command run with another package version | **Accept as debt**, target WP-0.5 (platform and doctor check installed packages on every platform). A test needs no mock: in a subprocess, put a `whisper_normalizer-0.1.15.dist-info` folder first on `sys.path` and require `NormaliserVersionError` from `normalise` and exit 2 from `score` |

## Convergence (round 3 onwards)
Not applicable: round 1.

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`).
- Approvals used: `docs/approvals/WP-0.3.md` on `main` (`2879cf4`), "Questions 1-7: as recommended in PLAN.md". This covers:
  - D1: Whisper applied until the text settles, so normalisation is idempotent;
  - `whisper-normalizer==0.1.1` as the pinned Whisper normaliser (2a);
  - Whisper's own filler list (3a);
  - D2: typographic apostrophes folded (4a);
  - the lock additions (5) and the CSV input formats (6a);
  - D3: the `schema_version` column, and D4: `summary.json` (7).
- Debt accepted so far: None for WP-0.3.
- Owner-run checks still pending: None. The spec runs this WP on the cloud VM only; WP-0.7 proves identical scores on Colab and Oracle.
- Note, not a WP-0.3 finding: on `main`, the "Values" line of `docs/progress/STATUS.md` lists `MERGED` twice and no longer lists `AUDIT-PASS`. Earlier audits used `AUDIT-PASS` and `AUDIT-FAIL`, and so does this one.
