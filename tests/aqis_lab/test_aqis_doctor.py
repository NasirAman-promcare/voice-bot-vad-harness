"""FR-0.5-02: `python -m aqis_lab doctor --target cloud|colab|oracle [--expect-gpu]`."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from aqis_lab import doctor
from aqis_lab import platform as lp
from aqis_runner_testutil import (MEMINFO, colab_env, drive_mountinfo_line, make_system_tree, nvidia_smi_script,
                                  stand_in_drive, write_command)
from aqis_testutil import ROOT, parse_lock, probe_python_major_minor

CONFIG = ROOT / "config" / "aqis_lab" / "doctor.yaml"
DOCTOR_DOC = ROOT / "docs" / "doctor" / "DOCTOR.md"
NAME_RE = re.compile(r"^doctor_(cloud-vm|colab|kaggle|oracle|unknown)_\d{8}T\d{6}Z\.json$")


def inputs_tree(tmp_path, probe=None, lock=None, minimums=None):
    """A copy of the doctor's inputs (probe, lock, minimums) that a test may change."""
    tree = tmp_path / "inputs"
    for rel in ("docs/environment/colab_probe.txt", "requirements/aqis_lab/phase0.txt", "config/aqis_lab/doctor.yaml"):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tree / rel)
    if probe is not None:
        (tree / "docs/environment/colab_probe.txt").write_text(probe, encoding="utf-8")
    if lock is not None:
        (tree / "requirements/aqis_lab/phase0.txt").write_text(lock, encoding="utf-8")
    if minimums is not None:
        (tree / "config/aqis_lab/doctor.yaml").write_text(yaml.safe_dump(minimums), encoding="utf-8")
    return tree


def rows(report):
    return {c.name: c for c in report.checks}


def cloud_system(tmp_path, meminfo=MEMINFO):
    root = make_system_tree(tmp_path / "sys", meminfo=meminfo)
    return lp.SystemView(root=root, environ={"CLAUDE_CODE_REMOTE": "true", "PATH": str(root / "bin")},
                         path=str(root / "bin"))


def colab_system(tmp_path, mount=None):
    mountinfo = drive_mountinfo_line(mount) if mount is not None else ""
    root = make_system_tree(tmp_path / "sys", mountinfo=mountinfo)
    return lp.SystemView(root=root, environ=colab_env({"PATH": str(root / "bin")}), path=str(root / "bin"))


def run_cli(*args, prefix=(), cwd=ROOT):
    return subprocess.run([*prefix, sys.executable, "-m", "aqis_lab", "doctor", *args], cwd=cwd,
                          capture_output=True, text=True, timeout=300)


def lock_with(change):
    """The real lock text with one entry changed by `change(name, block) -> new block or None to drop`."""
    text = (ROOT / "requirements/aqis_lab/phase0.txt").read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text)
    out = []
    for block in blocks:
        name = block.split("==", 1)[0].strip()
        new = change(name, block)
        if new is not None:
            out.append(new)
    return "\n".join(out)


def test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json(tmp_path):
    proc = run_cli("--target", "cloud", "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    expected = {"platform": "PASS", "python": "PASS", "lock": "PASS", "disk": "PASS", "ram": "PASS", "gpu": "SKIP"}
    table = {l.split()[0]: l.split()[1] for l in lines if l.split() and l.split()[0] in expected}
    assert table == expected, proc.stdout
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and NAME_RE.match(files[0].name) and files[0].name.startswith("doctor_cloud-vm_")
    assert str(files[0]) in proc.stdout
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["target"] == "cloud" and data["expect_gpu"] is False and data["result"] == "PASS"
    assert [c["name"] for c in data["checks"]] == list(expected)
    assert {c["name"]: c["status"] for c in data["checks"]} == expected
    assert data["machine"] == lp.machine_block()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", data["created_utc"])
    import hashlib
    assert data["lock"]["sha256"] == hashlib.sha256((ROOT / "requirements/aqis_lab/phase0.txt").read_bytes()).hexdigest()
    stamp = files[0].name[len("doctor_cloud-vm_"):-len(".json")]
    assert stamp == re.sub(r"[-:]|\.\d+", "", data["created_utc"])


def test_FR_0_5_02_fails_on_python_version_other_than_probe(tmp_path):
    other = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path / "a", probe="Python Version: 3.99.1 (main)\n"))
    row = rows(other)["python"]
    assert row.status == "FAIL" and row.expected == "3.99" and other.result == "FAIL"
    assert "%d.%d.%d" % sys.version_info[:3] in row.actual
    # the rule compares major.minor (owner decision, question 9): another patch release passes
    same = doctor.run_doctor("cloud", repo_root=inputs_tree(
        tmp_path / "b", probe=f"Python Version: {probe_python_major_minor()}.99 (main)\n"))
    assert rows(same)["python"].status == "PASS"
    unreadable = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path / "c", probe="no version here\n"))
    assert rows(unreadable)["python"].status == "FAIL"


def test_FR_0_5_02_fails_on_package_version_other_than_lock(tmp_path):
    lock = lock_with(lambda name, b: b.replace(f"pytest=={parse_lock()['pytest']['version']}", "pytest==0.0.1", 1)
                     if name == "pytest" else b)
    row = rows(doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path, lock=lock)))["lock"]
    assert row.status == "FAIL"
    assert "pytest" in row.detail and "0.0.1" in row.detail and parse_lock()["pytest"]["version"] in row.detail


def test_FR_0_5_02_fails_on_package_missing_from_lock(tmp_path):
    lock = lock_with(lambda name, b: None if name == "jiwer" else b)
    row = rows(doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path, lock=lock)))["lock"]
    assert row.status == "FAIL" and "jiwer" in row.detail and "not in the lock" in row.detail


def test_FR_0_5_02_fails_on_lock_package_not_installed(tmp_path):
    extra = "aqis-absent-package==1.0.0 \\\n    --hash=sha256:" + "0" * 64 + "\n"
    lock = lock_with(lambda name, b: b) + "\n" + extra
    row = rows(doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path, lock=lock)))["lock"]
    assert row.status == "FAIL" and "aqis-absent-package" in row.detail and "not installed" in row.detail


def huge(key):
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for target in data["minimums"]:
        data["minimums"][target][key] = 10 ** 9
    return data


def test_FR_0_5_02_fails_below_disk_minimum(tmp_path):
    report = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path, minimums=huge("free_disk_gb")),
                               work_dir=tmp_path)
    assert rows(report)["disk"].status == "FAIL" and rows(report)["ram"].status == "PASS"
    assert report.result == "FAIL"


def test_FR_0_5_02_fails_below_ram_minimum(tmp_path):
    system = cloud_system(tmp_path, meminfo="MemTotal: 4000000 kB\nMemAvailable:    3000000 kB\n")
    report = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path), system=system)
    row = rows(report)["ram"]
    assert row.status == "FAIL" and report.result == "FAIL"
    assert "3072000000" in row.actual.replace(",", "")          # 3,000,000 kB is 3,072,000,000 bytes
    ok = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path / "b"), system=cloud_system(tmp_path / "b"))
    assert rows(ok)["ram"].status == "PASS"


def test_FR_0_5_02_gpu_skipped_without_expect_gpu(tmp_path):
    report = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path))
    assert rows(report)["gpu"].status == "SKIP" and report.result == "PASS"


def test_FR_0_5_02_expect_gpu_fails_without_gpu(tmp_path):
    report = doctor.run_doctor("cloud", expect_gpu=True, repo_root=inputs_tree(tmp_path), system=cloud_system(tmp_path))
    assert rows(report)["gpu"].status == "FAIL" and report.result == "FAIL"
    proc = run_cli("--target", "cloud", "--expect-gpu", "--out", str(tmp_path / "out"))
    assert proc.returncode == 1 and re.search(r"^gpu\s+FAIL", proc.stdout, re.M), proc.stdout


def test_FR_0_5_02_expect_gpu_passes_with_gpu(tmp_path):
    system = cloud_system(tmp_path)
    write_command(system.root / "bin", "nvidia-smi", nvidia_smi_script(["Tesla T4"]))
    report = doctor.run_doctor("cloud", expect_gpu=True, repo_root=inputs_tree(tmp_path), system=system)
    assert rows(report)["gpu"].status == "PASS" and rows(report)["gpu"].actual == "Tesla T4"
    assert report.result == "PASS"


def test_FR_0_5_02_fails_when_target_is_not_this_platform(tmp_path):
    proc = run_cli("--target", "oracle", "--out", str(tmp_path))
    assert proc.returncode == 1
    assert re.search(r"^platform\s+FAIL\s+oracle\s+cloud-vm", proc.stdout, re.M), proc.stdout
    unknown = lp.SystemView(root=make_system_tree(tmp_path / "sys"), environ={"PATH": ""}, path="")
    report = doctor.run_doctor("cloud", repo_root=inputs_tree(tmp_path), system=unknown)
    assert rows(report)["platform"].status == "FAIL" and report.machine is None
    assert report.platform_name == "unknown"


def test_FR_0_5_02_colab_fails_when_drive_not_mounted(tmp_path):
    mount = stand_in_drive(tmp_path)
    report = doctor.run_doctor("colab", repo_root=inputs_tree(tmp_path), system=colab_system(tmp_path, mount=None),
                               drive_mount=mount)
    assert rows(report)["drive-mount"].status == "FAIL" and report.result == "FAIL"


def test_FR_0_5_02_colab_fails_when_aqis_lab_missing(tmp_path):
    mount = stand_in_drive(tmp_path, with_aqis_lab=False)
    report = doctor.run_doctor("colab", repo_root=inputs_tree(tmp_path), system=colab_system(tmp_path, mount),
                               drive_mount=mount)
    row = rows(report)["drive-folder"]
    assert rows(report)["drive-mount"].status == "PASS"
    assert row.status == "FAIL" and "missing" in row.detail and report.result == "FAIL"
    assert not (mount / "MyDrive" / "AQIS_LAB").exists(), "the doctor never creates AQIS_LAB"


def test_FR_0_5_02_colab_fails_when_aqis_lab_read_only(tmp_path):
    mount = stand_in_drive(tmp_path)
    folder = mount / "MyDrive" / "AQIS_LAB"
    folder.chmod(0o555)
    out = tmp_path / "out"
    # As root the mode bits are ignored; removing root's override makes them apply as for any user (plan finding 6).
    prefix = ["setpriv", "--bounding-set", "-dac_override,-dac_read_search", "--"] if os.geteuid() == 0 else []
    try:
        proc = run_cli("--target", "colab", "--drive-mount", str(mount), "--out", str(out), prefix=prefix)
    finally:
        folder.chmod(0o755)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = json.loads(next(out.iterdir()).read_text(encoding="utf-8"))
    row = next(c for c in report["checks"] if c["name"] == "drive-folder")
    assert row["status"] == "FAIL" and "not writable" in row["detail"] and "Permission denied" in row["detail"]
    assert list(folder.iterdir()) == []


def test_FR_0_5_02_colab_drive_checks_pass_when_writable(tmp_path):
    mount = stand_in_drive(tmp_path)
    report = doctor.run_doctor("colab", repo_root=inputs_tree(tmp_path), system=colab_system(tmp_path, mount),
                               drive_mount=mount)
    r = rows(report)
    assert [c.name for c in report.checks] == ["platform", "python", "lock", "disk", "ram", "gpu", "drive-mount",
                                                "drive-folder"]
    assert r["drive-mount"].status == "PASS" and r["drive-folder"].status == "PASS", report.checks
    assert report.result == "PASS"
    check = mount / "MyDrive" / "AQIS_LAB" / doctor.WRITE_CHECK
    assert json.loads(check.read_text(encoding="utf-8"))["created_utc"] == report.created_utc
    again = doctor.run_doctor("colab", repo_root=inputs_tree(tmp_path / "b"), system=colab_system(tmp_path / "b", mount),
                              drive_mount=mount)
    assert again.result == "PASS"
    assert sorted(p.name for p in (mount / "MyDrive" / "AQIS_LAB").iterdir()) == [doctor.WRITE_CHECK], \
        "the write check reuses one file; nothing accumulates"


def test_FR_0_5_02_any_fail_exits_non_zero(tmp_path):
    assert run_cli("--target", "oracle", "--out", str(tmp_path / "a")).returncode == 1
    assert run_cli("--target", "cloud", "--out", str(tmp_path / "b")).returncode == 0
    usage = run_cli("--target", "colab", "--out", str(tmp_path / "c"))
    assert usage.returncode == 2 and "--drive-mount" in usage.stderr
    assert run_cli("--target", "moon").returncode == 2


def documented_minimums(text):
    found = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*`?(cloud|colab|oracle)`?\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|", line)
        if m:
            found[m.group(1)] = {"free_disk_gb": float(m.group(2)), "available_ram_gb": float(m.group(3))}
    return found


def test_FR_0_5_02_minimums_documented_equal_config():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["minimums"]
    as_float = {t: {k: float(v) for k, v in m.items()} for t, m in config.items()}
    assert set(as_float) == {"cloud", "colab", "oracle"}
    assert documented_minimums(DOCTOR_DOC.read_text(encoding="utf-8")) == as_float
    # owner decision (question 8 (a)): 10 GB free disk and 4 GB available RAM on every target
    assert as_float == {t: {"free_disk_gb": 10.0, "available_ram_gb": 4.0} for t in ("cloud", "colab", "oracle")}
