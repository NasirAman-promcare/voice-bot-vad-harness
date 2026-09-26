# WP-0.6 — Oracle worker, results store and traceability

- **Depends on**: WP-0.5
- **Runs on**: cloud VM; the owner runs the Oracle checks
- **Read first**: `docs/environment/oracle_probe.txt`; Build Plan section "Resource plan"

## Goal
The Oracle VM runs the lab the same way as everywhere else; results are stored append-only; and any score can be traced back to exactly what produced it.

## Deliverables
- `aqis_lab/deploy/oracle_setup.sh`, `docs/oracle/ORACLE_RUNBOOK.md`
- `aqis_lab/results/` (store and queries), `aqis_lab/trace.py`, `aqis_lab/sync.py`, `aqis_lab/timing/cores.py`
- `config/aqis_lab/oracle.yaml` (paths, reserved cores, rclone remote name)

## Functional requirements
- **FR-0.6-01** `oracle_setup.sh` creates the virtual environment with the Colab-matching Python, installs the lock, and runs `doctor --target oracle`. It is idempotent and works on x86_64 and aarch64; if a dependency has no build for the architecture, it stops with a message naming the package.
- **FR-0.6-02** Results store: append-only files partitioned by `run_card_id`, never overwritten, with a documented schema and a DuckDB view. `python -m aqis_lab results query --run-card <id>` returns the rows.
- **FR-0.6-03** `python -m aqis_lab trace <result-row-id>` prints the run card, pack manifest ID and version, clip, git commit and lock hash for that row.
- **FR-0.6-04** Timing runs are pinned to the reserved cores in `oracle.yaml`, and batch runs are kept off them. A test reads the process CPU affinity to prove it.
- **FR-0.6-05** `python -m aqis_lab sync [--dry-run]` copies results one way to `AQIS_LAB/results` on Drive with rclone, never deleting remote files. A missing rclone remote gives a clear error pointing to the runbook.
- **FR-0.6-06** The runbook gives the owner exact steps: clone, setup, doctor, rclone configuration, a nightly sync schedule, and how to report results back.

## Acceptance commands
- **AT-0.6-01** On the cloud VM: `bash aqis_lab/deploy/oracle_setup.sh --dry-run` explains each step; the fast suite passes, including results-store, trace and affinity tests.
- **AT-0.6-02** The audit gate passes with `--wp WP-0.6`.

## Owner-run checks
- **OC-0.6-01** On Oracle: run `oracle_setup.sh`, then commit the doctor JSON to `docs/environment/`.
- **OC-0.6-02** Configure the rclone remote per the runbook and run `python -m aqis_lab sync --dry-run`; commit its output.

## Owner needs
- `docs/environment/oracle_probe.txt`; SSH access to the Oracle VM; a Google Drive rclone remote on Oracle.

## Stop and ask if
- The Oracle architecture blocks a pinned dependency, or core reservation is not possible on the shape.

## Must-catch behaviours
1. The results store refuses to overwrite existing rows.
2. `trace` returns the exact run card, manifest version, clip, commit and lock hash for a row.
3. Timing runs are pinned to the reserved cores.
4. `sync` never deletes remote files.
5. The setup script stops with a clear message on an unsupported architecture or operating system.
