"""Acceptance tests for WO-1.0-01 (FR-1.0-01): work-order parser, step plans, bundle importer, scope, pack.

Written by Claude before the order was sent; the implementer must not edit this file. One test (or one
parametrised test) per must-catch behaviour of the order's section 8, plus positive controls so that a tool
which refuses everything cannot pass. Modules are imported inside the tests, so a missing package fails each
test on its own instead of aborting collection.

Every test builds a scratch git repository holding the owner's real PROTECTED_PATHS.txt, FOUNDATION.md and
RETURN_FORMAT.md, a small work order WO-9.9-01 and its files. Command-line tests run
`python -m tools.outsourcing` as a subprocess from inside the scratch repository.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORDER_REL = "docs/outsourcing/orders/WO-9.9-01.md"
READ_ONLY_TEST = "tests/aqis_lab/demo/test_acceptance_demo.py"
CONTEXT_FILE = "docs/notes/context.md"
OUTPUTS3 = ("tools/demo/alpha.py", "tools/demo/beta.py", "tests/aqis_lab/demo/test_alpha.py")
OUTPUTS4 = OUTPUTS3 + ("tests/aqis_lab/demo/test_beta.py",)
KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"  # split so this file itself holds no key header
OWNER_FILES = ("docs/process/PROTECTED_PATHS.txt", "docs/process/outsourcing/FOUNDATION.md",
               "docs/process/outsourcing/templates/RETURN_FORMAT.md")


def mod(name: str):
    return importlib.import_module(f"tools.outsourcing.{name}")


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "AQIS Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "AQIS Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"})
    return env


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, capture_output=True,
                          text=True, env=git_env(), timeout=60)
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout


def order_text(outputs=OUTPUTS3, steps=None, context=(CONTEXT_FILE,)) -> str:
    lines = ["---", "id: WO-9.9-01", "wp: WP-9.9", "title: Scratch order for acceptance tests",
             "model: default", "channel: api", "attempt_budget: 2", "risk_tier: T2",
             "max_output_tokens: 20000", "context:"]
    lines += [f"  - {p}" for p in context]
    lines += ["outputs:"] + [f"  - {p}" for p in outputs]
    if steps is not None:
        lines += ["steps:"] + [f"  - {s}" for s in steps]
    lines += ["read_only_tests:", f"  - {READ_ONLY_TEST}", "allowed_dependencies:", "  - stdlib",
              "verify:", "  - .venv/bin/python -m pytest tests/aqis_lab/demo -q", "---", "",
              "# WO-9.9-01 — scratch order", "", "Body of the scratch order.", ""]
    return "\n".join(lines)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for rel in OWNER_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    files = {CONTEXT_FILE: "Context the implementer reads.\n",
             "docs/notes/old.md": "An existing note.\n",
             READ_ONLY_TEST: "def test_demo():\n    assert 1 + 1 == 2\n",
             ORDER_REL: order_text()}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return root


def write_order(root: Path, text: str) -> Path:
    (root / ORDER_REL).write_text(text, encoding="utf-8")
    return root / ORDER_REL


def load(root: Path):
    return mod("workorder").load_work_order(root / ORDER_REL, root)


def content(rel: str) -> str:
    return f'"""Module {rel} written by the scratch implementer."""\n\nVALUE = {len(rel)}\n'


def bundle_text(files: dict[str, str], manifest=None, dod=True) -> str:
    rows = list(files) if manifest is None else list(manifest)
    parts = ["=== MANIFEST ===", "| path | action | purpose |", "| --- | --- | --- |"]
    parts += [f"| {p} | create | scratch |" for p in rows]
    parts.append("=== END MANIFEST ===")
    for path, text in files.items():
        parts += [f"=== FILE: {path} ===", text.rstrip("\n"), "=== END FILE ==="]
    if dod:
        parts += ["=== DOD ===", "| item | met at (file:line) | how |", "| --- | --- | --- |",
                  "| D1 | tools/demo/alpha.py:1 | scratch |", "=== END DOD ==="]
    return "\n".join(parts) + "\n"


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "tools.outsourcing", *args], cwd=root, capture_output=True,
                          text=True, env=env, timeout=120)


def written(root: Path, paths) -> list[str]:
    return [p for p in paths if (root / p).exists()]


# ---------------------------------------------------------------- positive controls

def test_FR_1_0_01_valid_order_loads_with_its_fields(repo):
    order = load(repo)
    assert order.id == "WO-9.9-01" and order.wp == "WP-9.9" and order.attempt_budget == 2
    assert tuple(order.outputs) == OUTPUTS3
    steps = mod("workorder").plan_steps(order)
    assert [s.number for s in steps] == [1] and tuple(steps[0].paths) == OUTPUTS3


def test_FR_1_0_01_valid_bundle_imports_every_file_exactly(repo):
    files = {p: content(p) for p in OUTPUTS3}
    bundle = mod("bundle").parse_bundle(bundle_text(files))
    mod("importer").import_bundle(bundle, load(repo), repo, mode="first", dry_run=False)
    for path, text in files.items():
        assert (repo / path).read_text(encoding="utf-8") == text


def test_FR_1_0_01_cli_import_succeeds_with_exit_0(repo, tmp_path):
    answer = tmp_path / "answer.md"
    answer.write_text(bundle_text({p: content(p) for p in OUTPUTS3}), encoding="utf-8")
    proc = run_cli(repo, "import", "--wo", ORDER_REL, "--bundle", str(answer))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert written(repo, OUTPUTS3) == list(OUTPUTS3)
    assert len(proc.stdout.splitlines()) <= 25


# ---------------------------------------------------------------- must-catch 1

def test_FR_1_0_01_mc01_path_outside_outputs_fails_import_and_writes_nothing(repo, tmp_path):
    files = {p: content(p) for p in OUTPUTS3}
    files["tools/demo/gamma.py"] = content("tools/demo/gamma.py")
    bundle = mod("bundle").parse_bundle(bundle_text(files))
    with pytest.raises(mod("importer").ImportRefused):
        mod("importer").import_bundle(bundle, load(repo), repo, mode="first", dry_run=False)
    assert written(repo, files) == []
    answer = tmp_path / "answer.md"
    answer.write_text(bundle_text(files), encoding="utf-8")
    assert run_cli(repo, "import", "--wo", ORDER_REL, "--bundle", str(answer)).returncode == 3
    assert written(repo, files) == []


def test_FR_1_0_01_mc01_read_only_test_in_bundle_is_refused_and_unchanged(repo):
    before = (repo / READ_ONLY_TEST).read_bytes()
    files = {p: content(p) for p in OUTPUTS3}
    files[READ_ONLY_TEST] = "def test_demo():\n    assert 2 == 2\n"
    bundle = mod("bundle").parse_bundle(bundle_text(files))
    with pytest.raises(mod("importer").ImportRefused):
        mod("importer").import_bundle(bundle, load(repo), repo, mode="first", dry_run=False)
    assert (repo / READ_ONLY_TEST).read_bytes() == before
    assert written(repo, OUTPUTS3) == []


def test_FR_1_0_01_mc01_path_outside_expected_fails_fix_import(repo):
    files = {"tools/demo/alpha.py": content("a"), "tools/demo/beta.py": content("b")}
    bundle = mod("bundle").parse_bundle(bundle_text(files))
    with pytest.raises(mod("importer").ImportRefused):
        mod("importer").import_bundle(bundle, load(repo), repo, mode="fix", dry_run=False,
                                      expected={"tools/demo/alpha.py"})
    assert written(repo, files) == []
    ok = mod("bundle").parse_bundle(bundle_text({"tools/demo/alpha.py": content("a")}))
    mod("importer").import_bundle(ok, load(repo), repo, mode="fix", dry_run=False, expected={"tools/demo/alpha.py"})
    assert written(repo, files) == ["tools/demo/alpha.py"]


# ---------------------------------------------------------------- must-catch 2

def test_FR_1_0_01_mc02_missing_end_marker_fails_import(repo, tmp_path):
    text = bundle_text({p: content(p) for p in OUTPUTS3}).replace("=== END FILE ===\n=== DOD ===", "=== DOD ===")
    with pytest.raises(mod("bundle").BundleError):
        mod("bundle").parse_bundle(text)
    answer = tmp_path / "answer.md"
    answer.write_text(text, encoding="utf-8")
    assert run_cli(repo, "import", "--wo", ORDER_REL, "--bundle", str(answer)).returncode == 3
    assert written(repo, OUTPUTS3) == []


# ---------------------------------------------------------------- must-catch 3

TRUNCATION_LINES = ["...", "…", "# ...", "    # …", "# rest of the file as before", "# REMAINS UNCHANGED",
                    "# same as before", "# unchanged code", "# existing code here", "# omitted for brevity"]


@pytest.mark.parametrize("line", TRUNCATION_LINES)
def test_FR_1_0_01_mc03_truncation_sign_fails_import(repo, tmp_path, line):
    files = {p: content(p) for p in OUTPUTS3}
    files["tools/demo/beta.py"] = f'"""Beta."""\n\n\ndef beta():\n    return 1\n{line}\n'
    text = bundle_text(files)
    assert issubclass(mod("bundle").TruncatedBundle, mod("bundle").BundleError)
    with pytest.raises(mod("bundle").TruncatedBundle):
        mod("bundle").parse_bundle(text)
    answer = tmp_path / "answer.md"
    answer.write_text(text, encoding="utf-8")
    assert run_cli(repo, "import", "--wo", ORDER_REL, "--bundle", str(answer)).returncode == 5
    assert written(repo, OUTPUTS3) == []


# ---------------------------------------------------------------- must-catch 4

def test_FR_1_0_01_mc04_questions_block_stops_import_with_exit_4(repo, tmp_path):
    text = "=== QUESTIONS ===\n1. Which interface should beta call?\n=== END QUESTIONS ===\n"
    bundle = mod("bundle").parse_bundle(text)
    assert any("beta" in question for question in bundle.questions)
    with pytest.raises(mod("importer").QuestionsReturned):
        mod("importer").import_bundle(bundle, load(repo), repo, mode="first", dry_run=False)
    answer = tmp_path / "answer.md"
    answer.write_text(text, encoding="utf-8")
    assert run_cli(repo, "import", "--wo", ORDER_REL, "--bundle", str(answer)).returncode == 4
    assert written(repo, OUTPUTS3) == []


# ---------------------------------------------------------------- must-catch 5

def test_FR_1_0_01_mc05_scope_reports_extra_file_and_deletion(repo):
    git(repo, "checkout", "-qb", "wo/WO-9.9-01")
    (repo / "tools/demo").mkdir(parents=True)
    (repo / "tools/demo/alpha.py").write_text(content("a"), encoding="utf-8")
    (repo / "docs/extra.md").write_text("Not allowed.\n", encoding="utf-8")
    (repo / "docs/notes/old.md").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "branch work")
    proc = run_cli(repo, "scope", "--wo", ORDER_REL, "--base", "main")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "docs/extra.md" in proc.stdout and "docs/notes/old.md" in proc.stdout


def test_FR_1_0_01_mc05_scope_counts_uncommitted_and_untracked_changes(repo):
    git(repo, "checkout", "-qb", "wo/WO-9.9-01")
    (repo / "docs/untracked.md").write_text("Untracked.\n", encoding="utf-8")
    proc = run_cli(repo, "scope", "--wo", ORDER_REL, "--base", "main")
    assert proc.returncode == 1 and "docs/untracked.md" in proc.stdout


def test_FR_1_0_01_scope_passes_outputs_and_record_files(repo):
    git(repo, "checkout", "-qb", "wo/WO-9.9-01")
    allowed = ["tools/demo/alpha.py", "docs/outsourcing/returns/WO-9.9-01/summary.md",
               "docs/outsourcing/ledger.d/WO-9.9-01.md"]
    for rel in allowed:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("allowed\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "allowed work")
    proc = run_cli(repo, "scope", "--wo", ORDER_REL, "--base", "main")
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------- must-catch 6

def test_FR_1_0_01_mc06_pack_refuses_env_file(repo, tmp_path):
    (repo / "secrets").mkdir()
    (repo / "secrets/.env").write_text("MODE=lab\n", encoding="utf-8")
    write_order(repo, order_text(context=(CONTEXT_FILE, "secrets/.env")))
    with pytest.raises(mod("pack").SecretRefused):
        mod("pack").build_pack(load(repo), repo)
    out = tmp_path / "pack.txt"
    assert run_cli(repo, "pack", "--wo", ORDER_REL, "--out", str(out)).returncode == 6
    assert not out.exists()


def test_FR_1_0_01_mc06_pack_refuses_private_key_content(repo):
    (repo / "docs/notes/key.md").write_text(f"Notes\n{KEY_HEADER}\nMIIBOgIBAAJBAK\n", encoding="utf-8")
    write_order(repo, order_text(context=(CONTEXT_FILE, "docs/notes/key.md")))
    with pytest.raises(mod("pack").SecretRefused):
        mod("pack").build_pack(load(repo), repo)


def test_FR_1_0_01_pack_of_clean_order_holds_every_part_in_order(repo, tmp_path):
    out = tmp_path / "pack.txt"
    proc = run_cli(repo, "pack", "--wo", ORDER_REL, "--out", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = out.read_text(encoding="utf-8")
    foundation = (ROOT / OWNER_FILES[1]).read_text(encoding="utf-8")
    return_format = (ROOT / OWNER_FILES[2]).read_text(encoding="utf-8")
    marks = [text.index(foundation.strip()[:200]), text.index("# WO-9.9-01 — scratch order"),
             text.index(f"=== CONTEXT: {CONTEXT_FILE} ==="), text.index(f"=== CONTEXT: {READ_ONLY_TEST} ==="),
             text.rindex(return_format.strip()[:200])]
    assert marks == sorted(marks)
    pack = mod("pack").build_pack(load(repo), repo)
    assert pack.characters == len(pack.text)
    assert pack.estimated_tokens == -(-pack.characters * 2 // 7)  # ceil(characters / 3.5)


# ---------------------------------------------------------------- must-catch 7

@pytest.mark.parametrize("output", ["CLAUDE.md", ".claude/hooks/new_hook.py", "docs/process/WORKFLOW.md",
                                    "docs/specs/phase-1/x.md", "config/aqis_lab/model_pool.json",
                                    "bots/new_bot.py", ".gitignore", ".github/workflows/ci.yml",
                                    "tests/regression/test_new.py"])
def test_FR_1_0_01_mc07_output_under_never_or_guarded_path_is_invalid(repo, output):
    write_order(repo, order_text(outputs=("tools/demo/alpha.py", output)))
    with pytest.raises(mod("workorder").WorkOrderError):
        load(repo)
    assert run_cli(repo, "validate", "--wo", ORDER_REL).returncode == 2


@pytest.mark.parametrize("path, expected", [("CLAUDE.md", "NEVER"), (".claude/settings.json", "NEVER"),
                                            ("config/aqis_lab/model_pool.json", "NEVER"),
                                            ("bots/x.py", "GUARDED"), (".gitignore", "GUARDED"),
                                            ("config/aqis_lab/other.json", "LAB-OWNED"),
                                            ("tests/aqis_lab/x/test_y.py", "LAB-OWNED"),
                                            (".github/workflows/aqis-lab-x.yml", "LAB-OWNED"),
                                            ("tools/x/y.py", "FREE")])
def test_FR_1_0_01_mc07_classify_follows_protected_paths(repo, path, expected):
    assert mod("paths").classify(path, repo) == expected


def test_FR_1_0_01_mc07_lab_owned_and_free_outputs_are_valid(repo):
    write_order(repo, order_text(outputs=("tools/demo/alpha.py", "tests/aqis_lab/demo/test_alpha.py",
                                          ".github/workflows/aqis-lab-demo.yml")))
    assert tuple(load(repo).outputs)[-1] == ".github/workflows/aqis-lab-demo.yml"
    assert run_cli(repo, "validate", "--wo", ORDER_REL).returncode == 0


# ---------------------------------------------------------------- must-catch 8

def test_FR_1_0_01_mc08_missing_base_ref_is_never_no_changes(repo):
    with pytest.raises(mod("scope").ScopeError):
        mod("scope").check_scope(load(repo), repo, "origin/main", "HEAD")
    proc = run_cli(repo, "scope", "--wo", ORDER_REL, "--base", "origin/main")
    assert proc.returncode == 1


# ---------------------------------------------------------------- must-catch 9

GOOD_STEPS = ("tools/demo/alpha.py, tests/aqis_lab/demo/test_alpha.py",
              "tools/demo/beta.py, tests/aqis_lab/demo/test_beta.py")


def test_FR_1_0_01_mc09_valid_step_plan_is_numbered_in_order(repo):
    write_order(repo, order_text(outputs=OUTPUTS4, steps=GOOD_STEPS))
    steps = mod("workorder").plan_steps(load(repo))
    assert [(s.number, tuple(s.paths)) for s in steps] == [
        (1, ("tools/demo/alpha.py", "tests/aqis_lab/demo/test_alpha.py")),
        (2, ("tools/demo/beta.py", "tests/aqis_lab/demo/test_beta.py"))]


@pytest.mark.parametrize("steps", [
    ("tools/demo/alpha.py, tests/aqis_lab/demo/test_alpha.py", "tools/demo/beta.py"),
    GOOD_STEPS + ("tools/demo/alpha.py",),
    GOOD_STEPS[:1] + ("tools/demo/beta.py, tests/aqis_lab/demo/test_beta.py, tools/demo/gamma.py",),
    ("tools/demo/alpha.py, , tests/aqis_lab/demo/test_alpha.py", GOOD_STEPS[1]),
    ("tools/demo/alpha.py, tests/aqis_lab/demo/test_alpha.py,", GOOD_STEPS[1]),
], ids=["misses-an-output", "repeats-an-output", "path-outside-outputs", "empty-element", "trailing-comma"])
def test_FR_1_0_01_mc09_bad_step_plan_is_invalid(repo, steps):
    write_order(repo, order_text(outputs=OUTPUTS4, steps=steps))
    with pytest.raises(mod("workorder").WorkOrderError):
        mod("workorder").plan_steps(load(repo))
    assert run_cli(repo, "validate", "--wo", ORDER_REL).returncode == 2


def test_FR_1_0_01_mc09_more_than_three_outputs_without_steps_is_invalid(repo):
    write_order(repo, order_text(outputs=OUTPUTS4))
    with pytest.raises(mod("workorder").WorkOrderError, match="add a steps list"):
        mod("workorder").plan_steps(load(repo))
    assert run_cli(repo, "validate", "--wo", ORDER_REL).returncode == 2


# ---------------------------------------------------------------- must-catch 10

def test_FR_1_0_01_mc10_every_outsourcing_module_is_secret_clean():
    folder = ROOT / "tools" / "outsourcing"
    required = {"__init__.py", "__main__.py", "workorder.py", "paths.py", "secrets.py", "bundle.py",
                "importer.py", "scope.py", "pack.py"}
    present = {p.name for p in folder.glob("*.py")}
    assert required <= present, sorted(required - present)
    secret_reasons = mod("secrets").secret_reasons
    for path in sorted(folder.glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        assert secret_reasons(rel, path.read_text(encoding="utf-8")) == [], rel


@pytest.mark.parametrize("path, text", [
    ("docs/a.md", "token " + "hf_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"),
    ("docs/a.md", "ghp_" + "a" * 36),
    ("docs/a.md", "github_pat_" + "B" * 30),
    ("docs/a.md", "key = AIza" + "C" * 35),
    ("docs/a.md", "sk-ant-" + "d" * 24),
    ("docs/a.md", f"{KEY_HEADER}\nabc\n"),
    ("config/.env", "MODE=lab\n"),
    ("certs/server.pem", "text\n"),
    ("home/id_rsa", "text\n"),
])
def test_FR_1_0_01_mc10_secret_shapes_are_flagged(path, text):
    assert mod("secrets").secret_reasons(path, text) != []


def test_FR_1_0_01_mc10_bare_prefixes_are_clean():
    assert mod("secrets").secret_reasons("docs/a.md", "prefixes hf_ ghp_ github_pat_ AIza sk-ant- -----BEGIN") == []


def test_FR_1_0_01_mc10_text_after_stray_end_marker_fails_parse():
    inner = '"""Doc."""\n```text\n=== END FILE ===\n```\nVALUE = 1'
    text = bundle_text({"tools/demo/alpha.py": inner})
    with pytest.raises(mod("bundle").BundleError):
        mod("bundle").parse_bundle(text)
