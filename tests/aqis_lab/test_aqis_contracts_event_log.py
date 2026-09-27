"""FR-0.2-01: event log v1 — envelope, event types, payload sub-schemas and their rules."""
import json

import pytest
from jsonschema import Draft202012Validator

from aqis_contracts_testutil import (CLIP_TYPES, COMPONENTS, EITHER_LEVEL_TYPES, EVENT_FIELDS, EVENT_TYPES, FIXTURES,
                                     PAYLOAD_REQUIRED, RUN_LEVEL_TYPES, SCHEMA_DIR, WORD_FIELDS, first_event,
                                     get_path, pointer, pointers, valid_events)
from aqis_lab.contracts.validate import validate_event, validate_event_lines

SCHEMA_FILE = SCHEMA_DIR / "event_log.v1.json"


def test_FR_0_2_01_schema_is_valid_draft_2020_12():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    assert sorted(schema["required"]) == sorted(EVENT_FIELDS)
    assert sorted(schema["properties"]["component"]["enum"]) == sorted(COMPONENTS)
    assert sorted(schema["properties"]["event_type"]["enum"]) == sorted(EVENT_TYPES)


def test_FR_0_2_01_valid_fixture_covers_every_event_type():
    events = valid_events()
    assert {e["event_type"] for e in events} == set(EVENT_TYPES)
    assert {e["component"] for e in events} == set(COMPONENTS)
    kinds = {(e["event_type"], e["clip_id"] is None) for e in events}
    for event_type in EITHER_LEVEL_TYPES:
        assert (event_type, True) in kinds and (event_type, False) in kinds, event_type
    assert any(e["audio_time_s"] is None for e in events) and any(e["audio_time_s"] is not None for e in events)
    finals = [e for e in events if e["event_type"] == "final"]
    assert any("words" in e["payload"] for e in finals) and any("words" not in e["payload"] for e in finals)
    assert {e["payload"]["run_continues"] for e in events if e["event_type"] == "error"} == {True, False}
    assert {e["payload"]["status"] for e in events if e["event_type"] == "run_finished"} == {"completed", "failed"}


def test_FR_0_2_01_valid_fixture_passes():
    for number, event in enumerate(valid_events(), start=1):
        assert pointers(validate_event, event) == set(), f"valid_events.jsonl line {number}"


@pytest.mark.parametrize("event_type", EVENT_TYPES)
@pytest.mark.parametrize("field", EVENT_FIELDS)
def test_FR_0_2_01_rejects_missing_required_field(event_type, field):
    event = first_event(event_type)
    del event[field]
    assert pointers(validate_event, event) == {pointer(field)}


@pytest.mark.parametrize("event_type,field", [(t, f) for t, fields in PAYLOAD_REQUIRED.items() for f in fields])
def test_FR_0_2_01_rejects_missing_required_payload_field(event_type, field):
    event = first_event(event_type)
    del event["payload"][field]
    assert pointers(validate_event, event) == {pointer("payload", field)}


@pytest.mark.parametrize("field", WORD_FIELDS)
def test_FR_0_2_01_rejects_missing_required_word_field(field):
    event = first_event("final")
    del event["payload"]["words"][1][field]
    assert pointers(validate_event, event) == {pointer("payload", "words", 1, field)}


WRONG_VALUES = [
    ("final", ("run_id",), [5, "", "run 1", "run-1\n", None]),
    ("final", ("run_card_id",), [5, "A" * 64, "a" * 63, "a" * 65, "g" * 64, "a" * 64 + "\n", None]),
    ("final", ("seq",), ["1", 1.5, 1.0, -1, True, None]),
    ("final", ("component",), ["asr", "VAD", "", None, 1]),
    ("final", ("event_type",), ["Final", "started", "", None, 1]),
    ("final", ("clip_id",), ["Clip-1", "clip_1", "", 3, "clip-1\n", "clip-١٢", True]),
    ("final", ("audio_time_s",), [-0.001, "0", True]),
    ("final", ("wall_time_ns",), [-1, 1.0, "1", None, True]),
    ("final", ("wall_clock_utc",), ["2026-09-27T10:00:00", "2026-09-27T10:00:00z", "2026-09-27 10:00:00Z",
                                    "2026-09-27T10:00:00+00:00", "2026-13-01T00:00:00Z", "2026-02-29T00:00:00Z",
                                    "2026-09-27T10:60:00Z", "2026-09-27T10:00:60Z", "2026-09-27T10:00:00.Z",
                                    "2026-09-27T10:00:00.1234567890Z", "2026-09-27T10:00:00Z\n",
                                    "٢026-09-27T10:00:00Z", 20260927, None]),
    ("final", ("host_id",), ["", 1, None]),
    ("final", ("payload",), [[], "x", None]),
    ("final", ("payload", "text"), [1, None, ["a"]]),
    ("final", ("payload", "words"), [{}, "x", None]),
    ("final", ("payload", "words", 0, "word"), ["", 1, None]),
    ("final", ("payload", "words", 0, "start_s"), [-1, "0", None]),
    ("final", ("payload", "words", 0, "end_s"), [-1, "1", None]),
    ("partial", ("payload", "text"), [None, 1]),
    ("error", ("payload", "code"), ["", 1, None]),
    ("error", ("payload", "message"), ["", 1, None]),
    ("error", ("payload", "run_continues"), ["yes", 1, 0, None]),
    ("timing_mark", ("payload", "mark"), ["First-Partial", "first_partial", "first partial", "", 1, None]),
    ("run_finished", ("payload", "status"), ["done", "COMPLETED", "", None, True]),
]


@pytest.mark.parametrize("event_type,path,bad", [(t, p, v) for t, p, values in WRONG_VALUES for v in values])
def test_FR_0_2_01_rejects_wrong_type_or_enum(event_type, path, bad):
    event = first_event(event_type)
    parent, key = get_path(event, path)
    parent[key] = bad
    assert pointers(validate_event, event) == {pointer(*path)}


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_FR_0_2_01_clip_id_null_only_for_run_level_events(event_type):
    as_null, as_id = first_event(event_type), first_event(event_type)
    as_null["clip_id"] = None
    as_id["clip_id"] = "ls-test-clean-0001"
    null_ok = event_type in RUN_LEVEL_TYPES | EITHER_LEVEL_TYPES
    id_ok = event_type in CLIP_TYPES | EITHER_LEVEL_TYPES
    assert pointers(validate_event, as_null) == (set() if null_ok else {"/clip_id"})
    assert pointers(validate_event, as_id) == (set() if id_ok else {"/clip_id"})


def test_FR_0_2_01_null_audio_time_needs_reason():
    with_number = first_event("speech_start")
    assert isinstance(with_number["audio_time_s"], float)
    no_reason = dict(with_number, audio_time_s=None)
    assert pointers(validate_event, no_reason) == {"/audio_time_reason"}
    assert pointers(validate_event, dict(no_reason, audio_time_reason="no audio position for this event")) == set()
    assert pointers(validate_event, dict(no_reason, audio_time_reason="")) == {"/audio_time_reason"}
    assert pointers(validate_event, dict(no_reason, audio_time_reason=None)) == {"/audio_time_reason"}
    assert pointers(validate_event, dict(with_number, audio_time_reason="not needed")) == {"/audio_time_reason"}
    assert pointers(validate_event, dict(with_number, audio_time_s=0)) == set()        # integers are numbers too


def test_FR_0_2_01_final_word_timings():
    final = first_event("final")
    words = final["payload"]["words"]
    assert len(words) == 2
    without = first_event("final")
    del without["payload"]["words"]
    assert pointers(validate_event, without) == set()
    empty = first_event("final")
    empty["payload"]["words"] = []
    assert pointers(validate_event, empty) == set()
    equal = first_event("final")
    equal["payload"]["words"][0]["end_s"] = equal["payload"]["words"][0]["start_s"]
    assert pointers(validate_event, equal) == set()
    backwards = first_event("final")
    backwards["payload"]["words"][1]["end_s"] = backwards["payload"]["words"][1]["start_s"] - 0.01
    assert pointers(validate_event, backwards) == {"/payload/words/1/end_s"}
    extra = first_event("final")
    extra["payload"]["words"][0]["confidence"] = 0.9
    assert pointers(validate_event, extra) == {"/payload/words/0/confidence"}


def test_FR_0_2_01_error_payload_fields():
    for continues in (True, False):
        event = first_event("error")
        event["payload"]["run_continues"] = continues
        assert pointers(validate_event, event) == set()
    event = first_event("error")
    event["payload"] = {}
    assert pointers(validate_event, event) == {"/payload/code", "/payload/message", "/payload/run_continues"}


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_FR_0_2_01_rejects_unknown_field(event_type):
    top = first_event(event_type)
    top["extra"] = 1
    assert pointers(validate_event, top) == {"/extra"}
    inner = first_event(event_type)
    inner["payload"]["extra"] = 1
    assert pointers(validate_event, inner) == {"/payload/extra"}


def test_FR_0_2_01_invalid_fixture_names_expected_pointers():
    expected = json.loads((FIXTURES / "invalid_events.expected.json").read_text(encoding="utf-8"))
    reports = validate_event_lines((FIXTURES / "invalid_events.jsonl").read_bytes())
    assert [r.number for r in reports] == list(range(1, len(expected) + 1))
    for report in reports:
        got = sorted({err.pointer for err in report.errors})
        assert got == expected[str(report.number)], f"invalid_events.jsonl line {report.number}"
    assert sum(1 for r in reports if r.errors) >= 90
