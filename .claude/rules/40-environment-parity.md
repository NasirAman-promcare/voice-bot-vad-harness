# Environment parity: cloud VM, Colab, Oracle

- **Python**: use exactly the major.minor version recorded in `docs/environment/colab_probe.txt`. If that file is missing, stop and ask.
- **Dependencies**: pin every package in `requirements/aqis_lab/` lock files, installable with plain `pip` on Colab. GPU-only packages go in a separate `-gpu` lock and are imported only inside GPU adapters.
- **Paths**: no hard-coded absolute paths. Resolve from the repo root or command-line arguments.
- **Platform**: detect the platform once, in `aqis_lab.platform`, and record it in every run card: `cloud-vm`, `colab`, `kaggle` or `oracle`.
- **Colab limits**: no servers, tunnels or proxies; runtimes stop after about 12 hours at most; Google Drive is slow with many small files and struggles past about 10,000 items per folder. Copy archives to local disk before processing.
- **Untestable here**: anything that cannot run on this cloud VM (GPU, Drive, Oracle cores, Jitsi) needs a test marked `colab`, `oracle` or `gpu`, a one-command acceptance check for the owner, and its expected output. List these under "Owner-run checks" in `EVIDENCE.md`.
- **Cloud VM facts**: Ubuntu 24.04 on x86_64, about 4 vCPUs, 16 GB RAM, 30 GB disk, no GPU. The Oracle VM may be Arm; check `docs/environment/oracle_probe.txt`.
