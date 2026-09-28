"""FR-0.5-04: copy then compute. Pack archives are copied to local disk, hash-verified and extracted there first."""
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from aqis_lab import platform as lp
from aqis_lab.runner import stage
from aqis_lab.runner.run import RunOptions, run
from aqis_runner_testutil import SMOKE_PACK, colab_env, drive_mountinfo_line, make_system_tree, stand_in_drive
from aqis_testutil import ROOT

MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))


def copy_pack(dst):
    shutil.copytree(SMOKE_PACK, dst)
    return dst


def staged_dir(work):
    return work / "packs" / MANIFEST["manifest_id"] / MANIFEST["version"]


def test_FR_0_5_04_stages_repository_pack_to_local_disk(tmp_path):
    work = tmp_path / "work"
    staged = stage.stage_pack(SMOKE_PACK, work)
    assert staged.root == staged_dir(work) and staged.fresh is True
    for clip in MANIFEST["clips"]:
        path = staged.root / "clips" / clip["member_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == clip["sha256"], clip["clip_id"]
    for archive in MANIFEST["archives"]:
        copied = staged.root / "pack" / archive["name"]
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == archive["sha256"]
    marker = json.loads((staged.root / stage.STAGED_MARKER).read_text(encoding="utf-8"))
    from aqis_lab.contracts.canonical import sha256_canonical
    assert marker["manifest_sha256"] == sha256_canonical(MANIFEST)
    assert marker["archives"] == {a["name"]: a["sha256"] for a in MANIFEST["archives"]}
    assert sorted(p.name for p in staged.root.parent.iterdir()) == [MANIFEST["version"]], "no staging leftovers"


def test_FR_0_5_04_stages_pack_from_drive_folder(tmp_path):
    mount = stand_in_drive(tmp_path)
    source = copy_pack(mount / "MyDrive" / "AQIS_LAB" / "packs" / "smoke" / "v1")
    root = make_system_tree(tmp_path / "sys", mountinfo=drive_mountinfo_line(mount))
    system = lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin"))
    staged = stage.stage_pack(source, tmp_path / "local-work", system)
    assert staged.root.is_relative_to(tmp_path / "local-work")
    assert len(list((staged.root / "clips").rglob("*.wav"))) == len(MANIFEST["clips"])


def test_FR_0_5_04_rejects_changed_archive_and_stages_nothing(tmp_path):
    source = copy_pack(tmp_path / "source")
    archive = source / MANIFEST["archives"][2]["name"]
    data = bytearray(archive.read_bytes())
    data[5000] ^= 0xFF
    archive.write_bytes(bytes(data))
    work = tmp_path / "work"
    with pytest.raises(stage.StageError) as err:
        stage.stage_pack(source, work)
    assert MANIFEST["archives"][2]["name"] in str(err.value)
    assert not staged_dir(work).exists()
    leftovers = list((work / "packs").rglob("*")) if (work / "packs").exists() else []
    assert [p for p in leftovers if p.is_file()] == [], "nothing unverified is kept"


def test_FR_0_5_04_interrupted_staging_is_redone(tmp_path):
    work = tmp_path / "work"
    parent = staged_dir(work).parent
    leftover = parent / f".staging-{MANIFEST['version']}"
    (leftover / "clips").mkdir(parents=True)
    (leftover / "clips" / "half.wav").write_bytes(b"RIFF")
    broken = staged_dir(work)                      # a folder without a valid marker never counts as staged
    (broken / "clips").mkdir(parents=True)
    (broken / "clips" / "x.wav").write_bytes(b"not a clip")
    staged = stage.stage_pack(SMOKE_PACK, work)
    assert staged.fresh is True
    assert sorted(p.name for p in parent.iterdir()) == [MANIFEST["version"]]
    assert not (staged.root / "clips" / "x.wav").exists()
    (staged.root / stage.STAGED_MARKER).write_text('{"manifest_sha256": "0"}', encoding="utf-8")
    assert stage.stage_pack(SMOKE_PACK, work).fresh is True, "a marker for another manifest is not trusted"


def test_FR_0_5_04_restaging_a_staged_pack_copies_nothing(tmp_path):
    work = tmp_path / "work"
    first = stage.stage_pack(SMOKE_PACK, work)
    stamps = {p: p.stat().st_mtime_ns for p in first.root.rglob("*")}
    second = stage.stage_pack(SMOKE_PACK, work)
    assert second.fresh is False and second.root == first.root
    assert {p: p.stat().st_mtime_ns for p in second.root.rglob("*")} == stamps


def run_options(pack, out, work, **extra):
    return RunOptions(task="clip-stats", pack=pack, out=out, seed=0, work_dir=work, **extra)


def test_FR_0_5_04_run_reads_only_local_extracted_clips(tmp_path):
    source = copy_pack(tmp_path / "source")
    work = tmp_path / "work"
    stage.stage_pack(source, work)
    for archive in MANIFEST["archives"]:                 # the source's archives are now useless
        (source / archive["name"]).write_bytes(b"\0" * 10)
    outcome = run(run_options(source, tmp_path / "run-a", work, shard_clips=10))
    assert outcome.status == "complete"
    reference = run(run_options(SMOKE_PACK, tmp_path / "run-b", tmp_path / "work-b", shard_clips=10))
    assert (tmp_path / "run-a" / "results.jsonl").read_bytes() == (tmp_path / "run-b" / "results.jsonl").read_bytes()
    assert reference.status == "complete"


def test_FR_0_5_04_work_dir_on_drive_is_refused(tmp_path):
    mount = stand_in_drive(tmp_path)
    root = make_system_tree(tmp_path / "sys", mountinfo=drive_mountinfo_line(mount))
    system = lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin"))
    with pytest.raises(stage.StageError) as err:
        stage.stage_pack(SMOKE_PACK, mount / "MyDrive" / "AQIS_LAB" / "work", system)
    assert "local disk" in str(err.value)
    assert list((mount / "MyDrive" / "AQIS_LAB").iterdir()) == []


def test_FR_0_5_04_changed_extracted_clip_stops_the_run(tmp_path):
    work = tmp_path / "work"
    staged = stage.stage_pack(SMOKE_PACK, work)
    clip = MANIFEST["clips"][25]
    path = staged.root / "clips" / clip["member_path"]
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x01
    path.write_bytes(bytes(data))
    out = tmp_path / "run"
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(out), "--seed", "0", "--work-dir", str(work), "--shard-clips", "10"],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert clip["clip_id"] in proc.stderr and "sha256" in proc.stderr
    markers = sorted(p.name for p in (out / "shards").glob("*.done.json"))
    assert markers == ["shard-00000.done.json", "shard-00001.done.json"], "shard 2 (clip 25) never gets a marker"
    assert not (out / "results.jsonl").exists()
    log = (out / "runner.log").read_text(encoding="utf-8")
    assert "ERROR" in log and clip["clip_id"] in log
