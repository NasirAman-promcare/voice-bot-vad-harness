"""Shared helpers for the WP-0.4 registry and pack tests (not a test module).

Every audio file made here is a test input generated at test time (tones and seeded noise), written into the
test's own temporary folder; none is ever pack content. Archives follow the real layouts of LibriSpeech and
MUSAN (folder names, trans.txt, README, LICENSE and ANNOTATIONS formats) so the real code paths run.
The HTTP server is a real server on 127.0.0.1 that supports range requests, counts the bytes it sends and can
cut a transfer short, so downloads, resumption and "download nothing twice" are tested for real.
"""
import contextlib
import csv
import hashlib
import http.server
import io
import json
import math
import random
import struct
import tarfile
import threading
from pathlib import Path

import numpy as np
import soundfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
RATE = 16000
FAST_MARKERS = "not slow and not gpu and not colab and not oracle and not network"


# ---------------------------------------------------------------------------------------------
# signals and files
# ---------------------------------------------------------------------------------------------
def tone(n_samples, freq=440.0, amplitude=8000, phase=0.0):
    t = np.arange(n_samples, dtype=np.float64)
    return np.round(amplitude * np.sin(2 * math.pi * freq * t / RATE + phase)).astype(np.int16)


def seeded_noise(n_samples, seed, amplitude=3000):
    rng = random.Random(seed)
    return np.array([rng.randint(-amplitude, amplitude) for _ in range(n_samples)], dtype=np.int16)


def wav_bytes(samples, rate=RATE, channels=1, bits=16, extra_chunk=b""):
    """A PCM WAV file; extra_chunk (for example a LIST chunk) is placed between fmt and data."""
    array = np.asarray(samples)
    if bits == 16:
        payload = array.astype("<i2").tobytes()
    elif bits == 8:
        payload = (array.astype(np.int32) // 256 + 128).astype(np.uint8).tobytes()
    else:
        raise ValueError(bits)
    block = channels * bits // 8
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * block, block, bits)
    body = b"WAVE" + fmt + extra_chunk + b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def list_chunk(text=b"ISFTLavf61.7.100\x00"):
    info = b"INFO" + text[:4] + struct.pack("<I", len(text) - 4) + text[4:]
    if len(info) % 2:
        info += b"\x00"
    return b"LIST" + struct.pack("<I", len(info)) + info


def flac_bytes(samples, rate=RATE):
    buf = io.BytesIO()
    soundfile.write(buf, np.asarray(samples, dtype=np.int16), rate, format="FLAC", subtype="PCM_16")
    return buf.getvalue()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def tar_gz(members):
    """gzip-compressed tar of [(name, bytes)] (regular files), deterministic."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(data))
    import gzip
    return gzip.compress(raw.getvalue(), mtime=0)


# ---------------------------------------------------------------------------------------------
# source archives shaped like the real ones
# ---------------------------------------------------------------------------------------------
LIBRISPEECH_LICENSE = (b"LibriSpeech (c) 2014 by Vassil Panayotov\n\nLibriSpeech ASR corpus is licensed under a\n"
                       b"Creative Commons Attribution 4.0 International License.\n\n"
                       b"See <http://creativecommons.org/licenses/by/4.0/>.\n")
WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]


def librispeech_members(split, speakers, utts_per_speaker, seconds=(1.0, 1.5, 2.0), seed=1):
    """Members of a LibriSpeech-shaped archive: speakers 100.., chapter 7, utterances 0000.. with transcripts.

    Returns (members, utterances) where utterances maps utterance ID to (n_samples, transcript, flac bytes).
    """
    rng = random.Random(seed)
    members = [("LibriSpeech/LICENSE.TXT", LIBRISPEECH_LICENSE), ("LibriSpeech/README.TXT", b"readme\n"),
               ("LibriSpeech/SPEAKERS.TXT", b";ID |SEX\n")]
    utterances = {}
    for s in range(speakers):
        spk = str(100 + s)
        trans = []
        for u in range(utts_per_speaker):
            utt = f"{spk}-7-{u:04d}"
            n = int(RATE * seconds[(s + u) % len(seconds)])
            samples = tone(n, freq=200 + 37 * s + 11 * u, amplitude=6000 + 97 * u)
            data = flac_bytes(samples)
            text = " ".join(rng.choice(WORDS) for _ in range(3 + u % 4)).upper()
            utterances[utt] = (n, text, data)
            members.append((f"LibriSpeech/{split}/{spk}/7/{utt}.flac", data))
            trans.append(f"{utt} {text}")
        members.append((f"LibriSpeech/{split}/{spk}/7/{spk}-7.trans.txt", ("\n".join(trans) + "\n").encode()))
    return members, utterances


FREE_SOUND_LICENSE = (b"All selected recordings were marked as in the Public Domain\n"
                      b"on Free Sound (url: https://www.freesound.org/).\n")


def rfm_licence(tracks):
    lines = ["CC BY 3.0", "http://incompetech.com/music/royalty-free/index.html?genre=Blues", "=" * 78]
    for name, title in tracks:
        lines += [name, f'"{title}" (by Kevin MacLeod)']
    return ("\n".join(lines) + "\n").encode()


def musan_members(n_noise=8, n_background=4, n_music=4, noise_seconds=4.0, music_seconds=12.0):
    """Members of a MUSAN-shaped archive with free-sound noise, rfm music and one fma file that must not be extracted."""
    members = [("musan/README", b"MUSAN readme\n"), ("musan/noise/README", b"noise readme\n"),
               ("musan/music/README", b"music readme\n")]
    noise_names = [f"noise-free-sound-{i:04d}" for i in range(n_noise)]
    for i, name in enumerate(noise_names):
        samples = seeded_noise(int(RATE * noise_seconds) + 1000 * i, seed=50 + i)
        members.append((f"musan/noise/free-sound/{name}.wav", wav_bytes(samples)))
    background = noise_names[:n_background]
    members.append(("musan/noise/free-sound/LICENSE", FREE_SOUND_LICENSE))
    members.append(("musan/noise/free-sound/ANNOTATIONS", ("Background noises:\n" + "\n".join(background) + "\n").encode()))
    tracks = [(f"music-rfm-{i:04d}", f"Track {i}") for i in range(n_music)]
    ann = []
    for i, (name, _) in enumerate(tracks):
        samples = tone(int(RATE * music_seconds), freq=330 + 50 * i, amplitude=5000)
        members.append((f"musan/music/rfm/{name}.wav", wav_bytes(samples)))
        ann.append(f"{name} blues N Kevin_MacLeod")
    members.append(("musan/music/rfm/LICENSE", rfm_licence(tracks)))
    members.append(("musan/music/rfm/ANNOTATIONS", ("\n".join(ann) + "\n").encode()))
    members.append(("musan/music/rfm/README", b"Source: http://incompetech.com/music/royalty-free/index.html\n"))
    members.append(("musan/music/fma/music-fma-0001.wav", wav_bytes(tone(RATE, 500))))
    members.append(("musan/music/fma/LICENSE", b"CC BY-SA 4.0\n"))
    return members


# ---------------------------------------------------------------------------------------------
# local folders (TTS clips and owner recordings)
# ---------------------------------------------------------------------------------------------
TTS_VOICES = ["af_heart", "am_michael", "bf_emma", "bm_george"]


def make_tts_folder(repo_root, folder="data/tts_smoke", count=4, seconds=4.0, crlf=True):
    """A TTS folder like data/tts_smoke: NN.wav (with a LIST chunk, as ffmpeg writes), transcripts.csv, GENERATION.md."""
    base = Path(repo_root) / folder
    base.mkdir(parents=True, exist_ok=True)
    rows, table = [("file", "text")], []
    for i in range(1, count + 1):
        name = f"{i:02d}.wav"
        text = " ".join(WORDS[(i + k) % len(WORDS)] for k in range(4))
        data = wav_bytes(tone(int(RATE * seconds) + 800 * i, freq=180 + 20 * i), extra_chunk=list_chunk())
        (base / name).write_bytes(data)
        rows.append((name, text))
        voice = TTS_VOICES[(i - 1) % len(TTS_VOICES)]
        table.append(f"| {name} | {voice} | {len(data) / 32000:.2f} | {sha256(data)} | {text} |")
    newline = "\r\n" if crlf else "\n"
    (base / "transcripts.csv").write_text(newline.join(",".join(r) for r in rows) + newline, encoding="utf-8")
    doc = ["# Synthetic smoke clips (TTS)", "", "These are synthetic speech, not human recordings.", "",
           "| File | Voice | Seconds | SHA-256 | Text |", "| --- | --- | --- | --- | --- |"] + table
    (base / "GENERATION.md").write_text("\n".join(doc) + "\n", encoding="utf-8")
    return base


def make_owner_folder(repo_root, folder="data/owner_smoke", count=3, seconds=4.0, consent=True):
    base = Path(repo_root) / folder
    base.mkdir(parents=True, exist_ok=True)
    rows = [("file", "text")]
    for i in range(1, count + 1):
        name = f"{i:02d}.wav"
        (base / name).write_bytes(wav_bytes(tone(int(RATE * seconds), freq=150 + 30 * i)))
        rows.append((name, f"owner sentence number {i}"))
    with open(base / "transcripts.csv", "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    if consent:
        (base / "CONSENT.md").write_text("The speaker agreed to lab use.\n", encoding="utf-8")
    return base


# ---------------------------------------------------------------------------------------------
# HTTP server with range support
# ---------------------------------------------------------------------------------------------
class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        return None

    def do_GET(self):
        server = self.server
        path = self.path.lstrip("/")
        data = server.files.get(path)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        start = 0
        rng = self.headers.get("Range")
        if rng and server.honour_range:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        limit = server.cut_after.pop(path, None)
        if limit is not None:
            body = body[:limit]
        server.sent[path] = server.sent.get(path, 0) + len(body)
        server.requests.append((path, rng))
        self.wfile.write(body)
        if limit is not None:
            self.wfile.flush()
            self.close_connection = True


@contextlib.contextmanager
def serve(files):
    """Serve {path: bytes} at http://127.0.0.1:<port>/<path>; yields the server (with .base, .sent, .requests)."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.files = dict(files)
    server.sent, server.requests, server.cut_after = {}, [], {}
    server.honour_range = True
    server.base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------------------------
# datasets.yaml for tests
# ---------------------------------------------------------------------------------------------
def licences_block():
    return {
        "CC-BY-4.0": {"name": "Creative Commons Attribution 4.0 International",
                      "url": "https://creativecommons.org/licenses/by/4.0/", "attribution_required": True,
                      "share_alike": False, "non_commercial": False},
        "CC-BY-3.0": {"name": "Creative Commons Attribution 3.0 Unported",
                      "url": "https://creativecommons.org/licenses/by/3.0/", "attribution_required": True,
                      "share_alike": False, "non_commercial": False},
        "CC-BY-SA-4.0": {"name": "Creative Commons Attribution-ShareAlike 4.0 International",
                         "url": "https://creativecommons.org/licenses/by-sa/4.0/", "attribution_required": True,
                         "share_alike": True, "non_commercial": False},
        "LicenseRef-public-domain": {"name": "Public domain, as marked by the source", "url": None,
                                     "attribution_required": False, "share_alike": False, "non_commercial": False},
        "CC0-1.0": {"name": "Creative Commons Zero v1.0 Universal",
                    "url": "https://creativecommons.org/publicdomain/zero/1.0/", "attribution_required": False,
                    "share_alike": False, "non_commercial": False},
        "Apache-2.0": {"name": "Apache License 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0",
                       "attribution_required": True, "share_alike": False, "non_commercial": False},
        "LicenseRef-AQIS-owner-consent": {"name": "Recorded for AQIS lab use only; not for redistribution",
                                          "url": None, "attribution_required": False, "share_alike": False,
                                          "non_commercial": True},
    }


def download_entry(url, data, source, importer, kind, extract, licence, **extra):
    entry = {"type": "download", "source": source, "kind": kind, "importer": importer, "url": url,
             "bytes": len(data), "sha256": sha256(data), "md5": hashlib.md5(data).hexdigest(),
             "extract": extract, "licence": licence, "homepage": "https://www.openslr.org/",
             "attribution": f"{source} test attribution text"}
    entry.update(extra)
    return entry


def write_datasets(path, datasets, generated_licence="CC0-1.0"):
    doc = {"format_version": 1, "licences": licences_block(), "generated_licence": generated_licence,
           "datasets": datasets}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    return Path(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------
# a complete test world: served archives, datasets.yaml, local folders, fetched cache
# ---------------------------------------------------------------------------------------------
RFM_TEMPLATE = ('"{title}" {artist} (incompetech.com), Licensed under Creative Commons: By Attribution 3.0, '
                'http://creativecommons.org/licenses/by/3.0/')


def musan_subsets(members):
    by_name = dict(members)
    return {
        "noise/free-sound": {"split": "noise", "licence": "LicenseRef-public-domain",
                             "licence_file_sha256": sha256(by_name["musan/noise/free-sound/LICENSE"]),
                             "annotations": "noise-background-list"},
        "music/rfm": {"split": "music", "licence": "CC-BY-3.0",
                      "licence_file_sha256": sha256(by_name["musan/music/rfm/LICENSE"]),
                      "annotations": "music-table", "titles": "rfm-licence", "attribution_template": RFM_TEMPLATE},
    }


class World:
    """Paths of a fetched test world: repo (holding data/ and datasets.yaml), cache, and the raw inputs."""

    def __init__(self, repo, cache, datasets_path, utterances, musan):
        self.repo, self.cache, self.datasets_path = repo, cache, datasets_path
        self.utterances, self.musan = utterances, musan

    def datasets(self):
        from aqis_lab.registry.datasets import load_datasets
        return load_datasets(self.datasets_path)


def world_datasets(base, archives, musan, owner=False, tts=True):
    entries = {
        "librispeech-test-clean": download_entry(f"{base}/ls/test-clean.tar.gz", archives["ls/test-clean.tar.gz"],
                                                 "librispeech", "librispeech", "speech",
                                                 ["LibriSpeech/*.TXT", "LibriSpeech/test-clean/**"], "CC-BY-4.0",
                                                 split="test-clean"),
        "librispeech-test-other": download_entry(f"{base}/ls/test-other.tar.gz", archives["ls/test-other.tar.gz"],
                                                 "librispeech", "librispeech", "speech",
                                                 ["LibriSpeech/*.TXT", "LibriSpeech/test-other/**"], "CC-BY-4.0",
                                                 split="test-other"),
        "musan": download_entry(f"{base}/musan.tar.gz", archives["musan.tar.gz"], "musan", "musan", "non-speech",
                                ["musan/README", "musan/noise/README", "musan/music/README",
                                 "musan/noise/free-sound/**", "musan/music/rfm/**"], "CC-BY-4.0",
                                subsets=musan_subsets(musan)),
    }
    if tts:
        entries["tts-smoke"] = {"type": "local", "source": "tts", "kind": "speech", "importer": "tts",
                                "folder": "data/tts_smoke", "split": "tts", "licence": "Apache-2.0",
                                "generation_record": "data/tts_smoke/GENERATION.md", "clip_prefix": "tts-smoke-",
                                "speaker_prefix": "kokoro-", "tags": ["synthetic", "tts"],
                                "homepage": "https://huggingface.co/hexgrad/Kokoro-82M",
                                "attribution": "Synthetic speech generated with hexgrad/Kokoro-82M (Apache-2.0).",
                                "changes": "0.4 s of silence added at each end; converted to 16 kHz mono 16-bit PCM"}
    if owner:
        entries["owner-smoke"] = {"type": "local", "source": "owner", "kind": "speech", "importer": "owner",
                                  "folder": "data/owner_smoke", "split": "owner",
                                  "licence": "LicenseRef-AQIS-owner-consent",
                                  "consent_file": "data/owner_smoke/CONSENT.md", "speaker_id": "owner",
                                  "clip_prefix": "owner-", "homepage": None,
                                  "attribution": "Recorded by the lab owner for AQIS lab use only."}
    return entries


def make_world(tmp, clean=(12, 3), other=(6, 2), musan_kwargs=None, owner=False, tts_count=4, reverse=False):
    """Serve generated archives, write datasets.yaml and local folders under tmp/repo, fetch into tmp/cache."""
    from aqis_lab.registry.datasets import load_datasets
    from aqis_lab.registry.fetch import fetch_dataset
    tmp = Path(tmp)
    repo, cache = tmp / "repo", tmp / "cache"
    repo.mkdir(parents=True, exist_ok=True)
    clean_members, utterances = librispeech_members("test-clean", *clean, seed=1)
    other_members, other_utts = librispeech_members("test-other", *other, seed=2)
    utterances.update({("other", k): v for k, v in other_utts.items()})
    musan = musan_members(**(musan_kwargs or {}))
    order = (lambda m: list(reversed(m))) if reverse else list
    archives = {"ls/test-clean.tar.gz": tar_gz(order(clean_members)), "ls/test-other.tar.gz": tar_gz(order(other_members)),
                "musan.tar.gz": tar_gz(order(musan))}
    if tts_count:
        make_tts_folder(repo, count=tts_count)
    if owner:
        make_owner_folder(repo)
    datasets_path = repo / "data" / "registry" / "datasets.yaml"
    with serve(archives) as server:
        write_datasets(datasets_path, world_datasets(server.base, archives, musan, owner=owner, tts=bool(tts_count)))
        loaded = load_datasets(datasets_path)
        for dataset in loaded.datasets.values():
            if dataset["type"] == "download":
                fetch_dataset(dataset, cache, repo)
    return World(repo, cache, datasets_path, utterances, musan)


# ---------------------------------------------------------------------------------------------
# a pack spec with the smoke spec's structure and smaller counts, and a helper to build it
# ---------------------------------------------------------------------------------------------
def spec_dict(**changes):
    spec = {
        "spec_version": 1, "manifest_id": "tpack", "version": "1.0.0",
        "purpose": "Test pack built by the WP-0.4 tests from generated inputs.",
        "created_utc": "2026-09-27T00:00:00Z", "seed": 20260927,
        "limits": {"max_files_per_folder": 1000, "max_archive_bytes": 200000000},
        "licence_policy": {"allow_share_alike": False, "allow_non_commercial": False},
        "categories": [
            {"name": "test-clean", "count": 4, "tags": ["clean", "speech"], "parts": [
                {"kind": "take", "count": 4, "from": {"source": "librispeech", "split": "test-clean", "min_seconds": 1,
                                                      "max_seconds": 2, "distinct_speakers": True}}]},
            {"name": "test-other", "count": 2, "tags": ["other", "speech"], "parts": [
                {"kind": "take", "count": 2, "from": {"source": "librispeech", "split": "test-other",
                                                      "distinct_speakers": True}}]},
            {"name": "noisy", "count": 3, "tags": ["noisy", "speech"], "parts": [
                {"kind": "mix", "label": "mix", "snr_db": [5, 10, 20],
                 "speech": {"source": "librispeech", "split": "test-clean", "min_seconds": 1, "max_seconds": 2,
                            "distinct_speakers": True},
                 "noise": {"source": "musan", "split": "noise", "tags_all": ["background"]}}]},
            {"name": "non-speech", "count": 3, "tags": ["non-speech"], "parts": [
                {"kind": "excerpt", "label": "noise", "count": 1, "seconds": 1.0, "tags": ["noise"],
                 "from": {"source": "musan", "split": "noise", "tags_none": ["background"]}},
                {"kind": "excerpt", "label": "music", "count": 1, "seconds": 2.0, "tags": ["music"],
                 "from": {"source": "musan", "split": "music"}},
                {"kind": "silence", "label": "silence", "seconds": [0.5], "tags": ["silence"]}]},
            {"name": "tts", "count": 2, "tags": ["speech", "synthetic", "tts"], "parts": [
                {"kind": "take", "count": 2, "from": {"source": "tts", "split": "tts", "min_seconds": 3,
                                                      "max_seconds": 8}}]},
        ],
    }
    spec.update(changes)
    return spec


def write_spec(path, spec=None, **changes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec or spec_dict(**changes), sort_keys=False), encoding="utf-8")
    return path


def write_registry(world, path=None):
    """Build the world's registry with the real importer and write it; returns its path."""
    from aqis_lab.registry.importers import build_registry
    from aqis_lab.registry.registry import registry_bytes
    path = Path(path or world.repo / "data" / "registry" / "sources.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(registry_bytes(build_registry(world.datasets(), world.cache, world.repo)))
    return path


def build_test_pack(world, out, spec_path=None, registry_path=None, **spec_changes):
    from aqis_lab.packs.build import build_pack
    spec_path = spec_path or write_spec(Path(out).parent / f"{Path(out).name}-spec.yaml", **spec_changes)
    registry_path = registry_path or write_registry(world)
    return build_pack(spec_path, out, registry_path, world.datasets_path, world.cache, world.repo)


def tar_members(path):
    """{name: bytes} of a tar file, read with the standard library."""
    with tarfile.open(path) as tf:
        return {m.name: tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
