# Sprint 2 Oracle runbook (WP-1.2): VAD, turn-end and CPU streaming stages

These stages run on the Oracle Arm VM because the brief measures CPU speed there (brief sections 4 and 6). The Colab notebook `notebooks/aqis_lab/s2_live_stack.ipynb` builds the data first and runs the emotion stage afterwards. The general VM setup is in `ORACLE_RUNBOOK.md`; this page only adds what Sprint 2 needs. Copy each command's output into a `.txt` file and upload it with the results.

## 1. Update to the tag
In the clone on the VM (see "Update to a new tag" in `ORACLE_RUNBOOK.md`), check out `s2-colab-1`, then:
```bash
bash aqis_lab/deploy/oracle_setup.sh
uv venv --clear --python 3.13 ~/venv-live
uv pip sync --python ~/venv-live/bin/python --require-hashes --build-constraints requirements/aqis_lab/phase0.txt requirements/aqis_lab/s2-live.txt
```
The lock installs `textgrid` from source (pure Python); FunASR and TEN VAD are skipped on aarch64 by design, so `ten_vad` and the emotion models are not run here.

## 2. Pull the test sets from Drive
The Colab `prep` stage must have finished. This copies only, and writes nothing to Drive:
```bash
mkdir -p ~/s2
rclone copy aqis-drive:AQIS_LAB/s2/data ~/s2/data --checksum -v
```

## 3. Smoke, pilot, full (CLAUDE.md rule 6)
Run each stage on 3 clips, then 100, then everything. A rerun skips finished files. Batch work stays on CPUs 0-1; the streaming stage is timed alone on reserved CPU 2:
```bash
export PYTHONPATH=$PWD
taskset -c 0,1 ~/venv-live/bin/python -m aqis_lab.live vad  --out ~/s2 --limit 3
taskset -c 0,1 ~/venv-live/bin/python -m aqis_lab.live turn --out ~/s2 --limit 3
taskset -c 2   ~/venv-live/bin/python -m aqis_lab.live stream --out ~/s2 --limit 3
```
If these print `ERROR`, copy the whole output and stop: do not edit code on the VM. Then repeat with `--limit 100` and with no `--limit`. The `stream` stage runs `parakeet_tdt_v2_int8` and `parakeet_tdt_v2_fp32` at chunk sizes 160, 320 and 640 ms, and about 200 clips per file; allow the 30 minutes of the brief per shard and rerun to continue.

What the first runs print for the first time on this machine (record them in `EVIDENCE.md`): which model files were fetched (their SHA-256 goes to `~/s2/models/pins.json`), the machine line, and any `SMOKE FAILURE` line.

## 4. Send the results back
```bash
rclone copy ~/s2/results aqis-drive:AQIS_LAB/s2/results --immutable --checksum --exclude "*.partial" -v
rclone copy ~/s2/models/pins.json aqis-drive:AQIS_LAB/s2/models --immutable -v
```
`--immutable` never replaces a Drive file: if a stage was rerun and a finished file changed, rclone reports it instead. The Colab `report` stage then reads every result file from Drive.

## Not built
- The live Jitsi path (an `aiortc` bot receiving 20 ms RTP packets) is not part of this build; `aqis_lab/live/streaming.py` cuts clips into the same 20 ms frames and packets and measures the CPU decode. See `docs/progress/WP-1.2/PLAN.md`.
