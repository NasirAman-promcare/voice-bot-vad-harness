# Doctor (`python -m aqis_lab doctor`)

The doctor checks that a machine is ready for the lab and records the result. Built by WP-0.5 (FR-0.5-02). Code: `aqis_lab/doctor.py`, `aqis_lab/commands/doctor.py`. Every machine fact comes from `aqis_lab.platform` (FR-0.5-01).

## Usage
```bash
.venv/bin/python -m aqis_lab doctor --target cloud                  # this cloud VM (and the CI runner)
.venv/bin/python -m aqis_lab doctor --target oracle                 # the Oracle VM (WP-0.6)
.venv/bin/python -m aqis_lab doctor --target colab --drive-mount /content/drive --out /content/drive/MyDrive/AQIS_LAB/logs
.venv/bin/python -m aqis_lab doctor --target colab --expect-gpu --drive-mount /content/drive   # GPU runtime
```

| Option | Meaning |
| --- | --- |
| `--target cloud\|colab\|oracle` | The platform this machine must be (`cloud` means `cloud-vm`) |
| `--expect-gpu` | Fail unless a GPU is detected; without it the GPU check is SKIP |
| `--drive-mount DIR` | Where Google Drive is mounted; required with `--target colab` |
| `--out DIR` | Folder for the JSON report; default `data/raw/aqis_lab/doctor/` (git-ignored). On Drive it must be inside `MyDrive/AQIS_LAB` |
| `--work-dir DIR` | Local work folder whose free disk is checked; default `data/raw/aqis_lab/work/` |

| Exit code | Meaning |
| --- | --- |
| 0 | No check FAILs (PASS or SKIP only) |
| 1 | At least one check FAILs |
| 2 | Usage error, an unreadable input the report cannot be built without, or the report cannot be written. The message starts with `ERROR:` |

## Checks
Every check runs, even after an earlier FAIL, in this order:

| Check | PASS when |
| --- | --- |
| `platform` | `aqis_lab.platform` detects a platform and it equals the target. A detection error is a FAIL |
| `python` | The running Python major.minor equals the one in `docs/environment/colab_probe.txt` (owner decision, WP-0.5 question 9; both full versions are shown) |
| `lock` | The installed distributions equal the applicable entries of `requirements/aqis_lab/phase0.txt`: every entry installed at its pinned version, nothing installed that the lock does not list. Every difference is listed |
| `disk` | Free space on the file system of `--work-dir` is at least the target's minimum |
| `ram` | `MemAvailable` is at least the target's minimum |
| `gpu` | With `--expect-gpu`: a GPU type is detected (from `nvidia-smi`). Without it: SKIP |
| `drive-mount` (colab only) | `--drive-mount` is a Google Drive (`fuse.drive`) mount |
| `drive-folder` (colab only) | `<mount>/MyDrive/AQIS_LAB` is a folder, and `doctor_write_check.json` can be written in it atomically and read back. The same file is reused each time. The lab never creates `AQIS_LAB`; you create it in Google Drive |
| `cores` (oracle only; WP-0.6 FR-0.6-04) | The core reservation in `config/aqis_lab/oracle.yaml` is possible on this machine: every CPU in `cores.reserved_for_timing` is online, the reservation holds whole physical cores (all hardware threads of each core; owner decision, WP-0.6 question 10), and at least one online CPU is left for batch runs. PASS shows `timing on <CPUs>, batch on <CPUs>`; FAIL names the reason. See `docs/oracle/ORACLE_RUNBOOK.md` |

## Minimums
Values from `config/aqis_lab/doctor.yaml` (owner decision, WP-0.5 question 8). GB means 1,000,000,000 bytes. A test keeps this table, the config and `docs/colab/COLAB_RUNBOOK.md` identical.

| Target | Free disk (GB) | Available RAM (GB) |
| --- | --- | --- |
| cloud | 10 | 4 |
| colab | 10 | 4 |
| oracle | 10 | 4 |

## Report
The table goes to stdout, followed by `result: PASS|FAIL` and `report: <path>`. The file `doctor_<platform>_<YYYYMMDDTHHMMSSZ>.json` (`unknown` when detection failed) is never replaced. It holds:

| Field | Meaning |
| --- | --- |
| `report_version` | `"1.0"` |
| `target`, `expect_gpu` | The options given |
| `created_utc` | When the checks ran, UTC ISO 8601 with `Z`; the file name's timestamp is this time without separators and fraction |
| `machine` | The run card `machine` block from `aqis_lab.platform`, or null when detection failed |
| `lock` | `file` and the `sha256` of its bytes |
| `code` | The `version` command's line (package version, short commit, `+dirty`, Python) |
| `checks` | One object per check: `name`, `status` (`PASS`, `FAIL`, `SKIP`), `expected`, `actual`, `detail` |
| `result` | `FAIL` when any check fails, else `PASS` |
