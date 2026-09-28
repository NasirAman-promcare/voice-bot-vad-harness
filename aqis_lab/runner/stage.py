"""Copy then compute: copy a pack to local disk, verify every hash, extract it there, and read clips back checked.

CAPABILITIES:
  CAP-RUN-001: stage_pack() copies a pack folder (from Drive or the repository) into <work>/packs/<id>/<version>/pack on local disk through a staging folder, runs verify_pack on the copy, extracts every archive into clips/ with each clip's SHA-256 checked, writes the .staged marker and renames the folder into place; a failed verification stages nothing; a valid marker for the same manifest means nothing is copied again; a work folder on a Drive mount is refused [tests: test_FR_0_5_04_stages_repository_pack_to_local_disk, test_FR_0_5_04_stages_pack_from_drive_folder, test_FR_0_5_04_rejects_changed_archive_and_stages_nothing, test_FR_0_5_04_interrupted_staging_is_redone, test_FR_0_5_04_restaging_a_staged_pack_copies_nothing, test_FR_0_5_04_work_dir_on_drive_is_refused, test_FR_0_5_04_changed_source_manifest_is_staged_again, test_FR_0_5_04_archive_hash_mismatch_with_intact_members_stages_nothing]
  CAP-RUN-002: StagedPack.read_clip() reads a clip only from the local extracted copy and raises ClipError when its SHA-256 differs from the manifest [tests: test_FR_0_5_04_run_reads_only_local_extracted_clips, test_FR_0_5_04_changed_extracted_clip_stops_the_run]
INPUTS AND OUTPUTS: a pack folder (manifest.json, LICENCES.md, build_record.json, archives) and a local work folder
  in; a StagedPack out; StageError when the pack cannot be staged.
CONTRACTS: pack-manifest v1; the pack layout (docs/data/SMOKE_PACK.md); run folder docs in docs/runner/RUNNER.md.
INVARIANTS:
  - Only a folder with a valid .staged marker is ever processed; an interrupted staging never counts.
  - Nothing is extracted before the copied archives pass verify_pack.
  - Only local work folders are changed or removed; the pack source is only read.
NOT IN SCOPE:
  - Checking a pack in place (aqis_lab/packs/verify.py, reused here).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-04 created.
  2026-09-28 WP-0.5 NFR-0.5-01: a staged pack whose marker names exactly the source's manifest bytes is reused
             without validating those bytes again (they were validated and verified when staged).
  2026-09-28 WP-0.5 round 2 F06, F07: header lists the reuse and archive-hash tests (header only).
"""
import hashlib
import json
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from aqis_lab import drive
from aqis_lab.contracts.canonical import sha256_canonical
from aqis_lab.contracts.validate import ContractValidationError, display_pointer, parse_json, validate_manifest
from aqis_lab.packs.build import BUILD_RECORD, LICENCES, MANIFEST
from aqis_lab.packs.verify import VerifyInputError, verify_pack

STAGE_VERSION = "1.0"
STAGED_MARKER = ".staged"
PACK_DIR = "pack"
CLIPS_DIR = "clips"


class StageError(RuntimeError):
    """The pack cannot be staged on local disk."""


class ClipError(RuntimeError):
    """A staged clip is missing, unreadable or not the bytes the manifest names."""


@dataclass
class StagedPack:
    root: Path
    manifest: dict
    manifest_sha256: str
    fresh: bool

    def clip_path(self, clip):
        return self.root / CLIPS_DIR / clip["member_path"]

    def read_clip(self, clip):
        """The clip's bytes from the local extracted copy, checked against the manifest's SHA-256."""
        path = self.clip_path(clip)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ClipError(f"clip {clip['clip_id']}: cannot read {path}: {exc.strerror or exc}") from exc
        digest = hashlib.sha256(data).hexdigest()
        if digest != clip["sha256"]:
            raise ClipError(f"clip {clip['clip_id']}: {path} has sha256 {digest}, the manifest says {clip['sha256']}; "
                            f"the staged copy changed (restage the pack)")
        return data


def read_manifest_bytes(source):
    path = Path(source) / MANIFEST
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StageError(f"cannot read {path}: {exc.strerror or exc}") from exc


def read_manifest(source, data=None):
    """The pack manifest at `source`, parsed strictly and validated against pack-manifest v1."""
    path = Path(source) / MANIFEST
    data = read_manifest_bytes(source) if data is None else data
    try:
        manifest = parse_json(data, "manifest")
        validate_manifest(manifest)
    except ContractValidationError as exc:
        raise StageError(f"{path} is not a valid pack manifest: " + "; ".join(
            f"{display_pointer(e.pointer)}: {e.message}" for e in exc.errors)) from exc
    return manifest


def _marker_for(manifest, data):
    return {"stage_version": STAGE_VERSION, "manifest_id": manifest["manifest_id"], "version": manifest["version"],
            "manifest_sha256": sha256_canonical(manifest), "manifest_file_sha256": hashlib.sha256(data).hexdigest(),
            "archives": {a["name"]: a["sha256"] for a in manifest["archives"]}, "clips": len(manifest["clips"])}


def _read_marker(root):
    try:
        marker = json.loads((root / STAGED_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return marker if isinstance(marker, dict) else None


def _reuse(source, work_dir, data):
    """The already staged pack when its marker names exactly these manifest bytes, else None.

    Identical bytes were parsed, validated and verified when the pack was staged, so they are not validated again;
    the staged copy of the manifest is checked against the marker's hashes before it is used.
    """
    try:
        head = json.loads(data)
        dest = Path(work_dir) / "packs" / head["manifest_id"] / head["version"]
    except (ValueError, TypeError, KeyError):
        return None
    marker = _read_marker(dest) if dest.is_dir() else None
    if not marker or marker.get("stage_version") != STAGE_VERSION or \
            marker.get("manifest_file_sha256") != hashlib.sha256(data).hexdigest():
        return None
    try:
        staged_bytes = (dest / PACK_DIR / MANIFEST).read_bytes()
    except OSError:
        return None
    if staged_bytes != data:
        return None
    manifest = json.loads(staged_bytes)
    if _marker_for(manifest, staged_bytes) != marker:
        return None
    return StagedPack(dest, manifest, marker["manifest_sha256"], fresh=False)


def _remove_local(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _extract(archive_path, clips_dir, clips_by_member):
    with tarfile.open(archive_path, "r:") as tar:
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile():
                raise StageError(f"{archive_path.name}: unsafe or non-file member {member.name!r}")
            clip = clips_by_member.get(member.name)
            if clip is None:
                raise StageError(f"{archive_path.name}: member {member.name} is not a clip of the manifest")
            data = tar.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != clip["sha256"]:
                raise StageError(f"{archive_path.name}: member {member.name} does not match clip {clip['clip_id']}")
            target = clips_dir / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def stage_pack(source, work_dir, system=None):
    """Stage the pack at `source` into `work_dir` (local disk) and return a StagedPack."""
    source = Path(source)
    work_dir = Path(work_dir)
    if drive.drive_mount_of(work_dir, system) is not None:
        raise StageError(f"work folder {work_dir} is on Google Drive; packs are copied to and processed on local disk "
                         f"(choose a --work-dir outside the Drive mount)")
    data = read_manifest_bytes(source)
    reused = _reuse(source, work_dir, data)
    if reused is not None:
        return reused
    manifest = read_manifest(source, data)
    marker = _marker_for(manifest, data)
    dest = work_dir / "packs" / manifest["manifest_id"] / manifest["version"]
    parent = drive.make_dirs(dest.parent, system)
    staging = parent / f".staging-{manifest['version']}"
    _remove_local(staging)                       # an interrupted staging of this version (local disk only)
    (staging / PACK_DIR).mkdir(parents=True)
    names = [MANIFEST, LICENCES, BUILD_RECORD] + [a["name"] for a in manifest["archives"]]
    try:
        for name in names:
            shutil.copyfile(source / name, staging / PACK_DIR / name)
        try:
            report = verify_pack(staging / PACK_DIR)
        except VerifyInputError as exc:
            raise StageError(f"cannot verify the copy of {source}: {exc}") from exc
        if not report.ok:
            raise StageError(f"the pack copied from {source} failed verification ({len(report.problems)} problem(s)): "
                             + "; ".join(report.problems))
        if read_manifest_bytes(staging / PACK_DIR) != data:
            raise StageError(f"{source / MANIFEST} changed while it was being copied")
        by_member = {c["member_path"]: c for c in manifest["clips"]}
        for archive in manifest["archives"]:
            _extract(staging / PACK_DIR / archive["name"], staging / CLIPS_DIR, by_member)
        missing = [c["clip_id"] for c in manifest["clips"] if not (staging / CLIPS_DIR / c["member_path"]).is_file()]
        if missing:
            raise StageError(f"clips missing after extraction: {', '.join(missing)}")
        drive.write_bytes(staging / STAGED_MARKER, (json.dumps(marker, sort_keys=True, indent=2) + "\n").encode(),
                          system)
    except (OSError, tarfile.TarError, StageError) as exc:
        _remove_local(staging)
        if isinstance(exc, StageError):
            raise
        raise StageError(f"cannot stage {source} into {work_dir}: {exc}") from exc
    _remove_local(dest)                          # a folder here without a valid marker never counted as staged
    staging.rename(dest)
    return StagedPack(dest, manifest, marker["manifest_sha256"], fresh=True)
