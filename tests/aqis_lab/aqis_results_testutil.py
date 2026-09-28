"""Shared helpers for the WP-0.6 tests (Oracle setup, core reservation, results store, trace, sync). Not a test module.

Test doubles, each for an external service the rules name: a generated system tree with the Oracle asset tag and
CPU topology files stands in for the Oracle VM's cores (the pinning itself is real and runs on this machine's
CPUs), and an rclone `alias` remote on a local folder stands in for Google Drive (rclone itself is real). Expected
values are computed here independently of the code under test.
"""
import os
import re
from pathlib import Path

from aqis_lab import platform as lp
from aqis_runner_testutil import make_system_tree

ORACLE_TAG = "OracleCloud.com"


def cpu_list_text(cpus):
    """Kernel CPU-list text ("0-2,5") for a set of CPU numbers, written independently of aqis_lab."""
    cpus = sorted(cpus)
    parts, i = [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        parts.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(parts)


def parse_cpu_list(text):
    """The set of CPU numbers in kernel CPU-list text, parsed independently of aqis_lab."""
    out = set()
    for part in text.strip().split(","):
        lo, _, hi = part.partition("-")
        out.update(range(int(lo), int(hi or lo) + 1))
    return out


def usable_cpus():
    """This process's allowed CPUs; the core tests reserve the highest one and need at least one more for batch."""
    cpus = sorted(os.sched_getaffinity(0))
    assert len(cpus) >= 2, f"the core reservation tests need at least 2 CPUs, this machine allows {cpus}"
    return cpus


def oracle_system(tmp_path, online=None, siblings=None, name="oracle-sys"):
    """A SystemView that is the Oracle platform (asset tag) with the given online CPUs and SMT sibling groups.

    `online` defaults to this machine's usable CPUs; `siblings` is a list of CPU groups sharing a physical core
    (default: every CPU its own core, as on the Ampere A1 in docs/environment/oracle_probe.txt).
    """
    online = usable_cpus() if online is None else sorted(online)
    root = make_system_tree(Path(tmp_path) / name, chassis_asset_tag=ORACLE_TAG)
    base = root / "sys" / "devices" / "system" / "cpu"
    base.mkdir(parents=True, exist_ok=True)
    (base / "online").write_text(cpu_list_text(online) + "\n", encoding="utf-8")
    groups = siblings if siblings is not None else [[c] for c in online]
    for group in groups:
        for cpu in group:
            topo = base / f"cpu{cpu}" / "topology"
            topo.mkdir(parents=True, exist_ok=True)
            (topo / "thread_siblings_list").write_text(cpu_list_text(group) + "\n", encoding="utf-8")
    return lp.SystemView(root=root, environ={"PATH": str(root / "bin")}, path=str(root / "bin"))


def cloud_system(tmp_path, name="cloud-sys"):
    """A SystemView that is the cloud VM (CLAUDE_CODE_REMOTE=true), without any core files."""
    root = make_system_tree(Path(tmp_path) / name)
    return lp.SystemView(root=root, environ={"PATH": str(root / "bin"), "CLAUDE_CODE_REMOTE": "true"},
                         path=str(root / "bin"))


def oracle_config_text(reserved, remote="aqis-drive", results_store="data/raw/aqis_lab/results",
                       operating_systems="ubuntu:24.04", architectures="x86_64 aarch64", min_glibc="2.28",
                       work_dir="data/raw/aqis_lab/work", doctor_reports="data/raw/aqis_lab/doctor",
                       logs="data/raw/aqis_lab/logs"):
    return (f'schema_version: "1.0"\nsetup:\n  architectures: "{architectures}"\n'
            f'  operating_systems: "{operating_systems}"\n  min_glibc: "{min_glibc}"\npaths:\n'
            f"  work_dir: {work_dir}\n  doctor_reports: {doctor_reports}\n  results_store: {results_store}\n"
            f"  logs: {logs}\ncores:\n  reserved_for_timing: [{', '.join(str(c) for c in reserved)}]\n"
            f"rclone:\n  remote: {remote}\n")


def write_oracle_config(path, reserved, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(oracle_config_text(reserved, **kwargs), encoding="utf-8")
    return path


def thread_masks(pid):
    """{thread id: allowed CPUs} for every thread of a running process, read from /proc/<pid>/task/*/status."""
    masks = {}
    for task in sorted(Path(f"/proc/{pid}/task").iterdir()):
        text = (task / "status").read_text(encoding="utf-8")
        m = re.search(r"^Cpus_allowed_list:\s*(\S+)$", text, re.M)
        assert m, f"no Cpus_allowed_list in {task}/status"
        masks[int(task.name)] = parse_cpu_list(m.group(1))
    return masks
