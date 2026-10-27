"""Per-turn confidence of the stage 1 transcriber (parakeet-tdt-0.6b-v2), which the Sprint 1 prediction files do not hold.

CAPABILITIES:
  CAP-S3-030: summarise() gives a turn's mean and minimum token confidence and its token count, and None (never a made-up value)
    for a turn with no tokens [tests: test_s3_confidence_summary_is_the_mean_and_minimum_of_token_confidences,
    test_s3_a_turn_without_tokens_has_no_confidence_and_is_not_invented]
  CAP-S3-031: extract() runs parakeet-tdt-0.6b-v2 over the target turns on the GPU with NeMo's token confidence switched on, twice
    (a max-probability score and an entropy-based score, both higher = more confident), and writes them beside the other gate
    features in <out>/cascade/features.parquet [no unit test: it needs the model, NeMo and a GPU; the Colab smoke run checks it]
  CAP-S3-032: configure() switches token confidence on without alignments (which keep every logit and ran a 22 GB L4 out of memory);
    confidences_for_cell() sets the decoding up once per method for a whole file; cell_done() lets a rerun skip finished files;
    require_coverage() stops the run when NeMo returns no confidence for a whole file [tests:
    test_s3_decoding_keeps_confidences_but_not_alignments, test_s3_token_confidences_pass_the_batch_size_and_free_the_gpu_cache,
    test_s3_a_hypothesis_without_token_confidences_gives_an_empty_list_not_a_guess,
    test_s3_a_cell_sets_up_each_method_once_however_many_turns_it_has,
    test_s3_a_cell_is_finished_only_when_every_turn_has_both_scores,
    test_s3_no_confidences_at_all_is_an_error_and_a_few_missing_is_not, test_s3_the_config_names_a_positive_confidence_batch_size]
INPUTS AND OUTPUTS: the Sprint 1 data files in; <out>/cascade/features.parquet (key, confidence, entropy, nonspeech_ratio) out;
  ConfidenceError.
CONTRACTS: brief section 2A (the gate reads mean token log-probabilities or entropy); NeMo's confidence_cfg of the RNNT/TDT decoders.
INVARIANTS:
  - If NeMo returns no token confidences for a turn, the column stays empty for that turn and the policy that needs it is
    reported unavailable; a stand-in is never written.
NOT IN SCOPE:
  - Using the scores (aqis_lab/cascade/gate.py and simulate.py).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import hashlib
from pathlib import Path

import numpy as np

from aqis_lab.bench import lib


class ConfidenceError(RuntimeError):
    """Token confidences cannot be produced as asked."""


def summarise(token_confidences):
    values = [float(v) for v in token_confidences]
    if not values:
        return {"confidence": None, "min_confidence": None, "tokens": 0}
    return {"confidence": float(np.mean(values)), "min_confidence": float(min(values)), "tokens": len(values)}


def configure(model, method, omegaconf=None):
    """Switch NeMo's token confidence on for `method`, without alignments.

    preserve_alignments keeps every logit of every step; with it on, the first Colab run held 17 GB on a 22 GB L4 and ran out of memory
    on the second file. Token confidence needs the frame confidences, which are kept, and nothing else."""
    omegaconf = omegaconf or lib("omegaconf")
    decoding = model.cfg.decoding
    with omegaconf.open_dict(decoding):
        decoding.preserve_alignments = False
        decoding.confidence_cfg.preserve_frame_confidence = True
        decoding.confidence_cfg.preserve_token_confidence = True
        decoding.confidence_cfg.exclude_blank = True
        decoding.confidence_cfg.aggregation = "mean"
        decoding.confidence_cfg.method_cfg.name = method
    model.change_decoding_strategy(decoding)


def token_confidences(model, paths, batch_size, torch=None):
    """One list of token confidences per file (empty when NeMo returns none), from one transcribe call at `batch_size`."""
    torch = torch or lib("torch")
    with torch.inference_mode():
        out = model.transcribe(paths, batch_size=batch_size, return_hypotheses=True)
    if isinstance(out, tuple):
        out = out[0]
    result = []
    for hyp in out:
        confs = getattr(hyp, "token_confidence", None)
        result.append([float(c) for c in confs] if confs else [])
    torch.cuda.empty_cache()
    return result


def confidences_for_cell(model, paths, methods, batch_size, omegaconf=None, torch=None):
    """{name: lists} for {name: NeMo method}: the decoding is set up once per method, then the whole cell goes through it."""
    out = {}
    for name, method in methods.items():
        configure(model, method, omegaconf)
        out[name] = token_confidences(model, paths, batch_size, torch)
    return out


def cell_done(existing, keys):
    """True when every key already has both a confidence and an entropy score in the feature file."""
    return all(existing.get(k, {}).get("confidence") is not None and existing.get(k, {}).get("entropy") is not None for k in keys)


def require_coverage(found, where):
    """Share of turns with a confidence; an error when NeMo returned none for the whole cell."""
    covered = sum(1 for v in found.values() if v["confidence"] is not None)
    if found and not covered:
        raise ConfidenceError(f"NeMo returned no token confidences for any turn of {where}; the gate cannot use a feature that is empty")
    return covered / len(found) if found else 0.0


def target_cells(s1_cfg, s1_dir):
    """The (slice, condition) data files of the target set (caller slices, target conditions) that exist under s1_dir."""
    cells = []
    for slice_name in s1_cfg.caller_slices:
        for condition in s1_cfg.conditions_for(slice_name):
            if condition in s1_cfg.target_conditions and (Path(s1_dir) / "data" / slice_name / f"{condition}.parquet").is_file():
                cells.append((slice_name, condition))
    if not cells:
        raise ConfidenceError(f"no target-set data files under {Path(s1_dir) / 'data'}; run the Sprint 1 prep first")
    return cells


def extract(cfg, s1_cfg, s1_dir, out_dir, work_dir, log=print, limit=None):
    """Write confidence and entropy for every turn of the target-set data files (every turn is scored, not only answered ones).
    Finished files are skipped. With `limit`, only the first turns of the first file (the smoke run, written to its own folder
    by the caller)."""
    import pyarrow.parquet as pq
    from aqis_lab.bench import run as s1_run
    from aqis_lab.cascade.features import FEATURE_FILE, merge_features, read_features
    soundfile = lib("soundfile")
    nemo_asr = lib("nemo.collections.asr")
    huggingface_hub = lib("huggingface_hub")
    stage1 = cfg.cascade["stage1"]
    revision = s1_run.revision_for(stage1, s1_cfg.models[stage1]["hf"], s1_dir)
    folder = huggingface_hub.snapshot_download(s1_cfg.models[stage1]["hf"], revision=revision)
    files = sorted(Path(folder).glob("*.nemo"))
    if len(files) != 1:
        raise ConfidenceError(f"{stage1}@{revision[:10]} holds {len(files)} .nemo files, expected one")
    model = nemo_asr.models.ASRModel.restore_from(str(files[0])).to("cuda").eval()
    conf = cfg.cascade["confidence"]
    methods = {"confidence": conf["confidence_method"], "entropy": conf["entropy_method"]}
    scratch = Path(work_dir) / "s3_confidence"
    scratch.mkdir(parents=True, exist_ok=True)
    feature_path = Path(out_dir).joinpath(*FEATURE_FILE)
    cells = target_cells(s1_cfg, s1_dir)
    for slice_name, condition in cells[:1] if limit else cells:
        rows = pq.read_table(Path(s1_dir) / "data" / slice_name / f"{condition}.parquet", columns=["utt_id", "audio"]).to_pylist()[:limit]
        keys = [f"{slice_name}:{condition}:{r['utt_id']}" for r in rows]
        if cell_done(read_features(feature_path), keys):
            log(f"confidence {slice_name}/{condition}: done, skipped")
            continue
        paths = []
        for row in rows:
            path = scratch / f"{hashlib.sha1(row['utt_id'].encode()).hexdigest()}_{condition}.wav"
            soundfile.write(str(path), np.frombuffer(row["audio"], dtype=np.int16), 16000, subtype="PCM_16")
            paths.append(str(path))
        per_method = confidences_for_cell(model, paths, methods, conf["batch_size"])
        for path in paths:
            Path(path).unlink(missing_ok=True)
        found = {key: {name: summarise(per_method[name][i])["confidence"] for name in methods} for i, key in enumerate(keys)}
        share = require_coverage(found, f"{slice_name}/{condition}")
        merge_features(feature_path, found)
        log(f"confidence {slice_name}/{condition}: {len(rows)} turns, {share:.1%} with token confidences")
