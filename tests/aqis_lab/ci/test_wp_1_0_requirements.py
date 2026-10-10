"""WP-1.0 requirement tests that belong to no single work order: FR-1.0-10, FR-1.0-11, FR-1.0-13, NFR-1.0-01.

Written by Claude (not outsourced). Each test reads the committed repository state, so it fails until the work it
checks is committed: the `.relay/` ignore line, the DEBT-032 Colab output, the migrated debt fragments set to
CLOSED, every order's summary and ledger fragment, and the standard-library-only tools.
"""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GPU_LOCK = ROOT / "requirements/aqis_lab/phase0-gpu.txt"
CPU_LOCK = ROOT / "requirements/aqis_lab/phase0.txt"
GPU_IN = ROOT / "requirements/aqis_lab/phase0-gpu.in"
PARAKEET_DOC = ROOT / "docs/adapters/PARAKEET_UNIFIED.md"
GPU_OUTPUT = ROOT / "docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu_full.txt"
ORDERS = sorted((ROOT / "docs/outsourcing/orders").glob("WO-1.0-*.md"))
STDLIB_TOOL_DIRS = ("tools/outsourcing", "tools/index", "tools/progress", "tools/autonomy", "tools/ci",
                    "kit-staging/.claude/hooks")
STDLIB_TOOL_FILES = ("tools/audit/breaks.py", "tools/audit/mutate.py", "tools/audit/mutation_report.py")
REPOSITORY_ROOTS = {"tools", "aqis_lab", "tests", "_protected", "_loopstate"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z ]*):\s*(.*?)\s*$", line)
        if match and match.group(1) not in found:
            found[match.group(1)] = match.group(2)
    return found


def test_FR_1_0_10_gitignore_ignores_relay():
    proc = subprocess.run(["git", "check-ignore", "--no-index", "-q", ".relay/governor.json", ".relay/wt/WO-1.0-03"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, "`.relay/` is not ignored by .gitignore"


def test_FR_1_0_11_debt032_full_gpu_bootstrap_output_committed():
    # DEBT-032: the full Colab output of `dev_bootstrap.sh --gpu` must show the GPU extras line with the GPU lock's
    # real SHA-256 (the earlier note quoted only the CPU lock's hash) and a zero exit code.
    assert GPU_OUTPUT.is_file(), f"{GPU_OUTPUT.relative_to(ROOT)} is missing (BLK-1.0-03)"
    text = GPU_OUTPUT.read_text(encoding="utf-8", errors="replace")
    expected = f"OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 {sha256(GPU_LOCK)}"
    assert expected in text.splitlines()
    assert re.search(r"^exit code: 0$", text, re.M)


def test_FR_1_0_11_debt033_parakeet_doc_names_the_gpu_in_file():
    # DEBT-033: the adapter doc must send a reader to phase0-gpu.in's compiled-against line, not to the lock header.
    packages = PARAKEET_DOC.read_text(encoding="utf-8").split("## Packages", 1)[1].split("\n## ", 1)[0]
    assert "requirements/aqis_lab/phase0-gpu.in" in packages and "compiled-against" in packages
    assert "its header names that lock's SHA-256" not in packages
    line = next(l for l in GPU_IN.read_text(encoding="utf-8").splitlines() if l.startswith("# compiled-against:"))
    assert line.split()[-1] == sha256(CPU_LOCK)


@pytest.mark.parametrize("debt", ["DEBT-032", "DEBT-033", "DEBT-034"])
def test_FR_1_0_11_debt_fragment_is_closed(debt):
    path = ROOT / "docs/progress/debt.d" / f"{debt}.md"
    assert path.is_file(), f"{debt} has no migrated fragment"
    record = fields(path)
    assert record.get("Status", "").split()[0] == "CLOSED" and record.get("Legacy") == "yes"
    assert record.get("Closed by", "").strip(), f"{debt} does not say what closed it"


def test_FR_1_0_13_every_order_has_summary_and_ledger():
    assert len(ORDERS) == 11
    ledger_keys = ("WO", "Date", "Model", "Model version", "Attempts", "Prompt tokens", "Output tokens", "Result",
                   "Seconds")
    for order in ORDERS:
        wo = order.stem
        channel = re.search(r"^channel:\s*(\w+)", order.read_text(encoding="utf-8"), re.M).group(1)
        assert (ROOT / "docs/outsourcing/returns" / wo / "summary.md").is_file(), f"{wo}: no summary"
        ledger = ROOT / "docs/outsourcing/ledger.d" / f"{wo}.md"
        assert ledger.is_file(), f"{wo}: no ledger fragment"
        record = fields(ledger)
        assert all(record.get(key) for key in ledger_keys), (wo, record)
        assert record["WO"] == wo and record["Result"] == "ACCEPTED"
        if channel == "api":
            assert (ROOT / "docs/outsourcing/returns" / wo / "steps.md").is_file(), f"{wo}: no step log"


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_NFR_1_0_01_tools_import_stdlib_only():
    files = [ROOT / rel for rel in STDLIB_TOOL_FILES]
    for folder in STDLIB_TOOL_DIRS:
        found = sorted((ROOT / folder).rglob("*.py"))
        assert found, f"{folder} has no Python files yet"
        files.extend(found)
    allowed = set(sys.stdlib_module_names) | REPOSITORY_ROOTS | {"__future__"}
    offenders = {}
    for path in files:
        assert path.is_file(), f"{path.relative_to(ROOT)} is missing"
        extra = imported_roots(path) - allowed
        if extra:
            offenders[path.relative_to(ROOT).as_posix()] = sorted(extra)
    assert offenders == {}
