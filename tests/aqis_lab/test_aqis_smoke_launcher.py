"""OC-0.7-01: the smoke launcher notebook (notebooks/aqis_lab/phase0_smoke_launcher.ipynb; owner decision, question
13) obeys the WP-0.5 launcher rules (at most 6 cells, no logic, token only in the clone) and its commands parse with
the lab's own parsers. The rule checker is the WP-0.5 one, imported unchanged from test_aqis_launcher.py.
"""
import ast
import importlib
import json
import re

import test_aqis_launcher as rules
from aqis_testutil import ROOT

NOTEBOOK = ROOT / "notebooks" / "aqis_lab" / "phase0_smoke_launcher.ipynb"
RUNBOOK = ROOT / "docs" / "colab" / "COLAB_RUNBOOK.md"
TAG = "aqis-lab-wp-0.7-colab-1"                 # owner decision, question 14


def cells():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4 and 1 <= len(nb["cells"]) <= 6
    assert [c["cell_type"] for c in nb["cells"]] == ["markdown"] + ["code"] * (len(nb["cells"]) - 1)
    assert all(c["cell_type"] == "markdown" or (c["outputs"] == [] and c["execution_count"] is None)
               for c in nb["cells"])
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def settings():
    return {s.targets[0].id: ast.literal_eval(s.value) for s in ast.parse(cells()[0]).body if isinstance(s, ast.Assign)}


def test_FR_0_7_07_smoke_launcher_cells_contain_no_logic():
    code = cells()
    # The WP-0.5 checker knows the bootstrap step without options only. The approved plan (OC-0.7-01) adds `--gpu`
    # in cell 3, so exactly that one report is expected there; every other rule still applies to every cell.
    gpu_step = "command ['bash', 'aqis_lab/deploy/dev_bootstrap.sh', '--gpu'] is not one of the launcher's steps"
    for i, cell in enumerate(code, start=1):
        problems = rules.logic_problems(cell, first_cell=i == 1)
        expected = [f"line {n}: {gpu_step}" for n, line in enumerate(cell.splitlines(), start=1)
                    if '"aqis_lab/deploy/dev_bootstrap.sh", "--gpu"' in line]
        assert problems == expected, (i, problems)
    assert len(rules.logic_problems(code[2])) == 1
    assigned = [(i, n.targets[0].id) for i, cell in enumerate(code, start=1) for n in ast.walk(ast.parse(cell))
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)]
    for name in rules.SETTINGS:
        assert [i for i, target in assigned if target == name] == [1], name
    text = "\n".join(code)
    assert text.count("drive.mount(") == 1 and text.count("dev_bootstrap.sh") == 1
    assert '"aqis_lab/deploy/dev_bootstrap.sh", "--gpu"' in text, "the smoke needs the GPU extras (FR-0.7-03)"
    assert settings()["AQIS_TAG"] == TAG and settings()["RUN_OUT"].startswith("/content/drive/MyDrive/AQIS_LAB/")


def test_FR_0_7_07_token_only_reaches_the_clone_command():
    code = cells()
    text = "\n".join(code)
    assert text.count('userdata.get("GITHUB_TOKEN")') == 1
    calls = [n for cell in code for n in ast.walk(ast.parse(cell)) if isinstance(n, ast.Call)]
    clone = next(n for n in calls if rules.dotted(n.func) == "subprocess.run" and "clone" in ast.unparse(n.args[0]))
    env = next(k for k in clone.keywords if k.arg == "env")
    assert any(rules.dotted(n.func) == "userdata.get" for n in ast.walk(env.value) if isinstance(n, ast.Call))
    assert not any(isinstance(n, ast.Assign) and "userdata" in ast.unparse(n.value)
                   for cell in code for n in ast.walk(ast.parse(cell)))
    for forbidden in ("credential.helper", "--global", "set-url", "@github.com"):
        assert forbidden not in text
    assert not re.search(r"https://[^\"']*(token|userdata)", text, re.I)


def test_FR_0_7_07_smoke_launcher_commands_exist_and_parse():
    from aqis_lab.__main__ import COMMANDS
    ns = dict(settings())
    found = []
    for cell in cells()[1:]:
        for stmt in ast.parse(cell).body:
            if isinstance(stmt, ast.Assign):
                ns[stmt.targets[0].id] = eval(compile(ast.Expression(stmt.value), "<cell>", "eval"), {}, ns)
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call) and rules.dotted(node.func) == "subprocess.run":
                    argv = eval(compile(ast.Expression(node.args[0]), "<cell>", "eval"), {}, dict(ns))
                    if "aqis_lab" in argv:
                        found.append((argv[argv.index("aqis_lab") + 1], argv[argv.index("aqis_lab") + 2:]))
    assert [c for c, _ in found] == ["drive", "unitlog", "doctor", "phase0", "unitlog"]
    for command, args in found:
        parsed = importlib.import_module(COMMANDS[command][0]).build_parser().parse_args(args)
        if command == "doctor":
            assert parsed.target == "colab" and parsed.expect_gpu and parsed.out.endswith("/MyDrive/AQIS_LAB/logs")
        if command == "phase0":
            assert parsed.target == "colab" and parsed.drive_mount == "/content/drive"
            assert parsed.out == settings()["RUN_OUT"]


def test_FR_0_7_07_runbook_describes_the_smoke_launcher():
    text = RUNBOOK.read_text(encoding="utf-8")
    section = text[text.index("## OC-0.7-01"):]
    assert "phase0_smoke_launcher.ipynb" in section and TAG in section and "T4" in section
    assert settings()["RUN_OUT"] in section
    assert '!cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m "colab or gpu"' in section
    assert "data/runs/phase0-smoke/" in section
