"""
webrtc_bridge/rtp_sequence.py

One Job:
    Turn raw 16-bit RTP sequence numbers (random start, wrap at 65535) into a
    monotonic extended counter, so downstream code never sees the wraparound.
"""
from __future__ import annotations

from typing import Optional


class RtpSequenceUnwrapper:
    """Extends 16-bit RTP sequence numbers to a monotonic integer (RFC 3550 A.1 style)."""

    def __init__(self) -> None:
        self._highest: Optional[int] = None

    def unwrap(self, seq16: int) -> int:
        seq16 = int(seq16) & 0xFFFF
        if self._highest is None:
            self._highest = seq16
            return seq16
        # signed distance from the highest seen, in [-32768, 32767]
        delta = ((seq16 - (self._highest & 0xFFFF) + 0x8000) & 0xFFFF) - 0x8000
        extended = self._highest + delta
        if extended > self._highest:
            self._highest = extended
        return extended

    def reset(self) -> None:
        self._highest = None
