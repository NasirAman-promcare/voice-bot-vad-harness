# WP-0.2 — Contracts: event log, run card, pack manifest

- **Depends on**: WP-0.0
- **Runs on**: cloud VM
- **Read first**: AQIS Test Lab blueprint sections "Lab architecture" and "Metrics catalogue"; `docs/process/CHANGE_CONTROL.md`

## Goal
Define, document and validate the three records every later module speaks: the event log, the run card and the pack manifest.

## Deliverables
- `docs/contracts/EVENT_LOG.md`, `RUN_CARD.md`, `PACK_MANIFEST.md`
- `aqis_lab/contracts/schemas/event_log.v1.json`, `run_card.v1.json`, `pack_manifest.v1.json` (JSON Schema 2020-12)
- `aqis_lab/contracts/validate.py`, `aqis_lab/contracts/canonical.py`
- Valid and invalid example fixtures under `tests/aqis_lab/fixtures/contracts/`

## Functional requirements
- **FR-0.2-01 Event log v1.** One JSON object per line with required fields: `schema_version`, `run_id`, `run_card_id`, `seq` (per-run counter from 0), `component` (`vad`, `turn_end`, `live_stt`, `heavy_stt`, `emotion`, `filler`, `analyzer`, `fix`, `runner`), `event_type`, `clip_id` (null only for run-level events), `audio_time_s` (number ≥ 0, or null with `audio_time_reason`), `wall_time_ns` (monotonic integer), `wall_clock_utc`, `host_id`, and `payload`. Minimum event types: `run_started`, `run_finished`, `clip_started`, `clip_finished`, `speech_start`, `speech_end`, `partial`, `final`, `timing_mark`, `error`. Each event type has its own payload sub-schema; `final` carries text and optional word timings; `error` carries a code, message and whether the run continues.
- **FR-0.2-02 Run card v1.** Fields: `run_card_id`; `pack` (manifest ID, version, SHA-256); `model` (family, name, version or checksum, settings object); `processing` (ordered fix steps with parameters, per path: `vad`, `stt`, `emotion`); `mode` (`batch`, `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay`, `human_session`); `machine` (platform `cloud-vm`, `colab`, `kaggle`, `oracle`; GPU type or null; CPU model; architecture; OS; Python version); `seed`; `normaliser` (name, version); `lock` (file, SHA-256); `git` (commit, dirty flag); `created_utc`; `notes`.
- **FR-0.2-03 Pack manifest v1.** Fields: `manifest_id`, `version` (semantic version), `purpose`, `created_utc`, `clips[]` (`clip_id`, `source`, `source_ref`, `licence`, `speaker_id`, `consent_ref` required for owner and campaign recordings, `split`, `duration_s`, `sample_rate_hz`, `channels`, `sha256`, `archive`, `member_path`, `transcript` or null, `recipe` or null, `tags[]`), and `archives[]` (`name`, `sha256`, `bytes`, `n_members`).
- **FR-0.2-04 Validators.** `validate_event`, `validate_run_card` and `validate_manifest` raise a specific exception naming each failing field by JSON Pointer. `python -m aqis_lab contracts validate <file> --kind event|run_card|manifest` validates a file (events as JSON Lines) and prints a per-record report.
- **FR-0.2-05 Canonical JSON and IDs.** Deterministic serialisation (sorted keys, fixed separators, UTF-8, no NaN or Infinity). `run_card_id` is the SHA-256 of the canonical run card without `run_card_id`, `created_utc` and `notes`. A test computes the expected ID independently from this definition.
- **FR-0.2-06 Versioning.** Each schema has an `$id` carrying its version. Validators reject unknown major versions with a clear message. The contract documents describe the change policy.
- **FR-0.2-07 Documents match schemas.** A test asserts every schema field appears in its contract document and every documented field exists in the schema.

## Non-functional requirements
- **NFR-0.2-01** Validating 100,000 events takes under 10 s on the cloud VM (test marked `slow`).
- **NFR-0.2-02** Pure Python with pinned `jsonschema`.

## Acceptance commands
- **AT-0.2-01** The fast suite passes, including valid and invalid fixtures for every event type and field.
- **AT-0.2-02** `python -m aqis_lab contracts validate tests/aqis_lab/fixtures/contracts/valid_events.jsonl --kind event` exits 0; the invalid fixture exits non-zero and names the failing fields.
- **AT-0.2-03** The audit gate passes with `--wp WP-0.2`.

## Out of scope
Producing real events; adapters.

## Stop and ask if
- A field's meaning is unclear for later phases, or the blueprint and this spec disagree.
