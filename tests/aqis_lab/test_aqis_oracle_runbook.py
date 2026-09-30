"""FR-0.6-06: docs/oracle/ORACLE_RUNBOOK.md gives the owner exact steps: clone, setup, doctor, rclone configuration,
a nightly sync schedule and how to report results back; its commands exist and parse, and its values equal the
settings files.
"""
import importlib
import re
import shlex
from pathlib import Path

import yaml

from aqis_lab import oracle_config as oc
from aqis_lab.__main__ import COMMANDS
from aqis_lab.sync import MIN_RCLONE, RUNBOOK
from aqis_testutil import ROOT

DOC = ROOT / "docs" / "oracle" / "ORACLE_RUNBOOK.md"
TEXT = DOC.read_text(encoding="utf-8")
REQUIRED = ["Before you start", "Clone the repository", "Install uv and rclone", "Set up the lab", "Doctor",
            "Core reservation", "Configure rclone for Google Drive", "First sync", "Nightly sync schedule",
            "Report results back", "When something fails", "Update to a new tag"]


def sections():
    return re.findall(r"^## (.+)$", TEXT, re.M)


def section(title):
    return TEXT.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]


def code_lines():
    blocks = re.findall(r"```(?:bash|text)\n(.*?)```", TEXT, re.S)
    inline = re.findall(r"`([^`\n]*python -m aqis_lab [^`\n]*)`", TEXT)
    return [l.strip() for b in blocks for l in b.splitlines() if l.strip()] + inline


def test_FR_0_6_06_runbook_has_each_required_step():
    assert sections() == REQUIRED
    assert RUNBOOK == "docs/oracle/ORACLE_RUNBOOK.md" and DOC.exists()
    assert "ssh-keygen" in section("Clone the repository") and "Deploy keys" in section("Clone the repository")
    assert "git clone" in section("Clone the repository") and "git checkout aqis-lab-wp-0.6-oracle-1" in TEXT
    assert "bash aqis_lab/deploy/oracle_setup.sh --dry-run" in section("Set up the lab")
    assert "doctor --target oracle" in section("Doctor")
    assert 'rclone authorize "drive"' in section("Configure rclone for Google Drive")
    assert "rclone config" in section("Configure rclone for Google Drive")
    assert "crontab -e" in section("Nightly sync schedule") and "flock -n" in section("Nightly sync schedule")
    report = section("Report results back")
    assert "OC-0.6-01" in report and "OC-0.6-02" in report and "scp " in report
    assert "docs/progress/WP-0.6/OC-0.6-01_oracle.txt" in report
    assert "docs/progress/WP-0.6/OC-0.6-02_sync_dry_run.txt" in report
    # the sections that error messages send the owner to exist
    for path in (ROOT / "aqis_lab").rglob("*"):
        if path.suffix in (".py", ".sh"):
            for name in re.findall(r'section \\?"([^"\\]+)\\?"', path.read_text(encoding="utf-8")):
                assert name in REQUIRED, (path, name)


def test_FR_0_6_06_runbook_commands_exist_and_parse():
    lines = code_lines()
    lab = []
    for line in lines:
        for m in re.finditer(r"python -m aqis_lab ([^>&|;`]*)", line):
            lab.append(shlex.split(m.group(1)))
    assert {args[0] for args in lab} >= {"doctor", "results", "sync", "run"}
    for args in lab:
        assert args[0] in COMMANDS, args
        module = importlib.import_module(COMMANDS[args[0]][0])
        module.build_parser().parse_args(args[1:])
    scripts = set(re.findall(r"bash (aqis_lab/deploy/[\w.]+\.sh)", TEXT))
    assert scripts == {"aqis_lab/deploy/oracle_setup.sh"}
    assert all((ROOT / s).is_file() for s in scripts)
    cron = [l for l in lines if re.match(r"^[\d*/,-]+ [\d*/,-]+ [\d*/,-]+ [\d*/,-]+ [\d*/,-]+ ", l)]
    assert len(cron) == 1 and "python -m aqis_lab sync" in cron[0]
    fields = cron[0].split()[:5]
    assert 0 <= int(fields[0]) < 60 and 0 <= int(fields[1]) < 24 and fields[2:] == ["*", "*", "*"]


def test_FR_0_6_06_runbook_matches_config():
    cfg = oc.load()
    assert f"**`{cfg.rclone_remote}`**" in TEXT and f"{cfg.rclone_remote}:AQIS_LAB/results" in TEXT
    reserved = "-".join(str(c) for c in (min(cfg.reserved_for_timing), max(cfg.reserved_for_timing)))
    assert list(cfg.reserved_for_timing) == list(range(min(cfg.reserved_for_timing), max(cfg.reserved_for_timing) + 1))
    assert f"**CPUs {reserved} for timing runs**" in TEXT and "**batch runs use CPUs 0-1**" in TEXT
    assert "`ubuntu:24.04`" in TEXT and cfg.operating_systems == ("ubuntu:24.04",)
    assert f"glibc {cfg.min_glibc} or newer" in TEXT
    assert str(cfg.results_store.relative_to(oc.REPO_ROOT)) in TEXT
    assert str(cfg.logs.relative_to(oc.REPO_ROOT)) + "/sync.log" in TEXT
    assert f"rclone {'.'.join(map(str, MIN_RCLONE))} or newer" in TEXT and "uv 0.8.17" in TEXT
    minimums = yaml.safe_load((ROOT / "config/aqis_lab/doctor.yaml").read_text(encoding="utf-8"))["minimums"]["oracle"]
    row = re.search(r"^\| oracle \| (\S+) \| (\S+) \|$", section("Doctor"), re.M)
    assert row and (float(row.group(1)), float(row.group(2))) == (minimums["free_disk_gb"],
                                                                 minimums["available_ram_gb"])
    assert f"At least {minimums['free_disk_gb']} GB free" in TEXT and f"At least {minimums['available_ram_gb']} GB available" in TEXT
