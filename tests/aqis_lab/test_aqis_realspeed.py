"""FR-0.7-05 (and DEBT-017): the real-speed feeder feeds 20 ms frames no faster than real time, records audio time
and wall time on every event, reports first-partial and finalisation latency, and pins itself to the reserved timing
cores on Oracle.

The fast tests drive the real harness VAD adapter (a fast CPU adapter); the latency tests drive the real Vosk model
(`network`). Expected values are computed here from the events and the definitions in docs/adapters/VOSK.md.
"""
import json
import math
import subprocess
import sys
import time

import numpy as np
import pytest

from aqis_lab.adapters import base
from aqis_lab.adapters.harness_vad import HarnessVADAdapter
from aqis_lab.contracts.validate import validate_event, validate_event_lines
from aqis_lab.realspeed import FRAME_SAMPLES, RealSpeedFeeder
from aqis_adapters_testutil import SESSION_MODEL_CACHE, samples_of, smoke_clip, tone, vosk_model
from aqis_results_testutil import cpu_list_text, oracle_system, thread_masks, usable_cpus, write_oracle_config
from aqis_testutil import ROOT

CARD_ID = "d" * 64


def sink():
    return base.EventSink(run_id="run-realspeed-test", run_card_id=CARD_ID, host_id="cloud-vm:test")


def speechy(seconds):
    """A real clip: a tone, a pause, a tone (so the VAD reports segments)."""
    third = seconds / 3
    return np.concatenate([tone(third), np.zeros(int(third * 16000), dtype=np.int16), tone(third, freq=300.0)])


@pytest.fixture(scope="module")
def vad():
    a = HarnessVADAdapter()
    a.open()
    return a


class SlowAdapter(base.StreamingAdapter):
    """A test adapter that takes 30 ms per 20 ms frame, so it cannot keep up with real time."""
    name = "slow-test"
    component = "vad"

    def model_block(self):
        return {"family": "test", "name": "slow", "version": "1", "checksum": None, "settings": {}}

    def open(self):
        self.frames = []

    def process_clip(self, clip_id, samples, sink):
        raise AssertionError("the feeder must use the streaming steps")

    def start_clip(self, clip_id, sink):
        self.frames = []

    def feed(self, frame, audio_end_s, sink):
        self.frames.append((len(frame), audio_end_s))
        time.sleep(0.03)

    def finish_clip(self, audio_end_s, sink):
        return {"frames_seen": len(self.frames)}


def expected_ends(n):
    return [min((k + 1) * FRAME_SAMPLES, n) for k in range(math.ceil(n / FRAME_SAMPLES))]


def test_FR_0_7_05_feeder_never_faster_than_real_time(vad):
    # Must-catch 5: every frame is delivered at or after the moment its last sample would exist in real time.
    samples = speechy(1.2)
    s = sink()
    feeder = RealSpeedFeeder(vad)
    fields = feeder.run_clip("tone-1", samples, s)
    ends = expected_ends(len(samples))
    assert len(feeder.deliveries) == len(ends)
    for end, (deadline, delivered) in zip(ends, feeder.deliveries):
        assert deadline - feeder.t0 == round(end * 1_000_000_000 / 16000)
        assert delivered >= deadline
    assert feeder.deliveries[-1][1] - feeder.t0 >= len(samples) * 1_000_000_000 // 16000
    assert fields["wall_s"] >= len(samples) / 16000
    for r in (json.loads(l) for l in s.data().splitlines()):
        assert r["wall_time_ns"] - feeder.t0 >= r["audio_time_s"] * 1e9 - 1


def test_FR_0_7_05_frames_are_20_ms():
    adapter = SlowAdapter()
    adapter.open()
    samples = np.zeros(16000 // 10 + 123, dtype=np.int16)          # 5 whole frames and a 123-sample tail
    RealSpeedFeeder(adapter).run_clip("short", samples, sink())
    assert [n for n, _ in adapter.frames] == [320] * 5 + [123]
    assert [t for _, t in adapter.frames] == [e / 16000 for e in expected_ends(len(samples))]


def test_FR_0_7_05_slow_adapter_frames_delivered_late_not_skipped():
    adapter = SlowAdapter()
    adapter.open()
    samples = np.zeros(16000 // 2, dtype=np.int16)                 # 25 frames, 0.5 s
    feeder = RealSpeedFeeder(adapter)
    fields = feeder.run_clip("slow", samples, sink())
    assert fields["frames_seen"] == 25 and len(adapter.frames) == 25
    lags = [delivered - deadline for deadline, delivered in feeder.deliveries]
    assert lags[-1] > 0.2e9, "a 30 ms-per-frame adapter falls further behind with every 20 ms frame"
    assert fields["max_frame_lag_ms"] == pytest.approx(max(lags) / 1e6)


def test_FR_0_7_05_audio_end_mark_and_null_latency_without_words(vad):
    samples = speechy(0.9)
    s = sink()
    fields = RealSpeedFeeder(vad).run_clip("tone-2", samples, s)
    records = [json.loads(l) for l in s.data().splitlines()]
    marks = [r for r in records if r["event_type"] == "timing_mark"]
    assert len(marks) == 1 and marks[0]["payload"] == {"mark": "audio-end"} and marks[0]["component"] == "runner"
    assert marks[0]["audio_time_s"] == len(samples) / 16000
    assert fields["first_partial_latency_ms"] is None and fields["finalisation_latency_ms"] is None
    assert all(r.valid for r in validate_event_lines(s.data()))


def _expected_latencies(records, deliveries):
    finals = [r for r in records if r["event_type"] == "final"]
    words = [w for f in finals for w in f["payload"].get("words", [])]
    partials = [r for r in records if r["event_type"] == "partial"]
    if not words:
        return None, None
    onset_frame = min(int(words[0]["start_s"] * 16000) // FRAME_SAMPLES, len(deliveries) - 1)
    first = (partials[0]["wall_time_ns"] - deliveries[onset_frame][1]) / 1e6 if partials else None
    end_mark = next(r for r in records if r["event_type"] == "timing_mark")
    return first, (finals[-1]["wall_time_ns"] - end_mark["wall_time_ns"]) / 1e6


@pytest.mark.network
def test_FR_0_7_05_every_event_has_audio_and_wall_time():
    from aqis_lab.adapters.vosk_stt import VoskAdapter
    vosk_model()
    adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
    adapter.open()
    clip, wav = smoke_clip("tts-smoke-04")
    s = sink()
    feeder = RealSpeedFeeder(adapter)
    feeder.run_clip(clip["clip_id"], samples_of(wav), s)
    records = [json.loads(l) for l in s.data().splitlines()]
    assert {"partial", "final", "timing_mark"} <= {r["event_type"] for r in records}
    for r in records:
        validate_event(r)
        assert isinstance(r["audio_time_s"], float) and r["wall_time_ns"] >= feeder.t0
        assert r["wall_time_ns"] - feeder.t0 >= r["audio_time_s"] * 1e9 - 1


@pytest.mark.network
def test_FR_0_7_05_reports_first_partial_and_finalisation_latency():
    from aqis_lab.adapters.vosk_stt import VoskAdapter
    vosk_model()
    adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
    adapter.open()
    for clip_id in ("ls-test-clean-3570-5695-0009", "smoke-silence-01"):
        clip, wav = smoke_clip(clip_id)
        s = sink()
        feeder = RealSpeedFeeder(adapter)
        fields = feeder.run_clip(clip_id, samples_of(wav), s)
        records = [json.loads(l) for l in s.data().splitlines()]
        first, final = _expected_latencies(records, feeder.deliveries)
        assert fields["first_partial_latency_ms"] == first and fields["finalisation_latency_ms"] == final
        if clip_id.startswith("ls-"):
            assert first is not None and final is not None and final >= 0 and fields["text"]
        else:
            assert first is None and final is None


def test_FR_0_7_05_feeder_pins_every_thread_to_timing_cores(tmp_path):
    # DEBT-017: the feeder pins the whole process to the reserved timing cores on Oracle (the Oracle cores test
    # double of WP-0.6); the test reads every thread's Cpus_allowed_list from outside while the feeder runs.
    cpus = usable_cpus()
    reserved = {cpus[-1]}
    config = write_oracle_config(tmp_path / "oracle.yaml", sorted(reserved))
    view = oracle_system(tmp_path)
    script = (
        "import json, sys\nfrom pathlib import Path\nimport numpy\n"
        "from aqis_lab import platform as lp\nfrom aqis_lab.adapters import base\n"
        "from aqis_lab.adapters.harness_vad import HarnessVADAdapter\nfrom aqis_lab.realspeed import RealSpeedFeeder\n"
        "root, config, env = sys.argv[1:4]\nenv = json.loads(env)\n"
        "view = lp.SystemView(root=Path(root), environ=env, path=env['PATH'])\n"
        "import threading, time\nthreading.Thread(target=time.sleep, args=(30,), daemon=True).start()\n"
        "a = HarnessVADAdapter(); a.open()\n"
        "f = RealSpeedFeeder(a, system=view, cores_config=Path(config))\n"
        "print('STARTING', flush=True)\n"
        "f.run_clip('pin-test', numpy.zeros(16000 * 3, dtype=numpy.int16), base.EventSink('run-x', 'e' * 64, 'h'))\n"
        "print('PINNING', f.pinning.describe(), flush=True)\n")
    proc = subprocess.Popen([sys.executable, "-c", script, str(view.root), str(config), json.dumps(view.environ)],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "STARTING"
        deadline = time.monotonic() + 2.0
        masks = thread_masks(proc.pid)
        while any(m != reserved for m in masks.values()) and time.monotonic() < deadline:
            time.sleep(0.02)
            masks = thread_masks(proc.pid)
        assert proc.poll() is None, "the feeder must still be running while its threads are read"
        assert len(masks) >= 2 and all(m == reserved for m in masks.values()), masks
    finally:
        out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    assert f"timing on {cpu_list_text(reserved)}" in out
