"""Provision the existing VAD harness: system packages, .venv-harness, corpus and FireRedVAD weights.

Run through aqis_lab/deploy/harness_provision.sh (the first step everywhere the harness runs:
cloud VM, CI, Colab, Oracle). Standard library only; runs on any Python 3.10+ before a venv exists.

CAPABILITIES:
  CAP-ENV-003: provisions the harness idempotently: apt packages, .venv-harness on the Colab Python with the harness's own install command plus the hash-checked extras and the commit-pinned TEN VAD, the corpus from git at its pinned commit and the FireRedVAD weights into a cache outside the tree, verified by SHA-256 (no Git LFS pointer files), exposed only through git-ignored paths; prints a PASS/FAIL table and exits 1 on any failure [tests: test_FR_0_0_12_places_data_only_in_ignored_paths, test_FR_0_0_12_second_data_run_downloads_nothing, test_FR_0_0_12_reads_corpus_at_pinned_commit, test_FR_0_0_12_fails_on_asset_checksum_mismatch, test_FR_0_0_12_rejects_lfs_pointer_file, test_FR_0_0_12_manifest_mismatch_is_an_error, test_FR_0_0_12_refuses_target_that_git_does_not_ignore, test_FR_0_0_12_never_writes_token, test_FR_0_0_12_rejects_unknown_step, test_FR_0_0_12_provisions_harness_end_to_end, test_FR_0_0_12_second_run_downloads_nothing_within_60s]
INPUTS AND OUTPUTS: config/aqis_lab/harness_assets.json (or $AQIS_HARNESS_ASSETS), docs/environment/colab_probe.txt,
  the harness requirement files; writes .venv-harness/, ${AQIS_CACHE:-$HOME/.cache/aqis}, symlinks under
  corpus/audio/ and pretrained_models/FireRedVAD/ (both git-ignored). Options: --steps system,python,corpus,weights,verify.
CONTRACTS: harness_assets.json keys as in config/aqis_lab/harness_assets.json.
INVARIANTS:
  - Never creates tracked or un-ignored files: every target is checked with git check-ignore first, and
    git status --porcelain is compared before and after.
  - Never reads, writes or logs a GitHub token; the corpus comes from local git objects, not the network.
  - Every network action is counted and reported ("Downloads this run"); a repeat run with nothing changed makes none.
  - Existing user files are never overwritten: an occupied target is a FAIL.
NOT IN SCOPE:
  - torch (owner decision R2-3), GPU packages, running the harness tests (CI job harness-regression does).
CHANGE LOG:
  2026-09-25 WP-0.0 round 2 FR-0.0-12 created.
  2026-09-25 WP-0.0 round 2 BLK-005 option 1: corpus pinned to a commit (the tag lacks the archive).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEPS = ("system", "python", "corpus", "weights", "verify")
PROBE_REL = "docs/environment/colab_probe.txt"
LFS_POINTER_PREFIX = b"version https://git-lfs"
STAMP_NAME = ".aqis-harness-stamp"


class StepFailed(Exception):
    """A provisioning step could not complete; the message is shown in the report."""


class Provisioner:
    def __init__(self, root, config_path, cache):
        self.root = Path(root)
        self.cache = Path(cache)
        self.config_path = Path(config_path)
        try:
            self.cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StepFailed(f"cannot read assets config {self.config_path}: {exc}") from exc
        self.rows = []
        self.downloads = 0

    # -- helpers ---------------------------------------------------------------------------
    def row(self, step, result, detail):
        self.rows.append((step, result, detail.replace("|", "/")))
        print(f"[{result}] {step}: {detail}", flush=True)

    def run(self, cmd, *, network=False, cwd=None, env=None, check=True, timeout=3600):
        if network:
            self.downloads += 1
            print(f"DOWNLOAD: {' '.join(str(c) for c in cmd)}", flush=True)
        try:
            proc = subprocess.run([str(c) for c in cmd], cwd=cwd or self.root, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StepFailed(f"cannot run {cmd[0]}: {exc}") from exc
        if check and proc.returncode != 0:
            tail = " / ".join((proc.stderr or proc.stdout).strip().splitlines()[-3:])
            raise StepFailed(f"{Path(str(cmd[0])).name} {' '.join(str(c) for c in cmd[1:3])} failed "
                             f"(exit {proc.returncode}): {tail}")
        return proc

    def git(self, *args, cwd=None, network=False, check=True, env=None):
        return self.run(["git", *args], cwd=cwd, network=network, check=check, env=env)

    def ignored(self, rel):
        return self.git("check-ignore", "-q", "--no-index", rel, check=False).returncode == 0

    @staticmethod
    def sha256_file(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def status(self):
        return self.git("status", "--porcelain", "--untracked-files=all").stdout

    # -- step: system packages -------------------------------------------------------------
    def step_system(self):
        wanted = list(self.cfg.get("system_packages", []))
        if not wanted:
            self.row("system", "PASS", "no system packages requested")
            return
        if shutil.which("dpkg-query") is None or shutil.which("apt-get") is None:
            raise StepFailed("dpkg-query and apt-get are required (Debian or Ubuntu); install "
                             + ", ".join(wanted) + " by hand")
        missing = []
        for pkg in wanted:
            proc = self.run(["dpkg-query", "-W", "-f=${Status}", pkg], check=False)
            if proc.returncode != 0 or "install ok installed" not in proc.stdout:
                missing.append(pkg)
        if not missing:
            self.row("system", "PASS", "already installed: " + ", ".join(wanted))
            return
        prefix = []
        if os.geteuid() != 0:
            if shutil.which("sudo") is None:
                raise StepFailed("not root and sudo is not available; install " + ", ".join(missing) + " as root")
            prefix = ["sudo", "-n"]
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        self.run([*prefix, "apt-get", "update", "-y"], network=True, env=env)
        self.run([*prefix, "apt-get", "install", "-y", *missing], network=True, env=env)
        still = [p for p in missing
                 if "install ok installed" not in self.run(["dpkg-query", "-W", "-f=${Status}", p], check=False).stdout]
        if still:
            raise StepFailed("apt-get finished but these are not installed: " + ", ".join(still))
        self.row("system", "PASS", "installed " + ", ".join(missing) + "; already present: "
                 + (", ".join(p for p in wanted if p not in missing) or "none"))

    # -- step: python environment ----------------------------------------------------------
    def probe_python(self):
        probe = self.root / PROBE_REL
        try:
            text = probe.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            raise StepFailed(f"{PROBE_REL} is missing or unreadable: {exc}") from exc
        found = set()
        for line in text.splitlines():
            m = re.match(r"\s*(?:Python Version:\s*|Python\s+)(\d+)\.(\d+)", line)
            if m:
                found.add(f"{m.group(1)}.{m.group(2)}")
        if len(found) != 1:
            raise StepFailed(f"{PROBE_REL} must name exactly one Python version, found {sorted(found) or 'none'}")
        return found.pop()

    def venv_python_version(self, python):
        if not python.exists():
            return None
        proc = self.run([python, "-I", "-B", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], check=False)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def stamp_value(self, version):
        digest = hashlib.sha256(f"python={version}\n".encode())
        files = [*self.cfg["harness_requirements"], self.cfg["extras_lock"], self.cfg["vcs_lock"]]
        for rel in files:
            try:
                digest.update(rel.encode() + b"\0" + (self.root / rel).read_bytes() + b"\0")
            except OSError as exc:
                raise StepFailed(f"cannot read {rel}: {exc}") from exc
        return digest.hexdigest()

    def step_python(self):
        version = self.probe_python()
        uv = shutil.which("uv")
        if uv is None:
            raise StepFailed("uv not found on PATH; install uv 0.8.17 and re-run")
        venv = self.root / ".venv-harness"
        python = venv / "bin" / "python"
        current = self.venv_python_version(python)
        if current != version:
            self.run([uv, "venv", "--seed", "--clear", "--python", version, venv])
            if self.venv_python_version(python) != version:
                raise StepFailed(f".venv-harness does not run Python {version}")
        stamp_file = venv / STAMP_NAME
        stamp = self.stamp_value(version)
        try:
            previous = stamp_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            previous = ""
        except OSError as exc:
            raise StepFailed(f"cannot read {stamp_file}: {exc}") from exc
        if previous == stamp:
            self.row("python", "PASS", f".venv-harness Python {version}; requirements unchanged, nothing installed")
        else:
            self.run([python, "scripts/run_phase.py", "install", "all"], network=True)
            self.run([python, "-m", "pip", "install", "--no-input", "--require-hashes", "-r",
                      self.cfg["extras_lock"]], network=True)
            self.run([python, "-m", "pip", "install", "--no-input", "--no-deps", "--force-reinstall", "-r",
                      self.cfg["vcs_lock"]], network=True)
            stamp_file.write_text(stamp + "\n", encoding="utf-8")
            self.row("python", "PASS", f".venv-harness Python {version}; installed run_phase.py install all, "
                     f"{self.cfg['extras_lock']} (hash-checked), {self.cfg['vcs_lock']}")
        self.check_ten_vad(python)
        self.check_imports(python)
        for item in self.cfg.get("not_installed", []):
            self.row(item["name"], "INFO", f"not installed, {item['reason']}")

    def check_ten_vad(self, python):
        pin = self.cfg["ten_vad"]
        code = ("import importlib.metadata as m, json, sys\n"
                "d = m.distribution(sys.argv[1])\n"
                "print(json.dumps({'version': d.version, 'direct_url': json.loads(d.read_text('direct_url.json') or '{}')}))")
        proc = self.run([python, "-I", "-B", "-c", code, pin["distribution"]], check=False)
        if proc.returncode != 0:
            raise StepFailed(f"{pin['distribution']} is not installed in .venv-harness")
        info = json.loads(proc.stdout)
        commit = (info["direct_url"].get("vcs_info") or {}).get("commit_id")
        if commit != pin["commit"]:
            raise StepFailed(f"{pin['distribution']} commit is {commit}, pinned {pin['commit']}")
        self.row("ten-vad", "PASS", f"{pin['distribution']} {info['version']} at commit {commit[:12]} (pinned)")

    def check_imports(self, python):
        modules = list(self.cfg.get("import_check", []))
        code = ("import importlib, sys\n"
                "for name in sys.argv[1:]:\n"
                "    importlib.import_module(name)\n"
                "if 'ten_vad' in sys.argv[1:]:\n"
                "    import ten_vad\n"
                "    ten_vad.TenVad(256, 0.5)\n"
                "print('imports ok')")
        proc = self.run([python, "-B", "-c", code, *modules], check=False, cwd=self.root)
        if proc.returncode != 0:
            tail = " / ".join(proc.stderr.strip().splitlines()[-2:])
            raise StepFailed(f"import check failed: {tail}")
        self.row("imports", "PASS", "imported " + ", ".join(modules) + ("; TenVad native library loaded"
                                                                        if "ten_vad" in modules else ""))

    # -- step: corpus ----------------------------------------------------------------------
    def require_ignored(self, rel):
        if not self.ignored(rel):
            raise StepFailed(f"{rel} is not ignored by git; placing data there would create un-ignored files "
                             "(owner approval needed for .gitignore)")

    def step_corpus(self):
        c = self.cfg["corpus"]
        audio_rel = c["audio_dir"]
        self.require_ignored(f"{audio_rel}/probe.wav")
        commit = c["commit"]
        if self.git("cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
            self.git("fetch", "--no-tags", "origin", commit, network=True)
            if self.git("cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
                raise StepFailed(f"pinned commit {commit} is not available in this clone, even after fetching it")
        base = self.cache / "corpus" / c["sha256"]
        archive = base / Path(c["path"]).name
        if not (archive.is_file() and self.sha256_file(archive) == c["sha256"]):
            base.mkdir(parents=True, exist_ok=True)
            part = archive.with_name(archive.name + ".part")
            with open(part, "wb") as handle:
                proc = subprocess.run(["git", "cat-file", "blob", f"{commit}:{c['path']}"], cwd=self.root,
                                      stdout=handle, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                part.unlink()
                raise StepFailed(f"cannot read {c['path']} at commit {commit[:12]}: {proc.stderr.decode(errors='replace').strip()}")
            got = self.sha256_file(part)
            if got != c["sha256"]:
                part.unlink()
                raise StepFailed(f"{c['path']} at commit {commit[:12]} has sha256 {got}, pinned {c['sha256']}")
            part.replace(archive)
        extracted = base / "extracted"
        marker = extracted / ".complete"
        if not marker.is_file():
            if extracted.exists():
                shutil.rmtree(extracted)
            extracted.mkdir(parents=True)
            self.safe_extract(archive, extracted)
            marker.write_text(c["sha256"] + "\n", encoding="utf-8")
        tracked = self.root / c["manifest"]
        shipped = extracted / c["manifest"]
        if not shipped.is_file() or tracked.read_bytes() != shipped.read_bytes():
            raise StepFailed(f"the archive's {c['manifest']} differs from the tracked {c['manifest']}; not placing data")
        source_audio = extracted / audio_rel
        target_audio = self.root / audio_rel
        if target_audio.is_symlink() or (target_audio.exists() and not target_audio.is_dir()):
            raise StepFailed(f"{audio_rel} exists and is not a real directory; not touching it")
        clips = sorted(p for p in source_audio.iterdir() if p.is_file())
        target_audio.mkdir(parents=True, exist_ok=True)
        linked = 0
        for clip in clips:
            link = target_audio / clip.name
            if link.is_symlink() and os.readlink(link) == str(clip):
                continue
            if link.is_symlink() or link.exists():
                if link.is_file() and self.sha256_file(link) == self.sha256_file(clip):
                    continue  # the same clip is already present as a regular file
                raise StepFailed(f"{audio_rel}/{clip.name} is occupied by different content; not overwriting it")
            link.symlink_to(clip)
            linked += 1
        entries = json.loads(tracked.read_text(encoding="utf-8"))
        missing = [e["clip_path"] for e in entries if not (self.root / e["clip_path"]).is_file()]
        if missing:
            raise StepFailed(f"{len(missing)} manifest clips still missing, first {missing[0]}")
        self.row("corpus", "PASS", f"{c['name']} from git at commit {commit[:12]}, sha256 {c['sha256'][:12]} verified; "
                 f"{len(entries)} manifest clips available under {audio_rel}/ ({linked} links created)")

    @staticmethod
    def safe_extract(archive, dest):
        dest = dest.resolve()
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                target = (dest / member.name).resolve()
                if dest not in target.parents and target != dest:
                    raise StepFailed(f"archive member escapes the cache: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise StepFailed(f"archive member is not a regular file or folder: {member.name}")
            for member in tar.getmembers():
                target = dest / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tar.extractfile(member)
                with open(target, "wb") as handle:
                    shutil.copyfileobj(source, handle)

    # -- step: weights ---------------------------------------------------------------------
    def weights_ok(self, repo, files):
        problems = []
        for rel, pin in files.items():
            path = repo / rel
            if not path.is_file():
                problems.append(f"{rel} missing")
                continue
            with open(path, "rb") as handle:
                head = handle.read(len(LFS_POINTER_PREFIX))
            if head == LFS_POINTER_PREFIX:
                problems.append(f"{rel} is a Git LFS pointer, not content")
                continue
            got = self.sha256_file(path)
            if got != pin["sha256"]:
                problems.append(f"{rel} has sha256 {got}, pinned {pin['sha256']}")
        return problems

    def step_weights(self):
        w = self.cfg["firered"]
        link_rel = w["link"]
        self.require_ignored(link_rel)
        repo = self.cache / "firered" / w["commit"] / "repo"
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
        if self.weights_ok(repo, w["files"]):
            if repo.exists():
                shutil.rmtree(repo)
            repo.parent.mkdir(parents=True, exist_ok=True)
            self.git("clone", "--quiet", "--no-checkout", w["repo"], repo, cwd=repo.parent, network=True, env=env)
            self.git("checkout", "--quiet", w["commit"], cwd=repo, env=env)
            pointers = [rel for rel in w["files"] if (repo / rel).is_file()
                        and (repo / rel).read_bytes()[:len(LFS_POINTER_PREFIX)] == LFS_POINTER_PREFIX]
            if pointers:
                if self.run(["git", "lfs", "version"], check=False).returncode != 0:
                    raise StepFailed("git-lfs is not installed, so these stay Git LFS pointer files: "
                                     + ", ".join(pointers))
                include = ",".join(pointers)
                self.git("lfs", "pull", "--include", include, cwd=repo, network=True, check=False)
            problems = self.weights_ok(repo, w["files"])
            if problems:
                raise StepFailed("; ".join(problems))
        link = self.root / link_rel
        target = repo / w["subdir"]
        if link.is_symlink():
            if os.readlink(link) != str(target):
                raise StepFailed(f"{link_rel} already points elsewhere ({os.readlink(link)}); not changing it")
        elif link.exists():
            raise StepFailed(f"{link_rel} is occupied by a real file or folder; not overwriting it")
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
        self.row("weights", "PASS", f"{w['repo']} at {w['commit'][:12]}: " + ", ".join(w["files"])
                 + f" sha256 verified, no LFS pointers; available at {link_rel}")

    # -- step: verify ----------------------------------------------------------------------
    def step_verify(self, status_before):
        after = self.status()
        if after != status_before:
            raise StepFailed("git status changed during provisioning: " + " / ".join(
                sorted(set(after.splitlines()) - set(status_before.splitlines()))[:5]))
        if after.strip():
            raise StepFailed("git status --porcelain is not empty (it was not empty before provisioning either): "
                             + " / ".join(after.splitlines()[:5]))
        self.row("git-status", "PASS", "git status --porcelain is empty")

    # -- driver ----------------------------------------------------------------------------
    def provision(self, steps):
        status_before = self.status()
        failed = False
        for step in STEPS:
            if step not in steps:
                continue
            try:
                if step == "verify":
                    self.step_verify(status_before)
                else:
                    getattr(self, f"step_{step}")()
            except (StepFailed, OSError, ValueError, KeyError, tarfile.TarError) as exc:
                failed = True
                name = {"python": "python", "verify": "git-status"}.get(step, step)
                self.row(name, "FAIL", f"{type(exc).__name__}: {exc}" if not isinstance(exc, StepFailed) else str(exc))
        print()
        print("| Step | Result | Detail |")
        print("| --- | --- | --- |")
        for step, result, detail in self.rows:
            print(f"| {step} | {result} | {detail} |")
        print(f"Downloads this run: {self.downloads}")
        print("RESULT: " + ("FAIL" if failed else "PASS"))
        return 1 if failed else 0


def parse_steps(text):
    steps = [s.strip() for s in text.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEPS]
    if unknown or not steps:
        raise argparse.ArgumentTypeError(f"unknown step(s) {', '.join(unknown) or '(none given)'}; "
                                         f"choose from {', '.join(STEPS)}")
    return steps


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bash aqis_lab/deploy/harness_provision.sh",
                                     description="Provision the VAD harness (WP-0.0 FR-0.0-12).")
    parser.add_argument("--steps", type=parse_steps, default=list(STEPS),
                        help="comma-separated subset of: " + ", ".join(STEPS))
    args = parser.parse_args(argv)
    config = os.environ.get("AQIS_HARNESS_ASSETS") or str(ROOT / "config" / "aqis_lab" / "harness_assets.json")
    cache = os.environ.get("AQIS_CACHE") or str(Path.home() / ".cache" / "aqis")
    try:
        provisioner = Provisioner(ROOT, config, cache)
    except StepFailed as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return provisioner.provision(args.steps)


if __name__ == "__main__":
    sys.exit(main())
