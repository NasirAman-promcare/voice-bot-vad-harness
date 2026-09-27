"""Derived clips: noisy mixes at a stated SNR, excerpts and digital silence, and recipe v1 that reproduces each one.

CAPABILITIES:
  CAP-PACK-003: mix_clip() mixes a speech clip with an equally long noise segment at a target SNR using only exact integer arithmetic and Python's decimal module (the noise gain sqrt(Ss / (Sn * 10^(SNR/10))) at 50 digits, quantised to 24 fractional bits; one common scale on both gains when the mix would leave the 16-bit range, which keeps the SNR and is recorded), so the same inputs give the same samples on every machine; mix_recipe(), excerpt_recipe() and silence_recipe() record everything needed to rebuild a clip (source clip IDs, SNR, seed, offset, length, exact and quantised gains); recipe_problems() checks a recipe against recipe.v1.json and its own consistency; render_recipe() rebuilds a clip from its recipe and source samples alone and refuses a recipe whose gains do not follow from its SNR [tests: test_FR_0_4_04_same_inputs_and_seed_byte_identical, test_FR_0_4_04_different_seed_changes_audio, test_FR_0_4_04_recipe_records_sources_snr_seed_gains, test_FR_0_4_04_clip_rebuilt_from_recipe_alone, test_FR_0_4_04_snr_matches_definition, test_FR_0_4_04_gains_equal_independent_decimal_computation, test_FR_0_4_04_peak_limit_keeps_snr_and_is_recorded, test_FR_0_4_04_rejects_noise_shorter_than_speech, test_FR_0_4_04_recipe_doc_matches_schema]
INPUTS AND OUTPUTS: int16 sample arrays, an SNR in dB, clip IDs, seed and offsets in; int16 samples, MixResult and
  recipe dicts out; RenderError.
CONTRACTS: recipe v1.0 (aqis_lab/packs/schemas/recipe.v1.json, docs/data/SMOKE_PACK.md "Recipe v1").
INVARIANTS:
  - No floating-point maths library is used for audio: sums of squares are exact integers, gains come from decimal
    (software arithmetic), and samples are mixed with 64-bit integer multiply, add and shift.
  - Speech gain is exactly 1 unless the peak limit applies; the SNR is the same with or without the limit.
NOT IN SCOPE:
  - Choosing sources and offsets (aqis_lab/packs/select.py); writing files (aqis_lab/packs/build.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-04 created.
"""
import decimal
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aqis_lab.registry.datasets import schema_problems

RECIPE_SCHEMA = json.loads((Path(__file__).resolve().parent / "schemas" / "recipe.v1.json").read_text(encoding="utf-8"))
RECIPE_VERSION = "1.0"
Q = 24
ONE = 1 << Q
HALF = 1 << (Q - 1)
INT16_MAX = 32767
INT16_MIN = -32768
SNR_DEFINITION = ("SNR = 10*log10(Ps/Pn), where Ps and Pn are the mean squares of the 16-bit sample values of the whole "
                  "speech clip and of the equally long noise segment, each multiplied by its gain")
_CTX = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN, Emax=999999, Emin=-999999)


class RenderError(ValueError):
    """A derived clip cannot be made or rebuilt as its recipe says."""


@dataclass(frozen=True)
class MixResult:
    samples: np.ndarray
    speech_gain_q24: int
    noise_gain_q24: int
    peak_limited: bool
    achieved_snr_db: float


def _int16(array, what):
    array = np.asarray(array)
    if array.dtype != np.int16 or array.ndim != 1:
        raise RenderError(f"{what} must be a one-dimensional int16 array, got {array.dtype} {array.shape}")
    return array.astype(np.int64)


def _sum_squares(x):
    if len(x) >= 1 << 32:
        raise RenderError(f"clip of {len(x)} samples is too long for exact 64-bit sums of squares")
    return int(np.dot(x, x))


def _decimal(number):
    return decimal.Decimal(repr(number)) if isinstance(number, float) else decimal.Decimal(number)


def _power_ratio(snr_db):
    """10^(SNR/10) in the 50-digit context (exp and ln are correctly rounded by the decimal module)."""
    return _CTX.exp(_CTX.multiply(_CTX.divide(_decimal(snr_db), 10), _CTX.ln(decimal.Decimal(10))))


def _achieved(ss, sn, a, b):
    ratio = _CTX.divide(_CTX.multiply(decimal.Decimal(a * a), ss), _CTX.multiply(decimal.Decimal(b * b), sn))
    value = _CTX.multiply(10, _CTX.log10(ratio))
    return float(value.quantize(decimal.Decimal("0.0001"), rounding=decimal.ROUND_HALF_EVEN, context=_CTX))


def _combine(s, n, a, b):
    return (s * a + n * b + HALF) >> Q


def mix_clip(speech, noise_segment, snr_db):
    """Mix speech with an equally long noise segment at snr_db; see the module header for the arithmetic."""
    s = _int16(speech, "speech clip")
    n = _int16(noise_segment, "noise segment")
    if len(n) != len(s):
        raise RenderError(f"noise segment has {len(n)} samples, the speech clip {len(s)}; they must be equal")
    ss, sn = _sum_squares(s), _sum_squares(n)
    if ss == 0:
        raise RenderError("speech clip is silent; an SNR cannot be set")
    if sn == 0:
        raise RenderError("noise segment is silent; an SNR cannot be set")
    gain = _CTX.sqrt(_CTX.divide(decimal.Decimal(ss), _CTX.multiply(decimal.Decimal(sn), _power_ratio(snr_db))))
    a = ONE
    b = int(_CTX.multiply(gain, ONE).to_integral_value(rounding=decimal.ROUND_HALF_EVEN, context=_CTX))
    if b < 1:
        raise RenderError(f"noise gain {gain} rounds to 0 at {Q} fractional bits; the SNR {snr_db} dB is too high "
                          f"for this noise")
    out = _combine(s, n, a, b)
    limited = False
    if out.max() > INT16_MAX or out.min() < INT16_MIN:
        limited = True
        peak = int(np.max(np.abs(s * a + n * b)))
        scale = _CTX.divide(decimal.Decimal(INT16_MAX * ONE), decimal.Decimal(peak))
        a = int(_CTX.multiply(a, scale).to_integral_value(rounding=decimal.ROUND_FLOOR, context=_CTX))
        b = int(_CTX.multiply(b, scale).to_integral_value(rounding=decimal.ROUND_FLOOR, context=_CTX))
        if a < 1 or b < 1:
            raise RenderError("peak limiting would reduce a gain to 0")
        out = _combine(s, n, a, b)
        if out.max() > INT16_MAX or out.min() < INT16_MIN:
            raise RenderError("mix still leaves the 16-bit range after peak limiting")
    return MixResult(out.astype(np.int16), a, b, limited, _achieved(ss, sn, a, b))


def mix_recipe(speech_id, noise_id, snr_db, seed, noise_offset, length, result):
    return {"recipe_version": RECIPE_VERSION, "kind": "mix", "source_clip_ids": [speech_id, noise_id],
            "speech_clip_id": speech_id, "noise_clip_id": noise_id, "snr_db": snr_db, "seed": seed,
            "noise_offset_samples": noise_offset, "length_samples": length, "snr_definition": SNR_DEFINITION,
            "speech_gain": result.speech_gain_q24 / ONE, "noise_gain": result.noise_gain_q24 / ONE,
            "speech_gain_q24": result.speech_gain_q24, "noise_gain_q24": result.noise_gain_q24,
            "peak_limited": result.peak_limited, "achieved_snr_db": result.achieved_snr_db}


def excerpt_recipe(source_id, seed, offset, length):
    return {"recipe_version": RECIPE_VERSION, "kind": "excerpt", "source_clip_ids": [source_id], "seed": seed,
            "offset_samples": offset, "length_samples": length}


def silence_recipe(length):
    return {"recipe_version": RECIPE_VERSION, "kind": "silence", "source_clip_ids": [], "length_samples": length}


def recipe_problems(recipe):
    """Every problem of a recipe (schema of its kind, then consistency), as 'pointer: message' strings."""
    if not isinstance(recipe, dict):
        return [f"(recipe): not an object ({type(recipe).__name__})"]
    problems = schema_problems(RECIPE_SCHEMA, recipe)
    if problems:
        return problems
    problems = schema_problems(RECIPE_SCHEMA, recipe, recipe["kind"])
    if problems or recipe["kind"] != "mix":
        return problems
    if recipe["source_clip_ids"] != [recipe["speech_clip_id"], recipe["noise_clip_id"]]:
        problems.append("/source_clip_ids: must be [speech_clip_id, noise_clip_id]")
    for name in ("speech_gain", "noise_gain"):
        if recipe[name] != recipe[f"{name}_q24"] / ONE:
            problems.append(f"/{name}: {recipe[name]} is not {name}_q24 / 2^{Q}")
    if recipe["snr_definition"] != SNR_DEFINITION:
        problems.append("/snr_definition: differs from the definition of recipe v1")
    return problems


def _segment(samples, offset, length, what):
    if offset + length > len(samples):
        raise RenderError(f"{what}: offset {offset} + length {length} runs past its {len(samples)} samples")
    return samples[offset:offset + length]


def render_recipe(recipe, load):
    """Rebuild a derived clip from its recipe; load(clip_id) returns that source clip's int16 samples."""
    problems = recipe_problems(recipe)
    if problems:
        raise RenderError("recipe is invalid: " + "; ".join(problems))
    length = recipe["length_samples"]
    if recipe["kind"] == "silence":
        return np.zeros(length, dtype=np.int16)
    if recipe["kind"] == "excerpt":
        (source_id,) = recipe["source_clip_ids"]
        return _segment(load(source_id), recipe["offset_samples"], length, source_id).astype(np.int16)
    speech = load(recipe["speech_clip_id"])
    if len(speech) != length:
        raise RenderError(f"speech clip {recipe['speech_clip_id']} has {len(speech)} samples, the recipe {length}")
    noise = _segment(load(recipe["noise_clip_id"]), recipe["noise_offset_samples"], length, recipe["noise_clip_id"])
    result = mix_clip(speech, noise, recipe["snr_db"])
    if (result.speech_gain_q24, result.noise_gain_q24, result.peak_limited) != (
            recipe["speech_gain_q24"], recipe["noise_gain_q24"], recipe["peak_limited"]):
        raise RenderError(f"recipe gains ({recipe['speech_gain_q24']}, {recipe['noise_gain_q24']}) do not follow from "
                          f"its SNR {recipe['snr_db']} dB and sources (they give {result.speech_gain_q24}, "
                          f"{result.noise_gain_q24})")
    return result.samples
