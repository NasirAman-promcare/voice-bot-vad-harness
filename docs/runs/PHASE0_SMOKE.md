# Phase 0 smoke run

The phase 0 smoke run (WP-0.7, FR-0.7-07) runs the first three real components over the smoke pack `data/packs/smoke/v1` on one machine and writes a result bundle in which every number can be traced. Bundles from the cloud VM, Colab and Oracle are then compared with `parity` (FR-0.7-08). Code: `aqis_lab/smoke.py`, `aqis_lab/parity.py`. Settings: `config/aqis_lab/phase0_smoke.yaml`.

## How to run
```bash
.venv/bin/python -m aqis_lab phase0 smoke --target cloud
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--target {cloud,colab,oracle}` | The machine this is. Required: the lab never guesses. It must match the detected platform (`cloud-vm`, `colab`, `oracle`), otherwise `ERROR:` and exit 2 | — |
| `--out DIR` | Run folders (`<out>/runs/<task>/`) and the bundle archive. On Colab a folder under `MyDrive/AQIS_LAB`, so a disconnected runtime can resume | `data/raw/aqis_lab/smoke/<target>` |
| `--store DIR` | Results store on local disk | `data/raw/aqis_lab/results` |
| `--model-cache DIR` | Model cache on local disk | `data/raw/aqis_lab/models` |
| `--work-dir DIR` | Local folder the pack is staged in | the runner's default |
| `--bundle-dir DIR` | Local folder where the bundle is assembled and scored | `data/raw/aqis_lab/smoke-bundles` |
| `--drive-mount DIR` | The Google Drive mount on Colab: keeps the unit log current after every shard | none |
| `--from-scratch` | Start every run again. A run folder under `--out` that holds another run (for example one made at an earlier commit, which the runner refuses to resume) is renamed `<folder>.superseded-<UTC>`, never deleted | off: unfinished runs of the same commit resume |

Exit codes: 0 complete; 1 a run, score, store add, validation or trace failed; 2 a usage, configuration or machine problem found before anything is written (for example a GPU target without a GPU, or NeMo not installed).

Colab uses `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` (`docs/colab/COLAB_RUNBOOK.md`, OC-0.7-01). Oracle uses the steps in `docs/oracle/ORACLE_RUNBOOK.md` (OC-0.7-02).

## What runs where
Each task is a normal resumable runner run with its own run card (`docs/runner/RUNNER.md`):

| Task | Clips | Run-card mode | cloud | colab | oracle |
| --- | --- | --- | --- | --- | --- |
| `vosk-batch` | all 60 | `batch` | yes | yes | yes |
| `harness-vad` | all 60 | `batch` | yes | yes | yes |
| `vosk-realspeed` | the 5-clip subset | `realspeed_cpu` | yes | yes | yes |
| `parakeet-offline` | all 60 | `batch` | no | yes | no |
| `parakeet-compute-delay` | the 5-clip subset | `gpu_compute_delay` | no | yes | no |

Parakeet runs on the GPU target only. On `cloud` and `oracle` the report says "Parakeet: not run on target <target> (a CPU target; FR-0.7-07 runs Parakeet on the GPU target only)". On Colab without a usable GPU the smoke stops with exit 2. It never skips Parakeet.

**The 5-clip subset** (owner decision, question 8): per category, the clips with the lowest `sha256("aqis-phase0-subset-v1|" + clip_id)`: two test-clean, one test-other, one noisy and one tts clip. Today these are `ls-test-clean-3570-5695-0009`, `ls-test-clean-6829-68771-0030`, `ls-test-other-6128-63244-0013`, `smoke-mix-01` and `tts-smoke-04`, 25.6 s of audio. The config lists the IDs, and a test keeps them equal to what the rule computes on the pack. The subset goes into each run's shard plan (`clip_selection`), not into its run card.

## Steps
1. Check the target against this machine, then run every task's preflight. Nothing is written before both pass.
2. Run each task of the target into `<out>/runs/<task>/`. Running the smoke again resumes: finished shards are skipped.
3. Copy each run's `run_card.json`, `shard_plan.json`, `results.jsonl`, `events.jsonl` and `runner.log` into the bundle.
4. Score the transcripts of `vosk-batch` (and on Colab `parakeet-offline`) with the WP-0.3 `score` command, once per score subset (owner decision, question 10):
   - `natural`: test-clean, test-other and noisy (40 clips);
   - `synthetic-tts`: tts (10 clips). Synthetic speech is plumbing only, never a model judgement (`docs/data/SMOKE_PACK.md`).

   The references are the pack manifest's transcripts. Clips without a transcript are not scored.
5. Validate every run card and every `events.jsonl`, add every run and score folder to the results store, and run `trace` on every stored row of the smoke's run cards. Rows already in the store are not stored twice.
6. Write `PHASE0_SMOKE.md` and `BUNDLE.json` into the bundle folder, then the archive `<name>.tar` beside the bundle folder and into `--out`.

The last line is `smoke complete: bundle <folder> (<n> files, <n> rows traced), archive <path>, <seconds> s`.

## Result rows
After `clip_id`, `run_card_id`, `task` and `task_version`:

| Task | Fields |
| --- | --- |
| `vosk-batch` | `text`, `text_sha256`, `finals`, `partials`, `words`, `events`, `audio_s` |
| `vosk-realspeed` | the `vosk-batch` fields, plus `first_partial_latency_ms`, `finalisation_latency_ms`, `max_frame_lag_ms`, `wall_s` |
| `harness-vad` | `segments`, `speech_s`, `frames`, `speech_frames`, `dropped_tail_samples` |
| `parakeet-offline` | `text`, `text_sha256`, `audio_s` |
| `parakeet-compute-delay` | `text`, `text_sha256`, `audio_s`, `processing_ms`, `rtf`, `gpu` |

`text` is the clip transcript and `text_sha256` the SHA-256 of its UTF-8 bytes. The adapter documents (`docs/adapters/`) give the details.

**Real-speed measures** (owner decision, question 7). Frames of 20 ms are delivered no earlier than their real-time deadline on the monotonic clock (`aqis_lab/realspeed.py`):
- **First-partial latency:** wall time of the clip's first `partial` event minus the delivery time of the frame holding the first recognised word's start (from the `final` events' word times).
- **Finalisation latency:** wall time of the clip's last `final` event minus the `audio-end` timing mark, written when the last frame is delivered.
- Both are in milliseconds, and both are null when no word was recognised.
- `max_frame_lag_ms`: the largest delay of a frame after its deadline. A slow adapter gets its frames late, never skipped.
- `wall_s`: the clip's wall time from its first deadline to the end of the closing result.

On Oracle the real-speed run is pinned to the reserved timing cores 2-3 and the batch runs to cores 0-1 (`config/aqis_lab/oracle.yaml`).

**GPU compute delay** (FR-0.7-06): one untimed warm-up transcription first, then each clip's `transcribe` call is timed with CUDA synchronised before the start and after the end. `rtf` = processing time / audio length.

## The bundle
The bundle `phase0-smoke-<target>-<YYYYMMDDTHHMMSSZ>` holds:

```text
BUNDLE.json               the bundle's facts and the SHA-256 and size of every other file
PHASE0_SMOKE.md           the report
runs/<task>/              run_card.json, shard_plan.json, results.jsonl, events.jsonl, runner.log
scores/<task>-<subset>/   scores.parquet, scores.csv, summary.json (WP-0.3 score table 1.0)
```

`BUNDLE.json` (bundle version `1.0`):

| Key | Meaning |
| --- | --- |
| `bundle_version` | `1.0` |
| `name`, `target`, `platform`, `created_utc`, `host_id` | Which bundle, which machine |
| `elapsed_s` | Wall time of the whole smoke, in seconds (NFR-0.7-01: at most 900 s on the cloud VM) |
| `machine` | The run card's machine block (CPU model, architecture, OS, Python, GPU) |
| `git` | Commit and whether the tree was dirty |
| `locks` | Each installed lock file with its SHA-256 (`phase0.txt`, and on Colab also `phase0-gpu.txt`) |
| `runs` | Per task: `run_card_id`, `mode`, `clips`, `events` |
| `scores` | Per score table: `task`, `subset`, `run_card_id`, `summary_sha256` |
| `traced_rows` | Number of stored rows traced |
| `files` | Every file except `BUNDLE.json`: `sha256` and `bytes` |

The archive `<name>.tar` holds the bundle folder with sorted members, fixed owner and a fixed modification time (the bundle's `created_utc`), so the same bundle always gives the same archive bytes. Committed bundles go to `data/runs/phase0-smoke/<name>.tar` (owner decision, question 11).

## The report
`PHASE0_SMOKE.md` in each bundle states the machine, commit, locks and elapsed time. It then gives:
- the runs, with run card, mode, clip count, `results.jsonl` SHA-256 and event count;
- corpus WER, errors, reference words and CER per score table and normaliser variant, with the `summary.json` SHA-256;
- WER per clip for the `main` variant;
- the per-clip transcripts' hashes, VAD speech per clip, the real-speed latencies (median and maximum), and on Colab the Parakeet GPU times with the GPU type.

Every number is printed from a bundle file. Each table row names its `result_row_id`. To trace one, add the bundle's folders to a store (`python -m aqis_lab results add --run runs/<task>`, then `--scores scores/<table>`) and run `python -m aqis_lab trace <row>`. A test recomputes every number of the report from the row it names.

## Parity
```bash
.venv/bin/python -m aqis_lab parity <bundle A> <bundle B>
```
Each argument is a bundle folder or its `.tar`.
- Both bundles are first checked against their `BUNDLE.json`: bundle version, no file missing or extra, and every file's SHA-256 and size. A bundle that fails any check is exit 2.
- For every transcript task in both bundles (`vosk-batch` must be in both), it compares the clip sets and each clip's `text_sha256`.
- For every score table in both bundles, it compares each clip's and variant's `wer` (a row on one side only is a difference) and each variant's corpus WER, errors, reference words and corpus CER.
- A task or table in one bundle only is printed as `not compared: …`, never hidden.

Output: both bundles' facts (target, platform, machine, commit, locks), one `DIFFERENT <item> <clip or total> <field> A=<value> B=<value>` line for every difference, and a summary line: `parity: identical (…)` (exit 0) or `parity: <n> difference(s) (…)` (exit 1).

OC-0.7-03 runs parity on the three pairs of committed bundles (cloud and Colab, cloud and Oracle, Colab and Oracle). Any difference goes to the owner as a blocker.


### OC-0.7-03: the three machines compared
Run by Claude on the cloud VM, on the three committed bundles. All three pairs are identical. The Parakeet tasks and tables exist only in the Colab bundle, so parity names them as not compared. `test_FR_0_7_08_cloud_colab_oracle_bundles_identical` repeats this check on every test run.

```text
$ .venv/bin/python -m aqis_lab parity data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar
A: phase0-smoke-cloud-20260930T170440Z: target cloud, platform cloud-vm, Intel(R) Xeon(R) Processor @ 2.10GHz x86_64, commit 0a534ce22bf7d1d0b5d266920d2302bced0ef865, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4
B: phase0-smoke-colab-20261002T140101Z: target colab, platform colab, Intel(R) Xeon(R) CPU @ 2.00GHz x86_64, commit 7c27dd53e670d1a207be8738873eeb22bc1ce968, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4, requirements/aqis_lab/phase0-gpu.txt 837342085aed
not compared: parakeet-compute-delay is only in B (phase0-smoke-colab-20261002T140101Z)
not compared: parakeet-offline is only in B (phase0-smoke-colab-20261002T140101Z)
not compared: score table parakeet-offline-natural is only in B (phase0-smoke-colab-20261002T140101Z)
not compared: score table parakeet-offline-synthetic-tts is only in B (phase0-smoke-colab-20261002T140101Z)
parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)
exit 0

$ .venv/bin/python -m aqis_lab parity data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar data/runs/phase0-smoke/phase0-smoke-oracle-20261002T141937Z.tar
A: phase0-smoke-cloud-20260930T170440Z: target cloud, platform cloud-vm, Intel(R) Xeon(R) Processor @ 2.10GHz x86_64, commit 0a534ce22bf7d1d0b5d266920d2302bced0ef865, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4
B: phase0-smoke-oracle-20261002T141937Z: target oracle, platform oracle, Neoverse-N1 aarch64, commit 7c27dd53e670d1a207be8738873eeb22bc1ce968, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4
parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)
exit 0

$ .venv/bin/python -m aqis_lab parity data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar data/runs/phase0-smoke/phase0-smoke-oracle-20261002T141937Z.tar
A: phase0-smoke-colab-20261002T140101Z: target colab, platform colab, Intel(R) Xeon(R) CPU @ 2.00GHz x86_64, commit 7c27dd53e670d1a207be8738873eeb22bc1ce968, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4, requirements/aqis_lab/phase0-gpu.txt 837342085aed
B: phase0-smoke-oracle-20261002T141937Z: target oracle, platform oracle, Neoverse-N1 aarch64, commit 7c27dd53e670d1a207be8738873eeb22bc1ce968, locks requirements/aqis_lab/phase0.txt 87a1cc34c6d4
not compared: parakeet-compute-delay is only in A (phase0-smoke-colab-20261002T140101Z)
not compared: parakeet-offline is only in A (phase0-smoke-colab-20261002T140101Z)
not compared: score table parakeet-offline-natural is only in A (phase0-smoke-colab-20261002T140101Z)
not compared: score table parakeet-offline-synthetic-tts is only in A (phase0-smoke-colab-20261002T140101Z)
parity: identical (vosk-batch: 60 clips; vosk-realspeed: 5 clips; vosk-batch-natural: 80 rows; vosk-batch-synthetic-tts: 20 rows)
exit 0
```

## Reports
Each committed bundle's report, byte-copied from its `PHASE0_SMOKE.md` between the two marker lines. A test checks each copy against the committed archive in `data/runs/phase0-smoke/`.

### Cloud VM: `data/runs/phase0-smoke/phase0-smoke-cloud-20260930T170440Z.tar`
Made with `.venv/bin/python -m aqis_lab phase0 smoke --target cloud` on a clean tree at commit `0a534ce` (exit 0, 105.7 s).

<!-- report phase0-smoke-cloud-20260930T170440Z begin -->
# Phase 0 smoke run: target cloud

Bundle `phase0-smoke-cloud-20260930T170440Z` (bundle format 1.0, docs/runs/PHASE0_SMOKE.md), written 2026-09-30T17:04:40Z on cloud-vm:vm.

- Machine: platform cloud-vm, Intel(R) Xeon(R) Processor @ 2.10GHz, x86_64, Ubuntu 24.04.4 LTS, Python 3.13.12, GPU none.
- Code: git commit `0a534ce22bf7d1d0b5d266920d2302bced0ef865` (dirty: false).
- Locks: `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`.
- Elapsed: 105.7187 s (NFR-0.7-01: at most 900 s on the cloud VM).

Every number below is printed from a file of this bundle. A table row names its result row: add the bundle's run and score folders to a results store (`python -m aqis_lab results add --run runs/<task>`, then `--scores scores/<table>`) and run `python -m aqis_lab trace <row>`.

## Runs

| task | run card | mode | clips | results.jsonl sha256 | events |
| --- | --- | --- | --- | --- | --- |
| vosk-batch | `5eb8cb06f90d81fd2eb8290d3bdc09e4e799c57e2eb835e0f011b49673b70350` | batch | 60 | `2f42f17998622d836338e5fb8ea80af3e9df5846cb842f730e1bb46f1bce7da0` | 894 |
| harness-vad | `14db429d748b304b375a9a21bd00846001180575f86156a4f87c76bbc11ff3be` | batch | 60 | `70615de08363a75f1531f110aa8bba3d4527b333832ab4aeeb3aacc937f3ad34` | 462 |
| vosk-realspeed | `7a61ecfefa4b184d488bd377edf9e3858ee2e945b945bf6e464ef2b3b15d3bee` | realspeed_cpu | 5 | `5fc67ae2ad3098abd175de42c5f8ac57b725cb61ceaa612e8f8772f7241a5888` | 81 |

## Word error rate (WP-0.3 scorer)

Tables `*-synthetic-tts` are synthetic TTS speech: plumbing only, never a model judgement (docs/data/SMOKE_PACK.md).

| table | variant | corpus WER | errors | reference words | corpus CER | summary.json sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | disfluency_aware | 0.1074 | 74 | 689 | 0.0528 | `cc9156be12e087699c283cb70174ec8acfee95313a772906f14542a9aca0fc91` |
| vosk-batch-natural | main | 0.1074 | 74 | 689 | 0.0528 | `cc9156be12e087699c283cb70174ec8acfee95313a772906f14542a9aca0fc91` |
| vosk-batch-synthetic-tts | disfluency_aware | 0.0476 | 3 | 63 | 0.0115 | `54397abc4d8e21f4be7163b310801420725ea935b1fb9ffe84dbd2046d26d638` |
| vosk-batch-synthetic-tts | main | 0.0476 | 3 | 63 | 0.0115 | `54397abc4d8e21f4be7163b310801420725ea935b1fb9ffe84dbd2046d26d638` |

### WER per clip (variant main)

| table | clip_id | wer | errors | ref_words | row |
| --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | ls-test-clean-1188-133604-0029 | 0.1111 | 1 | 9 | `fa8f7d0a7dafdde0e282855c88ca7ecb029181b5938c0270e7ba623a05150d39` |
| vosk-batch-natural | ls-test-clean-121-127105-0012 | 0.1429 | 3 | 21 | `45862f8528b3945fb0aaada7fa9341f97e97bef22a1f6a837024d4aa2f6a400d` |
| vosk-batch-natural | ls-test-clean-1221-135767-0014 | 0.0500 | 1 | 20 | `152eb82cfae6649d1490ec465d0cc284aaf65fef983de31ddfa20c4fe0dcefcb` |
| vosk-batch-natural | ls-test-clean-1580-141083-0035 | 0.0769 | 1 | 13 | `a4bab45edcf5a3d2c1a1fdb08d1baaf3c4c2b5d32abb2e0911abd9825b09b5de` |
| vosk-batch-natural | ls-test-clean-237-134493-0011 | 0.0000 | 0 | 19 | `26ef488d6e70a732a415d32e22be3eb8dce8c937807382d0bf08a3cfefb48c81` |
| vosk-batch-natural | ls-test-clean-2830-3980-0007 | 0.0909 | 3 | 33 | `939ba4f8e6a56601919c154eb819eb906394c3707621e28ce58d4ac843d70e16` |
| vosk-batch-natural | ls-test-clean-3570-5695-0009 | 0.0714 | 1 | 14 | `c4407075603a120b38d91342cd262c551c312c89e6bea1986004d93faa62e6c5` |
| vosk-batch-natural | ls-test-clean-4077-13751-0014 | 0.1471 | 5 | 34 | `abe88376e41a80c05d0530c1596397ba080b8ba8786b3cd56b1fce765945604d` |
| vosk-batch-natural | ls-test-clean-4446-2271-0024 | 0.0769 | 1 | 13 | `87b1a6fd825bace79f8111d8f6756a774e3b2f1fbbebfb7e4d98ab160d0ab03d` |
| vosk-batch-natural | ls-test-clean-4507-16021-0058 | 0.0000 | 0 | 8 | `734bb67cd7fa5017614c30f459fa5f2438855de339aaeece5cdf5f4616b64b51` |
| vosk-batch-natural | ls-test-clean-4970-29095-0002 | 0.0769 | 1 | 13 | `9e25a1eb99792d05f847d879981e2b2aa8f06619e580b2408bc12d17b545f852` |
| vosk-batch-natural | ls-test-clean-4992-41797-0015 | 0.0333 | 1 | 30 | `4486a3c21f148fccbe16e53415df1537d2a730135ef489fb1075b9171db5c2bb` |
| vosk-batch-natural | ls-test-clean-61-70970-0011 | 0.1333 | 2 | 15 | `2d283b9acabaf6eeb2d42554f38ba8cbf98bd8acb3020ffefdfd9b215ece962c` |
| vosk-batch-natural | ls-test-clean-6829-68771-0030 | 0.0000 | 0 | 17 | `cb29b92191249b837e6fdd396bfda636ecb0f804ffb6ccc631a541bac7b80e41` |
| vosk-batch-natural | ls-test-clean-7127-75946-0009 | 0.0000 | 0 | 12 | `bd99f15a87980651b143f9d1a44e18492deadf0377733ad5188f4a5454bab7d7` |
| vosk-batch-natural | ls-test-clean-7176-92135-0018 | 0.0370 | 1 | 27 | `ecc60e6153608c6e5a6d9b42a8004b16263d868333c04d53fc319083892dc0b1` |
| vosk-batch-natural | ls-test-clean-7729-102255-0023 | 0.0000 | 0 | 10 | `042db9e72efb19e0d06203875120d3d0e6983a0a5b8821041591c98072b77eeb` |
| vosk-batch-natural | ls-test-clean-8230-279154-0011 | 0.0000 | 0 | 12 | `8f8b845074684a1ee4b575c9af735ac066ac8f0eaa35c75b7f52c92747eaec7b` |
| vosk-batch-natural | ls-test-clean-8455-210777-0037 | 0.0000 | 0 | 10 | `f1cc5238d4c93648700369d33e02a0df75d846730581cd725e9623f3e4319a54` |
| vosk-batch-natural | ls-test-clean-908-157963-0014 | 0.2727 | 3 | 11 | `0ff928801bcc1d38cb96ef68f46060ffcefd98519682d76884e5c123f96a877a` |
| vosk-batch-natural | ls-test-other-2609-156975-0000 | 0.5455 | 6 | 11 | `80b8cc89591764e8e5a7c75c0a6c6194eab6dab3b1224b96bf88f99bd9caf982` |
| vosk-batch-natural | ls-test-other-3080-5040-0016 | 0.0526 | 1 | 19 | `319363d4375031b76616e0d26236466e9a463e40b4df77b032f3c41bfb93a5f1` |
| vosk-batch-natural | ls-test-other-3528-168669-0043 | 0.3000 | 3 | 10 | `e7166aac43274d0cc2754baaffdcce19826de716e0060a44421d7e33f20c53f3` |
| vosk-batch-natural | ls-test-other-3538-142836-0006 | 0.0000 | 0 | 18 | `71c381e7c324623a400c1ffa0165a21180eeb608e25d394871f6e6ef576ee533` |
| vosk-batch-natural | ls-test-other-4198-12259-0026 | 0.4615 | 6 | 13 | `ac683e2456e1e25a6a197646b19b0423559ae02ce278940a1f45b31918e87d73` |
| vosk-batch-natural | ls-test-other-6128-63244-0013 | 0.6364 | 7 | 11 | `de1fa85a20ff4e0abbae3e5485e3d77e8de2729932f86b248cec06ac08823546` |
| vosk-batch-natural | ls-test-other-6432-63723-0046 | 0.0000 | 0 | 19 | `46858c3db30b36e5f5d74f652ed15b9f2de4f3be34406bb6a881f30937994af6` |
| vosk-batch-natural | ls-test-other-7105-2340-0033 | 0.0000 | 0 | 27 | `43bbe70dc15a4d4174747cafe62272766a396747e83d9fa8a7dced551c39f111` |
| vosk-batch-natural | ls-test-other-8188-269288-0027 | 0.1667 | 2 | 12 | `844521bebf4df9aa336cb84d974981d4bfff48efdb05979dce44013413dd0876` |
| vosk-batch-natural | ls-test-other-8280-266249-0004 | 0.1176 | 2 | 17 | `cf0f30d9c5e4969cb3c71caa8d658c5e0bec4c63a5293ad87c0949094bc52ad0` |
| vosk-batch-natural | smoke-mix-01 | 0.2500 | 3 | 12 | `f48c177b591a5f6e0c5adbb371d9197ab13382c15c0aaa0249de48642f5dae6d` |
| vosk-batch-natural | smoke-mix-02 | 0.3333 | 8 | 24 | `e87fe4d81f7326fb9b7ef4d990af39a416a7fdee087660301a6f7447967b9175` |
| vosk-batch-natural | smoke-mix-03 | 0.0000 | 0 | 19 | `ae267864d142a4e95dbdc47b4fba7ef145718a87e1236438ba635b02450c6091` |
| vosk-batch-natural | smoke-mix-04 | 0.0000 | 0 | 14 | `9b33267c5da7e700faab4df6f22e923e2c34f9c23383e4df78b006093c3fa5ea` |
| vosk-batch-natural | smoke-mix-05 | 0.0625 | 1 | 16 | `246ad130d7e9fc7648c6f238f058aad6a9372108bbc7920dab5dfbbc32db5781` |
| vosk-batch-natural | smoke-mix-06 | 0.2000 | 2 | 10 | `00ba2c9b0a59ce42420456425e1ed18d6e2beadfa8ee4214377f48219bf462e5` |
| vosk-batch-natural | smoke-mix-07 | 0.0385 | 1 | 26 | `b7a53fc8193e32d9961202fc66b1a5ac2c72c6fef23dad65a65a57b48c4d51f6` |
| vosk-batch-natural | smoke-mix-08 | 0.0870 | 2 | 23 | `8d8873a0279a3c41c828f2befbb2c9f767dcae5d7337c9f7e40a222d4759b206` |
| vosk-batch-natural | smoke-mix-09 | 0.1481 | 4 | 27 | `c01512cd4ac49deff5b4ef4d329e899a08652ce3ff0c3c64e2771a4085a2ce97` |
| vosk-batch-natural | smoke-mix-10 | 0.1000 | 2 | 20 | `1ad0635716a6b244ab57463faeeebdcef9d092d1059442ebd0ea37fbb431990f` |
| vosk-batch-synthetic-tts | tts-smoke-01 | 0.0000 | 0 | 1 | `e908f1bdab005d148458d2226a06e8c8ba1e4d7600d2cbcf42f7c258525a7bf6` |
| vosk-batch-synthetic-tts | tts-smoke-02 | 0.0000 | 0 | 10 | `7fe749e2e9ae39814253157ad1b70f410cbcccd2bd1a5daa6f4149971e173ead` |
| vosk-batch-synthetic-tts | tts-smoke-03 | 0.0000 | 0 | 1 | `b8e65e0e2bc5d858a5e9a788b9ed021036faf5647c49b5ca6388848bcc0eb60a` |
| vosk-batch-synthetic-tts | tts-smoke-04 | 0.1111 | 1 | 9 | `ae9a7f4638152910783731b0eb552ef8329c5c2e99870c7d88f360c427018319` |
| vosk-batch-synthetic-tts | tts-smoke-05 | 0.0000 | 0 | 1 | `a5cd894e6e66122a61368baf5a89e5aac6a4eab620594d51efc6c6ba6a3f1d46` |
| vosk-batch-synthetic-tts | tts-smoke-06 | 0.0000 | 0 | 14 | `da00cb49efd237da0339bd1d3dbd012d12eb1e8e01a75a81c143c87207a4e24f` |
| vosk-batch-synthetic-tts | tts-smoke-07 | 0.0000 | 0 | 1 | `ac9c247b04655724c64165b1905a73cec8bb54dffc994dbde1616f04fe0545a2` |
| vosk-batch-synthetic-tts | tts-smoke-08 | 0.0000 | 0 | 12 | `988d9864230d266b734a7fb19a0405a804e01f040255b503a1155cdc256f07a6` |
| vosk-batch-synthetic-tts | tts-smoke-09 | 0.0000 | 0 | 1 | `f6f1689ccd3f12d8163c8dd604e6660bfd130d548b202cccaa4442064e36ea32` |
| vosk-batch-synthetic-tts | tts-smoke-10 | 0.1538 | 2 | 13 | `674c5d5a533fee26180d1478ba3f8add8c86573f423ad924f60e52155a56ca34` |

## Vosk batch transcripts (60 clips)

| category | clip_id | words | text_sha256 | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 9 | ed0cdc46462af3fd85466e4075531ee6d435532e1ec02e0590bba2cf4537a288 | `994765df172b2bae9503c7136c8bde30ec91eeab06d563e9dc87c1c4d0b0d57a` |
| test-clean | ls-test-clean-121-127105-0012 | 18 | 699ad819bfcf8b39789087c3f0b15bf114c1c75b75f6e8ef6f0133c9ca259a29 | `e66948ea20198a8b691efa1178bb6ade0697dac5fa13a369e6147cdf0babd98d` |
| test-clean | ls-test-clean-1221-135767-0014 | 20 | 77eeb5c74e6a837f48d06d5d1c6e82e20d660dfb2f67893eb1545cfb971a1f5b | `e1dcd447f1291807aaef82d78923f11edd42bca86eea9d1eadaebaa8c5db8aa3` |
| test-clean | ls-test-clean-1580-141083-0035 | 13 | 7ed7925898bfabeb4443421409c639975eb0d4b8e1e5791df7871786d038e48e | `1e0380df074e0a851e599065f2c3839d4822862bbf601c36c8000bfc7bc7daed` |
| test-clean | ls-test-clean-237-134493-0011 | 18 | cd082978af6d92788438beec92e61403187c2a8d86ce1802c07fb22976191948 | `edfd67d2aff4fbc6d6a1af0897d223547f08f99324192769a769cce290c29b3c` |
| test-clean | ls-test-clean-2830-3980-0007 | 33 | 36af36ac244f4016d204bd3b991eb497bf48a15378c9434b726cb95846437cce | `f3919360548d8f9d146dccd5e87dd4f28da426075bf97d808c077a072efaa041` |
| test-clean | ls-test-clean-3570-5695-0009 | 15 | cff865c42fc22044f4f00219966c7fa5ff6d5718c9ff254e632e78630becf5a0 | `d3dac58816f5085c7d367d8389c1ad90efc2dc0a1eea255a4fb2c152854e1be6` |
| test-clean | ls-test-clean-4077-13751-0014 | 36 | 79d2318af8535b69de087760526f0ec46274301bf72765f91266629cb4b3be9c | `3e21f0e4f9e42ac3898dc2f6b38e734c7a86e397cf099ef72e4a84047e606daf` |
| test-clean | ls-test-clean-4446-2271-0024 | 11 | 74d466a6d2a3cd1a476bb21b1227a108c9f342eeed7caf78905599b9d01fa9aa | `314692a0f15260dfd87b7dd72a870c5de0b5bf3291540e9935c12854c0db754e` |
| test-clean | ls-test-clean-4507-16021-0058 | 8 | c236cd7f13c7f2639ac253c309b6c21d546aac29f50593b3ba1e7f84fe616c8c | `a2b9585884593cc6baaff262bbe8f5a0b5834be2710ba24476718d540e8e7481` |
| test-clean | ls-test-clean-4970-29095-0002 | 13 | 65fe9e8d47aff0d42b5918fa9aafe611fdddc93b8858e466b9577efe91a7ad12 | `096e529fc6a0080bd0be9a7642c15247a93800fa59d102ec6fa59f8a00bd74d8` |
| test-clean | ls-test-clean-4992-41797-0015 | 30 | 1fc5773314919c8012f97d56723388a6befb7c5cc17f463fa830398330a0a4fe | `97a73b1912ab7849d46eb16592855f6b08228515cbddd54493c492539465d60d` |
| test-clean | ls-test-clean-61-70970-0011 | 16 | 75e669b68ccb7686f78d6227dbbfc25e9f66e3dc6b817b02a2fab5c1196d94b7 | `57a390049aaa38c497c5af77b020c0b26d95d5d681b6bd77d780a3eab1f0b0fb` |
| test-clean | ls-test-clean-6829-68771-0030 | 17 | fbb99918869de67cd11ecd35fccf05d3b9ba7ba0de5d1183db2ceaa10a3ef5f0 | `0ed5f275bc40e506f10dbca2ed15706784f3daa8a723e9cf2a2c02f523b5dd23` |
| test-clean | ls-test-clean-7127-75946-0009 | 12 | b65a6039e3d0f4bdde3eb8f7c193af2bf48ff82369965e3310e3ccab78bc0d08 | `1ef932b9da39a760660350f0e89c78660e313d775f7b240601acda7caf0a7ab8` |
| test-clean | ls-test-clean-7176-92135-0018 | 27 | f49073c8aa17da02b2b0639369978d3a4c4af8dd74a1cff0f4614953a2ac666e | `ec2a6a6782441df063b87fd79797559c29467b80737b528c843a1b5dd70b01a0` |
| test-clean | ls-test-clean-7729-102255-0023 | 10 | 996a32b70e1851af5372a32bbc2b2899bf06bbbd161a9414a1f99118f26a8a24 | `5f6b70c07e22c5d704d35d46c0cb630c43ccbb7caaa34a98112283105946bb1b` |
| test-clean | ls-test-clean-8230-279154-0011 | 12 | dc8cb596dd4211fd11b0e55f11f8192c425d43957fbc795f33d5f8be372b78ff | `05aa2c537079426e5269bcba2d1da3cca8aa5727f6eed6c391e7bd21d3469f94` |
| test-clean | ls-test-clean-8455-210777-0037 | 10 | 4af3329969e0f398ea43d2be7b278776baa1bed28e313c0e2f091da363256aa1 | `021136997a3ce79b2a51ce3545ef58aab805e758f9a01ad96ddd593b8cf62cf3` |
| test-clean | ls-test-clean-908-157963-0014 | 11 | 35bb92d7da9f5472ab74a0fd16688e9739d86999017882ca2c8358a3a5dfb405 | `d22b44c189564f8af7e76f6545c154971ac622467337fdb47539044b3b284c50` |
| test-other | ls-test-other-2609-156975-0000 | 12 | da4a25a42447ac2efb2c4bf427ee83cabbf789e51a20cfbe95fda8461c26d76b | `aa576785b70dfc48f2cdc51cfdc9df8e79e312a4b69b3ad118c6c8344028d703` |
| test-other | ls-test-other-3080-5040-0016 | 18 | d95e960697381f2d028985cd69b7569eb5cfeaaf3adb33e47449f3f0dfe694ad | `85b5d8b9fb7a23023c7fc0a01f0b14deb4f947c5369859dfafe35d7dc7fdea52` |
| test-other | ls-test-other-3528-168669-0043 | 10 | d071a0bdb47a8d924c03c62240613d04335ed61caec31ccde0facef042f92f84 | `29fefc24ddbf229232f8202da42bc99861fda95f71e419109aaee3798e3a01a6` |
| test-other | ls-test-other-3538-142836-0006 | 18 | a3e636a5813ed01e48756a32859c4a32cc5edb17c700a1410d0eaecdd65a4284 | `970b8ccaa1693c6d081268ccf788f6420f95bc4969a37fcc004cfa7ce074b249` |
| test-other | ls-test-other-4198-12259-0026 | 15 | 776f18edf77e50dd07f3de821c05c8bd71a0696fa27e36433e3c0ac5b227dc50 | `95c820b10f66920562da1e1c022c3997dd5e7aa339dbb38e388d4987442ea95a` |
| test-other | ls-test-other-6128-63244-0013 | 10 | cdc1c8aa9174b98c2eaf0cfe2ddb73d6b2361c347227b38a2ffc0d5ead5c4383 | `f9377ee3bada50936a09260a5f407157d371ef936e2012db4a0c7afaa94e41c7` |
| test-other | ls-test-other-6432-63723-0046 | 19 | 956415288c8bf740b9b8db8f37e1ce15ab817f88578afe8fb2e744bc0c1cea82 | `2c07cddee33e3d1ced06cd11e287524810ab18151cf83d069250ba3640164feb` |
| test-other | ls-test-other-7105-2340-0033 | 27 | 92114c1d59b5d0e04984e651dd151729faf41453db2b7dd9bad84ddf04b6ddc6 | `cb595a12a2730fd3391a7fbf47e84be71685686a8748d14686040886a88faed6` |
| test-other | ls-test-other-8188-269288-0027 | 12 | 042a2cba559599707040b61d71bb8df67fbad439ae2ef02ca43ae18b2cb575c8 | `d3793ecc772039a207b44ec25ede3b57007be9e03602e285cabe33c1568870bb` |
| test-other | ls-test-other-8280-266249-0004 | 17 | 35ada150736b31211d48d52d8f5d96f4aafde1413bb34eec1e865cf4e0551e58 | `63934ae424f4e5745812644cdb1900ca22dad07536002a32377033dc49be8cbf` |
| noisy | smoke-mix-01 | 12 | 87910b29bb221a77c7c49aae0d15a1f4c1a9473281f693bf5024d4b56e62e2ab | `61565b13f52cc939ee5fbc6a2f34389c4a395c90de574253f18a986ede068d2a` |
| noisy | smoke-mix-02 | 25 | b888aff1a8cf3bd2a35cc8cedcf51e7015fff0800587946491ae250e2dfb0590 | `1f064a6d9360069c90c3ede1ae58f8dc19e2423094945a42addd09ab65a98475` |
| noisy | smoke-mix-03 | 19 | bcf0d81630c3e6bc5224d712424e3cea1d7b711ed7f35bfc7a7ae97b34b50b37 | `91b67dbedf0ba85365f12742e280674cd4a2330befcc663bf4c10d823fc0c774` |
| noisy | smoke-mix-04 | 14 | e758403d33ad61c1caa27def162b7e7c6303b3756016c7a6013ce7a9bc3332e1 | `0a974dd1dcfc6cc710c3cab83024b12dcc0471e469a8e9d69b0fea761523ce54` |
| noisy | smoke-mix-05 | 16 | 070d138be7141aeb954c90b79b133fd709a9471b5d07f0371116e2c7c44f476f | `1a75f1bd48c552ffdf7c3c74632c0473b001151295835588e6aff78fa6a32852` |
| noisy | smoke-mix-06 | 10 | c504300185d5fe7dd696fc1fde33810a22f1973177c97c9f4ff00c80099977ff | `32a67fa093b38619fb3a14842c225a10356a1654906ebe0ebf3689a89ca61de4` |
| noisy | smoke-mix-07 | 26 | 40a2aaa60d1da5489c171a1642ddd15cdc11e92ef3dee6d7c0cff31970c7f034 | `ecb8240ad2b77a300a2d2792e52440f42f97d7257ec07633ef5f36c531103698` |
| noisy | smoke-mix-08 | 23 | 150510b8461a309c5c4c998501060512397fd365cc24b69db00c4ac29c957563 | `2c6b59c74f6b2fe3fa818a2bd2a4903fa0586d8cbd240892be39f6e3bcc8be50` |
| noisy | smoke-mix-09 | 25 | 6a6abb83e505d3353861d315868bc023638ba33dc88d11b2399f732ad49c0c88 | `a0e8cd0a1bd9937f8a0ecb2c654312eacc47b2fa385d30fa42111634dd05718e` |
| noisy | smoke-mix-10 | 19 | b37dd1a23cdf37e3bbcadc14374e046e3772400577924656ea82b6c28873391c | `79c2dad13a60864b1676b2da3ecf3494f1b1a09d6bafdf96d8590f2c7bf381bb` |
| non-speech | smoke-music-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `8d2dcbeb26ca5fe1738a7db6c57a3854cef73ec293bc23e170cb449c5d61757e` |
| non-speech | smoke-music-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `512e19d67a3728735a52cbfb63cdaea5adffe18c9c480afb1fbb4051a49e7bdd` |
| non-speech | smoke-music-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `de7b41b405ad069ea59136a1ac930e005c719cdbe6c86ec647f4f79ec369c5f3` |
| non-speech | smoke-music-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `4819dec81d203a4e092460d4529e7226b56dfbd4862dba2333a98d172eef9b35` |
| non-speech | smoke-noise-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `ffa889906a4ad22ee705a8955299a8079ed6ad217665f7f810e4362db43ec6b9` |
| non-speech | smoke-noise-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `f6a75bd9af4c9b79fe523f8c60cf3ede3b8add57157e6ca53b179c312dffbc37` |
| non-speech | smoke-noise-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `79b57f7686b74cd6330ba17daf272b5208f66f23a38a124a2be62506d8f4268c` |
| non-speech | smoke-noise-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `0bde403f167894a7ae1c353cdbebed5c67db181efd82507747469c640c02cb9c` |
| non-speech | smoke-silence-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `58f26fce89c106b5232b600085e28ac5dd6fae526315df8138dccfaf1595b422` |
| non-speech | smoke-silence-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `d69d4eeae84fab9f0b02c0baf8156958868858547ff547d4d2155fe72ba808eb` |
| tts | tts-smoke-01 | 10 | 30640fce942d691c56bee86a2c000dfa620f2087b3ae22ec8abfd29c65b1eae1 | `81f9b2085efe24565c5f92a7b8179a4153c8adfc8a38ce783ff041e87c6db151` |
| tts | tts-smoke-02 | 10 | abfd320d882a8ec2ab888bf778f93eb52b29468e59b83822a313cc0e2881b132 | `af7f3d87af5493359f8490d6a53c43702e210af0e270833a424035657a4478bd` |
| tts | tts-smoke-03 | 10 | 25174bb2bfba68f128584857466e3aedcfbff528c3f8db91ffb1e738affc996e | `6e6dfa71a98ba1237e8717847536c5f7e8792cf50ae811833a5a9da12f321547` |
| tts | tts-smoke-04 | 9 | cb28d461f9814fb2319952d57cc1019fe6ad9a1b65321c667691c39387880a4e | `fbaf3bd7b6a7d1d61d8653d49013fa53b2835e599053151b6ea21ba0385866f7` |
| tts | tts-smoke-05 | 10 | de58dde5982f4880069fe246f111f88c13439cd7820235377345fcfcd7eac6d0 | `26e5108348fa9bc147b586096a72051facbbe3684b51cea86b1d97fc1bc69a67` |
| tts | tts-smoke-06 | 14 | 970e3092763b6055b4e31fd58c3dc4880f6053da1d3fb5eca16374419517a723 | `05043d2acc30f06f5c08db2c86a668695bde3518be74afb5aedf8b390908f4c0` |
| tts | tts-smoke-07 | 10 | 36ecaa833075d36b7382d79b1e10b2e2e3e92f761b443f9fb79c51bc7ded9b39 | `afdb3a176a63522eefd9dec85c433d41bd1b490a236dcc3df2677f59fe0889dd` |
| tts | tts-smoke-08 | 12 | 86ef79838b484c35c0ae08df921acae131a03cb554d88ec1e524f86838d2170d | `6c1287ed08f1f4e2f970e2c5a5fe242fb377f61ecf399475c0fd1df509cac621` |
| tts | tts-smoke-09 | 10 | a00dec41576b4f0fd1291d42ebbcd1c65945a112a2e6fb04df34e92a4d3978d4 | `d85611b88ce4fb7fbd49121ae28cd653039a8a5c5980cab725154602de063d69` |
| tts | tts-smoke-10 | 14 | a91a12354baa65c26dadf08f967e597bdd324308938da754e82bffc5545968bb | `8470ac52dcdad9dd97474f5b5f8b71b2cc5f6c25083e72d824377f53d083ccb7` |

## Real-speed Vosk (20 ms frames, never faster than real time)

First-partial latency: first partial event minus the delivery of the frame holding the first recognised word's start. Finalisation latency: last final event minus the audio-end mark. Both in milliseconds (owner decision, question 7).

| clip_id | audio_s | first_partial_latency_ms | finalisation_latency_ms | max_frame_lag_ms | row |
| --- | --- | --- | --- | --- | --- |
| ls-test-clean-3570-5695-0009 | 5.0250 | 237.9332 | 29.2362 | 274.2930 | `fd80b149df8e3bc822c3a474660175743dde9510d2aadc653742fa5f61bec643` |
| ls-test-clean-6829-68771-0030 | 6.2250 | 565.2863 | 20.8132 | 105.9073 | `e799c9ff886a3eab9c4d68b720a76b28a196e2a92b4ecf03cb576c3d5c59ba96` |
| ls-test-other-6128-63244-0013 | 4.1450 | 693.0897 | 33.0692 | 229.6111 | `f3d3d66c2a1bf5110bb2367077214cc1e756682a75a034db1fb7efa79ae22edb` |
| smoke-mix-01 | 5.2250 | 434.8279 | 12.6574 | 165.4683 | `9c3b73b8c83e5c4f1d6152f9c53ce5790c725a7cf8bbd657e73602b2414d801a` |
| tts-smoke-04 | 4.9750 | 728.3114 | 14.6829 | 142.7062 | `44608c4d98d68ec9a55fbeb72f2f59a8fad24ee3b1c49f9fc70b77e33150ab99` |

- First-partial latency: median 565.2863, maximum 728.3114 ms.
- Finalisation latency: median 20.8132, maximum 33.0692 ms.
- Real-speed transcript equal to the batch transcript: 5 of 5 clips.

## Harness VAD (webrtc_vad_mode2, 20 ms frames)

| category | clip_id | speech_frames | speech_s | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 115 | 2.3000 | `1881693905111f2044839f86c6b8ee97f0216a4e304dda41772d1d944dca21d0` |
| test-clean | ls-test-clean-121-127105-0012 | 227 | 4.5400 | `4ed544889a3740f377197a9c9660ea9333db1d7f6c962eb46ecfa7f450f2025d` |
| test-clean | ls-test-clean-1221-135767-0014 | 315 | 6.3000 | `6cc0b4e2818d6e9ffc02f1ff98a8e67213795668448a40594d7207206c51254f` |
| test-clean | ls-test-clean-1580-141083-0035 | 212 | 4.2400 | `86a5072d15125f21465dacd843f3edb5727c99c8b84708f002ff7c53ecf2285a` |
| test-clean | ls-test-clean-237-134493-0011 | 238 | 4.7600 | `19ab9abeb39b4effeca9d36975ee5b3a135c5ed8f3c525783fd572f543cc6e08` |
| test-clean | ls-test-clean-2830-3980-0007 | 430 | 8.6000 | `c52e45f4721e5dffd0bf0e153189b12fdb3962a34b73a1ca21aa4c4d7ea0f063` |
| test-clean | ls-test-clean-3570-5695-0009 | 221 | 4.4200 | `43badfc0a1af93339a79897fb0f7e6ce947a7e8896f3e398cb930736f9fe53e9` |
| test-clean | ls-test-clean-4077-13751-0014 | 595 | 11.9000 | `92d463e202527d0cf195d4eebed546a772549d5842749f71a8ce5b9cb3869764` |
| test-clean | ls-test-clean-4446-2271-0024 | 133 | 2.6600 | `b97ae94c7c47a029fce64853616e521d84887fbb9dde4a37e9aff00659700723` |
| test-clean | ls-test-clean-4507-16021-0058 | 122 | 2.4400 | `36872c103c690f2e896046c8c10c1b9506edd5b1229ec1dbd00ed89f1ed9a60c` |
| test-clean | ls-test-clean-4970-29095-0002 | 217 | 4.3400 | `858da08cb2363e497471c01de9b4649be7bdb275d1e2de16cc2836f3a51f77a2` |
| test-clean | ls-test-clean-4992-41797-0015 | 380 | 7.6000 | `6d68acdd31fb6f68088df05e7e54088a9c5a5d157cbae8df19942e646f648bc4` |
| test-clean | ls-test-clean-61-70970-0011 | 273 | 5.4600 | `4ab81f86d32cfc69acf46ea225993676c0459d662b96421f272e922cb2bc053d` |
| test-clean | ls-test-clean-6829-68771-0030 | 295 | 5.9000 | `800ab7fde94890819764e1a70fb77e511cea45fba5b6abafa0d2d80f6cc04961` |
| test-clean | ls-test-clean-7127-75946-0009 | 198 | 3.9600 | `3eec3a793a2ab70be0252d60b1b74e999a595b40b6937275af5c9fe75bd777ae` |
| test-clean | ls-test-clean-7176-92135-0018 | 419 | 8.3800 | `f81f217416412cb8e17ef4efc546aea379a870509b419307d42b6f32b4f093cd` |
| test-clean | ls-test-clean-7729-102255-0023 | 260 | 5.2000 | `3b3dda1932218d6a2336bd741832efd540e485843ce03da38f16bd2b080b2c4b` |
| test-clean | ls-test-clean-8230-279154-0011 | 282 | 5.6400 | `cc990cf1c6339ec02203a7829ac50f1abd058a0c9f4191aae0f7c0609e7b1166` |
| test-clean | ls-test-clean-8455-210777-0037 | 170 | 3.4000 | `09a7bd6e7a390587a2d0f01e8a4ec1630e4d1150f4f03acb26ae1b732918aef9` |
| test-clean | ls-test-clean-908-157963-0014 | 199 | 3.9800 | `9e1bb05bf9bde0396e948d643122337d43e63af9a9b133467603f7cd85815f99` |
| test-other | ls-test-other-2609-156975-0000 | 176 | 3.5200 | `4d99819925eb036b1b80a50128cf172164087202469f502e267bfe71fa819ab0` |
| test-other | ls-test-other-3080-5040-0016 | 218 | 4.3600 | `aee863eac1f54bbe54f90e5261ef040f7f25c3071076ab732130b979c0fffd9d` |
| test-other | ls-test-other-3528-168669-0043 | 166 | 3.3200 | `212d4be42bcde9106059fbec526e339c1766e48dd2c088b12370a1a418ca985f` |
| test-other | ls-test-other-3538-142836-0006 | 235 | 4.7000 | `27343ab841dd1f91d68276c9f074625555d139930882873cede5648d3a57436c` |
| test-other | ls-test-other-4198-12259-0026 | 214 | 4.2800 | `9a021e659b22f24ee2eb85f6406140066138a7c6ccdd77199e82894b07a7a0c0` |
| test-other | ls-test-other-6128-63244-0013 | 180 | 3.6000 | `99750003f1bc478b5c56d304ba0823622aac35dd65ea765dc46ccb51264f6286` |
| test-other | ls-test-other-6432-63723-0046 | 272 | 5.4400 | `8111b5a3cc6b5b53e674a111770c16a6b1921b768a9ebb7f4eb981551d238b98` |
| test-other | ls-test-other-7105-2340-0033 | 471 | 9.4200 | `992dbae122098c45348fe292f20f5ca2da09a3d835fd6598e8d29212affa3e7d` |
| test-other | ls-test-other-8188-269288-0027 | 160 | 3.2000 | `bb76557a6b489b9f9258f9e5a530592b0a9f446617c94c6202105103483969d6` |
| test-other | ls-test-other-8280-266249-0004 | 240 | 4.8000 | `e73f91edb53cc887408343a9553f2cb5c486533b14b9792ecb2da4e26ceb3379` |
| noisy | smoke-mix-01 | 260 | 5.2000 | `52e30f0642eb84c2768c10d49e41441d15609b18fda5e8205b3783d6c3d48df9` |
| noisy | smoke-mix-02 | 463 | 9.2600 | `02a40c2e7849b103a0b1ed6c6027e9535585f730487b490c933be31cee06a3aa` |
| noisy | smoke-mix-03 | 370 | 7.4000 | `62dc40b282d2cd6f8b637c0076ddb6cd1147c3ab2119de91e13871cb4cdd3256` |
| noisy | smoke-mix-04 | 253 | 5.0600 | `e3e021232c018b7e88ce85141f5e12b25c0de6dbbe7909295063d36e48eb1afa` |
| noisy | smoke-mix-05 | 302 | 6.0400 | `0ad0be80baa3a408af3440a4971a5fa2259a0c4c6a2216479420348672c41b65` |
| noisy | smoke-mix-06 | 156 | 3.1200 | `3c780339bb458ac52305ddee1393b208579b35870f4f55d558a2c2d88a3f494b` |
| noisy | smoke-mix-07 | 446 | 8.9200 | `365ac00836357e042d58bfee51049029126460ba70d1b5a34b65149b42655b86` |
| noisy | smoke-mix-08 | 341 | 6.8200 | `ec85db0c36038523428084f8c1c496b7f21c84c848c3ec2878a15857e03f3784` |
| noisy | smoke-mix-09 | 379 | 7.5800 | `a8790c3640ecd933c3001dd6ecc8fb8f76cf6aaedccb3d3868d46399be9b0390` |
| noisy | smoke-mix-10 | 330 | 6.6000 | `0ee1b4190eb7bee575a7b3bc027709ef8bcba85c2fab3e7ec80e98b36f6a0ba0` |
| non-speech | smoke-music-01 | 490 | 9.8000 | `16816b033ee7dd344c4ea27ec11570d2e9a71b9b6f0bc8cf5602209d0389a352` |
| non-speech | smoke-music-02 | 500 | 10.0000 | `5e6ef0a8628e835c12695106dc7efc7ee1d111aab85a8d651d6a17d8e0d63b9e` |
| non-speech | smoke-music-03 | 4 | 0.0800 | `0232fc1aa04127ac54b7a75c86d8133147a71b2ba54d3302fa376d578a72cc83` |
| non-speech | smoke-music-04 | 500 | 10.0000 | `87d715c4c24caa22fa0c19c0e13a4677f23839bbdf66090d7508cee4820cbd9a` |
| non-speech | smoke-noise-01 | 117 | 2.3400 | `e8b191218acc6fc1028836d2317891fe5286e9053fba9ef9e9f13c648e31791d` |
| non-speech | smoke-noise-02 | 500 | 10.0000 | `89d1b4ce683fa977698a5db9354bf7351634dd8bae60a03a54f993e6532c4275` |
| non-speech | smoke-noise-03 | 260 | 5.2000 | `bfbef13923ab018346788815fe51dab247379f1e9676a3007107a0886d8474fa` |
| non-speech | smoke-noise-04 | 8 | 0.1600 | `9e913740fca965b9f6b3dfa7be61d5ecf013a65ae9b3ef8336780304a6c37deb` |
| non-speech | smoke-silence-01 | 0 | 0 | `5bfa337b9e44ff3037e630698504a9cc7534975236da9fa386dc4967974c6e87` |
| non-speech | smoke-silence-02 | 0 | 0 | `945421d2413ce68a430357994de2cc93afba40e5b1725172ad930884bceb973f` |
| tts | tts-smoke-01 | 134 | 2.6800 | `7f27bfa40e83842f713bc93328da9eec0c0fcd2c92ca123ada8c0ef36c5508c1` |
| tts | tts-smoke-02 | 167 | 3.3400 | `49dcdc9aafc2aa11dde96fc70f73f1e009cc6cf9728b29e1d3ac0a01deef3e36` |
| tts | tts-smoke-03 | 141 | 2.8200 | `5686127fc07357c07b9a730ebf4dae5c844037aeccc257ec0600bff0e6102b53` |
| tts | tts-smoke-04 | 168 | 3.3600 | `f0b11ca502ffd501effaf9b96e89c890c67b713b6cf293ac2c574e6962961bf8` |
| tts | tts-smoke-05 | 143 | 2.8600 | `594d1a72ee34b8fb6fdd4f55ccc54726679787a5171619bbe2f0c4c069cf15af` |
| tts | tts-smoke-06 | 156 | 3.1200 | `0216fae69e3852863b0e69b063e5188bcf14e2b0f5d8775fe7d1a05de1f23638` |
| tts | tts-smoke-07 | 145 | 2.9000 | `35f318f8d0c4e230cd3f6f3ced543684bba1ddf4b3a6d314cc5412bb617566e4` |
| tts | tts-smoke-08 | 185 | 3.7000 | `00f27b3d868ea6bf2e0fd810e6efd81cbcb0562d40484a6fb855d022a4928282` |
| tts | tts-smoke-09 | 136 | 2.7200 | `1036902403fd4b1490a94e7f4c16d879b740adb2413ed776e18bf9ad56de9fae` |
| tts | tts-smoke-10 | 145 | 2.9000 | `9c59a359e7b564f073b51f638418df7f30f3360521a9b325e3ef6dae6c432b32` |

Parakeet: not run on target cloud (a CPU target; FR-0.7-07 runs Parakeet on the GPU target only).
<!-- report phase0-smoke-cloud-20260930T170440Z end -->

### Colab T4: `data/runs/phase0-smoke/phase0-smoke-colab-20261002T140101Z.tar`
Made by the owner with `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` (`phase0 smoke --target colab`) at commit `7c27dd5` (OC-0.7-01).

<!-- report phase0-smoke-colab-20261002T140101Z begin -->
# Phase 0 smoke run: target colab

Bundle `phase0-smoke-colab-20261002T140101Z` (bundle format 1.0, docs/runs/PHASE0_SMOKE.md), written 2026-10-02T14:01:01Z on colab:718ce26c003c.

- Machine: platform colab, Intel(R) Xeon(R) CPU @ 2.00GHz, x86_64, Ubuntu 24.04.4 LTS, Python 3.13.15, GPU Tesla T4.
- Code: git commit `7c27dd53e670d1a207be8738873eeb22bc1ce968` (dirty: false).
- Locks: `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`, `requirements/aqis_lab/phase0-gpu.txt` sha256 `837342085aedf769ce4bf8de055ec0168ddc9ee3667b7ab14865592d8157b451`.
- Elapsed: 374.4547 s (NFR-0.7-01: at most 900 s on the cloud VM).

Every number below is printed from a file of this bundle. A table row names its result row: add the bundle's run and score folders to a results store (`python -m aqis_lab results add --run runs/<task>`, then `--scores scores/<table>`) and run `python -m aqis_lab trace <row>`.

## Runs

| task | run card | mode | clips | results.jsonl sha256 | events |
| --- | --- | --- | --- | --- | --- |
| vosk-batch | `daadff54bb7238a62ff71f779aa5e5316a7df1e7bf936d6cf262ed3912d83384` | batch | 60 | `3c08419f3867a4feaffdae3c5ee128682b900352593ce95dd2e6e8cc5d1d6eb9` | 894 |
| harness-vad | `482ec4f183dfdefb69e64591f938d834a54e477a9089c35d570168c5dbce0b7c` | batch | 60 | `518b9f1533ebb8ae656a5f9153c1d3f93c0203dcd9fb8bd1b76658cf692bda14` | 462 |
| vosk-realspeed | `21574e5ca8e07c54312fd184a5e15bfd3837ecef401eb1bf4196de870e659ca8` | realspeed_cpu | 5 | `8fa40e89250383e28fb96d71a99909671c16e7a1535fb88b45fe7d2e797a5e51` | 81 |
| parakeet-offline | `7b4eef66a74701d8a259b10bb9aa425052fcf626aee3cafce2eb5c3f0dcd1c63` | batch | 60 | `4053203fe03511ac01f26a0d0b418e860f9a2f5cd0ddd51b58112096a1705503` | 182 |
| parakeet-compute-delay | `223b42abba178bf7d519e941ed066d5bc19c320e5f58c4b20c0c4345ce98c80d` | gpu_compute_delay | 5 | `4e06d2aaca80f23233a185e5720e3d6db8432f6237ab616246373d557b6b2b06` | 17 |

## Word error rate (WP-0.3 scorer)

Tables `*-synthetic-tts` are synthetic TTS speech: plumbing only, never a model judgement (docs/data/SMOKE_PACK.md).

| table | variant | corpus WER | errors | reference words | corpus CER | summary.json sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | disfluency_aware | 0.1074 | 74 | 689 | 0.0528 | `974cdf1fef8befdb0d3f4503d92657e54456ffb63b31059b99fe341d313cb1d5` |
| vosk-batch-natural | main | 0.1074 | 74 | 689 | 0.0528 | `974cdf1fef8befdb0d3f4503d92657e54456ffb63b31059b99fe341d313cb1d5` |
| vosk-batch-synthetic-tts | disfluency_aware | 0.0476 | 3 | 63 | 0.0115 | `55698cf450b1215ceac133f62a087ca95e4bd34561af6fa67f3837f947cf917b` |
| vosk-batch-synthetic-tts | main | 0.0476 | 3 | 63 | 0.0115 | `55698cf450b1215ceac133f62a087ca95e4bd34561af6fa67f3837f947cf917b` |
| parakeet-offline-natural | disfluency_aware | 0.0058 | 4 | 689 | 0.0024 | `6c92791b4bc7c11a9b62c01b90147e15423de418924722a9fd32e51058413156` |
| parakeet-offline-natural | main | 0.0058 | 4 | 689 | 0.0024 | `6c92791b4bc7c11a9b62c01b90147e15423de418924722a9fd32e51058413156` |
| parakeet-offline-synthetic-tts | disfluency_aware | 0.0317 | 2 | 63 | 0.0029 | `611f70f5a93463d03cefa665518f152ed1043f850b7c263cc629f0bd4799f7ea` |
| parakeet-offline-synthetic-tts | main | 0.0317 | 2 | 63 | 0.0029 | `611f70f5a93463d03cefa665518f152ed1043f850b7c263cc629f0bd4799f7ea` |

### WER per clip (variant main)

| table | clip_id | wer | errors | ref_words | row |
| --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | ls-test-clean-1188-133604-0029 | 0.1111 | 1 | 9 | `264c59387cfca00536b0d77f4ae82d406e59757df282e527469b44f705b4028f` |
| vosk-batch-natural | ls-test-clean-121-127105-0012 | 0.1429 | 3 | 21 | `2b3047208600b878bed892079b4cfaa36d0df3fc07e837b13dc4a0de677cf3bd` |
| vosk-batch-natural | ls-test-clean-1221-135767-0014 | 0.0500 | 1 | 20 | `05c05ee6c96aac7d4e4d46c66fa6d0d6ec5c044a02a03430477bbedb6f94fea7` |
| vosk-batch-natural | ls-test-clean-1580-141083-0035 | 0.0769 | 1 | 13 | `ed6e665326f90308a6e7731d869f3fc2f4098d9453e8b4c97a4c93976aa5eb76` |
| vosk-batch-natural | ls-test-clean-237-134493-0011 | 0.0000 | 0 | 19 | `566db855ad13fefab38af0829e67c7dc67f0bb9ca0315a9ef105910a75c3fe39` |
| vosk-batch-natural | ls-test-clean-2830-3980-0007 | 0.0909 | 3 | 33 | `cf789692f8943f3b2e57468895a8c0b63aff5e6dbe2bf911d67f84460983dab1` |
| vosk-batch-natural | ls-test-clean-3570-5695-0009 | 0.0714 | 1 | 14 | `801fa5b591d7f46e51c70185a197f72458ea8beafbddc4fc2eb9b5dd26b279eb` |
| vosk-batch-natural | ls-test-clean-4077-13751-0014 | 0.1471 | 5 | 34 | `8239542b20497e284d933768edbd913e5199df4d80d6f6f3f0dfda747d5f4305` |
| vosk-batch-natural | ls-test-clean-4446-2271-0024 | 0.0769 | 1 | 13 | `8faa987ecaf52314d7283db7d09ddb1324a1b438c9daa81ef0470602787818c9` |
| vosk-batch-natural | ls-test-clean-4507-16021-0058 | 0.0000 | 0 | 8 | `756281d5dd4ff3743980bc4862f7749ddf50ba4aa5540b2fdac28cc052c05808` |
| vosk-batch-natural | ls-test-clean-4970-29095-0002 | 0.0769 | 1 | 13 | `5c2c053dd2fd36b6c0e412c7a7db4c9151dbd3d485aac67de54db16284514b88` |
| vosk-batch-natural | ls-test-clean-4992-41797-0015 | 0.0333 | 1 | 30 | `e97c1c3c44646f1b83687166532f8a6014acfa96b1877836ec6dff8b0a1b86d0` |
| vosk-batch-natural | ls-test-clean-61-70970-0011 | 0.1333 | 2 | 15 | `60728020d172e7e33e4db8c16e17f707c8579a34a40ee634726bccbe51cfcd0a` |
| vosk-batch-natural | ls-test-clean-6829-68771-0030 | 0.0000 | 0 | 17 | `2d974fd2f585d12b07f72ca988559f27efaf9887c386681cd1865d96d09f95f4` |
| vosk-batch-natural | ls-test-clean-7127-75946-0009 | 0.0000 | 0 | 12 | `4926246fc3650e94550d46ffa17ba1428b71b14b58480f54489544063d6824e4` |
| vosk-batch-natural | ls-test-clean-7176-92135-0018 | 0.0370 | 1 | 27 | `3c3b9469589045dd248d9acb0dacd9b12cb8b19650dba05c264bbfe08c24b427` |
| vosk-batch-natural | ls-test-clean-7729-102255-0023 | 0.0000 | 0 | 10 | `6ae842679144b912f4ea82a5988ec622016b9a69f1048f56c70e810aec146cac` |
| vosk-batch-natural | ls-test-clean-8230-279154-0011 | 0.0000 | 0 | 12 | `7bdd777af7c20b5a5ad81cebf788843059487986cc175e0a69a1c8026db5d021` |
| vosk-batch-natural | ls-test-clean-8455-210777-0037 | 0.0000 | 0 | 10 | `b453e612227666044bf8526b5de59b9ee3764306be02107b2f5d3e42ef397b87` |
| vosk-batch-natural | ls-test-clean-908-157963-0014 | 0.2727 | 3 | 11 | `28e9fab4d9a8ac7c698795564d91a5daf0249f57b3886565791b3b9814bbac77` |
| vosk-batch-natural | ls-test-other-2609-156975-0000 | 0.5455 | 6 | 11 | `6cfafe4d4ab95fc213fbfaa04e13d80495eabe35833b8a69aba8598d1fed6f48` |
| vosk-batch-natural | ls-test-other-3080-5040-0016 | 0.0526 | 1 | 19 | `b2a35d1003febb14b3233a166a3d5596b7a264cf96d481d31813a1ba4d7ae28c` |
| vosk-batch-natural | ls-test-other-3528-168669-0043 | 0.3000 | 3 | 10 | `01947f9c30a9ae7734859e184897c46104e15db8231e6ffc4503ea9f0e67a058` |
| vosk-batch-natural | ls-test-other-3538-142836-0006 | 0.0000 | 0 | 18 | `ad3079bfce157d505b40aa0837095e45d8f98cd83bbc8ae9f17a10bff1ba76a6` |
| vosk-batch-natural | ls-test-other-4198-12259-0026 | 0.4615 | 6 | 13 | `0c4c7e35215b59b43283d204a63fc493e614b79c5273e7f94dcde9634e4ea11c` |
| vosk-batch-natural | ls-test-other-6128-63244-0013 | 0.6364 | 7 | 11 | `4a7b481ee7f1066197a8cb71d07fc34f46ced0705406a6753854cafca3ab720d` |
| vosk-batch-natural | ls-test-other-6432-63723-0046 | 0.0000 | 0 | 19 | `500ac5f0e08fa7441f27b2a6b2c4ee1583bf93261bb6fd85a6945ee87cc6a7b5` |
| vosk-batch-natural | ls-test-other-7105-2340-0033 | 0.0000 | 0 | 27 | `6a50d1b8a8875ffdb1378f9124cc64abc19b30778860cd8782c76c9e090d90af` |
| vosk-batch-natural | ls-test-other-8188-269288-0027 | 0.1667 | 2 | 12 | `568bee79e23f20f4dbe52335fbfb6e7276092e54923e40d377dbdfd9b78cc95f` |
| vosk-batch-natural | ls-test-other-8280-266249-0004 | 0.1176 | 2 | 17 | `3fd2d40960591c15fdceebeec86ecd53b0f8e4d7b7d68c72d3733fc359b91f4e` |
| vosk-batch-natural | smoke-mix-01 | 0.2500 | 3 | 12 | `ec65f6b39f5d165afe8d3721ad35621bfc322b7b8a8832c0efcdd9d8e5fa583f` |
| vosk-batch-natural | smoke-mix-02 | 0.3333 | 8 | 24 | `ee6fab5cbf165475b95bad1537d199b938618a0de32c0a7b71ab48174a103c32` |
| vosk-batch-natural | smoke-mix-03 | 0.0000 | 0 | 19 | `5213089d9322b8ad2b8d89c57a9a25262f36d062cc5ee3560695d958695c3458` |
| vosk-batch-natural | smoke-mix-04 | 0.0000 | 0 | 14 | `274bca257273c509ce6440e7435c67423232085a6813c4001f2057172f8e1077` |
| vosk-batch-natural | smoke-mix-05 | 0.0625 | 1 | 16 | `f268e52de3b397db6b6cd3059b9c7452509182bf70702b6f884cfd9e216ddcbf` |
| vosk-batch-natural | smoke-mix-06 | 0.2000 | 2 | 10 | `54a505867aa82bdef840331caea701bbe335e83e8ebf68fd2bcdbc74cb741284` |
| vosk-batch-natural | smoke-mix-07 | 0.0385 | 1 | 26 | `ae03b4d88f29d294ba47b851eadb181cad428b763234c5ae609c3552eb86241c` |
| vosk-batch-natural | smoke-mix-08 | 0.0870 | 2 | 23 | `a173d18c9e5de248f352d9b82a1a71c72808a36614ca568b82c2fbf3d4065e59` |
| vosk-batch-natural | smoke-mix-09 | 0.1481 | 4 | 27 | `46619bef3800f4fc5ab2c13cdbeab64bc2ef37de59ed0e3176048f8a62b8af6f` |
| vosk-batch-natural | smoke-mix-10 | 0.1000 | 2 | 20 | `32b500b140207bd0b5f3e99187f17a7156e3e00bbd963571f4eb12c0557321fd` |
| vosk-batch-synthetic-tts | tts-smoke-01 | 0.0000 | 0 | 1 | `9736b8aba0457e32fc8815403420dd3431c71ec8915117b4be1d52a263fb6039` |
| vosk-batch-synthetic-tts | tts-smoke-02 | 0.0000 | 0 | 10 | `ffc9110296938acfbed07d71349f02eea61eda153e508fd78d2c968c640ddfa6` |
| vosk-batch-synthetic-tts | tts-smoke-03 | 0.0000 | 0 | 1 | `0f228f8a965ddd1d96a78f5ade243ea545715b689fc54b41ff19fdd2a8ab7e2c` |
| vosk-batch-synthetic-tts | tts-smoke-04 | 0.1111 | 1 | 9 | `d5e3382f04ada15737d4e79300c3962d7154ac2fceb71d752ffd6c2dd4c1990c` |
| vosk-batch-synthetic-tts | tts-smoke-05 | 0.0000 | 0 | 1 | `bd5c1c8b349833ca4d4208e45d9a015808a5854c56e18805980c2fbf28769aec` |
| vosk-batch-synthetic-tts | tts-smoke-06 | 0.0000 | 0 | 14 | `149b42fd9aeb24e0c08a078a50247b0320f95b42a68e34622b40f6616c7092a9` |
| vosk-batch-synthetic-tts | tts-smoke-07 | 0.0000 | 0 | 1 | `74779d4bbe1aafb6ad18c2927e9cb045661454816c329f17741c61a319b09de9` |
| vosk-batch-synthetic-tts | tts-smoke-08 | 0.0000 | 0 | 12 | `8e4b1a8074d5c020f7140836ca1abf7126013588699eef65a7756fe3c5b6b2f2` |
| vosk-batch-synthetic-tts | tts-smoke-09 | 0.0000 | 0 | 1 | `df7da675123b0720c5caba6d361b4355ebd742d99cba9ebd188a27e2bac75f31` |
| vosk-batch-synthetic-tts | tts-smoke-10 | 0.1538 | 2 | 13 | `42c27600d5e3048559762354c8fe30625d639fed5dee299af96ee47af8a47b3a` |
| parakeet-offline-natural | ls-test-clean-1188-133604-0029 | 0.0000 | 0 | 9 | `98371a72dc947c1ba27bf1be243cbcc653cee26d030bd72507b863efd06f55a3` |
| parakeet-offline-natural | ls-test-clean-121-127105-0012 | 0.0000 | 0 | 21 | `e90808312d69c8b10271b6f2568fb7275549776b850fa365f7d9c432b1970f61` |
| parakeet-offline-natural | ls-test-clean-1221-135767-0014 | 0.0000 | 0 | 20 | `4f9c8bb65d428c8bd663876d1b9fe47cfce745ec9a615a65ad2fd29008ae180f` |
| parakeet-offline-natural | ls-test-clean-1580-141083-0035 | 0.0769 | 1 | 13 | `13e29c60c60122f34cd14ec639c6577baa4aae109cae8a6d1a7e8a89de473b71` |
| parakeet-offline-natural | ls-test-clean-237-134493-0011 | 0.0000 | 0 | 19 | `030526a09279e773cd7fbbd11bcad4b75cd7c495283089eed29f2b23acbcaa95` |
| parakeet-offline-natural | ls-test-clean-2830-3980-0007 | 0.0000 | 0 | 33 | `1646c937fd3fbff82bd7b660d64fda409e7dc5430e797555da0b5c369a9e2530` |
| parakeet-offline-natural | ls-test-clean-3570-5695-0009 | 0.0000 | 0 | 14 | `387976f921660b7298bcf45abc7e4190f561218cb47c14b7c9ce4648d72bb1b5` |
| parakeet-offline-natural | ls-test-clean-4077-13751-0014 | 0.0000 | 0 | 34 | `dc8f43d3ec8ecd80c237d7fc3c47c5610372d5be7c063b74bfaaf10897efb1a5` |
| parakeet-offline-natural | ls-test-clean-4446-2271-0024 | 0.0000 | 0 | 13 | `66e08226a760d17374601ce875c854ddb397dd5343dc76df7ac9b61469ea609f` |
| parakeet-offline-natural | ls-test-clean-4507-16021-0058 | 0.0000 | 0 | 8 | `3c17e622bbfc4bdf96184419191c6f126a127bbb36320d929abe24c738098f0e` |
| parakeet-offline-natural | ls-test-clean-4970-29095-0002 | 0.0000 | 0 | 13 | `57a284fe0b88c26b77193aa277036ca17a0c502592158fb48ed86c288006e86c` |
| parakeet-offline-natural | ls-test-clean-4992-41797-0015 | 0.0000 | 0 | 30 | `3dc568cf1d3d6109ba5d59617b6d76f1c1226d09989d67b852478c1a875bbd8f` |
| parakeet-offline-natural | ls-test-clean-61-70970-0011 | 0.0000 | 0 | 15 | `479432a16e5f73cca3eb68660899c0f416ddfb486ff12f19589d1a35c030f817` |
| parakeet-offline-natural | ls-test-clean-6829-68771-0030 | 0.0000 | 0 | 17 | `a08331c9dd6f1256c3ac90be57fbddc253b3d2595351144791a9cf1963ebd507` |
| parakeet-offline-natural | ls-test-clean-7127-75946-0009 | 0.0000 | 0 | 12 | `781287ace81d20b1a82095edc834bf738e03e5f1f8990ba91d35c2e8ee9a87b9` |
| parakeet-offline-natural | ls-test-clean-7176-92135-0018 | 0.0000 | 0 | 27 | `6bd01f2652b58c2c7792615402c933eb4462af5fb651678b70ecba080d12bc6f` |
| parakeet-offline-natural | ls-test-clean-7729-102255-0023 | 0.0000 | 0 | 10 | `a6fc24c922bcefde56d18bd51506826d6f25160d6c7ce0501c140351b2a41020` |
| parakeet-offline-natural | ls-test-clean-8230-279154-0011 | 0.0000 | 0 | 12 | `1f3e853b3074551011255a66ee187cb8680ec266e46f7502a720dce6b5b904e0` |
| parakeet-offline-natural | ls-test-clean-8455-210777-0037 | 0.0000 | 0 | 10 | `ed9e98088ad394c25ab418af0fef897348be50a957c0be33e3b30b0dbddc9694` |
| parakeet-offline-natural | ls-test-clean-908-157963-0014 | 0.0000 | 0 | 11 | `b4b3dcd0070f121a39ac33f811ea223f42312eb411e250e32994c1b3d21fa33b` |
| parakeet-offline-natural | ls-test-other-2609-156975-0000 | 0.0000 | 0 | 11 | `b69059efa629d898ab4f343916cec13e1a1961516d4d6d4ec5bcf171fb54d61d` |
| parakeet-offline-natural | ls-test-other-3080-5040-0016 | 0.0000 | 0 | 19 | `7b0746837479061420090b3deb62717a78a075c444a1c9e196bf4b4b2873b38a` |
| parakeet-offline-natural | ls-test-other-3528-168669-0043 | 0.0000 | 0 | 10 | `14242d79d684adb4ffbb7c352fd72a630ea4b3658849d9a4e93931e8e8a8a273` |
| parakeet-offline-natural | ls-test-other-3538-142836-0006 | 0.0000 | 0 | 18 | `bb86c2f8395ed15101a22081cce49a4833702221b3a54f47b9a7e66e351168e8` |
| parakeet-offline-natural | ls-test-other-4198-12259-0026 | 0.0000 | 0 | 13 | `e58b84273622d481c85b9805d2e8f85d0566e34fa44f8146519d8f6fe23486fa` |
| parakeet-offline-natural | ls-test-other-6128-63244-0013 | 0.0000 | 0 | 11 | `5d311990e195ea226986b1fd9ca4d743f9ad401de5b32e0d8fce01e96ebc5cca` |
| parakeet-offline-natural | ls-test-other-6432-63723-0046 | 0.0000 | 0 | 19 | `669bebf991586f18b91099313cedae1782c6760b6f9b745f31e504714e68a48f` |
| parakeet-offline-natural | ls-test-other-7105-2340-0033 | 0.0000 | 0 | 27 | `fe6b42bcf4f0813fa48fc13e09fc198e8a4d74e22d87746d57698d4b939d19c4` |
| parakeet-offline-natural | ls-test-other-8188-269288-0027 | 0.0000 | 0 | 12 | `9029bc6bc0ff059e30d32bcc5669cfb5fb081fce2851a16d6cfeb84ddfeeda73` |
| parakeet-offline-natural | ls-test-other-8280-266249-0004 | 0.0588 | 1 | 17 | `47ecc363b8bf131616b633ecb28518fd196d59bdea4dca2fe42098d7b3870647` |
| parakeet-offline-natural | smoke-mix-01 | 0.0833 | 1 | 12 | `2a52a2a57680597233086fb88ab3f78dba0e7bb19a2c595a9f90a93a915a273f` |
| parakeet-offline-natural | smoke-mix-02 | 0.0417 | 1 | 24 | `44fe377d580d3afa43b1280f2d4e03a01d5854f0727b2af8fdb6438ec048cd0a` |
| parakeet-offline-natural | smoke-mix-03 | 0.0000 | 0 | 19 | `37fe5f0c7441ea556524f9182ab61ea39ac8835629156f3a2a836984c8cfa9b8` |
| parakeet-offline-natural | smoke-mix-04 | 0.0000 | 0 | 14 | `b392bc2257da8bfc639f930d5ddcf93db00eb8f7b6aa5d33b44ca9f82552af8b` |
| parakeet-offline-natural | smoke-mix-05 | 0.0000 | 0 | 16 | `2ce785120497c5367168377bc278d7c6f690b5460d38ad21b4acbd6785d00cb4` |
| parakeet-offline-natural | smoke-mix-06 | 0.0000 | 0 | 10 | `e14ae2f39799cfb01e54f3495a4d43e9ec8bcdcd8486a90f4d63a1433c472e1d` |
| parakeet-offline-natural | smoke-mix-07 | 0.0000 | 0 | 26 | `f5c9160664ea14aac710bd9647fa5fed6cbfdefdbb32784ad52d6feb33a5d24d` |
| parakeet-offline-natural | smoke-mix-08 | 0.0000 | 0 | 23 | `c324071579623d099f4af522d3663951c12e29e162b97f443b0fbe83c160fbb1` |
| parakeet-offline-natural | smoke-mix-09 | 0.0000 | 0 | 27 | `a2391fdfa10be1e5992cc60650da645df3702468b819ea342a5cf8326747d65d` |
| parakeet-offline-natural | smoke-mix-10 | 0.0000 | 0 | 20 | `0b8d4f6bdc55dcbb8ca3b2694d902ff5ba66bd36c235be41c3b4d7e517b68b20` |
| parakeet-offline-synthetic-tts | tts-smoke-01 | 0.0000 | 0 | 1 | `c6f4769f8add0e65ada88833d400ed93fccd8f1b25264a435a3fbffa5732ae59` |
| parakeet-offline-synthetic-tts | tts-smoke-02 | 0.0000 | 0 | 10 | `e674dd8129cb2548cfa0654b4b06c608b945340d005cf4752f7322daf69d394c` |
| parakeet-offline-synthetic-tts | tts-smoke-03 | 0.0000 | 0 | 1 | `3d1b25ae5d3d61d1836c82c3f076c04a969c85ab8c7880c46301450d5a7f8014` |
| parakeet-offline-synthetic-tts | tts-smoke-04 | 0.0000 | 0 | 9 | `588ca8cbb91a85db0b874201e068acf205cf85e1a46670361a8c160f2f0dc9aa` |
| parakeet-offline-synthetic-tts | tts-smoke-05 | 0.0000 | 0 | 1 | `8d05d49559bf5497f5f3cbd449600cfd76e7bdea84ed4dfea662ab9f60f54001` |
| parakeet-offline-synthetic-tts | tts-smoke-06 | 0.0000 | 0 | 14 | `a2aedaeb7f0e58353debd1f21fc1a2ac46714014841aba55dd1706c03acdb09e` |
| parakeet-offline-synthetic-tts | tts-smoke-07 | 0.0000 | 0 | 1 | `78dc0f1f41eda63be98817616ac4bfe77923109388f01b1b8561f2bc5412b175` |
| parakeet-offline-synthetic-tts | tts-smoke-08 | 0.0000 | 0 | 12 | `6e167eeb456c9803ca21d7ba27eff20e90c4fc3eb3adf7706dda2751ca99e0a8` |
| parakeet-offline-synthetic-tts | tts-smoke-09 | 2.0000 | 2 | 1 | `a37c011ca0cf217f0944fd2362267e0a3d706eb87cd3df17e581d4131ddc6779` |
| parakeet-offline-synthetic-tts | tts-smoke-10 | 0.0000 | 0 | 13 | `72c527c61342fb13243b5363cb77e4668518cc66e08ed26c0411f1690cc51193` |

## Vosk batch transcripts (60 clips)

| category | clip_id | words | text_sha256 | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 9 | ed0cdc46462af3fd85466e4075531ee6d435532e1ec02e0590bba2cf4537a288 | `61000cc70e72a1d2ed3ec200e40e117e0cd86e20a4d3df1db560c9e84af06e07` |
| test-clean | ls-test-clean-121-127105-0012 | 18 | 699ad819bfcf8b39789087c3f0b15bf114c1c75b75f6e8ef6f0133c9ca259a29 | `9b25600b1c67df8d3911596d735fca808dd6baba17bdcedbc000f2ed67e1d39a` |
| test-clean | ls-test-clean-1221-135767-0014 | 20 | 77eeb5c74e6a837f48d06d5d1c6e82e20d660dfb2f67893eb1545cfb971a1f5b | `a435fb4dad67b63af26f167df55fa8384638f835b36240fc289f2716c29f8c47` |
| test-clean | ls-test-clean-1580-141083-0035 | 13 | 7ed7925898bfabeb4443421409c639975eb0d4b8e1e5791df7871786d038e48e | `6676491f25958e92e47f5b3de212e74604fcf820ac0324d06b34ab86e07a2f82` |
| test-clean | ls-test-clean-237-134493-0011 | 18 | cd082978af6d92788438beec92e61403187c2a8d86ce1802c07fb22976191948 | `1ceb2e86950f92c274130f988091257909e96eb7732b22d1429affd9a545fe6d` |
| test-clean | ls-test-clean-2830-3980-0007 | 33 | 36af36ac244f4016d204bd3b991eb497bf48a15378c9434b726cb95846437cce | `108cf2d2e3cf9328c2e68ef2a06544f16e8bf4ed70788b2773b43f91c276b150` |
| test-clean | ls-test-clean-3570-5695-0009 | 15 | cff865c42fc22044f4f00219966c7fa5ff6d5718c9ff254e632e78630becf5a0 | `05ebb45812c2281f2783a44eebebe48e991133e4dbf5693783a0825071a3b8be` |
| test-clean | ls-test-clean-4077-13751-0014 | 36 | 79d2318af8535b69de087760526f0ec46274301bf72765f91266629cb4b3be9c | `40cc29a7679b4025e3ef0689017b49131a9f27bcc6ce8871426f657d00d287e6` |
| test-clean | ls-test-clean-4446-2271-0024 | 11 | 74d466a6d2a3cd1a476bb21b1227a108c9f342eeed7caf78905599b9d01fa9aa | `708f9ab4bf1c904c3ed4d3049fbc01942df1f0ae985b25e008b077c9cbfbab34` |
| test-clean | ls-test-clean-4507-16021-0058 | 8 | c236cd7f13c7f2639ac253c309b6c21d546aac29f50593b3ba1e7f84fe616c8c | `5438153e612602e60b7124640715d1ffa3b6eafc585236214100ea4cb9451250` |
| test-clean | ls-test-clean-4970-29095-0002 | 13 | 65fe9e8d47aff0d42b5918fa9aafe611fdddc93b8858e466b9577efe91a7ad12 | `1bc7670232be46e3d6a7e443cadad645595c41695aeabca735c78d11267e49e3` |
| test-clean | ls-test-clean-4992-41797-0015 | 30 | 1fc5773314919c8012f97d56723388a6befb7c5cc17f463fa830398330a0a4fe | `7c0a0230d9b356449afd966a12e13998c18876458b0beed72a0ec202a9bf29f8` |
| test-clean | ls-test-clean-61-70970-0011 | 16 | 75e669b68ccb7686f78d6227dbbfc25e9f66e3dc6b817b02a2fab5c1196d94b7 | `ceb5716f1f9e8b501449c847dbf9298fa94170e8d0285849116e377bddf16b25` |
| test-clean | ls-test-clean-6829-68771-0030 | 17 | fbb99918869de67cd11ecd35fccf05d3b9ba7ba0de5d1183db2ceaa10a3ef5f0 | `db6fe8ff95d0b15d77e36edd24ee3fe2fa87bd8e6009b079cdc5f26d04d88bea` |
| test-clean | ls-test-clean-7127-75946-0009 | 12 | b65a6039e3d0f4bdde3eb8f7c193af2bf48ff82369965e3310e3ccab78bc0d08 | `6a83e2689e4d5282bee3e637dbe56b341103269835489b9975ba76565cb9193e` |
| test-clean | ls-test-clean-7176-92135-0018 | 27 | f49073c8aa17da02b2b0639369978d3a4c4af8dd74a1cff0f4614953a2ac666e | `2b1c56c11ca96827cdd946bd6d6bd571500a7d1fa3b8561ded1808a4bd4f6125` |
| test-clean | ls-test-clean-7729-102255-0023 | 10 | 996a32b70e1851af5372a32bbc2b2899bf06bbbd161a9414a1f99118f26a8a24 | `5954c6d74ec9a3cd8cdbee85674e54815ec40b39d328bee0fb564d177f863533` |
| test-clean | ls-test-clean-8230-279154-0011 | 12 | dc8cb596dd4211fd11b0e55f11f8192c425d43957fbc795f33d5f8be372b78ff | `f2ce10d86ab3831eab331a384a3d2c317d1c8284b6c6529d8430c303345f8df9` |
| test-clean | ls-test-clean-8455-210777-0037 | 10 | 4af3329969e0f398ea43d2be7b278776baa1bed28e313c0e2f091da363256aa1 | `503bd157772d9b25b264cba6c1653281d3207a9b42f30ad7c112f5a888eb8326` |
| test-clean | ls-test-clean-908-157963-0014 | 11 | 35bb92d7da9f5472ab74a0fd16688e9739d86999017882ca2c8358a3a5dfb405 | `083e406d6d1f420d1a6c5691bd2a16cd8ce9d8e08407aefb360a114c6c3c8caa` |
| test-other | ls-test-other-2609-156975-0000 | 12 | da4a25a42447ac2efb2c4bf427ee83cabbf789e51a20cfbe95fda8461c26d76b | `f75a5aec1b09f9926461bf34d93c5740205ff54ca50876895aeee76f9c975677` |
| test-other | ls-test-other-3080-5040-0016 | 18 | d95e960697381f2d028985cd69b7569eb5cfeaaf3adb33e47449f3f0dfe694ad | `651088041c3c01362372fcb0d8c4beafeb62b21ccc96afc08e3d264e32a0df1d` |
| test-other | ls-test-other-3528-168669-0043 | 10 | d071a0bdb47a8d924c03c62240613d04335ed61caec31ccde0facef042f92f84 | `7ee2131306b78476da0b5cb65a2075a91df22c0a9209c9c811c9d4139e42bee9` |
| test-other | ls-test-other-3538-142836-0006 | 18 | a3e636a5813ed01e48756a32859c4a32cc5edb17c700a1410d0eaecdd65a4284 | `29a1ac468744eb185058bf6f3ef135e54c8ae3a785912294c07ede342c4d46bd` |
| test-other | ls-test-other-4198-12259-0026 | 15 | 776f18edf77e50dd07f3de821c05c8bd71a0696fa27e36433e3c0ac5b227dc50 | `4a2bba97d6f6a78e3fda53de161eaec4c6ffe4909a1b8fb01e3ba07ddcaacf6a` |
| test-other | ls-test-other-6128-63244-0013 | 10 | cdc1c8aa9174b98c2eaf0cfe2ddb73d6b2361c347227b38a2ffc0d5ead5c4383 | `6b86b6e0e84c5747994a5b97e4f2e3d935c2727f7d9e4a64079d7a11f98341b1` |
| test-other | ls-test-other-6432-63723-0046 | 19 | 956415288c8bf740b9b8db8f37e1ce15ab817f88578afe8fb2e744bc0c1cea82 | `bfda596afe6fc3eb093d427611ecc7ccf31460a509a47bdff0993a138ce1e47d` |
| test-other | ls-test-other-7105-2340-0033 | 27 | 92114c1d59b5d0e04984e651dd151729faf41453db2b7dd9bad84ddf04b6ddc6 | `fdda5585dee92acb27acd7846bca23fa0f7335ddd7063edd981366a5bb4e2433` |
| test-other | ls-test-other-8188-269288-0027 | 12 | 042a2cba559599707040b61d71bb8df67fbad439ae2ef02ca43ae18b2cb575c8 | `5f88e7e1b8764f0547c10d5b9e6fd311017fb2f40c26533b7604c12493fc3e34` |
| test-other | ls-test-other-8280-266249-0004 | 17 | 35ada150736b31211d48d52d8f5d96f4aafde1413bb34eec1e865cf4e0551e58 | `dca7f5f533bff7b723b2d5fb4edf3209fb3224c2c05d8bd68c4e98cb59c42155` |
| noisy | smoke-mix-01 | 12 | 87910b29bb221a77c7c49aae0d15a1f4c1a9473281f693bf5024d4b56e62e2ab | `bbc66521b85028e84f21038190bf3af53070824c63908d92cf7fdea7244ba420` |
| noisy | smoke-mix-02 | 25 | b888aff1a8cf3bd2a35cc8cedcf51e7015fff0800587946491ae250e2dfb0590 | `fbee3b6e78a9e37800cdb700831fe6fec68406d79f4caa797a7f1f1f363d889a` |
| noisy | smoke-mix-03 | 19 | bcf0d81630c3e6bc5224d712424e3cea1d7b711ed7f35bfc7a7ae97b34b50b37 | `482f4eac93ef0f87fe1903b448419f669ef1f205de14dc5c150e12dd280b2605` |
| noisy | smoke-mix-04 | 14 | e758403d33ad61c1caa27def162b7e7c6303b3756016c7a6013ce7a9bc3332e1 | `636d46d140698f40de3a066b8d29e717e9ae16ef515b65ba05ea5b47173a5cda` |
| noisy | smoke-mix-05 | 16 | 070d138be7141aeb954c90b79b133fd709a9471b5d07f0371116e2c7c44f476f | `8b9b0be9ab4d0ae052d4456779e76b638de054a7487af01bb5762101983d6eb6` |
| noisy | smoke-mix-06 | 10 | c504300185d5fe7dd696fc1fde33810a22f1973177c97c9f4ff00c80099977ff | `642251d982c08781c33761726bf25a850519fe67e17aa912fbe69695aaa57ddc` |
| noisy | smoke-mix-07 | 26 | 40a2aaa60d1da5489c171a1642ddd15cdc11e92ef3dee6d7c0cff31970c7f034 | `036c939c88b7521c2953ac35fb007ae54de34be7ffe77888034fc3a5b02008e8` |
| noisy | smoke-mix-08 | 23 | 150510b8461a309c5c4c998501060512397fd365cc24b69db00c4ac29c957563 | `b854ed05ab998fe038f0710c3b35e32b68cc99cd3432ed195e82dc383279e5fa` |
| noisy | smoke-mix-09 | 25 | 6a6abb83e505d3353861d315868bc023638ba33dc88d11b2399f732ad49c0c88 | `e8e77101341cefff9e26d80ff23cd672a4e40ec3bc12aa117b083f896db2c921` |
| noisy | smoke-mix-10 | 19 | b37dd1a23cdf37e3bbcadc14374e046e3772400577924656ea82b6c28873391c | `db7b0e02e6c56e8133924215b747f21501e07d54648b73b2b8cd75c095790cf2` |
| non-speech | smoke-music-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `ef68609107f6931863c5c96bd1f74fc4403d0eb5eb7997d8542bcb50f3d524b8` |
| non-speech | smoke-music-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `1116d1294b1cf90367ac6b34865a2727871c8c87580c8588942a6575474076f3` |
| non-speech | smoke-music-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `f0922d4adaa105de146a6a7ee19b5f1a11571fcadb4958bb2e51897978793a99` |
| non-speech | smoke-music-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `2484b3c96e4bc93c12bbbf0812221d5bb33807e879fefed5b7ab4f5ea5f53338` |
| non-speech | smoke-noise-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `39915043ab9f2792dcaf210e0a16b5934abbbee5546b4e35b5937b8c191198a7` |
| non-speech | smoke-noise-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `80657cd7d73271ccabc2dc49115362bb40ee1c251baff23c8af0f0f179044507` |
| non-speech | smoke-noise-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `28cc33ee9adefec123f61ceb026bc7cb5d0778fa7fc0e37001bd25a9a8f2e132` |
| non-speech | smoke-noise-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `d8bc13e174e67715b3cf8321efa0b6f067fde74b4dedd494bd7e683c985b5355` |
| non-speech | smoke-silence-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `1df70df38bee17792e9faa33071ff4b1b9454f1bef619613f874f65da99321bb` |
| non-speech | smoke-silence-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `f8744bbf6eabd7873fc4675ac548e972583ad0d268a39d7394d0791d484bdac8` |
| tts | tts-smoke-01 | 10 | 30640fce942d691c56bee86a2c000dfa620f2087b3ae22ec8abfd29c65b1eae1 | `f80bfdc5fedad8401ac62b93d8365f4f5405fcb3874f220b68d385e2e37929fa` |
| tts | tts-smoke-02 | 10 | abfd320d882a8ec2ab888bf778f93eb52b29468e59b83822a313cc0e2881b132 | `6f7035f0eefc29b0d2857106bbdb6b1a2a9a70335a33a4e8ecc79b5bd2860cd4` |
| tts | tts-smoke-03 | 10 | 25174bb2bfba68f128584857466e3aedcfbff528c3f8db91ffb1e738affc996e | `7b7c6d2793fd401678e0c70bb71057d4a3406556a28cfbeae08c4a04f2533d0e` |
| tts | tts-smoke-04 | 9 | cb28d461f9814fb2319952d57cc1019fe6ad9a1b65321c667691c39387880a4e | `94c212f53a080b12fd5ac213841eac8d01731c6a53a7605e6a6e328e23ce4f63` |
| tts | tts-smoke-05 | 10 | de58dde5982f4880069fe246f111f88c13439cd7820235377345fcfcd7eac6d0 | `ecb94b2a4cc42ab207fb558e7147f4e15aa8546c0a18d5b505ad7b2d0432a92f` |
| tts | tts-smoke-06 | 14 | 970e3092763b6055b4e31fd58c3dc4880f6053da1d3fb5eca16374419517a723 | `e1640f54d7918cea0cf3ae0d685101be78096e07978533e5e058cdfad2fd7476` |
| tts | tts-smoke-07 | 10 | 36ecaa833075d36b7382d79b1e10b2e2e3e92f761b443f9fb79c51bc7ded9b39 | `61c85077500ba4e5217afcae36665f7ff40ed26c0a6bfe9f71b5c4b96e0dd7f6` |
| tts | tts-smoke-08 | 12 | 86ef79838b484c35c0ae08df921acae131a03cb554d88ec1e524f86838d2170d | `5d2877e70410f6bb4d5689a0ac40b54c042cf46eb797164bc9ee5d6ee12d6485` |
| tts | tts-smoke-09 | 10 | a00dec41576b4f0fd1291d42ebbcd1c65945a112a2e6fb04df34e92a4d3978d4 | `62c6126be987b96c13547ed81eeda6aff464fbe4bf2cb5cbf6b0a2db9cdda230` |
| tts | tts-smoke-10 | 14 | a91a12354baa65c26dadf08f967e597bdd324308938da754e82bffc5545968bb | `5765eb9f57c9e6684f124b4b7bbbc5e2b190b1123782b39cfa9ddcd15c29bf74` |

## Parakeet offline transcripts (60 clips)

| category | clip_id | text_sha256 | row |
| --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | d1c76ea36cf22ea32bc429a0bac8a5f2f1c40a7ff230d4b8a6696f6eb333d800 | `53313a666878d056586b49408134eeab2300cde3b59304be24ec6f14c7faa3b1` |
| test-clean | ls-test-clean-121-127105-0012 | 68d729e752d5423d7c2e76de8bf75b8d55fc3ce07d1174ed72ab6797f500db34 | `b503b126ecfa1e3bc36887f3551387ad41f23888d269c3e8b8a586d3b29fc728` |
| test-clean | ls-test-clean-1221-135767-0014 | dc08b223b0786c033d7ca013a2e76b146b17f4b719d6298dc727a4b7cbe98bde | `064679fcb0da106380d1079127dc863be7bc8f73393e1fc99473cdf6a9235408` |
| test-clean | ls-test-clean-1580-141083-0035 | 4bed4b9991e1c5613866117915433e03fdcc49266ccbc1641fae5ee56b86888e | `53073f7363b5f0acb6ed9e957ad0360c343586313afbab0c18a799419cbf1af5` |
| test-clean | ls-test-clean-237-134493-0011 | dcdbc64d0f8497a70fa084a990c7996d41c507d05374877129d3d5c809fdc249 | `edd7a9cbbfcb80e6b93e7ef821ee6fc5e6fcb078b5852a33331529f358d0866b` |
| test-clean | ls-test-clean-2830-3980-0007 | 5b083448d5c9f7822a0b742ba0bb5ea4a413e01b26a14b94380c38093fe784f4 | `fdc6a866ff973449b3e0be680a2307880c20d64107cf9d27e559931ede4fc800` |
| test-clean | ls-test-clean-3570-5695-0009 | 372c74bb4c007dd1b65386597db8384f9e0bb327515ccf7a908e23c8ded75be7 | `c41bf0b648c448ec577cdbf771345af72288ad9e60d0ddc19d9fc77f1d700656` |
| test-clean | ls-test-clean-4077-13751-0014 | 13045dff5dfaf9d56823a23bc6720141122b78e72f2782b5f2604a112efc4130 | `05971ac7abaa1f458916b54b850a1e36f810c84eae15149cdb1098f41f379811` |
| test-clean | ls-test-clean-4446-2271-0024 | a3eac60f7d42cad95c1472d1f12344f2135ab69be59f81f6e86669ffeeac2a51 | `c2f7c46e10ff92d5e4aa1048c603f1e676c3aef80bd144266a2328efa66646fe` |
| test-clean | ls-test-clean-4507-16021-0058 | 331475d475b712286466e562775cc66d53d7b6ebf2e54bb87d48f63d3f77220f | `95e6a427f4a4ca2f241c858fa180897d9be871c47f5dc424804f23b8cacd9aaf` |
| test-clean | ls-test-clean-4970-29095-0002 | f1a80aad29bf8fb66345f5dfec099e7f72640e7072a54afad4a8ca8453b89b74 | `c882e9e0d4ce4cbd2c02969189efdb12b1e096ae9aeffc11f72f3abdd3d0d004` |
| test-clean | ls-test-clean-4992-41797-0015 | 640fadabcf094ad69a72fe746cb4ee960210046fe28351c320a96dcd92917ce9 | `c508ceff9d08c45fe0ed4f1f18b1257c05bb207c5e9e57468244f9575ac11092` |
| test-clean | ls-test-clean-61-70970-0011 | c0e031da2c37d19f7ba120920572f09dda9c9ae8f872280d6fca7578ab11d5ae | `e09cee9e0e9ea935ff8ce18d4b4447e6e2584b869fa94391cf00f81d67b9c875` |
| test-clean | ls-test-clean-6829-68771-0030 | ce74d1a5d44c4a00f51d7280898b279798cd5e862ce0257b09563b90f1e27dac | `1546528f06c35779c7fcd0e887f2759aeb71242b4854151e38b177009d271c32` |
| test-clean | ls-test-clean-7127-75946-0009 | fafe3abe137dbb8a6886ecc87e8115320047aaa3881525f9789f5862a36ada71 | `e92bd77febc912c78a34a569da7d275961cf476bc39c4ffdb6da9bca2445c7d2` |
| test-clean | ls-test-clean-7176-92135-0018 | 99fc12416d4551008716467a5b069c3b6a99896805e35d8edf5ad3787ff0f328 | `22c84c34a01c406e65e21dead9cc31e10c16322e0eb9657f5847554261016b71` |
| test-clean | ls-test-clean-7729-102255-0023 | 8a42eebc3f878181271fc28e02e6aedb54b4622a7d9a048afe3aeaa82257a96b | `a2895e2aee475aa1347545ef7f401433c26703a8207c29a07362f35e9bbc4e40` |
| test-clean | ls-test-clean-8230-279154-0011 | ad50aa1fefbb8d4aa8823b53ca3cc688e9dac6116b0aa7684ee0125642260822 | `617ebf8baf5e8d1053cf6191da7f6904af27f76817226ee6c0c1afe7bf473bb9` |
| test-clean | ls-test-clean-8455-210777-0037 | 634a1ca8203e3cf6bca13a3e03b13ea8583acb09079ce6e8bc7f1b508fe0860d | `4b7c1257f06729f5552c9cf5bb8497481c6bb2e06e3872e49a2c401202d1c95b` |
| test-clean | ls-test-clean-908-157963-0014 | 02fc5351b32f8642488c726d7aadd7406995abf2107e01df8e31864a130b0099 | `52e130427f029893bfc22c9b61a6bc337deba46d1d6d4bb7e10116d522334e45` |
| test-other | ls-test-other-2609-156975-0000 | 2f005507256b3f8c185dea74bb64b160213609db06d4e6ca3347d0cd64778469 | `fe2f266ee04be3716e2ba36fe594eb55d4367b304187656d74e475c305e73968` |
| test-other | ls-test-other-3080-5040-0016 | 4fbbdd9a1874299bbc79e35ff27838d2c2c7a8386cea6baeaa2c5c625f71abcd | `3c07abcd6319895098e7db821f6ede30bc114cf8e68f14adc3d584a37287e8d0` |
| test-other | ls-test-other-3528-168669-0043 | 4b6433fe65cce4f0a529530e63ed925c8af59eb0cb5aa7331e86e2f6ecb6150f | `699c3e39cb33bb2246d078ecb24974c68d4d57baf3e141c8c78c528c01e40cfd` |
| test-other | ls-test-other-3538-142836-0006 | ed46740750361a83547fe4bfc97387c17ae558f94ad4f2dfc33870956e012525 | `0fee430de71322a3c96199ecc5a64bf63fa3a94ef6cebf65db55f1b07173c280` |
| test-other | ls-test-other-4198-12259-0026 | a680d5121ac569762cc6f9b7c6ade161c8b5f390669fcaeda679a683fbacdfcc | `abd8cd93b9185ae088bc62820f5e0f4bf186bd8439bc6530eb3c669175b8c492` |
| test-other | ls-test-other-6128-63244-0013 | f436b925895c6412d41e8bdc0527daa8cc998174371fd8dc7939253441fbadfb | `79a9853531af656024a1769e93c030002a4e144e75ce0a3142487c411050e1cb` |
| test-other | ls-test-other-6432-63723-0046 | 1c2c911e95c438d2873d5de65bb68e761405578b42943317733484f79aabea83 | `a92f0b61808b478bcbe6a755dfeed385a56b630e23a8129cefbd90fdbdc029ef` |
| test-other | ls-test-other-7105-2340-0033 | 64eb42f079a1b415a9300e90e17bb22c9e9010faea4590490b7e4b9d7cd032cf | `fe33338f1b1f3e9a17ef7b015ca9b0fb6b2472075835a432bfcb568df56afe88` |
| test-other | ls-test-other-8188-269288-0027 | b744b832b770124a92be5962b2d8fef51fb366fb0566963ea57b862faa402e38 | `8d3c926c38b4769ce1ce1f195c644ce650f92af6b520d19be202daf80e02ebdc` |
| test-other | ls-test-other-8280-266249-0004 | 7a134cce1231a98272ff91daa64c0e10d9718aa3cdc9c60a34d14092affdc7c5 | `029e7e1704fff4cb771aabe2d109f074cf5855c8ca9bfa8912563562220d97a1` |
| noisy | smoke-mix-01 | 7ab58b0b8c29089541ecf4ba5f832f982e8c48e4dcf514f5eb5362140b8dc742 | `450f2bffeb2ed2050330783e8d3a4848f1249c1dcfbb090d0d1d3b84d7ae956f` |
| noisy | smoke-mix-02 | bc0b290ba694d83fa8c2cc716d5e7c0e5825288da0f89c1b668b035f456b5104 | `dc79afd4cf0f06f2ee2aebd833f84653e5f907b43339efc53f50a82ccfe65ac6` |
| noisy | smoke-mix-03 | 7fb4b83d2fc6eb303b309fa0fa554054e3c1991dfcd046545fff0695b29fdbf2 | `99817a39b710f7306321e53a28a12c2b438d50fdfc2990126cafa6f606379293` |
| noisy | smoke-mix-04 | 75fb1fbecf484c9d0b438cdc4788a56784d6983e38074b81cfbf5815883e4cb8 | `9a44e66e8eef2b4235a631854587aca21f248e594d2ea7ce1f9442aaf7fcc69e` |
| noisy | smoke-mix-05 | 08bd9b3a5c20f777c10e9be00bf6696e5b50a51755be897e762e4d4993836f8e | `289b3f63572fa1b8f93a266a56218f02e8d3b17e250c207844fe33892a543e8d` |
| noisy | smoke-mix-06 | 4127a6350bc9e5cad3db3ed83263bc1d27d5b6f244bd3ea1c172501cefba9f38 | `1316642102e201a1d9159588a4aa538541b589ddd60a087cb1e73385f6a994bb` |
| noisy | smoke-mix-07 | f4ff0e0a6071573f0a66f842c4b8dc2976cb39194a20d9fce882846cb7f978db | `7ee0e2458768441e1360ea3764dd3e6a821465898ad3efba4781c90dca81b73e` |
| noisy | smoke-mix-08 | 35e4d1ec1dc56116bc5dff234c8ae600c725f0e8a74ea562e3e038da049b2991 | `128ac67900e17d9e4d7aec6324726710eb84265616f6cce03fc7d748c2cdd462` |
| noisy | smoke-mix-09 | 6805268231cdd4572584fc0b9ef6e0ace0730adbfbe99243dbf214efa3681367 | `69c3777723449842fe856a580070ab808b29c2f97f0eb59ce0ea601ba48cfb5b` |
| noisy | smoke-mix-10 | 242c44309d13873819bd8b915142b8a34a120b781e93d76ba5e205507213adca | `37cd6703f4706996005b6aff22decf9a36a3c54f8f3a92ac057fa94d1c4e08b7` |
| non-speech | smoke-music-01 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `e34703e9a2b7c0f14df5e2654e7f51da5454a6d1ecd0295068fca62e52139885` |
| non-speech | smoke-music-02 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `ac9fe1a276ce2f786be9210ab424fdbe0600a053044b0a01cbca3083957a61cb` |
| non-speech | smoke-music-03 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `080a54d4fe77e512bf37dc28d88c1601a927e2e86c4d9a698625c7e8ce2f8273` |
| non-speech | smoke-music-04 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `66db094f5fd8b61aa0351f6350606726aed22089042980493be904b86fd16678` |
| non-speech | smoke-noise-01 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `a27400a46da9147170c0f121f42ab013f5ddec1cfc69fabe2feb8a1b2ff0f1f5` |
| non-speech | smoke-noise-02 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `1422b0075ff5b191243109229ad0dd16c7bfbfd161c1b008b7c9604f7f78251f` |
| non-speech | smoke-noise-03 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `462a7d01601cb33b750fc0ac2f1524f8b9bb62a4654062b85a54b3bc2688e62e` |
| non-speech | smoke-noise-04 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `52d476c61928498dcb799b50c032b49f9455643880a5d1977f483d05419ef1ff` |
| non-speech | smoke-silence-01 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `8b9ef03a7c59b184e7fbe3d1deadd4525fca44d391ccb3575a729d7160a53e71` |
| non-speech | smoke-silence-02 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `5daa9d0202314e5bafedc0e5190f098cbf34e7ce8606005896417a40e68ca62e` |
| tts | tts-smoke-01 | 84d89877f0d4041efb6bf91a16f0248f2fd573e6af05c19f96bedb9f882f7882 | `556eca89a8618c0bca3b2e06b89162852e068b011e61584e908fdd5a4905d7cd` |
| tts | tts-smoke-02 | b9693ec1334f9e24e39a7d65a490ae72ccf0eb17fc9e99ee4b337773ba46e693 | `20fee5a4e40f911226a4fae421d893743e30572b2d1581f4472c0fa499938724` |
| tts | tts-smoke-03 | 7619ee8cea49187f309616e30ecf54be072259b43760f1f550a644945d5572f2 | `f4cc11ba57144b829b58ea6f38218b9bc2e363fdde8f0421d42df8f47079f519` |
| tts | tts-smoke-04 | aae92c693767a1dedccbe85fc0d81b969f02c484c19c21e8dfeaeeb47fd3c753 | `57b0a8b9870b4072a8d7835459f765799e9720aa189e8661dfad4cc861637af0` |
| tts | tts-smoke-05 | e60ca3d925d99b5ea4e705d6ecbaa3d17afb7fd5ac4da0aaffec5dc9786bad0e | `8585bb964bec4ef8526a8d5780ce6f105afc189a9ff3ca5d15817e7181871f75` |
| tts | tts-smoke-06 | 7370a823e8962099005fa8cd7707b8baceca15864044326b2210e8f0f6977a72 | `59e42a629cce40b68b47b542e7a6f3831742be190cce17d0385d0a3a460ff5a9` |
| tts | tts-smoke-07 | ae616480a1f36b57b54a83055dc12fa6f5e59dc2c3feee519c3aecf11fe0c242 | `46952d0d0cb788bb9091e0a13cd09e53a3c818c628b4d5e0be3bd06723e40762` |
| tts | tts-smoke-08 | bc2e8b38fafe0c4d9d6b76a148b62bf914fae4802906e756a2663a2a5b5542eb | `1d339aca0a590aa1ca01820de882a6fb835872aafa9df3f31c649e1789b4c262` |
| tts | tts-smoke-09 | 8519f82dd9c9c82320901d94f8d244ec4f028f3cbaa5ba4e104cc6972a16d766 | `f6b5382fd8f196d9a032a700ac80e3973006fed4d0d9c763504f484981a231de` |
| tts | tts-smoke-10 | 8c4cdc7c36083989fc0c1e90010055ee2a14892cd2c6d05a3a10824ec6660d44 | `0eb58b73b237e5acf91ee2641e2dbfcff83efd3aff2e90aa4392317169a1264a` |

## Real-speed Vosk (20 ms frames, never faster than real time)

First-partial latency: first partial event minus the delivery of the frame holding the first recognised word's start. Finalisation latency: last final event minus the audio-end mark. Both in milliseconds (owner decision, question 7).

| clip_id | audio_s | first_partial_latency_ms | finalisation_latency_ms | max_frame_lag_ms | row |
| --- | --- | --- | --- | --- | --- |
| ls-test-clean-3570-5695-0009 | 5.0250 | 216.9053 | 30.8932 | 296.4956 | `777d0bb3c238a983bfe813a96af5cd0bb29350d97446019a0beaf418aef237a6` |
| ls-test-clean-6829-68771-0030 | 6.2250 | 587.4114 | 39.2236 | 134.8856 | `5148fc56e74aaec3ec40a32c308d6ac7786390c768508e499d9804eb12041e06` |
| ls-test-other-6128-63244-0013 | 4.1450 | 727.6461 | 40.7356 | 261.0179 | `630f6719f4642c8ded5bba175d7a83322177f91eebf457e49a96f549bcd1297a` |
| smoke-mix-01 | 5.2250 | 436.1502 | 15.7976 | 204.1552 | `dcdd481d14b9f1bf39b2a17eabf167ab5aed05a7d1e65b2defc7920a95f6758b` |
| tts-smoke-04 | 4.9750 | 816.7170 | 16.8415 | 301.4447 | `0f20976980cb0a027b68307967b0e6f7b81d6ba70cdc099d87c6a59968bc8513` |

- First-partial latency: median 587.4114, maximum 816.7170 ms.
- Finalisation latency: median 30.8932, maximum 40.7356 ms.
- Real-speed transcript equal to the batch transcript: 5 of 5 clips.

## Harness VAD (webrtc_vad_mode2, 20 ms frames)

| category | clip_id | speech_frames | speech_s | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 115 | 2.3000 | `fd9577c399901496747a6586dd67c36ac2bd210744350ba7815e89f8c2f5e083` |
| test-clean | ls-test-clean-121-127105-0012 | 227 | 4.5400 | `ed5dd1834a6b62cac81cbcfea6eb123a9e2436a0f8af90ca8bcfa2654f27d350` |
| test-clean | ls-test-clean-1221-135767-0014 | 315 | 6.3000 | `c585938e71bbc212d35973ad21bd5fe184ca7c618a19f3d440447e9f844a5503` |
| test-clean | ls-test-clean-1580-141083-0035 | 212 | 4.2400 | `35c9de71e0b8d5e0fbacc5983469d191b240801e942b561890ec03648f0745b1` |
| test-clean | ls-test-clean-237-134493-0011 | 238 | 4.7600 | `f3afd1b56de47587612b9b29d262e5ed7f8a41d3c4062eaa721d66e0878701c3` |
| test-clean | ls-test-clean-2830-3980-0007 | 430 | 8.6000 | `766ea6883ecd596f4a57abb2b0ab899e66d2594871b14236f6e82a847f896fde` |
| test-clean | ls-test-clean-3570-5695-0009 | 221 | 4.4200 | `a7b1216d31f01889de407a86eaf0cae0d0dc758c1ff1070c9f54037fbebfb5af` |
| test-clean | ls-test-clean-4077-13751-0014 | 595 | 11.9000 | `1955d95503762a5150743d04de6c2db5114d0d33ebb79dab1384ba41c1a5b913` |
| test-clean | ls-test-clean-4446-2271-0024 | 133 | 2.6600 | `fdc7f5a65e5ea785fa1d18743d6bb05709bcdaf8c97822a33835e7303c96836e` |
| test-clean | ls-test-clean-4507-16021-0058 | 122 | 2.4400 | `6d5621fa7db93416e35bdfca1be322a1153a0f3bea846092f55dc4d781b32964` |
| test-clean | ls-test-clean-4970-29095-0002 | 217 | 4.3400 | `33f28c1d357d0bd81dfb1533fc45868d594a07f2154a788c419b4de77576ae3d` |
| test-clean | ls-test-clean-4992-41797-0015 | 380 | 7.6000 | `cdccbd7e260e226dd34fd67da97e1c33c7e971a61e04792fe8fe1e8d46cd05fa` |
| test-clean | ls-test-clean-61-70970-0011 | 273 | 5.4600 | `88766bcc1e85674ca4c6a8dc65351d4480e9a40f58d76ec76909f35f8540fb4d` |
| test-clean | ls-test-clean-6829-68771-0030 | 295 | 5.9000 | `fddca7353017bb14bdc586708f9a0227ca22019c37b573b9812c2fcb10fa4fc9` |
| test-clean | ls-test-clean-7127-75946-0009 | 198 | 3.9600 | `84c1a0d90998788b749de1100162d435e0905c9c62f6badc0e983d7bf7655c8b` |
| test-clean | ls-test-clean-7176-92135-0018 | 419 | 8.3800 | `8b5be1c7f7c123a1fbbdff015dd0b3ca7129fd6a2fa7f3b2421c1c5b84fc3548` |
| test-clean | ls-test-clean-7729-102255-0023 | 260 | 5.2000 | `d2ffdc2696975cb2a73661751c53780ead9e28e8c3625feb34f23f63fd7d503c` |
| test-clean | ls-test-clean-8230-279154-0011 | 282 | 5.6400 | `8ae8c8d11a44a8abb9ae37fec088b7697c992ec856e1c5b0282ea5709cbaf39d` |
| test-clean | ls-test-clean-8455-210777-0037 | 170 | 3.4000 | `3d768e278e6f3fb2450c35f11f1241abe0b650c4b352596fbf6fb1ff7478e6e0` |
| test-clean | ls-test-clean-908-157963-0014 | 199 | 3.9800 | `a3caa8d3bbb64bc9c4a992862c574fd8dc1c41f2d3123e49953e87cfaaf33b9b` |
| test-other | ls-test-other-2609-156975-0000 | 176 | 3.5200 | `c638426369d1ab95c259db83ccb1ba9846e017ec7bb27e363b3220f15b1a41af` |
| test-other | ls-test-other-3080-5040-0016 | 218 | 4.3600 | `1811948327b140fac3bebbae43149f21bebc49e9a0976b0f411d2c3b1813d6ec` |
| test-other | ls-test-other-3528-168669-0043 | 166 | 3.3200 | `3ed82f5cd586c2c8a99edddfb30f12e57448f64fd4b7219835fdd2ae181ef19a` |
| test-other | ls-test-other-3538-142836-0006 | 235 | 4.7000 | `a760ee6961092fc175e2bb2f86426fb3645e7f8991f7de8e988093fa5e805404` |
| test-other | ls-test-other-4198-12259-0026 | 214 | 4.2800 | `aa70d24447ea73277c770ead37f4836fa37e5bdaa1e4db3be9dd2c337bb0a3cb` |
| test-other | ls-test-other-6128-63244-0013 | 180 | 3.6000 | `ef740018fa79ca59b568fc06e261e53c9e8681f377af38ac9be69204657dfc8b` |
| test-other | ls-test-other-6432-63723-0046 | 272 | 5.4400 | `6d28c503a4178c45f4f4389922b6960d77417909c62bd4f5f99e59a3a6f88422` |
| test-other | ls-test-other-7105-2340-0033 | 471 | 9.4200 | `f950265e6a316c756cd9e333cc9c7a2a887a0f12a27e4dca564c52e4c976bdb6` |
| test-other | ls-test-other-8188-269288-0027 | 160 | 3.2000 | `0bc80b5f6a693f00d0ade2a0de06771a023c3f98ceac6b09bdd139092f81e11f` |
| test-other | ls-test-other-8280-266249-0004 | 240 | 4.8000 | `c3a816fd5ce702cebe479494415e956400e090c5ade7cde957222f7187039c4b` |
| noisy | smoke-mix-01 | 260 | 5.2000 | `0df1e2098120755c2047ff19f4693ba896f573fc5468e6247f4b53955ea5467d` |
| noisy | smoke-mix-02 | 463 | 9.2600 | `f3bd40a1f7bf2693290a5c666367d2291fe6b62fe953be38ff30158a6ba58cf9` |
| noisy | smoke-mix-03 | 370 | 7.4000 | `47f97eed355a98bc89ea90a77dc8f9709da7ed3be8713e4561a59b7f018d7184` |
| noisy | smoke-mix-04 | 253 | 5.0600 | `d73035b51baa71f419f45f94e4ba1b20e7d0fd0ef091d189f82120ca18ebfa87` |
| noisy | smoke-mix-05 | 302 | 6.0400 | `c183128bcfd772f323ab88c0908cc3c830a99a3522823c9ac4e912bd883a0bc4` |
| noisy | smoke-mix-06 | 156 | 3.1200 | `2a60d83ec727e24622623a95e5a0533e679ec999d94f60b4bd5f0ceda297a341` |
| noisy | smoke-mix-07 | 446 | 8.9200 | `d91356dac976483527a2b8c739e3a9be773f96114d9cfd6e7fa78194017f8fe9` |
| noisy | smoke-mix-08 | 341 | 6.8200 | `c754402a637d42f0e767cb8cb8d2f71edcc7ba06208c620104e9dc8d9610bba0` |
| noisy | smoke-mix-09 | 379 | 7.5800 | `e2239733b2beac722cf7893e1b4271fffce1e048ba666c0c520912669e9887e4` |
| noisy | smoke-mix-10 | 330 | 6.6000 | `7c290f3ee6dd6b71f1d0b77c7cd78012663eb05a29325541a4ec4d3a38bc8c30` |
| non-speech | smoke-music-01 | 490 | 9.8000 | `e593342af44f5c6fe38acfdee27fc577852481390e0b038c57d07a28a9564d4f` |
| non-speech | smoke-music-02 | 500 | 10.0000 | `97dc7e82645cb7d2090d2591feb3fd0f6862cc4de767a5df08099bfc3e62af39` |
| non-speech | smoke-music-03 | 4 | 0.0800 | `bbc2205f9251c79d1256ff709154d763cf22b5dd207402c752c0447dcac5fdda` |
| non-speech | smoke-music-04 | 500 | 10.0000 | `b6fb5b0fed3de62ad2efee2b0ca2bcf832fe3fa753aa5ce3e1e6d16c6386df26` |
| non-speech | smoke-noise-01 | 117 | 2.3400 | `6bb664382c740005c13adbafcc4107b284922c0d9e5692cb09ad8fb42fef97a9` |
| non-speech | smoke-noise-02 | 500 | 10.0000 | `bdce46408bcea2a221ddea0294d65df7963367a89fc5ce13a5c6fe84e2ceace6` |
| non-speech | smoke-noise-03 | 260 | 5.2000 | `4c5b3b22f13665e552ed6f6ee17273b03cb64d4d0a22d487fc86275952178249` |
| non-speech | smoke-noise-04 | 8 | 0.1600 | `c3ef801af78f87d595607c447e48cb9d5adcb04e2fbf01084382408fe0026f73` |
| non-speech | smoke-silence-01 | 0 | 0 | `f7da8ae4334144922445a849a6d81477c41a0d7454029669da75000c1ad3d988` |
| non-speech | smoke-silence-02 | 0 | 0 | `5339cbc5238c90069a3664ee85df4874d223de98dc778e67a9fc51cc2a75cd7b` |
| tts | tts-smoke-01 | 134 | 2.6800 | `30eb67b31e25faf3cf1848aa11919cd5fef6fe879703d349c2339dced1fb1535` |
| tts | tts-smoke-02 | 167 | 3.3400 | `e932de949f02bb7a538a09fc2d83b1b55d28539e68f9ce63035ed6602721f21c` |
| tts | tts-smoke-03 | 141 | 2.8200 | `768c1e18da626b3b6d7fff824aa1edd41a19b4befdf8e2d65a22854a8fe82f44` |
| tts | tts-smoke-04 | 168 | 3.3600 | `e42d8c41713f9241345b57f3ad1a3ba77e082be356cd649b37b81603fd92f1a4` |
| tts | tts-smoke-05 | 143 | 2.8600 | `bbad4af694158464d73f7fd7cb1e5a822fc7c779fffff558c2a5fd0076ef7ac9` |
| tts | tts-smoke-06 | 156 | 3.1200 | `bcd2a61329e4a6a7d43c1d81b9275080765eaa89e7de2f96ed63ccdccfc82af8` |
| tts | tts-smoke-07 | 145 | 2.9000 | `508f7b6aa323b16150928cf1823e34ca37337a75b20b77775a8a8a6338b20487` |
| tts | tts-smoke-08 | 185 | 3.7000 | `86ec8d2ff4e85372dca7efd224118f19ba125c60c2ed60aa8662d7f58659e37b` |
| tts | tts-smoke-09 | 136 | 2.7200 | `5de1a86693ce85f33f08f79619c055bd0513c4e6c90143d91757b30781aa5a7f` |
| tts | tts-smoke-10 | 145 | 2.9000 | `4831c55ea2cbfe5f1a20e8f7c3af2adf36c6c63c8dde8704a6e06dd1f6961aa4` |

## Parakeet GPU compute delay (one untimed warm-up first)

| clip_id | audio_s | processing_ms | rtf | gpu | row |
| --- | --- | --- | --- | --- | --- |
| ls-test-clean-3570-5695-0009 | 5.0250 | 129.5899 | 0.0258 | Tesla T4 | `8498b7bf9f6b5c146c2368fcc51cb45236b8a6aa101c163ec2a4c2155cbc4489` |
| ls-test-clean-6829-68771-0030 | 6.2250 | 162.3672 | 0.0261 | Tesla T4 | `6273a0169c75332969d5de916be56d76029e4f9b82fa586744b4314678812f01` |
| ls-test-other-6128-63244-0013 | 4.1450 | 117.6548 | 0.0284 | Tesla T4 | `8c7a0c40a6297e927e0c1c1394d44a2905405b8af43760f5267e1ac287cb2ca3` |
| smoke-mix-01 | 5.2250 | 128.8635 | 0.0247 | Tesla T4 | `7a7318faaa396d37fe7083d902a34b225eddb230225e2e55f8b56db24a2f2e36` |
| tts-smoke-04 | 4.9750 | 106.1279 | 0.0213 | Tesla T4 | `4ac86667553a7b6b9577c2eec59492d48874a8b209218ca1da45e6afeaf0713b` |

- Processing time: median 128.8635, maximum 162.3672 ms per clip on Tesla T4.
<!-- report phase0-smoke-colab-20261002T140101Z end -->

### Oracle VM (Neoverse-N1, aarch64): `data/runs/phase0-smoke/phase0-smoke-oracle-20261002T141937Z.tar`
Made by the owner with `.venv/bin/python -m aqis_lab phase0 smoke --target oracle` at commit `7c27dd5` (OC-0.7-02).

<!-- report phase0-smoke-oracle-20261002T141937Z begin -->
# Phase 0 smoke run: target oracle

Bundle `phase0-smoke-oracle-20261002T141937Z` (bundle format 1.0, docs/runs/PHASE0_SMOKE.md), written 2026-10-02T14:19:37Z on oracle:jitsi.

- Machine: platform oracle, Neoverse-N1, aarch64, Ubuntu 24.04.4 LTS, Python 3.13.7, GPU none.
- Code: git commit `7c27dd53e670d1a207be8738873eeb22bc1ce968` (dirty: false).
- Locks: `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`.
- Elapsed: 116.1602 s (NFR-0.7-01: at most 900 s on the cloud VM).

Every number below is printed from a file of this bundle. A table row names its result row: add the bundle's run and score folders to a results store (`python -m aqis_lab results add --run runs/<task>`, then `--scores scores/<table>`) and run `python -m aqis_lab trace <row>`.

## Runs

| task | run card | mode | clips | results.jsonl sha256 | events |
| --- | --- | --- | --- | --- | --- |
| vosk-batch | `24f9e3e1e4d17f1fcd37f2e2c0ea84bdbab0cc801f4a6b9a2ef46d65466dc537` | batch | 60 | `1420bad59794b6e33ca6bff91e2a94895fab536876635b180a801fb0d0e8071b` | 894 |
| harness-vad | `071e90050bb0573794f65bc2f563a028d9aad3559f779f5a324fbf869d6b42ed` | batch | 60 | `0bef22237eee7e87435111b8a4ce87a816e32ebad2391842a4751905b97823c4` | 462 |
| vosk-realspeed | `c77a2feefa83ffd7b7593601c2e317d9ffeaed49818997fd12b17210723dee7f` | realspeed_cpu | 5 | `b4c056ec8b62af06ef3e7341be5213e4c6139cecbc36fe1c61e48816df25aa48` | 81 |

## Word error rate (WP-0.3 scorer)

Tables `*-synthetic-tts` are synthetic TTS speech: plumbing only, never a model judgement (docs/data/SMOKE_PACK.md).

| table | variant | corpus WER | errors | reference words | corpus CER | summary.json sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | disfluency_aware | 0.1074 | 74 | 689 | 0.0528 | `935c77416e18bdec42b6285b436b126abc2c0495dcd9e244284a44a8c9632f23` |
| vosk-batch-natural | main | 0.1074 | 74 | 689 | 0.0528 | `935c77416e18bdec42b6285b436b126abc2c0495dcd9e244284a44a8c9632f23` |
| vosk-batch-synthetic-tts | disfluency_aware | 0.0476 | 3 | 63 | 0.0115 | `bc09907b715ce2a2acbb9960dc4ddcaaba837a694a7d31f020640fdeab2076d0` |
| vosk-batch-synthetic-tts | main | 0.0476 | 3 | 63 | 0.0115 | `bc09907b715ce2a2acbb9960dc4ddcaaba837a694a7d31f020640fdeab2076d0` |

### WER per clip (variant main)

| table | clip_id | wer | errors | ref_words | row |
| --- | --- | --- | --- | --- | --- |
| vosk-batch-natural | ls-test-clean-1188-133604-0029 | 0.1111 | 1 | 9 | `1561559d339dd4f417d537097b40735343cd405cc9e4ce70e96619aff97b4388` |
| vosk-batch-natural | ls-test-clean-121-127105-0012 | 0.1429 | 3 | 21 | `93ac1b71cf38930d7f9088dc56f0bc0c0dd88ee394d084ae7caff043e13cc425` |
| vosk-batch-natural | ls-test-clean-1221-135767-0014 | 0.0500 | 1 | 20 | `0396f913ff995f95ae267ca25ae754d92707c1a7244e0522ab8e154a51b27f0a` |
| vosk-batch-natural | ls-test-clean-1580-141083-0035 | 0.0769 | 1 | 13 | `1c5745409c16c4fdbcf56cc2e1965911be2e2c0b552efe7c5e7897c8c5d10b8c` |
| vosk-batch-natural | ls-test-clean-237-134493-0011 | 0.0000 | 0 | 19 | `f25e31124704048ddaffe0c5785d6ffda2487380bb1fb09e907fb4f5667d861b` |
| vosk-batch-natural | ls-test-clean-2830-3980-0007 | 0.0909 | 3 | 33 | `28a59081303f8823441c4dc3c53d994c56c35990595a5cd02c31873c0361e4ed` |
| vosk-batch-natural | ls-test-clean-3570-5695-0009 | 0.0714 | 1 | 14 | `5a11ccecd777ab764be3cc17aaef56cc0c73e5d0427a9214c2d583d369d7cb33` |
| vosk-batch-natural | ls-test-clean-4077-13751-0014 | 0.1471 | 5 | 34 | `563ff0d0761a229a588a03ed52180140311f92d25f70c555497d14e4ec9513cf` |
| vosk-batch-natural | ls-test-clean-4446-2271-0024 | 0.0769 | 1 | 13 | `a93971a4e833450cc4cbeb8700bf85a0e5d817f25e8a720914748f835b5dd2aa` |
| vosk-batch-natural | ls-test-clean-4507-16021-0058 | 0.0000 | 0 | 8 | `6673ec5fa813cbb85fa31c93595bc5d13d7f4345c3c3b64b6c94cf13311a4506` |
| vosk-batch-natural | ls-test-clean-4970-29095-0002 | 0.0769 | 1 | 13 | `6b33ff7368d273b7cc4da2416d11f59a6178c2693c93d449160827edf789c8b7` |
| vosk-batch-natural | ls-test-clean-4992-41797-0015 | 0.0333 | 1 | 30 | `0dcb1536da5a1be38e27cbb6bbffc92cdeb35e76cf323b6812169bc4a6ca8cf5` |
| vosk-batch-natural | ls-test-clean-61-70970-0011 | 0.1333 | 2 | 15 | `7db3443fb2ad4e0f4350398a1451ff849ed68374b0af9a7318a9e82c441bd861` |
| vosk-batch-natural | ls-test-clean-6829-68771-0030 | 0.0000 | 0 | 17 | `902449e27a0d018e89a4d24e90ac16ddbfdcd86eb885a74a530a08d4473d9d2f` |
| vosk-batch-natural | ls-test-clean-7127-75946-0009 | 0.0000 | 0 | 12 | `7f57868a0c95b4d6d7ad9f55806a3f3c50f7ce769a711c767a43059545dccd5c` |
| vosk-batch-natural | ls-test-clean-7176-92135-0018 | 0.0370 | 1 | 27 | `62471278084c4484359b3a6985b9029a920025cf83d9ca63c7b5172910727464` |
| vosk-batch-natural | ls-test-clean-7729-102255-0023 | 0.0000 | 0 | 10 | `edbe243d4a592371d4c6a5c4423af5aa562c87dd96c7b5ca3fed599aa1125166` |
| vosk-batch-natural | ls-test-clean-8230-279154-0011 | 0.0000 | 0 | 12 | `394af73af782ef485986e0a5b1c99d95398e6a701907d9a7743e023d714ad99e` |
| vosk-batch-natural | ls-test-clean-8455-210777-0037 | 0.0000 | 0 | 10 | `2773004ebbbfb4e1c9f4a991156112d66144cd1c1c924a68fce6233579ebfb33` |
| vosk-batch-natural | ls-test-clean-908-157963-0014 | 0.2727 | 3 | 11 | `4f42305e17ed17b8b95073dd366c64cc73f7cc544cf158afbe1e042cd03fd4d0` |
| vosk-batch-natural | ls-test-other-2609-156975-0000 | 0.5455 | 6 | 11 | `0a3f1ad1396640486bec983cb524e5b23e74f2bd8c2a16da072c5f5f75a3e776` |
| vosk-batch-natural | ls-test-other-3080-5040-0016 | 0.0526 | 1 | 19 | `aee8e2ea71fdc2f414268d2ad842a8e8670714609941be9d2bfd03a802e814d8` |
| vosk-batch-natural | ls-test-other-3528-168669-0043 | 0.3000 | 3 | 10 | `e2b2011848878b574528e9695892157bf8ab4ca2818bf30e22064d79ec696e16` |
| vosk-batch-natural | ls-test-other-3538-142836-0006 | 0.0000 | 0 | 18 | `2736a0ffe66d23417c31464b04b7f648b78437bd54cc49674cefc206e8d485a8` |
| vosk-batch-natural | ls-test-other-4198-12259-0026 | 0.4615 | 6 | 13 | `abf51c6e2b3033c90e5177407181a0dc5a44172f119de7b8ea21c8b3c34ad625` |
| vosk-batch-natural | ls-test-other-6128-63244-0013 | 0.6364 | 7 | 11 | `cbcbbb1d2a93b4190cb9beb6c0e4f6666513cc87d315788c4e359042482a318e` |
| vosk-batch-natural | ls-test-other-6432-63723-0046 | 0.0000 | 0 | 19 | `2ff071bb3fef72f7c24110a8399f4fc9db88703089eee7945cb314fed4fb9bc3` |
| vosk-batch-natural | ls-test-other-7105-2340-0033 | 0.0000 | 0 | 27 | `99b5c5bad6978753a3cf53a6c7cb8755779324072d5a49b0bd414e1cbdd6f02b` |
| vosk-batch-natural | ls-test-other-8188-269288-0027 | 0.1667 | 2 | 12 | `5f547130e247abb8484dca97885e57049d55e06d9498db8b128ebd4ff816523d` |
| vosk-batch-natural | ls-test-other-8280-266249-0004 | 0.1176 | 2 | 17 | `f2ec6ff98e9a76a534c1a8d76882fa3da440b2a5cb431667cdf5872d90a81623` |
| vosk-batch-natural | smoke-mix-01 | 0.2500 | 3 | 12 | `25939dd6b3f739d1ffa71246a89e63233e3da23408db4bb7f1a4f57a915b7116` |
| vosk-batch-natural | smoke-mix-02 | 0.3333 | 8 | 24 | `59d610fac50be2d28e64b41024611194b0f58b9a070b56d6a3cb261af96d457c` |
| vosk-batch-natural | smoke-mix-03 | 0.0000 | 0 | 19 | `956c90df74e8bbbd34f77ce1417d12de285c3dff4fadc2a2c3b11d4f895650b9` |
| vosk-batch-natural | smoke-mix-04 | 0.0000 | 0 | 14 | `a99622654b4e1bdc799732602f036ec46d90f0339a7965e142810038f4df6447` |
| vosk-batch-natural | smoke-mix-05 | 0.0625 | 1 | 16 | `d7202b09a896260603e56691a5e39f3fc1206ddb00af0a5ac2cff51f20615d8f` |
| vosk-batch-natural | smoke-mix-06 | 0.2000 | 2 | 10 | `19814967c811c7a7da0a59bd15e8c2a617c96c70084dd552e0cc3df212484a18` |
| vosk-batch-natural | smoke-mix-07 | 0.0385 | 1 | 26 | `47eb77e605ff51d489475f30d141e41f1f1ff78a009b4467d797f70892bec947` |
| vosk-batch-natural | smoke-mix-08 | 0.0870 | 2 | 23 | `5519d67460fa86489583a547d9250c09d9f87d006b318a4d40cf2c9c64f627ae` |
| vosk-batch-natural | smoke-mix-09 | 0.1481 | 4 | 27 | `93d72a1b9b532ca58105c0ebc696d8969c1ae63e1add3d228f4ecb0ef470e223` |
| vosk-batch-natural | smoke-mix-10 | 0.1000 | 2 | 20 | `1fc5088d66e29e80b8cbb47d9692d4f6ab24a0cc451d30dc1874c26151aaa048` |
| vosk-batch-synthetic-tts | tts-smoke-01 | 0.0000 | 0 | 1 | `6c8a735ffa0211f36f7caae701b50686cc63dea1e4125bff709e525b66b44f3c` |
| vosk-batch-synthetic-tts | tts-smoke-02 | 0.0000 | 0 | 10 | `79d364a0379f230ed2328f76fef6485cf2f5f53928faaf8e42c5205342b60146` |
| vosk-batch-synthetic-tts | tts-smoke-03 | 0.0000 | 0 | 1 | `e73ae472e83425501e01ee4f657b8970e9b8537fca54984d8b57f7928740a157` |
| vosk-batch-synthetic-tts | tts-smoke-04 | 0.1111 | 1 | 9 | `a7b6f080a17c1310e31064fccdb1cc1d9fc4522dc1b2f5051e7bd6ed806e027d` |
| vosk-batch-synthetic-tts | tts-smoke-05 | 0.0000 | 0 | 1 | `7519cd4375a8fc07e38a3e0da0d0d2f4533e6767d12b1f873d6e2aaa35d5306a` |
| vosk-batch-synthetic-tts | tts-smoke-06 | 0.0000 | 0 | 14 | `028c8a4d6cdb35b91511ffb26afb1f54d3eb52322b98f179a0e3996e541efdc9` |
| vosk-batch-synthetic-tts | tts-smoke-07 | 0.0000 | 0 | 1 | `6354dd1db445929651dff7998d6cf32757385167d9050e5b8a3bceeaa8ae4163` |
| vosk-batch-synthetic-tts | tts-smoke-08 | 0.0000 | 0 | 12 | `93ba7cb086b06de28a8e794bb6ae78be19a287390b770e600100095ac7924b03` |
| vosk-batch-synthetic-tts | tts-smoke-09 | 0.0000 | 0 | 1 | `9797e4de79b1f01197ab44bbc8d7f68dcf60f4409b828dde73eb845d23dbe209` |
| vosk-batch-synthetic-tts | tts-smoke-10 | 0.1538 | 2 | 13 | `12e83111217f62ce7d0cddc236a564f9b80f89a2054326ceb95848f70d0950b3` |

## Vosk batch transcripts (60 clips)

| category | clip_id | words | text_sha256 | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 9 | ed0cdc46462af3fd85466e4075531ee6d435532e1ec02e0590bba2cf4537a288 | `d2df021bd6f79eb30d038911462e2f556732355d73417418de0b2df6b07a46f3` |
| test-clean | ls-test-clean-121-127105-0012 | 18 | 699ad819bfcf8b39789087c3f0b15bf114c1c75b75f6e8ef6f0133c9ca259a29 | `d81ef1c659cddb56c3c8d782c122f7ce21e15bfccf4c896623facabe4e84209f` |
| test-clean | ls-test-clean-1221-135767-0014 | 20 | 77eeb5c74e6a837f48d06d5d1c6e82e20d660dfb2f67893eb1545cfb971a1f5b | `2fc78834859e490315d1c96245d89595b70262813d6873c2543db513ecb54890` |
| test-clean | ls-test-clean-1580-141083-0035 | 13 | 7ed7925898bfabeb4443421409c639975eb0d4b8e1e5791df7871786d038e48e | `54a975fb36287dcaaa30543d8d469ed1ffc5f221f4c10839a33f07c0616001f0` |
| test-clean | ls-test-clean-237-134493-0011 | 18 | cd082978af6d92788438beec92e61403187c2a8d86ce1802c07fb22976191948 | `90e41c7c90bc2f31ee178c29b9a7e10294f5b3ed4dba5b6a6e53ef4abf0ed108` |
| test-clean | ls-test-clean-2830-3980-0007 | 33 | 36af36ac244f4016d204bd3b991eb497bf48a15378c9434b726cb95846437cce | `bbd780863d5b698a1557df797f626e38de9bc4f5c3d8f52ab6b02afc504921bf` |
| test-clean | ls-test-clean-3570-5695-0009 | 15 | cff865c42fc22044f4f00219966c7fa5ff6d5718c9ff254e632e78630becf5a0 | `972c97027ebfb74c8f6b0c25d86779881882ef5e1f9bd1ef877da13735af0bbc` |
| test-clean | ls-test-clean-4077-13751-0014 | 36 | 79d2318af8535b69de087760526f0ec46274301bf72765f91266629cb4b3be9c | `4903c220b968eb486f2202a27f32384f6bed6033edaa899ff881153d1dd48463` |
| test-clean | ls-test-clean-4446-2271-0024 | 11 | 74d466a6d2a3cd1a476bb21b1227a108c9f342eeed7caf78905599b9d01fa9aa | `05142def7ee2080352a7f24fb3eaf7fa87d8eaeae8fc8c63e0aa89afe0d9fa1b` |
| test-clean | ls-test-clean-4507-16021-0058 | 8 | c236cd7f13c7f2639ac253c309b6c21d546aac29f50593b3ba1e7f84fe616c8c | `ee4f92816e10249be92d08b63a1aac451d95f7c02179b80d88e915a92ddd1767` |
| test-clean | ls-test-clean-4970-29095-0002 | 13 | 65fe9e8d47aff0d42b5918fa9aafe611fdddc93b8858e466b9577efe91a7ad12 | `38f093ecf385c3412350bac380a6d1b8bb8889ac8baad40fd270e482244700d8` |
| test-clean | ls-test-clean-4992-41797-0015 | 30 | 1fc5773314919c8012f97d56723388a6befb7c5cc17f463fa830398330a0a4fe | `99046e71acf029ea71b019e59ee9ac2ff1e1a2bc6b27506a726a9db163bc4bee` |
| test-clean | ls-test-clean-61-70970-0011 | 16 | 75e669b68ccb7686f78d6227dbbfc25e9f66e3dc6b817b02a2fab5c1196d94b7 | `5d8b80ff6b40498b7d392648df0975cdbdb6c270503ece29faf932dc2c7d3d60` |
| test-clean | ls-test-clean-6829-68771-0030 | 17 | fbb99918869de67cd11ecd35fccf05d3b9ba7ba0de5d1183db2ceaa10a3ef5f0 | `78fcd2c61947efb7036949dae2ece994cc10fdfe628c71be95c889ec2f09e4ac` |
| test-clean | ls-test-clean-7127-75946-0009 | 12 | b65a6039e3d0f4bdde3eb8f7c193af2bf48ff82369965e3310e3ccab78bc0d08 | `c01e673e9d9259f6ca17fbde23da195c32877ed1409b039378f389aa60cc24e9` |
| test-clean | ls-test-clean-7176-92135-0018 | 27 | f49073c8aa17da02b2b0639369978d3a4c4af8dd74a1cff0f4614953a2ac666e | `54ab36bd0c68f555d8b872ab50ba427af7e15430a969bf464a773d744aaec5dc` |
| test-clean | ls-test-clean-7729-102255-0023 | 10 | 996a32b70e1851af5372a32bbc2b2899bf06bbbd161a9414a1f99118f26a8a24 | `fbb3611ba55f999e4782af90d31e4d731f1d4b869c5f29d929351b3c34cf8224` |
| test-clean | ls-test-clean-8230-279154-0011 | 12 | dc8cb596dd4211fd11b0e55f11f8192c425d43957fbc795f33d5f8be372b78ff | `d88156471cdaadeb19e2b9411b7e7cef1793cc5fbd22907175f817dc639136b5` |
| test-clean | ls-test-clean-8455-210777-0037 | 10 | 4af3329969e0f398ea43d2be7b278776baa1bed28e313c0e2f091da363256aa1 | `f9ebc1b766a6132b170721d4defca89fa8694ae58cc7de5116016bd68ac82cca` |
| test-clean | ls-test-clean-908-157963-0014 | 11 | 35bb92d7da9f5472ab74a0fd16688e9739d86999017882ca2c8358a3a5dfb405 | `85a3169d5e7499d62fff638cc86e282b2de56c4ecbbb3a9aa7ca4cd1e91ad058` |
| test-other | ls-test-other-2609-156975-0000 | 12 | da4a25a42447ac2efb2c4bf427ee83cabbf789e51a20cfbe95fda8461c26d76b | `37b36b31f0653ff05050cd39d9453638e1c8051e4331b6959cc7f2d4db7fe2ef` |
| test-other | ls-test-other-3080-5040-0016 | 18 | d95e960697381f2d028985cd69b7569eb5cfeaaf3adb33e47449f3f0dfe694ad | `4705b0fc85db3df89eb06b542a8c48600252fb79eff755515a19d082d5eb2bb9` |
| test-other | ls-test-other-3528-168669-0043 | 10 | d071a0bdb47a8d924c03c62240613d04335ed61caec31ccde0facef042f92f84 | `e4ef5fb2bdbd216edcee4c34e5a99565543132bb91d2e3f7cfdf1fa9eff42a55` |
| test-other | ls-test-other-3538-142836-0006 | 18 | a3e636a5813ed01e48756a32859c4a32cc5edb17c700a1410d0eaecdd65a4284 | `224c7d9e0a8e982d1341d4eef44bb5be1aced28d7ba44fc32b379894ca370205` |
| test-other | ls-test-other-4198-12259-0026 | 15 | 776f18edf77e50dd07f3de821c05c8bd71a0696fa27e36433e3c0ac5b227dc50 | `9b53e9842e2d764bbe4f708c3854559a6a2bb8fbb115989dd490c1fa1df524ad` |
| test-other | ls-test-other-6128-63244-0013 | 10 | cdc1c8aa9174b98c2eaf0cfe2ddb73d6b2361c347227b38a2ffc0d5ead5c4383 | `f80a3d98741f3c43d5606be0e67e7b60201a6874105460ccc492d4a04dbcca27` |
| test-other | ls-test-other-6432-63723-0046 | 19 | 956415288c8bf740b9b8db8f37e1ce15ab817f88578afe8fb2e744bc0c1cea82 | `f4a62d7c0340003e34e99578982e139a1268f9a38d33eab6392ea0b7b586bac9` |
| test-other | ls-test-other-7105-2340-0033 | 27 | 92114c1d59b5d0e04984e651dd151729faf41453db2b7dd9bad84ddf04b6ddc6 | `457490b453babdd2f620dc31f8fc8ce18df6d1155b05fe95991ce3bc9fbb6294` |
| test-other | ls-test-other-8188-269288-0027 | 12 | 042a2cba559599707040b61d71bb8df67fbad439ae2ef02ca43ae18b2cb575c8 | `076a1649142834d817239700d2698ba87422d6f7f4548627939972337c24c757` |
| test-other | ls-test-other-8280-266249-0004 | 17 | 35ada150736b31211d48d52d8f5d96f4aafde1413bb34eec1e865cf4e0551e58 | `1d06ffa6feae0d561f191e5c03e548f2959b0abee7cf97bbbe2b4fdf5c6ffa96` |
| noisy | smoke-mix-01 | 12 | 87910b29bb221a77c7c49aae0d15a1f4c1a9473281f693bf5024d4b56e62e2ab | `cc576a2380e65016c831dae924e4de5441da4481e0e7e05a113df7a0f934cff2` |
| noisy | smoke-mix-02 | 25 | b888aff1a8cf3bd2a35cc8cedcf51e7015fff0800587946491ae250e2dfb0590 | `cfd0c2ebfb026b5237f0599ae8bfb8c02684c354360433e21c1da0d6e7ebeba8` |
| noisy | smoke-mix-03 | 19 | bcf0d81630c3e6bc5224d712424e3cea1d7b711ed7f35bfc7a7ae97b34b50b37 | `74596054e6f7c7afdf0e15716d65ecc474e4a1fd42c13ec3b4df1791a7171e4f` |
| noisy | smoke-mix-04 | 14 | e758403d33ad61c1caa27def162b7e7c6303b3756016c7a6013ce7a9bc3332e1 | `5192a2595b7b6adef3f7cec08b05b0c953b0112fd8542165e1ff06cc96d5da2f` |
| noisy | smoke-mix-05 | 16 | 070d138be7141aeb954c90b79b133fd709a9471b5d07f0371116e2c7c44f476f | `7107ce9e162873de0e98346157a76dbd04daa4bc5dbc81989e98c036799d5302` |
| noisy | smoke-mix-06 | 10 | c504300185d5fe7dd696fc1fde33810a22f1973177c97c9f4ff00c80099977ff | `2fcf0e6fe787b705ad73d03993f4879f7fbc520afeb8106a60afc50d7f3f6187` |
| noisy | smoke-mix-07 | 26 | 40a2aaa60d1da5489c171a1642ddd15cdc11e92ef3dee6d7c0cff31970c7f034 | `0805f5acaf4ff4c107862cdf935f10b45062ed0157d4f50b5efc33e1822066eb` |
| noisy | smoke-mix-08 | 23 | 150510b8461a309c5c4c998501060512397fd365cc24b69db00c4ac29c957563 | `f6d4f5c192f6ab0bde104c4a8758a3b64755017ceabf1e29eeaceec9fef86ad9` |
| noisy | smoke-mix-09 | 25 | 6a6abb83e505d3353861d315868bc023638ba33dc88d11b2399f732ad49c0c88 | `a6b7c741757faba974b7695ab8d0340b5de448f27168be03d41cb391b2187274` |
| noisy | smoke-mix-10 | 19 | b37dd1a23cdf37e3bbcadc14374e046e3772400577924656ea82b6c28873391c | `7aafc1db19b09317e073cd3d6095b07291e36c7a6359650c3bfd25778efa6a1d` |
| non-speech | smoke-music-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `4e5a1c130dbdf7b7dab972a6775fc233f7e6ff50b7a19aca26391582552778cb` |
| non-speech | smoke-music-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `2c395fa3665a44d995188edbc2c91d8dfe1c2720fc8d4a29b2e3fb5f27232998` |
| non-speech | smoke-music-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `ba6ffd892371aa2f1185120c28a0508207373eda80edd7fe0209eb79871b3a9a` |
| non-speech | smoke-music-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `4adbf9951cdbd8ae8978e6fb49f1a2366c6616b6f3aa788e87fd0878aea4a3e4` |
| non-speech | smoke-noise-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `af33728eb3cde7ea7038a2854dfd8a757d0b702a5f907219885e1ca9c47db613` |
| non-speech | smoke-noise-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `45ff2951954e38c36a5086cff0f78081f17ae3b783ab7fac7e32e44af29d89e5` |
| non-speech | smoke-noise-03 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `6245c968634b6d5bdaa8740130f0513827d535e56711c06c94781497b41a8eca` |
| non-speech | smoke-noise-04 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `4a7fcdaa7d9c74c27945b8a1acde2630a2b3d99af47002fd04706dbea6dfc5c3` |
| non-speech | smoke-silence-01 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `2cc1cc06ceaa928396e1a362b54b79e3d60aecb778f8c738349c8e7fceaddf44` |
| non-speech | smoke-silence-02 | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | `e04968d07f8bf8e43d5126a07a0852a19835fce9d012ef03fb14a5afa17e50b9` |
| tts | tts-smoke-01 | 10 | 30640fce942d691c56bee86a2c000dfa620f2087b3ae22ec8abfd29c65b1eae1 | `aea8e803f1312e324eac1a5dd5bd3558cfc8a924854a1660f49337234ecd8ef5` |
| tts | tts-smoke-02 | 10 | abfd320d882a8ec2ab888bf778f93eb52b29468e59b83822a313cc0e2881b132 | `ab280836d2fbd89e25603cbb1b3aafdc48c71a50453d4b0c5d8b08d68f07f577` |
| tts | tts-smoke-03 | 10 | 25174bb2bfba68f128584857466e3aedcfbff528c3f8db91ffb1e738affc996e | `d892bb8d8130dcf67cc4047b9837260335432dbec1e79bf39692c8e8f6a78639` |
| tts | tts-smoke-04 | 9 | cb28d461f9814fb2319952d57cc1019fe6ad9a1b65321c667691c39387880a4e | `f20a03336177e4a35e14f12c0eeba3c45455520b5e4a46c241433d30f91ae044` |
| tts | tts-smoke-05 | 10 | de58dde5982f4880069fe246f111f88c13439cd7820235377345fcfcd7eac6d0 | `0c25f69a058d480e52c69da0a4b58d293d2c96efc45d937c792ea377055e1079` |
| tts | tts-smoke-06 | 14 | 970e3092763b6055b4e31fd58c3dc4880f6053da1d3fb5eca16374419517a723 | `27de39e730badd9b6e67ac9060a02c843d9e3f58ecf70b0cda465c266e274324` |
| tts | tts-smoke-07 | 10 | 36ecaa833075d36b7382d79b1e10b2e2e3e92f761b443f9fb79c51bc7ded9b39 | `2eef34e87ec83f7bc939efb3f630f8bc7d38d94400e5b7e844d22acc8522b245` |
| tts | tts-smoke-08 | 12 | 86ef79838b484c35c0ae08df921acae131a03cb554d88ec1e524f86838d2170d | `c43790b9adb91fb018386a632d0888a6895a2a3f5ecf2c76c3add168d6b10073` |
| tts | tts-smoke-09 | 10 | a00dec41576b4f0fd1291d42ebbcd1c65945a112a2e6fb04df34e92a4d3978d4 | `6df5d09d8e7471c89b74c966ce28cc6fd4b0fa2a145e9281617b7db5d1b58e73` |
| tts | tts-smoke-10 | 14 | a91a12354baa65c26dadf08f967e597bdd324308938da754e82bffc5545968bb | `37a1d025df869a2e08f7a32bf9e8e40ddf16e6cf40c333829a057ed7e2035421` |

## Real-speed Vosk (20 ms frames, never faster than real time)

First-partial latency: first partial event minus the delivery of the frame holding the first recognised word's start. Finalisation latency: last final event minus the audio-end mark. Both in milliseconds (owner decision, question 7).

| clip_id | audio_s | first_partial_latency_ms | finalisation_latency_ms | max_frame_lag_ms | row |
| --- | --- | --- | --- | --- | --- |
| ls-test-clean-3570-5695-0009 | 5.0250 | 225.0800 | 32.2831 | 288.3487 | `63e3a71797502c1cd385f5604bb29efbcec8744c8a975fff13f966c3a1a50a76` |
| ls-test-clean-6829-68771-0030 | 6.2250 | 593.5512 | 23.2753 | 134.0884 | `c1b45bd2486fbad944f35ee48f5fa43f9e58a8ad945c66cbd6353a9902a32a64` |
| ls-test-other-6128-63244-0013 | 4.1450 | 740.4824 | 31.3153 | 271.3636 | `714fadc0c11061668ca5a68afddca14c1001b9e41cf84b919842a4ecf9a0bfaf` |
| smoke-mix-01 | 5.2250 | 435.7056 | 11.3555 | 189.6243 | `8c05ad82f3a6d67eaf94b134591b82c8fd3cfa103f1f993f6ef227b557ca9c29` |
| tts-smoke-04 | 4.9750 | 726.8046 | 12.9493 | 180.5859 | `b53c9f2226f47017ad80027120d93d47a5f34c8350dbf7f34d3769cc093384a6` |

- First-partial latency: median 593.5512, maximum 740.4824 ms.
- Finalisation latency: median 23.2753, maximum 32.2831 ms.
- Real-speed transcript equal to the batch transcript: 5 of 5 clips.

## Harness VAD (webrtc_vad_mode2, 20 ms frames)

| category | clip_id | speech_frames | speech_s | row |
| --- | --- | --- | --- | --- |
| test-clean | ls-test-clean-1188-133604-0029 | 115 | 2.3000 | `33d10ca6f72a0f1e0b31c2d9f5dc2f9b90efe2c090e456c7f06cd86e37fc2b96` |
| test-clean | ls-test-clean-121-127105-0012 | 227 | 4.5400 | `59e77dc3756162cafa50cc7a7d747fbfb721c1da7bcade58ede77fef589db41d` |
| test-clean | ls-test-clean-1221-135767-0014 | 315 | 6.3000 | `a66514cff008c1a6f0e5b7efb58fbebe28bc4817c9065c91af8213e9e7afacf0` |
| test-clean | ls-test-clean-1580-141083-0035 | 212 | 4.2400 | `549f2058d21e1602c39c13da1bb5395138f02e9ffe57b269885f46c4c0397496` |
| test-clean | ls-test-clean-237-134493-0011 | 238 | 4.7600 | `22f77e1680095ad3ecec444bb34cc0327d103f832f9c3304d10d366b2c784963` |
| test-clean | ls-test-clean-2830-3980-0007 | 430 | 8.6000 | `2b9e422e28d428d0a984cc1228c7676f8d26505f16225a119138965254c01867` |
| test-clean | ls-test-clean-3570-5695-0009 | 221 | 4.4200 | `38d8f26eba8900bc29cf2b90f906b75fc271cf927674bc3269bac34220bc8130` |
| test-clean | ls-test-clean-4077-13751-0014 | 595 | 11.9000 | `dc6959f32a633829da450ada0061d8d92679ec616f51bc4c3f3519af359393c1` |
| test-clean | ls-test-clean-4446-2271-0024 | 133 | 2.6600 | `2e69398c3addd06424ac3249865e691bbbfba0fef4228764042fa5061e7dd8b0` |
| test-clean | ls-test-clean-4507-16021-0058 | 122 | 2.4400 | `df964ccb79947d09cb12f138ded9be4f0cb85a495d4490183cbba173a2602194` |
| test-clean | ls-test-clean-4970-29095-0002 | 217 | 4.3400 | `47c27696cebd13dbff937b4944a51ff7f0085e5dd1127acf4893aab53639bfcb` |
| test-clean | ls-test-clean-4992-41797-0015 | 380 | 7.6000 | `26104b31944a8236a741676cdc78e1fad1c6ee98dacfcbf8d92e8f4bfbd08a84` |
| test-clean | ls-test-clean-61-70970-0011 | 273 | 5.4600 | `7a3027416096bbe3f56f4cb87f2f7a137f6011963a2a8e919ffc4e6a19fe1562` |
| test-clean | ls-test-clean-6829-68771-0030 | 295 | 5.9000 | `c7e7ee9aed1ab1355f8d2c4c5c78ae508fc400faab5c0fef65e5cd5022b862da` |
| test-clean | ls-test-clean-7127-75946-0009 | 198 | 3.9600 | `da2f3b9930c05699a809b9dfbcaae988b17679e953729841128445d25b558cc8` |
| test-clean | ls-test-clean-7176-92135-0018 | 419 | 8.3800 | `8f55898d0af63df65dc5db7ed3b6dc9dd498135f4a4625b450e37e078b79ff4d` |
| test-clean | ls-test-clean-7729-102255-0023 | 260 | 5.2000 | `011dd9b743d54855d953827a4ff5c206c42edb71561eef5fe9a3738aa6c5072d` |
| test-clean | ls-test-clean-8230-279154-0011 | 282 | 5.6400 | `1f4d0c4cf2b577c6212c25ee5b72c4ef08cc476507c76b966317a9df4611a22b` |
| test-clean | ls-test-clean-8455-210777-0037 | 170 | 3.4000 | `31674055fc7765619fb32900866d243855b13d5d50971aea11e4e4d08a689b43` |
| test-clean | ls-test-clean-908-157963-0014 | 199 | 3.9800 | `c2f166d3e89690c3551132f3ecc331b439b349fbdc4cd6f89665a8c455a83848` |
| test-other | ls-test-other-2609-156975-0000 | 176 | 3.5200 | `88ab4826b500ea0ccf9353c386907aebfdeccacaf5f8877d8f6055ba1c3fdae5` |
| test-other | ls-test-other-3080-5040-0016 | 218 | 4.3600 | `f96322dbde55ce7b382abadf2f9ba4183c8047aa1f183203eede50a23b806061` |
| test-other | ls-test-other-3528-168669-0043 | 166 | 3.3200 | `6936e1acca1ceba14fdc31fbe58eee7c954f147da682d563a4df8108136a9d60` |
| test-other | ls-test-other-3538-142836-0006 | 235 | 4.7000 | `cae52be5ad5d301dbec50a465eb8e3914b4dc613eccad0e50eff5688315003c9` |
| test-other | ls-test-other-4198-12259-0026 | 214 | 4.2800 | `f0617683aa83edc351b97f7f521789ca9818e2c5d553e39bae442fc8a0575d8d` |
| test-other | ls-test-other-6128-63244-0013 | 180 | 3.6000 | `d906fd544f80846e08b5510467676e9949b178c74c9ee3ac76720bdb2c77ea8d` |
| test-other | ls-test-other-6432-63723-0046 | 272 | 5.4400 | `1d0aac8eed53dee79439af3af516171624be8ed3f30b4169feeca0dc3e8b3f5b` |
| test-other | ls-test-other-7105-2340-0033 | 471 | 9.4200 | `693291d8215dfc71cdb6be883ca7f51a5dc53d0f1f175d95c89c447671810fb3` |
| test-other | ls-test-other-8188-269288-0027 | 160 | 3.2000 | `72968f2f948836f1b8dce5089ad79fb370ec38724480617a2e6886b2d96c511e` |
| test-other | ls-test-other-8280-266249-0004 | 240 | 4.8000 | `779bf85b654b3c9f4fa7d0ee7243cd3b5ecee15e8b7544efe42da3c20792cbb8` |
| noisy | smoke-mix-01 | 260 | 5.2000 | `b94354d71607526f93a77adfc720accf9e5aea8f90ffbc992b63c6a5887ad16e` |
| noisy | smoke-mix-02 | 463 | 9.2600 | `8198681fe50a3dad32892ab989b95f64abb5fb67629b73045696ddfc2009b36b` |
| noisy | smoke-mix-03 | 370 | 7.4000 | `b8c38855ff611bc814acc98d7dc751ed997262ff930888d6ed18c01b452b331c` |
| noisy | smoke-mix-04 | 253 | 5.0600 | `3de2556eddf48699fdc0dc3b8d0a34c26192c8e5798698bf8cdf28947f61a512` |
| noisy | smoke-mix-05 | 302 | 6.0400 | `4a4f0d3080074482d6ca9591770b0b483e6d6536d95b19b0a528541b9a70f8e5` |
| noisy | smoke-mix-06 | 156 | 3.1200 | `fca8c5970b568bf47c3cfc2760eec4c42ad02757def7aa3b5adf5b4b55800489` |
| noisy | smoke-mix-07 | 446 | 8.9200 | `f6a32c63e5a6b6c47781b8ac67469292da1e49e1f53b568c4bb9b699145ff8ee` |
| noisy | smoke-mix-08 | 341 | 6.8200 | `8793eb5d4d25237f664e4f8c6d6b1966e5689e43bec32953fe1407a5e4605045` |
| noisy | smoke-mix-09 | 379 | 7.5800 | `3f8034f8b1f5175db61d1954cc1836de2fa93ed7c921f3073fc9bb3d392c8f10` |
| noisy | smoke-mix-10 | 330 | 6.6000 | `e8b9bbadc607c8a70ef170d24b5b37b37d41fc826dfc26d4a0d0a288d1d9caa5` |
| non-speech | smoke-music-01 | 490 | 9.8000 | `585c3bc2460831f89692cfc030fb383f7f2d386347b8e9c2b3826d9c3bf1219e` |
| non-speech | smoke-music-02 | 500 | 10.0000 | `ad08306bdc1eac034be2c4d415965d5cf2e1061f1b9b21afb3840ba64b904bac` |
| non-speech | smoke-music-03 | 4 | 0.0800 | `a8847c23f16325afff5ebfb63eb7b0a29e54d1700f727a72a5008a7626275b25` |
| non-speech | smoke-music-04 | 500 | 10.0000 | `62b10fe5bae5300a15861d1f348e82341c169f0b790192323c6b675f9e1d93da` |
| non-speech | smoke-noise-01 | 117 | 2.3400 | `ab0255ae78b28253c94d8e2fa6d187aa9f92d73523da172c910c738df7bd729e` |
| non-speech | smoke-noise-02 | 500 | 10.0000 | `8dae8679947ac245cb369205a93983c95ec258743193ad13fc97b678d532f005` |
| non-speech | smoke-noise-03 | 260 | 5.2000 | `b8e11023982e0289ef5ff96151d15c4e43c4446304f9176e2949f9065b310fb5` |
| non-speech | smoke-noise-04 | 8 | 0.1600 | `f6d7bf7237a7c154e87c80b7feca49342e68fa28e2c9d03dead82dcfe12684a6` |
| non-speech | smoke-silence-01 | 0 | 0 | `751b0680aad8551e1054ebc5b5a3cd84925294baeaa71c601c3a919850823249` |
| non-speech | smoke-silence-02 | 0 | 0 | `ef00713033baff8430ed96531c1fd937b8ab75ed9b09ebc16842cb16e07bed39` |
| tts | tts-smoke-01 | 134 | 2.6800 | `6672dcd791f72ccdee6d3370606bf70164ae1990383d80ed80fd3c428a79341b` |
| tts | tts-smoke-02 | 167 | 3.3400 | `f0bfee53733c8f97f0796282d3a7462243e03771e803ca7444f120ff54cf6b9c` |
| tts | tts-smoke-03 | 141 | 2.8200 | `e501135bb3a9986452c8006e49cd19d56689d58a8bcc36c2bdb06d66c9934961` |
| tts | tts-smoke-04 | 168 | 3.3600 | `876421b5365fa56c1cdec736704e7b6ebf9825af475ccbfc98cd196a68e5cc17` |
| tts | tts-smoke-05 | 143 | 2.8600 | `45bbe3025945f3bcfb02a569bccc9e6c121d9fa7efad068584e3d02060cc31bc` |
| tts | tts-smoke-06 | 156 | 3.1200 | `1e23aef251a4cc11c4d0ccc59e9149a6df1a855a876122335dba71e67a0fdeb3` |
| tts | tts-smoke-07 | 145 | 2.9000 | `c343a2d38a27b42913f78448154712fffc00870ee8103327e9a5f73a3d9cd15f` |
| tts | tts-smoke-08 | 185 | 3.7000 | `7a69b3039a9a43a29c63108bc1774992c42a2f3cdb7046c935d9d0ad75c36841` |
| tts | tts-smoke-09 | 136 | 2.7200 | `d8fa54a9eb0363a597089251cae13962f62cdbf31ad2b55e553b33ab1da94706` |
| tts | tts-smoke-10 | 145 | 2.9000 | `24b114bd77d1f905259839dab3b6ef4bb9cc4403a5e4a8ece72e411aa11493c6` |

Parakeet: not run on target oracle (a CPU target; FR-0.7-07 runs Parakeet on the GPU target only).
<!-- report phase0-smoke-oracle-20261002T141937Z end -->
