"""Shared helpers for the WP-0.2 contract tests (not a test module).

The field lists here are written from the spec text (docs/specs/phase-0/WP-0.2-contracts.md) and
the approved plan (docs/progress/WP-0.2/PLAN.md), never read from the schemas, so a schema that
drops or renames a field fails the tests.
"""
import copy
import json
from pathlib import Path

from aqis_testutil import ROOT

FIXTURES = ROOT / "tests" / "aqis_lab" / "fixtures" / "contracts"
SCHEMA_DIR = ROOT / "aqis_lab" / "contracts" / "schemas"
DOCS = ROOT / "docs" / "contracts"

# FR-0.2-01, in the spec's order.
EVENT_FIELDS = ["schema_version", "run_id", "run_card_id", "seq", "component", "event_type", "clip_id",
                "audio_time_s", "wall_time_ns", "wall_clock_utc", "host_id", "payload"]
COMPONENTS = ["vad", "turn_end", "live_stt", "heavy_stt", "emotion", "filler", "analyzer", "fix", "runner"]
EVENT_TYPES = ["run_started", "run_finished", "clip_started", "clip_finished", "speech_start", "speech_end",
               "partial", "final", "timing_mark", "error"]
RUN_LEVEL_TYPES = {"run_started", "run_finished"}
CLIP_TYPES = {"clip_started", "clip_finished", "speech_start", "speech_end", "partial", "final"}
EITHER_LEVEL_TYPES = {"timing_mark", "error"}
# Required payload fields per event type (spec for final and error; plan question 3 for the rest).
PAYLOAD_REQUIRED = {"final": ["text"], "error": ["code", "message", "run_continues"], "partial": ["text"],
                    "timing_mark": ["mark"], "run_finished": ["status"], "run_started": [], "clip_started": [],
                    "clip_finished": [], "speech_start": [], "speech_end": []}
WORD_FIELDS = ["word", "start_s", "end_s"]

# FR-0.2-02 plus deviation D1 (schema_version). Paths use "/" between object members.
RUN_CARD_FIELDS = ["schema_version", "run_card_id", "pack", "model", "processing", "mode", "machine", "seed",
                   "normaliser", "lock", "git", "created_utc", "notes"]
RUN_CARD_NESTED = {"pack": ["manifest_id", "version", "sha256"],
                   "model": ["family", "name", "version", "checksum", "settings"],
                   "processing": ["vad", "stt", "emotion"],
                   "machine": ["platform", "gpu", "cpu_model", "architecture", "os", "python_version"],
                   "normaliser": ["name", "version"],
                   "lock": ["file", "sha256"],
                   "git": ["commit", "dirty"]}
STEP_FIELDS = ["name", "params"]
MODES = ["batch", "realspeed_cpu", "gpu_compute_delay", "tier2_live", "nearlive_replay", "human_session"]
PLATFORMS = ["cloud-vm", "colab", "kaggle", "oracle"]

# FR-0.2-03 plus deviation D1.
MANIFEST_FIELDS = ["schema_version", "manifest_id", "version", "purpose", "created_utc", "clips", "archives"]
CLIP_FIELDS = ["clip_id", "source", "source_ref", "licence", "speaker_id", "consent_ref", "split", "duration_s",
               "sample_rate_hz", "channels", "sha256", "archive", "member_path", "transcript", "recipe", "tags"]
ARCHIVE_FIELDS = ["name", "sha256", "bytes", "n_members"]


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def valid_events():
    return load_jsonl(FIXTURES / "valid_events.jsonl")


def first_event(event_type):
    """A deep copy of the first valid fixture event of this type."""
    for event in valid_events():
        if event["event_type"] == event_type:
            return copy.deepcopy(event)
    raise AssertionError(f"valid_events.jsonl has no {event_type} event")


def valid_run_card():
    return load_json(FIXTURES / "valid_run_card.json")


def valid_manifest():
    return load_json(FIXTURES / "valid_manifest.json")


def pointers(validate, record):
    """Set of JSON Pointers the validator names for record; empty when the record is valid."""
    from aqis_lab.contracts.validate import ContractValidationError
    try:
        result = validate(record)
    except ContractValidationError as exc:
        assert exc.errors, "a ContractValidationError must name at least one field"
        for err in exc.errors:
            assert err.pointer in str(exc), f"the exception message does not name {err.pointer!r}"
        return {err.pointer for err in exc.errors}
    assert result is None
    return set()


def pointer(*parts):
    """RFC 6901 pointer built independently of the code under test."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def get_path(record, parts):
    for p in parts[:-1]:
        record = record[p]
    return record, parts[-1]
