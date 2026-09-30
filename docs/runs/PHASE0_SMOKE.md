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
