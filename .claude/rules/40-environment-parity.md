# Environment parity: cloud VM, Colab, Oracle, CI

- **Python**: the major.minor recorded in `docs/environment/colab_probe.txt` (if missing, that is an ACCESS/COMPUTE request).
- **Dependencies**: pinned with hashes in `requirements/aqis_lab/` locks, installable with plain `pip`. GPU-only packages in a separate `-gpu` lock, imported only inside GPU adapters. Arm compatibility is checked against `docs/environment/oracle_probe.txt` (TEN VAD has no Arm build).
- **Paths**: no hard-coded absolute paths; resolve from the repo root or arguments.
- **Platform**: detected once in `aqis_lab.platform` and recorded in every run card.
- **Where work runs**: coding and fast tests on the cloud VM (4 vCPU, 16 GB RAM, 30 GB disk: never download corpora here); full suites, break suite and mutation in CI; heavy CPU and data jobs on the Oracle runner; GPU on Colab (owner) or an automated GPU runtime once its probe exists. `docs/process/CONTEXT_BUDGET.md` has the compute map.
- **Colab limits**: no servers, tunnels or proxies; runtimes stop after about 12 hours; Drive struggles past about 10,000 items per folder.
- **Untestable here**: anything that cannot run on the cloud VM gets a test marked `colab`, `oracle` or `gpu`, a one-command check with its expected output, and a line in the spec's owner-run checks (blocking or post-merge).
- **A new runtime** (Kaggle, Modal, AWS) counts only after a committed probe file and a parity test.
