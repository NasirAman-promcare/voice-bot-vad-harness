"""FR-0.5-03: the AQIS_LAB layout on Google Drive, never deleting, with a warning before a folder passes 1,000 items.

Google Drive is replaced by a folder the test makes plus a generated mountinfo line (Drive test double).
"""
import subprocess
import sys

import pytest

from aqis_lab import drive
from aqis_lab import platform as lp
from aqis_runner_testutil import colab_env, drive_mountinfo_line, make_system_tree, stand_in_drive, tree_snapshot
from aqis_testutil import ROOT

LAYOUT = ["packs", "models", "results", "logs"]


def colab_system(tmp_path, mount):
    root = make_system_tree(tmp_path / "sys", mountinfo=drive_mountinfo_line(mount))
    return lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin"))


def fill(folder, n):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (folder / f"item-{i:05d}").write_bytes(b"")


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "drive", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=300)


def test_FR_0_5_03_creates_missing_layout_folders(tmp_path):
    mount = stand_in_drive(tmp_path)
    lab = mount / "MyDrive" / "AQIS_LAB"
    (lab / "packs").mkdir()
    result = drive.ensure_layout(mount, colab_system(tmp_path, mount))
    assert result.created == ["models", "results", "logs"] and result.existing == ["packs"]
    assert sorted(p.name for p in lab.iterdir()) == sorted(LAYOUT)
    assert all((lab / name).is_dir() for name in LAYOUT)
    again = drive.ensure_layout(mount, colab_system(tmp_path / "b", mount))
    assert again.created == [] and again.existing == LAYOUT
    proc = run_cli("layout", "--drive-mount", str(stand_in_drive(tmp_path / "cli")))
    assert proc.returncode == 0, proc.stderr
    assert sorted(p.name for p in (tmp_path / "cli" / "drive" / "MyDrive" / "AQIS_LAB").iterdir()) == sorted(LAYOUT)
    for name in LAYOUT:
        assert f"created {name}" in proc.stdout


def test_FR_0_5_03_never_deletes_or_changes_existing_content(tmp_path):
    mount = stand_in_drive(tmp_path)
    lab = mount / "MyDrive" / "AQIS_LAB"
    (lab / "results" / "run-1").mkdir(parents=True)
    (lab / "results" / "run-1" / "results.jsonl").write_bytes(b'{"clip_id":"a"}\n')
    (lab / "notes.txt").write_text("owner notes\n", encoding="utf-8")
    (lab / "other").mkdir()
    (lab / "logs").mkdir(mode=0o750)
    (lab / "logs").chmod(0o750)
    (mount / "MyDrive" / "Unrelated.doc").write_bytes(b"not the lab's")
    before = tree_snapshot(mount)
    drive.ensure_layout(mount, colab_system(tmp_path, mount))
    after = tree_snapshot(mount)
    for path, value in before.items():
        assert after.get(path) == value, f"{path} changed or disappeared"
    assert set(after) - set(before) == {"MyDrive/AQIS_LAB/packs", "MyDrive/AQIS_LAB/models"}


def test_FR_0_5_03_refuses_when_aqis_lab_missing(tmp_path):
    mount = stand_in_drive(tmp_path, with_aqis_lab=False)
    before = tree_snapshot(mount)
    with pytest.raises(drive.DriveError) as err:
        drive.ensure_layout(mount, colab_system(tmp_path, mount))
    assert "AQIS_LAB" in str(err.value) and "create" in str(err.value)
    assert tree_snapshot(mount) == before
    proc = run_cli("layout", "--drive-mount", str(mount))
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:")
    assert tree_snapshot(mount) == before


def test_FR_0_5_03_layout_name_that_is_a_file_is_an_error(tmp_path):
    mount = stand_in_drive(tmp_path)
    lab = mount / "MyDrive" / "AQIS_LAB"
    (lab / "results").write_text("a file, not a folder", encoding="utf-8")
    before = tree_snapshot(mount)
    with pytest.raises(drive.DriveError) as err:
        drive.ensure_layout(mount, colab_system(tmp_path, mount))
    assert "results" in str(err.value) and "not a folder" in str(err.value)
    assert tree_snapshot(mount) == before, "nothing is created when the layout cannot be completed"


def test_FR_0_5_03_warns_before_folder_exceeds_1000_items(tmp_path, capsys):
    mount = stand_in_drive(tmp_path)
    system = colab_system(tmp_path, mount)
    lab = mount / "MyDrive" / "AQIS_LAB"
    fill(lab / "results", 999)
    drive.write_bytes(lab / "results" / "new-1", b"x", system)        # 999 -> 1,000: no warning
    assert "WARNING" not in capsys.readouterr().err
    drive.write_bytes(lab / "results" / "new-2", b"x", system)        # 1,000 -> 1,001: warning, still written
    err = capsys.readouterr().err
    assert "WARNING" in err and str(lab / "results") in err and "1001" in err.replace(",", "")
    assert (lab / "results" / "new-2").read_bytes() == b"x"
    drive.write_bytes(lab / "results" / "new-2", b"y", system)        # replacing adds no entry
    assert "WARNING" not in capsys.readouterr().err
    drive.make_dirs(lab / "results" / "run-9", system)                 # a new folder is an entry too
    assert "WARNING" in capsys.readouterr().err
    drive.append_bytes(lab / "results" / "units.csv", b"a\n", system)  # so is a new appended file
    assert "WARNING" in capsys.readouterr().err
    local = tmp_path / "local"
    fill(local, 1000)
    drive.write_bytes(local / "new", b"x", system)                     # not on Drive: no Drive warning
    assert "WARNING" not in capsys.readouterr().err


def test_FR_0_5_03_layout_reports_crowded_folders(tmp_path):
    mount = stand_in_drive(tmp_path)
    lab = mount / "MyDrive" / "AQIS_LAB"
    fill(lab / "results", 1001)
    fill(lab / "packs" / "smoke", 1000)
    result = drive.ensure_layout(mount, colab_system(tmp_path, mount))
    assert result.crowded == [(lab / "results", 1001)]
    proc = run_cli("layout", "--drive-mount", str(mount))
    assert proc.returncode == 0
    warnings = [l for l in proc.stderr.splitlines() if l.startswith("WARNING")]
    assert len(warnings) == 1 and str(lab / "results") in warnings[0] and "1001" in warnings[0].replace(",", "")
