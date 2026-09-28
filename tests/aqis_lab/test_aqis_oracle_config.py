"""WP-0.6: config/aqis_lab/oracle.yaml and its strict loader aqis_lab/oracle_config.py (FR-0.6-01, -04, -05)."""
import subprocess
import sys
from pathlib import Path

import pytest

from aqis_testutil import ROOT

from aqis_lab import oracle_config as oc

CONFIG = ROOT / "config" / "aqis_lab" / "oracle.yaml"

VALID = """\
schema_version: "1.0"
setup:
  architectures: "x86_64 aarch64"
  operating_systems: "ubuntu:24.04"
  min_glibc: "2.28"
paths:
  work_dir: data/raw/aqis_lab/work
  doctor_reports: data/raw/aqis_lab/doctor
  results_store: data/raw/aqis_lab/results
  logs: data/raw/aqis_lab/logs
cores:
  reserved_for_timing: [2, 3]
rclone:
  remote: aqis-drive
"""


def write(tmp_path, text):
    path = tmp_path / "oracle.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_FR_0_6_01_config_committed_values_follow_probe_and_approval():
    # docs/environment/oracle_probe.txt: Ubuntu 24.04.4 LTS on aarch64, glibc 2.39; this cloud VM: Ubuntu 24.04 on
    # x86_64. The lock's wheels need manylinux_2_28 (PLAN.md finding 4). docs/approvals/WP-0.6.md: cores 2-3 for
    # timing runs, batch runs on cores 0-1; questions 5 and 12: remote aqis-drive.
    cfg = oc.load(CONFIG)
    assert cfg.architectures == ("x86_64", "aarch64")
    assert cfg.operating_systems == ("ubuntu:24.04",)
    assert cfg.min_glibc == "2.28"
    assert cfg.reserved_for_timing == (2, 3)
    assert cfg.rclone_remote == "aqis-drive"
    assert cfg.results_store == ROOT / "data" / "raw" / "aqis_lab" / "results"
    assert cfg.work_dir == ROOT / "data" / "raw" / "aqis_lab" / "work"
    assert cfg.doctor_reports == ROOT / "data" / "raw" / "aqis_lab" / "doctor"
    assert cfg.logs == ROOT / "data" / "raw" / "aqis_lab" / "logs"


def test_FR_0_6_01_config_relative_paths_resolve_from_repository_root_absolute_kept(tmp_path):
    text = VALID.replace("  logs: data/raw/aqis_lab/logs", f"  logs: {tmp_path / 'logs'}")
    cfg = oc.load(write(tmp_path, text))
    assert cfg.results_store == oc.REPO_ROOT / "data/raw/aqis_lab/results"
    assert cfg.logs == tmp_path / "logs"


@pytest.mark.parametrize("old,new,words", [
    ('schema_version: "1.0"', 'schema_version: "2.0"', "schema_version"),
    ("rclone:\n  remote: aqis-drive\n", "", "rclone"),
    ("  logs: data/raw/aqis_lab/logs\n", "  logs: data/raw/aqis_lab/logs\n  extra: x\n", "paths"),
    ("cores:\n", "cores:\n  other: 1\n", "cores"),
    ('  architectures: "x86_64 aarch64"', '  architectures: ""', "setup.architectures"),
    ('  architectures: "x86_64 aarch64"', "  architectures: x86_64 aarch64", "setup.architectures"),
    ('  operating_systems: "ubuntu:24.04"', '  operating_systems: "ubuntu"', "setup.operating_systems"),
    ('  min_glibc: "2.28"', '  min_glibc: "2"', "setup.min_glibc"),
    ("[2, 3]", "[]", "cores.reserved_for_timing"),
    ("[2, 3]", "[2, 2]", "cores.reserved_for_timing"),
    ("[2, 3]", "[-1]", "cores.reserved_for_timing"),
    ("[2, 3]", "[true]", "cores.reserved_for_timing"),
    ("[2, 3]", "[2.0]", "cores.reserved_for_timing"),
    ("[2, 3]", "3", "cores.reserved_for_timing"),
    ("  remote: aqis-drive", "  remote: 'aqis:drive'", "rclone.remote"),
    ("  remote: aqis-drive", "  remote: ''", "rclone.remote"),
    ("  work_dir: data/raw/aqis_lab/work", "  work_dir: ''", "paths.work_dir"),
    ("  work_dir: data/raw/aqis_lab/work", "  work_dir: 7", "paths.work_dir"),
])
def test_FR_0_6_01_config_rejects_each_malformed_value(tmp_path, old, new, words):
    assert old in VALID
    with pytest.raises(oc.OracleConfigError) as info:
        oc.load(write(tmp_path, VALID.replace(old, new, 1)))
    assert words in str(info.value)


def test_FR_0_6_01_config_rejects_duplicate_key(tmp_path):
    text = VALID.replace("  remote: aqis-drive\n", "  remote: aqis-drive\n  remote: other\n")
    with pytest.raises(oc.OracleConfigError) as info:
        oc.load(write(tmp_path, text))
    assert "duplicate key 'remote'" in str(info.value)


def test_FR_0_6_01_config_missing_or_unreadable_file_is_an_error(tmp_path):
    with pytest.raises(oc.OracleConfigError) as info:
        oc.load(tmp_path / "nothing.yaml")
    assert "nothing.yaml" in str(info.value)
    with pytest.raises(oc.OracleConfigError):
        oc.load(write(tmp_path, "schema_version: [unclosed\n"))


def test_FR_0_6_01_config_get_prints_resolved_value(tmp_path):
    path = write(tmp_path, VALID)
    for key, expected in [("paths.work_dir", str(oc.REPO_ROOT / "data/raw/aqis_lab/work")),
                          ("rclone.remote", "aqis-drive"), ("cores.reserved_for_timing", "2 3"),
                          ("setup.operating_systems", "ubuntu:24.04")]:
        proc = subprocess.run([sys.executable, "-m", "aqis_lab.oracle_config", "get", key, "--config", str(path)],
                              cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == expected + "\n"
    proc = subprocess.run([sys.executable, "-m", "aqis_lab.oracle_config", "get", "paths.nothing", "--config",
                           str(path)], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:") and "paths.nothing" in proc.stderr


def test_FR_0_6_05_drive_destination_is_fixed_by_spec():
    assert oc.DRIVE_DESTINATION == "AQIS_LAB/results"
    assert not hasattr(oc.load(CONFIG), "destination")
