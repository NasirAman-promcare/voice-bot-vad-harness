"""The source datasets and the licence table (data/registry/datasets.yaml), loaded strictly.

CAPABILITIES:
  CAP-REG-002: load_datasets() reads datasets.yaml with duplicate keys rejected, checks it against datasets.v1.json (each dataset against the schema of its importer) and checks that every licence it names is in its licence table, that local paths are safe relative paths and that only the owner importer produces sources that need consent; load_yaml_strict() is the duplicate-rejecting YAML loader the pack spec uses too [tests: test_FR_0_4_01_datasets_file_rejects_unknown_licence_and_keys, test_FR_0_4_01_committed_datasets_file_is_valid]
INPUTS AND OUTPUTS: a YAML file path in; a Datasets value (licences, datasets, the licence of generated clips)
  out; DatasetsError naming the file and every problem.
CONTRACTS: datasets.yaml format 1 (docs/data/REGISTRY_FORMAT.md, aqis_lab/registry/schemas/datasets.v1.json).
INVARIANTS:
  - Never fills in a missing value: every field the schema requires must be present.
  - A licence ID used anywhere must be defined in the file's licence table.
NOT IN SCOPE:
  - Downloading (aqis_lab/registry/fetch.py); turning files into registry rows (aqis_lab/registry/importers.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-01 created.
"""
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).resolve().parent / "schemas" / "datasets.v1.json").read_text(encoding="utf-8"))
CONSENT_SOURCES = ("owner", "campaign")


class DatasetsError(ValueError):
    """datasets.yaml (or another strict YAML file) is unreadable or invalid."""


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last one."""


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise DatasetsError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml_strict(path):
    """Parse a YAML file with duplicate keys rejected; DatasetsError names the file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DatasetsError(f"cannot read {path}: {exc}") from exc
    try:
        return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - _StrictLoader is a SafeLoader subclass
    except DatasetsError as exc:
        raise DatasetsError(f"{path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DatasetsError(f"{path}: not valid YAML: {exc}") from exc


def schema_problems(schema, value, defs_ref=None, prefix=""):
    """Sorted 'pointer: message' strings for every schema error of value (against schema or one of its $defs)."""
    target = schema if defs_ref is None else {"$defs": schema["$defs"], "$ref": f"#/$defs/{defs_ref}"}
    validator = Draft202012Validator(target)
    out = []
    for err in validator.iter_errors(value):
        pointer = prefix + "".join(f"/{p}" for p in err.absolute_path)
        out.append(f"{pointer or '(top level)'}: {err.message}")
    return sorted(out)


@dataclass(frozen=True)
class Licence:
    licence_id: str
    name: str
    url: str
    attribution_required: bool
    share_alike: bool
    non_commercial: bool


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    fields: dict

    def __getitem__(self, key):
        return self.fields[key]

    def get(self, key, default=None):
        return self.fields.get(key, default)

    @property
    def splits(self):
        if self.fields["importer"] == "musan":
            return tuple(sorted({sub["split"] for sub in self.fields["subsets"].values()}))
        return (self.fields["split"],)

    def licence_for_split(self, split):
        if self.fields["importer"] == "musan":
            for sub in self.fields["subsets"].values():
                if sub["split"] == split:
                    return sub["licence"]
        return self.fields["licence"]


@dataclass(frozen=True)
class Datasets:
    path: Path
    licences: dict
    datasets: dict
    generated_licence: str

    def licence(self, licence_id):
        return self.licences[licence_id]


def _safe_relative(text):
    path = PurePosixPath(text)
    return not path.is_absolute() and "\\" not in text and all(part not in ("", ".", "..") for part in text.split("/"))


def load_datasets(path):
    """Load and check datasets.yaml; returns Datasets or raises DatasetsError listing every problem."""
    path = Path(path)
    doc = load_yaml_strict(path)
    problems = schema_problems(SCHEMA, doc)
    if not problems:
        for dataset_id, entry in doc["datasets"].items():
            problems += schema_problems(SCHEMA, entry, f"dataset_{entry['importer']}", f"/datasets/{dataset_id}")
    if problems:
        raise DatasetsError(f"{path} is invalid:\n  " + "\n  ".join(problems))
    licences = {lid: Licence(lid, v["name"], v["url"], v["attribution_required"], v["share_alike"],
                             v["non_commercial"]) for lid, v in doc["licences"].items()}
    used = [("/generated_licence", doc["generated_licence"])]
    for dataset_id, entry in doc["datasets"].items():
        used.append((f"/datasets/{dataset_id}/licence", entry["licence"]))
        for sub_id, sub in entry.get("subsets", {}).items():
            used.append((f"/datasets/{dataset_id}/subsets/{sub_id}/licence", sub["licence"]))
        for key in ("folder", "generation_record", "consent_file"):
            if key in entry and not _safe_relative(entry[key]):
                problems.append(f"/datasets/{dataset_id}/{key}: {entry[key]!r} is not a safe relative path")
        needs_consent = entry["source"] in CONSENT_SOURCES
        if needs_consent != (entry["importer"] == "owner"):
            problems.append(f"/datasets/{dataset_id}/source: {entry['source']!r} with importer "
                            f"{entry['importer']!r}: only the owner importer may produce sources "
                            f"{list(CONSENT_SOURCES)}, which need a consent reference")
    for pointer, licence_id in used:
        if licence_id not in licences:
            problems.append(f"{pointer}: licence {licence_id!r} is not defined in /licences")
    if problems:
        raise DatasetsError(f"{path} is invalid:\n  " + "\n  ".join(sorted(problems)))
    datasets = {dataset_id: Dataset(dataset_id, entry) for dataset_id, entry in sorted(doc["datasets"].items())}
    return Datasets(path, licences, datasets, doc["generated_licence"])
