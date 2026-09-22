"""
tests/regression/test_sequence_unwrapper.py
Regression test for F8: Verifies that RtpSequenceUnwrapper handles 16-bit RTP wraparound at 65535
and properly extends sequence numbers into a continuous monotonic counter.
"""

import pytest
from webrtc_bridge.rtp_sequence import RtpSequenceUnwrapper


def test_rtp_sequence_unwraps_past_65535():
    unwrapper = RtpSequenceUnwrapper()

    # Feed sequence numbers approaching 65535 and wrapping to 0, 1, 2
    raw_seqs = [65533, 65534, 65535, 0, 1, 2]
    unwrapped = [unwrapper.unwrap(s) for s in raw_seqs]

    expected = [65533, 65534, 65535, 65536, 65537, 65538]
    assert unwrapped == expected, f"Unwrap failed across boundary! Got {unwrapped}"


def test_rtp_sequence_handles_reordered_packets():
    unwrapper = RtpSequenceUnwrapper()

    # Initial packets
    assert unwrapper.unwrap(100) == 100
    assert unwrapper.unwrap(102) == 102
    # Out-of-order packet arriving late
    assert unwrapper.unwrap(101) == 101
    assert unwrapper.unwrap(103) == 103


def test_rtp_sequence_reset():
    unwrapper = RtpSequenceUnwrapper()
    assert unwrapper.unwrap(50000) == 50000
    assert unwrapper.unwrap(50001) == 50001

    unwrapper.reset()
    # After reset, starts fresh from new initial sequence
    assert unwrapper.unwrap(10) == 10
    assert unwrapper.unwrap(11) == 11


if __name__ == "__main__":
    pytest.main([__file__])