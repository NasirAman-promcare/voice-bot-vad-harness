"""WP-0.4 FR-0.4-05: pack verify recomputes every hash and checks every entry (aqis_lab/packs/verify.py).

Each test breaks a copy of a built pack in one way. Where the break would also change the archive's own hash, the
test updates the manifest's archive entry too, so that the member-level check alone must catch it.
"""
import hashlib
import io
import json
import shutil
import tarfile

import pytest

from aqis_packs_testutil import build_test_pack, make_world, read_json
from aqis_lab.packs.verify import VerifyInputError, verify_pack


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("verify")
    world = make_world(base / "world")
    out = base / "pack"
    build_test_pack(world, out)
    return out


@pytest.fixture
def pack(tmp_path, built):
    copy = tmp_path / "pack"
    shutil.copytree(built, copy)
    return copy


def _manifest(pack):
    return read_json(pack / "manifest.json")


def _write_manifest(pack, manifest):
    (pack / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _rewrite(pack, archive_name, transform, update_manifest=True):
    """Rewrite one archive through transform([(TarInfo, bytes|None)]) and, if asked, re-pin it in the manifest."""
    path = pack / archive_name
    with tarfile.open(path) as tf:
        members = [(m, tf.extractfile(m).read() if m.isfile() else None) for m in tf.getmembers()]
    members = transform(members)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for info, data in members:
            if data is not None:
                info.size = len(data)
            tf.addfile(info, io.BytesIO(data) if data is not None else None)
    path.write_bytes(buf.getvalue())
    if update_manifest:
        manifest = _manifest(pack)
        for entry in manifest["archives"]:
            if entry["name"] == archive_name:
                entry["sha256"] = hashlib.sha256(buf.getvalue()).hexdigest()
                entry["bytes"] = len(buf.getvalue())
        _write_manifest(pack, manifest)
        # keep the build record consistent, so only the intended problem remains
        from aqis_lab.contracts.canonical import sha256_canonical
        record = read_json(pack / "build_record.json")
        record["manifest_sha256"] = sha256_canonical(manifest)
        (pack / "build_record.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")


def _first_archive(pack):
    return _manifest(pack)["archives"][0]["name"]


def _problems(pack):
    return verify_pack(pack).problems


def test_FR_0_4_05_verify_passes_on_built_pack(built):
    report = verify_pack(built)
    assert report.ok, report.problems
    assert report.counts == {"test-clean": 4, "test-other": 2, "noisy": 3, "non-speech": 3, "tts": 2}
    assert report.summary().startswith("pack tpack 1.0.0: OK, 14 clips in 5 archives; test-clean 4")


def test_FR_0_4_05_verify_fails_on_changed_member(pack):
    def change(members):
        info, data = members[0]
        changed = bytearray(data)
        changed[-1] ^= 0x01                           # one sample bit; same size, header intact
        return [(info, bytes(changed))] + members[1:]
    _rewrite(pack, _first_archive(pack), change)
    problems = _problems(pack)
    assert len(problems) == 1 and "SHA-256" in problems[0] and "differs from clip" in problems[0], problems


def test_FR_0_4_05_verify_fails_on_missing_member(pack):
    name = _first_archive(pack)
    dropped = []
    _rewrite(pack, name, lambda members: (dropped.append(members[1][0].name), members[:1] + members[2:])[1])
    problems = _problems(pack)
    assert any(f"missing member {dropped[0]!r}" in p for p in problems), problems
    assert any("members, the manifest says" in p for p in problems)


def test_FR_0_4_05_verify_fails_on_extra_member(pack):
    def add(members):
        info = tarfile.TarInfo("test-clean/intruder.wav")
        return members + [(info, members[0][1])]
    _rewrite(pack, _first_archive(pack), add)
    problems = _problems(pack)
    assert any("'test-clean/intruder.wav': extra member" in p for p in problems), problems


def test_FR_0_4_05_verify_fails_on_changed_or_missing_archive(pack, tmp_path):
    name = _first_archive(pack)
    with open(pack / name, "ab") as fh:
        fh.write(bytes(tarfile.RECORDSIZE))          # same members, other archive bytes
    problems = _problems(pack)
    assert any(p.startswith(f"{name}: SHA-256") for p in problems), problems
    assert any(p.startswith(f"{name}: ") and "bytes, the manifest says" in p for p in problems)
    (pack / name).unlink()
    assert f"{name}: missing from the pack folder" in _problems(pack)


def test_FR_0_4_05_verify_fails_on_extra_file_in_pack_folder(pack):
    (pack / "notes.txt").write_text("x", encoding="utf-8")
    assert _problems(pack) == ["notes.txt: extra file in the pack folder; the manifest does not list it"]


@pytest.mark.parametrize("field,value,expected", [
    ("sha256", "0" * 64, "differs from clip"),
    ("duration_s", 99.0, "the manifest says 99.0"),
    ("sample_rate_hz", 8000, "sample rate 16000 Hz, the manifest says 8000"),
    ("channels", 2, "the manifest says 2"),
    ("member_path", "test-clean/elsewhere.wav", "missing member 'test-clean/elsewhere.wav'"),
])
def test_FR_0_4_05_verify_fails_on_manifest_entry_mismatch(pack, field, value, expected):
    manifest = _manifest(pack)
    manifest["clips"][0][field] = value
    _write_manifest(pack, manifest)
    problems = _problems(pack)
    assert any(expected in p for p in problems), problems


def test_FR_0_4_05_verify_fails_when_clip_names_another_archive(pack):
    manifest = _manifest(pack)
    manifest["clips"][0]["archive"] = manifest["archives"][1]["name"]
    _write_manifest(pack, manifest)
    problems = _problems(pack)
    assert any("extra member" in p for p in problems) and any("missing member" in p for p in problems)


@pytest.mark.parametrize("kind", ["symlink", "folder", "absolute", "dotdot"])
def test_FR_0_4_05_verify_rejects_unsafe_member(pack, kind):
    def add(members):
        if kind == "symlink":
            info = tarfile.TarInfo("test-clean/link.wav")
            info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
            return members + [(info, None)]
        if kind == "folder":
            info = tarfile.TarInfo("test-clean/sub")
            info.type = tarfile.DIRTYPE
            return members + [(info, None)]
        info = tarfile.TarInfo("/abs.wav" if kind == "absolute" else "test-clean/../../x.wav")
        return members + [(info, b"x")]
    _rewrite(pack, _first_archive(pack), add)
    problems = _problems(pack)
    assert any("unsafe path" in p or "not a regular file" in p for p in problems), problems


def test_FR_0_4_05_verify_reports_every_problem(pack):
    (pack / "notes.txt").write_text("x", encoding="utf-8")
    manifest = _manifest(pack)
    manifest["clips"][0]["duration_s"] = 99.0
    manifest["clips"][-1]["sha256"] = "1" * 64
    _write_manifest(pack, manifest)
    problems = _problems(pack)
    assert any("notes.txt" in p for p in problems)
    assert any("the manifest says 99.0" in p for p in problems)
    assert any(f"differs from clip {manifest['clips'][-1]['clip_id']}" in p for p in problems)
    assert any("build_record.json: manifest_sha256" in p for p in problems)


def test_FR_0_4_05_verify_checks_recipes_and_build_record(pack):
    manifest = _manifest(pack)
    mixed = next(c for c in manifest["clips"] if c["recipe"] and c["recipe"]["kind"] == "mix")
    del mixed["recipe"]["noise_gain"]
    _write_manifest(pack, manifest)
    problems = _problems(pack)
    assert any(f"clip {mixed['clip_id']} recipe" in p and "noise_gain" in p for p in problems), problems
    manifest = _manifest(pack)
    del manifest["clips"][0]["licence"]
    _write_manifest(pack, manifest)
    assert any("manifest.json: /clips/0/licence" in p for p in _problems(pack))


def test_FR_0_4_05_verify_input_errors(tmp_path):
    with pytest.raises(VerifyInputError):
        verify_pack(tmp_path / "missing")
    (tmp_path / "empty").mkdir()
    assert verify_pack(tmp_path / "empty").problems[0].startswith("manifest.json: cannot read")


def _replace_with(pack, name, kind):
    """Replace a pack file by a folder, or by a symbolic link that points nowhere."""
    (pack / name).unlink()
    if kind == "folder":
        (pack / name).mkdir()
    else:
        (pack / name).symlink_to(pack.parent / "nowhere" / name)


@pytest.mark.parametrize("kind", ["folder", "dangling_symlink"])
def test_FR_0_4_05_verify_fails_on_archive_that_is_not_a_file(pack, kind):
    """WP-0.4-F01: a listed archive that is a folder or a broken link is a problem, never skipped."""
    manifest = _manifest(pack)
    name = next(a["name"] for a in manifest["archives"] if "-tts-" in a["name"])
    _replace_with(pack, name, kind)
    report = verify_pack(pack)
    assert not report.ok and "OK" not in report.summary()
    expected = "is a folder, not a file" if kind == "folder" else "is a broken symbolic link"
    assert any(p.startswith(f"{name}: ") and expected in p for p in report.problems), report.problems


@pytest.mark.parametrize("kind", ["folder", "dangling_symlink"])
@pytest.mark.parametrize("name", ["LICENCES.md", "build_record.json"])
def test_FR_0_4_05_verify_fails_on_pack_file_that_is_not_a_file(pack, name, kind):
    """WP-0.4-F01: LICENCES.md and build_record.json must be regular files too."""
    _replace_with(pack, name, kind)
    problems = verify_pack(pack).problems
    expected = "is a folder, not a file" if kind == "folder" else "is a broken symbolic link"
    assert [p for p in problems if p.startswith(f"{name}: ")] and any(expected in p for p in problems), problems


def test_FR_0_4_05_verify_accepts_link_to_a_real_archive(pack, tmp_path):
    """A pack file may be a symbolic link to the real file (for example on a mounted Drive)."""
    name = _first_archive(pack)
    elsewhere = tmp_path / "drive" / name
    elsewhere.parent.mkdir()
    (pack / name).rename(elsewhere)
    (pack / name).symlink_to(elsewhere)
    assert verify_pack(pack).ok


def test_FR_0_4_05_verify_fails_on_duplicate_member_path(pack):
    """WP-0.4-F02: two clips naming one member of an archive are a problem; neither is taken as checked."""
    manifest = _manifest(pack)
    first, second = manifest["clips"][0], manifest["clips"][1]
    assert first["archive"] == second["archive"]
    own_path = first["member_path"]
    first["member_path"] = second["member_path"]
    _write_manifest(pack, manifest)
    _rewrite(pack, first["archive"], lambda members: [m for m in members if m[0].name != own_path])
    manifest = _manifest(pack)
    for entry in manifest["archives"]:
        if entry["name"] == first["archive"]:
            entry["n_members"] -= 1
    _write_manifest(pack, manifest)
    from aqis_lab.contracts.canonical import sha256_canonical
    record = read_json(pack / "build_record.json")
    record["manifest_sha256"] = sha256_canonical(manifest)
    (pack / "build_record.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    problems = _problems(pack)
    assert any(f"member {second['member_path']!r} is named by 2 clips" in p and first["clip_id"] in p
               and second["clip_id"] in p for p in problems), problems
