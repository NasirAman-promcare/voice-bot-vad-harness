"""Command line of the Sprint 2 benchmark: `python -m aqis_lab.live <action> --out DIR [options]`.

CAPABILITIES:
  CAP-S2-070: dispatches prep, smoke, vad, turn, stream, emotion and report; every action reads the same config
    (config/aqis_lab/s2.yaml) and writes under --out; each action imports only the modules it needs; exit 0 done, 1 smoke
    failures, 2 error [no unit test of its own: the stages it calls are described in aqis_lab/live/stages.py]
INPUTS AND OUTPUTS: command-line arguments in; files under --out, progress on stdout, errors on stderr.
CONTRACTS: brief sections 5.1 and 6.
INVARIANTS:
  - HF_TOKEN is read from the process environment only; it is never an argument, a log line or a file.
NOT IN SCOPE:
  - Mounting Drive, cloning the repository and the unit log (the notebook).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "s2.yaml"
DEFAULT_S1_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "s1.yaml"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab.live", description="Sprint 2 live-stack benchmark.")
    parser.add_argument("action", choices=["prep", "smoke", "vad", "turn", "stream", "emotion", "report"])
    parser.add_argument("--out", required=True, help="results folder (Drive: MyDrive/AQIS_LAB/s2)")
    parser.add_argument("--s1-out", help="Sprint 1 results folder with data/ (prep only; Drive: MyDrive/AQIS_LAB/s1)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--work-dir", default="/tmp/s2_work", help="local scratch folder for copies and downloads")
    parser.add_argument("--sets", nargs="+", choices=["vad", "turn", "stream", "emotion"], help="limit prep to these sets")
    parser.add_argument("--models", nargs="+", help="VADs, turn policies, streaming variants or emotion models to run")
    parser.add_argument("--conditions", nargs="+", help="limit a stage to these conditions")
    parser.add_argument("--chunks", nargs="+", type=int, help="streaming chunk sizes in ms")
    parser.add_argument("--limit", type=int, help="clips per file: a pilot (CLAUDE.md rule 6)")
    parser.add_argument("--device", default="cpu", help="cpu or cuda, for the emotion models")
    return parser


def main(argv=None):
    ns = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    from aqis_lab.live.config import ConfigError, load_config
    try:
        cfg = load_config(ns.config)
        out = Path(ns.out)
        if ns.action == "report":
            from aqis_lab.live import report
            report.build_report(cfg, out)
            return 0
        if ns.action == "prep":
            from aqis_lab.bench.config import load_config as load_s1
            from aqis_lab.live.prep import Prep
            if not ns.s1_out:
                print("ERROR: prep needs --s1-out, the Sprint 1 results folder", file=sys.stderr)
                return 2
            Prep(cfg, load_s1(DEFAULT_S1_CONFIG), out, ns.s1_out, ns.work_dir, REPO_ROOT).run(only=ns.sets)
            return 0
        from aqis_lab.live import stages
        run = stages.Run(cfg, out, REPO_ROOT)
        if ns.action == "smoke":
            failures = stages.smoke(run, ns.device)
            for failure in failures:
                print(f"SMOKE FAILURE: {failure}", file=sys.stderr)
            return 1 if failures else 0
        if ns.action == "vad":
            stages.run_vad(run, ns.models, ns.conditions, ns.limit)
        elif ns.action == "turn":
            stages.run_turn(run, ns.models, ns.conditions, ns.limit)
        elif ns.action == "stream":
            stages.run_stream(run, ns.models, ns.chunks, ns.conditions, ns.limit)
        else:
            stages.run_emotion(run, ns.models, ns.conditions, ns.limit, ns.device)
        return 0
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
