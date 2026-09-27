"""FR-0.0-01: `python -m aqis_lab version` prints package version, short commit (+dirty) and Python version."""
import ast
import platform
import re
import shutil
import subprocess
import sys

from aqis_testutil import ROOT, git, hermetic_git_env

LINE_RE = re.compile(r"aqis_lab (\S+) commit=([0-9a-f]{4,40})(\+dirty)? python=(\d+\.\d+\.\d+\S*)")


def package_version_from_source(root):
    tree = ast.parse((root / "aqis_lab" / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "__version__" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("__version__ not assigned in aqis_lab/__init__.py")


def run_version(cwd, env=None):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "version"], cwd=cwd, capture_output=True,
                          text=True, env=env or hermetic_git_env(), timeout=120)


def make_copy_repo(tmp_path, init_git=True):
    repo = tmp_path / "copy"
    repo.mkdir()
    shutil.copytree(ROOT / "aqis_lab", repo / "aqis_lab", ignore=shutil.ignore_patterns("__pycache__"))
    (repo / ".gitignore").write_text("*.log\n__pycache__/\n", encoding="utf-8")
    if init_git:
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "fixture")
    return repo


def test_FR_0_0_01_version_prints_package_commit_python():
    proc = run_version(ROOT)
    assert proc.returncode == 0, proc.stderr
    m = LINE_RE.fullmatch(proc.stdout.strip())
    assert m, proc.stdout
    expected_commit = git(ROOT, "rev-parse", "--short", "HEAD").strip()
    dirty = bool(git(ROOT, "status", "--porcelain", "--untracked-files=normal").strip())
    assert m.group(1) == package_version_from_source(ROOT)
    assert m.group(2) == expected_commit
    assert bool(m.group(3)) == dirty
    assert m.group(4) == platform.python_version()


def test_FR_0_0_01_version_marks_dirty_tree(tmp_path):
    repo = make_copy_repo(tmp_path)
    head = git(repo, "rev-parse", "--short", "HEAD").strip()

    clean = run_version(repo)
    assert clean.returncode == 0, clean.stderr
    assert f"commit={head} " in clean.stdout and "+dirty" not in clean.stdout

    (repo / "ignored.log").write_text("ignored files never make the tree dirty\n", encoding="utf-8")
    assert "+dirty" not in run_version(repo).stdout

    (repo / "notes.txt").write_text("untracked\n", encoding="utf-8")
    assert f"commit={head}+dirty " in run_version(repo).stdout
    (repo / "notes.txt").unlink()

    init = repo / "aqis_lab" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert f"commit={head}+dirty " in run_version(repo).stdout
    git(repo, "commit", "-q", "-am", "second")
    new_head = git(repo, "rev-parse", "--short", "HEAD").strip()
    after = run_version(repo).stdout
    assert f"commit={new_head} " in after and "+dirty" not in after and new_head != head

    # WP-0.0-F03: staged-only changes are uncommitted changes too.
    init.write_text(init.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    git(repo, "add", "aqis_lab/__init__.py")
    assert git(repo, "diff", "--name-only").strip() == ""          # nothing unstaged
    assert f"commit={new_head}+dirty " in run_version(repo).stdout
    git(repo, "commit", "-q", "-m", "third")
    third = git(repo, "rev-parse", "--short", "HEAD").strip()
    assert "+dirty" not in run_version(repo).stdout
    git(repo, "rm", "-q", "--cached", ".gitignore")                  # staged deletion, file still on disk
    (repo / ".git" / "info" / "exclude").write_text(".gitignore\n*.log\n__pycache__/\n", encoding="utf-8")
    assert f"commit={third}+dirty " in run_version(repo).stdout


def test_FR_0_0_01_version_fails_loudly_outside_git(tmp_path):
    repo = make_copy_repo(tmp_path, init_git=False)
    env = hermetic_git_env({"GIT_CEILING_DIRECTORIES": str(tmp_path)})
    proc = run_version(repo, env=env)
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr.startswith("ERROR:") and "git" in proc.stderr


def test_FR_0_0_01_dispatcher_rejects_unknown_command():
    unknown = subprocess.run([sys.executable, "-m", "aqis_lab", "no-such-command"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
    assert unknown.returncode == 2
    assert "invalid choice" in unknown.stderr and "version" in unknown.stderr
    missing = subprocess.run([sys.executable, "-m", "aqis_lab"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert missing.returncode == 2 and "usage:" in missing.stderr
    extra = subprocess.run([sys.executable, "-m", "aqis_lab", "version", "--bogus"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
    assert extra.returncode == 2 and "--bogus" in extra.stderr


def test_FR_0_0_01_version_reports_package_repository_not_cwd(tmp_path):
    # Audit F36: git is queried in the package's own repository, never the caller's working directory.
    repo = make_copy_repo(tmp_path)
    head = git(repo, "rev-parse", "--short", "HEAD").strip()
    other = tmp_path / "other"
    (other / "docs").mkdir(parents=True)
    (other / "docs" / "notes.md").write_text("another checkout\n", encoding="utf-8")
    git(other, "init", "-q")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "other checkout")
    other_head = git(other, "rev-parse", "--short", "HEAD").strip()
    assert other_head != head
    (tmp_path / "plain").mkdir()
    env = hermetic_git_env({"PYTHONPATH": str(repo)})
    for cwd in (other, other / "docs", tmp_path / "plain"):
        proc = run_version(cwd, env=env)
        assert proc.returncode == 0, (cwd, proc.stderr)
        m = LINE_RE.fullmatch(proc.stdout.strip())
        assert m and m.group(2) == head and not m.group(3), (cwd, proc.stdout)


def test_FR_0_0_01_version_rejects_package_below_checkout_top(tmp_path):
    # Audit F36: a package that is not at the top of its git checkout is an error, never another commit.
    checkout = tmp_path / "checkout"
    shutil.copytree(ROOT / "aqis_lab", checkout / "sub" / "aqis_lab", ignore=shutil.ignore_patterns("__pycache__"))
    git(checkout, "init", "-q")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "package in a subfolder")
    proc = run_version(tmp_path, env=hermetic_git_env({"PYTHONPATH": str(checkout / "sub")}))
    assert proc.returncode == 1 and proc.stdout == ""
    assert proc.stderr.startswith("ERROR:") and "is not its top level" in proc.stderr, proc.stderr
