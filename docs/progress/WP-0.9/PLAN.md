# PLAN — WP-0.9 Phase 0 review

Spec: `docs/specs/phase-0/WP-0.9-phase-review.md`  ·  Planned by session: https://claude.ai/code/session_01FYixR4QztgtCJqCD8TQGUi  ·  Date: 2026-10-03
Branch: `claude/great-heisenberg-h85gm9`  ·  Base: `origin/main` at `254c1e3`  ·  Depends on: WP-0.0 to WP-0.8 (all MERGED)

## Summary
When this WP is done:
- `docs/progress/PHASE0_MEMO.md` closes phase 0. It covers:
  - each exit criterion E1 to E6, with links to evidence that a test proves exists;
  - the decisions you took, each quoted from its approval file;
  - the open issues and lessons for the process, each tied to a committed record;
  - the phase 1 prerequisites: campaign A recruiting status, the pack v1 plan, and the Colab compute units used so far, recomputed from your unit log;
  - a link to the `/phase-audit 0` report.
- Every open row in `docs/progress/DEBT.md` that targets phase 0 is either closed or moved to a named later WP with your approval (must-catch 2). 19 rows target WP-0.9 today, and the plan below gives a recommendation for each.

**This plan needs more from you than most.** FR-0.9-02 depends on facts that only you hold. FR-0.9-03 and AT-0.9-01 depend on a command only you can start. Several debt rows need a ruling or an `ALLOW-EDIT` line. The questions are at the end.

## What I found in the repository (read-only inspection)
Nothing tracked was changed. The only writes were:
- `dev_bootstrap.sh`, which builds the git-ignored `.venv`;
- `git fetch --unshallow`, needed because this session's clone was shallow (see 9);
- scratchpad probes;
- one probe input under the git-ignored `data/raw/`, removed afterwards.

1. **Dependencies.** `STATUS.md` shows WP-0.0 to WP-0.8 as MERGED. Each `AUDIT.md` has verdict PASS:

   | WP | Final round | Commit audited |
   | --- | --- | --- |
   | WP-0.0 | 9 | `2588a23` |
   | WP-0.1 | 4 | `58865d4` |
   | WP-0.2 | 3 | `53d4be7` |
   | WP-0.3 | 3 | `050bbf4` |
   | WP-0.4 | 2 | `507a1bf` |
   | WP-0.5 | 3 | `f3bde36` |
   | WP-0.6 | 2 | `3501ca8` |
   | WP-0.7 | 2 | `93b1ad4` |
   | WP-0.8 | 3 | `8dc69d4` |

   CI on `main` at `254c1e3` is green: run 368, https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37130132258 (`lab` and `harness-regression`). No blocker is open: all 16 entries in `BLOCKERS.md` say `STATUS: RESOLVED`.

2. **Evidence for each exit criterion** (overview, "Phase 0 exit criteria"):

   | Criterion | What is committed | Note |
   | --- | --- | --- |
   | E1 Parity | `data/runs/phase0-smoke/phase0-smoke-{cloud-20260930T170440Z,colab-20261002T140101Z,oracle-20261002T141937Z}.tar`; the three `parity` outputs in `docs/runs/PHASE0_SMOKE.md` ("OC-0.7-03: the three machines compared"), each `parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)`; `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` | The cloud bundle is from commit `0a534ce`; the Colab and Oracle bundles are from `7c27dd5`. All three have the same CPU lock hash `87a1cc34c6d4`. |
   | E2 Resumability | Cloud VM: `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` and `test_FR_0_5_06_kill_during_result_write_never_counts` (`tests/aqis_lab/test_aqis_runner_resume.py`). Colab: `docs/progress/WP-0.5/OC-0.5-02_runner.log` and `OC-0.5-02_units.csv` | The Colab log shows session 1 stopping cleanly after 2 shards (`--max-shards 2`). The runtime was then deleted, and session 2 skipped both finished shards (`marker verified`) and computed the other 4. It is a stop plus runtime deletion, not a kill in the middle of a shard (question 9). |
   | E3 Traceability | `tests/aqis_lab/test_aqis_trace.py` (`test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock` and others). Each smoke bundle's `traced_rows` (Colab 390, Oracle 225, from `docs/progress/WP-0.7/EVIDENCE.md`) | The phase audit also traces 5 random rows (phase-audit step 4). |
   | E4 Baseline | `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md` and `raw/`; WP-0.1 `AUDIT.md` PASS | DEBT-028 to DEBT-031 concern this baseline (item 5). |
   | E5 Licences | `data/packs/smoke/v1/LICENCES.md`, `manifest.json`; `test_FR_0_4_07_committed_licences_cover_committed_manifest` | No owner recordings exist in phase 0. Your WP-0.4 approval replaced them with 10 synthetic TTS clips that "need no consent reference", so the consent half of E5 has nothing to check. The memo says so and cites the approval. |
   | E6 Governance | `STATUS.md`; each `AUDIT.md`; CI run 368; the `harness-regression` job (compares with `docs/baselines/harness_tests_baseline.md`) | WP-0.9 cannot itself be AUDIT-PASS and MERGED while the phase audit runs inside it (item 6, deviation D1). |

3. **WP-0.8's three owner-run checks have no committed result.** WP-0.8 is MERGED, but `docs/progress/WP-0.8/EVIDENCE.md` "Owner-run checks" still says "Pending (owner)" for:
   - the consent form on one page;
   - the wording review of the five documents;
   - `dev_bootstrap.sh --gpu` on Colab (DEBT-021).

   No report is committed. The phase-audit skill, step 3, says: "Owner-run results (Colab, Oracle) must exist as committed reports; a missing one is a MAJOR finding." The other WPs' owner-run checks are committed:
   - WP-0.0: OC-0.0-01, accepted in its approval;
   - WP-0.5: `OC-0.5-02_*`, and `docs/environment/doctor_colab_20260928T143840Z.json` for OC-0.5-01;
   - WP-0.6: `OC-0.6-01_oracle.txt`, `OC-0.6-02_sync_dry_run.txt`;
   - WP-0.7: `OC-0.7-01_colab.txt`, `OC-0.7-02_oracle.txt`, OC-0.7-03 in `PHASE0_SMOKE.md`.

   The WP-0.7 notes are one-line summaries, as WP-0.7's EVIDENCE.md already records.

4. **Debt.** `docs/progress/DEBT.md` has 19 OPEN rows with target WP-0.9:
   - from WP-0.0: DEBT-001 to DEBT-005;
   - from WP-0.2, WP-0.3 and WP-0.6: DEBT-006, DEBT-007, DEBT-009, DEBT-016;
   - from WP-0.7 and WP-0.8: DEBT-019, DEBT-022 to DEBT-026;
   - from WP-0.1: DEBT-028 to DEBT-031.

   DEBT-027 targets "Phase 2 VAD timing work", not phase 0, so must-catch 2 does not cover it. The memo still lists it as an open issue. One record is out of date: DEBT-026's "Accepted in" cell still says "Pending: needs a CONDITIONS line…", but `docs/approvals/WP-0.8.md` now has "Debt accepted: WP-0.8-F12 (target WP-0.9)".

5. **The raw-baseline protection added on `main` has no effect (DEBT-028).** Commit `254c1e3` appended `docs/baselines/tier2_vad/*/raw/**` to the end of `docs/process/PROTECTED_PATHS.txt`, which is inside the `[LAB-OWNED]` section. The hook's own parser (`.claude/hooks/_protected.py`, `load_patterns` and `classify`) gives:
   - `docs/baselines/tier2_vad/2026-10-03/raw/run.log -> LAB`
   - `bots/a.py -> GUARDED`

   `tools/audit/gate.py` (`classify`) uses the same rule order. So the raw files are still freely editable by Claude, which is the opposite of the intent. I cannot edit that file (NEVER list). See question 3.

6. **`/phase-audit 0` and this WP do not fit together as written.**
   - `.claude/skills/phase-audit/SKILL.md` has `disable-model-invocation: true`, so only you can start it. I cannot "run" it (FR-0.9-03).
   - Its step 2 audits "a fresh clone of `origin/main`". The memo and any debt fixes live on this branch until merge. A phase-audit FAIL that needs a fix here would fail again on re-run, because the re-run still clones `main`.
   - E6 needs every WP to be AUDIT-PASS and MERGED. WP-0.9 cannot be either while the memo waits for the phase-audit link that FR-0.9-03 requires.
   - The auditor may write only its report and a STATUS row (`.claude/agents/wp-auditor.md`).

   See question 1 and deviation D1.

7. **FR-0.9-02 inputs are not in the repository.**
   - **Campaign A recruiting status.** Nothing records it.
   - **Unit log.** It lives on your Drive (`MyDrive/AQIS_LAB/logs/units.csv`, `docs/colab/COLAB_RUNBOOK.md` "Unit log"). Only one row is committed: `docs/progress/WP-0.5/OC-0.5-02_units.csv`, a 0.0021 h CPU session of 0.0002 units. The WP-0.7 T4 sessions and any later ones are on Drive only.
   - **"Pack v1".** The spec does not define it, and no phase 1 spec exists. The committed Build Plan (`docs/specs/sources/AQIS_Test_Lab_Build_Plan.md`) gives only the phase 1 sizes: "Calibration pack: 2,000 synthetic clips; Campaign A: about 1,750 recorded turns", and the campaign A families. The smoke pack is already `data/packs/smoke/v1`, so "pack v1" probably means the phase 1 pack(s). Writing a plan beyond what the sources fix would mean inventing it (question 6).

8. **Leftover kit-patch files at the repository root:** `aqis-kit-patch-2.zip` and `aqis-kit-patch-3/`. The spec files in `aqis-kit-patch-3/` are byte-identical to `docs/specs/phase-0/`, but its `docs/progress/DEBT.md` is an old empty copy. No protected-path pattern matches these files. Whether to remove them is your call. The memo lists them as an open issue (question 10).

9. **Baseline test run at `254c1e3`.**
   - Fast suite in this session's first, shallow clone: `1 failed, 1855 passed, 55 deselected in 285.26s`. The failure was `test_FR_0_0_12_asset_pins_match_repository`, because `git cat-file` could not find the pinned corpus commit `14796262a824` in a shallow clone (`git rev-parse --is-shallow-repository` → `true`, 217 commits).
   - After `git fetch --unshallow origin`, that test gives `1 passed, 63 deselected in 3.28s`.
   - So the baseline is green with full history, and CI (`fetch-depth: 0`) agrees. WP-0.6's audit recorded the same need for full history. The build will run `git fetch --unshallow` before the suite whenever the clone is shallow.

10. **Facts behind the debt plan** (checked in `.venv` and the scratchpad):
   - **DEBT-001 to 005.** New tests can reuse `tests/aqis_lab/fixture_repo.py` (`FixtureRepo`, `normalise_hook`, `normalise_gate`), so no existing test file needs editing. `/usr/bin/python3.12` exists, so a `.venv` on the wrong Python can be built for real (K11.5a).
   - **DEBT-005, K11.5b.** The second guard, `[ "$actual" = "$PY" ]`, is reachable alone only if `uv venv --python 3.13` produced another Python. The real uv does not do that, so K11.5b cannot be tested without a stand-in for uv (question 5).
   - **DEBT-006.** A probe ran the real `python -m aqis_lab contracts validate <6,000-record file> --kind event --workers 2` as uid 65534 with `RLIMIT_NPROC` 1. Result: exit 2, `ERROR: cannot run 2 worker processes: [Errno 11] Resource temporarily unavailable; rerun with --workers 1`. The same run without the limit gave `event: 6000 records, 6000 valid, 0 invalid`. This uses a real OS limit, not a test double. The WP-0.0 K7.4 test already runs the gate as uid 65534.
   - **DEBT-007.** `test_FR_0_2_01_invalid_fixture_names_expected_pointers` and `test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields` compare sets of pointers, so one line per pointer keeps them green.
   - **DEBT-009.** A search of about 5,000 structured inputs found none that comes near `MAX_PASSES = 10`. The most passes found was 4 (`'oh % oh 1/2'`); for example `'oh oh oh'` and `'3 1/2'` take 3. No real input I found reaches `NormalisationError` (question 5).
   - **DEBT-019.** `tests/aqis_lab/test_aqis_ci.py` pins both `set(doc["jobs"]) == {"lab", "harness-regression"}` (line 38) and `lab_workflows == ["aqis-lab-ci.yml"]` (line 148). A network job or a new workflow both need `ALLOW-EDIT` for that file.
   - **DEBT-022.** The auditor's suggested rule ("option IDs may appear only in the Option column and in the How the owner decides block") rejects the committed `docs/decisions/TARGETS_OPTIONS.md` in three cells:
     - line 31, HR-B "What it gives": "than under HR-A";
     - lines 70 and 71, GE-B and GE-C "What it costs": "of GE-A".
   - **DEBT-023.** The WP-0.8 tests find the filler table with `table_with`, which needs a header that *holds* the five columns. So an added `Tone` column is found as before.
   - **DEBT-029.** `raw/run.log` names every clip of each operating point with its category and warm-up flag (`clip [1/229] 'clean_speech_dev_short_000.wav' (Category: 'clean speech', Warmup: True)`). So a per-category manifest count can cite a raw file.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.9-01 | Write `docs/progress/PHASE0_MEMO.md` in the layout under "Memo layout" below. Every claim links to a committed file, a commit, a collected test or this repository's CI run. A test checker (`tests/aqis_lab/aqis_memo_testutil.py`) parses the memo and checks it against the repository. | `docs/progress/PHASE0_MEMO.md`; `tests/aqis_lab/test_aqis_phase0_memo.py`; `tests/aqis_lab/aqis_memo_testutil.py` | `docs/capabilities/REGISTRY.md`: row `CAP-DOC-019` appended | `test_FR_0_9_01_memo_has_every_section`; `test_FR_0_9_01_exit_criteria_are_the_overview_six_verbatim`; `test_FR_0_9_01_every_evidence_link_exists` (must-catch 1); `test_FR_0_9_01_evidence_check_reports_each_broken_link` (break cases); `test_FR_0_9_01_decisions_quote_their_approval_files`; `test_FR_0_9_01_open_issues_list_every_open_debt_and_pending_check`; `test_FR_0_9_01_audit_round_counts_equal_each_audit_report`; `test_FR_0_9_01_lessons_cite_existing_records`; `test_FR_0_9_01_no_open_debt_row_targets_phase_0` (must-catch 2); `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows` (break cases) | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network" -k "FR_0_9"` |
| FR-0.9-02 | Memo section "Phase 1 prerequisites", in three parts. (a) Campaign A recruiting status: your figures from the approval, quoted, counts only (question 4). (b) Pack v1 plan: only what the Build Plan, `RECORDING_GUIDE.md`, `REGISTRY_FORMAT.md` and the existing pack tools fix, with every undecided item as `[OWNER DECIDES: …]` (question 6). (c) Compute units used: totals per runtime and overall (sessions, hours, estimated units) from your committed unit-log copy (question 4). | `docs/progress/WP-0.9/OC-0.9-01_units.csv` (committed by you) | none | `test_FR_0_9_02_unit_log_copy_has_the_unitlog_header_and_valid_rows`; `test_FR_0_9_02_each_row_estimate_recomputed_from_start_end_and_rate`; `test_FR_0_9_02_compute_units_used_equal_unit_log_totals`; `test_FR_0_9_02_recruiting_status_quotes_the_owner`; `test_FR_0_9_02_pack_v1_plan_cites_sources_and_leaves_owner_blanks` | same as FR-0.9-01 |
| FR-0.9-03 | After you run `/phase-audit 0` at the point set by question 1, the memo section "Phase audit" links `docs/progress/PHASE-0-AUDIT.md` and copies its verdict and audited commit. If the verdict is FAIL, each finding is fixed with `/surgical-fix` or accepted by you as debt, and the audit runs again. | — | `docs/progress/PHASE0_MEMO.md` (that section) | `test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict` (the report exists, its verdict line equals the memo's, and its "Commit audited" is an ancestor of `HEAD`) | the same `-k "FR_0_9"` command |
| AT-0.9-01 | `/phase-audit 0` returns PASS. I cannot start it (finding 6). | — | — | `test_FR_0_9_03_…` checks the recorded verdict | You type `/phase-audit 0`. Expected: report verdict `PASS`. |
| Must-catch 1 | The evidence checker resolves every link in E1 to E6: repository paths (must exist at `HEAD`), commit SHAs (`git cat-file -e`), test names (must be in `pytest --collect-only -q tests/aqis_lab`) and CI URLs (must be this repository's `actions/runs/<id>`). A criterion with no link, or any unresolved link, is a problem. | (in FR-0.9-01) | — | `test_FR_0_9_01_every_evidence_link_exists`; its break cases: a renamed path, an unknown test, an unknown commit, an E-row with no link, a missing E-row | fast suite |
| Must-catch 2 | Every DEBT row with a phase 0 target is CLOSED, or OPEN with a later target. Its status cell must cite an approval file on `origin/main` that names the row's debt ID or finding ID, plus the new target. The disposition of each row is under "Debt work". | (in FR-0.9-01) | `docs/progress/DEBT.md`: Target and Status cells of the 19 rows (and DEBT-026's "Accepted in" cell) | `test_FR_0_9_01_no_open_debt_row_targets_phase_0`; `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows` (breaks: a row left OPEN with target WP-0.9; a moved row whose approval does not name it) | fast suite |

### Memo layout (`docs/progress/PHASE0_MEMO.md`)
1. **Scope:** the commit reviewed, and links to `STATUS.md` and the overview.
2. **Exit criteria:** a table with columns ID, Criterion (verbatim from the overview), Status (`MET` or `MET with note`), Evidence (links) and Note. The evidence is item 2 above. A criterion that turns out not met is written `NOT MET`. It is never softened, and it goes to you.
3. **Decisions taken:** a table with columns Decision, Approval file, Quote. Each quote is copied character for character from that approval on `origin/main`. Examples:
   - the TTS clips replacing owner recordings (WP-0.4);
   - targets HR-B, PM-B, TB-B and GE-B, and retention of 3 years (WP-0.8);
   - the consent scheme `ca-sNNN` / `ca-cNNN`;
   - the WP-0.1 baseline run choice;
   - the BLK-008 handling of NFR-0.5-01.

   Harm rate is recorded as the rate only, below 2 % (DEBT-025).
4. **Open issues:** these must be listed:
   - every DEBT row still OPEN after this WP (at least DEBT-027), with its target;
   - every pending owner-run check;
   - finding 5 if it is not yet fixed;
   - the kit-patch leftovers;
   - any phase-audit finding you accept as debt.

   A test compares this list with `DEBT.md` and the WP evidence files.
5. **Lessons for the process:** each lesson cites the records it comes from. Candidates from the records:
   - audit rounds per WP (9, 4, 3, 3, 2, 3, 2, 2, 3; recomputed by a test from each `AUDIT.md`), and convergence after protocol version 2;
   - approval format and hook recognition (BLK-001, BLK-003);
   - missing spec sources (BLK-013);
   - intermittent CI from git and Arrow timing (BLK-011, BLK-012);
   - owner-run reports as one-line summaries (WP-0.7);
   - owner-run checks still pending at merge (WP-0.8);
   - a protection line placed in the wrong section (finding 5);
   - the shallow-clone baseline failure (finding 9).

   They are observations from the record, not new rules. Changing process is your decision.
6. **Phase 1 prerequisites** (FR-0.9-02).
7. **Phase audit** (FR-0.9-03).

### Debt work (must-catch 2; each row as you decide in question 2)
New tests go in `tests/aqis_lab/test_aqis_debt_wp09.py`, unless the row says otherwise. Each test is named after the requirement it protects, as WP-0.5 to WP-0.8 did. Each must fail when its behaviour is broken; the break is recorded in `EVIDENCE.md`. Each closed row's Status cell names the tests and the evidence.

| Debt | Recommendation | Fix | Changed files and functions (change budget) | Tests | `ALLOW-EDIT` needed |
| --- | --- | --- | --- | --- | --- |
| DEBT-001 | Close | Tests only. On `main` of a fixture repository, approvals named `readme.md` and `ReadMe.md` each carry `ALLOW-EDIT: vad_adapters/**`. The test edits a guarded file, and the hook and the gate must both report it. | `tools/audit/gate.py`: module docstring only (CAP-AUDIT-001 tests, CHANGE LOG); `REGISTRY.md` CAP-AUDIT-001 | `test_FR_0_0_06_parity_lowercase_readme_approval_approves_nothing` | none |
| DEBT-002 | Close | Tests only, each in a fixture repository: two specs match one WP (G37); a matching test name outside `tests/aqis_lab/` (G40); a path-style registry Module that is a folder (G33); a registry row without a capability ID (G63) | `gate.py` docstring (CAP-AUDIT-005, -006 tests, CHANGE LOG); `REGISTRY.md` rows | `test_FR_0_0_09_two_specs_for_one_wp_is_a_finding`, `test_FR_0_0_09_only_lab_test_names_count`, `test_FR_0_0_08_registry_module_that_is_a_folder_is_a_finding`, `test_FR_0_0_08_registry_row_without_capability_id_is_malformed` | none |
| DEBT-003 | Close | Tests only. G44: an `ALLOW-PATTERNS-IN` glob covering an unscanned file lists only the scanned one. P32: a local shallow clone without the pinned corpus commit fetches it from its local origin (no network). R15: a JUnit `testcase` without `name` or `classname` gives exit 2. B16: a probe naming the same version twice is accepted. | `gate.py`, `aqis_lab/deploy/harness_provision.py`, `tools/harness/regression_check.py`, `dev_bootstrap.sh`: header test lists and CHANGE LOG only; `REGISTRY.md` rows | `test_FR_0_0_07_exempted_files_list_only_scanned_files`, `test_FR_0_0_12_fetches_pinned_corpus_commit_missing_from_shallow_clone`, `test_FR_0_0_11_testcase_without_name_is_an_input_error`, `test_FR_0_0_02_probe_repeating_one_version_is_accepted` | none |
| DEBT-004 | Close (question 2 (b)) | Add the missing collection rules to the static index, each checked against `pytest --collect-only` on the same fixture file, as the WP-0.0 F47 tests do:<br>- pytest's default `norecursedirs` (`*.egg`, `.*`, `_darcs`, `build`, `CVS`, `dist`, `node_modules`, `venv`, `{arch}`);<br>- literal `collect_ignore` and `collect_ignore_glob` in `conftest.py`, where a non-literal value is a `GateError` (exit 2), never a guess;<br>- any false constant `__test__`;<br>- abstract `Test` classes (an `abc.abstractmethod`);<br>- module-level names rebound after their `def`.<br>Plus a test for the call-form fixture rule. Alternative (a): build the index from `pytest --collect-only`. I do not recommend it: the gate would import the test code, and existing gate tests that pin static messages (for example "cannot parse test file") could change. | `tools/audit/gate.py`: `test_functions`, `_collect_class`, `_sets_test_false`, new helpers `_skipped_dirs` and `_conftest_ignores`, module docstring; `docs/tools/AUDIT_GATE.md`: the known-gaps paragraph; `REGISTRY.md` CAP-AUDIT-005 and -006 | `test_FR_0_0_09_index_skips_folders_pytest_skips`, `…_honours_conftest_collect_ignore`, `…_non_literal_collect_ignore_is_an_error`, `…_false_dunder_test_values_switch_off`, `…_abstract_test_class_is_not_collected`, `…_rebound_test_name_is_not_collected`, `…_call_form_fixture_is_not_a_test` | none |
| DEBT-005 | Close K7.7, K10.6, K11.5a, K14.12, X4 and X8 with tests. K11.5b is your ruling (question 5). | K7.7: a lab test file with a syntax error gives exit 2 and `ERROR: <file>:<line>: cannot parse test file`. K10.6: a spec line holding two IDs, where only the first is planned, gives a finding for the second. K11.5a: a real `.venv` on `/usr/bin/python3.12` is recreated on the probe's 3.13. K14.12: an archive that fails partway through extraction leaves no `.complete` marker. X4: `class TestX(object)` counts, checked against pytest. X8: the report has a blank line before the import report. | header test lists and CHANGE LOG of `gate.py`, `harness_provision.py`, `dev_bootstrap.sh`; `REGISTRY.md` rows | `test_FR_0_0_06_fails_closed_on_unparsable_lab_test_file`, `test_FR_0_0_09_traces_every_id_on_a_spec_line`, `test_FR_0_0_02_recreates_venv_built_on_another_python`, `test_FR_0_0_12_no_complete_marker_after_failed_extraction`, `test_FR_0_0_09_test_class_with_explicit_object_base_counts`, `test_FR_0_0_12_blank_line_before_import_report` | none |
| DEBT-006 | Close | Test only (finding 10). Run the real CLI with `--workers 2` on a generated 6,000-record event file under `RLIMIT_NPROC` 1; as root, as uid 65534 (the K7.4 precedent). It requires exit 2, the "rerun with --workers 1" message, and no traceback. If CI's non-root runner shows another failure type (for example a thread that cannot start), that is a real gap in the same path, and `validate_event_lines` handles it. | `aqis_lab/contracts/validate.py`: `validate_event_lines` (its `except` clause, only if CI shows another failure type), module docstring; `REGISTRY.md` CAP-CONTRACTS row | `test_FR_0_2_04_cli_worker_start_failure_exits_2_with_rerun_hint` | none |
| DEBT-007 | Close | One report line per failing field: errors that share a pointer are merged into one `FieldError`, keeping each distinct message in order and joined with `; `. This applies to schema, value and rule errors (`_validate`) and to sequence errors (`validate_event_lines`). | `aqis_lab/contracts/validate.py`: `_validate`, `validate_event_lines`, new `_one_per_pointer`, module docstring (CAP-CONTRACTS-006); `REGISTRY.md` CAP-CONTRACTS-006 | `test_FR_0_2_04_one_report_line_per_failing_field` (invalid fixture line 26: one `/clip_id` line holding both messages; no record of the invalid fixture has two lines at one pointer) | none |
| DEBT-009 | Your ruling (question 5) | Time-boxed (2 h) systematic search for a real input that needs more than 10 passes. If one is found: a real CLI test. If not: your fallback. | `aqis_lab/commands/score.py`: docstring only, if a test is added | `test_FR_0_3_06_score_turns_normalisation_error_into_exit_2` (only with a real input) | none |
| DEBT-016 | Your ruling (question 5) | Recommended: close as a permanent limit of the FR-0.5-02 report-name format. The failure is loud and changes nothing, and a real setup takes seconds. Changing the name format is a spec change only you can make. | `DEBT.md` only | — | none |
| DEBT-019 | Close | Add a third job, `lab-network`, to `.github/workflows/aqis-lab-ci.yml`. It uses the same bootstrap and runs `.venv/bin/python -m pytest tests/aqis_lab -q -m "network and not slow and not gpu and not colab and not oracle"`, with read-only permissions as before. | `.github/workflows/aqis-lab-ci.yml` (new job, header comment); `tests/aqis_lab/test_aqis_ci.py`: `test_FR_0_0_10_ci_triggers_push_and_pull_request` (job set gains `lab-network`); `REGISTRY.md` CI row | `test_FR_0_0_10_ci_runs_network_only_tests` (exact marker expression; with `--collect-only`, it selects exactly the tests marked `network` and none marked slow, gpu, colab or oracle) | `tests/aqis_lab/test_aqis_ci.py` |
| DEBT-022 | Close | Reword the three cells (finding 10) to name the value, not the ID: "than under the 1 % option", "of the 10 % option". Meaning is unchanged. New check: option IDs appear only in the Option column and the "How the owner decides" block. | `docs/decisions/TARGETS_OPTIONS.md`: those three cells; `REGISTRY.md` CAP-DOC-018 | `test_FR_0_8_05_option_ids_only_in_option_column_and_decision_block`, `test_FR_0_8_05_option_id_check_detects_a_choice_in_other_words` (breaks: "The lab will work to HR-B." in prose, an ID in a trade-off cell, an ID in a heading) | none |
| DEBT-023 | Close | Add a `Tone` column to the filler table: `negative` or `positive` for Level 2 rows (as each row's "Intended use" already says), `n/a` for the others. New check: rule 1 keys on Tone. | `docs/fillers/FILLER_LIBRARY_v0.md`: filler table and header comment; `REGISTRY.md` CAP-DOC-017 | `test_FR_0_8_04_level_2_tone_is_explicit_and_rule_1_keys_on_it` (breaks: a positive filler worded "cheerful" without `ctx-negative-caller`; a Level 2 row without a tone) | none |
| DEBT-024 | Close after your wording review (question 7) | (a) Recommended: your WP-0.8 wording review confirms or edits the drafted items, and the docs say so with your approval line. (b) Otherwise: mark each drafted description and rule "Drafted in WP-0.8 for owner review", with a test that every unsourced item is marked. | (a) `RECORDING_GUIDE.md`, `FILLER_LIBRARY_v0.md`: only your edits, if any; (b) the same files, marks only | (b) `test_FR_0_8_02_drafted_guide_items_are_marked`, `test_FR_0_8_04_drafted_filler_texts_are_marked` | none |
| DEBT-025 | Move (question 8) | The memo records the harm-rate decision as the rate only, below 2 %. The decision rule (method and confidence) becomes an owner question for the WP you name in phase 4. Or you decide the rule now, and the row closes. | `DEBT.md` only | — | none |
| DEBT-026 | Close | Add the two cases the auditor named to `OWNER_FACT_BREAKS`: a pre-ticked expected box, and text added to the Signature line. Also correct the out-of-date "Accepted in" cell. | `tests/aqis_lab/test_aqis_recording_docs.py`: `OWNER_FACT_BREAKS` only | the existing `test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions`, gaining two cases | `tests/aqis_lab/test_aqis_recording_docs.py` |
| DEBT-028 | Close after you move one line (question 3) | You move `docs/baselines/tier2_vad/*/raw/**` from `[LAB-OWNED]` to `[GUARDED]` in `PROTECTED_PATHS.txt` on `main`. A new test checks both parsers. | none in code | `test_FR_0_1_03_raw_baseline_files_are_guarded`: for every file under `docs/baselines/tier2_vad/*/raw/`, both the hook's and the gate's `classify` return `GUARDED`. It fails today (`LAB`). | none |
| DEBT-029 | Close | Add an "In the manifest" column to the SUMMARY.md Conditions table. Each cell counts that category's clip lines in `raw/run.log` for the first operating point, warm-up included, cited with new S-rows. The checker gets a binding rule for the column (and a line-count source, if the existing `lines` source cannot express it). | `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md`: Conditions table and Sources rows; `tests/aqis_lab/aqis_baseline_testutil.py`: the Conditions binding spec in `binding_problems` (and the `lines` source in the resolver, if needed) | a new case in `test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column`; the existing citation tests cover the new cells | `tests/aqis_lab/aqis_baseline_testutil.py`, `tests/aqis_lab/test_aqis_tier2_baseline.py` |
| DEBT-030 | Close | Limit both exemptions in `body_text` to the named table, found by its header (`ID` in Sources, `Item` in Raw inventory). Add break cases X4 and X4-inv. | `aqis_baseline_testutil.py`: `body_text`; `test_aqis_tier2_baseline.py`: `test_FR_0_1_02_check_reports_uncited_numbers_in_every_section` parameters | that test, two new cases | same two files |
| DEBT-031 | Close | Add one isolating case per part (H1 `_report` row binding, H3 one row per operating point, H4 extra citation in `_cell_problems`, H5 `expr` operands in `_shape`), plus a check that every category has a Conditions row, with its case. | `aqis_baseline_testutil.py`: `binding_problems` (category completeness); `test_aqis_tier2_baseline.py`: parameters of `test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column` | that test, five new cases | same two files |

Before any existing file is changed, I record its tests and linked capability tests (change control). Existing test files change only where an `ALLOW-EDIT` names them, and only to add cases or widen the one job set. No existing assertion is loosened.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to the questions below, in `docs/approvals/WP-0.9.md` on `main` (template `docs/process/templates/APPROVAL.md`), with the `ALLOW-EDIT` lines your answers need (see question 2) | Approval and the change budget | Before `/wp-build` |
| 2 | Move one line in `docs/process/PROTECTED_PATHS.txt` (question 3) | DEBT-028; I cannot edit that file | Before `/wp-build` |
| 3 | A copy of `MyDrive/AQIS_LAB/logs/units.csv`, committed on `main` as `docs/progress/WP-0.9/OC-0.9-01_units.csv`. If `units_open_session.json` exists, close the session first with `unitlog end`. | FR-0.9-02, compute units used | Before the FR-0.9-02 part of the build |
| 4 | Campaign A recruiting status as counts only: speakers recruited of 22, consents signed, sessions recorded, quiet-room and everyday-noise split. No names. | FR-0.9-02 | In the approval |
| 5 | What "pack v1 plan" means, and any plan content you want beyond the sources (question 6) | FR-0.9-02 | In the approval |
| 6 | WP-0.8's three pending owner-run checks: one-page print preview of the consent form; wording review of the five documents; `bash aqis_lab/deploy/dev_bootstrap.sh --gpu` on a Colab GPU runtime. Commit one result note, for example `docs/progress/WP-0.8/OC-0.8_owner_checks.txt`. | Otherwise the phase audit records a MAJOR finding (finding 3); the wording review also settles DEBT-024 | Before `/phase-audit 0` |
| 7 | Type `/phase-audit 0` at the point question 1 sets | FR-0.9-03, AT-0.9-01; only you can start it | After I report the memo ready for the phase audit |
| 8 | WP IDs for any debt row you move (questions 2, 5 and 8) | Must-catch 2 needs a named later WP; no phase 1 or later spec exists yet | In the approval |

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| OC-0.9-01 unit log copy | Colab or Drive web | Download `MyDrive/AQIS_LAB/logs/units.csv` and commit it as `docs/progress/WP-0.9/OC-0.9-01_units.csv` | A CSV whose header is `session_id,platform,gpu_type,start_utc,end_utc,end_basis,hours,runtime,units_per_hour,estimated_units,rate_source` |
| WP-0.8 pending checks | Your computer, the PR, Colab | As in `docs/progress/WP-0.8/EVIDENCE.md` "Owner-run checks" | One page; your OK or edits; `OK: .venv ready: …` and `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …` |
| AT-0.9-01 | This repository, a Claude Code session on this branch | `/phase-audit 0` | `docs/progress/PHASE-0-AUDIT.md` with verdict `PASS` |

No new Colab or Oracle code runs in this WP. The DEBT-006 test runs as uid 65534 when root. On Colab it would do the same, but it needs no separate owner check.

## Risks and questions
**Questions** (recommended option first):

1. **How should `/phase-audit 0` fit into this WP?** (finding 6)
   - **(a) Recommended.** You edit `.claude/skills/phase-audit/SKILL.md` step 2 to clone the branch under review instead of `origin/main`. The phase audit then covers phase 0 plus this WP's fixes, and a re-run sees fixes made here. For the audit run inside WP-0.9, E6 covers WP-0.0 to WP-0.8 (deviation D1).
   - Sequence:
     1. `/wp-build WP-0.9`: debt work, then the memo up to the phase-audit link. I set STATUS to IN-BUILD and say when it is ready.
     2. You run `/phase-audit 0`.
     3. I link the report (FR-0.9-03) and finish `EVIDENCE.md`.
     4. `/wp-audit WP-0.9`.
     5. You merge.
   - **(b)** Keep the skill as it is. The phase audit then covers `main` only, and any phase-audit finding that needs a code fix must reach `main` before a re-run can pass.
   - **(c)** You decide another order.
2. **Debt dispositions.** Accept the "Debt work" table as recommended? That means 15 rows closed with fixes or tests (DEBT-001 to 007 except K11.5b, DEBT-019, 022, 023, 026, 028 to 031), and DEBT-009, 016, 024 and 025 by your rulings in questions 5, 7 and 8.
   - The approval would then need:
     - `ALLOW-EDIT: tests/aqis_lab/test_aqis_ci.py`
     - `ALLOW-EDIT: tests/aqis_lab/test_aqis_recording_docs.py`
     - `ALLOW-EDIT: tests/aqis_lab/aqis_baseline_testutil.py`
     - `ALLOW-EDIT: tests/aqis_lab/test_aqis_tier2_baseline.py`
   - Alternative: move the WP-0.0 tooling rows (DEBT-001 to 005) to a phase 1 WP you name. This shortens WP-0.9 but carries the gaps into phase 1.
   - For DEBT-004, choose (b), static rules (recommended), or (a), `pytest --collect-only`.
3. **DEBT-028: move the raw-baseline line into `[GUARDED]`?**
   - **(a) Recommended.** On `main`, in `docs/process/PROTECTED_PATHS.txt`, move `docs/baselines/tier2_vad/*/raw/**` from the end of the file to the `[GUARDED]` section, above `[LAB-OWNED]`. My test then checks both parsers.
   - **(b)** Put it in `[NEVER]` instead, so not even an approval can unlock it. Future baselines would then need you to commit raw files yourself, which you already do.
4. **FR-0.9-02 facts.** Please give the campaign A counts (owner need 4) and commit the unit-log copy (owner need 3). Is there a compute-unit budget figure the memo should compare usage against? If not, the memo reports usage only and says no budget was set.
5. **Rows that cannot be tested honestly under the rules** (DEBT-005 K11.5b, DEBT-009, DEBT-016). For each, choose:
   - **(a) Recommended for K11.5b and DEBT-016.** Close as a recorded, permanent limit, with your approval line as the reason.
   - **(b) Recommended for DEBT-009.** A 2-hour real-input search first, then (a) if none is found.
   - **(c)** Allow one named test double (a stand-in `uv` for K11.5b; a stand-in normaliser step for DEBT-009) as a written exception to `.claude/rules/30-testing-and-evidence.md`.
   - **(d)** Move to a later WP you name.
6. **"Pack v1 plan".**
   - **(a) Recommended.** It means the phase 1 packs: the Calibration pack (2,000 synthetic clips) and the Campaign A pack (about 1,750 turns). The memo states only:
     - what the Build Plan and committed docs fix;
     - what the lab already provides (registry `owner`/`campaign` importer rules, `pack build`, the file naming in `RECORDING_GUIDE.md`);
     - `[OWNER DECIDES: …]` for each open item: synthetic-speech source and voices, category mix, pack versioning and splits, storage location.
   - **(b)** You give the plan content, or the Build Plan sections "Dataset architecture" and "Phase 1" in full.
   - **(c)** Something else.
7. **DEBT-024.** Will your WP-0.8 wording review (owner need 6) confirm or edit the drafted items? Recommended (a). If you prefer not to review now, (b) marks them as drafted.
8. **DEBT-025.**
   - **(a) Recommended.** Move it to the phase 4 WP that scores the filler pack; please give its ID. The memo records "harm rate below 2 %" without a decision rule.
   - **(b)** Decide the rule now (for example "exact one-sided binomial test, 95 % confidence"), and the row closes.
9. **E2 on Colab.** The committed Colab check stopped cleanly after 2 shards (`--max-shards 2`), then deleted the runtime, then resumed (finding 2). It was not killed in the middle of a shard.
   - **(a) Recommended.** Accept it as E2's Colab evidence, as WP-0.5's approved plan defined it. The memo states exactly what was done.
   - **(b)** Run a new Colab check that interrupts a running shard (Runtime → Interrupt during shard 3, then resume), and commit its log.
10. **Kit-patch leftovers** (`aqis-kit-patch-2.zip`, `aqis-kit-patch-3/`):
    - **(a) Recommended.** Leave them, and list them as an open issue.
    - **(b)** Remove them in this WP. Name them in the approval.

**Risks:**
1. **The phase audit can fail for reasons outside this WP.** Examples: a slow-suite flake, a network outage during the smoke command, or the missing WP-0.8 reports. AT-0.9-01 then stays open until each finding is fixed or you accept it.
2. **The phase audit needs the network for its smoke run and harness provisioning** (alphacephei.com for the Vosk model; huggingface.co, PyPI and GitHub). Earlier sessions reached these hosts. If one is blocked, I report the exact host name.
3. **DEBT-019 makes CI depend on the Vosk model download.** An outage turns CI red. The extra job adds about 3 to 5 minutes.
4. **DEBT-004 changes the WP-0.0 gate's test index.** The whole gate test suite, including the hook parity tests, must stay green. Each new rule is checked against pytest itself.
5. **DEBT-006 on CI's non-root runner may fail differently from root/uid 65534.** If it does, that is a real defect in the same error path, and I fix it inside `validate_event_lines`.
6. **Session clones can be shallow** (finding 9). I check and unshallow before every suite run.
7. **Size.** 19 debt rows plus the memo is the largest build since WP-0.0. It may span more than one session. I commit and push per item.

## Deviations
- **D1. E6 during the in-WP phase audit.** E6 says every WP is AUDIT-PASS and MERGED. A phase audit run inside WP-0.9 cannot see WP-0.9 merged, and FR-0.9-03 needs its report before WP-0.9 can be audited.
  - Proposed: for that run, E6 covers WP-0.0 to WP-0.8, and WP-0.9 is recorded as the review in progress.
  - WP-0.9's own AUDIT-PASS and merge are proved by `/wp-audit WP-0.9` and your merge, as for every WP.
  - Please accept or reject. If you reject it, question 1 needs another order.

No other deviation is proposed.
