"""FR-0.6-01: aqis_lab/deploy/oracle_setup.sh checks the machine, checks the lock has builds for it, builds .venv on
the Colab Python from the hashed lock and runs the doctor for target oracle.

Every test copies the real script and the lab package into a throwaway git tree, so the repository's own .venv is
never touched. The unsupported-architecture test uses `setarch linux32`, which makes the kernel report i686 (the
WP-0.0 precedent); nothing in the script is replaced.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest
from packaging.markers import Marker

from aqis_lab import oracle_config as oc
from aqis_results_testutil import oracle_config_text, usable_cpus
from aqis_runner_testutil import tree_snapshot
from aqis_testutil import ROOT, hermetic_git_env, normalise, parse_lock, probe_python_major_minor

SCRIPT_REL = "aqis_lab/deploy/oracle_setup.sh"
COPIED = ("requirements/aqis_lab/phase0.txt", "docs/environment/colab_probe.txt", "config/aqis_lab/doctor.yaml")


def os_release():
    """(ID:VERSION_ID, PRETTY_NAME) of this machine, read independently of the script."""
    values = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key] = value.strip().strip('"')
    return f"{values['ID']}:{values['VERSION_ID']}", values.get("PRETTY_NAME", "")


def make_tree(tmp_path, config_text=None, lock_text=None):
    tree = tmp_path / "tree"
    shutil.copytree(ROOT / "aqis_lab", tree / "aqis_lab", ignore=shutil.ignore_patterns("__pycache__"))
    for rel in COPIED:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, tree / rel)
    if lock_text is not None:
        (tree / "requirements/aqis_lab/phase0.txt").write_text(lock_text, encoding="utf-8")
    config = tree / "config/aqis_lab/oracle.yaml"
    config.write_text(config_text if config_text is not None else oracle_config_text([usable_cpus()[-1]]),
                      encoding="utf-8")
    (tree / ".gitignore").write_text("/.venv/\n/data/raw/\n", encoding="utf-8")
    env = hermetic_git_env()
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run(["git", *args], cwd=tree, env=env, check=True, capture_output=True)
    return tree


def run(tree, *args, env=None, prefix=(), timeout=900):
    return subprocess.run([*prefix, "bash", str(tree / SCRIPT_REL), *args], cwd=tree, capture_output=True, text=True,
                          env=env, timeout=timeout)


def steps(stdout):
    return [line for line in stdout.splitlines() if line.startswith("step ")]


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


def test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing(tmp_path):
    tree = make_tree(tmp_path)
    before = tree_snapshot(tree)
    proc = run(tree, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    names = [re.match(r"step (\d)/6 (\w+):", line).groups() for line in steps(proc.stdout)]
    assert names == [("1", "platform"), ("2", "tools"), ("3", "python"), ("4", "wheels"), ("5", "venv"),
                     ("6", "doctor")]
    lines = steps(proc.stdout)
    assert lines[0].startswith("step 1/6 platform: PASS") and lines[1].startswith("step 2/6 tools: PASS")
    assert f"Python {probe_python_major_minor()}" in lines[2]
    assert "would check" in lines[3] and f"{len(parse_lock())} pins" in lines[3]   # every pin; uv evaluates markers
    assert "would create .venv" in lines[4] and "would run .venv/bin/python -m aqis_lab doctor --target oracle" in lines[5]
    assert proc.stdout.splitlines()[-1] == "DRY RUN: nothing was changed"
    assert tree_snapshot(tree) == before


def test_FR_0_6_01_dry_run_in_this_repository_reuses_venv():
    proc = run(ROOT, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "would reuse .venv" in steps(proc.stdout)[4]


@pytest.mark.parametrize("dry", [False, True])
def test_FR_0_6_01_refuses_unsupported_architecture(tmp_path, dry):
    # Must-catch 5: i686 (from `setarch linux32`) is outside x86_64 and aarch64; the script stops before any step.
    setarch = shutil.which("setarch")
    assert setarch, "setarch (util-linux) is needed for this test"
    tree = make_tree(tmp_path)
    before = tree_snapshot(tree)
    proc = run(tree, *(["--dry-run"] if dry else []), prefix=(setarch, "linux32"))
    assert proc.returncode == 1
    assert proc.stderr.strip() == ("ERROR: unsupported architecture i686: oracle_setup.sh supports x86_64 aarch64 "
                                   "(config/aqis_lab/oracle.yaml, setup.architectures).")
    assert steps(proc.stdout) == [] and tree_snapshot(tree) == before


def test_FR_0_6_01_refuses_unsupported_operating_system(tmp_path):
    # Must-catch 5: this machine's ID:VERSION_ID is not in the list, so the script stops before any step.
    this_os, pretty = os_release()
    tree = make_tree(tmp_path, oracle_config_text([1], operating_systems="debian:12 ubuntu:22.04"))
    before = tree_snapshot(tree)
    proc = run(tree)
    assert proc.returncode == 1
    assert proc.stderr.strip() == (f"ERROR: unsupported operating system {this_os} ({pretty}): oracle_setup.sh supports "
                                   f"debian:12 ubuntu:22.04 (config/aqis_lab/oracle.yaml, setup.operating_systems).")
    assert steps(proc.stdout) == [] and tree_snapshot(tree) == before


def test_FR_0_6_01_refuses_glibc_below_minimum(tmp_path):
    glibc = subprocess.run(["getconf", "GNU_LIBC_VERSION"], capture_output=True, text=True, check=True).stdout.split()[1]
    tree = make_tree(tmp_path, oracle_config_text([1], min_glibc="99.0"))
    proc = run(tree)
    assert proc.returncode == 1 and steps(proc.stdout) == []
    assert f"glibc {glibc} is older than 99.0" in proc.stderr and "setup.min_glibc" in proc.stderr


def test_FR_0_6_01_supports_x86_64_and_aarch64(tmp_path):
    # The spec's architectures; the list really decides: a list without this machine's architecture refuses it.
    assert oc.load().architectures == ("x86_64", "aarch64")
    arch = os.uname().machine
    assert arch in ("x86_64", "aarch64")
    other = "aarch64" if arch == "x86_64" else "x86_64"
    proc = run(make_tree(tmp_path, oracle_config_text([1], architectures=other)), "--dry-run")
    assert proc.returncode == 1 and f"unsupported architecture {arch}" in proc.stderr


def test_FR_0_6_01_setup_pin_read_by_script_equals_yaml(tmp_path):
    for i, text in enumerate([oc.DEFAULT_CONFIG.read_text(encoding="utf-8"),
                              oracle_config_text([1], operating_systems="ubuntu:24.04 debian:12",
                                                 architectures="aarch64 x86_64", min_glibc="2.17")]):
        tree = make_tree(tmp_path / str(i), text)
        cfg = oc.load(tree / "config/aqis_lab/oracle.yaml")
        proc = run(tree, "--dry-run")
        assert proc.returncode == 0, proc.stderr
        line = steps(proc.stdout)[0]
        assert f"(supported: {' '.join(cfg.architectures)})" in line
        assert f"; supported: {' '.join(cfg.operating_systems)})" in line
        assert f"(minimum {cfg.min_glibc})" in line
    tree = make_tree(tmp_path / "bad", oracle_config_text([1]).replace('  min_glibc: "2.28"', "  min_glibc: 2.28"))
    proc = run(tree, "--dry-run")
    assert proc.returncode == 1 and "setup.min_glibc must be written once" in proc.stderr


def wheel(folder, name, version, tag):
    """A minimal real wheel file (METADATA, WHEEL, RECORD) for a local uv find-links index."""
    dist = f"{name}-{version}.dist-info"
    files = {f"{name}/__init__.py": b"",
             f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
             f"{dist}/WHEEL": f"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: {tag}\n".encode()}
    record = "".join(f"{k},sha256={base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode()},"
                     f"{len(v)}\n" for k, v in files.items()) + f"{dist}/RECORD,,\n"
    path = Path(folder) / f"{name}-{version}-{tag}.whl"
    with zipfile.ZipFile(path, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
        z.writestr(f"{dist}/RECORD", record)
    return path


def test_FR_0_6_01_missing_build_names_the_package(tmp_path):
    # A lock whose second package has a Windows wheel only: the script names it, installs nothing. uv reads the
    # local wheels through its own UV_NO_INDEX and UV_FIND_LINKS settings; no network is used.
    links = tmp_path / "links"
    links.mkdir()
    good = wheel(links, "aqisgood", "1.0", "py3-none-any")
    win = wheel(links, "aqiswinonly", "2.5", "py3-none-win_amd64")
    lock = "".join(f"{n}=={v} \\\n    --hash=sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}\n"
                   for n, v, p in (("aqisgood", "1.0", good), ("aqiswinonly", "2.5", win)))
    tree = make_tree(tmp_path, lock_text=lock)
    env = dict(os.environ, UV_NO_INDEX="1", UV_FIND_LINKS=str(links), UV_CACHE_DIR=str(tmp_path / "uv-cache"))
    proc = run(tree, env=env)
    arch = os.uname().machine
    assert proc.returncode == 1, proc.stdout + proc.stderr
    errors = [line for line in proc.stderr.splitlines() if line.startswith("ERROR: no build of")]
    assert len(errors) == 1 and errors[0].startswith(f"ERROR: no build of aqiswinonly 2.5 for {arch} (glibc ")
    assert "Python " + probe_python_major_minor() in errors[0] and "requirements/aqis_lab/phase0.txt" in errors[0]
    assert "aqisgood" not in proc.stderr and "1 package(s)" in proc.stderr and "nothing was installed" in proc.stderr
    assert [s.split(":")[0] for s in steps(proc.stdout)] == ["step 1/6 platform", "step 2/6 tools", "step 3/6 python"]
    assert not (tree / ".venv").exists()


def test_FR_0_6_01_fails_when_uv_missing(tmp_path):
    tree = make_tree(tmp_path)
    proc = run(tree, env=dict(os.environ, PATH=path_without(tmp_path, {"uv", "uvx"})))
    assert proc.returncode == 1 and "uv not found on PATH" in proc.stderr
    assert "uv 0.8.17" in proc.stderr and "docs/oracle/ORACLE_RUNBOOK.md" in proc.stderr
    assert len(steps(proc.stdout)) == 1 and not (tree / ".venv").exists()


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_6_01_refuses_other_uv_version(tmp_path):
    # A real uv 0.8.16 from PyPI: the script needs exactly 0.8.17.
    arch = os.uname().machine
    info = json.load(urllib.request.urlopen("https://pypi.org/pypi/uv/0.8.16/json", timeout=60))
    url = next(f["url"] for f in info["urls"] if f["filename"].endswith(".whl") and "musllinux" not in f["filename"]
               and "manylinux" in f["filename"] and arch in f["filename"])
    wheel_path = tmp_path / "uv.whl"
    wheel_path.write_bytes(urllib.request.urlopen(url, timeout=300).read())
    bindir = tmp_path / "old-uv"
    bindir.mkdir()
    with zipfile.ZipFile(wheel_path) as z:
        member = next(n for n in z.namelist() if n.endswith("/scripts/uv"))
        (bindir / "uv").write_bytes(z.read(member))
    (bindir / "uv").chmod(0o755)
    tree = make_tree(tmp_path)
    env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{path_without(tmp_path, {'uv', 'uvx'})}")
    proc = run(tree, env=env)
    assert proc.returncode == 1 and "reports 'uv 0.8.16" in proc.stderr and "needs uv 0.8.17" in proc.stderr
    assert not (tree / ".venv").exists()


@pytest.mark.network
def test_FR_0_6_01_every_lock_package_has_x86_64_and_aarch64_builds(tmp_path):
    # The Oracle A1 VM is aarch64 (docs/environment/oracle_probe.txt, glibc 2.39); this VM and Colab are x86_64.
    pins = [f"{n}=={e['version']}" + (f" ; {e['marker']}" if e["marker"] else "") for n, e in parse_lock().items()]
    (tmp_path / "pins.txt").write_text("\n".join(pins) + "\n", encoding="utf-8")
    for platform in ("aarch64-manylinux_2_28", "x86_64-manylinux_2_28"):
        proc = subprocess.run(["uv", "pip", "compile", str(tmp_path / "pins.txt"), "--no-deps", "--only-binary",
                               ":all:", "--python-platform", platform, "--python-version", probe_python_major_minor(),
                               "--no-header", "--quiet", "-o", str(tmp_path / f"{platform}.txt")],
                              capture_output=True, text=True, timeout=600)
        assert proc.returncode == 0, (platform, proc.stderr)


def doctor_rows(tree):
    reports = sorted((tree / "data/raw/aqis_lab/doctor").glob("doctor_*.json"))
    return reports, {c["name"]: c for c in json.loads(reports[-1].read_text())["checks"]}


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor(tmp_path):
    # On this VM the doctor for target oracle must fail exactly its platform row (this is the cloud VM).
    tree = make_tree(tmp_path)
    proc = run(tree)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = steps(proc.stdout)
    assert [l.split(":")[0] for l in lines[:5]] == [f"step {i}/6 {n}" for i, n in
                                                     enumerate(("platform", "tools", "python", "wheels", "venv"), 1)]
    assert all(": PASS" in l for l in lines[:5]) and lines[5].startswith("step 6/6 doctor: .venv/bin/python -m aqis_lab "
                                                                          "doctor --target oracle --work-dir ")
    python = tree / ".venv/bin/python"
    version = subprocess.run([str(python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                             capture_output=True, text=True, check=True).stdout.strip()
    assert version == probe_python_major_minor()
    installed = json.loads(subprocess.run(
        [str(python), "-c", "import json, importlib.metadata as m; print(json.dumps({d.metadata['Name']: d.version "
                            "for d in m.distributions()}))"], capture_output=True, text=True, check=True).stdout)
    lock = {n: e["version"] for n, e in parse_lock().items() if not e["marker"] or Marker(e["marker"]).evaluate()}
    assert {normalise(k): v for k, v in installed.items()} == lock
    reports, rows = doctor_rows(tree)
    assert len(reports) == 1 and json.loads(reports[0].read_text())["target"] == "oracle"
    assert rows["platform"]["status"] == "FAIL" and rows["platform"]["expected"] == "oracle"
    assert {n: r["status"] for n, r in rows.items() if n != "platform"} == {
        "python": "PASS", "lock": "PASS", "disk": "PASS", "ram": "PASS", "gpu": "SKIP", "cores": "PASS"}
    assert "the doctor reported a problem (exit 1)" in proc.stderr


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_6_01_second_run_changes_nothing(tmp_path):
    tree = make_tree(tmp_path)
    run(tree)
    python = tree / ".venv/bin/python"
    site = sorted((tree / ".venv/lib").glob("python*/site-packages"))[0]
    state = lambda: ((python.resolve().stat().st_ino, python.stat().st_mtime_ns),
                     sorted((p.name, p.stat().st_mtime_ns) for p in site.iterdir()))
    before = state()
    # Doctor report names have one-second resolution (FR-0.5-02) and a report is never replaced, so two doctor runs
    # in the same second fail with exit 2. With a warm uv cache a setup run can finish in under a second here, so the
    # second run starts in a later second; the property under test is that nothing is reinstalled.
    time.sleep(1.1)
    second = run(tree)
    assert second.returncode == 1, second.stdout + second.stderr      # the doctor's platform row, as above
    assert "Reusing .venv" in second.stdout
    assert not re.search(r"^ [+-] ", second.stdout + second.stderr, re.M), "the second run installed or removed"
    assert state() == before
    reports, _ = doctor_rows(tree)
    assert len(reports) == 2                                           # one new report per run, none replaced


@pytest.mark.oracle
def test_FR_0_6_01_setup_passes_on_oracle():
    # On the Oracle VM, in the clone: the whole setup passes and the doctor passes every row (GPU skipped).
    proc = run(ROOT, timeout=1800)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = sorted((ROOT / "data/raw/aqis_lab/doctor").glob("doctor_oracle_*.json"))[-1]
    rows = {c["name"]: c["status"] for c in json.loads(report.read_text())["checks"]}
    assert rows == {"platform": "PASS", "python": "PASS", "lock": "PASS", "disk": "PASS", "ram": "PASS",
                    "gpu": "SKIP", "cores": "PASS"}


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_6_01_runs_from_any_directory(tmp_path):
    # Audit finding WP-0.6-F05: started from another folder, the setup reaches the doctor exactly as from the root
    # (on this VM the doctor then fails only its platform row).
    tree = make_tree(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    proc = subprocess.run(["bash", str(tree / SCRIPT_REL)], cwd=elsewhere, capture_output=True, text=True, timeout=900)
    assert "cannot read paths" not in proc.stderr, proc.stderr
    assert proc.returncode == 1 and "the doctor reported a problem (exit 1)" in proc.stderr, proc.stdout + proc.stderr
    assert f"--work-dir {tree}/data/raw/aqis_lab/work --out {tree}/data/raw/aqis_lab/doctor" in steps(proc.stdout)[5]
    reports, rows = doctor_rows(tree)
    assert len(reports) == 1 and rows["platform"]["status"] == "FAIL" and rows["cores"]["status"] == "PASS"
    assert list(elsewhere.iterdir()) == []
