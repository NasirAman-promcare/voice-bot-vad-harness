"""FR-0.0-12: aqis_lab/deploy/harness_provision.sh provisions the harness (system packages, .venv-harness,
corpus-v1 from git at its pinned commit, FireRedVAD weights) idempotently, only into ignored paths, and never
writes a token. It runs only on Linux x86_64, the one platform TEN VAD ships a native library for (owner
decision on audit finding F16).

Fast tests run the real script in a throwaway git repository whose assets config points at small local
sources (a corpus archive committed at a pinned commit and a local weights repository) and select the data
steps with --steps. The TEN VAD commit and pip check tests install a small local git package with pip into a
scratch virtual environment, offline. Slow tests provision this repository for real (AT-0.0-05)."""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

import pytest

from aqis_testutil import ROOT, git, hermetic_git_env

SCRIPT_SH = ROOT / "aqis_lab" / "deploy" / "harness_provision.sh"
SCRIPT_PY = ROOT / "aqis_lab" / "deploy" / "harness_provision.py"
WAV_A = b"RIFF" + b"\x00" * 60
WAV_B = b"RIFF" + b"\x01" * 60
MODEL = b"\x80\x02model-weights-for-a-test" * 40
CMVN = b"cmvn-stats-for-a-test\n"
REAL_CONFIG = json.loads((ROOT / "config" / "aqis_lab" / "harness_assets.json").read_text(encoding="utf-8"))
POINTER = (b"version https://git-lfs.github.com/spec/v1\n"
           b"oid sha256:" + hashlib.sha256(MODEL).hexdigest().encode() + b"\nsize " + str(len(MODEL)).encode() + b"\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest_bytes(names):
    entries = [{"clip_id": n, "clip_path": f"corpus/audio/{n}"} for n in names]
    return (json.dumps(entries, indent=1) + "\n").encode()


def corpus_archive(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def make_tree(tmp_path, *, model_blob=MODEL, tracked_manifest=None, corpus_sha=None, gitignore=None):
    tree = tmp_path / "tree"
    (tree / "aqis_lab" / "deploy").mkdir(parents=True)
    shutil.copy2(SCRIPT_SH, tree / "aqis_lab" / "deploy" / SCRIPT_SH.name)
    shutil.copy2(SCRIPT_PY, tree / "aqis_lab" / "deploy" / SCRIPT_PY.name)
    (tree / ".gitignore").write_text(
        (ROOT / ".gitignore").read_text(encoding="utf-8") if gitignore is None else gitignore, encoding="utf-8")
    manifest = manifest_bytes(["a.wav", "b.wav"])
    archive = corpus_archive({"corpus/audio/a.wav": WAV_A, "corpus/audio/b.wav": WAV_B,
                              "corpus/manifest.json": manifest, "corpus/build/recipe_log.json": b"{}\n"})
    (tree / "corpus").mkdir()
    (tree / "corpus" / "manifest.json").write_bytes(manifest if tracked_manifest is None else tracked_manifest)
    (tree / "corpus-v1.tar.gz").write_bytes(archive)
    git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", "tree with corpus")
    corpus_commit = git(tree, "rev-parse", "HEAD").strip()

    weights = tmp_path / "weights-src"
    (weights / "Stream-VAD").mkdir(parents=True)
    (weights / "Stream-VAD" / "model.pth.tar").write_bytes(model_blob)
    (weights / "Stream-VAD" / "cmvn.ark").write_bytes(CMVN)
    git(weights, "init", "-q")
    git(weights, "add", "-A")
    git(weights, "commit", "-q", "-m", "weights")
    weights_commit = git(weights, "rev-parse", "HEAD").strip()

    config = {
        "system_packages": [],
        "corpus": {"name": "corpus-v1", "commit": corpus_commit, "path": "corpus-v1.tar.gz",
                   "sha256": corpus_sha or sha(archive), "size": len(archive),
                   "manifest": "corpus/manifest.json", "audio_dir": "corpus/audio"},
        "firered": {"repo": str(weights), "commit": weights_commit, "subdir": "Stream-VAD",
                    "files": {"Stream-VAD/model.pth.tar": {"sha256": sha(MODEL), "size": len(MODEL)},
                              "Stream-VAD/cmvn.ark": {"sha256": sha(CMVN), "size": len(CMVN)}},
                    "link": "pretrained_models/FireRedVAD/Stream-VAD"},
        "harness_requirements": [], "extras_lock": "requirements/aqis_lab/harness-extras.txt",
        "vcs_lock": "requirements/aqis_lab/harness-vcs.txt",
        "ten_vad": {"distribution": "ten_vad", "commit": "0" * 40},
        "not_installed": [{"name": "torch", "reason": "decision R2-3"}],
        "import_check": [],
        "platform": REAL_CONFIG["platform"],
    }
    cfg = tmp_path / "assets.json"
    cfg.write_text(json.dumps(config, indent=1), encoding="utf-8")
    return tree, cfg


def run(tree, cfg, cache, *args, extra_env=None, timeout=600):
    env = hermetic_git_env({"AQIS_HARNESS_ASSETS": str(cfg), "AQIS_CACHE": str(cache), **(extra_env or {})})
    return subprocess.run(["bash", str(tree / "aqis_lab" / "deploy" / SCRIPT_SH.name), *args], cwd=tree,
                          capture_output=True, text=True, env=env, timeout=timeout)


def table(stdout):
    """{step: (result, detail)} from the PASS/FAIL table the script prints."""
    rows = {}
    for line in stdout.splitlines():
        m = re.fullmatch(r"\|\s*([a-z0-9-]+)\s*\|\s*(PASS|FAIL|INFO)\s*\|\s*(.*?)\s*\|", line.strip())
        if m:
            rows[m.group(1)] = (m.group(2), m.group(3))
    return rows


def downloads(stdout):
    m = re.search(r"^Downloads this run: (\d+)$", stdout, re.M)
    assert m, stdout[-2000:]
    return int(m.group(1))


DATA = ("--steps", "corpus,weights,verify")


def test_FR_0_0_12_places_data_only_in_ignored_paths(tmp_path):
    tree, cfg = make_tree(tmp_path)
    cache = tmp_path / "cache"
    proc = run(tree, cfg, cache, *DATA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = table(proc.stdout)
    assert rows["corpus"][0] == "PASS" and rows["weights"][0] == "PASS" and rows["git-status"][0] == "PASS"
    for name, data in (("a.wav", WAV_A), ("b.wav", WAV_B)):
        link = tree / "corpus" / "audio" / name
        assert link.is_symlink() and link.read_bytes() == data
        assert str(cache) in os.path.realpath(link)
    assert (tree / "corpus" / "audio").is_dir() and not (tree / "corpus" / "audio").is_symlink()
    weights = tree / "pretrained_models" / "FireRedVAD" / "Stream-VAD"
    assert weights.is_symlink() and (weights / "model.pth.tar").read_bytes() == MODEL
    assert git(tree, "status", "--porcelain") == ""
    assert (tree / "corpus" / "manifest.json").read_bytes() == manifest_bytes(["a.wav", "b.wav"])


def test_FR_0_0_12_second_data_run_downloads_nothing(tmp_path):
    tree, cfg = make_tree(tmp_path)
    cache = tmp_path / "cache"
    first = run(tree, cfg, cache, *DATA)
    assert first.returncode == 0 and downloads(first.stdout) >= 1, first.stdout
    second = run(tree, cfg, cache, *DATA)
    assert second.returncode == 0, second.stdout
    assert downloads(second.stdout) == 0
    assert git(tree, "status", "--porcelain") == ""


def test_FR_0_0_12_reads_corpus_at_pinned_commit(tmp_path):
    # Owner decision BLK-005 option 1: the archive comes from git at the pinned commit, not from the working tree.
    tree, cfg = make_tree(tmp_path)
    (tree / "corpus-v1.tar.gz").write_bytes(b"a later, different archive")
    git(tree, "commit", "-q", "-am", "archive replaced after the pinned commit")
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (tree / "corpus" / "audio" / "a.wav").read_bytes() == WAV_A
    config = json.loads(cfg.read_text(encoding="utf-8"))
    assert config["corpus"]["commit"][:12] in table(proc.stdout)["corpus"][1]


def test_FR_0_0_12_fails_on_asset_checksum_mismatch(tmp_path):
    tree, cfg = make_tree(tmp_path, corpus_sha="0" * 64)
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode != 0
    result, detail = table(proc.stdout)["corpus"]
    assert result == "FAIL" and "sha256" in detail
    assert not (tree / "corpus" / "audio").exists()


def test_FR_0_0_12_rejects_lfs_pointer_file(tmp_path):
    tree, cfg = make_tree(tmp_path, model_blob=POINTER)
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode != 0
    result, detail = table(proc.stdout)["weights"]
    assert result == "FAIL" and "pointer" in detail
    assert not (tree / "pretrained_models").exists()


def test_FR_0_0_12_manifest_mismatch_is_an_error(tmp_path):
    tree, cfg = make_tree(tmp_path, tracked_manifest=manifest_bytes(["a.wav"]))
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode != 0
    result, detail = table(proc.stdout)["corpus"]
    assert result == "FAIL" and "manifest" in detail


def test_FR_0_0_12_refuses_target_that_git_does_not_ignore(tmp_path):
    tree, cfg = make_tree(tmp_path, gitignore="__pycache__/\n")
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode != 0
    assert table(proc.stdout)["corpus"][0] == "FAIL" and "not ignored" in table(proc.stdout)["corpus"][1]
    assert table(proc.stdout)["weights"][0] == "FAIL" and "not ignored" in table(proc.stdout)["weights"][1]
    assert git(tree, "status", "--porcelain") == ""


def test_FR_0_0_12_never_writes_token(tmp_path):
    sentinel = "ghp_SENTINEL_value_that_must_not_be_written_0123456789"
    tree, cfg = make_tree(tmp_path)
    cache = tmp_path / "cache"
    proc = run(tree, cfg, cache, *DATA, extra_env={"GITHUB_TOKEN": sentinel})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert sentinel not in proc.stdout + proc.stderr
    for base in (tree, cache):
        for path in base.rglob("*"):
            if path.is_file() and not path.is_symlink():
                assert sentinel.encode() not in path.read_bytes(), path
    for source in (SCRIPT_SH, SCRIPT_PY):
        assert "GITHUB_TOKEN" not in source.read_text(encoding="utf-8")


def test_FR_0_0_12_rejects_unknown_step(tmp_path):
    tree, cfg = make_tree(tmp_path)
    proc = run(tree, cfg, tmp_path / "cache", "--steps", "corpus,bogus")
    assert proc.returncode == 2 and "bogus" in proc.stderr


def test_FR_0_0_12_fails_when_tree_was_dirty_before(tmp_path):
    # FR-0.0-12(f): provisioning must leave `git status --porcelain` empty; a tree that is already dirty is a
    # FAIL even though provisioning itself changed nothing (audit F12).
    tree, cfg = make_tree(tmp_path)
    (tree / "notes.txt").write_text("an untracked file\n", encoding="utf-8")
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    rows = table(proc.stdout)
    assert rows["corpus"][0] == "PASS" and rows["weights"][0] == "PASS"
    assert rows["git-status"][0] == "FAIL" and "?? notes.txt" in rows["git-status"][1]
    assert proc.stdout.splitlines()[-1] == "RESULT: FAIL"


def test_FR_0_0_12_fails_when_provisioning_dirties_tree(tmp_path):
    # A cache inside the working tree makes provisioning itself create untracked files (audit F12).
    tree, cfg = make_tree(tmp_path)
    proc = run(tree, cfg, tree / "cache-in-tree", *DATA)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    rows = table(proc.stdout)
    assert rows["corpus"][0] == "PASS" and rows["weights"][0] == "PASS"
    assert rows["git-status"][0] == "FAIL" and "changed during provisioning" in rows["git-status"][1]
    assert "?? cache-in-tree/" in rows["git-status"][1]
    assert proc.stdout.splitlines()[-1] == "RESULT: FAIL"


def test_FR_0_0_12_platform_pin_is_linux_x86_64():
    # Owner decision on audit F16: the harness and TEN VAD need Linux x86_64.
    pin = REAL_CONFIG["platform"]
    assert pin["system"] == "Linux" and pin["machines"] == ["x86_64"]
    assert "lib/Linux/x64/libten_vad.so" in pin["reason"] and "no Arm" in pin["reason"]
    assert REAL_CONFIG["ten_vad"]["commit"][:12] in pin["reason"]


def test_FR_0_0_12_fails_fast_on_machine_without_ten_vad_binary(tmp_path):
    # `setarch linux32` makes the kernel report i686: a real machine type TEN VAD has no library for, the same
    # situation as Arm (aarch64). Provisioning must stop before any step, download or file change.
    setarch = shutil.which("setarch")
    assert setarch, "setarch (util-linux) is needed for this test"
    tree, cfg = make_tree(tmp_path)
    cache = tmp_path / "cache"
    env = hermetic_git_env({"AQIS_HARNESS_ASSETS": str(cfg), "AQIS_CACHE": str(cache)})
    proc = subprocess.run([setarch, "linux32", "bash", str(tree / "aqis_lab" / "deploy" / SCRIPT_SH.name), *DATA],
                          cwd=tree, capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    rows = table(proc.stdout)
    assert list(rows) == ["platform"], rows
    result, detail = rows["platform"]
    assert result == "FAIL"
    assert "Linux i686" in detail and "x86_64" in detail and "no Arm" in detail
    assert downloads(proc.stdout) == 0 and proc.stdout.splitlines()[-1] == "RESULT: FAIL"
    assert not cache.exists() and not (tree / "corpus" / "audio").exists() and not (tree / "pretrained_models").exists()


def test_FR_0_0_12_rejects_config_missing_required_key(tmp_path):
    # A missing key is an error, never an empty default that turns into a PASS row (audit F21).
    tree, cfg = make_tree(tmp_path)
    full = json.loads(cfg.read_text(encoding="utf-8"))
    for key in ("system_packages", "import_check", "not_installed", "platform", "corpus", "firered", "ten_vad"):
        partial = {k: v for k, v in full.items() if k != key}
        cfg.write_text(json.dumps(partial), encoding="utf-8")
        proc = run(tree, cfg, tmp_path / "cache", "--steps", "verify")
        assert proc.returncode == 2, (key, proc.stdout, proc.stderr)
        assert proc.stderr.startswith("ERROR:") and repr(key) in proc.stderr, (key, proc.stderr)
        assert "RESULT:" not in proc.stdout


def test_FR_0_0_12_reports_lfs_pull_failure_detail(tmp_path):
    # When `git lfs pull` fails, its exit code and the source it failed on are in the FAIL row (audit F21).
    assert shutil.which("git-lfs"), "git-lfs is needed for this test (a system package the harness also needs)"
    tree, cfg = make_tree(tmp_path, model_blob=POINTER)
    proc = run(tree, cfg, tmp_path / "cache", *DATA)
    assert proc.returncode == 1
    result, detail = table(proc.stdout)["weights"]
    assert result == "FAIL" and "pointer" in detail
    assert re.search(r"git lfs pull failed \(exit [1-9]\d*\)", detail), detail
    assert str(tmp_path / "weights-src") in detail, detail


# ---- TEN VAD commit and pip check, against a real pip install (audit F13, F18) ---------------
BACKEND = """import base64, hashlib, zipfile
NAME, VERSION, REQUIRES = {name!r}, "1.0.6.8", {requires!r}
def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    info = NAME + "-" + VERSION + ".dist-info"
    meta = "Metadata-Version: 2.1\\nName: " + NAME + "\\nVersion: " + VERSION + "\\n"
    meta += "".join("Requires-Dist: " + r + "\\n" for r in REQUIRES)
    files = {{NAME + "/__init__.py": b"", info + "/METADATA": meta.encode(),
             info + "/WHEEL": b"Wheel-Version: 1.0\\nGenerator: aqis-test\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n"}}
    wheel = NAME + "-" + VERSION + "-py3-none-any.whl"
    with zipfile.ZipFile(wheel_directory + "/" + wheel, "w") as archive:
        record = []
        for path, data in files.items():
            archive.writestr(path, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            record.append(path + ",sha256=" + digest + "," + str(len(data)))
        record.append(info + "/RECORD,,")
        archive.writestr(info + "/RECORD", "\\n".join(record) + "\\n")
    return wheel
"""


def local_package(path, name, requires=()):
    """A git repository holding a pip-installable package (in-tree PEP 517 backend, so no download is needed).
    Returns the commits (first, second) of two different revisions."""
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text('[build-system]\nrequires = []\nbuild-backend = "backend"\n'
                                         'backend-path = ["."]\n', encoding="utf-8")
    (path / "backend.py").write_text(BACKEND.format(name=name, requires=list(requires)), encoding="utf-8")
    git(path, "init", "-q")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "first")
    first = git(path, "rev-parse", "HEAD").strip()
    (path / "README").write_text("second revision\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "second")
    return first, git(path, "rev-parse", "HEAD").strip()


def scratch_venv(path):
    subprocess.run([sys.executable, "-m", "venv", str(path)], check=True, capture_output=True, timeout=300)
    return path / "bin" / "python"


def pip_install(python, *args):
    proc = subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-input", "--disable-pip-version-check",
                           "-q", *args], capture_output=True, text=True, env=hermetic_git_env(), timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def load_provision_module():
    spec = importlib.util.spec_from_file_location("aqis_harness_provision_under_test", SCRIPT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_FR_0_0_12_rejects_ten_vad_at_other_commit(tmp_path):
    # BLK-004 option 1: provisioning verifies the commit pip recorded for the installed TEN VAD (PEP 610
    # direct_url.json) against the pin, and fails on any other commit or a non-git install.
    first, second = local_package(tmp_path / "ten-vad-src", "ten_vad")
    python = scratch_venv(tmp_path / "venv")
    pip_install(python, f"ten_vad @ git+file://{tmp_path / 'ten-vad-src'}@{first}")
    module = load_provision_module()
    tree, cfg = make_tree(tmp_path)
    config = json.loads(cfg.read_text(encoding="utf-8"))

    config["ten_vad"]["commit"] = first
    cfg.write_text(json.dumps(config), encoding="utf-8")
    provisioner = module.Provisioner(tree, cfg, tmp_path / "cache")
    provisioner.check_ten_vad(python)
    assert provisioner.rows == [("ten-vad", "PASS", f"ten_vad 1.0.6.8 at commit {first[:12]} (pinned)")]

    config["ten_vad"]["commit"] = second
    cfg.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(module.StepFailed) as wrong:
        module.Provisioner(tree, cfg, tmp_path / "cache").check_ten_vad(python)
    assert str(wrong.value) == f"ten_vad commit is {first}, pinned {second}"

    # Installed from a plain folder: pip records no git commit, which is not the pinned commit either.
    pip_install(python, "--force-reinstall", str(tmp_path / "ten-vad-src"))
    with pytest.raises(module.StepFailed) as plain:
        module.Provisioner(tree, cfg, tmp_path / "cache").check_ten_vad(python)
    assert str(plain.value) == f"ten_vad commit is None, pinned {second}"


def test_FR_0_0_12_reinstalls_when_pip_check_fails(tmp_path):
    # PLAN Round 2: the install is skipped only when the stamp matches AND `pip check` passes (audit F18).
    local_package(tmp_path / "pkg-src", "aqis_needs_dep", requires=["aqis-absent-dependency>=1"])
    python = scratch_venv(tmp_path / "venv")
    module = load_provision_module()
    tree, cfg = make_tree(tmp_path)
    provisioner = module.Provisioner(tree, cfg, tmp_path / "cache")
    stamp_file = tmp_path / "venv" / module.STAMP_NAME

    assert provisioner.reinstall_reason(python, "stamp-1") == "first install"
    stamp_file.write_text("stamp-0\n", encoding="utf-8")
    assert provisioner.reinstall_reason(python, "stamp-1") == "harness requirement files changed"
    stamp_file.write_text("stamp-1\n", encoding="utf-8")
    assert provisioner.reinstall_reason(python, "stamp-1") is None

    pip_install(python, "--no-deps", str(tmp_path / "pkg-src"))
    reason = provisioner.reinstall_reason(python, "stamp-1")
    assert reason is not None and reason.startswith("pip check failed")
    assert "aqis-absent-dependency" in reason


# ---- the real repository (AT-0.0-05, AT-0.0-06) ------------------------------------------
def run_real(timeout=3600):
    return subprocess.run(["bash", str(SCRIPT_SH)], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_0_12_provisions_harness_end_to_end():
    before = git(ROOT, "status", "--porcelain")
    proc = run_real()
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    rows = table(proc.stdout)
    for step in ("system", "python", "ten-vad", "imports", "corpus", "weights", "git-status"):
        assert rows[step][0] == "PASS", (step, rows.get(step))
    assert rows["torch"] == ("INFO", "not installed, decision R2-3")
    assert git(ROOT, "status", "--porcelain") == before


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_0_12_second_run_downloads_nothing_within_60s():
    first = run_real()
    assert first.returncode == 0, first.stdout[-4000:]
    before = git(ROOT, "status", "--porcelain")
    start = time.monotonic()
    second = run_real()
    elapsed = time.monotonic() - start
    assert second.returncode == 0, second.stdout[-4000:]
    assert downloads(second.stdout) == 0
    assert elapsed < 60, f"second run took {elapsed:.1f} s"
    assert git(ROOT, "status", "--porcelain") == before


# ---- pins and locks (FR-0.0-12 b and c) ---------------------------------------------------
def test_FR_0_0_12_harness_extras_lock_is_hash_pinned():
    from aqis_testutil import parse_lock
    lock = ROOT / "requirements" / "aqis_lab" / "harness-extras.txt"
    entries = parse_lock(lock.read_text(encoding="utf-8"))
    for required in ("pytest", "pytest-asyncio", "opuslib"):
        assert required in entries, required
    for name, entry in entries.items():
        assert entry["hashes"] and all(a == "sha256" and len(d) == 64 for a, d in entry["hashes"]), name
    header = lock.read_text(encoding="utf-8").splitlines()[1].lstrip("#").strip()
    assert header.startswith("uv pip compile requirements/aqis_lab/harness-extras.in --universal --python-version 3.13")
    assert header in (ROOT / "requirements" / "aqis_lab" / "harness-extras.in").read_text(encoding="utf-8")
    assert "git+" not in lock.read_text(encoding="utf-8"), "git requirements cannot be hash-checked (BLK-004)"


def test_FR_0_0_12_asset_pins_match_repository():
    config = json.loads((ROOT / "config" / "aqis_lab" / "harness_assets.json").read_text(encoding="utf-8"))
    corpus = config["corpus"]
    blob = subprocess.run(["git", "cat-file", "blob", f"{corpus['commit']}:{corpus['path']}"], cwd=ROOT,
                          capture_output=True, timeout=120, check=True).stdout
    assert len(blob) == corpus["size"] and sha(blob) == corpus["sha256"]
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        shipped = tar.extractfile(corpus["manifest"]).read()
    assert shipped == (ROOT / corpus["manifest"]).read_bytes()
    vcs = [line for line in (ROOT / "requirements" / "aqis_lab" / "harness-vcs.txt").read_text(encoding="utf-8").splitlines()
           if line.strip() and not line.startswith("#")]
    assert vcs == [f"ten_vad @ git+https://github.com/TEN-framework/ten-vad.git@{config['ten_vad']['commit']}"]
    assert config["ten_vad"]["commit"] == "22a3bcd4509d0faaa8eef4881e8af5f39c178950"
    assert config["not_installed"] == [{"name": "torch", "reason": "decision R2-3"}]
    for pkg in ("git-lfs", "libc++1", "libopus0"):
        assert pkg in config["system_packages"]
