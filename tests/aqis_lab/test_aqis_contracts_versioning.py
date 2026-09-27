"""FR-0.2-06: schema $id carries the version; unknown major (and newer minor) versions are rejected clearly."""
import json
import re

import pytest

from aqis_contracts_testutil import DOCS, SCHEMA_DIR, first_event, valid_manifest, valid_run_card
from aqis_lab.contracts.validate import (ContractValidationError, UnsupportedSchemaVersionError, validate_event,
                                         validate_manifest, validate_run_card)

KINDS = {  # kind: (schema stem, document, validator, example factory)
    "event": ("event_log", "EVENT_LOG.md", validate_event, lambda: first_event("final")),
    "run_card": ("run_card", "RUN_CARD.md", validate_run_card, valid_run_card),
    "manifest": ("pack_manifest", "PACK_MANIFEST.md", validate_manifest, valid_manifest),
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_FR_0_2_06_schema_ids_carry_version(kind):
    stem = KINDS[kind][0]
    schema = json.loads((SCHEMA_DIR / f"{stem}.v1.json").read_text(encoding="utf-8"))
    versions = schema["properties"]["schema_version"]["enum"]
    assert versions == ["1.0"]
    assert schema["$id"] == f"urn:aqis-lab:contracts:{stem}:{versions[-1]}"
    assert versions[-1].split(".")[0] == "1"                      # the file name carries the major version
    assert KINDS[kind][3]()["schema_version"] == "1.0"


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("version,major", [("2.0", 2), ("0.1", 0), ("10.0", 10), ("2.5", 2)])
def test_FR_0_2_06_rejects_unknown_major_version(kind, version, major):
    _, _, validate, example = KINDS[kind]
    record = example()
    record["schema_version"] = version
    record["unexpected_field_of_a_future_version"] = True        # not reported: the version decides first
    with pytest.raises(UnsupportedSchemaVersionError) as info:
        validate(record)
    assert info.value.pointers == ("/schema_version",)
    text = str(info.value)
    assert f"major version {major}" in text and "does not know" in text and "major version 1 (up to 1.0)" in text


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("version", ["1.1", "1.10"])
def test_FR_0_2_06_rejects_newer_minor_version(kind, version):
    _, _, validate, example = KINDS[kind]
    record = example()
    record["schema_version"] = version
    with pytest.raises(UnsupportedSchemaVersionError) as info:
        validate(record)
    assert info.value.pointers == ("/schema_version",)
    assert "newer than this validator" in str(info.value) and "update aqis_lab" in str(info.value)


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("bad", [1, 1.0, "1", "v1.0", "1.0.0", "01.0", "1.00", " 1.0", "1.0\n", "", None, ["1.0"]])
def test_FR_0_2_06_rejects_malformed_schema_version(kind, bad):
    _, _, validate, example = KINDS[kind]
    record = example()
    record["schema_version"] = bad
    with pytest.raises(ContractValidationError) as info:
        validate(record)
    assert not isinstance(info.value, UnsupportedSchemaVersionError)
    assert info.value.pointers == ("/schema_version",)
    assert "'<major>.<minor>'" in str(info.value)
    missing = example()
    del missing["schema_version"]
    missing["another_problem"] = 1
    with pytest.raises(ContractValidationError) as info:
        validate(missing)
    assert info.value.pointers == ("/schema_version",)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_FR_0_2_06_documents_describe_change_policy(kind):
    stem, doc = KINDS[kind][0], KINDS[kind][1]
    text = (DOCS / doc).read_text(encoding="utf-8")
    section = re.search(r"^## Versioning and change policy\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert section, f"{doc} has no 'Versioning and change policy' section"
    body = section.group(1)
    assert f"urn:aqis-lab:contracts:{stem}:1.0" in body and f"{stem}.v1.json" in body
    for phrase in ("Minor version", "Major version", "newer minor version", "unknown major version",
                   "same commit"):
        assert phrase in body, (doc, phrase)
