"""pack build: from a pack spec, the registry and the source files to a verified pack folder, byte-identical every time.

CAPABILITIES:
  CAP-PACK-005: build_pack() loads and checks the spec, datasets.yaml and the registry, plans the clips (aqis_lab/packs/select.py), reads every source file once and checks it against its registry SHA-256, sample count and the working format, renders each clip (taken as it is, mixed, cut or generated) as a canonical WAV, rebuilds every derived clip from its recipe to prove the recipe complete, lays the clips out per category in tar shards within the limits, writes manifest.json (validated with the WP-0.2 contract before it is written), LICENCES.md and build_record.json into a staging folder and renames it into place; an existing output or staging folder is never touched, and a failed build leaves nothing behind; on Google Drive it writes only under MyDrive/AQIS_LAB (NFR-0.5-02): the pack folder and its staging folder are checked before anything is read or written, and another Drive path is a BuildError [tests: test_FR_0_4_05_manifest_valid_under_wp_0_2_schema, test_FR_0_4_05_archive_hashes_sizes_and_member_counts_recorded, test_FR_0_4_05_members_in_documented_order, test_FR_0_4_05_build_twice_byte_identical, test_FR_0_4_05_created_utc_comes_from_spec, test_FR_0_4_05_clips_hold_the_source_samples, test_FR_0_4_05_derived_clips_match_their_recipes, test_FR_0_4_05_build_refuses_existing_output, test_FR_0_4_05_build_rejects_source_with_wrong_hash, test_FR_0_4_05_failed_build_leaves_nothing, test_FR_0_4_05_build_record_traces_inputs, test_FR_0_4_06_splits_archives_at_size_limit, test_FR_0_4_06_splits_member_folders_at_1000_files, test_FR_0_4_06_rejects_clip_larger_than_archive_limit, test_NFR_0_5_02_pack_build_refuses_drive_path_outside_aqis_lab]
INPUTS AND OUTPUTS: paths of the spec, output folder, registry, datasets file, cache and repository root in; the
  pack folder and a BuildResult out; BuildError naming the problem.
CONTRACTS: pack-manifest v1 (docs/contracts/PACK_MANIFEST.md); pack spec v1, recipe v1 and the layout
  (docs/data/SMOKE_PACK.md); registry format (docs/data/REGISTRY_FORMAT.md).
INVARIANTS:
  - The output depends only on the spec, the registry rows, datasets.yaml and the source bytes: never on the
    clock, the working folder, the user, the umask, the time zone or PYTHONHASHSEED.
  - Nothing is written outside the staging folder, which becomes the output folder only when complete.
NOT IN SCOPE:
  - Downloading sources (aqis_lab/registry/fetch.py); checking a built pack (aqis_lab/packs/verify.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-05 created.
  2026-09-30 WP-0.7 DEBT-014: build_pack checks the pack folder and its staging folder with
    aqis_lab.drive.check_write_path first (test_NFR_0_5_02_pack_build_refuses_drive_path_outside_aqis_lab).
"""
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aqis_lab import __version__
from aqis_lab.contracts.canonical import sha256_canonical
from aqis_lab.contracts.validate import ContractValidationError, validate_manifest
from aqis_lab.packs import archive, mix
from aqis_lab.packs.audio import WORKING_CHANNELS, WORKING_RATE, AudioFormatError, canonical_wav, decode_flac, read_wav
from aqis_lab.packs.licences import licences_markdown
from aqis_lab.packs.select import SelectionError, plan_pack
from aqis_lab.packs.spec import SpecError, load_spec
from aqis_lab.registry import fetch
from aqis_lab.registry.datasets import DatasetsError, load_datasets
from aqis_lab.registry.registry import RegistryValidationError, load_registry

MANIFEST = "manifest.json"
LICENCES = "LICENCES.md"
BUILD_RECORD = "build_record.json"
PACK_FILES = (MANIFEST, LICENCES, BUILD_RECORD)
BUILDER = f"aqis_lab {__version__} pack builder (recipe {mix.RECIPE_VERSION})"


class BuildError(RuntimeError):
    """A pack cannot be built as its spec says."""


@dataclass(frozen=True)
class BuildResult:
    out: Path
    manifest: dict
    archives: tuple


def json_text(value):
    """The one file form of the pack's JSON files: sorted keys, 2-space indent, UTF-8, final newline."""
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


class _Sources:
    """Source samples by clip_id, each file read once and checked against its registry row."""

    def __init__(self, rows, datasets, cache, repo_root):
        self.rows = {row.clip_id: row for row in rows}
        self.datasets, self.cache, self.repo_root = datasets, Path(cache), Path(repo_root)
        self.samples = {}

    def path(self, row):
        if self.datasets.datasets[row.dataset]["type"] == "download":
            try:
                return fetch.extracted_root(self.cache, row.dataset) / row.source_ref
            except fetch.FetchError as exc:
                raise BuildError(str(exc)) from exc
        return self.repo_root / row.source_ref

    def __call__(self, clip_id):
        if clip_id not in self.samples:
            row = self.rows[clip_id]
            path = self.path(row)
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise BuildError(f"{row.source_ref}: cannot read source file {path}: {exc.strerror or exc}") from exc
            sha = hashlib.sha256(data).hexdigest()
            if sha != row.sha256:
                raise BuildError(f"{row.source_ref}: SHA-256 {sha} differs from the registry ({row.sha256}); the file "
                                 f"changed after it was registered")
            try:
                _, samples = decode_flac(data, row.source_ref) if path.suffix == ".flac" else read_wav(data, row.source_ref)
            except AudioFormatError as exc:
                raise BuildError(str(exc)) from exc
            if len(samples) != row.n_samples:
                raise BuildError(f"{row.source_ref}: has {len(samples)} samples, the registry says {row.n_samples}")
            self.samples[clip_id] = samples
        return self.samples[clip_id]


def _licence_of(sources, datasets):
    if not sources:
        return datasets.generated_licence
    ids = []
    for row in sources:
        if row.licence not in ids:
            ids.append(row.licence)
    return " AND ".join(ids)


def _render(planned, spec, load, datasets):
    """(samples, clip fields without file facts) of one planned clip."""
    sources = planned.sources
    if planned.kind == "take":
        (row,) = sources
        samples, recipe = load(row.clip_id), None
        source, source_ref, speech = row.source, row.source_ref, row
    elif planned.kind == "mix":
        speech_row, noise_row = sources
        speech = speech_row
        segment = load(noise_row.clip_id)[planned.offset:planned.offset + planned.length_samples]
        try:
            result = mix.mix_clip(load(speech_row.clip_id), segment, planned.snr_db)
        except mix.RenderError as exc:
            raise BuildError(f"{planned.clip_id}: {exc}") from exc
        samples = result.samples
        recipe = mix.mix_recipe(speech_row.clip_id, noise_row.clip_id, planned.snr_db, spec.seed, planned.offset,
                                planned.length_samples, result)
        source = "mix"
        source_ref = (f"aqis_lab pack builder: {speech_row.clip_id} mixed with {noise_row.clip_id} at "
                      f"{planned.snr_db} dB SNR")
    elif planned.kind == "excerpt":
        (row,) = sources
        samples = load(row.clip_id)[planned.offset:planned.offset + planned.length_samples]
        recipe = mix.excerpt_recipe(row.clip_id, spec.seed, planned.offset, planned.length_samples)
        source, source_ref, speech = row.source, row.source_ref, None
    else:
        samples = np.zeros(planned.length_samples, dtype=np.int16)
        recipe = mix.silence_recipe(planned.length_samples)
        source, source_ref, speech = "generated", "aqis_lab pack builder: digital silence", None
    if recipe is not None:
        try:
            rebuilt = mix.render_recipe(recipe, load)
        except mix.RenderError as exc:
            raise BuildError(f"{planned.clip_id}: its recipe does not rebuild it: {exc}") from exc
        if not np.array_equal(rebuilt, samples):
            raise BuildError(f"{planned.clip_id}: rebuilding the clip from its recipe gives different samples")
    fields = {
        "clip_id": planned.clip_id, "source": source, "source_ref": source_ref,
        "licence": _licence_of(sources, datasets),
        "speaker_id": speech.speaker_id if speech else None,
        "consent_ref": speech.consent_ref if speech else None,
        "transcript": speech.transcript if speech else None,
        "split": planned.category, "sample_rate_hz": WORKING_RATE, "channels": WORKING_CHANNELS,
        "duration_s": len(samples) / WORKING_RATE, "recipe": recipe, "tags": list(planned.tags),
    }
    return samples, fields


def _file_ref(path):
    data = Path(path).read_bytes()
    return {"name": Path(path).name, "sha256": hashlib.sha256(data).hexdigest()}


def _assemble(spec, plan, load, datasets):
    """(manifest, {archive name: tar bytes}, {clip_id: sources}) of a planned pack."""
    rendered = {}
    for planned in plan:
        samples, fields = _render(planned, spec, load, datasets)
        rendered[planned.clip_id] = (planned, canonical_wav(samples), fields)
    clips, archives, tars = [], [], {}
    for category in spec.categories:
        ids = sorted(k for k, (p, _, _) in rendered.items() if p.category == category.name)
        try:
            paths = archive.member_paths(category.name, ids, spec.max_files_per_folder)
            shards = archive.plan_shards([(path, len(rendered[i][1])) for path, i in zip(paths, ids)],
                                         spec.max_archive_bytes)
        except archive.ArchiveError as exc:
            raise BuildError(str(exc)) from exc
        for number, indexes in enumerate(shards):
            name = archive.archive_name(spec.manifest_id, spec.version, category.name, number)
            members = [(paths[i], rendered[ids[i]][1]) for i in indexes]
            try:
                data = archive.tar_bytes(members, spec.created_epoch)
            except archive.ArchiveError as exc:
                raise BuildError(str(exc)) from exc
            tars[name] = data
            archives.append({"name": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                             "n_members": len(members)})
            for i in indexes:
                _, wav, fields = rendered[ids[i]]
                clips.append(dict(fields, sha256=hashlib.sha256(wav).hexdigest(), archive=name,
                                  member_path=paths[i]))
    manifest = {"schema_version": "1.0", "manifest_id": spec.manifest_id, "version": spec.version,
                "purpose": spec.purpose, "created_utc": spec.created_utc, "clips": clips, "archives": archives}
    return manifest, tars, {k: p.sources for k, (p, _, _) in rendered.items()}


def build_pack(spec_path, out_dir, registry_path, datasets_path, cache_dir, repo_root):
    """Build a pack folder at out_dir (see the module header); returns BuildResult or raises BuildError."""
    from aqis_lab.drive import DriveError, check_write_path
    from aqis_lab.platform import PlatformError
    out = Path(out_dir)
    staging = out.parent / f".{out.name}.partial"
    try:
        for path in (out, staging):          # NFR-0.5-02: on Google Drive, only under MyDrive/AQIS_LAB
            check_write_path(path)
    except (DriveError, PlatformError) as exc:
        raise BuildError(str(exc)) from exc
    if out.exists():
        raise BuildError(f"{out} already exists; a built pack is never overwritten (choose a new folder or version)")
    if staging.exists():
        raise BuildError(f"staging folder {staging} exists, probably from an interrupted build; remove it first")
    try:
        spec = load_spec(spec_path)
        datasets = load_datasets(datasets_path)
        rows = load_registry(registry_path, datasets, repo_root)
        plan = plan_pack(spec, rows, datasets)
    except (SpecError, DatasetsError, RegistryValidationError, SelectionError) as exc:
        raise BuildError(str(exc)) from exc
    load = _Sources(rows, datasets, cache_dir, repo_root)
    manifest, tars, clip_sources = _assemble(spec, plan, load, datasets)
    try:
        validate_manifest(manifest)
    except ContractValidationError as exc:
        raise BuildError(f"the manifest would break the pack manifest contract:\n{exc}") from exc
    if len(tars) + len(PACK_FILES) > spec.max_files_per_folder:
        raise BuildError(f"the pack folder would hold {len(tars) + len(PACK_FILES)} files, more than "
                         f"{spec.max_files_per_folder}")
    record = {"record_version": "1.0", "builder": BUILDER, "pack_spec": _file_ref(spec_path),
              "registry": _file_ref(registry_path), "datasets": _file_ref(datasets_path), "seed": spec.seed,
              "manifest_id": spec.manifest_id, "version": spec.version,
              "manifest_sha256": sha256_canonical(manifest)}
    files = dict(tars)
    files[MANIFEST] = json_text(manifest).encode("utf-8")
    files[LICENCES] = licences_markdown(spec, manifest, clip_sources, datasets).encode("utf-8")
    files[BUILD_RECORD] = json_text(record).encode("utf-8")
    try:
        staging.mkdir(parents=True)
        for name in sorted(files):
            (staging / name).write_bytes(files[name])
        staging.rename(out)
    except OSError as exc:
        if staging.exists():
            shutil.rmtree(staging)
        raise BuildError(f"cannot write the pack to {out}: {exc.strerror or exc}") from exc
    return BuildResult(out, manifest, tuple(a["name"] for a in manifest["archives"]))
