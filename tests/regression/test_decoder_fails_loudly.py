"""
tests/regression/test_decoder_fails_loudly.py
Regression test for A05: Verifies that missing Opus decoder fails loudly at init
and that corrupted byte packets produce silence with diagnostic records instead of raw noise.
"""

import sys
import numpy as np
import pytest
from bots.listener_bot import ListenerBot, ListenerBotError, OpusPCMDecoder


def test_missing_opuslib_fails_loudly(monkeypatch):
    """Verify that uninstalled opuslib raises ListenerBotError at decoder init."""
    monkeypatch.setitem(sys.modules, "opuslib", None)
    with pytest.raises(ListenerBotError) as excinfo:
        OpusPCMDecoder(target_sample_rate=16000)
    assert "Ensure 'opuslib' and system library 'libopus0' are installed" in str(excinfo.value)


def test_corrupt_packet_decodes_to_silence_and_diagnostic():
    """Verify that a corrupted byte payload produces 320 zeros and flags a diagnostic."""
    decoder = OpusPCMDecoder(target_sample_rate=16000)
    corrupt_payload = b"\xff\xff\xff\xff\x00\x00"

    samples, is_error = decoder.decode_chunk_to_16k(corrupt_payload)
    assert is_error is True, "Expected is_decode_error flag to be True"
    assert len(samples) == 320, f"Expected 320 samples of silence concealment, got {len(samples)}"
    assert np.all(samples == 0.0), "Expected silence array (all zeros)"

    # Test integration inside ListenerBot
    bot = ListenerBot(room_id="room", bridge_url="ws://mock")
    bot.prepare_for_clip("corrupt_test_clip")
    bot._process_single_ordered_packet(
        seq_id=1,
        arrival_ns=1000,
        raw_payload=corrupt_payload,
    )

    capture = bot._current_capture
    assert len(capture.packet_diagnostics) == 1
    assert "Corrupt packet at sequence 1" in capture.packet_diagnostics[0].message


if __name__ == "__main__":
    pytest.main([__file__])