# EVIDENCE — WP-0.5

Environment:
- cloud VM (Ubuntu 24.04.4 LTS, x86_64, 4 vCPUs, "Intel(R) Xeon(R) Processor @ 2.80GHz"), Python 3.13.12 in `.venv` (Colab probe: 3.13);
- lock `requirements/aqis_lab/phase0.txt` sha256 `84151d8f77b8512288620fdb82325fc2b22551da77324e171b7cdf055d732acc` (unchanged by this WP);
- branch `claude/magical-goldberg-kjvw5r`;
- approval `docs/approvals/WP-0.5.md` on `main`: questions 2 to 14 as recommended. The Colab unit rates come from the Build Plan (March 2026): cpu 0.08, Tesla T4 1.19, NVIDIA L4 1.71, NVIDIA A100-SXM4-40GB 5.40 units per hour. Source: "AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026)";
- Colab facts: `docs/environment/colab_platform_probe.txt` on `main`:
  - `COLAB_RELEASE_TAG` is set;
  - no `nvidia-smi` on a CPU runtime (exit 127);
  - CPU "Intel(R) Xeon(R) CPU @ 2.20GHz";
  - Drive mounted at `/content/drive` with type `fuse.drive`;
  - 206 GB free disk and 11 GB available RAM.

Baseline before any change (change-control step 3, for `aqis_lab/__main__.py` and the registry): `bash aqis_lab/deploy/dev_bootstrap.sh`, then the fast suite: `1365 passed, 14 deselected in 185.57s`.

All test outputs below are real excerpts from this session. Fast command, per requirement:
`.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network" -k <ID>`.

## Requirements
### FR-0.5-01 — Platform detection and machine facts
- Tests (`tests/aqis_lab/test_aqis_platform.py`):
  - `test_FR_0_5_01_detects_each_platform_from_its_signal` (5 cases);
  - `test_FR_0_5_01_unknown_platform_is_an_error` (4 cases);
  - `test_FR_0_5_01_conflicting_signals_are_an_error`;
  - `test_FR_0_5_01_gpu_type_from_nvidia_smi_else_null` (4 cases; stand-in `nvidia-smi`, the GPU test double);
  - `test_FR_0_5_01_failing_nvidia_smi_is_an_error`;
  - `test_FR_0_5_01_cpu_model_from_cpuinfo_or_lscpu`;
  - `test_FR_0_5_01_os_from_os_release`;
  - `test_FR_0_5_01_memory_disk_and_mount_facts`;
  - `test_FR_0_5_01_real_machine_facts`;
  - `test_FR_0_5_01_machine_block_valid_in_run_card`;
  - `test_FR_0_5_01_platform_details_only_from_platform_module` (must-catch 5; allow-list per question 7 (a)).
- Colab-only test: `test_FR_0_5_01_colab_runtime_detected` in `tests/aqis_lab/test_aqis_colab_live.py` (marker `colab`, OC-0.5-01).
- Test-first: before `aqis_lab/platform.py` existed, collection failed with `ImportError: cannot import name 'platform' from 'aqis_lab'`.
- Command: the fast command with `-k FR_0_5_01`.
```text
.....................                                                    [100%]
21 passed, 1380 deselected in 2.01s
```
- Real machine block on this VM (`.venv/bin/python -c "from aqis_lab import platform as p; print(p.machine_block()); print(p.machine_info().signals)"`):
```text
{'platform': 'cloud-vm', 'gpu': None, 'cpu_model': 'Intel(R) Xeon(R) Processor @ 2.80GHz', 'architecture': 'x86_64', 'os': 'Ubuntu 24.04.4 LTS', 'python_version': '3.13.12'}
('environment variable CLAUDE_CODE_REMOTE=true',)
```
- The Colab-only test fails here, as it must off Colab (`-m colab`): `1 failed, 1400 deselected`.
- Fast suite after FR-0.5-01 (the FR-0.5-02 test file, written next and not yet committed, set aside):
  - `1 failed, 1385 passed, 15 deselected in 190.00s`;
  - the one failure was `test_FR_0_0_04_lab_tests_use_only_registered_markers`, caused only by that uncommitted file's import error;
  - with the file set aside: `tests/aqis_lab/test_aqis_markers.py`, `5 passed in 4.63s`.
- Registry: rows CAP-PLAT-001 to CAP-PLAT-003. The first run caught a header/registry mismatch (`test_FR_0_0_08_module_headers_match_registry`); the header now lists the Colab test too.
- Status: DONE
