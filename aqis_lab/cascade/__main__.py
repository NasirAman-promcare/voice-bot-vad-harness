"""Command line of the Sprint 3 work: `python -m aqis_lab.cascade <action> --out DIR --s1-out DIR [options]`.

CAPABILITIES:
  CAP-S3-090: dispatches cascade (CPU: simulate gates over the Sprint 1 files; --nonspeech first computes the Silero v5 feature),
    confidence (GPU: saves parakeet-tdt-0.6b-v2 token confidences, the one gate feature the Sprint 1 files lack), prompt (GPU: keyword
    and context biasing), train (GPU: prepares the Eka training set unless --skip-prepare, then QLoRA with early stopping), eval (GPU:
    base against merged adapter) and report (CPU); every action reads the same config (config/aqis_lab/s3.yaml); exit 0 done, 2 error
    [no unit test of its own: the stages it calls are described in their modules]
INPUTS AND OUTPUTS: command-line arguments in; files under --out, progress on stdout, errors on stderr.
CONTRACTS: brief sections 4 and 5.
INVARIANTS:
  - HF_TOKEN is read from the process environment only; it is never an argument, a log line or a file.
  - Sprint 1's output folder (--s1-out) is read, except for the pinned revisions file it already holds.
NOT IN SCOPE:
  - Mounting Drive, cloning the repository and the unit log (the notebook).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "s3.yaml"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab.cascade", description="Sprint 3 cascade routing and LoRA pilot.")
    parser.add_argument("action", choices=["cascade", "confidence", "prompt", "train", "eval", "report"])
    parser.add_argument("--out", required=True, help="Sprint 3 results folder (Drive: MyDrive/AQIS_LAB/s3)")
    parser.add_argument("--s1-out", required=True, help="Sprint 1 results folder with data/ and preds/ (Drive: MyDrive/AQIS_LAB/s1)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--work-dir", default="/content/s3_work", help="local scratch folder for copies and downloads")
    parser.add_argument("--models", nargs="+", help="prompt: the models to run (default: all of prompt.models)")
    parser.add_argument("--nonspeech", action="store_true", help="cascade: compute the Silero v5 non-speech ratio first (CPU, a few minutes)")
    parser.add_argument("--skip-prepare", action="store_true", help="train: the training files already exist")
    parser.add_argument("--prepare-only", action="store_true", help="train: only prepare the training files")
    parser.add_argument("--smoke", action="store_true", help="confidence, prompt, train, eval: 3 turns or 4 steps, written under <out>/smoke (CLAUDE.md rule 6)")
    return parser


def _gpu():
    from aqis_lab import platform as lp
    block = lp.machine_block()
    gpu = block.get("gpu") or block.get("gpu_type") or block.get("gpu_name")
    if not gpu:
        raise RuntimeError("no GPU name found (the machine block has no gpu entry); this action needs a GPU runtime")
    return gpu


def _write_terms(cfg, s1_cfg, s1_dir, out, work_dir):
    """Drug names for the biasing prompts, from Eka turns outside the evaluated slice (CPU; the prepare step writes them)."""
    from aqis_lab import drive
    from aqis_lab.cascade import prompt_bias, train_data
    items, _ = train_data.eka_candidates(s1_cfg, s1_dir, work_dir, REPO_ROOT)
    clusters, _ = train_data.eval_exclusions(s1_dir)
    terms = prompt_bias.terms_from_candidates(items, clusters, cfg.prompt["terms"])
    path = Path(out) / "prompt" / "terms.json"
    drive.make_dirs(path.parent)
    drive.write_bytes(path, (json.dumps({"terms": terms, "config_hash": cfg.hash}, indent=2) + "\n").encode("utf-8"))
    return terms


def _read_terms(out):
    path = Path(out) / "prompt" / "terms.json"
    if not path.is_file():
        raise RuntimeError(f"{path} is missing; run the prepare step first (it writes the biasing terms on a CPU runtime)")
    return json.loads(path.read_text(encoding="utf-8"))["terms"]


def main(argv=None):
    ns = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    from aqis_lab.cascade.config import ConfigError, load_config
    try:
        cfg = load_config(ns.config)
        out, s1_dir = Path(ns.out), Path(ns.s1_out)
        from aqis_lab.bench.config import load_config as load_s1
        s1_cfg = load_s1(REPO_ROOT / cfg.s1["config"])
        if ns.action == "report":
            from aqis_lab.cascade import report
            report.build_report(cfg, s1_dir, out)
        elif ns.action == "cascade":
            from aqis_lab.cascade import simulate
            if ns.nonspeech:
                from aqis_lab.live.config import load_config as load_s2
                ts = simulate.load_target_set(s1_cfg, s1_dir, cfg.cascade["stage1"], cfg.cascade["heavy"])
                simulate.compute_nonspeech(cfg, load_s2(REPO_ROOT / cfg.s1["s2_config"]), s1_dir, out, ts)
            simulate.run(cfg, s1_cfg, s1_dir, out)
        elif ns.action == "confidence":
            from aqis_lab.cascade import confidence
            confidence.extract(cfg, s1_cfg, s1_dir, out / "smoke" if ns.smoke else out, ns.work_dir, limit=3 if ns.smoke else None)
        elif ns.action == "prompt":
            from aqis_lab.cascade import prompt_bias
            gpu = _gpu()
            terms = _read_terms(out)
            for model in ns.models or cfg.prompt["models"]:
                prompt_bias.run(cfg, s1_cfg, s1_dir, out / "smoke" if ns.smoke else out, model, terms, gpu, REPO_ROOT,
                                limit=3 if ns.smoke else None)
        elif ns.action == "train":
            from aqis_lab.cascade import train_data, train_lora
            if not ns.skip_prepare:
                _write_terms(cfg, s1_cfg, s1_dir, out, ns.work_dir)
                train_data.prepare(cfg, s1_cfg, s1_dir, out, ns.work_dir, REPO_ROOT)
            if not ns.prepare_only:
                _gpu()
                train_lora.train(cfg, s1_cfg, s1_dir, out, REPO_ROOT, smoke=ns.smoke)
        else:
            from aqis_lab.cascade import train_lora
            train_lora.evaluate(cfg, s1_cfg, s1_dir, out, REPO_ROOT, _gpu(), smoke=ns.smoke)
        return 0
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
