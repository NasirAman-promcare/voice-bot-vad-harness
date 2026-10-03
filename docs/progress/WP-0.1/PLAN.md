# PLAN — WP-0.1 Tier 2 VAD transport baseline

Spec: `docs/specs/phase-0/WP-0.1-tier2-baseline.md`  ·  Planned by session: https://claude.ai/code/session_01NVq6FhCHSL6tz42EFj3VhC  ·  Date: 2026-10-03
Branch: `claude/practical-knuth-wsgvud`  ·  Base: `origin/main` at `6eb94ac`  ·  Depends on: none

## Summary
When this WP is done:
- `docs/baselines/tier2_vad/<date>/raw/` holds your Tier 2 outputs, checked against an agreed list of required items (R1 to R8 below).
- `docs/baselines/tier2_vad/<date>/SUMMARY.md` gives the setup, the VADs, the conditions and the headline metrics for each VAD operating point.
  - Every number in it cites its raw file and a field or line.
  - A derived number also shows its formula, its inputs and its rounding.
  - Nothing is estimated or explained away.
- Tests in `tests/aqis_lab/` re-derive every number in SUMMARY.md from the raw files and check that the raw folder is complete. A changed raw value or a missing raw file makes them fail.
- Nothing changes in `aqis_lab/` or `tools/`, and no harness file changes.

**Blocked now (BLK-015):**
- The raw folder does not exist yet (spec "Owner steps", step 2).
- You need to decide which Tier 2 run becomes the baseline (question 1).

## What I found in the repository (read-only inspection)
Nothing in the repository was changed. The only command that wrote anything was `bash aqis_lab/deploy/dev_bootstrap.sh`, which builds `.venv` (git ignores it). The other commands were reads and short scripts in the session scratchpad.

1. **No raw folder yet.**
   - `docs/baselines/tier2_vad/` exists neither on `main` (`6eb94ac`) nor on this branch.
   - `docs/baselines/` holds only `harness_tests_baseline.md`.

2. **A complete-looking Tier 2 run is already committed, but it was made with an older harness.**
   - `results/run_output/raw_evaluations.jsonl` came in with commit `bb0ed2e` (2026-09-23 12:01 UTC). It holds one Tier 2 run:
     - run ID `vad_eval_run_20260913_001_20260923_072436`;
     - records from 07:24:36 to 11:00:54 UTC;
     - 1 `run_context` record, 1,344 `scoring_clip` records and 1,344 `tier2_pipeline_latency` records, and no `clip_failure` record.
   - That is 224 clips for each of 6 operating points: `ten_vad`, `firered_vad` and `webrtc_vad_mode0` to `webrtc_vad_mode3`.
     - 224 is the 229 manifest clips minus 5 warm-up clips.
     - All 10 corpus categories are covered.
   - The same commit `bb0ed2e` also changed harness code. The run had already finished, so it was made with the harness as it was **before** those changes, not with the harness "exactly as it is":
     - `orchestrator.py`: the listener wait went from 30 s to 75 s;
     - `bots/listener_bot.py`: a timeout now raises an error instead of keeping the partial audio;
     - `webrtc_bridge/media_session.py`: closing now cancels pending tasks;
     - `reporting.py`: new summary fields, and a category F1 that can be empty.
   - The configuration used for that run is not recorded in the repository:
     - Before `bb0ed2e`, `config/run_config.yaml` said `tiers_to_run: [tier2]` with `corpus_category_filter: [clean speech, packet-loss/jitter]`, yet the run covered all 10 categories.
     - Since `bb0ed2e` the file says `tiers_to_run: [tier1]`.
   - No console log of that run is in the repository. `run.log` at the repository root is a Tier 1 run (2026-09-23, 11:22 UTC).

3. **The harness has no written Tier 2 run instructions.**
   - The spec's "Read first" names "the harness README and its Tier 2 run instructions". But `README.md` holds only the title (46 bytes, the same in every commit).
   - What does exist:
     - `python scripts/run_phase.py run tier2` runs `jupyter nbconvert --to notebook --execute --inplace notebooks/02_tier2_live_pipeline.ipynb` (`scripts/run_phase.py:206-216`).
     - That notebook calls `orchestrator.run_benchmark("config/run_config.yaml")`.
     - Tier 2 runs only if `tiers_to_run` includes `tier2`. The committed config says `tier1`, so a Tier 2 run needs that setting changed in the copy you run. The change is not committed.

4. **What a Tier 2 run writes, and where that can mislead.**
   - **Records.** `ResultsStore` appends to `<results_destination>/raw_evaluations.jsonl`, which defaults to `results/run_output/`. It never starts a new file, so a new run lands in the same file as the 2026-09-23 run.
   - **Report.**
     - `notebooks/03_report.ipynb` reads the fixed folder `results/run_output` and calls `reporting.generate_report(store)` with no run or tier filter. Its tables therefore combine every run in that store.
     - It shows the tables in the notebook and writes no other file.
     - Its "human-edited" section contains statements that are not measurements, for example "within 20–40ms". SUMMARY.md never cites them.
   - **Console log.**
     - `orchestrator.py` logs INFO to standard output only (`orchestrator.py:104-107`).
     - The log survives only if the notebook is saved with its outputs (`run_phase.py` does this in place) or the output is captured.
   - **Jingle logs.** `webrtc_bridge/bridge_config.yaml` points them at `results/run_output/jingle_stanzas_debug*.log`. They are appended across sessions: the committed ones run from 2026-09-20 to 2026-09-23.
   - **Run ID.** Each record's `run_id` is the configured `run_id` plus a start-time suffix (`orchestrator.py:215-218`).
   - **Second source.** The log line "Tier 2 Completed for '<adapter>': Evaluated N clips | Precision | Recall | F1" (`orchestrator.py:784`) is an independent second source for those numbers.

5. **How the harness defines its Tier 2 headline numbers** (`reporting.py`).
   - Precision, recall, F1 and the FPR and FNR rates come from tp, fp, tn and fn summed over the clips (`_aggregate_confusion_counts`, `reporting.py:117-147`):
     - precision = tp/(tp+fp);
     - recall = tp/(tp+fn);
     - F1 = 2PR/(P+R);
     - FPR = fp/(fp+tn);
     - FNR = fn/(fn+tp).
   - "FPR (Silence)" uses only `silence-only` clips, and "FNR (Quiet)" only `quiet/whispered speech` clips.
   - "Onset Latency" and "Offset Hangover" are means over clips of each clip's `mean_onset_latency_ms` and `mean_offset_hangover_latency_ms` (collected at `reporting.py:332-345`, averaged at `reporting.py:366-369`).
   - Rounding uses Python `round`: 3 decimals for rates, 1 for milliseconds.
   - The wall-clock pipeline latency (`mean_wallclock_pipeline_latency_ms`) is the most transport-specific measure. It is in the records but not in the report.

6. **`.gitignore` ignores `*.jsonl`** (line 12).
   - `git add` would silently skip `raw/raw_evaluations.jsonl`. Use `git add -f`, or upload through the GitHub web page.
   - `results/run_output/raw_evaluations.jsonl` is tracked despite this rule.
   - `.gitignore` is a guarded file, and changing it is outside this WP.

7. **The Jingle logs contain IP addresses.** The committed ones include:
   - `150.136.154.245`: the Oracle VM, also public through DNS;
   - Google Cloud addresses: `34.106.79.247`, `34.73.128.63`, `34.74.98.108` and `136.112.197.167`;
   - private addresses: `172.28.0.12`, `172.18.0.3`, `172.18.0.4` and `192.168.1.14`.

   None of them is a secret. Question 5 asks whether you want them in the baseline as they are.

8. **Where the bots ran is not recorded.**
   - The run's `python_version` 3.13.15 matches `docs/environment/colab_probe.txt`.
   - The logs show Google Cloud addresses.
   - Both suggest the bots ran on Colab, not on the Oracle VM. I will not infer this: the network description must say it.

9. **Data notes on the 2026-09-23 run.** These are facts; I make no judgement on them.
   - `mean_wallclock_pipeline_latency_ms` is negative in most clips for 5 of the 6 operating points, out of 207 clips with a value each:

     | Operating point | Clips with a negative value |
     | --- | --- |
     | `ten_vad` | 175 |
     | `webrtc_vad_mode0` | 204 |
     | `webrtc_vad_mode1` | 204 |
     | `webrtc_vad_mode2` | 203 |
     | `webrtc_vad_mode3` | 199 |
     | `firered_vad` | 0 |

   - The value is missing (null) in 17 clips per operating point.
   - `alignment_status` is `longer_than_ground_truth` in 657 of the 1,344 scored clips.
   - If this run becomes the baseline, SUMMARY.md reports these values exactly as recorded and does not correct or explain them (question 6).

10. **The gate needs a test for every FR ID, FR-0.1-03 included.**
    - Check (f) of `tools/audit/gate.py` fails a WP unless each FR ID appears in a collected test name under `tests/aqis_lab/`, in PLAN.md and in EVIDENCE.md.
    - Audit item A6 needs a named test to fail for each must-catch behaviour.
    - FR-0.1-03 says "No code".
    - WP-0.8, which was documents only, met the same need with tests under `tests/aqis_lab/` that read its documents (question 2).

11. **Other facts.**
    - No debt in `docs/progress/DEBT.md` targets WP-0.1.
    - `docs/baselines/` is not a protected path, and `tests/aqis_lab/` is LAB-OWNED.
    - The registry's baseline row is `CAP-BASE-001`, so the next ID is `CAP-BASE-002`.
    - The Build Plan and Blueprint in `docs/specs/sources/` say nothing more about this baseline.
    - `bridge_config.yaml` last changed on 2026-09-22 (`7ca96c9`), before the 2026-09-23 run.

12. **Starting state, recorded before any WP-0.1 work.**
    - `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` → `1812 passed, 55 deselected in 197.46s`.
    - `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` → 5 findings, all expected at this stage: no PLAN.md, no EVIDENCE.md, and no test named for FR-0.1-01, FR-0.1-02 or FR-0.1-03.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.1-01 | Check the raw folder against required items R1 to R8 and their content and consistency rules (see "Required raw items"; question 3). SUMMARY.md gets a "Raw inventory" table: file, the item it meets, bytes and SHA-256. If any item is missing or inconsistent, I append a `BLOCKERS.md` entry naming each gap and stop. I never reconstruct or fill in missing data, and no SUMMARY number is taken from an incomplete folder | `tests/aqis_lab/test_aqis_tier2_baseline.py`; `tests/aqis_lab/aqis_baseline_testutil.py` | `docs/capabilities/REGISTRY.md`: row `CAP-BASE-002` appended; `docs/progress/BLOCKERS.md`: entries appended only if a gap is found | `test_FR_0_1_01_raw_folder_has_every_required_item`, `test_FR_0_1_01_inventory_lists_every_raw_file`, `test_FR_0_1_01_raw_files_agree_on_the_run`, `test_FR_0_1_01_raw_folder_holds_no_audio`, `test_FR_0_1_01_check_reports_each_missing_item` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_1_01` |
| FR-0.1-02 | Write SUMMARY.md to the layout in "SUMMARY.md layout", with the headline metrics of question 4. Every number carries a source ID `[S<n>]`, which leads to a row of the "Sources" table. I extract each number with a read-only command recorded in `EVIDENCE.md`, and the tests recompute each one independently from the raw files. Where the report, the run log and the records give the same metric, all are cited and must agree. If they disagree, I stop and ask; I never pick one | `docs/baselines/tier2_vad/<date>/SUMMARY.md` | `REGISTRY.md`: the same row `CAP-BASE-002` | `test_FR_0_1_02_summary_has_every_section`, `test_FR_0_1_02_every_number_cites_a_source`, `test_FR_0_1_02_every_number_matches_its_cited_source`, `test_FR_0_1_02_derived_numbers_show_formula_inputs_and_rounding`, `test_FR_0_1_02_headline_metrics_cover_every_operating_point`, `test_FR_0_1_02_report_log_and_records_agree`, `test_FR_0_1_02_check_reports_a_changed_raw_value` | `.venv/bin/python -m pytest tests/aqis_lab -q -k FR_0_1_02` |
| FR-0.1-03 | Change only the files listed in "Files this WP touches". Nothing changes in `aqis_lab/`, `tools/`, `config/`, `requirements/`, `notebooks/`, `.github/` or any other harness path, and raw files are never edited after your commit. Checked by the gate (checks (a) to (d)), the branch file list in `EVIDENCE.md` and two tests | — | — | `test_FR_0_1_03_baseline_folder_holds_only_summary_and_raw`, `test_FR_0_1_03_raw_files_unchanged_since_inventory` | `git diff --name-only origin/main...HEAD` lists only the planned files; `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` exits 0 |
| AT-0.1-01 | The "Sources" table lets the auditor pick 5 numbers at random and check each one against its raw file by hand. For each kind of locator, `EVIDENCE.md` gives the read-only command that extracts the value | — | — | all FR-0.1-02 tests | the auditor's 5 checks; the fast suite; `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.1` |

## Design details

### Required raw items: the definition of "complete" (question 3)
The spec asks for "run configuration, network description, per-VAD metrics and logs". I propose this list. The Raw inventory in SUMMARY.md maps each item to your file, so file names are free. The names below are only examples.

| Item | What | Example file | Checks |
| --- | --- | --- | --- |
| R1 Run configuration | `run_config.yaml` exactly as used | `run_config.yaml` | Parses as YAML. `tiers_to_run` includes `tier2`. Its `run_id` plus `_` starts the records' run ID. `active_adapters`, `concurrency_mode`, `scoring_grid_ms`, `hardware_policy` and `tiers_to_run` equal the `run_context` record |
| R2 Bridge configuration | `bridge_config.yaml` exactly as used | `bridge_config.yaml` | Parses as YAML. Has every key of the committed `webrtc_bridge/bridge_config.yaml` |
| R3 Harness version | The repository state on the machine that ran the bots, taken before the run | `harness_version.txt`: output of `git rev-parse HEAD` and `git status --porcelain` | Has a 40-character commit. Lists no changed tracked file other than `config/run_config.yaml`, `results/run_output/` and the notebooks the run rewrites |
| R4 Network description | Written by you | `NETWORK.md` | Answers each point: where Jitsi ran (VM shape, region, Jitsi version); where the speaker bot and the listener bot ran; the path between them (public internet or not, any TURN relay); any impairment added, or "none"; the run's start and end time in UTC. I check that each point is answered, not that the answer is true |
| R5 Records | The run's per-clip records | `raw_evaluations.jsonl` | Every line is valid JSON. Exactly one `run_context` record. Every record carries that run ID, with no other run mixed in. Every operating point named in the records follows from `active_adapters` and `webrtc_aggressiveness_modes` |
| R6 Report | The harness report for this run | the executed `03_report.ipynb` with its outputs | Its "Discovered Run ID(s)" output is exactly this run. One summary-table row per operating point |
| R7 Run log | The console output from "Loaded run configuration" to "=== Benchmark Run '<run ID>' Completed …" | the executed `02_tier2_live_pipeline.ipynb` with its outputs, or a captured log | Names this run ID. Has one "Tier 2 Completed" line per operating point |
| R8 Jingle logs | The speaker and listener stanza logs | `jingle_stanzas_debug_speaker.log`, `jingle_stanzas_debug_listener.log` | Their time stamps cover the run, from the first to the last record time stamp |

Also:
- `raw/` holds no audio file (`.wav`, `.flac`, `.mp3`, `.ogg`, `.opus`, `.m4a`, `.webm`), so no audio with personal data can slip in.
- If the run has any `clip_failure` record, or fewer scored clips than the manifest minus the warm-up clips, I report it in `BLOCKERS.md` and ask whether this still counts as the "full" Tier 2 run, before writing SUMMARY.md.

### SUMMARY.md layout
1. **Run**: run ID, start and end time (UTC), harness commit, the machines it ran on.
2. **Setup**:
   - Jitsi host, bot hosts and network path, from NETWORK.md, cited by line;
   - Python and aiortc versions, from `run_context`;
   - Opus bitrate, DTX and FEC, from the bridge configuration;
   - concurrency mode, scoring grid, decision threshold and hardware policy, from the run configuration.
3. **VADs**: one row per operating point, with adapter ID, library version (`vad_library_version`) and WebRTC mode.
4. **Conditions**:
   - corpus manifest version hash;
   - clips per category (scored and in the manifest);
   - warm-up clips excluded;
   - network conditions as NETWORK.md states them.
5. **Headline metrics per VAD**: one table (question 4).
6. **Run health**: clips scored, clips failed by stage, packets, gaps and missing packets, and counts of null and negative latencies (question 6).
7. **Raw inventory**: R1 to R8, each with file, bytes and SHA-256.
8. **Sources**: one row per number, with ID, value as shown, file, locator, kind (direct or derived), and the formula with its inputs and rounding.

The text states facts only. It contains no ranking, no "better" or "worse", and no explanation of odd values.

**Citation rules:**
- **Direct, text file**: `line N`. The value appears on that line exactly as shown.
- **Direct, YAML**: a key path, for example `opus_bitrate_bps`.
- **Direct, JSONL**: a selector plus a field path, for example `record_type=run_context` → `payload.python_version`. The selector must match exactly one record.
- **Direct, notebook**: cell number, output number and line within that output.
- **Derived**: one formula from a fixed set (count, sum, mean, median, ratio of sums), over a selector and a field, with its rounding.
  - The median is the middle value, or the mean of the two middle values, as `numpy.median` computes it in `reporting.py`.
  - Rounding is Python `round(x, n)`, as `reporting.py` uses it.
- **Not counted as numbers**: digits inside identifiers in backticks (run ID, file names, commit, requirement IDs) and the fixed terms "Tier 2" and "WP-0.1".

### Headline metrics per VAD operating point (question 4)
| Metric | Cited directly from | Recomputed from the records (derived) |
| --- | --- | --- |
| F1, precision, recall | report summary table (R6); run log "Tier 2 Completed" line (R7) | Σtp, Σfp and Σfn over the operating point's `scoring_clip` records, with the `_aggregate_confusion_counts` formulas |
| FPR on silence-only clips | report "FPR (Silence)" | Σfp/(Σfp+Σtn) over `category = silence-only` |
| FNR on quiet/whispered clips | report "FNR (Quiet)" | Σfn/(Σfn+Σtp) over `category = quiet/whispered speech` |
| Onset latency, mean | report "Onset Latency" | mean of the per-clip `mean_onset_latency_ms` values that are not null |
| Offset hangover, mean | report "Offset Hangover" | mean of the per-clip `mean_offset_hangover_latency_ms` values that are not null |
| Onset and offset hangover, median | — | median of the same per-clip values (the harness's `live_onset_median_ms` and `live_offset_median_ms` definitions; computed but not shown in its table) |
| Wall-clock pipeline latency, mean and median | — | mean and median of the per-clip `mean_wallclock_pipeline_latency_ms` values that are not null |
| Clips scored | run log "Evaluated N clips" | count of `scoring_clip` records |
| Clips with no onset, clips with no resolved hangover | — | count of `tier2_pipeline_latency` records with `has_speech` true and a null mean value (the harness's `false_negative_clips_count` and `unresolved_hangover_clips_count` definitions) |

### How the tests read the baseline
- `tests/aqis_lab/aqis_baseline_testutil.py` holds the shared parsing and checking code:
  - it reads SUMMARY.md's sections and pipe tables;
  - it resolves each locator in the raw file;
  - it evaluates the fixed formula set;
  - it returns a list of problems from `check_baseline(folder)`.

  The tests and the self-tests on edited copies both use it.
- The tests check every dated folder under `docs/baselines/tier2_vad/`.
- Expected values always come from the raw files, never from SUMMARY.md:
  - JSONL and notebooks are read with `json`, YAML with `yaml` (PyYAML is already in the phase 0 lock);
  - no new dependency is needed.
- Two self-tests run the check on edited copies under `tmp_path` and must see it fail:
  - `test_FR_0_1_01_check_reports_each_missing_item`: delete each required item's file in turn. The check must name that item and file as missing (must-catch 2).
  - `test_FR_0_1_02_check_reports_a_changed_raw_value`: parametrised over one direct JSONL value, one YAML value, one cited log line and one input of a derived number (one clip's `metrics.tp`). The check must report the mismatch and name the source ID, the file and the locator (must-catch 1).
- All tests are in the fast suite, with no `network`, `gpu`, `colab` or `oracle` marker.

### Must-catch proof (planned)
Each break is made in a copy under `/tmp`, and the result is recorded in `EVIDENCE.md`.
1. "Every number in SUMMARY.md matches its cited raw file":
   - change one clip's `metrics.tp` in `raw_evaluations.jsonl` → `test_FR_0_1_02_every_number_matches_its_cited_source` fails and names the derived numbers that use it;
   - separately, change one number on a cited log line → the same test fails and names that number.
2. "A missing raw file is reported as missing, never filled in":
   - delete one raw file → `test_FR_0_1_01_raw_folder_has_every_required_item` fails and names it as missing;
   - every number citing that file also fails in `test_FR_0_1_02_every_number_matches_its_cited_source`, so no number stands without its source.

### Registry row (appended; no existing row changes)
| ID | Module | What it does |
| --- | --- | --- |
| CAP-BASE-002 | `docs/baselines/tier2_vad/<date>/SUMMARY.md` | Tier 2 VAD transport baseline: setup, VADs, conditions and headline metrics per operating point. Every number is cited to the committed raw outputs, and derived numbers show formula, inputs and rounding. Lists the FR-0.1-01, FR-0.1-02 and FR-0.1-03 tests |

### Files this WP touches (change budget)
- **New:**
  - `docs/baselines/tier2_vad/<date>/SUMMARY.md`;
  - `tests/aqis_lab/test_aqis_tier2_baseline.py`;
  - `tests/aqis_lab/aqis_baseline_testutil.py`;
  - `docs/progress/WP-0.1/PLAN.md`, `EVIDENCE.md`, and later `FIXES.md` if an audit needs it.
- **Appended or edited:**
  - `docs/capabilities/REGISTRY.md` (one row appended);
  - `docs/progress/STATUS.md` (the WP-0.1 row only);
  - `docs/progress/BLOCKERS.md` (entries appended).
- **Not touched:**
  - your `raw/` files;
  - every harness path;
  - `aqis_lab/`, `tools/`, `config/`, `requirements/`, `notebooks/` and `.github/`.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Your answer to question 1: which run is the baseline | FR-0.1-01 and FR-0.1-02 depend on it | In the approval |
| 2 | Raw outputs R1 to R8 committed to `main` under `docs/baselines/tier2_vad/<YYYY-MM-DD>/raw/`. `<YYYY-MM-DD>` is the run's UTC start date. Use `git add -f` for the `.jsonl` file (finding 6) | Spec "Owner steps" 2; FR-0.1-01 | Before `/wp-build WP-0.1` |
| 3 | `NETWORK.md` (R4), written by you | Only you know the network setup (finding 8) | Before `/wp-build WP-0.1` |
| 4 | Answers to questions 2 to 6 | They decide what the tests and SUMMARY.md contain | In the approval |

### Suggested steps for a new run (question 1 (a)); adjust as you need
Run these on the machine that runs the bots, at the repository root, with `main` checked out. Nothing here changes harness code.
1. Run `D=docs/baselines/tier2_vad/$(date -u +%F)/raw && mkdir -p "$D"`.
2. Run `{ git rev-parse HEAD; git status --porcelain; } > "$D/harness_version.txt"` (R3).
3. Move the old results aside, for example `mv results/run_output results/run_output_2026-09-23`. The new records and Jingle logs then start empty, and the report notebook, which always reads `results/run_output`, sees only the new run.
4. In your local `config/run_config.yaml` only, set `tiers_to_run: [tier2]` and keep `corpus_category_filter: []`. Then run `cp config/run_config.yaml webrtc_bridge/bridge_config.yaml "$D/"` (R1, R2).
5. Run `python scripts/run_phase.py run tier2`, then `cp notebooks/02_tier2_live_pipeline.ipynb "$D/"` (R7).
6. Run `python scripts/run_phase.py run report`, then `cp notebooks/03_report.ipynb "$D/"` (R6).
7. Run `cp results/run_output/raw_evaluations.jsonl results/run_output/jingle_stanzas_debug*.log "$D/"` (R5, R8).
8. Write `"$D/NETWORK.md"` (R4).
9. Put the harness back exactly as it was:

   ```
   rm -rf results/run_output
   mv results/run_output_2026-09-23 results/run_output
   git checkout -- config/run_config.yaml notebooks/02_tier2_live_pipeline.ipynb notebooks/03_report.ipynb
   ```

   Then confirm that `git status --porcelain` lists only `$D`.
10. Commit only `$D`: `git add -f "$D"`, then commit and push to `main`.

## Owner-run checks planned
None. The Tier 2 run itself is your input (spec "Owner steps"). Nothing that this WP builds runs on Colab or Oracle.

## Risks and questions
**Risks**
1. **A report built from a mixed store.** If the report and the records disagree, for example because the report combined runs, I stop and ask. I never choose one source over the other.
2. **A run that is not full.** A new run can lose clips to network failures, which are recorded as `clip_failure`. I report this before writing SUMMARY.md (see "Required raw items").
3. **The odd latencies may recur.** The negative wall-clock latencies of finding 9 may appear in a new run too, because the code that computes them has not changed since. SUMMARY.md reports them as recorded, and judging them is yours (question 6).
4. **Harness drift.** If the bots' machine runs a harness checkout other than `main`, R3 shows it. I then stop and ask, because the spec requires the harness "exactly as it is".
5. **File sizes.** About 3 MB of records, under 1 MB of Jingle logs, and a notebook with several hours of log output. All are far below GitHub's 100 MB file limit.

**Questions** (also in the closing message)
1. **Which run is the baseline?**
   - **(a) Recommended:** a new full Tier 2 run with today's harness on `main`, captured as in the suggested steps. This is what the spec asks for, and every required item can be captured.
   - **(b)** The 2026-09-23 run already in `results/run_output/`. This needs deviation D2, because that run used the harness before `bb0ed2e`. You must also supply, for that run:
     - the run configuration actually used;
     - the harness commit and local changes;
     - the console log (R7).

     None of these is in the repository. If any cannot be supplied, it is missing, and I stop again.
2. **Tests in a WP whose FR-0.1-03 says "No code".**
   - **(a) Recommended:** tests and one test helper only in `tests/aqis_lab/`, as WP-0.8 did. Nothing goes in `aqis_lab/` or `tools/`, and no harness file changes (deviation D1).
   - **(b)** No tests at all. Then gate check (f) and audit items A2 and A6 cannot pass, and you would have to accept that.
3. **Is R1 to R8 the right definition of "complete"?**
   - **(a) Recommended:** as listed.
     - R3 (harness version) and R7 (run log) go slightly beyond the spec's words. Without R3, nothing shows the harness was run "exactly as it is".
     - R5 must hold only this run, so nothing has to be filtered out.
   - **(b)** As listed but without R3 or R7. Say which.
   - **(c)** Your own list.
4. **Headline metrics.**
   - **(a) Recommended:** the table in "Headline metrics per VAD operating point".
   - **(b)** Only the report's summary-table columns, with no derived numbers.
   - **(c)** (a) plus the report's category F1 matrix and SNR table: about 90 more numbers, each cited.
5. **IP addresses in the Jingle logs** (finding 7).
   - **(a) Recommended:** commit the logs as they are. The same kind of logs is already on `main` in `results/run_output/`, and none of the addresses is a secret.
   - **(b)** Remove the addresses yourself before committing, and say so in NETWORK.md. SUMMARY.md then cites nothing from the edited text.
   - **(c)** Leave the Jingle logs out, which drops R8.
6. **Negative or null latencies.**
   - **(a) Recommended:** SUMMARY.md reports them exactly as recorded, with factual counts in "Run health", and no explanation.
   - **(b)** You want them investigated first. That is harness work, outside this WP, which allows no harness change, so it needs its own decision.

## Deviations
- **D1 (only if question 2 (a)):** this WP adds a test file and a test helper under `tests/aqis_lab/`, although FR-0.1-03 says "No code". I read FR-0.1-03 as "no product code (`aqis_lab/`, `tools/`) and no harness change". Reason: gate check (f), audit items A2 and A6, and `.claude/rules/30-testing-and-evidence.md` require a collected test named after each requirement ID, and a named test that fails for each must-catch behaviour.
- **D2 (only if question 1 (b)):** the baseline run was made with the harness before commit `bb0ed2e` (finding 2), not with the harness "exactly as it is". SUMMARY.md would state the commit actually used and list the `bb0ed2e` differences as facts, with sources.
- Otherwise none.
