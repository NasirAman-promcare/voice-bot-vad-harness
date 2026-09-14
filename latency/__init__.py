"""
latency package initialization.

Exposes Tier 2 live pipeline latency calculation structures, marker alignment
utilities, and chirp waveform generators.
"""

from latency.latency_calculator import (
    LatencyCalculationError,
    PipelineLatencyResult,
    SegmentLatency,
    calculate_pipeline_latency,
)
from latency.marker_alignment import (
    MarkerAlignmentError,
    MarkerAlignmentResult,
    align_marker,
    generate_calibration_chirp,
)

__all__ = [
    # Latency Calculator
    "LatencyCalculationError",
    "PipelineLatencyResult",
    "SegmentLatency",
    "calculate_pipeline_latency",
    # Marker Alignment
    "MarkerAlignmentError",
    "MarkerAlignmentResult",
    "align_marker",
    "generate_calibration_chirp",
]