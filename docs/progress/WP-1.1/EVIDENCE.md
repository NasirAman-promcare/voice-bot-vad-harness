# EVIDENCE: WP-1.1 S1 ASR benchmark

Environment: cloud VM (Ubuntu 24.04, x86_64), `.venv` Python 3.13.16 from `requirements/aqis_lab/phase0.txt` (sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`), system libopus 1.4, branch `s1/asr-bench`, base `origin/main` at `33616e0`.

## Ruler tests were written first and failed
Before any `aqis_lab/bench` code existed:
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s1_select_clean.py tests/aqis_lab/test_s1_conditions.py tests/aqis_lab/test_s1_scoring.py tests/aqis_lab/test_s1_rows_config.py -q -p no:cacheprovider
E   ImportError: cannot import name 'config' from 'aqis_lab.bench' (unknown location)
ERROR tests/aqis_lab/test_s1_select_clean.py
ERROR tests/aqis_lab/test_s1_conditions.py
ERROR tests/aqis_lab/test_s1_scoring.py
ERROR tests/aqis_lab/test_s1_rows_config.py
4 errors in 0.24s
```

## Ruler tests now
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s1_select_clean.py tests/aqis_lab/test_s1_conditions.py tests/aqis_lab/test_s1_scoring.py tests/aqis_lab/test_s1_rows_config.py -q -p no:cacheprovider
133 passed in 4.33s
```
Brief 6.4 items 1 to 10 are covered, with expected values worked out from the definitions (hand-counted WER, entity, oracle and bootstrap examples; SNR by the definition; the seeded loss pattern recomputed in the test). Three tests first failed because of the test data and were fixed there, not in the code: "one two" normalises to "12" (Whisper's normaliser joins spelled numbers), "twenty five dollars and 3 cents" normalises to "$25.03", and a 5 kHz tone is rejected so completely that its output amplitude is exactly 0 (division by zero in the test's dB ratio).

Measured while writing them (same signals as the tests):
- Band-pass response: -6.0 dB at 300 and 3400 Hz, 0.0 dB at 1 and 3 kHz, -96.4 dB at 4 kHz. Phone tones at 1 and 3 kHz lose 0.007 dB. mu-law SQNR on a full-scale 440 Hz sine: 39.0 dB.
- Opus at the 16 kbps setting is variable bit rate and averages **14.6 kbps** on a harmonic signal with a noise floor (inside the 10% band), but only 10 to 12 kbps on a clean harmonic signal. The 8 and 24 kbps settings gave 6.5 and 24.2 kbps. Every webrtc utterance stores its packet and byte counts in `meta`, so the achieved rate is reportable.
- 2% loss over 501 packets (10 s) with seeds 21, 22 and 23: 18, 6 and 8 lost; FEC plus PLC equals the losses in every case.

## Fast suite
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
4 failed, 2116 passed, 55 deselected in 300.25s (0:05:00)
FAILED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing
FAILED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_dry_run_in_this_repository_reuses_venv
FAILED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_setup_pin_read_by_script_equals_yaml
FAILED tests/aqis_lab/test_aqis_oracle_setup.py::test_FR_0_6_01_missing_build_names_the_package
```
These 4 failed on `origin/main` before any change, because this VM has uv 0.11.32 and `oracle_setup.sh` needs 0.8.17 (`ERROR: ... reports 'uv 0.11.32' ... needs uv 0.8.17`). With uv 0.8.17 first on PATH the same file gives `15 passed, 1 failed`, the one failure being the `oracle`-marked test the fast suite deselects. CI installs uv 0.8.17.

## Two Phase 0 guard tests
The first full run failed `test_NFR_0_0_03_imports_are_stdlib_or_pinned` and `test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter`, because the bench modules import `huggingface_hub`, `soxr`, `matplotlib`, `torch`, NeMo and `qwen_asr`, which the brief requires and the phase 0 lock does not pin. They are unchanged. The bench loads those libraries through `aqis_lab.bench.lib()` (importlib), the way the Parakeet adapter does; `test_s1_runner_modules_import_no_scorer_and_no_ml_library` checks that the GPU runner imports no scorer and no ML library. The owner may prefer to extend the two tests instead.

## Locks
`uvx --from uv==0.8.17 uv pip compile requirements/aqis_lab/<name>.in -c requirements/aqis_lab/phase0.txt --python-version 3.13 --python-platform x86_64-manylinux_2_28 --generate-hashes --output-file requirements/aqis_lab/<name>.txt` for `s1-prep`, `s1-hf`, `s1-nemo`, `s1-qwen`: all exit 0. `uv pip sync --dry-run --only-binary :all:` resolves wheels for `s1-prep` and `s1-hf`; `s1-nemo` needs the source-only `antlr4-python3-runtime` and `s1-qwen` the source-only `sox`. Both build with the phase 0 lock as the build constraint (`uv pip install --require-hashes --no-deps --build-constraints requirements/aqis_lab/phase0.txt` installed `antlr4-python3-runtime==4.9.3` and `sox==1.5.0`). The torch stacks were not installed here (GBs); the Colab smoke run checks them.

## Checked on synthetic data (scratch, not committed)
`prep` (selection, cleaning, all 7 conditions), `smoke`, `pilot`, `full` and `speed` with a recording stand-in model, then `score` and `report`, ran end to end on generated sources: 40 utterances per slice, 3 models, resume skipping finished files, the smoke check flagging identical outputs, `scorecard.md`, `weakness_map.png` and `s1_report.zip` written. The dataset loaders, model wrappers and GPU stacks were not run here (no corpora or models in the cloud session). Dataset layouts, tags and entity categories were checked against the Hugging Face cards, parquet footers and the text columns only (`docs/progress/WP-1.1/PLAN.md`).

## Audit gate
```
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-1.1
```
```
aqis-audit-gate: base origin/main (merge-base 33616e0a69cf), head 6340daeec96e, approvals origin/main 33616e0a69cf, wp WP-1.1
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (1.0 s)
```

## Fixes after the first Colab runs (branch `s1/asr-bench`, from `main` at `caae9f6`)
New tests are in `tests/aqis_lab/test_s1_fixes.py`.
- **Parakeet Unified crash** (`'NoneType' object has no attribute 'get'` at `rnnt_bpe_models.py:540`): `NemoAsr` now gives the model an empty `cfg.validation_ds` when it is None (`ensure_validation_ds`, tested on a minimal config object because omegaconf comes with NeMo and is not installed here).
- **Canary-Qwen import error** (`scaled_grouped_mm`, `ScalingType` missing from torch 2.9.1): `NemoSalm` adds the two names to `torch.nn.functional` before importing `nemo.collections.speechlm2.models` (`add_torchao_symbols`, a compatibility shim; nothing is quantized). **Not verified**: it needs the Colab NeMo stack. If Canary-Qwen still does not load cleanly without recompiling C++ extensions, the brief's rule applies (drop it and record the reason here); no drop is recorded yet.
- **GPU name**: the machine block's key is `gpu`, not `gpu_type`, which caused the KeyError. `__main__` reads `gpu` (then `gpu_type`, `gpu_name`) and stops with an error when none is found, instead of writing `unknown_gpu` into result rows (every prediction row must record the GPU).
- **Earnings-22 duplicate IDs**: `segment_id` repeats across calls. IDs are now `earnings22-<row index in the split>` (the published chunk number stays in `meta`). `check_data_rows` and the source loaders now refuse repeated utterance IDs. Data prepared before this fix must be rebuilt: delete `AQIS_LAB/s1/data/numbers/` (and any `preds/*/numbers__*`) before the next prep.
- **HarperValleyBank cleaning rules**: already on `main` (`dd33022`); `\[baby\]` etc. are plain YAML scalars, so the backslash is single and the regexes work. Tests now check each tag is stripped and `[unintelligible]` and `<unk>` drop the turn.
- **Notebook**: cell 4 streams each action's output live (`Popen`, `PYTHONUNBUFFERED=1`, `PYTHONPATH`, `MPLBACKEND=Agg`); cell 5 frees the runtime only when setup worked and every action exited 0.

## Smoke run on Colab, 19 Oct 2026 (L4, notebook cloned at tag `s1-colab-1` = `caae9f6`, before the fixes above)
- whisper-large-v3, whisper-large-v3-turbo and parakeet-tdt-0.6b-v2 loaded (40, 19 and 53 s) and ran. parakeet-unified-0.6b hit the `validation_ds` crash and canary-qwen-2.5b the `ScalingType` import error: both are the failures fixed above, and the traceback line numbers are those of the old code. The tag still has to be moved to the fixed commit before a rerun can show whether the fixes work.
- **Wrong audio for some `numbers` utterances.** The three `numbers` clips printed references that no model matched: all three models gave the same text for clips 1 and 2 (different references) and a third text for clip 3, none of which is in the references. Cause: the same duplicate-ID bug as above. `prep` keyed the cut audio by utterance ID, so chunks sharing `earnings22-<segment_id>` took the audio of the last chunk with that ID. The `numbers` data and the `numbers__*` predictions made from it are not usable. Rebuild them: delete `AQIS_LAB/s1/data/numbers/` and `AQIS_LAB/s1/preds/*/numbers__*`, rerun `prep`, then the smoke stage. The other slices have unique IDs by construction (row index, speaker and sequence, registry clip ID) and the loaders now fail on a repeated ID.
- The smoke check missed it because only two of the three outputs matched. It now fails when any two clips with different references get the same output, prints a WARNING when a clean clip's output shares under a third of its reference words, and also prints REF and HYP for cells it skips (so the first smoke run's other slices can be read too). `test_s1_smoke_check.py`.
- granite-speech-4.1-2b printed nothing after its skipped cells before the notebook was interrupted, so the cause is unknown: its load (a download of several GB) may simply have been slow. The notebook's filter hides download progress. `run` now prints a "loading revision ..." line before each load.

## Smoke run on Colab, second run (19 Oct 2026, 18:13, notebook at the moved tag `s1-colab-1` = `e3502e2`)
- **parakeet-unified-0.6b**: loaded in 47 s and wrote us_conv, sa_conv, sa_india and medical cells: the `validation_ds` fix works.
- **Every model stopped at `numbers`**: `data/numbers/clean.parquet is missing`. That is expected after deleting the corrupt `numbers` data: run `prep` (CPU runtime) before smoke. Nothing is wrong in the runner; it stops before loading a model when a prepared file is missing.
- **canary-qwen-2.5b**: the two-name shim got past `ScalingType` and `scaled_grouped_mm` and then failed on `SwizzleType` (`torchao/prototype/mx_formats/mx_tensor.py`). Cause: `nemo-automodel` pulled torchao 0.18.0 into `s1-nemo.txt`, built for torch 2.11, while NeMo 3.0.0 pins torch 2.9.1, and transformers 5.20.1 imports torchao only when it is 0.15.0 or newer (`TORCHAO_MIN_VERSION`). Fix (the changed approach, not a third shim): `s1-nemo.in` now pins `torchao<0.15`, so the lock resolves torchao 0.14.1 (built for torch 2.9, a wheel exists for Python 3.13), transformers skips the torchao import, and no other pin moved. Checked here only by reading transformers 5.20.1 and torchao 0.14.1 source and recompiling the lock; **not verified on Colab**. If Canary-Qwen still fails after this, drop it and record the reason here, as the brief says.
