"""WP-0.4 FR-0.4-04: deterministic mixing, excerpts, silence and recipe v1 (aqis_lab/packs/mix.py)."""
import decimal
import json
import math
import re
from fractions import Fraction

import numpy as np
import pytest

from aqis_packs_testutil import ROOT, seeded_noise, tone
from aqis_lab.packs import mix
from aqis_lab.packs.select import offset_for
from aqis_lab.registry.registry import RegistryRow

SPEECH = tone(24000, freq=210, amplitude=7000)
NOISE = seeded_noise(60000, seed=11, amplitude=4000)


def _row(clip_id, n):
    return RegistryRow(clip_id, "musan", f"{clip_id}.wav", "LicenseRef-public-domain", None, None, None, "noise",
                       "musan", (), "0" * 64, 16000, 1, n, None)


def _independent_gain_q24(speech, noise, snr_db):
    """The noise gain by the definition in SMOKE_PACK.md, computed here with its own decimal context."""
    ctx = decimal.Context(prec=60)
    ss = sum(int(x) * int(x) for x in speech)
    sn = sum(int(x) * int(x) for x in noise)
    ratio = ctx.exp(ctx.multiply(ctx.divide(decimal.Decimal(repr(snr_db)), 10), ctx.ln(decimal.Decimal(10))))
    g = ctx.sqrt(ctx.divide(decimal.Decimal(ss), ctx.multiply(decimal.Decimal(sn), ratio)))
    return int(ctx.multiply(g, 2 ** 24).to_integral_value(rounding=decimal.ROUND_HALF_EVEN))


def _mix(snr=10, offset=1000, speech=SPEECH):
    segment = NOISE[offset:offset + len(speech)]
    return mix.mix_clip(speech, segment, snr)


def test_FR_0_4_04_same_inputs_and_seed_byte_identical():
    first, second = _mix(), _mix()
    assert first.samples.dtype == np.int16 and np.array_equal(first.samples, second.samples)
    assert (first.noise_gain_q24, first.speech_gain_q24, first.achieved_snr_db) == (
        second.noise_gain_q24, second.speech_gain_q24, second.achieved_snr_db)
    noise_row = _row("musan-noise-free-sound-0001", len(NOISE))
    offset = offset_for(7, "smoke-mix-01", noise_row, len(SPEECH))
    assert offset == offset_for(7, "smoke-mix-01", noise_row, len(SPEECH))
    assert 0 <= offset <= len(NOISE) - len(SPEECH)


def test_FR_0_4_04_different_seed_changes_audio():
    noise_row = _row("musan-noise-free-sound-0001", len(NOISE))
    offsets = {seed: offset_for(seed, "smoke-mix-01", noise_row, len(SPEECH)) for seed in (1, 2, 3)}
    assert len(set(offsets.values())) == 3
    a, b = _mix(offset=offsets[1]), _mix(offset=offsets[2])
    assert not np.array_equal(a.samples, b.samples)


def test_FR_0_4_04_recipe_records_sources_snr_seed_gains():
    result = _mix(snr=5, offset=123)
    recipe = mix.mix_recipe("ls-test-clean-1-2-0003", "musan-noise-free-sound-0001", 5, 20260927, 123, len(SPEECH),
                            result)
    assert mix.recipe_problems(recipe) == []
    assert recipe["recipe_version"] == "1.0" and recipe["kind"] == "mix"
    assert recipe["source_clip_ids"] == ["ls-test-clean-1-2-0003", "musan-noise-free-sound-0001"]
    assert (recipe["snr_db"], recipe["seed"], recipe["noise_offset_samples"]) == (5, 20260927, 123)
    assert recipe["speech_gain_q24"] == 2 ** 24 and recipe["speech_gain"] == 1.0
    assert recipe["noise_gain"] == recipe["noise_gain_q24"] / 2 ** 24
    assert recipe["snr_definition"] == mix.SNR_DEFINITION and recipe["peak_limited"] is False
    json.dumps(recipe, allow_nan=False)
    for missing in ("noise_gain", "seed", "snr_db", "source_clip_ids", "noise_offset_samples"):
        broken = {k: v for k, v in recipe.items() if k != missing}
        assert any(missing in p for p in mix.recipe_problems(broken)), missing
    inconsistent = dict(recipe, noise_gain=0.5)
    assert any("noise_gain" in p for p in mix.recipe_problems(inconsistent))
    assert mix.recipe_problems(dict(recipe, extra=1))


def test_FR_0_4_04_clip_rebuilt_from_recipe_alone():
    offset = 4321
    result = _mix(snr=20, offset=offset)
    recipe = mix.mix_recipe("s", "n", 20, 9, offset, len(SPEECH), result)
    sources = {"s": SPEECH, "n": NOISE}
    assert np.array_equal(mix.render_recipe(recipe, sources.__getitem__), result.samples)
    excerpt = mix.excerpt_recipe("n", 9, 500, 8000)
    assert np.array_equal(mix.render_recipe(excerpt, sources.__getitem__), NOISE[500:8500])
    silence = mix.silence_recipe(1600)
    assert np.array_equal(mix.render_recipe(silence, sources.__getitem__), np.zeros(1600, dtype=np.int16))
    with pytest.raises(mix.RenderError, match="gains"):
        mix.render_recipe(dict(recipe, snr_db=10), sources.__getitem__)


def test_FR_0_4_04_snr_matches_definition():
    for snr in (5, 10, 20, 0, 7.5):
        result = _mix(snr=snr, offset=2000)
        assert not result.peak_limited
        noise_in_output = result.samples.astype(np.int64) - SPEECH.astype(np.int64)
        ps = sum(int(x) ** 2 for x in SPEECH)
        pn = sum(int(x) ** 2 for x in noise_in_output)
        measured = 10 * math.log10(Fraction(ps, pn))
        assert abs(measured - snr) < 0.01, (snr, measured)
        assert abs(result.achieved_snr_db - snr) < 0.001


def test_FR_0_4_04_gains_equal_independent_decimal_computation():
    for snr in (5, 10, 20, 12.25):
        segment = NOISE[3000:3000 + len(SPEECH)]
        result = mix.mix_clip(SPEECH, segment, snr)
        assert result.noise_gain_q24 == _independent_gain_q24(SPEECH, segment, snr)
        expected = (SPEECH.astype(np.int64) * 2 ** 24 + segment.astype(np.int64) * result.noise_gain_q24 + 2 ** 23) >> 24
        assert np.array_equal(result.samples.astype(np.int64), expected)


def test_FR_0_4_04_peak_limit_keeps_snr_and_is_recorded():
    loud = tone(24000, freq=210, amplitude=30000)
    segment = seeded_noise(24000, seed=3, amplitude=30000)
    result = mix.mix_clip(loud, segment, 0)
    assert result.peak_limited and result.speech_gain_q24 < 2 ** 24
    assert int(np.max(np.abs(result.samples.astype(np.int64)))) <= 32767
    assert abs(result.achieved_snr_db - 0) < 0.001
    recipe = mix.mix_recipe("s", "n", 0, 1, 0, 24000, result)
    assert recipe["peak_limited"] is True and mix.recipe_problems(recipe) == []
    assert np.array_equal(mix.render_recipe(recipe, {"s": loud, "n": segment}.__getitem__), result.samples)


def test_FR_0_4_04_rejects_noise_shorter_than_speech():
    with pytest.raises(mix.RenderError, match="noise segment has 100 samples, the speech clip 24000"):
        mix.mix_clip(SPEECH, NOISE[:100], 5)
    with pytest.raises(mix.RenderError, match="silent"):
        mix.mix_clip(SPEECH, np.zeros(len(SPEECH), dtype=np.int16), 5)
    with pytest.raises(mix.RenderError, match="offset"):
        mix.render_recipe(mix.excerpt_recipe("n", 1, len(NOISE) - 10, 100), {"n": NOISE}.__getitem__)


def test_FR_0_4_04_recipe_doc_matches_schema():
    text = (ROOT / "docs" / "data" / "SMOKE_PACK.md").read_text(encoding="utf-8")
    section = text.split("## Recipe v1", 1)[1].split("\n## ", 1)[0]
    documented = {}
    for kind, field in re.findall(r"^\| (mix|excerpt|silence|all) \| `([a-z0-9_]+)` \|", section, flags=re.M):
        documented.setdefault(kind, set()).add(field)
    schema = mix.RECIPE_SCHEMA
    for kind in ("mix", "excerpt", "silence"):
        fields = set(schema["$defs"][kind]["properties"])
        assert documented.get("all", set()) | documented.get(kind, set()) == fields, kind
    assert mix.SNR_DEFINITION in section
