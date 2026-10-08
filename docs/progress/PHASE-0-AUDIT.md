# Phase 0 audit

Auditor: wp-auditor (`/phase-audit 0`) · Date: 2026-10-04 · Commit audited: `079571e147527f395782611d3f6cca9bd7c7f4a3` (branch `claude/great-heisenberg-h85gm9`) · Previous audited commit: first phase audit · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 · MAJOR: 0 · MINOR: 4 (open 4; none blocks)

All six exit criteria are met. E2, E5 and E6 carry notes the owner has already ruled on. I checked the evidence myself, without relying on the builder's records:
- Phase 0's results are identical on the cloud VM, Colab and Oracle, by my own comparison that does not use the lab's `parity` code.
- A fresh run at the audited commit matches all three.
- Re-running a committed run card at its own commit gives byte-identical result rows.
- Five random result rows trace completely.
- The harness regression baseline is unchanged.
- No Claude commit touched a guarded or owner-only path during the phase.

The four findings are gaps in the records, not in behaviour. None of them can make a check report success wrongly.

## Scope
- This audit runs inside WP-0.9, as the approval orders (`docs/approvals/WP-0.9.md`, Q1): build, then this audit on the branch, then the memo links this report, then `/wp-audit WP-0.9`, then merge. As accepted in deviation D1, E6 covers WP-0.0 to WP-0.8.
- **Not in scope:** the code audit of WP-0.9 itself. That means its must-catch breaks (A6) and the exploratory breaks on its changes to `tools/audit/gate.py` and `aqis_lab/contracts/validate.py`. They belong to `/wp-audit WP-0.9`.
- **Clone.** I made a fresh, full clone of the branch:
  - command: `git clone --branch claude/great-heisenberg-h85gm9 https://github.com/NasirAman-promcare/voice-bot-vad-harness /tmp/phase0-audit`;
  - HEAD `079571e`, the same as `origin/claude/great-heisenberg-h85gm9`;
  - `git rev-parse --is-shallow-repository` gives `false`; 381 commits.
- I ran nothing that changes the system. The harness provisioning's `system` step (which can call `apt-get`) was skipped; see step 6.

## Step 1: work packages
Each WP's `AUDIT.md` says `## Verdict: PASS`, and each has status MERGED in `docs/progress/STATUS.md`. For each one I checked three things:
- the PR is merged (GitHub REST API, `pulls?state=all`);
- the audited commit is an ancestor of `origin/main` (`git merge-base --is-ancestor`);
- what was merged after the audited commit (`git log` and `git diff` from the audited commit to the PR head, outside `docs/progress` and `docs/approvals`).

| WP | Verdict | Commit audited | PR, merged | Merged after the audited commit |
| --- | --- | --- | --- | --- |
| WP-0.0 | PASS | `2588a23` | #1, 2026-09-27 | the audit record only |
| WP-0.1 | PASS | `58865d4` | #9, 2026-10-03 | the audit record only |
| WP-0.2 | PASS | `53d4be7` | #2, 2026-09-27 | the audit record only |
| WP-0.3 | PASS | `050bbf4` | #3, 2026-09-27 | the audit record only |
| WP-0.4 | PASS | `507a1bf` | #4, 2026-09-27 | the audit record only |
| WP-0.5 | PASS | `f3bde36` | #5, 2026-09-28 | the audit record; the owner's Colab reports (`59a78ec`) |
| WP-0.6 | PASS | `3501ca8` | #6, 2026-09-30 | the audit record; the owner's Oracle reports (`4497623`) |
| WP-0.7 | PASS | `93b1ad4` | #7, 2026-10-02 | the audit record; the owner's Colab and Oracle bundles and notes (`d2d79e5`, `bbff98d`); OC-0.7-03 (`db6dabd`): the parity reports in `docs/runs/PHASE0_SMOKE.md`, a header-only change to `aqis_lab/commands/parity.py`, its registry row, and the new test `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` |
| WP-0.8 | PASS | `8dc69d4` | #8, 2026-10-03 | the audit record; the DEBT-026 row |

**Exceptions:**
- WP-0.9 is the review itself (D1). It is IN-BUILD.
- No WP audit covered the test added by OC-0.7-03. Because it is E1's standing evidence, I tested it with exploratory break X1 below, and it catches a real transcript difference.

## Step 2: clean install, full lab suite, smoke command
All commands below ran in `/tmp/phase0-audit`.

- **Install**, as documented (`CLAUDE.md`):
  - command: `bash aqis_lab/deploy/dev_bootstrap.sh`;
  - output: `OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef` (uv 0.8.17).
- **Full lab suite** (fast, slow and network; everything except the gpu, colab and oracle markers):
  - command: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not gpu and not colab and not oracle" -p no:randomly --junitxml=…`;
  - output: `1971 passed, 7 deselected in 1706.23s (0:28:26)`;
  - JUnit totals: tests 1971, failures 0, errors 0, skipped 0;
  - `git status --porcelain` was empty afterwards.
- **The 7 deselected tests** are the machine-only tests:
  - `test_FR_0_5_01_colab_runtime_detected`, `test_FR_0_5_02_colab_doctor_passes_on_colab`, `test_FR_0_5_07_colab_session_recorded`;
  - `test_FR_0_7_03_parakeet_transcribes_on_gpu`, `test_FR_0_7_06_gpu_compute_delay_on_colab_t4`;
  - `test_FR_0_6_01_setup_passes_on_oracle`, `test_FR_0_6_04_real_oracle_pinning`.

  The owner's reports cover them: `docs/progress/WP-0.7/OC-0.7-01_colab.txt` ("pytest -m 'colab or gpu' (5 passed)") and `docs/progress/WP-0.7/OC-0.7-02_oracle.txt` ("pytest -m oracle (2 passed)").
- **Phase smoke** (AT-0.7-01):
  - command: `.venv/bin/python -m aqis_lab phase0 smoke --target cloud`;
  - exit 0, last line: `smoke complete: bundle …/phase0-smoke-cloud-20261004T071549Z (23 files, 225 rows traced), archive …/phase0-smoke-cloud-20261004T071549Z.tar, 155.6 s` (NFR-0.7-01 allows 900 s).
- **Contracts check on the fresh results:**
  - the three run cards: `run_card: 1 record, 1 valid, 0 invalid` each;
  - the three event logs: `event: 894 records, 894 valid, 0 invalid`, `event: 462 records, 462 valid, 0 invalid` and `event: 81 records, 81 valid, 0 invalid`;
  - the pack manifest: `manifest: 1 record, 1 valid, 0 invalid`;
  - `pack verify data/packs/smoke/v1`: `pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`.
- **Parity of the fresh bundle** against each committed bundle (cloud, Colab, Oracle): `parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)`, exit 0 each time.
- **Audit gate:**
  - command: `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.9`;
  - output: `Findings: 0`, `0 findings: OK (0.5 s)`.
- **CI:**
  - On the audited commit `079571e`: run 380 (id 37143974245), jobs `lab`, `lab-network` and `harness-regression` all success.
  - On `main` at `699acd5`: run 373 (id 37140171102), jobs `lab` and `harness-regression` both success.

## Step 3: exit criteria
Every evidence link in the memo's E1 to E6 rows resolves. I checked each one myself:
- each path exists at HEAD;
- each commit passes `git cat-file -e`;
- each test name is in `pytest --collect-only`;
- the CI URL is run 373 above.

Every test the memo cites as evidence passed in my full suite run.

| ID | Status | My evidence | Note |
| --- | --- | --- | --- |
| E1 Parity | MET | See "E1 detail" below the table. | The cloud bundle was made at `0a534ce`, and the Colab and Oracle bundles at `7c27dd5`, all with the same CPU lock `87a1cc34c6d4`. The fresh run at `079571e` is identical too. |
| E2 Resumability | MET with note | See "E2 detail" below the table. | It was not killed in the middle of a shard. The owner accepted this run as E2's Colab evidence knowing that (`docs/approvals/WP-0.9.md`, Q9). The remaining untested case is a crash during a write on Drive's FUSE mount on Colab. The cloud test covers that logic on local disk only. |
| E3 Traceability | MET | Step 4: five random rows, each traced and each link checked against the source files. | — |
| E4 Baseline | MET | `docs/baselines/tier2_vad/2026-10-03/SUMMARY.md` and the ten `raw/` files, which the owner committed (`e3786b5`). The hook's own parser (`.claude/hooks/_protected.py`, `classify`) gives `NEVER` for `raw/run.log` and `raw/raw_evaluations.jsonl`. `test_FR_0_1_02_every_number_matches_its_cited_source` and `test_FR_0_1_03_raw_baseline_files_are_never_editable` pass. WP-0.1's AUDIT.md says PASS. | — |
| E5 Licences | MET with note | `data/packs/smoke/v1/manifest.json`: all 60 clips carry a licence, and all 60 clip IDs appear in `LICENCES.md`. 0 clips have source `owner` or `campaign`. `consent_ref` is null for every clip. `test_FR_0_4_07_committed_licences_cover_committed_manifest` passes. | Phase 0 has no owner recordings: the owner replaced them with 10 TTS clips (`docs/approvals/WP-0.4.md`), so the consent half has nothing to check. |
| E6 Governance | MET for WP-0.0 to WP-0.8 (D1) | Step 1 (all PASS and MERGED). CI is green on `main` at `699acd5` (run 373). The harness regression is unchanged (step 6). | WP-0.9's own audit and merge complete E6. |

**E1 detail.** The three committed bundles exist: `data/runs/phase0-smoke/phase0-smoke-{cloud-20260930T170440Z,colab-20261002T140101Z,oracle-20261002T141937Z}.tar`. The owner committed the Colab and Oracle bundles (`d2d79e5`, `bbff98d`). I checked them with my own script, without the lab's `parity` code:
- Every file in each bundle matches its `BUNDLE.json` SHA-256 and size: 0 mismatches, 0 files extra or missing.
- I recomputed each row's `text_sha256` from its `text`.
- Across x86_64 (cloud), x86_64 with a T4 (Colab) and aarch64 Neoverse-N1 (Oracle):
  - the per-clip text hashes are identical for `vosk-batch` (60 clips) and `vosk-realspeed` (5 clips);
  - every non-timing field of every row is identical;
  - every per-clip WER is identical (80 and 20 rows);
  - the corpus summaries are identical. For example, the natural subset's disfluency-aware corpus WER is 0.10740 in all three.
- 50 of the 60 batch transcripts are non-empty.

**E2 detail.**
- **Cloud VM:** `test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing` and `test_FR_0_5_06_kill_during_result_write_never_counts` pass.
- **Colab:** `docs/progress/WP-0.5/OC-0.5-02_runner.log` (owner commit `59a78ec`) shows:
  - session 1 `stopped after 2 computed shard(s) (--max-shards 2)`;
  - session 2 skipped shards 00000 and 00001 with `marker verified` and the same results SHA-256 as session 1;
  - session 2 then computed the other 4 shards.

**Owner-run reports (Colab, Oracle).** Each owner-run check of the phase has a committed result:
- WP-0.0: OC-0.0-01, `OWNER_VERIFY_COLAB_WP-0.0_*.md`;
- WP-0.5: OC-0.5-01 (doctor JSON) and OC-0.5-02;
- WP-0.6: OC-0.6-01 and OC-0.6-02;
- WP-0.7: OC-0.7-01, OC-0.7-02 and OC-0.7-03;
- WP-0.8: OC-0.8-01 to OC-0.8-03;
- WP-0.9: OC-0.9-01.

There are two caveats:
- F2: OC-0.5-01's test output file was never committed; a later owner report covers the result.
- F3: the WP-0.8 notes are one-line summaries, and OC-0.8-03 does not show the GPU-lock line.

No report is missing outright.

## Step 4: traceability
**Population.** I made a scratch store of every run and score folder of the three committed bundles with `results add`. It holds 840 rows (225 cloud, 390 Colab, 225 Oracle), equal to each `BUNDLE.json` `traced_rows`.

**Sample.** I drew five rows with Python `random.Random(504765013).sample` (the seed came from `secrets.randbits(32)`).

**Checks on each row.** `python -m aqis_lab trace <row>` exited 0 for all five. I then checked each link against the files myself:
- the row ID recomputes from its identity object (SHA-256 of canonical JSON);
- the stored run card is byte-identical to the bundle's `run_card.json`;
- the card's `pack` is `smoke` `1.0.0`, and its `pack.sha256` equals the SHA-256 of the committed manifest's canonical JSON;
- the clip is in the manifest;
- for score rows, `ref_sha256` equals the SHA-256 of the manifest transcript;
- the commit exists, is clean and equals the bundle's commit;
- the lock SHA-256 equals the SHA-256 of that lock file at that commit, as `git show` prints it.

| Row | Kind | Machine, task | Clip | Run card | Commit | Lock | All checks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `b8b4f1c34712…` | score (disfluency_aware) | Colab, parakeet-offline | `smoke-mix-08` | `7b4eef66a747…` | `7c27dd5` | `phase0-gpu.txt` `837342085aed` | pass |
| `187d8e1555b7…` | score (disfluency_aware) | Colab, vosk-batch | `ls-test-clean-1221-135767-0014` | `daadff54bb72…` | `7c27dd5` | `phase0-gpu.txt` `837342085aed` | pass |
| `d02b669f085c…` | score (disfluency_aware) | Colab, parakeet-offline | `ls-test-other-6432-63723-0046` | `7b4eef66a747…` | `7c27dd5` | `phase0-gpu.txt` `837342085aed` | pass |
| `aea8e803f131…` | run-result | Oracle, vosk-batch | `tts-smoke-01` | `24f9e3e1e4d1…` | `7c27dd5` | `phase0.txt` `87a1cc34c6d4` | pass |
| `78fcd2c61947…` | run-result | Oracle, vosk-batch | `ls-test-clean-6829-68771-0030` | `24f9e3e1e4d1…` | `7c27dd5` | `phase0.txt` `87a1cc34c6d4` | pass |

**GPU environments.** A run card from an environment with the GPU extras records only `phase0-gpu.txt`. The CPU lock is still bound: `requirements/aqis_lab/phase0-gpu.in` at `7c27dd5` reads `# compiled-against: requirements/aqis_lab/phase0.txt sha256 87a1cc34c6d4…`, and `test_FR_0_7_03_gpu_lock_header_binds_cpu_lock_sha256` keeps it equal. The documentation points to the wrong file for this binding (F4).

## Step 5: reproducibility
**The run card.** I re-ran the committed cloud `vosk-batch` run card `5eb8cb06f90d…`: commit `0a534ce`, lock `87a1cc34c6d4`, pack `90df3820e368`, model `30f26242c4eb`, seed 0.

**How.** I made a worktree at `0a534ce`, ran `dev_bootstrap.sh` from that commit's own lock (same hash), then ran `phase0 smoke --target cloud --model-cache <the clone's verified cache>`. It exited 0 in 100.3 s.

**The new card.** It is `dfabe828a8e4…`. It differs from the committed card only in `created_utc`, `run_card_id` and `machine.python_version` (3.13.14 instead of 3.13.12).

The table gives the SHA-256 prefixes:

| Result | Committed (`0a534ce`) | Re-run (`0a534ce`) | Fresh (`079571e`) |
| --- | --- | --- | --- |
| `vosk-batch` rows without `run_card_id` | `60c7d6b31628` | `60c7d6b31628` | `60c7d6b31628` |
| `harness-vad` rows without `run_card_id` | `59d376b53077` | `59d376b53077` | `59d376b53077` |
| `vosk-realspeed` rows without timing fields | `e4bd426900b9` | `e4bd426900b9` | `e4bd426900b9` |
| `vosk-batch-natural` score rows without `run_card_id` | `886bbdc9fa0a` | `886bbdc9fa0a` | `886bbdc9fa0a` |
| `vosk-batch-natural` corpus summary (`variants`) | `1ed825f9ca71` | `1ed825f9ca71` | `1ed825f9ca71` |
| `vosk-batch-synthetic-tts` score rows without `run_card_id` | `042888905a80` | `042888905a80` | `042888905a80` |
| `vosk-batch-synthetic-tts` corpus summary (`variants`) | `7afd4ece6b16` | `7afd4ece6b16` | `7afd4ece6b16` |

The whole `results.jsonl` files differ, but only because every row carries its `run_card_id`, and the run card contract includes `created_utc`. The timing fields of `vosk-realspeed` are wall-clock measurements, so they differ by design.

## Step 6: regression and protected paths
**Provisioning.**
- Command: `bash aqis_lab/deploy/harness_provision.sh --steps python,corpus,weights,verify`.
- Output: `RESULT: PASS`, with platform, python, ten-vad, imports, corpus, weights and git-status all PASS, and torch `INFO` (not installed, decision R2-3).
- I skipped the documented `system` step because an auditor must not run `apt-get`. Its three packages (`git-lfs`, `libc++1`, `libopus0`, from `config/aqis_lab/harness_assets.json`) were checked read-only with `dpkg-query -W`: each is `install ok installed`, so that step would have installed nothing.

**Baseline command**, exactly as in `docs/baselines/harness_tests_baseline.md` (round 2):
- pytest: `1 failed, 21 passed in 17.11s`;
- `GIT STATUS (incl. ignored) IDENTICAL`;
- regression check: `baseline: 22 tests, 21 passed; this run: 22 tests, 21 passed`, `RESULT: PASS`.

All 22 per-test outcomes equal the baseline table. The one failure is the recorded one, `TimeoutError: Clip 'packet_loss_sample_01.wav' did not complete within 3.0s` at `bots/listener_bot.py:508`.

**Protected paths across the phase** (`475890d`, the `main` commit before any lab file, to `079571e`; 348 commits):
- I classified every file each commit touched with the hook's own `classify`.
- The 281 Claude-authored commits touched **no** GUARDED or NEVER path.
- The 67 owner commits touched NEVER paths only: approvals, specs, process files, `.claude/` and the raw baseline.
- The harness tree is byte-identical across the phase. `git diff 475890d 079571e` over every GUARDED path, excluding the LAB-OWNED areas, is empty.

**Phase-wide gate.**
- Command: `tools.audit.gate --base 475890d --wp WP-0.9`.
- It gives 43 findings, all `A1 owner-only path changed`, all from owner commits.
- There are 0 compromise-pattern or test-integrity findings and 0 `# audit-allow` lines.
- The only exempted files are the gate's pattern table and gate fixtures (`docs/approvals/WP-0.0.md`).

**WP-0.9's edits to existing lab tests.** Each of the four is named by an `ALLOW-EDIT` line in `docs/approvals/WP-0.9.md`. No assertion was loosened:
- the only line removed from `test_aqis_ci.py` is the job set, which gains `lab-network`;
- the removed lines in `aqis_baseline_testutil.py` are replaced by narrower exemptions and an added `.log` source.

## Checklist (phase level)
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | WP-0.0 to WP-0.8 MERGED (step 1). The branch is not `main`. `git show origin/main:docs/approvals/WP-0.9.md` starts with `STATUS: APPROVED`. |
| A2 Requirement coverage | PASS | Every exit criterion has evidence that exists (step 3). The 13 FR-0.9 tests are collected and pass. Per-WP requirement coverage was proven by each WP's audit. |
| A3 Acceptance commands | PASS | The phase smoke (AT-0.7-01), the parity runs, the contracts checks and `pack verify` (step 2). AT-0.9-01 is this report. |
| A4 Test suites and CI | PASS | `1971 passed`, 0 failed or skipped (step 2). CI is green on `079571e` (run 380) and on `main` (run 373). See F1 for the record of earlier red runs. |
| A5 Test integrity | PASS | No skip, xfail or audit-allow anywhere in the phase (phase-wide gate). The WP-0.9 test edits are approved and not loosened (step 6). |
| A6 Must-catch proof | N/A here | WP-0.9's must-catch list is break-tested by `/wp-audit WP-0.9`. I verified both behaviours directly: every E1 to E6 link resolves (step 3), and the only open debt rows are DEBT-025, moved to WP-4.5 by `docs/approvals/WP-0.9.md` Q8, and DEBT-027, whose target is outside phase 0. |
| A7 Compromise scan | PASS | Phase-wide gate: 0 compromise findings. WP-0.9 gate: `0 findings: OK`. |
| A8 Scope diff | PASS | No protected path changed by Claude, and the harness tree is unchanged (step 6). |
| A9 Capabilities | PASS | `test_FR_0_0_08_module_headers_match_registry` and the registry tests pass in the full suite. |
| A10 Contracts | PASS | The fresh run cards, events and manifest validate (step 2). |
| A11 Environment parity | PASS | Python 3.13 matches the probe's major.minor. The same CPU lock hash is used on all three machines. Platform is recorded per card (`cloud-vm`, `colab`, `oracle`). Owner-run checks are listed and committed (see F2 and F3). |
| A12 Reproducibility and traceability | PASS | Steps 4 and 5. See F4 for the documentation. |
| A13 Errors and logging | PASS | The phase-wide gate finds no swallowed errors. Each WP's error paths were proven in its own audit. |
| A14 Documentation, licences, data | PASS | E5 is met. There is no real personal data: no owner or campaign clip, and the recruiting status holds counts only. Record gaps: F1 to F4. |
| A15 Exploratory breaks | PASS | 1 break, caught (below). |

## Exploratory breaks (A15)
| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1: in a throwaway worktree at HEAD, one Oracle `vosk-batch` transcript changed ("…cloud and far" to "…cloud and far extra"), with its `text_sha256` and `BUNDLE.json` hash updated so the bundle stays internally valid | `data/runs/phase0-smoke/phase0-smoke-oracle-20261002T141937Z.tar`, read by `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` (added after WP-0.7's audited commit) | No: `1 failed` (`assert proc.returncode == 0`, parity exit 1) | — |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation |
| --- | --- | --- | --- | --- | --- |
| PH0-F1 | MINOR | A4, A14 | WP-0.9's EVIDENCE.md "CI" says the branch's earlier red runs were "both explained", and lists runs 377 and 378. Runs 375 (`7d59019`) and 376 (`4760f58`) also failed in "Fast lab test suite". I reproduced both commits in worktrees: `test_FR_0_0_08_module_headers_match_registry` fails at each (`1 failed`). That is the same CAP-CONTRACTS-006 registry mismatch the evidence describes, so no defect is hidden; the record is incomplete. | GitHub Actions runs 375 (id 37141915556) and 376 (id 37142130245), with conclusion failure on the step "Fast lab test suite"; my reproduction | Fix now (record only): add runs 375 and 376 to the "CI" section of `docs/progress/WP-0.9/EVIDENCE.md`. |
| PH0-F2 | MINOR | A11, A14 | OC-0.5-01's planned report `docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt` was never committed. It was to hold `pytest -m colab` on a Colab CPU runtime, expected `3 passed`. WP-0.9's plan (finding 3) and the memo present WP-0.5's owner checks as committed. The result is not missing: OC-0.7-01 (owner commit `d2d79e5`) reports `pytest -m 'colab or gpu' (5 passed)` at `7c27dd5`, and those five tests include the same three (I collected them at `7c27dd5`), though on a T4 runtime. The doctor half is committed (`docs/environment/doctor_colab_20260928T143840Z.json`). I rate this MINOR, not MAJOR, because a committed owner report holds the result. | `git log --all -- docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt` is empty; WP-0.5 EVIDENCE.md "Owner-run checks", row OC-0.5-01 | Fix now (record only): the memo's "Open issues" should name this gap and point to OC-0.7-01. |
| PH0-F3 | MINOR | A14 | The three WP-0.8 owner-run results are one-line notes. `docs/progress/WP-0.8/EVIDENCE.md` still says "Pending (owner)" for all three, although the owner committed them in `0ce38e1`. OC-0.8-03 reads "dev_bootstrap.sh --gpu verified (172 packages installed, lock sha256 87a1cc34...)": that is the CPU lock's hash, and the expected line `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …` is not shown. It is the only Colab evidence for the `--gpu` path since DEBT-021 (`a59e12f`, not in `7c27dd5`, so OC-0.7-01 did not run it). The risk is low: a broken `--gpu` bootstrap stops with `ERROR:`, never silently. The memo already discloses the one-line notes. | `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu.txt`; WP-0.8 EVIDENCE.md "Owner-run checks"; `git merge-base --is-ancestor a59e12f 7c27dd5` is false | Accept as debt. Target: the first phase 1 WP that runs on a Colab GPU (the owner names its ID). There, commit the full output of `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`. |
| PH0-F4 | MINOR | A12, A14 | `docs/adapters/PARAKEET_UNIFIED.md` line 70 says the GPU lock's "header names that lock's SHA-256" (the CPU lock's). The header of `requirements/aqis_lab/phase0-gpu.txt` holds only uv's compile command. The hash is in `requirements/aqis_lab/phase0-gpu.in` (`# compiled-against: …`), and a test keeps it correct. Every run card from a GPU environment records only `phase0-gpu.txt` (3 of my 5 traced rows), so the document sends a reader to the wrong file when tracing such a row's CPU lock. The binding exists; the text is wrong. | `head -2 requirements/aqis_lab/phase0-gpu.txt`; `phase0-gpu.in` line 8 | Accept as debt. Target: the next WP that edits the GPU lock or the Parakeet adapter documents (the owner names its ID). The fix is one sentence. |

Phase-level convergence does not apply: this is the first phase audit. No finding sits inside a must-catch list.

## For the owner
- **audit-allow lines:** none in the whole phase.
- **Approvals used:**
  - `docs/approvals/WP-0.0.md` to `WP-0.9.md` on `main` (`699acd5`);
  - WP-0.9: Q1 (order, D1), Q5, Q8 and Q9;
  - WP-0.4: TTS clips instead of owner recordings.
- **Debt still open:** DEBT-025 (target WP-4.5) and DEBT-027 (Phase 2 VAD timing work). F3 and F4 are recommended as new debt.
- **Owner-run checks still pending:** none. This report answers AT-0.9-01.
- **What happens next:**
  - Under the approved order, the builder now links this report in the memo (FR-0.9-03).
  - Until then, `test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict` fails on the branch by design ("exists, but the memo still says the audit is pending"). CI on the commit that adds this report will be red for that test only.
  - The fixes for F1 and F2 fit into the same memo and EVIDENCE.md update.
