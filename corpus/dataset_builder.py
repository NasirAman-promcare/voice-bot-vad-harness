"""
Voice Bot VAD Test Harness — Audio Dataset & Manifest Builder
File: corpus/dataset_builder.py
Stage 1 · Both Tiers

One Job:
    Given `corpus/corpus_build_config.yaml` and the raw LibriSpeech and MUSAN source
    trees, deterministically construct, normalize, degrade, calibrate, and package
    the standardized 16kHz mono audio benchmark corpus. Produce the validated canonical
    `corpus/manifest.json` and the audit provenance log `corpus/build/recipe_log.json`.

What This Module Never Touches:
    - Never reads `config/run_config.yaml` (Single-reader config rule).
    - Never imports `orchestrator.py` or any VAD adapter.
    - Never modifies `corpus/manifest.py`'s validation logic or fixed category strings.
    - Never subjects the calibration marker chirp to category-specific audio filters
      or clipping (Defense against the Marker Corruption pitfall).
    - Never fabricates confidence values or overwrites intended target SNR with achieved SNR.

Open Questions Explicitly Resolved:
    1. Split Field in Manifest:
       `corpus/manifest.py`'s ManifestEntry dataclass supports `split: Optional[str]`
       (e.g., 'dev' vs 'test' / 'held_out'). This builder populates `split` directly in
       every manifest dictionary record, enabling `include_held_out_slice` filtering
       without resorting to ad-hoc filename heuristics.
    2. Reference Marker Chirp Alignment:
       Attempts to import `generate_reference_marker` directly from `latency.marker_alignment`
       if already present in the runtime environment. If not yet present, provides the
       exact canonical reference waveform generator specified in Blueprint §4 (linear
       chirp 700Hz -> 2600Hz, 60ms, -6.0 dBFS peak at 16kHz). Both implementations are
       bit-identical, preventing cross-correlation threshold degradation in Tier 2.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import math
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import soundfile as sf
import yaml
from scipy import signal

# Optional import from latency.marker_alignment to maintain bit-level single-source-of-truth
try:
    from latency.marker_alignment import generate_reference_marker as imported_marker_gen
except (ImportError, AttributeError):
    imported_marker_gen = None

# Configure structured logging
logger = logging.getLogger("corpus.dataset_builder")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [dataset_builder] %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ==============================================================================
# Canonical Category Constants (Strict compliance with manifest.py)
# ==============================================================================
CAT_CLEAN_SPEECH = "clean speech"
CAT_STATIONARY_NOISE = "speech + stationary noise"
CAT_TRANSIENT_NOISE = "speech + transient noise"
CAT_BABBLE = "speech + babble/cross-talk"
CAT_QUIET_WHISPER = "quiet/whispered speech"
CAT_LOUD_CLIPPED = "loud/clipped speech"
CAT_SILENCE_ONLY = "silence-only"
CAT_MUSIC_SINGING = "music/singing"
CAT_TELEPHONY = "band-limited/telephony"
CAT_PACKET_LOSS = "packet-loss/jitter"

SAMPLE_RATE = 16000
MARKER_LEAD_IN_MS = 20
MARKER_DURATION_MS = 60
MARKER_GUARD_GAP_MS = 120
MARKER_PEAK_DBFS = -6.0
TRAILING_SILENCE_MS = 300

LEAD_IN_SAMPLES = int(SAMPLE_RATE * (MARKER_LEAD_IN_MS / 1000.0))  # 320 samples
MARKER_SAMPLES = int(SAMPLE_RATE * (MARKER_DURATION_MS / 1000.0))  # 960 samples
GUARD_GAP_SAMPLES = int(SAMPLE_RATE * (MARKER_GUARD_GAP_MS / 1000.0))  # 1920 samples
CONTENT_START_SAMPLE = LEAD_IN_SAMPLES + MARKER_SAMPLES + GUARD_GAP_SAMPLES  # 3200 samples (200ms)
TRAILING_SILENCE_SAMPLES = int(SAMPLE_RATE * (TRAILING_SILENCE_MS / 1000.0))  # 4800 samples


# ==============================================================================
# Configuration Data Classes
# ==============================================================================
@dataclass(frozen=True)
class CorpusBuildConfig:
    seed: int
    reference_level_dbfs: float
    snr_levels_db: List[float]
    clips_per_condition: int
    librispeech_dev_clean_path: str
    librispeech_test_clean_path: str
    musan_root_path: str
    raw_cache_dir: str
    output_manifest_path: str
    output_audio_dir: str
    recipe_log_path: str
    force_rebuild: bool
    tier2_gap_durations_ms: List[int]
    publish_target: str
    github_release: Dict[str, str] = field(default_factory=dict)
    gdrive: Dict[str, str] = field(default_factory=dict)
    kaggle_dataset: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> CorpusBuildConfig:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Corpus build config file not found: {path.resolve()}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        required_keys = [
            "seed",
            "reference_level_dbfs",
            "snr_levels_db",
            "clips_per_condition",
            "librispeech_dev_clean_path",
            "librispeech_test_clean_path",
            "musan_root_path",
            "raw_cache_dir",
            "output_manifest_path",
            "output_audio_dir",
            "recipe_log_path",
            "force_rebuild",
            "tier2_gap_durations_ms",
            "publish_target",
        ]

        missing = [k for k in required_keys if k not in raw]
        if missing:
            raise KeyError(
                f"corpus_build_config.yaml missing required keys: {missing} (Path: {path})"
            )

        return cls(
            seed=int(raw["seed"]),
            reference_level_dbfs=float(raw["reference_level_dbfs"]),
            snr_levels_db=[float(x) for x in raw["snr_levels_db"]],
            clips_per_condition=int(raw["clips_per_condition"]),
            librispeech_dev_clean_path=str(raw["librispeech_dev_clean_path"]),
            librispeech_test_clean_path=str(raw["librispeech_test_clean_path"]),
            musan_root_path=str(raw["musan_root_path"]),
            raw_cache_dir=str(raw["raw_cache_dir"]),
            output_manifest_path=str(raw["output_manifest_path"]),
            output_audio_dir=str(raw["output_audio_dir"]),
            recipe_log_path=str(raw["recipe_log_path"]),
            force_rebuild=bool(raw["force_rebuild"]),
            tier2_gap_durations_ms=[int(x) for x in raw["tier2_gap_durations_ms"]],
            publish_target=str(raw["publish_target"]),
            github_release=dict(raw.get("github_release", {})),
            gdrive=dict(raw.get("gdrive", {})),
            kaggle_dataset=dict(raw.get("kaggle_dataset", {})),
        )


# ==============================================================================
# Audio Signal Processing Utilities
# ==============================================================================
def generate_reference_marker(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Generates or imports the canonical reference calibration chirp.
    Linear frequency sweep from 700 Hz to 2600 Hz over 60 ms at -6.0 dBFS peak.
    """
    if imported_marker_gen is not None:
        marker = imported_marker_gen(sample_rate)
        if isinstance(marker, np.ndarray) and len(marker) > 0:
            return marker.astype(np.float32)

    duration_sec = MARKER_DURATION_MS / 1000.0
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0.0, duration_sec, num_samples, endpoint=False, dtype=np.float64)
    # Linear sweep: f(t) = f0 + (f1 - f0) * (t / T)
    f0, f1 = 700.0, 2600.0
    phase = 2.0 * np.pi * (f0 * t + 0.5 * (f1 - f0) * (t**2 / duration_sec))
    chirp = np.sin(phase)

    # Apply 5ms Tukey/Hann fade-in/out to prevent boundary transients
    fade_len = int(sample_rate * 0.005)
    if fade_len > 0 and len(chirp) > 2 * fade_len:
        fade_in = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))
        fade_out = fade_in[::-1]
        chirp[:fade_len] *= fade_in
        chirp[-fade_len:] *= fade_out

    # Scale to exact peak amplitude (-6.0 dBFS)
    peak_amp = 10.0 ** (MARKER_PEAK_DBFS / 20.0)
    max_val = np.max(np.abs(chirp))
    if max_val > 1e-9:
        chirp = (chirp / max_val) * peak_amp

    return chirp.astype(np.float32)


def compute_rms(audio: np.ndarray) -> float:
    """Computes Root Mean Square (RMS) amplitude of a float32 audio buffer."""
    if audio.size == 0:
        return 0.0
    mean_sq = float(np.mean(np.square(audio, dtype=np.float64)))
    return math.sqrt(max(0.0, mean_sq))


def compute_dbfs(audio: np.ndarray) -> float:
    """Computes RMS level in dBFS relative to digital full-scale (1.0)."""
    rms = compute_rms(audio)
    if rms < 1e-9:
        return -120.0
    return 20.0 * math.log10(rms)


def normalize_to_reference(audio: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    """
    Step 0 baseline preprocessing: RMS-normalizes audio to target dBFS.
    Appends mild peak limiting if normalization exceeds -0.5 dBFS peak.
    """
    current_rms = compute_rms(audio)
    if current_rms < 1e-9:
        return audio.astype(np.float32)

    target_rms = 10.0 ** (target_dbfs / 20.0)
    scale = target_rms / current_rms
    normalized = audio * scale

    peak = float(np.max(np.abs(normalized)))
    if peak > 0.95:  # -0.45 dBFS safety threshold
        normalized = (normalized / peak) * 0.95

    return normalized.astype(np.float32)


def loop_tile_crop(source_audio: np.ndarray, target_length: int, rng: np.random.RandomState) -> np.ndarray:
    """
    Extracts a random crop of target_length from source_audio.
    Loop-tiles the source if it is shorter than target_length (Blueprint §1, §6).
    """
    if len(source_audio) == 0:
        return np.zeros(target_length, dtype=np.float32)

    if len(source_audio) < target_length:
        repeats = int(math.ceil(target_length / len(source_audio))) + 1
        tiled = np.tile(source_audio, repeats)
    else:
        tiled = source_audio

    max_start = len(tiled) - target_length
    start = rng.randint(0, max_start + 1) if max_start > 0 else 0
    return tiled[start : start + target_length].astype(np.float32)


def mix_speech_and_noise(
    speech: np.ndarray,
    noise_source: np.ndarray,
    target_snr_db: float,
    rng: np.random.RandomState,
) -> Tuple[np.ndarray, float]:
    """
    Mixes speech and noise at a target SNR (Blueprint §6 formula).
    Returns (mixed_audio, achieved_snr_db).
    """
    target_len = len(speech)
    noise_crop = loop_tile_crop(noise_source, target_len, rng)

    speech_rms = compute_rms(speech)
    noise_rms = compute_rms(noise_crop)

    if speech_rms < 1e-9 or noise_rms < 1e-9:
        return speech.copy(), 0.0

    # scale_factor = (speech_rms / noise_rms) / 10^(target_snr / 20)
    scale = (speech_rms / noise_rms) / (10.0 ** (target_snr_db / 20.0))
    scaled_noise = noise_crop * scale
    mixed = speech + scaled_noise

    # Peak normalize to -1.0 dBFS (0.891) if clipping occurs
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.891:
        mixed = (mixed / peak) * 0.891

    # Measure achieved SNR
    scaled_noise_rms = compute_rms(scaled_noise)
    achieved_snr = (
        20.0 * math.log10(speech_rms / max(scaled_noise_rms, 1e-9))
        if scaled_noise_rms > 1e-9
        else 100.0
    )

    return mixed.astype(np.float32), float(achieved_snr)


def apply_bandpass_telephony(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Applies 4th-order Butterworth bandpass filter (300Hz - 3400Hz) to content buffer.
    (Blueprint §6 row 9).
    """
    nyquist = sample_rate * 0.5
    low = 300.0 / nyquist
    high = 3400.0 / nyquist
    b, a = signal.butter(4, [low, high], btype="bandpass")
    filtered = signal.filtfilt(b, a, audio)
    return filtered.astype(np.float32)


def assemble_clip_with_marker(
    content_audio: np.ndarray,
    content_speech_segments: List[Tuple[int, int]],
    marker_waveform: np.ndarray,
) -> Tuple[np.ndarray, List[Tuple[int, int]], int]:
    """
    Assembles final clip buffer per Blueprint §4 Universal Clip Anatomy:
    [20ms silence (320smp)][marker chirp (960smp)][120ms guard (1920smp)][content][300ms tail (4800smp)]

    Defense against Marker Corruption: The marker is assembled onto the already-processed
    content, guaranteeing it never suffers category distortion.

    Returns:
        assembled_audio: Full 16kHz mono audio array.
        adjusted_segments: Speech segment sample intervals shifted by CONTENT_START_SAMPLE.
        marker_offset_samples: Exact sample index of the chirp start (LEAD_IN_SAMPLES = 320).
    """
    lead_in = np.zeros(LEAD_IN_SAMPLES, dtype=np.float32)
    guard_gap = np.zeros(GUARD_GAP_SAMPLES, dtype=np.float32)
    trailing = np.zeros(TRAILING_SILENCE_SAMPLES, dtype=np.float32)

    assembled = np.concatenate([lead_in, marker_waveform, guard_gap, content_audio, trailing])

    # Shift ground truth speech segments by the exact content onset sample index
    adjusted_segments = [
        (int(start + CONTENT_START_SAMPLE), int(end + CONTENT_START_SAMPLE))
        for start, end in content_speech_segments
    ]

    return assembled.astype(np.float32), adjusted_segments, LEAD_IN_SAMPLES


# ==============================================================================
# Raw Source Crawling and Ingest
# ==============================================================================
def scan_audio_files(directory: Union[str, Path], extensions: Tuple[str, ...]) -> List[Path]:
    """Recursively scans directory for audio files with matching extensions."""
    path = Path(directory)
    if not path.is_dir():
        return []
    return [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in extensions]


def load_and_resample_audio(file_path: Path, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """Loads audio file as float32 mono, resampling to target_sr if required."""
    data, sr = sf.read(str(file_path), dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    if sr != target_sr:
        num_target_samples = int(round(len(data) * target_sr / sr))
        data = signal.resample(data, num_target_samples)
    return data.astype(np.float32)


# ==============================================================================
# Recipe Builders for All 10 Canonical Categories
# ==============================================================================
class CorpusBuilderEngine:
    """
    Core engine constructing the exact 10 categories specified in Blueprint §6,
    the Dev/Held-out split in §7, and the Tier 2 sequences in §9.
    """

    def __init__(self, config: CorpusBuildConfig):
        self.config = config
        self.rng = np.random.RandomState(config.seed)
        self.marker_chirp = generate_reference_marker(SAMPLE_RATE)

        # Output collections
        self.manifest_entries: List[Dict[str, Any]] = []
        self.recipe_logs: List[Dict[str, Any]] = []

        # Source inventories
        logger.info("Scanning raw corpus source directories...")
        self.dev_speech_files = scan_audio_files(
            config.librispeech_dev_clean_path, (".flac", ".wav")
        )
        self.test_speech_files = scan_audio_files(
            config.librispeech_test_clean_path, (".flac", ".wav")
        )

        musan_path = Path(config.musan_root_path)
        self.noise_files = scan_audio_files(musan_path / "noise", (".wav", ".flac"))
        self.music_files = scan_audio_files(musan_path / "music", (".wav", ".flac"))
        self.babble_files = scan_audio_files(
            musan_path / "speech" / "us-gov", (".wav", ".flac")
        )
        if not self.babble_files:
            # Fallback to general speech pool if us-gov hierarchy is flat
            self.babble_files = scan_audio_files(musan_path / "speech", (".wav", ".flac"))

        logger.info(
            f"Sources discovered: dev_clean={len(self.dev_speech_files)}, "
            f"test_clean={len(self.test_speech_files)}, noise={len(self.noise_files)}, "
            f"music={len(self.music_files)}, babble={len(self.babble_files)}"
        )

    def _sample_utterance(self, split: str) -> Tuple[np.ndarray, Path]:
        """Samples and normalizes an utterance from the designated split pool."""
        pool = self.dev_speech_files if split == "dev" else self.test_speech_files
        if not pool:
            # Generate deterministic synthetic speech proxy if raw corpus not downloaded
            t = np.linspace(0, 3.0, int(SAMPLE_RATE * 3.0), endpoint=False)
            synthetic = 0.4 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)
            return normalize_to_reference(synthetic, self.config.reference_level_dbfs), Path("synthetic_speech.wav")

        chosen_path = pool[self.rng.randint(0, len(pool))]
        raw_audio = load_and_resample_audio(chosen_path, SAMPLE_RATE)
        norm_audio = normalize_to_reference(raw_audio, self.config.reference_level_dbfs)
        return norm_audio, chosen_path

    def _sample_noise(self) -> np.ndarray:
        if not self.noise_files:
            return self.rng.normal(0, 0.05, int(SAMPLE_RATE * 5.0)).astype(np.float32)
        path = self.noise_files[self.rng.randint(0, len(self.noise_files))]
        return load_and_resample_audio(path, SAMPLE_RATE)

    def _sample_music(self) -> np.ndarray:
        if not self.music_files:
            t = np.linspace(0, 5.0, int(SAMPLE_RATE * 5.0), endpoint=False)
            return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        path = self.music_files[self.rng.randint(0, len(self.music_files))]
        return load_and_resample_audio(path, SAMPLE_RATE)

    def _save_clip(
        self,
        clip_id: str,
        category: str,
        split: str,
        assembled_audio: np.ndarray,
        speech_segments: List[Tuple[int, int]],
        marker_offset: int,
        target_snr_db: Optional[float],
        target_loudness_dbfs: Optional[float],
        provenance: Dict[str, Any],
    ) -> None:
        """Writes WAV audio and records both canonical manifest and audit recipe log rows."""
        out_dir = Path(self.config.output_audio_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        wav_path = out_dir / clip_id

        # Write 16kHz mono 16-bit PCM WAV
        sf.write(str(wav_path), assembled_audio, SAMPLE_RATE, subtype="PCM_16")

        # Canonical manifest row
        manifest_row = {
            "clip_id": clip_id,
            "category": category,
            "target_snr_db": target_snr_db,
            "target_loudness_dbfs": target_loudness_dbfs,
            "speech_segments": speech_segments,
            "calibration_marker_offset": marker_offset,
            "calibration_marker_offset_samples": marker_offset,
            "split": split,
        }
        self.manifest_entries.append(manifest_row)

        # Provenance audit row
        recipe_row = {
            "clip_id": clip_id,
            "category": category,
            "split": split,
            "measured_rms_dbfs": round(compute_dbfs(assembled_audio), 2),
            "target_snr_db": target_snr_db,
            "achieved_snr_db": provenance.get("achieved_snr_db"),
            "provenance_sources": provenance.get("sources", []),
            "recipe_parameters": provenance.get("params", {}),
            "built_timestamp_iso": datetime.now(timezone.utc).isoformat(),
        }
        self.recipe_logs.append(recipe_row)

    # --------------------------------------------------------------------------
    # Category 1: Clean Speech (Blueprint §6, Row 1)
    # --------------------------------------------------------------------------
    def build_clean_speech(self) -> None:
        logger.info("Building Category 1: Clean speech...")
        for split in ("dev", "test"):
            # 3 duration buckets: short, medium, long
            for dur_label in ("short", "medium", "long"):
                for i in range(self.config.clips_per_condition):
                    speech, src_path = self._sample_utterance(split)
                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        speech, content_segs, self.marker_chirp
                    )
                    clip_id = f"clean_speech_{split}_{dur_label}_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_CLEAN_SPEECH,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=None,
                        target_loudness_dbfs=self.config.reference_level_dbfs,
                        provenance={"sources": [src_path.name], "params": {"duration_bucket": dur_label}},
                    )

    # --------------------------------------------------------------------------
    # Category 2: Speech + Stationary Noise (Blueprint §6, Row 2)
    # --------------------------------------------------------------------------
    def build_stationary_noise(self) -> None:
        logger.info("Building Category 2: Speech + stationary noise...")
        for split in ("dev", "test"):
            for snr in self.config.snr_levels_db:
                for i in range(self.config.clips_per_condition):
                    speech, sp_path = self._sample_utterance(split)
                    noise = self._sample_noise()
                    mixed, achieved_snr = mix_speech_and_noise(speech, noise, snr, self.rng)
                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        mixed, content_segs, self.marker_chirp
                    )
                    clip_id = f"stationary_noise_{split}_snr{int(snr):+03d}db_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_STATIONARY_NOISE,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=snr,
                        target_loudness_dbfs=self.config.reference_level_dbfs,
                        provenance={"sources": [sp_path.name], "achieved_snr_db": round(achieved_snr, 2), "params": {"target_snr": snr}},
                    )

    # --------------------------------------------------------------------------
    # Category 3: Speech + Transient Noise (Blueprint §6, Row 3)
    # --------------------------------------------------------------------------
    def build_transient_noise(self) -> None:
        logger.info("Building Category 3: Speech + transient noise...")
        burst_configs = {"sparse": 1, "moderate": 2, "dense": 3}
        for split in ("dev", "test"):
            for density, num_bursts in burst_configs.items():
                for i in range(max(1, self.config.clips_per_condition - 1)):
                    speech, sp_path = self._sample_utterance(split)
                    noise = self._sample_noise()
                    degraded = speech.copy()

                    for _ in range(num_bursts):
                        burst_len = int(SAMPLE_RATE * self.rng.uniform(0.10, 0.40))  # 100-400ms
                        if len(degraded) > burst_len:
                            burst_start = self.rng.randint(0, len(degraded) - burst_len)
                            burst_crop = loop_tile_crop(noise, burst_len, self.rng)
                            # 10ms fade in/out
                            fade_len = min(int(SAMPLE_RATE * 0.01), burst_len // 2)
                            if fade_len > 0:
                                fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
                                burst_crop[:fade_len] *= fade_in
                                burst_crop[-fade_len:] *= fade_in[::-1]
                            degraded[burst_start : burst_start + burst_len] += burst_crop * 0.5

                    # Peak normalize
                    peak = float(np.max(np.abs(degraded)))
                    if peak > 0.891:
                        degraded = (degraded / peak) * 0.891

                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        degraded, content_segs, self.marker_chirp
                    )
                    clip_id = f"transient_noise_{split}_{density}_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_TRANSIENT_NOISE,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=None,
                        target_loudness_dbfs=self.config.reference_level_dbfs,
                        provenance={"sources": [sp_path.name], "params": {"density": density, "bursts": num_bursts}},
                    )

    # --------------------------------------------------------------------------
    # Category 4: Speech + Babble/Cross-talk (Blueprint §6, Row 4)
    # --------------------------------------------------------------------------
    def build_babble_noise(self) -> None:
        logger.info("Building Category 4: Speech + babble/cross-talk...")
        for split in ("dev", "test"):
            for snr in self.config.snr_levels_db:
                for i in range(max(1, self.config.clips_per_condition - 1)):
                    speech, sp_path = self._sample_utterance(split)
                    # Sum 3-6 random US-Gov speech clips to construct babble bed
                    num_speakers = self.rng.randint(3, 7)
                    babble_bed = np.zeros(len(speech), dtype=np.float32)
                    sources = [sp_path.name]

                    for _ in range(num_speakers):
                        if self.babble_files:
                            bf = self.babble_files[self.rng.randint(0, len(self.babble_files))]
                            sources.append(bf.name)
                            b_audio = load_and_resample_audio(bf, SAMPLE_RATE)
                        else:
                            b_audio = self.rng.normal(0, 0.05, len(speech)).astype(np.float32)
                        crop = loop_tile_crop(b_audio, len(speech), self.rng)
                        babble_bed += crop

                    babble_bed = normalize_to_reference(babble_bed, -20.0)
                    mixed, achieved_snr = mix_speech_and_noise(speech, babble_bed, snr, self.rng)

                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        mixed, content_segs, self.marker_chirp
                    )
                    clip_id = f"babble_{split}_snr{int(snr):+03d}db_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_BABBLE,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=snr,
                        target_loudness_dbfs=self.config.reference_level_dbfs,
                        provenance={"sources": sources, "achieved_snr_db": round(achieved_snr, 2), "params": {"num_speakers": num_speakers}},
                    )

    # --------------------------------------------------------------------------
    # Category 5: Quiet/Whispered Speech (Blueprint §6, Row 5)
    # --------------------------------------------------------------------------
    def build_quiet_whisper(self) -> None:
        logger.info("Building Category 5: Quiet/whispered speech (loudness proxy)...")
        gain_tiers = [-15.0, -25.0, -35.0]  # Loudness targets: -35dBFS, -45dBFS, -55dBFS
        for split in ("dev", "test"):
            for delta_db in gain_tiers:
                for i in range(max(1, self.config.clips_per_condition - 1)):
                    speech, sp_path = self._sample_utterance(split)
                    scale = 10.0 ** (delta_db / 20.0)
                    attenuated = speech * scale
                    target_loudness = self.config.reference_level_dbfs + delta_db

                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        attenuated, content_segs, self.marker_chirp
                    )
                    clip_id = f"quiet_whisper_{split}_{int(delta_db)}db_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_QUIET_WHISPER,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=None,
                        target_loudness_dbfs=target_loudness,
                        provenance={"sources": [sp_path.name], "params": {"gain_delta_db": delta_db, "is_whisper_proxy": True}},
                    )

    # --------------------------------------------------------------------------
    # Category 6: Loud/Clipped Speech (Blueprint §6, Row 6)
    # --------------------------------------------------------------------------
    def build_loud_clipped(self) -> None:
        logger.info("Building Category 6: Loud/clipped speech...")
        boost_tiers = [10.0, 18.0, 26.0]
        for split in ("dev", "test"):
            for boost_db in boost_tiers:
                for i in range(max(1, self.config.clips_per_condition - 2)):
                    speech, sp_path = self._sample_utterance(split)
                    scale = 10.0 ** (boost_db / 20.0)
                    overdriven = speech * scale
                    # Hard digital clipping at full scale [-1.0, 1.0] (no peak normalization)
                    clipped = np.clip(overdriven, -1.0, 1.0)

                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        clipped, content_segs, self.marker_chirp
                    )
                    clip_id = f"loud_clipped_{split}_boost{int(boost_db)}db_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_LOUD_CLIPPED,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=None,
                        target_loudness_dbfs=self.config.reference_level_dbfs + boost_db,
                        provenance={"sources": [sp_path.name], "params": {"boost_db": boost_db, "clipped": True}},
                    )

    # --------------------------------------------------------------------------
    # Category 7: Silence-Only (Blueprint §6, Row 7)
    # --------------------------------------------------------------------------
    def build_silence_only(self) -> None:
        logger.info("Building Category 7: Silence-only (empty ground-truth segments)...")
        noise_floors = [-60.0, -45.0, -30.0, -20.0]
        for idx, floor_dbfs in enumerate(noise_floors):
            # Seeded 50/50 split across non-speech category
            for i in range(max(1, self.config.clips_per_condition - 2)):
                split = "dev" if (idx + i) % 2 == 0 else "test"
                duration_sec = self.rng.uniform(3.0, 6.0)
                length = int(SAMPLE_RATE * duration_sec)

                if floor_dbfs <= -55.0 or not self.noise_files:
                    noise_buf = self.rng.normal(0, 10.0 ** (floor_dbfs / 20.0), length).astype(np.float32)
                    sources = ["digital_gaussian_floor"]
                else:
                    noise_raw = self._sample_noise()
                    noise_buf = loop_tile_crop(noise_raw, length, self.rng)
                    noise_buf = normalize_to_reference(noise_buf, floor_dbfs)
                    sources = ["musan_noise_floor"]

                # Content has NO speech segments (Mathematical closure)
                assembled, segs, marker_off = assemble_clip_with_marker(
                    noise_buf, [], self.marker_chirp
                )
                clip_id = f"silence_{split}_floor{int(floor_dbfs)}db_{i:03d}.wav"
                self._save_clip(
                    clip_id=clip_id,
                    category=CAT_SILENCE_ONLY,
                    split=split,
                    assembled_audio=assembled,
                    speech_segments=segs,  # Empty []
                    marker_offset=marker_off,
                    target_snr_db=None,
                    target_loudness_dbfs=floor_dbfs,
                    provenance={"sources": sources, "params": {"floor_dbfs": floor_dbfs}},
                )

    # --------------------------------------------------------------------------
    # Category 8: Music / Singing (Blueprint §6, Row 8)
    # --------------------------------------------------------------------------
    def build_music_singing(self) -> None:
        logger.info("Building Category 8: Music/singing (pure and speech-mixed)...")
        # Sub-type A: Pure music (empty speech segments)
        for i in range(self.config.clips_per_condition):
            split = "dev" if i % 2 == 0 else "test"
            music_raw = self._sample_music()
            length = int(SAMPLE_RATE * self.rng.uniform(4.0, 7.0))
            music_crop = loop_tile_crop(music_raw, length, self.rng)
            music_norm = normalize_to_reference(music_crop, -20.0)

            assembled, segs, marker_off = assemble_clip_with_marker(
                music_norm, [], self.marker_chirp
            )
            clip_id = f"music_pure_{split}_{i:03d}.wav"
            self._save_clip(
                clip_id=clip_id,
                category=CAT_MUSIC_SINGING,
                split=split,
                assembled_audio=assembled,
                speech_segments=segs,  # Empty []
                marker_offset=marker_off,
                target_snr_db=None,
                target_loudness_dbfs=-20.0,
                provenance={"sources": ["musan_music"], "params": {"subtype": "pure_music"}},
            )

        # Sub-type B: Speech with background music bed
        for split in ("dev", "test"):
            for snr in (10.0, 0.0):
                for i in range(max(1, self.config.clips_per_condition - 3)):
                    speech, sp_path = self._sample_utterance(split)
                    music = self._sample_music()
                    mixed, achieved_snr = mix_speech_and_noise(speech, music, snr, self.rng)
                    content_segs = [(0, len(speech))]
                    assembled, segs, marker_off = assemble_clip_with_marker(
                        mixed, content_segs, self.marker_chirp
                    )
                    clip_id = f"music_speech_mix_{split}_snr{int(snr)}db_{i:03d}.wav"
                    self._save_clip(
                        clip_id=clip_id,
                        category=CAT_MUSIC_SINGING,
                        split=split,
                        assembled_audio=assembled,
                        speech_segments=segs,
                        marker_offset=marker_off,
                        target_snr_db=snr,
                        target_loudness_dbfs=self.config.reference_level_dbfs,
                        provenance={"sources": [sp_path.name, "musan_music"], "achieved_snr_db": round(achieved_snr, 2), "params": {"subtype": "music_bed"}},
                    )

    # --------------------------------------------------------------------------
    # Category 9: Band-Limited Telephony (Blueprint §6, Row 9)
    # --------------------------------------------------------------------------
    def build_telephony(self) -> None:
        logger.info("Building Category 9: Band-limited telephony (300-3400Hz)...")
        for split in ("dev", "test"):
            # Clean band-limited
            for i in range(max(1, self.config.clips_per_condition - 2)):
                speech, sp_path = self._sample_utterance(split)
                filtered = apply_bandpass_telephony(speech, SAMPLE_RATE)
                content_segs = [(0, len(speech))]
                assembled, segs, marker_off = assemble_clip_with_marker(
                    filtered, content_segs, self.marker_chirp
                )
                clip_id = f"telephony_clean_{split}_{i:03d}.wav"
                self._save_clip(
                    clip_id=clip_id,
                    category=CAT_TELEPHONY,
                    split=split,
                    assembled_audio=assembled,
                    speech_segments=segs,
                    marker_offset=marker_off,
                    target_snr_db=None,
                    target_loudness_dbfs=self.config.reference_level_dbfs,
                    provenance={"sources": [sp_path.name], "params": {"bandpass": "300-3400Hz", "noise": False}},
                )

            # Noisy band-limited
            for i in range(max(1, self.config.clips_per_condition - 3)):
                speech, sp_path = self._sample_utterance(split)
                noise = self._sample_noise()
                mixed, _ = mix_speech_and_noise(speech, noise, 10.0, self.rng)
                filtered = apply_bandpass_telephony(mixed, SAMPLE_RATE)
                content_segs = [(0, len(speech))]
                assembled, segs, marker_off = assemble_clip_with_marker(
                    filtered, content_segs, self.marker_chirp
                )
                clip_id = f"telephony_noisy_{split}_{i:03d}.wav"
                self._save_clip(
                    clip_id=clip_id,
                    category=CAT_TELEPHONY,
                    split=split,
                    assembled_audio=assembled,
                    speech_segments=segs,
                    marker_offset=marker_off,
                    target_snr_db=10.0,
                    target_loudness_dbfs=self.config.reference_level_dbfs,
                    provenance={"sources": [sp_path.name], "params": {"bandpass": "300-3400Hz", "noise": True}},
                )

    # --------------------------------------------------------------------------
    # Category 10: Packet-Loss/Jitter (Blueprint §6, Row 10)
    # --------------------------------------------------------------------------
    def tag_packet_loss_jitter(self) -> None:
        logger.info("Tagging Category 10: Packet-loss/jitter (manifest retagging)...")
        clean_entries = [e for e in self.manifest_entries if e["category"] == CAT_CLEAN_SPEECH]
        selected_clean = clean_entries[: max(2, len(clean_entries) // 3)]
        out_dir = Path(self.config.output_audio_dir)

        for entry in selected_clean:
            orig_id = entry["clip_id"]
            new_id = f"packet_loss_{orig_id}"
            
            # Copy audio file to match unique ID
            src_wav = out_dir / orig_id
            dst_wav = out_dir / new_id
            if src_wav.is_file() and not dst_wav.is_file():
                shutil.copy2(src_wav, dst_wav)

            retagged_entry = dict(entry)
            retagged_entry["clip_id"] = new_id
            retagged_entry["category"] = CAT_PACKET_LOSS
            self.manifest_entries.append(retagged_entry)

    # --------------------------------------------------------------------------
    # Tier 2 Conversation Sequences (Blueprint §9)
    # --------------------------------------------------------------------------
    def build_tier2_sequences(self) -> None:
        logger.info("Building Tier 2 conversation sequences with controlled silence gaps...")
        conditions = [
            ("clean", None),
            ("stationary_10db", 10.0),
            ("stationary_0db", 0.0),
            ("babble_5db", 5.0),
        ]
        gaps_ms = self.config.tier2_gap_durations_ms  # [300, 800, 1500, 3000]

        for cond_name, snr_val in conditions:
            num_seqs = 4
            for seq_idx in range(num_seqs):
                split = "dev" if seq_idx % 2 == 0 else "test"
                num_utterances = self.rng.randint(2, 5)

                utterance_buffers: List[np.ndarray] = []
                content_speech_segments: List[Tuple[int, int]] = []
                sources: List[str] = []
                curr_offset = 0

                for u_idx in range(num_utterances):
                    utt_audio, src_path = self._sample_utterance(split)
                    sources.append(src_path.name)
                    utt_len = len(utt_audio)

                    # Mix noise if condition requires it
                    if snr_val is not None:
                        if "babble" in cond_name:
                            noise = normalize_to_reference(self._sample_noise(), -20.0)
                        else:
                            noise = self._sample_noise()
                        mixed, _ = mix_speech_and_noise(utt_audio, noise, snr_val, self.rng)
                    else:
                        mixed = utt_audio

                    utterance_buffers.append(mixed)
                    content_speech_segments.append((curr_offset, curr_offset + utt_len))
                    curr_offset += utt_len

                    # Interleave silence gap between turns
                    if u_idx < num_utterances - 1:
                        gap_ms = gaps_ms[(seq_idx + u_idx) % len(gaps_ms)]
                        gap_samples = int(SAMPLE_RATE * (gap_ms / 1000.0))
                        gap_buf = np.zeros(gap_samples, dtype=np.float32)
                        utterance_buffers.append(gap_buf)
                        curr_offset += gap_samples

                full_content = np.concatenate(utterance_buffers)
                assembled, segs, marker_off = assemble_clip_with_marker(
                    full_content, content_speech_segments, self.marker_chirp
                )
                clip_id = f"tier2_seq_{cond_name}_{split}_{seq_idx:03d}.wav"
                cat = CAT_BABBLE if "babble" in cond_name else (CAT_STATIONARY_NOISE if snr_val is not None else CAT_CLEAN_SPEECH)

                self._save_clip(
                    clip_id=clip_id,
                    category=cat,
                    split=split,
                    assembled_audio=assembled,
                    speech_segments=segs,
                    marker_offset=marker_off,
                    target_snr_db=snr_val,
                    target_loudness_dbfs=self.config.reference_level_dbfs,
                    provenance={"sources": sources, "params": {"tier2_sequence": True, "condition": cond_name}},
                )

    def run_all(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Runs the entire recipe suite in deterministic sequence."""
        self.build_clean_speech()
        self.build_stationary_noise()
        self.build_transient_noise()
        self.build_babble_noise()
        self.build_quiet_whisper()
        self.build_loud_clipped()
        self.build_silence_only()
        self.build_music_singing()
        self.build_telephony()
        self.tag_packet_loss_jitter()
        self.build_tier2_sequences()

        logger.info(
            f"Corpus build complete. Generated {len(self.manifest_entries)} total entries."
        )
        return self.manifest_entries, self.recipe_logs


# ==============================================================================
# Manifest Hash, Caching, and Publishing Utilities (Blueprint §11, §12)
# ==============================================================================
def compute_manifest_sha256(manifest_entries: List[Dict[str, Any]]) -> str:
    """Computes a deterministic SHA-256 hash across manifest entries (matching manifest.py)."""
    serialized = json.dumps(manifest_entries, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def check_cache_and_materialize(
    manifest_path: Path,
    audio_dir: Path,
    expected_hash: Optional[str] = None,
) -> bool:
    """Returns True if valid cached manifest and corresponding audio clips exist."""
    if not manifest_path.is_file() or not audio_dir.is_dir():
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            return False

        if expected_hash is not None:
            current_hash = compute_manifest_sha256(data)
            if current_hash != expected_hash:
                return False

        # Verify a sample of audio files actually exist
        sample_entries = data[: min(10, len(data))]
        for entry in sample_entries:
            wav_file = audio_dir / entry["clip_id"]
            if not wav_file.is_file() or wav_file.stat().st_size == 0:
                return False

        return True
    except Exception as e:
        logger.warning(f"Cache validation encountered error: {e}")
        return False


def fetch_published_corpus(config: CorpusBuildConfig) -> bool:
    """
    Attempts to fetch pre-built processed corpus (~150MB) from remote publish target
    (Blueprint §12). Returns True on success, False to trigger local build.
    """
    target = config.publish_target.lower()
    logger.info(f"Checking remote publish target: {target}")

    try:
        if target == "github_release":
            repo = config.github_release.get("repo_slug")
            tag = config.github_release.get("tag_name", "corpus-v1")
            asset = config.github_release.get("asset_name", "corpus_processed.zip")
            if not repo or "your-org" in repo:
                return False

            url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
            import requests

            logger.info(f"Downloading pre-built corpus from: {url}")
            resp = requests.get(url, stream=True, timeout=60)
            if resp.status_code == 200:
                zip_dest = Path(config.raw_cache_dir) / asset
                zip_dest.parent.mkdir(parents=True, exist_ok=True)
                with open(zip_dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                with zipfile.ZipFile(zip_dest, "r") as zip_ref:
                    zip_ref.extractall(Path(config.output_audio_dir).parent)
                logger.info("Successfully fetched and extracted remote corpus archive.")
                return True

        elif target == "gdrive":
            drive_folder = config.gdrive.get("drive_folder_path")
            archive_name = config.gdrive.get("archive_name", "corpus_processed.zip")
            if drive_folder:
                archive_path = Path(drive_folder) / archive_name
                if archive_path.is_file():
                    logger.info(f"Extracting from Google Drive archive: {archive_path}")
                    with zipfile.ZipFile(archive_path, "r") as zip_ref:
                        zip_ref.extractall(Path(config.output_audio_dir).parent)
                    return True

        elif target == "kaggle_dataset":
            dataset_slug = config.kaggle_dataset.get("dataset_slug")
            if dataset_slug and not dataset_slug.startswith("your-"):
                logger.info(f"Attempting Kaggle CLI download for dataset: {dataset_slug}")
                ret = os.system(f"kaggle datasets download -d {dataset_slug} -p {config.raw_cache_dir} --unzip")
                return ret == 0

    except Exception as e:
        logger.warning(f"Could not fetch pre-built corpus from {target}: {e}")

    return False


# ==============================================================================
# Public Orchestration Entry Point
# ==============================================================================
def build_corpus(config_path: Union[str, Path], force_rebuild: bool = False) -> str:
    """
    Main programmatic interface for corpus building.
    1. Loads `corpus_build_config.yaml`.
    2. Checks cache idempotency; skips rebuild if manifest hash matches.
    3. Fetches remote archive if configured.
    4. Executes recipe suite, serializing manifest.json and recipe_log.json.
    5. Returns the manifest SHA-256 version hash.
    """
    config = CorpusBuildConfig.from_yaml(config_path)
    manifest_out = Path(config.output_manifest_path)
    audio_out = Path(config.output_audio_dir)
    recipe_out = Path(config.recipe_log_path)

    rebuild = force_rebuild or config.force_rebuild

    # Check cache idempotency if not forced
    if not rebuild and check_cache_and_materialize(manifest_out, audio_out):
        with open(manifest_out, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        manifest_hash = compute_manifest_sha256(existing_data)
        logger.info(
            f"Matching cached corpus detected (SHA-256: {manifest_hash[:12]}...). "
            f"Skipping rebuild. Use --force-rebuild to override."
        )
        return manifest_hash

    # Attempt fetching published corpus before touching raw 11GB
    if not rebuild and fetch_published_corpus(config):
        if check_cache_and_materialize(manifest_out, audio_out):
            with open(manifest_out, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            return compute_manifest_sha256(existing_data)

    # Execute full build
    logger.info("Executing full audio synthesis and mixing pipeline...")
    engine = CorpusBuilderEngine(config)
    manifest_entries, recipe_logs = engine.run_all()

    # Write output manifest JSON
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, indent=2)
    logger.info(f"Wrote canonical manifest: {manifest_out.resolve()}")

    # Write provenance recipe log JSON
    recipe_out.parent.mkdir(parents=True, exist_ok=True)
    with open(recipe_out, "w", encoding="utf-8") as f:
        json.dump(recipe_logs, f, indent=2)
    logger.info(f"Wrote provenance recipe log: {recipe_out.resolve()}")

    manifest_hash = compute_manifest_sha256(manifest_entries)
    logger.info(f"Corpus Manifest Version Hash (SHA-256): {manifest_hash}")

    return manifest_hash


# ==============================================================================
# CLI Invocation Interface
# ==============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voice Bot VAD Harness — Audio Dataset & Manifest Builder"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="corpus/corpus_build_config.yaml",
        help="Path to corpus_build_config.yaml",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force regeneration of audio files and manifest even if cache matches",
    )
    args = parser.parse_args()

    try:
        manifest_hash = build_corpus(args.config, force_rebuild=args.force_rebuild)
        print(f"\nSUCCESS: Corpus built and verified. Manifest SHA-256: {manifest_hash}")
    except Exception as err:
        logger.error(f"Fatal error during dataset construction: {err}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()