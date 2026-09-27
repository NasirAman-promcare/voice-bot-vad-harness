"""WP-0.4 FR-0.4-03: pack spec and seeded selection (aqis_lab/packs/spec.py, select.py)."""
import dataclasses
import random
from pathlib import Path

import pytest
import yaml

from aqis_packs_testutil import ROOT, make_world, spec_dict, write_spec, wav_bytes, tone, make_tts_folder
from aqis_lab.packs import select, spec as pack_spec
from aqis_lab.registry.importers import build_registry


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("world"))


@pytest.fixture(scope="module")
def rows(world):
    return build_registry(world.datasets(), world.cache, world.repo)


def _plan(tmp_path, world, rows, **changes):
    spec = pack_spec.load_spec(write_spec(tmp_path / "spec.yaml", **changes))
    return select.plan_pack(spec, rows, world.datasets())


def test_FR_0_4_03_smoke_spec_declares_exact_composition():
    doc = yaml.safe_load((ROOT / "packs" / "specs" / "smoke_v1.yaml").read_text(encoding="utf-8"))
    counts = {c["name"]: c["count"] for c in doc["categories"]}
    assert counts == {"test-clean": 20, "test-other": 10, "noisy": 10, "non-speech": 10, "tts": 10}
    by_name = {c["name"]: c for c in doc["categories"]}
    assert [p["from"]["split"] for p in by_name["test-clean"]["parts"]] == ["test-clean"]
    assert [p["from"]["split"] for p in by_name["test-other"]["parts"]] == ["test-other"]
    (mix,) = by_name["noisy"]["parts"]
    assert mix["kind"] == "mix" and sorted(set(mix["snr_db"])) == [5, 10, 20] and len(mix["snr_db"]) == 10
    assert mix["speech"]["source"] == "librispeech" and mix["noise"]["source"] == "musan"
    kinds = {}
    for part in by_name["non-speech"]["parts"]:
        kind = part.get("label")
        kinds[kind] = kinds.get(kind, 0) + (len(part["seconds"]) if part["kind"] == "silence" else part["count"])
    assert set(kinds) == {"noise", "music", "silence"} and sum(kinds.values()) == 10
    (tts,) = by_name["tts"]["parts"]
    assert tts["from"] == {"source": "tts", "split": "tts", "min_seconds": 3, "max_seconds": 8}
    assert pack_spec.load_spec(ROOT / "packs" / "specs" / "smoke_v1.yaml").manifest_id == "smoke"


def test_FR_0_4_03_builder_selects_exact_counts(tmp_path, world, rows):
    plan = _plan(tmp_path, world, rows)
    counts = {}
    for clip in plan:
        counts[clip.category] = counts.get(clip.category, 0) + 1
    assert counts == {"test-clean": 4, "test-other": 2, "noisy": 3, "non-speech": 3, "tts": 2}
    assert [c.category for c in plan] == sorted((c.category for c in plan),
                                                 key=["test-clean", "test-other", "noisy", "non-speech", "tts"].index)
    kinds = sorted(c.kind for c in plan if c.category == "non-speech")
    assert kinds == ["excerpt", "excerpt", "silence"]
    assert [c.snr_db for c in plan if c.kind == "mix"] == [5, 10, 20]
    assert {c.clip_id for c in plan if c.kind == "mix"} == {"tpack-mix-01", "tpack-mix-02", "tpack-mix-03"}


def test_FR_0_4_03_fails_when_too_few_candidates(tmp_path, world, rows):
    spec = spec_dict()
    spec["categories"][1]["count"] = 99
    spec["categories"][1]["parts"][0]["count"] = 99
    with pytest.raises(select.SelectionError, match="test-other.*needs 99.*found 6"):
        select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "a.yaml", spec)), rows, world.datasets())
    spec = spec_dict()
    spec["categories"][2]["count"] = 6
    spec["categories"][2]["parts"][0]["snr_db"] = [5, 5, 10, 10, 20, 20]    # only 4 background noises exist
    with pytest.raises(select.SelectionError, match="noisy.*noise"):
        select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "b.yaml", spec)), rows, world.datasets())


def test_FR_0_4_03_selection_ignores_registry_row_order(tmp_path, world, rows):
    shuffled = list(rows)
    random.Random(4).shuffle(shuffled)
    assert _plan(tmp_path, world, rows) == _plan(tmp_path, world, shuffled)
    assert _plan(tmp_path, world, list(reversed(rows))) == _plan(tmp_path, world, rows)


def test_FR_0_4_03_selection_changes_with_seed(tmp_path, world, rows):
    a = _plan(tmp_path, world, rows, seed=1)
    b = _plan(tmp_path, world, rows, seed=2)
    ids = lambda plan: [(c.clip_id, tuple(s.clip_id for s in c.sources), c.offset) for c in plan]
    assert ids(a) != ids(b)
    assert ids(a) == ids(_plan(tmp_path, world, rows, seed=1))


def test_FR_0_4_03_selection_key_is_the_documented_hash(tmp_path, world, rows):
    """The first test-clean clip is the candidate with the smallest documented SHA-256 key, recomputed here."""
    import hashlib
    plan = _plan(tmp_path, world, rows)
    candidates = [r for r in rows if r.split == "test-clean" and 1 * 16000 <= r.n_samples <= 2 * 16000]
    key = lambda r: hashlib.sha256(f"aqis-pack-select-v1|20260927|test-clean|0|take|{r.clip_id}".encode()).hexdigest()
    assert plan[0].clip_id == min(candidates, key=key).clip_id


def test_FR_0_4_03_distinct_speakers_and_utterances(tmp_path, world, rows):
    plan = _plan(tmp_path, world, rows)
    for category in ("test-clean", "test-other", "noisy"):
        speakers = [c.sources[0].speaker_id for c in plan if c.category == category]
        assert len(speakers) == len(set(speakers)), category
    used = [s.clip_id for c in plan for s in c.sources]
    assert len(used) == len(set(used))


def test_FR_0_4_03_tts_clips_need_3_to_8_seconds(tmp_path):
    world = make_world(tmp_path / "w", clean=(6, 2), other=(3, 1), tts_count=2)
    base = world.repo / "data" / "tts_smoke"
    record = (base / "GENERATION.md").read_text()
    import hashlib
    old = hashlib.sha256((base / "02.wav").read_bytes()).hexdigest()
    long_clip = wav_bytes(tone(16000 * 9))                    # 9 s: longer than the 8 s the spec allows
    (base / "02.wav").write_bytes(long_clip)
    (base / "GENERATION.md").write_text(record.replace(old, hashlib.sha256(long_clip).hexdigest()))
    rows = build_registry(world.datasets(), world.cache, world.repo)
    with pytest.raises(select.SelectionError, match="tts.*needs 2.*found 1"):
        select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "s.yaml")), rows, world.datasets())


def test_FR_0_4_03_licence_policy_keeps_share_alike_out(tmp_path, world, rows):
    music = [r for r in rows if r.split == "music"]
    others = [r for r in rows if r.split != "music"]
    share_alike = [dataclasses.replace(r, licence="CC-BY-SA-4.0") for r in music]
    with pytest.raises(select.SelectionError, match="non-speech.*music"):
        select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "s.yaml")), others + share_alike,
                         world.datasets())
    spec = spec_dict(licence_policy={"allow_share_alike": True, "allow_non_commercial": False})
    plan = select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "t.yaml", spec)), others + share_alike,
                            world.datasets())
    assert any(s.licence == "CC-BY-SA-4.0" for c in plan for s in c.sources)


def test_FR_0_4_03_excerpts_only_from_non_speech_sources(tmp_path, world, rows):
    spec = spec_dict()
    spec["categories"][3]["parts"][0]["from"] = {"source": "librispeech", "split": "test-other"}
    with pytest.raises(select.SelectionError, match="excerpt.*speech"):
        select.plan_pack(pack_spec.load_spec(write_spec(tmp_path / "s.yaml", spec)), rows, world.datasets())


def test_FR_0_4_03_derived_id_must_not_be_a_registry_id(tmp_path, world, rows):
    clash = dataclasses.replace(rows[0], clip_id="tpack-mix-02")
    with pytest.raises(select.SelectionError, match="tpack-mix-02.*registry"):
        _plan(tmp_path, world, rows + [clash])


@pytest.mark.parametrize("change,message", [
    (lambda s: s.update(surprise=1), "surprise"),
    (lambda s: s["categories"][0].update(count=5), "count 5.*parts give 4"),
    (lambda s: s["categories"][3]["parts"][2].update(seconds=[0.00001]), "whole number of samples"),
    (lambda s: s.update(created_utc="2026-02-30T00:00:00Z"), "created_utc"),
    (lambda s: s.update(version="1.0"), "version"),
    (lambda s: s["categories"].append(dict(s["categories"][0])), "test-clean.*twice"),
    (lambda s: s["categories"][0]["parts"][0]["from"].update(min_seconds=3, max_seconds=2), "min_seconds"),
])
def test_FR_0_4_03_spec_is_checked_strictly(tmp_path, change, message):
    spec = spec_dict()
    change(spec)
    with pytest.raises(pack_spec.SpecError, match=message):
        pack_spec.load_spec(write_spec(tmp_path / "s.yaml", spec))


def test_FR_0_4_03_spec_rejects_duplicate_keys(tmp_path):
    path = write_spec(tmp_path / "s.yaml")
    path.write_text(path.read_text() + "seed: 5\n", encoding="utf-8")
    with pytest.raises(pack_spec.SpecError, match="duplicate key 'seed'"):
        pack_spec.load_spec(path)
