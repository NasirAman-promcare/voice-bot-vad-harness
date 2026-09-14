"""
audio_profiler.py

One Job:
    Profile the physical acoustic properties of an audio clip or frame (loudness,
    peak level, clipping, noise floor, blind SNR estimation, spectral flatness,
    zero-crossing rate, and crest factor) with ZERO knowledge or awareness of any VAD
    decisions, adapters, or scores.

Verification vs. Blind Estimation (Single Code Path):
    This module serves two dual purposes through one unified interface:
      1. Acoustic Verification: When ground-truth target metadata (target SNR, target
         loudness) is provided from the manifest, it calculates deviations (deltas)
         to verify signal integrity post-transport/transcoding.
      2. Blind Estimation: When operated on unannotated audio without metadata, it
         performs pure blind estimation (percentile-based SNR, noise-floor tracking,
         spectral analysis) without assuming ground truth exists.

Silence-Only Defined Behavior:
    For silence-only audio buffers (RMS < 1e-5 / -100 dBFS):
      - Loudness: RMS = -100.0 dBFS, Peak = -100.0 dBFS.
      - Clipping: is_clipped = False, clipping_ratio = 0.0.
      - Noise Floor: -100.0 dBFS.
      - SNR: Explicitly None (mathematically undefined when true signal power is zero).
      - Spectral Flatness: 0.0.
      - Zero-Crossing Rate: 0.0.
      - Crest Factor: 1.0 (0.0 dB).

What this module must NEVER do:
    - Never import, reference, or inspect any VAD adapter, registry, or engine.
    - Never see, parse, or handle DecisionRecord objects or inference scores.
    - Never re-derive acoustic categories by listening to audio (category is read
      from manifest metadata or left None).
    - Never let profiling logic influence or depend on scoring logic.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Numerical stability floor for logarithm operations
_EPSILON = 1e-10
_SILENCE_RMS_FLOOR = 1e-5  # -100 dBFS threshold
_CLIPPING_THRESHOLD = 0.999  # Absolute amplitude threshold for float32 audio in [-1.0, 1.0]


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class LoudnessProfile:
    """Acoustic loudness and amplitude envelope metrics."""
    rms_dbfs: float
    peak_dbfs: float
    is_clipped: bool
    clipping_ratio: float
    clipped_sample_count: int


@dataclass(frozen=True)
class NoiseProfile:
    """Acoustic noise floor and signal-to-noise ratio estimation."""
    estimated_snr_db: Optional[float]
    noise_floor_dbfs: float
    signal_level_dbfs: Optional[float]


@dataclass(frozen=True)
class SpectralCharacterProfile:
    """Spectral distribution and time-domain waveform character metrics."""
    spectral_flatness: float
    spectral_centroid_hz: float
    zero_crossing_rate: float
    crest_factor: float
    crest_factor_db: float


@dataclass(frozen=True)
class VerificationDeltas:
    """Discrepancies between target metadata and measured physical acoustics."""
    target_snr_db: Optional[float]
    snr_delta_db: Optional[float]
    target_loudness_lufs: Optional[float]
    loudness_delta_db: Optional[float]


@dataclass(frozen=True)
class AudioProfile:
    """
    Immutable representation of an audio signal's acoustic character.
    """
    clip_id: Optional[str]
    category: Optional[str]
    sample_rate_hz: int
    duration_seconds: float
    total_samples: int
    is_silence: bool
    loudness: LoudnessProfile
    noise: NoiseProfile
    spectral: SpectralCharacterProfile
    verification: VerificationDeltas

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the profile into a JSON-serializable dictionary."""
        return asdict(self)


# ==============================================================================
# Core Acoustic Measurement Functions
# ==============================================================================

def compute_loudness_profile(
    audio: np.ndarray,
    clipping_threshold: float = _CLIPPING_THRESHOLD,
) -> Tuple[LoudnessProfile, bool]:
    """
    Computes RMS level (dBFS), peak amplitude (dBFS), and detects waveform clipping.

    Returns:
        A tuple of (LoudnessProfile, is_silence_flag).
    """
    if len(audio) == 0:
        return (
            LoudnessProfile(
                rms_dbfs=-100.0,
                peak_dbfs=-100.0,
                is_clipped=False,
                clipping_ratio=0.0,
                clipped_sample_count=0,
            ),
            True,
        )

    # Peak amplitude
    peak_linear = float(np.max(np.abs(audio)))
    if peak_linear < _SILENCE_RMS_FLOOR:
        peak_dbfs = -100.0
    else:
        peak_dbfs = float(20.0 * np.log10(np.clip(peak_linear, _EPSILON, 1.0)))

    # RMS amplitude
    mean_square = float(np.mean(audio ** 2))
    rms_linear = float(np.sqrt(mean_square))
    if rms_linear < _SILENCE_RMS_FLOOR:
        rms_dbfs = -100.0
        is_silence = True
    else:
        rms_dbfs = float(20.0 * np.log10(np.clip(rms_linear, _EPSILON, 1.0)))
        is_silence = False

    # Clipping detection
    clipped_mask = np.abs(audio) >= clipping_threshold
    clipped_count = int(np.sum(clipped_mask))
    clipping_ratio = float(clipped_count / len(audio))

    # Trigger clipping flag if >= 3 consecutive/total samples hit the maximum rail
    is_clipped = bool(clipped_count >= 3 or clipping_ratio >= 1e-4)

    return (
        LoudnessProfile(
            rms_dbfs=round(rms_dbfs, 2),
            peak_dbfs=round(peak_dbfs, 2),
            is_clipped=is_clipped,
            clipping_ratio=round(clipping_ratio, 6),
            clipped_sample_count=clipped_count,
        ),
        is_silence,
    )


def compute_noise_profile(
    audio: np.ndarray,
    sample_rate_hz: int = 16000,
    is_silence: bool = False,
) -> NoiseProfile:
    """
    Performs blind SNR and noise floor estimation using frame-level energy percentiles.

    For silence-only audio, SNR is explicitly None (undefined).
    """
    if is_silence or len(audio) == 0:
        return NoiseProfile(
            estimated_snr_db=None,
            noise_floor_dbfs=-100.0,
            signal_level_dbfs=None,
        )

    # Frame-level short-term energy (20ms window, 10ms hop)
    frame_len = int(sample_rate_hz * 0.020)
    hop_len = int(sample_rate_hz * 0.010)

    if len(audio) < frame_len:
        # Buffer too short for multi-frame histogram; fallback to scalar RMS
        rms_val = float(np.sqrt(np.mean(audio ** 2)))
        db_val = float(20.0 * np.log10(max(rms_val, _EPSILON)))
        return NoiseProfile(
            estimated_snr_db=None,
            noise_floor_dbfs=round(db_val, 2),
            signal_level_dbfs=round(db_val, 2),
        )

    num_frames = 1 + (len(audio) - frame_len) // hop_len
    frame_energies_db = np.zeros(num_frames, dtype=np.float32)

    for i in range(num_frames):
        start = i * hop_len
        end = start + frame_len
        frame = audio[start:end]
        frame_rms = np.sqrt(np.mean(frame ** 2))
        frame_energies_db[i] = 20.0 * np.log10(max(frame_rms, _EPSILON))

    # Noise floor estimated from the lower 10th percentile of frame energies
    noise_floor_db = float(np.percentile(frame_energies_db, 10))

    # Active signal level estimated from the upper 90th percentile of frame energies
    signal_level_db = float(np.percentile(frame_energies_db, 90))

    # SNR is difference between active signal level and background noise floor
    estimated_snr = max(0.0, signal_level_db - noise_floor_db)

    # If the entire clip has minimal dynamic energy range (< 2 dB variance), it is pure stationary noise or tone
    if (signal_level_db - noise_floor_db) < 2.0 and signal_level_db < -50.0:
        estimated_snr = 0.0

    return NoiseProfile(
        estimated_snr_db=round(estimated_snr, 2),
        noise_floor_dbfs=round(max(-100.0, noise_floor_db), 2),
        signal_level_dbfs=round(max(-100.0, signal_level_db), 2),
    )


def compute_spectral_character(
    audio: np.ndarray,
    sample_rate_hz: int = 16000,
    is_silence: bool = False,
) -> SpectralCharacterProfile:
    """
    Computes spectral flatness (Wiener entropy), spectral centroid, zero-crossing rate,
    and crest factor.
    """
    if is_silence or len(audio) == 0:
        return SpectralCharacterProfile(
            spectral_flatness=0.0,
            spectral_centroid_hz=0.0,
            zero_crossing_rate=0.0,
            crest_factor=1.0,
            crest_factor_db=0.0,
        )

    # 1. Zero Crossing Rate (ZCR)
    sign_changes = np.abs(np.diff(np.signbit(audio)))
    zcr = float(np.mean(sign_changes)) if len(sign_changes) > 0 else 0.0

    # 2. Crest Factor (Peak to RMS ratio)
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    crest_factor = float(peak / max(rms, _EPSILON))
    crest_factor_db = float(20.0 * np.log10(max(crest_factor, 1.0)))

    # 3. Spectral Analysis via Windowed STFT Power Spectrum
    n_fft = 512
    hop_length = 256
    window = np.hanning(n_fft)

    if len(audio) < n_fft:
        # Pad short buffer with zeros
        padded = np.pad(audio, (0, n_fft - len(audio)), mode="constant")
        frames = [padded]
    else:
        num_frames = 1 + (len(audio) - n_fft) // hop_length
        frames = [audio[i * hop_length : i * hop_length + n_fft] for i in range(num_frames)]

    flatness_values = []
    centroid_values = []
    freq_bins = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate_hz)

    for frame in frames:
        spec = np.abs(np.fft.rfft(frame * window)) ** 2
        spec_sum = np.sum(spec)

        if spec_sum < _EPSILON:
            continue

        # Spectral Flatness: Geometric Mean / Arithmetic Mean of Power Spectrum
        log_spec = np.log(spec + _EPSILON)
        geom_mean = np.exp(np.mean(log_spec))
        arith_mean = np.mean(spec) + _EPSILON
        flatness = float(np.clip(geom_mean / arith_mean, 0.0, 1.0))
        flatness_values.append(flatness)

        # Spectral Centroid: Weighted frequency average
        centroid = float(np.sum(freq_bins * spec) / spec_sum)
        centroid_values.append(centroid)

    avg_flatness = float(np.mean(flatness_values)) if flatness_values else 0.0
    avg_centroid = float(np.mean(centroid_values)) if centroid_values else 0.0

    return SpectralCharacterProfile(
        spectral_flatness=round(avg_flatness, 4),
        spectral_centroid_hz=round(avg_centroid, 2),
        zero_crossing_rate=round(zcr, 4),
        crest_factor=round(crest_factor, 2),
        crest_factor_db=round(crest_factor_db, 2),
    )


# ==============================================================================
# Public Profiler Entry Point
# ==============================================================================

def profile_audio_clip(
    audio: np.ndarray,
    sample_rate_hz: int = 16000,
    clip_id: Optional[str] = None,
    category: Optional[str] = None,
    target_snr_db: Optional[float] = None,
    target_loudness_lufs: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Profiles an audio clip, returning acoustic measurements and verification deltas.

    Unified Interface:
        - If target_snr_db or target_loudness_lufs are provided, calculates verification deltas.
        - If target parameters are None, performs pure blind acoustic estimation.

    Args:
        audio: 1D NumPy array of audio samples (float32 in [-1.0, 1.0] or int16).
        sample_rate_hz: Audio sample rate (default: 16000 Hz).
        clip_id: Optional clip identifier string.
        category: Optional category string from manifest.
        target_snr_db: Optional manifest ground-truth SNR for verification.
        target_loudness_lufs: Optional manifest ground-truth loudness for verification.

    Returns:
        A dictionary representation of the complete AudioProfile.

    Raises:
        ValueError: If audio buffer format or dimensions are invalid.
    """
    if not isinstance(audio, np.ndarray):
        audio = np.asarray(audio)

    # Normalize dimensions to 1D
    if audio.ndim > 1:
        if audio.shape[0] == 1 or audio.shape[1] == 1:
            audio = audio.flatten()
        else:
            raise ValueError(f"Expected 1D mono audio buffer, received shape {audio.shape}.")

    # Convert int16 to normalized float32 [-1.0, 1.0]
    if audio.dtype == np.int16:
        audio_float = audio.astype(np.float32) / 32768.0
    elif np.issubdtype(audio.dtype, np.floating):
        audio_float = audio.astype(np.float32)
    else:
        audio_float = (audio.astype(np.float32) / np.max(np.abs(audio) + _EPSILON)).astype(np.float32)

    total_samples = len(audio_float)
    duration_s = float(total_samples / sample_rate_hz) if sample_rate_hz > 0 else 0.0

    # 1. Loudness Profile & Silence Detection
    loudness, is_silence = compute_loudness_profile(audio_float)

    # 2. Noise Floor & Blind SNR Estimation
    noise = compute_noise_profile(audio_float, sample_rate_hz=sample_rate_hz, is_silence=is_silence)

    # 3. Spectral Character & Flatness
    spectral = compute_spectral_character(audio_float, sample_rate_hz=sample_rate_hz, is_silence=is_silence)

    # 4. Verification Deltas (if ground truth targets are provided)
    snr_delta: Optional[float] = None
    if target_snr_db is not None and noise.estimated_snr_db is not None:
        snr_delta = round(float(noise.estimated_snr_db - target_snr_db), 2)

    loudness_delta: Optional[float] = None
    if target_loudness_lufs is not None and not is_silence:
        loudness_delta = round(float(loudness.rms_dbfs - target_loudness_lufs), 2)

    verification = VerificationDeltas(
        target_snr_db=target_snr_db,
        snr_delta_db=snr_delta,
        target_loudness_lufs=target_loudness_lufs,
        loudness_delta_db=loudness_delta,
    )

    profile = AudioProfile(
        clip_id=clip_id,
        category=category,
        sample_rate_hz=sample_rate_hz,
        duration_seconds=round(duration_s, 3),
        total_samples=total_samples,
        is_silence=is_silence,
        loudness=loudness,
        noise=noise,
        spectral=spectral,
        verification=verification,
    )

    return profile.to_dict()