"""FR-0.2-04: the validator API — one exception naming every failing field by JSON Pointer, strict JSON."""
import copy
import json

import pytest

from aqis_contracts_testutil import (EVENT_FIELDS, EVENT_TYPES, FIXTURES, SCHEMA_DIR, first_event, pointers, rehash,
                                     valid_events, valid_manifest, valid_run_card)
from aqis_lab.contracts import validate as V
from aqis_lab.contracts.validate import (ContractValidationError, parse_json, validate_event, validate_event_lines,
                                         validate_manifest, validate_run_card)

VALIDATORS = {"event": validate_event, "run_card": validate_run_card, "manifest": validate_manifest}


def test_FR_0_2_04_error_names_every_failing_pointer():
    event = first_event("final")
    event["seq"] = -1
    event["component"] = "asr"
    del event["host_id"]
    event["payload"]["words"][1]["end_s"] = "late"
    with pytest.raises(ContractValidationError) as info:
        validate_event(event)
    exc = info.value
    expected = ("/component", "/host_id", "/payload/words/1/end_s", "/seq")
    assert exc.pointers == expected
    assert isinstance(exc, ValueError) and exc.kind == "event"
    assert [e.pointer for e in exc.errors] == sorted(e.pointer for e in exc.errors)
    text = str(exc)
    assert text.startswith("event log record is invalid (4 problems):")
    for p in expected:
        assert f"\n  {p}: " in text


def test_FR_0_2_04_pointer_escapes_tilde_and_slash():
    event = first_event("run_started")
    event["a/b~c"] = 1
    event["payload"]["x/y"] = 2
    assert pointers(validate_event, event) == {"/a~1b~0c", "/payload/x~1y"}
    card = valid_run_card()
    card["model"]["settings"]["t~/"] = float("nan")   # open object: only the value is wrong; the ID check is
    assert pointers(validate_run_card, card) == {"/model/settings/t~0~1"}   # skipped for a card JSON cannot hold


def test_FR_0_2_04_missing_field_pointer_names_the_field():
    card = valid_run_card()
    del card["pack"]["sha256"]
    assert pointers(validate_run_card, rehash(card)) == {"/pack/sha256"}
    manifest = valid_manifest()
    del manifest["clips"][2]["licence"]
    assert pointers(validate_manifest, manifest) == {"/clips/2/licence"}
    event = first_event("final")
    del event["payload"]["words"][0]["word"]
    assert pointers(validate_event, event) == {"/payload/words/0/word"}


def test_FR_0_2_04_rejects_nan_infinity_and_overflow():
    for literal in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ContractValidationError) as info:
            parse_json('{"a": %s}' % literal, "event")
        assert info.value.pointers == ("",) and literal in str(info.value)
    overflow = parse_json(json.dumps(first_event("final")).replace('"audio_time_s": 2.3', '"audio_time_s": 1e400'),
                          "event")
    assert overflow["audio_time_s"] == float("inf")
    assert pointers(validate_event, overflow) == {"/audio_time_s"}
    for value in (float("nan"), float("inf"), float("-inf")):
        event = first_event("speech_end")
        event["audio_time_s"] = value
        assert pointers(validate_event, event) == {"/audio_time_s"}
        manifest = valid_manifest()
        manifest["clips"][2]["recipe"]["snr_db"] = value
        assert pointers(validate_manifest, manifest) == {"/clips/2/recipe/snr_db"}


def test_FR_0_2_04_rejects_duplicate_keys():
    for text, key in (('{"a": 1, "a": 2}', "a"), ('{"p": {"x": 1, "y": 2, "x": 3}}', "x")):
        with pytest.raises(ContractValidationError) as info:
            parse_json(text, "manifest")
        assert info.value.pointers == ("",) and f"duplicate key {key!r}" in str(info.value)


def test_FR_0_2_04_rejects_integer_written_as_float():
    base = json.dumps(first_event("final"))
    assert '"seq": 8,' in base
    for written in ("8.0", "8e0", "8E0", "0.8e1"):
        event = parse_json(base.replace('"seq": 8,', f'"seq": {written},'), "event")
        assert pointers(validate_event, event) == {"/seq"}, written
    card = valid_run_card()
    card["seed"] = float(card["seed"])
    assert pointers(validate_run_card, rehash(card)) == {"/seed"}
    manifest = valid_manifest()
    manifest["clips"][4]["channels"] = 2.0
    manifest["archives"][1]["bytes"] = 1024000.0
    assert pointers(validate_manifest, manifest) == {"/clips/4/channels", "/archives/1/bytes"}


def _patterns(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern":
                out.append(value)
            else:
                _patterns(value, out)
    elif isinstance(node, list):
        for value in node:
            _patterns(value, out)
    return out


def test_FR_0_2_04_patterns_reject_trailing_newline_and_non_ascii_digits():
    for name in ("event_log.v1.json", "run_card.v1.json", "pack_manifest.v1.json"):
        found = _patterns(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")), [])
        assert found, name
        for pattern in found:
            assert pattern.startswith("^") and pattern.endswith("$(?!\\n)"), (name, pattern)
            assert "\\d" not in pattern and "\\w" not in pattern, (name, pattern)
    # behaviour on one ID field per contract
    event = first_event("final")
    for bad in ("ls-test-clean-0001\n", "clip-١"):
        assert pointers(validate_event, dict(event, clip_id=bad)) == {"/clip_id"}
    card = valid_run_card()
    card["git"]["commit"] += "\n"
    assert pointers(validate_run_card, rehash(card)) == {"/git/commit"}
    manifest = valid_manifest()
    manifest["archives"][0]["sha256"] += "\n"
    assert pointers(validate_manifest, manifest) == {"/archives/0/sha256"}


@pytest.mark.parametrize("bad", [(1, 2), {1, 2}, b"x", object()], ids=["tuple", "set", "bytes", "object"])
def test_FR_0_2_04_non_json_python_values_rejected(bad):
    card = valid_run_card()
    card["model"]["settings"]["x"] = bad
    assert pointers(validate_run_card, card) == {"/model/settings/x"}
    card = valid_run_card()
    card["model"]["settings"][3] = "non-string key"
    assert pointers(validate_run_card, card) == {"/model/settings/3"}


@pytest.mark.parametrize("kind", sorted(VALIDATORS))
def test_FR_0_2_04_non_object_record_rejected(kind):
    for bad in ([], "text", None, 5, [valid_run_card()]):
        with pytest.raises(ContractValidationError) as info:
            VALIDATORS[kind](bad)
        assert info.value.pointers == ("",) and "must be a JSON object" in str(info.value)


def test_FR_0_2_04_rule_errors_explain_the_rule():
    manifest = valid_manifest()
    manifest["clips"][3]["consent_ref"] = None
    with pytest.raises(ContractValidationError) as info:
        validate_manifest(manifest)
    assert "Rule: owner and campaign recordings need a consent reference" in str(info.value)
    card = valid_run_card()
    card["pack"] = None
    with pytest.raises(ContractValidationError) as info:
        validate_run_card(rehash(card))
    assert "Rule: pack may be null only when mode is human_session" in str(info.value)
    for event_type, change, rule in (("final", {"clip_id": None}, "Rule: this event type belongs to a clip"),
                                     ("run_started", {"clip_id": "c"}, "Rule: run_started and run_finished are run-level"),
                                     ("final", {"audio_time_s": None}, "Rule: a null audio_time_s needs audio_time_reason"),
                                     ("final", {"audio_time_reason": "x"}, "Rule: audio_time_reason is only for a null")):
        with pytest.raises(ContractValidationError) as info:
            validate_event(dict(first_event(event_type), **change))
        assert rule in str(info.value), (event_type, change)


def _event_mutations():
    records = [copy.deepcopy(e) for e in valid_events()]
    for event_type in EVENT_TYPES:
        for field in EVENT_FIELDS:
            event = first_event(event_type)
            del event[field]
            records.append(event)
        for field, bad in (("clip_id", None), ("clip_id", "c1"), ("audio_time_s", None), ("payload", {"z": 1}),
                           ("payload", {}), ("seq", 1.0), ("wall_clock_utc", "2026-02-30T00:00:00Z")):
            event = first_event(event_type)
            event[field] = bad
            records.append(event)
    for line in (FIXTURES / "invalid_events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def test_FR_0_2_04_dispatch_matches_full_schema_on_all_fixtures():
    full, per_type = V._event_validators()
    assert set(per_type) == set(EVENT_TYPES)
    records = _event_mutations()
    assert len(records) > 250
    compared = 0
    for record in records:
        event_type = record.get("event_type")
        if not isinstance(event_type, str) or event_type not in per_type:
            continue
        fast = sorted(set(V._schema_errors(per_type[event_type], record)))
        slow = sorted(set(V._schema_errors(full, record)))
        assert fast == slow, record
        compared += 1
    assert compared > 200


def _line(event, **changes):
    return json.dumps(dict(event, **changes))


def test_FR_0_2_04_seq_counts_from_zero_per_run():
    e = first_event("final")
    lines = [_line(e, run_id="a", seq=0), _line(e, run_id="b", seq=0), _line(e, run_id="a", seq=1),
             _line(e, run_id="b", seq=1), _line(e, run_id="a", seq=2)]
    reports = validate_event_lines(("\n".join(lines) + "\n").encode())
    assert [r.errors for r in reports] == [()] * 5                # interleaved runs, each counting from 0
    cases = [
        ([0, 2, 3], [set(), {"/seq"}, set()]),                     # gap: reported once, counting continues
        ([0, 1, 1, 2], [set(), set(), {"/seq"}, set()]),           # repeat
        ([1, 2], [{"/seq"}, set()]),                               # does not start at 0
        ([0, 2, 1], [set(), {"/seq"}, {"/seq"}]),                  # backwards after a gap
    ]
    for seqs, expected in cases:
        data = ("\n".join(_line(e, run_id="r", seq=s) for s in seqs) + "\n").encode()
        got = [{err.pointer for err in r.errors} for r in validate_event_lines(data)]
        assert got == expected, seqs
    # a record invalid for another reason still takes its place in its run's count
    data = ("\n".join([_line(e, run_id="r", seq=0), _line(e, run_id="r", seq=1, component="asr"),
                       _line(e, run_id="r", seq=2)]) + "\n").encode()
    assert [{err.pointer for err in r.errors} for r in validate_event_lines(data)] == [set(), {"/component"}, set()]
    # without a usable run_id or seq a record is not counted
    data = ("\n".join([_line(e, run_id="r", seq=0), _line(e, run_id=5, seq=1), _line(e, run_id="r", seq="1"),
                       _line(e, run_id="r", seq=1)]) + "\n").encode()
    assert [{err.pointer for err in r.errors} for r in validate_event_lines(data)] == \
        [set(), {"/run_id"}, {"/seq"}, set()]
    message = [err.message for r in validate_event_lines(b"%s\n" % _line(e, run_id="r", seq=3).encode())
               for err in r.errors][0]
    assert "expected 0" in message and "'r'" in message


def test_FR_0_2_04_worker_pool_report_identical_to_single_process():
    valid = (FIXTURES / "valid_events.jsonl").read_bytes().splitlines()
    invalid = (FIXTURES / "invalid_events.jsonl").read_bytes().splitlines()
    lines = []
    while len(lines) < V.POOL_MIN_RECORDS + 1500:
        lines += valid + invalid
    data = b"\n".join(lines) + b"\n"
    assert V.uses_worker_pool(len(lines), 3) and not V.uses_worker_pool(len(lines), 1)
    assert not V.uses_worker_pool(V.POOL_MIN_RECORDS - 1, 3)
    single = validate_event_lines(data, workers=1)
    pooled = validate_event_lines(data, workers=3)
    assert len(single) == len(lines)
    assert pooled == single
    assert sum(1 for r in single if r.errors) > len(lines) // 2
    with pytest.raises(ValueError):
        validate_event_lines(data, workers=0)
