"""WP-1.2 ruler test 1: streamed frames keep exact length and amplitude and drop no samples; chunked-streaming timing maths.

Expected values are worked out from the definitions in docs/specs/sprints/WP-1.2-S2-live-stack.md sections 3.3 and 4.
"""
import numpy as np
import pytest

from aqis_lab.live import streaming


def ramp(n):
    return (np.arange(n) % 30001 - 15000).astype(np.int16)           # every value distinct from its neighbours


# ---- frames --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("rate,frame_ms,expected", [(8000, 20, 160), (16000, 20, 320), (16000, 10, 160), (48000, 20, 960)])
def test_s2_frame_length_follows_rate_and_duration(rate, frame_ms, expected):
    assert streaming.frame_length(rate, frame_ms) == expected


def test_s2_frame_length_must_be_a_whole_number_of_samples():
    with pytest.raises(streaming.StreamError, match="whole number"):
        streaming.frame_length(16000, 0.01)


def test_s2_frames_have_exact_length_and_amplitude():
    x = ramp(3200)                                                    # 200 ms at 16 kHz = 10 frames of 320
    frames = list(streaming.frame_stream(x, 16000, 20))
    assert len(frames) == 10
    for k, f in enumerate(frames):
        assert len(f.samples) == 320 and f.valid == 320 and f.samples.dtype == np.int16
        assert np.array_equal(f.samples, x[k * 320:(k + 1) * 320])    # amplitude untouched, not one sample moved
        assert f.seq == k and f.start_sample == k * 320 and f.start_ms == pytest.approx(20.0 * k)


def test_s2_no_sample_is_dropped_when_the_clip_ends_mid_frame():
    x = ramp(3200 + 100)                                              # 10 whole frames and 100 samples
    frames = list(streaming.frame_stream(x, 16000, 20))
    assert len(frames) == 11 and frames[-1].valid == 100
    assert len(frames[-1].samples) == 320 and not np.any(frames[-1].samples[100:])   # zero padded after the clip
    assert np.array_equal(streaming.reassemble(frames), x)


def test_s2_reassembled_stream_equals_the_clip_for_any_length_and_rate():
    for rate, n in ((8000, 1), (8000, 160), (8000, 161), (16000, 7777), (16000, 0)):
        x = ramp(n)
        assert np.array_equal(streaming.reassemble(streaming.frame_stream(x, rate, 20)), x)


def test_s2_frame_stream_rejects_non_int16_and_stereo_input():
    with pytest.raises(streaming.StreamError):
        list(streaming.frame_stream(np.zeros(320, dtype=np.float32), 16000, 20))
    with pytest.raises(streaming.StreamError):
        list(streaming.frame_stream(np.zeros((2, 320), dtype=np.int16), 16000, 20))


def test_s2_packets_carry_rtp_style_sequence_and_timestamp():
    x = ramp(1000)
    packets = list(streaming.packetize(x, 16000, 20, first_seq=65534, first_timestamp=4294967000))
    assert [p.seq for p in packets] == [65534, 65535, 0, 1]           # 16-bit sequence wraps
    assert [p.timestamp for p in packets] == [4294967000, (4294967000 + 320) % 2 ** 32, (4294967000 + 640) % 2 ** 32,
                                              (4294967000 + 960) % 2 ** 32]
    assert np.array_equal(streaming.reassemble(packets), x)


# ---- rolling-window streaming and its timing -----------------------------------------------------------------
class StepClock:
    """A clock that advances by a fixed time on each decode, so the timing maths has known answers."""

    def __init__(self, seconds_per_decode):
        self.now, self.step = 0.0, seconds_per_decode

    def __call__(self):
        return self.now

    def decode(self, samples):
        self.now += self.step
        return f"{len(samples)}"


def test_s2_rolling_streamer_decodes_the_trailing_window_after_each_chunk():
    clock = StepClock(0.05)
    x = ramp(16000)                                                  # 1 s
    result = streaming.RollingStreamer(clock.decode, 16000, chunk_ms=200, window_ms=600, clock=clock).run(x)
    # chunks end at 200, 400, 600, 800, 1000 ms; windows are the last 600 ms: 3200, 6400, 9600, 9600, 9600 samples
    assert [s.end_ms for s in result.steps] == [200, 400, 600, 800, 1000]
    assert [s.text for s in result.steps] == ["3200", "6400", "9600", "9600", "9600"]
    assert all(s.compute_ms == pytest.approx(50.0) for s in result.steps)


def test_s2_real_time_factor_is_total_compute_over_audio_duration():
    clock = StepClock(0.05)
    result = streaming.RollingStreamer(clock.decode, 16000, chunk_ms=200, window_ms=600, clock=clock).run(ramp(16000))
    assert result.audio_ms == 1000
    assert result.rtf == pytest.approx(5 * 0.05 / 1.0)               # 5 decodes of 50 ms over 1 s of audio
    assert result.chunk_latency_ms() == {"p50": pytest.approx(50.0), "p95": pytest.approx(50.0)}
    assert result.response_delay_ms() == {"p50": pytest.approx(250.0), "p95": pytest.approx(250.0)}   # 200 ms chunk + 50 ms


def test_s2_rolling_streamer_flushes_a_final_partial_chunk():
    clock = StepClock(0.01)
    result = streaming.RollingStreamer(clock.decode, 16000, chunk_ms=200, window_ms=10000, clock=clock).run(ramp(16000 + 800))
    assert [s.end_ms for s in result.steps] == [200, 400, 600, 800, 1000, 1050]
    assert result.audio_ms == 1050 and result.steps[-1].text == str(16800)


def test_s2_chunk_latency_percentiles_use_linear_interpolation():
    steps = [streaming.Step(end_ms=200 * (i + 1), chunk_ms=200, compute_ms=float(i + 1), text="") for i in range(100)]
    result = streaming.StreamResult(steps=steps, audio_ms=20000)
    assert result.chunk_latency_ms()["p50"] == pytest.approx(50.5) and result.chunk_latency_ms()["p95"] == pytest.approx(95.05)
