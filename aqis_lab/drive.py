"""Google Drive rules for the WP-0.5 commands' writes: only under MyDrive/AQIS_LAB, atomic files, the layout.

CAPABILITIES:
  CAP-DRIVE-001: check_write_path() refuses any path on a Google Drive mount (from aqis_lab.platform) that is not inside <mount>/MyDrive/AQIS_LAB, before anything is written; write_bytes(), append_bytes() and make_dirs() always apply it; the WP-0.5 commands (doctor, drive layout, run, unitlog) write only through them (the older score, pack build, registry build and fetch do not yet: DEBT-014, target WP-0.7) [tests: test_NFR_0_5_02_each_command_refuses_drive_path_outside_aqis_lab, test_NFR_0_5_02_writes_under_aqis_lab_allowed]
  CAP-DRIVE-003: ensure_layout() creates only the missing AQIS_LAB/{packs,models,results,logs} folders (never AQIS_LAB itself, never deleting or changing anything; a layout name that is not a folder stops it before anything is created) and reports every AQIS_LAB folder holding more than 1,000 entries; every write through write_bytes, append_bytes or make_dirs (all WP-0.5 commands; DEBT-014 for the older writers) that adds an entry to a Drive folder warns first when the folder would pass 1,000 entries, then still writes [tests: test_FR_0_5_03_creates_missing_layout_folders, test_FR_0_5_03_never_deletes_or_changes_existing_content, test_FR_0_5_03_refuses_when_aqis_lab_missing, test_FR_0_5_03_layout_name_that_is_a_file_is_an_error, test_FR_0_5_03_warns_before_folder_exceeds_1000_items, test_FR_0_5_03_layout_reports_crowded_folders]
  CAP-DRIVE-002: write_bytes() writes a file atomically (write <name>.partial, fsync, rename, fsync the folder), so a reader sees the old file or the whole new one, never a torn file [tests: test_FR_0_5_02_colab_drive_checks_pass_when_writable, test_FR_0_5_05_shard_results_written_atomically_with_marker]
INPUTS AND OUTPUTS: paths and bytes in; files and folders out; DriveError when a path is refused.
CONTRACTS: the Drive layout documented in the Colab runbook (docs/colab/).
INVARIANTS:
  - Nothing is ever deleted: files are replaced by rename, folders are only created.
  - The lab never creates MyDrive/AQIS_LAB itself; the owner does.
NOT IN SCOPE:
  - Mounting Drive (the launcher notebook) and copying results to Drive from Oracle (WP-0.6 sync).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-02 created (write guard and atomic writes, also NFR-0.5-02).
  2026-09-28 WP-0.5 FR-0.5-03: ensure_layout, crowded_folders, warn_if_crowded (called by every write function).
  2026-09-28 WP-0.5 round 2 F02: header states which commands use the guard (header only).
  2026-09-28 WP-0.5 round 3 F12: summary line no longer says "every lab write" (older writers: DEBT-014; header only).
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from aqis_lab import platform as lp

MY_DRIVE = "MyDrive"
AQIS_FOLDER = "AQIS_LAB"
PARTIAL_SUFFIX = ".partial"
LAYOUT = ("packs", "models", "results", "logs")
MAX_FOLDER_ITEMS = 1000       # Drive struggles with crowded folders; owner decision: warn, still write (question 10)


class DriveError(RuntimeError):
    """A write that the Drive rules forbid, or a Drive folder that is not usable."""


def aqis_lab_folder(mount):
    """<mount>/MyDrive/AQIS_LAB, the only place on Drive the lab writes to."""
    return Path(mount) / MY_DRIVE / AQIS_FOLDER


def _inside(path, folder):
    return path == folder or folder in path.parents


def drive_mount_of(path, system=None):
    """The Google Drive mount holding `path` (resolved), or None when the path is not on Drive."""
    target = Path(path).resolve()
    for mount in lp.drive_mounts(system):
        resolved = mount.resolve()
        if _inside(target, resolved):
            return resolved
    return None


def check_write_path(path, system=None):
    """The resolved path, or DriveError when it is on Drive outside MyDrive/AQIS_LAB (NFR-0.5-02)."""
    target = Path(path).resolve()
    mount = drive_mount_of(target, system)
    if mount is not None and not _inside(target, aqis_lab_folder(mount)):
        raise DriveError(f"refusing to write {path}: it is on Google Drive ({mount}) but outside "
                         f"{aqis_lab_folder(mount)}; the lab writes to Drive only under {MY_DRIVE}/{AQIS_FOLDER}")
    return target


def warn_if_crowded(folder, system=None, adding=1):
    """Print one WARNING when adding entries to a Drive folder would make it hold more than 1,000; returns it."""
    folder = Path(folder)
    if drive_mount_of(folder, system) is None or not folder.is_dir():
        return None
    count = sum(1 for _ in os.scandir(folder))
    if count + adding <= MAX_FOLDER_ITEMS:
        return None
    message = (f"WARNING: {folder} will hold {count + adding:,} entries, more than {MAX_FOLDER_ITEMS:,}; Google "
               f"Drive gets slow and unreliable with crowded folders. Split the content into subfolders.")
    print(message, file=sys.stderr, flush=True)
    return message


def make_dirs(path, system=None):
    """Create a folder and its missing parents (never anything else); returns the resolved path."""
    target = check_write_path(path, system)
    missing = []
    probe = target
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    if not probe.is_dir():
        raise DriveError(f"cannot create {target}: {probe} exists and is not a folder")
    for folder in reversed(missing):
        warn_if_crowded(folder.parent, system)
        folder.mkdir()
    return target


def _fsync_folder(folder):
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_bytes(path, data, system=None, exclusive=False):
    """Write `data` to `path` atomically; with exclusive=True an existing file is an error, never replaced."""
    target = check_write_path(path, system)
    if exclusive and target.exists():
        raise DriveError(f"refusing to replace {target}: it already exists")
    if not target.parent.is_dir():
        raise DriveError(f"cannot write {target}: the folder {target.parent} does not exist")
    if not target.exists():
        warn_if_crowded(target.parent, system)
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        view = memoryview(bytes(data))
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(partial, target)
    _fsync_folder(target.parent)
    return target


def append_bytes(path, data, system=None):
    """Append `data` to `path` (created when missing) and fsync; existing bytes are never rewritten."""
    target = check_write_path(path, system)
    if not target.parent.is_dir():
        raise DriveError(f"cannot write {target}: the folder {target.parent} does not exist")
    if not target.exists():
        warn_if_crowded(target.parent, system)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        view = memoryview(bytes(data))
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return target


@dataclass
class LayoutResult:
    folder: Path
    created: list = field(default_factory=list)
    existing: list = field(default_factory=list)
    crowded: list = field(default_factory=list)     # [(folder, entry count)] over MAX_FOLDER_ITEMS


def crowded_folders(root):
    """[(folder, entries)] for every folder at or below root holding more than MAX_FOLDER_ITEMS entries."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        count = len(dirnames) + len(filenames)
        if count > MAX_FOLDER_ITEMS:
            found.append((Path(dirpath), count))
    return found


def ensure_layout(mount, system=None):
    """Create the missing layout folders in <mount>/MyDrive/AQIS_LAB; never creates AQIS_LAB, never deletes."""
    folder = aqis_lab_folder(mount)
    if not folder.is_dir():
        raise DriveError(f"{folder} does not exist or is not a folder: create the folder {MY_DRIVE}/{AQIS_FOLDER} in "
                         f"Google Drive first (the lab never creates it)")
    check_write_path(folder, system)
    blocked = [name for name in LAYOUT if (folder / name).exists() and not (folder / name).is_dir()]
    if blocked:
        raise DriveError(f"{', '.join(str(folder / n) for n in blocked)}: exists but is not a folder; the layout "
                         f"needs folders {', '.join(LAYOUT)} (nothing was created or changed)")
    result = LayoutResult(folder)
    for name in LAYOUT:
        if (folder / name).is_dir():
            result.existing.append(name)
        else:
            make_dirs(folder / name, system)
            result.created.append(name)
    result.crowded = crowded_folders(folder)
    for path, count in result.crowded:
        print(f"WARNING: {path} holds {count:,} entries, more than {MAX_FOLDER_ITEMS:,}; Google Drive gets slow and "
              f"unreliable with crowded folders. Split the content into subfolders.", file=sys.stderr, flush=True)
    return result
