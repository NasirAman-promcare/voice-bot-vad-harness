"""WP-0.4 FR-0.4-01: registry rows from fetched datasets and local folders (aqis_lab/registry/importers.py)."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aqis_packs_testutil import (ROOT, RFM_TEMPLATE, make_owner_folder, make_tts_folder, make_world, sha256,
                                 wav_bytes, tone)
from aqis_lab.registry import importers
from aqis_lab.registry import registry as reg


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("world"), owner=True)


def _rows(world):
    return {r.clip_id: r for r in importers.build_registry(world.datasets(), world.cache, world.repo)}


def test_FR_0_4_01_librispeech_rows_from_archive(world):
    rows = _rows(world)
    clean = [r for r in rows.values() if r.split == "test-clean"]
    assert len(clean) == 12 * 3
    for utt, (n, text, data) in ((k, v) for k, v in world.utterances.items() if isinstance(k, str)):
        row = rows[f"ls-test-clean-{utt}"]
        spk, chap, _ = utt.split("-")
        assert row.source == "librispeech" and row.dataset == "librispeech-test-clean"
        assert row.source_ref == f"LibriSpeech/test-clean/{spk}/{chap}/{utt}.flac"
        assert row.transcript == text and row.speaker_id == spk and row.n_samples == n
        assert row.sha256 == hashlib.sha256(data).hexdigest()
        assert (row.licence, row.consent_ref, row.sample_rate_hz, row.channels) == ("CC-BY-4.0", None, 16000, 1)
    assert len([r for r in rows.values() if r.split == "test-other"]) == 6 * 2


def test_FR_0_4_01_musan_rows_carry_subset_licence_and_titles(world):
    rows = _rows(world)
    noise = sorted((r for r in rows.values() if r.split == "noise"), key=lambda r: r.clip_id)
    music = sorted((r for r in rows.values() if r.split == "music"), key=lambda r: r.clip_id)
    assert [r.clip_id for r in noise] == [f"musan-noise-free-sound-{i:04d}" for i in range(8)]
    assert [r.tags for r in noise] == [("background",)] * 4 + [()] * 4
    assert {r.licence for r in noise} == {"LicenseRef-public-domain"}
    assert all(r.speaker_id is None and r.transcript is None for r in noise + music)
    assert [r.clip_id for r in music] == [f"musan-music-rfm-{i:04d}" for i in range(4)]
    assert {r.licence for r in music} == {"CC-BY-3.0"}
    assert music[2].attribution == RFM_TEMPLATE.format(title="Track 2", artist="Kevin MacLeod")
    assert music[0].tags == ("genre-blues", "vocals-no")
    files = dict(world.musan)
    assert noise[1].sha256 == sha256(files["musan/noise/free-sound/noise-free-sound-0001.wav"])
    assert not any("fma" in r.clip_id for r in rows.values())


def test_FR_0_4_01_musan_licence_file_must_match_its_pin(world, tmp_path):
    datasets = world.datasets()
    licence = world.cache / "musan" / "musan" / "music" / "rfm" / "LICENSE"
    original = licence.read_bytes()
    try:
        licence.write_bytes(original.replace(b"CC BY 3.0", b"CC BY-SA 3.0"))
        with pytest.raises(importers.SourceImportError, match="LICENSE.*does not match its pin"):
            importers.build_registry(datasets, world.cache, world.repo)
    finally:
        licence.write_bytes(original)


def test_FR_0_4_01_tts_rows_carry_synthetic_voice_and_apache_licence(world):
    rows = _rows(world)
    tts = sorted((r for r in rows.values() if r.source == "tts"), key=lambda r: r.clip_id)
    assert [r.clip_id for r in tts] == ["tts-smoke-01", "tts-smoke-02", "tts-smoke-03", "tts-smoke-04"]
    assert [r.speaker_id for r in tts] == ["kokoro-af_heart", "kokoro-am_michael", "kokoro-bf_emma", "kokoro-bm_george"]
    assert tts[0].tags == ("synthetic", "tts", "voice-af-heart")
    assert all(r.licence == "Apache-2.0" and r.consent_ref is None and r.split == "tts" for r in tts)
    base = world.repo / "data" / "tts_smoke"
    assert tts[1].sha256 == sha256((base / "02.wav").read_bytes())
    assert tts[1].transcript == (base / "transcripts.csv").read_text().splitlines()[2].split(",", 1)[1]


def _local_world(tmp_path, maker, **kwargs):
    from aqis_packs_testutil import write_datasets, world_datasets
    repo = tmp_path / "repo"
    maker(repo, **kwargs)
    entries = world_datasets("http://127.0.0.1", {"ls/test-clean.tar.gz": b"a", "ls/test-other.tar.gz": b"b",
                                                   "musan.tar.gz": b"c"},
                             [("musan/noise/free-sound/LICENSE", b"x"), ("musan/music/rfm/LICENSE", b"y")],
                             owner=maker is make_owner_folder, tts=maker is make_tts_folder)
    local = {k: v for k, v in entries.items() if v["type"] == "local"}
    from aqis_lab.registry.datasets import load_datasets
    datasets = load_datasets(write_datasets(repo / "data" / "registry" / "datasets.yaml", local))
    return repo, datasets


def test_FR_0_4_01_tts_rows_match_generation_record(tmp_path):
    repo, datasets = _local_world(tmp_path, make_tts_folder, count=3)
    assert len(importers.build_registry(datasets, tmp_path / "cache", repo)) == 3
    record = repo / "data" / "tts_smoke" / "GENERATION.md"
    text = record.read_text(encoding="utf-8")
    digest = sha256((repo / "data" / "tts_smoke" / "02.wav").read_bytes())
    record.write_text(text.replace(digest, "0" * 64), encoding="utf-8")
    with pytest.raises(importers.SourceImportError, match="02.wav.*SHA-256.*GENERATION.md"):
        importers.build_registry(datasets, tmp_path / "cache", repo)
    record.write_text(text, encoding="utf-8")
    transcripts = repo / "data" / "tts_smoke" / "transcripts.csv"
    lines = transcripts.read_bytes().split(b"\r\n")
    lines[2] = lines[2] + b" extra"                       # 02.wav's text no longer equals the TTS input text
    transcripts.write_bytes(b"\r\n".join(lines))
    with pytest.raises(importers.SourceImportError, match="02.wav.*text differs"):
        importers.build_registry(datasets, tmp_path / "cache", repo)


def test_FR_0_4_01_owner_import_rows_have_consent(tmp_path):
    repo, datasets = _local_world(tmp_path, make_owner_folder)
    rows = importers.build_registry(datasets, tmp_path / "cache", repo)
    assert [r.clip_id for r in rows] == ["owner-01", "owner-02", "owner-03"]
    assert all(r.consent_ref == "data/owner_smoke/CONSENT.md" and r.source == "owner" and r.speaker_id == "owner"
               for r in rows)


def _break_owner(base, problem):
    if problem == "missing transcript":
        lines = (base / "transcripts.csv").read_text().splitlines()
        (base / "transcripts.csv").write_text("\n".join(lines[:-1]) + "\n")
    elif problem == "extra transcript":
        with open(base / "transcripts.csv", "a") as fh:
            fh.write("09.wav,no such file\n")
    elif problem == "empty text":
        text = (base / "transcripts.csv").read_text().replace("owner sentence number 2", "")
        (base / "transcripts.csv").write_text(text)
    elif problem == "wrong format":
        (base / "02.wav").write_bytes(wav_bytes(tone(48000), rate=48000))
    elif problem == "bad file name":
        (base / "02.wav").rename(base / "Take 2.wav")
        text = (base / "transcripts.csv").read_text().replace("02.wav", "Take 2.wav")
        (base / "transcripts.csv").write_text(text)
    elif problem == "missing CONSENT.md":
        (base / "CONSENT.md").unlink()
    elif problem == "unexpected file":
        (base / "03.m4a").write_bytes(b"x")
    elif problem == "wrong header":
        text = (base / "transcripts.csv").read_text().replace("file,text", "name,text")
        (base / "transcripts.csv").write_text(text)


@pytest.mark.parametrize("problem,message", [
    ("missing transcript", "03.wav has no row in transcripts.csv"),
    ("extra transcript", "09.wav.*no such WAV file"),
    ("empty text", "empty text"),
    ("wrong format", "48000 Hz"),
    ("bad file name", "Take 2.wav.*lowercase letters"),
    ("missing CONSENT.md", "consent file data/owner_smoke/CONSENT.md"),
    ("unexpected file", "03.m4a.*not expected"),
    ("wrong header", "header must be exactly file,text"),
])
def test_FR_0_4_01_owner_import_rejects_bad_inputs(tmp_path, problem, message):
    repo, datasets = _local_world(tmp_path, make_owner_folder)
    _break_owner(repo / "data" / "owner_smoke", problem)
    with pytest.raises(importers.SourceImportError, match=message):
        importers.build_registry(datasets, tmp_path / "cache", repo)


def test_FR_0_4_01_librispeech_rejects_missing_transcript(tmp_path):
    world = make_world(tmp_path, clean=(2, 2), other=(1, 1), tts_count=0)
    trans = world.cache / "librispeech-test-clean" / "LibriSpeech" / "test-clean" / "100" / "7" / "100-7.trans.txt"
    lines = trans.read_text().splitlines()
    trans.write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(importers.SourceImportError, match="has no transcript"):
        importers.build_registry(world.datasets(), world.cache, world.repo)
    trans.write_text("\n".join(lines + ["100-7-0099 NOT A FILE"]) + "\n")
    with pytest.raises(importers.SourceImportError, match="100-7-0099.*no FLAC file"):
        importers.build_registry(world.datasets(), world.cache, world.repo)


def test_FR_0_4_01_build_requires_fetched_datasets(tmp_path, world):
    with pytest.raises(importers.SourceImportError, match="not fetched"):
        importers.build_registry(world.datasets(), tmp_path / "empty-cache", world.repo)


def test_FR_0_4_01_build_is_deterministic(tmp_path, world):
    """Two registry builds by the command, with archives in the opposite member order and another hash seed."""
    other = make_world(tmp_path / "reversed", owner=True, reverse=True)
    outs = []
    for w, seed in ((world, "1"), (other, "987")):
        out = tmp_path / f"sources-{seed}.csv"
        env = dict(os.environ, PYTHONHASHSEED=seed)
        done = subprocess.run([sys.executable, "-m", "aqis_lab", "registry", "build", "--datasets",
                               str(w.datasets_path), "--cache", str(w.cache), "--repo-root", str(w.repo), "--out",
                               str(out)], capture_output=True, text=True, cwd=ROOT, env=env)
        assert done.returncode == 0, done.stderr
        outs.append(out.read_bytes())
    assert outs[0] == outs[1]
    rows = reg.load_registry_bytes(outs[0], world.datasets(), world.repo, "x")
    assert reg.registry_bytes(rows) == outs[0]
    text = outs[0].decode("utf-8")
    assert "\r" not in text and text.splitlines()[0] == ",".join(reg.COLUMNS)
    ids = [line.split(",", 1)[0] for line in text.splitlines()[1:]]
    assert ids == sorted(ids)
