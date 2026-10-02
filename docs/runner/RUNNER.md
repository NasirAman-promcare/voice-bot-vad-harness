# Runner (`python -m aqis_lab run`)

The runner runs a task over every clip of a pack in shards. It survives a disconnect: a restart skips the shards that are provably finished and computes only the rest. Built by WP-0.5 (FR-0.5-04 to FR-0.5-06). Code: `aqis_lab/runner/` and `aqis_lab/commands/run.py`.

## Usage
```bash
.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --out <run folder> --seed 0
.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --out <run folder> --seed 0 --shard-clips 10 --max-shards 2
```

| Option | Meaning |
| --- | --- |
| `--task` | The work done for each clip: `clip-stats` (WP-0.5) or a model adapter's task (WP-0.7, below) |
| `--pack DIR` | Pack folder, in the repository (`data/packs/smoke/v1`) or on Drive (`…/AQIS_LAB/packs/…`) |
| `--out DIR` | Run folder. Running the same command with the same folder resumes the run |
| `--seed N` | Seed recorded in the run card (required; `clip-stats` has no random step) |
| `--work-dir DIR` | Local folder the pack is copied to and extracted in; default `data/raw/aqis_lab/work/` (git-ignored). A folder on a Drive mount is refused |
| `--shard-minutes M` | Most expected minutes of work per shard; default 30 |
| `--shard-clips N` | Most clips per shard; default no limit |
| `--max-shards N` | Stop cleanly after computing N shards in this session (owner decision, WP-0.5 question 5) |
| `--from-scratch` | Rename an existing run folder to `<out>.superseded-<UTC>` and start again; nothing is deleted |
| `--drive-mount DIR` | On Colab: keeps the unit log's "last seen" time current (FR-0.5-07) |
| `--notes TEXT` | Free text for the run card |

| Exit code | Meaning |
| --- | --- |
| 0 | Complete, or stopped by `--max-shards` (the log says how many shards remain) |
| 1 | A clip failed: an `ERROR` line names it, its shard gets no marker, and the run stops |
| 2 | Usage or input error, including a run folder that holds another run. The message starts with `ERROR:` |

## Copy then compute (FR-0.5-04)
1. Read the pack's `manifest.json` strictly and validate it (pack-manifest v1).
2. Copy the manifest, `LICENCES.md`, `build_record.json` and every archive into `<work-dir>/packs/<manifest_id>/.staging-<version>/pack/` on local disk.
3. Run `pack verify` (`verify_pack`) on the copy: every archive's size and SHA-256, and every member, rate, channel count and duration. Any problem stops here, and the staging folder is removed.
4. Extract every archive into `clips/`, check each clip's SHA-256 against the manifest, and write the `.staged` marker. The marker records the manifest's canonical SHA-256, the SHA-256 of the manifest file's bytes and every archive's SHA-256.
5. Rename the staging folder to `<work-dir>/packs/<manifest_id>/<version>/`.

Only a folder with a valid `.staged` marker for exactly the same manifest bytes is used; such a pack is not validated or copied again. An interrupted staging never counts and is redone. A pack already staged is not copied again. Clips are read only from the local copy, and each clip's SHA-256 is checked again every time it is read.

## Tasks
| Task | Adapter (docs/adapters/) | Run-card mode | Rows repeat byte for byte on a rerun? | Events |
| --- | --- | --- | --- | --- |
| `clip-stats` 1.0 | none | `batch` | yes | none |
| `vosk-batch` 1.0 | Vosk, 20 ms frames as fast as it goes | `batch` | yes, on the same machine and kernel | yes |
| `vosk-realspeed` 1.0 | Vosk through the real-speed feeder (`aqis_lab/realspeed.py`) | `realspeed_cpu` | no (measured latencies) | yes |
| `harness-vad` 1.0 | the harness WebRTC VAD, mode 2, 20 ms | `batch` | yes | yes |
| `parakeet-offline` 1.0 | Parakeet Unified on a GPU | `batch` | not promised (GPU arithmetic) | yes |
| `parakeet-compute-delay` 1.0 | Parakeet Unified, timed per clip after one untimed warm-up | `gpu_compute_delay` | no (measured times) | yes |

The model tasks (WP-0.7) record the adapter's model block, the main text normaliser for text tasks (null for the VAD) and the lock the environment was installed from (`requirements/aqis_lab/phase0.txt`, or `phase0-gpu.txt` with the GPU extras). Their result rows are listed in `docs/runs/PHASE0_SMOKE.md`. A task that cannot run on this machine (Parakeet without a GPU or NeMo) stops the run with exit 2 before anything is written. Their expected processing seconds per audio second, used only to size shards: `vosk-batch` 0.19 and `harness-vad` 0.000542 (measured on the cloud VM with the script below: 67.9 to 74.6 s and 0.212 s for the 390.9 s smoke pack), `vosk-realspeed` 1.0 (real time by construction), both Parakeet tasks 1.0 (an upper bound; the compute-delay run measures the real figure on the T4).

`clip-stats` 1.0 reads each clip (16 kHz mono 16-bit PCM) and writes integers only, so its rows are byte-identical on every machine:
- `samples`, `sample_rate_hz`, `channels`;
- `peak_abs` (largest absolute sample), `sum_samples`, `sum_squares`.

Its run card model block is family `aqis-lab-task`, name `clip-stats`, version `1.0`, checksum null, settings `{}`.

### Expected work
A shard holds at most `--shard-minutes` of expected work. Expected work is clip duration × the task's expected processing seconds per second of audio. For `clip-stats` that ratio is **0.000169**, measured on the cloud VM (Intel Xeon @ 2.80GHz, Python 3.13.12): the median of 7 passes over the staged smoke pack was 0.0661 s for 390.935 s of audio. With the default 30 minutes, the smoke pack is one shard. The measurement script:
```python
import statistics, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, ".")
from aqis_lab.runner.stage import stage_pack
from aqis_lab.runner.tasks import TASKS
task = TASKS["clip-stats"]
with tempfile.TemporaryDirectory() as tmp:
    staged = stage_pack("data/packs/smoke/v1", Path(tmp) / "work")
    clips = staged.manifest["clips"]
    audio = sum(c["duration_s"] for c in clips)
    times = []
    for _ in range(7):
        t = time.perf_counter_ns()
        for c in clips:
            task.run_clip(c, staged.read_clip(c))
        times.append(time.perf_counter_ns() - t)
    med = statistics.median(times) / 1e9
    print(f"audio {audio:.3f} s; median {med:.4f} s; ratio {med/audio:.6f}")
```

## Run card
Built and validated against run-card v1 before anything runs:

| Field | Value |
| --- | --- |
| `pack` | `manifest_id`, `version`, canonical SHA-256 of the manifest |
| `model` | the task's model block |
| `processing` | three empty lists |
| `mode` | `batch` |
| `machine` | `aqis_lab.platform.machine_block()` |
| `seed` | from `--seed` |
| `normaliser` | null |
| `lock` | `requirements/aqis_lab/phase0.txt` and its SHA-256 |
| `git` | the full commit and dirty flag of this checkout |

## Shard plan
Clips are taken in manifest order. A run may be limited to a subset of the pack's clips (`RunOptions.clips`, used by `phase0 smoke` for its 5-clip runs); a clip that is not in the pack is exit 2. A shard closes before adding a clip would pass the expected-work limit or the clip limit; a clip over the limit gets a shard of its own, and the log says so. `shard_plan.json` holds:
- `plan_version` (`"1.0"`), `run_card_id`;
- `task`: name, version and seconds per audio second;
- `shard_minutes`, `shard_clips`;
- `shards`: each shard's `index`, `clip_ids` and `expected_work_s`;
- `clip_selection` (only for a clip subset): `clip_ids`, the subset in manifest order. The run card does not change: it decides each clip's result, the plan decides which clips are computed;
- `plan_id`: the SHA-256 of the canonical plan without `plan_id`.

## Run folder
| File | Content |
| --- | --- |
| `run_card.json` | The run card, written once |
| `shard_plan.json` | The shard plan, written once |
| `shards/shard-NNNNN.jsonl` | One row per clip, in manifest order (below) |
| `shards/shard-NNNNN.done.json` | Completion marker: `marker_version`, `plan_id`, `shard`, `results_file`, `results_sha256`, `results_bytes`, `rows`, `finished_utc`, `duration_ns` (monotonic clock), `session`, `machine` (the machine that computed the shard) |
| `shards/shard-NNNNN.events.jsonl` | Tasks with events only: the shard's events, numbered on from the finished shards before it; its marker then also holds `events_file`, `events_sha256`, `events_bytes`, `events` and `seq_first`, and the shard counts as finished only when the events file matches too. A failed shard's events (with its `error` event) are written without a marker |
| `run_id.txt`, `events.head.jsonl` | Tasks with events only: the run ID (`run-<UTC>-<first 12 hex of the run card ID>`) and the `run_started` event (`seq` 0), written once when the run folder is created; a resumed run keeps both |
| `events.jsonl` | Tasks with events only: `events.head.jsonl`, every shard's events and a `run_finished` event, validated against event log v1 (docs/contracts/EVENT_LOG.md) before it is written |
| `results.jsonl` | Every shard's results joined in order, written once all are finished |
| `runner.log` | One UTC-stamped line per event: `session N start` (task, pack, run card, plan, machine), `cores:` (the core pinning, below), `shard NNNNN skipped` (and why it counts as finished), `not finished` (and why), `started`, `finished`, `ERROR`, `stopped after`, `run complete` |

**Result rows.** One canonical JSON object per line (sorted keys, no spaces). Fields: `clip_id`, `run_card_id`, `task`, `task_version`, then the task's fields.

**Writes.** Every file is written atomically: `<name>.partial`, fsync, rename, fsync of the folder. The results file is written before its marker. On Drive every write must be inside `MyDrive/AQIS_LAB`.

## Resume rules
- **A shard counts as finished only when** its marker parses, names this plan and this shard, and matches the results file's SHA-256 and size. Anything else is computed again and replaced, and the log gives the reason.
- **An existing run folder is resumed only when:**
  - its `run_card.json` equals the rebuilt card, apart from `created_utc`, `notes` and `machine.cpu_model`. A new Colab runtime may have another CPU model (owner decision, WP-0.5 question 4 (b)): the stored card keeps the first session's machine, and each marker records its own;
  - its `shard_plan.json` equals the plan for the options given.
- **Otherwise the run stops with exit 2** and names the differing fields; use another `--out`, or `--from-scratch`.
- **Session numbers** come from `runner.log`.

## Core reservation on Oracle (WP-0.6 FR-0.6-04)
Before it stages the pack, the runner pins itself for the task's run mode (`batch` for `clip-stats` and the batch tasks, a timing mode for `vosk-realspeed` and `parakeet-compute-delay`) with `aqis_lab.timing.cores`:
- **On the `oracle` platform** every thread of the process is pinned to the batch CPUs: every online CPU except `cores.reserved_for_timing` in `config/aqis_lab/oracle.yaml` (cores 2-3 on the A1 VM, owner decision in `docs/approvals/WP-0.6.md`). Each thread is read back; child processes inherit the pin. The log line reads `cores: batch on 0-1 (timing reserved 2-3; config <path>)`.
- **On every other platform** nothing is pinned, and the log line reads `cores: no reservation (platform cloud-vm)`.
- **A reservation that is not possible** (a reserved CPU not online, no CPU left for batch runs, a reservation that splits a physical core) or a pin that does not take stops the run with exit 2 before anything is staged or written.

Timing runs (every mode other than `batch`: `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay`, `human_session`) are pinned to the reserved CPUs by the same function, and the log line reads `cores: timing on 2-3 (…)`. The real-speed feeder pins itself the same way (DEBT-017).

## Not in WP-0.5
- Two runners on one run folder at the same time are not supported. Markers still make every counted shard provably complete.
