# Colab runbook (phase 0)

How to run the AQIS lab on Google Colab with `notebooks/aqis_lab/phase0_launcher.ipynb`, and how to do the WP-0.5 owner-run checks OC-0.5-01 and OC-0.5-02. The same lab commands run unchanged on the cloud VM and on Oracle.

## Before you start (once)
1. **Drive folder.** In Google Drive, create the folder `AQIS_LAB` directly in "My Drive" (`MyDrive/AQIS_LAB`). The lab never creates it; it only creates the subfolders listed below.
2. **GitHub token.**
   - On GitHub: **Settings → Developer settings → Fine-grained tokens**. Create a token with read-only "Contents" access to this repository only.
   - In Colab: open the key icon (Secrets), add `GITHUB_TOKEN`, and switch on notebook access.
   - The launcher reads the token inside the one `git clone` command's environment. It never goes into a variable, a URL, `.git/config` or any output.
3. **Tag.**
   - The launcher clones the repository at the pinned tag in cell 1, `AQIS_TAG`. For the WP-0.5 checks it is `aqis-lab-wp-0.5-colab-1`, created on the audited commit (owner decision, question 12).
   - A later fix gets `-colab-2`, and so on. Change `AQIS_TAG` in cell 1 when you are told a new tag exists.

## Running the launcher
1. On GitHub, open `notebooks/aqis_lab/phase0_launcher.ipynb` at the tag and download it. In Colab: **File → Upload notebook**.
2. **Runtime → Change runtime type → CPU** (a T4 is needed only from WP-0.7).
3. Edit only cell 1: `AQIS_TAG` and `RUN_ARGS`. Run the cells from top to bottom. Cell 1 also fixes the clone folder `/content/aqis` and the run folder on Drive, `RUN_OUT = "/content/drive/MyDrive/AQIS_LAB/results/wp05-smoke-clip-stats"`.

| Cell | What it does | What you see |
| --- | --- | --- |
| 1 | Settings (literals only), then mounts Google Drive at `/content/drive` | Drive's permission prompt, then `Mounted at /content/drive` |
| 2 | Removes any old local clone in `/content/aqis` (local disk only, never Drive), then clones the repository at `AQIS_TAG` | Nothing on success; a failed clone stops the cell with the command line, which holds no token |
| 3 | Installs `uv` 0.8.17 and runs `bash aqis_lab/deploy/dev_bootstrap.sh`: `.venv` on the Colab probe's Python with the hash-checked lock | `OK: .venv ready: Python 3.13.x, lock sha256 …` |
| 4 | `drive layout`, `unitlog start`, `doctor --target colab`, then the smoke-pack runner | The layout lines, `session colab-… started`, the doctor's PASS/FAIL table and `report: …`, then the runner log |
| 5 | `unitlog end`: appends this session's compute units to `AQIS_LAB/logs/units.csv` | `session colab-…: <hours> h x <rate> units/h = <units> units` |

Every command runs with `check=True`. A failing command (for example a doctor FAIL) stops its cell with an error, and the later commands in that cell do not run.

## Drive layout
`drive layout` creates only the missing folders below. It never deletes, renames or changes anything.

```text
MyDrive/AQIS_LAB/
  packs/      packs copied to Drive (later phases; phase 0 reads the smoke pack from the repository)
  models/     model files (WP-0.7)
  results/    run folders, such as results/wp05-smoke-clip-stats/
  logs/       doctor reports, units.csv, units_open_session.json
  doctor_write_check.json   the doctor's write test, overwritten each time
```

- **Only under `AQIS_LAB`.** The commands the launcher runs (`doctor`, `drive layout`, `run`, `unitlog`) refuse to write anywhere on Drive outside `MyDrive/AQIS_LAB` (NFR-0.5-02). The older `score`, `pack build`, `registry build` and `registry fetch` commands do not check this yet (DEBT-014, fixed in WP-0.7): do not point their `--out` or cache at Drive.
- **Crowded folders.** Google Drive gets slow with crowded folders. Before a lab write would make a Drive folder hold more than 1,000 entries, the lab prints a `WARNING:` line and then still writes (owner decision, question 10). `drive layout` also warns about every folder already over 1,000.
- **Local disk for computing.** Packs are copied to local disk (`/content/aqis/data/raw/aqis_lab/work/`), checked by SHA-256, and extracted there before any processing. The run folder itself (`RUN_OUT`) is on Drive, so a run survives a disconnect.

## Doctor minimums
`python -m aqis_lab doctor` checks free disk on the local work folder and available RAM against these values (`config/aqis_lab/doctor.yaml`; details in `docs/doctor/DOCTOR.md`). GB means 1,000,000,000 bytes.

| Target | Free disk (GB) | Available RAM (GB) |
| --- | --- | --- |
| cloud | 10 | 4 |
| colab | 10 | 4 |
| oracle | 10 | 4 |

## Unit log
Each Colab session appends one row to `AQIS_LAB/logs/units.csv`:

| Column | Meaning |
| --- | --- |
| `session_id` | `colab-<date>-<12 hex>` |
| `platform` | Platform name |
| `gpu_type` | GPU type; empty on a CPU runtime |
| `start_utc`, `end_utc` | Start and end, UTC |
| `end_basis` | `end-command` or `last-seen` |
| `hours` | Session length in hours |
| `runtime` | The rate key |
| `units_per_hour` | The rate used |
| `estimated_units` | `hours` × `units_per_hour` |
| `rate_source` | Where the rate comes from |

- **Estimate.** The exact session length in hours × the rate for the runtime, computed exactly and rounded half-even to 4 decimals.
- **Rates.** From `config/aqis_lab/colab_rates.yaml`: the Build Plan's figures (source "AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026)"). A runtime missing from the table is an error, never a guessed rate. TPU runtimes are not recognised; phase 0 uses CPU and T4 runtimes only.

| Runtime | Units per hour |
| --- | --- |
| cpu | 0.08 |
| Tesla T4 | 1.19 |
| NVIDIA L4 | 1.71 |
| NVIDIA A100-SXM4-40GB | 5.40 |

**When a session ends.**
- `unitlog start` (cell 4) records the session in `AQIS_LAB/logs/units_open_session.json`. `run` (after every shard) and `doctor` keep its "last seen" time current.
- `unitlog end` (cell 5) appends the row with `end_basis=end-command`.
- If a runtime dies before cell 5, the next `unitlog start` first closes the old session at its last-seen time, with `end_basis=last-seen` (owner decision, question 11).
- The estimate leaves out the minutes before cell 4 and idle time after the last command.

## OC-0.5-01: doctor on Colab
1. Cell 1: `AQIS_TAG = "aqis-lab-wp-0.5-colab-1"` and `RUN_ARGS = ["--shard-clips", "10"]`. Run cells 1 to 4 on a CPU runtime.
   - **Expected:** the doctor table shows `platform`, `python`, `lock`, `disk`, `ram`, `drive-mount` and `drive-folder` as PASS and `gpu` as SKIP, then `result: PASS`.
2. Add one new cell and run:
   ```text
   !cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab
   ```
   **Expected:** a last line ending in `passed`, with nothing failed.
3. Run cell 5.
4. Commit to the pull request's branch on GitHub (**Add file → Upload files**):
   - the doctor report `MyDrive/AQIS_LAB/logs/doctor_colab_<timestamp>.json`, into `docs/environment/`;
   - the pytest output, copied into `docs/progress/WP-0.5/OC-0.5-01_colab_tests.txt`.

## OC-0.5-02: disconnect and resume
The smoke run takes about a second, so it is stopped on purpose after 2 of its 6 shards, and then resumed on a fresh runtime (owner decision, question 5).

1. Cell 1: `RUN_ARGS = ["--shard-clips", "10", "--max-shards", "2"]`. Run all cells (1 to 5).
   - **Expected:** the runner log ends with `stopped after 2 computed shard(s) (--max-shards 2); 4 shard(s) remain`.
2. **Runtime → Disconnect and delete runtime.** The local disk is wiped; the run folder on Drive is kept.
3. Reconnect. Cell 1: `RUN_ARGS = ["--shard-clips", "10"]`. Run all cells again.
   - **Expected:** `session 2 start`, then `shard 00000 skipped` and `shard 00001 skipped`, then shards 00002 to 00005 `started` and `finished`, then `run complete: 6 shard(s), 2 skipped and 4 computed in this session`.
   - If the new runtime has another CPU model, a line says so; that is allowed.
4. Commit to the pull request's branch:
   - `MyDrive/AQIS_LAB/results/wp05-smoke-clip-stats/runner.log` as `docs/progress/WP-0.5/OC-0.5-02_runner.log`;
   - `MyDrive/AQIS_LAB/logs/units.csv` as `docs/progress/WP-0.5/OC-0.5-02_units.csv`.

**Starting a run again from nothing.** Add `"--from-scratch"` to `RUN_ARGS`. The old run folder is renamed `wp05-smoke-clip-stats.superseded-<UTC>` on Drive, never deleted.

## OC-0.7-01: phase 0 smoke on a T4
The WP-0.7 smoke run uses its own launcher, `notebooks/aqis_lab/phase0_smoke_launcher.ipynb` (owner decision, WP-0.7 question 13). It follows the same rules and has the same five code cells as the WP-0.5 launcher. Two things differ:
- Cell 3 installs the GPU extras too.
- Cell 4 checks the GPU and runs the smoke.

It needs a **T4 GPU** runtime. The run folder is `RUN_OUT = "/content/drive/MyDrive/AQIS_LAB/results/phase0-smoke-colab"`. On Colab the smoke runs `vosk-batch`, `harness-vad`, `vosk-realspeed`, `parakeet-offline` and `parakeet-compute-delay` (`config/aqis_lab/phase0_smoke.yaml`). Details of the bundle are in `docs/runs/PHASE0_SMOKE.md`.

| Cell | What it does | What you see |
| --- | --- | --- |
| 1 | Settings (literals only), then mounts Google Drive at `/content/drive` | `Mounted at /content/drive` |
| 2 | Clones the repository at `AQIS_TAG` into `/content/aqis` | Nothing on success |
| 3 | Installs `uv` 0.8.17 and runs `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`: the CPU lock plus `requirements/aqis_lab/phase0-gpu.txt` (NeMo, torch; about 5 GB, several minutes) | `OK: .venv ready: Python 3.13.x, lock sha256 …`, then `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …` |
| 4 | `drive layout`, `unitlog start`, `doctor --target colab --expect-gpu`, then `phase0 smoke --target colab --out RUN_OUT --drive-mount /content/drive` | The doctor table, then the runner logs of the five tasks, the `scored …` lines and `smoke complete: bundle … archive …/phase0-smoke-colab-<stamp>.tar` |
| 5 | `unitlog end` | `session colab-…: <hours> h x <rate> units/h = <units> units` |

1. Download the launcher at the tag `aqis-lab-wp-0.7-colab-1` and upload it to Colab (as in "Running the launcher").
2. **Runtime → Change runtime type → T4 GPU.**
3. In cell 1, check `AQIS_TAG = "aqis-lab-wp-0.7-colab-1"` and `RUN_ARGS = []`. Run cells 1 to 4.
   - **Expected (doctor):** `gpu` PASS with `Tesla T4`, `lock` PASS naming `requirements/aqis_lab/phase0.txt + requirements/aqis_lab/phase0-gpu.txt`, then `result: PASS`.
   - **Expected (smoke):** the last line starts with `smoke complete:` and names the archive `/content/drive/MyDrive/AQIS_LAB/results/phase0-smoke-colab/phase0-smoke-colab-<stamp>.tar`.
4. Add one new cell and run:
   ```text
   !cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m "colab or gpu"
   ```
   **Expected:** a last line ending in `passed`, with nothing failed.
5. Run cell 5.
6. Commit to the pull request's branch on GitHub (**Add file → Upload files**):
   - the archive `MyDrive/AQIS_LAB/results/phase0-smoke-colab/phase0-smoke-colab-<stamp>.tar`, into `data/runs/phase0-smoke/`;
   - the doctor report `MyDrive/AQIS_LAB/logs/doctor_colab_<timestamp>.json`, into `docs/environment/`;
   - the output of cells 3 and 4 and of the pytest cell, copied into `docs/progress/WP-0.7/OC-0.7-01_colab.txt`.

If the runtime disconnects during the smoke, reconnect and run all cells again with the same `RUN_OUT`: each task's run resumes and skips its finished shards.

**Running it again at a new tag.** The run folders in `RUN_OUT` belong to the commit that made them. The smoke at a new tag stops with `ERROR: … holds another run … --from-scratch`. Set `RUN_ARGS = ["--from-scratch"]` in cell 1 for that run: each old run folder is renamed `<task>.superseded-<UTC>` on Drive, never deleted, and the runs start again. Set it back to `RUN_ARGS = []` afterwards. A task that cannot run on this runtime (for example no GPU) stops with `ERROR:` before anything is written.

## When something fails
Commit the output (or the report) to the pull request's branch, start a Claude session, and type `/surgical-fix <path to the report>`. Do not debug inside Colab. Do not run two launchers on the same run folder at once, for example in two browser tabs.
