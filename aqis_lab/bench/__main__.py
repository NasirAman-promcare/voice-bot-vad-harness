"""Command line of the Sprint 1 benchmark: `python -m aqis_lab.bench <action> --out DIR [options]`.

CAPABILITIES:
  CAP-S1-021: dispatches the actions prep (CPU), smoke, run --stage anchor|pilot|full and speed (GPU), and score and
    report (CPU); every action reads the same config (config/aqis_lab/s1.yaml) and writes under --out; each action imports
    only the modules it needs, so a GPU virtual environment never loads the scorer; exit 0 done, 1 smoke failures, 2 error
    [tests: test_s1_runner_modules_import_no_scorer_and_no_ml_library]
INPUTS AND OUTPUTS: command-line arguments in; files under --out, progress on stdout, errors on stderr.
CONTRACTS: brief section 6.2.
INVARIANTS:
  - HF_TOKEN is read from the process environment only; it is never an argument, a log line or a file.
NOT IN SCOPE:
  - Mounting Drive, cloning the repository and the unit log (the notebook).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "s1.yaml"
DEFAULT_WORK = "/content/s1_work"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab.bench", description="Sprint 1 speech-to-text benchmark.")
    parser.add_argument("action", choices=["prep", "smoke", "run", "speed", "score", "report"])
    parser.add_argument("--out", required=True, help="results folder (Drive: MyDrive/AQIS_LAB/s1)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--work-dir", default=DEFAULT_WORK, help="local scratch folder for copies and downloads")
    parser.add_argument("--model", help="model name from the config (smoke, run, speed)")
    parser.add_argument("--stage", choices=["anchor", "pilot", "full"], help="stage for `run`")
    parser.add_argument("--slices", nargs="+", help="limit prep or a run to these slices")
    parser.add_argument("--dtype", choices=["bf16", "fp16", "fp32"], help="override the model's dtype (record it)")
    parser.add_argument("--gaps", help="JSON file {model: one-line reason} for the scorecard's gap list")
    return parser


def main(argv=None):
    ns = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    from aqis_lab.bench.config import ConfigError, load_config
    try:
        cfg = load_config(ns.config)
        out = Path(ns.out)
        if ns.action == "prep":
            from aqis_lab.bench.prep import prep
            prep(cfg, out, ns.work_dir, REPO_ROOT, only=ns.slices)
            return 0
        if ns.action in ("smoke", "run", "speed"):
            if not ns.model:
                print("ERROR: --model is required", file=sys.stderr)
                return 2
            from aqis_lab import platform as lp
            from aqis_lab.bench import run
            gpu = lp.machine_block().get("gpu_type") or lp.machine_block().get("gpu") or lp.machine_block().get("gpu_name") or "unknown_gpu"
            if not gpu:
                print("ERROR: no GPU found; smoke, run and speed need a GPU runtime", file=sys.stderr)
                return 2
            if ns.action == "speed":
                run.run_speed(cfg, ns.model, out, ns.work_dir, REPO_ROOT, gpu, ns.dtype)
                return 0
            stage = "smoke" if ns.action == "smoke" else ns.stage
            if stage is None:
                print("ERROR: run needs --stage anchor, pilot or full", file=sys.stderr)
                return 2
            failures = run.run_model(cfg, ns.model, stage, out, ns.work_dir, REPO_ROOT, gpu, ns.dtype, ns.slices)
            for failure in failures:
                print(f"SMOKE FAILURE: {failure}", file=sys.stderr)
            return 1 if failures else 0
        from aqis_lab.bench import report
        if ns.action == "score":
            import json
            gaps = json.loads(Path(ns.gaps).read_text(encoding="utf-8")) if ns.gaps else None
            report.score_all(cfg, out, gaps)
        else:
            report.build_report(cfg, out)
        return 0
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
