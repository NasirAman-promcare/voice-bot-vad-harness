"""
tests/regression/test_stateful_chunking.py
Regression test for A04: Verifies that adapters with frame sizes that do not divide 320
(such as TEN VAD with 256-sample frames) receive 100% of the audio stream via carry buffering.
"""

import numpy as np
import pytest
from bots.listener_bot import ListenerBot
from vad_adapters.adapter_contract import DecisionRecord, VADAdapterContract


class MockTenVadAdapter(VADAdapterContract):
    """Mock adapter with 256-sample native frame size."""

    def __init__(self) -> None:
        self.delivered_records = []

    @property
    def adapter_id(self) -> str:
        return "mock_ten_vad"

    @property
    def frame_size_samples(self) -> int:
        return 256

    @property
    def sample_rate_hz(self) -> int:
        return 16000

    def reset(self) -> None:
        self.delivered_records.clear()

    def process_frame(
        self,
        frame: np.ndarray,
        sample_offset: int,
        frame_index: int,
    ) -> DecisionRecord:
        assert len(frame) == 256, f"Expected 256 samples, got {len(frame)}"
        rec = DecisionRecord(
            adapter_id=self.adapter_id,
            sample_offset=sample_offset,
            frame_index=frame_index,
            is_speech=False,
            score=0.0,
        )
        self.delivered_records.append(rec)
        return rec


def test_stateful_chunking_preserves_ten_vad_audio():
    adapter = MockTenVadAdapter()
    bot = ListenerBot(
        room_id="test_room",
        bridge_url="ws://mock",
        adapters={"mock_ten_vad": adapter},
    )
    bot.prepare_for_clip("clip_chunking_test")

    # Send 250 packets of 320 samples = 80,000 total samples
    # 80,000 // 256 = 312 full frames (79,872 samples), with 128 samples remainder
    num_packets = 250
    packet_samples = 320
    total_samples = num_packets * packet_samples

    for seq in range(num_packets):
        fake_pcm = np.ones(packet_samples, dtype=np.float32) * 0.05
        bot._process_single_ordered_packet(
            seq_id=seq,
            arrival_ns=seq * 20_000_000,
            raw_payload=fake_pcm,
        )

    expected_frames = total_samples // 256  # 312 frames
    assert len(adapter.delivered_records) == expected_frames, (
        f"Expected {expected_frames} frames delivered, but got {len(adapter.delivered_records)}"
    )

    # Verify contiguous sample offsets and strictly monotonic frame indices
    for idx, rec in enumerate(adapter.delivered_records):
        assert rec.frame_index == idx, f"Frame index mismatch at frame {idx}: got {rec.frame_index}"
        assert rec.sample_offset == idx * 256, (
            f"Sample offset mismatch at frame {idx}: expected {idx * 256}, got {rec.sample_offset}"
        )


if __name__ == "__main__":
    pytest.main([__file__])