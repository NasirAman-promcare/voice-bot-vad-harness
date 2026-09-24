# WP-0.5 — Platform detection, doctor, resumable runner and Colab launcher

- **Depends on**: WP-0.2, WP-0.4
- **Runs on**: cloud VM; the owner runs the Colab checks
- **Read first**: `.claude/rules/40-environment-parity.md`; Build Plan sections "Resource plan" and "Run modes by phase"

## Goal
The same command runs on the cloud VM, Colab and Oracle; a health check proves the environment is right; and long runs survive disconnects without redoing finished work.

## Deliverables
- `aqis_lab/platform.py`, `aqis_lab/doctor.py`, `aqis_lab/runner/`, `aqis_lab/unitlog.py`
- `config/aqis_lab/colab_rates.yaml` (owner-editable unit rates per GPU type)
- `notebooks/aqis_lab/phase0_launcher.ipynb`
- `docs/colab/COLAB_RUNBOOK.md`

## Functional requirements
- **FR-0.5-01** `aqis_lab.platform` is the only place that detects the platform. It returns platform (`cloud-vm`, `colab`, `kaggle`, `oracle`), GPU type (from `nvidia-smi` when present, else null), CPU model, architecture, OS and Python version, and fills the run card's `machine` block.
- **FR-0.5-02** `python -m aqis_lab doctor --target cloud|colab|oracle [--expect-gpu]` checks: Python version equals the Colab probe's; the installed packages match the lock; free disk and RAM against documented minimums; GPU present when `--expect-gpu`; on Colab, Google Drive mounted and the `AQIS_LAB` folder writable. It prints a PASS/FAIL table and writes `doctor_<platform>_<UTC timestamp>.json`. Any FAIL gives a non-zero exit.
- **FR-0.5-03** Drive layout: creates `AQIS_LAB/{packs,models,results,logs}` when missing, never deletes, and warns before any folder exceeds 1,000 items.
- **FR-0.5-04** Copy then compute: pack archives are copied from Drive (or the repo) to local disk, hash-verified, and extracted locally before any processing.
- **FR-0.5-05** Resumable runner: a run card is split into shards of configurable size (default at most 30 minutes of expected work). Each shard's results are written atomically with a completion marker. On restart, finished shards are skipped; starting over requires an explicit `--from-scratch`.
- **FR-0.5-06** Kill-and-resume test: a test kills a real run in a subprocess after k shards, restarts it, and asserts the final results are byte-identical to an uninterrupted run and that finished shards were not recomputed.
- **FR-0.5-07** Unit log: each Colab session appends platform, GPU type, start and end UTC, and estimated units (hours × rate from `colab_rates.yaml`) to `AQIS_LAB/logs/units.csv`. Initial rates are the Build Plan's figures with their source.
- **FR-0.5-08** Launcher notebook: at most 6 cells. They only mount Drive, clone the private repo at a pinned tag using the `GITHUB_TOKEN` Colab secret, install the lock, and call phase commands. No logic lives in the notebook; a static test enforces this. The repo tag is one variable in the first cell.

## Non-functional requirements
- **NFR-0.5-01** Runner overhead under 5 % against a direct loop on the smoke pack.
- **NFR-0.5-02** Nothing in the lab writes to Drive except under `AQIS_LAB/`.

## Acceptance commands
- **AT-0.5-01** `python -m aqis_lab doctor --target cloud` passes on the cloud VM.
- **AT-0.5-02** The fast and slow CPU suites pass, including the kill-and-resume test.
- **AT-0.5-03** The audit gate passes with `--wp WP-0.5`.

## Owner-run checks
- **OC-0.5-01** Open the launcher notebook in Colab on a CPU runtime, run all cells, and commit the doctor JSON to `docs/environment/`. Expected: all checks PASS except the GPU check, which is skipped without `--expect-gpu`.
- **OC-0.5-02** In the same notebook, start the smoke pack runner, disconnect the runtime partway, reconnect, run it again, and commit the runner log showing skipped shards.

## Owner needs
- Google Drive folder `AQIS_LAB`; a fine-grained, read-only GitHub token for this repository stored as `GITHUB_TOKEN` in Colab Secrets.

## Stop and ask if
- A Colab-only behaviour cannot be exercised by an automated test here; describe the owner check instead of guessing.
