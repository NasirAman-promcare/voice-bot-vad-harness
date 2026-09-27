"""FR-0.2-02: run card v1 — fields, enums, nullability rules and the run_card_id check."""
import copy
import json

import pytest
from jsonschema import Draft202012Validator

from aqis_contracts_testutil import (FIXTURES, MODES, PLATFORMS, RUN_CARD_FIELDS, RUN_CARD_NESTED, SCHEMA_DIR,
                                     STEP_FIELDS, get_path, pointer, pointers, rehash, valid_run_card)
from aqis_lab.contracts.validate import validate_run_card

SCHEMA_FILE = SCHEMA_DIR / "run_card.v1.json"


def test_FR_0_2_02_schema_is_valid_draft_2020_12():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    assert sorted(schema["required"]) == sorted(RUN_CARD_FIELDS)
    assert sorted(schema["properties"]["mode"]["enum"]) == sorted(MODES)


def test_FR_0_2_02_valid_fixture_passes():
    card = valid_run_card()
    assert pointers(validate_run_card, card) == set()
    variants = {
        "human session without pack": dict(card, mode="human_session", pack=None),
        "no normaliser": dict(card, normaliser=None),
        "checksum only": dict(card, model=dict(card["model"], version=None, checksum="b" * 64)),
        "both version and checksum": dict(card, model=dict(card["model"], checksum="b" * 64)),
        "gpu run": dict(card, mode="gpu_compute_delay",
                        machine=dict(card["machine"], platform="colab", gpu="Tesla T4", python_version="3.13.15")),
        "empty notes": dict(card, notes=""),
        "sha-256 git commit": dict(card, git={"commit": "c" * 64, "dirty": True}),
        "python version with suffix": dict(card, machine=dict(card["machine"], python_version="3.14.0rc1")),
    }
    for mode in MODES:
        variants[f"mode {mode}"] = dict(card, mode=mode)
    for platform in PLATFORMS:
        variants[f"platform {platform}"] = dict(card, machine=dict(card["machine"], platform=platform))
    for name, variant in variants.items():
        assert pointers(validate_run_card, rehash(copy.deepcopy(variant))) == set(), name


MISSING = [(f,) for f in RUN_CARD_FIELDS] + [(parent, f) for parent, fields in RUN_CARD_NESTED.items() for f in fields] \
    + [("processing", "vad", 1, f) for f in STEP_FIELDS] + [("processing", "stt", 0, f) for f in STEP_FIELDS]


@pytest.mark.parametrize("path", MISSING, ids=lambda p: "/".join(map(str, p)))
def test_FR_0_2_02_rejects_missing_required_field(path):
    card = valid_run_card()
    parent, key = get_path(card, path)
    del parent[key]
    if path != ("run_card_id",):
        rehash(card)
    assert pointers(validate_run_card, card) == {pointer(*path)}


WRONG_VALUES = [
    (("run_card_id",), ["A" * 64, "a" * 63, "a" * 64 + "\n", 5, None]),
    (("pack",), ["smoke", [], 5, None]),
    (("pack", "manifest_id"), ["Smoke", "smoke_v1", "", 1, None]),
    (("pack", "version"), ["1.0", "v1.0.0", "01.0.0", "1.0.0-", "1.0.0+", "1.0.0\n", "1.0.٠", 1, None]),
    (("pack", "sha256"), ["x", "A" * 64, None]),
    (("model",), [None, "vosk", []]),
    (("model", "family"), ["", 1, None]),
    (("model", "name"), ["", 1, None]),
    (("model", "version"), ["", 1]),
    (("model", "checksum"), ["abc", "A" * 64, 1]),
    (("model", "settings"), [[], "x", None]),
    (("processing",), [[], None]),
    (("processing", "vad"), [{}, "x", None]),
    (("processing", "stt", 0), ["resample", None, []]),
    (("processing", "vad", 0, "name"), ["", 1, None]),
    (("processing", "vad", 0, "params"), [[], "x", None]),
    (("mode",), ["fast", "Batch", "", None]),
    (("machine",), [None, []]),
    (("machine", "platform"), ["aws", "cloud_vm", "Colab", "", None]),
    (("machine", "gpu"), ["", 1]),
    (("machine", "cpu_model"), ["", None]),
    (("machine", "architecture"), ["", None]),
    (("machine", "os"), ["", None]),
    (("machine", "python_version"), ["3.13", "3", "python3.13.12", "3.13.12 ", "3.13.12\n", "", None]),
    (("seed",), [-1, 1.5, 20260927.0, "1", True, None]),
    (("normaliser",), ["whisper", []]),
    (("normaliser", "name"), ["", None]),
    (("normaliser", "version"), ["", None]),
    (("lock",), [None, "x"]),
    (("lock", "file"), ["/abs/phase0.txt", "../phase0.txt", "a/../b.txt", "a//b.txt", "a\\b.txt", "./a.txt", "a/.",
                        "", None]),
    (("lock", "sha256"), ["x", None]),
    (("git",), [None, "abc"]),
    (("git", "commit"), ["014b051", "A" * 40, "a" * 41, "", None]),
    (("git", "dirty"), ["false", 0, None]),
    (("created_utc",), ["2026-09-27", "2026-09-27T09:45:00+01:00", "2026-09-31T00:00:00Z", None]),
    (("notes",), [None, 5]),
]


@pytest.mark.parametrize("path,bad", [(p, v) for p, values in WRONG_VALUES for v in values],
                         ids=lambda x: repr(x)[:40])
def test_FR_0_2_02_rejects_wrong_type_or_enum(path, bad):
    card = valid_run_card()
    parent, key = get_path(card, path)
    parent[key] = bad
    if path != ("run_card_id",):
        rehash(card)
    assert pointers(validate_run_card, card) == {pointer(*path)}


def test_FR_0_2_02_model_needs_version_or_checksum():
    card = valid_run_card()
    card["model"]["version"] = None
    card["model"]["checksum"] = None
    assert pointers(validate_run_card, rehash(card)) == {"/model/version", "/model/checksum"}


def test_FR_0_2_02_pack_null_only_for_human_session():
    for mode in MODES:
        card = valid_run_card()
        card["mode"], card["pack"] = mode, None
        expected = set() if mode == "human_session" else {"/pack"}
        assert pointers(validate_run_card, rehash(card)) == expected, mode


def test_FR_0_2_02_processing_keeps_step_order_per_path():
    card = valid_run_card()
    swapped = copy.deepcopy(card)
    swapped["processing"]["vad"].reverse()
    assert swapped["processing"]["vad"] != card["processing"]["vad"]
    assert pointers(validate_run_card, rehash(swapped)) == set()
    assert swapped["run_card_id"] != card["run_card_id"]      # order is part of the card
    stale = copy.deepcopy(swapped)
    stale["run_card_id"] = card["run_card_id"]
    assert pointers(validate_run_card, stale) == {"/run_card_id"}


def test_FR_0_2_02_rejects_run_card_id_mismatch():
    card = valid_run_card()
    for field, value in (("seed", 1), ("mode", "realspeed_cpu"), ("notes", "changed")):
        changed = dict(copy.deepcopy(card), **{field: value})
        expected = set() if field == "notes" else {"/run_card_id"}   # notes are not part of the ID
        assert pointers(validate_run_card, changed) == expected, field
    expected_files = json.loads((FIXTURES / "invalid_expected.json").read_text(encoding="utf-8"))
    for name in ("invalid_run_card_id.json", "invalid_run_card_fields.json"):
        record = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert sorted(pointers(validate_run_card, record)) == expected_files[name], name


@pytest.mark.parametrize("path", [(), ("pack",), ("model",), ("processing",), ("machine",), ("normaliser",), ("lock",),
                                  ("git",), ("processing", "vad", 0)], ids=lambda p: "/".join(map(str, p)) or "root")
def test_FR_0_2_02_rejects_unknown_field(path):
    card = valid_run_card()
    target = card
    for part in path:
        target = target[part]
    target["extra"] = 1
    assert pointers(validate_run_card, rehash(card)) == {pointer(*path, "extra")}


def test_FR_0_2_02_open_objects_accept_any_members():
    card = valid_run_card()
    card["model"]["settings"] = {"beam": 5, "nested": {"list": [1, "a", None]}}
    card["processing"]["vad"][0]["params"] = {}
    assert pointers(validate_run_card, rehash(card)) == set()
