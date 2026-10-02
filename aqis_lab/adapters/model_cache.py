"""Pinned model downloads: fetch a model into a local cache and verify it by size and SHA-256 before any use.

CAPABILITIES:
  CAP-MODEL-001: load_pins() reads config/aqis_lab/models.yaml strictly (schema_version 1.0; for each model url, kind zip or file, bytes, lowercase SHA-256, licence, optional revision; a zip also names its root folder and every member file with its SHA-256 and size); any unknown, missing or malformed key is a ModelCacheError naming the model [tests: test_FR_0_7_02_committed_pins_load_and_match_the_plan, test_FR_0_7_02_pins_file_is_checked]
  CAP-MODEL-002: fetch() downloads a pinned model to <cache>/<name>/<first 16 hex of its SHA-256>/ on local disk: the download is checked for size and SHA-256 before anything is extracted, a zip is extracted through a staging folder and every member is checked against its own pin (no member missing, extra, changed or outside the model folder), the files are made read-only, a marker is written and later fetches reuse the verified folder after verifying it again; a mismatch raises ModelChecksumError and leaves nothing behind but the verified models already there; a cache on a Google Drive mount is refused [tests: test_FR_0_7_02_model_downloaded_to_cache_and_verified_from_local_source, test_FR_0_7_02_model_rejected_when_checksum_differs, test_FR_0_7_02_model_rejected_when_size_differs, test_FR_0_7_02_member_that_differs_from_its_pin_is_rejected, test_FR_0_7_02_extra_or_missing_member_is_rejected, test_FR_0_7_02_member_outside_the_model_folder_is_rejected, test_FR_0_7_02_single_file_model_pinned_by_size_and_sha, test_FR_0_7_02_cache_on_drive_is_refused, test_FR_0_7_02_unreachable_source_is_a_download_error, test_FR_0_7_02_model_downloaded_to_cache_and_verified]
  CAP-MODEL-003: verify() checks a fetched model's files against the pin again (at every load), raising ModelChecksumError naming each changed, missing or extra file [tests: test_FR_0_7_02_changed_model_file_rejected_at_load]
INPUTS AND OUTPUTS: a ModelPin and a cache folder in; the verified model folder (zip) or file (file) out;
  ModelCacheError (code model-download) or ModelChecksumError (code model-checksum) on failure.
CONTRACTS: config/aqis_lab/models.yaml (schema_version 1.0).
INVARIANTS:
  - Nothing unverified is ever returned: size and SHA-256 are checked before extraction, every file after it.
  - Only the cache's own .partial and .staging-* entries are ever removed.
  - The cache is on local disk (docs/progress/WP-0.7/PLAN.md, question 12 (a)).
NOT IN SCOPE:
  - Loading a model into its library (the adapters).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-02 created.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import yaml

from aqis_lab import drive
from aqis_lab.adapters.base import AdapterError

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PINS = REPO_ROOT / "config" / "aqis_lab" / "models.yaml"
DEFAULT_CACHE = REPO_ROOT / "data" / "raw" / "aqis_lab" / "models"
SCHEMA_VERSION = "1.0"
MARKER = ".verified.json"
KINDS = ("zip", "file")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
CHUNK = 1 << 20
TIMEOUT_S = 120
COMMON_KEYS = {"url", "kind", "bytes", "sha256", "licence"}
OPTIONAL_KEYS = {"revision"}
ZIP_KEYS = {"root", "files"}


class ModelCacheError(AdapterError):
    """A model could not be fetched or its pins are unusable."""

    def __init__(self, message, code="model-download"):
        super().__init__(code, message)


class ModelChecksumError(ModelCacheError):
    """A model file's size or SHA-256 differs from its pin."""

    def __init__(self, message):
        super().__init__(message, code="model-checksum")


@dataclass(frozen=True)
class ModelPin:
    name: str
    url: str
    kind: str
    bytes: int
    sha256: str
    licence: str
    root: str | None
    files: dict | None
    revision: str | None

    @property
    def filename(self):
        return PurePosixPath(urllib.request.url2pathname(self.url.split("?", 1)[0])).name


def _safe_rel(rel):
    parts = PurePosixPath(rel).parts
    return bool(parts) and not rel.startswith("/") and "\\" not in rel and all(p not in ("", ".", "..") for p in parts)


def _check_hash_entry(name, where, entry):
    if not isinstance(entry, dict) or set(entry) != {"sha256", "bytes"}:
        raise ModelCacheError(f"models.yaml, model {name}: {where} must have exactly sha256 and bytes")
    if not isinstance(entry["sha256"], str) or not SHA_RE.match(entry["sha256"]):
        raise ModelCacheError(f"models.yaml, model {name}: {where} sha256 must be 64 lowercase hex characters")
    if type(entry["bytes"]) is not int or entry["bytes"] < 0:
        raise ModelCacheError(f"models.yaml, model {name}: {where} bytes must be an integer >= 0")


def _pin(name, entry):
    if not NAME_RE.match(name):
        raise ModelCacheError(f"models.yaml: model name {name!r} must be lowercase letters, digits, '.', '_', '-'")
    if not isinstance(entry, dict):
        raise ModelCacheError(f"models.yaml, model {name}: not a mapping")
    kind = entry.get("kind")
    if kind not in KINDS:
        raise ModelCacheError(f"models.yaml, model {name}: kind must be one of {', '.join(KINDS)}, got {kind!r}")
    allowed = COMMON_KEYS | OPTIONAL_KEYS | (ZIP_KEYS if kind == "zip" else set())
    required = COMMON_KEYS | (ZIP_KEYS if kind == "zip" else set())
    unknown, missing = sorted(set(entry) - allowed), sorted(required - set(entry))
    if unknown or missing:
        raise ModelCacheError(f"models.yaml, model {name}: unknown key(s) {unknown}, missing key(s) {missing}")
    _check_hash_entry(name, "the download", {"sha256": entry["sha256"], "bytes": entry["bytes"]})
    for key in ("url", "licence") + (("revision",) if "revision" in entry else ()):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise ModelCacheError(f"models.yaml, model {name}: {key} must be non-empty text")
    files = root = None
    if kind == "zip":
        root, files = entry["root"], entry["files"]
        if not isinstance(root, str) or not _safe_rel(root) or "/" in root:
            raise ModelCacheError(f"models.yaml, model {name}: root must be one folder name")
        if not isinstance(files, dict) or not files:
            raise ModelCacheError(f"models.yaml, model {name}: files must list every member")
        for rel, value in files.items():
            if not isinstance(rel, str) or not _safe_rel(rel):
                raise ModelCacheError(f"models.yaml, model {name}: unsafe member path {rel!r}")
            _check_hash_entry(name, f"file {rel}", value)
        files = {rel: dict(value) for rel, value in files.items()}
    return ModelPin(name=name, url=entry["url"], kind=kind, bytes=entry["bytes"], sha256=entry["sha256"],
                    licence=entry["licence"], root=root, files=files, revision=entry.get("revision"))


def load_pins(path=DEFAULT_PINS):
    """{model name: ModelPin} from models.yaml; ModelCacheError on any problem."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ModelCacheError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "models"}:
        raise ModelCacheError(f"{path}: needs exactly the keys schema_version and models")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ModelCacheError(f"{path}: schema_version must be {SCHEMA_VERSION!r}, got {data['schema_version']!r}")
    if not isinstance(data["models"], dict) or not data["models"]:
        raise ModelCacheError(f"{path}: models must be a non-empty mapping")
    return {name: _pin(name, entry) for name, entry in data["models"].items()}


def _sha_file(path):
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _download(pin, partial):
    request = urllib.request.Request(pin.url, headers={"User-Agent": "aqis-lab-model-cache/1.0"})
    digest, size = hashlib.sha256(), 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response, open(partial, "wb") as out:
            while chunk := response.read(CHUNK):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        partial.unlink(missing_ok=True)
        raise ModelCacheError(f"cannot download model {pin.name} from {pin.url}: {exc}") from exc
    if size != pin.bytes:
        partial.unlink()
        raise ModelChecksumError(f"model {pin.name}: download from {pin.url} has {size} bytes, the pin says "
                                 f"{pin.bytes} bytes (config/aqis_lab/models.yaml); nothing was kept")
    if digest.hexdigest() != pin.sha256:
        partial.unlink()
        raise ModelChecksumError(f"model {pin.name}: download from {pin.url} has SHA-256 {digest.hexdigest()}, the "
                                 f"pin says {pin.sha256} (config/aqis_lab/models.yaml); nothing was kept")


def _problems(pin, folder):
    """Every difference between a model folder (zip kind) and its per-file pins."""
    problems = []
    found = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != MARKER}
    for rel in sorted(found - set(pin.files)):
        problems.append(f"{rel} is not in the pin")
    for rel in sorted(set(pin.files) - found):
        problems.append(f"{rel} is missing")
    for rel in sorted(found & set(pin.files)):
        digest, size = _sha_file(folder / rel)
        want = pin.files[rel]
        if size != want["bytes"] or digest != want["sha256"]:
            problems.append(f"{rel} has {size} bytes and SHA-256 {digest}, the pin says {want['bytes']} bytes and "
                            f"{want['sha256']}")
    return problems


def verify(pin, target):
    """ModelChecksumError unless the fetched model at `target` still equals its pin."""
    target = Path(target)
    if pin.kind == "file":
        if not target.is_file():
            raise ModelChecksumError(f"model {pin.name}: {target} is missing")
        digest, size = _sha_file(target)
        if size != pin.bytes or digest != pin.sha256:
            raise ModelChecksumError(f"model {pin.name}: {target} has {size} bytes and SHA-256 {digest}, the pin says "
                                     f"{pin.bytes} bytes and {pin.sha256}")
        return target
    problems = _problems(pin, target) if target.is_dir() else [f"{target} is missing"]
    if problems:
        raise ModelChecksumError(f"model {pin.name} in {target} differs from its pin: " + "; ".join(problems))
    return target


def _extract(pin, archive, staging):
    prefix = pin.root + "/"
    try:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name = info.filename
                if name.endswith("/"):
                    if name != prefix and not (name.startswith(prefix) and _safe_rel(name[len(prefix):-1])):
                        raise ModelChecksumError(f"model {pin.name}: archive folder {name} is outside {pin.root}/")
                    continue
                rel = name[len(prefix):] if name.startswith(prefix) else ""
                if not rel or not _safe_rel(rel):
                    raise ModelChecksumError(f"model {pin.name}: archive member {name} is outside {pin.root}/")
                if rel not in pin.files:
                    raise ModelChecksumError(f"model {pin.name}: archive member {rel} is not in the pin")
                out = staging / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "xb") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ModelChecksumError(f"model {pin.name}: cannot extract {archive}: {exc}") from exc
    problems = _problems(pin, staging)
    if problems:
        raise ModelChecksumError(f"model {pin.name} extracted from {pin.url} differs from its pin: "
                                 + "; ".join(problems))


def _read_only(path):
    for item in ([path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]):
        item.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def fetch(pin, cache_dir=DEFAULT_CACHE, system=None):
    """The verified local copy of `pin` (a folder for kind zip, the file for kind file), downloading it if needed."""
    cache = Path(cache_dir)
    if drive.drive_mount_of(cache, system) is not None:
        raise ModelCacheError(f"the model cache {cache} is on a Google Drive mount; models are kept on local disk "
                              f"only (copy then compute; docs/adapters/VOSK.md)")
    home = cache / pin.name
    folder = home / pin.sha256[:16]
    target = folder / pin.filename if pin.kind == "file" else folder
    if (folder / MARKER).is_file():
        try:
            marker = json.loads((folder / MARKER).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ModelChecksumError(f"model {pin.name}: marker {folder / MARKER} is unreadable: {exc}") from exc
        if marker.get("sha256") != pin.sha256:
            raise ModelChecksumError(f"model {pin.name}: {folder} was verified for {marker.get('sha256')}, not "
                                     f"{pin.sha256}")
        return verify(pin, target)
    if folder.exists():
        raise ModelCacheError(f"model {pin.name}: {folder} exists without its verification marker; move it aside "
                              f"and fetch again")
    home.mkdir(parents=True, exist_ok=True)
    partial = home / f"{pin.filename}.partial"
    staging = home / f".staging-{pin.sha256[:16]}"
    if staging.exists():
        shutil.rmtree(staging)
    _download(pin, partial)
    staging.mkdir()
    try:
        if pin.kind == "zip":
            _extract(pin, partial, staging)
        else:
            os.replace(partial, staging / pin.filename)
        _read_only(staging)
        marker = {"model": pin.name, "sha256": pin.sha256, "bytes": pin.bytes, "url": pin.url,
                  "verified_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        (staging / MARKER).write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(staging, folder)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        partial.unlink(missing_ok=True)
        raise
    partial.unlink(missing_ok=True)
    return target
