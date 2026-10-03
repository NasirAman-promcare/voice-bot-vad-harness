# EVIDENCE — WP-0.1

Environment: cloud VM (Ubuntu 24.04, x86_64), `.venv` Python 3.13.14, lock `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`, branch `claude/practical-knuth-wsgvud`. Build commits `f85584f`, `cb49333` and `bcdd3e6`, then this file.

Inputs from the owner:
- `docs/approvals/WP-0.1.md` (`75e39d9`): questions 1 to 6 as recommended in PLAN.md, the owner's statement on negative latencies with DEBT-027, and the R6 `orchestrator` row ruling.
- Raw outputs `docs/baselines/tier2_vad/2026-10-03/raw/` (`e3786b5`), with `NETWORK.md` completed in `a3420c3`.
- BLK-016 rulings: R3 allows the root `run.log` console capture, and R8 is met when the Jingle logs cover every clip record.

## Requirements

### FR-0.1-01 — the raw folder is complete
- Tests:
  - `test_FR_0_1_01_raw_folder_has_every_required_item`
  - `test_FR_0_1_01_inventory_lists_every_raw_file`
  - `test_FR_0_1_01_raw_files_agree_on_the_run`
  - `test_FR_0_1_01_raw_folder_holds_no_audio`
  - `test_FR_0_1_01_check_reports_each_missing_item` (must-catch 2 self-test)
- Checks: `raw_problems` in `tests/aqis_lab/aqis_baseline_testutil.py`, covering R1 to R8 as PLAN.md "Required raw items" defines them, with the BLK-016 rulings.
- What was found (read-only, before any summary was written):
  - **First check.** It found three R4 points unanswered (Jitsi version, TURN relay, start and end time), plus two differences in R3 and R8. Raised as **BLK-016**. Nothing was filled in; the owner completed `NETWORK.md` on `main` (`a3420c3`).
  - **R5.** `raw_evaluations.jsonl` holds 2,689 records of one run, `vad_eval_run_20260913_001_20261003_075907`: 1 `run_context`, 224 `scoring_clip` and 224 `tier2_pipeline_latency` records for each of the 6 operating points, and 0 `clip_failure`. So the run is full: 229 manifest clips minus 5 warm-up clips.
  - **R3.** Commit `75e39d9` was committed at 06:38 UTC, before the run started at 07:59 UTC. `git diff --stat 75e39d9 origin/main` lists only files under `docs/baselines/tier2_vad/2026-10-03/raw/`, so the harness on `main` is the harness that ran.
  - **R7.** `02_tier2_live_pipeline.ipynb` holds an earlier aborted attempt (`…_074053`, `libc++.so.1` not found). It is listed in the inventory as `other`; `run.log` is R7.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_1_01 -rA -p no:cacheprovider`
- Output (real excerpt):
```text
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_raw_folder_has_every_required_item
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_inventory_lists_every_raw_file
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_raw_files_agree_on_the_run
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_raw_folder_holds_no_audio
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_check_reports_each_missing_item
5 passed, 1880 deselected in 4.82s
```
- Test first: at the tests-only commit `cb49333`, before SUMMARY.md existed, the run gave 17 failed and 1 passed (corrected in round 2, audit finding WP-0.1-F6; the round 1 text said every test failed).
  - 16 tests failed with `FileNotFoundError: … docs/baselines/tier2_vad/2026-10-03/SUMMARY.md`, because there was no Raw inventory yet.
  - `test_FR_0_1_03_baseline_folder_holds_only_summary_and_raw` failed with `assert ['raw'] == ['SUMMARY.md', 'raw']`.
  - `test_FR_0_1_01_raw_folder_holds_no_audio` passed, as it should: it reads only `raw/`, never SUMMARY.md, and `raw/` holds no audio.
- Status: DONE

### FR-0.1-02 — SUMMARY.md, every number cited
- File: `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md`.
  - Sections: Run, Setup, VADs, Conditions, Headline metrics per VAD, Run health, Owner's statement, Raw inventory, Sources.
  - 359 Sources rows, each `direct` (value exactly as in the raw file at the locator) or `derived` (`where` + op over the records, or `expr` over other source IDs, with formula, inputs and rounding).
- Agreement across sources:
  - **Report, run log and records.** Every harness-reported metric (F1, precision, recall, silence FPR, quiet FNR, mean onset, mean offset hangover, clips scored) is cited to the report and/or run log and to a recomputation from the records. All agree for all 6 operating points (`test_FR_0_1_02_report_log_and_records_agree`, which recomputes reporting.py's formulas in the test).
  - **Not in the report.** Medians, wall-clock pipeline latency and null or negative counts are derived only, with formulas shown.
  - **Owner's statement.** It is quoted word for word from the approval and labelled as the owner's (`test_FR_0_1_02_summary_has_every_section` compares it with `docs/approvals/WP-0.1.md`).
  - **`orchestrator` report row.** Recorded and not counted (approval, R6).
- Tests:
  - `test_FR_0_1_02_summary_has_every_section`
  - `test_FR_0_1_02_every_number_cites_a_source`
  - `test_FR_0_1_02_every_number_matches_its_cited_source`
  - `test_FR_0_1_02_derived_numbers_show_formula_inputs_and_rounding`
  - `test_FR_0_1_02_headline_metrics_cover_every_operating_point`
  - `test_FR_0_1_02_report_log_and_records_agree`
  - `test_FR_0_1_02_check_reports_a_changed_raw_value` (must-catch 1 self-test, 5 cases)
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_1_02 -rA -p no:cacheprovider`
- Output (real excerpt):
```text
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_summary_has_every_section
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_every_number_cites_a_source
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_every_number_matches_its_cited_source
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_derived_numbers_show_formula_inputs_and_rounding
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_headline_metrics_cover_every_operating_point
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_report_log_and_records_agree
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_check_reports_a_changed_raw_value[jsonl-direct]
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_check_reports_a_changed_raw_value[jsonl-derived-input]
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_check_reports_a_changed_raw_value[yaml]
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_check_reports_a_changed_raw_value[log-line]
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_check_reports_a_changed_raw_value[report-cell]
11 passed, 1874 deselected in 6.06s
```
- Read-only commands that extract each locator kind by hand (used for AT-0.1-01 below; run in `docs/baselines/tier2_vad/2026-10-03/raw/`):
  - text `{"line": N, "after": L}`: `sed -n Np <file>`
  - YAML `{"key": K}`: `grep -n '^K:' <file>`
  - JSONL `where` + `field`, or a derived `op`: `jq -s '[.[] | select(<where>)] | …' raw_evaluations.jsonl`
  - notebook `{"cell", "output", "row", "col"}`: `jq -r '.cells[C].outputs[O].data["text/markdown"] | join("")' 03_report.ipynb`
- Status: DONE

### FR-0.1-03 — no code and no harness change
- Tests:
  - `test_FR_0_1_03_baseline_folder_holds_only_summary_and_raw`
  - `test_FR_0_1_03_raw_files_unchanged_since_inventory` (bytes and SHA-256 of every raw file equal the Raw inventory)
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_1_03 -rA -p no:cacheprovider`
- Output (real excerpt):
```text
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_03_baseline_folder_holds_only_summary_and_raw
PASSED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_03_raw_files_unchanged_since_inventory
2 passed, 1883 deselected in 0.74s
```
- Branch file list, run as `git fetch -q origin main; git diff --name-only origin/main...HEAD` before this file was added:
```text
docs/baselines/tier2_vad/2026-10-03/SUMMARY.md
docs/capabilities/REGISTRY.md
docs/progress/BLOCKERS.md
docs/progress/DEBT.md
docs/progress/STATUS.md
docs/progress/WP-0.1/PLAN.md
tests/aqis_lab/aqis_baseline_testutil.py
tests/aqis_lab/test_aqis_tier2_baseline.py
```
- Notes on that list:
  - `git diff --name-status origin/main...HEAD -- aqis_lab tools config requirements notebooks .github bots webrtc_bridge orchestrator.py reporting.py | wc -l` → `0`.
  - The raw files came from the owner's commits on `main`. This branch never edits them, as the SHA-256 test shows.
  - `docs/progress/DEBT.md` is outside PLAN.md's file list. It was added because the approval's condition on question 6 requires it (row DEBT-027).
  - SUMMARY.md was written by a scratchpad script, which was not committed. Its values are verified independently by the tests above.
- Status: DONE (deviation D1, accepted in the approval: tests and a test helper only, in `tests/aqis_lab/`)

## Acceptance commands

### AT-0.1-01 — five random numbers against the raw files
The auditor makes their own picks. This is the builder's self-check: 5 Sources rows drawn with `random.Random(20261003).sample(...)`, each checked with `sed` or `jq`, independently of the test helper.

```text
S15 | Opus 16 kHz, 20 ms packet frames. | NETWORK.md | direct | {"line": 12, "after": "Transport Protocol:"}
S313 | 17 | raw_evaluations.jsonl | derived | count_null of payload.mean_offset_hangover_latency_ms, tier2_pipeline_latency, firered_vad
S3 | 2026-10-03 11:34:53 UTC | NETWORK.md | direct | {"line": 10, "after": "End Time:"}
S174 | 0.943 | — | derived | {"expr": "S165 / (S165 + S168)"}  (recall, webrtc_vad_mode0)
S74 | 18 | raw_evaluations.jsonl | derived | count of scoring_clip, webrtc_vad_mode3, loud/clipped speech
```
```text
$ sed -n 12p NETWORK.md
- Transport Protocol: Opus 16 kHz, 20 ms packet frames.
$ sed -n 10p NETWORK.md
- End Time: 2026-10-03 11:34:53 UTC
$ jq -s '[.[] | select(.record_type=="tier2_pipeline_latency" and .adapter_id=="firered_vad") | select(.payload.mean_offset_hangover_latency_ms==null)] | length' raw_evaluations.jsonl
17
$ jq -s '[.[] | select(.record_type=="scoring_clip" and .adapter_id=="webrtc_vad_mode0") | .payload.metrics] | {tp: (map(.tp)|add), fn: (map(.fn)|add)} | . + {recall: (.tp/(.tp+.fn))}' raw_evaluations.jsonl
{ "tp": 150652, "fn": 9065, "recall": 0.9432433616959998 }
$ jq -s '[.[] | select(.record_type=="scoring_clip" and .adapter_id=="webrtc_vad_mode3" and .payload.category=="loud/clipped speech")] | length' raw_evaluations.jsonl
18
```
All five match: `S165` = 150652 and `S168` = 9065 in SUMMARY.md's frame-count table, and 0.94324… rounds to 0.943.

## Must-catch proof
Run in a full copy of the repository (`git archive HEAD | tar -x -C <scratchpad>/mc`, under `/tmp`), with `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q`. Before the breaks the copy gave `18 passed`. The copy was restored after each break, and gave `18 passed` again after the last.

**1. Every number in SUMMARY.md matches its cited raw file.**

1a. One record value changed: `raw_evaluations.jsonl` line 3 (`ten_vad`, `clean_speech_dev_medium_000.wav`), `metrics.tp` 319 → 320.
```text
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_every_number_matches_its_cited_source
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_03_raw_files_unchanged_since_inventory
7 failed, 11 passed in 6.66s
E   Left contains 4 more items, first extra item: 'S99 (raw/raw_evaluations.jsonl {"where": {"record_type": "scoring_clip", "adapter_id": "ten_vad"}, "op": "sum", "fiel...pe = scoring_clip, adapter_id = ten_vad gives 135821, shown under 'exact' as '135821'; SUMMARY.md shows '135820''
```
(The other 5 failures are the `check_reports_a_changed_raw_value` self-tests, whose precondition, a clean summary, no longer holds.)

1b. One cited log value changed: `run.log` line 3987, `F1: 0.910` → `F1: 0.911`.
```text
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_every_number_matches_its_cited_source
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_report_log_and_records_agree
8 failed, 10 passed in 6.65s
E   Left contains one more item: 'S112 (raw/run.log {"line": 3987, "after": "F1:"}): line 3987: after 'F1:' comes '0.911', not '0.910''
```

**2. A missing raw file is reported as missing, never filled in.** Deleted `raw/bridge_config.yaml` (R2).
```text
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_01_raw_folder_has_every_required_item
FAILED tests/aqis_lab/test_aqis_tier2_baseline.py::test_FR_0_1_02_every_number_matches_its_cited_source
11 failed, 7 passed in 3.46s
E   AssertionError: 2026-10-03: R2 raw/bridge_config.yaml missing or empty
E   Left contains 3 more items, first extra item: 'S18 (raw/bridge_config.yaml {"key": "opus_bitrate_bps"}): raw/bridge_config.yaml is missing'
```
The same two behaviours are also guarded inside the suite on edited `tmp_path` copies:
- `test_FR_0_1_02_check_reports_a_changed_raw_value`, with a JSONL value, a derived input, a YAML value, a log line and a report cell;
- `test_FR_0_1_01_check_reports_each_missing_item`, which deletes every required file in turn.

## Fast suite
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"`
```text
1830 passed, 55 deselected in 240.76s (0:04:00)
```
(Before WP-0.1, at planning: `1812 passed, 55 deselected`. The 18 new tests make the difference.)

## Audit gate
- Command: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1`
- Output (real, with this file in the working tree):
```text
aqis-audit-gate: base origin/main (merge-base a3420c34483e), head bcdd3e693c55, approvals origin/main a3420c34483e, wp WP-0.1
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.4 s)
```

## CI
Workflow `aqis-lab-ci.yml` on commit `59162cc`, PR https://github.com/NasirAman-promcare/voice-bot-vad-harness/pull/9 (GitHub check runs, read 2026-10-03):

| Run | Job | Started (UTC) | Completed (UTC) | Conclusion |
| --- | --- | --- | --- | --- |
| 37122361388 (push) | `lab` | 12:16:59 | 12:20:51 | success |
| 37122361388 (push) | `harness-regression` | 12:17:01 | 12:18:12 | success |
| 37122374004 (pull_request) | `lab` | 12:17:15 | 12:21:09 | success |
| 37122374004 (pull_request) | `harness-regression` | 12:17:13 | 12:18:30 | success |

## Owner-run checks
None. The Tier 2 run itself was the owner's input (spec "Owner steps"). Nothing this WP builds runs on Colab or Oracle.

## audit-allow lines
None.

## Round 2 (audit round 1 fixes; approval "Round 2 Fixes")
Full record: `docs/progress/WP-0.1/FIXES.md`. F4 and F5 were accepted as debt: DEBT-028 and DEBT-029, target WP-0.9.

| Finding | New tests | Result |
| --- | --- | --- |
| F1 | `test_FR_0_1_02_cells_cite_their_own_row_and_column`; `test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column` (7 swaps, including swaps of equal values) | pass; each swap case failed before the fix |
| F2 | `test_FR_0_1_02_check_reports_uncited_numbers_in_every_section` (6 inserts) | pass; each failed before the fix |
| F3 | `test_FR_0_1_01_check_reports_each_inconsistency` (12 cases, R1 to R8) | pass; the R1 and R5 cases fail under the auditor's E6 and E10 mutations |
| F6 | — | "Test first" line corrected above (17 failed, 1 passed at `cb49333`) |
| F7 | `test_FR_0_1_01_check_reports_each_inconsistency[R8-listener-log-missing]` | pass; failed before the fix |

Commands and real output:
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_tier2_baseline.py -q -p no:cacheprovider
44 passed in 17.09s
$ .venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"
1856 passed, 55 deselected in 225.93s (0:03:45)
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1
Findings: 0
0 findings: OK (0.4 s)
```
Round 2 CI: recorded below after the push.
