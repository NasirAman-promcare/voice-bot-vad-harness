"""NFR-0.5-02: nothing in the lab writes to Google Drive except under MyDrive/AQIS_LAB.

Google Drive is replaced by a folder the test makes plus a generated fuse.drive mountinfo line (Drive test double),
so the real code paths of every writing command run with the guard active.
"""
import json

import pytest

from aqis_lab import doctor, drive, unitlog
from aqis_lab import platform as lp
from aqis_lab.runner.run import RunInputError, RunOptions, run
from aqis_runner_testutil import SMOKE_PACK, colab_env, drive_mountinfo_line, make_system_tree, stand_in_drive, \
    tree_snapshot
from aqis_testutil import ROOT

RATES = ROOT / "config" / "aqis_lab" / "colab_rates.yaml"


def colab_system(tmp_path, mount):
    root = make_system_tree(tmp_path / "sys", mountinfo=drive_mountinfo_line(mount))
    return lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin"))


@pytest.fixture
def world(tmp_path):
    mount = stand_in_drive(tmp_path)
    (mount / "MyDrive" / "Personal").mkdir()
    (mount / "MyDrive" / "Personal" / "diary.txt").write_text("not the lab's\n", encoding="utf-8")
    system = colab_system(tmp_path, mount)
    drive.ensure_layout(mount, system)
    return mount, system


def test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab(tmp_path, world):
    mount, system = world
    lab = drive.aqis_lab_folder(mount)
    outside = mount / "MyDrive" / "Personal"
    report = doctor.run_doctor("colab", drive_mount=mount, system=system)
    before = tree_snapshot(mount)
    refused = [
        ("doctor --out", lambda: doctor.write_report(report, outside / "logs", system)),
        ("run --out", lambda: run(RunOptions(task="clip-stats", pack=SMOKE_PACK, out=outside / "run", seed=0,
                                             work_dir=tmp_path / "work"), system=system, echo=None)),
        ("run --out at the Drive root", lambda: run(RunOptions(task="clip-stats", pack=SMOKE_PACK, out=mount / "run",
                                                               seed=0, work_dir=tmp_path / "work"),
                                                    system=system, echo=None)),
        ("write_bytes", lambda: drive.write_bytes(mount / "MyDrive" / "x.json", b"{}", system)),
        ("append_bytes", lambda: drive.append_bytes(outside / "diary.txt", b"more\n", system)),
        ("make_dirs", lambda: drive.make_dirs(mount / "MyDrive" / "AQIS_LAB2" / "logs", system)),
    ]
    for name, action in refused:
        with pytest.raises((drive.DriveError, RunInputError)) as err:
            action()
        assert "outside" in str(err.value) and "AQIS_LAB" in str(err.value), name
        assert tree_snapshot(mount) == before, f"{name} wrote to Drive before refusing"
    # a folder inside AQIS_LAB that is a link to elsewhere on Drive is judged by where it really points
    (lab / "logs").rename(lab / "logs-real")
    (lab / "logs").symlink_to(outside)
    before = tree_snapshot(mount)
    machine = {"platform": "colab", "gpu": None, "cpu_model": "x", "architecture": "x86_64", "os": "y",
               "python_version": "3.13.15"}
    with pytest.raises(drive.DriveError):
        unitlog.start_session(mount, machine, unitlog.load_rates(RATES), system=system)
    with pytest.raises(drive.DriveError):
        doctor.write_report(report, lab / "logs", system)
    assert tree_snapshot(mount) == before
    assert (outside / "diary.txt").read_text(encoding="utf-8") == "not the lab's\n"


def test_NFR_0_5_02_writes_under_aqis_lab_allowed(tmp_path, world):
    mount, system = world
    lab = drive.aqis_lab_folder(mount)
    report = doctor.run_doctor("colab", drive_mount=mount, system=system)
    path = doctor.write_report(report, lab / "logs", system)
    assert path.parent == lab / "logs" and json.loads(path.read_text(encoding="utf-8"))["target"] == "colab"
    machine = lp.machine_block(system)
    rates = unitlog.load_rates(RATES)
    unitlog.start_session(mount, machine, rates, system=system)
    outcome = run(RunOptions(task="clip-stats", pack=SMOKE_PACK, out=lab / "results" / "smoke", seed=0,
                             work_dir=tmp_path / "work"), system=system, echo=None)
    assert outcome.status == "complete" and (lab / "results" / "smoke" / "results.jsonl").is_file()
    unitlog.end_session(mount, rates, system=system)
    assert (lab / "logs" / "units.csv").is_file()
    added = {p for p in tree_snapshot(mount)}
    assert all(p.startswith("MyDrive/AQIS_LAB/") or p in ("MyDrive", "MyDrive/AQIS_LAB") or p.startswith("MyDrive/Personal")
               for p in added)
    assert (mount / "MyDrive" / "Personal" / "diary.txt").read_text(encoding="utf-8") == "not the lab's\n"
    assert sorted(p.name for p in (mount / "MyDrive").iterdir()) == ["AQIS_LAB", "Personal"]
