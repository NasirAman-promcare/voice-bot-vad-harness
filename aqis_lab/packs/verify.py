"""pack verify: recompute every hash of a built pack and check every manifest entry, archive member and limit.

CAPABILITIES:
  CAP-PACK-006: verify_pack() checks a pack folder without any source file or network and reports every problem: the manifest parses strictly and passes the WP-0.2 contract and each recipe passes recipe v1; the folder holds exactly the manifest, LICENCES.md, build_record.json and the listed archives, and at most 1,000 entries; each archive matches its size and SHA-256, is at most 200,000,000 bytes, and holds exactly its manifest clips (a changed, missing, extra, duplicate or non-regular member, or an unsafe path, is a problem) with at most 1,000 entries in any folder; each member matches its clip's SHA-256 and is a canonical 16-bit PCM WAV whose rate, channels and duration equal the manifest; LICENCES.md lists every clip with its licence; build_record.json names the manifest's canonical SHA-256; the report ends with the clip counts per category [tests: test_FR_0_4_05_verify_passes_on_built_pack, test_FR_0_4_05_verify_fails_on_changed_member, test_FR_0_4_05_verify_fails_on_missing_member, test_FR_0_4_05_verify_fails_on_extra_member, test_FR_0_4_05_verify_fails_on_changed_or_missing_archive, test_FR_0_4_05_verify_fails_on_extra_file_in_pack_folder, test_FR_0_4_05_verify_fails_on_manifest_entry_mismatch, test_FR_0_4_05_verify_rejects_unsafe_member, test_FR_0_4_05_verify_reports_every_problem, test_FR_0_4_05_verify_checks_recipes_and_build_record, test_FR_0_4_06_verify_fails_on_oversized_archive, test_FR_0_4_06_verify_fails_on_crowded_folder, test_FR_0_4_07_verify_fails_when_a_clip_is_missing]
INPUTS AND OUTPUTS: a pack folder in; a VerifyReport (problems, counts per category, summary line) out;
  VerifyInputError when the folder itself cannot be read.
CONTRACTS: pack-manifest v1; recipe v1 and the pack layout (docs/data/SMOKE_PACK.md).
INVARIANTS:
  - Every check runs on every entry; one problem never stops the others from being reported.
  - Nothing is written or extracted; members are read in memory from the archives.
NOT IN SCOPE:
  - Rebuilding the pack from its sources (aqis_lab/packs/build.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-05 created.
"""
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from aqis_lab.contracts.canonical import CanonicalJSONError, sha256_canonical
from aqis_lab.contracts.validate import ContractValidationError, display_pointer, parse_json, validate_manifest
from aqis_lab.packs import archive, mix
from aqis_lab.packs.audio import WAV_HEADER_BYTES, AudioFormatError, wav_info
from aqis_lab.packs.build import BUILD_RECORD, LICENCES, MANIFEST
from aqis_lab.packs.licences import listed_clips


class VerifyInputError(RuntimeError):
    """The pack folder cannot be read at all."""


@dataclass
class VerifyReport:
    pack_dir: Path
    problems: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    manifest_id: str = "?"
    version: str = "?"
    n_clips: int = 0
    n_archives: int = 0

    @property
    def ok(self):
        return not self.problems

    def summary(self):
        counts = ", ".join(f"{k} {v}" for k, v in self.counts.items())
        state = "OK" if self.ok else f"INVALID, {len(self.problems)} problem(s)"
        return (f"pack {self.manifest_id} {self.version}: {state}, {self.n_clips} clips in {self.n_archives} "
                f"archives; {counts}")


def _safe_member(name):
    path = PurePosixPath(name)
    return (bool(name) and not name.startswith("/") and "\\" not in name and ".." not in path.parts
            and "." not in path.parts and all(ord(c) >= 32 for c in name))


def _check_members(report, archive_entry, data, clips):
    name = archive_entry["name"]
    expected = {clip["member_path"]: clip for clip in clips}
    seen = set()
    paths = []
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
            members = tf.getmembers()
            for member in members:
                where = f"{name}: member {member.name!r}"
                if not _safe_member(member.name):
                    report.problems.append(f"{where}: unsafe path")
                    continue
                if not member.isreg():
                    report.problems.append(f"{where}: not a regular file (links, folders and devices are not allowed)")
                    continue
                if member.name in seen:
                    report.problems.append(f"{where}: appears more than once")
                    continue
                seen.add(member.name)
                paths.append(member.name)
                clip = expected.get(member.name)
                if clip is None:
                    report.problems.append(f"{where}: extra member; no manifest clip names it")
                    continue
                _check_clip_bytes(report, where, tf.extractfile(member).read(), clip)
    except tarfile.TarError as exc:
        report.problems.append(f"{name}: not a readable tar file: {exc}")
        return
    for path in sorted(set(expected) - seen):
        report.problems.append(f"{name}: missing member {path!r} (clip {expected[path]['clip_id']})")
    if archive_entry["n_members"] != len(members):
        report.problems.append(f"{name}: has {len(members)} members, the manifest says {archive_entry['n_members']}")
    for folder, count in archive.folder_entry_counts(paths).items():
        if count > archive.MAX_FILES_PER_FOLDER:
            report.problems.append(f"{name}: folder {folder or '(top)'!r} has {count} entries, more than "
                                   f"{archive.MAX_FILES_PER_FOLDER}")


def _check_clip_bytes(report, where, data, clip):
    sha = hashlib.sha256(data).hexdigest()
    if sha != clip["sha256"]:
        report.problems.append(f"{where}: SHA-256 {sha} differs from clip {clip['clip_id']} ({clip['sha256']})")
    try:
        info = wav_info(data, where)
    except AudioFormatError as exc:
        report.problems.append(str(exc))
        return
    if info.data_offset != WAV_HEADER_BYTES or info.data_offset + info.data_bytes != len(data):
        report.problems.append(f"{where}: not a canonical WAV (44-byte header, then the samples)")
    if info.bits != 16:
        report.problems.append(f"{where}: {info.bits}-bit samples; packs hold 16-bit PCM")
    if info.sample_rate_hz != clip["sample_rate_hz"]:
        report.problems.append(f"{where}: sample rate {info.sample_rate_hz} Hz, the manifest says "
                               f"{clip['sample_rate_hz']}")
    if info.channels != clip["channels"]:
        report.problems.append(f"{where}: {info.channels} channel(s), the manifest says {clip['channels']}")
    duration = info.n_samples / info.sample_rate_hz
    if duration != clip["duration_s"]:
        report.problems.append(f"{where}: lasts {duration} s, the manifest says {clip['duration_s']}")


def verify_pack(pack_dir):
    """Verify a pack folder; returns a VerifyReport (see the module header)."""
    pack = Path(pack_dir)
    if not pack.is_dir():
        raise VerifyInputError(f"{pack} is not a folder")
    report = VerifyReport(pack)
    try:
        manifest = parse_json((pack / MANIFEST).read_bytes(), "manifest")
        validate_manifest(manifest)
    except OSError as exc:
        report.problems.append(f"{MANIFEST}: cannot read: {exc.strerror or exc}")
        return report
    except ContractValidationError as exc:
        report.problems += [f"{MANIFEST}: {display_pointer(e.pointer)}: {e.message}" for e in exc.errors]
        return report
    report.manifest_id, report.version = manifest["manifest_id"], manifest["version"]
    report.n_clips, report.n_archives = len(manifest["clips"]), len(manifest["archives"])
    for clip in manifest["clips"]:
        report.counts[clip["split"]] = report.counts.get(clip["split"], 0) + 1
        if clip["recipe"] is not None:
            report.problems += [f"{MANIFEST}: clip {clip['clip_id']} recipe {p}" for p in mix.recipe_problems(clip["recipe"])]
    entries = sorted(p.name for p in pack.iterdir())
    expected_files = {MANIFEST, LICENCES, BUILD_RECORD} | {a["name"] for a in manifest["archives"]}
    for name in sorted(set(entries) - expected_files):
        report.problems.append(f"{name}: extra file in the pack folder; the manifest does not list it")
    for name in sorted(expected_files - set(entries)):
        report.problems.append(f"{name}: missing from the pack folder")
    if len(entries) > archive.MAX_FILES_PER_FOLDER:
        report.problems.append(f"pack folder has {len(entries)} entries, more than {archive.MAX_FILES_PER_FOLDER}")
    for entry in manifest["archives"]:
        path = pack / entry["name"]
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) > archive.MAX_ARCHIVE_BYTES:
            report.problems.append(f"{entry['name']}: {len(data)} bytes, more than {archive.MAX_ARCHIVE_BYTES}")
        if len(data) != entry["bytes"]:
            report.problems.append(f"{entry['name']}: {len(data)} bytes, the manifest says {entry['bytes']}")
        sha = hashlib.sha256(data).hexdigest()
        if sha != entry["sha256"]:
            report.problems.append(f"{entry['name']}: SHA-256 {sha} differs from the manifest ({entry['sha256']})")
        _check_members(report, entry, data, [c for c in manifest["clips"] if c["archive"] == entry["name"]])
    if (pack / LICENCES).is_file():
        listed = listed_clips((pack / LICENCES).read_text(encoding="utf-8"))
        for clip in manifest["clips"]:
            if listed.get(clip["clip_id"]) != clip["licence"]:
                report.problems.append(f"{LICENCES}: does not list clip {clip['clip_id']} with licence {clip['licence']}")
    if (pack / BUILD_RECORD).is_file():
        try:
            record = json.loads((pack / BUILD_RECORD).read_text(encoding="utf-8"))
            if record.get("manifest_sha256") != sha256_canonical(manifest):
                report.problems.append(f"{BUILD_RECORD}: manifest_sha256 does not match the manifest")
        except (ValueError, CanonicalJSONError, AttributeError) as exc:
            report.problems.append(f"{BUILD_RECORD}: not a readable build record: {exc}")
    return report
