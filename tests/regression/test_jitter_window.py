"""
tests/regression/test_jitter_window.py
Regression test for A13: Verifies that the jitter buffer enforces jitter_buffer_window_ms,
flushing stalled packets instead of accumulating an unbounded backlog.
"""

import numpy as np
import pytest
from bots.listener_bot import ListenerBot


def test_jitter_buffer_flushes_after_window_timeout():
    # Configure 40ms jitter buffer window
    window_ms = 40
    bot = ListenerBot(room_id="room", bridge_url="ws://mock", jitter_buffer_window_ms=window_ms)
    bot.prepare_for_clip("jitter_timeout_test")

    # Ingest packets 0..19
    for seq in range(20):
        bot.ingest_packet(
            sequence_id=seq,
            payload=np.zeros(320, dtype=np.float32),
            timestamp_ns=seq * 20_000_000,
        )

    assert len(bot._jitter_buffer) == 0, "Jitter buffer should be empty for in-order packets"

    # Skip packet 20. Ingest packet 21 with timestamp within window (10ms later)
    bot.ingest_packet(
        sequence_id=21,
        payload=np.zeros(320, dtype=np.float32),
        timestamp_ns=400_000_000 + 10_000_000,
    )
    # Packet 21 is queued waiting for packet 20
    assert 21 in bot._jitter_buffer

    # Ingest packet 22 with timestamp exceeding 40ms timeout window (400ms + 50ms)
    bot.ingest_packet(
        sequence_id=22,
        payload=np.zeros(320, dtype=np.float32),
        timestamp_ns=400_000_000 + 50_000_000,
    )

    # Window elapsed: packet 20 declared lost, backlog for 21 and 22 flushed immediately
    assert len(bot._jitter_buffer) == 0, (
        f"Backlog remained frozen! Expected empty jitter buffer, but contained {list(bot._jitter_buffer.keys())}"
    )


if __name__ == "__main__":
    pytest.main([__file__])