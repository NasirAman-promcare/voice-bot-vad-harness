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


# --- The adapter on a machine without a GPU or without NeMo (this cloud VM) ---
import json

import numpy as np
import pytest

from aqis_lab import platform as lp
from aqis_lab.adapters import base
from aqis_lab.adapters.parakeet_unified import ParakeetUnifiedAdapter
from aqis_lab.contracts.validate import validate_event
from aqis_runner_testutil import make_system_tree, nvidia_smi_script, write_command
from aqis_testutil import parse_lock


def sink():
    return base.EventSink(run_id="run-parakeet-test", run_card_id="f" * 64, host_id="cloud-vm:test")


def gpu_system(tmp_path):
    """The cloud VM with a stand-in nvidia-smi that reports a Tesla T4 (the GPU test double)."""
    root = make_system_tree(tmp_path / "sys")
    write_command(root / "bin", "nvidia-smi", nvidia_smi_script(["Tesla T4"]))
    return lp.SystemView(root=root, environ={"PATH": str(root / "bin"), "CLAUDE_CODE_REMOTE": "true"},
                         path=str(root / "bin"))


def test_FR_0_7_03_refuses_without_gpu():
    # Must-catch 3: this VM has no GPU; the adapter refuses with a platform error and says it is never skipped.
    assert lp.gpu_type(lp.SystemView.real()) is None
    adapter = ParakeetUnifiedAdapter()
    with pytest.raises(base.AdapterPlatformError) as info:
        adapter.preflight()
    assert info.value.code == "parakeet-no-gpu"
    assert "no GPU" in info.value.message and "never skipped" in info.value.message
    s = sink()
    with pytest.raises(base.AdapterPlatformError):
        base.guarded(adapter, s, None, "open", adapter.open)
    error = json.loads(s.data())
    validate_event(error)
    assert error["component"] == "heavy_stt" and error["payload"]["code"] == "parakeet-no-gpu"


def test_FR_0_7_03_refuses_without_nemo(tmp_path):
    adapter = ParakeetUnifiedAdapter(system=gpu_system(tmp_path))
    with pytest.raises(base.AdapterPlatformError) as info:
        adapter.preflight()
    assert info.value.code == "parakeet-no-nemo"
    assert "requirements/aqis_lab/phase0-gpu.txt" in info.value.message and "--gpu" in info.value.message


def test_FR_0_7_03_parakeet_model_block_records_pinned_versions():
    block = base.check_model_block(ParakeetUnifiedAdapter().model_block())
    gpu = parse_lock((ROOT / "requirements/aqis_lab/phase0-gpu.txt").read_text(encoding="utf-8"))
    assert block["family"] == "nemo" and block["name"] == "nvidia/parakeet-unified-en-0.6b"
    assert block["version"] == "fe53cd885760c96b6a5f51a0bfd362cb4584a98b"
    assert block["checksum"] == "ec23ed9150c8fde49072c3e2d61678ab903dbcef389d658db833420cbc1da35b"
    s = block["settings"]
    assert s["mode"] == "offline" and s["device"] == "cuda" and s["batch_size"] == 1 and s["dtype"] == "float32"
    assert s["nemo"] == gpu["nemo-toolkit"]["version"] and s["torch"] == gpu["torch"]["version"]
    assert ParakeetUnifiedAdapter.component == "heavy_stt"


class TimedStandIn(ParakeetUnifiedAdapter):
    """GPU test double (rule 30 allows one for GPUs): replaces only the CUDA call and the synchronisation, so the
    adapter's own timing code runs unchanged."""

    def __init__(self, clock_steps):
        super().__init__()
        self.calls, self._steps = [], iter(clock_steps)
        self.gpu = "Tesla T4"
        self.clock = lambda: next(self._steps)

    def _synchronize(self):
        self.calls.append("sync")

    def _run(self, audio):
        self.calls.append(("run", audio.dtype.name, len(audio)))
        return "hello world"


def test_FR_0_7_06_compute_delay_rows_hold_gpu_and_per_clip_time():
    adapter = TimedStandIn(clock_steps=[1_000_000, 251_000_000])
    samples = np.full(32000, 16384, dtype=np.int16)
    s = sink()
    fields = adapter.process_clip_timed("clip-9", samples, s)
    assert adapter.calls == ["sync", ("run", "float32", 32000), "sync"]
    assert fields["processing_ms"] == 250.0 and fields["rtf"] == 0.125 and fields["gpu"] == "Tesla T4"
    assert fields["text"] == "hello world" and fields["audio_s"] == 2.0
    final = json.loads(s.data())
    validate_event(final)
    assert final["event_type"] == "final" and final["payload"] == {"text": "hello world"}


def test_FR_0_7_06_audio_is_scaled_to_float_range():
    adapter = TimedStandIn(clock_steps=[0, 1])
    seen = {}
    adapter._run = lambda audio: seen.setdefault("audio", audio) is None or "x"
    adapter.process_clip_timed("clip-1", np.array([-32768, 0, 16384], dtype=np.int16), sink())
    assert seen["audio"].tolist() == [-1.0, 0.0, 0.5]


def test_FR_0_7_06_warm_up_not_timed():
    # The compute-delay task transcribes its first clip once untimed, then times every clip (question 7).
    from aqis_lab.runner.tasks import TASKS
    from aqis_adapters_testutil import smoke_clip
    task = TASKS["parakeet-compute-delay"]
    task.configure(model_cache=None)
    task.adapter = TimedStandIn(clock_steps=[0, 5_000_000, 10_000_000, 12_000_000])
    task.warmed = False
    s = sink()
    for clip_id in ("tts-smoke-04", "smoke-mix-01"):
        clip, wav = smoke_clip(clip_id)
        fields = task.run_clip(clip, wav, s)
        assert fields["gpu"] == "Tesla T4"
    runs = [c for c in task.adapter.calls if c != "sync"]
    assert len(runs) == 3, "one untimed warm-up plus one timed run per clip"
    assert task.adapter.calls[0][0] == "run" and task.adapter.calls[1:4] == ["sync", runs[1], "sync"]
    records = [json.loads(l) for l in s.data().splitlines()]
    assert [r["event_type"] for r in records] == ["clip_started", "final", "clip_finished"] * 2
