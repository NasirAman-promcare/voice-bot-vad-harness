"""Owner-run checks of WP-0.7 on the real machine: Parakeet Unified on the Colab T4 (OC-0.7-01). Both tests carry the
`colab` and `gpu` markers, so neither runs in the fast suite; each asserts the real result, never a stand-in. The smoke
runs on Colab and Oracle are the runbook commands (OC-0.7-01, OC-0.7-02), and parity compares their bundles
(OC-0.7-03).
"""
import json

import pytest

from aqis_lab import platform as lp
from aqis_lab.adapters import base
from aqis_lab.contracts.validate import validate_event
from aqis_adapters_testutil import samples_of, smoke_clip

SUBSET = ["ls-test-clean-3570-5695-0009", "ls-test-clean-6829-68771-0030", "ls-test-other-6128-63244-0013",
          "smoke-mix-01", "tts-smoke-04"]


def sink():
    return base.EventSink(run_id="run-live", run_card_id="9" * 64, host_id=base.host_id())


@pytest.fixture(scope="module")
def parakeet():
    from aqis_lab.adapters.parakeet_unified import ParakeetUnifiedAdapter
    adapter = ParakeetUnifiedAdapter()
    adapter.open()
    return adapter


@pytest.mark.colab
@pytest.mark.gpu
def test_FR_0_7_03_parakeet_transcribes_on_gpu(parakeet):
    assert lp.detect_platform(lp.SystemView.real()).platform == "colab"
    clip, wav = smoke_clip("ls-test-clean-3570-5695-0009")
    s = sink()
    fields = parakeet.process_clip(clip["clip_id"], samples_of(wav), s)
    final = json.loads(s.data())
    validate_event(final)
    assert final["component"] == "heavy_stt" and final["payload"]["text"] == fields["text"] and fields["text"]
    words = set(fields["text"].lower().replace(",", "").replace(".", "").split())
    reference = set(clip["transcript"].lower().split())
    assert len(words & reference) >= len(reference) // 2, (fields["text"], clip["transcript"])


@pytest.mark.colab
@pytest.mark.gpu
def test_FR_0_7_06_gpu_compute_delay_on_colab_t4(parakeet):
    assert parakeet.gpu == "Tesla T4"
    first = samples_of(smoke_clip(SUBSET[0])[1])
    parakeet.transcribe(first)                              # the untimed warm-up (owner decision, question 7)
    for clip_id in SUBSET:
        _, wav = smoke_clip(clip_id)
        fields = parakeet.process_clip_timed(clip_id, samples_of(wav), sink())
        assert fields["processing_ms"] > 0 and fields["gpu"] == "Tesla T4" and fields["text"]
        assert fields["rtf"] == pytest.approx(fields["processing_ms"] / 1000 / fields["audio_s"])
