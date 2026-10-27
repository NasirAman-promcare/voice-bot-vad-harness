"""Per-turn confidence of the stage 1 transcriber (parakeet-tdt-0.6b-v2), which the Sprint 1 prediction files do not hold.

CAPABILITIES:
  CAP-S3-030: summarise() gives a turn's mean and minimum token confidence and its token count, and None (never a made-up value)
    for a turn with no tokens [tests: test_s3_confidence_summary_is_the_mean_and_minimum_of_token_confidences,
    test_s3_a_turn_without_tokens_has_no_confidence_and_is_not_invented]
  CAP-S3-031: extract() runs parakeet-tdt-0.6b-v2 over the target turns on the GPU with NeMo's token confidence switched on, twice
    (a max-probability score and an entropy-based score, both higher = more confident), and writes them beside the other gate
    features in <out>/cascade/features.parquet [no unit test: it needs the model, NeMo and a GPU; the Colab smoke run checks it]
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


def _confidence_cfg(model, method):
    omegaconf = lib("omegaconf")
    decoding = model.cfg.decoding
    with omegaconf.open_dict(decoding):
        decoding.preserve_alignments = True
        decoding.confidence_cfg.preserve_token_confidence = True
        decoding.confidence_cfg.exclude_blank = True
        decoding.confidence_cfg.aggregation = "mean"
        decoding.confidence_cfg.method_cfg.name = method
    model.change_decoding_strategy(decoding)


def token_confidences(model, paths, method, batch_size):
    """One list of token confidences per file, from hypotheses with preserve_token_confidence switched on."""
    _confidence_cfg(model, method)
    torch = lib("torch")
    with torch.inference_mode():
        out = model.transcribe(paths, batch_size=batch_size, return_hypotheses=True)
    if isinstance(out, tuple):
        out = out[0]
    result = []
    for hyp in out:
        confs = getattr(hyp, "token_confidence", None)
        result.append([float(c) for c in confs] if confs else [])
    return result


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
    With `limit`, only the first turns of the first file (the smoke run, written to its own folder by the caller)."""
    import pyarrow.parquet as pq
    from aqis_lab.bench import run as s1_run
    from aqis_lab.cascade.features import FEATURE_FILE, merge_features
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
    batch = s1_cfg.models[stage1]["batch"]
    methods = {"confidence": cfg.cascade["confidence"]["confidence_method"], "entropy": cfg.cascade["confidence"]["entropy_method"]}
    scratch = Path(work_dir) / "s3_confidence"
    scratch.mkdir(parents=True, exist_ok=True)
    feature_path = Path(out_dir).joinpath(*FEATURE_FILE)
    cells = target_cells(s1_cfg, s1_dir)
    for slice_name, condition in cells[:1] if limit else cells:
        rows = pq.read_table(Path(s1_dir) / "data" / slice_name / f"{condition}.parquet", columns=["utt_id", "audio"]).to_pylist()[:limit]
        found = {}
        for start in range(0, len(rows), batch):
            chunk = rows[start:start + batch]
            paths = []
            for row in chunk:
                path = scratch / f"{hashlib.sha1(row['utt_id'].encode()).hexdigest()}_{condition}.wav"
                soundfile.write(str(path), np.frombuffer(row["audio"], dtype=np.int16), 16000, subtype="PCM_16")
                paths.append(str(path))
            per_method = {name: token_confidences(model, paths, method, len(paths)) for name, method in methods.items()}
            for i, row in enumerate(chunk):
                found[f"{slice_name}:{condition}:{row['utt_id']}"] = {name: summarise(per_method[name][i])["confidence"] for name in methods}
            for path in paths:
                Path(path).unlink(missing_ok=True)
        merge_features(feature_path, found)
        log(f"confidence {slice_name}/{condition}: {len(rows)} turns")
