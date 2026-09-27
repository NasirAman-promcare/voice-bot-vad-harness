"""Validators for the AQIS lab contracts, naming every failing field by JSON Pointer.

CAPABILITIES:
  CAP-CONTRACTS-001: validate_event checks one event-log record against event_log.v1.json (dispatched by event type) plus the word-timing order rule; validate_event_lines checks a JSON Lines file record by record, including the per-run seq order [tests: test_FR_0_2_01_schema_is_valid_draft_2020_12, test_FR_0_2_01_valid_fixture_covers_every_event_type, test_FR_0_2_01_valid_fixture_passes, test_FR_0_2_01_rejects_missing_required_field, test_FR_0_2_01_rejects_missing_required_payload_field, test_FR_0_2_01_rejects_missing_required_word_field, test_FR_0_2_01_rejects_wrong_type_or_enum, test_FR_0_2_01_clip_id_null_only_for_run_level_events, test_FR_0_2_01_null_audio_time_needs_reason, test_FR_0_2_01_final_word_timings, test_FR_0_2_01_error_payload_fields, test_FR_0_2_01_rejects_unknown_field, test_FR_0_2_01_invalid_fixture_names_expected_pointers]
  CAP-CONTRACTS-002: validate_run_card checks a run card against run_card.v1.json (pack null only for human_session, a model version or checksum) and that run_card_id is the SHA-256 of the canonical card without run_card_id, created_utc and notes [tests: test_FR_0_2_02_schema_is_valid_draft_2020_12, test_FR_0_2_02_valid_fixture_passes, test_FR_0_2_02_rejects_missing_required_field, test_FR_0_2_02_rejects_wrong_type_or_enum, test_FR_0_2_02_model_needs_version_or_checksum, test_FR_0_2_02_pack_null_only_for_human_session, test_FR_0_2_02_processing_keeps_step_order_per_path, test_FR_0_2_02_rejects_run_card_id_mismatch, test_FR_0_2_02_rejects_unknown_field, test_FR_0_2_02_open_objects_accept_any_members]
  CAP-CONTRACTS-003: validate_manifest checks a pack manifest against pack_manifest.v1.json (consent_ref for owner and campaign clips, safe archive names and member paths) plus unique clip_id and archive names and every clip's archive listed in archives [tests: test_FR_0_2_03_schema_is_valid_draft_2020_12, test_FR_0_2_03_valid_fixture_passes, test_FR_0_2_03_rejects_missing_required_field, test_FR_0_2_03_rejects_wrong_type_or_enum, test_FR_0_2_03_version_must_be_semver, test_FR_0_2_03_owner_and_campaign_clips_need_consent_ref, test_FR_0_2_03_rejects_duplicate_clip_id, test_FR_0_2_03_rejects_duplicate_archive_name, test_FR_0_2_03_clip_archive_must_be_listed, test_FR_0_2_03_rejects_unsafe_archive_name, test_FR_0_2_03_rejects_unsafe_member_path, test_FR_0_2_03_rejects_unknown_field, test_FR_0_2_03_recipe_accepts_any_members, test_FR_0_2_03_invalid_fixture_names_expected_pointers]
  CAP-CONTRACTS-005: schema_version is checked before anything else: a missing or malformed version, an unknown major version and a newer minor version are rejected at /schema_version with a clear message (UnsupportedSchemaVersionError for the last two); each schema $id carries <major>.<minor> [tests: test_FR_0_2_06_schema_ids_carry_version, test_FR_0_2_06_rejects_unknown_major_version, test_FR_0_2_06_rejects_newer_minor_version, test_FR_0_2_06_rejects_malformed_schema_version, test_FR_0_2_06_documents_describe_change_policy]
  CAP-CONTRACTS-007: the validator API: one ContractValidationError naming every failing field by RFC 6901 pointer (missing fields at their own pointer, 'Rule:' text for cross-field rules), strict JSON (UTF-8, no NaN or Infinity, no duplicate keys, integers without a fraction), per-run seq order in JSON Lines, and a worker-process pool for large event files giving the same reports as one process [tests: test_FR_0_2_04_error_names_every_failing_pointer, test_FR_0_2_04_pointer_escapes_tilde_and_slash, test_FR_0_2_04_missing_field_pointer_names_the_field, test_FR_0_2_04_rejects_nan_infinity_and_overflow, test_FR_0_2_04_rejects_duplicate_keys, test_FR_0_2_04_rejects_integer_written_as_float, test_FR_0_2_04_patterns_reject_trailing_newline_and_non_ascii_digits, test_FR_0_2_04_non_json_python_values_rejected, test_FR_0_2_04_non_object_record_rejected, test_FR_0_2_04_rule_errors_explain_the_rule, test_FR_0_2_04_dispatch_matches_full_schema_on_all_fixtures, test_FR_0_2_04_seq_counts_from_zero_per_run, test_FR_0_2_04_worker_pool_report_identical_to_single_process, test_NFR_0_2_01_validates_100k_events_under_10s, test_NFR_0_2_02_contracts_code_is_pure_python_with_pinned_jsonschema]
INPUTS AND OUTPUTS: parsed JSON values (or raw JSON text for the parsers) in; None when valid, otherwise
  ContractValidationError listing (JSON Pointer, message) for every failing field.
CONTRACTS: event-log v1 (docs/contracts/EVENT_LOG.md), run-card v1 (docs/contracts/RUN_CARD.md),
  pack-manifest v1 (docs/contracts/PACK_MANIFEST.md).
INVARIANTS:
  - The schema files are the single source of the structural rules; the per-event-type validators are derived
    from event_log.v1.json at load time by dropping the other types' if/then blocks, which cannot apply.
  - "integer" means a JSON integer written without a fraction or exponent; NaN, Infinity, numbers that overflow
    to infinity, unpaired surrogates and non-JSON Python values are errors at their own pointer.
  - A missing field is reported at the field's own pointer, never at its parent.
  - Never prints; never swallows an error: every problem found is in the raised exception.
NOT IN SCOPE:
  - Writing records; the command line (aqis_lab/commands/contracts.py).
CHANGE LOG:
  2026-09-27 WP-0.2 FR-0.2-01 created.
  2026-09-27 WP-0.2 FR-0.2-02 run cards: validate_run_card and the run_card_id check.
  2026-09-27 WP-0.2 FR-0.2-03 pack manifests: validate_manifest and the checks across clips.
  2026-09-27 WP-0.2 FR-0.2-04 validate_document, the worker pool (question 2), 'Rule:' messages.
  2026-09-27 WP-0.2 FR-0.2-06 schema_version check and UnsupportedSchemaVersionError.
  2026-09-27 WP-0.2 NFR-0.2-01 per-type event validators use inlined local references.
"""
import datetime
import functools
import json
import math
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, validators

from aqis_lab.contracts.canonical import CanonicalJSONError, compute_run_card_id

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
# kind -> (label used in messages, schema file stem)
KINDS = {"event": ("event log", "event_log"), "run_card": ("run card", "run_card"),
         "manifest": ("pack manifest", "pack_manifest")}
ROOT_POINTER_LABEL = "(document)"
# Event files with at least this many records are split over worker processes when more than one is allowed
# (NFR-0.2-01, plan question 2); each chunk is validated in one worker, and results keep the file order.
POOL_MIN_RECORDS = 5000
POOL_CHUNK_RECORDS = 2000
# kind -> {known major version: newest known minor version}. The v1 schema files accept every v1 minor up to it.
SUPPORTED_VERSIONS = {"event": {1: 0}, "run_card": {1: 0}, "manifest": {1: 0}}
VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
UTC_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,9})?Z")


@dataclass(frozen=True, order=True)
class FieldError:
    """One failing field: RFC 6901 JSON Pointer ('' is the whole record) and the reason."""
    pointer: str
    message: str


class ContractSchemaError(RuntimeError):
    """A packaged schema file is not in the form this validator relies on."""


class WorkerPoolError(RuntimeError):
    """Worker processes for bulk validation could not be started or died."""


class ContractValidationError(ValueError):
    """A record breaks its contract; .errors lists every failing field, sorted by pointer."""

    def __init__(self, kind, errors):
        self.kind = kind
        self.errors = tuple(sorted(set(errors)))
        label = KINDS[kind][0] if kind in KINDS else str(kind)
        count = len(self.errors)
        lines = [f"{label} record is invalid ({count} problem{'' if count == 1 else 's'}):"]
        lines += [f"  {display_pointer(err.pointer)}: {err.message}" for err in self.errors]
        super().__init__("\n".join(lines))

    @property
    def pointers(self):
        return tuple(sorted({err.pointer for err in self.errors}))


class UnsupportedSchemaVersionError(ContractValidationError):
    """The record claims a schema version this validator does not know (unknown major or newer minor)."""


@dataclass(frozen=True)
class RecordReport:
    """Validation result of one record of a file: number is the 1-based line or record number."""
    number: int
    errors: tuple

    @property
    def valid(self):
        return not self.errors


def json_pointer(parts):
    """RFC 6901 pointer for a sequence of object keys and array indexes."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def display_pointer(pointer):
    return pointer if pointer else ROOT_POINTER_LABEL


# ---------------------------------------------------------------------------------------------
# JSON Schema machinery
# ---------------------------------------------------------------------------------------------
def _is_json_integer(checker, instance):
    return isinstance(instance, int) and not isinstance(instance, bool)


_TYPE_CHECKER = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_json_integer)
_Validator = validators.extend(Draft202012Validator, type_checker=_TYPE_CHECKER)
_FORMATS = FormatChecker(formats=())


@_FORMATS.checks("date-time", raises=ValueError)
def _utc_is_a_real_time(instance):
    """Calendar check for UTC timestamps; the schema's pattern checks their written form."""
    if not isinstance(instance, str):
        return True
    match = UTC_RE.fullmatch(instance)
    if match is None:
        return True  # the pattern keyword reports the wrong form
    datetime.datetime(*(int(g) for g in match.groups()))  # ValueError for a day, hour or second that does not exist
    return True


@functools.cache
def load_schema(kind):
    """The parsed v1 schema for kind, checked against the JSON Schema 2020-12 meta-schema."""
    path = SCHEMA_DIR / f"{KINDS[kind][1]}.v1.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _make_validator(schema):
    return _Validator(schema, format_checker=_FORMATS)


def _event_type_of_branch(entry):
    """The event type an allOf entry selects, or None when it is not an event-type if/then block."""
    if not isinstance(entry, dict) or set(entry) != {"if", "then"}:
        return None
    cond = entry["if"]
    if not isinstance(cond, dict) or set(cond) != {"required", "properties"} or cond["required"] != ["event_type"]:
        return None
    props = cond["properties"]
    if not isinstance(props, dict) or set(props) != {"event_type"}:
        return None
    const = props["event_type"]
    if not isinstance(const, dict) or set(const) != {"const"}:
        return None
    return const["const"]


ANNOTATION_KEYWORDS = frozenset({"description", "title"})
DATA_KEYWORDS = frozenset({"enum", "const", "default", "examples"})


def _inline_local_refs(node, root, stack=()):
    """Copy of node with every local "$ref" replaced by its target where the $ref's siblings are annotations only.

    Such a node means exactly its target (annotations do not validate), so validation results are unchanged; the
    validator just skips the reference lookups. Other $ref nodes are kept as they are.
    """
    if isinstance(node, list):
        return [_inline_local_refs(item, root, stack) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/") and set(node) - {"$ref"} <= ANNOTATION_KEYWORDS:
        if ref in stack:
            raise ContractSchemaError(f"schema reference cycle through {ref}")
        target = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        inlined = dict(_inline_local_refs(target, root, stack + (ref,)))
        inlined.update({key: node[key] for key in node if key in ANNOTATION_KEYWORDS})
        return inlined
    return {key: (value if key in DATA_KEYWORDS else _inline_local_refs(value, root, stack))
            for key, value in node.items()}


@functools.cache
def _event_validators():
    """(full validator, {event_type: validator}) built from event_log.v1.json.

    For a record whose event_type is T, every other type's if/then block has a false "if" and no "else", so it
    adds nothing; the derived schema keeps the common blocks and T's "then" only, and gives the same result.
    Its local references are inlined (_inline_local_refs) for speed (NFR-0.2-01).
    """
    schema = load_schema("event")
    common, branches = [], {}
    for entry in schema["allOf"]:
        event_type = _event_type_of_branch(entry)
        if event_type is None:
            common.append(entry)
        elif event_type in branches:
            raise ContractSchemaError(f"event_log.v1.json selects event type {event_type!r} twice")
        else:
            branches[event_type] = entry["then"]
    types = schema["properties"]["event_type"]["enum"]
    if set(branches) != set(types):
        raise ContractSchemaError(f"event_log.v1.json has payload rules for {sorted(branches)}, "
                                  f"but its event types are {sorted(types)}")
    per_type = {}
    for event_type in types:
        derived = dict(schema)
        derived["allOf"] = common + [branches[event_type]]
        per_type[event_type] = _make_validator(_inline_local_refs(derived, schema))
    return _make_validator(schema), per_type


def _field_errors(error):
    """FieldErrors for one jsonschema error, each pointing at the field that fails."""
    path = list(error.absolute_path)
    if error.validator == "required":
        instance = error.instance
        missing = [p for p in error.validator_value if isinstance(instance, dict) and p not in instance]
        return [FieldError(json_pointer(path + [p]), _with_rule("required field is missing", error.schema))
                for p in missing]
    if error.validator == "additionalProperties" and error.validator_value is False:
        allowed = set(error.schema.get("properties", {}))
        return [FieldError(json_pointer(path + [key]), "field is not part of the contract")
                for key in error.instance if key not in allowed]
    if error.validator in ("anyOf", "oneOf") and error.context:
        depth = max(len(sub.absolute_path) for sub in error.context)
        leaves = [leaf for sub in error.context if len(sub.absolute_path) == depth for leaf in _field_errors(sub)]
        return [FieldError(leaf.pointer, f"no allowed alternative matched: {leaf.message}") for leaf in leaves]
    if error.validator == "not" and error.validator_value == {}:
        return [FieldError(json_pointer(path), _with_rule("field is not allowed here", error.schema))]
    if error.validator == "not" and error.validator_value == {"type": "null"}:
        return [FieldError(json_pointer(path), _with_rule("must not be null here", error.schema))]
    return [FieldError(json_pointer(path), _with_rule(error.message, error.schema))]


def _with_rule(message, schema):
    """Append the text of a cross-field rule (a subschema described as 'Rule: ...') to its error message."""
    description = schema.get("description", "") if isinstance(schema, dict) else ""
    return f"{message}. {description}" if description.startswith("Rule: ") else message


def _schema_errors(validator, record):
    errors = []
    for error in validator.iter_errors(record):
        errors.extend(_field_errors(error))
    return errors


# ---------------------------------------------------------------------------------------------
# rules JSON Schema cannot express
# ---------------------------------------------------------------------------------------------
def _is_unicode(text):
    if text.isascii():
        return True
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _json_value_errors(value, parts, errors):
    """Append errors for values JSON (and canonical JSON) cannot hold, anywhere inside value."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(FieldError(json_pointer(parts + (str(key),)),
                                         f"object keys must be strings, got {type(key).__name__}"))
                continue
            if not _is_unicode(key):
                errors.append(FieldError(json_pointer(parts + (key,)), "key is not valid Unicode (unpaired surrogate)"))
            _json_value_errors(item, parts + (key,), errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _json_value_errors(item, parts + (index,), errors)
    elif isinstance(value, str):
        if not _is_unicode(value):
            errors.append(FieldError(json_pointer(parts), "text is not valid Unicode (unpaired surrogate)"))
    elif isinstance(value, float):
        if not math.isfinite(value):
            errors.append(FieldError(json_pointer(parts), "number must be finite: NaN, Infinity and numbers too "
                                                          "large for a double are not allowed"))
    elif value is not None and not isinstance(value, (bool, int)):
        errors.append(FieldError(json_pointer(parts), f"{type(value).__name__} is not a JSON value"))


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _event_rules(record):
    errors = []
    payload = record.get("payload")
    if record.get("event_type") == "final" and isinstance(payload, dict) and isinstance(payload.get("words"), list):
        for index, word in enumerate(payload["words"]):
            if isinstance(word, dict) and _is_number(word.get("start_s")) and _is_number(word.get("end_s")) \
                    and word["end_s"] < word["start_s"]:
                errors.append(FieldError(json_pointer(("payload", "words", index, "end_s")),
                                         f"end_s {word['end_s']} is before start_s {word['start_s']}"))
    return errors


def _run_card_rules(card):
    claimed = card.get("run_card_id")
    if not isinstance(claimed, str) or SHA256_RE.fullmatch(claimed) is None:
        return []  # the schema reports a missing or malformed run_card_id
    try:
        defined = compute_run_card_id(card)
    except CanonicalJSONError:
        return []  # _json_value_errors reports the value canonical JSON cannot hold
    if claimed == defined:
        return []
    return [FieldError("/run_card_id", f"does not match the SHA-256 of the canonical run card without run_card_id, "
                                       f"created_utc and notes ({defined})")]


def _unique_errors(items, key, path, label):
    """Errors at path/<i>/key for each later item repeating an earlier item's string key."""
    first, errors = {}, []
    for index, item in enumerate(items):
        value = item.get(key) if isinstance(item, dict) else None
        if not isinstance(value, str):
            continue
        if value in first:
            errors.append(FieldError(json_pointer((path, index, key)),
                                     f"duplicate {label} {value!r}: already used by {json_pointer((path, first[value]))}"))
        else:
            first[value] = index
    return errors


def _manifest_rules(manifest):
    clips, archives = manifest.get("clips"), manifest.get("archives")
    errors = []
    if isinstance(clips, list):
        errors += _unique_errors(clips, "clip_id", "clips", "clip_id")
    if isinstance(archives, list):
        errors += _unique_errors(archives, "name", "archives", "archive name")
    names = [a.get("name") if isinstance(a, dict) else None for a in archives] if isinstance(archives, list) else []
    # References are judged only against a complete, non-empty list of archive names: a nameless entry might be
    # the one a clip names, and the schema already reports the entry itself.
    if isinstance(clips, list) and names and all(isinstance(n, str) for n in names):
        for index, clip in enumerate(clips):
            archive = clip.get("archive") if isinstance(clip, dict) else None
            if isinstance(archive, str) and archive not in names:
                errors.append(FieldError(json_pointer(("clips", index, "archive")),
                                         f"archive {archive!r} is not listed in /archives"))
    return errors


@functools.cache
def _validator_for(kind):
    return _make_validator(load_schema(kind))


# ---------------------------------------------------------------------------------------------
# public validators
# ---------------------------------------------------------------------------------------------
def _json_type_name(value):
    names = {dict: "object", list: "array", str: "string", bool: "boolean", int: "number", float: "number"}
    return "null" if value is None else names.get(type(value), type(value).__name__)


def _check_version(kind, record):
    """Raise unless schema_version names a version this validator knows; other fields are not judged before."""
    label = KINDS[kind][0]
    if "schema_version" not in record:
        raise ContractValidationError(kind, [FieldError("/schema_version", "required field is missing; without it "
                                                                           "the record's contract version is unknown")])
    version = record["schema_version"]
    match = VERSION_RE.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        raise ContractValidationError(kind, [FieldError("/schema_version", f"must be a string '<major>.<minor>' such "
                                                                           f"as '1.0', got {version!r}")])
    major, minor = int(match.group(1)), int(match.group(2))
    known = SUPPORTED_VERSIONS[kind]
    known_text = ", ".join(f"major version {m} (up to {m}.{known[m]})" for m in sorted(known))
    if major not in known:
        raise UnsupportedSchemaVersionError(kind, [FieldError(
            "/schema_version", f"{label} schema_version {version!r} has major version {major}, which this validator "
                               f"does not know; it knows {known_text}")])
    if minor > known[major]:
        raise UnsupportedSchemaVersionError(kind, [FieldError(
            "/schema_version", f"{label} schema_version {version!r} is newer than this validator "
                               f"({major}.{known[major]}); update aqis_lab to validate it")])


def _validate(kind, record, validator, rules):
    if not isinstance(record, dict):
        label = KINDS[kind][0]
        article = "an" if label[0] in "aeiou" else "a"
        raise ContractValidationError(kind, [FieldError("", f"{article} {label} record must be a JSON object, "
                                                            f"got {_json_type_name(record)}")])
    _check_version(kind, record)
    errors = _schema_errors(validator, record)
    _json_value_errors(record, (), errors)
    errors.extend(rules(record))
    if errors:
        raise ContractValidationError(kind, errors)


def validate_event(record):
    """Validate one event-log record; return None or raise ContractValidationError."""
    full, per_type = _event_validators()
    event_type = record.get("event_type") if isinstance(record, dict) else None
    validator = per_type.get(event_type, full) if isinstance(event_type, str) else full
    _validate("event", record, validator, _event_rules)


def validate_run_card(card):
    """Validate one run card, including its run_card_id; return None or raise ContractValidationError."""
    _validate("run_card", card, _validator_for("run_card"), _run_card_rules)


def validate_manifest(manifest):
    """Validate one pack manifest, including the checks across clips; return None or raise ContractValidationError."""
    _validate("manifest", manifest, _validator_for("manifest"), _manifest_rules)


# ---------------------------------------------------------------------------------------------
# strict parsing and files
# ---------------------------------------------------------------------------------------------
def _reject_constant(name):
    raise ValueError(f"{name} is not allowed (JSON has no NaN or Infinity)")


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def parse_json(data, kind):
    """Parse one JSON text strictly (UTF-8, no NaN or Infinity, no duplicate keys, not empty).

    Raises ContractValidationError at the document pointer '' when the text is not acceptable JSON.
    """
    if isinstance(data, (bytes, bytearray)):
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractValidationError(kind, [FieldError("", f"not valid UTF-8 ({exc.reason} at byte {exc.start})")]) \
                from exc
    else:
        text = data
    if not text.strip(" \t\r\n"):
        raise ContractValidationError(kind, [FieldError("", "no JSON value (the text is empty or blank)")])
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError) as exc:
        raise ContractValidationError(kind, [FieldError("", f"not valid JSON: {exc}")]) from exc


def split_json_lines(data):
    """The records of a JSON Lines byte string: one per line; a final newline does not start a record."""
    lines = bytes(data).split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines


def _check_event_line(raw):
    """(errors, run_id, seq) for one JSON Lines record; run_id and seq are None unless usable for ordering."""
    try:
        record = parse_json(raw, "event")
    except ContractValidationError as exc:
        return exc.errors, None, None
    try:
        validate_event(record)
        errors = ()
    except ContractValidationError as exc:
        errors = exc.errors
    if not isinstance(record, dict):
        return errors, None, None
    run_id, seq = record.get("run_id"), record.get("seq")
    usable = isinstance(run_id, str) and isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0
    return errors, (run_id if usable else None), (seq if usable else None)


def _sequence_errors(results):
    """Per-record /seq errors: for each run_id, seq must run 0, 1, 2, ... in file order."""
    expected, out = {}, []
    for _, run_id, seq in results:
        extra = ()
        if run_id is not None:
            want = expected.get(run_id, 0)
            if seq != want:
                extra = (FieldError("/seq", f"seq {seq} is out of order for run_id {run_id!r}: expected {want} "
                                            f"(seq counts 0, 1, 2, ... per run, in file order)"),)
            if seq >= want:
                expected[run_id] = seq + 1
        out.append(extra)
    return out


def uses_worker_pool(n_records, workers):
    """True when validate_event_lines splits n_records over worker processes."""
    return workers > 1 and n_records >= POOL_MIN_RECORDS


def _check_event_chunk(raws):
    return [_check_event_line(raw) for raw in raws]


def validate_event_lines(data, workers=1):
    """Validate a JSON Lines event log given as bytes; one RecordReport per line, in file order.

    workers > 1 splits files of at least POOL_MIN_RECORDS records over that many worker processes; the reports
    are identical to one process. The per-run seq order is checked afterwards, in file order.
    """
    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError(f"workers must be a whole number of at least 1, got {workers!r}")
    lines = split_json_lines(data)
    if uses_worker_pool(len(lines), workers):
        chunks = [lines[i:i + POOL_CHUNK_RECORDS] for i in range(0, len(lines), POOL_CHUNK_RECORDS)]
        try:
            with ProcessPoolExecutor(max_workers=min(workers, len(chunks)),
                                     mp_context=multiprocessing.get_context("spawn")) as pool:
                results = [result for chunk in pool.map(_check_event_chunk, chunks) for result in chunk]
        except (OSError, BrokenProcessPool) as exc:
            raise WorkerPoolError(f"cannot run {workers} worker processes: {exc}") from exc
    else:
        results = _check_event_chunk(lines)
    sequence = _sequence_errors(results)
    return [RecordReport(number, tuple(sorted(set(errors) | set(extra))))
            for number, ((errors, _, _), extra) in enumerate(zip(results, sequence), start=1)]


VALIDATORS = {"event": validate_event, "run_card": validate_run_card, "manifest": validate_manifest}


def validate_document(kind, data):
    """Parse and validate one JSON document (bytes) of kind; RecordReport number 1."""
    try:
        VALIDATORS[kind](parse_json(data, kind))
    except ContractValidationError as exc:
        return RecordReport(1, exc.errors)
    return RecordReport(1, ())
