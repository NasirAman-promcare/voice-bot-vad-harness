"""Strict loader for config/aqis_lab/s3.yaml, the one configuration of the Sprint 3 cascade and fine-tuning work.

CAPABILITIES:
  CAP-S3-001: load_config() reads s3.yaml and refuses an unknown key, a wrong schema tag, a missing required key, a model that is
    not a Sprint 1 model, a heavy list that is empty or holds the stage 1 model, unsorted or out-of-range escalation rates, an
    unknown policy or feature, a missing cost entry for a heavy model, a condition no Sprint 1 condition defines, a LoRA rank
    of 0 or an empty module pattern, an early-stopping patience below 1, a validation share outside 0 to 0.5, and a threshold
    outside 0 to 1; the SHA-256 of the file's canonical JSON is the config hash recorded with every result [tests:
    test_s3_the_committed_config_loads_and_hashes_its_content, test_s3_config_hash_changes_when_a_value_changes,
    test_s3_config_rejects_what_it_does_not_understand, test_s3_missing_config_file_is_an_error,
    test_s3_condition_mix_weights_sum_to_one]
INPUTS AND OUTPUTS: a path in; an S3Config out; ConfigError naming the problem.
CONTRACTS: brief sections 2 and 4.
INVARIANTS:
  - No default is invented for a missing key: a missing key is an error.
NOT IN SCOPE:
  - What the values mean to a stage (the stage modules).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "s3-v1"
TOP_KEYS = {"schema", "seed", "s1", "cascade", "prompt", "train", "eval", "bootstrap"}
POLICIES = ("random", "duration", "words_per_s", "digits", "channel", "nonspeech", "confidence", "entropy", "hybrid")
FEATURES = ("duration_s", "words_per_s", "digit_tokens", "is_phone", "is_webrtc", "nonspeech_ratio", "confidence", "entropy")
CASCADE_KEYS = {"stage1", "heavy", "target_wer_max", "escalation_max", "rates", "folds", "min_gain_errors", "policies",
                "channel_risk", "hybrid_features", "hybrid", "cost", "nonspeech", "confidence"}
PROMPT_KEYS = {"models", "slices", "conditions", "terms", "numbers_hint"}
TRAIN_KEYS = {"base", "source", "max_train_utts", "val_fraction", "condition_mix", "lora", "optim", "early_stopping"}
EVAL_KEYS = {"slices", "drug_recall_min", "us_conv_wer_increase_max", "category"}


class ConfigError(ValueError):
    """The Sprint 3 configuration is unreadable or inconsistent."""


@dataclass(frozen=True)
class S3Config:
    raw: dict
    hash: str

    def __getattr__(self, name):
        try:
            return self.raw[name]
        except KeyError:
            raise AttributeError(name) from None


def _require(mapping, keys, where):
    if not isinstance(mapping, dict):
        raise ConfigError(f"{where}: must be a mapping")
    missing = sorted(set(keys) - set(mapping))
    if missing:
        raise ConfigError(f"{where}: missing {', '.join(missing)}")


def _no_extra(mapping, allowed, where):
    extra = sorted(set(mapping) - set(allowed))
    if extra:
        raise ConfigError(f"{where}: unknown key {', '.join(extra)}")


def _fraction(value, where, low=0.0, high=1.0, inclusive_low=False):
    ok = isinstance(value, (int, float)) and (low <= value if inclusive_low else low < value) and value <= high
    if not ok:
        raise ConfigError(f"{where}: must be a number in {'[' if inclusive_low else '('}{low}, {high}], got {value!r}")


def _positive_int(value, where):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{where}: must be a whole number of at least 1, got {value!r}")


def _validate(raw, s1):
    _no_extra(raw, TOP_KEYS, "s3.yaml")
    _require(raw, TOP_KEYS, "s3.yaml")
    if raw["schema"] != SCHEMA:
        raise ConfigError(f"s3.yaml: schema is {raw['schema']!r}, this code reads {SCHEMA!r}")
    models, conditions = set(s1["models"]), set(s1["conditions"])

    def model(name, where):
        if name not in models:
            raise ConfigError(f"{where}: {name!r} is not a Sprint 1 model ({', '.join(sorted(models))})")

    cas = raw["cascade"]
    _no_extra(cas, CASCADE_KEYS, "cascade")
    _require(cas, CASCADE_KEYS, "cascade")
    model(cas["stage1"], "cascade.stage1")
    if not isinstance(cas["heavy"], list) or not cas["heavy"]:
        raise ConfigError("cascade.heavy: must be a non-empty list of models")
    for name in cas["heavy"]:
        model(name, "cascade.heavy")
        if name == cas["stage1"]:
            raise ConfigError(f"cascade.heavy: {name!r} is the stage1 model; a heavy model must differ from stage1")
        if name not in cas["cost"]["heavy"]:
            raise ConfigError(f"cascade.cost.heavy: no rtfx and latency for {name}")
    _fraction(cas["target_wer_max"], "cascade.target_wer_max")
    _fraction(cas["escalation_max"], "cascade.escalation_max")
    rates = cas["rates"]
    if (not isinstance(rates, list) or not rates or rates != sorted(set(rates)) or rates[0] != 0 or rates[-1] != 1
            or any(not isinstance(r, (int, float)) or not 0 <= r <= 1 for r in rates)):
        raise ConfigError("cascade.rates: must be a sorted list of distinct numbers from 0 to 1 that starts at 0 and ends at 1")
    if not isinstance(cas["folds"], int) or cas["folds"] < 2:
        raise ConfigError(f"cascade.folds: must be a whole number of at least 2, got {cas['folds']!r}")
    _positive_int(cas["min_gain_errors"], "cascade.min_gain_errors")
    for name in cas["policies"]:
        if name not in POLICIES:
            raise ConfigError(f"cascade.policies: unknown policy {name!r} (one of {', '.join(POLICIES)})")
    for name in cas["hybrid_features"]:
        if name not in FEATURES:
            raise ConfigError(f"cascade.hybrid_features: unknown feature {name!r} (one of {', '.join(FEATURES)})")
    _require(cas["cost"], {"live_rtfx", "heavy"}, "cascade.cost")

    pr = raw["prompt"]
    _no_extra(pr, PROMPT_KEYS, "prompt")
    _require(pr, PROMPT_KEYS, "prompt")
    for name in pr["models"]:
        model(name, "prompt.models")
        if name not in ("granite-speech-4.1-2b", "qwen3-asr-1.7b"):
            raise ConfigError(f"prompt.models: {name!r} has no context or keyword prompt (granite-speech-4.1-2b and qwen3-asr-1.7b do)")
    for name in pr["conditions"]:
        if name not in conditions:
            raise ConfigError(f"prompt.conditions: {name!r} is not a Sprint 1 condition ({', '.join(sorted(conditions))})")

    tr = raw["train"]
    _no_extra(tr, TRAIN_KEYS, "train")
    _require(tr, TRAIN_KEYS, "train")
    model(tr["base"], "train.base")
    if tr["base"] != "qwen3-asr-1.7b":
        raise ConfigError(f"train.base: {tr['base']!r} has no LoRA recipe here (qwen3-asr-1.7b does)")
    _fraction(tr["val_fraction"], "train.val_fraction", 0.0, 0.5)
    for name, weight in tr["condition_mix"].items():
        if name not in conditions:
            raise ConfigError(f"train.condition_mix: {name!r} is not a Sprint 1 condition ({', '.join(sorted(conditions))})")
        _fraction(weight, f"train.condition_mix.{name}")
    lora = tr["lora"]
    _require(lora, {"r", "alpha", "dropout", "target_modules"}, "train.lora")
    _positive_int(lora["r"], "train.lora.r (the LoRA rank)")
    _positive_int(lora["alpha"], "train.lora.alpha")
    if not isinstance(lora["target_modules"], str) or not lora["target_modules"].strip():
        raise ConfigError("train.lora.target_modules: must be a non-empty regular expression")
    _fraction(lora["dropout"], "train.lora.dropout", 0.0, 0.9, inclusive_low=True)
    _positive_int(tr["early_stopping"]["patience"], "train.early_stopping.patience")

    ev = raw["eval"]
    _no_extra(ev, EVAL_KEYS, "eval")
    _require(ev, EVAL_KEYS, "eval")
    _fraction(ev["drug_recall_min"], "eval.drug_recall_min")
    _fraction(ev["us_conv_wer_increase_max"], "eval.us_conv_wer_increase_max", 0.0, 1.0)

    _require(raw["bootstrap"], {"resamples", "ci"}, "bootstrap")
    _positive_int(raw["bootstrap"]["resamples"], "bootstrap.resamples")
    _fraction(raw["bootstrap"]["ci"], "bootstrap.ci")


def load_config(path, s1_path=None):
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path.name} is unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path.name} must hold a mapping")
    s1_file = Path(s1_path) if s1_path else Path(__file__).resolve().parents[2] / raw.get("s1", {}).get("config", "config/aqis_lab/s1.yaml")
    try:
        s1 = yaml.safe_load(s1_file.read_text(encoding="utf-8"))
        s1 = {"models": s1["models"], "conditions": s1["conditions"]}
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise ConfigError(f"the Sprint 1 config {s1_file} cannot be read for its models and conditions: {exc}") from exc
    _validate(raw, s1)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return S3Config(raw, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
