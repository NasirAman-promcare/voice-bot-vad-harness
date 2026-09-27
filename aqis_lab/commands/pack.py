"""The `pack` command: build a test pack from a pack spec, or verify a built pack folder.

CAPABILITIES:
  CAP-PACK-008: `python -m aqis_lab pack build SPEC --out DIR [--registry FILE] [--datasets FILE] [--cache DIR] [--repo-root DIR]` builds a pack (defaults: the repository's data/registry/sources.csv, data/registry/datasets.yaml and data/raw/aqis_lab) and prints what it wrote; `pack verify DIR` prints one line per problem and a summary with the clip counts per category; exit 0 success, 1 verification failed, 2 usage, input or build error [tests: test_FR_0_4_05_cli_exit_codes, test_FR_0_4_05_pack_and_registry_listed_by_dispatcher, test_FR_0_4_05_build_twice_byte_identical]
INPUTS AND OUTPUTS: command-line arguments in; a pack folder (build) and a report on stdout, errors on stderr, exit
  code 0, 1 or 2.
CONTRACTS: pack-manifest v1; pack spec v1 and the layout (docs/data/SMOKE_PACK.md).
INVARIANTS:
  - A failed build leaves no output folder.
NOT IN SCOPE:
  - Building and checking themselves (aqis_lab/packs/build.py, verify.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-05 created.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab pack",
                                     description="Build a test pack from a pack spec, or verify a built pack "
                                                 "(docs/data/SMOKE_PACK.md).")
    actions = parser.add_subparsers(dest="action", required=True, metavar="action")
    build = actions.add_parser("build", help="build a pack folder from a pack spec")
    build.add_argument("spec", help="pack spec file, such as packs/specs/smoke_v1.yaml")
    build.add_argument("--out", required=True, help="pack folder to create (it must not exist)")
    build.add_argument("--repo-root", default=None, help="repository root (default: this checkout)")
    build.add_argument("--registry", default=None, help="registry (default: <repo-root>/data/registry/sources.csv)")
    build.add_argument("--datasets", default=None, help="datasets file (default: <repo-root>/data/registry/datasets.yaml)")
    build.add_argument("--cache", default=None, help="fetched sources (default: <repo-root>/data/raw/aqis_lab)")
    verify = actions.add_parser("verify", help="recompute every hash of a pack folder and check every entry")
    verify.add_argument("pack", help="pack folder, such as data/packs/smoke/v1")
    return parser


def main(argv):
    ns = build_parser().parse_args(argv)
    if ns.action == "build":
        from aqis_lab.packs.build import BuildError, build_pack
        from aqis_lab.registry.fetch import DEFAULT_CACHE
        root = Path(ns.repo_root) if ns.repo_root else REPO_ROOT
        registry = Path(ns.registry) if ns.registry else root / "data" / "registry" / "sources.csv"
        datasets = Path(ns.datasets) if ns.datasets else root / "data" / "registry" / "datasets.yaml"
        cache = Path(ns.cache) if ns.cache else root / DEFAULT_CACHE
        try:
            result = build_pack(ns.spec, ns.out, registry, datasets, cache, root)
        except BuildError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        counts = {}
        for clip in result.manifest["clips"]:
            counts[clip["split"]] = counts.get(clip["split"], 0) + 1
        print(f"built pack {result.manifest['manifest_id']} {result.manifest['version']} in {result.out}: "
              f"{len(result.manifest['clips'])} clips in {len(result.archives)} archives; "
              + ", ".join(f"{k} {v}" for k, v in counts.items()))
        return 0
    from aqis_lab.packs.verify import VerifyInputError, verify_pack
    try:
        report = verify_pack(ns.pack)
    except VerifyInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for problem in report.problems:
        print(f"{ns.pack}: {problem}")
    print(report.summary())
    return 0 if report.ok else 1
