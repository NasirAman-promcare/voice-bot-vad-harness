# Parakeet Unified adapter

NVIDIA Parakeet Unified (`nvidia/parakeet-unified-en-0.6b`) in offline mode on a CUDA GPU, through NeMo (FR-0.7-03). It also measures each clip's GPU compute delay (FR-0.7-06). The code is in `aqis_lab/adapters/parakeet_unified.py` (class `ParakeetUnifiedAdapter`, event-log component `heavy_stt`).

The runner uses it in two tasks, which run only on the Colab T4 target (`config/aqis_lab/phase0_smoke.yaml`):
- `parakeet-offline`: every clip (mode `batch`; owner decision, question 9);
- `parakeet-compute-delay`: the 5 subset clips, timed (mode `gpu_compute_delay`).

## GPU only, never skipped
Before anything is written, the runner calls the adapter's `preflight()`:
- **No GPU** (`aqis_lab.platform` finds none): error `parakeet-no-gpu`. The message says that Parakeet runs only on a CUDA GPU and is never skipped or replaced, and points to the Colab runbook.
- **No NeMo or torch installed:** error `parakeet-no-nemo`. The message names `requirements/aqis_lab/phase0-gpu.txt` and `bash aqis_lab/deploy/dev_bootstrap.sh --gpu`.

`open()` repeats those checks. It then refuses when torch sees no CUDA device (`parakeet-no-cuda`, naming the torch and CUDA versions). It never falls back to the CPU. `phase0 smoke --target colab` on a runtime without a GPU stops with `ERROR:` and exit 2, and writes nothing.

torch and NeMo are imported only inside this adapter's `open()`. A test scans the `aqis_lab` package to keep it that way.

## Model
The pin is in `config/aqis_lab/models.yaml`:

| Item | Value |
| --- | --- |
| Source | Hugging Face `nvidia/parakeet-unified-en-0.6b`, revision `fe53cd885760c96b6a5f51a0bfd362cb4584a98b` |
| File | `parakeet-unified-en-0.6b.nemo` |
| Size | 2,474,055,680 bytes |
| SHA-256 | `ec23ed9150c8fde49072c3e2d61678ab903dbcef389d658db833420cbc1da35b` |
| Licence | NVIDIA Open Model License (`https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/`) |

Size and SHA-256 are Hugging Face's own values, and the planning download matched them. On Colab the file is downloaded to local disk each session (about 2.5 GB), never kept on Drive (owner decision, question 12). The cache rules are those of `docs/adapters/VOSK.md` ("Cache"): nothing is used before its size and SHA-256 match.

The model is restored with `ASRModel.restore_from(<file>, map_location="cuda")` and put in evaluation mode. The load time is logged in the runner log.

## Transcription
- The clip's 16-bit samples are turned into float32 in memory (`int16 / 32768`) and passed to `transcribe([audio], batch_size=1)` under `torch.inference_mode()`. NeMo 3.0.0's file-path call fails for this model (PLAN.md, finding 10), and the adapter never uses it.
- Decoding is the model's default greedy RNN-T decoding.
- One `final` event is written per clip, at the clip's end, with the text.

**Compute delay (FR-0.7-06).**
1. The model is loaded once.
2. One untimed warm-up transcription of the first subset clip runs before any timing (owner decision, question 7).
3. Each clip's time is measured on the monotonic clock around the one `transcribe` call. CUDA is synchronised before the start and after the end.

Model loading is not part of any clip's time.

## Result row fields
After `clip_id`, `run_card_id`, `task` and `task_version`:

| Task | Fields |
| --- | --- |
| `parakeet-offline` | `text`, `text_sha256`, `audio_s` |
| `parakeet-compute-delay` | `text`, `text_sha256`, `audio_s`, `processing_ms`, `rtf` (processing time / audio length), `gpu` (the GPU type from `aqis_lab.platform`, for example `Tesla T4`) |

GPU arithmetic is not promised to give the same bytes on a rerun. The timing rows are measurements, so a resumed run keeps the times measured first.

## Run card
The `model` block: family `nemo`, name `nvidia/parakeet-unified-en-0.6b`, version = the revision, checksum = the file's SHA-256. Settings:

| Setting | Value |
| --- | --- |
| `mode` | `offline` |
| `decoding` | `the model's default (greedy RNN-T)` |
| `batch_size` | 1 |
| `dtype` | `float32` |
| `device` | `cuda` |
| `input` | `in-memory float32 samples (int16 / 32768)` |
| `nemo` | the `nemo-toolkit` version pinned in `phase0-gpu.txt` (3.0.0) |
| `torch` | the `torch` version pinned in `phase0-gpu.txt` (2.14.0) |

## Packages
The GPU extras are in `requirements/aqis_lab/phase0-gpu.txt`: `nemo_toolkit[asr]==3.0.0` (owner decision, question 4) and torch from PyPI, a CUDA 13 build (question 5; the Colab T4 driver is 580.82.07). The lock is compiled against the CPU lock with `-c requirements/aqis_lab/phase0.txt`, and its header names that lock's SHA-256. It changes none of the CPU pins, so Colab has the same CPU packages as the cloud VM and Oracle. `dev_bootstrap.sh --gpu` installs both locks, hash-checked. The doctor's `lock` row then names both files, and the run card records `phase0-gpu.txt`.

The model card lists Volta, Ampere, Hopper and Blackwell GPUs, not Turing. OC-0.7-01 (`docs/colab/COLAB_RUNBOOK.md`) is the first run on a T4.
