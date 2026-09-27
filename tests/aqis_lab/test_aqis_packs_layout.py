"""WP-0.4 FR-0.4-06: Drive-friendly layout: at most 1,000 files per folder and 200 MB per archive (archive.py)."""
import hashlib
import io
import json
import shutil
import tarfile

import pytest

from aqis_packs_testutil import ROOT, build_test_pack, make_world, read_json, spec_dict, tar_members, write_spec
from aqis_lab.packs import archive
from aqis_lab.packs import spec as pack_spec
from aqis_lab.packs.build import BuildError
from aqis_lab.packs.verify import verify_pack


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("layout"))


def _independent_tar_size(sizes):
    """POSIX tar: a 512-byte header per member, data padded to 512, two zero blocks, padded to 20 blocks."""
    total = sum(512 + ((n + 511) // 512) * 512 for n in sizes) + 1024
    return ((total + 10239) // 10240) * 10240


@pytest.mark.parametrize("sizes", [[], [0], [1], [511], [512], [513], [44 + 32000, 44 + 64000], [9000] * 7])
def test_FR_0_4_06_tar_size_is_exact(sizes):
    members = [(f"c/{i}.wav", bytes([i % 256]) * n) for i, n in enumerate(sizes)]
    assert archive.tar_size(sizes) == _independent_tar_size(sizes) == len(archive.tar_bytes(members, 0))


def test_FR_0_4_06_splits_archives_at_size_limit(tmp_path, world):
    limit = 150_000
    result = build_test_pack(world, tmp_path / "pack", limits={"max_files_per_folder": 1000,
                                                               "max_archive_bytes": limit})
    manifest = result.manifest
    for entry in manifest["archives"]:
        assert (tmp_path / "pack" / entry["name"]).stat().st_size == entry["bytes"] <= limit
    for category in ("test-clean", "noisy", "tts"):
        sizes = [44 + 2 * round(c["duration_s"] * 16000) for c in manifest["clips"] if c["split"] == category]
        expected, current = [], []
        for size in sizes:                                  # greedy, in member order, computed here
            if current and _independent_tar_size(current + [size]) > limit:
                expected.append(current)
                current = []
            current.append(size)
        expected.append(current)
        names = [a["name"] for a in manifest["archives"] if f"-{category}-" in a["name"]]
        assert names == [f"tpack-1.0.0-{category}-{i:03d}.tar" for i in range(len(expected))]
        assert [a["n_members"] for a in manifest["archives"] if a["name"] in names] == [len(s) for s in expected]
    assert len(manifest["archives"]) > 5
    assert verify_pack(tmp_path / "pack").ok


def test_FR_0_4_06_splits_member_folders_at_1000_files(tmp_path, world):
    many = {"name": "many", "count": 1001, "tags": ["silence"],
            "parts": [{"kind": "silence", "label": "quiet", "seconds": [0.01] * 1001, "tags": []}]}
    result = build_test_pack(world, tmp_path / "pack", categories=[many])
    paths = [c["member_path"] for c in result.manifest["clips"]]
    assert paths[0] == "many/000/tpack-quiet-0001.wav" and paths[999].startswith("many/000/")
    assert paths[1000] == "many/001/tpack-quiet-1001.wav"
    counts = {}
    for path in paths:
        folder = path.rsplit("/", 1)[0]
        counts[folder] = counts.get(folder, 0) + 1
    assert counts == {"many/000": 1000, "many/001": 1}
    assert verify_pack(tmp_path / "pack").ok
    four = {"max_files_per_folder": 4, "max_archive_bytes": 200000000}   # the pack folder then holds exactly 4
    small = build_test_pack(world, tmp_path / "small", categories=[dict(many, count=13, parts=[dict(
        many["parts"][0], seconds=[0.01] * 13)])], limits=four)
    assert [c["member_path"].rsplit("/", 1)[0] for c in small.manifest["clips"]] == \
        ["many/000"] * 4 + ["many/001"] * 4 + ["many/002"] * 4 + ["many/003"]
    with pytest.raises(BuildError, match="more than 4 folders of 4"):   # 17 clips would need 5 subfolders
        build_test_pack(world, tmp_path / "too-many", categories=[dict(many, count=17, parts=[dict(
            many["parts"][0], seconds=[0.01] * 17)])], limits=four)


@pytest.mark.parametrize("limits,message", [
    ({"max_files_per_folder": 1001, "max_archive_bytes": 200000000}, "above the hard cap of 1000 files"),
    ({"max_files_per_folder": 1000, "max_archive_bytes": 200000001}, "above the hard cap of 200000000 bytes"),
])
def test_FR_0_4_06_rejects_limits_above_hard_caps(tmp_path, limits, message):
    assert (archive.MAX_FILES_PER_FOLDER, archive.MAX_ARCHIVE_BYTES) == (1000, 200_000_000)
    with pytest.raises(pack_spec.SpecError, match=message):
        pack_spec.load_spec(write_spec(tmp_path / "s.yaml", limits=limits))


def test_FR_0_4_06_rejects_clip_larger_than_archive_limit(tmp_path, world):
    with pytest.raises(BuildError, match="does not fit in one archive of at most 20000 bytes"):
        build_test_pack(world, tmp_path / "pack", limits={"max_files_per_folder": 1000, "max_archive_bytes": 20000})
    assert not (tmp_path / "pack").exists()


def _repin(pack, name):
    manifest = read_json(pack / "manifest.json")
    data = (pack / name).read_bytes()
    for entry in manifest["archives"]:
        if entry["name"] == name:
            entry["sha256"], entry["bytes"] = hashlib.sha256(data).hexdigest(), len(data)
    (pack / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def test_FR_0_4_06_verify_fails_on_oversized_archive(tmp_path, world):
    build_test_pack(world, tmp_path / "pack")
    pack = tmp_path / "pack"
    name = read_json(pack / "manifest.json")["archives"][-1]["name"]
    with open(pack / name, "ab") as fh:
        for _ in range(20):
            fh.write(bytes(10_000_000))                    # 200,000,000 more bytes of zero records
    _repin(pack, name)
    problems = verify_pack(pack).problems
    assert any(p.startswith(f"{name}: ") and "more than 200000000" in p for p in problems), problems


def test_FR_0_4_06_verify_fails_on_crowded_folder(tmp_path, world):
    build_test_pack(world, tmp_path / "pack")
    pack = tmp_path / "pack"
    for i in range(1000):
        (pack / f"extra-{i:04d}.txt").write_bytes(b"")
    entries = len(list(pack.iterdir()))
    problems = verify_pack(pack).problems
    assert entries > 1000 and any(f"pack folder has {entries} entries, more than 1000" in p for p in problems)
    for p in pack.glob("extra-*.txt"):
        p.unlink()
    name = read_json(pack / "manifest.json")["archives"][0]["name"]
    members = tar_members(pack / name)
    crowded = [(path, data) for path, data in members.items()] + [(f"test-clean/x{i:04d}.wav", b"") for i in range(1001)]
    (pack / name).write_bytes(archive.tar_bytes(crowded, 0))
    _repin(pack, name)
    problems = verify_pack(pack).problems
    assert any("folder 'test-clean' has 1005 entries, more than 1000" in p for p in problems), problems[:3]


def test_FR_0_4_06_layout_doc_states_the_limits():
    text = (ROOT / "docs" / "data" / "SMOKE_PACK.md").read_text(encoding="utf-8")
    section = text.split("## Layout", 1)[1].split("\n## ", 1)[0]
    assert "1,000" in section and "200,000,000 bytes" in section
    assert "<category>/<clip_id>.wav" in section and "<category>/<nnn>/<clip_id>.wav" in section
    assert "<manifest_id>-<version>-<category>-<nnn>.tar" in section
