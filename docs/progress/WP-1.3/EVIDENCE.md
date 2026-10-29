# EVIDENCE: WP-1.3 S3 Cascade and Fine-Tuning

Environment: cloud VM (Ubuntu 24.04, x86_64), `.venv` Python 3.13.16 from `requirements/aqis_lab/phase0.txt`, uv 0.8.17, branch `s3/cascade-finetune`, base `origin/main` at `de85e84`.

## Ruler tests were written first and failed
Tests copied onto a clean checkout of `origin/main` (no `aqis_lab/cascade`), commit `555bd64` holds them:
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s3_*.py -q -p no:cacheprovider
ERROR tests/aqis_lab/test_s3_score.py
ERROR tests/aqis_lab/test_s3_simulate.py
!!!!!!!!!!!!!!!!!!! Interrupted: 6 errors during collection !!!!!!!!!!!!!!!!!!!!
6 errors in 0.44s
```
Three test-data slips were corrected in the tests, not in the code, after the first run: the tie-break example expected the wrong two turns (the two lowest tiebreak values are turns 2 and 1), the heavy model's errors in the simulation example sum to 5, not 6 (so the all-heavy WER is 5/80), and column positions in the report-row assertions. `test_s3_report.py` and the notebook, light-import and lock-resolution tests were added after the modules existed.

## Ruler tests now
```
$ .venv/bin/python -m pytest tests/aqis_lab/test_s3_*.py -q -p no:cacheprovider -m "not network"
108 passed, 2 deselected in 2.60s
$ .venv/bin/python -m pytest tests/aqis_lab/test_s3_config.py -q -p no:cacheprovider -m network
2 passed, 35 deselected in 0.51s
```
What they fix, with values worked out by hand: pooled WER and the mean of slice WERs; `floor(rate x turns)` escalation (29 of 100 at 0.29); the perfect-gate curve of a six-turn example (15, 10, 7 and 8 errors at 0, 1/6, 2/6 and all); GPU-second saving (1 - 1.4/2.0 = 0.3); out-of-fold scores that never come from a model that saw the row's speaker; thresholds that never split a tie; a simulation over synthetic Sprint 1 files (18 errors in 80 words for stage 1, 5 for the heavy model, perfect gate 9/80 at rate 0.25 and 4/80 at 0.5); speaker-disjoint training and validation sets; r 16 / alpha 32 LoRA settings and a target pattern that matches the text layers and not the audio tower; and the drug-recall and us_conv gates at exactly their limits.

## Fast suite
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
2384 passed, 59 deselected in 317.34s (0:05:17)
```

## Locks
`uv pip compile ... -c requirements/aqis_lab/phase0.txt --python-version 3.13 --python-platform x86_64-manylinux_2_28 --generate-hashes` (uv 0.8.17) exits 0 for `s3-cascade` and, with `-c requirements/aqis_lab/s1-qwen.txt` as well, for `s3-train` (torch 2.14.1, transformers 4.57.6, qwen-asr 0.0.6 and accelerate 1.12.0 as in Sprint 1; peft 0.21.2, bitsandbytes 0.50.2 added). `uv pip install --dry-run --require-hashes --only-binary :all:` resolves wheels for every pin of `s3-cascade`, and for `s3-train` except `sox`, which builds from source as in the Sprint 1 Qwen lock. Nothing was installed (torch and the models are GBs).

## Synthetic end-to-end checks
`test_s3_simulate.py` runs the real `simulate.run` over generated Sprint 1 data and prediction files (scored by the Sprint 1 scorer), `test_s3_report.py` the real fine-tuning and prompt scorecards over generated prediction files. A scratch run with matplotlib installed outside `.venv` also built `tradeoff.png`, `scorecard.md`, `decision_inputs.md` and `s3_report.zip` from them.

## Audit gate
```
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-1.3
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (1.0 s)
```

## Follow-up: token confidences without running out of GPU memory (branch `s3/confidence-memory`)
Tests first: `tests/aqis_lab/test_s3_confidence.py` (commit before the fix, `7 failed` against the merged code: no `configure`, `confidences_for_cell`, `cell_done`, `require_coverage`, and no `confidence.batch_size`). The fakes stand in for NeMo, torch and omegaconf; the real NeMo run is the owner's Colab run, whose log gave the evidence for the fix (OOM after the first file, alignment warning, decoding set up per batch).
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network" -p no:cacheprovider
2391 passed, 59 deselected in 361.63s (0:06:01)
$ .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-1.3
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.7 s)
```

## Closeout: the four Colab fixes on main (29 Oct 2026)
Tests first: `tests/aqis_lab/test_s3_closeout.py`, committed before the fixes; against the merged code 9 of its 11 tests failed (the 2 that passed pin behaviour that must not change: evaluated speakers are still left out whole when enough others remain, and too few speakers overall is still an error).
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network"
2402 passed, 59 deselected in 442.85s (0:07:22)
$ .venv/bin/python -m tools.audit.gate --base origin/main
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.7 s)
```
The ten existing S3 test files were not edited. The two existing tests that touch the changed functions (`test_s3_split_with_too_few_speakers_for_a_validation_set_is_an_error`, `test_s3_decoding_keeps_confidences_but_not_alignments`) still pass unchanged.
Not checked here: the real NeMo, Qwen3-ASR/PEFT and Eka runs, which happened on Colab. WP-1.3 status: complete, with the gate outcomes stated in `PLAN.md`.

## Follow-up: word-less stage 1 turns and DECISION.md corrections (30 Oct 2026)
Tests first: `tests/aqis_lab/test_s3_zero_tokens.py` (committed before the fix; 4 of 5 failed against the merged code, the fifth, that nothing imputed is written to the feature file, already held). They check that only word-less turns are filled, that the confidence policies become available with the count in `policies.json`, that the filled turn is escalated first with hand-worked errors (22 - 9 - 4 = 9 of 80 words at a 25% rate), and that a turn with words and no confidence still makes the policy unavailable. The ten existing S3 test files were not edited.
```
$ .venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network"
2407 passed, 59 deselected in 538.66s (0:08:58)
$ .venv/bin/python -m tools.audit.gate --base origin/main
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 0
Findings: 0
0 findings: OK (0.8 s)
```
`docs/results/S3/DECISION.md`: each added figure was read from the committed files (oracle difference -3.73 points, CI -4.10 to -3.36; `channel` against stage 1 -0.76, CI -0.97 to -0.57; medical-phone WER 9.96% to 11.52%; 11 of 12 biased cells "too close to call"; GPU saving 0.536535 rounds to 53.7%). Not checked here: the rerun itself (it needs the Sprint 1 files on Drive and the `confidence` features), so the cascade section stays marked as open in the decision.
