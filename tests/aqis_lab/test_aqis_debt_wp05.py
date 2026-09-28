"""Accepted debt with target WP-0.5 (owner decision, WP-0.5 question 13 (a)); test-only additions.

DEBT-009 (WP-0.3-F03): the wiring of the normaliser version check. A real installed-package record of another
whisper-normalizer version (a dist-info folder) is put first on the import path of a subprocess, so
importlib.metadata reports that version exactly as it would for a different install.
DEBT-011 (WP-0.4-F04): the one-clip-per-speaker rule of pack selection, with a registry where most candidates share
one speaker, so the rule, not luck, keeps the speakers distinct.
"""
import dataclasses
import os
import subprocess
import sys

import pytest

from aqis_lab.packs import select, spec as pack_spec
from aqis_lab.registry.importers import build_registry
from aqis_packs_testutil import make_world, write_spec
from aqis_testutil import ROOT

OTHER_VERSION = "0.1.2"


def other_version_path(tmp_path):
    site = tmp_path / "site"
    info = site / f"whisper_normalizer-{OTHER_VERSION}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: whisper-normalizer\nVersion: {OTHER_VERSION}\n",
                                   encoding="utf-8")
    return site


def python_with(site, *args):
    env = dict(os.environ, PYTHONPATH=str(site))
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)


def test_FR_0_3_01_normaliser_checks_package_version_on_first_use(tmp_path):
    site = other_version_path(tmp_path)
    code = ("import importlib.metadata as m; from aqis_lab.scoring import normalise as N\n"
            "print('installed', m.version('whisper-normalizer'))\n"
            "try:\n    N.normalise('Hello, World')\nexcept N.NormaliserVersionError as exc:\n    print('refused:', exc)\n")
    proc = python_with(site, "-c", code)
    assert proc.returncode == 0, proc.stderr
    assert f"installed {OTHER_VERSION}" in proc.stdout
    assert "refused:" in proc.stdout and OTHER_VERSION in proc.stdout and "0.1.1" in proc.stdout
    clean = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert "refused:" not in clean.stdout, "with the pinned version installed, normalising works"


def test_FR_0_3_06_score_turns_normaliser_version_error_into_exit_2(tmp_path):
    ref = tmp_path / "ref.csv"
    hyp = tmp_path / "hyp.csv"
    ref.write_text("clip_id,text\nclip-a,hello world\n", encoding="utf-8")
    hyp.write_text("run_card_id,clip_id,text\n" + "a" * 64 + ",clip-a,hello world\n", encoding="utf-8")
    proc = python_with(other_version_path(tmp_path), "-m", "aqis_lab", "score", "--ref", str(ref), "--hyp", str(hyp),
                       "--out", str(tmp_path / "out"))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.startswith("ERROR:") and OTHER_VERSION in proc.stderr and "Traceback" not in proc.stderr
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("world"))


def test_FR_0_4_03_one_clip_per_speaker_when_candidates_share_a_speaker(tmp_path, world):
    rows = build_registry(world.datasets(), world.cache, world.repo)
    clean = [r for r in rows if r.split == "test-clean"]
    keep, seen = set(), set()
    for row in clean:                                      # one row each of 6 speakers keeps its own speaker
        if row.speaker_id not in seen and len(seen) < 6:
            seen.add(row.speaker_id)
            keep.add(row.clip_id)
    shared = [r if r.split != "test-clean" or r.clip_id in keep else dataclasses.replace(r, speaker_id="shared")
              for r in rows]
    assert sum(1 for r in shared if r.speaker_id == "shared") >= 2 * len(keep)
    plan = select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "spec.yaml")), shared, world.datasets())
    for category in ("test-clean", "noisy"):
        speakers = [c.sources[0].speaker_id for c in plan if c.category == category]
        assert speakers and len(speakers) == len(set(speakers)), (category, speakers)
