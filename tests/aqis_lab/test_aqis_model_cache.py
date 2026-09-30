"""FR-0.7-02 (and FR-0.7-03's model file): models are downloaded to a local cache and verified by checksum before
use (aqis_lab/adapters/model_cache.py, config/aqis_lab/models.yaml).

The fast tests build real archives in the test and serve them through file:// URLs, which the cache opens with the
same urllib call it uses for https://; expected hashes are computed here independently of the code under test.
"""
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest
import yaml

from aqis_lab import platform as lp
from aqis_lab.adapters import model_cache as mc
from aqis_testutil import ROOT
from aqis_adapters_testutil import drive_view

MODELS_YAML = ROOT / "config" / "aqis_lab" / "models.yaml"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_zip(path, root, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{root}/", b"")
        for rel, data in files.items():
            z.writestr(f"{root}/{rel}", data)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


FILES = {"README": b"test model\n", "am/final.mdl": os.urandom(4096), "conf/model.conf": b"--min-active=200\n"}


def zip_pin(tmp_path, files=FILES, archive_files=None, bad_sha=False, bad_bytes=False, name="test-model-1"):
    archive = tmp_path / "src" / "test-model-1.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    data = make_zip(archive, "test-model-1", files if archive_files is None else archive_files)
    return mc.ModelPin(name=name, url=archive.as_uri(), kind="zip", bytes=len(data) + (1 if bad_bytes else 0),
                       sha256=("0" * 64) if bad_sha else sha(data), licence="test", root="test-model-1",
                       files={rel: {"sha256": sha(d), "bytes": len(d)} for rel, d in files.items()}, revision=None)


def test_FR_0_7_02_model_downloaded_to_cache_and_verified_from_local_source(tmp_path):
    pin = zip_pin(tmp_path)
    cache = tmp_path / "cache"
    path = mc.fetch(pin, cache)
    assert path.is_dir() and path.parent == cache / "test-model-1" and path.name == pin.sha256[:16]
    for rel, data in FILES.items():
        assert (path / rel).read_bytes() == data
    assert sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file() and p.name != mc.MARKER) \
        == sorted(FILES)
    assert json.loads((path / mc.MARKER).read_text())["sha256"] == pin.sha256
    # nothing of the download or staging is left beside the verified folder
    leftovers = [p.name for p in (cache / "test-model-1").rglob("*") if ".partial" in p.name or ".staging" in p.name]
    assert leftovers == []
    # a second fetch uses the cache: the source is gone and it still returns the same verified folder
    (tmp_path / "src" / "test-model-1.zip").unlink()
    assert mc.fetch(pin, cache) == path


def test_FR_0_7_02_model_rejected_when_checksum_differs(tmp_path):
    # Must-catch 4: an archive whose SHA-256 differs from the pin is rejected before anything is extracted.
    pin = zip_pin(tmp_path, bad_sha=True)
    cache = tmp_path / "cache"
    with pytest.raises(mc.ModelChecksumError) as info:
        mc.fetch(pin, cache)
    assert info.value.code == "model-checksum" and "0" * 64 in str(info.value)
    assert sha((tmp_path / "src" / "test-model-1.zip").read_bytes()) in str(info.value)
    assert [p for p in cache.rglob("*") if p.is_file()] == []


def test_FR_0_7_02_model_rejected_when_size_differs(tmp_path):
    pin = zip_pin(tmp_path, bad_bytes=True)
    with pytest.raises(mc.ModelChecksumError) as info:
        mc.fetch(pin, tmp_path / "cache")
    assert "bytes" in str(info.value)
    assert [p for p in (tmp_path / "cache").rglob("*") if p.is_file()] == []


def test_FR_0_7_02_member_that_differs_from_its_pin_is_rejected(tmp_path):
    # The archive matches its own pin, but one member differs from the per-file pin: nothing is published.
    pin = zip_pin(tmp_path, archive_files={**FILES, "conf/model.conf": b"--min-active=999\n"})
    pin_files = dict(pin.files)
    pin = mc.ModelPin(**{**pin.__dict__, "files": pin_files})
    with pytest.raises(mc.ModelChecksumError) as info:
        mc.fetch(pin, tmp_path / "cache")
    assert "conf/model.conf" in str(info.value)
    assert not any(p.is_dir() and mc.MARKER in [c.name for c in p.iterdir()]
                   for p in (tmp_path / "cache").rglob("*") if p.is_dir())


def test_FR_0_7_02_extra_or_missing_member_is_rejected(tmp_path):
    extra = zip_pin(tmp_path, archive_files={**FILES, "am/extra.bin": b"x"})
    with pytest.raises(mc.ModelChecksumError, match="am/extra.bin"):
        mc.fetch(extra, tmp_path / "cache-a")
    missing = zip_pin(tmp_path, archive_files={k: v for k, v in FILES.items() if k != "README"})
    with pytest.raises(mc.ModelChecksumError, match="README"):
        mc.fetch(missing, tmp_path / "cache-b")


def test_FR_0_7_02_member_outside_the_model_folder_is_rejected(tmp_path):
    archive = tmp_path / "src" / "evil.zip"
    archive.parent.mkdir(parents=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("test-model-1/README", FILES["README"])
        z.writestr("test-model-1/../../escape.txt", b"x")
    archive.write_bytes(buf.getvalue())
    pin = mc.ModelPin(name="test-model-1", url=archive.as_uri(), kind="zip", bytes=len(buf.getvalue()),
                      sha256=sha(buf.getvalue()), licence="test", root="test-model-1",
                      files={"README": {"sha256": sha(FILES["README"]), "bytes": len(FILES["README"])}},
                      revision=None)
    with pytest.raises(mc.ModelChecksumError, match="escape.txt"):
        mc.fetch(pin, tmp_path / "cache")
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path / "cache" / "escape.txt").exists()


def test_FR_0_7_02_changed_model_file_rejected_at_load(tmp_path):
    # Must-catch 4: a model file changed after it was verified is caught the next time the model is used.
    pin = zip_pin(tmp_path)
    path = mc.fetch(pin, tmp_path / "cache")
    mc.verify(pin, path)
    target = path / "am" / "final.mdl"
    target.chmod(0o644)
    data = bytearray(target.read_bytes())
    data[100] ^= 0xFF
    target.write_bytes(bytes(data))
    with pytest.raises(mc.ModelChecksumError, match="am/final.mdl"):
        mc.verify(pin, path)
    with pytest.raises(mc.ModelChecksumError, match="am/final.mdl"):
        mc.fetch(pin, tmp_path / "cache")


def test_FR_0_7_02_single_file_model_pinned_by_size_and_sha(tmp_path):
    data = os.urandom(10000)
    src = tmp_path / "src" / "weights.nemo"
    src.parent.mkdir()
    src.write_bytes(data)
    pin = mc.ModelPin(name="file-model", url=src.as_uri(), kind="file", bytes=len(data), sha256=sha(data),
                      licence="test", root=None, files=None, revision="abc")
    path = mc.fetch(pin, tmp_path / "cache")
    assert path.name == "weights.nemo" and path.read_bytes() == data
    bad = mc.ModelPin(**{**pin.__dict__, "sha256": "f" * 64, "name": "file-model-2"})
    with pytest.raises(mc.ModelChecksumError):
        mc.fetch(bad, tmp_path / "cache")


def test_FR_0_7_02_cache_on_drive_is_refused(tmp_path):
    pin = zip_pin(tmp_path)
    system, mount = drive_view(tmp_path)
    with pytest.raises(mc.ModelCacheError, match="local disk"):
        mc.fetch(pin, mount / "MyDrive" / "AQIS_LAB" / "models", system=system)


def test_FR_0_7_02_unreachable_source_is_a_download_error(tmp_path):
    pin = zip_pin(tmp_path)
    missing = mc.ModelPin(**{**pin.__dict__, "url": (tmp_path / "nowhere.zip").as_uri()})
    with pytest.raises(mc.ModelCacheError) as info:
        mc.fetch(missing, tmp_path / "cache")
    assert info.value.code == "model-download"


def test_FR_0_7_02_committed_pins_load_and_match_the_plan():
    pins = mc.load_pins(MODELS_YAML)
    vosk = pins["vosk-model-small-en-us-0.15"]
    assert vosk.kind == "zip" and vosk.bytes == 41205931
    assert vosk.sha256 == "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
    assert vosk.url == "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    assert len(vosk.files) == 14 and vosk.root == "vosk-model-small-en-us-0.15"
    parakeet = pins["parakeet-unified-en-0.6b"]
    assert parakeet.kind == "file" and parakeet.bytes == 2474055680
    assert parakeet.sha256 == "ec23ed9150c8fde49072c3e2d61678ab903dbcef389d658db833420cbc1da35b"
    assert parakeet.revision == "fe53cd885760c96b6a5f51a0bfd362cb4584a98b" and parakeet.revision in parakeet.url


@pytest.mark.parametrize("change", ["unknown_key", "missing_sha", "bad_sha", "bad_kind", "zip_without_files"])
def test_FR_0_7_02_pins_file_is_checked(tmp_path, change):
    data = yaml.safe_load(MODELS_YAML.read_text(encoding="utf-8"))
    entry = data["models"]["vosk-model-small-en-us-0.15"]
    if change == "unknown_key":
        entry["mirror"] = "https://example.invalid/"
    elif change == "missing_sha":
        del entry["sha256"]
    elif change == "bad_sha":
        entry["sha256"] = "30F2"
    elif change == "bad_kind":
        entry["kind"] = "tar"
    else:
        del entry["files"]
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(mc.ModelCacheError, match="vosk-model-small-en-us-0.15"):
        mc.load_pins(path)


@pytest.mark.network
def test_FR_0_7_02_model_downloaded_to_cache_and_verified(tmp_path):
    pin = mc.load_pins(MODELS_YAML)["vosk-model-small-en-us-0.15"]
    path = mc.fetch(pin, tmp_path / "cache")
    for rel, expected in pin.files.items():
        data = (path / rel).read_bytes()
        assert len(data) == expected["bytes"] and sha(data) == expected["sha256"], rel
