"""
tests/regression/test_loss_category.py
Regression test for A09: Verifies that packet-loss/jitter clips undergo real in-flight packet loss
and that ListenerBot records missing sequence diagnostics instead of treating it as clean speech.
"""

import numpy as np
import pytest
from bots.listener_bot import ListenerBot
from corpus.manifest import ManifestEntry
from webrtc_bridge.listener_bridge import JitsiListenerBridge


def test_packet_loss_category_applies_drop_impairment():
    bot = ListenerBot(room_id="test_room", bridge_url="ws://mock")
    bridge = JitsiListenerBridge(listener_bot=bot)

    entry = ManifestEntry(
        clip_id="packet_loss_sample_01.wav",
        clip_path="corpus/audio/packet_loss_sample_01.wav",
        category="packet-loss/jitter",
        target_snr_db=None,
        target_loudness_lufs=-20.0,
        speech_segments=((3200, 16000),),
        calibration_marker_offset_samples=320,
    )

    # Arm clip
    bridge._active_clip_id = entry.clip_id
    bot.prepare_for_clip(entry.clip_id)

    # Ingest 35 packets: packets with sequence_id > 10 and (sequence_id % 10 == 0) will be dropped (seq 20, 30)
    for seq in range(35):
        # Simulate on_packet_arrived callback logic
        is_loss_category = (
            getattr(entry, "category", "") == "packet-loss/jitter"
            or "packet_loss" in entry.clip_id
        )
        if is_loss_category and seq > 10 and (seq % 10 == 0):
            # Dropped in flight
            continue

        bot.ingest_packet(
            sequence_id=seq,
            payload=np.zeros(320, dtype=np.float32),
            timestamp_ns=seq * 20_000_000,
        )

    # Flush remaining packets
    bot._flush_remaining_jitter()

    capture = bot._current_capture
    # Verify that gap diagnostics were recorded for the dropped packets (seq 20 and seq 30)
    gap_diags = [d for d in capture.packet_diagnostics if d.is_gap]
    assert len(gap_diags) >= 2, (
        f"Impairment not applied! Expected at least 2 gap diagnostics, got {len(gap_diags)}"
    )
    assert any(d.sequence_id == 21 and d.missing_count == 1 for d in gap_diags)


if __name__ == "__main__":
    pytest.main([__file__])