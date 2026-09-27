"""WP-0.4 FR-0.4-05: pack build (aqis_lab/packs/build.py, archive.py) and the pack command."""
import hashlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import wave
from pathlib import Path

import numpy as np
import pytest
import soundfile

from aqis_packs_testutil import (ROOT, build_test_pack, make_world, read_json, tar_members, write_registry,
                                 write_spec, spec_dict)
from aqis_lab.contracts.canonical import sha256_canonical
from aqis_lab.contracts.validate import validate_manifest
from aqis_lab.packs import build as pack_build
from aqis_lab.packs import mix
from aqis_lab.packs.audio import canonical_wav, read_wav

CATEGORY_ORDER = ["test-clean", "test-other", "noisy", "non-speech", "tts"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("built")
    world = make_world(base / "world")
    out = base / "pack"
    build_test_pack(world, out)
    return world, out


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_FR_0_4_05_manifest_valid_under_wp_0_2_schema(built):
    _, out = built
    manifest = read_json(out / "manifest.json")
    assert validate_manifest(manifest) is None
    assert manifest["schema_version"] == "1.0" and manifest["manifest_id"] == "tpack" and manifest["version"] == "1.0.0"
    for clip in manifest["clips"]:
        if clip["recipe"] is not None:
            assert mix.recipe_problems(clip["recipe"]) == [], clip["clip_id"]
    text = (out / "manifest.json").read_text(encoding="utf-8")
    assert text == json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def test_FR_0_4_05_archive_hashes_sizes_and_member_counts_recorded(built):
    _, out = built
    manifest = read_json(out / "manifest.json")
    clips_by_archive = {}
    for clip in manifest["clips"]:
        clips_by_archive.setdefault(clip["archive"], []).append(clip)
    assert [a["name"] for a in manifest["archives"]] == [f"tpack-1.0.0-{c}-000.tar" for c in CATEGORY_ORDER]
    for archive in manifest["archives"]:
        path = out / archive["name"]
        assert archive["sha256"] == _sha(path) and archive["bytes"] == path.stat().st_size
        members = tar_members(path)
        assert archive["n_members"] == len(members) == len(clips_by_archive[archive["name"]])
        for clip in clips_by_archive[archive["name"]]:
            assert hashlib.sha256(members[clip["member_path"]]).hexdigest() == clip["sha256"]


def test_FR_0_4_05_members_in_documented_order(built):
    _, out = built
    manifest = read_json(out / "manifest.json")
    ids = [c["clip_id"] for c in manifest["clips"]]
    expected = []
    for category in CATEGORY_ORDER:
        expected += sorted(c["clip_id"] for c in manifest["clips"] if c["split"] == category)
    assert ids == expected
    for archive in manifest["archives"]:
        with tarfile.open(out / archive["name"]) as tf:
            names = [m.name for m in tf.getmembers()]
        category = archive["name"].split("-1.0.0-")[1].rsplit("-", 1)[0]
        assert names == [f"{category}/{c}.wav" for c in sorted(c["clip_id"] for c in manifest["clips"]
                                                               if c["archive"] == archive["name"])]


def test_FR_0_4_05_tar_headers_are_normalised(built):
    _, out = built
    import calendar
    import time
    epoch = calendar.timegm(time.strptime("2026-09-27T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"))
    for tar_path in sorted(out.glob("*.tar")):
        raw = tar_path.read_bytes()
        assert raw[257:263] == b"ustar\x00"
        with tarfile.open(tar_path) as tf:
            for m in tf.getmembers():
                assert (m.type, m.mode, m.uid, m.gid, m.uname, m.gname, m.mtime) == (
                    tarfile.REGTYPE, 0o644, 0, 0, "", "", epoch), (tar_path.name, m.name)
        assert len(raw) % tarfile.RECORDSIZE == 0


def _cli_build(world, spec, registry, out, cwd, seed, tz, umask):
    command = (f"umask {umask} && exec {sys.executable} -m aqis_lab pack build {spec} --out {out} --registry "
               f"{registry} --datasets {world.datasets_path} --cache {world.cache} --repo-root {world.repo}")
    env = dict(os.environ, PYTHONHASHSEED=seed, TZ=tz, PYTHONPATH=str(ROOT))
    done = subprocess.run(["sh", "-c", command], capture_output=True, text=True, cwd=cwd, env=env)
    assert done.returncode == 0, done.stderr
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


def test_FR_0_4_05_build_twice_byte_identical(tmp_path, built):
    world, first_out = built
    spec = write_spec(tmp_path / "spec.yaml")
    registry = write_registry(world, tmp_path / "sources.csv")
    (tmp_path / "elsewhere").mkdir()
    a = _cli_build(world, spec, registry, tmp_path / "a", ROOT, "0", "UTC", "022")
    b = _cli_build(world, spec, registry, tmp_path / "b", tmp_path / "elsewhere", "4242", "Asia/Kolkata", "077")
    assert a == b
    assert set(a) == {"manifest.json", "LICENCES.md", "build_record.json"} | {p.name for p in first_out.glob("*.tar")}
    in_process = {p.name: p.read_bytes() for p in first_out.iterdir()}
    for name in a:
        if name != "build_record.json":           # the fixture's registry file is another file with the same rows
            assert a[name] == in_process[name], name
    # the registry's row order does not matter either (only the build record names the registry file's hash)
    lines = registry.read_text(encoding="utf-8").splitlines()
    body = lines[1:]
    random.Random(8).shuffle(body)
    shuffled = tmp_path / "shuffled.csv"
    shuffled.write_text("\n".join([lines[0]] + body) + "\n", encoding="utf-8")
    c = _cli_build(world, spec, shuffled, tmp_path / "c", ROOT, "1", "UTC", "022")
    assert {k: v for k, v in c.items() if k != "build_record.json"} == \
        {k: v for k, v in a.items() if k != "build_record.json"}


def test_FR_0_4_05_created_utc_comes_from_spec(tmp_path, built):
    world, out = built
    assert read_json(out / "manifest.json")["created_utc"] == "2026-09-27T00:00:00Z"
    other = tmp_path / "other"
    build_test_pack(world, other, created_utc="2030-01-02T03:04:05Z")
    assert read_json(other / "manifest.json")["created_utc"] == "2030-01-02T03:04:05Z"
    with tarfile.open(next(other.glob("*.tar"))) as tf:
        assert {m.mtime for m in tf.getmembers()} == {1893553445}
    for name in ("LICENCES.md",):
        assert (other / name).read_bytes() == (out / name).read_bytes()


def test_FR_0_4_05_clips_hold_the_source_samples(built):
    world, out = built
    manifest = read_json(out / "manifest.json")
    members = {}
    for archive in manifest["archives"]:
        members.update(tar_members(out / archive["name"]))
    for clip in manifest["clips"]:
        data = members[clip["member_path"]]
        with wave.open(io.BytesIO(data)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
            assert clip["duration_s"] == w.getnframes() / 16000
        if clip["split"] in ("test-clean", "test-other"):
            flac = world.cache / f"librispeech-{clip['split']}" / clip["source_ref"]
            samples, _ = soundfile.read(flac, dtype="int16")
            assert data == canonical_wav(samples)
            assert clip["recipe"] is None and clip["source"] == "librispeech"
        if clip["split"] == "tts":
            _, samples = read_wav((world.repo / clip["source_ref"]).read_bytes())
            assert data == canonical_wav(samples)
            assert clip["licence"] == "Apache-2.0" and clip["consent_ref"] is None and "synthetic" in clip["tags"]


def test_FR_0_4_05_derived_clips_match_their_recipes(built):
    world, out = built
    manifest = read_json(out / "manifest.json")
    members = {}
    for archive in manifest["archives"]:
        members.update(tar_members(out / archive["name"]))
    from aqis_lab.registry.datasets import load_datasets
    from aqis_lab.registry.registry import load_registry
    rows = {r.clip_id: r for r in load_registry(world.repo / "data/registry/sources.csv", load_datasets(world.datasets_path), world.repo)}

    def load(clip_id):
        row = rows[clip_id]
        path = (world.cache / row.dataset / row.source_ref) if row.dataset != "tts-smoke" else world.repo / row.source_ref
        if path.suffix == ".flac":
            return soundfile.read(path, dtype="int16")[0]
        return read_wav(path.read_bytes())[1]

    derived = [c for c in manifest["clips"] if c["recipe"] is not None]
    assert {c["recipe"]["kind"] for c in derived} == {"mix", "excerpt", "silence"}
    for clip in derived:
        assert members[clip["member_path"]] == canonical_wav(mix.render_recipe(clip["recipe"], load)), clip["clip_id"]
        if clip["recipe"]["kind"] == "mix":
            speech = rows[clip["recipe"]["speech_clip_id"]]
            assert clip["transcript"] == speech.transcript and clip["speaker_id"] == speech.speaker_id
            assert clip["source"] == "mix" and clip["licence"] == "CC-BY-4.0 AND LicenseRef-public-domain"
            assert clip["recipe"]["seed"] == 20260927
        else:
            assert clip["transcript"] is None and clip["speaker_id"] is None
    assert [c["licence"] for c in derived if c["recipe"]["kind"] == "silence"] == ["CC0-1.0"]


def test_FR_0_4_05_build_refuses_existing_output(tmp_path, built):
    world, _ = built
    out = tmp_path / "pack"
    out.mkdir()
    (out / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(pack_build.BuildError, match="already exists"):
        build_test_pack(world, out)
    assert [p.name for p in out.iterdir()] == ["keep.txt"]
    fresh = tmp_path / "fresh"
    (tmp_path / ".fresh.partial").mkdir()
    with pytest.raises(pack_build.BuildError, match="staging folder"):
        build_test_pack(world, fresh)
    assert not fresh.exists()


def test_FR_0_4_05_build_rejects_source_with_wrong_hash(tmp_path):
    world = make_world(tmp_path / "w")
    registry = write_registry(world)
    for target in (world.cache / "musan" / "musan" / "music" / "rfm").glob("*.wav"):
        data = bytearray(target.read_bytes())
        data[-1] ^= 1                                  # same size, one bit changed after registration
        target.write_bytes(bytes(data))
    with pytest.raises(pack_build.BuildError, match=r"music-rfm-[0-9]{4}\.wav: SHA-256 .* differs from the registry"):
        build_test_pack(world, tmp_path / "pack", registry_path=registry,
                        categories=[spec_dict()["categories"][3]])


def test_FR_0_4_05_failed_build_leaves_nothing(tmp_path):
    world = make_world(tmp_path / "w")
    registry = write_registry(world)
    target = next((world.cache / "musan" / "musan" / "music" / "rfm").glob("*.wav"))
    for p in (world.cache / "musan" / "musan" / "music" / "rfm").glob("*.wav"):
        p.write_bytes(p.read_bytes()[:-2])            # every music file changed after registration
    with pytest.raises(pack_build.BuildError):
        build_test_pack(world, tmp_path / "pack", registry_path=registry)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pack-spec.yaml", "w"]
    assert target.exists()


def test_FR_0_4_05_build_record_traces_inputs(built):
    world, out = built
    record = read_json(out / "build_record.json")
    spec_path = out.parent / "pack-spec.yaml"
    assert record["pack_spec"] == {"name": "pack-spec.yaml", "sha256": _sha(spec_path)}
    assert record["registry"] == {"name": "sources.csv", "sha256": _sha(world.repo / "data/registry/sources.csv")}
    assert record["datasets"] == {"name": "datasets.yaml", "sha256": _sha(world.datasets_path)}
    assert record["seed"] == 20260927 and record["record_version"] == "1.0"
    assert record["manifest_sha256"] == sha256_canonical(read_json(out / "manifest.json"))
    assert (record["manifest_id"], record["version"]) == ("tpack", "1.0.0")
    assert (out / "build_record.json").read_bytes() == json.dumps(record, sort_keys=True, indent=2).encode() + b"\n"


def test_FR_0_4_05_pack_and_registry_listed_by_dispatcher():
    done = subprocess.run([sys.executable, "-m", "aqis_lab", "--help"], capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0
    assert "pack " in done.stdout and "registry " in done.stdout
    for command in ("pack", "registry"):
        done = subprocess.run([sys.executable, "-m", "aqis_lab", command, "--help"], capture_output=True, text=True,
                              cwd=ROOT)
        assert done.returncode == 0, done.stderr


def test_FR_0_4_05_cli_exit_codes(tmp_path, built):
    world, out = built
    run = lambda *args: subprocess.run([sys.executable, "-m", "aqis_lab", "pack", *map(str, args)],
                                       capture_output=True, text=True, cwd=ROOT)
    ok = run("verify", out)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "pack tpack 1.0.0: OK, 14 clips in 5 archives; test-clean 4, test-other 2, noisy 3, non-speech 3, tts 2" \
        in ok.stdout
    broken = tmp_path / "broken"
    shutil.copytree(out, broken)
    (broken / "LICENCES.md").unlink()
    bad = run("verify", broken)
    assert bad.returncode == 1 and "INVALID" in bad.stdout and "LICENCES.md" in bad.stdout
    assert run("verify", tmp_path / "missing").returncode == 2
    spec = write_spec(tmp_path / "bad.yaml", spec_dict(seed=-1))
    failed = run("build", spec, "--out", tmp_path / "x", "--registry", world.repo / "data/registry/sources.csv",
                 "--datasets", world.datasets_path, "--cache", world.cache, "--repo-root", world.repo)
    assert failed.returncode == 2 and "ERROR" in failed.stderr and not (tmp_path / "x").exists()
