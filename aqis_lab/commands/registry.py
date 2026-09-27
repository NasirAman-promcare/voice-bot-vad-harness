"""The `registry` command: fetch source datasets, build data/registry/sources.csv, validate a registry file.

CAPABILITIES:
  CAP-REG-005: `python -m aqis_lab registry fetch <dataset>...|all`, `registry build [--out FILE]` and `registry validate [FILE]`, each with --datasets, --cache and --repo-root defaulting to the repository's data/registry/datasets.yaml, data/raw/aqis_lab and the repository root; validate prints OK with row counts per source or one line per problem; build writes the registry atomically and never writes an invalid one; exit 0 success, 1 invalid registry, 2 usage, input, download or I/O error [tests: test_FR_0_4_01_cli_validate_exit_codes, test_FR_0_4_01_build_is_deterministic, test_FR_0_4_05_pack_and_registry_listed_by_dispatcher]
INPUTS AND OUTPUTS: command-line arguments in; the registry file (build), the cache (fetch) and a report on
  stdout, errors on stderr, exit code 0, 1 or 2.
CONTRACTS: registry format and datasets.yaml format 1 (docs/data/REGISTRY_FORMAT.md).
INVARIANTS:
  - build writes through a staging file renamed into place, so a failed build leaves the old registry unchanged.
NOT IN SCOPE:
  - The rules themselves (aqis_lab/registry/).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-01, FR-0.4-02 created.
"""
import argparse
import collections
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASETS = "data/registry/datasets.yaml"
DEFAULT_REGISTRY = "data/registry/sources.csv"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m aqis_lab registry",
                                     description="Source registry: fetch datasets, build and validate "
                                                 "data/registry/sources.csv (docs/data/REGISTRY_FORMAT.md).")
    actions = parser.add_subparsers(dest="action", required=True, metavar="action")

    def common(sub, cache=True):
        sub.add_argument("--repo-root", default=None, help="repository root (default: this checkout)")
        sub.add_argument("--datasets", default=None, help=f"datasets file (default: <repo-root>/{DEFAULT_DATASETS})")
        if cache:
            sub.add_argument("--cache", default=None,
                             help="download and extraction cache (default: <repo-root>/data/raw/aqis_lab)")

    fetch = actions.add_parser("fetch", help="download, check and extract datasets into the cache")
    fetch.add_argument("dataset", nargs="+", help="dataset IDs from the datasets file, or 'all'")
    common(fetch)
    build = actions.add_parser("build", help="regenerate the registry from the fetched datasets and local folders")
    build.add_argument("--out", default=None, help=f"registry file to write (default: <repo-root>/{DEFAULT_REGISTRY})")
    common(build)
    validate = actions.add_parser("validate", help="check a registry file and print every problem")
    validate.add_argument("file", nargs="?", default=None, help=f"registry file (default: <repo-root>/{DEFAULT_REGISTRY})")
    common(validate, cache=False)
    return parser


def _paths(ns):
    from aqis_lab.registry.fetch import DEFAULT_CACHE
    root = Path(ns.repo_root) if ns.repo_root else REPO_ROOT
    datasets = Path(ns.datasets) if ns.datasets else root / DEFAULT_DATASETS
    cache = Path(ns.cache) if getattr(ns, "cache", None) else root / DEFAULT_CACHE
    return root, datasets, cache


def _counts(rows):
    counts = collections.Counter(r.source for r in rows)
    return ", ".join(f"{source} {counts[source]}" for source in sorted(counts))


def main(argv):
    ns = build_parser().parse_args(argv)
    from aqis_lab.registry.datasets import DatasetsError, load_datasets
    from aqis_lab.registry.registry import RegistryValidationError
    root, datasets_path, cache = _paths(ns)
    try:
        datasets = load_datasets(datasets_path)
    except DatasetsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if ns.action == "fetch":
        from aqis_lab.registry.fetch import FetchError, fetch_dataset
        wanted = [d for d, v in datasets.datasets.items() if v["type"] == "download"] if ns.dataset == ["all"] \
            else ns.dataset
        for dataset_id in wanted:
            dataset = datasets.datasets.get(dataset_id)
            if dataset is None or dataset["type"] != "download":
                print(f"ERROR: {dataset_id!r} is not a download dataset in {datasets_path}", file=sys.stderr)
                return 2
            try:
                result = fetch_dataset(dataset, cache, root)
            except FetchError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
            print(f"{dataset_id}: OK, archive {result.archive_path}, extracted {result.extracted_root} "
                  f"(downloaded {result.downloaded_bytes:,} bytes, {'extracted' if result.extracted else 'extraction reused'})")
        return 0
    if ns.action == "build":
        from aqis_lab.registry.importers import SourceImportError, build_registry
        from aqis_lab.registry.registry import registry_bytes
        out = Path(ns.out) if ns.out else root / DEFAULT_REGISTRY
        try:
            rows = build_registry(datasets, cache, root)
        except (SourceImportError, RegistryValidationError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        staging = out.with_name(f".{out.name}.partial")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            staging.write_bytes(registry_bytes(rows))
            os.replace(staging, out)
        except OSError as exc:
            print(f"ERROR: cannot write {out}: {exc.strerror or exc}", file=sys.stderr)
            return 2
        print(f"wrote {out}: {len(rows)} rows ({_counts(rows)})")
        return 0
    from aqis_lab.registry.registry import load_registry
    path = Path(ns.file) if ns.file else root / DEFAULT_REGISTRY
    if not path.is_file():
        print(f"ERROR: cannot read {path}: no such file", file=sys.stderr)
        return 2
    try:
        rows = load_registry(path, datasets, root)
    except RegistryValidationError as exc:
        if any(p.column == "(file)" and p.message.startswith("cannot read") for p in exc.problems):
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        for problem in exc.problems:
            print(f"{path}: line {problem.line} column {problem.column}: {problem.message}")
        print(f"{path}: INVALID, {len(exc.problems)} problem(s)")
        return 1
    print(f"{path}: OK, {len(rows)} rows ({_counts(rows)})")
    return 0
