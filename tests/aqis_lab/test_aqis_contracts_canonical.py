"""FR-0.2-05: canonical JSON (sorted keys, fixed separators, UTF-8, no NaN or Infinity) and run_card_id."""
import copy
import hashlib
import json
import math

import pytest

from aqis_contracts_testutil import RUN_CARD_FIELDS, valid_run_card
from aqis_lab.contracts.canonical import CanonicalJSONError, canonical_json, compute_run_card_id, sha256_canonical


def independent_encode(value):
    """Canonical JSON written from the FR-0.2-05 definition, without canonical.py or json.dumps' sort_keys."""
    if isinstance(value, dict):
        items = sorted(value.items())
        return "{" + ",".join(independent_encode(k) + ":" + independent_encode(v) for k, v in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(independent_encode(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)          # string escaping only
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    assert isinstance(value, float) and math.isfinite(value)
    return repr(value)


def independent_run_card_id(card):
    body = {k: v for k, v in card.items() if k not in ("run_card_id", "created_utc", "notes")}
    return hashlib.sha256(independent_encode(body).encode("utf-8")).hexdigest()


def test_FR_0_2_05_canonical_bytes_match_definition():
    value = {"b": [1, 2.5, 0.1, -3, 1.0, True, False, None], "a": "é\n\"\\/", "c": {"z": [], "y": {}}, "é": 1}
    expected = (b'{"a":"\xc3\xa9\\n\\"\\\\/","b":[1,2.5,0.1,-3,1.0,true,false,null],'
                b'"c":{"y":{},"z":[]},"\xc3\xa9":1}')
    assert canonical_json(value) == expected
    assert canonical_json(value) == independent_encode(value).encode("utf-8")
    assert sha256_canonical(value) == hashlib.sha256(expected).hexdigest()


def test_FR_0_2_05_key_order_does_not_change_bytes():
    card = valid_run_card()
    reordered = {k: card[k] for k in reversed(list(card))}
    reordered["machine"] = {k: card["machine"][k] for k in reversed(list(card["machine"]))}
    assert list(reordered) != list(card)
    assert canonical_json(reordered) == canonical_json(card)
    assert compute_run_card_id(reordered) == compute_run_card_id(card)


def test_FR_0_2_05_run_card_id_computed_independently():
    card = valid_run_card()
    expected = independent_run_card_id(card)
    assert compute_run_card_id(card) == expected
    assert card["run_card_id"] == expected                 # the fixture carries the defined ID
    assert len(expected) == 64 and expected == expected.lower()


def test_FR_0_2_05_run_card_id_ignores_only_the_three_excluded_fields():
    card = valid_run_card()
    base = compute_run_card_id(card)
    for field, value in (("run_card_id", "0" * 64), ("created_utc", "2030-01-01T00:00:00Z"), ("notes", "other")):
        changed = copy.deepcopy(card)
        changed[field] = value
        assert compute_run_card_id(changed) == base, field
        del changed[field]
        assert compute_run_card_id(changed) == base, field
    others = [f for f in RUN_CARD_FIELDS if f not in ("run_card_id", "created_utc", "notes")]
    assert len(others) == 10
    for field in others:
        changed = copy.deepcopy(card)
        changed[field] = "changed"
        assert compute_run_card_id(changed) != base, field
    nested = copy.deepcopy(card)
    nested["model"]["settings"]["words"] = False
    assert compute_run_card_id(nested) != base
    as_float = copy.deepcopy(card)
    as_float["seed"] = float(card["seed"])
    assert compute_run_card_id(as_float) != base           # 20260927 and 20260927.0 are different JSON


@pytest.mark.parametrize("bad,where", [
    (float("nan"), ""), (float("inf"), ""), ({"a": [1, float("-inf")]}, "/a/1"), ((1, 2), ""), ({1, 2}, ""),
    (b"x", ""), (object(), ""), ({1: "a"}, ""), ({"k": "\ud800"}, "/k"), ({"\ud800": 1}, ""), ({"a/b": {"t~": (1,)}}, "/a~1b/t~0"),
])
def test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json(bad, where):
    with pytest.raises(CanonicalJSONError) as info:
        canonical_json(bad)
    assert f"at '{where}'" in str(info.value)
    with pytest.raises(CanonicalJSONError):
        sha256_canonical(bad)
    with pytest.raises(CanonicalJSONError):
        compute_run_card_id({"seed": 1, "model": bad})
