"""Oracle worker settings: load and check config/aqis_lab/oracle.yaml (setup pin, paths, reserved cores, rclone remote).

CAPABILITIES:
  CAP-ORACLE-001: load() reads oracle.yaml strictly (exact keys, no duplicate keys, schema_version 1.0; setup values as quoted one-line strings the setup script can read; distinct non-negative reserved core numbers; an rclone remote name) and resolves relative paths from the repository root; `python -m aqis_lab.oracle_config get <key>` prints one resolved value for oracle_setup.sh [tests: test_FR_0_6_01_config_committed_values_follow_probe_and_approval, test_FR_0_6_01_config_relative_paths_resolve_from_repository_root_absolute_kept, test_FR_0_6_01_config_rejects_each_malformed_value, test_FR_0_6_01_config_rejects_duplicate_key, test_FR_0_6_01_config_missing_or_unreadable_file_is_an_error, test_FR_0_6_01_config_get_prints_resolved_value, test_FR_0_6_05_drive_destination_is_fixed_by_spec]
INPUTS AND OUTPUTS: a YAML file in; an OracleConfig out; OracleConfigError naming the key on any problem.
CONTRACTS: the file format documented in config/aqis_lab/oracle.yaml and docs/oracle/ORACLE_RUNBOOK.md.
INVARIANTS:
  - A missing or malformed setting is an error naming the key, never a default.
  - Each setup value must be written as `  <key>: "<value>"` on one line, the form oracle_setup.sh reads, and the
    line must hold the same value YAML reads.
  - The Drive destination is fixed (AQIS_LAB/results, FR-0.6-05); it is not a setting.
NOT IN SCOPE:
  - Checking the settings against the machine (aqis_lab/timing/cores.py, aqis_lab/deploy/oracle_setup.sh).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-01 created (also used by FR-0.6-04 and FR-0.6-05).
"""
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "aqis_lab" / "oracle.yaml"
DRIVE_DESTINATION = "AQIS_LAB/results"
SCHEMA_VERSION = "1.0"
SECTIONS = {"schema_version", "setup", "paths", "cores", "rclone"}
SETUP_KEYS = ("architectures", "operating_systems", "min_glibc")
PATH_KEYS = ("work_dir", "doctor_reports", "results_store", "logs")
TOKEN_RE = re.compile(r"[A-Za-z0-9_.+-]+")
OS_RE = re.compile(r"[a-z0-9._-]+:[A-Za-z0-9._-]+")
GLIBC_RE = re.compile(r"\d+\.\d+")
REMOTE_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


class OracleConfigError(ValueError):
    """oracle.yaml is missing, unreadable or malformed."""


class _StrictLoader(yaml.SafeLoader):
    """A safe YAML loader that refuses duplicate mapping keys."""


def _mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class OracleConfig:
    path: Path
    architectures: tuple
    operating_systems: tuple
    min_glibc: str
    work_dir: Path
    doctor_reports: Path
    results_store: Path
    logs: Path
    reserved_for_timing: tuple
    rclone_remote: str

    def get(self, key):
        """The value of a dotted key (such as paths.work_dir) as text, the way oracle_setup.sh reads it."""
        values = {
            "setup.architectures": " ".join(self.architectures),
            "setup.operating_systems": " ".join(self.operating_systems),
            "setup.min_glibc": self.min_glibc,
            **{f"paths.{k}": str(getattr(self, k)) for k in PATH_KEYS},
            "cores.reserved_for_timing": " ".join(str(c) for c in self.reserved_for_timing),
            "rclone.remote": self.rclone_remote,
        }
        if key not in values:
            raise OracleConfigError(f"unknown key {key!r}; known keys: {', '.join(sorted(values))}")
        return values[key]


def _section(data, name, keys, where):
    value = data.get(name)
    if not isinstance(value, dict) or set(value) != set(keys):
        raise OracleConfigError(f"{where}: {name} must hold exactly {', '.join(keys)}")
    return value


def _setup_line_value(text, key, where):
    lines = re.findall(rf'(?m)^  {key}: "([^"\n]*)"[ \t]*(?:#.*)?$', text)
    if len(lines) != 1:
        raise OracleConfigError(f'{where}: setup.{key} must be written once as `  {key}: "<value>"` on one line '
                                f"(oracle_setup.sh reads it before Python exists)")
    return lines[0]


def load(path=None):
    """The checked OracleConfig from `path` (default config/aqis_lab/oracle.yaml)."""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    where = str(path)
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.load(text, Loader=_StrictLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise OracleConfigError(f"{where} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or set(data) != SECTIONS:
        raise OracleConfigError(f"{where} must hold exactly {', '.join(sorted(SECTIONS))}")
    if data["schema_version"] != SCHEMA_VERSION:
        raise OracleConfigError(f'{where}: schema_version must be "{SCHEMA_VERSION}", got {data["schema_version"]!r}')
    setup = _section(data, "setup", SETUP_KEYS, where)
    for key in SETUP_KEYS:
        if not isinstance(setup[key], str) or setup[key] != _setup_line_value(text, key, where):
            raise OracleConfigError(f"{where}: setup.{key} must be a quoted string on one line")
    architectures = tuple(setup["architectures"].split())
    systems = tuple(setup["operating_systems"].split())
    if not architectures or not all(TOKEN_RE.fullmatch(a) for a in architectures):
        raise OracleConfigError(f"{where}: setup.architectures must list machine names such as x86_64, got "
                                f"{setup['architectures']!r}")
    if not systems or not all(OS_RE.fullmatch(s) for s in systems):
        raise OracleConfigError(f"{where}: setup.operating_systems must list ID:VERSION_ID values such as "
                                f"ubuntu:24.04, got {setup['operating_systems']!r}")
    if not GLIBC_RE.fullmatch(setup["min_glibc"]):
        raise OracleConfigError(f"{where}: setup.min_glibc must be a version such as 2.28, got {setup['min_glibc']!r}")
    paths = _section(data, "paths", PATH_KEYS, where)
    resolved = {}
    for key in PATH_KEYS:
        value = paths[key]
        if not isinstance(value, str) or not value.strip():
            raise OracleConfigError(f"{where}: paths.{key} must be a non-empty path, got {value!r}")
        p = Path(value)
        resolved[key] = p if p.is_absolute() else REPO_ROOT / p
    cores = _section(data, "cores", ("reserved_for_timing",), where)["reserved_for_timing"]
    if (not isinstance(cores, list) or not cores
            or not all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in cores)
            or len(set(cores)) != len(cores)):
        raise OracleConfigError(f"{where}: cores.reserved_for_timing must be a non-empty list of distinct CPU "
                                f"numbers (integers >= 0), got {cores!r}")
    remote = _section(data, "rclone", ("remote",), where)["remote"]
    if not isinstance(remote, str) or not REMOTE_RE.fullmatch(remote):
        raise OracleConfigError(f"{where}: rclone.remote must be an rclone remote name (letters, digits, _ . -), "
                                f"got {remote!r}")
    return OracleConfig(path=path, architectures=architectures, operating_systems=systems,
                        min_glibc=setup["min_glibc"], reserved_for_timing=tuple(sorted(cores)), rclone_remote=remote,
                        **resolved)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m aqis_lab.oracle_config",
                                     description="Print one checked value of config/aqis_lab/oracle.yaml.")
    sub = parser.add_subparsers(dest="action", required=True)
    get = sub.add_parser("get", help="print one value, such as paths.work_dir")
    get.add_argument("key")
    get.add_argument("--config", default=None, help=f"settings file (default {DEFAULT_CONFIG})")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        print(load(ns.config).get(ns.key))
    except OracleConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
