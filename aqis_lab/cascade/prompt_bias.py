"""Sprint 3 workstream B: keyword and context prompt biasing of granite-speech-4.1-2b and qwen3-asr-1.7b on medical and numbers.

CAPABILITIES:
  CAP-S3-050: bias_terms() counts entities of one category by case-insensitive text over Eka turns of speakers outside the evaluated
    slice and returns the most frequent first (ties alphabetical, at most max_terms); terms_text() joins whole terms to fit a
    character limit; granite_prompt(), qwen_context(), granite_hint_prompt() and qwen_hint_context() build the cards' keyword and
    context prompts [tests: test_s3_bias_terms_count_the_chosen_category_case_insensitively_most_frequent_first,
    test_s3_bias_terms_never_come_from_the_evaluated_speakers, test_s3_bias_terms_stop_at_max_terms,
    test_s3_term_text_drops_whole_terms_from_the_end_to_fit_the_limit, test_s3_granite_and_qwen_prompts_follow_their_cards,
    test_s3_numbers_hint_prompts_keep_the_card_prompt_and_add_the_hint]
  CAP-S3-051: run() transcribes the Sprint 1 data files of the medical and numbers slices with a biasing prompt and writes prediction
    files in the Sprint 1 format under <out>/prompt/<model>/, one per slice and condition, resumable; medical turns get the drug list,
    numbers turns the digit hint [no unit test: it needs the models and a GPU; the Colab smoke run checks it]
INPUTS AND OUTPUTS: s3 and s1 configs, the Sprint 1 data folder; prediction parquet files out; PromptError.
CONTRACTS: Granite Speech 4.1 card ("transcribe the speech to text. Keywords: <kw1>, <kw2>, ..."); Qwen3-ASR's transcribe(context=...).
INVARIANTS:
  - Terms never come from the evaluated slice's speakers or its reference texts.
  - Every row carries the trace columns of the Sprint 1 format (model, revision, dtype, GPU, commit, seed).
NOT IN SCOPE:
  - Scoring (aqis_lab/cascade/report.py uses the Sprint 1 scorers).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import collections
from pathlib import Path


GRANITE_BASE = "<|audio|>transcribe the speech with proper punctuation and capitalization."
GRANITE_KEYWORDS = "<|audio|>transcribe the speech to text. Keywords: "
QWEN_PREFIX = "Medication and clinical terms: "


class PromptError(RuntimeError):
    """Prompt biasing cannot run as asked."""


def bias_terms(entities, exclude_clusters, max_terms, category):
    counts = collections.Counter()
    for e in entities:
        if e["category"] == category and e["cluster"] not in exclude_clusters:
            counts[e["text"].strip().lower()] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _ in ordered[:max_terms]]


def terms_text(terms, max_chars):
    kept = []
    for term in terms:
        if len(", ".join([*kept, term])) > max_chars:
            break
        kept.append(term)
    return ", ".join(kept)


def granite_prompt(text):
    return GRANITE_KEYWORDS + text if text else GRANITE_BASE


def qwen_context(text):
    return QWEN_PREFIX + text if text else ""


def granite_hint_prompt(hint):
    return f"{GRANITE_BASE} {hint}"


def qwen_hint_context(hint):
    return hint


def _prompts(model_name, slice_name, text, hint):
    if slice_name == "medical":
        return granite_prompt(text) if model_name.startswith("granite") else qwen_context(text)
    return granite_hint_prompt(hint) if model_name.startswith("granite") else qwen_hint_context(hint)


def terms_from_candidates(candidates, eval_clusters, terms_cfg):
    """Bias terms from Eka candidate turns (aqis_lab.cascade.train_data.eka_candidates) outside the evaluated speakers."""
    entities = [{"cluster": c["cluster"], "category": e["category"], "text": e["text"]}
                for c in candidates for e in c["meta"].get("entities", [])]
    return bias_terms(entities, eval_clusters, terms_cfg["max_terms"], terms_cfg["category"])


def run(cfg, s1_cfg, s1_dir, out_dir, model_name, terms, gpu, repo_root, log=print, limit=None):
    """Transcribe the configured slices and conditions of one model with biasing prompts; skips finished files; `limit` keeps only
    the first turns of each file (the smoke run, written to its own folder by the caller)."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from aqis_lab import drive
    from aqis_lab.bench import models, run as s1_run
    pr = cfg.prompt
    text = terms_text(terms, pr["terms"]["max_chars"])
    revision = s1_run.revision_for(model_name, s1_cfg.models[model_name]["hf"], s1_dir)
    model = models.load(model_name, s1_cfg.models[model_name], revision)
    commit = s1_run.git_commit(repo_root)
    try:
        for slice_name in pr["slices"]:
            for condition in pr["conditions"]:
                src = Path(s1_dir) / "data" / slice_name / f"{condition}.parquet"
                dst = Path(out_dir) / "prompt" / model_name / f"{slice_name}__{condition}.parquet"
                if dst.exists():
                    log(f"prompt {model_name} {slice_name}/{condition}: done, skipped")
                    continue
                if not src.is_file():
                    raise PromptError(f"{src} is missing; run the Sprint 1 prep first")
                rows = pq.read_table(src, columns=["utt_id", "audio", "n_samples"]).to_pylist()[:limit]
                prompt = _prompts(model_name, slice_name, text, pr["numbers_hint"])
                set_prompt(model, model_name, prompt)
                size = s1_cfg.models[model_name]["batch"]
                out = []
                for start in range(0, len(rows), size):
                    chunk = rows[start:start + size]
                    audios = [np.frombuffer(r["audio"], dtype=np.int16).astype(np.float32) / 32768.0 for r in chunk]
                    hyps = model.transcribe(audios)
                    for r, h in zip(chunk, hyps):
                        out.append({"utt_id": r["utt_id"], "model": model_name, "revision": revision, "prompt": prompt, "hyp": h,
                                    "dtype": model.dtype, "gpu": gpu, "git_commit": commit, "seed": cfg.seed})
                sink = pa.BufferOutputStream()
                pq.write_table(pa.Table.from_pylist(out), sink, compression="zstd")
                drive.make_dirs(dst.parent)
                drive.write_bytes(dst, sink.getvalue().to_pybytes())
                log(f"prompt {model_name} {slice_name}/{condition}: {len(out)} turns")
    finally:
        model.close()


def set_prompt(model, model_name, prompt):
    """Give a loaded Sprint 1 wrapper the biasing prompt: Granite's user prompt, or Qwen3-ASR's context string."""
    if model_name.startswith("granite"):
        model.prompt = model.tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False,
                                                           add_generation_prompt=True)
    else:
        qwen = model.model

        def run(audios, _context=prompt, _model=model):
            results = qwen.transcribe(audio=[(a, 16000) for a in audios], context=_context,
                                      language=[_model.language] * len(audios))
            return [r.text.strip() for r in results]
        model.run = run
