# Oracle runbook

How you, the owner, set up and run the AQIS lab on the Oracle VM, sync its results to Google Drive every night, and report results back. Built by WP-0.6 (FR-0.6-01 to FR-0.6-06).

**The VM** (from `docs/environment/oracle_probe.txt`): VM.Standard.A1.Flex, Ampere Altra (aarch64), 4 OCPUs (CPUs `0-3`, one hardware thread each), 24 GB RAM, Ubuntu 24.04.4 LTS, glibc 2.39. Settings: `config/aqis_lab/oracle.yaml`.

Run every command as the user that runs the lab, in an SSH session. Nothing here needs a browser on the VM.

## Before you start
- SSH access to the Oracle VM.
- A computer with a web browser and rclone installed (for one Google sign-in; see "Configure rclone for Google Drive").
- The Google Drive folder `MyDrive/AQIS_LAB` with its subfolders `packs`, `models`, `results` and `logs`. The Colab launcher's `drive layout` step made them in WP-0.5. The lab never creates `AQIS_LAB` itself.
- The tag to use. After each audit passes, Claude pushes an annotated tag such as `aqis-lab-wp-0.6-oracle-1` (a later fix gets `-oracle-2`).
- About 20 minutes the first time.

## Clone the repository
The repository is private. Give the VM a **read-only deploy key** that opens this repository only (owner decision, WP-0.6 question 14):
1. On the VM, make a key:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/aqis_deploy -N "" -C "aqis-oracle-read-only"
   cat ~/.ssh/aqis_deploy.pub
   ```
2. On GitHub: the repository → **Settings → Deploy keys → Add deploy key**. Title `Oracle VM (read-only)`, paste the line `cat` printed, and leave **Allow write access** unticked. Save.
3. On the VM, add this to `~/.ssh/config` (create the file if it is missing):
   ```text
   Host github-aqis
     HostName github.com
     User git
     IdentityFile ~/.ssh/aqis_deploy
     IdentitiesOnly yes
   ```
4. Clone and check out the tag:
   ```bash
   git clone git@github-aqis:NasirAman-promcare/voice-bot-vad-harness.git ~/aqis
   cd ~/aqis
   git checkout aqis-lab-wp-0.6-oracle-1
   ```
   Every command below runs in `~/aqis`.

## Install uv and rclone
The setup needs **uv 0.8.17** (the version CI and Colab use), **git** and, for the nightly sync, **rclone 1.60.1 or newer**. On Ubuntu 24.04 the `rclone` package is 1.60.1, the same version as the cloud VM and CI (owner decision, WP-0.6 question 5). The probe shows rclone 1.60.1 is already installed.
```bash
curl -LsSf https://astral.sh/uv/0.8.17/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
sudo apt-get update
sudo apt-get install -y git rclone
rclone version
```
`uv --version` must print `uv 0.8.17`. Add the `export` line to `~/.bashrc` so new sessions find uv.

## Set up the lab
First see what the setup will do; nothing is changed:
```bash
bash aqis_lab/deploy/oracle_setup.sh --dry-run
```
It prints six `step N/6` lines and ends with `DRY RUN: nothing was changed`. Then run it:
```bash
bash aqis_lab/deploy/oracle_setup.sh
```
| Step | What it does |
| --- | --- |
| 1 platform | Stops at once unless the machine is x86_64 or aarch64, runs an operating system listed in `setup.operating_systems` (`ubuntu:24.04`), and has glibc 2.28 or newer |
| 2 tools | Checks git and uv 0.8.17 |
| 3 python | Takes the Python version from `docs/environment/colab_probe.txt` (3.13). Ubuntu 24.04 ships 3.12, so uv downloads its checksum-verified Python 3.13 from GitHub in step 5 |
| 4 wheels | Checks that every package in `requirements/aqis_lab/phase0.txt` has a ready-built wheel for this machine (aarch64); otherwise it stops and names each package. Nothing is compiled on the VM |
| 5 venv | Builds `.venv` and installs the lock with hash checking (`aqis_lab/deploy/dev_bootstrap.sh`) |
| 6 doctor | Runs `python -m aqis_lab doctor --target oracle` and exits with its status |

Running it again is safe: it reuses `.venv`, installs nothing and only writes a new doctor report.

## Doctor
Step 6 prints a table and the report path, `data/raw/aqis_lab/doctor/doctor_oracle_<UTC timestamp>.json`. Every row must be PASS except `gpu`, which is SKIP. You can run it on its own at any time:
```bash
.venv/bin/python -m aqis_lab doctor --target oracle --work-dir data/raw/aqis_lab/work --out data/raw/aqis_lab/doctor
```
| Row | PASS when |
| --- | --- |
| `platform` | The VM is detected as `oracle` (its asset tag reads `OracleCloud.com`) |
| `python` | Python major.minor equals the Colab probe's (3.13) |
| `lock` | The installed packages equal the lock |
| `disk` | At least 10 GB free for `data/raw/aqis_lab/work` |
| `ram` | At least 4 GB available |
| `gpu` | SKIP (the VM has no GPU) |
| `cores` | The core reservation below is possible on this VM |

The minimums come from `config/aqis_lab/doctor.yaml`:

| Target | Free disk (GB) | Available RAM (GB) |
| --- | --- | --- |
| oracle | 10 | 4 |

## Core reservation
Timing runs must not be slowed down by other lab work (FR-0.6-04). `config/aqis_lab/oracle.yaml` reserves **CPUs 2-3 for timing runs**; **batch runs use CPUs 0-1** (owner decision in `docs/approvals/WP-0.6.md`: the highest-numbered half of the physical cores).
- Timing runs (run modes `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay`, `human_session`) pin every thread to CPUs 2-3.
- Batch runs (the runner's `run` command) pin every thread to CPUs 0-1. Their `runner.log` shows `cores: batch on 0-1 (timing reserved 2-3; config …)`.
- A reservation that is not possible (a CPU that is not online, no CPU left for batch, half of a physical core) is a `cores` FAIL in the doctor and stops a run with exit 2.

This keeps **lab** work apart. Programs outside the lab, such as Jitsi on this VM, can still use CPUs 2-3. **Optional, your choice** (it changes system services): keep every system service, Jitsi included, on CPUs 0-1 while your own login sessions keep all four:
```bash
sudo systemctl set-property system.slice AllowedCPUs=0-1
systemctl show system.slice -p AllowedCPUs
```
Jitsi then has two CPUs. To undo it: `sudo systemctl set-property system.slice AllowedCPUs=`.

## Configure rclone for Google Drive
The sync copies to `AQIS_LAB/results` on your Drive through an rclone remote named **`aqis-drive`** (`rclone.remote` in `config/aqis_lab/oracle.yaml`). The VM has no browser, so you sign in to Google on your own computer once:
1. **On your computer** (with rclone installed), run `rclone authorize "drive"`. A browser opens: sign in with the Google account that owns `AQIS_LAB` and allow access. The terminal then prints a token between two arrow lines. Copy the whole `{"access_token": …}` text.
2. **On the VM**, run `rclone config` and answer:
   - `n` (new remote), name `aqis-drive`;
   - storage: `drive` (Google Drive);
   - `client_id` and `client_secret`: press Enter (leave empty);
   - scope: `1` (full access, `drive`). The narrower `drive.file` scope cannot see the `AQIS_LAB` folder you made, and then nothing could be synced (owner decision, WP-0.6 question 12);
   - `service_account_file`: Enter; edit advanced config: `n`;
   - use a web browser to authenticate: `n`, then paste the token from step 1;
   - configure as a Shared Drive: `n`; keep the remote: `y`; then `q` to quit.

   Do **not** set a `root_folder_id`: the sync writes to `AQIS_LAB/results` below your My Drive.
3. Protect the token and check the remote:
   ```bash
   chmod 600 ~/.config/rclone/rclone.conf
   rclone lsd aqis-drive:AQIS_LAB
   ```
   The listing must show `logs`, `models`, `packs` and `results`. If `results` is missing, `sync` stops with an error rather than create anything.

The token gives the VM access to your whole Drive. The sync itself only ever copies into `AQIS_LAB/results` and never deletes or replaces a file there.

## First sync
The sync copies the results store (`data/raw/aqis_lab/results`, `paths.results_store` in `oracle.yaml`) one way to `aqis-drive:AQIS_LAB/results` with `rclone copy --immutable`. It never deletes a file on Drive, and a Drive file that differs from the store is left as it is and reported (exit 1). Rows reach the store with `results add`:
```bash
.venv/bin/python -m aqis_lab results add --run data/raw/aqis_lab/runs/oc-0.6-02
.venv/bin/python -m aqis_lab sync --dry-run
.venv/bin/python -m aqis_lab sync
```
`--dry-run` lists what it would copy (`Skipped copy as --dry-run is set`) and ends with `DRY RUN: nothing was copied`. The real run ends with `sync complete`.

## Nightly sync schedule
Make the log folder once, then add one line to your crontab:
```bash
mkdir -p data/raw/aqis_lab/logs
crontab -e
```
Add this line, then save:
```text
17 2 * * * cd $HOME/aqis && /usr/bin/flock -n data/raw/aqis_lab/logs/sync.lock .venv/bin/python -m aqis_lab sync >> data/raw/aqis_lab/logs/sync.log 2>&1
```
It runs every night at 02:17 in the VM's time zone. `flock -n` skips a night's run if the previous one is still going, so two syncs never overlap. Check it with `crontab -l`, and the next morning with `tail -n 20 data/raw/aqis_lab/logs/sync.log`.

## Report results back
Copy files from the VM to your computer, then upload them on GitHub (**Add file → Upload files**) into the folder named below, on the work package's branch while it is open:
```bash
scp oracle:~/aqis/data/raw/aqis_lab/doctor/doctor_oracle_*.json .
```
(`oracle` is the SSH name you use for the VM.) For command output, copy the terminal text into a `.txt` file.

**OC-0.6-01** (after the WP-0.6 audit passes, in the clone at the tag):
1. `bash aqis_lab/deploy/oracle_setup.sh --dry-run`
2. `bash aqis_lab/deploy/oracle_setup.sh`
3. `.venv/bin/python -m pytest tests/aqis_lab -q -m oracle`

Upload the doctor JSON to `docs/environment/`, and the output of all three commands as `docs/progress/WP-0.6/OC-0.6-01_oracle.txt`.

**OC-0.6-02** (after "Configure rclone for Google Drive"):
1. `.venv/bin/python -m aqis_lab run --task clip-stats --pack data/packs/smoke/v1 --out data/raw/aqis_lab/runs/oc-0.6-02 --seed 0`
2. `.venv/bin/python -m aqis_lab results add --run data/raw/aqis_lab/runs/oc-0.6-02`
3. `.venv/bin/python -m aqis_lab sync --dry-run`

Upload the output of all three as `docs/progress/WP-0.6/OC-0.6-02_sync_dry_run.txt`.

## When something fails
Do not change code on the VM. Copy the full output into a `.txt` file, upload it next to the check's other files, and run `/surgical-fix` in a Claude session with its name. Common messages:

| Message | What to do |
| --- | --- |
| `ERROR: unsupported architecture …` or `unsupported operating system …` | The VM is not what `oracle.yaml` expects; send the message to Claude (the setup changed nothing) |
| `ERROR: uv not found on PATH` or `needs uv 0.8.17` | Follow "Install uv and rclone" |
| `ERROR: no build of <package> …` | A locked package has no aarch64 build; send the message to Claude |
| Doctor row `cores` FAIL | The reservation does not fit this VM; send the row's detail to Claude |
| `ERROR: rclone remote "aqis-drive" is not configured` | Follow "Configure rclone for Google Drive" |
| `ERROR: … AQIS_LAB/results must already exist` | Create the folder in Google Drive (or run the Colab launcher's `drive layout`) |
| `ERROR: … differ from the store and were left as they are` | A Drive file was changed by hand or by another machine; nothing was replaced. Send the message to Claude |

## Update to a new tag
```bash
cd ~/aqis
git fetch --tags
git checkout aqis-lab-wp-0.6-oracle-2
bash aqis_lab/deploy/oracle_setup.sh
```
The setup reinstalls only what the new lock changed.
