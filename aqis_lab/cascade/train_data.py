"""Sprint 3 workstream C data: speaker-disjoint training and validation sets from Eka, augmented to phone and noise conditions.

CAPABILITIES:
  CAP-S3-060: split_train() leaves out the evaluated speakers and turns, then splits the rest by speaker into training and validation
    sets (so early stopping never sees a training speaker); augmentation_condition() picks a condition for a turn from the configured
    mix, the same pick for the same turn and seed; training_target() writes Qwen3-ASR's target text with its language prefix [tests:
    test_s3_train_and_validation_share_no_speaker_and_neither_touches_the_evaluated_ones,
    test_s3_split_is_deterministic_and_independent_of_input_order,
    test_s3_split_with_too_few_speakers_for_a_validation_set_is_an_error,
    test_s3_augmentation_choice_is_stable_and_follows_the_mix,
    test_s3_training_target_has_the_language_prefix_qwen_was_trained_with]
  CAP-S3-061: eval_exclusions() reads the evaluated medical slice's speakers and turns from the Sprint 1 data files; eka_candidates() reads
    Eka through the Sprint 1 source; prepare() writes train.jsonl, val.jsonl, the wav files and manifest.json (counts, and how many
    evaluated drug names also occur in training) [no unit test: it reads Eka and MUSAN, which the cloud session never downloads; the
    Colab prepare step runs it]
INPUTS AND OUTPUTS: s3 and s1 configs, the Sprint 1 output folder; jsonl, wav and manifest files out; TrainDataError.
CONTRACTS: brief section 2C. Eka has a test split only (3,619 English turns), so "the Eka training split" is the part of Eka that is
  speaker-disjoint from the 300-turn `medical` evaluation slice.
INVARIANTS:
  - No training or validation speaker appears in the evaluated medical slice, and no evaluated turn is trained on.
  - The overlap of evaluated drug names with training drug names is measured and written to the manifest, not hidden.
NOT IN SCOPE:
  - Training (aqis_lab/cascade/train_lora.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

MIN_SPEAKERS = 4
LANGUAGE_PREFIX = "language English<asr_text>"


class TrainDataError(RuntimeError):
    """The training data cannot be prepared as asked."""


@dataclass
class Split:
    train: list
    val: list
    notes: list = field(default_factory=list)


def _hash(seed, text):
    return int.from_bytes(hashlib.sha256(f"aqis-s3-train|{seed}|{text}".encode("utf-8")).digest()[:8], "big")


def split_train(items, eval_clusters, eval_utt_ids, val_fraction, seed):
    usable = [x for x in items if x["cluster"] not in eval_clusters and x["utt_id"] not in eval_utt_ids]
    clusters = sorted({x["cluster"] for x in usable}, key=lambda c: (_hash(seed, c), c))
    if len(clusters) < MIN_SPEAKERS:
        raise TrainDataError(f"training needs at least {MIN_SPEAKERS} speakers outside the evaluated slice, there are {len(clusters)}")
    n_val = max(1, round(val_fraction * len(clusters)))
    val_clusters = set(clusters[:n_val])
    return Split([x for x in usable if x["cluster"] not in val_clusters], [x for x in usable if x["cluster"] in val_clusters],
                 [f"split: {len(clusters)} speakers, {len(val_clusters)} for validation, {len(items) - len(usable)} turns left out "
                  f"as evaluated or from evaluated speakers"])


def augmentation_condition(utt_id, mix, seed):
    names = sorted(mix)
    point = _hash(seed, f"aug|{utt_id}") / 2 ** 64 * sum(mix[n] for n in names)
    for name in names:
        point -= mix[name]
        if point < 0:
            return name
    return names[-1]


def training_target(text):
    return LANGUAGE_PREFIX + text


def eval_exclusions(s1_dir, slice_name="medical"):
    """(clusters, utt ids) of every file of the evaluated slice under <s1_dir>/data."""
    import pyarrow.parquet as pq
    clusters, ids = set(), set()
    files = sorted((Path(s1_dir) / "data" / slice_name).glob("*.parquet"))
    if not files:
        raise TrainDataError(f"{Path(s1_dir) / 'data' / slice_name} holds no data files; run the Sprint 1 prep first")
    for path in files:
        for row in pq.read_table(path, columns=["utt_id", "cluster"]).to_pylist():
            clusters.add(row["cluster"])
            ids.add(row["utt_id"].split(":", 1)[-1])
    return clusters, ids


def eka_candidates(s1_cfg, s1_dir, work_dir, repo_root, log=print):
    """All cleaned Eka turns (utt_id, cluster, ref_clean, meta with entities and _loc) and the source handle."""
    from aqis_lab.bench import prep as s1_prep
    prep = s1_prep.Prep(s1_cfg, s1_dir, work_dir, repo_root, log)
    items, _ = prep.candidates("eka_medical")
    return items, prep


def prepare(cfg, s1_cfg, s1_dir, out_dir, work_dir, repo_root, log=print):
    import numpy as np
    import soundfile
    from aqis_lab import drive
    from aqis_lab.bench import conditions, select
    from aqis_lab.scoring.normalise import MAIN
    t = cfg.train
    items, prep = eka_candidates(s1_cfg, s1_dir, work_dir, repo_root, log)
    eval_clusters, eval_ids = eval_exclusions(s1_dir)
    with_entities = [x for x in items if x["meta"].get("entities")]
    split = split_train(with_entities, eval_clusters, eval_ids, t["val_fraction"], cfg.seed)
    train = select.round_robin(split.train, t["max_train_utts"], cfg.seed, "s3-train")
    val = select.round_robin(split.val, max(1, round(t["max_train_utts"] * t["val_fraction"])), cfg.seed, "s3-val")
    handle = prep.open_source("eka_medical")
    audio = handle.fetch_audio([tuple(x["meta"]["_loc"]) for x in train + val])
    noise = prep.noise_pool() if any("noise" in s1_cfg.conditions[c] for c in t["condition_mix"]) else {}
    folder = Path(work_dir) / "s3_train"
    out = {"train": [], "val": []}
    for name, group in (("train", train), ("val", val)):
        for x in group:
            samples = audio[tuple(x["meta"]["_loc"])]
            condition = augmentation_condition(x["utt_id"], t["condition_mix"], cfg.seed)
            rendered, _ = conditions.render_condition(condition, s1_cfg.conditions, samples, cfg.seed, f"s3:{x['utt_id']}", noise)
            if len(rendered) / 16000 > t["optim"]["max_audio_s"]:
                continue
            wav = folder / name / f"{x['utt_id']}.wav"
            wav.parent.mkdir(parents=True, exist_ok=True)
            soundfile.write(str(wav), np.asarray(rendered, dtype=np.int16), 16000, subtype="PCM_16")
            out[name].append({"audio": str(wav), "text": training_target(x["ref_clean"]), "utt_id": x["utt_id"],
                              "cluster": x["cluster"], "condition": condition})
    evaluated = {MAIN(e["text"]) for x in items if x["utt_id"] in eval_ids for e in x["meta"].get("entities", [])
                 if e["category"] == cfg.eval["category"]}
    trained = {MAIN(e["text"]) for x in train for e in x["meta"].get("entities", []) if e["category"] == cfg.eval["category"]}
    manifest = {"config_hash": cfg.hash, "train_turns": len(out["train"]), "val_turns": len(out["val"]),
                "train_speakers": len({r["cluster"] for r in out["train"]}), "val_speakers": len({r["cluster"] for r in out["val"]}),
                "conditions": {c: sum(1 for r in out["train"] if r["condition"] == c) for c in t["condition_mix"]},
                "eval_drug_names": len(evaluated), "eval_drug_names_also_in_training": len(evaluated & trained),
                "notes": split.notes}
    for name in out:
        drive.write_bytes(Path(out_dir) / "train" / f"{name}.jsonl",
                          ("\n".join(json.dumps(r, ensure_ascii=False) for r in out[name]) + "\n").encode("utf-8"))
    drive.write_bytes(Path(out_dir) / "train" / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    log(f"train set: {manifest}")
    return manifest
