"""Frame-by-frame streaming of a clip as 20 ms packets, and the rolling-window streamer that times a CPU speech-to-text model.

CAPABILITIES:
  CAP-S2-002: frame_stream() cuts a 16-bit mono clip into frames of an exact length in samples (160 at 8 kHz, 320 at 16 kHz for
    20 ms), the last one zero padded with its valid length recorded; packetize() adds an RTP-style 16-bit sequence number and
    32-bit timestamp that wrap; reassemble() puts the valid samples back, so no sample is dropped, moved or changed
    [tests: test_s2_frame_length_follows_rate_and_duration, test_s2_frame_length_must_be_a_whole_number_of_samples,
    test_s2_frames_have_exact_length_and_amplitude, test_s2_no_sample_is_dropped_when_the_clip_ends_mid_frame,
    test_s2_reassembled_stream_equals_the_clip_for_any_length_and_rate, test_s2_frame_stream_rejects_non_int16_and_stereo_input,
    test_s2_packets_carry_rtp_style_sequence_and_timestamp]
  CAP-S2-003: RollingStreamer feeds a clip chunk by chunk and, after each chunk, decodes the trailing window with a model
    callable, timing each decode with a clock; StreamResult gives the real-time factor (total decode time over audio time),
    the chunk latency (decode time per step, p50 and p95) and the response delay (chunk length plus decode time)
    [tests: test_s2_rolling_streamer_decodes_the_trailing_window_after_each_chunk,
    test_s2_real_time_factor_is_total_compute_over_audio_duration, test_s2_rolling_streamer_flushes_a_final_partial_chunk,
    test_s2_chunk_latency_percentiles_use_linear_interpolation]
INPUTS AND OUTPUTS: int16 samples, a sample rate and a frame or chunk length in ms in; Frame, Packet and StreamResult values out;
  StreamError.
CONTRACTS: brief sections 2.2 and 3.3 (20 ms frames; chunk sizes; RTF and chunk latency).
INVARIANTS:
  - A frame holds exactly frame_length() samples and reassembling the frames of a clip gives the clip back sample for sample.
  - Timing uses only the clock it is given, so the maths is testable with a clock that moves by known amounts.
  - The brief says "20 ms (160 samples)": that holds at 8 kHz; at the lab's 16 kHz a 20 ms frame is 320 samples, and the frame
    length is always derived from the rate and the duration.
NOT IN SCOPE:
  - Speech-to-text models (aqis_lab/live/prep.py loads them for the stream stage) and the live Jitsi room: this module replays
    clips as the packet stream a room delivers, it does not join a room.
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
from dataclasses import dataclass, field

import numpy as np


class StreamError(ValueError):
    """A clip cannot be streamed as asked."""


def frame_length(sample_rate, frame_ms):
    n = sample_rate * frame_ms / 1000
    if n != int(n) or n <= 0:
        raise StreamError(f"{frame_ms} ms at {sample_rate} Hz is not a whole number of samples ({n})")
    return int(n)


@dataclass(frozen=True)
class Frame:
    seq: int
    start_sample: int
    start_ms: float
    samples: np.ndarray
    valid: int


@dataclass(frozen=True)
class Packet(Frame):
    timestamp: int = 0


def frame_stream(samples, sample_rate=16000, frame_ms=20):
    x = np.asarray(samples)
    if x.dtype != np.int16 or x.ndim != 1:
        raise StreamError(f"a clip must be one-dimensional int16, got {x.dtype} {x.shape}")
    n = frame_length(sample_rate, frame_ms)
    for seq, start in enumerate(range(0, len(x), n)):
        chunk = x[start:start + n]
        frame = np.zeros(n, dtype=np.int16)
        frame[:len(chunk)] = chunk
        yield Frame(seq=seq, start_sample=start, start_ms=1000.0 * start / sample_rate, samples=frame, valid=len(chunk))


def packetize(samples, sample_rate=16000, frame_ms=20, first_seq=0, first_timestamp=0):
    n = frame_length(sample_rate, frame_ms)
    for f in frame_stream(samples, sample_rate, frame_ms):
        yield Packet(seq=(first_seq + f.seq) % 65536, start_sample=f.start_sample, start_ms=f.start_ms, samples=f.samples,
                     valid=f.valid, timestamp=(first_timestamp + f.seq * n) % 2 ** 32)


def reassemble(frames):
    parts = [f.samples[:f.valid] for f in frames]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)


# ---- rolling-window streaming ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    end_ms: float
    chunk_ms: float
    compute_ms: float
    text: str


def _percentiles(values):
    if not values:
        return {"p50": None, "p95": None}
    return {"p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95))}


@dataclass
class StreamResult:
    steps: list = field(default_factory=list)
    audio_ms: float = 0.0

    @property
    def compute_s(self):
        return sum(s.compute_ms for s in self.steps) / 1000.0

    @property
    def rtf(self):
        return self.compute_s / (self.audio_ms / 1000.0) if self.audio_ms else None

    def chunk_latency_ms(self):
        return _percentiles([s.compute_ms for s in self.steps])

    def response_delay_ms(self):
        return _percentiles([s.chunk_ms + s.compute_ms for s in self.steps])


class RollingStreamer:
    """Feeds a clip in chunks; after each chunk decodes the trailing `window_ms` of audio with `decode(samples) -> text`.

    This is not cache-aware streaming: the model re-reads its left context at every step, which is what the live bot
    would pay per chunk with a model that is not built to carry state."""

    def __init__(self, decode, sample_rate, chunk_ms, window_ms, clock):
        self.decode, self.rate, self.chunk_ms, self.window_ms, self.clock = decode, sample_rate, chunk_ms, window_ms, clock

    def run(self, samples):
        x = np.asarray(samples)
        chunk = frame_length(self.rate, self.chunk_ms)
        window = frame_length(self.rate, self.window_ms)
        steps = []
        ends = list(range(chunk, len(x), chunk)) + ([len(x)] if len(x) else [])
        for end in ends:
            part = x[max(0, end - window):end]
            started = self.clock()
            text = self.decode(part)
            elapsed = self.clock() - started
            previous = steps[-1].end_ms if steps else 0.0
            end_ms = 1000.0 * end / self.rate
            steps.append(Step(end_ms=end_ms, chunk_ms=end_ms - previous, compute_ms=1000.0 * elapsed, text=text))
        return StreamResult(steps=steps, audio_ms=1000.0 * len(x) / self.rate)
