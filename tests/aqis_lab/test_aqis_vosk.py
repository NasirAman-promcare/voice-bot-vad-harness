"""FR-0.7-02: the Vosk adapter (vosk-model-small-en-us-0.15 on CPU): model from the verified cache, fixed OpenBLAS
kernel and thread count, 20 ms feeding, `partial` and `final` events with word times.

Tests marked `network` use the real model (downloaded once per test session into a git-ignored cache and checked
against config/aqis_lab/models.yaml). Expected transcripts come from Vosk driven directly in a separate process
(not through the adapter), with the same kernel and feed size.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile

import numpy as np
import pytest

from aqis_lab.adapters import base, model_cache
from aqis_lab.adapters.vosk_stt import VoskAdapter
from aqis_lab.contracts.validate import validate_event, validate_event_lines
from aqis_adapters_testutil import SESSION_MODEL_CACHE, samples_of, smoke_clip, vosk_model
from aqis_testutil import ROOT

CARD_ID = "b" * 64
CLIP = "ls-test-clean-1188-133604-0029"          # "ONLY THERE ARE TWO SORTS OF CLOUD AND FIRE"
REFERENCE = r"""
import json, os, sys, wave
os.environ["OPENBLAS_CORETYPE"] = "Prescott"; os.environ["OPENBLAS_NUM_THREADS"] = "1"
from vosk import Model, KaldiRecognizer, SetLogLevel
SetLogLevel(-1)
rec = KaldiRecognizer(Model(sys.argv[1]), 16000); rec.SetWords(True)
w = wave.open(sys.argv[2]); data = w.readframes(w.getnframes())
texts = []
for i in range(0, len(data), 640):
    if rec.AcceptWaveform(data[i:i + 640]):
        texts.append(json.loads(rec.Result()).get("text", ""))
texts.append(json.loads(rec.FinalResult()).get("text", ""))
print(json.dumps(" ".join(t for t in texts if t)))
"""


def sink():
    return base.EventSink(run_id="run-vosk-test", run_card_id=CARD_ID, host_id="cloud-vm:test")


def reference_text(tmp_path, wav):
    path = tmp_path / "clip.wav"
    path.write_bytes(wav)
    proc = subprocess.run([sys.executable, "-c", REFERENCE, str(vosk_model()), str(path)], capture_output=True,
                          text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def in_subprocess(code, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=env,
                          timeout=300)


def test_FR_0_7_02_model_block_records_checksum_and_settings():
    adapter = VoskAdapter()
    block = base.check_model_block(adapter.model_block())
    pin = model_cache.load_pins()["vosk-model-small-en-us-0.15"]
    assert block["family"] == "vosk" and block["name"] == "vosk-model-small-en-us-0.15"
    assert block["version"] == "0.15" and block["checksum"] == pin.sha256
    s = block["settings"]
    assert s["sample_rate_hz"] == 16000 and s["feed_samples"] == 320 and s["words"] is True
    assert s["openblas_coretype"] == "Prescott" and s["openblas_num_threads"] == 1   # owner decision, question 6
    assert s["library"] == "vosk 0.3.45" and adapter.component == "live_stt"
    assert s["c_rand_seed_per_clip"] == 1        # the dither's generator, reseeded per clip (glibc's own start seed)


@pytest.mark.network
def test_FR_0_7_02_emits_partial_and_final_events_with_word_times(tmp_path):
    clip, wav = smoke_clip(CLIP)
    samples = samples_of(wav)
    adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
    adapter.open()
    s = sink()
    fields = adapter.process_clip(CLIP, samples, s)
    records = [json.loads(line) for line in s.data().splitlines()]
    for r in records:
        validate_event(r)
        assert r["component"] == "live_stt" and r["clip_id"] == CLIP
    assert all(r.valid for r in validate_event_lines(s.data()))
    partials = [r for r in records if r["event_type"] == "partial"]
    finals = [r for r in records if r["event_type"] == "final"]
    assert partials and finals and {r["event_type"] for r in records} == {"partial", "final"}
    assert all(p["payload"]["text"] for p in partials)
    texts = [p["payload"]["text"] for p in partials]
    assert all(a != b for a, b in zip(texts, texts[1:])), "a partial is written only when its text changes"
    duration = len(samples) / 16000
    words = [w for f in finals for w in f["payload"].get("words", [])]
    assert words and all(0 <= w["start_s"] <= w["end_s"] <= duration + 0.05 for w in words)
    times = [r["audio_time_s"] for r in records]
    assert times == sorted(times) and times[-1] == duration
    expected = reference_text(tmp_path, wav)
    assert fields["text"] == expected == " ".join(f["payload"]["text"] for f in finals if f["payload"]["text"])
    assert fields["text_sha256"] == hashlib.sha256(expected.encode("utf-8")).hexdigest()
    assert fields["finals"] == len(finals) and fields["partials"] == len(partials)
    assert fields["words"] == len(words) and fields["events"] == len(records) and fields["audio_s"] == duration
    assert fields["text"].startswith("only there are two sorts of cloud")


@pytest.mark.network
def test_FR_0_7_02_same_input_gives_identical_transcript():
    clip, wav = smoke_clip("ls-test-other-2609-156975-0000")
    samples = samples_of(wav)
    adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
    adapter.open()
    runs = []
    for _ in range(2):
        s = sink()
        fields = adapter.process_clip(clip["clip_id"], samples, s)
        events = [{k: v for k, v in json.loads(l).items() if k not in ("wall_time_ns", "wall_clock_utc", "seq")}
                  for l in s.data().splitlines()]
        runs.append((fields, events))
    assert runs[0] == runs[1]


@pytest.mark.network
def test_FR_0_7_02_clip_result_independent_of_earlier_clips(tmp_path):
    # Kaldi dithers the features with noise from the C library's rand(), a process-wide generator: without a fixed
    # seed per clip, a clip's result depends on everything the process computed before it. This clip showed it: 4
    # different transcripts in 20 repeats in one process (docs/progress/WP-0.7/EVIDENCE.md).
    clip, wav = smoke_clip("ls-test-other-3080-5040-0016")
    other, other_wav = smoke_clip(CLIP)
    samples, other_samples = samples_of(wav), samples_of(other_wav)
    adapter = VoskAdapter(cache_dir=SESSION_MODEL_CACHE)
    adapter.open()
    results = []
    for repeat in range(10):
        for _ in range(repeat % 3):
            adapter.process_clip(other["clip_id"], other_samples, sink())
        s = sink()
        fields = adapter.process_clip(clip["clip_id"], samples, s)
        events = [{k: v for k, v in json.loads(l).items() if k not in ("wall_time_ns", "wall_clock_utc", "seq")}
                  for l in s.data().splitlines()]
        results.append((fields, events))
    assert all(r == results[0] for r in results), [r[0]["partials"] for r in results]
    # the same as the clip computed first in a fresh process by Vosk itself
    assert results[0][0]["text"] == reference_text(tmp_path, wav)


@pytest.mark.network
def test_FR_0_7_02_openblas_kernel_pinned_and_verified():
    # The process starts with another kernel requested; the adapter still loads Vosk with its pinned kernel and
    # reads the library's active kernel back.
    vosk_model()
    code = ("from aqis_lab.adapters.vosk_stt import VoskAdapter\n"
            f"a = VoskAdapter(cache_dir={str(SESSION_MODEL_CACHE)!r}); a.open()\n"
            "from aqis_lab.adapters.vosk_stt import active_threads\n"
            "import os; print(a.kernel, active_threads(), os.environ['OPENBLAS_CORETYPE'], "
            "os.environ['OPENBLAS_NUM_THREADS'])\n")
    proc = in_subprocess(code, {"OPENBLAS_CORETYPE": "Haswell", "OPENBLAS_NUM_THREADS": "4"})
    assert proc.returncode == 0, proc.stderr
    kernel, threads, coretype, env_threads = proc.stdout.split()
    if os.uname().machine == "x86_64":
        assert kernel == "PRESCOTT"
    else:
        assert kernel == "fixed-build"
    assert threads == "1"
    # the settings apply to libvosk only: the process environment (and so its child processes) is unchanged
    assert (coretype, env_threads) == ("Haswell", "4")


def test_FR_0_7_02_refuses_when_vosk_already_loaded_with_other_kernel():
    if os.uname().machine != "x86_64":
        # The aarch64 library has no kernel dispatch, so a library loaded earlier cannot hold another kernel.
        proc = in_subprocess("import os\nos.environ['OPENBLAS_CORETYPE'] = 'Haswell'\nimport vosk\n"
                             "from aqis_lab.adapters.vosk_stt import active_kernel\nprint(active_kernel())\n")
        assert proc.returncode == 0 and proc.stdout.strip() == "fixed-build", proc.stderr
        return
    code = ("import os\nos.environ['OPENBLAS_CORETYPE'] = 'Haswell'\nimport vosk\n"
            "from aqis_lab.adapters.vosk_stt import VoskAdapter\nfrom aqis_lab.adapters.base import AdapterError\n"
            "try:\n    VoskAdapter().open()\nexcept AdapterError as exc:\n    print(exc.code); print(exc.message)\n")
    proc = in_subprocess(code)
    assert proc.returncode == 0, proc.stderr
    code_line, message = proc.stdout.splitlines()[:2]
    assert code_line == "vosk-library-loaded" and "haswell" in message.lower() and "Prescott" in message


def test_FR_0_7_01_vosk_unusable_model_emits_error_event_and_raises(tmp_path):
    # Must-catch 2 with a real library failure: files that pass their checksums but are not a Kaldi model.
    files = {"README": b"not a model\n", "am/final.mdl": b"\x00" * 64, "conf/model.conf": b"--bogus\n"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for rel, data in files.items():
            z.writestr(f"broken-model-0.1/{rel}", data)
    archive = tmp_path / "broken-model-0.1.zip"
    archive.write_bytes(buf.getvalue())
    pin = model_cache.ModelPin(name="broken-model-0.1", url=archive.as_uri(), kind="zip",
                               bytes=len(buf.getvalue()), sha256=hashlib.sha256(buf.getvalue()).hexdigest(),
                               licence="test", root="broken-model-0.1", revision=None,
                               files={k: {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)}
                                      for k, v in files.items()})
    adapter = VoskAdapter(pin=pin, cache_dir=tmp_path / "cache")
    s = sink()
    with pytest.raises(base.AdapterError) as info:
        base.guarded(adapter, s, None, "open", adapter.open)
    assert info.value.code == "vosk-open-failed"
    error = json.loads(s.data())
    validate_event(error)
    assert error["event_type"] == "error" and error["payload"]["code"] == "vosk-open-failed"
    assert error["payload"]["run_continues"] is False


@pytest.mark.network
def test_FR_0_7_02_changed_model_file_stops_vosk_open(tmp_path):
    # A verified copy of the real model whose acoustic model is then changed: open() refuses with model-checksum.
    pin = model_cache.load_pins()["vosk-model-small-en-us-0.15"]
    src = vosk_model()
    dst = tmp_path / "cache" / pin.name / src.name
    shutil.copytree(src, dst)
    target = dst / "am" / "final.mdl"
    target.chmod(0o644)
    data = bytearray(target.read_bytes())
    data[1000] ^= 0x01
    target.write_bytes(bytes(data))
    adapter = VoskAdapter(cache_dir=tmp_path / "cache")
    s = sink()
    with pytest.raises(base.AdapterError) as info:
        base.guarded(adapter, s, None, "open", adapter.open)
    assert info.value.code == "model-checksum" and "am/final.mdl" in info.value.message
    assert json.loads(s.data())["payload"]["code"] == "model-checksum"


def test_FR_0_7_02_process_before_open_is_an_error():
    adapter = VoskAdapter()
    with pytest.raises(base.AdapterError, match="open"):
        adapter.process_clip("clip-1", np.zeros(320, dtype=np.int16), sink())
