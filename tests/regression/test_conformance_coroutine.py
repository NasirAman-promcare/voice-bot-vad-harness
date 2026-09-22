"""
tests/regression/test_conformance_coroutine.py
Regression test for F7 & A25: Verifies that media_session.check_aiortc_conformance strictly
validates that RTCRtpReceiver._handle_rtp_packet is an async coroutine function.
"""

import inspect
import pytest
from aiortc.rtcrtpreceiver import RTCRtpReceiver
from webrtc_bridge.media_session import check_aiortc_conformance, AIORTCConformanceError
from webrtc_bridge.raw_rtp_tap import RawRtpTap


def test_conformance_check_validates_coroutine_handler(monkeypatch):
    # 1. Normal state: should pass conformance
    check_aiortc_conformance()

    # 2. Verify RawRtpTap._tap_handle_rtp_packet is an async coroutine function
    assert inspect.iscoroutinefunction(RawRtpTap._tap_handle_rtp_packet), (
        "RawRtpTap._tap_handle_rtp_packet must be an async coroutine function (F7)"
    )

    # 3. Simulate regression: replace _handle_rtp_packet with a synchronous function
    def fake_sync_handler(self, packet, arrival_time_ms=None):
        pass

    monkeypatch.setattr(RTCRtpReceiver, "_handle_rtp_packet", fake_sync_handler)

    # Must raise AIORTCConformanceError
    with pytest.raises(AIORTCConformanceError) as excinfo:
        check_aiortc_conformance()
    assert "not an async coroutine function" in str(excinfo.value)


if __name__ == "__main__":
    pytest.main([__file__])