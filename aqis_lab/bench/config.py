"""Strict loader for config/aqis_lab/s1.yaml, the one configuration of the Sprint 1 benchmark.

CAPABILITIES:
  CAP-S1-001: load_config() reads s1.yaml and refuses an unknown key, a wrong schema tag, a missing required key, a
    slice that names an unknown source or condition, a model with an unknown stack or role or no Hugging Face ID, a
    stage or caller list that names an unknown slice or model, and an anchor figure missing for an anchor model; the
    SHA-256 of the file's canonical JSON is the config hash recorded with every result [tests:
    test_s1_the_committed_config_loads_and_hashes_its_content, test_s1_config_hash_changes_when_a_value_changes,
    test_s1_config_rejects_what_it_does_not_understand, test_s1_config_missing_file_is_an_error]
INPUTS AND OUTPUTS: a path in; an S1Config out; ConfigError naming the problem.
CONTRACTS: Appendix A of docs/specs/sprints/WP-1.1-S1-asr-benchmark.md plus the additions listed in the config header.
INVARIANTS:
  - No default is invented for a missing key: a missing key is an error.
NOT IN SCOPE:
  - What the values mean to a stage (aqis_lab/bench/run.py, select.py).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "s1-v1"
STACKS = ("hf", "nemo", "qwen")
ROLES = ("live", "heavy")
BOOTSTRAP_UNITS = ("speaker", "utterance")
TOP_KEYS = {"schema", "seed", "normaliser", "bootstrap", "utterance", "sources", "slices", "conditions",
            "default_conditions", "target_conditions", "caller_slices", "models", "optional_models", "stages", "speed",
            "anchor_published_test_other_wer", "gpu"}
SOURCE_KEYS = {"hf", "config", "splits", "licence", "gated", "clean", "git", "registry", "entity_categories",
               "ignored_entity_categories"}
SLICE_KEYS = {"source", "n", "l1", "stratify", "require_entities", "min_digit_tokens", "min_s", "max_s",
              "native_rate_hz", "conditions", "mix", "level_dbfs", "length_s", "balance_roles", "digits_first"}
MODEL_KEYS = {"hf", "stack", "role", "batch", "dtype", "language", "mode", "prompt", "gated", "delay_ms", "licence"}


class ConfigError(ValueError):
    """The Sprint 1 configuration is unreadable or inconsistent."""


@dataclass(frozen=True)
class S1Config:
    raw: dict
    hash: str

    def __getattr__(self, name):
        # raw keys are read as attributes: cfg.seed, cfg.slices, cfg.conditions, cfg.models, ...
        try:
            return self.raw[name]
        except KeyError:
            raise AttributeError(name) from None

    def conditions_for(self, slice_name):
        """The conditions a slice is rendered in: its own list, else default_conditions."""
        return list(self.slices[slice_name].get("conditions", self.default_conditions))

    def stage_conditions(self, stage, slice_name):
        """The conditions a stage runs for a slice: the stage's list within the slice's own, else all of the slice's."""
        own = self.conditions_for(slice_name)
        wanted = self.stages[stage].get("conditions")
        if wanted is None:
            return own
        picked = [c for c in wanted if c in own]
        return picked or own


def _require(mapping, keys, where):
    missing = sorted(set(keys) - set(mapping))
    if missing:
        raise ConfigError(f"{where}: missing {', '.join(missing)}")


def _no_extra(mapping, allowed, where):
    extra = sorted(set(mapping) - set(allowed))
    if extra:
        raise ConfigError(f"{where}: unknown key {', '.join(extra)}")


def _validate(raw):
    if not isinstance(raw, dict):
        raise ConfigError("s1.yaml must hold a mapping")
    _no_extra(raw, TOP_KEYS, "s1.yaml")
    _require(raw, TOP_KEYS, "s1.yaml")
    if raw["schema"] != SCHEMA:
        raise ConfigError(f"s1.yaml: schema is {raw['schema']!r}, this code reads {SCHEMA!r}")
    if raw["normaliser"] != "main":
        raise ConfigError(f"s1.yaml: normaliser must be 'main', got {raw['normaliser']!r}")
    boot = raw["bootstrap"]
    _require(boot, {"resamples", "unit", "ci"}, "bootstrap")
    if boot["unit"] not in BOOTSTRAP_UNITS:
        raise ConfigError(f"bootstrap: unit must be one of {BOOTSTRAP_UNITS}, got {boot['unit']!r}")
    _require(raw["utterance"], {"min_s", "max_s", "min_ref_words"}, "utterance")
    for name, source in raw["sources"].items():
        _no_extra(source, SOURCE_KEYS, f"sources.{name}")
        if not ({"hf", "git", "registry"} & set(source)):
            raise ConfigError(f"sources.{name}: needs hf, git or registry")
        if "hf" in source:
            _require(source, {"licence", "splits", "clean"}, f"sources.{name}")
        if "clean" in source:
            _require(source["clean"], {"strip", "drop_if"}, f"sources.{name}.clean")
    for name, cond in raw["conditions"].items():
        if cond.get("channel") not in (None, "g711_mulaw", "opus"):
            raise ConfigError(f"conditions.{name}: unknown channel {cond['channel']!r}")
    for key in ("default_conditions", "target_conditions"):
        for name in raw[key]:
            if name not in raw["conditions"]:
                raise ConfigError(f"{key}: unknown condition {name}")
    for name, spec in raw["slices"].items():
        _no_extra(spec, SLICE_KEYS, f"slices.{name}")
        _require(spec, {"source", "n"}, f"slices.{name}")
        if spec["source"] not in raw["sources"]:
            raise ConfigError(f"slices.{name}: source {spec['source']!r} is not in sources (nowhere to read it from)")
        for cond in spec.get("conditions", []):
            if cond not in raw["conditions"]:
                raise ConfigError(f"slices.{name}: unknown condition {cond}")
    for name in raw["caller_slices"]:
        if name not in raw["slices"]:
            raise ConfigError(f"caller_slices: unknown slice {name}")
    models = raw["models"]
    for group in ("models", "optional_models"):
        for name, model in raw[group].items():
            _no_extra(model, MODEL_KEYS, f"{group}.{name}")
            _require(model, {"hf", "stack", "role"}, f"{group}.{name}")
            if model["stack"] not in STACKS:
                raise ConfigError(f"{group}.{name}: unknown stack {model['stack']!r} (one of {STACKS})")
            if model["role"] not in ROLES:
                raise ConfigError(f"{group}.{name}: unknown role {model['role']!r} (one of {ROLES})")
    for stage, spec in raw["stages"].items():
        for name in spec.get("slices", []):
            if name not in raw["slices"]:
                raise ConfigError(f"stages.{stage}: unknown slice {name}")
        for name in spec.get("models", []):
            if name not in models:
                raise ConfigError(f"stages.{stage}: unknown model {name}")
        for name in spec.get("conditions", []):
            if name not in raw["conditions"]:
                raise ConfigError(f"stages.{stage}: unknown condition {name}")
    anchor = raw["anchor_published_test_other_wer"]
    for name in raw["stages"]["anchor"]["models"]:
        if name not in anchor:
            raise ConfigError(f"anchor_published_test_other_wer: no published figure for {name}")


def load_config(path):
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path.name} is unreadable: {exc}") from exc
    _validate(raw)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return S1Config(raw, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
