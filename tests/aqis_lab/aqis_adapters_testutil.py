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
