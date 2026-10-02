"""Helpers for the WP-0.7 adapter, runner-event, smoke and parity tests.

- drive_view(): a Colab SystemView whose Google Drive mount is a local folder (the Drive test double of WP-0.5).
- vosk_model(): the real Vosk model, downloaded once per test session into a git-ignored cache and verified against
  config/aqis_lab/models.yaml (tests that call it are marked `network`).
- wav_bytes() / tone(): real 16-bit PCM WAV clips generated in the test.
Expected values in tests are computed independently of the code under test.
"""
import io
import wave
from pathlib import Path

import numpy as np

from aqis_lab import platform as lp
from aqis_runner_testutil import colab_env, drive_mountinfo_line, make_system_tree, stand_in_drive
from aqis_testutil import ROOT

MODELS_YAML = ROOT / "config" / "aqis_lab" / "models.yaml"
SESSION_MODEL_CACHE = ROOT / "data" / "raw" / "aqis_lab" / "test-model-cache"


def drive_view(tmp_path):
    """(SystemView of a Colab runtime with a Drive mount, the mount folder)."""
    mount = stand_in_drive(tmp_path)
    root = make_system_tree(Path(tmp_path) / "sys", mountinfo=drive_mountinfo_line(mount))
    return lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin")), mount


def vosk_model():
    """Path of the real, verified Vosk model (downloaded on first use; later tests reuse the verified cache)."""
    from aqis_lab.adapters import model_cache
    pin = model_cache.load_pins(MODELS_YAML)["vosk-model-small-en-us-0.15"]
    return model_cache.fetch(pin, SESSION_MODEL_CACHE)


def wav_bytes(samples, rate=16000, channels=1):
    samples = np.asarray(samples, dtype="<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def tone(seconds, freq=440.0, amplitude=8000, rate=16000):
    t = np.arange(int(round(seconds * rate))) / rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


SMOKE_PACK = ROOT / "data" / "packs" / "smoke" / "v1"


def smoke_clip(clip_id):
    """(manifest clip, WAV bytes) of one smoke-pack clip, read straight from its archive and checked by SHA-256."""
    import hashlib
    import json
    import tarfile
    manifest = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
    clip = next(c for c in manifest["clips"] if c["clip_id"] == clip_id)
    with tarfile.open(SMOKE_PACK / clip["archive"]) as tar:
        data = tar.extractfile(clip["member_path"]).read()
    assert hashlib.sha256(data).hexdigest() == clip["sha256"]
    return clip, data


def samples_of(data):
    """int16 samples of a 16 kHz mono 16-bit WAV (read with the standard library, independently of the lab)."""
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").copy()


def make_bundle(root, name, texts, refs, target="cloud", platform="cloud-vm", card_char="a", extra_tasks=None):
    """A result bundle in the documented format (docs/runs/PHASE0_SMOKE.md), built here without aqis_lab.smoke:
    runs/vosk-batch/results.jsonl from `texts` ({clip_id: text}), and scores/vosk-batch-natural/ from the real WP-0.3
    `score` command against `refs`; BUNDLE.json lists every file with its SHA-256 and size."""
    import csv
    import hashlib
    import json
    import subprocess
    import sys
    bundle = Path(root) / name
    runs = bundle / "runs" / "vosk-batch"
    runs.mkdir(parents=True)
    card_id = card_char * 64
    rows = [{"clip_id": c, "run_card_id": card_id, "task": "vosk-batch", "task_version": "1.0", "text": t,
             "text_sha256": hashlib.sha256(t.encode("utf-8")).hexdigest()} for c, t in texts.items()]
    (runs / "results.jsonl").write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                                                for r in rows), encoding="utf-8")
    for task, task_rows in (extra_tasks or {}).items():
        (bundle / "runs" / task).mkdir(parents=True)
        (bundle / "runs" / task / "results.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in task_rows), encoding="utf-8")
    inputs = Path(root) / f"{name}.inputs"
    inputs.mkdir()
    with open(inputs / "ref.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["clip_id", "text"])
        w.writerows([[c, refs[c]] for c in texts if c in refs])
    with open(inputs / "hyp.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["run_card_id", "clip_id", "text"])
        w.writerows([[card_id, c, texts[c]] for c in texts if c in refs])
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "score", "--ref", str(inputs / "ref.csv"), "--hyp",
                           str(inputs / "hyp.csv"), "--out", str(bundle / "scores" / "vosk-batch-natural")],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    (bundle / "PHASE0_SMOKE.md").write_text(f"# test bundle {name}\n", encoding="utf-8")
    files = {p.relative_to(bundle).as_posix(): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    meta = {"bundle_version": "1.0", "name": name, "target": target, "platform": platform,
            "machine": {"platform": platform, "cpu_model": "test CPU", "architecture": "x86_64", "os": "test OS",
                        "python_version": "3.13.0", "gpu": None},
            "git": {"commit": "c" * 40, "dirty": False},
            "locks": [{"file": "requirements/aqis_lab/phase0.txt", "sha256": "d" * 64}],
            "runs": {"vosk-batch": {"run_card_id": card_id}},
            "files": {rel: {"sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)} for rel, d in sorted(files.items())}}
    (bundle / "BUNDLE.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle


def tar_bundle(bundle):
    import tarfile
    tar_path = bundle.parent / f"{bundle.name}.tar"
    with tarfile.open(tar_path, "w") as tar:
        for p in sorted(bundle.rglob("*")):
            if p.is_file():
                tar.add(p, arcname=f"{bundle.name}/{p.relative_to(bundle).as_posix()}")
    return tar_path
