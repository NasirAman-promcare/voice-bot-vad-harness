<!-- AQIS lab WP-0.9 FR-0.9-01 to FR-0.9-03. Tests read this file (tests/aqis_lab/test_aqis_phase0_memo.py with
tests/aqis_lab/aqis_memo_testutil.py): keep the section headings, the table columns, the quoted passages and the
backticked evidence links when editing. -->
# Phase 0 memo

## Scope
This memo closes phase 0 of the AQIS Test Lab: foundations and plumbing (`docs/specs/phase-0/00-PHASE-0-OVERVIEW.md`). It covers WP-0.0 to WP-0.8, which are all MERGED (`docs/progress/STATUS.md`), and the work of WP-0.9 itself (`docs/progress/WP-0.9/PLAN.md`). For the phase audit run inside WP-0.9, exit criterion E6 covers WP-0.0 to WP-0.8 (deviation D1, accepted in `docs/approvals/WP-0.9.md`). WP-0.9's own audit and merge close the phase.

## Exit criteria
| ID | Criterion | Status | Evidence | Note |
| --- | --- | --- | --- | --- |
| E1 | **Parity**: Vosk results on the smoke pack are identical on the cloud VM, Colab and Oracle: same transcript hashes, same WER. | MET | `data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar`, `data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar`, `data/runs/phase0-smoke/phase0-smoke-oracle-20261002T141937Z.tar` (made at commits `0a534ce` and `7c27dd5`, one CPU lock); the three parity outputs in `docs/runs/PHASE0_SMOKE.md`; `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` repeats the comparison on every test run | All three pairs: `parity: identical` for the Vosk batch and real-speed transcripts and both score tables. Parakeet runs on Colab only, so parity names it and compares nothing for it. |
| E2 | **Resumability**: a run killed partway resumes without redoing finished shards, on the cloud VM (automated test) and on Colab (owner check). | MET with note | Cloud VM: `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing`, `test_FR_0_5_06_kill_during_result_write_never_counts`. Colab: `docs/progress/WP-0.5/OC-0.5-02_runner.log`, accepted as E2's Colab evidence in `docs/approvals/WP-0.9.md` (question 9) | On Colab the run stopped cleanly after two shards (`--max-shards 2`), the runtime was deleted, and the next session skipped both finished shards (marker verified) and computed the other four. It was not killed in the middle of a shard; the owner accepted this check as it is. |
| E3 | **Traceability**: any score row leads back to its run card, pack manifest version, clip, git commit and lock hash. | MET | `test_FR_0_6_03_trace_prints_run_card_manifest_clip_commit_lock`, `test_FR_0_6_03_trace_prints_the_rows_own_commit_and_lock_hash`, `test_FR_0_6_03_rows_of_two_run_cards_trace_to_their_own_card`; every stored smoke row traced in each bundle (`docs/progress/WP-0.7/EVIDENCE.md`, "Owner-run checks: results") | The smoke traced 225 rows on the cloud VM, 390 on Colab and 225 on Oracle (each bundle's `BUNDLE.json`). The phase audit traces five more rows of its own choice. |
| E4 | **Baseline**: the Tier 2 VAD transport baseline is committed with its summary. | MET | `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md`, `docs/baselines/tier2_vad/2026-10-03/raw/raw_evaluations.jsonl`, `docs/progress/WP-0.1/AUDIT.md`; `test_FR_0_1_02_every_number_matches_its_cited_source`, `test_FR_0_1_03_raw_baseline_files_are_never_editable` | Every number in the summary cites the owner's raw outputs. The raw files are owner-only (`[NEVER]` in `docs/process/PROTECTED_PATHS.txt`, DEBT-028). |
| E5 | **Licences**: every smoke clip has a licence entry; owner recordings carry a consent reference. | MET with note | `data/packs/smoke/v1/LICENCES.md`, `data/packs/smoke/v1/manifest.json`, `test_FR_0_4_07_committed_licences_cover_committed_manifest`, `docs/approvals/WP-0.4.md` | Phase 0 has no owner recordings: the owner replaced them with 10 synthetic TTS clips that "need no consent reference" (`docs/approvals/WP-0.4.md`). The consent-reference rules and their tests stay for the phase 1 campaign recordings. |
| E6 | **Governance**: every WP is AUDIT-PASS and MERGED; CI is green on `main`; the harness regression baseline is unchanged. | MET with note | `docs/progress/STATUS.md`; `docs/progress/WP-0.0/AUDIT.md` to `docs/progress/WP-0.8/AUDIT.md` (each "Verdict: PASS"); CI on main at `699acd5`: [run 373](https://github.com/NasirAman-promcare/voice-bot-vad-harness/actions/runs/37140171102), jobs lab and harness-regression green; `docs/baselines/harness_tests_baseline.md`, `test_FR_0_0_11_regression_check_accepts_repository_baseline` | WP-0.0 to WP-0.8 are AUDIT-PASS and MERGED. WP-0.9 is the review itself (deviation D1): its own audit and the owner's merge complete E6. |

## Decisions taken
The owner's decisions that shape phase 0's results, each quoted from its approval file on `main`.

| Decision | Approval | Quote |
| --- | --- | --- |
| No torch in the harness environment | `docs/approvals/WP-0.0.md` | "R2-3: option A. Do not install torch; the provisioning report must list it as "not installed, decision R2-3"." |
| Harness provisioning platforms | `docs/approvals/WP-0.0.md` | "F16 decision: harness provisioning supports Debian or Ubuntu on x86_64 only." |
| The Tier 2 baseline run | `docs/approvals/WP-0.1.md` | "Question 1: a new full Tier 2 run with today's harness, captured with the plan's owner steps, with the old results moved aside first." |
| Synthetic TTS clips instead of owner recordings in the smoke pack | `docs/approvals/WP-0.4.md` | "the 10 "owner" clips are replaced by 10 synthetic TTS clips in data/tts_smoke/ (category "tts", source "tts"), generated with hexgrad/Kokoro-82M as recorded in data/tts_smoke/GENERATION.md." |
| Synthetic clips never judge models | `docs/approvals/WP-0.4.md` | "They must never be used to judge or compare models." |
| Colab compute-unit rates | `docs/approvals/WP-0.5.md` | "Colab unit rates from Build Plan (March 2026): cpu: 0.08 units/hr, Tesla T4: 1.19 units/hr, NVIDIA L4: 1.71 units/hr, NVIDIA A100-SXM4-40GB: 5.40 units/hr." |
| Oracle cores for timing and batch runs | `docs/approvals/WP-0.6.md` | "Core reservation policy: reserve highest-numbered half of physical cores (cores 2-3) for timing runs, keeping batch runs on cores 0-1." |
| The VAD in the smoke run | `docs/approvals/WP-0.7.md` | "Question 1: WebRTC VAD, mode 2, 20 ms frames (webrtc_vad_mode2 through the harness registry)." |
| Deterministic Vosk across clips | `docs/approvals/WP-0.7.md` | "Approved: the Vosk adapter reseeds the C library random generator with 1 before every clip, recorded as c_rand_seed_per_clip: 1 in every Vosk run card." |
| Harm-rate target (recorded as the rate only, below 2 %; the decision rule moves to WP-4.5, DEBT-025) | `docs/approvals/WP-0.8.md` | "DECISION: harm-rate = HR-B" |
| Practical margin | `docs/approvals/WP-0.8.md` | "DECISION: margin = PM-B" |
| Timing budget | `docs/approvals/WP-0.8.md` | "DECISION: timing-budget = TB-B" |
| Gate escalation limit | `docs/approvals/WP-0.8.md` | "DECISION: gate-escalation = GE-B" |
| Retention of campaign recordings | `docs/approvals/WP-0.8.md` | "DECISION: retention = 3 years from the date of recording, after which all voice recordings are permanently deleted." |
| Speaker IDs and consent references | `docs/approvals/WP-0.8.md` | "Speaker ID is ca-sNNN (pseudonymous) and consent reference is ca-cNNN. Signed consent forms kept offline by owner." |
| How the phase audit runs inside WP-0.9 | `docs/approvals/WP-0.9.md` | "Order: build, then /phase-audit 0 on this branch, then the memo links its report, then /wp-audit WP-0.9, then merge. E6 covers WP-0.0 to WP-0.8 (deviation D1)." |
| Untestable debt closed as recorded limits | `docs/approvals/WP-0.9.md` | "K11.5b, DEBT-016 and DEBT-009 closed as recorded permanent limits." |

## Open issues
Debt still open (`docs/progress/DEBT.md`):
- DEBT-025: the decision rule (method and confidence) behind the harm-rate target is undecided; moved to WP-4.5 by the owner.
- DEBT-027: wall-clock pipeline latencies in the Tier 2 baseline are estimated from the first packet, so some look negative; the fix is harness work for the phase 2 VAD timing work.

Recorded permanent limits, closed by the owner's ruling (`docs/approvals/WP-0.9.md`, question 5):
- DEBT-009 permanent limit: no real input makes the normaliser exceed its pass limit, so `score`'s handling of a `NormalisationError` has no test.
- DEBT-016 permanent limit: two doctor runs within one second fail on the second, because report names have one-second resolution (FR-0.5-02).
- DEBT-005 K11.5b permanent limit: the bootstrap's final Python check alone has no test.

Other open points:
- Two Colab GPU sessions are not in the unit log: the T4 smoke run behind `data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar` and the `--gpu` bootstrap of `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu.txt`. The owner recorded them as unmetered (`docs/approvals/WP-0.9.md`).
- Some owner-run results are committed as one-line summaries, not full command output: `docs/progress/WP-0.7/OC-0.7-01_colab.txt`, `docs/progress/WP-0.7/OC-0.7-02_oracle.txt` and the three `docs/progress/WP-0.8/OC-0.8-0*` notes. The bundles themselves carry the WP-0.7 results.
- The audit gate's test index reads pytest's default collection rules, but not custom collection hooks in a `conftest.py`, plugins or pytest ini options (`docs/tools/AUDIT_GATE.md`). The repository uses none of them.
- No blocker is open (`docs/progress/BLOCKERS.md`).

## Lessons for the process
Observations from the records; changing the process is the owner's decision.

1. Audits converge once they are bounded. WP-0.0 needed 9 rounds, most of them under protocol version 1; after version 2 bounded the breaks (`docs/process/AUDIT_PROTOCOL.md`), every later WP passed in 2 to 4 rounds (table below, read from each `AUDIT.md`).
2. Approval files are read by machines, so their exact form matters: an approval with a bulleted status line was ignored (BLK-001), and `ALLOW-EDIT` lines that named other files than the plan needed stopped a build (BLK-017) (`docs/progress/BLOCKERS.md`).
3. A spec that cites outside documents needs them in the repository: WP-0.8 could not start until the blueprint and Build Plan were committed (BLK-013, `docs/specs/sources/AQIS_Test_Lab_Build_Plan.md`).
4. A protection line takes effect only in the right section: the raw-baseline line was first placed under `[LAB-OWNED]`, where the hooks read it as editable. A test now asks both parsers (`docs/progress/WP-0.9/PLAN.md`, finding 5; `tests/aqis_lab/test_aqis_debt_wp09.py`).
5. Owner-run checks are most useful as full command output committed before the merge: WP-0.7's notes are one-line summaries, and WP-0.8 was merged with its checks still pending (`docs/progress/WP-0.7/EVIDENCE.md`, `docs/progress/WP-0.8/EVIDENCE.md`).
6. Intermittent CI failures had real causes each time: git maintenance racing fixture repositories (BLK-011), Arrow buffers released at interpreter exit (BLK-012) and a parity process that sometimes never exited (`docs/progress/WP-0.7/EVIDENCE.md`). Root-cause fixes, not reruns, kept CI trustworthy.
7. The unit log meters only sessions started through the launcher cells; Colab work run another way goes unmetered (`docs/progress/WP-0.9/OC-0.9-01_units.csv`, BLK-017).
8. The lab's fast suite needs full git history, because some tests read historical commits; a shallow session clone fails one test until it is unshallowed (`docs/progress/WP-0.6/AUDIT.md`; `docs/progress/WP-0.9/EVIDENCE.md`).

| WP | Audit rounds | Record |
| --- | --- | --- |
| WP-0.0 | 9 | `docs/progress/WP-0.0/AUDIT.md` |
| WP-0.1 | 4 | `docs/progress/WP-0.1/AUDIT.md` |
| WP-0.2 | 3 | `docs/progress/WP-0.2/AUDIT.md` |
| WP-0.3 | 3 | `docs/progress/WP-0.3/AUDIT.md` |
| WP-0.4 | 2 | `docs/progress/WP-0.4/AUDIT.md` |
| WP-0.5 | 3 | `docs/progress/WP-0.5/AUDIT.md` |
| WP-0.6 | 2 | `docs/progress/WP-0.6/AUDIT.md` |
| WP-0.7 | 2 | `docs/progress/WP-0.7/AUDIT.md` |
| WP-0.8 | 3 | `docs/progress/WP-0.8/AUDIT.md` |

## Phase 1 prerequisites

### Campaign A recruiting status
The owner's statement (`docs/approvals/WP-0.9.md`, question 4):

> "Campaign A: not started: 0 of 22 recruited, 0 consents signed, 0 sessions recorded, quiet/noise split 0/0."

The consent form, recording guide and session form are ready and reviewed (`docs/recording/CONSENT_FORM.md`, `docs/recording/RECORDING_GUIDE.md`, `docs/recording/SESSION_FORM.md`, `docs/progress/WP-0.8/OC-0.8-02_wording_review.txt`).

### Pack v1 plan
"Pack v1" means the phase 1 packs: the Calibration pack and the Campaign A pack (`docs/approvals/WP-0.9.md`, question 6). This plan states only what the sources fix; everything else is the owner's decision.

What the sources fix:
- Phase 1 builds two packs: "Calibration pack: 2,000 synthetic clips" and "Campaign A: about 1,750 recorded turns" [Build Plan § Phases].
- Campaign A: 22 speakers, 80 prompts each in seven families, own phones, half quiet rooms and half everyday noise, about 1,760 turns [Build Plan § Campaign A].
- Recordings arrive as one archive per speaker session, keep the phone's original, and are converted to 16 kHz mono 16-bit PCM WAV; file names follow `<speaker-id>-<family-id>-<NN>.wav` (`docs/recording/RECORDING_GUIDE.md`).
- Only the registry's owner and campaign importers may produce campaign rows, and each row needs a consent reference that resolves to a file in the repository (`docs/data/REGISTRY_FORMAT.md`).
- Packs are built, verified and licensed by the phase 0 tools from a pack spec, as the smoke pack was (`packs/specs/smoke_v1.yaml`, `docs/data/SMOKE_PACK.md`).
- Recordings are kept for 3 years from the date of recording (`docs/approvals/WP-0.8.md`).

Open decisions for the phase 1 specs:
- [OWNER DECIDES: how the 2,000 synthetic calibration clips are made: the speech model or models, the voices, and their licences]
- [OWNER DECIDES: the categories of the Calibration pack and the number of clips in each]
- [OWNER DECIDES: whether the Campaign A pack holds every recorded turn or a selection, and how it is split, for example by speaker]
- [OWNER DECIDES: the pack names and versions, and where the built packs are stored]
- [OWNER DECIDES: what the consent-reference file in the repository holds for each speaker, given that signed forms stay offline]

### Colab compute units used so far
From the owner's copy of the unit log, `docs/progress/WP-0.9/OC-0.9-01_units.csv` (rates from `config/aqis_lab/colab_rates.yaml`; each row's hours and estimate are recomputed by `test_FR_0_9_02_unit_log_copy_is_consistent`):

| Runtime | Sessions | Hours | Estimated units |
| --- | --- | --- | --- |
| cpu | 1 | 0.0021 | 0.0002 |
| Tesla T4 | 1 | 0.0363 | 0.0432 |
| Total | 2 | 0.0384 | 0.0434 |

The owner's budget and the sessions the log does not hold (`docs/approvals/WP-0.9.md`):

> "Budget: 50 Colab units a month (Google AI Plus), planned use 40 of them."

> "the Colab T4 smoke run (14:01Z, ~374 s) and OC-0.8-03 bootstrap are noted as unmetered sessions."

## Phase audit
Report: `docs/progress/PHASE-0-AUDIT.md`

Verdict: pending (`/phase-audit 0` has not run yet)
