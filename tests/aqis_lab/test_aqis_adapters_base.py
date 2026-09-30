"""FR-0.7-01: the adapter contract. Every adapter declares its component, model and settings, writes events valid
under event log v1, and on failure writes an `error` event and raises.

The adapters themselves are exercised with real models and real clips in test_aqis_vosk.py, test_aqis_harness_vad.py
and test_aqis_parakeet.py; this file covers the base class, the event sink and the failure guard.
"""
import json
import re
import socket
import time

import numpy as np
import pytest

from aqis_lab import platform as lp
from aqis_lab.adapters import base
from aqis_lab.contracts.validate import ContractValidationError, load_schema, validate_event, validate_event_lines

CARD_ID = "a" * 64
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


class ListeningAdapter(base.Adapter):
    """A small concrete adapter for the base-class tests: it reports one final per clip, or fails on request."""
    name = "listening-test"
    component = "live_stt"

    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.opened = False

    def model_block(self):
        return {"family": "test", "name": "listening-test", "version": "1", "checksum": None, "settings": {}}

    def open(self):
        self.opened = True

    def process_clip(self, clip_id, samples, sink):
        if self.fail_with is not None:
            raise self.fail_with
        sink.emit(self.component, "final", clip_id, len(samples) / 16000, {"text": "ok"})
        return {"text": "ok"}


def new_sink(seq_start=0):
    return base.EventSink(run_id="run-test", run_card_id=CARD_ID, host_id="cloud-vm:test", seq_start=seq_start)


def test_FR_0_7_01_sink_stamps_every_envelope_field_and_validates():
    sink = new_sink()
    before = time.monotonic_ns()
    sink.emit("runner", "run_started", None, None, {}, audio_time_reason="run-level event")
    sink.emit("vad", "speech_start", "clip-1", 0.25, {})
    sink.emit("live_stt", "final", "clip-1", 1.5, {"text": "hi", "words": [{"word": "hi", "start_s": 0.3,
                                                                            "end_s": 0.6}]})
    after = time.monotonic_ns()
    records = [json.loads(line) for line in sink.data().splitlines()]
    assert [r["seq"] for r in records] == [0, 1, 2] and sink.count == 3 and sink.next_seq == 3
    schema_fields = set(load_schema("event")["required"])
    for r in records:
        assert schema_fields <= set(r)
        assert r["run_id"] == "run-test" and r["run_card_id"] == CARD_ID and r["host_id"] == "cloud-vm:test"
        assert before <= r["wall_time_ns"] <= after and UTC_RE.match(r["wall_clock_utc"])
        validate_event(r)
    assert records[0]["audio_time_s"] is None and records[0]["audio_time_reason"] == "run-level event"
    assert records[1]["audio_time_s"] == 0.25 and "audio_time_reason" not in records[1]
    assert all(r.valid for r in validate_event_lines(sink.data()))
    # canonical JSON lines: sorted keys, no spaces, one per line
    for line in sink.data().splitlines():
        assert line == json.dumps(json.loads(line), sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")


def test_FR_0_7_01_sink_continues_seq_from_start():
    sink = new_sink(seq_start=41)
    sink.emit("vad", "speech_end", "clip-9", 2.0, {})
    assert json.loads(sink.data())["seq"] == 41 and sink.next_seq == 42


@pytest.mark.parametrize("bad", [
    dict(component="live_stt", event_type="partial", clip_id=None, audio_time_s=0.5, payload={"text": "x"}),
    dict(component="live_stt", event_type="final", clip_id="clip-1", audio_time_s=-1.0, payload={"text": "x"}),
    dict(component="speaker", event_type="final", clip_id="clip-1", audio_time_s=1.0, payload={"text": "x"}),
    dict(component="vad", event_type="speech_start", clip_id="clip-1", audio_time_s=1.0, payload={"extra": 1}),
    dict(component="live_stt", event_type="final", clip_id="clip-1", audio_time_s=1.0,
         payload={"text": "x", "words": [{"word": "x", "start_s": 0.9, "end_s": 0.2}]}),
])
def test_FR_0_7_01_sink_refuses_invalid_event(bad):
    sink = new_sink()
    sink.emit("vad", "speech_start", "clip-1", 0.1, {})
    with pytest.raises(ContractValidationError):
        sink.emit(**bad)
    assert sink.count == 1 and sink.next_seq == 1 and len(sink.data().splitlines()) == 1


def test_FR_0_7_01_sink_refuses_audio_time_without_reason_rules():
    sink = new_sink()
    with pytest.raises(ContractValidationError):
        sink.emit("runner", "run_started", None, None, {})          # null audio time needs a reason
    with pytest.raises(ContractValidationError):
        sink.emit("vad", "speech_start", "clip-1", 0.5, {}, audio_time_reason="not allowed with a time")
    assert sink.count == 0


def test_FR_0_7_01_adapter_failure_emits_error_event_and_raises():
    sink = new_sink()
    adapter = ListeningAdapter(fail_with=ValueError("decoder stopped"))
    samples = np.zeros(16000, dtype=np.int16)
    with pytest.raises(base.AdapterError) as info:
        base.guarded(adapter, sink, "clip-7", "clip", adapter.process_clip, "clip-7", samples, sink)
    assert isinstance(info.value.__cause__, ValueError)
    assert info.value.code == "listening-test-clip-failed"
    records = [json.loads(line) for line in sink.data().splitlines()]
    assert len(records) == 1
    error = records[0]
    validate_event(error)
    assert error["event_type"] == "error" and error["component"] == "live_stt" and error["clip_id"] == "clip-7"
    assert error["payload"] == {"code": "listening-test-clip-failed", "message": "ValueError: decoder stopped",
                                "run_continues": False}
    assert error["audio_time_s"] is None and error["audio_time_reason"]


def test_FR_0_7_01_error_code_of_an_adapter_error_is_kept():
    sink = new_sink()
    adapter = ListeningAdapter()
    failure = base.AdapterError("vosk-model-checksum", "model file am/final.mdl changed")

    def fail():
        raise failure

    with pytest.raises(base.AdapterError) as info:
        base.guarded(adapter, sink, None, "open", fail)
    assert info.value.code == "vosk-model-checksum"
    error = json.loads(sink.data())
    assert error["clip_id"] is None and error["payload"]["code"] == "vosk-model-checksum"
    assert error["payload"]["message"] == "model file am/final.mdl changed"


def test_FR_0_7_01_guarded_success_writes_no_error():
    sink = new_sink()
    adapter = ListeningAdapter()
    out = base.guarded(adapter, sink, "clip-1", "clip", adapter.process_clip, "clip-1",
                       np.zeros(8000, dtype=np.int16), sink)
    assert out == {"text": "ok"} and [json.loads(l)["event_type"] for l in sink.data().splitlines()] == ["final"]


def test_FR_0_7_01_components_are_event_log_components():
    assert set(base.COMPONENTS) == set(load_schema("event")["properties"]["component"]["enum"])


def test_FR_0_7_01_model_block_must_fit_the_run_card():
    adapter = ListeningAdapter()
    base.check_model_block(adapter.model_block())
    with pytest.raises(base.AdapterError):
        base.check_model_block({"family": "test", "name": "x", "version": None, "checksum": None, "settings": {}})


def test_FR_0_7_01_host_id_names_platform_and_host():
    host = lp.host_name()
    assert host == socket.gethostname() and host
    assert base.host_id() == f"{lp.detect_platform(lp.SystemView.real()).platform}:{host}"
