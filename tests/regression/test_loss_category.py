"""
tests/regression/test_loss_category.py
Regression test for A09: Verifies that JitsiListenerBridge's real packet tap callback
applies 10% in-flight packet loss to packet-loss/jitter clips.
"""

import numpy as np
import pytest
from bots.listener_bot import ListenerBot
from corpus.manifest import ManifestEntry
from webrtc_bridge.listener_bridge import JitsiListenerBridge
from aiortc.rtcrtpreceiver import RTCRtpReceiver


class FakeReceiver(RTCRtpReceiver):
    """Mock receiver that exposes _handle_rtp_packet for RawRtpTap."""
    def __init__(self):
        self._track = None
    async def _handle_rtp_packet(self, packet, arrival_time_ms=None):
        pass


class FakeMediaSession:
    def __init__(self):
        self._receiver = FakeReceiver()
    def get_incoming_receiver(self):
        return self._receiver


def test_packet_loss_category_applies_drop_impairment_in_bridge():
    import concurrent.futures
    bot = ListenerBot(room_id="test_room", bridge_url="ws://mock")
    bridge = JitsiListenerBridge(listener_bot=bot)
    bridge._media_session = FakeMediaSession()


    # Mock completed future so wait_until_ready() succeeds in offline unit test
    mock_future = concurrent.futures.Future()
    mock_future.set_result(None)
    bridge._ready_future = mock_future
    bridge.is_connected = True

    entry = ManifestEntry(
        clip_id="packet_loss_sample_01.wav",
        clip_path="corpus/audio/packet_loss_sample_01.wav",
        category="packet-loss/jitter",
        target_snr_db=None,
        target_loudness_lufs=-20.0,
        speech_segments=((3200, 16000),),
        calibration_marker_offset_samples=320,
    )

    # Arm clip through real bridge method (sets up worker thread & tap callback)
    bridge.arm_clip(entry)

    tap_callback = bridge._current_tap._on_packet

    # Drive the real on_packet_arrived callback with 35 packets
    for seq in range(35):
        tap_callback(seq, np.zeros(320, dtype=np.float32).tobytes(), seq * 20_000_000)

    # Await clip completion through real bridge method
    captured_data = bridge.await_clip(entry, timeout_s=3.0)

    # Check that sequence gaps were detected and diagnostics recorded (for seq 20 and seq 30)
    gap_diags = [d for d in captured_data.packet_diagnostics if d.is_gap]
    assert len(gap_diags) >= 2, (
        f"Impairment not applied by bridge! Expected >= 2 gap diagnostics, got {len(gap_diags)}"
    )
    assert any(d.missing_count == 1 for d in gap_diags)


if __name__ == "__main__":
    pytest.main([__file__])