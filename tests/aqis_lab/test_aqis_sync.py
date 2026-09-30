"""FR-0.6-05: `python -m aqis_lab sync [--dry-run]` copies the results store one way to AQIS_LAB/results with rclone and
never deletes or replaces a remote file.

rclone is real. Google Drive is replaced by an rclone `alias` remote pointing at a local folder (a Drive test double),
configured only through environment variables, so no rclone config file is read or written.
"""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from aqis_lab import sync
from aqis_lab.results import ingest, store
from aqis_results_testutil import smoke_run, write_oracle_config
from aqis_runner_testutil import tree_snapshot
from aqis_testutil import ROOT

REMOTE = "aqisdrive"
DELETE_CAPABLE = {"sync", "bisync", "move", "moveto", "delete", "deletefile", "purge", "rmdir", "rmdirs", "dedupe",
                  "cleanup", "--delete-before", "--delete-during", "--delete-after", "--delete-excluded",
                  "--backup-dir", "--max-delete", "--suffix"}


@pytest.fixture(scope="module")
def filled_store(tmp_path_factory):
    base = tmp_path_factory.mktemp("sync")
    store_dir = base / "store"
    store.add_batch(store_dir, ingest.from_run_folder(smoke_run(base / "run", base / "work")))
    return store_dir


def make_drive(tmp_path, with_results=True):
    drive = tmp_path / "drive"
    (drive / "AQIS_LAB" / ("results" if with_results else "packs")).mkdir(parents=True)
    return drive


def env_for(tmp_path, drive, remote=REMOTE, path=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("RCLONE_")}
    env["RCLONE_CONFIG"] = str(tmp_path / "no-rclone.conf")
    if drive is not None:
        env[f"RCLONE_CONFIG_{remote.upper()}_TYPE"] = "alias"
        env[f"RCLONE_CONFIG_{remote.upper()}_REMOTE"] = str(drive)
    if path is not None:
        env["PATH"] = path
    return env


def run_sync(tmp_path, store_dir, env, *extra, remote=REMOTE):
    config = write_oracle_config(tmp_path / "oracle.yaml", [3], remote=remote, results_store=str(store_dir))
    return subprocess.run([sys.executable, "-m", "aqis_lab", "sync", "--config", str(config), *extra], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=300)


def store_files(store_dir):
    return {p.relative_to(store_dir).as_posix(): p.read_bytes() for p in store_dir.rglob("*")
            if p.is_file() and not p.name.endswith(".partial") and p.name != ".lock"}


def remote_files(drive):
    base = drive / "AQIS_LAB" / "results"
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


def test_FR_0_6_05_copies_store_to_aqis_lab_results(tmp_path, filled_store):
    drive = make_drive(tmp_path)
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, drive))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert remote_files(drive) == store_files(filled_store)
    assert f"destination {REMOTE}:AQIS_LAB/results" in proc.stdout and "mode COPY" in proc.stdout
    assert re.search(r"^rclone v\d+\.\d+\.\d+", proc.stdout, re.M)
    assert "sync complete" in proc.stdout
    again = run_sync(tmp_path, filled_store, env_for(tmp_path, drive))
    assert again.returncode == 0 and remote_files(drive) == store_files(filled_store)


def test_FR_0_6_05_never_deletes_remote_files(tmp_path, filled_store):
    # Must-catch 4: files on Drive that the store does not have stay exactly as they were.
    drive = make_drive(tmp_path)
    extra = {drive / "AQIS_LAB" / "results" / "keep.txt": b"remote only\n",
             drive / "AQIS_LAB" / "results" / "run_card_id=other" / "part-x.parquet": b"another machine's rows",
             drive / "AQIS_LAB" / "logs" / "units.csv": b"session_id\n"}
    for path, data in extra.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    before = tree_snapshot(drive)
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, drive))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    after = tree_snapshot(drive)
    assert all(after.get(k) == v for k, v in before.items()), "a remote file or folder was removed or changed"
    assert set(remote_files(drive)) == set(store_files(filled_store)) | {"keep.txt", "run_card_id=other/part-x.parquet"}


def test_FR_0_6_05_never_replaces_a_remote_file(tmp_path, filled_store):
    # Must-catch 4: a remote file that differs from the store is reported and left untouched.
    drive = make_drive(tmp_path)
    name = sorted(store_files(filled_store))[-1]
    target = drive / "AQIS_LAB" / "results" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"different bytes on Drive")
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, drive))
    assert proc.returncode == 1
    assert proc.stderr.startswith("ERROR:") and name in proc.stderr and "never replaced" in proc.stderr
    assert target.read_bytes() == b"different bytes on Drive"


def test_FR_0_6_05_dry_run_changes_nothing(tmp_path, filled_store):
    drive = make_drive(tmp_path)
    before = tree_snapshot(drive)
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, drive), "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert tree_snapshot(drive) == before
    assert "mode DRY RUN" in proc.stdout and "DRY RUN: nothing was copied" in proc.stdout
    for name in store_files(filled_store):
        assert f"{name}: Skipped copy as --dry-run is set" in proc.stdout


def test_FR_0_6_05_command_is_copy_only(tmp_path):
    # Must-catch 4: the only rclone command sync builds is `copy` with --immutable; the module holds no
    # delete-capable rclone command or flag at all.
    argv = sync.copy_command("/usr/bin/rclone", Path("/store"), "aqis-drive", dry_run=False)
    assert argv[:4] == ["/usr/bin/rclone", "copy", "/store", "aqis-drive:AQIS_LAB/results"]
    assert "--immutable" in argv and "--checksum" in argv and "--dry-run" not in argv
    assert sync.copy_command("/usr/bin/rclone", Path("/store"), "aqis-drive", dry_run=True)[-1] == "--dry-run"
    assert not DELETE_CAPABLE & set(argv)
    tree = ast.parse((ROOT / "aqis_lab" / "sync.py").read_text(encoding="utf-8"))
    constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not DELETE_CAPABLE & constants, DELETE_CAPABLE & constants


def test_FR_0_6_05_missing_remote_points_to_runbook(tmp_path, filled_store):
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, None))
    assert proc.returncode == 2 and proc.stdout.count("\n") <= 4
    assert proc.stderr.startswith("ERROR:") and f'rclone remote "{REMOTE}" is not configured' in proc.stderr
    assert "docs/oracle/ORACLE_RUNBOOK.md" in proc.stderr and "Configure rclone for Google Drive" in proc.stderr


def path_without(tmp_path, names):
    bindir = tmp_path / "bin-without"
    bindir.mkdir()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        d = Path(directory)
        if not d.is_dir():
            continue
        for entry in d.iterdir():
            if entry.name in names or (bindir / entry.name).exists():
                continue
            if entry.is_file() and os.access(entry, os.X_OK):
                (bindir / entry.name).symlink_to(entry.resolve())
    return str(bindir)


def test_FR_0_6_05_missing_rclone_points_to_runbook(tmp_path, filled_store):
    drive = make_drive(tmp_path)
    env = env_for(tmp_path, drive, path=path_without(tmp_path, {"rclone"}))
    proc = run_sync(tmp_path, filled_store, env)
    assert proc.returncode == 2 and "rclone not found" in proc.stderr
    assert "docs/oracle/ORACLE_RUNBOOK.md" in proc.stderr and "Install uv and rclone" in proc.stderr


def test_FR_0_6_05_refuses_when_remote_results_folder_missing(tmp_path, filled_store):
    drive = make_drive(tmp_path, with_results=False)
    before = tree_snapshot(drive)
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, drive))
    assert proc.returncode == 2 and "AQIS_LAB/results" in proc.stderr and "never creates" in proc.stderr
    assert tree_snapshot(drive) == before
    empty = tmp_path / "empty-drive"
    empty.mkdir()
    proc = run_sync(tmp_path, filled_store, env_for(tmp_path, empty))
    assert proc.returncode == 2 and "AQIS_LAB" in proc.stderr and list(empty.iterdir()) == []


def test_FR_0_6_05_partial_files_not_copied(tmp_path, filled_store):
    copy = tmp_path / "store"
    subprocess.run(["cp", "-a", str(filled_store), str(copy)], check=True)
    partition = next(copy.glob("run_card_id=*"))
    (partition / "part-abc.parquet.partial").write_bytes(b"half")
    drive = make_drive(tmp_path)
    proc = run_sync(tmp_path, copy, env_for(tmp_path, drive))
    assert proc.returncode == 0, proc.stderr
    names = set(remote_files(drive))
    assert not any(n.endswith(".partial") or n.endswith(".lock") for n in names)
    assert names == set(store_files(copy))


def test_FR_0_6_05_missing_store_exit_2(tmp_path):
    drive = make_drive(tmp_path)
    proc = run_sync(tmp_path, tmp_path / "no-store", env_for(tmp_path, drive))
    assert proc.returncode == 2 and "no results store" in proc.stderr


@pytest.mark.parametrize("text, ok", [("rclone v1.60.1-DEV\n", True), ("rclone v1.68.2\n- os/version", True),
                                      ("rclone v1.60.0\n", False), ("rclone v1.53.3-DEV\n", False),
                                      ("something else\n", False)])
def test_FR_0_6_05_rclone_version_minimum(text, ok):
    if ok:
        assert sync.check_rclone_version(text) >= (1, 60, 1)
    else:
        with pytest.raises(sync.SyncUsageError) as info:
            sync.check_rclone_version(text)
        assert "1.60.1" in str(info.value)


def test_FR_0_6_05_ci_installs_rclone_before_fast_suite():
    import yaml
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "aqis-lab-ci.yml").read_text(encoding="utf-8"))
    runs = [s.get("run", "") for s in doc["jobs"]["lab"]["steps"]]
    install = next(i for i, r in enumerate(runs) if "apt-get install -y --no-install-recommends rclone" in r)
    fast = next(i for i, r in enumerate(runs) if "pytest tests/aqis_lab" in r)
    assert install < fast and "rclone version" in runs[install]
