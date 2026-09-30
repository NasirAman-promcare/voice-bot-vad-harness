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
