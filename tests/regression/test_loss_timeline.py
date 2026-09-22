"""
tests/regression/test_loss_timeline.py
Regression test for A06: Verifies that lost packets insert 320 zero samples per loss,
preventing timeline compression and sample-clock drift.
"""

import numpy as np
import pytest
from bots.listener_bot import ListenerBot
from vad_adapters.adapter_contract import DecisionRecord, VADAdapterContract


class RecordingAdapter(VADAdapterContract):
    def __init__(self) -> None:
        self.offsets = []

    @property
    def adapter_id(self) -> str:
        return "recorder"

    @property
    def frame_size_samples(self) -> int:
        return 160

    @property
    def sample_rate_hz(self) -> int:
        return 16000

    def reset(self) -> None:
        self.offsets.clear()

    def process_frame(self, frame: np.ndarray, sample_offset: int, frame_index: int) -> DecisionRecord:
        self.offsets.append(sample_offset)
        return DecisionRecord(self.adapter_id, sample_offset, frame_index, is_speech=False, score=0.0)


def test_packet_loss_inserts_concealment_and_preserves_offsets():
    # Pass 1: Clean run without loss (packets 0 to 4)
    adapter_clean = RecordingAdapter()
    bot_clean = ListenerBot("room", "ws://mock", adapters={"recorder": adapter_clean})
    bot_clean.prepare_for_clip("clean_run")

    for seq in range(5):
        bot_clean.ingest_packet(seq, np.zeros(320, dtype=np.float32), timestamp_ns=seq * 20_000_000)

    # Pass 2: Lossy run (packet 2 dropped) -> sequence 0, 1, (2 lost), 3, 4
    adapter_lossy = RecordingAdapter()
    bot_lossy = ListenerBot("room", "ws://mock", adapters={"recorder": adapter_lossy})
    bot_lossy.prepare_for_clip("lossy_run")

    bot_lossy.ingest_packet(0, np.zeros(320, dtype=np.float32), timestamp_ns=0)
    bot_lossy.ingest_packet(1, np.zeros(320, dtype=np.float32), timestamp_ns=20_000_000)
    # Packet 2 is missing! Send packet 3 directly:
    bot_lossy.ingest_packet(3, np.zeros(320, dtype=np.float32), timestamp_ns=60_000_000)
    bot_lossy.ingest_packet(4, np.zeros(320, dtype=np.float32), timestamp_ns=80_000_000, is_clip_end=True)

    capture = bot_lossy.await_clip_completion("lossy_run", timeout_s=1.0)

    # Total audio buffer must equal clean run (5 * 320 = 1600 samples)
    assert len(capture.decoded_audio_16k) == 1600, (
        f"Timeline compressed: expected 1600 samples, got {len(capture.decoded_audio_16k)}"
    )

    # Verify adapter sample offsets at packet 3 and 4 match clean run exactly
    assert adapter_lossy.offsets == adapter_clean.offsets, (
        f"Offsets drifted! Clean: {adapter_clean.offsets}, Lossy: {adapter_lossy.offsets}"
    )

    # Verify a diagnostic record was generated for sequence 2
    assert len(capture.packet_diagnostics) >= 1
    assert capture.packet_diagnostics[0].missing_count == 1


if __name__ == "__main__":
    pytest.main([__file__])