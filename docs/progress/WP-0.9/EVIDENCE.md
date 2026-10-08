# EVIDENCE — WP-0.9 Phase 0 review

Environment: cloud VM (Ubuntu 24.04, x86_64), `.venv` Python 3.13.14 (`docs/environment/colab_probe.txt`: 3.13.15, same major.minor), lock `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`, branch `claude/great-heisenberg-h85gm9`. Approval: `docs/approvals/WP-0.9.md` on `main` (`0ce38e1`, corrected for BLK-017 in `699acd5`).

**Status:** every requirement is done. The owner ran `/phase-audit 0` on this branch (approval Q1): verdict PASS at `079571e` (`docs/progress/PHASE-0-AUDIT.md`), with 4 MINOR findings handled under "Phase audit findings". Next in the approved order: `/wp-audit WP-0.9`.

## Baseline before any change
- At planning (`254c1e3`, then a shallow clone): `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` gave `1 failed, 1855 passed, 55 deselected in 285.26s`. The failure was `test_FR_0_0_12_asset_pins_match_repository`: `git cat-file` cannot find the pinned corpus commit in a shallow clone (`git rev-parse --is-shallow-repository` → `true`). After `git fetch --unshallow origin`: `1 passed, 63 deselected in 3.28s`. So the baseline is green with full history (`docs/progress/WP-0.9/PLAN.md`, finding 9).
- Before each change to an existing file, its tests were run green (gate tests `167 passed` with only the new WP-0.9 tests failing; contracts `758 passed`; Tier 2 baseline `46 passed`; WP-0.8 documents `64 passed` and `32 passed`; CI tests `8 passed`).

## Build order
The debt work was built before the memo, because the memo's open issues and must-catch 2 depend on the final state of `docs/progress/DEBT.md`. Each item was test-first; the first failing runs are quoted under each item.

## Requirements

### FR-0.9-01 — Phase 0 memo: exit criteria with evidence, decisions, open issues, lessons
- Memo: `docs/progress/PHASE0_MEMO.md` (CAP-DOC-019). Checks: `tests/aqis_lab/aqis_memo_testutil.py`.
- Tests (`tests/aqis_lab/test_aqis_phase0_memo.py`): `test_FR_0_9_01_memo_has_every_section`, `test_FR_0_9_01_exit_criteria_link_evidence_that_exists` (must-catch 1), `test_FR_0_9_01_evidence_check_reports_each_broken_link` (6 breaks: renamed path, unknown test, unknown commit, a row without links, a missing row, a changed criterion), `test_FR_0_9_01_decisions_quote_their_approval_files`, `test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker`, `test_FR_0_9_01_audit_round_counts_and_lessons_cite_records`, `test_FR_0_9_01_no_open_debt_row_targets_phase_0` (must-catch 2, CAP-DOC-020), `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows` (3 breaks), `test_FR_0_9_01_memo_passes_every_check`.
- How the checks work, with every expected value read from the repository, never from the memo:
  - **Exit criteria:** each of E1 to E6 must appear once, in the overview's own words (parsed from `docs/specs/phase-0/00-PHASE-0-OVERVIEW.md`), with a status from MET, MET with note or NOT MET. A status other than MET needs a note. Every backticked link in the Evidence cell must resolve:
    - a path must exist;
    - a `test_…` name must be in `pytest --collect-only` of `tests/aqis_lab`;
    - a commit must pass `git cat-file -e`;
    - a URL must be a run or pull request of this repository.

    Each cell needs at least one path or test, so a URL alone is not enough.
  - **Decisions:** each quote must appear word for word (whitespace aside) in the one approval file it names.
  - **Open issues:** every OPEN row of `DEBT.md` and every OPEN blocker must be named, and no CLOSED row may be listed as open (permanent limits are listed as such).
  - **Lessons:** each numbered lesson must cite an existing record, and the audit-round table must equal the round in each `AUDIT.md` header (9, 4, 3, 3, 2, 3, 2, 2, 3).
- Test first: `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py -q -p no:cacheprovider` before the memo existed: `5 passed, 15 errors in 0.73s` (the 15 errors: `FileNotFoundError` for `docs/progress/PHASE0_MEMO.md`; the 5 that passed read only DEBT.md and the unit log, which were already done). With the memo, before this file existed: `2 failed, 18 passed`, both failures `lesson "8. ...es not exist` (lesson 8 cites this file).
- The memo's statuses: E1 MET, E2 MET with note (the Colab check is a clean stop plus runtime deletion, accepted by the owner, Q9), E3 MET, E4 MET, E5 MET with note (no owner recordings in phase 0, owner decision in `docs/approvals/WP-0.4.md`), E6 MET with note (deviation D1).
- Command and output: see "Final runs" below.
- Status: DONE

### FR-0.9-02 — Phase 1 prerequisites
- Memo section "Phase 1 prerequisites" with three subsections:
  - **Campaign A recruiting status:** the owner's statement quoted from the approval (Q4): "Campaign A: not started: 0 of 22 recruited, 0 consents signed, 0 sessions recorded, quiet/noise split 0/0."
  - **Pack v1 plan:** as the owner defined it (Q6), only what the sources fix, each bullet citing `[Build Plan § …]` or a committed file, then five `[OWNER DECIDES: …]` items.
  - **Colab compute units used so far:** totals per runtime from `docs/progress/WP-0.9/OC-0.9-01_units.csv`: cpu 1 session, 0.0021 h, 0.0002 units; Tesla T4 1 session, 0.0363 h, 0.0432 units; total 2 sessions, 0.0384 h, 0.0434 units. These are given with the owner's quoted budget ("50 Colab units a month (Google AI Plus), planned use 40 of them") and the two unmetered sessions the owner named (BLK-017).
- Tests: `test_FR_0_9_02_unit_log_copy_is_consistent` recomputes each row's hours from its start and end, and its estimate from the rate in `config/aqis_lab/colab_rates.yaml`, exactly with fractions and rounded half-even to 4 places. Both rows agree: 130.650096 s → 0.0363 h, × 1.19 → 0.0432. `test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources` checks:
  - each quote is in the approval;
  - each pack bullet cites a real Build Plan heading or an existing file, or is an owner decision;
  - every quoted Build Plan passage is in the Build Plan;
  - the units table equals the unit log's exact totals;
  - breaks: a changed total and an uncited pack bullet are both reported.
- Status: DONE

### FR-0.9-03 — `/phase-audit 0`; the memo links its report
- The memo's "Phase audit" section links `docs/progress/PHASE-0-AUDIT.md`, and today states `Verdict: pending (/phase-audit 0 has not run yet)`.
- Tests: `test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict` and `test_FR_0_9_03_phase_audit_check_follows_the_approved_order`. The approved order runs the phase audit on this branch while WP-0.9 is IN-BUILD, and the phase audit runs the whole suite. So the check cannot demand the report before the audit has written it:
  - while WP-0.9's STATUS is PLANNED, APPROVED or IN-BUILD and no report exists, the memo must state exactly that the audit is pending;
  - once the report exists, the memo must state its verdict and audited commit, and that commit must be an ancestor of `HEAD`;
  - from READY-FOR-AUDIT on, a missing report is a failure.

  The second test checks all four states on a copy of the records.
- Result: the owner ran `/phase-audit 0`; the report `docs/progress/PHASE-0-AUDIT.md` (commit `5e2bf2e`) has `## Verdict: PASS` and "Commit audited: `079571e147527f395782611d3f6cca9bd7c7f4a3`". The memo's "Phase audit" section now links it with `Verdict: PASS` and that commit, and summarises the four findings.
- Test first: with the report present and the memo still pending, `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py -q -p no:cacheprovider` gave `1 failed, 19 passed`, with `'docs/progress/PHASE-0-AUDIT.md exists, but the memo still says the audit is pending'`. After the memo update: `20 passed in 21.02s`.
- Status: DONE

### AT-0.9-01 — `/phase-audit 0` returns PASS
- Run by the owner (only the owner can start it): PASS, `CRITICAL: 0 · MAJOR: 0 · MINOR: 4 (open 4; none blocks)` at `079571e` (`docs/progress/PHASE-0-AUDIT.md`). As the report summarises: a fresh full clone of this branch, the full lab suite `1971 passed`, the smoke command in 155.6 s and identical to the three committed bundles, five random rows traced, a run card re-run byte-identical, and the harness regression unchanged.

## Debt closed
Every row below was OPEN with target WP-0.9; dispositions follow `docs/approvals/WP-0.9.md` (Q2, Q3, Q5, Q7, Q8). New tests are in `tests/aqis_lab/test_aqis_debt_wp09.py` unless named otherwise. Every break was made alone in a throwaway clone (`/tmp/wp09-breaks`, a `git clone` of this branch with `.venv` linked), run with `.venv/bin/python -m pytest <file> -q -p no:cacheprovider -k <tests>`, and reverted with `git checkout`; the clone was clean after each batch ("clone clean afterwards").

### DEBT-001 to DEBT-005 (WP-0.0 gate, regression check, provisioning, bootstrap)
- **DEBT-001** `test_FR_0_0_06_parity_lowercase_readme_approval_approves_nothing` (`readme.md`, `ReadMe.md`): the hook and the gate both report `("A2", "vad_adapters/example.py", "M")`.
- **DEBT-002** G37 `test_FR_0_0_09_two_specs_for_one_wp_is_a_finding`; G40 `test_FR_0_0_09_only_lab_test_names_count`; G33 `test_FR_0_0_08_registry_module_that_is_a_folder_is_a_finding`; G63 `test_FR_0_0_08_registry_row_without_capability_id_is_malformed`.
- **DEBT-003** G44 `test_FR_0_0_07_exempted_files_list_only_scanned_files`; P32 `test_FR_0_0_12_fetches_pinned_corpus_commit_missing_from_shallow_clone` (a `--depth 1` clone over `file://` of a local tree, no network; the pinned commit is absent before and present after); R15 `test_FR_0_0_11_testcase_without_name_is_an_input_error` (3 cases, exact stderr); B16 `test_FR_0_0_02_probe_repeating_one_version_is_accepted`.
- **DEBT-005** K7.7 `test_FR_0_0_06_fails_closed_on_unparsable_lab_test_file`; K10.6 `test_FR_0_0_09_traces_every_id_on_a_spec_line`; K11.5a `test_FR_0_0_02_recreates_venv_built_on_another_python` (a real `.venv` on `/usr/bin/python3.12` with an empty lock, offline: `Recreating .venv (found Python 3.12, need 3.13)`); K14.12 `test_FR_0_0_12_no_complete_marker_after_failed_extraction` (an archive member whose parent is a file stops extraction for real); X4 in the probe of `test_FR_0_0_09_index_follows_pytest_collection_rules`; X8 `test_FR_0_0_12_blank_line_before_import_report`. K11.5b: closed as a recorded permanent limit (owner, Q5), no test.
- **DEBT-004** `tools/audit/gate.py`:
  - **Change:** `test_functions` now follows pytest 9.1's collection rules. It uses new helpers, which are named differently from the plan's examples: `_pytest_skips`, `_ignores_for`, `_conftest_ignores`, `_in_virtualenv`, `_parse_python`, `_final_bindings`, `_bound_names`, `_defs_pytest_keeps`, `_literal_test_value`, `_class_test_flag`, `_metaclass`, `_is_abcmeta`, `_abstract_names` and `_is_collected_class`. `_collect_class` and `_sets_test_false` were rewritten; the test-file error messages are unchanged.
  - **Rules now modelled:**
    - default `norecursedirs`, `__pycache__` and virtual environments;
    - the nearest conftest's literal `collect_ignore` and `collect_ignore_glob` (a non-literal list is exit 2);
    - false or unreadable `__test__` values, own or inherited;
    - abstract classes; a class with an unknown metaclass is not counted;
    - names rebound after their def, including conditionally;
    - a def before a star import is not counted.
  - **Tests:**
    - `test_FR_0_0_09_index_follows_pytest_collection_rules` has pinned pytest collect a probe with one case per rule (an independent oracle). Pytest collects the 9 expected names plus 2 that the gate deliberately does not count (unknown metaclass, def before a star import, documented as stricter). The gate must then report exactly the 32 names pytest does not collect, plus those 2.
    - `test_FR_0_0_09_index_counts_every_collected_probe_test` checks that the gate counts all 9 collected names.
    - `test_FR_0_0_09_non_literal_collect_ignore_is_an_error` covers 4 forms, each exit 2 with `cannot tell which files pytest collects`.
  - **Docs:** `docs/tools/AUDIT_GATE.md` states the rules and what is still not read (conftest collection hooks, plugins, ini options; the repository uses none).
- Test first: `6 failed, 17 passed in 4.87s`. The 6 failures were the two DEBT-004 index tests (the gate counted 30 names pytest does not collect and missed `test_in_module_switched_back_on`) and the 4 non-literal cases (no exit 2). The 17 that passed protect behaviour that already existed; the breaks below show each fails when broken.
- Breaks (all caught):

```text
D001 readme case: CAUGHT: 2 failed, 21 deselected
D002 G37 one spec / G40 lab tests only / G33 module file / G63 capability id: CAUGHT (1 failed each)
D003 G44 scan scope / P32 fetch / B16 dedupe: CAUGHT (1 failed each); R15 nameless testcase: CAUGHT: 3 failed
D005 K7.7 unparsable / K10.6 every id / K11.5a reuse guard / K14.12 marker order / X8 blank line: CAUGHT (1 failed each)
D005 X4 object base: CAUGHT: 2 failed
D004 norecursedirs / virtualenv / __pycache__ / collect_ignore / collect_ignore_glob: CAUGHT (1 failed each)
D004 nearest conftest: CAUGHT: 2 failed; non-literal ignore: CAUGHT: 4 failed
D004 false __test__ values / inherited __test__ / abstract classes / unknown metaclass / rebound names /
     star import / conditional rebinding / call-form fixture: CAUGHT (1 failed each)
clone clean afterwards
```

  Failure reasons checked one by one for the fastest runs:
  - P32: `[PASS] platform … assert 1 == 0`, the corpus step fails without the fetch;
  - B16: the probe line is missing because the conflict error comes first;
  - K11.5a: the final guard stops the reused 3.12 `.venv`;
  - K14.12: `assert [PosixPath('/…/.complete')] == []`.

  An unbroken control run in the clone: `23 passed`.

### DEBT-006, DEBT-007 (contracts validate)
- **DEBT-006:**
  - **Test:** `test_FR_0_2_04_cli_worker_start_failure_exits_2_with_rerun_hint` runs `python -m aqis_lab contracts validate <6,000-record file> --kind event --workers 2` with `RLIMIT_NPROC` 1, as uid 65534 when root, with a control run without the limit. It requires exit 2, one `ERROR: cannot run 2 worker processes: …; rerun with --workers 1` line and no traceback. A real OS limit, not a test double.
  - **Planning probe output:** `ERROR: cannot run 2 worker processes: [Errno 11] Resource temporarily unavailable; rerun with --workers 1`.
  - **Test first:** the behaviour already existed, so the test passed at once. Breaks prove it.
  - **Code:** none changed; the plan's conditional change to `validate_event_lines` was not needed. CI runs as a non-root user, and its result on CI is under "CI".
- **DEBT-007:**
  - **Change:** `_one_per_pointer` in `aqis_lab/contracts/validate.py` merges errors that share a pointer, joining the distinct messages with `; `. It is used in `_validate` and `validate_event_lines`.
  - **Result:** fixture line 26 now reads `line 26: INVALID /clip_id: 7 is not of type 'string', 'null'; 7 is not of type 'string'. Rule: this event type belongs to a clip; clip_id must name it.`
  - **Tests:** `test_FR_0_2_04_one_report_line_per_failing_field` (CLI and `validate_event_lines`) and `test_FR_0_2_04_validator_api_gives_one_error_per_field`.
  - **Test first:** `AssertionError: (26, ['/clip_id', '/clip_id'])`.
  - **Gap found and closed:** the first break run showed `D007 duplicates kept in _validate: SURVIVED`, because the merge in `validate_event_lines` masked it. The validator-API test was added for that path.
- Breaks (final run):

```text
D006 pool error becomes traceback: CAUGHT: 1 failed, 25 deselected in 1.60s
D006 rerun hint dropped: CAUGHT: 1 failed, 25 deselected in 1.53s
D007 duplicates kept in _validate: CAUGHT: 1 failed, 1 passed, 24 deselected in 0.40s
D007 merge drops a message: CAUGHT: 2 failed, 24 deselected in 0.43s
clone clean afterwards
```

### DEBT-009, DEBT-016 (owner's ruling, Q5)
Both are closed as recorded permanent limits with no code change.
- DEBT-009: the evidence is the planning search of about 5,000 structured inputs, which reached at most 4 normaliser passes (`'oh % oh 1/2'`) against `MAX_PASSES = 10`.
- DEBT-016: the report-name format is FR-0.5-02's.

### DEBT-019 (network-only tests in CI)
- **Change:** a new job `lab-network` in `.github/workflows/aqis-lab-ci.yml` (CAP-CI-003). It uses the same checkout, uv and bootstrap as `lab`, then runs `.venv/bin/python -m pytest tests/aqis_lab -q -m "network and not slow and not gpu and not colab and not oracle"`. Its permissions are read-only, inherited from the workflow.
- **Existing test changed:** `tests/aqis_lab/test_aqis_ci.py` widens one job-set assertion to include `lab-network` (`ALLOW-EDIT`). Its other assertions, including the check that only `aqis-lab-ci.yml` exists, are unchanged.
- **Test:** `test_FR_0_0_10_ci_runs_network_only_tests` checks the job. Using pytest's own collection, it also checks that the network-only and fast suites together equal every test without another lab marker, and do not overlap. That is 12 network-only tests today.
- **Test first:** `KeyError: 'lab-network'`.
- **Breaks:** `D019 network job removed: CAUGHT`, `D019 network job also runs slow tests: CAUGHT`.

### DEBT-022, DEBT-023, DEBT-024, DEBT-025, DEBT-026 (WP-0.8 documents)
- **DEBT-022:**
  - **Tests:** `test_FR_0_8_05_option_ids_only_in_option_column_and_decision_block` and `test_FR_0_8_05_option_id_check_detects_a_choice_in_other_words`. The latter has three breaks: "The lab will work to HR-B." in prose, an ID in a trade-off cell, and an ID in a heading.
  - **Test first:** the committed document failed on lines 31, 70 and 71, as found at planning.
  - **Document change:** those three cells now name the value: "than under the 1 % option" and "of the 10 % option" (twice).
  - **Breaks:** rewording undone, CAUGHT (3 failed); a choice added in prose, CAUGHT (4 failed).
- **DEBT-023:**
  - **Change:** a `Tone` column in `docs/fillers/FILLER_LIBRARY_v0.md`. Level 2 rows get the tone their "Intended use" already states (negative: fil-011, fil-013, fil-015; positive: fil-012, fil-014); other rows get `n/a`. The change script asserted each Level 2 row's use text before writing its tone.
  - **Test:** `test_FR_0_8_04_level_2_tone_is_explicit_and_rule_1_keys_on_it`.
  - **Test first:** no Tone column.
  - **Breaks:** a positive filler loses `ctx-complaint`, CAUGHT; a tone mislabelled, CAUGHT.
  - **Existing tests:** the WP-0.8 filler, targets and debt tests stay green (`32 passed`).
- **DEBT-024:** closed by the owner's wording review, `docs/progress/WP-0.8/OC-0.8-02_wording_review.txt` (Q7). No change.
- **DEBT-025:** moved to WP-4.5 (Q8). The memo records harm rate as the rate only (below 2 %).
- **DEBT-026:**
  - **Change:** `OWNER_FACT_BREAKS` in `tests/aqis_lab/test_aqis_recording_docs.py` gains `Y1-pre-ticked-expected-box` and `Y4-signature-line-addition` (`ALLOW-EDIT`); nothing else in the file changed (`git diff --stat`: `6 +`).
  - **Breaks:** box state ignored → `[Y1-pre-ticked-expected-box]` fails; fill-in lines matched by prefix → `[Y4-signature-line-addition]` fails.
  - **Record fix:** the row's out-of-date "Accepted in" cell now cites the WP-0.8 approval line.

### DEBT-028 to DEBT-031 (Tier 2 baseline)
- **DEBT-028:** the owner moved the line into `[NEVER]` on `main` (Q3, `0ce38e1`).
  - **Test:** `test_FR_0_1_03_raw_baseline_files_are_never_editable` asks the hooks' `_protected.py` (run without writing bytecode into `.claude/`) and the gate's `classify` about every raw file, and both say `NEVER`. SUMMARY.md stays `None`.
  - **Break:** the old policy file (the line under `[LAB-OWNED]`) is CAUGHT.
- **DEBT-029:**
  - **SUMMARY.md change:** the Conditions table gets the column "Clips in the manifest (warm-up included)". Its cells are cited to S360 to S369, derived rows over `raw/run.log` with locator `{"where": {"operating_point": "ten_vad", "category": …}, "op": "count"}`. The counts are clean speech 34 (29 scored + 5 warm-up), the other nine categories equal to their scored counts, 229 in total.
  - **Helper change** (`tests/aqis_lab/aqis_baseline_testutil.py`, `ALLOW-EDIT`): `run_log_clips` reads one record per operating point and clip (a repeated line counts once; conflicting details are an error). `resolve_sources` accepts derived rows over the run log, and `binding_problems` binds the new column to its own category.
  - **Tests:** `test_FR_0_1_02_conditions_show_clips_in_the_manifest_per_category` recomputes every count from the log with its own regular expression, and checks that scored plus warm-up equals the manifest count and that the counts add up to the manifest total. `test_FR_0_1_02_run_log_clip_count_counts_each_clip_once` covers the de-duplication, and a new `manifest-count-category` case covers the binding.
  - **Gap found and closed:** the first break run showed `D029 run-log clip listed twice counts twice: SURVIVED` (the real log repeats no clip); the de-duplication test was added for it.
- **DEBT-030:**
  - **Change:** `body_text` tracks the table each line belongs to. It exempts only the Sources table headed `ID`, and only the Bytes and SHA-256 cells of the Raw inventory table headed `Item`.
  - **Tests:** new cases `sources-second-table` (X4), `inventory-second-table` (X4-inv) and `inventory-second-table-same-columns`.
  - **Test first:** the first two failed before the change.
  - **Gap found and closed:** the first break run showed `D030 inventory exemption covers every table: SURVIVED`, because the X4-inv table uses other column names. The same-columns case was added for it.
- **DEBT-031:**
  - **Isolating cases:** H1 `report-row-binding` swaps only the citations of two WebRTC rows whose version text is equal; H4 `extra-citation` adds a same-value citation of another row; H5 `expr-operand-binding` replaces S140's second operand by another row's Source with the same value 435, found at run time.
  - **New test:** `test_FR_0_1_02_check_reports_missing_or_repeated_rows` covers H3 with a repeated headline row. It also covers the new one-row-per-category check (`binding_problems`) with a category row removed with its Sources, and a category row repeated.
  - **Where the cases live:** H3 and the category cases are in this new sibling test, not in `test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column` as the debt row suggested. That test's assertion requires a "cites … row/column" message, and the row-set checks report "expected one per …". Adding them there would have meant changing an existing assertion.
- Breaks:

```text
D028 old policy (raw line under LAB-OWNED): CAUGHT
D029 manifest column binding dropped: CAUGHT
D029 run-log clip listed twice counts twice: SURVIVED (first run) → CAUGHT after adding test_FR_0_1_02_run_log_clip_count_counts_each_clip_once
D030 Sources exemption covers every table: CAUGHT
D030 inventory exemption covers every table: SURVIVED (first run) → CAUGHT after adding inventory-second-table-same-columns
D031 H1 _report row check / H3 one row per operating point / H4 extra citation / H5 expr operands: CAUGHT
D031 category completeness: CAUGHT: 2 failed
clone clean afterwards
```

### Kit-patch leftovers (Q10)
`aqis-kit-patch-2.zip` and `aqis-kit-patch-3/` (18 tracked files) were removed in their own commit. No code or test referred to them; only historical progress records mention them.

## Must-catch proof
1. **Each exit criterion E1 to E6 links to evidence that exists.** Breaks in the clone:
   - linked evidence moved away (`docs/progress/WP-0.5/OC-0.5-02_runner.log`): `test_FR_0_9_01_exit_criteria_link_evidence_that_exists` fails with `E2: path docs/progress/WP-0.5/OC-0.5-02_runner.log does not exist`;
   - E4's evidence replaced by plain words: the same test fails;
   - the checker loosened to accept missing paths, uncollected tests, rows without links or a missing criterion: each fails its `test_FR_0_9_01_evidence_check_reports_each_broken_link[…]` case.

   My first definition of the "file removed" break changed the file's content instead of moving it, and survived. The break was redone by moving the file, as above.
2. **Every open phase 0 debt row is closed or moved with the owner's approval.** Breaks in the clone:
   - DEBT-001 set back to OPEN: `test_FR_0_9_01_no_open_debt_row_targets_phase_0` fails;
   - DEBT-025's move citing an approval that does not name it: that test and `…debt_check_reports_open_or_unapproved_rows[moved-without-approval]` fail;
   - the checker loosened to ignore open phase 0 rows, or the move approval: the matching break cases fail.

```text
MC1 evidence row links nothing: CAUGHT
MC1 checker accepts missing paths / unknown tests / a row without links / a missing criterion: CAUGHT (1 failed each)
MC2 a phase 0 debt row left open: CAUGHT
MC2 a moved row without the owner's approval: CAUGHT: 2 failed
MC2 checker ignores open phase 0 rows / ignores the move approval: CAUGHT
clone clean afterwards
```

## Incidents during the build
- **Unrelated runner test failure during an early fast-suite run:** `test_FR_0_5_05_shard_size_is_configurable` failed once (`1 failed, 1878 passed`). Its two runs compare `results.jsonl` bytes, and byte 88 of a row is the first character of `run_card_id`. A run card records the git commit and dirty flag, and I committed in the middle of that suite run. Run alone three times on a stable tree it passed (`1 passed` each). The final runs were made on a clean, unchanging tree.
- **Registry row inconsistent with its module header:** I first added two DEBT-006/007 tests to registry row CAP-CONTRACTS-006 without its module's header listing them. `test_FR_0_0_08_module_headers_match_registry` caught it. The row was put back byte-identical to `main`; the tests stay listed under CAP-CONTRACTS-001 and CAP-CONTRACTS-007, whose headers list them.

## Final runs
All at `8365189` on a clean tree (`git status --porcelain` empty), full history:

```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9"
20 passed, 1958 deselected in 10.75s

$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp09.py -q -p no:cacheprovider
33 passed in 10.21s

$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"
1923 passed, 55 deselected in 295.22s (0:04:55)
```

Network-only suite (the new CI job's selection), run locally at `882ac4c`, whose code and tests are the same as `8365189`'s: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "network and not slow and not gpu and not colab and not oracle"` → `12 passed, 1966 deselected in 82.18s`.

After the phase audit, at `37b2b5a` (memo linked, findings handled) on a clean tree:

```text
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.9
aqis-audit-gate: base origin/main (merge-base 699acd501838), head 37b2b5a0b57e, approvals origin/main 699acd501838, wp WP-0.9
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (1.2 s)

$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"
1923 passed, 55 deselected in 286.81s (0:04:46)
```

CI on `37b2b5a`: [run 382](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37763724325), all three jobs success: `lab` (Fast lab test suite and Audit gate success), `lab-network` (step "Lab tests marked only network (WP-0.9 DEBT-019)" success) and `harness-regression` (Regression check against the provisioned baseline success). The commit that adds this paragraph and sets STATUS to READY-FOR-AUDIT changes only this file and `docs/progress/STATUS.md`; its CI is in the pull request.

## Acceptance commands
- AT-0.9-01 (`/phase-audit 0` returns PASS): PASS (`docs/progress/PHASE-0-AUDIT.md`, "## Verdict: PASS"). The spec has no other acceptance command.

## Audit gate
```text
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.9
aqis-audit-gate: base origin/main (merge-base 699acd501838), head 8365189746a3, approvals origin/main 699acd501838, wp WP-0.9
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.7 s)
```
The four edited existing test files are each covered by an `ALLOW-EDIT` line in the approval. No NEVER or GUARDED path changed: the deleted `aqis-kit-patch-3/.claude/…` files are copies inside the leftover folder, not the project's `.claude/`.

## CI
- `8365189`: [run 379](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37143595686), all three jobs success: `lab` (fast suite and gate), `lab-network` (the new job; step "Lab tests marked only network (WP-0.9 DEBT-019)" success) and `harness-regression` (regression check success).
- Red runs on this branch, all explained (corrected for phase audit finding PH0-F1, which found runs 375 and 376 missing from this list):
  - [run 375](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37141915556) (`7d59019`), [run 376](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37142130245) (`4760f58`) and [run 377](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37142549275) (`18283bf`, `1 failed, 1900 passed`) failed in "Fast lab test suite" on `test_FR_0_0_08_module_headers_match_registry`: the CAP-CONTRACTS-006 mismatch under "Incidents", introduced in `4f91f72` and fixed in `8365189`. The auditor reproduced the failure at `7d59019` and `4760f58` (`1 failed` each).
  - [run 378](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37143036198) (`882ac4c`) failed on that test and on the two memo tests that needed this file.
  - [run 381](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37186012354) (`5e2bf2e`, the phase audit report) failed by design on `test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict`, because the report existed and the memo still said pending; the auditor confirmed it was the only failure (`1 failed, 1922 passed`).
- Green: [run 380](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37143974245) on `079571e`, the commit the phase audit audited.
- This EVIDENCE update only adds text; CI on it is in the pull request.

## Owner-run checks
| Check | Where | Command | Expected output | Result report |
| --- | --- | --- | --- | --- |
| AT-0.9-01 phase audit | A Claude Code session on branch `claude/great-heisenberg-h85gm9` (the updated skill clones the current branch) | `/phase-audit 0` | `docs/progress/PHASE-0-AUDIT.md` with `## Verdict: PASS` and its audited commit; E6 covers WP-0.0 to WP-0.8 (D1) | Done: PASS at `079571e` (`5e2bf2e`) |
| OC-0.9-01 unit log copy | Drive | Committed by the owner | `docs/progress/WP-0.9/OC-0.9-01_units.csv` | Done (`0ce38e1`; BLK-017 answer `699acd5`) |

No WP-0.9 code runs only on Colab or Oracle. The DEBT-006 test runs as uid 65534 when root (cloud VM, Colab) and as the runner user on CI, where run 379 passed.

## audit-allow lines
None.

## Phase audit findings
From `docs/progress/PHASE-0-AUDIT.md`, all MINOR; handled as the owner instructed in the session chat (2026-10-08):
- **PH0-F1** (fixed, record only): the CI section above now lists runs 375 and 376 as well, both checked through the GitHub API (conclusion `failure`, heads `7d59019` and `4760f58`).
- **PH0-F2** (fixed, record only): the memo's Open issues names the missing OC-0.5-01 report (`docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt` was never committed) and points to OC-0.7-01 (`docs/progress/WP-0.7/OC-0.7-01_colab.txt`, `pytest -m 'colab or gpu'` 5 passed at `7c27dd5`, including the same three tests on a T4 runtime) and to the committed doctor report.
- **PH0-F3** (accepted as debt): DEBT-032, target WP-1.0. Commit the full `bash aqis_lab/deploy/dev_bootstrap.sh --gpu` output on a Colab GPU runtime.
- **PH0-F4** (accepted as debt): DEBT-033, target WP-1.0. One sentence in `docs/adapters/PARAKEET_UNIFIED.md` naming `requirements/aqis_lab/phase0-gpu.in`.

The protocol lets the builder record MINOR findings in `DEBT.md` without an approval line, so the "Accepted in" cells of DEBT-032 and DEBT-033 cite the owner's chat instruction. The must-catch 2 check (`test_FR_0_9_01_no_open_debt_row_targets_phase_0`) stays clean: their target, WP-1.0, is not a phase 0 WP. The memo's Open issues names both rows, which `test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker` requires.

## Deviations from the plan
Recorded for audit finding WP-0.9-F06 (round 2; the owner chose "record only" in the session chat, 2026-10-08).

**(a) The open-issues test does not compare with pending owner-run checks.** The plan ("Memo layout", item 4) says the Open issues list holds every OPEN debt row, every pending owner-run check, finding 5 if not fixed, the kit-patch leftovers and any phase audit finding accepted as debt, and that "a test compares this list with `DEBT.md` and the WP evidence files". It names `test_FR_0_9_01_open_issues_list_every_open_debt_and_pending_check`. The built test is `test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker`. Through `open_issue_problems`, it checks three things against `DEBT.md` and `docs/progress/BLOCKERS.md`:
- every OPEN debt row is named;
- no CLOSED row is listed as open;
- every OPEN blocker is named.

It does not read the "Owner-run checks" tables of the WP evidence files, so a pending owner-run check missing from the memo would not be reported. The memo's current list is right: the pending WP-0.8 items are carried by DEBT-032 (OPEN, so the test requires it), and the OC-0.5-01 gap is named (PH0-F2).

**(b) The planned test names were merged into fewer tests.** The Requirements table of `PLAN.md` names 16 FR-0.9 tests (FR-0.9-01: 10, FR-0.9-02: 5, FR-0.9-03: 1). Round 1 built 13; the audit counted 15 planned. Each planned check is in a built test:

| Planned test | Built test (round 1) |
| --- | --- |
| `test_FR_0_9_01_memo_has_every_section` | same name |
| `test_FR_0_9_01_exit_criteria_are_the_overview_six_verbatim` | `test_FR_0_9_01_exit_criteria_link_evidence_that_exists` (`exit_criteria_problems` compares each criterion with the overview's words); break "a changed criterion" in `test_FR_0_9_01_evidence_check_reports_each_broken_link` |
| `test_FR_0_9_01_every_evidence_link_exists` | `test_FR_0_9_01_exit_criteria_link_evidence_that_exists` |
| `test_FR_0_9_01_evidence_check_reports_each_broken_link` | same name |
| `test_FR_0_9_01_decisions_quote_their_approval_files` | same name |
| `test_FR_0_9_01_open_issues_list_every_open_debt_and_pending_check` | `test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker` (narrower, see (a)) |
| `test_FR_0_9_01_audit_round_counts_equal_each_audit_report` | `test_FR_0_9_01_audit_round_counts_and_lessons_cite_records` |
| `test_FR_0_9_01_lessons_cite_existing_records` | `test_FR_0_9_01_audit_round_counts_and_lessons_cite_records` |
| `test_FR_0_9_01_no_open_debt_row_targets_phase_0` | same name |
| `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows` | same name |
| `test_FR_0_9_02_unit_log_copy_has_the_unitlog_header_and_valid_rows` | `test_FR_0_9_02_unit_log_copy_is_consistent` (`unit_log_problems` checks the header and every row) |
| `test_FR_0_9_02_each_row_estimate_recomputed_from_start_end_and_rate` | `test_FR_0_9_02_unit_log_copy_is_consistent` |
| `test_FR_0_9_02_compute_units_used_equal_unit_log_totals` | `test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources` |
| `test_FR_0_9_02_recruiting_status_quotes_the_owner` | `test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources` |
| `test_FR_0_9_02_pack_v1_plan_cites_sources_and_leaves_owner_blanks` | `test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources` |
| `test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict` | same name |

Round 1 also added two tests the plan did not name: `test_FR_0_9_01_memo_passes_every_check` and `test_FR_0_9_03_phase_audit_check_follows_the_approved_order`. Round 2 adds seven more (see "Round 2" below). Three of them give the merged checks their own failing case: X8 for the unit log, X9 for the owner's quotes, and X1/X2 for the phase audit.

## Round 2 (audit round 1 findings WP-0.9-F01 to F07)
The owner approved the fixes in `docs/approvals/WP-0.9.md` on `main` (`604e9a4`); the branch merged `origin/main` at `7c1f147`. `FIXES.md` holds the change budget, the root causes, each fix with its test, and 15 break proofs, all caught.

New tests, by requirement:
- FR-0.9-01: `test_FR_0_9_01_audit_rounds_cover_only_the_reviewed_wps` (F02), `test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09` and `test_FR_0_9_01_debt_check_covers_every_pinned_row` (F01, 30 cases), and three new `test_FR_0_9_01_evidence_check_reports_each_broken_link` cases (F07: `folder-link`, `outside-repository`, `escaping-repository`).
- FR-0.9-02: `test_FR_0_9_02_unit_log_check_reports_a_wrong_row` (X8, 3 cases) and `test_FR_0_9_02_owner_quotes_must_be_in_the_approval` (X9, 3 cases).
- FR-0.9-03: `test_FR_0_9_03_memo_verdict_and_commit_must_be_the_reports` (X1) and `test_FR_0_9_03_audited_commit_must_be_an_ancestor_of_head` (X2).
- DEBT-004 (gate, F04): `test_FR_0_0_09_index_applies_conftests_above_the_collected_folder` (2 cases).
- DEBT-030 (baseline, F05): `test_FR_0_1_02_check_reports_uncited_numbers_in_every_section[sources-second-table-same-header]` and `[inventory-second-table-same-header]`.

**F01, which IDs are pinned.** The owner's message listed 19 IDs: DEBT-001 to 007, 009, 010 and 012 to 021. `DEBT.md` at `254c1e3`, where WP-0.9 started, has 30 rows with a phase 0 target: DEBT-001 to 026 and 028 to 031. The list leaves out DEBT-022 to 026 and 028 to 031, among them DEBT-025, the only moved row. `PHASE0_DEBT_IDS` therefore pins all 30, a superset of the list. A test checks the set against `DEBT.md` at `254c1e3`. See `FIXES.md`.

Runs at `35d214e` on a clean tree:

```text
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.9
aqis-audit-gate: base origin/main (merge-base 604e9a4df74f), head 35d214e29fe2, approvals origin/main 604e9a4df74f, wp WP-0.9
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.7 s)

$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9"
63 passed, 1962 deselected in 2.24s

$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"
1970 passed, 55 deselected in 253.54s (0:04:13)
```

**Incident: free disk.** The first full run at `35d214e` gave `5 failed, 1965 passed`. All five failures were `test_FR_0_5_02_*` doctor tests, whose disk check requires at least 10 GB free; this VM had 9,883,615,232 bytes. I deleted `/tmp/pytest-of-root` (1.7 GB of earlier pytest temporary folders), and the run above passed with nothing else changed.
