"""Sprint 2 stage runners: VAD, turn-end, CPU streaming STT and emotion over the prepared test sets, writing traced result files.

CAPABILITIES:
  CAP-S2-050: run_vad() runs each configured VAD over data/vad/<condition>.parquet and writes results/vad/<model>__<condition>.parquet:
    per clip the speech runs, the onset and offset lag of every reference segment, the miss and false-alarm sample counts for
    every collar, DET counts for VADs that give scores, and the compute time; run_turn() runs the fixed timers and the
    predictive policies over data/turn and writes the endpoint triggers; run_stream() streams data/stream clips in 20 ms packets
    through a rolling-window CPU decode and writes the step timings; run_emotion() scores data/emotion with each emotion model and
    writes the four class scores [no unit test: they need corpora, weights and the target machines; the pieces they call are
    tested in test_s2_vad_score.py, test_s2_turn.py, test_s2_frames.py, test_s2_emotion.py and test_s2_data.py; the smoke stage
    runs each on 3 clips]
  CAP-S2-051: smoke() runs every component on a few clips and prints what each returned, stopping at the first error [same]
INPUTS AND OUTPUTS: s2.yaml, the output folder with data/ from prep; parquet result files out; StageError.
CONTRACTS: brief sections 3 and 6; CLAUDE.md rules 3 and 6 (smoke, pilot with --limit, then full).
INVARIANTS:
  - A result file is resumable: a rerun computes only the clips it does not hold, and a different model revision is refused.
  - A model file or weight is fetched from a pinned reference, and a fetched file's SHA-256 is recorded in models/pins.json on
    first use and checked on every later use.
  - An input that is missing stops the run; no stand-in audio, text or score is used.
NOT IN SCOPE:
  - Metrics and tables (aqis_lab/live/score.py and report.py) and building the data (aqis_lab/live/prep.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import time
import urllib.request
from pathlib import Path

import numpy as np

from aqis_lab import drive
from aqis_lab import platform as platform_facts
from aqis_lab.bench import lib
from aqis_lab.bench.run import git_commit
from aqis_lab.live import emotion, results, score, streaming, turn, vad
from aqis_lab.live.prep import read_data

SR = 16000
PACKAGES = ("numpy", "onnxruntime", "onnx-asr", "huggingface-hub", "transformers", "torch", "funasr", "soundfile", "webrtcvad",
            "ten-vad", "pyarrow")


class StageError(RuntimeError):
    """A stage cannot run as asked."""


# ---- run facts ---------------------------------------------------------------------------------------------------
def machine_info():
    block = platform_facts.machine_block()
    return f"{block['cpu_model']}, {block['architecture']}, {os.cpu_count()} logical cores"


def gpu_name():
    torch = lib("torch")
    return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None


def lib_versions():
    found = {}
    for name in PACKAGES:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return json.dumps(found, sort_keys=True)


class Run:
    def __init__(self, cfg, out_dir, repo_root, log=print, machine=None):
        self.cfg, self.out, self.repo, self.log = cfg, Path(out_dir), Path(repo_root), log
        self.data, self.models, self.results = self.out / "data", self.out / "models", self.out / "results"
        self.commit = git_commit(self.repo)
        self.machine = machine or machine_info()
        self.versions = lib_versions()
        self.arch = platform_facts.machine_block()["architecture"]

    def trace(self, component, model, revision, slice_name, condition):
        if not revision:
            raise StageError(f"{component} {model}: no revision to record")
        return {"component": component, "model": model, "revision": revision, "slice": slice_name, "condition": condition,
                "seed": self.cfg.seed, "git_commit": self.commit, "machine": self.machine, "versions": self.versions,
                "utc": results.utc_now()}

    def clips(self, set_name, condition, limit=None):
        path = self.data / set_name / f"{condition}.parquet"
        if not path.exists():
            raise StageError(f"{path} is missing; run `python -m aqis_lab.live prep` first")
        rows = read_data(path)
        return rows[:limit] if limit else rows

    def result_path(self, component, name, condition):
        return self.results / component / f"{name}__{condition}.parquet"

    def pin_file(self, key, sha256):
        """Record a fetched file's hash the first time, refuse a different one later."""
        path = self.models / "pins.json"
        pins = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if pins.get(key, sha256) != sha256:
            raise StageError(f"{key} now hashes to {sha256}, but the first fetch recorded {pins[key]}")
        if key not in pins:
            pins[key] = sha256
            drive.make_dirs(path.parent)
            drive.write_bytes(path, (json.dumps(pins, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    def fetch_url(self, url, name):
        dest = self.models / name
        if not dest.exists():
            self.log(f"fetching {url}")
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            drive.make_dirs(dest.parent)
            drive.write_bytes(dest, data)
        self.pin_file(name, hashlib.sha256(dest.read_bytes()).hexdigest())
        return dest

    def hf_file(self, repo_id, filename, revision):
        return Path(lib("huggingface_hub").hf_hub_download(repo_id, filename, revision=revision, cache_dir=self.models / "hf"))


def _int16(data):
    return np.frombuffer(data, dtype="<i2").copy()


def _runs_ms(flags, frame_ms):
    runs, start = [], None
    for k, flag in enumerate(flags):
        if flag and start is None:
            start = k
        if not flag and start is not None:
            runs.append((start * frame_ms, k * frame_ms))
            start = None
    if start is not None:
        runs.append((start * frame_ms, len(flags) * frame_ms))
    return runs


def _pending(path, rows):
    return results.missing_ids(path, [r["utt_id"] for r in rows])


# ---- VAD ---------------------------------------------------------------------------------------------------------
def vad_names(cfg, arch):
    names = []
    for name, spec in cfg.vad.items():
        if not cfg.vad_supported(name, arch):
            continue
        if name == "webrtc_vad":
            names += [f"webrtc_vad_mode{m}" for m in spec.get("modes", [spec.get("mode")]) if m is not None]
        else:
            names.append(name)
    return names


def ten_vad_library():
    """Path of libten_vad.so inside the installed ten-vad package (Linux x86_64 only), which the harness adapter cannot find alone."""
    spec = importlib.util.find_spec("ten_vad")
    if spec is None or not spec.origin:
        raise StageError("the ten-vad package is not installed (it has no build for this machine's architecture, or the s2-live lock was not installed)")
    path = Path(spec.origin).parent / "lib" / "Linux" / "x64" / "libten_vad.so"
    if not path.is_file():
        raise StageError(f"the ten-vad package holds no libten_vad.so for Linux x86_64 at {path}")
    return path


def export_ten_vad_library():
    """Point the harness's TEN VAD adapter at the package's library unless the environment already names one."""
    if "TEN_VAD_LIB_PATH" not in os.environ:
        os.environ["TEN_VAD_LIB_PATH"] = str(ten_vad_library())


def make_vad(run, name):
    """(adapter, smoother or None, revision) for a configured VAD name."""
    cfg = run.cfg
    base = "webrtc_vad" if name.startswith("webrtc_vad_mode") else name
    spec = cfg.vad[base]
    if base.startswith("silero"):
        url = f"https://raw.githubusercontent.com/{spec['repo']}/{spec['ref']}/{spec['file']}"
        path = run.fetch_url(url, f"{base}.onnx")
        adapter = vad.SileroVAD(name, spec["model_version"], path, spec["threshold"])
        revision = f"{spec['repo']}@{spec['ref']}"
    elif base == "firered_vad":
        root = Path(lib("huggingface_hub").snapshot_download(spec["hf"], revision=spec["revision"], cache_dir=run.models / "hf",
                                                             allow_patterns=["Stream-VAD/*", "config.yaml"]))
        adapter = vad.HarnessVAD(name, "firered_vad", model_dir=str(root / "Stream-VAD"), speech_threshold=spec["threshold"])
        revision = f"{spec['hf']}@{spec['revision']}"
    elif base == "ten_vad":
        export_ten_vad_library()
        adapter = vad.HarnessVAD(name, "ten_vad", hop_size=int(spec["hop_size_ms"] * SR / 1000), threshold=spec["threshold"])
        revision = f"{spec['package']}=={importlib.metadata.version(spec['package'])}"
    else:
        adapter = vad.HarnessVAD(name, name)
        revision = f"webrtcvad=={importlib.metadata.version('webrtcvad')}"
    smoother = None
    if "min_speech_ms" in spec or "min_silence_ms" in spec:
        smoother = vad.HysteresisSmoother(adapter.frame_samples * 1000 // SR, spec.get("min_speech_ms", 0), spec.get("min_silence_ms", 0))
    return adapter, smoother, revision


def vad_decide(adapter, smoother, samples):
    d = vad.run_vad(adapter, samples)
    if smoother is not None:
        d = vad.Decisions(d.frame_samples, smoother.apply(d.speech), d.score, d.n_scored_samples, d.compute_s)
    return d


def run_vad(run, names=None, conditions=None, limit=None):
    cfg = run.cfg
    names = names or vad_names(cfg, run.arch)
    collars, thresholds = cfg.scoring["collars_ms"], cfg.scoring["det_thresholds"]
    for name in names:
        adapter, smoother, revision = make_vad(run, name)
        frame_ms = adapter.frame_samples * 1000.0 / SR
        for condition in conditions or cfg.conditions["vad"]:
            rows = run.clips("vad", condition, limit)
            path = run.result_path("vad", name, condition)
            todo = set(_pending(path, rows))
            if not todo:
                run.log(f"vad {name}/{condition}: complete, skipped")
                continue
            payloads = []
            for row in rows:
                if row["utt_id"] not in todo:
                    continue
                samples = _int16(row["audio"])
                ref = json.loads(row["ref"])["segments_ms"]
                d = vad_decide(adapter, smoother, samples)
                timings = score.segment_timings(ref, d)
                payloads.append({
                    "utt_id": row["utt_id"], "cluster": row["cluster"], "frame_samples": d.frame_samples,
                    "n_scored_samples": d.n_scored_samples, "audio_s": len(samples) / SR, "compute_s": d.compute_s,
                    "runs_ms": json.dumps(_runs_ms(d.speech, frame_ms)),
                    "onset_lags_ms": json.dumps([t.onset_lag_ms for t in timings]),
                    "offset_lags_ms": json.dumps([t.offset_lag_ms for t in timings]),
                    "counts": json.dumps({str(c): score.vad_counts(ref, d, collar_ms=c) for c in collars}),
                    "det": json.dumps(score.det_counts(ref, d, thresholds) if not np.isnan(d.score).any() else None)})
            results.merge_rows(path, results.make_rows(run.trace("vad", name, revision, "vad", condition), payloads))
            run.log(f"vad {name}/{condition}: {len(payloads)} clips")


# ---- turn end ----------------------------------------------------------------------------------------------------
def make_smart_turn(run):
    """(factory(samples) -> Predictive, revision) for the Smart Turn policy of the config."""
    spec = run.cfg.turn_end["predictive"]["smart_turn"]
    model = turn.SmartTurn(run.hf_file(spec["hf"], spec["file"], spec["revision"]))

    def factory(samples):
        return turn.Predictive(lambda t_ms: model.probability(samples[:int(t_ms * SR / 1000)]), spec["threshold"],
                               spec["min_silence_ms"], spec["query_every_ms"], spec["max_wait_ms"])
    return factory, f"{spec['hf']}@{spec['revision']}:{spec['file']}"


def run_turn(run, policies=None, conditions=None, limit=None):
    cfg = run.cfg
    adapter, smoother, vad_revision = make_vad(run, cfg.turn_end["vad"])
    frame_ms = adapter.frame_samples * 1000 // SR
    known = [f"fixed_{t}" for t in cfg.turn_end["fixed_thresholds_ms"]] + list(cfg.turn_end["predictive"])
    for policy in policies or known:
        if policy not in known:
            raise StageError(f"unknown turn policy {policy!r} (one of {', '.join(known)})")
        for condition in conditions or cfg.conditions["turn"]:
            rows = run.clips("turn", condition, limit)
            path = run.result_path("turn", policy, condition)
            todo = set(_pending(path, rows))
            if not todo:
                run.log(f"turn {policy}/{condition}: complete, skipped")
                continue
            if policy == "smart_turn":
                factory, model_revision = make_smart_turn(run)
                revision = f"{vad_revision}+{model_revision}"
            else:
                threshold = int(policy.split("_")[1])
                factory, revision = (lambda t=threshold: turn.FixedSilence(t)), vad_revision
            payloads = []
            for row in rows:
                if row["utt_id"] not in todo:
                    continue
                samples = _int16(row["audio"])
                d = vad_decide(adapter, smoother, samples)
                ref = json.loads(row["ref"])
                pol = factory(samples) if policy == "smart_turn" else factory()
                triggers = turn.endpoints(pol, d.speech, frame_ms)
                outcome = score.turn_outcome(triggers, [tuple(p) for p in ref["pauses_ms"]], ref["end_ms"], row["cluster"])
                payloads.append({"utt_id": row["utt_id"], "cluster": row["cluster"], "triggers_ms": json.dumps(triggers),
                                 "pauses": outcome.pauses, "false_interruptions": outcome.false_interruptions,
                                 "spurious": outcome.spurious, "latency_ms": outcome.latency_ms, "missed_end": outcome.missed_end,
                                 "end_ms": ref["end_ms"], "compute_s": d.compute_s})
            results.merge_rows(path, results.make_rows(run.trace("turn", policy, revision, "turn", condition), payloads))
            run.log(f"turn {policy}/{condition}: {len(payloads)} turns")


# ---- streaming STT -----------------------------------------------------------------------------------------------
def make_stt(run, variant):
    """(decode(samples int16) -> text, revision) for an onnx-asr variant of the configured model, from the pinned repository."""
    spec = run.cfg.stt_streaming["variants"][variant]
    onnx_asr, ort, hub = lib("onnx_asr"), lib("onnxruntime"), lib("huggingface_hub")
    ignore = ["*.int8.onnx"] if not spec["quantization"] else ["encoder-model.onnx*", "decoder_joint-model.onnx"]
    root = hub.snapshot_download(spec["hf"], revision=spec["revision"], cache_dir=run.models / "hf", ignore_patterns=ignore)
    options = ort.SessionOptions()
    options.inter_op_num_threads = options.intra_op_num_threads = run.cfg.stt_streaming["threads"]
    kwargs = {"quantization": spec["quantization"]} if spec["quantization"] else {}
    model = onnx_asr.load_model(spec["onnx_asr_name"], path=root, providers=["CPUExecutionProvider"], sess_options=options, **kwargs)

    def decode(samples):
        return model.recognize(np.asarray(samples, dtype=np.float32) / 32768.0)
    return decode, f"{spec['hf']}@{spec['revision']}[{spec['quantization'] or 'fp32'}] onnx-asr=={importlib.metadata.version('onnx-asr')}"


def run_stream(run, variants=None, chunks=None, conditions=None, limit=None):
    cfg = run.cfg
    stt = cfg.stt_streaming
    for variant in variants or list(stt["variants"]):
        decode, revision = make_stt(run, variant)
        warm = _int16(run.clips("stream", (conditions or cfg.conditions["stream"])[0], 1)[0]["audio"])[:SR]
        decode(warm)                                                   # the first call builds buffers: not timed, not scored
        for chunk_ms in chunks or stt["chunk_sizes_ms"]:
            streamer = streaming.RollingStreamer(decode, SR, chunk_ms, stt["window_ms"], time.perf_counter)
            for condition in conditions or cfg.conditions["stream"]:
                rows = run.clips("stream", condition, limit)
                path = run.result_path("stream", f"{variant}__c{chunk_ms}", condition)
                todo = set(_pending(path, rows))
                if not todo:
                    run.log(f"stream {variant}/c{chunk_ms}/{condition}: complete, skipped")
                    continue
                payloads = []
                for row in rows:
                    if row["utt_id"] not in todo:
                        continue
                    samples = _int16(row["audio"])
                    result = streamer.run(samples)
                    started = time.perf_counter()
                    decode(samples)                                    # one decode of the whole clip: what a bot pays at the end of a turn
                    offline_s = time.perf_counter() - started
                    payloads.append({"utt_id": row["utt_id"], "cluster": row["cluster"], "chunk_ms": chunk_ms,
                                     "window_ms": stt["window_ms"], "audio_s": result.audio_ms / 1000.0, "compute_s": result.compute_s,
                                     "rtf": result.rtf, "offline_compute_s": offline_s, "n_steps": len(result.steps),
                                     "step_compute_ms": json.dumps([round(s.compute_ms, 3) for s in result.steps]),
                                     "final_text": result.steps[-1].text if result.steps else ""})
                results.merge_rows(path, results.make_rows(run.trace("stream", f"{variant}__c{chunk_ms}", revision, "stream", condition),
                                                           payloads))
                run.log(f"stream {variant}/c{chunk_ms}/{condition}: {len(payloads)} clips")


# ---- emotion -----------------------------------------------------------------------------------------------------
def make_emotion(run, name, device):
    spec = run.cfg.emotion[name]
    if name.startswith("emotion2vec"):
        return emotion.Emotion2Vec(spec["hf"], spec["revision"]), f"{spec['hf']}@{spec['revision']}"
    if name == "wav2vec2_er":
        return emotion.Wav2Vec2Emotion(spec["hf"], spec["revision"], device), f"{spec['hf']}@{spec['revision']}"
    raise StageError(f"emotion model {name!r} is built by run_emotion")


def run_emotion(run, names=None, conditions=None, limit=None, device="cpu"):
    cfg = run.cfg
    conditions = conditions or cfg.conditions["emotion"]
    for name in names or list(cfg.emotion):
        if name == "acoustic_baseline":
            _run_baseline(run, conditions, limit)
            continue
        model, revision = make_emotion(run, name, device)
        for condition in conditions:
            rows = run.clips("emotion", condition, limit)
            path = run.result_path("emotion", name, condition)
            todo = set(_pending(path, rows))
            if not todo:
                run.log(f"emotion {name}/{condition}: complete, skipped")
                continue
            payloads = []
            for row in rows:
                if row["utt_id"] not in todo:
                    continue
                started = time.perf_counter()
                probs = model.scores(_int16(row["audio"]))
                payloads.append({"utt_id": row["utt_id"], "cluster": row["cluster"], "label": row["label"],
                                 "scores": json.dumps([round(float(p), 6) for p in probs]),
                                 "pred": emotion.CLASSES[int(np.argmax(probs))], "compute_s": time.perf_counter() - started})
            results.merge_rows(path, results.make_rows(run.trace("emotion", name, revision, "emotion", condition), payloads))
            run.log(f"emotion {name}/{condition}: {len(payloads)} clips")


def _run_baseline(run, conditions, limit):
    """The acoustic baseline is trained on the clean clips of the actors outside each fold and scored on the held-out actors."""
    cfg = run.cfg
    folds = cfg.emotion["acoustic_baseline"]["folds"]
    clean = run.clips("emotion", "clean", limit)
    actors = sorted({r["cluster"] for r in clean})
    fold_of = {a: i % folds for i, a in enumerate(actors)}
    train = [(r["cluster"], emotion.AcousticBaseline.vector(_int16(r["audio"])), emotion.CLASSES.index(r["label"])) for r in clean]
    models = {}
    for fold in range(folds):
        keep = [(x, y) for actor, x, y in train if fold_of[actor] != fold]
        model = emotion.AcousticBaseline(cfg.seed)
        model.classifier.fit([x for x, _ in keep], [y for _, y in keep], len(emotion.CLASSES))
        models[fold] = model
    revision = f"acoustic features + logistic regression, {folds}-fold by actor, trained on clean clips"
    for condition in conditions:
        rows = run.clips("emotion", condition, limit)
        path = run.result_path("emotion", "acoustic_baseline", condition)
        todo = set(_pending(path, rows))
        if not todo:
            run.log(f"emotion acoustic_baseline/{condition}: complete, skipped")
            continue
        payloads = []
        for row in rows:
            if row["utt_id"] not in todo:
                continue
            started = time.perf_counter()
            probs = models[fold_of[row["cluster"]]].scores(_int16(row["audio"]))
            payloads.append({"utt_id": row["utt_id"], "cluster": row["cluster"], "label": row["label"],
                             "scores": json.dumps([round(float(p), 6) for p in probs]),
                             "pred": emotion.CLASSES[int(np.argmax(probs))], "compute_s": time.perf_counter() - started})
        results.merge_rows(path, results.make_rows(run.trace("emotion", "acoustic_baseline", revision, "emotion", condition), payloads))
        run.log(f"emotion acoustic_baseline/{condition}: {len(payloads)} clips")


# ---- smoke ---------------------------------------------------------------------------------------------------------
def smoke(run, device="cpu", clips=3):
    """Run every component on `clips` clips of its first condition; returns the list of failures (empty when all ran)."""
    cfg = run.cfg
    steps = [("vad", lambda: run_vad(run, conditions=cfg.conditions["vad"][:1], limit=clips)),
             ("turn", lambda: run_turn(run, conditions=cfg.conditions["turn"][:1], limit=clips)),
             ("stream", lambda: run_stream(run, chunks=cfg.stt_streaming["chunk_sizes_ms"][:1],
                                           conditions=cfg.conditions["stream"][:1], limit=clips)),
             ("emotion", lambda: run_emotion(run, conditions=cfg.conditions["emotion"][:1], limit=clips, device=device))]
    failures = []
    for name, step in steps:
        try:
            step()
        except Exception as exc:                          # one component failing must not hide the others' smoke result
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            run.log(f"SMOKE FAILURE {failures[-1]}")
    return failures
