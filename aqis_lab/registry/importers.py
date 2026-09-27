"""Registry import: turn fetched datasets and local folders into registry rows, checking every file on the way.

CAPABILITIES:
  CAP-REG-004: build_registry() imports every dataset of datasets.yaml and returns validated, sorted RegistryRow values: LibriSpeech (one row per FLAC utterance, transcript from its chapter's trans.txt, one-to-one), MUSAN subsets (subset LICENSE file checked against its pin, background tags from free-sound ANNOTATIONS, genre and vocals tags from music ANNOTATIONS, per-track attribution from the rfm LICENSE titles), synthetic TTS folders (transcripts.csv and the GENERATION.md table must agree on every file, text and SHA-256) and owner-recording folders (transcripts.csv one-to-one, consent file present); every audio file must be 16 kHz mono 16-bit, file names lowercase letters, digits and hyphens [tests: test_FR_0_4_01_librispeech_rows_from_archive, test_FR_0_4_01_musan_rows_carry_subset_licence_and_titles, test_FR_0_4_01_musan_licence_file_must_match_its_pin, test_FR_0_4_01_tts_rows_carry_synthetic_voice_and_apache_licence, test_FR_0_4_01_tts_rows_match_generation_record, test_FR_0_4_01_owner_import_rows_have_consent, test_FR_0_4_01_owner_import_rejects_bad_inputs, test_FR_0_4_01_librispeech_rejects_missing_transcript, test_FR_0_4_01_build_requires_fetched_datasets, test_FR_0_4_01_build_is_deterministic]
INPUTS AND OUTPUTS: a Datasets value, the fetch cache and the repository root in; a sorted list of RegistryRow
  out; SourceImportError naming the dataset, the file and the problem.
CONTRACTS: registry format and datasets.yaml format 1 (docs/data/REGISTRY_FORMAT.md).
INVARIANTS:
  - Never corrects or guesses: a missing transcript, an unmatched file, a changed licence file or a file in another
    format is an error, never skipped.
  - Rows depend only on file contents, never on listing order, the clock or the environment.
NOT IN SCOPE:
  - Downloading (aqis_lab/registry/fetch.py); the validation rules (aqis_lab/registry/registry.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-01 created.
"""
import csv
import hashlib
import io
import re
from pathlib import Path

from aqis_lab.packs.audio import AudioFormatError, flac_info, require_working_format, wav_info
from aqis_lab.registry import fetch
from aqis_lab.registry.registry import RegistryRow, check_rows

FILE_NAME_RE = re.compile(r"[a-z0-9-]+\.wav")
TAG_RE = re.compile(r"[^a-z0-9]+")


class SourceImportError(ValueError):
    """A dataset's files cannot be turned into valid registry rows."""


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _tag(text):
    return TAG_RE.sub("-", text.lower()).strip("-")


def _audio_facts(path, where, flac=False):
    head = path.read_bytes()
    try:
        info = flac_info(head, where)[0] if flac else wav_info(head, where)
        require_working_format(info, where)
    except AudioFormatError as exc:
        raise SourceImportError(str(exc)) from exc
    if info.n_samples < 1:
        raise SourceImportError(f"{where}: has no samples")
    return info, hashlib.sha256(head).hexdigest()


# ---------------------------------------------------------------------------------------------
# LibriSpeech
# ---------------------------------------------------------------------------------------------
def _librispeech(dataset, root):
    split = dataset["split"]
    base = root / "LibriSpeech" / split
    if not base.is_dir():
        raise SourceImportError(f"{dataset.dataset_id}: folder LibriSpeech/{split} is missing from the extraction")
    rows = []
    for trans in sorted(base.glob("*/*/*.trans.txt")):
        rel_dir = trans.parent.relative_to(root).as_posix()
        spk, chap = trans.parent.parent.name, trans.parent.name
        texts = {}
        for number, line in enumerate(trans.read_text(encoding="utf-8").splitlines(), start=1):
            utt, sep, text = line.partition(" ")
            if not sep or not text.strip() or not re.fullmatch(rf"{spk}-{chap}-[0-9]+", utt):
                raise SourceImportError(f"{rel_dir}/{trans.name} line {number}: not '<utterance> <TEXT>' for "
                                        f"speaker {spk}, chapter {chap}: {line!r}")
            if utt in texts:
                raise SourceImportError(f"{rel_dir}/{trans.name}: utterance {utt} is listed twice")
            texts[utt] = text
        flacs = {p.stem: p for p in trans.parent.glob("*.flac")}
        for utt in sorted(set(flacs) - set(texts)):
            raise SourceImportError(f"{rel_dir}/{utt}.flac has no transcript in {trans.name}")
        for utt in sorted(set(texts) - set(flacs)):
            raise SourceImportError(f"{rel_dir}/{trans.name} lists {utt}, but there is no FLAC file for it")
        for utt in sorted(texts):
            source_ref = f"{rel_dir}/{utt}.flac"
            info, sha = _audio_facts(flacs[utt], source_ref, flac=True)
            rows.append(RegistryRow(
                clip_id=f"ls-{split}-{utt}", source=dataset["source"], source_ref=source_ref,
                licence=dataset["licence"], speaker_id=spk, consent_ref=None, transcript=texts[utt], split=split,
                dataset=dataset.dataset_id, tags=(), sha256=sha, sample_rate_hz=info.sample_rate_hz,
                channels=info.channels, n_samples=info.n_samples, attribution=None))
    loose = sorted(p for p in base.rglob("*.flac") if not (p.parent / f"{p.parent.parent.name}-{p.parent.name}.trans.txt").exists())
    if loose:
        raise SourceImportError(f"{loose[0].relative_to(root).as_posix()} has no transcript (its folder has no "
                                f"trans.txt)")
    if not rows:
        raise SourceImportError(f"{dataset.dataset_id}: no utterances found under LibriSpeech/{split}")
    return rows


# ---------------------------------------------------------------------------------------------
# MUSAN
# ---------------------------------------------------------------------------------------------
def _background_list(text, where):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "Background noises:":
        raise SourceImportError(f"{where}: expected a first line 'Background noises:'")
    return set(lines[1:])


def _music_table(text, where):
    table = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 4 or parts[2] not in ("Y", "N"):
            raise SourceImportError(f"{where} line {number}: expected '<file> <genres> <Y|N> <artist>': {line!r}")
        tags = {f"genre-{_tag(g)}" for g in parts[1].split(",") if _tag(g)}
        tags.add("vocals-yes" if parts[2] == "Y" else "vocals-no")
        if parts[0] in table:
            raise SourceImportError(f"{where}: {parts[0]} is listed twice")
        table[parts[0]] = (tags, " ".join(parts[3:]).replace("_", " "))
    return table


def _rfm_titles(text, where):
    titles = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        name = line.strip()
        if re.fullmatch(r"music-rfm-[0-9]{4}", name):
            following = lines[index + 1].strip() if index + 1 < len(lines) else ""
            match = re.fullmatch(r'"(.+)" \(by (.+)\)', following)
            if match is None:
                raise SourceImportError(f"{where}: the line after {name} is not '\"<title>\" (by <artist>)': "
                                        f"{following!r}")
            titles[name] = (match.group(1), match.group(2))
    return titles


def _musan(dataset, root):
    rows = []
    for subset, spec in sorted(dataset["subsets"].items()):
        folder = root / "musan" / subset
        where = f"musan/{subset}"
        licence_file = folder / "LICENSE"
        if not licence_file.is_file():
            raise SourceImportError(f"{where}/LICENSE is missing from the extraction")
        if _sha256(licence_file) != spec["licence_file_sha256"]:
            raise SourceImportError(f"{where}/LICENSE does not match its pin in datasets.yaml; its licence "
                                    f"statement must be read again before the files can be registered")
        wavs = {p.stem: p for p in folder.glob("*.wav")}
        if not wavs:
            raise SourceImportError(f"{where}: no WAV files")
        annotations = (folder / "ANNOTATIONS").read_text(encoding="utf-8") if (folder / "ANNOTATIONS").is_file() else None
        if annotations is None:
            raise SourceImportError(f"{where}/ANNOTATIONS is missing from the extraction")
        tags = {name: set() for name in wavs}
        artists = {}
        if spec["annotations"] == "noise-background-list":
            background = _background_list(annotations, f"{where}/ANNOTATIONS")
            unknown = sorted(background - set(wavs))
            if unknown:
                raise SourceImportError(f"{where}/ANNOTATIONS lists {unknown[0]}, which has no WAV file")
            for name in background:
                tags[name].add("background")
        else:
            table = _music_table(annotations, f"{where}/ANNOTATIONS")
            if set(table) != set(wavs):
                missing = sorted(set(wavs) ^ set(table))[0]
                raise SourceImportError(f"{where}: {missing} is not both a WAV file and an ANNOTATIONS row")
            for name, (file_tags, artist) in table.items():
                tags[name] |= file_tags
                artists[name] = artist
        titles = {}
        if spec.get("titles") == "rfm-licence":
            titles = _rfm_titles(licence_file.read_text(encoding="utf-8"), f"{where}/LICENSE")
            missing = sorted(set(wavs) - set(titles))
            if missing:
                raise SourceImportError(f"{where}/LICENSE gives no title for {missing[0]}")
        for name in sorted(wavs):
            source_ref = f"musan/{subset}/{name}.wav"
            info, sha = _audio_facts(wavs[name], source_ref)
            attribution = None
            if name in titles:
                if "attribution_template" not in spec:
                    raise SourceImportError(f"{where}: titles are read but no attribution_template is given")
                title, artist = titles[name]
                attribution = spec["attribution_template"].format(title=title, artist=artist)
            rows.append(RegistryRow(
                clip_id=f"musan-{name}", source=dataset["source"], source_ref=source_ref, licence=spec["licence"],
                speaker_id=None, consent_ref=None, transcript=None, split=spec["split"],
                dataset=dataset.dataset_id, tags=tuple(sorted(tags[name])), sha256=sha,
                sample_rate_hz=info.sample_rate_hz, channels=info.channels, n_samples=info.n_samples,
                attribution=attribution))
    return rows


# ---------------------------------------------------------------------------------------------
# local folders: synthetic TTS clips and owner recordings
# ---------------------------------------------------------------------------------------------
def _transcripts(folder, where):
    path = folder / "transcripts.csv"
    try:
        text = path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise SourceImportError(f"{where}/transcripts.csv cannot be read: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise SourceImportError(f"{where}/transcripts.csv is not UTF-8: {exc}") from exc
    rows = list(csv.reader(io.StringIO(text.removeprefix("﻿"), newline="")))
    if not rows or rows[0] != ["file", "text"]:
        raise SourceImportError(f"{where}/transcripts.csv: header must be exactly file,text")
    texts = {}
    for number, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        if len(row) != 2:
            raise SourceImportError(f"{where}/transcripts.csv line {number}: expected 2 fields, found {len(row)}")
        name, spoken = row
        if name in texts:
            raise SourceImportError(f"{where}/transcripts.csv line {number}: {name} is listed twice")
        if not spoken.strip():
            raise SourceImportError(f"{where}/transcripts.csv line {number}: {name} has an empty text")
        texts[name] = spoken
    return texts


def _local_files(dataset, repo_root, allowed):
    folder = Path(repo_root) / dataset["folder"]
    where = dataset["folder"]
    if not folder.is_dir():
        raise SourceImportError(f"{dataset.dataset_id}: folder {where} does not exist")
    for path in sorted(folder.iterdir()):
        if path.name in allowed:
            continue
        if path.suffix == ".wav" and not FILE_NAME_RE.fullmatch(path.name):
            raise SourceImportError(f"{where}/{path.name}: file names must be lowercase letters, digits and "
                                    f"hyphens with .wav (for example 01.wav)")
        if path.suffix != ".wav" or not path.is_file():
            raise SourceImportError(f"{where}/{path.name} is not expected here (only NN.wav files and "
                                    f"{', '.join(sorted(allowed))})")
    texts = _transcripts(folder, where)
    wavs = {p.name: p for p in folder.glob("*.wav")}
    for name in sorted(set(wavs) - set(texts)):
        raise SourceImportError(f"{where}/{name} has no row in transcripts.csv")
    for name in sorted(set(texts) - set(wavs)):
        raise SourceImportError(f"{where}/transcripts.csv lists {name}, but there is no such WAV file")
    if not wavs:
        raise SourceImportError(f"{where}: no WAV files")
    return folder, where, texts, wavs


def _generation_record(path, where):
    """{file: (voice, sha256, text)} from the table in GENERATION.md."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SourceImportError(f"{where} cannot be read: {exc.strerror or exc}") from exc
    header = None
    table = {}
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            if header is not None and table:
                break
            continue
        if header is None:
            if "File" in cells and "Voice" in cells and "SHA-256" in cells and "Text" in cells:
                header = cells
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        if len(cells) != len(header):
            raise SourceImportError(f"{where}: table row has {len(cells)} cells, the header has {len(header)}: "
                                    f"{line!r}")
        row = dict(zip(header, cells))
        table[row["File"]] = (row["Voice"], row["SHA-256"], row["Text"])
    if header is None:
        raise SourceImportError(f"{where}: no table with the columns File, Voice, SHA-256 and Text")
    return table


def _tts(dataset, repo_root):
    record_name = Path(dataset["generation_record"]).name
    folder, where, texts, wavs = _local_files(dataset, repo_root, {"transcripts.csv", record_name})
    record = _generation_record(Path(repo_root) / dataset["generation_record"], dataset["generation_record"])
    if set(record) != set(wavs):
        odd = sorted(set(record) ^ set(wavs))[0]
        raise SourceImportError(f"{where}/{odd} is not both a WAV file and a row of {record_name}")
    rows = []
    for name in sorted(wavs):
        source_ref = f"{where}/{name}"
        info, sha = _audio_facts(wavs[name], source_ref)
        voice, record_sha, record_text = record[name]
        if sha != record_sha:
            raise SourceImportError(f"{source_ref}: SHA-256 {sha} differs from {record_sha} in {record_name}")
        if texts[name] != record_text:
            raise SourceImportError(f"{source_ref}: text differs between transcripts.csv ({texts[name]!r}) and "
                                    f"{record_name} ({record_text!r})")
        if not voice:
            raise SourceImportError(f"{source_ref}: no voice in {record_name}")
        tags = tuple(sorted(set(dataset["tags"]) | {f"voice-{_tag(voice)}"}))
        rows.append(RegistryRow(
            clip_id=f"{dataset['clip_prefix']}{Path(name).stem}", source=dataset["source"], source_ref=source_ref,
            licence=dataset["licence"], speaker_id=f"{dataset['speaker_prefix']}{voice}", consent_ref=None,
            transcript=texts[name], split=dataset["split"], dataset=dataset.dataset_id, tags=tags, sha256=sha,
            sample_rate_hz=info.sample_rate_hz, channels=info.channels, n_samples=info.n_samples, attribution=None))
    return rows


def _owner(dataset, repo_root):
    consent = dataset["consent_file"]
    consent_path = Path(repo_root) / consent
    if not consent_path.is_file() or consent_path.stat().st_size == 0:
        raise SourceImportError(f"{dataset.dataset_id}: consent file {consent} is missing or empty; owner "
                                f"recordings are registered only with a consent note")
    folder, where, texts, wavs = _local_files(dataset, repo_root, {"transcripts.csv", Path(consent).name})
    rows = []
    for name in sorted(wavs):
        source_ref = f"{where}/{name}"
        info, sha = _audio_facts(wavs[name], source_ref)
        rows.append(RegistryRow(
            clip_id=f"{dataset['clip_prefix']}{Path(name).stem}", source=dataset["source"], source_ref=source_ref,
            licence=dataset["licence"], speaker_id=dataset["speaker_id"], consent_ref=consent,
            transcript=texts[name], split=dataset["split"], dataset=dataset.dataset_id, tags=(), sha256=sha,
            sample_rate_hz=info.sample_rate_hz, channels=info.channels, n_samples=info.n_samples, attribution=None))
    return rows


def import_dataset(dataset, cache_dir, repo_root):
    """Registry rows of one dataset (fetched into cache_dir, or a local folder under repo_root)."""
    importer = dataset["importer"]
    if dataset["type"] == "download":
        try:
            root = fetch.extracted_root(cache_dir, dataset.dataset_id)
        except fetch.FetchError as exc:
            raise SourceImportError(str(exc)) from exc
        return _librispeech(dataset, root) if importer == "librispeech" else _musan(dataset, root)
    return _tts(dataset, repo_root) if importer == "tts" else _owner(dataset, repo_root)


def build_registry(datasets, cache_dir, repo_root):
    """Validated registry rows of every dataset, sorted by clip_id."""
    rows = []
    for dataset in datasets.datasets.values():
        rows += import_dataset(dataset, cache_dir, repo_root)
    check_rows(rows, datasets, repo_root, "the imported registry")
    return sorted(rows, key=lambda r: r.clip_id)
