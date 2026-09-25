# Harness regression baseline

This file records how the existing VAD harness tests run and what they return. Failures are recorded here and **not fixed**: the harness is protected, and fixing it is outside WP-0.0. The regression check (`python -m tools.harness.regression_check`, CI job `harness-regression`) compares every CI run with the **provisioned baseline (round 2)** below. The round 1 baseline is kept unchanged as history.

## Provisioned baseline (round 2)

Recorded by WP-0.0 round 2 (FR-0.0-11 amended) on 2026-09-25 in the environment built by `aqis_lab/deploy/harness_provision.sh` (FR-0.0-12) on the cloud VM.

- Commit tested: `d6b23646601d53046757229c85b7fc2f6c61d361` (branch `claude/hopeful-noether-yinc4e`; the harness tree is identical to `origin/main`)
- Summary: **22 tests: 21 passed, 1 failed, 0 errors, 0 skipped** (no import or collection errors, AT-0.0-06). The outcomes are identical to the round 1 baseline.

### Command
Run from the repository root:

```bash
bash aqis_lab/deploy/harness_provision.sh          # system packages, .venv-harness, corpus, weights (PASS table)
git status --porcelain --ignored > /tmp/before.txt
PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m pytest tests/regression -rA \
    -p no:cacheprovider --junitxml="${TMPDIR:-/tmp}/harness_junit.xml"
git status --porcelain --ignored > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt && echo "GIT STATUS (incl. ignored) IDENTICAL"
.venv-harness/bin/python -m tools.harness.regression_check --junit "${TMPDIR:-/tmp}/harness_junit.xml"
```

Read-only proof: `git status --porcelain --ignored` was identical before and after the test run (`GIT STATUS (incl. ignored) IDENTICAL`).

### Environment
- Platform: cloud VM, Ubuntu 24.04.4 LTS, `Linux-6.18.44-fc-v37-x86_64-with-glibc2.39`
- Python: `3.13.12 (main, Feb  4 2026, 09:25:39) [GCC 13.3.0]` in `.venv-harness` (major.minor from `docs/environment/colab_probe.txt`)
- uv: `0.8.17`
- System packages: `git-lfs 3.4.1-1ubuntu0.4`, `libc++1 1:18.0-59~exp2`, `libopus0 1.4-1build1`, `libsndfile1 1.2.2-1ubuntu5.24.04.1`
- Installed by provisioning:
  - `scripts/run_phase.py install all` (the harness's own command).
  - `requirements/aqis_lab/harness-extras.txt`, hash-checked: pytest, pytest-asyncio, opuslib.
  - `requirements/aqis_lab/harness-vcs.txt`: TEN VAD at commit `22a3bcd4…`, verified.
  - torch is not installed (decision R2-3).
- Data:
  - The corpus comes from git at commit `14796262a824` (sha256 `ef4d5da1…`, 229 clips as links under `corpus/audio/`).
  - The FireRedVAD Stream-VAD weights come from `huggingface.co/FireRedTeam/FireRedVAD` at `7990aac`, linked at `pretrained_models/FireRedVAD/Stream-VAD`.

#### Installed packages (`uv pip freeze`)
```text
aioice==0.10.2
aiortc==1.15.0
anyio==4.15.1
argon2-cffi==25.1.0
argon2-cffi-bindings==26.1.0
arrow==1.4.0
asttokens==3.0.2
async-lru==2.3.0
attrs==26.1.0
av==17.1.0
babel==2.18.0
beautifulsoup4==4.15.0
bleach==6.4.0
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
comm==0.2.3
contourpy==1.4.0
cryptography==50.0.1
cycler==0.12.1
debugpy==1.8.22
defusedxml==0.7.1
dnspython==2.8.0
executing==2.2.1
fastjsonschema==2.22.2
fireredvad==0.0.2
fonttools==4.66.0
fqdn==1.5.1
google-crc32c==1.9.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
ifaddr==0.2.0
iniconfig==2.3.0
ipykernel==7.3.0
ipython==9.17.1
ipython-pygments-lexers==1.1.1
ipywidgets==8.1.9
isoduration==20.11.0
jedi==0.20.0
jinja2==3.1.6
json5==0.15.0
jsonpointer==3.1.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
jupyter==1.1.1
jupyter-builder==1.2.3
jupyter-client==8.10.0
jupyter-console==6.6.3
jupyter-core==5.9.1
jupyter-events==0.12.1
jupyter-lsp==2.3.1
jupyter-server==2.21.1
jupyter-server-terminals==0.5.4
jupyterlab==4.6.4
jupyterlab-pygments==0.3.0
jupyterlab-server==2.28.1
jupyterlab-widgets==3.0.17
kaldi-native-fbank==1.22.3
kaldiio==2.18.1
kiwisolver==1.5.1
lark==1.3.1
markupsafe==3.0.3
matplotlib==3.11.2
matplotlib-inline==0.2.2
mistune==3.3.4
nbclient==0.11.0
nbconvert==7.17.1
nbformat==5.11.1
nest-asyncio2==1.7.3
notebook==7.6.3
notebook-shim==0.2.4
numpy==2.5.3
opuslib==3.0.1
packaging==26.3
pandas==3.0.6
pandocfilters==1.5.1
parso==0.8.7
pexpect==4.9.0
pillow==12.3.0
pip==26.2.1
platformdirs==4.11.13
pluggy==1.6.0
prometheus-client==0.26.0
prompt-toolkit==3.0.53
psutil==7.2.2
ptyprocess==0.7.0
pure-eval==0.2.4
pycparser==3.0
pyee==14.0.0
pygments==2.21.0
pylibsrtp==1.0.0
pyopenssl==26.4.0
pyparsing==3.3.3
pytest==9.1.1
pytest-asyncio==1.4.0
python-dateutil==2.9.0.post0
python-json-logger==4.2.0
pyyaml==6.0.3
pyzmq==27.2.0
referencing==0.37.0
requests==2.34.2
rfc3339-validator==0.1.4
rfc3986-validator==0.1.1
rfc3987-syntax==1.1.0
rpds-py==2026.6.3
scipy==1.18.1
send2trash==2.1.0
six==1.17.0
soundfile==0.14.0
soupsieve==2.10
stack-data==0.6.3
ten-vad @ git+https://github.com/TEN-framework/ten-vad.git@22a3bcd4509d0faaa8eef4881e8af5f39c178950
terminado==0.18.1
textgrid==1.6.1
tinycss2==1.5.1
tornado==6.5.10
traitlets==5.16.1
typing-extensions==4.16.0
tzdata==2026.4
uri-template==1.3.0
urllib3==2.8.0
wcwidth==0.9.1
webcolors==25.10.0
webencodings==0.6.1
webrtcvad-wheels==2.0.14
websocket-client==1.9.2
websockets==17.1
widgetsnbextension==4.0.16
```

### Results
| Test | Outcome | Seconds |
| --- | --- | --- |
| `tests/regression/test_accept_no_whitespace.py::test_session_accept_contains_no_whitespace_text_nodes` | passed | 0.005 |
| `tests/regression/test_conformance_coroutine.py::test_conformance_check_validates_coroutine_handler` | passed | 0.001 |
| `tests/regression/test_decoder_fails_loudly.py::test_missing_opuslib_fails_loudly` | passed | 0.001 |
| `tests/regression/test_decoder_fails_loudly.py::test_corrupt_packet_decodes_to_silence_and_diagnostic` | passed | 0.007 |
| `tests/regression/test_hangover_cutoff.py::test_early_speech_cutoff_reports_negative_hangover` | passed | 0.001 |
| `tests/regression/test_hangover_cutoff.py::test_early_trigger_reports_negative_onset_latency` | passed | 0.001 |
| `tests/regression/test_iq_replies.py::test_jingle_action_stanzas_are_acknowledged` | passed | 0.002 |
| `tests/regression/test_jitter_window.py::test_jitter_buffer_flushes_after_window_timeout` | passed | 0.001 |
| `tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge` | failed | 3.005 |
| `tests/regression/test_loss_timeline.py::test_packet_loss_inserts_concealment_and_preserves_offsets` | passed | 0.001 |
| `tests/regression/test_marker_gating.py::test_low_confidence_marker_is_gated` | passed | 0.087 |
| `tests/regression/test_results_integrity.py::test_results_store_persists_tier_and_clip_failures` | passed | 0.005 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_unwraps_past_65535` | passed | 0.000 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_handles_reordered_packets` | passed | 0.000 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_reset` | passed | 0.000 |
| `tests/regression/test_session_identity.py::test_session_identity_protected_from_p2p_overwrites` | passed | 0.001 |
| `tests/regression/test_stateful_chunking.py::test_stateful_chunking_preserves_ten_vad_audio` | passed | 0.004 |
| `tests/regression/test_tier2_alignment.py::test_tier2_realignment_recovers_ground_truth_accuracy` | passed | 0.014 |
| `tests/regression/test_translator_sdp_direction.py::test_translator_handles_direction_before_mid_and_source_ssrc` | passed | 0.001 |
| `tests/regression/test_undefined_metrics.py::test_silence_only_clip_returns_none_for_precision_recall_f1` | passed | 0.000 |
| `tests/regression/test_undefined_metrics.py::test_empty_adapter_evaluation_returns_none` | passed | 0.000 |
| `tests/regression/test_undefined_metrics.py::test_correlation_engine_handles_silence_clips_without_type_error` | passed | 0.001 |

### Failures (recorded, not fixed)
#### `tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge`
The same deterministic, offline failure as in round 1: `TimeoutError: Clip 'packet_loss_sample_01.wav' did not complete within 3.0s` (`bots/listener_bot.py:508`), raised as `ListenerBridgeExecutionError` (`webrtc_bridge/listener_bridge.py:333`). Provisioning (opuslib, libopus0, the corpus) does not change it.

## History (round 1)

Recorded by WP-0.0 (FR-0.0-11) on 2026-09-25, before any AQIS lab file existed on the branch. It records how the existing VAD harness tests run and what they return. Failures are recorded here and **not fixed** (the harness is protected; fixing it is outside WP-0.0).

- Commit tested: `a631db7c0e42711d244c1e87c458455cd0501c08` (branch `claude/hopeful-noether-yinc4e`, identical harness tree to `origin/main` `475890d`)
- Summary: **22 tests: 21 passed, 1 failed, 0 errors, 0 skipped** (1 warning). Reproduced 4 times with the same result.

### How the harness tests run (findings)
- The only pytest suite is `tests/regression/` (16 files, 22 test functions). The repository has no pytest configuration (`pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`) and no `conftest.py`.
- The tests import harness packages (`webrtc_bridge`, `bots`, `latency`, ...) from the repository root, so they must be run as `python -m pytest` from the root (plain `pytest` does not put the root on `sys.path`).
- `pytest` and `pytest-asyncio` (two tests use `@pytest.mark.asyncio`) are not listed in any `requirements/*.txt`; they have to be added to the environment.
- Dependencies come from `requirements/base.txt`, `requirements/corpus.txt` and `requirements/tier2.txt` (unpinned `>=` ranges). `requirements/tier1.txt` is not needed by these tests and was not installed (its `ten-vad` entry is fetched from `github.com`, which this environment blocks). `requirements/report.txt` is not imported by the tests.
- No network or external service is used: the tests use `ws://mock` URLs, in-process fakes and `tmp_path`.
- `tests/smoke_test_tier1/` is **not a pytest suite** and was **not run**: it is an orchestrator run config and manifest with absolute `/workspaces/voice-bot-vad-harness/...` paths, and running it writes into the tracked file `tests/smoke_test_tier1/results/raw_evaluations.jsonl`, so it cannot run read-only (owner decision 3, `docs/progress/WP-0.0/PLAN.md`).

### Command
Run from the repository root. `HARNESS_VENV` is any directory outside the repository.

```bash
HARNESS_VENV="${TMPDIR:-/tmp}/aqis-harness-venv"
uv venv --python 3.13 "$HARNESS_VENV"
uv pip install --python "$HARNESS_VENV/bin/python" \
    -r requirements/base.txt -r requirements/corpus.txt -r requirements/tier2.txt \
    pytest pytest-asyncio
git status --porcelain --ignored > /tmp/before.txt
PYTHONDONTWRITEBYTECODE=1 "$HARNESS_VENV/bin/python" -m pytest tests/regression -rA \
    -p no:cacheprovider --junitxml="${TMPDIR:-/tmp}/harness_junit.xml"
git status --porcelain --ignored > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt && echo "GIT STATUS (incl. ignored) IDENTICAL"
```

To compare like with like later, install the exact versions in "Installed packages" below instead of the unpinned requirement files.

Read-only proof: `git status --porcelain --ignored` was empty before and after the run (`GIT STATUS (incl. ignored) IDENTICAL`). `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` stop pytest writing `__pycache__` or `.pytest_cache`.

### Environment
- Platform: cloud VM, Ubuntu 24.04.4 LTS, `Linux-6.18.44-fc-v37-x86_64-with-glibc2.39`
- Python: `3.13.12 (main, Feb  4 2026, 09:25:39) [GCC 13.3.0]` (`/usr/bin/python3.13`; major.minor matches `docs/environment/colab_probe.txt`)
- uv: `0.8.17`
- System libraries: `libopus0 1.4-1build1`, `libsndfile1 1.2.2-1ubuntu5.24.04.1`
- Test tools: `pytest==9.1.1`, `pytest-asyncio==1.4.0`

#### Installed packages (`uv pip freeze`)
```text
aioice==0.10.2
aiortc==1.15.0
anyio==4.15.1
argon2-cffi==25.1.0
argon2-cffi-bindings==26.1.0
arrow==1.4.0
asttokens==3.0.2
async-lru==2.3.0
attrs==26.1.0
av==17.1.0
babel==2.18.0
beautifulsoup4==4.15.0
bleach==6.4.0
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
comm==0.2.3
cryptography==50.0.1
debugpy==1.8.22
defusedxml==0.7.1
dnspython==2.8.0
executing==2.2.1
fastjsonschema==2.22.2
fqdn==1.5.1
google-crc32c==1.9.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
ifaddr==0.2.0
iniconfig==2.3.0
ipykernel==7.3.0
ipython==9.17.1
ipython-pygments-lexers==1.1.1
ipywidgets==8.1.9
isoduration==20.11.0
jedi==0.20.0
jinja2==3.1.6
json5==0.15.0
jsonpointer==3.1.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
jupyter==1.1.1
jupyter-builder==1.2.3
jupyter-client==8.10.0
jupyter-console==6.6.3
jupyter-core==5.9.1
jupyter-events==0.12.1
jupyter-lsp==2.3.1
jupyter-server==2.21.1
jupyter-server-terminals==0.5.4
jupyterlab==4.6.4
jupyterlab-pygments==0.3.0
jupyterlab-server==2.28.1
jupyterlab-widgets==3.0.17
lark==1.3.1
markupsafe==3.0.3
matplotlib-inline==0.2.2
mistune==3.3.4
nbclient==0.11.0
nbconvert==7.17.1
nbformat==5.11.1
nest-asyncio2==1.7.3
notebook==7.6.3
notebook-shim==0.2.4
numpy==2.5.3
opuslib==3.0.1
packaging==26.3
pandocfilters==1.5.1
parso==0.8.7
pexpect==4.9.0
platformdirs==4.11.13
pluggy==1.6.0
prometheus-client==0.26.0
prompt-toolkit==3.0.53
psutil==7.2.2
ptyprocess==0.7.0
pure-eval==0.2.4
pycparser==3.0
pyee==14.0.0
pygments==2.21.0
pylibsrtp==1.0.0
pyopenssl==26.4.0
pytest==9.1.1
pytest-asyncio==1.4.0
python-dateutil==2.9.0.post0
python-json-logger==4.2.0
pyyaml==6.0.3
pyzmq==27.2.0
referencing==0.37.0
requests==2.34.2
rfc3339-validator==0.1.4
rfc3986-validator==0.1.1
rfc3987-syntax==1.1.0
rpds-py==2026.6.3
scipy==1.18.1
send2trash==2.1.0
six==1.17.0
soundfile==0.14.0
soupsieve==2.10
stack-data==0.6.3
terminado==0.18.1
tinycss2==1.5.1
tornado==6.5.10
traitlets==5.16.1
typing-extensions==4.16.0
tzdata==2026.4
uri-template==1.3.0
urllib3==2.8.0
wcwidth==0.9.1
webcolors==25.10.0
webencodings==0.6.1
websocket-client==1.9.2
websockets==17.1
widgetsnbextension==4.0.16
```

### Results
| Test | Outcome | Seconds |
| --- | --- | --- |
| `tests/regression/test_accept_no_whitespace.py::test_session_accept_contains_no_whitespace_text_nodes` | passed | 0.002 |
| `tests/regression/test_conformance_coroutine.py::test_conformance_check_validates_coroutine_handler` | passed | 0.001 |
| `tests/regression/test_decoder_fails_loudly.py::test_missing_opuslib_fails_loudly` | passed | 0.000 |
| `tests/regression/test_decoder_fails_loudly.py::test_corrupt_packet_decodes_to_silence_and_diagnostic` | passed | 0.203 |
| `tests/regression/test_hangover_cutoff.py::test_early_speech_cutoff_reports_negative_hangover` | passed | 0.001 |
| `tests/regression/test_hangover_cutoff.py::test_early_trigger_reports_negative_onset_latency` | passed | 0.001 |
| `tests/regression/test_iq_replies.py::test_jingle_action_stanzas_are_acknowledged` | passed | 0.002 |
| `tests/regression/test_jitter_window.py::test_jitter_buffer_flushes_after_window_timeout` | passed | 0.001 |
| `tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge` | failed | 3.004 |
| `tests/regression/test_loss_timeline.py::test_packet_loss_inserts_concealment_and_preserves_offsets` | passed | 0.001 |
| `tests/regression/test_marker_gating.py::test_low_confidence_marker_is_gated` | passed | 0.047 |
| `tests/regression/test_results_integrity.py::test_results_store_persists_tier_and_clip_failures` | passed | 0.007 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_unwraps_past_65535` | passed | 0.000 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_handles_reordered_packets` | passed | 0.000 |
| `tests/regression/test_sequence_unwrapper.py::test_rtp_sequence_reset` | passed | 0.000 |
| `tests/regression/test_session_identity.py::test_session_identity_protected_from_p2p_overwrites` | passed | 0.001 |
| `tests/regression/test_stateful_chunking.py::test_stateful_chunking_preserves_ten_vad_audio` | passed | 0.004 |
| `tests/regression/test_tier2_alignment.py::test_tier2_realignment_recovers_ground_truth_accuracy` | passed | 0.011 |
| `tests/regression/test_translator_sdp_direction.py::test_translator_handles_direction_before_mid_and_source_ssrc` | passed | 0.001 |
| `tests/regression/test_undefined_metrics.py::test_silence_only_clip_returns_none_for_precision_recall_f1` | passed | 0.001 |
| `tests/regression/test_undefined_metrics.py::test_empty_adapter_evaluation_returns_none` | passed | 0.000 |
| `tests/regression/test_undefined_metrics.py::test_correlation_engine_handles_silence_clips_without_type_error` | passed | 0.001 |

### Failures (recorded, not fixed)
#### `tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge` — failed
Deterministic (4 of 4 runs), offline (in-process fake media session, no sockets).
```text
E           TimeoutError: Clip 'packet_loss_sample_01.wav' did not complete within 3.0s
bots/listener_bot.py:508: TimeoutError
E           webrtc_bridge.listener_bridge.ListenerBridgeExecutionError: Failed to capture stream for clip 'packet_loss_sample_01.wav': Clip 'packet_loss_sample_01.wav' did not complete within 3.0s
webrtc_bridge/listener_bridge.py:333: ListenerBridgeExecutionError
```

### Warnings
```text
tests/regression/test_decoder_fails_loudly.py::test_corrupt_packet_decodes_to_silence_and_diagnostic
  .../site-packages/opuslib/api/decoder.py:73: SyntaxWarning: "is not" with 'int' literal. Did you mean "!="?
    if result_code.value is not 0:
```
