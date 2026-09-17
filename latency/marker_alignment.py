"""
latency/marker_alignment.py

One Job:
    Cross-correlate the incoming decoded 16kHz audio stream against the known calibration
    chirp waveform to find the exact sample index where normalized cross-correlation peaks,
    establishing the ground-truth physical "Time Zero" ($T_0$) on the Listener Bot's timeline.

Why this file exists (Single Clock Authority):
    In a distributed, two-process Tier 2 pipeline (Speaker Bot playing into Jitsi, Listener
    Bot receiving off the bridge), process clocks drift and NTP sync is insufficient for
    sub-millisecond VAD benchmarking. Cross-correlating the embedded acoustic chirp grounds
    all latency calculations purely in physical audio arrival time on the Listener Bot's
    local clock.

Peak Disambiguation & Low-Confidence Policy:
    - Minimum Confidence Threshold: Normalized cross-correlation peak must exceed
      `min_confidence_threshold` (default 0.50). If transport artifacts, clipping, or
      packet loss corrupt the marker such that the peak is below this threshold, the output
      explicitly returns `marker_detected=False`, `detected_marker_sample_offset=None`,
      and `status='low_confidence'`. Low-confidence guesses are NEVER passed off as ground truth.
    - Multiple Candidate Peaks: If a secondary correlation peak occurs within 85% of the
      primary peak's magnitude, the highest peak is selected, but the result is flagged with
      `is_ambiguous=True` and `status='ambiguous_peaks'` for downstream auditability.

What this module must NEVER do:
    - Never accept, reference, or subtract wall-clock timestamps from speaker_bot.py.
    - Never return a bare index without an accompanying confidence metric.
    - Never silently fall through with an unverified or arbitrary sample index.
    - Never perform VAD scoring or confusion matrix calculations.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Canonical calibration chirp parameters: 60ms linear sweep (700Hz -> 2600Hz) at 16kHz
DEFAULT_CHIRP_DURATION_S = 0.060
DEFAULT_CHIRP_F_START_HZ = 700.0
DEFAULT_CHIRP_F_END_HZ = 2600.0
DEFAULT_MIN_CONFIDENCE_THRESHOLD = 0.50
DEFAULT_AMBIGUITY_RATIO_THRESHOLD = 0.85


# ==============================================================================
# Exceptions
# ==============================================================================

class MarkerAlignmentError(Exception):
    """Base exception for marker alignment failures."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class MarkerAlignmentResult:
    """
    Immutable result of the acoustic cross-correlation marker alignment.

    Attributes:
        marker_detected: True if a valid marker was detected above the confidence threshold.
        detected_marker_sample_offset: Sample index where the chirp begins in the received stream (None if undetected).
        reference_marker_offset_samples: Expected marker sample offset from manifest metadata.
        sample_offset_delta: Alignment discrepancy (detected - reference).
        alignment_confidence: Normalized cross-correlation peak coefficient [0.0, 1.0].
        secondary_peak_ratio: Ratio of second highest peak to highest peak (None if single peak).
        is_ambiguous: True if a secondary peak is close in magnitude to the primary peak.
        time_zero_timestamp_ns: Monotonic nanosecond timestamp of sample 0 on the Listener Bot's clock.
        status: Diagnostic status ('detected', 'low_confidence', 'ambiguous_peaks', 'signal_silence').
    """
    marker_detected: bool
    detected_marker_sample_offset: Optional[int]
    reference_marker_offset_samples: int
    sample_offset_delta: Optional[int]
    alignment_confidence: float
    secondary_peak_ratio: Optional[float]
    is_ambiguous: bool
    time_zero_timestamp_ns: int
    status: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the alignment result to a dictionary."""
        return asdict(self)


# ==============================================================================
# Canonical Calibration Chirp Generator (Exported with dual aliases)
# ==============================================================================

def generate_calibration_chirp(
    sample_rate_hz: int = 16000,
    duration_s: float = DEFAULT_CHIRP_DURATION_S,
    f_start_hz: float = DEFAULT_CHIRP_F_START_HZ,
    f_end_hz: float = DEFAULT_CHIRP_F_END_HZ,
) -> np.ndarray:
    """
    Generates the deterministic canonical calibration chirp waveform (16kHz float32).

    Uses a linear frequency sweep with a 10% Tukey window (fade-in/fade-out) to prevent
    spectral leakage and boundary step transients.

    Returns:
        1D NumPy array of float32 samples.
    """
    num_samples = int(sample_rate_hz * duration_s)
    t = np.linspace(0.0, duration_s, num_samples, endpoint=False, dtype=np.float32)

    # Instantaneous phase for linear chirp: phi(t) = 2 * pi * (f_start * t + (f_end - f_start) / (2 * T) * t^2)
    k = (f_end_hz - f_start_hz) / duration_s
    phase = 2.0 * np.pi * (f_start_hz * t + 0.5 * k * (t ** 2))
    raw_chirp = np.sin(phase).astype(np.float32)

    # 10% Tukey taper window
    taper_len = int(0.10 * num_samples)
    if taper_len > 0:
        window = np.ones(num_samples, dtype=np.float32)
        fade = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, taper_len, dtype=np.float32)))
        window[:taper_len] = fade
        window[-taper_len:] = fade[::-1]
        raw_chirp *= window

    # Normalize amplitude to -6 dBFS (0.501187 peak)
    max_val = np.max(np.abs(raw_chirp))
    if max_val > 0:
        raw_chirp = (raw_chirp / max_val) * 0.501187

    return raw_chirp


def generate_reference_marker(sample_rate_hz: int = 16000) -> np.ndarray:
    """
    Public alias for generate_calibration_chirp ensuring seamless cross-module imports.
    """
    return generate_calibration_chirp(sample_rate_hz=sample_rate_hz)


# ==============================================================================
# Normalized Cross-Correlation Engine
# ==============================================================================

def _compute_normalized_cross_correlation(
    audio: np.ndarray,
    template: np.ndarray,
) -> np.ndarray:
    """
    Computes running Normalized Cross-Correlation (NCC) between audio and template.

    NCC[k] = sum(audio[k:k+M] * template) / sqrt(sum(audio[k:k+M]^2) * sum(template^2))

    Returns:
        1D array of correlation coefficients bounded in [-1.0, 1.0].
    """
    audio_len = len(audio)
    tmpl_len = len(template)

    if audio_len < tmpl_len or tmpl_len == 0:
        return np.empty(0, dtype=np.float32)

    # Energy of the template
    tmpl_energy = float(np.sum(template ** 2))
    if tmpl_energy < 1e-10:
        return np.zeros(audio_len - tmpl_len + 1, dtype=np.float32)

    # Fast convolution via FFT
    try:
        from scipy.signal import fftconvolve
        # Cross-correlation via convolution with reversed template
        raw_corr = fftconvolve(audio, template[::-1], mode="valid")
    except ImportError:
        # NumPy fallback convolution
        raw_corr = np.convolve(audio, template[::-1], mode="valid")

    # Running energy of audio windows using cumulative sum
    audio_sq = audio.astype(np.float64) ** 2
    cumsum = np.pad(np.cumsum(audio_sq), (1, 0), mode="constant")
    window_energies = cumsum[tmpl_len:] - cumsum[:-tmpl_len]

    # Compute normalized correlation denominator
    # Energy threshold: zero out windows with near-zero energy (avoids divide-by-zero silence spikes)
    min_energy_threshold = 1e-4 * tmpl_energy
    valid_mask = window_energies > min_energy_threshold
    denom = np.sqrt(np.maximum(window_energies * tmpl_energy, 1e-12))
    ncc = np.zeros_like(raw_corr, dtype=np.float32)
    np.divide(raw_corr, denom, out=ncc, where=valid_mask)
    return np.clip(ncc, -1.0, 1.0)


# ==============================================================================
# Marker Alignment Entry Point
# ==============================================================================

def align_marker(
    received_audio: np.ndarray,
    reference_marker_offset: Optional[int] = 320,
    marker_waveform: Optional[np.ndarray] = None,
    stream_start_timestamp_ns: int = 0,
    sample_rate_hz: int = 16000,
    min_confidence_threshold: float = DEFAULT_MIN_CONFIDENCE_THRESHOLD,
    ambiguity_ratio_threshold: float = DEFAULT_AMBIGUITY_RATIO_THRESHOLD,
    expected_offset_samples: Optional[int] = None,
) -> MarkerAlignmentResult:
    """
    Locates the calibration chirp in received audio via normalized cross-correlation.

    Finds the sample index of maximum correlation, evaluates detection confidence,
    resolves candidate peak ties, and establishes ground-truth Time Zero ($T_0$).

    Args:
        received_audio: Decoded 16kHz mono audio from Listener Bot.
        reference_marker_offset: Sample index where chirp was placed in the original clip.
        marker_waveform: Reference chirp template (generated automatically if None).
        stream_start_timestamp_ns: Monotonic arrival timestamp of sample 0 from Listener Bot.
        sample_rate_hz: Expected sample rate (16000 Hz).
        min_confidence_threshold: Minimum correlation peak required for valid detection (0.50).
        ambiguity_ratio_threshold: Ratio threshold to flag closely competing secondary peaks (0.85).
        expected_offset_samples: Compatibility alias for reference_marker_offset.

    Returns:
        MarkerAlignmentResult containing detection status, sample offset, and confidence.
    """
    if sample_rate_hz != 16000:
        raise ValueError(f"align_marker strictly requires 16000 Hz, received {sample_rate_hz}.")

    ref_offset = expected_offset_samples if expected_offset_samples is not None else (reference_marker_offset or 0)

    if not isinstance(received_audio, np.ndarray):
        received_audio = np.asarray(received_audio)

    # Normalize dimensions
    if received_audio.ndim > 1:
        received_audio = received_audio.flatten()

    # Generate or validate reference chirp template
    template = (
        marker_waveform
        if marker_waveform is not None
        else generate_calibration_chirp(sample_rate_hz=sample_rate_hz)
    )

    # Edge Case: Audio buffer shorter than chirp or empty
    if len(received_audio) < len(template):
        logger.warning(
            "[MarkerAlignment] Audio buffer length (%d) < template length (%d). Marker undetected.",
            len(received_audio),
            len(template),
        )
        return MarkerAlignmentResult(
            marker_detected=False,
            detected_marker_sample_offset=None,
            reference_marker_offset_samples=ref_offset,
            sample_offset_delta=None,
            alignment_confidence=0.0,
            secondary_peak_ratio=None,
            is_ambiguous=False,
            time_zero_timestamp_ns=stream_start_timestamp_ns,
            status="buffer_too_short",
        )

    # Check for silence buffer (RMS < 1e-5)
    rms = float(np.sqrt(np.mean(received_audio ** 2)))
    if rms < 1e-5:
        logger.warning("[MarkerAlignment] Received audio is pure silence (RMS < 1e-5). Marker undetected.")
        return MarkerAlignmentResult(
            marker_detected=False,
            detected_marker_sample_offset=None,
            reference_marker_offset_samples=ref_offset,
            sample_offset_delta=None,
            alignment_confidence=0.0,
            secondary_peak_ratio=None,
            is_ambiguous=False,
            time_zero_timestamp_ns=stream_start_timestamp_ns,
            status="signal_silence",
        )

    # Compute Normalized Cross-Correlation across entire audio buffer
    ncc = _compute_normalized_cross_correlation(received_audio, template)
    if len(ncc) == 0:
        return MarkerAlignmentResult(
            marker_detected=False,
            detected_marker_sample_offset=None,
            reference_marker_offset_samples=ref_offset,
            sample_offset_delta=None,
            alignment_confidence=0.0,
            secondary_peak_ratio=None,
            is_ambiguous=False,
            time_zero_timestamp_ns=stream_start_timestamp_ns,
            status="correlation_failed",
        )

    # Peak detection & disambiguation
    primary_peak_idx = int(np.argmax(ncc))
    primary_peak_val = float(ncc[primary_peak_idx])

    # Find secondary peak outside the mainlobe (exclusion window = template_length / 2)
    exclusion_radius = len(template) // 2
    ncc_masked = ncc.copy()
    mask_start = max(0, primary_peak_idx - exclusion_radius)
    mask_end = min(len(ncc), primary_peak_idx + exclusion_radius)
    ncc_masked[mask_start:mask_end] = -1.0

    secondary_peak_val = float(np.max(ncc_masked)) if len(ncc_masked) > 0 else 0.0
    secondary_ratio: Optional[float] = None
    is_ambiguous = False

    if primary_peak_val > 0.0 and secondary_peak_val > 0.0:
        secondary_ratio = round(secondary_peak_val / primary_peak_val, 4)
        if secondary_ratio >= ambiguity_ratio_threshold:
            is_ambiguous = True

    # Validate against minimum confidence threshold
    if primary_peak_val < min_confidence_threshold:
        logger.warning(
            "[MarkerAlignment] Low confidence detection (peak=%.3f < threshold=%.2f). Marker unreliable.",
            primary_peak_val,
            min_confidence_threshold,
        )
        return MarkerAlignmentResult(
            marker_detected=False,
            detected_marker_sample_offset=None,
            reference_marker_offset_samples=ref_offset,
            sample_offset_delta=None,
            alignment_confidence=round(primary_peak_val, 4),
            secondary_peak_ratio=secondary_ratio,
            is_ambiguous=is_ambiguous,
            time_zero_timestamp_ns=stream_start_timestamp_ns,
            status="low_confidence",
        )

    # Calculate Time Zero ($T_0$) timestamp on Listener Bot clock
    detected_offset = primary_peak_idx
    sample_delta = detected_offset - ref_offset

    time_zero_ns = stream_start_timestamp_ns
    if stream_start_timestamp_ns > 0:
        offset_duration_ns = int((detected_offset / sample_rate_hz) * 1e9)
        time_zero_ns = stream_start_timestamp_ns + offset_duration_ns

    status = "ambiguous_peaks" if is_ambiguous else "detected"
    if is_ambiguous:
        logger.warning(
            "[MarkerAlignment] Ambiguous candidate peaks detected (primary=%.3f, secondary=%.3f, ratio=%.3f)",
            primary_peak_val,
            secondary_peak_val,
            secondary_ratio,
        )

    logger.debug(
        "[MarkerAlignment] Marker detected at sample %d (conf=%.3f, delta=%d samples)",
        detected_offset,
        primary_peak_val,
        sample_delta,
    )

    return MarkerAlignmentResult(
        marker_detected=True,
        detected_marker_sample_offset=detected_offset,
        reference_marker_offset_samples=ref_offset,
        sample_offset_delta=sample_delta,
        alignment_confidence=round(primary_peak_val, 4),
        secondary_peak_ratio=secondary_ratio,
        is_ambiguous=is_ambiguous,
        time_zero_timestamp_ns=time_zero_ns,
        status=status,
    )