# Event log contract, version 1.0

Schema: `aqis_lab/contracts/schemas/event_log.v1.json` (JSON Schema 2020-12, `$id` `urn:aqis-lab:contracts:event_log:1.0`). Validator: `aqis_lab.contracts.validate.validate_event`. Introduced by WP-0.2 (FR-0.2-01).

## Purpose
Every lab component reports what it does as events: a run starts, a clip starts, speech starts, a partial or final transcript appears, an error happens. One event log holds the events of one or more runs. Scores, timings and traces in later work packages are computed from these records, so every record names its run, its run card, its clip and its time.

## File format
- JSON Lines: one JSON object per line, UTF-8, lines separated by `\n` (a `\r` before it is accepted), a final newline after the last record. A blank line is an invalid record.
- Strict JSON: no `NaN`, `Infinity` or duplicate keys; numbers must be finite.
- Integers (`seq`, `wall_time_ns`) are written without a fraction or exponent: `5`, never `5.0` or `5e0`.
- Every object is closed: a field that is not listed below is an error. Payloads are closed too.

## Fields
Paths are JSON Pointers from the record root; `*` means any array item.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/schema_version` | string, `"1.0"` | yes | Contract version, `<major>.<minor>`. |
| `/run_id` | string without whitespace | yes | Identifier of one execution of a run card. |
| `/run_card_id` | 64 lowercase hex characters | yes | `run_card_id` of the run card the run executes (see RUN_CARD.md). |
| `/seq` | integer ≥ 0 | yes | Per-run counter: 0 for the first event of a run, then +1 for each next event of that run, in file order. |
| `/component` | one of `vad`, `turn_end`, `live_stt`, `heavy_stt`, `emotion`, `filler`, `analyzer`, `fix`, `runner` | yes | Part of the system that emitted the event. |
| `/event_type` | one of `run_started`, `run_finished`, `clip_started`, `clip_finished`, `speech_start`, `speech_end`, `partial`, `final`, `timing_mark`, `error` | yes | Kind of event; selects the payload sub-schema below. |
| `/clip_id` | lowercase letters, digits and hyphens, or null | yes | Clip the event belongs to; null only for run-level events (rules below). |
| `/audio_time_s` | number ≥ 0, or null | yes | Position in the clip's audio in seconds. Null when there is no audio position; then `audio_time_reason` says why. |
| `/audio_time_reason` | non-empty string | only when `audio_time_s` is null | Why the event has no audio position. Not allowed when `audio_time_s` is a number. |
| `/wall_time_ns` | integer ≥ 0 | yes | Monotonic clock reading in nanoseconds (for durations within one process). |
| `/wall_clock_utc` | `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, fraction 1 to 9 digits, a real date and time | yes | Wall-clock time in UTC. |
| `/host_id` | non-empty string | yes | Machine that emitted the event. |
| `/payload` | object | yes | Event-type specific data; its fields are listed per event type below. |

## Payloads
Each event type has its own payload sub-schema. A payload with no fields is the empty object `{}`.

### Payload: `run_started`
No fields. The envelope carries the run and run card IDs.

### Payload: `run_finished`
| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/payload/status` | `completed` or `failed` | yes | How the run ended. |

### Payload: `clip_started`
No fields.

### Payload: `clip_finished`
No fields.

### Payload: `speech_start`
No fields. The boundary time is `audio_time_s`.

### Payload: `speech_end`
No fields. The boundary time is `audio_time_s`.

### Payload: `partial`
| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/payload/text` | string (may be empty) | yes | Interim transcript text. |

### Payload: `final`
| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/payload/text` | string (may be empty) | yes | Final transcript text. |
| `/payload/words` | array of word objects | no | Word timings, in order. |
| `/payload/words/*/word` | non-empty string | yes (in each word) | The word as recognised. |
| `/payload/words/*/start_s` | number ≥ 0 | yes (in each word) | Word start in the clip's audio, seconds. |
| `/payload/words/*/end_s` | number ≥ 0, not before `start_s` | yes (in each word) | Word end in the clip's audio, seconds. |

### Payload: `timing_mark`
| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/payload/mark` | lowercase letters, digits and hyphens | yes | What is marked, such as `first-partial`. |

### Payload: `error`
| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/payload/code` | non-empty string | yes | Stable machine-readable error code. |
| `/payload/message` | non-empty string | yes | Human-readable explanation. |
| `/payload/run_continues` | boolean | yes | True when the run goes on after this error. |

## Rules across fields
- `clip_id` must be null for `run_started` and `run_finished` (run-level events). It must name a clip for `clip_started`, `clip_finished`, `speech_start`, `speech_end`, `partial` and `final`. For `timing_mark` and `error` it may be either: null marks a run-level event.
- `audio_time_reason` is present exactly when `audio_time_s` is null.
- In a `final` payload, each word's `end_s` is not before its `start_s` (checked by the validator; JSON Schema cannot compare two fields).
- In a JSON Lines file, `seq` runs 0, 1, 2, … for each `run_id`, in file order, with no gap or repeat (checked by `contracts validate` and `validate_event_lines`, not by the single-record validator). A resumed run continues its counter.
- `wall_time_ns` is not compared across records: a monotonic clock belongs to one process on one host.

## Example
```json
{"schema_version": "1.0", "run_id": "run-0001", "run_card_id": "92544853e82e677dba6ae51e8a53d57b2527d96f7d8b7e4158b0d28e2db7c243", "seq": 8, "component": "live_stt", "event_type": "final", "clip_id": "ls-test-clean-0001", "audio_time_s": 2.3, "wall_time_ns": 7000, "wall_clock_utc": "2026-09-27T10:00:02.5Z", "host_id": "cloud-vm-1", "payload": {"text": "hello world", "words": [{"word": "hello", "start_s": 0.42, "end_s": 0.95}, {"word": "world", "start_s": 1.02, "end_s": 1.9}]}}
```
More examples, valid and invalid: `tests/aqis_lab/fixtures/contracts/valid_events.jsonl`, `invalid_events.jsonl`.

## Validating
- Python: `validate_event(record)` returns `None` or raises `ContractValidationError`, whose `.errors` lists every failing field as `(pointer, message)` (RFC 6901 pointers; a missing field is reported at its own pointer; `''` is the whole record). `validate_event_lines(data, workers=1)` checks a whole JSON Lines file given as bytes and returns one report per line, including the `seq` order.
- Command line: `python -m aqis_lab contracts validate <file> --kind event [--workers N]` prints `line <n>: OK` or one `line <n>: INVALID <pointer>: <message>` per failing field, then a summary. Exit code 0 when every record is valid, 1 when any record is invalid or the file has no records, 2 on a usage error or an unreadable file. Files of at least 5,000 records are split over worker processes (default: the CPUs the process may use; `--workers 1` keeps everything in one process); the report is the same either way.

## Versioning and change policy
- The version is `<major>.<minor>` in each record's `schema_version` and in the schema's `$id`, `urn:aqis-lab:contracts:event_log:1.0`. The schema file name carries the major version: `event_log.v1.json`.
- **Minor version**: additions that every existing valid record survives: a new optional field, a new event type, a new enum value, or members defined inside a previously open object. The v1 file always describes the newest v1 minor version and accepts every v1 minor version up to it. A validator rejects a record with a newer minor version than its own, with a message saying to update aqis_lab, because it cannot judge fields it does not know.
- **Major version**: anything else: a removed or renamed field, a changed type or meaning, a field that becomes required, a removed enum value. A new major version gets a new file (`event_log.v2.json`); the old file stays so that old records still validate. A validator rejects an unknown major version, naming the major versions it knows.
- The contract document, the schema, the fixtures and the tests change in the same commit. A test (FR-0.2-07) keeps the fields in this document and in the schema identical.
