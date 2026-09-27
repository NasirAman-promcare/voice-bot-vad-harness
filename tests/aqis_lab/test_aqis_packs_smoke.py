"""WP-0.4: the committed registry and smoke pack (data/registry/, data/packs/smoke/v1/), and the real rebuild.

Fast tests read only committed files. The slow network tests fetch the real sources (about 11.8 GB) into the
git-ignored cache when it lacks them, then rebuild the smoke pack and time the build.
"""
import csv
import hashlib
import io
import json
import re
import tarfile
import time
import wave

import pytest

from aqis_packs_testutil import ROOT
from aqis_lab.packs.licences import listed_clips
from aqis_lab.packs.verify import verify_pack
from aqis_lab.registry import datasets as ds
from aqis_lab.registry.registry import load_registry

PACK = ROOT / "data" / "packs" / "smoke" / "v1"
REGISTRY = ROOT / "data" / "registry" / "sources.csv"
DATASETS = ROOT / "data" / "registry" / "datasets.yaml"
SPEC = ROOT / "packs" / "specs" / "smoke_v1.yaml"
# FR-0.4-03, written out here from the spec (with the owner's deviation D6: tts replaces owner).
EXPECTED_COUNTS = {"test-clean": 20, "test-other": 10, "noisy": 10, "non-speech": 10, "tts": 10}


def _manifest():
    return json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))


def test_FR_0_4_01_committed_datasets_file_is_valid():
    loaded = ds.load_datasets(DATASETS)
    assert set(loaded.datasets) == {"librispeech-test-clean", "librispeech-test-other", "musan", "tts-smoke"}
    assert not [d for d in loaded.datasets.values() if d["source"] in ds.CONSENT_SOURCES]   # no owner data in phase 0


def test_FR_0_4_01_committed_registry_is_valid():
    rows = load_registry(REGISTRY, ds.load_datasets(DATASETS), ROOT)
    assert len(rows) == 6559


def test_FR_0_4_01_committed_registry_row_counts():
    with open(REGISTRY, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    counts = {}
    for row in rows:
        counts[(row["source"], row["split"])] = counts.get((row["source"], row["split"]), 0) + 1
    # 2,620 and 2,939: the LibriSpeech paper's test-clean and test-other utterance counts; 147: the lines of
    # MUSAN music/rfm/ANNOTATIONS; 10: the synthetic TTS clips; no owner recordings in phase 0.
    assert counts[("librispeech", "test-clean")] == 2620 and counts[("librispeech", "test-other")] == 2939
    assert counts[("musan", "music")] == 147 and counts[("tts", "tts")] == 10
    assert not [r for r in rows if r["source"] in ("owner", "campaign") or r["consent_ref"]]
    assert sum("background" in r["tags"].split() for r in rows) == 37


def test_FR_0_4_01_tts_rows_match_generation_record():
    """The 10 tts rows against data/tts_smoke/GENERATION.md and the files, recomputed here."""
    record = (ROOT / "data" / "tts_smoke" / "GENERATION.md").read_text(encoding="utf-8")
    table = {m.group(1): (m.group(2), m.group(3), m.group(4)) for m in re.finditer(
        r"^\| (\d\d\.wav) \| (\w+) \| [\d.]+ \| ([0-9a-f]{64}) \| (.+?) \|$", record, flags=re.M)}
    assert len(table) == 10
    with open(REGISTRY, encoding="utf-8", newline="") as fh:
        rows = {r["clip_id"]: r for r in csv.DictReader(fh) if r["source"] == "tts"}
    for name, (voice, sha, text) in table.items():
        row = rows[f"tts-smoke-{name[:2]}"]
        data = (ROOT / "data" / "tts_smoke" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha == row["sha256"]
        assert row["transcript"] == text and row["speaker_id"] == f"kokoro-{voice}"
        assert (row["licence"], row["consent_ref"], row["split"]) == ("Apache-2.0", "", "tts")
        assert "synthetic" in row["tags"].split()


def test_FR_0_4_05_committed_smoke_pack_verifies():
    report = verify_pack(PACK)
    assert report.ok, report.problems
    assert report.summary() == ("pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, "
                                "noisy 10, non-speech 10, tts 10")


def test_FR_0_4_03_committed_smoke_pack_has_exact_counts():
    manifest = _manifest()
    counts = {}
    for clip in manifest["clips"]:
        counts[clip["split"]] = counts.get(clip["split"], 0) + 1
    assert counts == EXPECTED_COUNTS
    snrs = sorted(c["recipe"]["snr_db"] for c in manifest["clips"] if c["split"] == "noisy")
    assert snrs == [5, 5, 5, 5, 10, 10, 10, 20, 20, 20]
    kinds = sorted(t for c in manifest["clips"] if c["split"] == "non-speech" for t in c["tags"] if t != "non-speech")
    assert kinds == ["music"] * 4 + ["noise"] * 4 + ["silence"] * 2
    for archive in manifest["archives"]:
        with tarfile.open(PACK / archive["name"]) as tf:
            for member in tf.getmembers():
                with wave.open(io.BytesIO(tf.extractfile(member).read())) as w:
                    assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype()) == (
                        16000, 1, 2, "NONE"), member.name
    tts = [c for c in manifest["clips"] if c["split"] == "tts"]
    assert all(c["licence"] == "Apache-2.0" and c["consent_ref"] is None and "synthetic" in c["tags"] for c in tts)
    assert all(3 <= c["duration_s"] <= 8 for c in tts)
    for category, n in (("test-clean", 20), ("test-other", 10), ("noisy", 10)):
        assert len({c["speaker_id"] for c in manifest["clips"] if c["split"] == category}) == n, category


def test_FR_0_4_07_committed_licences_cover_committed_manifest():
    text = (PACK / "LICENCES.md").read_text(encoding="utf-8")
    manifest = _manifest()
    assert listed_clips(text) == {c["clip_id"]: c["licence"] for c in manifest["clips"]}
    assert "Kevin MacLeod (incompetech.com)" in text and "hexgrad/Kokoro-82M" in text and "LibriSpeech ASR corpus" in text
    assert "MUSAN: A Music, Speech, and Noise Corpus" in text


def test_FR_0_4_05_committed_build_record_names_committed_inputs():
    record = json.loads((PACK / "build_record.json").read_text(encoding="utf-8"))
    for key, path in (("pack_spec", SPEC), ("registry", REGISTRY), ("datasets", DATASETS)):
        assert record[key] == {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, key


def _fetch_real_sources():
    from aqis_lab.registry.fetch import DEFAULT_CACHE, fetch_dataset
    loaded = ds.load_datasets(DATASETS)
    for dataset in loaded.datasets.values():
        if dataset["type"] == "download":
            fetch_dataset(dataset, ROOT / DEFAULT_CACHE, ROOT)
    return ROOT / DEFAULT_CACHE


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_4_05_rebuild_equals_committed_smoke_pack(tmp_path):
    from aqis_lab.packs.build import build_pack
    cache = _fetch_real_sources()
    out = tmp_path / "v1"
    build_pack(SPEC, out, REGISTRY, DATASETS, cache, ROOT)
    assert sorted(p.name for p in out.iterdir()) == sorted(p.name for p in PACK.iterdir())
    for path in PACK.iterdir():
        assert (out / path.name).read_bytes() == path.read_bytes(), path.name


@pytest.mark.slow
@pytest.mark.network
def test_NFR_0_4_01_smoke_build_under_2_minutes(tmp_path):
    from aqis_lab.packs.build import build_pack
    cache = _fetch_real_sources()                      # fetching is a separate step, not timed
    start = time.monotonic_ns()
    build_pack(SPEC, tmp_path / "v1", REGISTRY, DATASETS, cache, ROOT)
    elapsed_s = (time.monotonic_ns() - start) / 1e9
    assert elapsed_s < 120, elapsed_s
