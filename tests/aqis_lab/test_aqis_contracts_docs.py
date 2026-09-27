"""FR-0.2-07: every schema field appears in its contract document, and every documented field is in the schema.

The schema walker and the document parser live here, independent of aqis_lab/contracts. Fields are compared as
(context, path) pairs: path is a JSON Pointer with '*' for array items; context is the event type for event
payload fields ('/payload/...') and '' otherwise.
"""
import copy
import json
import re

import pytest

from aqis_contracts_testutil import (CLIP_FIELDS, DOCS, EVENT_FIELDS, EVENT_TYPES, MANIFEST_FIELDS, RUN_CARD_FIELDS,
                                     RUN_CARD_NESTED, SCHEMA_DIR)

KINDS = {"event": ("event_log.v1.json", "EVENT_LOG.md"), "run_card": ("run_card.v1.json", "RUN_CARD.md"),
         "manifest": ("pack_manifest.v1.json", "PACK_MANIFEST.md")}
PAYLOAD_HEADING = re.compile(r"^### Payload: `([a-z_]+)`\s*$")
FIELD_ROW = re.compile(r"^\|\s*`(/[^`]*)`\s*\|")


def _escape(name):
    return name.replace("~", "~0").replace("/", "~1")


def _resolve(ref, root):
    assert ref.startswith("#/"), f"only local references are expected, got {ref}"
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _event_type_of(entry):
    cond = entry.get("if") if isinstance(entry, dict) else None
    try:
        return cond["properties"]["event_type"]["const"]
    except (TypeError, KeyError):
        return None


def schema_fields(schema):
    out = set()

    def walk(node, prefix, context):
        if not isinstance(node, dict):
            return
        if "$ref" in node:
            walk(_resolve(node["$ref"], schema), prefix, context)
        for name, sub in node.get("properties", {}).items():
            path = f"{prefix}/{_escape(name)}"
            out.add((context if path.startswith("/payload/") else "", path))
            walk(sub, path, context)
        if "items" in node:
            walk(node["items"], prefix + "/*", context)
        for key in ("allOf", "anyOf", "oneOf"):
            for entry in node.get(key, []):
                event_type = _event_type_of(entry)
                if event_type is not None:
                    walk(entry["if"], prefix, context)
                    walk(entry["then"], prefix, event_type)
                else:
                    walk(entry, prefix, context)
        for key in ("if", "then", "else", "not"):
            walk(node.get(key), prefix, context)

    walk(schema, "", "")
    return out


def document_fields(text):
    out, context = set(), ""
    for line in text.splitlines():
        heading = PAYLOAD_HEADING.match(line)
        if heading:
            context = heading.group(1)
            continue
        if line.startswith("#"):
            context = ""
            continue
        row = FIELD_ROW.match(line)
        if row:
            path = row.group(1)
            out.add((context if path.startswith("/payload/") else ("" if not context else f"{context}!"), path))
    return out


def payload_headings(text):
    return [m.group(1) for m in map(PAYLOAD_HEADING.match, text.splitlines()) if m]


def load(kind):
    schema_file, doc = KINDS[kind]
    return json.loads((SCHEMA_DIR / schema_file).read_text(encoding="utf-8")), (DOCS / doc).read_text(encoding="utf-8")


def differences(schema, text):
    in_schema, in_doc = schema_fields(schema), document_fields(text)
    return sorted(in_schema - in_doc), sorted(in_doc - in_schema)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_FR_0_2_07_documents_and_schemas_list_same_fields(kind):
    schema, text = load(kind)
    undocumented, not_in_schema = differences(schema, text)
    assert undocumented == [], f"schema fields missing from {KINDS[kind][1]}: {undocumented}"
    assert not_in_schema == [], f"documented fields missing from {KINDS[kind][0]}: {not_in_schema}"
    fields = {path for _, path in schema_fields(schema)}
    # the comparison covers the spec's fields, written out independently in aqis_contracts_testutil
    spec = {"event": {f"/{f}" for f in EVENT_FIELDS},
            "run_card": {f"/{f}" for f in RUN_CARD_FIELDS} | {f"/{p}/{c}" for p, cs in RUN_CARD_NESTED.items() for c in cs},
            "manifest": {f"/{f}" for f in MANIFEST_FIELDS} | {f"/clips/*/{f}" for f in CLIP_FIELDS}}[kind]
    assert spec <= fields, sorted(spec - fields)
    if kind == "event":
        assert sorted(payload_headings(text)) == sorted(EVENT_TYPES)
        assert ("final", "/payload/words/*/end_s") in schema_fields(schema)
        assert ("error", "/payload/run_continues") in schema_fields(schema)


def test_FR_0_2_07_comparison_detects_missing_and_extra_fields():
    for kind, dropped_row, added_row in (("run_card", "/model/checksum", "/model/extra"),
                                         ("manifest", "/clips/*/consent_ref", "/archives/*/extra"),
                                         ("event", "/payload/words/*/start_s", "/host")):
        schema, text = load(kind)
        assert differences(schema, text) == ([], [])
        lines = text.splitlines()
        kept = [line for line in lines if not line.startswith(f"| `{dropped_row}` |")]
        assert len(kept) == len(lines) - 1, dropped_row
        undocumented, _ = differences(schema, "\n".join(kept))
        assert [path for _, path in undocumented] == [dropped_row]
        _, extra = differences(schema, text + f"\n| `{added_row}` | string | yes | not in the schema |\n")
        assert [path for _, path in extra] == [added_row]
    # a field removed from the schema is found too, including one inside a payload sub-schema
    schema, text = load("event")
    changed = copy.deepcopy(schema)
    del changed["$defs"]["payload_error"]["properties"]["run_continues"]
    _, extra = differences(changed, text)
    assert extra == [("error", "/payload/run_continues")]
    # a payload row placed under the wrong event type does not count for the right one
    moved = text.replace("### Payload: `partial`", "### Payload: `partial-moved`", 1)
    undocumented, extra = differences(schema, moved)
    assert ("partial", "/payload/text") in undocumented
