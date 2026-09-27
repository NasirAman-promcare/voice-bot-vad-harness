"""Canonical JSON and the content IDs derived from it (run_card_id, pack.sha256).

CAPABILITIES:
  CAP-CONTRACTS-004: canonical_json serialises a JSON value deterministically (sorted keys, "," and ":" separators, raw UTF-8, no NaN or Infinity) and refuses anything JSON cannot hold; compute_run_card_id is the SHA-256 of the canonical run card without run_card_id, created_utc and notes [tests: test_FR_0_2_05_canonical_bytes_match_definition, test_FR_0_2_05_key_order_does_not_change_bytes, test_FR_0_2_05_run_card_id_computed_independently, test_FR_0_2_05_run_card_id_ignores_only_the_three_excluded_fields, test_FR_0_2_05_canonical_rejects_nan_infinity_and_non_json]
INPUTS AND OUTPUTS: a JSON value made of dict (string keys), list, str, int, float, bool and None in; bytes
  or a lowercase SHA-256 hex string out; CanonicalJSONError naming the JSON Pointer of the first bad value.
CONTRACTS: run-card v1 (run_card_id), pack-manifest v1 (pack.sha256 in the run card); Phase 0 convention
  "IDs derived from content use SHA-256 of canonical JSON".
INVARIANTS:
  - Never converts silently: tuples, sets, bytes, non-string keys, unpaired surrogates, NaN and Infinity are errors.
  - The same value gives the same bytes on every platform (the float form is Python's shortest round-trip repr).
NOT IN SCOPE:
  - Checking a record against its contract (aqis_lab/contracts/validate.py).
CHANGE LOG:
  2026-09-27 WP-0.2 FR-0.2-05 created.
"""
import hashlib
import json
import math

RUN_CARD_ID_EXCLUDED = ("run_card_id", "created_utc", "notes")


class CanonicalJSONError(ValueError):
    """The value cannot be written as canonical JSON."""


def _pointer(parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _check(value, parts):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError(f"object key {key!r} is not a string at '{_pointer(parts)}'")
            _check_text(key, parts, "object key")
            _check(item, parts + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check(item, parts + (index,))
    elif isinstance(value, str):
        _check_text(value, parts, "text")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJSONError(f"number {value!r} is not allowed (no NaN or Infinity) at '{_pointer(parts)}'")
    elif value is not None and not isinstance(value, (bool, int)):
        raise CanonicalJSONError(f"{type(value).__name__} is not a JSON value at '{_pointer(parts)}'")


def _check_text(text, parts, what):
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalJSONError(f"{what} is not valid Unicode (unpaired surrogate) at '{_pointer(parts)}'") from exc


def canonical_json(value):
    """Canonical UTF-8 bytes of a JSON value: sorted keys, separators "," and ":", no NaN or Infinity."""
    try:
        _check(value, ())
    except RecursionError as exc:
        raise CanonicalJSONError("value is nested too deeply at ''") from exc
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return text.encode("utf-8")


def sha256_canonical(value):
    """Lowercase SHA-256 hex of canonical_json(value)."""
    return hashlib.sha256(canonical_json(value)).hexdigest()


def compute_run_card_id(card):
    """run_card_id: SHA-256 of the canonical run card without run_card_id, created_utc and notes."""
    if not isinstance(card, dict):
        raise CanonicalJSONError(f"a run card must be a JSON object, got {type(card).__name__} at ''")
    return sha256_canonical({key: value for key, value in card.items() if key not in RUN_CARD_ID_EXCLUDED})
