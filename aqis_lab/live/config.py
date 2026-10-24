"""Strict loader for config/aqis_lab/s2.yaml, the one configuration of the Sprint 2 live-stack benchmark.

CAPABILITIES:
  CAP-S2-001: load_config() reads s2.yaml and refuses an unknown key, a wrong schema tag, a missing required key, an unknown
    model name under vad or emotion, a WebRTC mode outside 0 to 3, a threshold outside 0 to 1, an empty or non-positive
    list of timer thresholds, chunk sizes or collars, a non-positive real-time target and a condition no Sprint 1
    condition defines; the SHA-256 of the file's canonical JSON is the config hash recorded with every result;
    vad_supported() says whether a VAD has a build for a CPU architecture [tests:
    test_s2_the_committed_config_loads_and_hashes_its_content, test_s2_ten_vad_runs_only_where_it_has_a_build,
    test_s2_config_hash_changes_when_a_value_changes, test_s2_config_rejects_what_it_does_not_understand,
    test_s2_missing_config_file_is_an_error]
INPUTS AND OUTPUTS: a path in; an S2Config out; ConfigError naming the problem.
CONTRACTS: Appendix A of docs/specs/sprints/WP-1.2-S2-live-stack.md plus the additions listed in the config header.
INVARIANTS:
  - No default is invented for a missing key: a missing key is an error.
NOT IN SCOPE:
  - What the values mean to a stage (the stage modules).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "s2-v1"
TOP_KEYS = {"schema", "seed", "s1", "conditions", "scoring", "data", "vad", "turn_end", "stt_streaming", "emotion"}
COMPONENTS = ("vad", "turn", "stream", "emotion")
VAD_NAMES = {"silero_v5", "silero_v4", "firered_vad", "webrtc_vad", "ten_vad"}
EMOTION_NAMES = {"emotion2vec_seed", "emotion2vec_base", "wav2vec2_er", "acoustic_baseline"}
SCORING_KEYS = {"bootstrap", "collars_ms", "primary_collar_ms", "vad_reference_merge_gap_ms", "det_thresholds", "gates"}
TURN_KEYS = {"fixed_thresholds_ms", "predictive", "min_pause_ms", "trail_ms", "vad"}
GATE_KEYS = {"far_max", "mdr_max", "onset_p50_ms_max", "fir_max", "endpoint_p50_ms_max", "chunk_latency_ms_max",
             "frustration_recall_phone_min", "frustration_recall_target"}
STT_KEYS = {"model", "variants", "chunk_sizes_ms", "target_rtf_max", "target_chunk_latency_ms", "window_ms", "threads", "utterances"}


class ConfigError(ValueError):
    """The Sprint 2 configuration is unreadable or inconsistent."""


@dataclass(frozen=True)
class S2Config:
    raw: dict
    hash: str

    def __getattr__(self, name):
        try:
            return self.raw[name]
        except KeyError:
            raise AttributeError(name) from None

    def vad_supported(self, name, arch):
        """False when the VAD lists the architectures it has a build for and `arch` is not one of them."""
        archs = self.vad[name].get("supported_arch")
        return archs is None or arch in archs


def _require(mapping, keys, where):
    missing = sorted(set(keys) - set(mapping))
    if missing:
        raise ConfigError(f"{where}: missing {', '.join(missing)}")


def _no_extra(mapping, allowed, where):
    extra = sorted(set(mapping) - set(allowed))
    if extra:
        raise ConfigError(f"{where}: unknown key {', '.join(extra)}")


def _positive_list(values, where):
    if not isinstance(values, list) or not values or any(not isinstance(v, (int, float)) or v <= 0 for v in values):
        raise ConfigError(f"{where}: must be a non-empty list of positive numbers, got {values!r}")


def _validate(raw, s1_conditions):
    if not isinstance(raw, dict):
        raise ConfigError("s2.yaml must hold a mapping")
    _no_extra(raw, TOP_KEYS, "s2.yaml")
    _require(raw, TOP_KEYS, "s2.yaml")
    if raw["schema"] != SCHEMA:
        raise ConfigError(f"s2.yaml: schema is {raw['schema']!r}, this code reads {SCHEMA!r}")
    _require(raw["conditions"], COMPONENTS, "conditions")
    _no_extra(raw["conditions"], COMPONENTS, "conditions")
    for component, names in raw["conditions"].items():
        for name in names:
            if name not in s1_conditions:
                raise ConfigError(f"conditions.{component}: {name!r} is not a condition of the Sprint 1 config "
                                  f"({', '.join(s1_conditions)})")
    scoring = raw["scoring"]
    _no_extra(scoring, SCORING_KEYS, "scoring")
    _require(scoring, SCORING_KEYS, "scoring")
    _require(scoring["bootstrap"], {"resamples", "ci"}, "scoring.bootstrap")
    if not isinstance(scoring["collars_ms"], list) or not scoring["collars_ms"] or any(c < 0 for c in scoring["collars_ms"]):
        raise ConfigError(f"scoring.collars_ms: must be a non-empty list of numbers of at least 0, got {scoring['collars_ms']!r}")
    if scoring["primary_collar_ms"] not in scoring["collars_ms"]:
        raise ConfigError(f"scoring.primary_collar_ms: {scoring['primary_collar_ms']!r} is not one of collars_ms {scoring['collars_ms']}")
    _require(scoring["gates"], GATE_KEYS, "scoring.gates")
    _no_extra(scoring["gates"], GATE_KEYS, "scoring.gates")
    for name, spec in raw["vad"].items():
        if name not in VAD_NAMES:
            raise ConfigError(f"vad: unknown VAD {name!r} (one of {', '.join(sorted(VAD_NAMES))})")
        if "threshold" in spec and not 0 < spec["threshold"] < 1:
            raise ConfigError(f"vad.{name}: threshold must be between 0 and 1, got {spec['threshold']!r}")
    webrtc = raw["vad"].get("webrtc_vad", {})
    modes = list(webrtc.get("modes", [])) + ([webrtc["mode"]] if "mode" in webrtc else [])
    for mode in modes:
        if mode not in (0, 1, 2, 3):
            raise ConfigError(f"vad.webrtc_vad: mode {mode!r} is not one of 0, 1, 2, 3")
    turn = raw["turn_end"]
    _no_extra(turn, TURN_KEYS, "turn_end")
    _require(turn, TURN_KEYS, "turn_end")
    _positive_list(turn["fixed_thresholds_ms"], "turn_end.fixed_thresholds_ms")
    if turn["vad"] not in raw["vad"]:
        raise ConfigError(f"turn_end.vad: {turn['vad']!r} is not a VAD of the vad block")
    stt = raw["stt_streaming"]
    _no_extra(stt, STT_KEYS, "stt_streaming")
    _require(stt, {"model", "chunk_sizes_ms", "target_rtf_max"}, "stt_streaming")
    _positive_list(stt["chunk_sizes_ms"], "stt_streaming.chunk_sizes_ms")
    if not isinstance(stt["target_rtf_max"], (int, float)) or stt["target_rtf_max"] <= 0:
        raise ConfigError(f"stt_streaming.target_rtf_max: must be positive, got {stt['target_rtf_max']!r}")
    for name in raw["emotion"]:
        if name not in EMOTION_NAMES:
            raise ConfigError(f"emotion: unknown model {name!r} (one of {', '.join(sorted(EMOTION_NAMES))})")


def load_config(path, s1_path=None):
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path.name} is unreadable: {exc}") from exc
    s1_file = Path(s1_path) if s1_path else Path(__file__).resolve().parents[2] / (raw or {}).get("s1", {}).get(
        "config", "config/aqis_lab/s1.yaml")
    try:
        s1_conditions = yaml.safe_load(s1_file.read_text(encoding="utf-8"))["conditions"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise ConfigError(f"the Sprint 1 config {s1_file} cannot be read for its conditions: {exc}") from exc
    _validate(raw, s1_conditions)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return S2Config(raw, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
