"""Seeded selection: which registry clips a pack takes, mixes, cuts or generates, decided by SHA-256 keys only.

CAPABILITIES:
  CAP-PACK-009: plan_pack() turns a PackSpec and the registry into PlannedClip values in category order: for each part, the candidates passing its filter and the licence policy, not already used in the pack, are taken in the order of sha256("aqis-pack-select-v1|<seed>|<category>|<part index>|<role>|<clip_id>") with at most one clip per speaker where asked; mixes pair each chosen speech clip with the first unused noise clip long enough for it; excerpt and noise offsets are sha256("aqis-pack-offset-v1|<seed>|<derived clip id>|<source clip id>") modulo the room; derived clips get IDs <manifest_id>-<label>-<nn>, which must not be registry IDs; too few candidates is an error naming the category [tests: test_FR_0_4_03_builder_selects_exact_counts, test_FR_0_4_03_fails_when_too_few_candidates, test_FR_0_4_03_selection_ignores_registry_row_order, test_FR_0_4_03_selection_changes_with_seed, test_FR_0_4_03_selection_key_is_the_documented_hash, test_FR_0_4_03_distinct_speakers_and_utterances, test_FR_0_4_03_tts_clips_need_3_to_8_seconds, test_FR_0_4_03_licence_policy_keeps_share_alike_out, test_FR_0_4_03_excerpts_only_from_non_speech_sources, test_FR_0_4_03_derived_id_must_not_be_a_registry_id]
INPUTS AND OUTPUTS: a PackSpec, RegistryRow values and Datasets in; a list of PlannedClip out; SelectionError.
CONTRACTS: pack spec version 1; selection rule in docs/data/SMOKE_PACK.md.
INVARIANTS:
  - Depends only on the spec, the rows' contents and the seed: never on row order, the clock, PYTHONHASHSEED or
    Python's random module.
  - A registry clip is used at most once in a pack.
NOT IN SCOPE:
  - Reading or rendering audio (aqis_lab/packs/build.py, mix.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-03 created.
"""
import hashlib
from dataclasses import dataclass


class SelectionError(ValueError):
    """The registry cannot supply what a pack spec asks for."""


@dataclass(frozen=True)
class PlannedClip:
    category: str
    clip_id: str
    kind: str
    sources: tuple
    length_samples: int
    tags: tuple
    snr_db: float | int | None = None
    offset: int | None = None


def selection_key(seed, category, part_index, role, clip_id):
    return hashlib.sha256(f"aqis-pack-select-v1|{seed}|{category}|{part_index}|{role}|{clip_id}".encode("utf-8")).hexdigest()


def offset_for(seed, derived_id, source, length):
    room = source.n_samples - length + 1
    digest = hashlib.sha256(f"aqis-pack-offset-v1|{seed}|{derived_id}|{source.clip_id}".encode("utf-8")).hexdigest()
    return int(digest, 16) % room


def _allowed(row, spec, datasets):
    licence = datasets.licences.get(row.licence)
    if licence is None:
        return False
    if licence.share_alike and not spec.allow_share_alike:
        return False
    return not (licence.non_commercial and not spec.allow_non_commercial)


def _snr_tag(snr):
    text = f"{snr:g}".replace(".", "-")
    return f"snr-{text}" if not text.startswith("-") else f"snr-minus{text}"


def plan_pack(spec, rows, datasets):
    """PlannedClip values for every clip of the pack, in category order (see the module header)."""
    by_id = {}
    for row in rows:
        by_id[row.clip_id] = row
    ordered_rows = [by_id[k] for k in sorted(by_id)]
    used = set()
    label_totals, label_next = {}, {}
    for category in spec.categories:
        for part in category.parts:
            if part.label:
                label_totals[part.label] = label_totals.get(part.label, 0) + part.count

    def derived_id(label):
        label_next[label] = label_next.get(label, 0) + 1
        width = max(2, len(str(label_totals[label])))
        clip_id = f"{spec.manifest_id}-{label}-{label_next[label]:0{width}d}"
        if clip_id in by_id:
            raise SelectionError(f"derived clip ID {clip_id} is also a registry clip ID; change the part label")
        return clip_id

    def choose(category, part, flt, role, count, speakers, min_samples=0, what="clips"):
        candidates = [r for r in ordered_rows if r.clip_id not in used and flt.admits(r) and _allowed(r, spec, datasets)
                      and r.n_samples >= min_samples]
        candidates.sort(key=lambda r: selection_key(spec.seed, category.name, part.index, role, r.clip_id))
        chosen = []
        for row in candidates:
            if flt.distinct_speakers and row.speaker_id is not None and row.speaker_id in speakers:
                continue
            chosen.append(row)
            used.add(row.clip_id)
            if flt.distinct_speakers and row.speaker_id is not None:
                speakers.add(row.speaker_id)
            if len(chosen) == count:
                return chosen
        raise SelectionError(
            f"category {category.name} part {part.index} ({part.kind}) needs {count} {what} but found {len(chosen)} "
            f"eligible candidates (source {flt.source}, split {flt.split}, tags {list(flt.tags_all)}, not "
            f"{list(flt.tags_none)}, {flt.min_seconds}..{flt.max_seconds} s, licence policy, unused"
            f"{', one per speaker' if flt.distinct_speakers else ''})")

    plan = []
    for category in spec.categories:
        speakers = set()
        for part in category.parts:
            tags = tuple(sorted(set(category.tags) | set(part.tags)))
            if part.kind == "take":
                for row in choose(category, part, part.source_filter, "take", part.count, speakers):
                    plan.append(PlannedClip(category.name, row.clip_id, "take", (row,), row.n_samples, tags))
            elif part.kind == "mix":
                speech = choose(category, part, part.speech, "mix-speech", part.count, speakers, what="speech clips")
                for number, (row, snr) in enumerate(zip(speech, part.snr_db), start=1):
                    try:
                        (noise,) = choose(category, part, part.noise, "mix-noise", 1, set(), min_samples=row.n_samples,
                                          what=f"noise clips of at least {row.n_samples} samples")
                    except SelectionError as exc:
                        raise SelectionError(f"{exc} (for mix {number})") from exc
                    clip_id = derived_id(part.label)
                    plan.append(PlannedClip(category.name, clip_id, "mix", (row, noise), row.n_samples,
                                            tuple(sorted(set(tags) | {_snr_tag(snr)})), snr_db=snr,
                                            offset=offset_for(spec.seed, clip_id, noise, row.n_samples)))
            elif part.kind == "excerpt":
                dataset = datasets.datasets.get(_dataset_of(ordered_rows, part.source_filter))
                if dataset is not None and dataset["kind"] == "speech":
                    raise SelectionError(f"category {category.name} part {part.index}: an excerpt cannot come from "
                                         f"speech ({part.source_filter.source}/{part.source_filter.split}); its "
                                         f"transcript would not match")
                for row in choose(category, part, part.source_filter, "excerpt", part.count, speakers,
                                  min_samples=part.length_samples):
                    clip_id = derived_id(part.label)
                    plan.append(PlannedClip(category.name, clip_id, "excerpt", (row,), part.length_samples, tags,
                                            offset=offset_for(spec.seed, clip_id, row, part.length_samples)))
            else:
                for length in part.silence_lengths:
                    plan.append(PlannedClip(category.name, derived_id(part.label), "silence", (), length, tags))
    return plan


def _dataset_of(rows, flt):
    """Dataset ID of the rows a filter's source and split name (None if the registry has none)."""
    for row in rows:
        if row.source == flt.source and row.split == flt.split:
            return row.dataset
    return None
