"""Sprint 1 prep (CPU): read the public sources, clean references, select the slices, render the conditions.

CAPABILITIES:
  CAP-S1-017: prep() builds data/<slice>/<condition>.parquet for every slice of s1.yaml and data/manifest.json,
    data/LICENCES.md and data/prep_report.md: it opens each source at a revision pinned on the first run (stopping when a
    dataset card says non-commercial), cleans the references per source and counts every rule's drops, selects each slice
    by the seeded speaker-balanced rules (EdAcc preselects three times N because the dataset gives no durations), cuts
    the audio, renders every condition of the slice with the same noise draw for all noise conditions, writes each file
    atomically and skips files that exist; a gated, refused or unreachable source drops its slices and the manifest says
    so. It needs the network and the datasets, so the Colab prep run checks it; it has no unit tests.
INPUTS AND OUTPUTS: the config, an output folder (Drive AQIS_LAB/s1), a local work folder and the repository root in;
  the files above out; the source errors of sources.py.
CONTRACTS: brief sections 2, 3 and 6.3.
INVARIANTS:
  - Selection depends only on the seed, the config and the pinned source revisions.
  - No audio, reference or number is invented: every utterance comes from a source and the manifest counts them.
  - Audio and per-utterance texts are written only under the output folder (Drive); nothing here goes to the repository.
NOT IN SCOPE:
  - Transcription (run.py) and scoring (score.py, report.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import collections
import json
from pathlib import Path

import numpy as np

from aqis_lab import drive
from aqis_lab.bench import conditions, select, sources
from aqis_lab.bench.run import RunError, git_commit

SR = 16000
PREFILTER = 3                                  # EdAcc has no duration column: preselect this many times N, then measure


def _load_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _write_json(path, value):
    drive.write_bytes(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def _write_rows(path, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sources.check_data_rows(rows)
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist([{c: r[c] for c in sources.DATA_COLUMNS} for r in rows]), sink,
                   compression="zstd")
    drive.make_dirs(Path(path).parent)
    drive.write_bytes(path, sink.getvalue().to_pybytes())


def _public_meta(meta):
    return {k: v for k, v in meta.items() if not k.startswith("_")}


class Prep:
    def __init__(self, cfg, out_dir, work_dir, repo_root, log=print):
        self.cfg, self.log = cfg, log
        self.out, self.work, self.repo = Path(out_dir), Path(work_dir), Path(repo_root)
        self.data = self.out / "data"
        drive.make_dirs(self.data)
        self.work.mkdir(parents=True, exist_ok=True)
        self.pins = _load_json(self.data / "pins.json", {})
        self.manifest = _load_json(self.data / "manifest.json", {})
        self.handles, self.candidate_cache, self.card_licences = {}, {}, {}
        self.registry = None
        self.noise = None

    # ---- sources ----------------------------------------------------------------------------------------------
    def registry_audio(self, dataset_id):
        from aqis_lab.registry import fetch
        if self.registry is None:
            self.registry = sources.RegistryAudio(self.repo, self.work / "registry_cache")
        try:
            fetch.extracted_root(self.work / "registry_cache", dataset_id)
        except fetch.FetchError:
            self.log(f"fetching {dataset_id} into {self.work / 'registry_cache'} (pinned size and checksums)")
            try:
                fetch.fetch_dataset(self.registry.datasets.datasets[dataset_id], self.work / "registry_cache", self.repo)
            except fetch.FetchError as exc:
                raise sources.SourceUnavailable(f"{dataset_id}: {exc}") from exc
        return self.registry

    def open_source(self, name):
        if name in self.handles:
            return self.handles[name]
        scfg = self.cfg.sources[name]
        if name in sources.HF_SOURCES:
            handle = sources.HF_SOURCES[name](name, scfg, self.pins.get(name))
            self.card_licences[name] = handle.check_licence()
        elif name == "harper_valley_bank":
            handle = sources.HvbSource(name, scfg, self.work)
            self.card_licences[name] = None
        else:
            raise RunError(f"no loader for source {name!r}")
        pinned = self.pins.get(name)
        if pinned and pinned != handle.revision:
            raise sources.SourceError(f"{name} is at revision {handle.revision}, but the first prep run pinned {pinned}; "
                                      f"delete data/pins.json only if the sprint's data is being rebuilt")
        self.pins[name] = handle.revision
        _write_json(self.data / "pins.json", self.pins)
        self.handles[name] = handle
        return handle

    def candidates(self, name):
        if name not in self.candidate_cache:
            handle = self.open_source(name)
            self.log(f"{name}: reading metadata of {handle.revision[:10]}")
            self.candidate_cache[name] = handle.candidates()
        return self.candidate_cache[name]

    def noise_pool(self):
        if self.noise is None:
            registry = self.registry_audio("musan")
            rows = registry.rows_of("musan", "noise")
            self.log(f"loading {len(rows)} MUSAN noise clips")
            self.noise = {r.clip_id: registry.read(r) for r in rows}
        return self.noise

    # ---- slices -----------------------------------------------------------------------------------------------
    def speech_items(self, slice_name, spec):
        """(selected items with audio, notes, cleaning report) for a speech slice."""
        cfg = self.cfg
        source = spec["source"]
        if source == "librispeech-test-other":
            registry = self.registry_audio("librispeech-test-other")
            rows = registry.rows_of("librispeech-test-other")
            items = [{"utt_id": r.clip_id, "source": "librispeech", "licence": r.licence, "duration_s": r.duration_s,
                      "ref_text": r.transcript, "ref_clean": r.transcript, "speaker": r.speaker_id,
                      "cluster": r.speaker_id, "meta": {"_row": r.clip_id}} for r in rows]
            report = {"seen": len(items), "kept": len(items)}
            chosen = select.select_slice(slice_name, spec, items, cfg.utterance, cfg.seed)
            by_id = {r.clip_id: r for r in rows}
            audio = {x["utt_id"]: registry.read(by_id[x["meta"]["_row"]]) for x in chosen.items}
            return chosen.items, audio, chosen.notes, report
        handle = self.open_source(source)
        pool, report = self.candidates(source)
        pool = [dict(x, meta=dict(x["meta"])) for x in pool]
        audio = {}
        if handle.needs_audio_duration:
            wide = dict(cfg.utterance, min_s=0.0, max_s=1e9)
            pre = select.select_slice(slice_name, dict(spec, n=spec["n"] * PREFILTER, min_s=0.0, max_s=1e9), pool, wide,
                                      cfg.seed)
            self.log(f"{slice_name}: measuring the duration of {len(pre.items)} preselected utterances")
            got = handle.fetch_audio([tuple(x["meta"]["_loc"]) for x in pre.items])
            for x in pre.items:
                x["_audio"] = got[tuple(x["meta"]["_loc"])]
                x["duration_s"] = len(x["_audio"]) / SR
            pool = pre.items
        chosen = select.select_slice(slice_name, spec, pool, cfg.utterance, cfg.seed)
        need = [x for x in chosen.items if "_audio" not in x]
        if need:
            self.log(f"{slice_name}: reading audio of {len(need)} utterances")
            got = handle.fetch_audio([tuple(x["meta"]["_loc"]) for x in need])
            for x in need:
                x["_audio"] = got[tuple(x["meta"]["_loc"])]
        for x in chosen.items:
            measured = len(x["_audio"]) / SR
            if abs(measured - x["duration_s"]) > 0.5:
                raise sources.SourceError(f"{x['utt_id']}: the audio lasts {measured:.2f} s but the metadata says "
                                          f"{x['duration_s']:.2f} s")
            x["duration_s"] = measured
            audio[x["utt_id"]] = x.pop("_audio")
        return chosen.items, audio, chosen.notes, report

    def nonspeech_items(self, spec):
        registry = self.registry_audio("musan")
        noise_rows = {r.clip_id: r for r in registry.rows_of("musan", "noise")}
        music_rows = {r.clip_id: r for r in registry.rows_of("musan", "music")}
        plan = select.plan_nonspeech(spec, {k: r.n_samples for k, r in noise_rows.items()},
                                     {k: r.n_samples for k, r in music_rows.items()}, self.cfg.seed)
        cache, items, audio = {}, [], {}
        for p in plan:
            if p["kind"] == "silence":
                samples, row = np.zeros(p["length"], dtype=np.int16), None
            else:
                row = (noise_rows if p["kind"] == "noise" else music_rows)[p["clip_id"]]
                if row.clip_id not in cache:
                    cache[row.clip_id] = registry.read(row)
                samples = conditions.scale_to_dbfs(cache[row.clip_id][p["offset"]:p["offset"] + p["length"]],
                                                   p["level_dbfs"])
            items.append({"utt_id": p["utt_id"], "source": "musan", "licence": row.licence if row else "CC0-1.0",
                          "duration_s": p["length"] / SR, "ref_text": "", "ref_clean": "",
                          "speaker": p["clip_id"] or p["utt_id"], "cluster": p["clip_id"] or p["utt_id"],
                          "meta": {"kind": p["kind"], "clip": p["clip_id"], "offset": p["offset"],
                                   "level_dbfs": p["level_dbfs"]}})
            audio[p["utt_id"]] = samples
        return items, audio, [], {"seen": len(items), "kept": len(items)}

    def render_slice(self, slice_name, spec):
        cfg = self.cfg
        names = cfg.conditions_for(slice_name)
        todo = [c for c in names if not (self.data / slice_name / f"{c}.parquet").exists()]
        if not todo:
            self.log(f"{slice_name}: all {len(names)} condition files exist, skipped")
            return None
        if spec["source"] == "musan":
            items, audio, notes, report = self.nonspeech_items(spec)
        else:
            items, audio, notes, report = self.speech_items(slice_name, spec)
        if not items:
            raise sources.SourceError(f"{slice_name}: no utterance of {spec['source']} passes the slice's filters; "
                                      f"check the cleaning drops and filters in the prep report before going on")
        noise = self.noise_pool() if any("noise" in cfg.conditions[c] for c in todo) else {}
        for condition in todo:
            rows = []
            for item in items:
                utt_id = f"{slice_name}:{item['utt_id']}"
                samples, info = conditions.render_condition(condition, cfg.conditions, audio[item["utt_id"]], cfg.seed,
                                                            utt_id, noise)
                meta = dict(_public_meta(item["meta"]), condition=condition, **info)
                rows.append({"utt_id": utt_id, "source": item["source"], "licence": item["licence"],
                             "audio": samples.astype("<i2").tobytes(), "n_samples": len(samples),
                             "duration_s": len(samples) / SR, "ref_text": item["ref_text"],
                             "ref_clean": item["ref_clean"], "speaker": item["speaker"], "cluster": item["cluster"],
                             "meta": json.dumps(meta, sort_keys=True, ensure_ascii=False)})
            _write_rows(self.data / slice_name / f"{condition}.parquet", rows)
            self.log(f"{slice_name}/{condition}: {len(rows)} utterances written")
        speakers = {i["cluster"] for i in items}
        return {"requested": spec["n"], "n": len(items), "conditions": names, "clusters": len(speakers),
                "hours": sum(i["duration_s"] for i in items) / 3600, "notes": notes, "cleaning": report,
                "words": sum(len(i["ref_clean"].split()) for i in items),
                "roles": dict(collections.Counter(i["meta"].get("role") for i in items if "role" in i["meta"]))}

    # ---- the whole run ----------------------------------------------------------------------------------------
    def run(self, only=None):
        cfg = self.cfg
        manifest = self.manifest
        manifest.update({"config_hash": cfg.hash, "git_commit": git_commit(self.repo), "seed": cfg.seed})
        manifest.setdefault("slices", {})
        manifest.setdefault("dropped_slices", {})
        for slice_name, spec in cfg.slices.items():
            if only and slice_name not in only:
                continue
            try:
                result = self.render_slice(slice_name, spec)
            except sources.SourceUnavailable as exc:
                manifest["dropped_slices"][slice_name] = str(exc)
                manifest["slices"].pop(slice_name, None)
                self.log(f"DROPPED slice {slice_name}: {exc}")
                continue
            if result is not None:
                manifest["slices"][slice_name] = result
                manifest["dropped_slices"].pop(slice_name, None)
            _write_json(self.data / "manifest.json", manifest)
        manifest["sources"] = {n: {"revision": self.pins.get(n), "licence": cfg.sources[n].get("licence"),
                                   "card_licence": self.card_licences.get(n)} for n in self.pins}
        manifest["total_hours"] = sum(s["hours"] for s in manifest["slices"].values())
        _write_json(self.data / "manifest.json", manifest)
        self.write_licences()
        self.write_report()
        return manifest

    def write_licences(self):
        cfg = self.cfg
        lines = ["# Licences and attributions of the Sprint 1 test set", "",
                 "Public data, used for evaluation only. Audio and per-utterance texts stay on Drive.", ""]
        for name, src in cfg.sources.items():
            if "registry" in src:
                continue
            card = self.card_licences.get(name)
            lines.append(f"- **{name}**: {src.get('licence')} (config); dataset card licence field: {card or 'none stated'}; "
                         f"revision {self.pins.get(name, 'not used in this run')}; {src.get('hf') or src.get('git')}")
        if self.registry is not None:
            for dataset_id in ("librispeech-test-other", "musan"):
                entry = self.registry.datasets.datasets.get(dataset_id)
                if entry is not None:
                    lines += ["", f"## {dataset_id}", "", str(entry["attribution"]).strip()]
        drive.write_bytes(self.data / "LICENCES.md", ("\n".join(lines) + "\n").encode("utf-8"))

    def write_report(self):
        m = self.manifest
        lines = ["# Prep report", "", f"config hash `{m['config_hash'][:12]}`, commit `{m['git_commit'][:10]}`, seed {m['seed']}",
                 "", "| slice | requested | real N | clusters | hours | conditions |", "| --- | --- | --- | --- | --- | --- |"]
        for name, s in m["slices"].items():
            lines.append(f"| {name} | {s['requested']} | {s['n']} | {s['clusters']} | {s['hours']:.2f} | {len(s['conditions'])} |")
        for name, reason in m["dropped_slices"].items():
            lines.append(f"| {name} | dropped | 0 | 0 | 0 | {reason[:80]} |")
        lines += ["", "## Cleaning and selection notes", ""]
        for name, s in m["slices"].items():
            lines.append(f"- **{name}**: cleaning {json.dumps(s['cleaning'], sort_keys=True)}; "
                         f"{'; '.join(s['notes']) or 'no selection notes'}")
        drive.write_bytes(self.data / "prep_report.md", ("\n".join(lines) + "\n").encode("utf-8"))


def prep(cfg, out_dir, work_dir, repo_root, only=None, log=print):
    return Prep(cfg, out_dir, work_dir, repo_root, log).run(only)
