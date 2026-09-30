"""FR-0.7-03 and FR-0.7-06: the Parakeet Unified adapter (offline mode on a GPU through NeMo) and the GPU
compute-delay run.

This cloud VM has no GPU and no NeMo, so the tests here prove the refusals and the isolation; the GPU path itself
runs in the `colab`/`gpu` tests (test_aqis_smoke_live.py) during OC-0.7-01.
"""
import ast
import subprocess
import sys

from aqis_testutil import ROOT

GPU_ONLY_MODULES = ("torch", "nemo", "lightning", "hydra", "omegaconf")


def _imported_top_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if fname in ("import_module", "__import__"):
                names.add(node.args[0].value.split(".")[0])
    return names


def test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter():
    # Rule 40: GPU-only packages are imported only inside GPU adapters.
    offenders = []
    for top in ("aqis_lab", "tools"):
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "aqis_lab/adapters/parakeet_unified.py":
                continue
            found = _imported_top_modules(path) & set(GPU_ONLY_MODULES)
            if found:
                offenders.append((rel, sorted(found)))
    assert offenders == []
    # Importing the adapters package (and the runner's task table) loads no adapter's heavy dependency.
    code = ("import sys, aqis_lab.adapters, aqis_lab.runner.tasks; "
            f"print(sorted(m for m in {GPU_ONLY_MODULES + ('vosk', 'webrtcvad', 'vad_adapters')!r} "
            "if m in sys.modules))")
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]"
