"""Colab-only checks (marker `colab`; never in the fast suite). The owner runs them in OC-0.5-01, after the launcher:

    !cd /content/aqis && .venv/bin/python -m pytest tests/aqis_lab -q -m colab

They need the Drive mounted at /content/drive with MyDrive/AQIS_LAB present (docs/colab/COLAB_RUNBOOK.md).
"""
import os
from pathlib import Path

import pytest

from aqis_lab import platform as lp

pytestmark = pytest.mark.colab

DRIVE_MOUNT = Path(os.environ.get("AQIS_DRIVE_MOUNT", "/content/drive"))


def test_FR_0_5_01_colab_runtime_detected():
    info = lp.machine_info()
    assert info.platform == "colab", info
    assert "environment variable COLAB_RELEASE_TAG is set" in info.signals
    assert info.cpu_model and info.os and info.architecture == "x86_64"
    assert DRIVE_MOUNT in lp.drive_mounts(), f"{DRIVE_MOUNT} is not a fuse.drive mount"
