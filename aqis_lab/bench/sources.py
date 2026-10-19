"""Sprint 1 dataset loaders and reference cleaning: EdAcc, Svarah, Eka, Earnings-22, HarperValleyBank, LibriSpeech, MUSAN.

CAPABILITIES:
  CAP-S1-010: clean_reference() and Cleaner apply the per-source rules of s1.yaml to a published reference: drop_if
    rules drop an utterance (overlap, unintelligible, foreign, empty), strip rules remove tags, spaces are collapsed; a
    tag-like token (<...> or [...]) that no rule covers is reported, and Cleaner.require_no_unknown_tags() stops prep
    with the list, so no tag is silently scored; the Cleaner counts every rule's drops and strips for the prep report
    [tests: test_s1_clean_strips_listed_tags_and_collapses_spaces, test_s1_clean_drops_marked_utterances_with_the_rule_name,
    test_s1_clean_reports_tags_no_rule_covers, test_s1_clean_text_without_tags_is_unchanged,
    test_s1_clean_text_empty_after_stripping_is_dropped_as_empty, test_s1_cleaner_counts_every_rule_it_applies,
    test_s1_cleaner_tallies_unknown_tags_across_utterances]
  CAP-S1-011: check_data_rows() checks prepared-data rows against the columns of brief section 6.3 (every column present,
    audio length equal to n_samples) [tests: test_s1_data_rows_have_every_column_of_the_spec,
    test_s1_data_row_audio_length_must_match_n_samples]
  CAP-S1-012: the dataset handles read each public source from its pinned revision: Hugging Face parquet files by column
    projection and row group (EdAcc, Svarah, Eka, Earnings-22), the HarperValleyBank git repository, and the lab's
    source registry for LibriSpeech and MUSAN; audio is decoded with soundfile or ffmpeg and resampled to 16 kHz with
    soxr. These need the network and the datasets, so the Colab prep run checks them; they have no unit tests.
INPUTS AND OUTPUTS: s1.yaml source blocks, a Hugging Face token (environment), a work folder in; utterance dicts
  (utt_id, source, licence, duration_s, ref_text, ref_clean, speaker, cluster, meta) and 16 kHz int16 audio out.
  CleaningError, UnknownTagsError, DataError, SourceUnavailable, SourceError.
CONTRACTS: brief sections 2 and 6.3.
INVARIANTS:
  - Nothing is invented: a missing column, an unreadable shard or an unknown tag or entity category stops the run with a
    message that names it; only a gated, refused or unreachable source is dropped, and prep records that.
  - Heavy imports (huggingface_hub, pyarrow.parquet, soxr) happen inside the functions that use them.
NOT IN SCOPE:
  - Choosing which utterances a slice takes (select.py) and rendering conditions (conditions.py, prep.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created. Dataset layouts checked on 17 Oct 2026 against the Hugging Face dataset cards and the
  HarperValleyBank README.
"""
import collections
import hashlib
import io
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aqis_lab.bench import lib

SR = 16000
TAG_RE = re.compile(r"<[^<>]+>|\[[^\[\]]+\]")
DATA_COLUMNS = ("utt_id", "source", "licence", "audio", "n_samples", "duration_s", "ref_text", "ref_clean", "speaker",
                "cluster", "meta")
NON_COMMERCIAL_RE = re.compile(r"non[\s-]?commercial|\bcc[\s-]by[\s-]nc\b", re.I)


class CleaningError(ValueError):
    """A reference cannot be cleaned."""


class UnknownTagsError(CleaningError):
    """References hold tags that no cleaning rule covers."""


class DataError(ValueError):
    """Prepared data rows break the format of brief section 6.3."""


class SourceUnavailable(RuntimeError):
    """A source cannot be reached or is refused (gated, missing); prep drops its slices and says so."""


class SourceError(RuntimeError):
    """A source is reachable but does not look as the code expects; the run stops."""


# ---- cleaning ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CleanResult:
    text: str | None
    dropped: str | None
    unknown_tags: tuple
    stripped: tuple


def clean_reference(raw, rules):
    """Clean one reference with a source's {strip: {label: regex}, drop_if: {label: regex}} rules."""
    for label, pattern in rules["drop_if"].items():
        if re.search(pattern, raw, re.I):
            return CleanResult(None, label, (), ())
    text, stripped = raw, []
    for label, pattern in rules["strip"].items():
        replaced = re.sub(pattern, " ", text, flags=re.I)
        if replaced != text:
            stripped.append(label)
            text = replaced
    unknown = tuple(TAG_RE.findall(text))
    text = " ".join(text.split())
    if not text:
        return CleanResult(None, "empty", unknown, tuple(stripped))
    return CleanResult(text, None, unknown, tuple(stripped))


class Cleaner:
    """Applies one source's rules to many references and counts what each rule did."""

    def __init__(self, rules):
        self.rules = rules
        self.seen = 0
        self.kept = 0
        self.dropped = collections.Counter()
        self.stripped = collections.Counter()
        self.unknown = collections.Counter()

    def apply(self, raw):
        result = clean_reference(raw, self.rules)
        self.seen += 1
        if result.dropped:
            self.dropped[result.dropped] += 1
        else:
            self.kept += 1
        self.stripped.update(result.stripped)
        self.unknown.update(tag.lower() for tag in result.unknown_tags)
        return result

    def report(self):
        return {"seen": self.seen, "kept": self.kept, "dropped": dict(self.dropped),
                "stripped": dict(self.stripped), "unknown_tags": dict(self.unknown)}

    def require_no_unknown_tags(self, source):
        if self.unknown:
            listing = ", ".join(f"{tag} ({n})" for tag, n in sorted(self.unknown.items()))
            raise UnknownTagsError(f"{source}: reference tags no cleaning rule covers: {listing}; read the examples, "
                                   f"then add a strip or drop_if rule for each in config/aqis_lab/s1.yaml")


# ---- prepared rows -------------------------------------------------------------------------------------------
def check_unique_ids(ids, where):
    seen, repeated = set(), []
    for ident in ids:
        if ident in seen and ident not in repeated:
            repeated.append(ident)
        seen.add(ident)
    if repeated:
        raise DataError(f"{where}: utterance IDs repeat ({len(repeated)}), for example {', '.join(repeated[:3])}")


def check_data_rows(rows):
    check_unique_ids([r.get("utt_id") for r in rows], "data rows")
    for row in rows:
        missing = [c for c in DATA_COLUMNS if c not in row]
        if missing:
            raise DataError(f"data row {row.get('utt_id', '?')} lacks {', '.join(missing)}")
        extra = sorted(set(row) - set(DATA_COLUMNS))
        if extra:
            raise DataError(f"data row {row['utt_id']} has unlisted column {', '.join(extra)}")
        if len(row["audio"]) != 2 * row["n_samples"]:
            raise DataError(f"data row {row['utt_id']}: audio holds {len(row['audio']) // 2} samples, n_samples says "
                            f"{row['n_samples']}")
        json.loads(row["meta"])


# ---- audio ---------------------------------------------------------------------------------------------------
def to_16k(samples, rate):
    """Mono float or int samples at `rate` to 16 kHz int16 (soxr, very high quality)."""
    x = np.asarray(samples)
    if x.dtype == np.int16:
        x = x.astype(np.float32) / 32768.0
    if rate != SR:
        soxr = lib("soxr")
        x = soxr.resample(x.astype(np.float32), rate, SR, quality="VHQ")
    return np.clip(np.round(x * 32768.0), -32768, 32767).astype(np.int16)


def decode_audio(data):
    """16 kHz mono int16 from encoded bytes: soundfile first, ffmpeg for formats it cannot read (Eka's m4a)."""
    import soundfile as sf
    try:
        x, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except sf.LibsndfileError:
        proc = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(SR),
                               "pipe:1"], input=data, capture_output=True)
        if proc.returncode != 0 or not proc.stdout:
            raise SourceError(f"ffmpeg could not decode {len(data)} bytes of audio: {proc.stderr.decode()[:300]}")
        return np.frombuffer(proc.stdout, dtype=np.int16).copy()
    return to_16k(x.mean(axis=1), rate)


# ---- Hugging Face parquet sources ----------------------------------------------------------------------------
HF_GLOBS = {                      # file layouts of the dataset repositories, checked on 17 Oct 2026
    "edacc": {"test": "data/test-*.parquet", "validation": "data/validation-*.parquet"},
    "svarah": {"test": "data/test-*.parquet"},
    "eka_medical": {"test": "en/test-*.parquet"},
    "earnings22": {"test": "chunked/test-*.parquet"},
}
SVARAH_SPEAKER_COLUMNS = ("gender", "age-group", "primary_language", "native_place_state", "native_place_district",
                          "highest_qualification", "job_category", "occupation_domain")


def _token():
    return os.environ.get("HF_TOKEN") or None


class HfParquetSource:
    """One Hugging Face dataset read through its parquet files: metadata columns first, audio only for chosen rows."""

    audio_column = "audio"
    meta_columns = ()
    needs_audio_duration = False

    def __init__(self, name, cfg, pinned_revision=None):
        self.name, self.cfg = name, cfg
        self.repo = cfg["hf"]
        self.licence = cfg["licence"]
        self.revision = pinned_revision or self._resolve_revision()
        self.fs = lib("huggingface_hub").HfFileSystem(token=_token())
        self.root = f"datasets/{self.repo}@{self.revision}"
        self.files = {}
        for split in cfg["splits"]:
            found = sorted(self.fs.glob(f"{self.root}/{HF_GLOBS[name][split]}"))
            if not found:
                raise SourceError(f"{self.repo}@{self.revision[:8]}: no parquet files match {HF_GLOBS[name][split]}")
            self.files[split] = found
        self._open = {}

    def _resolve_revision(self):
        errors = lib("huggingface_hub.errors")
        GatedRepoError, HfHubHTTPError, RepositoryNotFoundError = (errors.GatedRepoError, errors.HfHubHTTPError,
                                                                    errors.RepositoryNotFoundError)
        try:
            return lib("huggingface_hub").HfApi(token=_token()).dataset_info(self.repo).sha
        except (GatedRepoError, RepositoryNotFoundError) as exc:
            raise SourceUnavailable(f"{self.repo}: {exc}") from exc
        except HfHubHTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403, 404):
                raise SourceUnavailable(f"{self.repo}: HTTP {exc.response.status_code} (is the Hugging Face terms page "
                                        f"accepted for this token?)") from exc
            raise

    def card_text(self):
        try:
            return self.fs.read_text(f"{self.root}/README.md")
        except OSError as exc:
            raise SourceUnavailable(f"{self.repo}: README.md cannot be read: {exc}") from exc

    def check_licence(self):
        """Stop when the dataset card says non-commercial; returns the card's own licence line for the record."""
        text = self.card_text()
        hit = NON_COMMERCIAL_RE.search(text)
        if hit:
            line = next(ln for ln in text.splitlines() if hit.group(0).lower() in ln.lower())
            raise SourceError(f"{self.repo}: the dataset card says non-commercial ({line.strip()[:200]!r}); the brief "
                              f"stops prep here (section 2)")
        match = re.search(r"^license:\s*(\S+)", text, re.M)
        return match.group(1) if match else None

    def _parquet(self, path):
        if path not in self._open:
            import pyarrow.parquet as pq
            self._open[path] = pq.ParquetFile(self.fs.open(path, "rb"))
        return self._open[path]

    def iter_meta(self):
        """Yield (split, row_index_in_split, loc, row_dict) with only the metadata columns read."""
        for split, files in self.files.items():
            index = 0
            for fi, path in enumerate(files):
                pf = self._parquet(path)
                missing = sorted(set(self.meta_columns) - set(pf.schema_arrow.names))
                if missing:
                    raise SourceError(f"{self.repo}: {path.rsplit('/', 1)[-1]} lacks column {', '.join(missing)}; it has "
                                      f"{', '.join(pf.schema_arrow.names)}")
                for rg in range(pf.num_row_groups):
                    rows = pf.read_row_group(rg, columns=list(self.meta_columns)).to_pylist()
                    for i, row in enumerate(rows):
                        yield split, index, (split, fi, rg, i), row
                        index += 1

    def fetch_audio(self, locs):
        """{loc: 16 kHz int16} for the (split, file, row group, row) locations; each row group is read once."""
        by_group = collections.defaultdict(list)
        for loc in locs:
            by_group[loc[:3]].append(loc[3])
        out = {}
        for (split, fi, rg), rows in sorted(by_group.items()):
            pf = self._parquet(self.files[split][fi])
            column = pf.read_row_group(rg, columns=[self.audio_column]).column(self.audio_column).to_pylist()
            for i in rows:
                data = column[i]["bytes"] if isinstance(column[i], dict) else column[i]   # Eka stores plain binary
                if not data:
                    raise SourceError(f"{self.repo}: row {(split, fi, rg, i)} has no audio bytes")
                out[(split, fi, rg, i)] = decode_audio(data)
        return out

    def row_to_utt(self, split, index, row):
        """The utterance dict for one metadata row, or None when it has no text; each dataset defines this."""
        raise SourceError(f"{type(self).__name__} does not define row_to_utt")

    def candidates(self):
        cleaner = Cleaner(self.cfg["clean"])
        items, extra = [], collections.Counter()
        for split, index, loc, row in self.iter_meta():
            utt = self.row_to_utt(split, index, row)
            if utt is None:
                extra["no_text"] += 1
                continue
            result = cleaner.apply(utt["ref_text"])
            if result.dropped:
                continue
            utt["ref_clean"] = result.text
            utt["meta"]["_loc"] = list(loc)
            items.append(utt)
        cleaner.require_no_unknown_tags(self.name)
        check_unique_ids([x["utt_id"] for x in items], self.name)
        return items, {**cleaner.report(), **dict(extra)}


class EdaccSource(HfParquetSource):
    meta_columns = ("speaker", "text", "l1", "accent", "gender")
    needs_audio_duration = True

    def row_to_utt(self, split, index, row):
        if not row["text"]:
            return None
        return {"utt_id": f"edacc-{split}-{index:05d}", "source": self.name, "licence": self.licence,
                "duration_s": 0.0, "ref_text": row["text"], "speaker": row["speaker"], "cluster": row["speaker"],
                "meta": {"l1": row["l1"], "accent": row["accent"], "gender": row["gender"], "split": split}}


class SvarahSource(HfParquetSource):
    audio_column = "audio_filepath"
    meta_columns = ("duration", "text") + SVARAH_SPEAKER_COLUMNS

    def row_to_utt(self, split, index, row):
        if not row["text"]:
            return None
        key = "|".join(str(row[c]) for c in SVARAH_SPEAKER_COLUMNS)       # the dataset gives no speaker ID column
        speaker = "svarah-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
        return {"utt_id": f"svarah-{index:05d}", "source": self.name, "licence": self.licence,
                "duration_s": float(row["duration"]), "ref_text": row["text"], "speaker": speaker, "cluster": speaker,
                "meta": {"gender": row["gender"], "age_group": row["age-group"],
                         "primary_language": row["primary_language"], "state": row["native_place_state"]}}


class EkaSource(HfParquetSource):
    meta_columns = ("duration", "text", "session_id", "speaker", "type_concept", "recording_context",
                    "medical_entities")

    def __init__(self, name, cfg, pinned_revision=None):
        super().__init__(name, cfg, pinned_revision)
        self.scored = set(cfg["entity_categories"])
        self.ignored = set(cfg["ignored_entity_categories"])
        self.categories = collections.Counter()
        self.empty_entities = 0

    def row_to_utt(self, split, index, row):
        from aqis_lab.bench import score
        from aqis_lab.scoring.normalise import MAIN
        if not row["text"]:
            return None
        entities = []
        for category, text in score.parse_entities(row["medical_entities"]):
            self.categories[category] += 1
            if category in self.ignored:
                continue
            if category not in self.scored:
                continue                                # reported by require_known_categories after the pass
            if not MAIN(text).split():
                self.empty_entities += 1
                continue
            entities.append({"category": category, "text": text})
        speaker = row["speaker"] or row["session_id"]
        return {"utt_id": f"eka-{index:05d}", "source": self.name, "licence": self.licence,
                "duration_s": float(row["duration"]), "ref_text": row["text"], "speaker": speaker,
                "cluster": speaker,
                "meta": {"entities": entities, "type_concept": row["type_concept"],
                         "recording_context": row["recording_context"]}}

    def candidates(self):
        items, report = super().candidates()
        unknown = sorted(c for c in self.categories if c not in self.scored | self.ignored)
        if unknown:
            raise SourceError(f"{self.repo}: entity categories no rule covers: "
                              f"{', '.join(f'{c} ({self.categories[c]})' for c in unknown)}; list each under "
                              f"entity_categories or ignored_entity_categories in config/aqis_lab/s1.yaml")
        return items, {**report, "entity_categories": dict(self.categories), "empty_entities_dropped": self.empty_entities}


class Earnings22Source(HfParquetSource):
    meta_columns = ("file_id", "segment_id", "transcription", "start_ts", "end_ts")

    def row_to_utt(self, split, index, row):
        if not row["transcription"]:
            return None
        # segment_id repeats across calls, so the row's place in the split makes the ID unique
        return {"utt_id": f"earnings22-{index:05d}", "source": self.name, "licence": self.licence,
                "duration_s": float(row["end_ts"]) - float(row["start_ts"]), "ref_text": row["transcription"],
                "speaker": row["file_id"], "cluster": row["file_id"],
                "meta": {"file_id": row["file_id"], "segment_id": row["segment_id"]}}


HF_SOURCES = {"edacc": EdaccSource, "svarah": SvarahSource, "eka_medical": EkaSource, "earnings22": Earnings22Source}


# ---- HarperValleyBank ----------------------------------------------------------------------------------------
class HvbSource:
    """HarperValleyBank: segments cut from the per-role 8 kHz channel files and upsampled to 16 kHz."""

    needs_audio_duration = False

    def __init__(self, name, cfg, work_dir):
        self.name, self.cfg, self.licence = name, cfg, cfg["licence"]
        self.dir = Path(work_dir) / "harper_valley_bank"
        if not self.dir.is_dir():
            proc = subprocess.run(["git", "clone", "--quiet", "--depth", "1", cfg["git"], str(self.dir)],
                                  capture_output=True, text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
            if proc.returncode != 0:
                raise SourceUnavailable(f"{cfg['git']}: git clone failed: {proc.stderr.strip()[:300]}")
        self.revision = subprocess.run(["git", "-C", str(self.dir), "rev-parse", "HEAD"], capture_output=True,
                                       text=True, check=True).stdout.strip()
        self.data = self.dir / "data"
        for part in ("transcript", "metadata", "audio/agent", "audio/caller"):
            if not (self.data / part).is_dir():
                raise SourceUnavailable(f"{cfg['git']}: data/{part} is missing from the clone (the repository may keep "
                                        f"its audio elsewhere)")

    def check_licence(self):
        return None

    def candidates(self):
        cleaner = Cleaner(self.cfg["clean"])
        items, skipped = [], collections.Counter()
        for path in sorted((self.data / "transcript").glob("*.json")):
            sid = path.stem
            segments = json.loads(path.read_text(encoding="utf-8"))
            meta_path = self.data / "metadata" / f"{sid}.json"
            call = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
            for seg in segments:
                text, role = seg.get("human_transcript"), seg.get("speaker_role")
                if not text or role not in ("agent", "caller"):
                    skipped["no_text_or_role"] += 1
                    continue
                result = cleaner.apply(text)
                if result.dropped:
                    continue
                speaker_id = (call or {}).get(role, {}).get("speaker_id")
                speaker = f"hvb-{role}-{speaker_id}" if speaker_id is not None else f"hvb-{sid}-{role}"
                tasks = (call or {}).get("tasks") or [{}]
                items.append({"utt_id": f"hvb-{sid}-{seg['index']:03d}", "source": self.name, "licence": self.licence,
                              "duration_s": seg["duration_ms"] / 1000.0, "ref_text": text, "ref_clean": result.text,
                              "speaker": speaker, "cluster": speaker,
                              "meta": {"role": role, "sid": sid, "task_type": tasks[0].get("task_type"),
                                       "_loc": [sid, role, int(seg["offset_ms"]), int(seg["duration_ms"])]}})
        cleaner.require_no_unknown_tags(self.name)
        check_unique_ids([x["utt_id"] for x in items], self.name)
        return items, {**cleaner.report(), **dict(skipped)}

    def fetch_audio(self, locs):
        import soundfile as sf
        out = {}
        for loc in locs:
            sid, role, offset_ms, duration_ms = loc
            path = self.data / "audio" / role / f"{sid}.wav"
            info = sf.info(str(path))
            if info.samplerate != 8000:
                raise SourceError(f"{path.name}: sample rate is {info.samplerate} Hz, but slice us_phone stands for real "
                                  f"8 kHz telephone audio")
            start, frames = int(offset_ms * info.samplerate / 1000), int(duration_ms * info.samplerate / 1000)
            x, rate = sf.read(str(path), start=start, frames=frames, dtype="float32", always_2d=True)
            if len(x) < frames - info.samplerate // 20:
                raise SourceError(f"{path.name}: segment at {offset_ms} ms for {duration_ms} ms runs past the end of the "
                                  f"file ({info.frames / info.samplerate:.1f} s); the transcript offsets do not match "
                                  f"the audio files")
            out[tuple(loc)] = to_16k(x.mean(axis=1), rate)
        return out


# ---- the lab's source registry: LibriSpeech and MUSAN --------------------------------------------------------
class RegistryAudio:
    """Clips of registry datasets, read from the fetch cache and checked against their registry SHA-256."""

    def __init__(self, repo_root, cache_dir):
        from aqis_lab.registry.datasets import load_datasets
        from aqis_lab.registry.registry import load_registry
        self.repo_root, self.cache = Path(repo_root), Path(cache_dir)
        self.datasets = load_datasets(self.repo_root / "data/registry/datasets.yaml")
        self.rows = load_registry(self.repo_root / "data/registry/sources.csv", self.datasets, self.repo_root)

    def rows_of(self, dataset_id, split=None):
        return [r for r in self.rows if r.dataset == dataset_id and (split is None or r.split == split)]

    def read(self, row):
        from aqis_lab.packs.audio import decode_flac, read_wav
        from aqis_lab.registry import fetch
        path = fetch.extracted_root(self.cache, row.dataset) / row.source_ref
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SourceUnavailable(f"{row.source_ref}: {path} cannot be read ({exc.strerror or exc}); run "
                                    f"`python -m aqis_lab registry fetch {row.dataset}` first") from exc
        if hashlib.sha256(data).hexdigest() != row.sha256:
            raise SourceError(f"{row.source_ref}: SHA-256 differs from the registry; the file changed after registering")
        _, samples = decode_flac(data, row.source_ref) if path.suffix == ".flac" else read_wav(data, row.source_ref)
        if row.sample_rate_hz != SR:
            samples = to_16k(samples, row.sample_rate_hz)
        return samples
