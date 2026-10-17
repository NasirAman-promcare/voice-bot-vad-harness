"""Seeded, speaker-balanced selection of the utterances of each Sprint 1 slice, as pure functions.

CAPABILITIES:
  CAP-S1-004: round_robin() picks items one speaker at a time (speakers and each speaker's items ordered by SHA-256 of
    the seed, a salt and their IDs), so no speaker dominates and every prefix of the result is balanced; select_slice()
    applies a slice's filters (length range, words after cleaning, L1 list, entities, digit tokens), then picks N by
    round robin: stratified by speech type when the source has that field, half caller and half agent turns with
    digit-bearing turns first for a telephone slice; a source with fewer than N qualifying utterances gives all of them
    and a note with the real N [tests: test_s1_round_robin_takes_one_per_speaker_per_round,
    test_s1_round_robin_is_deterministic_for_a_seed_and_changes_with_it, test_s1_select_slice_applies_length_and_word_filters,
    test_s1_select_slice_n_caps_and_notes_a_short_source, test_s1_select_slice_filters_l1_and_entities,
    test_s1_select_slice_digit_token_filter_counts_normalised_reference_tokens, test_s1_select_slice_stratifies_by_the_stratum_field,
    test_s1_select_slice_without_a_stratum_field_picks_plainly_and_says_so,
    test_s1_select_slice_telephone_turns_half_caller_half_agent_digits_first, test_s1_select_slice_is_deterministic_for_a_seed]
  CAP-S1-005: plan_nonspeech() lays out the non-speech slice: 60 noise, 20 music and 20 silence clips of 3 to 8 s, each
    noise or music clip a seeded excerpt of a MUSAN clip long enough for it at a seeded level between -35 and -15 dBFS
    [tests: test_s1_nonspeech_plan_has_the_stated_mix_levels_and_lengths]
INPUTS AND OUTPUTS: utterance dicts (utt_id, speaker, cluster, duration_s, ref_clean, meta) and a slice spec in;
  a Selection (items in pick order, notes) out. SelectionError.
CONTRACTS: brief section 2 "Selection rules" and "Bootstrap clusters".
INVARIANTS:
  - The result depends on the seed, the slice name and the items' contents, never on the order they are given in,
    the clock or PYTHONHASHSEED.
  - Items come back in round-robin order, so the first k of a slice (the pilot's 100) are themselves speaker-balanced.
NOT IN SCOPE:
  - Reading datasets (aqis_lab/bench/sources.py) and rendering audio (aqis_lab/bench/conditions.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import hashlib
import math
from dataclasses import dataclass, field

from aqis_lab.scoring.normalise import MAIN


class SelectionError(ValueError):
    """A slice cannot be selected as specified."""


@dataclass
class Selection:
    items: list
    notes: list = field(default_factory=list)


def _key(seed, salt, kind, ident):
    return hashlib.sha256(f"aqis-s1-select|{seed}|{salt}|{kind}|{ident}".encode("utf-8")).hexdigest()


def round_robin(items, n, seed, salt):
    """Up to n items, one speaker at a time; deterministic for (seed, salt) whatever the input order."""
    by_speaker = {}
    for item in items:
        by_speaker.setdefault(item["speaker"], []).append(item)
    speakers = sorted(by_speaker, key=lambda s: _key(seed, salt, "speaker", s))
    queues = [sorted(by_speaker[s], key=lambda x: _key(seed, salt, "utt", x["utt_id"])) for s in speakers]
    chosen = []
    depth = 0
    while len(chosen) < n and any(len(q) > depth for q in queues):
        for q in queues:
            if len(q) > depth and len(chosen) < n:
                chosen.append(q[depth])
        depth += 1
    return chosen


def digit_token_count(text):
    """Tokens of the MAIN-normalised text that contain a digit."""
    return sum(1 for token in MAIN(text).split(" ") if any(ch.isdigit() for ch in token))


def _passes(item, spec, utt_cfg):
    min_s, max_s = spec.get("min_s", utt_cfg["min_s"]), spec.get("max_s", utt_cfg["max_s"])
    if not min_s <= item["duration_s"] <= max_s:
        return False
    if len(item["ref_clean"].split()) < utt_cfg["min_ref_words"]:
        return False
    if "l1" in spec and item["meta"].get("l1") not in spec["l1"]:
        return False
    if spec.get("require_entities") and not item["meta"].get("entities"):
        return False
    return True


def _has_digit(item):
    """True when the MAIN-normalised reference has a token with a digit (spelled numbers become digits)."""
    if "_has_digit" not in item["meta"]:
        item["meta"]["_has_digit"] = digit_token_count(item["ref_clean"]) > 0
    return item["meta"]["_has_digit"]


def _balanced_roles(pool, n, spec, seed, salt):
    """Half caller and half agent turns; with digits_first, up to half of each role's turns carry digits."""
    quota = {"caller": n - n // 2, "agent": n // 2}
    chosen = []
    for role in ("caller", "agent"):
        group = [x for x in pool if x["meta"].get("role") == role]
        want = quota[role]
        if not spec.get("digits_first"):
            chosen += round_robin(group, want, seed, f"{salt}|{role}")
            continue
        with_digits = [x for x in group if _has_digit(x)]
        without = [x for x in group if not _has_digit(x)]
        first = round_robin(with_digits, math.ceil(want / 2), seed, f"{salt}|{role}|digits")
        rest = round_robin(without, want - len(first), seed, f"{salt}|{role}|plain")
        if len(first) + len(rest) < want:       # too few plain turns: top up with the digit turns not yet taken
            taken = {x["utt_id"] for x in first}
            rest += round_robin([x for x in with_digits if x["utt_id"] not in taken], want - len(first) - len(rest),
                                seed, f"{salt}|{role}|topup")
        chosen += first + rest
    return chosen


def select_slice(name, spec, utts, utt_cfg, seed):
    """The utterances of slice `name`: filters, then a speaker-balanced pick of spec['n'] (see the module header)."""
    notes = []
    pool = [x for x in utts if _passes(x, spec, utt_cfg)]
    if "min_digit_tokens" in spec:
        pool = [x for x in pool if digit_token_count(x["ref_clean"]) >= spec["min_digit_tokens"]]
    n = spec["n"]
    if spec.get("balance_roles"):
        items = _balanced_roles(pool, n, spec, seed, name)
    elif spec.get("stratify"):
        if not any("stratum" in x["meta"] for x in pool):
            notes.append(f"{name}: no stratum field in the source; selected without stratification")
            items = round_robin(pool, n, seed, name)
        else:
            items = []
            for stratum, count in spec["stratify"].items():
                items += round_robin([x for x in pool if x["meta"].get("stratum") == stratum], count, seed,
                                     f"{name}|{stratum}")
    else:
        items = round_robin(pool, n, seed, name)
    if len(items) < n:
        notes.append(f"{name}: only {len(items)} utterances qualify, {n} asked for; the real N is {len(items)}")
    return Selection(items, notes)


def _fraction(seed, what, ident):
    """A seeded number in [0, 1)."""
    return int(_key(seed, "nonspeech", what, ident), 16) / 16 ** 64


def plan_nonspeech(spec, noise_lengths, music_lengths, seed):
    """The non-speech clips: dicts with utt_id, kind, clip_id, offset, length (samples) and level_dbfs."""
    mix = spec["mix"]
    if sum(mix.values()) != spec["n"]:
        raise SelectionError(f"nonspeech mix {mix} does not add up to n={spec['n']}")
    lo_s, hi_s = spec["length_s"]
    lo_db, hi_db = spec["level_dbfs"]
    pools = {"noise": noise_lengths, "music": music_lengths}
    plan = []
    for kind in ("noise", "music", "silence"):
        for i in range(mix[kind]):
            ident = f"nonspeech-{kind}-{i + 1:03d}"
            length = lo_s * 16000 + int(_fraction(seed, "length", ident) * ((hi_s - lo_s) * 16000 + 1))
            if kind == "silence":
                plan.append({"utt_id": ident, "kind": kind, "clip_id": None, "offset": None, "length": length,
                             "level_dbfs": None})
                continue
            eligible = sorted(c for c, size in pools[kind].items() if size >= length)
            if not eligible:
                raise SelectionError(f"no {kind} clip has the {length} samples {ident} needs")
            clip = min(eligible, key=lambda c: _key(seed, "nonspeech", "clip", f"{ident}|{c}"))
            room = pools[kind][clip] - length + 1
            offset = int(_key(seed, "nonspeech", "offset", f"{ident}|{clip}"), 16) % room
            plan.append({"utt_id": ident, "kind": kind, "clip_id": clip, "offset": offset, "length": length,
                         "level_dbfs": lo_db + _fraction(seed, "level", ident) * (hi_db - lo_db)})
    return plan
