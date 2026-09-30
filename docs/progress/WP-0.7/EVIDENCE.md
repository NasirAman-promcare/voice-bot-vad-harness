# EVIDENCE — WP-0.7 First adapters and the smoke run

Environment: cloud VM (`cloud-vm`), Ubuntu 24.04.4 LTS, x86_64, 4 CPUs, Python 3.13.12 in `.venv`, uv 0.8.17, lock `requirements/aqis_lab/phase0.txt` sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef` (after the WP-0.7 lock change). Branch `claude/clever-wright-gmps92`.

Owner inputs used: `docs/approvals/WP-0.7.md` on `main` (`a2d10f5`): questions 1 to 16 as recommended; question 1 WebRTC VAD mode 2, 20 ms frames (`webrtc_vad_mode2` through the harness registry); question 5 driver 580.82.07, so torch comes from PyPI (CUDA 13); `ALLOW-EDIT: tests/aqis_lab/test_aqis_oracle_setup.py`. T4 probe `docs/environment/colab_gpu_probe.txt` (Tesla T4, driver 580.82.07, compute capability 7.5, Python 3.13.15, 2 vCPUs).

## Requirements

### Locks and installs (FR-0.7-02, FR-0.7-03; owner decisions, questions 2 and 3)
- Code: `requirements/aqis_lab/phase0.in` and `phase0.txt` (CAP-ENV-002), `aqis_lab/deploy/dev_bootstrap.sh` (CAP-ENV-001), `aqis_lab/deploy/oracle_setup.sh` (CAP-ENV-007); the approved test edit `tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` (only that function, plus its helper `script_source_builds`).
- Lock change (regenerated with the recorded command; existing pins kept as preferences):
```text
$ diff <(grep -oE "^[a-z0-9_.-]+==[^ ]+" phase0.before.txt) <(grep -oE "^[a-z0-9_.-]+==[^ ]+" requirements/aqis_lab/phase0.txt)
> certifi==2026.7.22
> charset-normalizer==3.5.2
> idna==3.20
< packaging==26.3
> packaging==24.2
> requests==2.34.2
> setuptools==84.0.0
> srt==3.5.3
> tqdm==4.70.1
> urllib3==2.8.0
> vosk==0.3.45
> webrtcvad-wheels==2.0.14
> websockets==17.1
```
- Tests: `test_FR_0_7_02_lock_pins_vosk_webrtcvad_and_the_srt_build_tool`, `test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints`, `test_FR_0_7_02_source_build_uses_only_the_locked_setuptools` (slow, network), `test_FR_0_7_02_bootstrap_rejects_unknown_option`, `test_FR_0_7_03_bootstrap_gpu_needs_the_gpu_lock`, `test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds` (network, approved edit).
- Tests first, against the previous `dev_bootstrap.sh` (`git show HEAD:aqis_lab/deploy/dev_bootstrap.sh`): 4 failed for the expected reasons (no `--build-constraints`; the source build picked the refusing setuptools: `ImportError: this setuptools is not the pinned one`; `--cpu` and `--gpu` accepted silently). With the new script:
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_locks_gpu.py -q -p no:cacheprovider
5 passed in 2.08s
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_lock.py tests/aqis_lab/test_aqis_bootstrap.py tests/aqis_lab/test_aqis_oracle_setup.py -q -p no:cacheprovider -m "not gpu and not colab and not oracle"
30 passed, 1 deselected in 39.35s
$ bash aqis_lab/deploy/oracle_setup.sh --dry-run | grep "step 4"
step 4/6 wheels: would check that each of the 37 pins in requirements/aqis_lab/phase0.txt has a binary build for x86_64-manylinux_2_39 and Python 3.13 (uv pip compile --only-binary :all:), except the approved source builds (srt); it stops naming every package without one
```
- Fast suite after this step: `1644 passed, 26 deselected in 210.16s`.
- Status: DONE for the CPU lock; the GPU lock is under FR-0.7-03.

### FR-0.7-02 — Vosk adapter and model cache (in progress: runner and smoke parts follow)
- Code: `aqis_lab/adapters/model_cache.py` (CAP-MODEL-001 to -003), `config/aqis_lab/models.yaml` (CAP-MODEL-004), `aqis_lab/adapters/vosk_stt.py` (CAP-VOSK-001 to -003).
- Tests: `tests/aqis_lab/test_aqis_model_cache.py`, `tests/aqis_lab/test_aqis_vosk.py`, `tests/aqis_lab/test_aqis_locks_gpu.py` (all `test_FR_0_7_02_*`); network tests use the real model downloaded from alphacephei.com and checked against the pins.
- Tests first: before `model_cache.py` and `vosk_stt.py` existed, both test files failed at collection (`ModuleNotFoundError: aqis_lab.adapters.model_cache` / `…vosk_stt`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_7_02"`
```text
28 passed, 1695 deselected in 23.19s
```
- OpenBLAS kernel on this session's VM: `OPENBLAS_CORETYPE` unset → `COOPERLAKE`; `Prescott` → `PRESCOTT`; `Haswell` → `HASWELL` (read from libvosk's `gotoblas` table with ctypes). The planning session's VM fell back to Prescott, so the default kernel really does change between machines; the adapter pins Prescott and 1 thread (owner decision, question 6) and `test_FR_0_7_02_openblas_kernel_pinned_and_verified` reads it back as `PRESCOTT`.

### FR-0.7-04 — Harness VAD adapter (WebRTC VAD mode 2, 20 ms; owner decision, question 1)
- Code: `aqis_lab/adapters/harness_vad.py` (CAP-HVAD-001 to -003). No file under `vad_adapters/` changed.
- Tests: `tests/aqis_lab/test_aqis_harness_vad.py` (`test_FR_0_7_04_*`; expected segments computed with `webrtcvad` directly on six real smoke clips: clean speech, noisy mix, noise, music, TTS, digital silence).
- Tests first: the file failed at collection before `harness_vad.py` existed (`ModuleNotFoundError`).
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "FR_0_7_04"`
```text
13 passed, 1710 deselected in 0.95s
```
- Fast suite after both adapters: `1691 passed, 32 deselected in 202.21s`.

### FR-0.7-05 — Real-speed feeder (and DEBT-017)
- Code: `aqis_lab/realspeed.py` (CAP-RSPEED-001 to -003).
- Tests: `tests/aqis_lab/test_aqis_realspeed.py` (`test_FR_0_7_05_*`): the harness VAD as a fast real adapter, a 30 ms-per-frame test adapter for lateness, the real Vosk model for latencies (`network`), and the WP-0.6 Oracle cores test double for pinning (the test reads every thread's `Cpus_allowed_list` of the running feeder process; the child runs a second Python thread so more than the main thread is checked).
- Tests first: the file failed at collection before `realspeed.py` existed (`ModuleNotFoundError`). The first run of the pinning test showed one thread only (`{19471: {3}}`); the test now starts a second thread in the child so "every thread" is really exercised.
- Command: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k FR_0_7_05`
```text
7 passed, 1723 deselected in 23.51s
```
