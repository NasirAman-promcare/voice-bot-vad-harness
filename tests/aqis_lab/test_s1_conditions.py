"""WP-1.1 ruler tests 2 to 4: noise at a target SNR, the phone channel and the WebRTC (Opus) channel.

Expected values come from the definitions (SNR, G.711, Opus packetisation, the seeded loss pattern), computed in this
file with its own code; the channel code under test is aqis_lab/bench/conditions.py.
"""
import math

import numpy as np
import pytest

from aqis_lab.bench import conditions, select

CONDITIONS = {
    "clean": {},
    "noise_10": {"noise": "musan-noise", "snr_db": 10},
    "noise_0": {"noise": "musan-noise", "snr_db": 0},
    "phone": {"channel": "g711_mulaw", "band_hz": [300, 3400], "fir_taps": 511, "kaiser_beta": 8.0},
    "phone_noise_10": {"noise": "musan-noise", "snr_db": 10, "channel": "g711_mulaw"},
    "webrtc": {"channel": "opus", "bitrate_bps": 16000, "frame_ms": 20, "fec": True, "loss": 0.02},
    "webrtc_noise_10": {"noise": "musan-noise", "snr_db": 10, "channel": "opus"},
    "native": {},
}
SR = 16000


def tone(freq, seconds=2.0, amplitude=10000.0):
    t = np.arange(int(seconds * SR)) / SR
    return np.round(amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def tone_amplitude(x, freq):
    """Amplitude of the sinusoid at freq in x, by projection on sine and cosine (the middle half of the signal)."""
    n = len(x)
    seg = x[n // 4: 3 * n // 4].astype(np.float64)
    t = (np.arange(n // 4, 3 * n // 4)) / SR
    c = np.sum(seg * np.cos(2 * np.pi * freq * t)) * 2 / len(seg)
    s = np.sum(seg * np.sin(2 * np.pi * freq * t)) * 2 / len(seg)
    return math.hypot(c, s)


def db(ratio):
    return 20 * math.log10(ratio)


def speech_like(seconds=10.0):
    """An amplitude-modulated harmonic signal: 150 Hz and nine harmonics, 4 Hz envelope."""
    t = np.arange(int(seconds * SR)) / SR
    carrier = sum(np.sin(2 * np.pi * 150 * k * t) / k for k in range(1, 11))
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 4 * t)
    return np.round(7000 * carrier * envelope).astype(np.int16)


def noise_signal(n, seed, amplitude=4000):
    return np.round(np.random.default_rng(seed).normal(0, amplitude, n)).astype(np.int16)


# ---- noise ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("target", [10, 0])
def test_s1_noise_achieved_snr_equals_target_within_005_db(target):
    speech, noise = speech_like(3.0), noise_signal(48000, seed=5)
    out = conditions.add_noise(speech, noise, target)
    added = out.astype(np.float64) - speech.astype(np.float64)
    measured = 10 * math.log10(np.sum(speech.astype(np.float64) ** 2) / np.sum(added ** 2))
    assert measured == pytest.approx(target, abs=0.05)


def test_s1_noise_draw_is_seeded_and_only_uses_clips_long_enough():
    lengths = {"n1": 20000, "n2": 90000, "n3": 100000, "n4": 50000}
    draw = conditions.noise_draw(7, "utt-1", lengths, 60000)
    assert draw == conditions.noise_draw(7, "utt-1", dict(reversed(list(lengths.items()))), 60000)
    assert draw.clip_id in {"n2", "n3"}
    assert 0 <= draw.offset <= lengths[draw.clip_id] - 60000
    draws = {conditions.noise_draw(7, f"utt-{i}", lengths, 60000) for i in range(40)}
    assert len({d.clip_id for d in draws}) == 2 and len({d.offset for d in draws}) > 20
    assert conditions.noise_draw(8, "utt-1", lengths, 60000) != draw


def test_s1_noise_draw_with_no_long_enough_clip_is_an_error():
    with pytest.raises(conditions.ConditionError, match="no noise clip"):
        conditions.noise_draw(1, "u", {"n1": 1000}, 5000)


def test_s1_noise_draw_is_shared_by_all_noise_conditions_of_an_utterance():
    speech = speech_like(2.0)
    pool = {"n1": noise_signal(60000, 1), "n2": noise_signal(80000, 2), "n3": noise_signal(50000, 3)}
    infos = {name: conditions.render_condition(name, CONDITIONS, speech, seed=3, utt_id="u9", noise=pool)[1]
             for name in ("noise_10", "noise_0", "phone_noise_10", "webrtc_noise_10")}
    draws = {(i["noise_clip"], i["noise_offset"]) for i in infos.values()}
    assert len(draws) == 1
    assert infos["noise_0"]["snr_db"] == 0 and infos["noise_10"]["snr_db"] == 10


def test_s1_noise_conditions_apply_noise_before_the_channel():
    speech = speech_like(2.0)
    pool = {"n1": noise_signal(60000, 1)}
    noisy, _ = conditions.render_condition("noise_10", CONDITIONS, speech, seed=3, utt_id="u9", noise=pool)
    phone_noisy, info = conditions.render_condition("phone_noise_10", CONDITIONS, speech, seed=3, utt_id="u9",
                                                    noise=pool)
    assert np.array_equal(phone_noisy, conditions.phone_channel(noisy))
    web_noisy, web_info = conditions.render_condition("webrtc_noise_10", CONDITIONS, speech, seed=3, utt_id="u9",
                                                      noise=pool)
    expected, _ = conditions.webrtc_channel(noisy, web_info["loss_seed"])
    assert np.array_equal(web_noisy, expected)


def test_s1_clean_and_native_leave_the_audio_unchanged():
    speech = speech_like(1.0)
    for name in ("clean", "native"):
        out, info = conditions.render_condition(name, CONDITIONS, speech, seed=1, utt_id="u", noise={})
        assert np.array_equal(out, speech) and info == {}


def test_s1_phone_noise_condition_uses_the_phone_condition_filter():
    cfg = dict(CONDITIONS)
    cfg["phone"] = dict(CONDITIONS["phone"], band_hz=[500, 3000])
    speech = speech_like(2.0)
    pool = {"n1": noise_signal(60000, 1)}
    noisy, _ = conditions.render_condition("noise_10", cfg, speech, seed=1, utt_id="u", noise=pool)
    got, _ = conditions.render_condition("phone_noise_10", cfg, speech, seed=1, utt_id="u", noise=pool)
    narrow = conditions.bandpass_fir(lo=500.0, hi=3000.0)
    assert np.array_equal(got, conditions.phone_channel(noisy, narrow))
    assert not np.array_equal(got, conditions.phone_channel(noisy))


def test_s1_unknown_condition_is_an_error():
    with pytest.raises(conditions.ConditionError, match="unknown condition"):
        conditions.render_condition("studio", CONDITIONS, speech_like(1.0), seed=1, utt_id="u", noise={})


# ---- phone ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("n", [16000, 16001, 24999])
def test_s1_phone_preserves_length(n):
    assert len(conditions.phone_channel(tone(1000)[:n])) == n


@pytest.mark.parametrize("freq", [1000, 3000])
def test_s1_phone_passband_tones_lose_less_than_half_a_db(freq):
    x = tone(freq)
    loss = db(tone_amplitude(x, freq) / tone_amplitude(conditions.phone_channel(x), freq))
    assert abs(loss) < 0.5


def test_s1_phone_5khz_tone_loses_at_least_50_db():
    x = tone(5000)
    out = tone_amplitude(conditions.phone_channel(x), 5000)           # the rejection is below one sample step: 0.0
    assert db(tone_amplitude(x, 5000) / max(out, 1e-12)) >= 50


def test_s1_ulaw_decode_known_codes():
    out = conditions.ulaw_decode(np.array([0x00, 0x80, 0xFF], dtype=np.uint8))
    assert out.tolist() == [-32124, 32124, 0]


def test_s1_ulaw_encode_inverts_decode_except_negative_zero():
    codes = np.arange(256, dtype=np.uint8)
    back = conditions.ulaw_encode(conditions.ulaw_decode(codes))
    expected = codes.copy()
    expected[0x7F] = 0xFF                                    # -0 and +0 decode to the same sample
    assert np.array_equal(back, expected)


def test_s1_ulaw_sqnr_is_at_least_35_db_on_a_full_scale_signal():
    t = np.arange(8000) / 8000
    x = np.round(32000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    y = conditions.ulaw_decode(conditions.ulaw_encode(x)).astype(np.float64)
    error = y - x.astype(np.float64)
    assert 10 * math.log10(np.sum(x.astype(np.float64) ** 2) / np.sum(error ** 2)) >= 35


def test_s1_bandpass_has_minus_6_db_at_the_band_edges_and_unity_in_the_band():
    h = conditions.bandpass_fir()
    assert len(h) == 511
    response = np.abs(np.fft.rfft(h, 1 << 16))
    freqs = np.fft.rfftfreq(1 << 16, 1 / SR)
    at = lambda f: response[np.argmin(np.abs(freqs - f))]
    assert db(at(300)) == pytest.approx(-6.0, abs=0.3) and db(at(3400)) == pytest.approx(-6.0, abs=0.3)
    assert db(at(1000)) == pytest.approx(0.0, abs=0.1) and db(at(3000)) == pytest.approx(0.0, abs=0.1)
    assert db(at(4000)) < -60


# ---- webrtc --------------------------------------------------------------------------------------------------
def test_s1_webrtc_same_seed_same_output_and_other_seed_other_losses():
    x = speech_like(10.0)
    a, stats_a = conditions.webrtc_channel(x, seed=21)
    b, stats_b = conditions.webrtc_channel(x, seed=21)
    c, stats_c = conditions.webrtc_channel(x, seed=22)
    assert np.array_equal(a, b) and stats_a == stats_b
    assert not np.array_equal(a, c)


def test_s1_webrtc_lost_packets_follow_the_seeded_pattern_and_fec_plus_plc_add_up():
    x = speech_like(10.0)
    for seed in (21, 22, 23):
        out, stats = conditions.webrtc_channel(x, seed=seed, loss=0.02)
        lost = np.random.default_rng(seed).random(stats["packets"]) < 0.02
        expected_fec = sum(1 for i in range(len(lost)) if lost[i] and i + 1 < len(lost) and not lost[i + 1])
        assert stats["lost"] == int(lost.sum())
        assert stats["fec"] == expected_fec
        assert stats["fec"] + stats["plc"] == stats["lost"]


def test_s1_webrtc_packet_count_covers_the_signal_plus_encoder_lookahead():
    x = speech_like(10.0)
    _, stats = conditions.webrtc_channel(x, seed=1)
    assert 500 <= stats["packets"] <= 502                    # 10 s of 20 ms frames, plus at most the lookahead frame


@pytest.mark.parametrize("n", [160000, 160001, 159999, 16123])
def test_s1_webrtc_preserves_length(n):
    x = speech_like(10.0)[:n]
    out, _ = conditions.webrtc_channel(x, seed=4)
    assert len(out) == len(x) and out.dtype == np.int16


def breathy_speech_like(seconds=10.0, seed=0):
    """The harmonic signal with a seeded noise floor under the same 4 Hz envelope: enough content to use Opus's budget."""
    t = np.arange(int(seconds * SR)) / SR
    carrier = sum(np.sin(2 * np.pi * 150 * k * t) / k for k in range(1, 11))
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 4 * t)
    noise = np.random.default_rng(seed).normal(0, 3000, len(t))
    return np.clip(np.round((7000 * carrier + noise) * envelope), -32768, 32767).astype(np.int16)


def kbps_of(x, **kwargs):
    _, stats = conditions.webrtc_channel(x, seed=1, **kwargs)
    return stats["bytes"] * 8 / (len(x) / SR) / 1000


def test_s1_webrtc_bitrate_from_packet_bytes_is_within_10_percent_of_16_kbps():
    # Opus VBR spends the whole budget only on a signal with enough content; the clean harmonic signal above codes
    # at 10 to 12 kbps, which is why this one carries a noise floor.
    for seed in (0, 1, 2):
        assert 14.4 <= kbps_of(breathy_speech_like(seed=seed), bitrate=16000) <= 17.6


def test_s1_webrtc_bitrate_follows_the_setting():
    x = breathy_speech_like()
    low, mid, high = kbps_of(x, bitrate=8000), kbps_of(x, bitrate=16000), kbps_of(x, bitrate=24000)
    assert low < mid < high
    assert 24 * 0.9 <= high <= 24 * 1.1


def test_s1_webrtc_without_loss_keeps_the_speech_aligned_with_the_input():
    x = speech_like(5.0)
    out, stats = conditions.webrtc_channel(x, seed=1, loss=0.0)
    assert stats["lost"] == 0 and stats["fec"] == 0 and stats["plc"] == 0
    a = x.astype(np.float64)
    b = out.astype(np.float64)

    def corr(lag):
        n = len(a) - 200
        return np.corrcoef(a[100:100 + n], b[100 + lag:100 + lag + n])[0, 1]

    lags = range(-80, 81)
    assert abs(max(lags, key=corr)) <= 4                    # the encoder lookahead is trimmed: at most a few samples of drift
    assert corr(0) > 0.5


# ---- non-speech clips ----------------------------------------------------------------------------------------
NS_CFG = {"n": 100, "mix": {"noise": 60, "music": 20, "silence": 20}, "level_dbfs": [-35, -15], "length_s": [3, 8]}


def _pools():
    noise = {f"noise-{i}": 16000 * (4 + i % 20) for i in range(30)}
    music = {f"music-{i}": 16000 * (5 + i % 30) for i in range(12)}
    return noise, music


def test_s1_nonspeech_plan_has_the_stated_mix_levels_and_lengths():
    noise, music = _pools()
    plan = select.plan_nonspeech(NS_CFG, noise, music, seed=5)
    kinds = [p["kind"] for p in plan]
    assert (kinds.count("noise"), kinds.count("music"), kinds.count("silence")) == (60, 20, 20)
    assert len({p["utt_id"] for p in plan}) == 100
    for p in plan:
        assert 3 * SR <= p["length"] <= 8 * SR
        if p["kind"] == "silence":
            assert p["clip_id"] is None and p["level_dbfs"] is None
        else:
            pool = noise if p["kind"] == "noise" else music
            assert -35 <= p["level_dbfs"] <= -15
            assert 0 <= p["offset"] <= pool[p["clip_id"]] - p["length"]
    assert plan == select.plan_nonspeech(NS_CFG, noise, music, seed=5)
    assert plan != select.plan_nonspeech(NS_CFG, noise, music, seed=6)


def test_s1_scale_to_dbfs_sets_the_rms_level():
    clip = noise_signal(48000, seed=3, amplitude=1500)
    for level in (-35.0, -25.0, -15.0):
        out = conditions.scale_to_dbfs(clip, level)
        rms = math.sqrt(np.mean(out.astype(np.float64) ** 2)) / 32768
        assert 20 * math.log10(rms) == pytest.approx(level, abs=0.05)
    assert not np.any(conditions.scale_to_dbfs(np.zeros(100, np.int16), -20.0))
