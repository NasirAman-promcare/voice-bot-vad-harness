"""FR-0.5-08: the Colab launcher notebook (at most 6 cells; mount Drive, clone at a pinned tag with the GITHUB_TOKEN
secret, install the lock, call lab commands; no logic)."""
import ast
import importlib
import json
import re
import subprocess
import sys
import traceback
import types

import pytest
import yaml

from aqis_testutil import ROOT

NOTEBOOK = ROOT / "notebooks" / "aqis_lab" / "phase0_launcher.ipynb"
RUNBOOK = ROOT / "docs" / "colab" / "COLAB_RUNBOOK.md"
TAG = "aqis-lab-wp-0.5-colab-1"            # owner decision, question 12 (a)

# --- the static no-logic check (must-catch 4) --------------------------------------------------------------------
ALLOWED_NODES = (ast.Module, ast.Expr, ast.Assign, ast.Delete, ast.Import, ast.ImportFrom, ast.alias, ast.Name,
                 ast.Load, ast.Store, ast.Del, ast.Constant, ast.List, ast.Starred, ast.BinOp, ast.Add, ast.Call,
                 ast.Attribute, ast.keyword)
ALLOWED_IMPORTS = {"base64", "os", "subprocess"}
ALLOWED_FROM = {"google.colab": {"drive", "userdata"}}
ALLOWED_CALLS = {"drive.mount", "subprocess.run", "userdata.get", "base64.b64encode", "dict"}
ALLOWED_METHODS = {"encode", "decode"}
ALLOWED_ATTRIBUTES = {"os.environ"}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def _const(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _name(node):
    return node.id if isinstance(node, ast.Name) else None


def command_shape_problems(call):
    """WP-0.5-F04: a launcher command must be one of the launcher's own steps, in its exact shape.

    Allowed: `rm -rf WORKDIR`; the one `git clone --quiet --depth 1 --branch AQIS_TAG REPO WORKDIR` (the only call
    with env=); `pip install [--quiet] uv==X.Y.Z`; `bash aqis_lab/deploy/dev_bootstrap.sh`; and
    `PY -m aqis_lab <registered command> <options>` whose options are literals or settings, never `-c`.
    Keywords other than check, cwd (a setting) and the clone's env are refused, so is a command that is not a list.
    """
    from aqis_lab.__main__ import COMMANDS
    if len(call.args) != 1 or not isinstance(call.args[0], ast.List):
        return ["the command must be a literal list (no string command, no command held in a variable)"]
    items = call.args[0].elts
    consts = [_const(e) for e in items]
    names = [_name(e) for e in items]
    words = [c if c is not None else (f"${n}" if n else None) for c, n in zip(consts, names)]
    problems = []
    is_clone = words == ["git", "clone", "--quiet", "--depth", "1", "--branch", "$AQIS_TAG", "$REPO", "$WORKDIR"]
    shapes = (
        words == ["rm", "-rf", "$WORKDIR"],
        is_clone,
        words[:2] == ["pip", "install"] and len(words) in (3, 4) and words[2:-1] in ([], ["--quiet"])
        and bool(re.fullmatch(r"uv==\d+\.\d+\.\d+", words[-1] or "")),
        words == ["bash", "aqis_lab/deploy/dev_bootstrap.sh"],
        words[:3] == ["$PY", "-m", "aqis_lab"] and len(words) >= 4 and words[3] in COMMANDS
        and "-c" not in words[4:]
        and all(isinstance(e, (ast.Constant, ast.Name, ast.BinOp, ast.Starred)) for e in items[4:]),
    )
    if not any(shapes):
        problems.append(f"command {ast.unparse(call.args[0])} is not one of the launcher's steps")
    for keyword in call.keywords:
        if keyword.arg == "check":
            continue
        if keyword.arg == "cwd" and _name(keyword.value):
            continue
        if keyword.arg == "env" and is_clone:
            continue
        problems.append(f"keyword {keyword.arg}= is not allowed for this command")
    return problems


SETTINGS = ("AQIS_TAG", "REPO", "WORKDIR", "DRIVE_MOUNT", "AQIS_DRIVE", "RUN_OUT", "RUN_ARGS")
LATER_CELL_NAMES = ("PY",)       # the only name a later cell may assign (pinned in the no-logic test)


def logic_problems(source, first_cell=False):
    """Every construct in one code cell that is not one of the launcher's allowed steps.

    WP-0.5-F10: the commands trust the cell-1 settings (`rm -rf WORKDIR`), so only cell 1 assigns them and a later
    cell may assign only `PY`. A cell checked on its own counts as a later cell unless first_cell is True.
    """
    problems = []
    for no, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith(("!", "%")):
            problems.append(f"line {no}: shell or magic line {line.strip()!r}")
    if problems:
        return problems
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"not plain Python: {exc}"]
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            problems.append(f"line {getattr(node, 'lineno', '?')}: {type(node).__name__} is logic")
        elif isinstance(node, ast.Import):
            problems += [f"import {a.name}" for a in node.names if a.name not in ALLOWED_IMPORTS or a.asname]
        elif isinstance(node, ast.ImportFrom):
            names = ALLOWED_FROM.get(node.module, set())
            problems += [f"from {node.module} import {a.name}" for a in node.names if a.name not in names or a.asname]
        elif isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                problems.append(f"line {node.lineno}: assignment to something other than one name")
            else:
                target = node.targets[0].id
                allowed = SETTINGS if first_cell else LATER_CELL_NAMES
                if target not in allowed:
                    problems.append(f"line {node.lineno}: {target} may not be assigned in this cell "
                                    f"({'cell 1 assigns only the settings' if first_cell else 'the settings belong to cell 1'})")
        elif isinstance(node, ast.Call):
            name = dotted(node.func)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if name not in ALLOWED_CALLS and method not in ALLOWED_METHODS:
                problems.append(f"line {node.lineno}: call {name or ast.unparse(node.func)} is not an allowed step")
            if name == "subprocess.run":
                check = [k for k in node.keywords if k.arg == "check"]
                if not (check and isinstance(check[0].value, ast.Constant) and check[0].value.value is True):
                    problems.append(f"line {node.lineno}: subprocess.run without check=True can hide a failure")
                problems += [f"line {node.lineno}: {p}" for p in command_shape_problems(node)]
        elif isinstance(node, ast.Attribute):
            name = dotted(node)
            if not (name in ALLOWED_ATTRIBUTES or name in ALLOWED_CALLS or node.attr in ALLOWED_METHODS):
                problems.append(f"line {node.lineno}: attribute {ast.unparse(node)} is not an allowed step")
    return problems


def notebook():
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def code_cells():
    return ["".join(c["source"]) for c in notebook()["cells"] if c["cell_type"] == "code"]


def test_FR_0_5_08_launcher_has_at_most_6_cells():
    nb = notebook()
    assert nb["nbformat"] == 4 and 1 <= len(nb["cells"]) <= 6
    assert [c["cell_type"] for c in nb["cells"]] == ["markdown"] + ["code"] * (len(nb["cells"]) - 1)
    for cell in nb["cells"]:
        assert cell["cell_type"] == "markdown" or (cell["outputs"] == [] and cell["execution_count"] is None), \
            "the committed notebook carries no outputs"


def test_FR_0_5_08_tag_is_one_variable_in_first_cell():
    cells = code_cells()
    assigns = [(i, n) for i, cell in enumerate(cells) for n in ast.walk(ast.parse(cell))
               if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "AQIS_TAG"]
    assert len(assigns) == 1 and assigns[0][0] == 0
    node = assigns[0][1]
    assert isinstance(node.value, ast.Constant) and node.value.value == TAG
    first = ast.parse(cells[0])
    for stmt in first.body:
        if isinstance(stmt, ast.Assign):
            assert isinstance(stmt.value, (ast.Constant, ast.List)), "cell 1 settings are literals"
    clone = [n for n in ast.walk(ast.parse(cells[1])) if isinstance(n, ast.Call) and dotted(n.func) == "subprocess.run"
             and "clone" in ast.unparse(n.args[0])]
    assert len(clone) == 1 and "'--branch', AQIS_TAG" in ast.unparse(clone[0].args[0])


def test_FR_0_5_08_launcher_cells_contain_no_logic():
    for i, cell in enumerate(code_cells(), start=1):
        assert logic_problems(cell, first_cell=i == 1) == [], f"cell {i}: {logic_problems(cell, first_cell=i == 1)}"
    # WP-0.5-F10: every cell-1 setting is assigned exactly once in the whole notebook, and that is in cell 1
    assigned = [(i, n.targets[0].id) for i, cell in enumerate(code_cells(), start=1) for n in ast.walk(ast.parse(cell))
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)]
    for name in SETTINGS:
        assert [i for i, target in assigned if target == name] == [1], f"{name} must be assigned once, in cell 1"
    text = "\n".join(code_cells())
    assert text.count("drive.mount(") == 1 and text.count("dev_bootstrap.sh") == 1
    # WP-0.5-F04: the commands trust PY, so PY is the lab environment's Python, defined once
    py = [n for cell in code_cells() for n in ast.walk(ast.parse(cell))
          if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "PY"]
    assert len(py) == 1 and ast.unparse(py[0].value) == "WORKDIR + '/.venv/bin/python'"
    assert re.search(r'"git", "clone"', text) and text.count('"clone"') == 1


@pytest.mark.parametrize("source", [
    "if AQIS_TAG:\n    PY = 1\n",
    "for a in [1]:\n    pass\n",
    "while False:\n    pass\n",
    "def f():\n    return 1\n",
    "try:\n    PY = 1\nexcept OSError:\n    PY = 2\n",
    "with open('x') as fh:\n    PY = fh\n",
    "PY = [a for a in 'ab']\n",
    "PY = 1 if True else 2\n",
    "PY = AQIS_TAG == 'a'\n",
    "PY = lambda: 1\n",
    "!pip install uv\n",
    "%cd /content\n",
    "import shutil\n",
    "import os\nos.system('ls')\n",
    "import subprocess\nsubprocess.run(['ls'])\n",
    "import subprocess\nsubprocess.run(['ls'], check=False)\n",
    "PY = open('/etc/passwd')\n",
    "PY = y[0]\n",
    "import os\nos.chdir('/content')\n",
])
def test_FR_0_5_08_logic_checker_rejects_each_forbidden_form(source):
    assert logic_problems(source), f"the checker let this through: {source!r}"


# WP-0.5-F04: logic hidden inside a command. Only the launcher's own command shapes may run.
HIDDEN_LOGIC = {
    "bash_c": 'subprocess.run(["bash", "-c", "if [ -d data/raw ]; then rm -rf data/raw; fi"], cwd=WORKDIR, check=True)',
    "python_c": 'subprocess.run(["python", "-c", "print(1)"], check=True)',
    "venv_python_c": 'subprocess.run([PY, "-c", "import os"], cwd=WORKDIR, check=True)',
    "string_shell": 'subprocess.run("ls -la", shell=True, check=True)',
    "shell_keyword": 'subprocess.run(["rm", "-rf", WORKDIR], shell=True, check=True)',
    "other_program": 'subprocess.run(["ls", "/content"], check=True)',
    "rm_elsewhere": 'subprocess.run(["rm", "-rf", "/content/drive"], check=True)',
    "pip_other_package": 'subprocess.run(["pip", "install", "requests"], check=True)',
    "venv_pip": 'subprocess.run([PY, "-m", "pip", "install", "x"], cwd=WORKDIR, check=True)',
    "unknown_lab_command": 'subprocess.run([PY, "-m", "aqis_lab", "nosuch"], cwd=WORKDIR, check=True)',
    "clone_other_branch": 'subprocess.run(["git", "clone", "--branch", "main", REPO, WORKDIR], check=True)',
    "other_script": 'subprocess.run(["bash", "other.sh"], cwd=WORKDIR, check=True)',
    "env_outside_clone": 'subprocess.run(["rm", "-rf", WORKDIR], env=dict(os.environ), check=True)',
    "command_in_variable": 'subprocess.run(RUN_ARGS, check=True)',
    # WP-0.5-F10, break E4: a later cell re-points WORKDIR before `rm -rf WORKDIR`
    "reassign_workdir": 'WORKDIR = "/content/drive/MyDrive"\nsubprocess.run(["rm", "-rf", WORKDIR], check=True)',
}


@pytest.mark.parametrize("name", sorted(HIDDEN_LOGIC))
def test_FR_0_5_08_logic_checker_rejects_logic_inside_commands(name):
    source = "import os\nimport subprocess\n" + HIDDEN_LOGIC[name] + "\n"
    assert logic_problems(source), f"the checker let this through: {HIDDEN_LOGIC[name]!r}"


def test_FR_0_5_08_token_only_reaches_the_clone_command():
    cells = code_cells()
    text = "\n".join(cells)
    assert text.count('userdata.get("GITHUB_TOKEN")') == 1
    calls = [n for cell in cells for n in ast.walk(ast.parse(cell)) if isinstance(n, ast.Call)]
    token_calls = [n for n in calls if dotted(n.func) == "userdata.get"]
    clone = next(n for n in calls if dotted(n.func) == "subprocess.run" and "clone" in ast.unparse(n.args[0]))
    env = next(k for k in clone.keywords if k.arg == "env")
    assert any(t is n for t in token_calls for n in ast.walk(env.value)), "the token is read inside the clone's env"
    assert not any(isinstance(n, ast.Assign) and "userdata" in ast.unparse(n.value)
                   for cell in cells for n in ast.walk(ast.parse(cell))), "no variable ever holds the token"
    assert "GIT_CONFIG_KEY_0=\"http.extraHeader\"" in text.replace("'", '"')
    for forbidden in ("credential.helper", "--global", "set-url", "@github.com"):
        assert forbidden not in text, forbidden
    assert not re.search(r"https://[^\"']*(token|userdata)", text, re.I)


def run_cells(cells, ns):
    for cell in cells:
        exec(compile(cell, "<launcher cell>", "exec"), ns)


def test_FR_0_5_08_clone_failure_never_shows_token(tmp_path, capfd, monkeypatch):
    token = "github_pat_FR_0_5_08_token_value_0123456789abcdef"
    colab = types.ModuleType("google.colab")
    colab.drive = types.SimpleNamespace(mount=lambda path: None)          # Google Drive test double
    colab.userdata = types.SimpleNamespace(get=lambda name: token if name == "GITHUB_TOKEN" else None)
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    cells = code_cells()
    ns = {}
    run_cells(cells[:1], ns)
    ns["WORKDIR"] = str(tmp_path / "clone")
    ns["REPO"] = str(tmp_path / "no-such-repository.git")
    with pytest.raises(subprocess.CalledProcessError) as err:
        run_cells(cells[1:2], ns)
    shown = capfd.readouterr()
    rendered = "".join(traceback.format_exception(err.value)) + str(err.value)
    for text in (shown.out, shown.err, rendered, repr(err.value.cmd)):
        assert token not in text
    for name, value in ns.items():
        if not name.startswith("__"):
            assert token not in repr(value), f"the token stays in the notebook variable {name}"


def command_argvs(extra_run_args=None):
    """[(command, arguments)] of every `python -m aqis_lab` call, with the launcher's settings filled in."""
    cells = code_cells()
    ns = {}
    first = ast.parse(cells[0])
    for stmt in first.body:
        if isinstance(stmt, ast.Assign):
            ns[stmt.targets[0].id] = ast.literal_eval(stmt.value)
    if extra_run_args is not None:
        ns["RUN_ARGS"] = extra_run_args
    found = []
    for cell in cells[1:]:
        for stmt in ast.parse(cell).body:
            if isinstance(stmt, ast.Assign):
                ns[stmt.targets[0].id] = eval(compile(ast.Expression(stmt.value), "<cell>", "eval"), {}, ns)
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call) and dotted(node.func) == "subprocess.run":
                    argv = eval(compile(ast.Expression(node.args[0]), "<cell>", "eval"), {}, dict(ns))
                    if "aqis_lab" in argv:
                        at = argv.index("aqis_lab")
                        found.append((argv[at + 1], argv[at + 2:]))
    return found


RUNBOOK_RUN_ARGS = [["--shard-clips", "10"], ["--shard-clips", "10", "--max-shards", "2"]]


@pytest.mark.parametrize("run_args", [None] + RUNBOOK_RUN_ARGS)
def test_FR_0_5_08_launcher_commands_exist_and_parse(run_args):
    from aqis_lab.__main__ import COMMANDS
    calls = command_argvs(run_args)
    assert [c for c, _ in calls] == ["drive", "unitlog", "doctor", "run", "unitlog"]
    for command, args in calls:
        module = importlib.import_module(COMMANDS[command][0])
        ns = module.build_parser().parse_args(args)          # SystemExit would fail the test
        if command == "doctor":
            assert ns.target == "colab" and ns.drive_mount and ns.out.endswith("/MyDrive/AQIS_LAB/logs")
        if command == "run":
            assert "/MyDrive/AQIS_LAB/" in ns.out and ns.drive_mount


def test_FR_0_5_08_runbook_matches_launcher():
    text = RUNBOOK.read_text(encoding="utf-8")
    assert TAG in text and "GITHUB_TOKEN" in text and "OC-0.5-01" in text and "OC-0.5-02" in text
    for args in RUNBOOK_RUN_ARGS:
        assert f"RUN_ARGS = {json.dumps(args)}" in text, args
    assert "!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab" in text
    settings = {s.targets[0].id: ast.literal_eval(s.value) for s in ast.parse(code_cells()[0]).body
                if isinstance(s, ast.Assign)}
    assert settings["WORKDIR"] == "/content/aqis" and settings["RUN_OUT"] in text
    # the runbook's minimums table equals config/aqis_lab/doctor.yaml (with docs/doctor/DOCTOR.md, FR-0.5-02)
    config = yaml.safe_load((ROOT / "config/aqis_lab/doctor.yaml").read_text(encoding="utf-8"))["minimums"]
    table = {m.group(1): {"free_disk_gb": float(m.group(2)), "available_ram_gb": float(m.group(3))}
             for m in re.finditer(r"^\|\s*(cloud|colab|oracle)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|", text, re.M)}
    assert table == {t: {k: float(v) for k, v in m.items()} for t, m in config.items()}
    rates = yaml.safe_load((ROOT / "config/aqis_lab/colab_rates.yaml").read_text(encoding="utf-8"))["rates"]
    for rate in rates:
        assert f"| {rate['runtime']} | {rate['units_per_hour']} |" in text
