"""The adapter contract: what every model adapter declares, how it reports events, and how it fails (FR-0.7-01).

CAPABILITIES:
  CAP-ADAPT-001: Adapter and StreamingAdapter declare the component (an event-log v1 component), the run-card v1 `model` block (family, name, version, checksum, settings) and the steps preflight, open, process_clip (and start_clip, feed, finish_clip for streaming) and close; check_model_block() validates a model block against the run-card v1 `model` schema and its version-or-checksum rule [tests: test_FR_0_7_01_components_are_event_log_components, test_FR_0_7_01_model_block_must_fit_the_run_card]
  CAP-ADAPT-002: EventSink stamps every envelope field (run_id, run_card_id, seq counted from seq_start, component, clip_id, audio time or its reason, monotonic wall_time_ns, UTC wall_clock_utc, host_id), validates each record against event log v1 before keeping it (an invalid record raises and nothing is kept) and returns the records as canonical JSON lines [tests: test_FR_0_7_01_sink_stamps_every_envelope_field_and_validates, test_FR_0_7_01_sink_continues_seq_from_start, test_FR_0_7_01_sink_refuses_invalid_event, test_FR_0_7_01_sink_refuses_audio_time_without_reason_rules]
  CAP-ADAPT-003: guarded() runs one adapter step; any failure becomes one `error` event (code, message, run_continues false) followed by an AdapterError raised from the cause; an AdapterError keeps its own code [tests: test_FR_0_7_01_adapter_failure_emits_error_event_and_raises, test_FR_0_7_01_error_code_of_an_adapter_error_is_kept, test_FR_0_7_01_guarded_success_writes_no_error]
  CAP-ADAPT-004: host_id() is "<platform>:<host name>", both from aqis_lab.platform [tests: test_FR_0_7_01_host_id_names_platform_and_host]
INPUTS AND OUTPUTS: adapter steps and event fields in; validated event records (canonical JSON lines) out;
  AdapterError, AdapterPlatformError or ContractValidationError on failure.
CONTRACTS: event-log v1 (docs/contracts/EVENT_LOG.md); run-card v1 `model` block (docs/contracts/RUN_CARD.md).
INVARIANTS:
  - No event is kept unless it validates against event log v1.
  - A failed step always leaves exactly one `error` event and always raises; nothing is skipped or replaced.
  - wall_time_ns comes from the monotonic clock; wall_clock_utc is UTC with Z.
NOT IN SCOPE:
  - Writing events to files and numbering runs (aqis_lab/runner/); models (the adapter modules).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-01 created.
"""
import abc
import functools
import time
from datetime import datetime, timezone

import jsonschema

from aqis_lab import platform as lp
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.contracts.validate import load_schema, validate_event

COMPONENTS = ("vad", "turn_end", "live_stt", "heavy_stt", "emotion", "filler", "analyzer", "fix", "runner")
SAMPLE_RATE_HZ = 16000


class AdapterError(RuntimeError):
    """An adapter step failed; `code` is the stable error code written in the `error` event."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class AdapterPlatformError(AdapterError):
    """The adapter cannot run on this machine (for example no GPU); it is never skipped or replaced."""


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def host_id(system=None):
    """The event-log host_id of this machine: "<platform>:<host name>"."""
    system = system or lp.SystemView.real()
    return f"{lp.detect_platform(system).platform}:{lp.host_name()}"


@functools.lru_cache(maxsize=1)
def _model_validator():
    schema = load_schema("run_card")
    return jsonschema.Draft202012Validator({"$defs": schema["$defs"], **schema["properties"]["model"]})


def check_model_block(block):
    """AdapterError unless `block` is a valid run-card v1 `model` object."""
    errors = sorted(_model_validator().iter_errors(block), key=lambda e: list(e.absolute_path))
    if errors:
        where = "; ".join(f"/model/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors)
        raise AdapterError("model-block-invalid", f"the adapter's model block is not a run-card v1 model: {where}")
    return block


class EventSink:
    """Collects one run's events: every envelope field stamped, every record validated before it is kept."""

    def __init__(self, run_id, run_card_id, host_id, seq_start=0, clock=time.monotonic_ns):
        self.run_id, self.run_card_id, self.host_id = run_id, run_card_id, host_id
        self.next_seq = seq_start
        self.clock = clock
        self.records = []
        self._lines = []

    @property
    def count(self):
        return len(self._lines)

    def emit(self, component, event_type, clip_id, audio_time_s, payload, audio_time_reason=None):
        """Validate and keep one event; returns the record. An invalid record raises and is not kept."""
        record = {"schema_version": "1.0", "run_id": self.run_id, "run_card_id": self.run_card_id,
                  "seq": self.next_seq, "component": component, "event_type": event_type, "clip_id": clip_id,
                  "audio_time_s": audio_time_s, "wall_time_ns": self.clock(), "wall_clock_utc": utc_now(),
                  "host_id": self.host_id, "payload": dict(payload)}
        if audio_time_reason is not None:
            record["audio_time_reason"] = audio_time_reason
        validate_event(record)
        line = canonical_json(record) + b"\n"
        self.records.append(record)
        self._lines.append(line)
        self.next_seq += 1
        return record

    def data(self):
        """Every kept event as canonical JSON lines."""
        return b"".join(self._lines)


class Adapter(abc.ABC):
    """One component under test. Subclasses set `name` (stable, used in error codes) and `component`."""
    name = None
    component = None
    uses_model_cache = False        # True when the adapter takes cache_dir and system (a pinned model file)

    @abc.abstractmethod
    def model_block(self):
        """The run-card v1 `model` object: family, name, version, checksum and the settings the run uses."""

    def preflight(self):
        """Refuse early (before any run folder is written) when this machine cannot run the adapter. The base
        adapter has no machine requirement beyond the CPU lock, so it accepts every machine."""
        return None

    @abc.abstractmethod
    def open(self):
        """Load and check the model; raises on any problem (called once, before the first clip)."""

    @abc.abstractmethod
    def process_clip(self, clip_id, samples, sink):
        """Process one clip (16 kHz mono int16 samples), emit its events into `sink` and return its result fields."""

    def close(self):
        """Release what open() loaded. The base class holds nothing, so it has nothing to release."""
        return None


class StreamingAdapter(Adapter):
    """An adapter that can also take a clip frame by frame (the real-speed feeder, aqis_lab/realspeed.py)."""

    @abc.abstractmethod
    def start_clip(self, clip_id, sink):
        """Begin a clip."""

    @abc.abstractmethod
    def feed(self, frame, audio_end_s, sink):
        """Take the next frame (int16 samples); `audio_end_s` is the audio position at the frame's end."""

    @abc.abstractmethod
    def finish_clip(self, audio_end_s, sink):
        """End the clip, emit its last events and return its result fields."""


def guarded(adapter, sink, clip_id, step, action, *args):
    """Run `action(*args)` for `adapter`; on failure emit one `error` event, then raise AdapterError."""
    try:
        return action(*args)
    except Exception as exc:
        if isinstance(exc, AdapterError):
            code, message = exc.code, exc.message
        else:
            code = f"{adapter.name}-{step}-failed"
            message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        sink.emit(adapter.component, "error", clip_id, None,
                  {"code": code, "message": message, "run_continues": False},
                  audio_time_reason=f"error during the {step} step")
        if isinstance(exc, AdapterError):
            raise
        raise AdapterError(code, message) from exc
