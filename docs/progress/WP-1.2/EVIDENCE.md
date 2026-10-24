# EVIDENCE: WP-1.2 S2 Live Stack benchmark

Environment: cloud VM (Ubuntu 24.04, x86_64), `.venv` Python 3.13.16 from `requirements/aqis_lab/phase0.txt`, uv 0.8.17, branch `s2/live-stack`, base `origin/main` at `22baec1`.

## Ruler tests were written first and failed
Tests copied onto a clean checkout of `origin/main` (no `aqis_lab/live`):
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s2_frames.py tests/aqis_lab/test_s2_vad_score.py tests/aqis_lab/test_s2_turn.py tests/aqis_lab/test_s2_emotion.py tests/aqis_lab/test_s2_data.py tests/aqis_lab/test_s2_config.py tests/aqis_lab/test_s2_pipeline.py -q -p no:cacheprovider
E   ModuleNotFoundError: No module named 'aqis_lab.live'
7 errors in 0.50s
```
(`test_s2_pipeline.py` was added after the modules existed, to cover the stage wiring; the other six files came first, in commit 62abab9.) Several expected values were corrected in the tests before the first run, from my own arithmetic slips, not from the code: UAR test accuracy 40/50, the Smart Turn "quiet" case (trigger at 2700), and the emotion balance assertion.

## Ruler tests now
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s2_*.py -q -p no:cacheprovider -m "not network"
.........................................................                [100%]
129 passed, 2 deselected in 11.68s
$ .venv/bin/python -m pytest tests/aqis_lab/test_s2_config.py -q -p no:cacheprovider -m network
2 passed, 22 deselected in 0.60s
```

## Fast suite
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
2269 passed, 57 deselected in 323.81s (0:05:23)
```
A first full run had one failure, `test_FR_0_5_01_platform_details_only_from_platform_module`: `stages.py` read the CPU model with `lscpu` and `platform.machine()`. It now uses `aqis_lab.platform.machine_block()`; the guard test is unchanged.

## Lock
`uv pip compile requirements/aqis_lab/s2-live.in -c requirements/aqis_lab/phase0.txt --universal --python-version 3.13 --generate-hashes` (uv 0.8.17) exits 0. `uv pip install --dry-run --require-hashes --only-binary :all:` with the five source builds allowed (`textgrid`; on x86_64 `antlr4-python3-runtime`, `jieba`, `oss2`, `crcmod`) resolves for `aarch64-manylinux_2_28` and `x86_64-manylinux_2_28` (test above). Nothing was installed (torch, FunASR and the models are GBs).

## Synthetic end-to-end check
`tests/aqis_lab/test_s2_pipeline.py` writes synthetic data files with known tone-burst boundaries, runs the real `run_vad` and `run_turn` (an energy VAD stands in for the model), and checks the report tables: the 300 ms timer gives FIR 8/12 and latency 300 ms, 500 ms gives 4/12 and 500 ms, 1000 ms gives 0 and 1000 ms; VAD onset lag 20 ms, offset lag 0, FAR and MDR 0; trace columns on every row; a rerun adds no rows. A scratch run also built `scorecard.md`, both plots and `s2_report.zip` (matplotlib installed outside `.venv`).

## Audit gate
