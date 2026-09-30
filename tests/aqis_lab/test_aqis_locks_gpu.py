"""WP-0.7 locks and installs: the CPU lock's approved source build (FR-0.7-02, owner decision question 2 (a)) and
the GPU extras lock phase0-gpu.txt with `dev_bootstrap.sh --gpu` (FR-0.7-03, questions 3 to 5).

The bootstrap tests copy the real script into a throwaway tree, so the repository's own .venv is never touched.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import pytest

from aqis_lab import doctor, locks
from aqis_testutil import BOOTSTRAP, LOCK, PROBE, ROOT, normalise, parse_lock

PROBE_REL = "docs/environment/colab_probe.txt"


def make_tree(tmp_path, lock_text=None, gpu_lock_text=None):
    tree = tmp_path / "tree"
    (tree / "aqis_lab" / "deploy").mkdir(parents=True)
    shutil.copy2(BOOTSTRAP, tree / "aqis_lab" / "deploy" / "dev_bootstrap.sh")
    locks = tree / "requirements" / "aqis_lab"
    locks.mkdir(parents=True)
    (locks / "phase0.txt").write_text(LOCK.read_text(encoding="utf-8") if lock_text is None else lock_text,
                                      encoding="utf-8")
    if gpu_lock_text is not None:
        (locks / "phase0-gpu.txt").write_text(gpu_lock_text, encoding="utf-8")
    (tree / PROBE_REL).parent.mkdir(parents=True)
    shutil.copy2(PROBE, tree / PROBE_REL)
    return tree


def bootstrap(tree, *args, env=None, timeout=900):
    return subprocess.run(["bash", str(tree / "aqis_lab" / "deploy" / "dev_bootstrap.sh"), *args], cwd=tree,
                          capture_output=True, text=True, env=env, timeout=timeout)


def lock_block(name):
    """The pin of `name` in the real lock, with its hashes, as lock text."""
    entry = parse_lock()[name]
    hashes = " \\\n".join(f"    --hash={algo}:{digest}" for algo, digest in entry["hashes"])
    return f"{name}=={entry['version']} \\\n{hashes}\n"


def pypi_file(name, version, packagetype, dest):
    """Download the one PyPI file of this type (sdist or a py3-none-any wheel) and check it against the lock."""
    info = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60))
    files = [f for f in info["urls"] if f["packagetype"] == packagetype
             and (packagetype == "sdist" or f["filename"].endswith("-py3-none-any.whl"))]
    assert len(files) == 1, [f["filename"] for f in info["urls"]]
    data = urllib.request.urlopen(files[0]["url"], timeout=300).read()
    assert ("sha256", hashlib.sha256(data).hexdigest()) in parse_lock()[normalise(name)]["hashes"]
    path = Path(dest) / files[0]["filename"]
    path.write_bytes(data)
    return path


def refusing_setuptools_wheel(folder, version):
    """A real wheel named setuptools whose import fails: any build that uses it instead of the pin fails loudly."""
    dist = f"setuptools-{version}.dist-info"
    files = {"setuptools/__init__.py": b"raise ImportError('this setuptools is not the pinned one')\n",
             f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: setuptools\nVersion: {version}\n".encode(),
             f"{dist}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    record = "".join(f"{k},sha256={base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode()},"
                     f"{len(v)}\n" for k, v in files.items()) + f"{dist}/RECORD,,\n"
    path = Path(folder) / f"setuptools-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
        z.writestr(f"{dist}/RECORD", record)
    return path


def test_FR_0_7_02_lock_pins_vosk_webrtcvad_and_the_srt_build_tool():
    entries = parse_lock()
    assert entries["vosk"]["version"] == "0.3.45"
    for name in ("webrtcvad-wheels", "srt", "setuptools", "requests", "tqdm", "websockets"):
        assert name in entries, name
    assert int(entries["packaging"]["version"].split(".")[0]) < 25, "question 3 (a): packaging<25"


def test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    syncs = [line for line in text.splitlines() if '"$UV" pip sync' in line]
    assert syncs and all('--require-hashes --strict --build-constraints "$LOCK"' in line for line in syncs), syncs


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_02_source_build_uses_only_the_locked_setuptools(tmp_path):
    # A local index holds the real srt source archive, the real pinned setuptools wheel and a newer "setuptools"
    # that refuses to import. uv prefers the newest build tool, so only a build bound to the lock's pin succeeds.
    links = tmp_path / "links"
    links.mkdir()
    pypi_file("srt", parse_lock()["srt"]["version"], "sdist", links)
    pypi_file("setuptools", parse_lock()["setuptools"]["version"], "bdist_wheel", links)
    refusing_setuptools_wheel(links, "999.0.0")
    lock = lock_block("srt") + lock_block("setuptools")
    env = dict(os.environ, UV_NO_INDEX="1", UV_FIND_LINKS=str(links), UV_CACHE_DIR=str(tmp_path / "uv-cache"))
    tree = make_tree(tmp_path, lock_text=lock)
    proc = bootstrap(tree, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    check = subprocess.run([str(tree / ".venv" / "bin" / "python"), "-c",
                            "import srt, importlib.metadata as m; print(m.version('srt'))"],
                           capture_output=True, text=True, timeout=120)
    assert check.stdout.strip() == parse_lock()["srt"]["version"], check.stderr
    # Control: the same install without the lock as build constraint picks the refusing setuptools and fails.
    control = tmp_path / "control"
    subprocess.run(["uv", "venv", "--quiet", "--python", str(tree / ".venv" / "bin" / "python"), str(control)],
                   check=True, capture_output=True, env=env, timeout=300)
    (tmp_path / "lock.txt").write_text(lock, encoding="utf-8")
    env_fresh = dict(env, UV_CACHE_DIR=str(tmp_path / "uv-cache-control"))
    unbound = subprocess.run(["uv", "pip", "sync", "--python", str(control / "bin" / "python"), "--require-hashes",
                              "--strict", str(tmp_path / "lock.txt")],
                             capture_output=True, text=True, env=env_fresh, timeout=600)
    assert unbound.returncode != 0 and "not the pinned one" in unbound.stderr, unbound.stderr


def test_FR_0_7_02_bootstrap_rejects_unknown_option(tmp_path):
    tree = make_tree(tmp_path)
    proc = bootstrap(tree, "--cpu")
    assert proc.returncode == 1 and "ERROR: unknown option '--cpu'" in proc.stderr
    assert "[--gpu]" in proc.stderr and not (tree / ".venv").exists()


def test_FR_0_7_03_bootstrap_gpu_needs_the_gpu_lock(tmp_path):
    tree = make_tree(tmp_path)
    proc = bootstrap(tree, "--gpu")
    assert proc.returncode == 1 and "requirements/aqis_lab/phase0-gpu.txt is missing (needed by --gpu)" in proc.stderr
    assert not (tree / ".venv").exists()


# --- The GPU extras lock (FR-0.7-03) and which lock set is installed (aqis_lab/locks.py) ---

GPU_LOCK = LOCK.parent / "phase0-gpu.txt"
GPU_IN = LOCK.parent / "phase0-gpu.in"


def gpu_entries():
    return parse_lock(GPU_LOCK.read_text(encoding="utf-8"))


def test_FR_0_7_03_gpu_lock_is_hashed_and_layers_on_cpu_lock():
    gpu, cpu = gpu_entries(), parse_lock()
    assert gpu["nemo-toolkit"]["version"] == "3.0.0" and "torch" in gpu            # owner decision, questions 4, 5
    for name, entry in gpu.items():
        assert entry["hashes"] and all(a == "sha256" and len(d) == 64 for a, d in entry["hashes"]), name
    shared = sorted(set(gpu) & set(cpu))
    assert shared, "NeMo shares packages with the CPU lock (numpy, packaging, setuptools, ...)"
    assert [n for n in shared if gpu[n]["version"] != cpu[n]["version"]] == []
    command = GPU_LOCK.read_text(encoding="utf-8").splitlines()[1].lstrip("# ").strip()
    assert command == ("uv pip compile requirements/aqis_lab/phase0-gpu.in -c requirements/aqis_lab/phase0.txt "
                       "--python-version 3.13 --python-platform x86_64-manylinux_2_28 --generate-hashes "
                       "--output-file requirements/aqis_lab/phase0-gpu.txt")
    assert command in GPU_IN.read_text(encoding="utf-8")


def test_FR_0_7_03_gpu_lock_header_binds_cpu_lock_sha256():
    lines = [l for l in GPU_IN.read_text(encoding="utf-8").splitlines() if l.startswith("# compiled-against:")]
    assert lines == [f"# compiled-against: requirements/aqis_lab/phase0.txt sha256 "
                     f"{hashlib.sha256(LOCK.read_bytes()).hexdigest()}"]


@pytest.mark.network
def test_FR_0_7_03_gpu_lock_has_x86_64_wheels_except_antlr4(tmp_path):
    for name, entry in gpu_entries().items():
        (tmp_path / "one.txt").write_text(f"{name}=={entry['version']}\n", encoding="utf-8")
        proc = subprocess.run(["uv", "pip", "compile", str(tmp_path / "one.txt"), "--no-deps", "--only-binary", ":all:",
                               "--python-platform", "x86_64-manylinux_2_28", "--python-version", "3.13",
                               "--no-header", "--quiet", "-o", str(tmp_path / "o.txt")],
                              capture_output=True, text=True, timeout=300)
        assert (proc.returncode == 0) == (name != "antlr4-python3-runtime"), (name, proc.stderr)


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_03_gpu_lock_installs_with_cpu_lock(tmp_path):
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", "--quiet", "--python", "3.13", str(venv)], check=True, capture_output=True,
                   timeout=300)
    proc = subprocess.run(["uv", "pip", "sync", "--dry-run", "--python", str(venv / "bin" / "python"),
                           "--require-hashes", "--strict", "--build-constraints", str(LOCK), str(LOCK),
                           str(GPU_LOCK)], capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "nemo-toolkit==3.0.0" in proc.stdout + proc.stderr


def lock_tree(tmp_path, cpu_text, gpu_text=None):
    tree = tmp_path / "locks-tree"
    for rel in ("docs/environment/colab_probe.txt", "config/aqis_lab/doctor.yaml"):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tree / rel)
    (tree / "requirements" / "aqis_lab").mkdir(parents=True)
    (tree / "requirements" / "aqis_lab" / "phase0.txt").write_text(cpu_text, encoding="utf-8")
    if gpu_text is not None:
        (tree / "requirements" / "aqis_lab" / "phase0-gpu.txt").write_text(gpu_text, encoding="utf-8")
    return tree


def split_lock(name):
    """(the real CPU lock without `name`, the block of `name` alone)."""
    text = LOCK.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text)
    rest = [b for b in blocks if b.split("==", 1)[0].strip() != name]
    one = [b for b in blocks if b.split("==", 1)[0].strip() == name]
    assert len(one) == 1
    return "\n".join(rest) + "\n", one[0] + "\n"


def test_FR_0_7_03_installed_lock_is_the_cpu_lock_here():
    assert locks.installed_lock() == "requirements/aqis_lab/phase0.txt"


def test_FR_0_7_03_installed_lock_names_the_gpu_lock_when_extras_are_installed(tmp_path):
    # This environment equals CPU lock + GPU lock when "srt" is moved from one file to the other.
    cpu, extra = split_lock("srt")
    tree = lock_tree(tmp_path, cpu, extra)
    assert locks.installed_lock(tree) == "requirements/aqis_lab/phase0-gpu.txt"
    with pytest.raises(locks.LockError, match="srt"):
        locks.installed_lock(lock_tree(tmp_path / "no-gpu", cpu))


def test_FR_0_7_03_doctor_lock_row_names_the_lock_set(tmp_path):
    cpu, extra = split_lock("srt")
    row = {c.name: c for c in doctor.run_doctor("cloud", repo_root=lock_tree(tmp_path, cpu, extra)).checks}["lock"]
    assert row.status == "PASS" and "phase0.txt + requirements/aqis_lab/phase0-gpu.txt" in row.detail
    row = {c.name: c for c in doctor.run_doctor("cloud", repo_root=lock_tree(tmp_path / "cpu", cpu)).checks}["lock"]
    assert row.status == "FAIL" and "srt" in row.detail and "not in the lock" in row.detail
    real = {c.name: c for c in doctor.run_doctor("cloud", repo_root=ROOT).checks}["lock"]
    assert real.status == "PASS" and real.detail == "installed packages equal requirements/aqis_lab/phase0.txt"
