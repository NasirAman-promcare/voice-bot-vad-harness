# WP-0.7 — First adapters and the smoke run

- **Depends on**: WP-0.3, WP-0.5, WP-0.6
- **Runs on**: cloud VM; the owner runs Colab and Oracle checks
- **Read first**: AQIS Test Lab blueprint sections "VAD and end-of-turn test plan" and "Live transcription test plan"; the event log and run card contracts

## Goal
Run three real components on the smoke pack end to end and prove identical results across machines: Vosk on CPU, Parakeet Unified on GPU, and one existing harness VAD.

## Deliverables
- `aqis_lab/adapters/base.py`, `vosk_stt.py`, `parakeet_unified.py`, `harness_vad.py`
- `aqis_lab/realspeed.py` (20 ms frame feeder at real time)
- `aqis_lab/parity.py`, and `python -m aqis_lab phase0 smoke --target cloud|colab|oracle`
- `requirements/aqis_lab/phase0-gpu.in` and `.txt`
- `docs/adapters/VOSK.md`, `PARAKEET_UNIFIED.md`, `HARNESS_VAD.md`, `docs/runs/PHASE0_SMOKE.md`

## Functional requirements
- **FR-0.7-01** Adapter contract: each adapter declares its component, model name and version, and settings; emits events valid under event log v1; and on failure emits an `error` event and raises.
- **FR-0.7-02** Vosk adapter: model `vosk-model-small-en-us-0.15`, downloaded to a cache and verified by checksum; emits `partial` and `final` events with word times where Vosk provides them.
- **FR-0.7-03** Parakeet Unified adapter: offline mode on GPU through NeMo, pinned in `phase0-gpu.txt`. Without a GPU or NeMo it raises a clear platform error; it is never silently skipped or replaced.
- **FR-0.7-04** Harness VAD adapter: imports one existing harness VAD (the owner names which in the approval) without modifying harness files, and emits `speech_start` and `speech_end` events.
- **FR-0.7-05** Real-speed feeder: feeds 20 ms frames at real time to CPU adapters and records audio time and wall time on every event; reports first-partial and finalisation latency.
- **FR-0.7-06** GPU compute-delay run: for Parakeet, measures per-clip processing time on Colab for 5 clips and records the GPU type.
- **FR-0.7-07** `phase0 smoke` creates run cards; runs Vosk in batch on all 60 clips; scores speech clips with the WP-0.3 scorer; runs the harness VAD on all clips; runs real-speed Vosk on 5 clips; on a GPU target, runs Parakeet; and writes results plus `PHASE0_SMOKE.md`, every number traceable.
- **FR-0.7-08** Parity: `python -m aqis_lab parity <results-A> <results-B>` compares transcript hashes and WER per clip and in total, and lists every difference. Vosk batch results must be identical across cloud VM, Colab (CPU) and Oracle.

## Non-functional requirements
- **NFR-0.7-01** The cloud VM smoke run finishes within 15 minutes on CPU.

## Acceptance commands
- **AT-0.7-01** `python -m aqis_lab phase0 smoke --target cloud` completes; results validate against the contracts; `trace` works on any row.
- **AT-0.7-02** The fast and slow CPU suites pass; the audit gate passes with `--wp WP-0.7`.

## Owner-run checks
- **OC-0.7-01** Colab on a T4 runtime: run the launcher with `phase0 smoke --target colab`; commit the result bundle.
- **OC-0.7-02** Oracle: `phase0 smoke --target oracle`; commit the result bundle.
- **OC-0.7-03** Claude then runs `parity` across the three bundles in a session; any difference goes to the owner.

## Owner needs
- Cloud environment allowlist includes `alphacephei.com`. Which harness VAD to wrap.

## Stop and ask if
- A model download host is blocked; results differ across platforms (report every difference, never hide one); NeMo cannot be pinned for the Colab Python version.

## Must-catch behaviours
1. Every adapter event validates against event log v1.
2. An adapter failure emits an `error` event and raises.
3. The Parakeet adapter refuses to run without a GPU and is never silently skipped.
4. The Vosk model is rejected when its checksum differs.
5. The real-speed feeder cannot run faster than real time.
6. `parity` reports every per-clip difference.
