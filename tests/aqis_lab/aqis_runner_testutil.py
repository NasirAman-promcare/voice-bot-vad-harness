"""Shared helpers for the WP-0.5 tests (platform, doctor, Drive, staging, runner, unit log). Not a test module.

Generated system trees stand in for the operating-system files that aqis_lab.platform reads, stand-in commands on
PATH stand in for nvidia-smi and lscpu (GPU test doubles), and a folder with a generated mountinfo entry stands in for
Google Drive: the three external things the rules allow tests to replace. Expected values are computed here
independently of the code under test.
"""
import os
import shlex
import stat
from pathlib import Path

from aqis_testutil import ROOT

SMOKE_PACK = ROOT / "data" / "packs" / "smoke" / "v1"

X86_CPUINFO = ("processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n"
               "flags\t\t: fpu vme\n\nprocessor\t: 1\nmodel name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n")
ARM_CPUINFO = "processor\t: 0\nBogoMIPS\t: 50.00\nFeatures\t: fp asimd\nCPU implementer\t: 0x41\nCPU part\t: 0xd0c\n"
UBUNTU_OS_RELEASE = 'PRETTY_NAME="Ubuntu 24.04.4 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nID=ubuntu\n'
MEMINFO = "MemTotal:       16000000 kB\nMemFree:         1000000 kB\nMemAvailable:    8000000 kB\n"


def write_command(bin_dir, name, script):
    """An executable shell script `name` in bin_dir (a stand-in command on PATH)."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def nvidia_smi_script(names, exit_code=0, stderr=""):
    """A stand-in nvidia-smi that answers only the exact query aqis_lab.platform must use."""
    body = "".join(f"echo {shlex.quote(n)}\n" for n in names)
    err = f"echo {shlex.quote(stderr)} >&2\n" if stderr else ""
    return ('if [ "$*" != "--query-gpu=name --format=csv,noheader" ]; then echo "unexpected arguments: $*" >&2; '
            f'exit 64; fi\n{body}{err}exit {exit_code}\n')


def make_system_tree(root, cpuinfo=X86_CPUINFO, os_release=UBUNTU_OS_RELEASE, meminfo=MEMINFO, mountinfo="",
                     chassis_asset_tag=None):
    """A generated root folder holding the system files aqis_lab.platform reads."""
    root = Path(root)
    files = {"proc/cpuinfo": cpuinfo, "etc/os-release": os_release, "proc/meminfo": meminfo,
             "proc/self/mountinfo": mountinfo}
    if chassis_asset_tag is not None:
        files["sys/class/dmi/id/chassis_asset_tag"] = chassis_asset_tag + "\n"
    for rel, text in files.items():
        if text is None:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "bin").mkdir(parents=True, exist_ok=True)
    return root


def drive_mountinfo_line(mount_point, fstype="fuse.drive"):
    """One /proc/self/mountinfo line for a mount, in the format Colab showed (docs/environment/colab_platform_probe.txt)."""
    escaped = str(mount_point).replace("\\", "\\134").replace(" ", "\\040").replace("\t", "\\011").replace("\n", "\\012")
    return f"138 572 0:45 / {escaped} rw,nosuid,nodev,relatime - {fstype} drive rw,user_id=0,group_id=0\n"


def colab_env(extra=None):
    env = {"COLAB_RELEASE_TAG": "release-colab-external_20260920-060000_RC00", "PATH": "/usr/bin:/bin"}
    if extra:
        env.update(extra)
    return env


def stand_in_drive(tmp_path, with_aqis_lab=True):
    """A folder standing in for the Drive mount (Google Drive test double): <mount>/MyDrive[/AQIS_LAB]."""
    mount = Path(tmp_path) / "drive"
    (mount / "MyDrive").mkdir(parents=True)
    if with_aqis_lab:
        (mount / "MyDrive" / "AQIS_LAB").mkdir()
    return mount


def tree_snapshot(root):
    """{relative path: (kind, mode, bytes or None)} for every entry below root, for before/after comparisons."""
    root = Path(root)
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            st = path.lstat()
            kind = "dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"
            snap[path.relative_to(root).as_posix()] = (kind, stat.S_IMODE(st.st_mode),
                                                       path.read_bytes() if kind == "file" else None)
    return snap
