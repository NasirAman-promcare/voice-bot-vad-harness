"""Real-speed feeder: feed a clip to a streaming CPU adapter in 20 ms frames, never faster than real time (FR-0.7-05).

CAPABILITIES:
  CAP-RSPEED-001: RealSpeedFeeder.run_clip() cuts a clip into 20 ms frames (320 samples; the last part-frame as it is) and delivers frame k no earlier than t0 + (end sample of frame k) / 16 kHz on the monotonic clock, checking the clock again after every sleep; a slow adapter gets its frames late, never skipped, and the lag is recorded; a `timing_mark` `audio-end` (component runner) is written when the last frame is delivered; every event carries audio time and wall time [tests: test_FR_0_7_05_feeder_never_faster_than_real_time, test_FR_0_7_05_frames_are_20_ms, test_FR_0_7_05_slow_adapter_frames_delivered_late_not_skipped, test_FR_0_7_05_audio_end_mark_and_null_latency_without_words, test_FR_0_7_05_every_event_has_audio_and_wall_time]
  CAP-RSPEED-002: latencies() computes, from the clip's events and frame deliveries, first-partial latency (first partial event minus the delivery of the frame holding the first recognised word's start) and finalisation latency (last final event minus the audio-end mark), in milliseconds, both null when no word was recognised (owner decision, question 7); run_clip() returns them with max_frame_lag_ms and wall_s [tests: test_FR_0_7_05_reports_first_partial_and_finalisation_latency, test_FR_0_7_05_audio_end_mark_and_null_latency_without_words]
  CAP-RSPEED-003: before its first clip the feeder pins the whole process for its run mode (realspeed_cpu) with aqis_lab.timing.cores.pin_for_mode: on Oracle every thread goes to the reserved timing cores (DEBT-017) [tests: test_FR_0_7_05_feeder_pins_every_thread_to_timing_cores]
INPUTS AND OUTPUTS: a StreamingAdapter, int16 samples and an EventSink in; the adapter's result fields plus the
  latencies out; the adapter's own errors, CoreError on a pin that did not take.
CONTRACTS: event-log v1 (timing_mark payload `mark`).
INVARIANTS:
  - A frame is never delivered before its real-time deadline; frames are never skipped or merged.
  - Durations use the monotonic clock in nanoseconds.
NOT IN SCOPE:
  - Recognition itself (the adapters); running over a pack (aqis_lab/runner/).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-05 created.
"""
import time

from aqis_lab.adapters.base import SAMPLE_RATE_HZ
from aqis_lab.timing import cores

FRAME_SAMPLES = 320                     # 20 ms at 16 kHz
MODE = "realspeed_cpu"
AUDIO_END_MARK = "audio-end"


def latencies(records, deliveries):
    """(first_partial_latency_ms, finalisation_latency_ms) of one clip; both None when no word was recognised."""
    finals = [r for r in records if r["event_type"] == "final"]
    words = [w for f in finals for w in f["payload"].get("words", [])]
    if not words:
        return None, None
    partials = [r for r in records if r["event_type"] == "partial"]
    onset_frame = min(int(words[0]["start_s"] * SAMPLE_RATE_HZ) // FRAME_SAMPLES, len(deliveries) - 1)
    first = (partials[0]["wall_time_ns"] - deliveries[onset_frame][1]) / 1e6 if partials else None
    end_mark = next(r for r in records if r["event_type"] == "timing_mark" and r["payload"]["mark"] == AUDIO_END_MARK)
    return first, (finals[-1]["wall_time_ns"] - end_mark["wall_time_ns"]) / 1e6


class RealSpeedFeeder:
    """Feeds one clip at a time to a streaming adapter at real speed; `deliveries` holds (deadline, delivered) ns."""

    def __init__(self, adapter, system=None, cores_config=None, clock=time.monotonic_ns, sleep=time.sleep):
        self.adapter, self.system, self.cores_config = adapter, system, cores_config
        self.clock, self.sleep = clock, sleep
        self.pinning = None
        self.t0 = None
        self.deliveries = []

    def pin(self):
        if self.pinning is None:
            self.pinning = cores.pin_for_mode(MODE, self.system, self.cores_config)
        return self.pinning

    def run_clip(self, clip_id, samples, sink):
        self.pin()
        adapter, n = self.adapter, len(samples)
        first_event = sink.count
        adapter.start_clip(clip_id, sink)
        self.deliveries = []
        self.t0 = t0 = self.clock()
        for start in range(0, n, FRAME_SAMPLES):
            end = min(start + FRAME_SAMPLES, n)
            deadline = t0 + round(end * 1_000_000_000 / SAMPLE_RATE_HZ)
            now = self.clock()
            while now < deadline:
                self.sleep((deadline - now) / 1e9)
                now = self.clock()
            self.deliveries.append((deadline, now))
            if end == n:
                sink.emit("runner", "timing_mark", clip_id, n / SAMPLE_RATE_HZ, {"mark": AUDIO_END_MARK})
            adapter.feed(samples[start:end], end / SAMPLE_RATE_HZ, sink)
        fields = adapter.finish_clip(n / SAMPLE_RATE_HZ, sink)
        done = self.clock()
        first, final = latencies(sink.records[first_event:], self.deliveries)
        lag = max((delivered - deadline for deadline, delivered in self.deliveries), default=0)
        return {**fields, "first_partial_latency_ms": first, "finalisation_latency_ms": final,
                "max_frame_lag_ms": lag / 1e6, "wall_s": (done - t0) / 1e9}
