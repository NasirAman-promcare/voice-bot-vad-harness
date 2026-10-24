"""Sprint 2 data preparation: the VAD, turn-end, streaming and emotion test sets, rendered per condition.

CAPABILITIES:
  CAP-S2-040: select_emotion() takes per_class utterances of each of the four emotion classes, spread over the actors one at a
    time, the same for the same seed whatever the input order, and says in a note when a class has fewer than asked for [tests:
    test_s2_emotion_selection_is_class_balanced_and_actor_balanced_within_a_class,
    test_s2_emotion_selection_is_deterministic_and_independent_of_input_order,
    test_s2_emotion_selection_takes_all_of_a_short_class_and_says_so]
  CAP-S2-041: Prep.run() builds data/<set>/<condition>.parquet for the vad, turn, stream and emotion sets and data/manifest.json:
    the vad set is the Sprint 1 us_phone turns (reference speech segments from HarperValleyBank's machine word timings) plus
    the Sprint 1 non-speech clips (no speech); the turn set is HarperValleyBank turns with a pause, cut with trailing audio;
    the stream set is Sprint 1 anchor and us_conv clips; the emotion set is CREMA-D. A condition file that exists is skipped
    [no unit test: it reads corpora, which the cloud session never downloads; the Oracle and Colab smoke runs build and read
    the files]
INPUTS AND OUTPUTS: s2.yaml and s1.yaml configs, the Sprint 1 output folder, a work folder; parquet files and a manifest out;
  PrepError.
CONTRACTS: brief section 2 and the deviations listed in docs/progress/WP-1.2/PLAN.md.
INVARIANTS:
  - Nothing is invented: a missing Sprint 1 file or a corpus that does not match its card stops the run with the file named.
  - Every reference segment comes from a source's own timings; the manifest says which source and how many clips have one.
  - Audio and per-utterance texts stay on Drive; the manifest holds counts only.
NOT IN SCOPE:
  - Scoring (aqis_lab/live/score.py) and the Sprint 1 slices themselves (aqis_lab/bench/prep.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import collections
import json
import re
from pathlib import Path

from aqis_lab import drive
from aqis_lab.bench import lib, select, sources
from aqis_lab.bench import conditions as s1_conditions
from aqis_lab.bench import prep as s1_prep
from aqis_lab.bench.run import git_commit
from aqis_lab.live import emotion, turn

SR = 16000
SETS = ("vad", "turn", "stream", "emotion")
DATA_COLUMNS = ("utt_id", "source", "licence", "audio", "n_samples", "duration_s", "speaker", "cluster", "label", "ref", "meta")
HVB_ID = re.compile(r"hvb-(?P<sid>.+)-(?P<index>\d{3})$")


class PrepError(RuntimeError):
    """A test set cannot be built from what is on disk."""


def select_emotion(items, per_class, seed):
    chosen, notes = [], []
    for label in emotion.CLASSES:
        pool = [x for x in items if x["label"] == label]
        picked = select.round_robin(pool, per_class, seed, f"emotion:{label}")
        if len(picked) < per_class:
            notes.append(f"emotion: class {label} has only {len(pool)} utterances, {per_class} asked for; the real N is {len(picked)}")
        chosen += picked
    return select.Selection(chosen, notes)


def _write_rows(path, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sources.check_unique_ids([r["utt_id"] for r in rows], str(path))
    for r in rows:
        if len(r["audio"]) != 2 * r["n_samples"]:
            raise PrepError(f"{r['utt_id']}: audio holds {len(r['audio']) // 2} samples, n_samples says {r['n_samples']}")
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist([{c: r[c] for c in DATA_COLUMNS} for r in rows]), sink, compression="zstd")
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, sink.getvalue().to_pybytes())


def read_data(path):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


class Prep:
    def __init__(self, cfg, s1_cfg, out_dir, s1_dir, work_dir, repo_root, log=print):
        self.cfg, self.s1_cfg, self.log = cfg, s1_cfg, log
        self.out, self.s1_out, self.work, self.repo = Path(out_dir), Path(s1_dir), Path(work_dir), Path(repo_root)
        self.data = self.out / "data"
        self.s1 = s1_prep.Prep(s1_cfg, self.out, self.work, self.repo, log)      # HarperValleyBank handle and MUSAN noise pool
        s1_pins = s1_prep._load_json(self.s1_out / "data" / "pins.json", {})
        self.s1.pins = {**s1_pins, **self.s1.pins}
        self.manifest = s1_prep._load_json(self.data / "manifest.json", {})
        self.notes = []

    # ---- Sprint 1 inputs --------------------------------------------------------------------------------------
    def s1_rows(self, slice_name, condition):
        path = self.s1_out / "data" / slice_name / f"{condition}.parquet"
        if not path.exists():
            raise PrepError(f"{path} is missing; run the Sprint 1 prep (python -m aqis_lab.bench prep) for slice {slice_name} first")
        return read_data(path)

    def hvb(self):
        handle = self.s1.open_source("harper_valley_bank")
        return handle

    def hvb_segment(self, sid, index):
        path = self.hvb().data / "transcript" / f"{sid}.json"
        for seg in json.loads(path.read_text(encoding="utf-8")):
            if seg["index"] == index:
                return seg
        raise PrepError(f"{path.name} has no segment {index}")

    def speaker_of(self, sid, role):
        meta = self.hvb().data / "metadata" / f"{sid}.json"
        speaker_id = (json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}).get(role, {}).get("speaker_id")
        return f"hvb-{role}-{speaker_id}" if speaker_id is not None else f"hvb-{sid}-{role}"

    @staticmethod
    def words_of(seg):
        offsets, durations = seg.get("word_offsets_ms"), seg.get("word_durations_ms")
        if not offsets or not durations:
            return None
        return turn.words_from_offsets(offsets, durations)

    # ---- rendering --------------------------------------------------------------------------------------------
    def noise(self, names):
        needs = any("noise" in self.s1_cfg.conditions[c] for c in names)
        return self.s1.noise_pool() if needs else {}

    def render(self, set_name, items, audio, names):
        """Write data/<set>/<condition>.parquet for each condition whose file is missing; returns the conditions written."""
        todo = [c for c in names if not (self.data / set_name / f"{c}.parquet").exists()]
        noise = self.noise(todo)
        for condition in todo:
            rows = []
            for item in items:
                utt_id = f"{set_name}:{item['utt_id']}"
                samples, info = s1_conditions.render_condition(condition, self.s1_cfg.conditions, audio[item["utt_id"]],
                                                              self.cfg.seed, utt_id, noise)
                rows.append({"utt_id": utt_id, "source": item["source"], "licence": item["licence"],
                             "audio": samples.astype("<i2").tobytes(), "n_samples": len(samples),
                             "duration_s": len(samples) / SR, "speaker": item["speaker"], "cluster": item["cluster"],
                             "label": item.get("label", ""), "ref": json.dumps(item["ref"], sort_keys=True),
                             "meta": json.dumps(dict(item.get("meta", {}), condition=condition, **info), sort_keys=True)})
            _write_rows(self.data / set_name / f"{condition}.parquet", rows)
            self.log(f"{set_name}/{condition}: {len(rows)} clips written")
        return todo

    # ---- the four sets ----------------------------------------------------------------------------------------
    def build_vad(self):
        gap = self.cfg.scoring["vad_reference_merge_gap_ms"]
        items, audio, without = [], {}, 0
        for row in self.s1_rows("us_phone", "native"):
            m = HVB_ID.search(row["utt_id"])
            if not m:
                raise PrepError(f"{row['utt_id']} is not a HarperValleyBank clip id")
            words = self.words_of(self.hvb_segment(m["sid"], int(m["index"])))
            if words is None:
                without += 1
                continue
            samples = _int16(row["audio"])
            end = len(samples) * 1000.0 / SR
            segments = [(s, min(e, end)) for s, e in turn.speech_segments_from_words(words, gap) if s < end]
            items.append({"utt_id": row["utt_id"], "source": row["source"], "licence": row["licence"], "speaker": row["speaker"],
                          "cluster": row["cluster"], "ref": {"segments_ms": segments, "kind": "speech"},
                          "meta": {"timing_source": "HarperValleyBank machine word timings"}})
            audio[row["utt_id"]] = samples
        if without:
            self.notes.append(f"vad: {without} of {len(items) + without} us_phone clips have no machine word timings and are left out")
        for row in self.s1_rows("nonspeech", "clean"):
            items.append({"utt_id": row["utt_id"], "source": row["source"], "licence": row["licence"], "speaker": row["speaker"],
                          "cluster": row["cluster"], "ref": {"segments_ms": [], "kind": json.loads(row["meta"]).get("kind")},
                          "meta": {"timing_source": "none: the clip holds no speech"}})
            audio[row["utt_id"]] = _int16(row["audio"])
        self.notes.append("vad: sa_conv has no millisecond speech boundaries, so it is not scored (brief section 2.2 asks for it)")
        written = self.render("vad", items, audio, self.cfg.conditions["vad"])
        return {"clips": len(items), "speech_clips": sum(1 for x in items if x["ref"]["segments_ms"]), "written": written}

    def build_turn(self):
        t = self.cfg.turn_end
        handle = self.hvb()
        import soundfile as sf
        by_role = collections.defaultdict(list)
        pool = []
        for path in sorted((handle.data / "transcript").glob("*.json")):
            segs = json.loads(path.read_text(encoding="utf-8"))
            for role in ("agent", "caller"):
                mine = sorted((s for s in segs if s.get("speaker_role") == role), key=lambda s: s["offset_ms"])
                for k, seg in enumerate(mine):
                    words = self.words_of(seg)
                    if not words or len(words) < self.cfg.data["turn"]["min_words"]:
                        continue
                    end = turn.turn_end_ms(words)
                    if not turn.pauses_from_words(words, t["min_pause_ms"]):
                        continue
                    following = mine[k + 1]["offset_ms"] if k + 1 < len(mine) else None
                    if following is not None and following - (seg["offset_ms"] + end) < t["trail_ms"]:
                        continue
                    pool.append({"utt_id": f"hvb-{path.stem}-{seg['index']:03d}", "source": "harper_valley_bank",
                                 "licence": self.cfg.data["turn"]["licence"], "speaker": self.speaker_of(path.stem, role),
                                 "cluster": self.speaker_of(path.stem, role), "words": words, "role": role, "sid": path.stem,
                                 "offset_ms": int(seg["offset_ms"]), "end_ms": end,
                                 "ref": {"words_ms": words, "pauses_ms": turn.pauses_from_words(words, t["min_pause_ms"]),
                                         "end_ms": end}, "meta": {"role": role, "timing_source": "HarperValleyBank machine word timings"}})
        n = self.cfg.data["turn"]["n_per_role"]
        items = []
        for role in ("agent", "caller"):
            mine = [x for x in pool if x["role"] == role]
            picked = select.round_robin(mine, n, self.cfg.seed, f"turn:{role}")
            if len(picked) < n:
                self.notes.append(f"turn: role {role} has only {len(mine)} turns that qualify, {n} asked for; the real N is {len(picked)}")
            items += picked
        audio = {}
        for x in items:
            path = handle.data / "audio" / x["role"] / f"{x['sid']}.wav"
            info = sf.info(str(path))
            frames = int((x["end_ms"] + t["trail_ms"]) * info.samplerate / 1000)
            start = int(x["offset_ms"] * info.samplerate / 1000)
            raw, rate = sf.read(str(path), start=start, frames=frames, dtype="float32", always_2d=True)
            if len(raw) < frames:
                raise PrepError(f"{path.name}: turn {x['utt_id']} needs {t['trail_ms']} ms after its end but the file stops first")
            audio[x["utt_id"]] = sources.to_16k(raw.mean(axis=1), rate)
        written = self.render("turn", items, audio, self.cfg.conditions["turn"])
        return {"clips": len(items), "roles": dict(collections.Counter(x["role"] for x in items)), "written": written}

    def build_stream(self):
        n = self.cfg.stt_streaming["utterances"]
        items, audio = [], {}
        for slice_name in ("anchor", "us_conv"):
            rows = self.s1_rows(slice_name, "clean")
            picked = select.round_robin([dict(r, utt_id=r["utt_id"]) for r in rows], n // 2, self.cfg.seed, f"stream:{slice_name}")
            for r in picked:
                items.append({"utt_id": r["utt_id"], "source": r["source"], "licence": r["licence"], "speaker": r["speaker"],
                              "cluster": r["cluster"], "ref": {"ref_clean": r["ref_clean"]}, "meta": {"slice": slice_name}})
                audio[r["utt_id"]] = _int16(r["audio"])
        written = self.render("stream", items, audio, self.cfg.conditions["stream"])
        return {"clips": len(items), "written": written}

    def build_emotion(self):
        spec = self.cfg.data["emotion"]
        hub, pq = lib("huggingface_hub"), lib("pyarrow.parquet")
        revision = self.s1.pins.get("cremad") or spec["revision"]
        if self.s1.pins.get("cremad") and spec["revision"] != self.s1.pins["cremad"]:
            raise PrepError(f"CREMA-D is pinned at {self.s1.pins['cremad']} by the first prep run but s2.yaml says {spec['revision']}")
        files = [hub.hf_hub_download(spec["hf"], f"data/{split}-00000-of-00001.parquet", repo_type="dataset", revision=revision)
                 for split in spec["splits"]]
        pool = []
        for f, path in enumerate(files):
            for row, name in enumerate(pq.read_table(path, columns=["file"]).column("file").to_pylist()):
                base = Path(name).name
                parts = base.split("_")
                label = emotion.crema_label(parts[2]) if len(parts) > 2 else None
                if label is None:
                    continue
                pool.append({"utt_id": Path(base).stem, "speaker": f"actor{parts[0]}", "cluster": f"actor{parts[0]}",
                             "label": label, "_at": (f, row)})
        picked = select_emotion(pool, spec["per_class"], self.cfg.seed)
        self.notes += picked.notes
        want = collections.defaultdict(dict)
        for x in picked.items:
            want[x["_at"][0]][x["_at"][1]] = x
        audio = {}
        for f, path in enumerate(files):
            if f not in want:
                continue
            indices = sorted(want[f])
            cells = pq.read_table(path, columns=["audio"]).take(indices).column("audio").to_pylist()
            for row_index, cell in zip(indices, cells):
                audio[want[f][row_index]["utt_id"]] = sources.decode_audio(cell["bytes"])
        items = [{"utt_id": x["utt_id"], "source": "cremad", "licence": spec["licence"], "speaker": x["speaker"],
                  "cluster": x["cluster"], "label": x["label"], "ref": {"label": x["label"]}, "meta": {}} for x in picked.items]
        self.s1.pins["cremad"] = revision
        s1_prep._write_json(self.data / "pins.json", self.s1.pins)
        written = self.render("emotion", items, audio, self.cfg.conditions["emotion"])
        return {"clips": len(items), "per_class": dict(collections.Counter(x["label"] for x in items)),
                "actors": len({x["cluster"] for x in items}), "written": written}

    def run(self, only=None):
        manifest = self.manifest
        manifest.update({"config_hash": self.cfg.hash, "git_commit": git_commit(self.repo), "seed": self.cfg.seed})
        manifest.setdefault("sets", {})
        for name in SETS:
            if only and name not in only:
                continue
            manifest["sets"][name] = getattr(self, f"build_{name}")()
            manifest["notes"] = sorted(set(manifest.get("notes", [])) | set(self.notes))
            s1_prep._write_json(self.data / "manifest.json", manifest)
        return manifest


def _int16(data):
    import numpy as np
    return np.frombuffer(data, dtype="<i2").copy()
