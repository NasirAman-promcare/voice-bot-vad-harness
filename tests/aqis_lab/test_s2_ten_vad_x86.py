"""WP-1.2 x86 TEN VAD run: where the harness adapter finds the library, and what the Colab notebook's vad stage runs."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from aqis_lab.live import stages, vad
from aqis_lab.live.config import load_config

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK = REPO / "notebooks" / "aqis_lab" / "s2_live_stack.ipynb"


# ---- smoothing equal to Silero v5
def test_s2_ten_vad_is_smoothed_exactly_like_silero_v5():
    """The x86 TEN VAD run must be apples to apples with Silero v5: the same minimum speech and silence in milliseconds."""
    cfg = load_config(REPO / "config" / "aqis_lab" / "s2.yaml")
    for key in ("min_speech_ms", "min_silence_ms"):
        assert cfg.vad["ten_vad"][key] == cfg.vad["silero_v5"][key]
    assert (cfg.vad["ten_vad"]["min_speech_ms"], cfg.vad["ten_vad"]["min_silence_ms"]) == (64, 100)


# ---- the shared library of the pip package -----------------------------------------------------------------------
def fake_ten_vad_package(root, with_library=True):
    package = root / "ten_vad"
    (package / "lib" / "Linux" / "x64").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    if with_library:
        (package / "lib" / "Linux" / "x64" / "libten_vad.so").write_bytes(b"\x7fELF")
    return package


def test_s2_ten_vad_library_is_found_inside_the_installed_package(tmp_path, monkeypatch):
    package = fake_ten_vad_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "ten_vad", raising=False)
    assert stages.ten_vad_library() == package / "lib" / "Linux" / "x64" / "libten_vad.so"


def test_s2_ten_vad_without_its_library_is_an_error_naming_the_package(tmp_path, monkeypatch):
    fake_ten_vad_package(tmp_path, with_library=False)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "ten_vad", raising=False)
    with pytest.raises(stages.StageError, match="libten_vad.so"):
        stages.ten_vad_library()


def test_s2_the_library_path_is_set_for_the_adapter_unless_the_owner_set_one(tmp_path, monkeypatch):
    package = fake_ten_vad_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "ten_vad", raising=False)
    monkeypatch.delenv("TEN_VAD_LIB_PATH", raising=False)
    stages.export_ten_vad_library()
    assert Path(stages.os.environ["TEN_VAD_LIB_PATH"]) == package / "lib" / "Linux" / "x64" / "libten_vad.so"
    monkeypatch.setenv("TEN_VAD_LIB_PATH", "/somewhere/else.so")
    stages.export_ten_vad_library()
    assert stages.os.environ["TEN_VAD_LIB_PATH"] == "/somewhere/else.so"


def test_s2_ten_vad_smoothing_turns_16_ms_frames_into_whole_frames():
    smoother = vad.HysteresisSmoother(16, 64, 100)             # 4 frames of speech to start, ceil(100 / 16) = 7 of silence to stop
    flags = np.array([1] * 3 + [0] * 5 + [1] * 4 + [0] * 7 + [1], dtype=bool)
    # speech starts on the 4th speech frame (index 11) and stops on the 7th silent frame (index 18); 3 speech frames never start it
    assert smoother.apply(flags).astype(int).tolist() == [0] * 11 + [1] * 7 + [0, 0]


# ---- the notebook's vad stage ----------------------------------------------------------------------------------
def code_cells():
    return ["".join(c["source"]) for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"]


def test_s2_notebook_offers_a_vad_stage_and_every_cell_compiles():
    cells = code_cells()
    assert 'STAGES = ("prep", "vad", "smoke", "emotion", "report")' in "\n".join(cells)
    for source in cells:
        compile(source, "cell", "exec")


def test_s2_notebook_vad_stage_runs_only_ten_vad_on_cpu_after_installing_libcxx():
    text = "\n".join(code_cells())
    branch = text[text.index('elif STAGE == "vad"'):text.index('elif STAGE == "report"')]
    lines = [line for line in branch.splitlines() if not line.strip().startswith("#")]
    assert branch.count('"--models"') == 1 and 'live(LIVE_PY, "vad", "--models", "ten_vad"' in branch
    assert not any("MODELS" in line or "silero" in line or "firered" in line or "webrtc" in line for line in lines)
    install = text.index("apt-get install -y libc++1")
    assert "apt-get update" in text[:install] and install < text.index('"--models", "ten_vad"')
    assert 'platform.machine() == "x86_64"' in text and "nvidia-smi" in text.split('if STAGE == "vad":')[1].split("else:")[1]
