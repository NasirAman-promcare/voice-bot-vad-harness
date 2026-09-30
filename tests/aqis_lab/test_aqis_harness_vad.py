"""FR-0.7-04: the harness VAD adapter wraps the existing harness WebRTC VAD (mode 2, 20 ms frames; owner decision,
question 1) without modifying harness files, and emits `speech_start` and `speech_end` events.

Expected segments are computed in the test from the `webrtcvad` package directly (not through the harness or the
adapter), on real smoke-pack clips.
"""
import json
import subprocess

import numpy as np
import pytest

from aqis_lab.adapters import base
from aqis_lab.adapters.harness_vad import HarnessVADAdapter
from aqis_lab.contracts.validate import validate_event, validate_event_lines
from aqis_adapters_testutil import samples_of, smoke_clip
from aqis_testutil import ROOT, parse_lock, probe_python_major_minor

CARD_ID = "c" * 64
CLIPS = ["ls-test-clean-1188-133604-0029", "smoke-mix-01", "smoke-noise-01", "smoke-music-02", "tts-smoke-04",
         "smoke-silence-01"]


def sink():
    return base.EventSink(run_id="run-vad-test", run_card_id=CARD_ID, host_id="cloud-vm:test")


def expected_segments(samples):
    """Speech runs of webrtcvad mode 2 over whole 20 ms frames, as (start_s, end_s)."""
    import webrtcvad
    vad = webrtcvad.Vad(2)
    segments, start = [], None
    n_frames = len(samples) // 320
    for k in range(n_frames):
        speech = vad.is_speech(samples[k * 320:(k + 1) * 320].astype("<i2").tobytes(), 16000)
        if speech and start is None:
            start = k * 320
        elif not speech and start is not None:
            segments.append([start / 16000, k * 320 / 16000])
            start = None
    if start is not None:
        segments.append([start / 16000, n_frames * 320 / 16000])
    return segments


@pytest.fixture(scope="module")
def adapter():
    a = HarnessVADAdapter()
    a.open()
    return a


def test_FR_0_7_04_model_block_names_the_harness_vad():
    block = base.check_model_block(HarnessVADAdapter().model_block())
    assert block["family"] == "harness-vad" and block["name"] == "webrtc_vad_mode2" and block["checksum"] is None
    assert block["version"] == f"webrtcvad-wheels {parse_lock()['webrtcvad-wheels']['version']}"
    s = block["settings"]
    assert s["mode"] == 2 and s["frame_size_samples"] == 320
    assert s["harness_module"] == "vad_adapters.webrtc_vad_adapter" and s["registry_name"] == "webrtc_vad_mode2"
    assert HarnessVADAdapter.component == "vad"


def test_FR_0_7_04_wraps_named_harness_vad_without_modifying_harness(adapter):
    wrapped = adapter.harness_adapter
    module_file = ROOT / "vad_adapters" / "webrtc_vad_adapter.py"
    import sys
    assert type(wrapped).__name__ == "WebRTCVADAdapter"
    assert sys.modules[type(wrapped).__module__].__file__ == str(module_file)
    assert wrapped.adapter_id == "webrtc_vad_mode2" and wrapped.frame_size_samples == 320
    status = subprocess.run(["git", "status", "--porcelain", "--", "vad_adapters"], cwd=ROOT, capture_output=True,
                            text=True, check=True)
    assert status.stdout == "", "harness files changed in the working tree"
    base_ref = subprocess.run(["git", "merge-base", "origin/main", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    assert base_ref.returncode == 0, base_ref.stderr
    changed = subprocess.run(["git", "diff", "--name-only", base_ref.stdout.strip(), "HEAD", "--", "vad_adapters"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
    assert changed.stdout == "", "this branch changed harness files"


@pytest.mark.parametrize("clip_id", CLIPS)
def test_FR_0_7_04_segments_follow_frame_decisions(adapter, clip_id):
    _, wav = smoke_clip(clip_id)
    samples = samples_of(wav)
    s = sink()
    fields = adapter.process_clip(clip_id, samples, s)
    want = expected_segments(samples)
    assert fields["segments"] == want
    assert fields["frames"] == len(samples) // 320 and fields["dropped_tail_samples"] == len(samples) % 320
    assert fields["speech_s"] == pytest.approx(sum(e - b for b, e in want))
    records = [json.loads(l) for l in s.data().splitlines()]
    boundaries = [[r["event_type"], r["audio_time_s"]] for r in records]
    assert boundaries == [x for b, e in want for x in (["speech_start", b], ["speech_end", e])]


def test_FR_0_7_04_emits_speech_start_and_speech_end(adapter):
    clip, wav = smoke_clip("ls-test-clean-1188-133604-0029")
    samples = samples_of(wav)
    s = sink()
    fields = adapter.process_clip(clip["clip_id"], samples, s)
    records = [json.loads(l) for l in s.data().splitlines()]
    assert records and len(records) % 2 == 0 and fields["segments"]
    for r in records:
        validate_event(r)
        assert r["component"] == "vad" and r["clip_id"] == clip["clip_id"] and r["payload"] == {}
    assert all(r.valid for r in validate_event_lines(s.data()))
    types = [r["event_type"] for r in records]
    assert types == ["speech_start", "speech_end"] * (len(records) // 2)
    times = [r["audio_time_s"] for r in records]
    assert times == sorted(times) and 0 <= times[0] and times[-1] <= clip["duration_s"]
    assert all(a < b for a, b in zip(times[::2], times[1::2]))


def test_FR_0_7_04_silence_gives_no_segment(adapter):
    _, wav = smoke_clip("smoke-silence-01")
    s = sink()
    fields = adapter.process_clip("smoke-silence-01", samples_of(wav), s)
    assert fields["segments"] == [] and fields["speech_s"] == 0 and fields["speech_frames"] == 0 and s.count == 0


def test_FR_0_7_04_streaming_equals_whole_clip(adapter):
    clip, wav = smoke_clip("smoke-mix-01")
    samples = samples_of(wav)
    whole = adapter.process_clip("smoke-mix-01", samples, sink())
    s = sink()
    adapter.start_clip("smoke-mix-01", s)
    for start in range(0, len(samples), 320):
        end = min(start + 320, len(samples))
        adapter.feed(samples[start:end], end / 16000, s)
    streamed = adapter.finish_clip(len(samples) / 16000, s)
    assert streamed == whole


def test_FR_0_7_04_process_before_open_is_an_error():
    with pytest.raises(base.AdapterError, match="open"):
        HarnessVADAdapter().process_clip("clip-1", np.zeros(640, dtype=np.int16), sink())


@pytest.mark.network
def test_FR_0_7_04_vad_package_has_x86_64_and_aarch64_builds(tmp_path):
    pin = f"webrtcvad-wheels=={parse_lock()['webrtcvad-wheels']['version']}"
    (tmp_path / "pin.txt").write_text(pin + "\n", encoding="utf-8")
    for platform in ("x86_64-manylinux_2_28", "aarch64-manylinux_2_28"):
        proc = subprocess.run(["uv", "pip", "compile", str(tmp_path / "pin.txt"), "--no-deps", "--only-binary",
                               ":all:", "--python-platform", platform, "--python-version", probe_python_major_minor(),
                               "--no-header", "--quiet", "-o", str(tmp_path / "out.txt")],
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, (platform, proc.stderr)
