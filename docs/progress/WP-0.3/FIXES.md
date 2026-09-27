# FIXES — WP-0.3

## Round 2 (audit rounds 1 and 2; approval `docs/approvals/WP-0.3.md` on `main`, `20ba9ba`)
Owner condition: "Round 2: fix WP-0.3-F01 (add asymmetric clip-set input error tests). WP-0.3-F02 and WP-0.3-F03 are accepted as debt in docs/progress/DEBT.md (target WP-0.6 and WP-0.5)."

### WP-0.3-F01 (MAJOR) — no test for a one-sided clip-set mismatch
- **Root cause.** This is a missing test, not a code defect. `read_inputs` in `aqis_lab/commands/score.py` rejects a clip that is only in the reference file and a clip that is only in the hypothesis file (exit 2, no output). The only clip-set test, `test_FR_0_3_06_input_errors_exit_2[clip-sets-differ]`, has a one-sided clip on both sides at once, so it still passes when either check is removed. The auditor's breaks X2 (reference-only check dropped, missing hypothesis read as `""`) and X2m (hypothesis-only check dropped) both survived all 177 WP-0.3 tests.
- **Same gap nearby (surgical-fix step 6).** I listed every `raise InputError` path of `read_records`, `read_inputs` and `_refuse_existing`. These had no test of their own, and all are correct today (exit 2, `ERROR:` naming the file, no output), as checked before the change:
  - the hypothesis file missing (only a missing reference file was tested);
  - a CSV syntax error (`csv.Error`, such as an unterminated quote);
  - an empty file with no header;
  - an invalid `clip_id` in the hypothesis file only (the existing case puts the bad ID in both files, so only the reference check runs);
  - `--out` naming an existing file.

  Two paths are left out on purpose, because they belong to accepted debt: an `--out` folder that cannot be created (F02, WP-0.6) and the normaliser version error (F03, WP-0.5).
- **Change budget.**
  - `tests/aqis_lab/test_aqis_scoring_table.py`: two new test functions appended at the end. Every existing line stays byte-identical, and no existing test changes.
  - `aqis_lab/commands/score.py`: the module docstring only. The CAP-SCORE-005 test list gains the two new tests, and one CHANGE LOG line is added. No code changes.
  - `docs/capabilities/REGISTRY.md`: the CAP-SCORE-005 Tests cell gains the same two tests.
  - Records: this file, `EVIDENCE.md` (appended), `docs/progress/DEBT.md` (two rows appended) and the WP-0.3 row of `STATUS.md`.
- **Capabilities at risk.** None. No production code changes. CAP-SCORE-005's header must still equal its registry row (`test_FR_0_0_08_module_headers_match_registry`).
- **Baseline before the change.** `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "scoring or FR_0_0_08 or FR_0_0_01 or FR_0_2_04_cli_listed" -m "not slow and not network"` gave `196 passed, 989 deselected in 46.49s`.
- **Current behaviour checked first.** Each case was run with the unmodified code: every one exits 2 with `ERROR:` and writes nothing. For example:
  - `ERROR: the two files must list the same clips; only in …/ref2.csv: c-2; only in …/hyp1.csv: none`;
  - `ERROR: …/refq.csv line 2: unexpected end of data`;
  - `ERROR: --out …/afile exists and is not a folder`.
- **Tests added** (`tests/aqis_lab/test_aqis_scoring_table.py`, appended; `diff` of the first 208 lines against the copy taken before the change shows no difference):
  - `test_FR_0_3_06_one_sided_clip_is_an_input_error`, with 3 cases:
    - `clip-only-in-ref`;
    - `clip-only-in-hyp`;
    - `ref-empty-hyp-has-clip`.

    Each requires exit 2, `ERROR:` and empty stdout. Stderr must name the one-sided clip after its own file (`only in <file>: <clip>`) and give `none` for the other file, and there must be no output folder.
  - `test_FR_0_3_06_more_input_and_output_errors_exit_2`, with 5 cases:
    - `hyp-bad-clip-id`;
    - `hyp-missing-file`;
    - `ref-unterminated-quote`;
    - `ref-empty-file`;
    - `out-is-a-file` (the file is left unchanged).

    Each requires exit 2, `ERROR:` naming the file, the expected message and no output.
- **Reproduction and mutation proof.** Each break was made in a copy of the branch under `/tmp/wp03r2`, one at a time; the copy imports its own `aqis_lab` (`/tmp/wp03r2/aqis_lab/commands/score.py`). All scoring tests were run (`-k scoring -m "not slow and not network"`) and the file was restored after each break. X2 and X2m are the auditor's breaks. In X2, X2m, S1, S3, S4 and S5 only the new tests fail, which reproduces F01: the previous suite passed with each of these checks removed. Real output:
```text
== X2 reference-only check dropped, missing hypothesis read as empty text: 1 failed, 183 passed, 1009 deselected in 45.14s
   FAILED test_FR_0_3_06_one_sided_clip_is_an_input_error[clip-only-in-ref]
== X2m hypothesis-only check dropped: 2 failed, 182 passed, 1009 deselected in 44.65s
   FAILED test_FR_0_3_06_one_sided_clip_is_an_input_error[clip-only-in-hyp]
   FAILED test_FR_0_3_06_one_sided_clip_is_an_input_error[ref-empty-hyp-has-clip]
== S1 clip_id not checked in the hypothesis file: 1 failed, 183 passed, 1009 deselected in 44.69s
   FAILED test_FR_0_3_06_more_input_and_output_errors_exit_2[hyp-bad-clip-id]
== S2 missing file not caught: 2 failed, 182 passed, 1009 deselected in 45.10s
   FAILED test_FR_0_3_06_input_errors_exit_2[missing-ref-file]
   FAILED test_FR_0_3_06_more_input_and_output_errors_exit_2[hyp-missing-file]
== S3 CSV syntax error not caught: 1 failed, 183 passed, 1009 deselected in 45.06s
   FAILED test_FR_0_3_06_more_input_and_output_errors_exit_2[ref-unterminated-quote]
== S4 empty file accepted as having a header: 1 failed, 183 passed, 1009 deselected in 45.12s
   FAILED test_FR_0_3_06_more_input_and_output_errors_exit_2[ref-empty-file]
== S5 --out naming a file not refused: 1 failed, 183 passed, 1009 deselected in 46.30s
   FAILED test_FR_0_3_06_more_input_and_output_errors_exit_2[out-is-a-file]
```
  The breaks, all in `aqis_lab/commands/score.py`:
  - **X2:** `if only_ref or only_hyp:` → `if only_hyp:`, and `hyps[clip_id]` → `hyps.get(clip_id, "")`.
  - **X2m:** → `if only_ref:`.
  - **S1:** the `clip_id` check only for column 0.
  - **S2:** `except OSError` → `except PermissionError` when reading a file.
  - **S3:** `except csv.Error` → `except UnicodeError`.
  - **S4:** `if first != header:` → `if first is not None and first != header:`.
  - **S5:** the `--out` not-a-folder check → `if False:`.
- **Verification after the change.**
  - Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` gave `1182 passed, 11 deselected in 108.09s (0:01:48)` (1174 before, plus the 8 new cases).
  - Gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.3` gave `Findings: 0` / `0 findings: OK (0.3 s)`.
  - `git diff -U0 aqis_lab/` shows only the `score.py` docstring (the CAP-SCORE-005 test list and one CHANGE LOG line).
- **Registry and header.** The CAP-SCORE-005 Tests cell and the `score.py` header both list the two new tests (`test_FR_0_0_08_module_headers_match_registry` passes in the fast suite).
- **Status:** fixed (tests only; no production code changed).

### WP-0.3-F02 and WP-0.3-F03 (MINOR) — accepted as debt
Recorded in `docs/progress/DEBT.md`, as the owner's round 2 condition says:
- **DEBT-008** (F02, target WP-0.6): an `--out` folder that cannot be created gives a traceback and exit 1.
- **DEBT-009** (F03, target WP-0.5): the wiring of the normaliser version check has no test.

No code was changed for either.
