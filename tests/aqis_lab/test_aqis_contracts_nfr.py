"""NFR-0.2-01 (100,000 events validated in under 10 s on the cloud VM) and NFR-0.2-02 (pure Python, pinned jsonschema)."""
import ast
import json
import subprocess
import sys
import time

import pytest

from aqis_contracts_testutil import EVENT_TYPES, valid_events
from aqis_testutil import ROOT, parse_lock

CONTRACT_CODE = sorted((ROOT / "aqis_lab" / "contracts").glob("*.py")) + [ROOT / "aqis_lab" / "commands" / "contracts.py"]


@pytest.mark.slow
def test_NFR_0_2_01_validates_100k_events_under_10s(tmp_path):
    templates = [e for e in valid_events() if e["run_id"] == "run-0001"]
    assert {e["event_type"] for e in templates} == set(EVENT_TYPES)
    path = tmp_path / "events_100k.jsonl"
    with path.open("w", encoding="utf-8") as out:
        for i in range(100_000):
            out.write(json.dumps(dict(templates[i % len(templates)], run_id="run-nfr", seq=i, wall_time_ns=1000 + i)))
            out.write("\n")
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "contracts", "validate", str(path), "--kind", "event"],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)
    seconds = time.perf_counter() - start
    assert proc.returncode == 0, proc.stderr[-2000:]
    lines = proc.stdout.splitlines()
    assert lines[-1] == "event: 100000 records, 100000 valid, 0 invalid"
    assert sum(1 for line in lines if line.endswith(": OK")) == 100_000
    print(f"validated 100000 events in {seconds:.2f} s ({proc.stderr.strip()})")
    assert seconds < 10, f"took {seconds:.2f} s"


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: relative import"
            yield node.module.split(".")[0]


def test_NFR_0_2_02_contracts_code_is_pure_python_with_pinned_jsonschema():
    assert len(CONTRACT_CODE) == 4
    third_party = set()
    for path in CONTRACT_CODE:
        for name in _imports(path):
            if name not in sys.stdlib_module_names and name != "aqis_lab":
                third_party.add(name)
    assert third_party == {"jsonschema"}
    pin = parse_lock()["jsonschema"]
    assert pin["version"] == "4.26.0" and pin["hashes"]
    import jsonschema
    from importlib.metadata import version
    assert version("jsonschema") == pin["version"] and jsonschema.Draft202012Validator
    # nothing compiled or non-Python in the package: only modules and the JSON schema files
    files = [p for p in (ROOT / "aqis_lab" / "contracts").rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    kinds = {(p.parent.name, p.suffix) for p in files}
    assert kinds == {("contracts", ".py"), ("schemas", ".json")}, kinds
