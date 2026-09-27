"""FR-0.2-03: pack manifest v1 — manifest, clip and archive fields, consent rule and checks across clips."""
import copy
import json

import pytest
from jsonschema import Draft202012Validator

from aqis_contracts_testutil import (ARCHIVE_FIELDS, CLIP_FIELDS, FIXTURES, MANIFEST_FIELDS, SCHEMA_DIR, get_path,
                                     pointer, pointers, valid_manifest)
from aqis_lab.contracts.validate import validate_manifest

SCHEMA_FILE = SCHEMA_DIR / "pack_manifest.v1.json"


def clip_index(manifest, source):
    return next(i for i, c in enumerate(manifest["clips"]) if c["source"] == source)


def test_FR_0_2_03_schema_is_valid_draft_2020_12():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    assert sorted(schema["required"]) == sorted(MANIFEST_FIELDS)


def test_FR_0_2_03_valid_fixture_passes():
    manifest = valid_manifest()
    assert pointers(validate_manifest, manifest) == set()
    sources = {c["source"] for c in manifest["clips"]}
    assert {"owner", "campaign"} <= sources and len(sources) >= 4
    assert any(c["speaker_id"] is None for c in manifest["clips"])
    assert any(c["recipe"] is not None for c in manifest["clips"])
    assert any(c["transcript"] is None for c in manifest["clips"])
    variants = {
        "prerelease and build version": dict(manifest, version="1.0.0-rc.1+build.5"),
        "public clip with a consent reference": copy.deepcopy(manifest),
        "archive with zero bytes and members listed": copy.deepcopy(manifest),
    }
    variants["public clip with a consent reference"]["clips"][0]["consent_ref"] = "consent/extra-note"
    variants["archive with zero bytes and members listed"]["archives"].append(
        {"name": "empty.tar", "sha256": "e" * 64, "bytes": 0, "n_members": 0})
    for name, variant in variants.items():
        assert pointers(validate_manifest, variant) == set(), name


MISSING = [(f,) for f in MANIFEST_FIELDS] + [("clips", 0, f) for f in CLIP_FIELDS] + \
          [("archives", 1, f) for f in ARCHIVE_FIELDS]


@pytest.mark.parametrize("path", MISSING, ids=lambda p: "/".join(map(str, p)))
def test_FR_0_2_03_rejects_missing_required_field(path):
    manifest = valid_manifest()
    parent, key = get_path(manifest, path)
    del parent[key]
    assert pointers(validate_manifest, manifest) == {pointer(*path)}


WRONG_VALUES = [
    (("manifest_id",), ["Smoke", "smoke_v1", "", 1, None]),
    (("purpose",), ["", 1, None]),
    (("created_utc",), ["2026-09-27T09:30:00", "2026-02-30T00:00:00Z", 1, None]),
    (("clips",), [[], {}, None]),
    (("archives",), [[], {}, None]),
    (("clips", 0), ["clip", None]),
    (("clips", 0, "clip_id"), ["Clip-1", "clip_1", "", "clip-1\n", 1, None]),
    (("clips", 0, "source"), ["LibriSpeech", "", 1, None]),
    (("clips", 0, "source_ref"), ["", 1, None]),
    (("clips", 0, "licence"), ["", 1, None]),
    (("clips", 0, "speaker_id"), ["", 1]),
    (("clips", 0, "consent_ref"), ["", 1]),
    (("clips", 0, "split"), ["Test Clean", "test_clean", "", None]),
    (("clips", 0, "duration_s"), [0, -1.5, "10", True, None]),
    (("clips", 0, "sample_rate_hz"), [0, 16000.0, "16000", -16000, None]),
    (("clips", 0, "channels"), [0, 1.0, "1", None]),
    (("clips", 0, "sha256"), ["x", "A" * 64, None]),
    (("clips", 0, "member_path"), ["/speech/a.wav", "../a.wav", "speech/../a.wav", "speech//a.wav", "speech\\a.wav",
                                   "./a.wav", "speech/.", "", "a.wav\n", None]),
    (("clips", 0, "transcript"), [1, ["a"]]),
    (("clips", 0, "recipe"), ["x", [], 1]),
    (("clips", 0, "tags"), ["speech", ["a", "a"], None]),
    (("clips", 0, "tags", 0), [1, "", None]),
    (("clips", 0, "archive"), ["a/b.tar", "", "..", 1, None]),
    (("archives", 0, "sha256"), ["x", None]),
    (("archives", 0, "bytes"), [-1, 1.5, "1", None]),
    (("archives", 0, "n_members"), [-1, 2.0, "2", None]),
]


@pytest.mark.parametrize("path,bad", [(p, v) for p, values in WRONG_VALUES for v in values],
                         ids=lambda x: repr(x)[:40])
def test_FR_0_2_03_rejects_wrong_type_or_enum(path, bad):
    manifest = valid_manifest()
    parent, key = get_path(manifest, path)
    parent[key] = bad
    assert pointers(validate_manifest, manifest) == {pointer(*path)}


@pytest.mark.parametrize("bad", ["1", "1.0", "v1.0.0", "01.0.0", "1.00.0", "1.0.0-", "1.0.0+", "1.0.0-01",
                                 "1.0.0\n", "1.0.٠", "", 1, None])
def test_FR_0_2_03_version_must_be_semver(bad):
    manifest = valid_manifest()
    manifest["version"] = bad
    assert pointers(validate_manifest, manifest) == {"/version"}


def test_FR_0_2_03_owner_and_campaign_clips_need_consent_ref():
    for source in ("owner", "campaign"):
        manifest = valid_manifest()
        i = clip_index(manifest, source)
        assert manifest["clips"][i]["consent_ref"]
        manifest["clips"][i]["consent_ref"] = None
        assert pointers(validate_manifest, manifest) == {f"/clips/{i}/consent_ref"}, source
        del manifest["clips"][i]["consent_ref"]
        assert pointers(validate_manifest, manifest) == {f"/clips/{i}/consent_ref"}, source
    manifest = valid_manifest()
    i = clip_index(manifest, "librispeech")
    assert manifest["clips"][i]["consent_ref"] is None
    manifest["clips"][i]["source"] = "owner"
    assert pointers(validate_manifest, manifest) == {f"/clips/{i}/consent_ref"}


def test_FR_0_2_03_rejects_duplicate_clip_id():
    manifest = valid_manifest()
    manifest["clips"][3]["clip_id"] = manifest["clips"][1]["clip_id"]
    assert pointers(validate_manifest, manifest) == {"/clips/3/clip_id"}
    manifest["clips"].append(copy.deepcopy(manifest["clips"][0]))
    assert pointers(validate_manifest, manifest) == {"/clips/3/clip_id", "/clips/5/clip_id"}


def test_FR_0_2_03_rejects_duplicate_archive_name():
    manifest = valid_manifest()
    manifest["archives"].append(dict(manifest["archives"][0], sha256="f" * 64))
    assert pointers(validate_manifest, manifest) == {"/archives/2/name"}


def test_FR_0_2_03_clip_archive_must_be_listed():
    manifest = valid_manifest()
    manifest["clips"][2]["archive"] = "smoke-v1-009.tar"
    assert pointers(validate_manifest, manifest) == {"/clips/2/archive"}
    manifest = valid_manifest()
    manifest["archives"] = [a for a in manifest["archives"] if a["name"] != "smoke-v1-000.tar"]
    using = {f"/clips/{i}/archive" for i, c in enumerate(manifest["clips"]) if c["archive"] == "smoke-v1-000.tar"}
    assert len(using) == 2
    assert pointers(validate_manifest, manifest) == using


@pytest.mark.parametrize("bad", ["a/b.tar", "..", ".", "", "a\\b.tar", "a.tar\n", None, 1])
def test_FR_0_2_03_rejects_unsafe_archive_name(bad):
    manifest = valid_manifest()
    manifest["archives"][0]["name"] = bad
    # A renamed archive is no longer the one its clips name. Without a string name the clips' references
    # cannot be judged (the nameless entry might be theirs), so only the name is reported.
    using = {f"/clips/{i}/archive" for i, c in enumerate(manifest["clips"]) if c["archive"] == "smoke-v1-000.tar"}
    assert len(using) == 2
    expected = {"/archives/0/name"} | (using if isinstance(bad, str) else set())
    assert pointers(validate_manifest, manifest) == expected


@pytest.mark.parametrize("bad", ["/abs.wav", "../up.wav", "a/../../b.wav", "a//b.wav", "a\\b.wav", "./a.wav", "a/./b.wav",
                                 "a/..", "a/\u0001.wav"])
def test_FR_0_2_03_rejects_unsafe_member_path(bad):
    manifest = valid_manifest()
    manifest["clips"][1]["member_path"] = bad
    assert pointers(validate_manifest, manifest) == {"/clips/1/member_path"}


@pytest.mark.parametrize("path", [(), ("clips", 0), ("archives", 0)], ids=lambda p: "/".join(map(str, p)) or "root")
def test_FR_0_2_03_rejects_unknown_field(path):
    manifest = valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target["extra"] = 1
    assert pointers(validate_manifest, manifest) == {pointer(*path, "extra")}


def test_FR_0_2_03_recipe_accepts_any_members():
    manifest = valid_manifest()
    manifest["clips"][0]["recipe"] = {"source_clip_ids": ["a"], "snr_db": 5, "gains": {"speech": 1.0}}
    assert pointers(validate_manifest, manifest) == set()


def test_FR_0_2_03_invalid_fixture_names_expected_pointers():
    expected = json.loads((FIXTURES / "invalid_expected.json").read_text(encoding="utf-8"))
    record = json.loads((FIXTURES / "invalid_manifest_fields.json").read_text(encoding="utf-8"))
    assert sorted(pointers(validate_manifest, record)) == expected["invalid_manifest_fields.json"]
