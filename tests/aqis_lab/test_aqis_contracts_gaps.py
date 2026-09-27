"""Round-2 audit fixes WP-0.2-F01 (type rules without a test) and WP-0.2-F02 (last record without a final newline).

F01: each test puts a wrong-typed value where only the named schema "type" rule rejects it, so removing that
rule makes the test fail. F02: JSON Lines input whose last record has no final newline must still be read.
"""
import copy
import json
import subprocess
import sys

import pytest

from aqis_contracts_testutil import FIXTURES, first_event, pointers, rehash, valid_manifest, valid_run_card
from aqis_lab.contracts.validate import validate_event, validate_event_lines, validate_manifest, validate_run_card
from aqis_testutil import ROOT

NON_STRING_OR_NULL = [7, 1.5, True, [], {}, ["clip-1"]]
NON_OBJECTS = [1, 1.5, True, "hello", [], ["x"], None]


# ------------------------------------------------------------------------------------------ F01
@pytest.mark.parametrize("event_type", ["timing_mark", "error"])
@pytest.mark.parametrize("bad", NON_STRING_OR_NULL, ids=repr)
def test_FR_0_2_01_rejects_wrong_clip_id_type_on_either_level_events(event_type, bad):
    # timing_mark and error may be run-level (null) or clip-level (an ID); only the envelope's
    # type ["string", "null"] rejects anything else.
    for clip_id in (None, "ls-test-clean-0001"):
        assert pointers(validate_event, dict(first_event(event_type), clip_id=clip_id)) == set()
    assert pointers(validate_event, dict(first_event(event_type), clip_id=bad)) == {"/clip_id"}


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("bad", NON_OBJECTS, ids=repr)
def test_FR_0_2_01_rejects_non_object_word_items(index, bad):
    event = first_event("final")
    assert len(event["payload"]["words"]) == 2
    event["payload"]["words"][index] = bad
    assert pointers(validate_event, event) == {f"/payload/words/{index}"}


@pytest.mark.parametrize("bad", [b for b in NON_OBJECTS if b is not None] + ["smoke"], ids=repr)
def test_FR_0_2_02_human_session_pack_must_be_object_or_null(bad):
    card = valid_run_card()
    card["mode"] = "human_session"
    for good in (None, copy.deepcopy(card["pack"])):
        assert pointers(validate_run_card, rehash(dict(card, pack=good))) == set()
    assert pointers(validate_run_card, rehash(dict(card, pack=bad))) == {"/pack"}


@pytest.mark.parametrize("bad", NON_OBJECTS, ids=repr)
def test_FR_0_2_03_rejects_non_object_archive_items(bad):
    replaced = valid_manifest()
    replaced["archives"][0] = bad
    # the clips of that archive cannot be judged against a list with a nameless entry; only the item is reported
    assert pointers(validate_manifest, replaced) == {"/archives/0"}
    appended = valid_manifest()
    appended["archives"].append(bad)
    assert pointers(validate_manifest, appended) == {"/archives/2"}


# ------------------------------------------------------------------------------------------ F02
def _valid_lines():
    return (FIXTURES / "valid_events.jsonl").read_bytes().splitlines()


def _with_invalid_last(lines):
    last = json.loads(lines[-1])
    last["component"] = "asr"
    return lines[:-1] + [json.dumps(last).encode()]


def test_FR_0_2_04_last_record_without_final_newline_is_validated():
    lines = _valid_lines()
    count = len(lines)
    for data in (b"\n".join(lines), b"\n".join(lines) + b"\r"):
        reports = validate_event_lines(data)
        assert len(reports) == count and all(r.valid for r in reports)
    reports = validate_event_lines(b"\n".join(_with_invalid_last(lines)))
    assert len(reports) == count
    assert [r.number for r in reports if not r.valid] == [count]
    assert {e.pointer for e in reports[-1].errors} == {"/component"}
    single = json.dumps(dict(first_event("run_started"), component="asr")).encode()
    assert [{e.pointer for e in r.errors} for r in validate_event_lines(single)] == [{"/component"}]
    assert validate_event_lines(b"") == []


def _run(path, kind):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "contracts", "validate", str(path), "--kind", kind],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_FR_0_2_04_cli_last_line_without_final_newline_fails(tmp_path):
    lines = _valid_lines()
    count = len(lines)
    bad = tmp_path / "invalid_last_no_newline.jsonl"
    bad.write_bytes(b"\n".join(_with_invalid_last(lines)))
    assert not bad.read_bytes().endswith(b"\n")
    proc = _run(bad, "event")
    assert proc.returncode == 1, proc.stdout[-500:]
    out = proc.stdout.splitlines()
    assert out[-2].startswith(f"line {count}: INVALID /component: ")
    assert out[-1] == f"event: {count} records, {count - 1} valid, 1 invalid"
    good = tmp_path / "valid_no_newline.jsonl"
    good.write_bytes(b"\n".join(lines))
    proc = _run(good, "event")
    assert proc.returncode == 0 and proc.stdout.splitlines()[-1] == f"event: {count} records, {count} valid, 0 invalid"


@pytest.mark.parametrize("kind,name,code", [("run_card", "valid_run_card.json", 0),
                                            ("run_card", "invalid_run_card_id.json", 1),
                                            ("manifest", "valid_manifest.json", 0),
                                            ("manifest", "invalid_manifest_fields.json", 1)])
def test_FR_0_2_04_cli_documents_without_final_newline(tmp_path, kind, name, code):
    path = tmp_path / name
    path.write_bytes((FIXTURES / name).read_bytes().rstrip(b"\n"))
    proc = _run(path, kind)
    assert proc.returncode == code, proc.stdout
    assert proc.stdout.splitlines()[-1] == f"{kind}: 1 record, {1 - code} valid, {code} invalid"
