"""NFR-0.0-01 (gate runtime), NFR-0.0-02 (file:line and rule in every message), NFR-0.0-03 (dependencies)."""
import ast
import importlib.metadata as md
import json
import re
import subprocess
import sys
import time

from aqis_testutil import ROOT, git, normalise, parse_lock
from fixture_repo import FixtureRepo

MESSAGE_RE = re.compile(r"^(?P<path>[^\s:]+):(?P<line>\d+): \[(?P<rule>[A-F]\d)\] (?:CRITICAL|MAJOR|COMPROMISE): \S.*$")


def test_NFR_0_0_01_gate_runtime_under_60s():
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "-B", "-m", "tools.audit.gate", "--base", "origin/main", "--wp", "WP-0.0",
                           "--json"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    elapsed = time.monotonic() - start
    assert proc.returncode in (0, 1), proc.stderr
    assert json.loads(proc.stdout)["tool"] == "aqis-audit-gate"
    assert elapsed < 60, f"gate took {elapsed:.1f} s"


def test_NFR_0_0_02_every_message_names_file_line_and_rule(tmp_path):
    repo = FixtureRepo(tmp_path)
    repo.write("docs/specs/phase-9/WP-9.9-x.md", "- **FR-9.9-01** thing\n- **AT-9.9-01** run\n")
    repo.commit("spec")
    git(repo.path, "push", "-q", "origin", "main")
    repo.branch()
    repo.write("CLAUDE.md", "x\n")                                              # A1
    repo.append("vad_adapters/example.py", "\nY = 2\n")                          # A2
    repo.append("tests/regression/test_example.py", "\n# edited\n")              # A2 + B1
    repo.delete("tests/lab_support/test_adds.py")                                # A2 + B2 + E3
    repo.copy_fixture("code_patterns.py", "tools/bad.py")                        # C1
    repo.copy_fixture("test_patterns.py", "tests/aqis_lab/test_bad.py")          # C2
    repo.write("aqis_lab/no_header.py", "".join(f"V{i} = {i}\n" for i in range(6)))  # D1
    repo.append("docs/capabilities/REGISTRY.md", "| CAP-Z | `nowhere.py` | f | x | `test_zz` | WP | ACTIVE |\n")  # E3, E4
    repo.write("docs/progress/WP-9.9/PLAN.md", "nothing\n")                     # F2, F3, F4
    text = repo.gate("--base", "origin/main", "--wp", "WP-9.9", json_output=False)
    report = json.loads(repo.gate("--base", "origin/main", "--wp", "WP-9.9").stdout)
    assert text.returncode == 1
    lines = text.stdout.splitlines()
    start = lines.index(f"Findings: {len(report['findings'])}") + 1
    finding_lines = lines[start:start + len(report["findings"])]
    assert len(finding_lines) == len(report["findings"]) > 0
    rules = set()
    for line in finding_lines:
        m = MESSAGE_RE.match(line)
        assert m, f"message does not name file:line and rule: {line}"
        rules.add(m.group("rule"))
    for f in report["findings"]:
        assert f["path"] and isinstance(f["line"], int) and f["line"] >= 1 and f["rule"]
    assert {"A1", "A2", "B1", "B2", "C1", "C2", "D1", "E3", "E4", "F2", "F3", "F4"} <= rules
    assert lines[-1].startswith(f"{len(report['findings'])} findings: FAIL")


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_NFR_0_0_03_imports_are_stdlib_or_pinned():
    stdlib = set(sys.stdlib_module_names)
    first_party = {"aqis_lab", "tools"}
    pinned = set(parse_lock())
    pinned_imports = {mod for mod, dists in md.packages_distributions().items()
                      if any(normalise(d) in pinned for d in dists)}
    for folder in ("aqis_lab", "tools"):
        files = sorted((ROOT / folder).rglob("*.py"))
        assert files, folder
        for path in files:
            for name in _imports(path):
                assert name in stdlib | first_party | pinned_imports, f"{path.relative_to(ROOT)} imports {name}"
                if folder == "tools":
                    # The gate must also run under the Stop hook's fallback interpreter: standard library only.
                    assert name in stdlib | {"tools"}, f"{path.relative_to(ROOT)} imports non-stdlib {name}"
