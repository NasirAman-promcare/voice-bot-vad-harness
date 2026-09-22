"""
orchestrator.py — ★ MASTER FILE

One Job:
    The single coordination hub of the VAD benchmark harness. Reads and validates
    config/run_config.yaml, instantiates the required modules across their agreed
    contracts, executes Tier 1 (offline frame bench) and Tier 2 (live Jitsi pipeline),
    enforces concurrency and hardware policies, applies cold-start warm-up discarding,
    and isolates faults so that no individual clip or adapter failure crashes a run.

The Single Deliberate Boundary Exception:
    This is the ONLY file in the entire project permitted to import across multiple
    subsystems (corpus, vad_adapters, scoring, storage, latency, bots, audio_profiler,
    webrtc_bridge). Every other module remains strictly unaware of sibling internals.

What this module must NEVER do:
    - Never perform mathematical scoring, resampling, profiling, or latency calculations
      internally; all computations are delegated strictly outward to domain modules.
    - Never let a failure in one adapter or clip terminate the evaluation of others.
    - Never silently fall back across hardware policies (e.g. CPU fallback when GPU requested).
    - Never allow parallel adapter execution when concurrency_mode is set to 'sequential' for timing.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import yaml



# Core Contracts & Subsystems
from corpus.manifest import Manifest, ManifestEntry, load_manifest
from scoring.vad_scorer import (
    ClipScoreResult,
    VADScorerReport,
    score_adapter_evaluation,
    score_single_clip,
)
from storage.results_store import ResultsStore, get_vad_library_version
import dataclasses
from vad_adapters.adapter_contract import (
    DecisionRecord,
    VADAdapterContract,
    chunk_audio_stream,
)
from vad_adapters.adapter_registry import (
    UnknownAdapterError,
    build_active_adapters,
    resolve_active_adapter_names,
)

# Optional / Downstream Modules
try:
    from audio_profiler import profile_audio_clip
except ImportError:
    profile_audio_clip = None

try:
    from scoring.correlation_engine import correlate_profiles_and_scores
except ImportError:
    correlate_profiles_and_scores = None

try:
    from bots.speaker_bot import SpeakerBot
except ImportError:
    SpeakerBot = None

try:
    from bots.listener_bot import ListenerBot
except ImportError:
    ListenerBot = None

try:
    from latency.marker_alignment import align_marker
except ImportError:
    align_marker = None

try:
    from latency.latency_calculator import calculate_pipeline_latency
except ImportError:
    calculate_pipeline_latency = None

# WebRTC Bridge Subsystem for Tier 2 Live WebRTC Pipeline
try:
    from webrtc_bridge.injector import WebRTCJitsiAudioInjector
except ImportError:
    WebRTCJitsiAudioInjector = None

try:
    from webrtc_bridge.listener_bridge import JitsiListenerBridge
except ImportError:
    JitsiListenerBridge = None

# Configure structured unbuffered logging
logger = logging.getLogger("orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(stream_handler)


# ==============================================================================
# Configuration Schema & Loader (The ONLY direct reader of run_config.yaml)
# ==============================================================================

@dataclass(frozen=True)
class RunConfig:
    """Immutable representation of declarative run parameters."""
    run_id: str
    tiers_to_run: Tuple[str, ...]
    active_adapters: Tuple[str, ...]
    webrtc_aggressiveness_modes: Tuple[int, ...]
    corpus_manifest_path: str
    corpus_category_filter: Tuple[str, ...]
    hardware_policy: str
    warmup_clip_count: int
    scoring_grid_ms: int
    decision_threshold: float
    concurrency_mode: str
    include_held_out_slice: bool
    results_destination: str
    jitsi_room: str
    bridge_url: str


def load_run_config(config_path: Union[str, Path]) -> RunConfig:
    """
    Parses and validates config/run_config.yaml.

    Enforces startup validation: fails fast if required keys are missing, adapter
    names are unrecognized, or hardware policies cannot be satisfied.
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path.resolve()}")

    with open(path, mode="r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML in '{path}': {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Root of configuration file '{path}' must be a mapping.")

    # Validate required keys
    required_keys = [
        "run_id", "tiers_to_run", "active_adapters", "webrtc_aggressiveness_modes",
        "corpus_manifest_path", "corpus_category_filter", "hardware_policy",
        "warmup_clip_count", "scoring_grid_ms", "concurrency_mode",
        "include_held_out_slice", "results_destination", "jitsi_room", "bridge_url",
    ]
    missing_keys = [k for k in required_keys if k not in raw]
    if missing_keys:
        raise ValueError(f"Configuration file '{path}' is missing required keys: {missing_keys}")

    # Validate execution tiers
    tiers = tuple(str(t).strip().lower() for t in raw["tiers_to_run"])
    valid_tiers = {"tier1", "tier2"}
    invalid_tiers = set(tiers) - valid_tiers
    if invalid_tiers or not tiers:
        raise ValueError(f"Invalid tiers_to_run: {tiers}. Allowed subset of: {valid_tiers}")

    # Validate hardware policy
    hardware_policy = str(raw["hardware_policy"]).strip()
    if hardware_policy not in ("cpu_only", "gpu_for_firered"):
        raise ValueError(
            f"Invalid hardware_policy: '{hardware_policy}'. Must be 'cpu_only' or 'gpu_for_firered'."
        )

    # Fail fast: verify GPU capability if gpu_for_firered is explicitly chosen
    if hardware_policy == "gpu_for_firered":
        try:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "hardware_policy is set to 'gpu_for_firered', but PyTorch reports CUDA is NOT available. "
                    "Refusing to run with silent CPU fallback to prevent invalid latency comparisons."
                )
        except ImportError as exc:
            raise RuntimeError(
                "hardware_policy 'gpu_for_firered' requires PyTorch with CUDA support, but torch is not installed."
            ) from exc

    # Validate concurrency mode
    concurrency_mode = str(raw["concurrency_mode"]).strip().lower()
    if concurrency_mode not in ("sequential", "parallel"):
        raise ValueError(f"Invalid concurrency_mode: '{concurrency_mode}'. Must be 'sequential' or 'parallel'.")

    # Validate WebRTC modes
    webrtc_modes = tuple(int(m) for m in raw.get("webrtc_aggressiveness_modes", [0, 1, 2, 3]))
    for mode in webrtc_modes:
        if mode not in (0, 1, 2, 3):
            raise ValueError(f"Invalid WebRTC mode: {mode}. Must be 0, 1, 2, or 3.")

    # Validate adapter names against registry at startup (Fail Fast)
    raw_adapters = tuple(str(a).strip() for a in raw["active_adapters"])
    try:
        resolved_adapters = resolve_active_adapter_names(raw_adapters, webrtc_modes=webrtc_modes)
        if not resolved_adapters:
            raise ValueError("No active adapters resolved from configuration.")
    except UnknownAdapterError as exc:
        raise ValueError(f"Configuration specifies unrecognized active adapter: {exc}") from exc

    base_run_id = str(raw["run_id"]).strip()
    # Append unique UTC timestamp to prevent log collision across attempts (K14)
    timestamp_suffix = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    run_id = f"{base_run_id}_{timestamp_suffix}" if not base_run_id.endswith(timestamp_suffix) else base_run_id

    return RunConfig(
        run_id=run_id,
        tiers_to_run=tiers,
        active_adapters=raw_adapters,
        webrtc_aggressiveness_modes=webrtc_modes,
        corpus_manifest_path=str(raw["corpus_manifest_path"]).strip(),
        corpus_category_filter=tuple(str(c).strip() for c in raw.get("corpus_category_filter", [])),
        hardware_policy=hardware_policy,
        warmup_clip_count=max(0, int(raw.get("warmup_clip_count", 5))),
        scoring_grid_ms=max(1, int(raw.get("scoring_grid_ms", 10))),
        decision_threshold=float(raw.get("decision_threshold", 0.5)),
        concurrency_mode=concurrency_mode,
        include_held_out_slice=bool(raw.get("include_held_out_slice", False)),
        results_destination=str(raw["results_destination"]).strip(),
        jitsi_room=str(raw["jitsi_room"]).strip(),
        bridge_url=str(raw["bridge_url"]).strip(),
    )


# ==============================================================================
# Audio I/O Utility (16kHz Mono Float32 Loader with Directory Resolution)
# ==============================================================================

def read_audio_16k_mono(clip_path: Union[str, Path]) -> Tuple[np.ndarray, int]:
    """
    Loads an audio file as a 1D float32 NumPy array at 16000 Hz.

    Handles mono downmixing, sample rate validation, and automatic corpus/audio directory resolution.
    """
    path = Path(clip_path)
    if not path.is_file():
        candidate = Path("corpus/audio") / path.name
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"Audio file does not exist: {path.resolve()} (also checked {candidate.resolve()})")

    try:
        import soundfile as sf
        audio_data, sr = sf.read(str(path), dtype="float32")
    except Exception as exc:
        raise RuntimeError(f"Failed to read audio file '{path}': {exc}") from exc

    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1, dtype=np.float32)

    if sr != 16000:
        raise ValueError(f"Audio file '{path}' has sample rate {sr} Hz. Expected 16000 Hz.")

    return np.ascontiguousarray(audio_data, dtype=np.float32), len(audio_data)


# ==============================================================================
# Tier 1 Control Flow: Offline Bench
# ==============================================================================

def run_tier1_offline_bench(
    config: RunConfig,
    manifest: Manifest,
    results_store: ResultsStore,
) -> Dict[str, VADScorerReport]:
    """
    Executes Tier 1: Local frame-by-frame offline evaluation.
    """
    logger.info("=== Starting Tier 1 Offline Evaluation [Run ID: %s] ===", config.run_id)
    sys.stdout.flush()

    adapters = build_active_adapters(
        active_adapters=config.active_adapters,
        webrtc_modes=config.webrtc_aggressiveness_modes,
        hardware_policy=config.hardware_policy,
    )
    logger.info("Instantiated %d active adapter operating point(s): %s", len(adapters), list(adapters.keys()))
    sys.stdout.flush()

    adapter_clip_results: Dict[str, List[ClipScoreResult]] = {name: [] for name in adapters}
    audio_profiles: Dict[str, Dict[str, Any]] = {}

    for clip_idx, entry in enumerate(manifest):
        is_warmup = clip_idx < config.warmup_clip_count
        logger.info(
            "Tier 1 clip [%d/%d] '%s' (Category: '%s', Warmup: %s)",
            clip_idx + 1,
            len(manifest),
            entry.clip_id,
            entry.category,
            is_warmup,
        )
        sys.stdout.flush()

        target_path = getattr(entry, "clip_path", None) or entry.clip_id
        try:
            audio_samples, total_samples = read_audio_16k_mono(target_path)
        except Exception as exc:
            logger.error(
                "[Run %s | Tier 1 | Clip %s] Failed to load audio: %s",
                config.run_id,
                entry.clip_id,
                exc,
            )
            results_store.store_clip_failure(
                run_id=config.run_id,
                manifest_version=manifest.version_hash,
                adapter_id="all",
                clip_id=entry.clip_id,
                tier="tier1",
                stage="audio_load",
                error=str(exc),
            )
            continue

        if profile_audio_clip is not None and entry.clip_id not in audio_profiles:
            try:
                profile_data = profile_audio_clip(audio_samples, sample_rate_hz=16000)
                audio_profiles[entry.clip_id] = profile_data
                results_store.store_audio_profile(
                    run_id=config.run_id,
                    manifest_version=manifest.version_hash,
                    clip_id=entry.clip_id,
                    profile_data=profile_data,
                )
            except Exception as exc:
                logger.error(
                    "[Run %s | Tier 1 | Clip %s | AudioProfiler] Profiling failed: %s",
                    config.run_id,
                    entry.clip_id,
                    exc,
                )

        for adapter_name, adapter in adapters.items():
            adapter_records: List[DecisionRecord] = []
            frame_compute_times_ns: List[int] = []

            try:
                adapter.reset()
                chunks = list(chunk_audio_stream(audio_samples, adapter.frame_size_samples, 16000))

                for chunk in chunks:
                    t0 = time.perf_counter_ns()
                    record = adapter.process_frame(
                        frame=chunk.samples,
                        sample_offset=chunk.sample_offset,
                        frame_index=chunk.frame_index,
                    )
                    t1 = time.perf_counter_ns()

                    adapter_records.append(record)
                    frame_compute_times_ns.append(t1 - t0)

            except Exception as exc:
                logger.error(
                    "[Run %s | Tier 1 | Clip %s | Adapter %s] Frame processing failed: %s",
                    config.run_id,
                    entry.clip_id,
                    adapter_name,
                    exc,
                    exc_info=True,
                )
                results_store.store_clip_failure(
                    run_id=config.run_id,
                    manifest_version=manifest.version_hash,
                    adapter_id=adapter_name,
                    clip_id=entry.clip_id,
                    tier="tier1",
                    stage="frame_processing",
                    error=str(exc),
                )
                continue

            if is_warmup:
                logger.debug(
                    "Discarded warm-up clip '%s' for adapter '%s' (absorbs cold-start).",
                    entry.clip_id,
                    adapter_name,
                )
                continue

            try:
                clip_score = score_single_clip(
                    decision_records=adapter_records,
                    manifest_entry=entry,
                    total_clip_samples=total_samples,
                    scoring_grid_ms=config.scoring_grid_ms,
                    sample_rate_hz=16000,
                    decision_threshold=config.decision_threshold,
                )
                adapter_clip_results[adapter_name].append(clip_score)

                

                results_store.store_clip_score_result(
                    run_id=config.run_id,
                    manifest_version=manifest.version_hash,
                    clip_score_result=clip_score,
                    tier="tier1",
                )

                if frame_compute_times_ns:
                    timings_ms = [t / 1e6 for t in frame_compute_times_ns]
                    latency_payload = {
                        "frame_count": len(timings_ms),
                        "mean_compute_ms": float(np.mean(timings_ms)),
                        "p50_compute_ms": float(np.percentile(timings_ms, 50)),
                        "p95_compute_ms": float(np.percentile(timings_ms, 95)),
                        "p99_compute_ms": float(np.percentile(timings_ms, 99)),
                        "max_compute_ms": float(np.max(timings_ms)),
                    }
                    results_store.store_latency_measurement(
                        run_id=config.run_id,
                        manifest_version=manifest.version_hash,
                        adapter_id=adapter_name,
                        clip_id=entry.clip_id,
                        latency_data=latency_payload,
                        record_type="tier1_algorithmic_latency",
                        tier="tier1",
                    )

            except Exception as exc:
                logger.error(
                    "[Run %s | Tier 1 | Clip %s | Adapter %s] Scoring failed: %s",
                    config.run_id,
                    entry.clip_id,
                    adapter_name,
                    exc,
                )
                results_store.store_clip_failure(
                    run_id=config.run_id,
                    manifest_version=manifest.version_hash,
                    adapter_id=adapter_name,
                    clip_id=entry.clip_id,
                    tier="tier1",
                    stage="scoring",
                    error=str(exc),
                )
                continue

    reports: Dict[str, VADScorerReport] = {}
    for adapter_name, scored_clips in adapter_clip_results.items():
        report = score_adapter_evaluation(
            clip_results=scored_clips,
            scoring_grid_ms=config.scoring_grid_ms,
        )
        reports[adapter_name] = report
        logger.info(
            "Tier 1 Completed for '%s': Evaluated %d clips | Precision: %.3f | Recall: %.3f | F1: %.3f",
            adapter_name,
            len(scored_clips),
            report.overall_metrics.metrics.precision,
            report.overall_metrics.metrics.recall,
            report.overall_metrics.metrics.f1,
        )
        sys.stdout.flush()

    if correlate_profiles_and_scores is not None and audio_profiles:
        try:
            for adapter_name, scored_clips in adapter_clip_results.items():
                correlation_report = correlate_profiles_and_scores(
                    profiles=list(audio_profiles.values()),
                    scores=scored_clips,
                )
                results_store.store_latency_measurement(
                    run_id=config.run_id,
                    manifest_version=manifest.version_hash,
                    adapter_id=adapter_name,
                    clip_id="all_clips",
                    latency_data=correlation_report,
                    record_type="tier1_correlation_heatmap",
                )
        except Exception as exc:
            logger.error("[Run %s | Tier 1 | CorrelationEngine] Correlation failed: %s", config.run_id, exc)

    return reports


# ==============================================================================
# Tier 2 Control Flow: Live Pipeline (Jitsi WebRTC Bridge)
# ==============================================================================

def run_tier2_live_pipeline(
    config: RunConfig,
    manifest: Manifest,
    results_store: ResultsStore,
) -> Dict[str, VADScorerReport]:
    """
    Executes Tier 2: Real live pipeline evaluation via Speaker and Listener Bots.
    """
    logger.info("=== Starting Tier 2 Live Pipeline Evaluation [Run ID: %s] ===", config.run_id)
    sys.stdout.flush()

    if SpeakerBot is None or ListenerBot is None:
        raise RuntimeError(
            "Tier 2 execution requires bots/speaker_bot.py and bots/listener_bot.py."
        )
    if align_marker is None or calculate_pipeline_latency is None:
        raise RuntimeError(
            "Tier 2 execution requires latency/marker_alignment.py and latency/latency_calculator.py."
        )

    adapters = build_active_adapters(
        active_adapters=config.active_adapters,
        webrtc_modes=config.webrtc_aggressiveness_modes,
        hardware_policy=config.hardware_policy,
    )

    # 1. Initialize SpeakerBot with WebRTC Injector
    if WebRTCJitsiAudioInjector is not None:
        logger.info("Using WebRTCJitsiAudioInjector for live WebRTC microphone injection.")
        injector = WebRTCJitsiAudioInjector()
        speaker_bot = SpeakerBot(
            room_id=config.jitsi_room,
            bridge_url=config.bridge_url,
            injector=injector,
        )
    else:
        logger.warning("WebRTCJitsiAudioInjector not available; using default injector.")
        speaker_bot = SpeakerBot(
            room_id=config.jitsi_room,
            bridge_url=config.bridge_url,
        )

    # 2. Initialize ListenerBot and connect JitsiListenerBridge
    listener_bot = ListenerBot(
        room_id=config.jitsi_room,
        bridge_url=config.bridge_url,
        adapters=adapters,
        scoring_grid_ms=config.scoring_grid_ms,
        concurrency_mode=config.concurrency_mode,
    )

    listener_bridge = None
    if JitsiListenerBridge is not None:
        logger.info("Using JitsiListenerBridge for live WebRTC stream reception.")
        listener_bridge = JitsiListenerBridge(listener_bot=listener_bot)
        listener_bridge.connect_and_join(
            room_id=config.jitsi_room,
            bridge_url=config.bridge_url,
        )

    adapter_clip_results: Dict[str, List[ClipScoreResult]] = {name: [] for name in adapters}

    # 3. Enforce Concurrency Policy
    if config.concurrency_mode == "sequential":
        eval_passes = [(name, {name: adapter}) for name, adapter in adapters.items()]
        logger.info("Tier 2 executing in SEQUENTIAL mode (%d single-adapter passes for timing fairness)", len(eval_passes))
    else:
        eval_passes = [("all_parallel", adapters)]
        logger.info("Tier 2 executing in PARALLEL mode (all %d adapters active simultaneously)", len(adapters))
    sys.stdout.flush()

    try:
        for pass_label, pass_adapters in eval_passes:
            listener_bot.set_active_adapters(pass_adapters)

            for clip_idx, entry in enumerate(manifest):
                is_warmup = clip_idx < config.warmup_clip_count
                logger.info(
                    "Tier 2 [%s] clip [%d/%d] '%s' (Category: '%s', Warmup: %s)",
                    pass_label,
                    clip_idx + 1,
                    len(manifest),
                    entry.clip_id,
                    entry.category,
                    is_warmup,
                )
                sys.stdout.flush()

                # Step 3: Stream clip via SpeakerBot & capture via ListenerBridge concurrently
                try:
                    if listener_bridge is not None:
                        # Arm the receiver tap FIRST to guarantee 0 lost leading packets / chirp
                        listener_bridge.arm_clip(entry)
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            play_future = executor.submit(speaker_bot.play_clip, entry)
                            captured_data = listener_bridge.await_clip(entry, timeout_s=30.0)
                            playback_meta = play_future.result()
                    else:
                        listener_bot.prepare_for_clip(entry.clip_id)
                        playback_meta = speaker_bot.play_clip(entry)
                        captured_data = listener_bot.await_clip_completion(entry.clip_id, timeout_s=15.0)
                except Exception as exc:
                    logger.error(
                        "[Run %s | Tier 2 | Clip %s | Pass %s] Live transaction failed: %s",
                        config.run_id,
                        entry.clip_id,
                        pass_label,
                        exc,
                    )
                    results_store.store_clip_failure(
                        run_id=config.run_id,
                        manifest_version=manifest.version_hash,
                        adapter_id=pass_label,
                        clip_id=entry.clip_id,
                        tier="tier2",
                        stage="transport",
                        error=str(exc),
                    )
                    continue

                # Step 4: Marker cross-correlation alignment for ground-truth Time Zero
                try:
                    alignment_offset = getattr(playback_meta, "calibration_marker_offset_samples", None) or getattr(entry, "calibration_marker_offset_samples", 320)
                    stream_t0_ns = captured_data.arrival_timestamps_ns[0] if captured_data.arrival_timestamps_ns else 0
                    alignment_result = align_marker(
                        received_audio=captured_data.decoded_audio_16k,
                        reference_marker_offset=alignment_offset,
                        stream_start_timestamp_ns=stream_t0_ns,
                        sample_rate_hz=16000,
                    )
                except Exception as exc:
                    logger.error(
                        "[Run %s | Tier 2 | Clip %s | MarkerAlignment] Alignment failed: %s",
                        config.run_id,
                        entry.clip_id,
                        exc,
                    )
                    results_store.store_clip_failure(
                        run_id=config.run_id,
                        manifest_version=manifest.version_hash,
                        adapter_id=pass_label,
                        clip_id=entry.clip_id,
                        tier="tier2",
                        stage="marker_alignment",
                        error=str(exc),
                    )
                    continue

                # A03 Fix: Gate on successful marker detection (do not store corrupted/undetected markers as good runs)
                if not alignment_result.marker_detected or alignment_result.status != "detected":
                    logger.warning(
                        "[Run %s | Tier 2 | Clip %s] Marker not detected (status=%s, conf=%.3f). Gating clip.",
                        config.run_id,
                        entry.clip_id,
                        alignment_result.status,
                        alignment_result.alignment_confidence,
                    )
                    results_store.store_clip_failure(
                        run_id=config.run_id,
                        manifest_version=manifest.version_hash,
                        adapter_id=pass_label,
                        clip_id=entry.clip_id,
                        tier="tier2",
                        stage="marker_gating",
                        error=f"Marker alignment failed with status: '{alignment_result.status}' (confidence: {alignment_result.alignment_confidence})",
                    )
                    continue

                # A01 & A21 Fix: Realign timeline by subtracting delta, using speaker's reported clip duration
                delta = alignment_result.sample_offset_delta or 0
                clip_len = getattr(playback_meta, "duration_samples", len(captured_data.decoded_audio_16k))

                # Step 5: Evaluate each adapter with realigned decision records
                for adapter_name, adapter_records in captured_data.adapter_decisions.items():
                    if is_warmup:
                        continue

                    # Shift adapter sample offsets to clip coordinates (A01)
                    aligned_records = [
                        dataclasses.replace(r, sample_offset=r.sample_offset - delta)
                        for r in adapter_records
                        if 0 <= (r.sample_offset - delta) < clip_len
                    ]

                    # Calculate pipeline onset and offset/hangover latencies
                    try:
                        latency_metrics = calculate_pipeline_latency(
                            decision_records=aligned_records,
                            speech_segments=entry.speech_segments,
                            time_zero_ns=alignment_result.time_zero_timestamp_ns,
                            marker_alignment=alignment_result,
                            sample_rate_hz=16000,
                            decision_threshold=config.decision_threshold,
                            clip_id=entry.clip_id,
                        )
                        results_store.store_latency_measurement(
                            run_id=config.run_id,
                            manifest_version=manifest.version_hash,
                            adapter_id=adapter_name,
                            clip_id=entry.clip_id,
                            latency_data=latency_metrics,
                            record_type="tier2_pipeline_latency",
                            tier="tier2",
                        )
                    except Exception as exc:
                        logger.error(
                            "[Run %s | Tier 2 | Clip %s | Adapter %s | LatencyCalc] Latency error: %s",
                            config.run_id,
                            entry.clip_id,
                            adapter_name,
                            exc,
                        )

                    # Score single clip using vad_scorer in clip coordinates
                    try:
                        clip_score = score_single_clip(
                            decision_records=aligned_records,
                            manifest_entry=entry,
                            total_clip_samples=clip_len,
                            scoring_grid_ms=config.scoring_grid_ms,
                            sample_rate_hz=16000,
                            decision_threshold=config.decision_threshold,
                        )
                        adapter_clip_results[adapter_name].append(clip_score)
                        diag_summary = {
                            "packet_count": len(captured_data.arrival_timestamps_ns),
                            "gap_count": sum(1 for d in captured_data.packet_diagnostics if d.is_gap),
                            "missing_packets": sum(d.missing_count for d in captured_data.packet_diagnostics),
                        }
                        results_store.store_clip_score_result(
                            run_id=config.run_id,
                            manifest_version=manifest.version_hash,
                            clip_score_result=clip_score,
                            tier="tier2",
                            diagnostics=diag_summary,

                        )
                    except Exception as exc:
                        logger.error(
                            "[Run %s | Tier 2 | Clip %s | Adapter %s | Scorer] Scoring failed: %s",
                            config.run_id,
                            entry.clip_id,
                            adapter_name,
                            exc,
                        )
                        results_store.store_clip_failure(
                            run_id=config.run_id,
                            manifest_version=manifest.version_hash,
                            adapter_id=adapter_name,
                            clip_id=entry.clip_id,
                            tier="tier2",
                            stage="scoring",
                            error=str(exc),
                        )
                        continue

    finally:
        # Step 7: Cleanly disconnect both WebRTC participants at the end of the run
        if listener_bridge is not None:
            try:
                listener_bridge.disconnect()
            except Exception as exc:
                logger.debug("Notice disconnecting listener bridge: %s", exc)

        speaker_bot.close()

    # Verify that at least one clip was successfully evaluated
    total_successful = sum(len(clips) for clips in adapter_clip_results.values())
    if total_successful == 0:
        raise RuntimeError(
            f"Tier 2 Live Pipeline Failed: 0 clips were captured across all {len(adapters)} adapters. "
            "The WebRTC media connection failed to connect."
        )

    # Step 5 (Part D): Build aggregated adapter reports
    reports: Dict[str, VADScorerReport] = {}
    for adapter_name, scored_clips in adapter_clip_results.items():
        if not scored_clips:
            logger.warning("[Tier 1] Adapter '%s' scored 0 clips.", adapter_name)
            continue
        report = score_adapter_evaluation(
            clip_results=scored_clips,
            scoring_grid_ms=config.scoring_grid_ms,
        )
        reports[adapter_name] = report
        logger.info(
            "Tier 2 Completed for '%s': Evaluated %d clips | Precision: %.3f | Recall: %.3f | F1: %.3f",
            adapter_name,
            len(scored_clips),
            report.overall_metrics.metrics.precision,
            report.overall_metrics.metrics.recall,
            report.overall_metrics.metrics.f1,
        )
        sys.stdout.flush()

    return reports


# ==============================================================================
# Main Orchestration Entrypoint
# ==============================================================================

def run_benchmark(config_path: Union[str, Path] = "config/run_config.yaml") -> Dict[str, Any]:
    """
    Master execution entrypoint for the VAD benchmark harness.
    """
    config = load_run_config(config_path)
    logger.info("Loaded run configuration for run_id: '%s'", config.run_id)
    sys.stdout.flush()

    # Tier 1 Step 1: Load corpus manifest via canonical loader
    manifest = load_manifest(
        manifest_path=config.corpus_manifest_path,
        category_filter=config.corpus_category_filter if config.corpus_category_filter else None,
        include_held_out=config.include_held_out_slice,
    )
    logger.info("Loaded manifest '%s' (%d clips, hash=%s)", config.corpus_manifest_path, len(manifest), manifest.version_hash)
    sys.stdout.flush()

    try:
        from importlib.metadata import version as _pkg_version
        aiortc_ver = _pkg_version("aiortc")
    except Exception:
        aiortc_ver = "not installed"

    # Initialize permanent results store
    results_store = ResultsStore(config.results_destination)
    results_store.store_run_context(
        run_id=config.run_id,
        manifest_version=manifest.version_hash,
        context_data={
            "hardware_policy": config.hardware_policy,
            "concurrency_mode": config.concurrency_mode,
            "scoring_grid_ms": config.scoring_grid_ms,
            "active_adapters": list(config.active_adapters),
            "tiers_to_run": list(config.tiers_to_run),
            "aiortc_version": aiortc_ver,
            "python_version": sys.version.split()[0],
        },
    )

    run_summary: Dict[str, Any] = {
        "run_id": config.run_id,
        "manifest_version": manifest.version_hash,
        "tiers_executed": {},
    }

    # Execute Tier 1 if configured
    if "tier1" in config.tiers_to_run:
        try:
            tier1_reports = run_tier1_offline_bench(
                config=config,
                manifest=manifest,
                results_store=results_store,
            )
            run_summary["tiers_executed"]["tier1"] = {
                "status": "success",
                "adapters_evaluated": list(tier1_reports.keys()),
            }
        except Exception as exc:
            logger.error("[Run %s | Tier 1] Fatal tier failure: %s", config.run_id, exc, exc_info=True)
            run_summary["tiers_executed"]["tier1"] = {"status": "failed", "error": str(exc)}

    # Execute Tier 2 if configured (Tier 1 failures do not cancel Tier 2)
    if "tier2" in config.tiers_to_run:
        try:
            tier2_reports = run_tier2_live_pipeline(
                config=config,
                manifest=manifest,
                results_store=results_store,
            )
            run_summary["tiers_executed"]["tier2"] = {
                "status": "success",
                "adapters_evaluated": list(tier2_reports.keys()),
            }
        except Exception as exc:
            logger.error("[Run %s | Tier 2] Fatal tier failure: %s", config.run_id, exc, exc_info=True)
            run_summary["tiers_executed"]["tier2"] = {"status": "failed", "error": str(exc)}

    results_store.close()
    has_fatal_failure = any(
        res.get("status") == "failed" for res in run_summary["tiers_executed"].values()
    )
    if has_fatal_failure:
        logger.error("=== Benchmark Run '%s' Completed With Failures ===", config.run_id)
    else:
        logger.info("=== Benchmark Run '%s' Completed Successfully ===", config.run_id)
    sys.stdout.flush()
    return run_summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VAD Benchmark Harness Orchestrator")
    parser.add_argument(
        "--config",
        type=str,
        default="config/run_config.yaml",
        help="Path to run_config.yaml",
    )
    args = parser.parse_args()
    run_benchmark(config_path=args.config)